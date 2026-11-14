"""W4 ohne zweite Freigabe: `rueckblick_schreiben` und `vorschlaege_pflegen` legen nur einen Antrag im Posteingang an (wie `prozess_beantragen`); der Antrag
ist die Freigabe, eine Karte davor gibt es nicht mehr. Gegenproben: nichts wird geschrieben, ein verbotener Eintrag im Katalog stoppt sie, ein fehlendes
Pflichtfeld legt keinen Antrag an."""
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import katalog
from sedra_runtime.harness.freigabe import Karten, Kiste
from sedra_runtime.harness.werkzeuge import Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'


class OhneKarteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'projekt'
        (root / 'docs').mkdir(parents=True)
        self.root = root
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        projekt = {'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': ['docs/**']}
        self.regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        self.antraege = []
        self.w = Werkzeuge(projekt, guard=self.guard, mission_id='M-HARNESS', regeln=self.regeln,
                           rueckblick_antrag=lambda a: self.antraege.append(('rueckblick', a)) or {'ok': True},
                           vorschlag_antrag=lambda a: self.antraege.append(('vorschlag', a)) or {'ok': True})
        self.karten = Karten(Path(self.tmp.name) / 'karten')

    def kiste(self, regeln=None):
        return Kiste(self.w, regeln=regeln or self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id='S-00000001')

    def test_rueckblick_legt_direkt_einen_antrag_an_ohne_karte(self):
        r = self.kiste().aufruf('rueckblick_schreiben', {'titel': 'Lauf 14.11.', 'was_gelaufen_ist': 'Specs fertig'})
        self.assertEqual((r['status'], r['wirkung']), ('ok', False))
        self.assertIn('liegt im Posteingang', r['ergebnis'])
        self.assertEqual([a[0] for a in self.antraege], ['rueckblick'])
        self.assertEqual(self.antraege[0][1]['titel'], 'Lauf 14.11.')
        self.assertNotIn('karte', r, 'der Antrag ist die Freigabe, keine zweite Karte davor')
        self.assertFalse((self.root / 'docs' / 'AAR').exists(), 'es wird nichts geschrieben')

    def test_vorschlag_legt_direkt_einen_antrag_an_ohne_karte(self):
        r = self.kiste().aufruf('vorschlaege_pflegen', {'titel': 'Tests schneller', 'aktion': 'anlegen'})
        self.assertEqual((r['status'], r['wirkung']), ('ok', False))
        self.assertEqual([a[0] for a in self.antraege], ['vorschlag'])
        self.assertNotIn('karte', r)

    def test_gegenprobe_pflichtfeld_fehlt_kein_antrag(self):
        r = self.kiste().aufruf('rueckblick_schreiben', {'was_gelaufen_ist': 'ohne Titel'})
        self.assertEqual(r['status'], 'fehler')
        self.assertEqual(self.antraege, [])

    def test_gegenprobe_ein_verboten_im_katalog_stoppt_sie(self):
        regeln = list(self.regeln) + [{'id': 'verbot-rueckblick', 'werkzeug': ['rueckblick_schreiben'], 'muster': ['**'], 'stufe': 'verboten', 'begruendung': 'Test'}]
        regeln = katalog.pruefe_entwurf(regeln)
        r = self.kiste(regeln).aufruf('rueckblick_schreiben', {'titel': 'x', 'was_gelaufen_ist': 'y'})
        self.assertEqual(r['status'], 'verboten')
        self.assertEqual(self.antraege, [])

    def test_gegenprobe_ohne_antragsweg_kommt_ein_fehler_kein_stilles_ok(self):
        w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(self.root), 'schreibbereich': ['docs/**']}, guard=self.guard, mission_id='M', regeln=self.regeln)
        kiste = Kiste(w, regeln=self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id='S-00000002')
        r = kiste.aufruf('vorschlaege_pflegen', {'titel': 'x', 'aktion': 'anlegen'})
        self.assertEqual(r['status'], 'fehler')


if __name__ == '__main__':
    unittest.main()
