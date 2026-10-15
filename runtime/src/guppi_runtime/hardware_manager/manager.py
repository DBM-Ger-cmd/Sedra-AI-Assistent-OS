"""Hardware information, Captain profiles and bounded reversible adjustments."""
from ..feasibility import AdmissionUnavailable
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid

from ..util import atomic_write_json, load_json, utcnow
from .collector import NativeCollector
from .power import WindowsPowerAdapter, SCHEMES


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


BUILTINS = {
    'auto': {'label': 'Auto', 'ram_reserve_gib': 0, 'max_jobs': 4, 'cpu_thread_cap': None, 'power_plan': None},
    'balanced': {'label': 'Ausgewogen', 'ram_reserve_gib': 2, 'max_jobs': 2, 'cpu_thread_cap': None, 'power_plan': None},
    'quiet': {'label': 'Leise', 'ram_reserve_gib': 2, 'max_jobs': 1, 'cpu_thread_cap': 4, 'power_plan': None},
    'ai-sustained': {'label': 'KI-Dauerlast', 'ram_reserve_gib': 3, 'max_jobs': 1, 'cpu_thread_cap': None, 'power_plan': None},
}


class HardwareManager:
    def __init__(self, root, audit=None, collector=None, power=None):
        self.root = Path(root); self.audit = audit
        self.collector = collector or NativeCollector(root.parent)
        self.power = power or WindowsPowerAdapter()
        self.lock = threading.RLock(); self.jobs = 0
        self._sample = None; self._sample_at = 0
        self._history = []
        self._thermal = 'NORMAL'; self._cool_since = None
        self._profile_digest = None

    def inventory(self): return deepcopy(self.collector.inventory())

    def profiles(self):
        custom = load_json(self.root / 'profiles.json', {})
        out = {k: dict(v, thermal_limits=[], vendor_profile_reference=None) for k, v in BUILTINS.items()}
        for key, value in custom.items():
            out[key] = self.validate_profile(value, custom=True)
        return deepcopy(out)

    def validate_profile(self, value, custom=False):
        if not isinstance(value, dict): raise ValueError('profile_object_required')
        allowed = {'label', 'ram_reserve_gib', 'max_jobs', 'cpu_thread_cap', 'power_plan',
                   'thermal_limits', 'vendor_profile_reference', 'hardware_fingerprint'}
        if set(value) - allowed: raise ValueError('unsupported_profile_fields')
        p = deepcopy(value)
        if not isinstance(p.get('label'), str) or not 1 <= len(p['label']) <= 80:
            raise ValueError('invalid_profile_label')
        for name, low, high in [('ram_reserve_gib', 0, 128), ('max_jobs', 1, 4)]:
            v = p.get(name)
            if type(v) not in (int, float) or not math.isfinite(v) or not low <= v <= high:
                raise ValueError('invalid_' + name)
        if type(p['max_jobs']) is not int: raise ValueError('integer_max_jobs_required')
        if p.get('cpu_thread_cap') is not None and (type(p['cpu_thread_cap']) is not int or not 1 <= p['cpu_thread_cap'] <= 256):
            raise ValueError('invalid_cpu_thread_cap')
        if p.get('power_plan') not in (None, *SCHEMES): raise ValueError('unsupported_power_plan')
        p.setdefault('thermal_limits', [])
        if not isinstance(p['thermal_limits'], list) or len(p['thermal_limits']) > 16:
            raise ValueError('invalid_thermal_limits')
        for limit in p['thermal_limits']:
            if not isinstance(limit, dict) or set(limit) != {'sensor_id', 'warm', 'hot', 'critical', 'hysteresis'}:
                raise ValueError('invalid_thermal_limit_schema')
            if not isinstance(limit['sensor_id'], str) or not 1 <= len(limit['sensor_id']) <= 300:
                raise ValueError('invalid_sensor_id')
            for name in ['warm', 'hot', 'critical', 'hysteresis']:
                v = limit[name]
                if type(v) not in (int, float) or not math.isfinite(v): raise ValueError('invalid_temperature_limit')
            if not (20 <= limit['warm'] < limit['hot'] < limit['critical'] <= 120 and 1 <= limit['hysteresis'] <= 15):
                raise ValueError('invalid_threshold_order')
        ids = [r['sensor_id'] for r in p['thermal_limits']]
        if len(set(ids)) != len(ids): raise ValueError('duplicate_sensor_limit')
        ref = p.get('vendor_profile_reference')
        if ref is not None and (not isinstance(ref, str) or len(ref) > 200): raise ValueError('invalid_vendor_reference')
        if custom and p.get('hardware_fingerprint') != self.inventory()['fingerprint']:
            raise ValueError('profile_hardware_mismatch')
        return p

    def state_record(self): return load_json(self.root / 'active.json', {'profile_id': 'auto', 'status': 'active'})

    def active_profile(self):
        state = self.state_record()
        if state.get('status') != 'active': raise RuntimeError('hardware_profile_recovery_required')
        if state.get('hardware_fingerprint', self.inventory()['fingerprint']) != self.inventory()['fingerprint']:
            raise RuntimeError('active_profile_hardware_changed')
        return self.profiles()[state['profile_id']]

    @contextmanager
    def mutation(self):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / 'mutation.lock'
        try: fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError: raise RuntimeError('hardware_mutation_locked; inspect_interrupted_operation')
        try:
            os.write(fd, str(os.getpid()).encode()); os.close(fd)
            yield
        finally: path.unlink(missing_ok=True)

    def preview_profile(self, profile_id):
        profiles = self.profiles()
        if profile_id not in profiles: raise ValueError('unknown_hardware_profile')
        p = profiles[profile_id]
        caps = self.power.capabilities()
        blockers = []
        if p['power_plan'] and p['power_plan'] not in caps['profiles']:
            blockers.append('requested_power_plan_unavailable')
        plan = {'profile_id': profile_id, 'profile': p, 'hardware_fingerprint': self.inventory()['fingerprint'],
                'previous_state': self.state_record(), 'power_capabilities': caps,
                'current_power_guid': self.power.current() if p['power_plan'] and caps['read_supported'] else None,
                'blockers': blockers, 'changes': ['GUPPI admission policy and future llama.cpp starts'],
                'vendor_profile': 'manual_reference_only; no_GCC_API_verified',
                'fan_control': 'unavailable; manufacturer_remains_owner',
                'running_jobs': 'not_retuned_or_cancelled; checks_between_requests_only'}
        if p['power_plan']: plan['changes'].append('Windows active power plan')
        plan['plan_digest'] = digest(plan)
        return plan

    def save_preview(self, profile_id, profile):
        if not isinstance(profile_id, str) or not re.fullmatch(r'custom-[a-z0-9-]{1,48}', profile_id):
            raise ValueError('custom_profile_id_required')
        p = self.validate_profile(profile, custom=True)
        state = self.state_record()
        if state.get('profile_id') == profile_id or (state.get('previous_state') or {}).get('profile_id') == profile_id:
            raise ValueError('cannot_modify_active_or_restore_profile')
        plan = {'profile_id': profile_id, 'profile': p, 'existing': self.profiles().get(profile_id)}
        plan['plan_digest'] = digest(plan)
        return plan

    def save_profile(self, plan):
        with self.lock, self.mutation():
            if self.save_preview(plan['profile_id'], plan['profile']) != plan: raise ValueError('profile_changed_repreview')
            data = load_json(self.root / 'profiles.json', {})
            data[plan['profile_id']] = plan['profile']
            atomic_write_json(self.root / 'profiles.json', data)
            self.event('HARDWARE_PROFILE_SAVED', {'profile_id': plan['profile_id']})
        return {'saved': plan['profile_id']}

    def apply_profile(self, plan):
        with self.lock, self.mutation():
            if self.preview_profile(plan['profile_id']) != plan: raise ValueError('profile_changed_repreview')
            if plan['blockers']: raise ValueError('hardware_profile_blocked')
            previous = plan['previous_state']
            if previous.get('previous_state'): raise ValueError('restore_active_profile_before_replacement')
            if previous.get('status') != 'active': raise ValueError('restore_interrupted_profile_first')
            state = {'profile_id': plan['profile_id'], 'status': 'applying', 'previous_state': previous,
                     'hardware_fingerprint': self.inventory()['fingerprint'],
                     'previous_power_guid': plan['current_power_guid'], 'expected_power_guid': None,
                     'applied_at': utcnow()}
            atomic_write_json(self.root / 'active.json', state)
            try:
                if plan['profile']['power_plan']:
                    state['expected_power_guid'] = SCHEMES[plan['profile']['power_plan']]
                    atomic_write_json(self.root / 'active.json', state)
                    self.power.set_guid(state['expected_power_guid'])
                state['status'] = 'active'; atomic_write_json(self.root / 'active.json', state)
            except Exception:
                restored = False
                try:
                    if state['previous_power_guid']: self.power.set_guid(state['previous_power_guid'])
                    restored = True
                except Exception: pass
                atomic_write_json(self.root / 'active.json', previous if restored else dict(state, status='recovery_required'))
                self.event('HARDWARE_PROFILE_FAILED', {'rollback_confirmed': restored})
                raise
            self._profile_digest = None
            self.event('HARDWARE_PROFILE_APPLIED', {'profile_id': plan['profile_id'], 'digest': plan['plan_digest']})
            return state

    def rebind_preview(self):
        """What a rebind would change: the active profile and custom profiles still bound to a fingerprint of this PC's earlier state
        (after a driver or BIOS update). Limits stay as they are; only the binding moves to the current fingerprint."""
        current = self.inventory()['fingerprint']
        state = self.state_record()
        if state.get('status') != 'active': raise RuntimeError('hardware_profile_recovery_required')
        old = state.get('hardware_fingerprint')
        custom = load_json(self.root / 'profiles.json', {})
        stale = sorted(k for k, v in custom.items() if v.get('hardware_fingerprint') not in (None, current))
        state_stale = old not in (None, current)
        if not state_stale and not stale: return {'needed': False, 'hardware_fingerprint': current}
        plan = {'needed': True, 'hardware_fingerprint': current, 'previous_fingerprint': old, 'active_profile': state.get('profile_id'),
                'active_state_rebound': state_stale, 'profiles_rebound': stale,
                'display_adapters': self.inventory().get('display_adapters'), 'limits_unchanged': True}
        plan['plan_digest'] = digest(plan)
        return plan

    def rebind(self, plan):
        with self.lock, self.mutation():
            if self.rebind_preview() != plan: raise ValueError('rebind_changed_repreview')
            if not plan['needed']: return {'rebound': []}
            current = plan['hardware_fingerprint']; stamp = utcnow().replace(':', '-')
            for name in ('active.json', 'profiles.json'):
                src = self.root / name
                if src.exists(): (self.root / f'{name}.bak_{stamp}').write_bytes(src.read_bytes())
            done = []
            if plan['active_state_rebound']:
                state = self.state_record(); state['hardware_fingerprint'] = current
                atomic_write_json(self.root / 'active.json', state); done.append('active_state')
            if plan['profiles_rebound']:
                custom = load_json(self.root / 'profiles.json', {})
                for k in plan['profiles_rebound']: custom[k]['hardware_fingerprint'] = current; done.append(k)
                atomic_write_json(self.root / 'profiles.json', custom)
            self._profile_digest = None
            self.event('HARDWARE_PROFILE_REBOUND', {'from': plan['previous_fingerprint'], 'to': current, 'rebound': done, 'digest': plan['plan_digest']})
            return {'rebound': done, 'hardware_fingerprint': current}

    def restore_preview(self):
        plan = {'state': self.state_record(), 'hardware_fingerprint': self.inventory()['fingerprint']}
        state = plan['state']
        if state.get('hardware_fingerprint', plan['hardware_fingerprint']) != plan['hardware_fingerprint']:
            raise RuntimeError('restore_hardware_changed; target_PC_required')
        plan['current_power_guid'] = self.power.current() if state.get('previous_power_guid') else None
        plan['plan_digest'] = digest(plan)
        return plan

    def restore(self, plan):
        with self.lock, self.mutation():
            if self.restore_preview() != plan: raise ValueError('restore_state_changed')
            state = plan['state']
            old = state.get('previous_power_guid')
            if old:
                current = plan['current_power_guid']
                if current not in {old, state.get('expected_power_guid')}:
                    raise RuntimeError('power_plan_changed_externally; no_overwrite')
                self.power.set_guid(old)
            previous = state.get('previous_state') or {'profile_id': 'auto', 'status': 'active'}
            atomic_write_json(self.root / 'active.json', previous)
            self._profile_digest = None
            self.event('HARDWARE_PROFILE_RESTORED', {'profile_id': previous['profile_id']})
            return previous

    def event(self, kind, payload):
        if self.audit: self.audit.append(kind, component='hardware-manager', payload=payload)

    def _thermal_state(self, sample, profile):
        readings = {r['sensor_id']: r['reading'] for r in sample['sensors'] if r['type'] == 'Temperature'}
        readings.update({g['device_id'] + ':core': g['temperature_core'] for g in sample['gpus']})
        state = 'NORMAL'; ranks = {'NORMAL': 0, 'WARM': 1, 'HOT': 2, 'CRITICAL': 3}
        cool = True
        for limit in profile['thermal_limits']:
            reading = readings.get(limit['sensor_id'])
            if not reading or reading.get('state') != 'valid': return 'SENSOR_FAULT'
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(reading['timestamp'])).total_seconds()
            if not 0 <= age <= 15: return 'SENSOR_FAULT'
            value = reading['value']
            level = 'CRITICAL' if value >= limit['critical'] else 'HOT' if value >= limit['hot'] else 'WARM' if value >= limit['warm'] else 'NORMAL'
            if ranks[level] > ranks[state]: state = level
            cool &= value < limit['warm'] - limit['hysteresis']
        if not profile['thermal_limits']: return 'UNQUALIFIED'
        if state in {'HOT', 'CRITICAL'}: self._cool_since = None; return state
        if self._thermal in {'HOT', 'CRITICAL', 'SENSOR_FAULT', 'RECOVERY'}:
            if not cool: self._cool_since = None; return 'RECOVERY'
            self._cool_since = self._cool_since or time.monotonic()
            if time.monotonic() - self._cool_since < 15: return 'RECOVERY'
        return state

    def get_state(self, fresh=False):
        with self.lock:
            if fresh or self._sample is None or time.monotonic() - self._sample_at >= 2:
                sample = deepcopy(self._collect(fresh))
                try:
                    p = self.active_profile()
                    if digest(p) != self._profile_digest:
                        self._thermal = 'NORMAL'; self._cool_since = None; self._profile_digest = digest(p)
                    self._thermal = self._thermal_state(sample, p)
                    error = None
                except Exception as exc:
                    self._thermal = 'SENSOR_FAULT'; error = str(exc)
                sample.update(thermal_state=self._thermal, profile_state=self.state_record(), profile_error=error,
                              thermal_scope='admission_only; no_fan_writes; no_inflight_cancellation')
                try:
                    runs = load_json(self.root.parent / 'models' / 'benchmarks.json', {}).get('runs', {})
                    last = max(runs.values(), key=lambda r: r.get('created_at', ''), default=None)
                    sample['runtime'] = {'last_benchmark': {k: last.get(k) for k in
                        ['benchmark_id', 'created_at', 'provider', 'metrics', 'qualification']} if last else None,
                        'scope': 'completed_benchmark; not_live_token_rate'}
                except Exception:
                    sample['runtime'] = {'last_benchmark': None, 'scope': 'benchmark_data_unavailable'}
                self._sample = sample; self._sample_at = time.monotonic()
                self._history.append(deepcopy(sample)); self._history = self._history[-300:]
            return deepcopy(self._sample)

    def _collect(self, fresh):
        """`fresh` reaches the collector only if it can honour it (test doubles and older collectors take no argument)."""
        if fresh and 'fresh' in inspect.signature(self.collector.sample).parameters:
            return self.collector.sample(fresh=True)
        return self.collector.sample()

    def history(self, limit=120):
        if type(limit) is not int or not 1 <= limit <= 300: raise ValueError('invalid_history_limit')
        with self.lock: return deepcopy(self._history[-limit:])

    def capabilities(self):
        return {'native_telemetry': True, 'power_plan': self.power.capabilities(),
                'gigabyte': self.inventory()['gigabyte'],
                'fan_control': {'read_supported': 'sensor_dependent', 'write_supported': False,
                                'reason': 'no_target_qualified_adapter; manufacturer_owns_control'},
                'runtime_profile': {'write_supported': True, 'scope': 'future_managed_llama_cpp_starts'},
                'admission': {'write_supported': True, 'scope': 'GUPPI_requests; concurrency_per_runtime_instance'},
                'firmware_voltage_overclock_rgb': False}

    def preflight(self):
        sample = self.get_state(fresh=True); p = self.active_profile()
        if sample['thermal_state'] in {'HOT', 'CRITICAL', 'SENSOR_FAULT', 'RECOVERY'}:
            raise AdmissionUnavailable('THERMAL_' + sample['thermal_state'])
        mem = sample['memory']['available']
        if p['ram_reserve_gib'] and (mem['state'] != 'valid' or mem['value'] < p['ram_reserve_gib']):
            raise AdmissionUnavailable('RAM_RESERVE_UNAVAILABLE')
        return sample

    @contextmanager
    def job(self):
        with self.lock:
            self.preflight(); p = self.active_profile()
            cap = min(1, p['max_jobs']) if self._thermal == 'WARM' else p['max_jobs']
            if self.jobs >= cap: raise AdmissionUnavailable('JOB_LIMIT')
            self.jobs += 1
        try: yield
        finally:
            with self.lock: self.jobs -= 1

    def constrain_runtime_profile(self, profile):
        p = self.active_profile(); out = deepcopy(profile)
        cap = p['cpu_thread_cap']
        if cap is not None: out['cpu_threads'] = min(cap, out.get('cpu_threads') or cap)
        out['parallelism'] = min(p['max_jobs'], out.get('parallelism') or p['max_jobs'])
        out['memory_reserve_gb'] = max(p['ram_reserve_gib'], out.get('memory_reserve_gb', 0))
        return out

    def record_run(self, samples=5, interval=2):
        if type(samples) is not int or not 1 <= samples <= 300: raise ValueError('invalid_record_sample_count')
        if type(interval) not in (int, float) or not math.isfinite(interval) or not 1 <= interval <= 10:
            raise ValueError('invalid_record_interval')
        if samples * interval > 600: raise ValueError('record_budget_exceeded')
        run = {'run_id': 'HW-' + uuid.uuid4().hex, 'created_at': utcnow(), 'inventory': self.inventory(),
               'samples': [], 'status': 'recording', 'scope': 'hardware_only; benchmark_link_via_timestamps'}
        path = self.root / 'records' / (run['run_id'] + '.json')
        try:
            for i in range(samples):
                run['samples'].append(self.get_state(fresh=True)); atomic_write_json(path, run)
                if i + 1 < samples: time.sleep(interval)
            run['status'] = 'completed'
        finally:
            if run['status'] == 'recording': run['status'] = 'interrupted'
            run['finished_at'] = utcnow(); atomic_write_json(path, run)
        return {'run_id': run['run_id'], 'path': str(path), 'samples': len(run['samples']), 'status': run['status']}
