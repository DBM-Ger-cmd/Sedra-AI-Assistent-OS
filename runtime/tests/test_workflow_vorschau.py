"""Die Vorschau eines n8n-Imports: echte Exporte (auch lockere), Fehlertexte, Normalisieren, Funde und Urteil."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sedra_runtime.workflows import vorschau as v  # noqa: E402


def n8n_export():
    """So ähnlich schreibt n8n 1.x einen Workflow: Webhook, HTTP-Anfrage mit Zugangsdaten, Bedingung, Felder setzen, Antwort, eine Notiz."""
    return {
        'name': 'Anfrage prüfen', 'active': True, 'id': 'abc123', 'versionId': 'v1', 'tags': [{'id': 't', 'name': 'kunden'}], 'meta': {'instanceId': 'x'},
        'settings': {'executionOrder': 'v1'}, 'pinData': {'Webhook': [{'json': {'a': 1}}]},
        'nodes': [
            {'id': 'n1', 'name': 'Webhook', 'type': 'n8n-nodes-base.webhook', 'typeVersion': 2, 'position': [0, 200], 'parameters': {'path': 'anfrage'}, 'webhookId': 'w1'},
            {'id': 'n2', 'name': 'Kunde laden', 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': [220, 200], 'parameters': {'url': 'https://x'},
             'credentials': {'httpHeaderAuth': {'id': '7', 'name': 'API'}}},
            {'id': 'n3', 'name': 'Bekannt?', 'type': 'n8n-nodes-base.if', 'typeVersion': 2.2, 'position': [440, 200], 'parameters': {}},
            {'id': 'n4', 'name': 'Ja-Zweig', 'type': 'n8n-nodes-base.noOp', 'typeVersion': 1, 'position': [660, 120], 'parameters': {}},
            {'id': 'n5', 'name': 'Nein-Zweig', 'type': 'n8n-nodes-base.noOp', 'typeVersion': 1, 'position': [660, 300], 'parameters': {}, 'disabled': True},
            {'id': 'n6', 'name': 'Hinweis', 'type': 'n8n-nodes-base.stickyNote', 'typeVersion': 1, 'position': [0, 0], 'parameters': {'content': 'Notiz'}},
        ],
        'connections': {'Webhook': {'main': [[{'node': 'Kunde laden', 'type': 'main', 'index': 0}]]}, 'Kunde laden': {'main': [[{'node': 'Bekannt?', 'type': 'main', 'index': 0}]]},
                        'Bekannt?': {'main': [[{'node': 'Ja-Zweig', 'type': 'main', 'index': 0}], [{'node': 'Nein-Zweig', 'type': 'main', 'index': 0}]]}}}


class Fehlertexte(unittest.TestCase):
    def test_kein_json(self):
        r = v.vorschau('das ist kein json', 'x.json')
        self.assertFalse(r['ok'])
        self.assertEqual(r['fehler']['code'], 'invalid_workflow_json')
        self.assertIn('kein gültiges JSON', r['fehler']['satz'])
        self.assertIsNone(r['workflow'])

    def test_zu_gross_und_kein_text(self):
        self.assertEqual(v.vorschau('x' * 1_100_000)['fehler']['code'], 'workflow_size_limit')
        self.assertEqual(v.vorschau(None)['fehler']['code'], 'workflow_size_limit')

    def test_doppelter_schluessel_und_nan(self):
        self.assertEqual(v.vorschau('{"a":1,"a":2}')['fehler']['code'], 'duplicate_json_key')
        self.assertEqual(v.vorschau('{"a": NaN}')['fehler']['code'], 'non_finite_json')

    def test_kein_workflow(self):
        r = v.vorschau(json.dumps({'foo': 'bar'}))
        self.assertEqual(r['fehler']['code'], 'workflow_nodes_or_connections_invalid')
        self.assertIn('nicht nach einem n8n-Workflow', r['fehler']['satz'])

    def test_verbindung_zu_unbekanntem_knoten_und_doppelte_namen(self):
        d = n8n_export(); d['connections']['Webhook']['main'][0][0]['node'] = 'gibt es nicht'
        self.assertEqual(v.vorschau(json.dumps(d))['fehler']['code'], 'invalid_connection_target')
        d = n8n_export(); d['nodes'][1]['name'] = 'Webhook'
        self.assertEqual(v.vorschau(json.dumps(d))['fehler']['code'], 'invalid_or_duplicate_node_name')

    def test_jeder_fehlercode_der_pruefung_hat_einen_satz(self):
        import re
        quelle = (Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'workflows' / 'schema.py').read_text(encoding='utf-8')
        codes = set(re.findall(r"ValueError\('([a-z_]+)'\)", quelle)) - {'invalid_json_value', 'workflow_name_required', 'workflow_name_too_long'}
        fehlt = sorted(c for c in codes if c not in v.SAETZE)
        self.assertEqual(fehlt, [], 'Fehlercodes ohne deutschen Satz')


class EchterExport(unittest.TestCase):
    def setUp(self):
        self.r = v.vorschau(json.dumps(n8n_export()), 'anfrage.json')

    def test_ok_und_zaehler(self):
        self.assertTrue(self.r['ok'])
        self.assertEqual(self.r['name'], 'Anfrage prüfen')
        self.assertEqual(self.r['zaehler'], {'knoten': 5, 'notizen': 1, 'verbindungen': 4, 'unbekannt': 2, 'zugang': 1, 'ausloeser': 1})

    def test_knotenzeilen_mit_klartext_und_hinweisen(self):
        zeilen = {z['name']: z for z in self.r['knoten']}
        self.assertEqual((zeilen['Webhook']['art'], zeilen['Webhook']['status'], zeilen['Webhook']['ausloeser']), ('Webhook', 'erhalten', True))
        self.assertIn('startet in n8n von außen', ' '.join(zeilen['Webhook']['hinweise']))
        self.assertEqual((zeilen['Kunde laden']['art'], zeilen['Kunde laden']['zugang']), ('HTTP-Anfrage', True))
        self.assertIn('Zugangsdaten', ' '.join(zeilen['Kunde laden']['hinweise']))
        self.assertEqual(zeilen['Bekannt?']['status'], 'unterstuetzt')
        self.assertTrue(zeilen['Nein-Zweig']['deaktiviert'])
        self.assertEqual(zeilen['Hinweis']['status'], 'notiz')

    def test_verbindungen_mit_ja_und_nein(self):
        zweige = {(x['von'], x['nach']): x['zweig'] for x in self.r['verbindungen']}
        self.assertEqual(zweige[('Bekannt?', 'Ja-Zweig')], 'Ja')
        self.assertEqual(zweige[('Bekannt?', 'Nein-Zweig')], 'Nein')
        self.assertEqual(zweige[('Webhook', 'Kunde laden')], '')

    def test_funde_nennen_unbekanntes_zugang_pindata_und_aktiv(self):
        texte = ' | '.join(f['text'] for f in self.r['funde'])
        self.assertIn('2 von 5 Knoten kennt SEDRA noch nicht', texte)
        self.assertIn('Zugangsdaten: 1 Knoten', texte)
        self.assertIn('keine Passwörter', texte)
        self.assertIn('angeheftete Testdaten', texte)
        self.assertIn('1 Knoten sind in n8n ausgeschaltet', texte)
        self.assertIn('nie von selbst gestartet', texte)
        self.assertEqual({f['stufe'] for f in self.r['funde']} - {'info', 'warn'}, set())

    def test_urteil_teilweise_und_nichts_geht_verloren(self):
        self.assertEqual(self.r['urteil']['stufe'], 'teilweise')
        self.assertIn('vollständig erhalten', self.r['urteil']['satz'])
        d = self.r['workflow']
        orig = n8n_export()
        self.assertEqual(d['nodes'][1]['credentials'], orig['nodes'][1]['credentials'])
        self.assertEqual(d['pinData'], orig['pinData'])
        self.assertEqual((d['tags'], d['meta'], d['settings']), (orig['tags'], orig['meta'], orig['settings']))
        self.assertEqual(self.r['aenderungen'], [])

    def test_vorschau_ist_ein_reiner_blick_das_eingabedokument_bleibt(self):
        text = json.dumps(n8n_export())
        v.vorschau(text)
        self.assertEqual(json.loads(text), n8n_export())


class LockererExport(unittest.TestCase):
    def test_teilauswahl_aus_der_zwischenablage_bekommt_name_aus_dem_dateinamen(self):
        d = {'nodes': [{'id': 'a', 'name': 'Start', 'type': 'n8n-nodes-base.manualTrigger', 'typeVersion': 1, 'position': [0, 0], 'parameters': {}}], 'connections': {}}
        r = v.vorschau(json.dumps(d), 'Mein Ablauf.json')
        self.assertTrue(r['ok'])
        self.assertEqual(r['name'], 'Mein Ablauf')
        self.assertIn('keinen Namen', r['aenderungen'][0])
        self.assertEqual(v.vorschau(json.dumps(d))['name'], 'Importierter n8n-Workflow')

    def test_alter_export_ohne_kennungen_positionen_und_version(self):
        d = {'name': 'Alt', 'nodes': [{'name': 'A', 'type': 'n8n-nodes-base.manualTrigger'}, {'name': 'B', 'type': 'n8n-nodes-base.noOp', 'parameters': None}],
             'connections': {'A': {'main': [[{'node': 'B', 'type': 'main', 'index': 0}]]}}}
        r = v.vorschau(json.dumps(d))
        self.assertTrue(r['ok'], r['fehler'])
        sätze = ' '.join(r['aenderungen'])
        for teil in ('2 Knoten bekamen eine Kennung', '2 Knoten hatten keine Position', '2 Knoten bekamen die Version 1', '2 Knoten bekamen leere Parameter'):
            self.assertIn(teil, sätze)
        self.assertTrue(r['layout_noetig'])
        ids = [n['id'] for n in r['workflow']['nodes']]
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(v.vorschau(json.dumps(d))['workflow']['nodes'][0]['id'], ids[0], 'die Kennungen sind stabil, nicht zufällig')

    def test_ohne_connections_gilt_als_leer(self):
        d = {'name': 'Einzeln', 'nodes': [{'id': 'a', 'name': 'A', 'type': 'n8n-nodes-base.noOp', 'typeVersion': 1, 'position': [0, 0], 'parameters': {}}]}
        r = v.vorschau(json.dumps(d))
        self.assertTrue(r['ok'])
        self.assertIn('keine Verbindungen', ' '.join(r['aenderungen']))
        self.assertTrue(any('Nicht verbunden: A' in f['text'] for f in r['funde']))

    def test_alle_knoten_bekannt_ist_ok(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from workflow_fixture import sample
        r = v.vorschau(json.dumps(sample()))
        self.assertEqual(r['urteil']['stufe'], 'ok')
        self.assertTrue(r['ausfuehrbar'])
        self.assertFalse(r['layout_noetig'])

    def test_doppelte_kennung_wird_nicht_still_ueberschrieben(self):
        d = n8n_export(); d['nodes'][1]['id'] = 'n1'
        self.assertEqual(v.vorschau(json.dumps(d))['fehler']['code'], 'invalid_or_duplicate_node_id')

    def test_zu_viele_knoten(self):
        d = {'name': 'Gross', 'nodes': [{'id': 'i%d' % i, 'name': 'N%d' % i, 'type': 'n8n-nodes-base.noOp', 'typeVersion': 1, 'position': [i, 0], 'parameters': {}} for i in range(300)], 'connections': {}}
        self.assertEqual(v.vorschau(json.dumps(d))['fehler']['code'], 'workflow_nodes_or_connections_invalid')


class Labels(unittest.TestCase):
    def test_bekannte_und_unbekannte_typen(self):
        self.assertEqual(v._label('n8n-nodes-base.httpRequest'), 'HTTP-Anfrage')
        self.assertEqual(v._label('n8n-nodes-base.googleDriveTrigger'), 'Google drive trigger')
        self.assertEqual(v._label('@n8n/n8n-nodes-langchain.agent'), 'Agent')
        self.assertTrue(v._ist_ausloeser('n8n-nodes-base.googleDriveTrigger'))
        self.assertTrue(v._ist_ausloeser('n8n-nodes-base.webhook'))
        self.assertFalse(v._ist_ausloeser('n8n-nodes-base.set'))


class VerbImDesk(unittest.TestCase):
    def test_verb(self):
        from sedra_runtime.workflows import desk
        out = desk._import_vorschau(None, None, {'text': json.dumps(n8n_export()), 'dateiname': 'a.json'})
        self.assertEqual((out['status'], out['ok']), ('erledigt', True))
        self.assertEqual(desk._import_vorschau(None, None, {'text': 'x'})['fehler']['code'], 'invalid_workflow_json')


if __name__ == '__main__':
    unittest.main()
