"""Die Wissensbasis am Server (SPEC_SHELL_WISSEN_v1 §4.1–4.6, W2 bis W7): Abschnitt mit Nachbarn und Rechtefilter, Notizen des
Captains (einmal freigegeben, danach ohne Gate, Audit ohne Inhalt), Filter der Suche vor dem Ranking, die Zelle der Leiste,
„Frag das Wissen“ ohne Modell, und die Vorgabe, deren Orte aus ui/places.js kommen."""
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk import vorgabe
from guppi_runtime.wissen import desk_basis
from guppi_runtime.wissen.speicher import leser
from test_wissen_desk import Basis

LANG = "# Lager\n\n## Anfang\n\nDer Anfang der Datei.\n\n## Lease\n\nVor dem Laden die Lease holen.\n\n## Ende\n\nDas Ende der Datei.\n"


class Abschnitt(Basis):
    def setUp(self):
        super().setUp()
        (self.project / 'notizen' / 'lager.md').write_text(LANG, encoding='utf-8')
        self.decide(self.beantrage(pfad='notizen/lager.md', stufe=2))

    def test_abschnitt_mit_nachbarn_und_rechtefilter(self):
        tid = self.act('wissen', None, 'suche', frage='Lease')['treffer'][0]['id']
        obj = self.objects(type='wissen_abschnitt', id=tid)
        a = obj['abschnitt']
        self.assertEqual((obj['type'], a['stelle'].endswith('Lease'), a['stufe']), ('wissen_abschnitt', True, 2))
        self.assertIn('Anfang', a['davor']['stelle']); self.assertIn('Ende', a['danach']['stelle'])
        with self.assertRaisesRegex(ValueError, 'wis_abschnitt_unbekannt'):
            desk_basis.abschnitt(self.sp, tid, leser('agent', 1, None, 'A-1'))       # über der Stufe des Lesers: nicht lesbar
        with self.assertRaisesRegex(ValueError, 'object_not_found'):
            self.objects(type='wissen_abschnitt', id='W00000000000')
        with self.assertRaisesRegex(ValueError, 'object_not_found'):
            self.objects(type='wissen_abschnitt', id="x' OR 1=1")

    def test_filter_wirkt_vor_dem_ranking(self):
        alle = self.act('wissen', None, 'suche', frage='Datei')
        self.assertGreaterEqual(len(alle['treffer']), 2)
        q = alle['treffer'][0]['quelle']
        self.assertEqual(len(self.act('wissen', None, 'suche', frage='Datei', filter={'quellen': [q]})['treffer']), len(alle['treffer']))
        self.assertEqual(self.act('wissen', None, 'suche', frage='Datei', filter={'quellen': ['Q-fremd']})['treffer'], [])
        self.assertEqual(self.act('wissen', None, 'suche', frage='Datei', filter={'arten': ['logbuch']})['treffer'], [])
        self.assertEqual(self.act('wissen', None, 'suche', frage='Datei', filter={'seit': '2999-01-01'})['treffer'], [])
        self.assertEqual(len(self.act('wissen', None, 'suche', frage='Datei', filter={'bis': '2999-01-01'})['treffer']), len(alle['treffer']))
        out = self.act('wissen', None, 'suche', frage='Datei', filter={'seit': 'gestern'})
        self.assertEqual((out['status'], out['code']), ('fehler', 'wis_filter_ungueltig'))
        self.assertEqual(self.act('wissen', None, 'suche', frage='Datei', filter={'leser': 'x'})['code'], 'wis_filter_ungueltig')

    def test_zelle_der_leiste(self):
        z = desk_basis.strip_zelle(self.sp)
        self.assertEqual((z['value'], z['tone'], z['vorschlaege_offen']), ('nur Volltext', 'warn', 0))
        self.assertIsNone(desk_basis.strip_zelle(None))
        self.assertEqual(self.hub.strip_view()['wissen']['value'], 'nur Volltext')

    def test_frag_das_wissen_ohne_modell(self):
        out = self.hub.chat_reply({'text': 'Wann die Lease holen?', 'wissen': True})
        self.assertEqual((out['status'], out['model']), ('completed', 'wissen'))
        self.assertIn('Das habe ich im Wissen gefunden', out['reply'])
        self.assertRegex(out['reply'], r'\[W[0-9a-f]{10,16}\]')
        self.assertEqual(out['wissen']['personenbezug'], False)
        self.assertIn(out['wissen']['ids'][0], out['reply'])
        aus = self.hub.chat_reply({'text': 'Wann die Lease holen?'})
        self.assertEqual(aus['status'], 'no_model', 'ohne den Schalter der Shell bleibt das Gespräch, wie es war')


class Notizen(Basis):
    def test_erst_ein_gate_dann_keins_und_sofort_findbar(self):
        out = self.act('wissen', None, 'notiz_anlegen', titel='Kunde Nordwerk', text='Rückruf immer vormittags, Ansprechpartnerin Lena.')
        self.assertEqual(out['status'], 'beantragt')
        zweite = self.act('wissen', None, 'notiz_anlegen', titel='Zweite', text='Noch eine Notiz zur Werkbank.', personenbezug=False)
        self.assertEqual(zweite['decision_id'], out['decision_id'], 'ein offener Antrag wird nicht verdoppelt')
        self.assertEqual(self.decide(out)['status'], 'applied')
        dritte = self.act('wissen', None, 'notiz_anlegen', titel='Dritte', text='Der Ofen braucht zwanzig Minuten Vorlauf.', personenbezug=False)
        self.assertEqual(dritte['status'], 'erledigt', 'nach der Freigabe kein Gate mehr')
        treffer = self.act('wissen', None, 'suche', frage='Vorlauf Ofen')['treffer']
        self.assertTrue(treffer and 'Vorlauf' in treffer[0]['text'])
        lena = self.act('wissen', None, 'suche', frage='vormittags')['treffer']
        self.assertTrue(lena and lena[0]['personenbezug'], 'Notiz mit Personenbezug trägt das Kennzeichen')
        liste = self.act('wissen', None, 'notizen')
        self.assertEqual((len(liste['notizen']), liste['freigegeben']), (3, True))
        audit = self.audit('WIS_NOTIZ')
        self.assertEqual([a['aktion'] for a in audit], ['anlegen', 'anlegen', 'anlegen'])
        self.assertNotIn('Lena', str(audit)); self.assertNotIn('Nordwerk', str(audit))

    def test_aendern_loeschen_und_fremde_dateien(self):
        self.act('wissen', None, 'notiz_anlegen', titel='Alt', text='alter Text', personenbezug=False)
        datei = self.act('wissen', None, 'notizen')['notizen'][0]['datei']
        self.assertEqual(self.act('wissen', None, 'notiz_aendern', datei=datei, titel='Neu', text='neuer Text')['datei'], datei)
        self.assertEqual(self.act('wissen', None, 'notizen')['notizen'][0]['titel'], 'Neu')
        for falsch in ('../../secrets.md', 'allgemein/../x.md', 'anders/x.md', ''):
            self.assertEqual(self.act('wissen', None, 'notiz_loeschen', datei=falsch)['code'], 'wis_notiz_unbekannt', falsch)
        self.assertEqual(self.act('wissen', None, 'notiz_anlegen', titel='', text='x')['code'], 'wis_notiz_leer')
        self.assertEqual(self.act('wissen', None, 'notiz_loeschen', datei=datei)['status'], 'beantragt')
        self.assertEqual(self.act('wissen', None, 'notizen')['notizen'], [])


class Vorgabe(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'shells'

    def test_orte_kommen_aus_der_ortskunde(self):
        ids = vorgabe.place_ids()
        self.assertIn('wissen-suche', ids); self.assertIn('tasks', ids)
        enum = vorgabe.schema()['properties']['orte']['properties']['liste']['items']['enum']
        self.assertIn('wissen-eigenes', enum)

    def test_wissensbasis_ist_gueltig_und_ein_fremder_ort_nicht(self):
        import yaml
        doc = yaml.safe_load((self.ROOT / 'wissensbasis' / 'shell.vorgabe.yaml').read_text(encoding='utf-8'))
        self.assertEqual(vorgabe.check(doc), [])
        self.assertIn('Das Gespräch antwortet aus dem Wissen', vorgabe.sentence(doc))
        studio = yaml.safe_load((self.ROOT / 'gateway-studio' / 'shell.vorgabe.yaml').read_text(encoding='utf-8'))
        self.assertEqual(vorgabe.check(studio), [])
        kaputt = dict(doc, orte={'liste': ['wissen-suche', 'gibtsnicht']})
        self.assertTrue(vorgabe.check(kaputt))


if __name__ == '__main__':
    unittest.main()
