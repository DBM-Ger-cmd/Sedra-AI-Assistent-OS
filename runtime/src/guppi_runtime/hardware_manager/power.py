"""Bounded Windows power-plan adapter. No elevated shell or free tuning."""
import os
import re
import subprocess
from .collector import windows_exe

GUID = re.compile(r'(?i)\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b')
SCHEMES = {'balanced': '381b4222-f694-41f0-9685-ff5bb260df2e',
           'power_saver': 'a1841308-3541-4fab-bc81-f71556f20b4a'}


class WindowsPowerAdapter:
    def _run(self, *args):
        if os.name != 'nt': raise RuntimeError('Windows_power_control_unavailable')
        proc = subprocess.run([windows_exe('powercfg.exe'), *args], capture_output=True,
                              text=True, timeout=5, shell=False)
        if proc.returncode: raise RuntimeError('powercfg_failed_or_permission_denied')
        return proc.stdout

    def current(self):
        matches = GUID.findall(self._run('/getactivescheme'))
        if len(matches) != 1: raise RuntimeError('active_power_scheme_not_identified')
        return matches[0].lower()

    def available(self):
        try:
            return {x.lower() for x in GUID.findall(self._run('/list'))}
        except Exception: return set()

    def set_guid(self, guid):
        if not isinstance(guid, str) or not GUID.fullmatch(guid):
            raise ValueError('invalid_power_scheme_guid')
        if guid.lower() not in self.available(): raise RuntimeError('power_scheme_not_available')
        self._run('/setactive', guid)
        if self.current() != guid.lower(): raise RuntimeError('power_scheme_readback_failed')

    def capabilities(self):
        available = self.available()
        return {'read_supported': bool(available), 'write_supported': bool(available),
                'write_permission': 'checked_on_apply; not_target_qualified',
                'profiles': [k for k, v in SCHEMES.items() if v in available],
                'adapter': 'Windows.powercfg', 'validation_status': 'PC_ACCEPTANCE_PENDING'}
