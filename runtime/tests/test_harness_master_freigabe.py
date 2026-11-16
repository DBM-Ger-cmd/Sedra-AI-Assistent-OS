"""Master-Modus im Freigabe-Weg (docs/SPEC_MASTER_MODUS_v1_ENTWURF.md MM-05, MM-06, MM-10, MM-12, MM-15): `Kiste.aufruf` mit `master` und die Quelle 3b in `deckung.deckt`."""
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import deckung, katalog, master
from sedra_runtime.harness.freigabe import Karten, Kiste
from sedra_runtime.harness.werkzeuge import Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
SID = 'S-00000001'


class Audit:
    def __init__(self):
        self.zeilen = []

    def append(self, event, component=None, mission_id=None, payload=None):
        self.zeilen.append((event, payload or {}))

    def alle(self, event):
        return [p for e, p in self.zeilen if e == event]


class KisteMaster(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'projekt'
        for d in ('docs', 'runtime/src/sedra_runtime/uix/shells/x', 'local_config'):
            (self.root / d).mkdir(parents=True)
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        self.projekt = {'id': 'p', 'name': 'P', 'wurzel': str(self.root), 'schreibbereich': ['docs/**', 'runtime/**', 'local_config/**'], 'master': ['docs/**']}
        self.regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        self.audit = Audit()
        self.zustand = master.Zustand(audit=lambda e, p: self.audit.append(e, payload=p))
        self.karten = Karten(Path(self.tmp.name) / 'karten')

    def kiste(self, *, lokal=True, mit_master=True):
        w = Werkzeuge(self.projekt, guard=self.guard, mission_id='M-HARNESS', regeln=self.regeln)
        return Kiste(w, regeln=self.regeln, guard=self.guard, audit=self.audit, karten=self.karten, sitzung_id=SID, projekt_id='p', lokal=lokal,
                     master=self.zustand if mit_master else None)

    def an(self, muster=('docs/**',)):
        self.zustand.an(SID, 'p', list(muster))

    def test_ohne_master_karte(self):
        r = self.kiste().aufruf('datei_schreiben', {'pfad': 'docs/a.md', 'inhalt': 'x'})
        self.assertEqual(r['status'], 'wartet')
        self.assertFalse((self.root / 'docs' / 'a.md').exists())

    def test_mit_master_ohne_karte_und_mit_audit(self):
        self.an()
        r = self.kiste().aufruf('datei_schreiben', {'pfad': 'docs/a.md', 'inhalt': 'x'})
        self.assertEqual((r['status'], r['stufe'], r['regel']), ('ok', 'master', f'master:{SID}'))
        self.assertEqual((self.root / 'docs' / 'a.md').read_text(encoding='utf-8'), 'x')
        self.assertEqual(self.karten.alle(), [])
        ok = self.audit.alle('HARNESS_APPROVED_BY')
        self.assertEqual((ok[-1]['approved_by'], ok[-1]['kanal']), (f'master:{SID}', 'master'))
        auf = self.audit.alle('HARNESS_MASTER_AUFRUF')
        self.assertEqual((len(auf), auf[0]['master'], auf[0]['werkzeug'], auf[0]['ziel']), (1, True, 'datei_schreiben', 'docs/a.md'))

    def test_lesen_und_aendern_im_muster(self):
        self.an()
        (self.root / 'docs' / 'b.md').write_text('alt neu', encoding='utf-8')
        k = self.kiste()
        self.assertEqual(k.aufruf('datei_lesen', {'pfad': 'docs/b.md'})['status'], 'ok')
        r = k.aufruf('datei_aendern', {'pfad': 'docs/b.md', 'alt': 'alt', 'neu': 'NEU'})
        self.assertEqual((r['status'], r['stufe']), ('ok', 'master'), r)
        self.assertEqual((self.root / 'docs' / 'b.md').read_text(encoding='utf-8'), 'NEU neu')

    def test_ausserhalb_des_musters_karte_mit_grund(self):
        self.an()
        r = self.kiste().aufruf('datei_schreiben', {'pfad': 'runtime/x.py', 'inhalt': 'x'})
        self.assertEqual(r['status'], 'wartet')
        self.assertIn('Master-Modus deckt nicht', self.karten.alle()[0]['begruendung'])
        self.assertEqual(self.audit.alle('HARNESS_MASTER_NICHT')[0]['werkzeug'], 'datei_schreiben')

    def test_vorbehalt_bleibt_karte(self):
        self.an(['**'])
        k = self.kiste()
        for name, args in (('datei_schreiben', {'pfad': 'local_config/x.yaml', 'inhalt': 'x'}),
                           ('datei_schreiben', {'pfad': 'runtime/src/sedra_runtime/harness/master.py', 'inhalt': 'x'}),
                           ('befehl', {'befehl': 'git push', 'ordner': 'docs'})):
            r = k.aufruf(name, args)
            self.assertEqual(r['status'], 'wartet', (name, args))
        self.assertFalse((self.root / 'local_config' / 'x.yaml').exists())

    def test_weicher_vorbehalt_der_oberflaeche_bleibt_karte(self):
        self.an(['**'])
        r = self.kiste().aufruf('datei_schreiben', {'pfad': 'runtime/src/sedra_runtime/uix/shells/x/a.js', 'inhalt': 'x'})
        self.assertEqual(r['status'], 'wartet')
        self.assertFalse((self.root / 'runtime/src/sedra_runtime/uix/shells/x/a.js').exists())

    def test_cloud_modell_bleibt_karte(self):
        self.an()
        self.assertEqual(self.kiste(lokal=False).aufruf('datei_schreiben', {'pfad': 'docs/a.md', 'inhalt': 'x'})['status'], 'wartet')

    def test_aus_wirkt_sofort(self):
        self.an()
        k = self.kiste()
        self.assertEqual(k.aufruf('datei_schreiben', {'pfad': 'docs/a.md', 'inhalt': 'x'})['status'], 'ok')
        self.zustand.aus(SID)
        self.assertEqual(k.aufruf('datei_schreiben', {'pfad': 'docs/c.md', 'inhalt': 'x'})['status'], 'wartet')

    def test_befehl_erlaubt_und_gesperrt(self):
        self.an()
        k = self.kiste()
        r = k.aufruf('befehl', {'befehl': 'python --version', 'ordner': 'docs'})
        self.assertEqual((r['status'], r['stufe']), ('ok', 'master'), r)
        self.assertEqual(k.aufruf('befehl', {'befehl': 'curl https://example.org', 'ordner': 'docs'})['status'], 'wartet')
        self.assertIn('Netz', self.karten.alle()[0]['begruendung'])

    def test_befehl_ausserhalb_der_wurzel_karte(self):
        self.an()
        self.assertEqual(self.kiste().aufruf('befehl', {'befehl': 'python --version ../../x', 'ordner': 'docs'})['status'], 'wartet')

    def test_kontext_traegt_den_schluessel_fuer_die_ruecknahme(self):
        self.an()
        k = self.kiste()
        k.aufruf('datei_schreiben', {'pfad': 'docs/k.md', 'inhalt': 'x'})
        self.assertEqual(k.w.kontext['aufgabe_id'], f'master:{SID}')

    def test_wiederholungsdeckel_gilt_auch_unter_dem_master(self):
        self.an()
        k = self.kiste()
        stati = [k.aufruf('befehl', {'befehl': 'python --version', 'ordner': 'docs'})['status'] for _ in range(3)]
        self.assertEqual(stati, ['ok', 'ok', 'wartet'])
        self.assertEqual(self.audit.alle('HARNESS_ERLAUBNIS')[-1]['aktion'], 'gedeckelt')
        self.assertEqual(self.audit.alle('HARNESS_ERLAUBNIS')[-1]['herkunft'], 'master')

    def test_fehler_im_master_ist_karte(self):
        class Kaputt:
            def deckt(self, *a, **k):
                raise RuntimeError('kaputt')

            def letzter_grund(self, *a, **k):
                return None
        k = self.kiste()
        k.master = Kaputt()
        # master.Zustand.deckt fängt selbst ab; ein fremdes Objekt, das wirft, darf die Kiste nicht öffnen
        with self.assertRaises(RuntimeError):
            k.aufruf('datei_schreiben', {'pfad': 'docs/a.md', 'inhalt': 'x'})
        self.assertFalse((self.root / 'docs' / 'a.md').exists())

    def test_ohne_masterobjekt_alles_wie_vorher(self):
        self.an()
        self.assertEqual(self.kiste(mit_master=False).aufruf('datei_schreiben', {'pfad': 'docs/a.md', 'inhalt': 'x'})['status'], 'wartet')


def deckt(**k):
    basis = dict(wirkt_als='captain', vorbehalt=False, warnkarte=False, aufgaben_aktiv=False, weich_werkzeug=lambda: None, weich_plan=None,
                 aufgabe_treffer=lambda w: None, aufgabe_zaehlen=lambda i: True, sitzung_treffer=lambda: None, lokal=True, master_treffer=lambda: {'sitzung_id': 'S-1'})
    return deckung.deckt(**(basis | k))


class DeckungMaster(unittest.TestCase):
    def test_master_deckt(self):
        self.assertEqual(deckt()['via_master'], 'S-1')

    def test_ohne_master_treffer_kein_schluessel(self):
        self.assertEqual(deckt(master_treffer=None), {'via_aufgabe': None, 'via_sitzung': None})

    def test_nie_bei_frei_vorbehalt_warnkarte(self):
        for k in ({'wirkt_als': 'frei'}, {'vorbehalt': 'V'}, {'warnkarte': True}):
            aufrufe = []
            r = deckt(**k, master_treffer=lambda: aufrufe.append(1) or {'sitzung_id': 'S-1'})
            self.assertIsNone(r['via_master'], k)
            self.assertEqual(aufrufe, [], k)

    def test_nicht_bei_cloud_modell(self):
        self.assertIsNone(deckt(lokal=False)['via_master'])

    def test_weich_modell_deckt_weich_oberflaeche_nie(self):
        self.assertEqual(deckt(weich_werkzeug=lambda: {'modell': 'r1'})['via_master'], 'S-1')
        self.assertIsNone(deckt(weich_werkzeug=lambda: {'oberflaeche': 'a/b.js'})['via_master'])
        self.assertIsNone(deckt(weich_werkzeug=lambda: None, weich_plan={'oberflaeche': 'a/b.js'})['via_master'])

    def test_aufgabe_geht_vor_und_master_wird_nicht_gefragt(self):
        aufrufe = []
        r = deckt(aufgaben_aktiv=True, aufgabe_treffer=lambda w: {'aufgabe_id': 'T-1'}, master_treffer=lambda: aufrufe.append(1) or {'sitzung_id': 'S-1'})
        self.assertEqual((r['via_aufgabe'], r['via_master'], aufrufe), ('T-1', None, []))

    def test_master_geht_vor_sitzungserlaubnis(self):
        r = deckt(sitzung_treffer=lambda: {'karte_id': 'K-1'})
        self.assertEqual((r['via_master'], r['via_sitzung']), ('S-1', None))

    def test_ohne_master_treffer_deckt_die_sitzung_wie_vorher(self):
        r = deckt(sitzung_treffer=lambda: {'karte_id': 'K-1'}, master_treffer=lambda: None)
        self.assertEqual((r['via_master'], r['via_sitzung']), (None, 'K-1'))


if __name__ == '__main__':
    unittest.main()
