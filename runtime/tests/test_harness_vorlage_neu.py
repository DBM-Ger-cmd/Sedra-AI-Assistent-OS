"""„Neue Vorlage anlegen“ (Captain 04.11.2026, wie „Neues Projekt“): Angaben → Antrag im Posteingang; die zwei Dateien entstehen erst nach der Freigabe in local_config,
ohne Rechte und ohne Sitzungs-Erlaubnisse, und eine vorhandene id wird nie überschrieben."""
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sedra_runtime.harness import antraege, vorlagen
from sedra_runtime.harness import vorlagen_neu as vn
from sedra_runtime.harness.vorlagen import VorlageFehler

REPO = vorlagen.VORLAGEN_DIR


class Hub:
    def __init__(self, root, offen=()):
        self.project_root = root
        self._offen = list(offen)
        self.audit = []
        self.runtime = SimpleNamespace(audit=SimpleNamespace(append=lambda e, component=None, payload=None, **k: self.audit.append((e, payload))))
        self.events = SimpleNamespace(publish=lambda name, daten: None)

    def _open_requests(self):
        return self._offen


class Basis(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.hub = Hub(self.root)

    def antrag(self, **payload):
        with mock.patch.object(antraege.gated, 'request', return_value={'mission_id': 'M-V'}) as anfrage:
            out = antraege.vorlage_neu_antrag(self.hub, payload)
        return out, anfrage


class Weg(unittest.TestCase):
    def test_der_weg_ist_bekannt_und_geschuetzt(self):
        from sedra_runtime.harness.api import GESCHUETZT, WEG
        for pfad in ('/api/harness/vorlagen/neu', '/api/harness/vorlagen/grenzen'):
            m = WEG.fullmatch(pfad)
            self.assertIsNotNone(m, pfad)
            self.assertIn('vorlagen', m.groups())
        self.assertIsNotNone(GESCHUETZT.fullmatch('/api/harness/vorlagen/neu'), 'die Herkunft der Anfrage wird geprüft')


class Entwurf(Basis):
    def test_id_aus_dem_namen(self):
        self.assertEqual(vn.id_aus_name('Mein Prüfer 2'), 'mein-pruefer-2')
        self.assertEqual(vn.id_aus_name('  Übersetzer-Helfer!! '), 'uebersetzer-helfer')
        self.assertEqual(vn.id_aus_name('???'), '')
        self.assertLessEqual(len(vn.id_aus_name('x' * 80)), 32)

    def test_mit_basis_kommen_werkzeuge_anweisung_und_grenzen_mit_aber_keine_rechte(self):
        e = vn.entwurf(self.root, {'name': 'Mein Prüfer', 'basis': 'vorarbeiter'})
        v = e['vorlage']
        self.assertEqual(v['id'], 'mein-pruefer')
        self.assertEqual(v['rechte'], {'vorarbeiter_freigabe': False, 'aufgaben_vorschlagen': False})
        self.assertEqual(v['erlaubnisse'], [])
        self.assertTrue(v['system'])
        self.assertIn('datei_lesen', v['werkzeuge'])
        self.assertFalse([w for w in v['werkzeuge'] if w in vn.NUR_VORARBEITER], 'die Werkzeuge des Vorarbeiters kommen nicht mit')

    def test_ohne_basis_braucht_es_werkzeuge_und_anweisung(self):
        for p, code in [({'name': 'X'}, 'werkzeuge_fehlen'), ({'name': 'X', 'werkzeuge': ['datei_lesen']}, 'system_leer'), ({'name': ''}, 'name_fehlt'),
                        ({'name': '???', 'werkzeuge': ['datei_lesen'], 'system': 'a'}, 'id_ungueltig')]:
            with self.assertRaisesRegex(VorlageFehler, code):
                vn.entwurf(self.root, p)
        e = vn.entwurf(self.root, {'name': 'Leser', 'werkzeuge': ['datei_lesen', 'suchen'], 'system': 'Du liest nur.'})
        self.assertEqual(e['vorlage']['werkzeuge'], ['datei_lesen', 'suchen'])
        self.assertIn('rechte: {}', e['yaml'])
        self.assertEqual(e['md'], 'Du liest nur.\n')

    def test_vorarbeiter_werkzeuge_unbekannte_und_vergebene_ids_sind_abgelehnt(self):
        with self.assertRaisesRegex(VorlageFehler, 'werkzeug_nur_vorarbeiter'):
            vn.entwurf(self.root, {'name': 'X', 'werkzeuge': ['datei_lesen', 'freigabe_entscheiden'], 'system': 'a'})
        with self.assertRaisesRegex(VorlageFehler, 'werkzeug_unbekannt'):
            vn.entwurf(self.root, {'name': 'X', 'werkzeuge': ['gibt_es_nicht'], 'system': 'a'})
        with self.assertRaisesRegex(VorlageFehler, 'id_vergeben'):
            vn.entwurf(self.root, {'name': 'Prüfer', 'basis': 'pruefer'})
        with self.assertRaisesRegex(VorlageFehler, 'vorlage_unbekannt'):
            vn.entwurf(self.root, {'name': 'X', 'basis': 'gibt-es-nicht'})

    def test_rechte_und_erlaubnisse_aus_dem_formular_zaehlen_nicht(self):
        e = vn.entwurf(self.root, {'name': 'Mut', 'werkzeuge': ['datei_lesen'], 'system': 'a', 'rechte': {'vorarbeiter_freigabe': True},
                                   'erlaubnisse': [{'werkzeug': 'befehl', 'muster': 'git status*'}]})
        self.assertFalse(any(e['vorlage']['rechte'].values()))
        self.assertEqual(e['vorlage']['erlaubnisse'], [])


class Antrag(Basis):
    def test_der_antrag_legt_nichts_an_und_nennt_die_werkzeuge(self):
        out, anfrage = self.antrag(name='Leser', werkzeuge=['datei_lesen'], system='Du liest.')
        self.assertEqual((out['vorlage'], out['werkzeuge']), ('leser', ['datei_lesen']))
        self.assertFalse((self.root / 'local_config').exists(), 'der Antrag schreibt nichts')
        args, kw = anfrage.call_args
        self.assertTrue(args[4]['neu'])
        self.assertEqual(args[3], 'local_config/harness_vorlagen/leser.yaml')
        self.assertIn('Keine Rechte', kw['risks'][1])
        self.assertEqual(kw['describe'], 'Neue Vorlage anlegen: Leser')

    def test_fehler_sind_ein_satz_mit_kennung(self):
        with self.assertRaisesRegex(ValueError, 'name_fehlt'):
            self.antrag()

    def test_offene_antraege_sind_begrenzt_und_nicht_doppelt(self):
        offen = [{'kind': antraege.KIND_VORLAGE, 'binding': {'neu': True, 'vorlage': f'v{n}'}} for n in range(vn.OFFEN_MAX)]
        self.hub._offen = offen
        with self.assertRaisesRegex(ValueError, 'zu_viele_offene_antraege'):
            self.antrag(name='Leser', werkzeuge=['datei_lesen'], system='a')
        self.hub._offen = offen[:1]
        with self.assertRaisesRegex(ValueError, 'antrag_liegt_schon_im_posteingang'):
            self.antrag(name='V0', werkzeuge=['datei_lesen'], system='a')


class Freigabe(Basis):
    def test_nach_der_freigabe_liegen_zwei_dateien_und_die_vorlage_laedt(self):
        out, anfrage = self.antrag(name='Leser', werkzeuge=['datei_lesen'], system='Du liest.', beschreibung='nur lesen')
        binding = anfrage.call_args.args[4]
        res = antraege._grenzen_anwenden(self.hub, binding)
        self.assertTrue(Path(res['datei']).is_file() and Path(res['md']).is_file())
        v = vorlagen.laden(self.root, 'leser')
        self.assertEqual((v['quelle'], v['werkzeuge'], v['beschreibung']), ('local_config', ['datei_lesen'], 'nur lesen'))
        self.assertIn('leser', [x['id'] for x in vorlagen.liste(self.root)])
        self.assertEqual(self.hub.audit[0][0], 'HARNESS_VORLAGE_ANGELEGT')

    def test_zweite_freigabe_ueberschreibt_nicht(self):
        out, anfrage = self.antrag(name='Leser', werkzeuge=['datei_lesen'], system='a')
        binding = anfrage.call_args.args[4]
        antraege._grenzen_anwenden(self.hub, binding)
        with self.assertRaisesRegex(ValueError, 'vorlage_nicht_angelegt'):
            antraege._grenzen_anwenden(self.hub, binding)

    def test_die_alte_grenzen_freigabe_laeuft_weiter_ueber_denselben_weg(self):
        ziel = self.root / 'local_config' / 'harness_vorlagen'
        ziel.mkdir(parents=True)
        v = vorlagen.laden(self.root, 'pruefer')
        zuege = 10 if v['max_zuege'] != 10 else 12
        res = antraege._grenzen_anwenden(self.hub, {'vorlage': 'pruefer', 'max_zuege': zuege, 'stand_hash': v['hash']})
        self.assertEqual(res['max_zuege'], zuege)

    def test_eine_kaputte_binding_schreibt_nichts(self):
        with self.assertRaises(ValueError):
            antraege._grenzen_anwenden(self.hub, {'neu': True, 'vorlage': '../x', 'yaml': 'a: 1', 'md': 'b'})
        self.assertFalse((self.root / 'local_config').exists())


if __name__ == '__main__':
    unittest.main()
