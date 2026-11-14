"""S4.1 (SPEC_FREIGABEN_S4_v1, FS-01 bis FS-04): alle Erlaubnisse in einer Sicht – rein, und die Leseroute `GET /api/harness/erlaubnisse`.

Die Sicht liest die drei bestehenden Ablagen (Sitzungs-Erlaubnis, Aufgabe, Katalogregel `frei`) und ändert nichts. Gegenproben: die Eingaben
bleiben unverändert, nur die Stufe `frei` der Katalogregeln erscheint, ein falscher Status ist ein Fehler, und die Route kennt nur GET."""
import copy
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401
from sedra_runtime.harness import erlaubnisse_sicht as sicht
from sedra_runtime.harness.api import NichtGefunden
from sedra_runtime.uix_server import UIXHub

S1, S2 = 'S-11111111', 'S-22222222'
KOPF1 = {'id': S1, 'projekt': 'p1', 'vorlage': None}
KOPF2 = {'id': S2, 'projekt': 'p2', 'vorlage': 'bauagent'}


def sitzung(kopf, *erl):
    return {'kopf': kopf, 'erlaubnisse': list(erl)}


def erl(kid, werkzeug='datei_schreiben', muster='docs/**', zeit='2026-11-14T10:00:00+01:00'):
    return {'karte_id': kid, 'werkzeug': werkzeug, 'muster': muster, 'regel': None, 'zeit': zeit, 'aktiv': True}


def aufgabe(**kw):
    a = {'id': 'T-00000001', 'titel': 'Doku', 'zweck': 'Dokumente pflegen', 'projekt': 'p1', 'sitzungen': [S1], 'status': 'aktiv', 'aufrufe': 2,
         'erlaubt': [{'werkzeug': 'datei_aendern', 'muster': 'docs/log.md'}], 'angelegt': '2026-11-14T09:00:00+01:00',
         'ende': {'bis': '2026-11-14T12:00:00+01:00', 'max_aufrufe': 5}, 'vorschlag_von': None}
    a.update(kw)
    return a


def regel(rid='lesen-frei', stufe='frei', werkzeug=('datei_lesen',), muster=('docs/**',)):
    return {'id': rid, 'werkzeug': list(werkzeug), 'muster': list(muster), 'stufe': stufe, 'begruendung': 'Lesen ist harmlos'}


class FormTests(unittest.TestCase):
    def test_sitzungs_erlaubnis(self):
        e = sicht.aus_sitzung(KOPF1, erl('K-00000001', 'befehl', 'git status*'))
        self.assertEqual((e['art'], e['id']), ('sitzung', f'{S1}:K-00000001'))
        self.assertEqual(e['was'], [{'werkzeug': 'befehl', 'muster': 'git status*'}])
        self.assertEqual(e['wo'], {'projekt': 'p1', 'sitzungen': [S1]})
        self.assertEqual(e['dauer'], {'art': 'sitzung', 'bis': None, 'max_aufrufe': None})
        self.assertEqual((e['herkunft']['von'], e['status']), ('captain', 'aktiv'))

    def test_vorlage_erlaubnis_traegt_die_vorlage(self):
        e = sicht.aus_sitzung(KOPF2, erl('V-bauagent-1'))
        self.assertEqual(e['herkunft'], {'von': 'vorlage', 'karte_id': 'V-bauagent-1', 'vorlage': 'bauagent'})

    def test_aufgabe_ist_befristet_mit_zweck(self):
        e = sicht.aus_aufgabe(aufgabe())
        self.assertEqual((e['art'], e['id'], e['warum']), ('aufgabe', 'T-00000001', 'Dokumente pflegen'))
        self.assertEqual(e['dauer'], {'art': 'befristet', 'bis': '2026-11-14T12:00:00+01:00', 'max_aufrufe': 5})
        self.assertEqual((e['herkunft']['von'], e['status'], e['aufrufe']), ('captain', 'aktiv', 2))

    def test_vorschlag_des_vorarbeiters_und_beendete_aufgabe(self):
        e = sicht.aus_aufgabe(aufgabe(vorschlag_von='S-33333333', status='abgelaufen'))
        self.assertEqual((e['herkunft']['von'], e['status'], e['status_roh']), ('vorarbeiter', 'beendet', 'abgelaufen'))

    def test_katalogregel_ist_immer_und_nur_anzeige(self):
        e = sicht.aus_katalog(regel(werkzeug=('datei_lesen', 'suchen'), muster=('a/**', 'b/**')))
        self.assertEqual((e['art'], e['id'], e['dauer']['art']), ('katalog', 'K:lesen-frei', 'immer'))
        self.assertEqual(len(e['was']), 4)                                   # jedes Werkzeug mit jedem Muster
        self.assertEqual((e['warum'], e['herkunft']['regel']), ('Lesen ist harmlos', 'lesen-frei'))


class SammelnTests(unittest.TestCase):
    def setUp(self):
        self.sitz = [sitzung(KOPF1, erl('K-00000001'), erl('K-00000002', 'befehl', 'git status*')), sitzung(KOPF2, erl('V-bauagent-1'))]
        self.auf = [aufgabe(), aufgabe(id='T-00000002', projekt='p2', sitzungen=[S2], status='erschoepft')]
        self.kat = [regel(), regel('fragen', stufe='captain'), regel('verbot', stufe='verboten')]

    def sammeln(self, **kw):
        return sicht.sammeln(self.sitz, self.auf, self.kat, **kw)

    def test_alle_drei_ablagen_in_einer_liste(self):
        out = self.sammeln(status='alle')
        self.assertEqual(out['anzahl'], 3 + 2 + 1)
        self.assertEqual(out['nach_art'], {'sitzung': 3, 'aufgabe': 2, 'katalog': 1})
        self.assertEqual([e['art'] for e in out['erlaubnisse']], ['sitzung'] * 3 + ['aufgabe'] * 2 + ['katalog'])

    def test_nur_die_stufe_frei_ist_eine_erlaubnis(self):
        regeln = [e['herkunft']['regel'] for e in self.sammeln()['erlaubnisse'] if e['art'] == 'katalog']
        self.assertEqual(regeln, ['lesen-frei'])                              # „fragen“ und „verboten“ erlauben nichts

    def test_vorgabe_ist_aktiv(self):
        out = self.sammeln()
        self.assertTrue(all(e['status'] == 'aktiv' for e in out['erlaubnisse']))
        self.assertNotIn('T-00000002', [e['id'] for e in out['erlaubnisse']])  # erschöpft = beendet
        self.assertEqual([e['id'] for e in self.sammeln(status='beendet')['erlaubnisse']], ['T-00000002'])

    def test_filter_projekt_und_sitzung(self):
        out = self.sammeln(projekt='p1', status='alle')
        self.assertEqual({e['wo']['projekt'] for e in out['erlaubnisse'] if e['art'] != 'katalog'}, {'p1'})
        self.assertIn('K:lesen-frei', [e['id'] for e in out['erlaubnisse']])    # die Katalogregel gilt überall
        eine = self.sammeln(sitzung=S2, status='alle')
        self.assertEqual({e['art'] for e in eine['erlaubnisse']}, {'sitzung', 'aufgabe', 'katalog'})
        self.assertEqual({sid for e in eine['erlaubnisse'] if e['wo']['sitzungen'] for sid in e['wo']['sitzungen']}, {S2})

    def test_unbekannter_status_ist_ein_fehler(self):
        with self.assertRaises(ValueError):
            self.sammeln(status='alles')

    def test_leere_eingaben(self):
        self.assertEqual(sicht.sammeln(None, None, None), {'erlaubnisse': [], 'anzahl': 0, 'nach_art': {'sitzung': 0, 'aufgabe': 0, 'katalog': 0}})

    def test_die_eingaben_bleiben_unveraendert(self):
        vorher = copy.deepcopy((self.sitz, self.auf, self.kat))
        self.sammeln(status='alle')
        self.assertEqual((self.sitz, self.auf, self.kat), vorher)             # nur Sicht: nichts wird erteilt, geändert oder gelöscht


ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='erlaubnisse-sicht-')
        cls.hub = UIXHub(Path(cls.tmp.name) / 'project', ARCH)
        cls.api = cls.hub.harness
        kopf = cls.api.sitzungen.anlegen('proj-a', 'Probe')
        cls.sid = kopf['id']
        cls.api.sitzungen.erlauben(cls.sid, 'K-0000000A', 'befehl', 'git status*')
        cls.api.sitzungen.anlegen('proj-b', 'Leer')                           # ohne Erlaubnis: wird nicht geladen
        cls.api.aufgaben.anlegen({'titel': 'Doku', 'zweck': 'Dokumente pflegen', 'projekt': 'proj-a', 'sitzungen': [cls.sid],
                                  'erlaubt': [{'werkzeug': 'datei_aendern', 'muster': 'docs/log.md'}], 'ende': {'max_aufrufe': 5}})

    @classmethod
    def tearDownClass(cls):
        cls.hub.close(); cls.tmp.cleanup()

    def get(self, query=''):
        return self.api.handle('GET', '/api/harness/erlaubnisse', query)

    def test_eine_antwort_fuer_alle_ablagen(self):
        status, body = self.get('projekt=proj-a&status=alle')
        self.assertEqual(status, 200)
        arten = [e['art'] for e in body['erlaubnisse']]
        self.assertEqual(arten.count('sitzung'), 1)
        self.assertEqual(arten.count('aufgabe'), 1)
        self.assertIn('katalog_fehler', body)

    def test_filter_nach_sitzung_und_projekt(self):
        _, body = self.get(f'sitzung={self.sid}&status=alle')
        self.assertEqual({e['art'] for e in body['erlaubnisse'] if e['art'] != 'katalog'}, {'sitzung', 'aufgabe'})
        _, leer = self.get('projekt=proj-b&status=alle')
        self.assertEqual([e['art'] for e in leer['erlaubnisse'] if e['art'] != 'katalog'], [])

    def test_fehler_bei_falschen_angaben(self):
        with self.assertRaises(ValueError):
            self.get('status=alles')
        with self.assertRaises(ValueError):
            self.get('sitzung=keine-id')

    def test_nur_lesen_kein_schreibweg(self):
        for methode in ('POST', 'DELETE', 'PATCH'):
            with self.assertRaises(Exception):
                self.api.handle(methode, '/api/harness/erlaubnisse', '', {})
        with self.assertRaises(NichtGefunden):
            self.api.handle('GET', '/api/harness/erlaubnisse/antrag', '')


if __name__ == '__main__':
    unittest.main()
