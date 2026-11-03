"""Chat-Liste aufräumen aus dem Chat (03.11.2026): `sitzungen_auflisten` (lesen, frei) zeigt, was zu einem Wunsch passt; `sitzungen_aufraeumen` legt immer eine Karte mit der
Liste vor (fester Vorbehalt, nie eine Sitzungs-Erlaubnis, nie eine Aufgabe) und verschiebt erst nach der Freigabe des Captains nach geloescht/."""
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import erlaubnis, katalog
from guppi_runtime.harness.api import HarnessApi
from guppi_runtime.harness.freigabe import Karten, Kiste, beantworten
from guppi_runtime.harness.werkzeuge import NAMEN, Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
MISSION = 'M-AUFRAEUMEN'
JETZT = datetime.now().astimezone()


def zeile(n, titel, tage=0, nachrichten=6, projekt='p'):
    return {'id': f'S-{n:08X}', 'titel': titel, 'projekt': projekt, 'nachrichten': nachrichten, 'zuletzt': (JETZT - timedelta(days=tage)).isoformat(timespec='seconds')}


class Fassade(HarnessApi):
    """Nur die Auswahl-Logik des Servers, mit Attrappen für Sitzungen, Antworten und Vorarbeiter."""

    def __init__(self, zeilen, laufend=(), vorarbeiter=()):
        self.sitzungen = type('S', (), {'liste': lambda s, projekt=None: list(zeilen)})()
        self.stroeme = type('T', (), {'laufend_in': lambda s, sid: sid in laufend})()
        self.vorarbeiter = type('V', (), {'projekt_von': lambda s, sid: 'p' if sid in vorarbeiter else None})()


ZEILEN = [zeile(1, 'Rekorder testen', 40), zeile(2, 'Rekorder testen', 2), zeile(3, 'Leer', 50, 1), zeile(4, 'Laeuft', 60), zeile(5, 'Vorarbeiter', 70), zeile(6, 'Diese', 80), zeile(7, 'Neu', 1)]


def fassade():
    return Fassade(ZEILEN, laufend=('S-00000004',), vorarbeiter=('S-00000005',))


class Auswahl(unittest.TestCase):
    def ids(self, kriterien):
        return [s['id'] for s in fassade().sitzungen_fuer_modell(kriterien, aktuelle='S-00000006')]

    def test_alter_schliesst_laufende_aktuelle_und_vorarbeiter_aus(self):
        self.assertEqual(self.ids({'aelter_als_tage': 30}), ['S-00000001', 'S-00000003'])

    def test_kriterien_gelten_gemeinsam(self):
        self.assertEqual(self.ids({'aelter_als_tage': 30, 'leer': True}), ['S-00000003'])
        self.assertEqual(self.ids({'titel_enthaelt': 'rekorder'}), ['S-00000001', 'S-00000002'])

    def test_doppelte_lassen_die_neueste_stehen(self):
        self.assertEqual(self.ids({'doppelte': True}), ['S-00000001'])

    def test_ohne_kriterium_nichts(self):
        self.assertEqual(self.ids({}), [])

    def test_mit_ids_kommen_auch_geschuetzte_mit_grund_zurueck(self):
        r = {s['id']: s['geschuetzt'] for s in fassade().sitzungen_fuer_modell({'ids': ['S-00000004', 'S-00000005', 'S-00000006', 'S-00000001']}, aktuelle='S-00000006')}
        self.assertEqual(r, {'S-00000004': 'läuft gerade', 'S-00000005': 'Vorarbeiter', 'S-00000006': 'diese Sitzung', 'S-00000001': None})


class Werkzeug(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'projekt'
        root.mkdir()
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        self.regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        self.weg = []
        projekt = {'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': ['docs/**']}
        self.w = Werkzeuge(projekt, guard=self.guard, mission_id=MISSION, regeln=self.regeln, sitzungen_liste=fassade().sitzungen_fuer_modell, sitzungen_weg=self.verschieben)
        self.karten = Karten(Path(self.tmp.name) / 'karten')
        self.kiste = Kiste(self.w, regeln=self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id='S-00000006')

    def verschieben(self, ids):
        self.weg += ids
        return {'verschoben': list(ids), 'uebersprungen': []}

    def freigabe(self, karte, weg):
        return beantworten(self.karten, karte['karte_id'], weg, guard=self.guard, audit=None, werkzeuge_fuer=lambda k: self.w)

    def test_die_werkzeuge_sind_da(self):
        self.assertIn('sitzungen_auflisten', NAMEN)
        self.assertIn('sitzungen_aufraeumen', NAMEN)

    def test_auflisten_ist_frei_und_aendert_nichts(self):
        r = self.kiste.aufruf('sitzungen_auflisten', {'aelter_als_tage': 30})
        self.assertEqual((r['status'], r['stufe'], r['wirkung']), ('ok', 'frei', False))
        self.assertIn('2 Sitzungen passen', r['ergebnis'])
        self.assertIn('S-00000001 · Rekorder testen', r['ergebnis'])
        self.assertNotIn('S-00000004', r['ergebnis'])
        self.assertNotIn('karte', r)
        self.assertEqual(self.weg, [])

    def test_auflisten_ohne_kriterium_ist_ein_fehler(self):
        r = self.kiste.aufruf('sitzungen_auflisten', {})
        self.assertEqual(r['status'], 'fehler')
        self.assertIn('Kriterium', r['ergebnis'])

    def test_aufraeumen_legt_immer_eine_karte_mit_der_liste_vor(self):
        r = self.kiste.aufruf('sitzungen_aufraeumen', {'ids': ['S-00000001', 'S-00000003']}, antwort_id='A-00000001')
        self.assertEqual(r['status'], 'wartet')
        k = r['karte']
        self.assertEqual((k['werkzeug'], k['stufe'], k['vorbehalt']), ('sitzungen_aufraeumen', 'captain', True))
        self.assertIn('S-00000001 · Rekorder testen', k['vorschau'])
        self.assertIn('S-00000003 · Leer', k['vorschau'])
        self.assertIn('nichts wird endgültig gelöscht', k['vorschau'])
        self.assertEqual(self.weg, [])                                                   # vor der Freigabe wird nichts verschoben

    def test_ein_katalog_frei_und_eine_sitzungserlaubnis_helfen_nicht(self):
        regeln = [{'id': 'alles', 'werkzeug': ['*'], 'muster': ['*'], 'stufe': 'frei', 'grund': 'test'}]
        kiste = Kiste(self.w, regeln=regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id='S-00000006',
                      erlaubnisse=[{'karte_id': 'K-1', 'werkzeug': 'sitzungen_aufraeumen', 'muster': '*', 'aktiv': True}])
        r = kiste.aufruf('sitzungen_aufraeumen', {'ids': ['S-00000001']})
        self.assertEqual(r['status'], 'wartet')
        self.assertFalse(erlaubnis.erlaubt_fuer_karte(r['karte']))

    def test_geschuetzte_unbekannte_und_falsche_ids_gehen_nicht(self):
        for ids, wort in ((['S-00000004'], 'geschuetzt'), (['S-00000006'], 'geschuetzt'), (['S-00000005'], 'geschuetzt'), (['S-000000FF'], 'sitzung_unbekannt'),
                          (['../x'], 'ids_ungueltig'), ([], 'ids_ungueltig')):
            r = self.kiste.aufruf('sitzungen_aufraeumen', {'ids': ids})
            self.assertEqual(r['status'], 'fehler', ids)
            self.assertIn(wort, r['ergebnis'])
        self.assertEqual(self.weg, [])

    def test_erst_die_freigabe_verschiebt(self):
        r = self.kiste.aufruf('sitzungen_aufraeumen', {'ids': ['S-00000001', 'S-00000003']}, antwort_id='A-00000001')
        out = self.freigabe(r['karte'], 'erlauben')
        self.assertEqual(out['status'], 'ok')
        self.assertIn('2 Sitzungen nach geloescht/ verschoben', out['ergebnis'])
        self.assertEqual(sorted(self.weg), ['S-00000001', 'S-00000003'])

    def test_ablehnen_verschiebt_nichts(self):
        r = self.kiste.aufruf('sitzungen_aufraeumen', {'ids': ['S-00000001']})
        out = self.freigabe(r['karte'], 'ablehnen')
        self.assertEqual(out['status'], 'abgelehnt')
        self.assertEqual(self.weg, [])

    def test_hoechstens_hundert_je_aufruf(self):
        ids = [f'S-{n:08X}' for n in range(0x100, 0x100 + 101)]
        r = self.kiste.aufruf('sitzungen_aufraeumen', {'ids': ids})
        self.assertEqual(r['status'], 'fehler')
        self.assertIn('zu_viele', r['ergebnis'])


class Vorlage(unittest.TestCase):
    def test_der_masterchat_hat_beide_werkzeuge_und_die_anweisung(self):
        ordner = Path(__file__).resolve().parents[1] / 'config' / 'harness_vorlagen'
        text = (ordner / 'masterchat.md').read_text(encoding='utf-8')
        yaml_text = (ordner / 'masterchat.yaml').read_text(encoding='utf-8')
        self.assertIn('sitzungen_auflisten', yaml_text)
        self.assertIn('sitzungen_aufraeumen', yaml_text)
        self.assertIn('Chat-Liste aufräumen', text)
        self.assertIn('Erst nach seinem „Ja“', text)


if __name__ == '__main__':
    unittest.main()
