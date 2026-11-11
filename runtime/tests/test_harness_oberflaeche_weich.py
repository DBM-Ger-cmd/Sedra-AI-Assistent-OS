"""Apps v1 O3, der weiche Teil (SPEC_APPS_v1_O3PLUS_G9_G2 O3-03 bis O3-05, G1-01 bis G1-04): der Code der Oberfläche (`uix/shells/**`, `uix/tools/**`, `uix/css/**`) ist ein weicher Vorbehalt –
er gilt vor dem Katalog (auch bei `frei`), nur eine aktive Aufgabe mit dem Pfad in `oberflaeche` deckt ihn; Sitzungs-Erlaubnis und Vorarbeiter nie.
Die Aufgabe für die Oberfläche ist eng: ein Ordner, vom Captain, höchstens eine je Projekt."""
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import aufgabe as aufgabe_mod
from sedra_runtime.harness import vorbehalte
from sedra_runtime.harness.aufgabe import AufgabeFehler, Aufgaben, pruefen_neu
from sedra_runtime.harness.freigabe import Karten, Kiste, einstufung
from sedra_runtime.harness.werkzeuge import Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
S = 'runtime/src/sedra_runtime/uix/'
TASKLEISTE = S + 'shells/harness/taskleiste.js'
SHELL_CSS = S + 'shells/harness/shell.css'
GAUGE_JS = S + 'tools/gauge-ram/tool.js'
SITZUNG = 'S-0000000A'


def regel(rid, werkzeug, muster, stufe):
    return {'id': rid, 'werkzeug': werkzeug, 'muster': muster, 'stufe': stufe, 'begruendung': rid}


class Weich(unittest.TestCase):
    def test_oberflaeche_ist_weich(self):
        for pfad in (TASKLEISTE, SHELL_CSS, GAUGE_JS, S + 'css/x.css', S + 'shells/neu/shell.js', S + 'tools/neu/preview.png', 'RUNTIME\\SRC\\sedra_runtime\\Uix\\Shells\\Harness\\Taskleiste.js'):
            for w in ('datei_schreiben', 'datei_aendern'):
                weich = vorbehalte.pruefen_weich(w, pfad, {'inhalt': 'x'})
                self.assertIsNotNone(weich, (w, pfad))
                self.assertIn('Code der Oberfläche', weich['grund'])
                self.assertTrue(weich['oberflaeche'].startswith('runtime/src/sedra_runtime/uix/'))
                self.assertNotIn('modell', weich)

    def test_was_frei_oder_hart_ist_bleibt_so(self):
        for pfad in (S + 'shells/harness/README.md', S + 'tools/gauge-ram/README.md', 'docs/x.md', 'runtime/src/sedra_runtime/harness/schleife.py', '../ausserhalb/x.js'):
            self.assertIsNone(vorbehalte.pruefen_weich('datei_aendern', pfad, {'alt': 'a', 'neu': 'b'}), pfad)
        for hart in (S + 'ui/loader.js', S + 'tools/gauge-ram/tool.yaml', S + 'shells/harness/shell.yaml', S + 'shells/harness/arbeitsplatz.yaml'):
            self.assertIsNone(vorbehalte.pruefen_weich('datei_aendern', hart, {'alt': 'a', 'neu': 'b'}), hart)
            self.assertIsNotNone(vorbehalte.pruefen('datei_aendern', hart, {'alt': 'a', 'neu': 'b'}), hart)

    def test_lesen_und_befehle_sind_nicht_weich(self):
        self.assertIsNone(vorbehalte.pruefen_weich('datei_lesen', TASKLEISTE))
        self.assertIsNone(vorbehalte.pruefen_weich('befehl', 'python x.py'))

    def test_modelle_bleiben_wie_sie_waren(self):
        weich = vorbehalte.pruefen_weich('modell_laden', 'coder.local_primary_team')
        self.assertEqual(weich['modell'], 'coder.local_primary_team')
        self.assertNotIn('oberflaeche', weich)


class VorDemKatalog(unittest.TestCase):
    """O3-04 (schließt N2): ein `frei` im Katalog hebt den weichen Vorbehalt der Oberfläche nicht auf."""

    def einstufen(self, stufe, pfad, werkzeug='datei_aendern'):
        regeln = [regel('schreiben', ['datei_schreiben', 'datei_aendern'], ['**'], stufe)]
        return einstufung(regeln, werkzeug, {'alt': 'a', 'neu': 'b', 'inhalt': 'x'}, {'ziel': pfad})

    def test_frei_wird_zur_karte_an_den_captain(self):
        e = self.einstufen('frei', TASKLEISTE)
        self.assertEqual((e['stufe'], e['wirkt_als'], e['regel'], e['vorbehalt']), ('captain', 'captain', 'vorbehalt-weich', False))
        self.assertIn('Code der Oberfläche', e['begruendung'])

    def test_vorarbeiter_wird_zum_captain(self):
        e = self.einstufen('vorarbeiter', GAUGE_JS)
        self.assertEqual((e['stufe'], e['wirkt_als']), ('captain', 'captain'))

    def test_ein_captain_im_katalog_bleibt_captain(self):
        e = self.einstufen('captain', TASKLEISTE)
        self.assertEqual((e['stufe'], e['regel']), ('captain', 'schreiben'))

    def test_readme_und_andere_pfade_bleiben_frei(self):
        self.assertEqual(self.einstufen('frei', S + 'shells/harness/README.md')['stufe'], 'frei')
        self.assertEqual(self.einstufen('frei', 'docs/x.md')['stufe'], 'frei')

    def test_harter_vorbehalt_geht_weiter_vor(self):
        e = self.einstufen('frei', S + 'ui/loader.js')
        self.assertEqual((e['regel'], e['vorbehalt']), ('vorbehalt', True))


def aufgabe(**mehr):
    doc = {'titel': 'Taskleiste', 'zweck': 'Die Taskleiste anpassen', 'projekt': 'p', 'sitzungen': [SITZUNG], 'ende': {'max_aufrufe': 10},
           'erlaubt': [{'werkzeug': 'datei_aendern', 'muster': S + 'shells/harness/**'}, {'werkzeug': 'datei_lesen', 'muster': S + '**'}]}
    doc.update(mehr)
    return doc


class FeldOberflaeche(unittest.TestCase):
    def test_gueltig(self):
        a, _ = pruefen_neu(aufgabe(oberflaeche=[S + 'shells/harness/taskleiste.js', S + 'shells/harness/*.css']))
        self.assertEqual(a['oberflaeche'], [S + 'shells/harness/taskleiste.js', S + 'shells/harness/*.css'])

    def test_ohne_das_feld_ist_es_leer(self):
        self.assertEqual(pruefen_neu(aufgabe())[0]['oberflaeche'], [])

    def test_zu_breit(self):
        for muster in (S + '**', S + 'shells/**', S + 'shells/*/shell.js', S + 'tools/**/tool.js', S + 'shells/harness', 'docs/**', '**'):
            with self.assertRaises(AufgabeFehler) as fehler:
                pruefen_neu(aufgabe(oberflaeche=[muster], erlaubt=[{'werkzeug': 'datei_aendern', 'muster': '**'}]))
            self.assertIn('oberflaeche_zu_breit', str(fehler.exception), muster)

    def test_ein_ordner(self):
        erlaubt = [{'werkzeug': 'datei_aendern', 'muster': S + '**'}]
        with self.assertRaises(AufgabeFehler) as fehler:
            pruefen_neu(aufgabe(oberflaeche=[S + 'shells/harness/a.js', S + 'tools/gauge-ram/tool.js'], erlaubt=erlaubt))
        self.assertIn('oberflaeche_mehrere_ordner', str(fehler.exception))
        a, _ = pruefen_neu(aufgabe(oberflaeche=[S + 'css/a.css', S + 'css/b.css'], erlaubt=erlaubt))
        self.assertEqual(len(a['oberflaeche']), 2)

    def test_jedes_muster_muss_erlaubt_sein(self):
        with self.assertRaises(AufgabeFehler) as fehler:
            pruefen_neu(aufgabe(oberflaeche=[S + 'tools/gauge-ram/tool.js']))               # erlaubt nennt nur shells/harness
        self.assertIn('oberflaeche_nicht_erlaubt', str(fehler.exception))
        with self.assertRaises(AufgabeFehler):
            pruefen_neu(aufgabe(oberflaeche=[S + 'shells/harness/a.js'], erlaubt=[{'werkzeug': 'datei_lesen', 'muster': '**'}]))      # Lesen zählt nicht

    def test_ungueltig(self):
        for roh in ('text', [''], [5], {'a': 1}):
            with self.assertRaises(AufgabeFehler) as fehler:
                pruefen_neu(aufgabe(oberflaeche=roh))
            self.assertIn('oberflaeche_ungueltig', str(fehler.exception), roh)

    def test_ein_vorschlag_des_vorarbeiters_darf_es_nicht_enthalten(self):
        with self.assertRaises(AufgabeFehler) as fehler:
            pruefen_neu(aufgabe(oberflaeche=[S + 'shells/harness/a.js']), vorschlag=True)
        self.assertIn('oberflaeche_nur_captain', str(fehler.exception))
        pruefen_neu(aufgabe(), vorschlag=True)                                                # ohne das Feld bleibt ein Vorschlag möglich

    def test_hinweis_in_der_oeffentlichen_aufgabe(self):
        a, _ = pruefen_neu(aufgabe(oberflaeche=[S + 'shells/harness/a.js']))
        self.assertIn('läuft in der Oberfläche mit allen Rechten', aufgabe_mod.oeffentlich(dict(a, id='T-00000001', aufrufe=0))['oberflaeche_hinweis'])
        self.assertIsNone(aufgabe_mod.oeffentlich(dict(pruefen_neu(aufgabe())[0], id='T-00000002', aufrufe=0))['oberflaeche_hinweis'])


class Speicher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.aufgaben = Aufgaben(Path(self.tmp.name) / 'aufgaben')

    def test_hoechstens_eine_aktive_aufgabe_je_projekt(self):
        a, _ = self.aufgaben.anlegen(aufgabe(oberflaeche=[S + 'shells/harness/a.js']))
        with self.assertRaises(AufgabeFehler) as fehler:
            self.aufgaben.anlegen(aufgabe(oberflaeche=[S + 'shells/harness/b.js']))
        self.assertEqual(str(fehler.exception), 'oberflaeche_schon_aktiv: ' + a['id'])
        self.aufgaben.anlegen(aufgabe())                                                      # ohne `oberflaeche` immer möglich
        self.aufgaben.anlegen(aufgabe(projekt='anderes', oberflaeche=[S + 'shells/harness/b.js']))      # anderes Projekt
        self.aufgaben.beenden(a['id'], 'fertig')
        self.aufgaben.anlegen(aufgabe(oberflaeche=[S + 'shells/harness/b.js']))                # nach dem Ende wieder

    def test_nur_der_genannte_pfad_deckt(self):
        self.aufgaben.anlegen(aufgabe(oberflaeche=[S + 'shells/harness/taskleiste.js']))
        weich = vorbehalte.pruefen_weich('datei_aendern', TASKLEISTE, {'alt': 'a', 'neu': 'b'})
        self.assertIsNotNone(self.aufgaben.deckt(SITZUNG, 'datei_aendern', TASKLEISTE, weich=weich))
        anderer = vorbehalte.pruefen_weich('datei_aendern', SHELL_CSS, {'alt': 'a', 'neu': 'b'})
        self.assertIsNone(self.aufgaben.deckt(SITZUNG, 'datei_aendern', SHELL_CSS, weich=anderer), 'erlaubt trifft, aber `oberflaeche` nennt die Datei nicht')

    def test_eine_aufgabe_ohne_oberflaeche_deckt_nie(self):
        self.aufgaben.anlegen(aufgabe())
        weich = vorbehalte.pruefen_weich('datei_aendern', TASKLEISTE, {'alt': 'a', 'neu': 'b'})
        self.assertIsNone(self.aufgaben.deckt(SITZUNG, 'datei_aendern', TASKLEISTE, weich=weich))

    def test_die_deckung_der_modelle_ist_unveraendert(self):
        self.aufgaben.anlegen(aufgabe(modelle=['coder.local_primary_1x80k'], erlaubt=[{'werkzeug': 'modell_laden', 'muster': '**'}]))
        weich = vorbehalte.pruefen_weich('modell_laden', 'coder.local_primary_1x80k')
        self.assertIsNotNone(self.aufgaben.deckt(SITZUNG, 'modell_laden', 'coder.local_primary_1x80k', weich=weich))
        self.assertIsNone(self.aufgaben.deckt(SITZUNG, 'modell_laden', 'coder.local_primary_team', weich=vorbehalte.pruefen_weich('modell_laden', 'coder.local_primary_team')))


class GanzerWeg(unittest.TestCase):
    """Mit echtem Guard und einem Katalog, der alles Schreiben `frei` gibt – wie eine großzügige Sitzung: die Oberfläche bleibt eine Karte, außer eine Aufgabe nennt den Pfad."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'projekt'
        for rel in (TASKLEISTE, SHELL_CSS, S + 'shells/harness/README.md'):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text('alt\n', encoding='utf-8')
        (self.root / 'docs').mkdir()
        (self.root / 'docs' / 'notiz.md').write_text('alt\n', encoding='utf-8')
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        self.regeln = [regel('lesen', ['datei_lesen', 'dateien_auflisten', 'suchen'], ['**'], 'frei'), regel('schreiben', ['datei_schreiben', 'datei_aendern'], ['**'], 'frei')]
        projekt = {'id': 'p', 'name': 'P', 'wurzel': str(self.root), 'schreibbereich': ['**']}
        self.w = Werkzeuge(projekt, guard=self.guard, mission_id='M-O3WEICH', regeln=self.regeln)
        self.karten = Karten(Path(self.tmp.name) / 'karten')
        self.aufgaben = Aufgaben(Path(self.tmp.name) / 'aufgaben')
        self.kiste = Kiste(self.w, regeln=self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id=SITZUNG, aufgaben=self.aufgaben, projekt_id='p')

    def aendern(self, pfad):
        return self.kiste.aufruf('datei_aendern', {'pfad': pfad, 'alt': 'alt', 'neu': 'neu'})

    def test_oberflaeche_wird_trotz_frei_zur_karte(self):
        out = self.aendern(TASKLEISTE)
        self.assertEqual(out['status'], 'wartet', out)
        self.assertEqual(out['regel'], 'vorbehalt-weich')
        self.assertEqual((self.root / TASKLEISTE).read_text(encoding='utf-8'), 'alt\n', 'nichts geschrieben')
        self.assertEqual(self.karten.laden(out['karte']['karte_id'])['an'], 'captain')

    def test_readme_und_normale_dateien_laufen_frei(self):
        self.assertEqual(self.aendern(S + 'shells/harness/README.md')['status'], 'ok')
        self.assertEqual(self.aendern('docs/notiz.md')['status'], 'ok')

    def test_eine_aufgabe_mit_dem_pfad_deckt_nur_diesen(self):
        self.aufgaben.anlegen(aufgabe(oberflaeche=[TASKLEISTE]))
        gedeckt = self.aendern(TASKLEISTE)
        self.assertEqual(gedeckt['status'], 'ok', gedeckt)
        self.assertEqual(gedeckt['stufe'], 'aufgabe')
        self.assertEqual((self.root / TASKLEISTE).read_text(encoding='utf-8'), 'neu\n')
        anders = self.aendern(SHELL_CSS)
        self.assertEqual(anders['status'], 'wartet', 'die Aufgabe nennt das CSS nicht')

    def test_eine_sitzungs_erlaubnis_deckt_die_oberflaeche_nie(self):
        kiste = Kiste(self.w, regeln=self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id=SITZUNG, aufgaben=self.aufgaben, projekt_id='p',
                      erlaubnisse=[{'karte_id': 'K-00000001', 'werkzeug': 'datei_aendern', 'muster': S + 'shells/harness/**'}])
        out = kiste.aufruf('datei_aendern', {'pfad': TASKLEISTE, 'alt': 'alt', 'neu': 'neu'})
        self.assertEqual(out['status'], 'wartet', out)


if __name__ == '__main__':
    unittest.main()
