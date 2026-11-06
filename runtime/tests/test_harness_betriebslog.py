"""Betriebslog (05.11.2026): Tagesdateien aus dem Audit-Log, nur Wichtiges, nur Neues, sicherer Tag-Zugriff, Route und Wissensquelle."""
import json
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.harness import betriebslog as bl
from sedra_runtime.harness.api import GESCHUETZT, WEG
from sedra_runtime.uix_server import UIXHub

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'


def audit(*zeilen):
    p = Path(tempfile.mkdtemp()) / 'events.jsonl'
    p.write_text('\n'.join(json.dumps({'event_type': t, 'timestamp': z, 'payload': pl, 'source': {'component': 'x'}}) for t, z, pl in zeilen) + '\n', encoding='utf-8')
    return p


def anhaengen(p, t, z, pl):
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'event_type': t, 'timestamp': z, 'payload': pl, 'source': {}}) + '\n')


START = ('SLOT_SERVER_STARTED', '2026-11-05T06:45:59+00:00', {'recipe': 'r.a', 'slots': 2, 'context_per_slot': 32768, 'vram_gb': 9.152})
RAUSCHEN = ('SG_MODEL_CALL', '2026-11-05T06:46:00+00:00', {})


class Sichern(unittest.TestCase):
    def test_nur_wichtiges_in_tagesdatei_mit_klartext(self):
        p, proj = audit(START, RAUSCHEN, ('BOOT_STARTED', '2026-11-06T01:00:00+00:00', {})), tempfile.mkdtemp()
        r = bl.sichern(p, proj)
        self.assertEqual((r['neu'], r['tage']), (2, ['2026-11-05', '2026-11-06']))
        text = bl.tag_lesen(proj, '2026-11-05')
        self.assertIn('# Betriebslog 2026-11-05', text)
        self.assertIn('- 06:45:59 Modellserver gestartet: r.a, 2 Slots, je 32768 Token Fenster', text)
        self.assertNotIn('SG_MODEL_CALL', text)
        self.assertEqual(bl.tage(proj), [{'tag': '2026-11-06', 'zeilen': 1}, {'tag': '2026-11-05', 'zeilen': 1}])

    def test_zweiter_lauf_haengt_nur_neues_an(self):
        p, proj = audit(START), tempfile.mkdtemp()
        bl.sichern(p, proj)
        self.assertEqual(bl.sichern(p, proj)['neu'], 0)
        anhaengen(p, 'JOB_FAILED', '2026-11-05T07:00:00+00:00', {'grund': 'kaputt'})
        self.assertEqual(bl.sichern(p, proj)['neu'], 1)
        text = bl.tag_lesen(proj, '2026-11-05')
        self.assertEqual(text.count('Modellserver gestartet'), 1)
        self.assertEqual(text.count('# Betriebslog'), 1)
        self.assertIn('JOB_FAILED', text)

    def test_tag_nur_in_datumsform(self):
        proj = tempfile.mkdtemp()
        for schlecht in ('../x', '2026-11-05.md', '', None, '2026-11-5'):
            with self.assertRaises(ValueError):
                bl.tag_lesen(proj, schlecht)
        with self.assertRaises(ValueError):
            bl.tag_lesen(proj, '2026-11-05')                       # gültige Form, aber nicht gesichert

    def test_ordner_ist_unter_runtime_data(self):
        self.assertEqual(bl.QUELLE_PFAD, 'runtime_data/harness/betriebslog')
        self.assertEqual(bl.ordner('/p').parts[-3:], ('runtime_data', 'harness', 'betriebslog'))


class MitWissen(unittest.TestCase):
    """Am echten Hub mit Wissensspeicher: der Antrag nimmt den Ordner erst nach der Freigabe auf, danach findet die Suche den Verlauf."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='betriebslog-')
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name) / 'project'
        (self.project / 'local_config').mkdir(parents=True)
        (self.project / 'local_config' / 'switches.yaml').write_text('switches:' + chr(10) + '  wissen: {enabled: true}' + chr(10), encoding='utf-8')
        self.hub = UIXHub(self.project, ARCH)
        self.addCleanup(self.hub.close)
        self.api = self.hub.harness

    def test_antrag_freigabe_und_suche(self):
        anh = self.hub.runtime.audit
        anh.append('SLOT_SERVER_STARTED', component='t', payload={'recipe': 'r.zeta', 'slots': 2, 'context_per_slot': 32768, 'vram_gb': 9.2})
        self.assertEqual(self.api.handle('GET', '/api/harness/info', '')[1]['verlauf']['wissen'], 'nicht')
        antwort = self.api.handle('POST', '/api/harness/info/wissen', '', {})[1]
        self.assertEqual(antwort['status'], 'beantragt')
        self.assertEqual(self.api.handle('GET', '/api/harness/info', '')[1]['verlauf']['wissen'], 'nicht')          # ohne Freigabe bleibt es leer
        self.hub.decide({'id': antwort['decision_id'], 'way': 'freigeben_und_anwenden'})
        self.assertEqual(self.api.handle('GET', '/api/harness/info', '')[1]['verlauf']['wissen'], 'aufgenommen')
        self.assertEqual(self.api.handle('POST', '/api/harness/info/wissen', '', {})[1]['status'], 'schon_aufgenommen')
        sp = self.hub.runtime.wissen
        sp.abgleich()
        treffer = sp.suche('Modellserver gestartet r.zeta', leser={'art': 'captain', 'stufe': 6})
        self.assertTrue(treffer, 'die Suche findet den Verlauf')


class Wege(unittest.TestCase):
    def test_wissen_weg_ist_bekannt_und_geschuetzt(self):
        m = WEG.fullmatch('/api/harness/info/wissen')
        self.assertIsNotNone(m)
        self.assertTrue(GESCHUETZT.match('/api/harness/info/wissen'))


if __name__ == '__main__':
    unittest.main()
