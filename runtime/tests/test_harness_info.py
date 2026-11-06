"""Info-Hub (05.11.2026): Klartext aus dem Audit-Log, Modelle laut Log, Filter, Route."""
import json
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.harness import info
from sedra_runtime.harness.api import WEG


def log(*ereignisse):
    p = Path(tempfile.mkdtemp()) / 'events.jsonl'
    zeilen = [json.dumps({'event_type': t, 'timestamp': '2026-11-05T06:%02d:00+00:00' % i, 'payload': pl, 'source': {'component': 'x'}}) for i, (t, pl) in enumerate(ereignisse)]
    p.write_text('\n'.join(zeilen) + '\n', encoding='utf-8')
    return p


START = ('SLOT_SERVER_STARTED', {'recipe': 'r.a', 'slots': 2, 'context_per_slot': 32768, 'vram_gb': 9.152})


class Modelle(unittest.TestCase):
    def test_start_stopp_und_neustart(self):
        m = info.stand(log(START))['modelle']
        self.assertEqual([(x['rezept'], x['fenster_je_slot'], x['vram_gb']) for x in m['laeuft']], [('r.a', 32768, 9.2)])
        self.assertEqual(info.stand(log(START, ('SLOT_SERVER_STOPPED', {'recipe': 'r.a'})))['modelle']['laeuft'], [])
        self.assertEqual(info.stand(log(START, ('BOOT_STARTED', {})))['modelle']['laeuft'], [])

    def test_ablehnung_mit_grund_bis_es_klappt(self):
        nein = ('ROLE_RESOLUTION_FAILED', {'role': 'coder', 'rejected': [{'capability_id': 'r.a', 'reason': 'vram_insufficient'}]})
        m = info.stand(log(nein))['modelle']['abgelehnt']
        self.assertEqual((m[0]['rezept'], m[0]['grund']), ('r.a', 'zu wenig Grafikspeicher für dieses Fenster'))
        self.assertEqual(info.stand(log(nein, ('ROLE_RESOLVED', {'capability_id': 'r.a', 'role': 'coder'})))['modelle']['abgelehnt'], [])


class Ereignisse(unittest.TestCase):
    def test_klartext_und_filter(self):
        p = log(START, ('SG_MODEL_CALL', {}), ('HARNESS_FREIGABE', {'x': 1}), ('JOB_FAILED', {'grund': 'kaputt'}))
        alle = info.stand(p)['ereignisse']
        self.assertNotIn('SG_MODEL_CALL', [z['typ'] for z in alle])             # Modellaufrufe verdecken sonst alles
        self.assertIn('je 32768 Token Fenster', alle[0]['text'])
        self.assertEqual([z['typ'] for z in info.stand(p, art='fehler')['ereignisse']], ['JOB_FAILED'])
        self.assertEqual([z['typ'] for z in info.stand(p, art='freigaben')['ereignisse']], ['HARNESS_FREIGABE'])
        self.assertEqual([z['typ'] for z in info.stand(p, such='sg model')['ereignisse']], ['SG_MODEL_CALL'])
        self.assertEqual(len(info.stand(p, limit=1)['ereignisse']), 1)

    def test_fehlende_datei_ist_ein_valueerror(self):
        with self.assertRaises(ValueError):
            info.stand(Path(tempfile.mkdtemp()) / 'gibt-es-nicht.jsonl')

    def test_weg_kennt_info(self):
        self.assertIn('info', WEG.fullmatch('/api/harness/info').groups())


if __name__ == '__main__':
    unittest.main()
