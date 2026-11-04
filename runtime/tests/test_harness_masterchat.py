"""MasterChat (03.11.2026): Vorlage mit weitreichenden Freigaben zur Anpassung und Einrichtung von SEDRA aus dem Chat. Die Freigaben gelten nur nach dem ausdrücklichen Ja des Captains
beim Anlegen der Sitzung, nur für diese Sitzung, und die festen Vorbehalte gelten trotzdem."""
import re
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.chat_tools import SCHEMAS as CHAT_SCHEMAS
from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import katalog
from guppi_runtime.harness import vorlagen as harness_vorlagen
from guppi_runtime.harness.api import HarnessApi
from guppi_runtime.harness.erlaubnis import aktive
from guppi_runtime.harness.freigabe import Karten, Kiste
from guppi_runtime.harness.sitzung import Sitzungen
from guppi_runtime.harness.vorlagen import VorlageFehler, pruefen
from guppi_runtime.harness.werkzeuge import NAMEN as HARNESS_NAMEN, Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
CONFIG = Path(__file__).resolve().parents[1] / 'config' / 'harness_vorlagen'


def vorlage(**kw):
    doc = {'harness_vorlage': dict({'id': 'x', 'name': 'X', 'werkzeuge': ['datei_schreiben', 'datei_aendern', 'befehl', 'lauf_starten'], 'rechte': {}, 'max_zuege': 24}, **kw)}
    return pruefen(doc, 'Systemtext.')


class VorlageTests(unittest.TestCase):
    def setUp(self):
        self.m = harness_vorlagen.laden(Path('gibt-es-nicht'), 'masterchat', CONFIG)

    def test_die_vorlage_laedt_mit_hinweis_und_zwoelf_erlaubnissen(self):
        self.assertEqual((self.m['id'], self.m['name']), ('masterchat', 'MasterChat'))
        self.assertIn('Anpassung und Einrichtung von SEDRA', self.m['hinweis'])
        self.assertIn('weitreichende Befugnisse', self.m['hinweis'])
        self.assertEqual(len(self.m['erlaubnisse']), 12)
        self.assertTrue(all(e['werkzeug'] in self.m['werkzeuge'] for e in self.m['erlaubnisse']))
        self.assertEqual(self.m['rechte'], {'vorarbeiter_freigabe': False, 'aufgaben_vorschlagen': False})          # entscheidet keine Karten, schlägt nichts vor

    def test_keine_erlaubnis_greift_in_die_festen_vorbehalte_oder_modelle(self):
        for e in self.m['erlaubnisse']:
            self.assertNotIn(e['werkzeug'], ('modell_laden', 'modell_entladen'))
            self.assertNotIn(e['muster'], ('*', '**'))
            self.assertNotIn('core', e['muster'])
            self.assertNotIn('harness_vorlagen', e['muster'])
            self.assertNotIn('config', e['muster'])
        muster = {(e['werkzeug'], e['muster']) for e in self.m['erlaubnisse']}
        self.assertNotIn(('befehl', 'git commit*'), muster)                                                          # committen nur mit Karte
        self.assertNotIn(('befehl', 'git add*'), muster)

    def test_der_systemtext_enthaelt_pflichtsatz_vorbehalte_und_den_weg(self):
        text = (CONFIG / 'masterchat.md').read_text(encoding='utf-8')
        self.assertIn('Pflichtsatz in der ersten Antwort', text)
        self.assertIn('Anpassung und Einrichtung von SEDRA', text)
        self.assertIn('weitreichende Befugnisse', text)
        self.assertNotIn('GUPPI', text)
        for wort in ('Erfinde nichts', 'Feste Vorbehalte', 'docs/wunsch_umsetzen', 'Nachweis', 'Abnahme', 'git commit', 'Neustart', '400 Zeilen'):
            self.assertIn(wort, text, wort)

    def test_der_systemtext_nennt_volle_pfade_und_verlangt_in_jeder_antwort_einen_schritt(self):
        """Log 03.11.2026: das Modell schrieb nach docs/01_wuensche statt docs/wunsch_umsetzen/01_wuensche und antwortete auf „setze um“ nur mit einer Suche."""
        text = (CONFIG / 'masterchat.md').read_text(encoding='utf-8')
        for pfad in ('docs/wunsch_umsetzen/01_wuensche/W-', 'docs/wunsch_umsetzen/02_auftraege/A-', 'docs/wunsch_umsetzen/03_ergebnisse/', 'docs/wunsch_umsetzen/04_luecken/L-'):
            self.assertIn(pfad, text)
        self.assertIn('jeder Antwort einen Schritt weiter', text)
        self.assertIn('nur sucht oder zusammenfasst', text)
        self.assertIn('pfad: runtime/src', text)
        self.assertIn('ohne dass es einen Auftrag gibt', text)

    def test_der_systemtext_verlangt_die_syntaxpruefung_nach_jeder_aenderung(self):
        """Log 03.11.2026: der MasterChat liess in export.py eine Zeile doppelt stehen (Syntaxfehler) und merkte es nicht."""
        text = (CONFIG / 'masterchat.md').read_text(encoding='utf-8')
        self.assertIn('python -m py_compile', text)
        self.assertIn('node --check', text)
        self.assertIn('Prüfe jede Änderung sofort', text)
        yaml_text = (CONFIG / 'masterchat.yaml').read_text(encoding='utf-8')
        self.assertIn('py_compile', yaml_text)
        self.assertIn('node --check', yaml_text)

    def test_der_systemtext_hat_einen_auskunftsteil_mit_lesenden_werkzeugen(self):
        """Der MasterChat gibt auch Auskunft über Sitzungen, Projekte und die Arbeit der Harness (Captain 04.11.2026): erst das Werkzeug fragen, dann antworten."""
        text = (CONFIG / 'masterchat.md').read_text(encoding='utf-8')
        teil = text.split('## Auskunft und Lenkung', 1)[1].split('\n## ', 1)[0]
        self.assertIn('frag das Werkzeug', teil)
        self.assertIn('nenne die Quelle', teil)
        for w in ('arbeitsplatz_stand', 'lauf_status', 'sitzungen_auflisten', 'list_projects', 'list_missions', 'erinnern', 'recent_audit', 'app_oeffnen'):
            self.assertIn('`' + w + '`', teil, w)
            self.assertIn(w, self.m['werkzeuge'])
        self.assertLess(len(teil), 1400)                                                                                # jede Zeile kostet bei jeder Anfrage Token

    def test_jedes_werkzeug_der_vorlage_gibt_es_wirklich(self):
        """Die Ladeprüfung lässt auch „vorgesehene“ Namen durch, die noch nichts ausführen; hier zählt nur, was die Harness oder der Chat wirklich kennt."""
        wirklich = set(HARNESS_NAMEN) | set(CHAT_SCHEMAS)
        self.assertEqual([w for w in self.m['werkzeuge'] if w not in wirklich], [])
        self.assertEqual(len(self.m['werkzeuge']), len(set(self.m['werkzeuge'])))

    def test_jedes_im_systemtext_genannte_werkzeug_steht_in_der_whitelist(self):
        """Nennt der Text ein Werkzeug (in Rückstrichen), das die Vorlage nicht hat, ruft das Modell etwas auf, das der Server abweist."""
        text = (CONFIG / 'masterchat.md').read_text(encoding='utf-8')
        genannt = {n for n in re.findall(r'`([a-z][a-z_]+)`', text) if n in set(HARNESS_NAMEN) | set(CHAT_SCHEMAS)}
        self.assertIn('sitzungen_aufraeumen', genannt)
        self.assertIn('datei_aendern', genannt)
        self.assertEqual(sorted(genannt - set(self.m['werkzeuge'])), [])

    def test_zu_weite_oder_verbotene_erlaubnisse_lehnt_die_pruefung_ab(self):
        schlecht = [
            {'werkzeug': 'datei_schreiben', 'muster': '**'}, {'werkzeug': 'datei_aendern', 'muster': '*'}, {'werkzeug': 'datei_aendern', 'muster': '../x/**'},
            {'werkzeug': 'datei_aendern', 'muster': 'C:/x/**'}, {'werkzeug': 'datei_schreiben', 'muster': 'ohne_ordner'},
            {'werkzeug': 'befehl', 'muster': 'git push*'}, {'werkzeug': 'befehl', 'muster': 'python*'}, {'werkzeug': 'befehl', 'muster': 'node --check x; rm y*'},
            {'werkzeug': 'befehl', 'muster': 'curl http://x*'}, {'werkzeug': 'lauf_starten', 'muster': 'Run Tests'}, {'werkzeug': 'modell_laden', 'muster': 'x'},
            {'werkzeug': 'datei_lesen', 'muster': 'docs/**'}, {'muster': 'docs/**'}, 'docs/**']
        for e in schlecht:
            with self.assertRaises(VorlageFehler, msg=str(e)):
                vorlage(erlaubnisse=[e])
        with self.assertRaises(VorlageFehler):
            vorlage(werkzeuge=['datei_lesen'], erlaubnisse=[{'werkzeug': 'datei_schreiben', 'muster': 'docs/**'}])          # nicht in der Whitelist
        with self.assertRaises(VorlageFehler):
            vorlage(erlaubnisse=[{'werkzeug': 'datei_schreiben', 'muster': f'docs{i}/**'} for i in range(40)])
        with self.assertRaises(VorlageFehler):
            vorlage(hinweis='x' * 1000)
        ok = vorlage(erlaubnisse=[{'werkzeug': 'datei_schreiben', 'muster': 'docs/**'}, {'werkzeug': 'befehl', 'muster': 'python -m py_compile*'}, {'werkzeug': 'lauf_starten', 'muster': 'run_tests'}])
        self.assertEqual(len(ok['erlaubnisse']), 3)
        self.assertEqual(vorlage()['erlaubnisse'], [])                                                                 # ohne Angabe: keine


class FakeMissions:
    def create_mission(self, *a, **k):
        return {'identity': {'mission_id': 'M-FAKE'}}


class AnlegenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sitzungen = Sitzungen(self.root / 'sitzungen')
        api = HarnessApi.__new__(HarnessApi)
        api.sitzungen = self.sitzungen
        api.hub = type('H', (), {'project_root': self.root / 'hub', 'runtime': type('R', (), {'brain': FakeMissions()})()})()
        api._projekt = lambda pid: {'id': pid, 'name': 'Sedra Entwicklung', 'wurzel': str(self.root), 'schreibbereich': ['runtime/**', 'docs/**', 'redesign/**']}
        api._mission_stand = lambda *a, **k: None
        self.gesehen = []
        api._audit = lambda event, payload: self.gesehen.append((event, payload))
        api._melden = lambda *a, **k: None
        self.api = api
        harness_vorlagen.VORLAGEN_DIR_TEST = CONFIG
        self._laden = harness_vorlagen.laden
        harness_vorlagen.laden = lambda root, vid, repo_dir=CONFIG: self._laden(root, vid, CONFIG)
        self.addCleanup(setattr, harness_vorlagen, 'laden', self._laden)

    def test_ohne_ausdrueckliches_ja_entsteht_keine_sitzung(self):
        for payload in ({'vorlage': 'masterchat', 'projekt': 'sedra-entwicklung'}, {'vorlage': 'masterchat', 'projekt': 'sedra-entwicklung', 'erlaubnisse_bestaetigt': 'ja'},
                        {'vorlage': 'masterchat', 'projekt': 'sedra-entwicklung', 'erlaubnisse_bestaetigt': 1}):
            with self.assertRaises(ValueError) as ctx:
                self.api.anlegen(payload)
            self.assertIn('erlaubnisse_nicht_bestaetigt', str(ctx.exception))
        self.assertEqual(self.sitzungen.liste(), [])
        self.assertEqual(self.gesehen, [])

    def test_mit_ja_gelten_die_erlaubnisse_in_dieser_sitzung_und_stehen_im_audit(self):
        kopf = self.api.anlegen({'vorlage': 'masterchat', 'projekt': 'sedra-entwicklung', 'erlaubnisse_bestaetigt': True})
        s = self.sitzungen.laden(kopf['id'])
        self.assertEqual(len(s['erlaubnisse']), 12)
        self.assertEqual(s['erlaubnisse'][0]['karte_id'], 'V-masterchat-1')
        self.assertEqual(s['erlaubnisse'][0]['regel'], 'vorlage-masterchat')
        ereignis = [p for e, p in self.gesehen if e == 'HARNESS_VORLAGE_ERLAUBNISSE'][0]
        self.assertEqual((ereignis['sitzung_id'], ereignis['anzahl']), (kopf['id'], 12))
        andere = self.api.anlegen({'vorlage': 'bauagent', 'projekt': 'sedra-entwicklung'})                         # andere Vorlagen: keine Erlaubnisse, keine Rückfrage nötig
        self.assertEqual(self.sitzungen.laden(andere['id'])['erlaubnisse'], [])

    def test_die_erlaubnisse_lassen_sich_wie_jede_zuruecknehmen(self):
        kopf = self.api.anlegen({'vorlage': 'masterchat', 'projekt': 'sedra-entwicklung', 'erlaubnisse_bestaetigt': True})
        self.sitzungen.erlaubnis_zuruecknehmen(kopf['id'], 'V-masterchat-1')
        self.assertEqual(len(self.sitzungen.laden(kopf['id'])['erlaubnisse']), 11)

    def test_was_sie_oeffnen_und_was_trotzdem_eine_karte_braucht(self):
        kopf = self.api.anlegen({'vorlage': 'masterchat', 'projekt': 'sedra-entwicklung', 'erlaubnisse_bestaetigt': True})
        erl = aktive(self.sitzungen.laden(kopf['id'])['eintraege'])
        wurzel = self.root / 'projekt'
        for rel in ('runtime/src/guppi_runtime/core', 'runtime/src/guppi_runtime/harness', 'runtime/tests', 'docs', 'runtime/config/harness_vorlagen', 'runtime/config'):
            (wurzel / rel).mkdir(parents=True, exist_ok=True)
        (wurzel / 'runtime/src/guppi_runtime/harness/api.py').write_text('a = 1\n', encoding='utf-8')
        (wurzel / 'runtime/src/guppi_runtime/harness/freigabe.py').write_text('f = 1\n', encoding='utf-8')
        (wurzel / 'runtime/src/guppi_runtime/core/guard.py').write_text('g = 1\n', encoding='utf-8')
        (wurzel / 'runtime/config/llama_server.yaml').write_text('x: 1\n', encoding='utf-8')
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, self.root / 'tokens.json')
        regeln = katalog.mit_projekt(katalog.laden(Path('gibt-es-nicht'))['regeln'], {'schreibbereich': ['runtime/**', 'docs/**', 'redesign/**']})
        w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(wurzel), 'schreibbereich': ['runtime/**', 'docs/**', 'redesign/**']}, guard=guard, mission_id='M-MC', regeln=regeln)
        kiste = Kiste(w, regeln=regeln, guard=guard, audit=None, karten=Karten(self.root / 'karten'), sitzung_id=kopf['id'], erlaubnisse=erl)
        frei = [('datei_schreiben', {'pfad': 'docs/neu.md', 'inhalt': 'a\n'}), ('datei_schreiben', {'pfad': 'runtime/tests/test_x.py', 'inhalt': 'a\n'}),
                ('datei_aendern', {'pfad': 'runtime/src/guppi_runtime/harness/api.py', 'alt': 'a = 1', 'neu': 'a = 2'})]
        for name, args in frei:
            r = kiste.aufruf(name, args)
            self.assertEqual(r['status'], 'ok', (name, args, r))
            self.assertTrue(r['stufe'] in ('sitzung', 'frei'), r)
        self.assertEqual((wurzel / 'runtime/src/guppi_runtime/harness/api.py').read_text(encoding='utf-8'), 'a = 2\n')
        karte = [('datei_aendern', {'pfad': 'runtime/src/guppi_runtime/harness/freigabe.py', 'alt': 'f = 1', 'neu': 'f = 2'}),        # fester Vorbehalt: Freigabe-Code
                 ('datei_aendern', {'pfad': 'runtime/src/guppi_runtime/core/guard.py', 'alt': 'g = 1', 'neu': 'g = 2'}),               # fester Vorbehalt: Kern
                 ('datei_schreiben', {'pfad': 'runtime/config/harness_vorlagen/neu.md', 'inhalt': 'x\n'}),                             # fester Vorbehalt: Vorlagen
                 ('datei_aendern', {'pfad': 'runtime/config/llama_server.yaml', 'alt': 'x: 1', 'neu': 'x: 2'}),                         # keine Erlaubnis für runtime/config
                 ('befehl', {'befehl': 'git push origin main'}), ('befehl', {'befehl': 'git commit -m x'})]
        for name, args in karte:
            r = kiste.aufruf(name, args)
            self.assertIn(r['status'], ('wartet', 'verboten', 'fehler'), (name, args, r))
            self.assertNotEqual(r.get('stufe'), 'sitzung', (name, args))
        self.assertEqual((wurzel / 'runtime/src/guppi_runtime/harness/freigabe.py').read_text(encoding='utf-8'), 'f = 1\n')
        self.assertEqual((wurzel / 'runtime/src/guppi_runtime/core/guard.py').read_text(encoding='utf-8'), 'g = 1\n')


if __name__ == '__main__':
    unittest.main()
