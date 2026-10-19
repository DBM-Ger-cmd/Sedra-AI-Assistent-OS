"""Der Fisch (19.10.2026): Übersetzer, Nachrichten aus gegebenen Quellen, Transkripte – die Fachlogik hinter der Shell „Fisch“.

Je Zusage ein Test: die Antwort des Übersetzers wird gelesen, nicht erraten; eine Meldung ohne bekannte Quelle ist unsicher;
SRT/VTT/TXT werden importiert und wieder exportiert wie bei LocalScribe; Suche findet ganze Wörter in Reihenfolge; Pseudonymisierung
ist eine neue Fassung mit getrenntem Mapping; Export ändert den Record nie; Freigabe friert die Fassung ein; ohne Modell `no_model`;
der STT-Provider ist ein benannter Platzhalter."""
import json
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.fisch import nachrichten as nw
from guppi_runtime.fisch import transkripte as tk
from guppi_runtime.fisch import uebersetzer as ue

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'
SRT = "1\n00:00:01,000 --> 00:00:03,500\nGuten Morgen, Frau Musterfrau.\n\n2\n00:00:04,000 --> 00:00:06,000\nDie Lieferung kommt am Montag.\n"


class Uebersetzer(unittest.TestCase):
    def test_the_answer_is_read_into_three_fields_and_a_wrong_format_invents_nothing(self):
        out = ue.lesen('ÜBERSETZUNG:\nWir liefern am Montag.\nUNSICHERHEITEN:\n- Uhrzeit fehlt\nHINWEISE:\n- keine')
        self.assertEqual(out, {'uebersetzung': 'Wir liefern am Montag.', 'unsicherheiten': ['Uhrzeit fehlt'], 'hinweise': [], 'format_ok': True})
        frei = ue.lesen('Einfach ein Satz.')
        self.assertEqual((frei['uebersetzung'], frei['format_ok'], frei['unsicherheiten']), ('Einfach ein Satz.', False, []))

    def test_the_input_is_checked(self):
        e = ue.pruefen({'text': 'Hallo', 'von': 'it_entwicklung', 'nach': 'management'})
        self.assertEqual((e['von'], e['nach'], e['ton'], e['tiefe']), ('it_entwicklung', 'management', 'klar', 'standard'))
        self.assertIn('Management', ue.nachricht(e))
        for bad in ({'text': ''}, {'text': 'x', 'von': 'chef'}, {'text': 'x', 'ton': 'laut'}):
            with self.assertRaises(ValueError):
                ue.pruefen(bad)


class Nachrichten(unittest.TestCase):
    def test_a_report_without_a_known_source_is_marked_uncertain(self):
        quellen = nw.quellen_pruefen([{'name': 'Pressemitteilung A', 'text': 'Firma A eröffnet ein Werk.'}])
        antwort = ('MELDUNG\nTITEL: Werk eröffnet\nKURZ: Firma A eröffnet ein Werk.\nWARUM: passt zu Industrie\nTIEFE: Mehr dazu.\n'
                   'QUELLE: Pressemitteilung A\nTAGS: industrie, werk\nVERTRAUEN: hoch\n'
                   'MELDUNG\nTITEL: Erfundenes\nKURZ: x\nWARUM: y\nTIEFE: z\nQUELLE: Irgendwo\nTAGS: \nVERTRAUEN: hoch\n')
        items = nw.lesen(antwort, quellen)
        self.assertEqual([(i['titel'], i['quelle_bekannt'], i['vertrauen']) for i in items], [('Werk eröffnet', True, 'hoch'), ('Erfundenes', False, 'niedrig')])
        self.assertEqual(items[0]['tags'], ['industrie', 'werk'])

    def test_the_profile_is_checked_and_the_message_names_the_sources(self):
        p = nw.profil_pruefen({'interessen': 'Local AI, Automatisierung', 'max_items': '3', 'tiefe': 'kurz'})
        self.assertEqual((p['interessen'], p['max_items'], p['region']), (['Local AI', 'Automatisierung'], 3, 'DE/EU'))
        with self.assertRaises(ValueError):
            nw.profil_pruefen({'tiefe': 'tief'})
        with self.assertRaises(ValueError):
            nw.quellen_pruefen([])
        text = nw.nachricht(p, nw.quellen_pruefen([{'name': 'Q1', 'text': 'Inhalt'}]), '2026-10-19')
        self.assertIn('=== Quelle: Q1', text)


class Transkripte(unittest.TestCase):
    def test_srt_in_srt_out_and_vtt_and_txt_follow_localscribe(self):
        imp = tk.importieren(SRT, 'Kundengespräch', 'de', 'gespraech.srt')
        self.assertEqual((imp['format'], len(imp['cues']), imp['geschaetzt']), ('srt', 2, False))
        self.assertEqual(imp['cues'][0], {'start': 1.0, 'end': 3.5, 'text': 'Guten Morgen, Frau Musterfrau.'})
        self.assertEqual(tk.export_srt(imp['cues']), SRT)
        self.assertTrue(tk.export_vtt(imp['cues']).startswith('WEBVTT\n\n00:00:01.000 --> 00:00:03.500\n'))
        self.assertEqual(tk.export_vtt([]), 'WEBVTT\n'); self.assertEqual(tk.export_srt([]), '')
        txt = tk.importieren('Nur Text ohne Zeiten. ' * 10, 'Notiz')
        self.assertTrue(txt['geschaetzt'])
        self.assertEqual(tk.cues_aus_srt_vtt('WEBVTT\n\n00:01.000 --> 00:02.000\nHallo\n')[0]['start'], 1.0)

    def test_search_finds_whole_words_in_order_case_insensitive(self):
        cues = tk.importieren(SRT, 'x')['cues']
        self.assertEqual([t['cue'] for t in tk.suchen(cues, 'frau musterfrau')], [0])
        self.assertEqual(tk.suchen(cues, 'Musterfrau Frau'), [])
        self.assertEqual(tk.suchen(cues, 'Lieferun'), [])
        self.assertEqual(tk.suchen(cues, 'montag')[0]['start'], 4.0)

    def test_the_record_versions_freezes_and_exports_without_changing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = tk.Store(Path(tmp))
            t = store.schreiben(tk.neu(tk.importieren(SRT, 'Kundengespräch'), '2026-10-19T20:00:00Z'))
            self.assertEqual((t['status'], t['aktuell']), ('entwurf', 1))
            t = store.neue_fassung(t, [{'start': 1.0, 'end': 3.5, 'text': 'Guten Morgen, [NAME_1].'}], 'pseudonymisiert', '2026-10-19T20:01:00Z', mapping={'[NAME_1]': 'Frau Musterfrau'})
            self.assertEqual((t['aktuell'], len(t['versionen']), t['versionen'][1]['mapping']), (2, 2, True))
            self.assertTrue((Path(tmp) / 'fisch' / 'transkripte' / f"{t['id']}.mapping.json").is_file())
            with self.assertRaises(ValueError):
                store.status_setzen(t, 'freigegeben', 'now')             # erst prüfen
            t = store.status_setzen(t, 'geprueft', 'now'); t = store.status_setzen(t, 'freigegeben', 'now')
            self.assertEqual(t['freigegeben_version'], 2)
            with self.assertRaises(ValueError):
                store.neue_fassung(t, [], 'x', 'now')                   # ein Golden Record bekommt keine neue Fassung
            vorher = json.dumps(store.get(t['id']), sort_keys=True)
            out = tk.exportieren(t, 'json')
            self.assertNotIn('Musterfrau', out, 'das Mapping ist nie im Export')
            self.assertEqual(json.dumps(store.get(t['id']), sort_keys=True), vorher, 'Export ändert den Record nie')
            self.assertEqual(tk.transkribieren()['status'], 'platzhalter')


class ThroughTheHub(unittest.TestCase):
    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='fisch-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)

    def test_without_a_model_the_fish_says_so_and_a_fake_model_is_read(self):
        self.assertEqual(self.hub.fisch.uebersetzen({'text': 'Hallo', 'von': 'alltag', 'nach': 'business'})['status'], 'no_model')
        class FakeServer:
            def loaded_models(self): return [{'identifier': 'fake', 'modelKey': 'fake'}]
        self.hub.runtime.llama_server = FakeServer()
        self.hub.runtime.control.execute = lambda m, r: {'status': 'completed', 'model_result': {'content': 'ÜBERSETZUNG:\nWir liefern Montag.\nUNSICHERHEITEN:\n- keine\nHINWEISE:\n- keine', 'finish_reason': 'stop'}}
        out = self.hub.fisch.uebersetzen({'text': 'Montag kommt das Zeug', 'von': 'alltag', 'nach': 'business'})
        self.assertEqual((out['status'], out['uebersetzung']), ('completed', 'Wir liefern Montag.'))
        self.assertIn('FISCH_UEBERSETZT', [e['event_type'] for e in self.hub.audit_view()['events']])

    def test_import_pseudonymize_release_export_through_the_hub(self):
        made = self.hub.fisch.transkript_import({'text': SRT, 'titel': 'Kundengespräch', 'sprache': 'de', 'quelle': 'gespraech.srt'})
        tid = made['id']
        self.assertEqual(self.hub.fisch.transkript_suche({'id': tid, 'frage': 'Montag'})['treffer'][0]['cue'], 1)
        ps = self.hub.fisch.transkript_pseudonymisieren({'id': tid})
        self.assertEqual(ps['version'], 2)
        self.assertNotIn('Musterfrau', ' '.join(c['text'] for c in self.hub.fisch.transkript({'id': tid})['cues']), 'der Name ist ein Platzhalter')
        self.hub.fisch.transkript_status({'id': tid, 'status': 'geprueft'})
        self.assertEqual(self.hub.fisch.transkript_status({'id': tid, 'status': 'freigegeben'})['freigegeben_version'], 2)
        ex = self.hub.fisch.transkript_export({'id': tid, 'format': 'srt'})
        self.assertEqual((ex['version'], ex['vorlaeufig']), (2, False))
        self.assertTrue((Path(self.tmp.name) / 'project' / ex['datei']).is_file())
        self.hub.sprache.which = lambda n: None          # auf diesem Rechner kann whisperx installiert sein – der Test fragt den Kern ohne Provider
        self.assertEqual(self.hub.fisch.transkripte()['stt']['status'], 'platzhalter')
        self.assertEqual(self.hub.fisch.profil()['gespeichert'], False)
        self.assertEqual(self.hub.fisch.profil_speichern({'profil': {'interessen': ['Local AI']}})['profil']['interessen'], ['Local AI'])
        self.assertEqual(self.hub.fisch.profil()['gespeichert'], True)


if __name__ == '__main__':
    unittest.main()
