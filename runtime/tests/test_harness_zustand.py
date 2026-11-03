"""Zustandswerkzeuge gebündelt (02.11.2026, Token sparen): die elf lesenden Werkzeuge stehen der Anfrage als EIN Werkzeug `zustand` mit Auswahl `was` vor
(Messung mit dem echten Router: rund 340 Token weniger je Anfrage). Die einzelnen Namen und die Whitelist einer Vorlage gelten weiter."""
import json
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.chat_tools import ChatTools
from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import katalog
from guppi_runtime.harness.api import LESEN
from guppi_runtime.harness.freigabe import Karten, Kiste
from guppi_runtime.harness.vorlagen import Begrenzt
from guppi_runtime.harness.werkzeuge import Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'


class Hub:
    def chat_projects(self):
        return [{'id': 'sedra', 'name': 'Sedra'}]


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / 'projekt').mkdir()
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, root / 'tokens.json')
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(root / 'projekt'), 'schreibbereich': ['docs/**']}, guard=guard, mission_id='M-Z', regeln=regeln)
        self.kiste = Kiste(w, regeln=regeln, guard=guard, audit=None, karten=Karten(root / 'karten'), sitzung_id='S-00000001', chat=ChatTools(Hub(), LESEN))


class ZustandTests(Basis):
    def namen(self, box):
        return [s['function']['name'] for s in box.schemas()]

    def test_statt_elf_einzelner_nur_ein_zustandswerkzeug_mit_auswahl(self):
        namen = self.namen(self.kiste)
        self.assertEqual(sum(1 for n in namen if n in LESEN), 0)
        self.assertEqual(namen.count('zustand'), 1)
        z = next(s for s in self.kiste.schemas() if s['function']['name'] == 'zustand')
        self.assertEqual(z['function']['parameters']['properties']['was']['enum'], list(LESEN))

    def test_der_aufruf_geht_an_das_gewaehlte_einzelwerkzeug(self):
        r = self.kiste.aufruf('zustand', {'was': 'list_projects'})
        self.assertEqual((r['status'], r['stufe'], r['regel'], r['wirkung']), ('ok', 'frei', 'zustand-lesen', False))
        self.assertIn('Sedra', r['ergebnis'])
        self.assertEqual(self.kiste.aufruf('list_projects', {})['status'], 'ok')             # der alte Name gilt weiter (Verlauf, Gewohnheit des Modells)
        r2 = self.kiste.aufruf('zustand', {'was': 'gibt_es_nicht'})
        self.assertEqual(r2['status'], 'fehler')
        self.assertIn('erlaubt', r2['ergebnis'])
        self.assertEqual(self.kiste.aufruf('zustand', {})['status'], 'fehler')

    def test_eine_vorlage_bekommt_nur_die_zustandswerkzeuge_die_sie_nennt(self):
        eng = Begrenzt(self.kiste, ['datei_lesen', 'list_projects', 'get_switches'])
        z = next(s for s in eng.schemas() if s['function']['name'] == 'zustand')
        self.assertEqual(z['function']['parameters']['properties']['was']['enum'], ['get_switches', 'list_projects'])
        self.assertEqual(eng.aufruf('zustand', {'was': 'list_projects'})['status'], 'ok')
        nein = eng.aufruf('zustand', {'was': 'recent_audit'})
        self.assertEqual(nein['status'], 'fehler')
        self.assertIn('nicht erlaubt', nein['ergebnis'])
        ohne = Begrenzt(self.kiste, ['datei_lesen'])                                           # nennt die Vorlage keines: kein Zustandswerkzeug
        self.assertNotIn('zustand', [s['function']['name'] for s in ohne.schemas()])

    def test_list_projects_nennt_die_projekte_der_harness_und_markiert_das_der_sitzung(self):
        """Log 02.11.2026: das Modell hielt „Earth 2140“ für unbekannt, weil die Liste des SEDRA-Kerns leer war, obwohl die Sitzung schon in diesem Projekt lief."""
        liste = [{'id': 'sedra', 'name': 'Sedra', 'ordner': 'E:/s', 'schreibbereich': ['docs/**'], 'diese_sitzung': False},
                 {'id': 'earth-2140', 'name': 'Earth 2140', 'ordner': 'F:/GOG/Earth 2140', 'schreibbereich': ['**'], 'diese_sitzung': True}]
        k = Kiste(self.kiste.w, regeln=self.kiste.regeln, guard=self.kiste.guard, audit=None, karten=self.kiste.karten, sitzung_id='S-00000003',
                  chat=ChatTools(Hub(), LESEN), projekte=lambda: liste)
        for r in (k.aufruf('zustand', {'was': 'list_projects'}), k.aufruf('list_projects', {})):
            self.assertEqual(r['status'], 'ok')
            daten = json.loads(r['ergebnis'])
            self.assertEqual([p['id'] for p in daten if p['diese_sitzung']], ['earth-2140'])
            self.assertIn('F:/GOG/Earth 2140', r['ergebnis'])
            self.assertNotIn('"id": "sedra", "name": "Sedra"}', r['ergebnis'])           # nicht die Kernliste
        self.assertIn('Sedra', self.kiste.aufruf('list_projects', {})['ergebnis'])        # ohne die Harness-Liste bleibt es bei der alten Auskunft

    def test_ohne_chat_werkzeuge_gibt_es_kein_zustand(self):
        k = Kiste(self.kiste.w, regeln=self.kiste.regeln, guard=self.kiste.guard, audit=None, karten=self.kiste.karten, sitzung_id='S-00000002')
        self.assertNotIn('zustand', self.namen(k))


if __name__ == '__main__':
    unittest.main()
