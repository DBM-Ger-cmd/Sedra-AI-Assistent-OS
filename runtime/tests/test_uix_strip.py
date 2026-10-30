"""`/api/strip` für den Statusbereich der Harness-Shell (SPEC_HARNESS_SHELL_v1 HS-32, G2 Stufe 4 §5, G3 N2): RAM, Modellserver,
Scheduler und die GPU-Zelle mit Temperatur aus der Probe des Hardware-Managers. Keine eigene Messung: `strip_view` ruft nie
`nvidia-smi` oder PowerShell – die Attrappe des Hardware-Managers zählt mit."""
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.uix_server import UIXHub

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'


def m(value, unit='°C'):
    return {'value': value, 'unit': unit, 'source': 'test', 'state': 'valid' if value is not None else 'unavailable'}


class Attrappe:
    """Der Hardware-Manager, wie ihn `strip_view` sieht: nur `get_state()`. `aufrufe` zählt, `probe` ist die Antwort."""
    def __init__(self, probe):
        self.probe, self.aufrufe = probe, 0

    def get_state(self, fresh=False):
        self.aufrufe += 1
        if isinstance(self.probe, Exception):
            raise self.probe
        return self.probe


def probe(*, lhm_gpu=None, smi=None, vram=(3.2, 12.0), ram=(9.5, 31.0), thermal='NORMAL', sensors_reason=None):
    sensors = []
    if lhm_gpu is not None:
        sensors = [{'sensor_id': '/gpu-nvidia/0/temperature/0', 'name': 'GPU Core', 'type': 'Temperature', 'reading': m(lhm_gpu)},
                   {'sensor_id': '/lpc/it8688e/temperature/0', 'name': 'CPU', 'type': 'Temperature', 'reading': m(41.0)}]
    gpus = []
    if smi is not None or vram is not None:
        gpus = [{'device_id': 'GPU-1', 'temperature_core': m(smi), 'vram_used': m(vram[0] if vram else None, 'GiB'),
                 'vram_total': m(vram[1] if vram else None, 'GiB')}]
    return {'gpus': gpus, 'sensors': sensors,
            'memory': {'total': m(ram[1] if ram else None, 'GiB'), 'available': m(ram[0] if ram else None, 'GiB')},
            'provider_status': {'gpu': None, 'sensors': sensors_reason}, 'thermal_state': thermal}


class Temperatur(unittest.TestCase):
    """K6: Reihenfolge der Quelle – Board-Sensor (LHM), nvidia-smi, keine. Rein."""

    def test_board_sensor_vor_nvidia_smi(self):
        self.assertEqual(UIXHub.gpu_temperatur(probe(lhm_gpu=58.0, smi=61.0)), (58.0, 'LHM'))

    def test_nvidia_smi_wenn_kein_board_sensor(self):
        self.assertEqual(UIXHub.gpu_temperatur(probe(smi=61.0)), (61.0, 'nvidia-smi'))
        self.assertEqual(UIXHub.gpu_temperatur(probe(lhm_gpu=None, smi=61.0, sensors_reason='LibreHardwareMonitor_WMI_not_running_or_not_available')), (61.0, 'nvidia-smi'))

    def test_keine_quelle_keine_temperatur(self):
        self.assertEqual(UIXHub.gpu_temperatur(probe(smi=None, vram=None)), (None, 'keine'))
        self.assertEqual(UIXHub.gpu_temperatur(None), (None, 'keine'))
        self.assertEqual(UIXHub.gpu_temperatur({'sensors': [{'type': 'Temperature', 'name': 'GPU', 'reading': m(None)}], 'gpus': []}), (None, 'keine'))

    def test_nur_gpu_sensoren_zaehlen(self):
        p = probe(smi=None, vram=None)
        p['sensors'] = [{'type': 'Temperature', 'name': 'CPU Package', 'reading': m(70.0)}]
        self.assertEqual(UIXHub.gpu_temperatur(p), (None, 'keine'))


class Zellen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='strip-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)

    def mit(self, p):
        self.hub.runtime.hardware_manager = Attrappe(p)
        self.hub._hw_probe = None
        return self.hub.strip_view()

    def test_gpu_zelle_mit_lhm(self):
        strip = self.mit(probe(lhm_gpu=58.4, smi=61.0))
        gpu = strip['gpu']
        self.assertEqual((gpu['temperatur'], gpu['quelle'], gpu['vram_belegt'], gpu['thermisch']), (58.4, 'LHM', 3.2, 'NORMAL'))
        self.assertTrue(gpu['value'].startswith('58 °C · 3.2/12 GB'), gpu['value'])
        self.assertIn('Temperatur: LHM', gpu['hint'])
        self.assertEqual(gpu['tone'], 'ok')

    def test_gpu_zelle_ohne_lhm_nennt_den_satz(self):
        strip = self.mit(probe(smi=None, vram=(1.1, 12.0), sensors_reason='LibreHardwareMonitor_WMI_not_running_or_not_available'))
        gpu = strip['gpu']
        self.assertNotIn('temperatur', gpu)
        self.assertIn('LibreHardwareMonitor nicht gestartet', gpu['hint'])
        self.assertIn('Remote Web Server', gpu['hint'])
        self.assertIn('8085', gpu['hint'])

    def test_lhm_satz_steht_auch_neben_nvidia_smi(self):
        gpu = self.mit(probe(smi=61.0, sensors_reason='LibreHardwareMonitor_WMI_not_running_or_not_available'))['gpu']
        self.assertEqual((gpu['temperatur'], gpu['quelle']), (61.0, 'nvidia-smi'))
        self.assertIn('LibreHardwareMonitor nicht gestartet', gpu['hint'], 'D-S3: wie man die Board-Sensoren bekommt, steht dabei')

    def test_thermischer_zustand_faerbt(self):
        self.assertEqual(self.mit(probe(smi=70.0, thermal='WARM'))['gpu']['tone'], 'warn')
        self.assertEqual(self.mit(probe(smi=88.0, thermal='HOT'))['gpu']['tone'], 'bad')

    def test_ram_server_scheduler(self):
        strip = self.mit(probe(smi=60.0))
        self.assertEqual(strip['ram']['value'], '9.5/31 GB')
        self.assertEqual(strip['ram']['tone'], 'ok')
        self.assertEqual(self.mit(probe(smi=60.0, ram=(1.2, 31.0)))['ram']['tone'], 'warn', 'unter 2 GB frei')
        self.assertEqual(strip['scheduler'], {'value': 'aus', 'hint': 'Scheduler nicht eingeschaltet', 'tone': 'off'})
        self.assertIn(strip.get('server', {}).get('value', 'aus'), ('aus', 'bereit'))

    def test_ohne_quelle_fehlt_die_zelle(self):
        strip = self.mit(probe(smi=None, vram=None, ram=None))
        self.assertNotIn('ram', strip, 'kein RAM-Wert → keine Zelle, kein „–“')
        self.assertNotIn('temperatur', strip['gpu'])
        strip = self.mit(RuntimeError('WMI kaputt'))
        self.assertNotIn('ram', strip)
        self.assertIn('gpu', strip, 'die GPU-Zelle bleibt (Name aus dem Inventar), auch wenn die Probe scheitert')
        self.hub.runtime.hardware_manager = None
        self.hub._hw_probe = None
        strip = self.hub.strip_view()
        self.assertNotIn('ram', strip)

    def test_keine_eigene_messung_und_hoechstens_alle_10_s(self):
        att = Attrappe(probe(smi=60.0))
        self.hub.runtime.hardware_manager = att
        self.hub._hw_probe = None
        for _ in range(5):
            self.hub.strip_view()
        self.assertEqual(att.aufrufe, 1, 'fünf Leisten-Abfragen, eine Probe des Hardware-Managers; strip_view misst nie selbst')

    def test_server_zelle(self):
        z = UIXHub._server_zelle({'running': True, 'endpoint': 'http://127.0.0.1:8089', 'engine_build': 'b11160', 'engine_check': 'ok'})
        self.assertEqual((z['value'], z['tone'], z['hint']), ('bereit', 'ok', 'Engine b11160 · Port 8089'))
        z = UIXHub._server_zelle({'running': False, 'endpoint': 'http://127.0.0.1:8089', 'engine_build': 'b11160', 'engine_check': 'engine_not_installed'})
        self.assertEqual((z['value'], z['tone']), ('aus', 'off'))
        self.assertIn('engine_not_installed', z['hint'])
        self.assertIsNone(UIXHub._server_zelle(None))


if __name__ == '__main__':
    unittest.main()
