"""recent_audit zeigt den Inhalt der Ereignisse und lässt sich filtern (Testgespräch MasterChat 04.11.2026): Die Meldung „vram_insufficient, Rezept coder.llama_qwen35“ lag eine Stunde
zurück unter Modellaufrufen und war ohne Inhalt nicht zu erkennen. Mit `name` (Filter) und dem Feld `inhalt` findet der MasterChat Grund und Rezept in einem Aufruf."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from guppi_runtime.uix_server import UIXHub


def schreiben(pfad, ereignisse):
    Path(pfad).write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in ereignisse) + '\n', encoding='utf-8')


def ereignis(typ, payload=None, zeit='2026-11-04T08:00:00+00:00'):
    return {'timestamp': zeit, 'event_type': typ, 'source': {'component': 'test'}, 'payload': payload or {}}


class ChatAuditInhalt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pfad = Path(self.tmp.name) / 'events.jsonl'
        self.hub = SimpleNamespace(runtime=SimpleNamespace(audit=SimpleNamespace(path=self.pfad)))

    def audit(self, limit, such=None):
        return UIXHub.chat_audit(self.hub, limit, such)

    def test_ohne_filter_die_letzten_mit_inhalt_in_zeitfolge(self):
        schreiben(self.pfad, [ereignis('A'), ereignis('B', {'grund': 'x'}), ereignis('C')])
        out = self.audit(2)
        self.assertEqual([e['event'] for e in out], ['B', 'C'])
        self.assertEqual(json.loads(out[0]['inhalt']), {'grund': 'x'})
        self.assertEqual(set(out[0]), {'time', 'event', 'component', 'inhalt'})

    def test_filter_findet_eine_alte_meldung_unter_vielen_modellaufrufen(self):
        alt = ereignis('ROLE_RESOLUTION_FAILED', {'code': 'hardware_pressure', 'rejected': [{'capability_id': 'coder.llama_qwen35', 'reason': 'vram_insufficient'}]})
        schreiben(self.pfad, [alt] + [ereignis('SG_MODEL_CALL', {'n': i}) for i in range(500)])
        self.assertNotIn('ROLE_RESOLUTION_FAILED', [e['event'] for e in self.audit(10)])                   # ohne Filter versunken
        out = self.audit(10, 'FAILED')
        self.assertEqual([e['event'] for e in out], ['ROLE_RESOLUTION_FAILED'])
        self.assertIn('vram_insufficient', out[0]['inhalt'])
        self.assertIn('coder.llama_qwen35', out[0]['inhalt'])

    def test_filter_gilt_auch_fuer_den_inhalt_ohne_gross_und_klein(self):
        schreiben(self.pfad, [ereignis('MODEL_LOADED', {'model': 'Qwen3.5-9B'}), ereignis('MODEL_LOADED', {'model': 'gemma'})])
        out = self.audit(10, 'qwen3.5')
        self.assertEqual(len(out), 1)
        self.assertIn('Qwen3.5-9B', out[0]['inhalt'])

    def test_limit_gilt_nach_dem_filter_und_langer_inhalt_wird_gekuerzt(self):
        schreiben(self.pfad, [ereignis('X', {'text': 'a' * 1000, 'n': i}) for i in range(5)])
        out = self.audit(3, 'X')
        self.assertEqual(len(out), 3)
        self.assertLessEqual(len(out[0]['inhalt']), 240)
        self.assertTrue(out[0]['inhalt'].endswith('…'))

    def test_kaputte_zeilen_und_leere_datei_stoeren_nicht(self):
        self.pfad.write_text('kein json\n' + json.dumps(ereignis('OK')) + '\n', encoding='utf-8')
        self.assertEqual([e['event'] for e in self.audit(5)], ['OK'])
        self.pfad.write_text('', encoding='utf-8')
        self.assertEqual(self.audit(5, 'x'), [])


if __name__ == '__main__':
    unittest.main()
