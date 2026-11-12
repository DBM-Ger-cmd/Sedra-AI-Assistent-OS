import json
import tempfile
import unittest
from pathlib import Path

from test_workflow_lokal import WF, RECHNUNG, pdf
from sedra_runtime.workflows import lokal
from sedra_runtime.workflows.lokal_daten import Eingaben, Tabellen

NB = 'n8n-nodes-base.'


def knoten(name, typ, version, parameters):
    return {'id': 'id-' + name, 'name': name, 'type': NB + typ, 'typeVersion': version, 'parameters': parameters, 'position': [0, 0]}


def code(name, js):
    return knoten(name, 'code', 2, {'jsCode': js})


def wf(nodes, verbindungen):
    c = {}
    for von, nach, ast, idx in verbindungen:
        c.setdefault(von, {'main': []})
        while len(c[von]['main']) <= ast:
            c[von]['main'].append([])
        c[von]['main'][ast].append({'node': nach, 'type': 'main', 'index': idx})
    return {'name': 'Test', 'nodes': [knoten('Start', 'manualTrigger', 1, {})] + nodes, 'connections': c}


def bed(links, op, rechts, art='string'):
    return {'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict', 'version': 2}, 'combinator': 'and',
            'conditions': [{'id': 'a', 'leftValue': links, 'rightValue': rechts, 'operator': {'type': art, 'operation': op}}]}


DREI = code('Daten', 'return [{json:{art:"a",n:1}},{json:{art:"b",n:2}},{json:{art:"a",n:3}},{json:{art:"c",n:4}}];')


def laufen(doc, modell=None, eingabe=None):
    with tempfile.TemporaryDirectory() as tmp:
        return lokal.ausfuehren(doc, eingabe or {}, Path(tmp), modell)


class Neue(unittest.TestCase):
    def test_switch_filter(self):
        doc = wf([DREI,
                  knoten('Weg', 'switch', 3, {'mode': 'rules', 'rules': {'values': [{'conditions': bed('={{ $json.art }}', 'equals', 'a')}, {'conditions': bed('={{ $json.art }}', 'equals', 'b')}]},
                                                'options': {'fallbackOutput': 'extra'}}),
                  knoten('A', 'noOp', 1, {}), knoten('B', 'noOp', 1, {}), knoten('Rest', 'noOp', 1, {}),
                  knoten('Gross', 'filter', 2.2, {'conditions': bed('={{ $json.n }}', 'gt', 2, 'number'), 'options': {}})],
                 [('Start', 'Daten', 0, 0), ('Daten', 'Weg', 0, 0), ('Weg', 'A', 0, 0), ('Weg', 'B', 1, 0), ('Weg', 'Rest', 2, 0), ('Daten', 'Gross', 0, 0)])
        r = laufen(doc)
        self.assertEqual(r['status'], 'completed', r)
        self.assertEqual({k['name']: k['ausgang'] for k in r['knoten']}['Weg'], [2, 1, 1])
        self.assertEqual([i['n'] for i in r['output']['Gross']], [3, 4])

    def test_merge_aggregate_split(self):
        doc = wf([code('L', 'return [{json:{x:1}},{json:{x:2}}];'), code('R', 'return [{json:{y:"a"}},{json:{y:"b"}}];'),
                  knoten('Paar', 'merge', 3, {'mode': 'combine', 'combineBy': 'combineByPosition', 'options': {}}),
                  knoten('Alle', 'aggregate', 1, {'aggregate': 'aggregateAllItemData', 'destinationFieldName': 'liste', 'options': {}}),
                  knoten('Auf', 'splitOut', 1, {'fieldToSplitOut': 'liste', 'options': {}})],
                 [('Start', 'L', 0, 0), ('Start', 'R', 0, 0), ('L', 'Paar', 0, 0), ('R', 'Paar', 0, 1), ('Paar', 'Alle', 0, 0), ('Alle', 'Auf', 0, 0)])
        r = laufen(doc)
        self.assertEqual(r['status'], 'completed', r)
        self.assertEqual(r['output']['Auf'], [{'liste': {'x': 1, 'y': 'a'}}, {'liste': {'x': 2, 'y': 'b'}}])

    def test_unbekannter_merge_modus_wird_abgelehnt(self):
        doc = wf([knoten('M', 'merge', 3, {'mode': 'combine', 'combineBy': 'combineByFields', 'options': {}})], [('Start', 'M', 0, 0)])
        self.assertFalse(lokal.bewerten(doc)['executable'])


class Zeilen(unittest.TestCase):
    def test_zeile_anlegen_aendern_loeschen(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Tabellen(Path(tmp))
            z = t.zeile_speichern('Kostenübersicht', None, {'rechnungsnummer': 'R1', 'rechnungsbetrag': 10})
            self.assertEqual(z['id'], 1)
            t.zeile_speichern('Kosten bersicht', 1, {'rechnungsbetrag': 12.5, 'id': 99})       # gleiche Tabelle trotz fehlendem Umlaut, id bleibt
            self.assertEqual(t.lesen('Kostenübersicht')['zeilen'][0]['rechnungsbetrag'], 12.5)
            self.assertEqual(t.lesen('Kostenübersicht')['zeilen'][0]['id'], 1)
            with self.assertRaises(ValueError):
                t.zeile_speichern('Kostenübersicht', 7, {'x': 1})
            self.assertEqual(t.zeile_loeschen('Kostenübersicht', 1)['zeilen'], 0)
            with self.assertRaises(ValueError):
                t.zeile_loeschen('Kostenübersicht', 1)


class Modell(unittest.TestCase):
    """Die Rechnungspruefung mit angeschlossenem Information Extractor: das Modell ist hier eine Attrappe, geprueft wird die Verdrahtung."""

    def doc(self):
        d = json.loads(json.dumps(WF))
        d['connections']['Extract from File']['main'][0].append({'node': 'Information Extractor', 'type': 'main', 'index': 0})
        return d

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        Tabellen(self.p).importieren('Auftraege', json.dumps([{'auftragsnummer': 'AUF-2026-ST-17', 'gesamt_brutto': 2510.9}]))
        Tabellen(self.p).importieren('Auftragspositionen', json.dumps([{'auftragsnummer': 'AUF-2026-ST-17', 'lv_position': '01.01.0010', 'menge': 1, 'einzelpreis_netto': 1200, 'gesamtpreis_netto': 1200}]))

    def test_bewertung_und_lauf(self):
        b = lokal.bewerten(self.doc())
        self.assertTrue(b['executable'], b)
        self.assertTrue(b['braucht_modell'])
        self.assertEqual(b['modelle'], ['Anthropic Chat Model'])
        gesehen = []

        def modell(nachrichten, schema):
            gesehen.append((nachrichten, schema))
            return {'Rechnungsnummer': 'RE-ST-2026-0042', 'Rechnungsbetrag': 2510.9, 'Rechnungsdatum': '2026-11-12'}
        summe = Eingaben(self.p).speichern(pdf(RECHNUNG))
        r = lokal.ausfuehren(self.doc(), {'Rechnung': {'datei': summe, 'name': 'r.pdf'}}, self.p, modell)
        self.assertEqual(r['status'], 'completed', r)
        self.assertEqual(r['output']['Information Extractor'][0]['output']['Rechnungsnummer'], 'RE-ST-2026-0042')
        self.assertIn('RE-ST-2026-0042', gesehen[0][0][1]['content'])
        self.assertEqual(sorted(gesehen[0][1]['properties']), ['Rechnungsbetrag', 'Rechnungsdatum', 'Rechnungsnummer'])

    def test_ohne_modell_ein_klarer_fehler(self):
        summe = Eingaben(self.p).speichern(pdf(RECHNUNG))
        r = lokal.ausfuehren(self.doc(), {'Rechnung': {'datei': summe, 'name': 'r.pdf'}}, self.p, None)
        self.assertEqual(r['status'], 'failed')
        self.assertEqual(r['fehler_knoten'], 'Information Extractor')
        self.assertIn('kein_lokales_modell', r['fehler_text'])

    def test_extraktor_ohne_modellknoten_wird_abgelehnt(self):
        d = self.doc()
        d['connections'].pop('Anthropic Chat Model')
        self.assertEqual(lokal.bewerten(d)['reason'], 'model_node_missing:Information Extractor')


if __name__ == '__main__':
    unittest.main()
