"""Read-only native telemetry. No driver installation or arbitrary commands."""
import csv
import hashlib
import ctypes
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time
import urllib.request

from ..hardware import detect_hardware
from ..core.util import utcnow


def metric(value, unit, source, *, reason=None):
    if isinstance(value, bool) or (isinstance(value, (int, float)) and not math.isfinite(value)):
        value = None
    return {'value': value, 'unit': unit, 'source': source, 'timestamp': utcnow(),
            'state': 'valid' if value is not None else 'unavailable', 'reason': reason}


def windows_exe(name):
    # Fixed trusted system path; not an executable supplied through tool arguments.
    return str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / name)


def powershell(script, timeout=8):
    result = subprocess.run([windows_exe(r'WindowsPowerShell\v1.0\powershell.exe'),
                             '-NoLogo', '-NoProfile', '-NonInteractive', '-Command',
                             "[Console]::OutputEncoding=[Text.Encoding]::UTF8;" + script],
                            capture_output=True, text=True, encoding='utf-8',
                            timeout=timeout, shell=False)
    if result.returncode:
        raise RuntimeError('windows_query_failed')
    return json.loads(result.stdout.lstrip('\ufeff').strip())


LHM_WEB_URL = 'http://127.0.0.1:8085/data.json'     # Remote Web Server von LibreHardwareMonitor (ab 0.9.6 ohne WMI); fest, nur diese Schleife
LHM_WEB_MAX = 5 * 1024 * 1024
LHM_UNITS = {'Temperature': '°C', 'Fan': 'RPM', 'Power': 'W', 'Clock': 'MHz'}
_LHM_NUMBER = re.compile(r'-?\d+(?:[.,]\d+)?')


def lhm_web_sensors(tree):
    """Die Blätter von data.json (Temperatur, Lüfter, Leistung, Takt) in dieselbe Form wie die WMI-Zeilen. Werte stehen dort als Text mit Komma (\"35,0 °C\")."""
    rows = []
    def walk(node, depth=0):
        if not isinstance(node, dict) or depth > 12:
            return
        children = node.get('Children')
        if isinstance(children, list) and children:
            for child in children:
                walk(child, depth + 1)
            return
        kind = node.get('Type')
        if kind not in LHM_UNITS:
            return
        found = _LHM_NUMBER.search(str(node.get('Value') or ''))
        value = float(found.group().replace(',', '.')) if found else None
        rows.append({'sensor_id': str(node.get('SensorId') or ''), 'name': str(node.get('Text') or ''), 'type': kind,
                     'reading': metric(value, LHM_UNITS[kind], 'LHM.web')})
    walk(tree)
    return rows


class NativeCollector:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self._cpu_previous = None
        self._inventory = None
        self._slow = None
        self._slow_at = 0

    def inventory(self):
        if self._inventory is not None:
            return self._inventory
        snap = detect_hardware()
        data = {'hardware': snap.to_dict(), 'fingerprint': snap.fingerprint(),
                'mainboard': None, 'bios': None, 'display_adapters': [],
                'gigabyte': {'installed_products': [], 'detection_state': 'unavailable',
                             'profile_automation': 'not_verified', 'write_supported': False},
                'refresh': 'new_manager_or_process_required'}
        if os.name == 'nt':
            try:
                extra = powershell("$b=Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product,Version;"
                    "$f=Get-CimInstance Win32_BIOS | Select-Object SMBIOSBIOSVersion;"
                    "$g=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion);"
                    "$a=@(Get-ItemProperty 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
                    "'HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' "
                    "-ErrorAction SilentlyContinue | Where-Object {$_.Publisher -match 'GIGABYTE' "
                    "-or $_.DisplayName -match 'GIGABYTE|AORUS Engine'} | Select-Object DisplayName,DisplayVersion);"
                    "@{board=$b;bios=$f;gpus=$g;apps=$a}|ConvertTo-Json -Depth 5")
                data.update(mainboard=extra.get('board'), bios=extra.get('bios'),
                            display_adapters=extra.get('gpus') or [])
                data['gigabyte']['installed_products'] = extra.get('apps') or []
                data['gigabyte']['detection_state'] = 'valid'
            except Exception:
                data['gigabyte']['reason'] = 'CIM_or_registry_query_unavailable'
        elif platform.system() == 'Linux':
            def read(name):
                p = Path('/sys/class/dmi/id') / name
                try: return p.read_text().strip()
                except OSError: return None
            data['mainboard'] = {'Manufacturer': read('board_vendor'), 'Product': read('board_name'),
                                 'Version': read('board_version')}
            data['bios'] = {'SMBIOSBIOSVersion': read('bios_version')}
        binding = {k: data[k] for k in ['fingerprint', 'mainboard', 'bios', 'display_adapters', 'gigabyte']}
        data['fingerprint'] = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()[:24]
        self._inventory = data
        return data

    def _cpu(self):
        try:
            if os.name == 'nt':
                class FT(ctypes.Structure):
                    _fields_ = [('low', ctypes.c_uint32), ('high', ctypes.c_uint32)]
                idle, kernel, user = FT(), FT(), FT()
                if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                    raise OSError()
                value = lambda f: (f.high << 32) + f.low
                pair = (value(kernel) + value(user), value(idle))
                source = 'Windows.GetSystemTimes'
            else:
                fields = [int(v) for v in Path('/proc/stat').read_text().splitlines()[0].split()[1:]]
                pair = (sum(fields[:8]), fields[3] + fields[4])
                source = 'Linux.proc.stat'
            previous, self._cpu_previous = self._cpu_previous, pair
            if previous is None or pair[0] <= previous[0]:
                return metric(None, '%', source, reason='second_sample_required')
            value = 100 * (1 - (pair[1] - previous[1]) / (pair[0] - previous[0]))
            return metric(round(max(0, min(100, value)), 2), '%', source)
        except Exception:
            return metric(None, '%', 'native.cpu', reason='unsupported_or_query_failed')

    def _memory(self):
        try:
            if os.name == 'nt':
                class MEM(ctypes.Structure):
                    _fields_ = [('length', ctypes.c_uint32), ('load', ctypes.c_uint32)] + [
                        (n, ctypes.c_uint64) for n in ['total', 'available', 'page_total', 'page_available',
                                                       'virtual_total', 'virtual_available', 'extended']]
                data = MEM(); data.length = ctypes.sizeof(MEM)
                if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(data)):
                    raise OSError()
                total, available = data.total, data.available
                source = 'Windows.GlobalMemoryStatusEx'
            else:
                data = dict((k.rstrip(':'), int(v.split()[0]) * 1024)
                            for k, v in (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines()))
                total, available = data['MemTotal'], data['MemAvailable']
                source = 'Linux.proc.meminfo'
            return {k: metric(round(v / 1024**3, 3), 'GiB', source)
                    for k, v in [('total', total), ('available', available), ('used', total-available)]}
        except Exception:
            return {k: metric(None, 'GiB', 'native.memory', reason='query_failed') for k in ['total', 'available', 'used']}

    @staticmethod
    def _number(value):
        try:
            n = float(value)
            return n if math.isfinite(n) else None
        except (ValueError, TypeError): return None

    def _gpu(self):
        exe = shutil.which('nvidia-smi')
        if not exe:
            return [], 'nvidia_smi_unavailable; other_GPU_telemetry_not_implemented'
        columns = ['uuid', 'name', 'driver_version', 'temperature.gpu', 'utilization.gpu',
                   'memory.total', 'memory.used', 'fan.speed', 'power.draw']
        try:
            proc = subprocess.run([exe, '--query-gpu=' + ','.join(columns), '--format=csv,noheader,nounits'],
                                  capture_output=True, text=True, timeout=5, shell=False)
            if proc.returncode: raise OSError()
            out = []
            for row in csv.reader(io.StringIO(proc.stdout)):
                if len(row) != len(columns): continue
                row = [x.strip() for x in row]
                total, used = self._number(row[5]), self._number(row[6])
                out.append({'device_id': row[0], 'name': row[1], 'driver_version': row[2],
                    'temperature_core': metric(self._number(row[3]), '°C', 'nvidia-smi'),
                    'utilization': metric(self._number(row[4]), '%', 'nvidia-smi'),
                    'vram_total': metric(total / 1024 if total is not None else None, 'GiB', 'nvidia-smi'),
                    'vram_used': metric(used / 1024 if used is not None else None, 'GiB', 'nvidia-smi'),
                    'vram_available': metric((total-used) / 1024 if total is not None and used is not None else None, 'GiB', 'nvidia-smi'),
                    'fan_percent': metric(self._number(row[7]), '%', 'nvidia-smi', reason='not_measured_RPM'),
                    'power': metric(self._number(row[8]), 'W', 'nvidia-smi'),
                    'fan_rpm': metric(None, 'RPM', 'nvidia-smi', reason='not_available_from_this_query')})
            return out, None if out else 'no_gpu_rows'
        except Exception: return [], 'GPU_query_failed'

    def _sensors_web(self):
        with urllib.request.urlopen(LHM_WEB_URL, timeout=2) as response:      # fest verdrahtete Loopback-Adresse, keine Eingabe von aussen
            raw = response.read(LHM_WEB_MAX + 1)
        if len(raw) > LHM_WEB_MAX:
            raise ValueError('lhm_web_too_large')
        return lhm_web_sensors(json.loads(raw.decode('utf-8-sig', 'replace')))

    def _sensors(self):
        if os.name == 'nt':
            try:
                rows = self._sensors_web()                 # zuerst der Webserver: schnell und ohne PowerShell; LibreHardwareMonitor ab 0.9.6 hat kein WMI mehr
                if rows: return rows, None
            except Exception: pass
            try:
                rows = powershell("@(Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor "
                                  "-ErrorAction Stop | Where-Object {$_.SensorType -in @('Temperature','Fan','Power','Clock')} "
                                  "| Select-Object Identifier,Name,SensorType,Value)|ConvertTo-Json -Depth 3", timeout=4)
                if isinstance(rows, dict): rows = [rows]
                return [{'sensor_id': r['Identifier'], 'name': r['Name'], 'type': r['SensorType'],
                         'reading': metric(self._number(r.get('Value')), {'Temperature':'°C', 'Fan':'RPM',
                                           'Power':'W', 'Clock':'MHz'}[r['SensorType']], 'LHM.WMI')}
                        for r in rows or []], None
            except Exception: return [], 'LibreHardwareMonitor_WMI_not_running_or_not_available'
        rows = []
        for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input'):
            try:
                value = float(p.read_text()) / 1000
                label = p.with_name(p.name.replace('_input', '_label'))
                rows.append({'sensor_id': str(p), 'name': label.read_text().strip() if label.exists() else p.parent.name + '/' + p.stem,
                             'type': 'Temperature', 'reading': metric(value, '°C', 'Linux.hwmon')})
            except (OSError, ValueError): pass
        return rows, None if rows else 'native_temperature_sensors_unavailable'

    def sample(self, fresh=False):
        # GPU/WMI queries are bounded and cached; cached readings keep original timestamps.
        # `fresh` skips that cache: a binding decision right after a model was unloaded must not read the old VRAM figure.
        now = time.monotonic()
        if fresh or self._slow is None or now - self._slow_at >= 5:
            gpu, gpu_reason = self._gpu()
            sensors, sensor_reason = self._sensors()
            self._slow = (gpu, gpu_reason, sensors, sensor_reason); self._slow_at = now
        gpu, gpu_reason, sensors, sensor_reason = self._slow
        disks = []
        seen = set()
        for role, path in [('project', self.root), ('runtime', Path(__file__).resolve().parents[3])]:
            try:
                device = path.stat().st_dev
                if device in seen: continue
                seen.add(device); usage = shutil.disk_usage(path)
                disks.append({'path': str(path), 'role': role, 'total': metric(round(usage.total/1024**3, 2), 'GiB', 'disk_usage'),
                              'available': metric(round(usage.free/1024**3, 2), 'GiB', 'disk_usage')})
            except OSError: pass
        cpu, memory = self._cpu(), self._memory()
        return {'timestamp': utcnow(), 'cpu_utilization': cpu, 'memory': memory,
                'gpus': gpu, 'sensors': sensors, 'disks': disks,
                'provider_status': {'gpu': gpu_reason, 'sensors': sensor_reason},
                'scope': 'host_hardware; no_process_list_or_command_lines'}
