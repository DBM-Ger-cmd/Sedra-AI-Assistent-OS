"""Bounded managed llama.cpp tuning. Preview is pure; execution is Captain-gated."""
from copy import deepcopy
from itertools import product
from pathlib import Path
import hashlib
import json
import time
import uuid

from ..util import atomic_write_json, load_json, utcnow


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid_' + name)
    return value


class TuningManager:
    AXES = {'context', 'batch_size', 'gpu_layers', 'kv_precision'}

    def __init__(self, manager):
        self.manager = manager
        self.root = manager.data_root / 'models' / 'tuning'

    def plan(self, *, model_id, profile_id=None, axes=None, max_candidates=12,
             repeats=3, warmups=1, max_tokens=128, port=18080,
             max_failures=2, budget_seconds=1800):
        integer(max_candidates, 1, 24, 'max_candidates')
        integer(repeats, 2, 4, 'repeats')
        integer(warmups, 0, 1, 'warmups')
        integer(max_tokens, 8, 256, 'max_tokens')
        integer(port, 1024, 65535, 'port')
        integer(max_failures, 1, 3, 'max_failures')
        integer(budget_seconds, 30, 3600, 'budget_seconds')
        rec = self.manager.catalog.get(model_id)
        path = self.manager.catalog._validate_path(Path(rec['path']))
        if not path.is_file() or path.suffix.lower() != '.gguf':
            raise ValueError('model_file_required')
        passed = self.manager.profile_for(profile_id, rec['size_gb'], model_id=model_id, runtime='llama-cpp-server')
        if passed['status'] != 'PASS':
            raise ValueError('base_profile_requires_review')
        base = passed['effective_profile']
        if base.get('runtime') != 'llama-cpp-server':
            raise ValueError('tuning_requires_llama_cpp_profile')
        ctx = base['context']['recommended']
        batch = base['batch_size']
        axes = deepcopy(axes if axes is not None else {
            'context': [ctx, max(512, ctx // 2)],
            'batch_size': [batch, max(16, batch // 2)],
            'gpu_layers': [base.get('gpu_layers', 0), 0],
            'kv_precision': [base.get('kv_cache', {}).get('precision', 'fp16'), 'fp16'],
        })
        if not isinstance(axes, dict) or set(axes) != self.AXES:
            raise ValueError('all_four_tuning_axes_required')
        for name, values in axes.items():
            if not isinstance(values, list) or not 1 <= len(values) <= 4:
                raise ValueError('invalid_axis_length')
            for value in values:
                if name == 'context': integer(value, 512, base['context']['maximum'], name)
                if name == 'batch_size': integer(value, 16, 1024, name)
                if name == 'gpu_layers' and value != 'auto': integer(value, 0, 999, name)
                if name == 'kv_precision' and value not in {'fp16', 'q8_0'}:
                    raise ValueError('unsupported_kv_precision')
        # Cartesian enumeration is hard bounded, even before truncation.
        if len(list(product(*axes.values()))) > 128:
            raise ValueError('matrix_too_large')
        request = dict(model_id=model_id, profile_id=profile_id, axes=axes,
                       max_candidates=max_candidates, repeats=repeats, warmups=warmups,
                       max_tokens=max_tokens, port=port, max_failures=max_failures,
                       budget_seconds=budget_seconds)
        candidates, seen = [], set()
        names = sorted(self.AXES)
        for values in product(*(axes[n] for n in names)):
            variant = dict(zip(names, values))
            profile = deepcopy(base)
            profile['context']['recommended'] = variant['context']
            profile['batch_size'] = variant['batch_size']
            profile['microbatch_size'] = min(base['microbatch_size'], variant['batch_size'])
            profile['gpu_layers'] = variant['gpu_layers']
            profile.setdefault('kv_cache', {})['precision'] = variant['kv_precision']
            result = self.manager.hardware_pass.evaluate(profile, model_size_gb=rec['size_gb'])
            effective = result['effective_profile']
            key = digest(effective)
            if result['status'] != 'PASS' or key in seen:
                continue
            seen.add(key)
            candidates.append({'candidate_id': 'TC-' + key[:16], 'profile': effective})
        total = len(candidates)
        plan = {'schema': 1, 'provider': 'llama-cpp-server', 'request': request,
                'hardware_fingerprint': self.manager.hardware.fingerprint(),
                'model_sha256': file_digest(path), 'base_profile': base,
                'benchmark_policy': deepcopy(self.manager.benchmark.policy),
                'candidates': candidates[:max_candidates], 'eligible_count': total,
                'truncated': total > max_candidates,
                'measurement_scope': 'short_prompt_smoke_throughput; not full-context or VRAM qualification'}
        if not plan['candidates']:
            raise ValueError('no_eligible_candidates')
        plan['plan_digest'] = digest(plan)
        return plan

    def validate(self, plan):
        if not isinstance(plan, dict) or not isinstance(plan.get('request'), dict):
            raise ValueError('tuning_plan_required')
        rebuilt = self.plan(**plan['request'])
        if rebuilt != plan:
            raise ValueError('tuning_plan_changed_replan_required')
        return rebuilt

    def history(self):
        if not self.root.exists(): return []
        return [load_json(p, {}) for p in sorted(self.root.glob('TR-*.json'))]

    def run(self, plan):
        # Called only behind ModelRuntimeTool's exact digest Captain gate.
        plan = self.validate(plan)
        ctl = self.manager.controller('llama-cpp-server')
        if ctl.status().get('managed_running'):
            raise RuntimeError('managed_runtime_already_running')
        request = plan['request']
        record = {'run_id': 'TR-' + uuid.uuid4().hex, 'created_at': utcnow(),
                  'status': 'RUNNING', 'plan': plan, 'results': [], 'recommended_benchmark_id': None}
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / (record['run_id'] + '.json')
        atomic_write_json(path, record)
        started = time.monotonic()
        failures = 0
        try:
            for candidate in plan['candidates']:
                if time.monotonic() - started >= request['budget_seconds']:
                    record['status'] = 'BUDGET_EXHAUSTED'; break
                if failures >= request['max_failures']:
                    record['status'] = 'FAILURE_LIMIT'; break
                try:
                    bm = self.manager.benchmark.benchmark_managed_llamacpp(
                        model_id=request['model_id'], profile_id=request['profile_id'],
                        profile_override=candidate['profile'], repeats=request['repeats'],
                        warmups=request['warmups'], max_tokens=request['max_tokens'],
                        port=request['port'], keep_running=False)
                    item = {'candidate_id': candidate['candidate_id'], 'benchmark_id': bm['benchmark_id'],
                            'status': bm['qualification']['status'], 'metrics': bm['metrics']}
                    if item['status'] != 'PASS': failures += 1
                except Exception as exc:
                    failures += 1
                    item = {'candidate_id': candidate['candidate_id'], 'status': 'ERROR',
                            'error': f'{type(exc).__name__}:{exc}'}
                record['results'].append(item)
                atomic_write_json(path, record)
            else:
                record['status'] = 'COMPLETED'
        except BaseException:
            record['status'] = 'INTERRUPTED'
            raise
        finally:
            passed = [x for x in record['results'] if x['status'] == 'PASS']
            # Never rank estimated token counts against exact provider counts.
            eligible = []
            for item in passed:
                samples = self.manager.benchmark.store.get(item['benchmark_id']).get('samples', [])
                if samples and all(s.get('tokens_estimated') is False for s in samples):
                    eligible.append(item)
            if eligible:
                winner = max(eligible, key=lambda x: (x['metrics']['median_tokens_per_second'], x['candidate_id']))
                record['recommended_benchmark_id'] = winner['benchmark_id']
            record['finished_at'] = utcnow()
            atomic_write_json(path, record)
            if self.manager.audit:
                self.manager.audit.append('MODEL_TUNING_COMPLETED', component='model-tuning',
                                          payload={'run_id': record['run_id'], 'status': record['status']})
        return record
