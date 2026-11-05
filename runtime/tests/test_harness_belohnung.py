"""Belohnungssystem (05.11.2026): Lobwoerter nach einer Antwort merken die gute Antwort – Erkennung, Bezug auf die richtige Antwort, Loesung bei Code, Tagesdatei und Index fuer die Wissensdatenbank,
Uebersicht, Eintrag in der Sitzung; nichts davon darf die Nachricht aufhalten."""
import json
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.harness import belohnung as bl
from guppi_runtime.uix_server import UIXHub

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
EINST = bl.einstellungen()


def antwort(i='A-1', text='Hier ist die Lösung.', ende='antwort'):
    return {'typ': 'modell', 'antwort_id': i, 'text': text, 'ende': ende}


def captain(text='Mach das bitte.'):
    return {'typ': 'captain', 'text': text}


class Erkennen(unittest.TestCase):
    def test_lob_und_stufe(self):
        for text, erwartet in (('Danke!', ('danke', 1)), ('das hast du gut gemacht', ('das hast du gut gemacht', 1)), ('Vielen Dank, super', ('vielen dank', 1)),
                               ('Perfekt, danke', ('perfekt', 2)), ('genau so, danke dir', ('genau so', 2)), ('SUPER.', ('super', 1))):
            self.assertEqual(bl.erkennen(text, EINST), erwartet, text)

    def test_kein_lob(self):
        for text in ('nicht gut gemacht', 'kein danke nötig', 'das war nicht perfekt', 'dankbar', 'Superman', 'ok', '', '   ', 'Danke, jetzt mach noch X. ' * 30):
            self.assertIsNone(bl.erkennen(text, EINST), text[:40])
        self.assertIsNone(bl.erkennen(None, EINST))

    def test_eigene_woerter_aus_local_config(self):
        p = Path(tempfile.mkdtemp())
        (p / 'local_config').mkdir()
        (p / 'local_config' / 'belohnung.yaml').write_text('belohnung:\n  lob_zusaetzlich: [bravo]\n  besonders_zusaetzlich: [meisterhaft]\n', encoding='utf-8')
        e = bl.einstellungen(p)
        self.assertEqual(bl.erkennen('Bravo!', e), ('bravo', 1))
        self.assertEqual(bl.erkennen('meisterhaft', e), ('meisterhaft', 2), 'ein besonders-Wort ist auch ein Lobwort')
        (p / 'local_config' / 'belohnung.yaml').write_text('belohnung:\n  lob: [klasse]\n', encoding='utf-8')
        e = bl.einstellungen(p)
        self.assertIsNone(bl.erkennen('danke', e), '`lob` ersetzt die Liste des Pakets')
        self.assertEqual(bl.erkennen('Klasse', e), ('klasse', 1))


class Bezug(unittest.TestCase):
    def test_nur_die_antwort_direkt_vor_der_nachricht(self):
        a, f = bl.gelobte_antwort([captain('Frage 1'), antwort('A-1', 'Antwort 1')])
        self.assertEqual((a['antwort_id'], f['text']), ('A-1', 'Frage 1'))
        self.assertEqual(bl.gelobte_antwort([antwort('A-1'), captain('noch eine Frage')]), (None, None), 'eine Frage dazwischen: kein Lob für die ältere Antwort')
        self.assertEqual(bl.gelobte_antwort([captain('x')]), (None, None))
        self.assertEqual(bl.gelobte_antwort([]), (None, None))

    def test_nicht_zu_ende_gekommene_und_schon_gelobte_antworten(self):
        for ende in bl.KEIN_LOB_ENDE:
            self.assertEqual(bl.gelobte_antwort([captain(), antwort(ende=ende)]), (None, None), ende)
        self.assertEqual(bl.gelobte_antwort([captain(), antwort('A-1'), {'typ': 'belohnung', 'antwort_id': 'A-1'}]), (None, None), 'jede Antwort höchstens einmal')
        self.assertEqual(bl.gelobte_antwort([captain(), antwort('A-1', text='')]), (None, None), 'eine leere Antwort gibt es nicht zu loben')

    def test_loesung_nennt_dateien_befehle_und_nur_was_gelang(self):
        eintraege = [{'typ': 'werkzeug', 'antwort_id': 'A-1', 'name': 'datei_aendern', 'args': {'pfad': 'src/a.py'}, 'status': 'ok'},
                     {'typ': 'werkzeug', 'antwort_id': 'A-1', 'name': 'datei_aendern', 'args': {'pfad': 'src/a.py'}, 'status': 'ok'},
                     {'typ': 'werkzeug', 'antwort_id': 'A-1', 'name': 'datei_schreiben', 'args': {'pfad': 'tests/t.py'}, 'status': 'ok'},
                     {'typ': 'werkzeug', 'antwort_id': 'A-1', 'name': 'befehl', 'args': {'befehl': 'python -m pytest tests'}, 'status': 'ok'},
                     {'typ': 'werkzeug', 'antwort_id': 'A-1', 'name': 'datei_aendern', 'args': {'pfad': 'nie.py'}, 'status': 'fehler'},
                     {'typ': 'werkzeug', 'antwort_id': 'A-2', 'name': 'datei_aendern', 'args': {'pfad': 'andere.py'}, 'status': 'ok'}]
        t = bl.loesung(eintraege, 'A-1')
        self.assertEqual((t['dateien'], t['befehle'], t['code']), (['src/a.py', 'tests/t.py'], ['python -m pytest tests'], True))
        self.assertEqual(t['werkzeuge'], {'datei_aendern': 2, 'datei_schreiben': 1, 'befehl': 1})
        self.assertFalse(bl.loesung([], 'A-1')['code'])


class Ablage(unittest.TestCase):
    def test_tagesdatei_index_und_uebersicht(self):
        p = tempfile.mkdtemp()
        a = antwort('A-1', 'Die Lösung steht in a.py.')
        satz = bl.vermerken(p, 'perfekt', a, captain('Wie löse ich das?'), sitzung_id='S-1', titel='Fehler beheben', vorlage='bauagent', modell='qwen', stufe=2,
                            tat={'dateien': ['src/a.py'], 'befehle': ['pytest'], 'werkzeuge': {'datei_aendern': 1}, 'code': True}, zeit='2026-11-05T08:30:00')
        bl.vermerken(p, 'danke', antwort('A-2', 'Erklärung.'), captain('Was ist X?'), sitzung_id='S-2', vorlage=None, modell='qwen', zeit='2026-11-05T09:00:00')
        self.assertEqual((satz['stufe'], satz['art']), (2, 'code'))
        text = (bl.ordner(p) / '2026-11-05.md').read_text(encoding='utf-8')
        self.assertEqual(text.count('# Gute Antworten'), 1)
        for teil in ('## 08:30 Besonders gute Antwort „perfekt“', 'Frage: Wie löse ich das?', 'Gelöst in Dateien: src/a.py', 'Befehle und Läufe: pytest', 'datei_aendern×1', '## 09:00 Gute Antwort „danke“'):
            self.assertIn(teil, text)
        u = bl.uebersicht(p)
        self.assertEqual((u['anzahl'], u['besonders'], u['code']), (2, 1, 1))
        self.assertEqual(u['je_modell'], [{'name': 'qwen', 'anzahl': 2}])
        self.assertEqual([x['name'] for x in u['je_vorlage']], ['bauagent', '–'])
        self.assertEqual(u['letzte'][0]['antwort_id'], 'A-2', 'die neueste zuerst')
        self.assertEqual(bl.uebersicht(tempfile.mkdtemp())['anzahl'], 0)

    def test_lange_texte_werden_gekuerzt(self):
        p = tempfile.mkdtemp()
        s = bl.vermerken(p, 'danke', antwort('A-1', 'x ' * 2000), captain('y ' * 500), sitzung_id='S-1')
        self.assertLessEqual((len(s['frage']), len(s['antwort'])), (bl.FRAGE_MAX, bl.ANTWORT_MAX))


class AmHub(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='belohnung-')
        self.addCleanup(tmp.cleanup)
        self.projekt = Path(tmp.name) / 'project'
        (self.projekt / 'local_config').mkdir(parents=True)
        self.hub = UIXHub(self.projekt, ARCH)
        self.addCleanup(self.hub.close)
        self.api = self.hub.harness
        kopf = self.api.sitzungen.anlegen('p', titel='Fehler beheben', modell='qwen', vorlage='bauagent')
        self.sid = kopf['id']
        for e in (captain('Behebe den Fehler.'), {'typ': 'werkzeug', 'antwort_id': 'A-9', 'name': 'datei_aendern', 'args': {'pfad': 'src/a.py'}, 'status': 'ok'}, antwort('A-9', 'Erledigt.')):
            self.api.sitzungen.anhaengen(self.sid, e)

    def test_danke_nach_einer_antwort_wird_zur_guten_antwort(self):
        s = self.api.sitzungen.laden(self.sid)
        satz = self.api._belohnung_pruefen(self.sid, s, 'Perfekt, danke!')
        self.assertIsNotNone(satz)
        self.assertEqual((satz['stufe'], satz['art'], satz['vorlage'], satz['modell'], satz['tat']['dateien']), (2, 'code', 'bauagent', 'qwen', ['src/a.py']))
        eintraege = self.api.sitzungen.laden(self.sid)['eintraege']
        self.assertEqual([e['ausloeser'] for e in eintraege if e['typ'] == 'belohnung'], ['perfekt'])
        self.assertTrue((bl.ordner(self.projekt) / bl.INDEX).exists())
        self.assertIn('"HARNESS_BELOHNUNG"', self.hub.runtime.audit.path.read_text(encoding='utf-8'))
        self.assertIsNone(self.api._belohnung_pruefen(self.sid, self.api.sitzungen.laden(self.sid), 'danke nochmal'), 'dieselbe Antwort wird nicht zweimal gelobt')

    def test_kein_lob_ohne_lobwort_oder_ohne_vorherige_antwort(self):
        s = self.api.sitzungen.laden(self.sid)
        self.assertIsNone(self.api._belohnung_pruefen(self.sid, s, 'Mach bitte noch etwas'))
        kopf = self.api.sitzungen.anlegen('p', titel='leer')
        self.assertIsNone(self.api._belohnung_pruefen(kopf['id'], self.api.sitzungen.laden(kopf['id']), 'danke'))
        self.assertEqual(bl.uebersicht(self.projekt)['anzahl'], 0)

    def test_ein_fehler_beim_merken_haelt_nie_die_nachricht_auf(self):
        self.assertIsNone(self.api._belohnung_pruefen(self.sid, None, 'danke'))               # kaputte Sitzung: der Zugriff scheitert, die Methode schluckt es
        s = self.api.sitzungen.laden(self.sid)
        s['eintraege'] = [{'typ': 'modell', 'antwort_id': 'A-9', 'text': 'x', 'ende': 'antwort', 'args': 5}, 5]                 # kaputte Eintraege
        self.assertIsNone(self.api._belohnung_pruefen(self.sid, s, 'danke'))

    def test_info_route_nennt_die_guten_antworten(self):
        self.api._belohnung_pruefen(self.sid, self.api.sitzungen.laden(self.sid), 'danke')
        out = self.api.handle('GET', '/api/harness/info', '')[1]
        self.assertEqual(out['belohnungen']['anzahl'], 1)
        self.assertIn(out['belohnungen']['wissen'], ('nicht', 'aus'))
        with self.assertRaises(ValueError):
            self.api.handle('POST', '/api/harness/info/wissen', '', {'quelle': 'unbekannt'})


if __name__ == '__main__':
    unittest.main()
