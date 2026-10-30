"""Build 24 (Ticket B6-G-06, Klaus 15.10.2026 19:22): SEDRA kennt seinen Arbeitsplatz – die Oberflächen, ihre Orte, Anleitungen und was wartet.
Deterministisch, ohne Modell; Knöpfe statt Handlungen."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.desk import arbeitsplatz as ap
from guppi_runtime.desk.registry import Registry

UIX = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'


def module():
    return ap.module_aus_registry(Registry(Path(tempfile.mkdtemp(prefix='ap-reg-'))))


class DieReinenTeile(unittest.TestCase):
    def test_zustaendig_nur_fuer_fragen_nach_ort_weg_oder_naechstem_schritt(self):
        ja = ['Wo finde ich den Posteingang?', 'wie füge ich ein modell hinzu', 'Was ist die Werkbank?', 'was muss ich als nächstes machen',
              'wie wechsle ich die oberfläche', 'Wo ist die Teststrecke?']
        nein = ['Baue einen CSV-Parser', 'Welches Modell ist geladen?', 'Erkläre mir Pseudonymisierung', 'hallo']
        for f in ja:
            self.assertTrue(ap.zustaendig(f, 'cockpit'), f)
        for f in nein:
            self.assertFalse(ap.zustaendig(f, 'cockpit'), f)

    def test_die_beschreibung_nennt_die_oberflaeche_und_ihre_woerter(self):
        shells, _, _, _ = ap.sammle(module())
        pc = ap.beschreibung('paperclip', shells)
        self.assertIn('Paperclip', pc); self.assertIn('Posteingang', pc); self.assertIn('Alt+S', pc)
        self.assertIn('Cockpit', ap.beschreibung('cockpit', shells))
        self.assertIn('Oberfläche von SEDRA', ap.beschreibung(None, shells))

    def test_jedes_modul_traegt_sein_wissen_selbst(self):
        # Klaus 19:36: Arbeitsplatzwissen bleibt im Modul – jede Shell hat ihre arbeitsplatz.yaml, die Werkzeuge mit Anleitungen ebenso
        shells, anleitungen, begriffe, befunde = ap.sammle(module())
        self.assertEqual(befunde, [], befunde)
        for sid in ('cockpit', 'paperclip', 'minimal', 'gateway-studio'):
            self.assertIn(sid, shells); self.assertTrue(shells[sid]['satz'], sid)
        self.assertEqual(shells['paperclip']['woerter']['posteingang'][1]['type'], 'decision')
        quellen = {a['id']: a.get('modul') for a in anleitungen}
        self.assertEqual(quellen['modell_hinzufuegen'], 'tool/workshop'); self.assertEqual(quellen['projekt_anlegen'], 'tool/files')
        self.assertEqual(quellen['gateway_vorgang'], 'tool/gateway'); self.assertIsNone(quellen['shell_wechseln'], 'der Umschalter ist Vertrag, kein Modul')
        self.assertIn('werkbank', begriffe); self.assertIn('gate', begriffe)

    def test_eine_kaputte_datei_ist_ein_befund_kein_absturz(self):
        tmp = Path(tempfile.mkdtemp(prefix='ap-bad-')); self.addCleanup(lambda: __import__('shutil').rmtree(tmp, ignore_errors=True))
        (tmp / 'arbeitsplatz.yaml').write_text('arbeitsplatz:\n  satz: ok\n  fremd: 1\n  woerter: {x: {ist: y, objekt: {type: routine, id: a, title: b}}}\n  anleitungen: [{id: a}]\n', encoding='utf-8')
        wissen, befunde = ap.lies_modul(tmp, 'shell', 'kaputt')
        self.assertEqual(wissen['satz'], 'ok'); self.assertEqual(wissen['woerter'], {}); self.assertEqual(wissen['anleitungen'], [])
        self.assertEqual(len(befunde), 3)
        (tmp / 'arbeitsplatz.yaml').write_text(':: kein yaml: [', encoding='utf-8')
        self.assertEqual(ap.lies_modul(tmp, 'shell', 'kaputt')[0], {})
        self.assertEqual(ap.lies_modul(tmp / 'nix', 'shell', 'leer'), ({}, []))

    def test_naechstes_in_der_reihenfolge_eines_menschen(self):
        punkte = ap.naechstes({'grenzen_bestaetigt': False, 'entscheidungen': 2, 'gateway_wartend': 1, 'aufgaben_wartend': 0, 'modell_geladen': None, 'projekte': 1})
        typen = [o['type'] if o else None for _, o in punkte]
        self.assertEqual(typen, ['boundary', 'decision', None, 'model'], 'das GateWay bekommt keinen Knopf – es bleibt im Studio (Klaus 19:34)')
        self.assertIn('2 Entscheidungen warten', punkte[1][0])
        self.assertIn('1 GateWay-Vorgang wartet', punkte[2][0]); self.assertIn('Studio', punkte[2][0])
        ruhe = ap.naechstes({'grenzen_bestaetigt': True, 'modell_geladen': 'coder.local_primary', 'projekte': 1})
        self.assertEqual(len(ruhe), 1); self.assertIn('Nichts wartet', ruhe[0][0])

    def test_jede_anleitung_oeffnet_ein_objekt_des_vertrags(self):
        from guppi_runtime.desk.gateway import OBJECT_TYPES
        self.assertEqual(set(ap.OBJEKT_TYPEN) - {'routine'}, set(OBJECT_TYPES) - {'routine'}, 'dieselben Typen wie der Vertrag – ohne routine (kein Werkzeug)')
        _, anleitungen, _, _ = ap.sammle(module())
        for a in anleitungen:
            self.assertTrue(a['schritte'] and a['stich'], a['id'])
            if a['ort']:
                self.assertIn(a['ort']['type'], OBJECT_TYPES, a['id'])
        self.assertFalse(any(a['ort'] and a['ort']['type'] == 'routine' for a in anleitungen))


class DieWissensbasis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='arbeitsplatz-')
        self.addCleanup(self.tmp.cleanup)     # Reihenfolge: erst die Verbindung schließen (w.close), dann den Ordner löschen
        self.live = {'shell': 'cockpit', 'entscheidungen': 1, 'gateway_wartend': 0, 'gateway_gesamt': 0, 'aufgaben_wartend': 0,
                     'grenzen_bestaetigt': True, 'modell_geladen': None, 'projekte': 1}
        self.w = ap.ArbeitsplatzWissen(Path(self.tmp.name), lambda: self.live, module()); self.addCleanup(self.w.close)

    def test_die_datei_entsteht_und_traegt_alle_arten(self):
        self.assertTrue((Path(self.tmp.name) / 'local_config' / 'sedra' / 'arbeitsplatz.sqlite').is_file())
        arten = {r[0] for r in self.w._db.execute('SELECT DISTINCT art FROM wissen')}
        self.assertEqual(arten, {'shell', 'wort', 'ueberall', 'anleitung', 'begriff'})

    def test_wo_ist_der_posteingang(self):
        out = self.w.antwort('Wo finde ich den Posteingang?', 'paperclip')
        self.assertIn('Entscheidungen', out['reply'])
        self.assertEqual(out['quelle'], 'arbeitsplatz-wissen ' + ap.VERSION)
        self.assertTrue(all(a['kind'] == 'open' for a in out['ui_actions']))

    def test_wo_ist_das_start_menue_der_harness(self):
        # Harness Stufe 4 (G3 N7): die Shell trägt ihr Wissen über Start-Menü, Apps und Hardware-Zelle selbst
        out = self.w.antwort('Wo finde ich das Start-Menü?', 'harness')
        self.assertIn('Start', out['reply']); self.assertIn('Alt+S', out['reply'])
        out = self.w.antwort('Wo finde ich die Hardware?', 'harness')
        self.assertIn('Hardware', out['reply']); self.assertIn('Temperatur', out['reply'])

    def test_wie_fuege_ich_ein_modell_hinzu_bringt_die_anleitung_und_den_knopf(self):
        out = self.w.antwort('Wie füge ich ein neues Modell hinzu?', 'cockpit')
        self.assertEqual(out['art'], 'anleitung')
        self.assertIn('GGUF', out['reply']); self.assertIn('Freigabe', out['reply'])
        self.assertEqual(out['ui_actions'][0]['object'], {'type': 'model', 'id': 'neu', 'title': 'Neues Modell'})

    def test_naechster_schritt_aus_dem_live_stand(self):
        out = self.w.antwort('Was muss ich als nächstes machen?', 'cockpit')
        self.assertEqual(out['art'], 'naechstes')
        self.assertIn('Cockpit', out['reply']); self.assertIn('1 Entscheidung wartet', out['reply']); self.assertIn('Kein Modell geladen', out['reply'])
        self.assertEqual(out['ui_actions'][0]['object']['type'], 'decision')

    def test_ein_kaputter_leseweg_ist_keine_stoerung(self):
        def kaputt(): raise RuntimeError('weg')
        w = ap.ArbeitsplatzWissen(Path(self.tmp.name), kaputt, module()); self.addCleanup(w.close)
        out = w.antwort('was jetzt?', 'paperclip')
        self.assertEqual(out['art'], 'naechstes'); self.assertIn('Paperclip', out['reply'])

    def test_unbekanntes_bleibt_unbekannt(self):
        out = self.w.antwort('Wo finde ich den Kaffeeautomaten?', 'cockpit')
        self.assertEqual(out['art'], 'unbekannt'); self.assertEqual(out['ui_actions'], [])

    def test_begriff(self):
        out = self.w.antwort('Was ist ein Gate?', 'cockpit')
        self.assertIn('Einmal-Token', out['reply'])


if __name__ == '__main__':
    unittest.main()


class ImGespraech(unittest.TestCase):
    """Im Cockpit und in Paperclip antwortet der Arbeitsplatz vor dem Modell; alles andere bleibt, wie es war."""

    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='ap-chat-'); self.addCleanup(self.tmp.cleanup)
        arch = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'
        self.hub = UIXHub(Path(self.tmp.name) / 'project', arch); self.addCleanup(self.hub.close)
        self.hub.new_project({'name': 'Nordwerk'})
        self.hub.gateway.registry.save_config(shell='paperclip')

    def test_naechster_schritt_kommt_aus_dem_live_stand(self):
        import json
        out = self.hub.chat_reply({'text': 'Was muss ich als Nächstes machen?', 'history': []})
        self.assertEqual((out['status'], out['model']), ('completed', 'arbeitsplatz-wissen'))
        self.assertIn('Paperclip', out['reply']); self.assertIn('Modus und Grenzen sind nicht bestätigt', out['reply'])
        self.assertEqual(out['ui_actions'][0]['object']['type'], 'boundary')
        row = next(e for e in self.hub.audit_view()['events'] if e['event_type'] == 'UIX_CHAT_ARBEITSPLATZ_WISSEN')
        self.assertNotIn('Nächstes', json.dumps(row, ensure_ascii=False))
        self.assertEqual(self.hub.chat_reply({'text': 'welches modell läuft gerade', 'history': []})['status'], 'no_model', 'ohne Arbeitsplatz-Bezug wie bisher')

    def test_wo_und_wie_fragen(self):
        out = self.hub.chat_reply({'text': 'Wo finde ich den Posteingang?', 'history': []})
        self.assertEqual(out['model'], 'arbeitsplatz-wissen'); self.assertIn('Entscheidungen', out['reply'])
        out = self.hub.chat_reply({'text': 'Wie fahre ich die Teststrecke?', 'history': []})
        self.assertIn('Standardtest', out['reply']); self.assertEqual(out['ui_actions'][0]['object'], {'type': 'model', 'id': 'teststrecke', 'title': 'Teststrecke'})

    def test_das_gateway_geht_vor(self):
        out = self.hub.chat_reply({'text': 'Wo finde ich die Regel R-06?', 'history': []})
        self.assertEqual(out['model'], 'gateway-wissen')

    def test_der_live_stand_hat_nur_zahlen_und_namen(self):
        live = self.hub.arbeitsplatz_stand()
        self.assertEqual(live['shell'], 'paperclip'); self.assertEqual(live['projekte'], 1); self.assertIs(live['grenzen_bestaetigt'], False)
        self.assertIsNone(live['modell_geladen'])
        for v in live.values():
            self.assertNotIsInstance(v, (list, dict))

    def test_die_modellwerkzeuge_lesen_den_arbeitsplatz(self):
        import json
        from guppi_runtime.chat_tools import ChatTools
        box = ChatTools(self.hub)
        hit = json.loads(box.call('arbeitsplatz_wissen', {'frage': 'wie lege ich ein projekt an'}))
        self.assertEqual(hit['shell'], 'paperclip'); self.assertEqual(hit['treffer'][0]['id'], 'A-projekt_anlegen')
        stand = json.loads(box.call('arbeitsplatz_stand', {}))
        self.assertEqual(stand['stand']['shell'], 'paperclip'); self.assertTrue(stand['naechstes'])

    def test_der_systemtext_des_modells_nennt_die_oberflaeche(self):
        # der Pfad zum Modell: die Beschreibung kommt aus der Instanz (Modul-Dateien), nicht aus einem festen Text
        text = self.hub.arbeitsplatz.beschreibung(self.hub.aktive_shell())
        self.assertIn('Paperclip', text); self.assertIn('Posteingang', text); self.assertIn('KI GateWay Studio', text)
