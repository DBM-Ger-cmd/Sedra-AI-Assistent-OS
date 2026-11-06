"""Ladeprobe (05.11.2026): sagt je Rezept, ob es laden koennte, und warum nicht; Modelldatei, Lader, Satz fuers Log, Weg ueber die Info-Route."""
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.harness import ladeprobe as lp
from sedra_runtime.uix_server import UIXHub

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'


def modell(i, passt=True, grund=None, **mehr):
    return dict({'id': i, 'modell': i + '-m', 'passt': passt, 'grund': grund, 'kontext': 32768, 'geladen': False, 'bedarf_vram_gb': 9.2}, **mehr)


def rezept(i, gguf=None):
    return {'id': i, 'profile': {'server': {'gguf': gguf} if gguf else {}}}


class Pruefen(unittest.TestCase):
    def test_passt_und_passt_nicht(self):
        sicht = {'loader': True, 'frei_vram_gb': 9.4, 'frei_ram_gb': 11.0, 'modelle': [modell('a'), modell('b', False, 'vram_insufficient'), modell('c', None)]}
        p = lp.pruefen(sicht, [rezept('a'), rezept('b'), rezept('c')])
        self.assertEqual((p['ok'], p['gesamt']), (1, 3))
        self.assertEqual([x['grund'] for x in p['rezepte']], [None, 'vram_insufficient', 'nicht prüfbar'])

    def test_fehlende_modelldatei_ist_ein_problem_auch_wenn_der_router_zustimmt(self):
        da = Path(tempfile.mkdtemp()) / 'm.gguf'
        da.write_bytes(b'x')
        sicht = {'loader': True, 'modelle': [modell('a'), modell('b')]}
        p = lp.pruefen(sicht, [rezept('a', str(da)), rezept('b', str(da.parent / 'weg.gguf'))])
        self.assertEqual([x['ok'] for x in p['rezepte']], [True, False])
        self.assertTrue(p['rezepte'][1]['grund'].startswith('Modelldatei fehlt: '))

    def test_satz_nennt_probleme_und_lader_aus(self):
        sicht = {'loader': True, 'frei_vram_gb': 9.4, 'frei_ram_gb': 11.0, 'modelle': [modell('a'), modell('b', False, 'vram_insufficient')]}
        s = lp.satz(lp.pruefen(sicht, []))
        self.assertIn('1 von 2 Rezepten bereit', s)
        self.assertIn('b: vram_insufficient', s)
        self.assertIn('Lader ist aus', lp.satz(lp.pruefen({'loader': False, 'modelle': []}, [])))


class AmHub(unittest.TestCase):
    def test_info_route_nennt_die_probe_und_das_audit_haelt_sie_einmal_fest(self):
        tmp = tempfile.TemporaryDirectory(prefix='ladeprobe-')
        self.addCleanup(tmp.cleanup)
        projekt = Path(tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        hub = UIXHub(projekt, ARCH)
        self.addCleanup(hub.close)
        st, body = hub.harness.handle('GET', '/api/harness/info', '')
        self.assertEqual(st, 200)
        self.assertIn('ladeprobe', body)
        hub.harness.handle('GET', '/api/harness/info', '')
        text = hub.runtime.audit.path.read_text(encoding='utf-8')
        self.assertEqual(text.count('"LADEPROBE"') + text.count('"LADEPROBE_PROBLEM"'), 1, 'nur beim ersten Aufruf nach dem Start')


if __name__ == '__main__':
    unittest.main()
