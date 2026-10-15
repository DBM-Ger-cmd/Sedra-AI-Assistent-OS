from __future__ import annotations
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


class MicrosandboxProvider:
    """Launch the pinned SDK in a sanitized child; never execute guest argv on host."""
    def __init__(self, home: Path, runtime_root: Path):
        self.home = Path(home)
        self.runtime_root = Path(runtime_root)
        self.worker = Path(__file__).with_name('worker.py')

    def environment(self, job_root):
        # Do not forward HOME, tokens, cloud selection, Python hooks or proxy settings.
        # System-wide Windows folders (no user data, no secrets): the native SDK refuses to start without them
        # ("cannot resolve ProgramData"), measured on the Captain's PC on 2026-10-02.
        system_dirs = ('SYSTEMROOT', 'WINDIR', 'SYSTEMDRIVE', 'PROGRAMDATA', 'ALLUSERSPROFILE', 'PUBLIC')
        env = {key: os.environ[key] for key in system_dirs if key in os.environ}
        local_home = str(Path(job_root).resolve())
        env.update({'HOME': local_home, 'USERPROFILE': local_home,
                    'APPDATA': local_home, 'LOCALAPPDATA': local_home,
                    'TMP': local_home, 'TEMP': local_home, 'TMPDIR': local_home,
                    'MSB_HOME': str(self.home.resolve()), 'MSB_BACKEND': 'local',
                    'PYTHONNOUSERSITE': '1', 'LANG': 'C.UTF-8'})
        return env

    def _command(self, mode, request, result):
        return [sys.executable, '-I', '-B', str(self.worker), mode, str(request), str(result)]

    def probe(self):
        reasons = []
        system = platform.system()
        if system == 'Linux' and not os.access('/dev/kvm', os.R_OK | os.W_OK):
            reasons.append('kvm_unavailable')
        elif system not in {'Linux', 'Windows', 'Darwin'}:
            reasons.append('unsupported_platform')
        # Platform capabilities alone never count as isolation qualification.
        import importlib.metadata
        try:
            installed = importlib.metadata.version('microsandbox')
        except importlib.metadata.PackageNotFoundError:
            installed = None
        if installed != '0.7.4': reasons.append('pinned_sdk_not_installed')
        return {'backend': 'microsandbox', 'sdk_version': installed,
                'host': system, 'blockers': reasons, 'vm_boundary_tested': False}

    def execute(self, request: dict, job_root: Path):
        return self._execute_worker('run',request,job_root)

    def import_image(self, request: dict, job_root: Path):
        return self._execute_worker('import_image',request,job_root)

    def _execute_worker(self, mode, request, job_root):
        request_path = job_root / 'worker-request.json'
        result_path = job_root / 'worker-result.json'
        request_path.write_text(json.dumps(request), encoding='utf-8')
        self.home.mkdir(parents=True, exist_ok=True)
        kwargs = dict(env=self.environment(job_root), cwd=job_root,
                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL, shell=False)
        if os.name != 'nt': kwargs['start_new_session'] = True
        proc = subprocess.Popen(self._command(mode, request_path, result_path), **kwargs)
        cleanup_timeout=request.get('policy',{}).get('cleanup_timeout_seconds',15)
        deadline = request.get('policy',{}).get('job_timeout_seconds',300) + cleanup_timeout + 10
        try:
            proc.wait(timeout=deadline)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            (job_root / 'cancel').touch()
            try:
                proc.wait(timeout=cleanup_timeout + 5)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=5)
            # Killing launcher is not evidence that the owned VM stopped.
            return {'status': 'CLEANUP_UNCONFIRMED', 'error': 'supervisor_timeout_or_cancel',
                    'cleanup_confirmed': False, 'exports': [], 'commands': []}
        if not result_path.is_file() or result_path.stat().st_size > 8 * 1024 * 1024:
            return {'status': 'CLEANUP_UNCONFIRMED', 'error': 'worker_result_missing_or_oversize',
                    'cleanup_confirmed': False, 'exports': [], 'commands': []}
        return json.loads(result_path.read_text(encoding='utf-8'))
