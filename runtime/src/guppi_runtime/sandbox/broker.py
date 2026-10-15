from __future__ import annotations
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid
import yaml
from ..tools.base import BaseTool, ToolValidationError
from ..util import atomic_write_json, load_json, utcnow
from ..tuning import digest, integer
from .evidence import validate_pass


class SandboxBroker(BaseTool):
    id = 'sandbox'
    version = '0.3.0'
    supported_operations = {'doctor', 'preview', 'run', 'history', 'verify', 'image_preview', 'image_import'}
    ALLOWED_SUFFIXES = {'.py', '.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.csv', '.js', '.css', '.html'}      # .js .css .html: Captain 2026-10-06, so GUPPI can build UIX windows in the DevVM (text only; the guest runs python)

    def __init__(self, root, data_root, config_path, provider, guard, audit=None):
        super().__init__(root, guard, audit)
        self.data_root = Path(data_root)
        self.config_path = Path(config_path)
        self.provider = provider

    def policy(self):
        p = yaml.safe_load(self.config_path.read_text(encoding='utf-8'))['sandbox']
        if p['backend'] != 'microsandbox' or p['sdk_version'] != '0.7.4' or p['network'] != 'deny':
            raise ToolValidationError('unsupported_sandbox_policy')
        bounds = {'cpus': (1, 4), 'memory_mib': (256, 4096), 'root_disk_mib': (32, 1024),
                  'command_timeout_seconds': (1, 120), 'job_timeout_seconds': (10, 600),
                  'cleanup_timeout_seconds': (5, 30), 'max_processes': (1, 128),
                  'max_files': (1, 500), 'max_input_bytes': (1, 8*1024*1024),
                  'max_file_bytes': (1, 2*1024*1024), 'max_export_bytes': (1, 4*1024*1024),
                  'max_log_bytes': (1024, 65536)}
        for name, (lo, hi) in bounds.items(): integer(p[name], lo, hi, name)
        if p['root_disk_mib'] > p['memory_mib'] // 2:
            raise ToolValidationError('root_tmpfs_exceeds_memory_budget')
        if type(p['target_qualified']) is not bool:
            raise ToolValidationError('target_qualification_must_be_boolean')
        if 'allow_export_dirs' in p and type(p['allow_export_dirs']) is not bool:
            raise ToolValidationError('allow_export_dirs_must_be_boolean')       # absent = off; the Captain turns it on in config/sandbox.yaml
        return p

    @staticmethod
    def relative(value, directory=False):
        if not isinstance(value, str) or not value or len(value) > 240 or '\\' in value or ':' in value or '\x00' in value:
            raise ToolValidationError('invalid_workspace_path')
        reserved = {'con', 'prn', 'aux', 'nul', 'conin$', 'conout$'} | {f'{prefix}{n}' for prefix in ('com', 'lpt') for n in range(1, 10)} | {prefix+n for prefix in ('com', 'lpt') for n in ('¹', '²', '³')}
        for part in value.split('/'):
            if part.endswith((' ', '.')) or any(ord(c) < 32 for c in part) or part.split('.')[0].lower() in reserved:
                raise ToolValidationError('unsafe_windows_filename')
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {'.', '..'} or part.startswith('.') for part in value.split('/')):
            raise ToolValidationError('protected_or_traversing_path')
        if not directory and path.suffix.lower() not in SandboxBroker.ALLOWED_SUFFIXES:
            raise ToolValidationError('unsupported_workspace_file_type')      # a directory has no file type; its files are checked one by one when they come back
        if any(word in path.name.lower() for word in ('secret', 'credential', 'password', 'token')):
            raise ToolValidationError('potential_credential_file')
        return path.as_posix()

    def snapshot(self, source, policy):
        root = self._resolve(source, must_exist=True)
        if root == self.root or not root.is_dir():
            raise ToolValidationError('explicit_project_subdirectory_required')
        files = []
        total = 0
        entries = []
        todo = [root]
        while todo:
            directory = todo.pop()
            with os.scandir(directory) as scanned:
                for entry in scanned:
                    if len(entries) >= policy['max_files'] * 8:
                        raise ToolValidationError('workspace_entry_limit')
                    child = Path(entry.path); entries.append(child)
                    if entry.is_dir(follow_symlinks=False): todo.append(child)
        for p in sorted(entries):
            rel = p.relative_to(root).as_posix()
            mode = p.lstat().st_mode
            if stat.S_ISLNK(mode): raise ToolValidationError('workspace_symlink_forbidden')
            if any(x.startswith('.') for x in p.relative_to(root).parts):
                raise ToolValidationError('workspace_hidden_entry_forbidden')
            if stat.S_ISDIR(mode): continue
            if not stat.S_ISREG(mode): raise ToolValidationError('workspace_special_file_forbidden')
            self.relative(rel)
            size = p.stat().st_size
            if size > policy['max_file_bytes']: raise ToolValidationError('input_file_limit')
            with p.open('rb') as stream: blob = stream.read(policy['max_file_bytes']+1)
            if len(blob) > policy['max_file_bytes']: raise ToolValidationError('input_file_limit')
            total += len(blob)
            if len(files) >= policy['max_files'] or total > policy['max_input_bytes']:
                raise ToolValidationError('workspace_size_limit')
            files.append({'path': rel, 'size': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()})
        if not files: raise ToolValidationError('workspace_empty')
        return files

    def preview(self, *, source, commands, exports=None, export_dirs=None):
        policy = self.policy()
        if not isinstance(source, str) or Path(source).is_absolute() or source.startswith('.'):
            raise ToolValidationError('relative_project_subdirectory_required')
        if not isinstance(commands, list) or not 1 <= len(commands) <= 5:
            raise ToolValidationError('one_to_five_guest_commands_required')
        for argv in commands:
            if not isinstance(argv, list) or not 1 <= len(argv) <= 32:
                raise ToolValidationError('invalid_guest_argv')
            if any(not isinstance(x, str) or not x or len(x) > 4096 or '\x00' in x for x in argv):
                raise ToolValidationError('invalid_guest_argument')
        exports = exports if exports is not None else []
        if not isinstance(exports, list) or len(exports) > policy['max_files']:
            raise ToolValidationError('invalid_exports')
        exports = [self.relative(x) for x in exports]
        if len(set(exports)) != len(exports): raise ToolValidationError('duplicate_exports')
        request = {'source': source, 'commands': commands, 'exports': exports}
        if export_dirs:
            # Directory export (DevVM Phase 1): the Captain approves directories instead of single files. Off unless the Captain set
            # `allow_export_dirs: true` in config/sandbox.yaml. The key stays out of the plan when unused, so existing plan digests do not change.
            if policy.get('allow_export_dirs') is not True: raise ToolValidationError('export_dirs_disabled_by_policy')
            if not isinstance(export_dirs, list) or len(export_dirs) > 8: raise ToolValidationError('invalid_export_dirs')
            export_dirs = [self.relative(x, directory=True) for x in export_dirs]
            if len(set(export_dirs)) != len(export_dirs) or any(a != b and (a + '/').startswith(b + '/') for a in export_dirs for b in export_dirs):
                raise ToolValidationError('overlapping_export_dirs')
            request['export_dirs'] = export_dirs
        plan = {'schema': 1, 'request': request,
                'policy': policy, 'files': self.snapshot(source, policy),
                'host_root': str(self.root), 'backend': 'microsandbox', 'network': 'deny'}
        plan['plan_digest'] = digest(plan)
        return deepcopy(plan)

    def validate(self, plan):
        if not isinstance(plan, dict) or not isinstance(plan.get('request'), dict):
            raise ToolValidationError('sandbox_plan_required')
        current = self.preview(**plan['request'])
        if current != plan: raise ToolValidationError('sandbox_plan_changed_repreview_required')
        return current

    def doctor(self):
        p = self.policy()
        result = self.provider.probe()
        blockers = list(result['blockers'])
        if p['target_qualified'] is not True: blockers.append('target_boundary_acceptance_pending')
        if not isinstance(p['image'], str) or not re.fullmatch(r'[^\s]+@sha256:[a-f0-9]{64}', p['image']):
            blockers.append('pinned_guest_image_missing')
        if (self.data_root / 'active.lock').exists(): blockers.append('sandbox_active_or_cleanup_pending')
        health = self.path_health()
        if (health.get('vm_path') or {}).get('ok') is False: blockers.append('vm_path_too_long')
        return {**result, 'blockers': blockers, 'execution_ready': not blockers,
                'unsafe_host_fallback': False, 'network': 'deny', 'path_health': health}

    # Set by the runtime: () -> (project_root, [{"mission_id", "host_root"}] of the open candidates). The broker knows no missions.
    path_health_source = None

    def path_health(self):
        """GUPPI's own capability capabilities/path_health (self-developed, integrated 2026-10-02): will the VM's longest path fit
        under the Windows limit, and which open candidates point at an old project folder. A too long path blocks (the VM would
        not start); stale candidates are reported only. A missing or failing capability never breaks the doctor."""
        try:
            from ..capabilities.path_health import path_health
        except ImportError:
            return {'status': 'UNAVAILABLE', 'reason': 'capability_not_integrated'}
        home = getattr(self.provider, 'home', None)
        if home is None:
            return {'status': 'UNAVAILABLE', 'reason': 'provider_has_no_backend_home'}
        try:
            from .worker import sandbox_name
            root, reports = self.path_health_source() if self.path_health_source else (str(self.root), [])
            return path_health(str(root), str(Path(home).resolve()), reports, name_length=len(sandbox_name('probe')))
        except Exception as exc:
            return {'status': 'ERROR', 'reason': f'{type(exc).__name__}:{str(exc)[:120]}'}

    def history(self):
        return [load_json(p, {}) for p in sorted(self.data_root.glob('jobs/SBX-*/report.json'))]

    def execute(self, mission_id, operation, args=None, approval_token=None):
        args = args or {}
        if operation in {'image_preview', 'image_import'}:
            from .provision import preview_image, import_image
            if operation == 'image_preview': return {'status':'completed','plan':preview_image(self, **args)}
            return import_image(self, mission_id, args.get('plan'), approval_token)
        if operation == 'doctor': return {'status': 'completed', 'sandbox': self.doctor()}
        if operation == 'preview': return {'status': 'completed', 'plan': self.preview(**args)}
        if operation == 'history': return {'status': 'completed', 'runs': self.history()}
        if operation == 'verify': return self.verify(mission_id, **args)
        if operation != 'run': raise ToolValidationError('unsupported_sandbox_operation')
        plan = self.validate(args.get('plan'))
        health = self.doctor()
        if not health['execution_ready']: return {'status': 'blocked', 'sandbox': health}
        target = 'sandbox:' + plan['plan_digest']
        verdict = self.guard.evaluate('sandbox_execute', mission_id=mission_id, target=target)
        if verdict['decision'] == 'BLOCK': return {'status': 'blocked', 'guard': verdict}
        if verdict['decision'] == 'CAPTAIN_REQUIRED':
            auth = self.guard.authorize(approval_token, mission_id=mission_id, action='sandbox_execute', target=target)
            if not auth['authorized']:
                gate = self.guard.create_gate(mission_id, 'sandbox_execute', target,
                    risks=['Execute approved commands in a private offline MicroVM; export candidate only'], rollback_available=True)
                return {'status': 'captain_required', 'gate': gate, 'guard': verdict}
        try:
            return self._run(mission_id, plan)
        except Exception as exc:
            self._audit('SANDBOX_FAILED', mission_id, {'error': str(exc)})
            return {'status': 'failed', 'error': f'{type(exc).__name__}:{exc}'}

    def _run(self, mission_id, plan):
        self.validate(plan)
        self.data_root.mkdir(parents=True, exist_ok=True)
        lock = self.data_root / 'active.lock'
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        job_id = 'SBX-' + uuid.uuid4().hex
        try:
            os.write(fd, job_id.encode()); os.close(fd)
            job = self.data_root / 'jobs' / job_id
            job.mkdir(parents=True)
            record = {'job_id': job_id, 'mission_id': mission_id, 'created_at': utcnow(),
                      'status': 'RUNNING', 'plan': plan, 'candidate': None,
                      'qualification': self.result_qualification()}
            atomic_write_json(job / 'report.json', record)
        except BaseException:
            lock.unlink(missing_ok=True)      # nothing was started yet: no VM to clean up, so the lock must not stay behind
            raise
        cleanup_confirmed = True  # No VM exists until provider launch.
        try:
            self._resolve(plan['request']['source'], must_exist=True)
            staging = job / 'input'; staging.mkdir()
            for rec in plan['files']:
                current = self._resolve(Path(plan['request']['source']) / rec['path'], must_exist=True)
                if not stat.S_ISREG(current.lstat().st_mode): raise ToolValidationError('input_changed')
                blob = current.read_bytes()
                if hashlib.sha256(blob).hexdigest() != rec['sha256']: raise ToolValidationError('input_changed')
                out = staging / rec['path']; out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(blob)
            payload = {'job_id': job_id, 'source': str(staging), 'commands': plan['request']['commands'],
                       'exports': plan['request']['exports'], 'policy': plan['policy'], 'job_root': str(job)}
            if plan['request'].get('export_dirs'): payload['export_dirs'] = plan['request']['export_dirs']
            self._audit('SANDBOX_STARTED', mission_id, {'job_id': job_id, 'plan_digest': plan['plan_digest']})
            cleanup_confirmed = False
            result = self.provider.execute(payload, job)
            if not isinstance(result, dict): raise ToolValidationError('invalid_worker_response')
            cleanup_confirmed = result.get('cleanup_confirmed') is True
            record.update({'status': result.get('status', 'FAILED'), 'commands': result.get('commands', []),
                           'error': result.get('error'), 'cleanup_confirmed': cleanup_confirmed})
            if not cleanup_confirmed:
                record['status'] = 'CLEANUP_UNCONFIRMED'
            if record['status'] == 'PASS':
                validate_pass(result, plan)
                record['candidate'] = self._candidate(job, plan, result.get('exports', []))
            return {'status': 'completed' if record['status'] == 'PASS' else 'failed', 'sandbox': record}
        except BaseException as exc:
            record.update({'status': 'FAILED' if cleanup_confirmed else 'CLEANUP_UNCONFIRMED',
                           'error': f'{type(exc).__name__}:{exc}', 'cleanup_confirmed': cleanup_confirmed})
            raise
        finally:
            record['finished_at'] = utcnow()
            atomic_write_json(job / 'report.json', record)
            if cleanup_confirmed: lock.unlink(missing_ok=True)
            self._audit('SANDBOX_FINISHED', mission_id, {'job_id': job_id, 'status': record['status'], 'cleanup_confirmed': cleanup_confirmed})

    def result_qualification(self):
        from .provider import MicrosandboxProvider
        return 'MICROVM_RESULT' if type(self.provider) is MicrosandboxProvider else 'SIMULATED_INTERFACE'

    def report_path(self, job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r'SBX-[0-9a-f]{32}', job_id):
            raise ToolValidationError('invalid_sandbox_job_id')
        path = self.data_root / 'jobs' / job_id / 'report.json'
        current = self.data_root
        for part in path.relative_to(self.data_root).parts:
            current = current / part
            if current.is_symlink(): raise ToolValidationError('sandbox_evidence_symlink')
        return path

    def receipt(self, job_id):
        path = self.report_path(job_id)
        if not path.is_file() or path.stat().st_size > 8*1024*1024:
            raise ToolValidationError('sandbox_report_missing_or_oversize')
        with path.open('rb') as stream: raw = stream.read(8*1024*1024+1)
        if len(raw) > 8*1024*1024: raise ToolValidationError('sandbox_report_oversize')
        return raw

    def verify(self, mission_id, job_id, report_sha256, plan_digest):
        try:
            raw = self.receipt(job_id)
            if hashlib.sha256(raw).hexdigest() != report_sha256:
                raise ToolValidationError('sandbox_report_integrity_failed')
            report = json.loads(raw)
            if report.get('mission_id') != mission_id or report.get('job_id') != job_id or not report.get('finished_at'):
                raise ToolValidationError('sandbox_report_identity_mismatch')
            plan = report['plan']; unsigned = deepcopy(plan); unsigned.pop('plan_digest', None)
            if plan.get('plan_digest') != plan_digest or digest(unsigned) != plan_digest:
                raise ToolValidationError('sandbox_report_plan_mismatch')
            self.validate(plan)  # Policy and candidate inputs must still match.
            validate_pass(report, plan)
            if report.get('qualification') not in {'MICROVM_RESULT', 'SIMULATED_INTERFACE'}:
                raise ToolValidationError('sandbox_result_qualification_invalid')
            candidate = report.get('candidate')
            if not isinstance(candidate, dict) or candidate.get('promotion') != 'CAPTAIN_REVIEW_REQUIRED':
                raise ToolValidationError('sandbox_candidate_manifest_invalid')
            root = self.data_root / 'jobs' / job_id / 'candidate'
            if candidate.get('path') != str(root) or root.is_symlink() or not root.is_dir():
                raise ToolValidationError('sandbox_candidate_path_invalid')
            files = candidate.get('files')
            paths = [x.get('path') for x in files] if isinstance(files, list) else None
            explicit, dirs = plan['request']['exports'], plan['request'].get('export_dirs', [])
            if paths is None or (paths != explicit if not dirs else
                                 (len(set(paths)) != len(paths) or not set(explicit) <= set(paths)
                                  or not all(p in explicit or any(str(p).startswith(d + '/') for d in dirs) for p in paths))):
                raise ToolValidationError('sandbox_export_manifest_mismatch')
            expected = set()
            for rec in files:
                rel = self.relative(rec['path']); target = root / rel
                for part in [target, *target.parents]:
                    if part == root.parent: break
                    if part.is_symlink(): raise ToolValidationError('sandbox_export_symlink')
                if not target.is_file() or target.stat().st_size > plan['policy']['max_file_bytes']:
                    raise ToolValidationError('sandbox_export_missing_or_oversize')
                with target.open('rb') as stream: blob = stream.read(plan['policy']['max_file_bytes']+1)
                if len(blob) != rec['size'] or hashlib.sha256(blob).hexdigest() != rec['sha256']:
                    raise ToolValidationError('sandbox_export_integrity_failed')
                expected.add(rel)
                expected.update(str(x) for x in PurePosixPath(rel).parents if str(x) != '.')
            todo = [root]; seen = set()
            while todo:
                directory = todo.pop()
                with os.scandir(directory) as entries:
                    for entry in entries:
                        rel = Path(entry.path).relative_to(root).as_posix()
                        if rel not in expected or entry.is_symlink():
                            raise ToolValidationError('sandbox_export_unexpected_entry')
                        seen.add(rel)
                        if entry.is_dir(follow_symlinks=False): todo.append(Path(entry.path))
                        elif not entry.is_file(follow_symlinks=False): raise ToolValidationError('sandbox_export_special_file')
            if seen != expected: raise ToolValidationError('sandbox_export_inventory_mismatch')
            return {'status': 'completed', 'verification': 'PASS', 'job_id': job_id,
                    'qualification': report['qualification'], 'plan_digest': plan_digest,
                    'report_sha256': report_sha256, 'ready_for_merge': False}
        except Exception as exc:
            return {'status': 'failed', 'verification': 'FAIL', 'ready_for_merge': False,
                    'error': f'{type(exc).__name__}:{exc}'}

    def _candidate(self, job, plan, exports):
        explicit, dirs = plan['request']['exports'], plan['request'].get('export_dirs', [])
        if not isinstance(exports, list) or len(exports) > len(explicit) + (plan['policy']['max_files'] if dirs else 0):
            raise ToolValidationError('invalid_export_response')
        total, checked, seen = 0, [], set()
        baseline = {x['path']: x['sha256'] for x in plan['files']}
        # Validate ALL untrusted data before writing any candidate file.
        for rec in exports:
            path = self.relative(rec['path'])        # file-type and name rules also apply to files that came back from an approved directory
            if (path not in explicit and not any(path.startswith(d + '/') for d in dirs)) or path in seen:
                raise ToolValidationError('export_outside_approved_scope')
            seen.add(path)
            encoded = rec['data_base64']
            if not isinstance(encoded, str) or len(encoded) > 4*plan['policy']['max_file_bytes']//3+8:
                raise ToolValidationError('export_file_limit')
            data = base64.b64decode(encoded, validate=True)
            total += len(data)
            if len(data) > plan['policy']['max_file_bytes'] or total > plan['policy']['max_export_bytes']:
                raise ToolValidationError('export_size_limit')
            checked.append((path, data))
        if not set(explicit) <= seen: raise ToolValidationError('missing_export')       # every single approved file must come back; directory files are whatever the guest holds
        candidate = job / 'candidate'; candidate.mkdir()
        manifest = []
        for path, data in checked:
            out = candidate / path; out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            manifest.append({'path': path, 'size': len(data), 'sha256': sha,
                             'change': 'unchanged' if baseline.get(path) == sha else ('modified' if path in baseline else 'added')})
        atomic_write_json(job / 'candidate-manifest.json', {'files': manifest, 'promotion': 'CAPTAIN_REVIEW_REQUIRED'})
        return {'path': str(candidate), 'files': manifest, 'promotion': 'CAPTAIN_REVIEW_REQUIRED'}
