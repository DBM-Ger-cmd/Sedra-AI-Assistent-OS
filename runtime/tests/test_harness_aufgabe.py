"""N3 der Harness-Shell Stufe 3 (rein, ohne Server): Deckung und Zustand der Aufgaben-Freigabe, Prüfung beim Anlegen (Pflichtgrenzen D-G4,
weite Muster S4, Schreiben-dann-Ausführen S9), Speicher, Zähler, Ablauf, Rücknahme, weicher Vorbehalt und die neuen harten Vorbehalte (S8)."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from guppi_runtime.harness import aufgabe, aufgabe_deckung, katalog, vorbehalte

JETZT = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
S1, S2 = 'S-11111111', 'S-22222222'


def roh(**kw):
    a = {'id': 'T-00000001', 'sitzungen': [S1], 'erlaubt': [{'werkzeug': 'datei_schreiben', 'muster': 'docs/**'}], 'status': 'aktiv', 'aufrufe': 0,
         'ende': {'bis': (JETZT + timedelta(hours=1)).isoformat(), 'max_aufrufe': 3}}
    a.update(kw)
    return a


def eingabe(**kw):
    d = {'titel': 'Test', 'projekt': 'p', 'sitzungen': [S1], 'erlaubt': [{'werkzeug': 'datei_aendern', 'muster': 'docs/log.md'}],
         'ende': {'max_aufrufe': 5}}
    d.update(kw)
    return d


class DeckungTests(unittest.TestCase):
    def deckt(self, aufgaben, werkzeug='datei_schreiben', ziel='docs/a.md', sitzung=S1):
        return aufgabe_deckung.deckt(aufgaben, sitzung, werkzeug, ziel, JETZT, katalog.passt)

    def test_treffer_und_verfehlungen(self):
        self.assertIsNone(self.deckt([]))
        self.assertEqual(self.deckt([roh()])['aufgabe_id'], 'T-00000001')
        self.assertIsNone(self.deckt([roh()], werkzeug='datei_aendern'))
        self.assertIsNone(self.deckt([roh()], sitzung=S2))
        self.assertIsNone(self.deckt([roh()], ziel='runtime/x.py'))

    def test_status_frist_und_zaehler(self):
        for st in ('zurueckgenommen', 'erledigt', 'abgelaufen', 'erschoepft'):
            self.assertIsNone(self.deckt([roh(status=st)]), st)
        grenze = JETZT.isoformat()
        self.assertIsNone(self.deckt([roh(ende={'bis': grenze})]), 'genau auf der Grenze gilt nicht mehr')
        self.assertIsNone(self.deckt([roh(ende={'bis': (JETZT - timedelta(seconds=1)).isoformat()})]))
        self.assertIsNone(self.deckt([roh(aufrufe=3)]))
        self.assertIsNotNone(self.deckt([roh(aufrufe=2)]))
        self.assertIsNone(self.deckt([roh(ende={'bis': '2026-10-29T13:00:00'})]), 'ohne Zeitzone gilt nicht')

    def test_muster_wie_im_katalog(self):
        self.assertIsNotNone(self.deckt([roh(erlaubt=[{'werkzeug': 'befehl', 'muster': 'python benchmarks/run_tests.py *'}])],
                                        werkzeug='befehl', ziel='python  benchmarks/run_tests.py harness'))
        self.assertIsNone(self.deckt([roh(erlaubt=[{'werkzeug': 'befehl', 'muster': 'python benchmarks/run_tests.py *'}])], werkzeug='befehl', ziel='python x.py'))
        self.assertIsNotNone(self.deckt([roh(erlaubt=[{'werkzeug': 'datei_schreiben', 'muster': 'DOCS/**'}])], ziel='docs/a/b.md'))
        self.assertIsNotNone(self.deckt([roh(erlaubt=[{'werkzeug': 'lauf_starten', 'muster': 'run_*'}])], werkzeug='lauf_starten', ziel='run_tests'))

    def test_mehrere_treffer_deterministisch(self):
        spaet = roh(id='T-00000001', ende={'bis': (JETZT + timedelta(hours=5)).isoformat()})
        frueh = roh(id='T-00000009', ende={'bis': (JETZT + timedelta(hours=1)).isoformat()})
        ohne = roh(id='T-00000000', ende={'max_aufrufe': 5})
        self.assertEqual(self.deckt([spaet, frueh, ohne])['aufgabe_id'], 'T-00000009')
        self.assertEqual(self.deckt([spaet, ohne])['aufgabe_id'], 'T-00000001', 'ohne Ende zuletzt')
        gleich = (JETZT + timedelta(hours=2)).isoformat()
        self.assertEqual(self.deckt([roh(id='T-00000005', ende={'bis': gleich}), roh(id='T-00000002', ende={'bis': gleich})])['aufgabe_id'], 'T-00000002')

    def test_zustand_und_muell(self):
        self.assertEqual(aufgabe_deckung.zustand(roh(), JETZT), 'aktiv')
        self.assertEqual(aufgabe_deckung.zustand(roh(aufrufe=3), JETZT), 'erschoepft')
        self.assertEqual(aufgabe_deckung.zustand(roh(ende={'bis': JETZT.isoformat()}), JETZT), 'abgelaufen')
        a = roh()
        vorher = repr(a)
        aufgabe_deckung.zustand(a, JETZT); self.deckt([a])
        self.assertEqual(repr(a), vorher, 'das Eingabeobjekt bleibt unverändert')
        for muell in (None, 'x', 5, [], {}, {'status': 'aktiv'}, {'status': 'aktiv', 'ende': 'kaputt'}):
            aufgabe_deckung.zustand(muell, JETZT)
            self.assertIsNone(self.deckt([muell]) if muell is not None else None)
        self.assertIsNone(self.deckt('kein-liste'))


class PruefenTests(unittest.TestCase):
    def fehler(self, **kw):
        with self.assertRaises(aufgabe.AufgabeFehler) as cm:
            aufgabe.pruefen_neu(eingabe(**kw), jetzt_z=JETZT)
        return str(cm.exception)

    def test_gueltig(self):
        a, warn = aufgabe.pruefen_neu(eingabe(), jetzt_z=JETZT)
        self.assertEqual((a['titel'], a['sitzungen'], a['ende']), ('Test', [S1], {'bei_erledigt': True, 'max_aufrufe': 5}))
        self.assertEqual(warn, [])

    def test_pflichtgrenzen(self):
        self.assertIn('ende_fehlt', self.fehler(ende={}))
        self.assertIn('ende_fehlt', self.fehler(ende={'bei_erledigt': True}))
        self.assertIn('bis_vergangen', self.fehler(ende={'bis': (JETZT - timedelta(minutes=1)).isoformat()}))
        self.assertIn('bis_zu_weit', self.fehler(ende={'bis': (JETZT + timedelta(hours=25)).isoformat()}))
        self.assertIn('bis_ungueltig', self.fehler(ende={'bis': '2026-10-29T13:00:00'}))
        self.assertIn('max_aufrufe_ungueltig', self.fehler(ende={'max_aufrufe': 501}))
        self.assertIn('max_aufrufe_ungueltig', self.fehler(ende={'max_aufrufe': 0}))
        a, _ = aufgabe.pruefen_neu(eingabe(ende={'bis': (JETZT + timedelta(hours=24)).isoformat()}), jetzt_z=JETZT)
        self.assertIn('bis', a['ende'])

    def test_felder(self):
        self.assertIn('sitzungen_fehlen', self.fehler(sitzungen=[]))
        self.assertIn('sitzungen_fehlen', self.fehler(sitzungen=['S-xyz']))
        self.assertIn('erlaubt_fehlt', self.fehler(erlaubt=[]))
        self.assertIn('erlaubt_1_ungueltig', self.fehler(erlaubt=[{'werkzeug': 'hacken', 'muster': 'x'}]))
        self.assertIn('muster_ausserhalb', self.fehler(erlaubt=[{'werkzeug': 'datei_schreiben', 'muster': '../geheim/**'}]))
        self.assertIn('muster_ausserhalb', self.fehler(erlaubt=[{'werkzeug': 'datei_schreiben', 'muster': 'C:/x/**'}]))
        self.assertIn('titel_fehlt', self.fehler(titel=' '))
        self.assertIn('modelle_ungueltig', self.fehler(modelle='coder'))

    def test_weite_muster_nur_beim_captain_mit_warnung(self):
        weit = eingabe(erlaubt=[{'werkzeug': 'datei_schreiben', 'muster': '**'}, {'werkzeug': 'befehl', 'muster': 'git *'}])
        a, warn = aufgabe.pruefen_neu(weit, jetzt_z=JETZT)
        self.assertEqual(len(warn), 2)
        with self.assertRaisesRegex(aufgabe.AufgabeFehler, 'muster_weit'):
            aufgabe.pruefen_neu(weit, jetzt_z=JETZT, vorschlag=True)
        a, warn = aufgabe.pruefen_neu(eingabe(erlaubt=[{'werkzeug': 'datei_lesen', 'muster': '**'}]), jetzt_z=JETZT, vorschlag=True)
        self.assertEqual(warn, [], 'Lesen ist nicht weit (der Katalog regelt es)')

    def test_vorbehalt_im_muster(self):
        e = eingabe(erlaubt=[{'werkzeug': 'datei_schreiben', 'muster': 'docs/local_config/**'}, {'werkzeug': 'befehl', 'muster': 'git push origin *'}])
        a, warn = aufgabe.pruefen_neu(e, jetzt_z=JETZT)
        self.assertEqual(len(warn), 2)
        self.assertTrue(all('Vorbehalt' in w for w in warn))
        with self.assertRaisesRegex(aufgabe.AufgabeFehler, 'vorbehalt'):
            aufgabe.pruefen_neu(e, jetzt_z=JETZT, vorschlag=True)

    def test_s9_schreiben_und_ausfuehren(self):
        e = eingabe(erlaubt=[{'werkzeug': 'datei_schreiben', 'muster': 'docs/skript.py'}, {'werkzeug': 'befehl', 'muster': 'python -c *'}])
        a, warn = aufgabe.pruefen_neu(e, jetzt_z=JETZT)
        self.assertTrue(any('S9' in w for w in warn))
        with self.assertRaisesRegex(aufgabe.AufgabeFehler, 'S9'):
            aufgabe.pruefen_neu(e, jetzt_z=JETZT, vorschlag=True)
        ok = eingabe(erlaubt=[{'werkzeug': 'datei_schreiben', 'muster': 'docs/skript.py'}, {'werkzeug': 'befehl', 'muster': 'python benchmarks/run_tests.py *'}])
        self.assertEqual(aufgabe.pruefen_neu(ok, jetzt_z=JETZT, vorschlag=True)[1], [])

    def test_vorschlag_ohne_vorarbeiter_als_nutzer(self):
        with self.assertRaisesRegex(aufgabe.AufgabeFehler, 'selbstfreigabe'):
            aufgabe.pruefen_neu(eingabe(sitzungen=[S1, S2]), jetzt_z=JETZT, vorschlag=True, verbotene_sitzungen=(S2,))
        aufgabe.pruefen_neu(eingabe(sitzungen=[S1, S2]), jetzt_z=JETZT, vorschlag=False, verbotene_sitzungen=(S2,))


class SpeicherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aufgaben-')
        self.ordner = Path(self.tmp.name) / 'aufgaben'
        self.audit, self.ereignisse = [], []
        self.store = aufgabe.Aufgaben(self.ordner, audit=self._audit, melden=lambda n, d: self.ereignisse.append((n, d)))

    def tearDown(self):
        self.tmp.cleanup()

    def _audit(self, event, payload, **_):
        self.audit.append((event, payload))

    def neu(self, **kw):
        a, _ = self.store.anlegen(eingabe(**kw), jetzt_z=JETZT)
        return a

    def test_anlegen_laden_neustart(self):
        a = self.neu()
        self.assertRegex(a['id'], r'T-[0-9A-F]{8}')
        self.assertEqual((a['status'], a['aufrufe'], a['von']), ('aktiv', 0, 'captain'))
        neu = aufgabe.Aufgaben(self.ordner)
        self.assertEqual(neu.laden(a['id'], JETZT)['titel'], 'Test')
        self.assertEqual([x['id'] for x in neu.alle('aktiv', JETZT)], [a['id']])
        self.assertEqual(self.audit[0][0], 'HARNESS_AUFGABE_ANGELEGT')
        self.assertEqual(self.ereignisse[0], ('harness.aufgabe', {'id': a['id'], 'zustand': 'aktiv'}))
        with self.assertRaises(KeyError):
            self.store.laden('T-FFFFFFFF')
        with self.assertRaises(KeyError):
            self.store.laden('../x')

    def test_zaehler_erschoepft_sich_mit_audit(self):
        a = self.neu(ende={'max_aufrufe': 2})
        self.assertTrue(self.store.zaehlen(a['id'], JETZT))
        self.assertEqual(self.store.laden(a['id'], JETZT)['status'], 'aktiv')
        self.assertTrue(self.store.zaehlen(a['id'], JETZT))
        self.assertEqual(self.store.laden(a['id'], JETZT)['status'], 'erschoepft')
        self.assertFalse(self.store.zaehlen(a['id'], JETZT))
        self.assertEqual(self.store.laden(a['id'], JETZT)['aufrufe'], 2)
        self.assertIn('HARNESS_AUFGABE_ERSCHOEPFT', [e for e, _ in self.audit])

    def test_ablauf_wird_festgestellt(self):
        a = self.neu(ende={'bis': (JETZT + timedelta(minutes=10)).isoformat()})
        self.assertEqual(self.store.laden(a['id'], JETZT + timedelta(minutes=5))['status'], 'aktiv')
        spaeter = JETZT + timedelta(minutes=11)
        self.assertEqual(self.store.laden(a['id'], spaeter)['status'], 'abgelaufen')
        self.assertFalse(self.store.zaehlen(a['id'], spaeter))
        self.assertIsNone(self.store.deckt(S1, 'datei_aendern', 'docs/log.md', jetzt_z=spaeter))
        self.assertIn('HARNESS_AUFGABE_ABGELAUFEN', [e for e, _ in self.audit])

    def test_deckung_nur_fuer_genannte_sitzung_und_weich_nur_mit_modell(self):
        a = self.neu()
        self.assertEqual(self.store.deckt(S1, 'datei_aendern', 'docs/log.md', jetzt_z=JETZT)['aufgabe_id'], a['id'])
        self.assertIsNone(self.store.deckt(S2, 'datei_aendern', 'docs/log.md', jetzt_z=JETZT))
        b = self.neu(erlaubt=[{'werkzeug': 'modell_laden', 'muster': 'coder.*'}], modelle=['coder.llama_qwen35'])
        weich = vorbehalte.pruefen_weich('modell_laden', 'coder.llama_qwen35')
        self.assertEqual(self.store.deckt(S1, 'modell_laden', 'coder.llama_qwen35', weich=weich, jetzt_z=JETZT)['aufgabe_id'], b['id'])
        fremd = vorbehalte.pruefen_weich('modell_laden', 'coder.anderes')
        self.assertIsNone(self.store.deckt(S1, 'modell_laden', 'coder.anderes', weich=fremd, jetzt_z=JETZT), 'das Modell steht nicht in `modelle`')

    def test_ruecknahme_und_beenden(self):
        a = self.neu()
        z = self.store.zuruecknehmen(a['id'], 'Fehler', jetzt_z=JETZT)
        self.assertEqual((z['status'], z['grund']), ('zurueckgenommen', 'Fehler'))
        self.assertIsNone(self.store.deckt(S1, 'datei_aendern', 'docs/log.md', jetzt_z=JETZT))
        with self.assertRaisesRegex(aufgabe.AufgabeFehler, 'nicht_aktiv'):
            self.store.zuruecknehmen(a['id'])
        b = self.neu(ende={'max_aufrufe': 3, 'bei_erledigt': False})
        with self.assertRaisesRegex(aufgabe.AufgabeFehler, 'beenden_nicht_erlaubt'):
            self.store.beenden(b['id'], 'fertig', wer='vorarbeiter:S-1', jetzt_z=JETZT)
        self.assertEqual(self.store.beenden(b['id'], 'fertig', wer='captain', jetzt_z=JETZT)['status'], 'erledigt')
        c = self.neu()
        self.assertEqual(self.store.beenden(c['id'], 'fertig', wer='vorarbeiter:S-1', jetzt_z=JETZT)['status'], 'erledigt')
        self.assertTrue({'HARNESS_AUFGABE_ZURUECKGENOMMEN', 'HARNESS_AUFGABE_BEENDET'} <= {e for e, _ in self.audit})

    def test_oeffentlich_rest(self):
        a = self.neu(ende={'bis': (JETZT + timedelta(minutes=30)).isoformat(), 'max_aufrufe': 5})
        self.store.zaehlen(a['id'], JETZT)
        o = aufgabe.oeffentlich(self.store.laden(a['id'], JETZT), JETZT)
        self.assertEqual((o['rest_aufrufe'], o['rest_min']), (4, 30))


class VorbehaltTests(unittest.TestCase):
    def test_neue_harte_pfade(self):
        for pfad in ('runtime/src/guppi_runtime/harness/aufgabe.py', 'runtime/src/guppi_runtime/harness/aufgabe_deckung.py',
                     'runtime/src/guppi_runtime/harness/vorarbeiter.py', 'runtime/src/guppi_runtime/harness/lauf.py',
                     'runtime/src/guppi_runtime/harness/lauf_huelle.py', 'runtime/src/guppi_runtime/harness/herkunft.py',
                     'runtime/config/harness_vorlagen/vorarbeiter.md', 'runtime/config/harness_vorlagen/neu.yaml', 'runtime/config/harness_laeufe.yaml',
                     'workspace/GUPPI_OS/runtime_data/harness/aufgaben/T-00000001.json', 'runtime_data/harness/karten/K-00000001.json'):
            for w in ('datei_schreiben', 'datei_aendern'):
                self.assertIsNotNone(vorbehalte.pruefen(w, pfad, {'inhalt': 'x'}), (w, pfad))
        self.assertIsNone(vorbehalte.pruefen('datei_aendern', 'runtime/src/guppi_runtime/harness/schleife.py', {'alt': 'a', 'neu': 'b'}))

    def test_weicher_vorbehalt(self):
        self.assertEqual(vorbehalte.pruefen_weich('modell_laden', ' coder.x ')['modell'], 'coder.x')
        self.assertIsNotNone(vorbehalte.pruefen_weich('modell_entladen', 'coder.x'))
        for w in ('datei_schreiben', 'befehl', 'lauf_starten', 'datei_lesen'):
            self.assertIsNone(vorbehalte.pruefen_weich(w, 'x'), w)

    def test_katalog_kennt_die_neuen_werkzeuge(self):
        for w in ('lauf_starten', 'lauf_stoppen', 'modell_laden', 'modell_entladen'):
            self.assertIn(w, katalog.WERKZEUGE)
        regeln = katalog.pruefen({'freigabe_katalog': {'regeln': [{'id': 'lauf-tests', 'werkzeug': 'lauf_starten', 'muster': ['run_tests'],
                                                                   'stufe': 'vorarbeiter', 'begruendung': 'Tests ändern nichts.'}]}})
        self.assertEqual(katalog.einstufen(regeln, 'lauf_starten', 'run_tests')['stufe'], 'vorarbeiter')
        self.assertEqual(katalog.einstufen(regeln, 'lauf_starten', 'devvm_build')['stufe'], 'captain')


if __name__ == '__main__':
    unittest.main()
