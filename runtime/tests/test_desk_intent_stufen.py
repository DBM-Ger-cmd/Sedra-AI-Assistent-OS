"""Vorhaben mit Stufen (19.10.2026): ein Weg in Stufen, jede Stufe kann eine Aufgabe werden, der Zustand kommt aus den Aufgaben.

Je Zusage ein Test: die Stufen werden geprüft, nicht geraten; eine Stufe trägt ihre Aufgaben; die erste nicht fertige Stufe ist die
aktuelle; eine Vorlage gibt Titel, Satz und Stufen; „Aufgabe daraus machen“ mit `stufe` plant die Stufe und hängt sie an."""
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk import intents as desk_intents
from guppi_runtime.desk import vorhaben_vorlagen as vv

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'


class Pure(unittest.TestCase):
    def test_stufen_are_checked_not_guessed(self):
        self.assertEqual(desk_intents.check_stufen(None), [])
        self.assertEqual(desk_intents.check_stufen(['Planen', {'name': 'Bauen', 'text': 'das Ding'}]),
                         [{'name': 'Planen', 'text': '', 'tasks': []}, {'name': 'Bauen', 'text': 'das Ding', 'tasks': []}])
        for bad in ('kein-array', [{'text': 'ohne Namen'}], [{'name': ''}], [{'name': 'x' * 81}], ['s'] * 13, [42]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                desk_intents.check_stufen(bad)

    def test_the_state_of_a_stage_comes_from_its_tasks_and_the_first_unfinished_one_is_current(self):
        entry = {'stufen': [{'name': 'A', 'tasks': ['M-1']}, {'name': 'B', 'tasks': ['M-2']}, {'name': 'C', 'tasks': []}]}
        missions = {'M-1': {'mission_id': 'M-1', 'intent': 'a', 'phase': 'COMPLETE', 'status': 'done'},
                    'M-2': {'mission_id': 'M-2', 'intent': 'b', 'phase': 'EXECUTE', 'status': 'active', 'pending_gates': 1}}
        out = desk_intents.stufen_of(entry, missions)
        self.assertEqual([s['state'] for s in out], ['fertig', 'wartet auf dich', 'offen'])
        self.assertEqual([s['current'] for s in out], [False, True, False])
        self.assertEqual(out[1]['tasks'][0]['waits'], True)

    def test_every_template_has_a_title_a_sentence_and_checked_stages(self):
        ids = [v['id'] for v in vv.liste()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn('3d-assets-shop', ids)
        for v in vv.liste():
            self.assertTrue(v['titel'] and v['satz'])
            desk_intents.check_stufen(v['stufen'])          # jede Vorlage muss die Prüfung bestehen, die ein Nutzer auch besteht
        self.assertEqual(len(vv.finde('3d-assets-shop')['stufen']), 8)
        self.assertIsNone(vv.finde('gibt-es-nicht'))


class Store(unittest.TestCase):
    def test_a_task_hangs_on_its_stage_and_on_the_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = desk_intents.Store(Path(tmp))
            made = store.add('Shop', 'drei Assets', 'p1', '2026-10-19T18:00:00Z', stufen=['Nische', 'Modellieren'], vorlage='3d-assets-shop')
            self.assertEqual([s['name'] for s in made['stufen']], ['Nische', 'Modellieren'])
            self.assertEqual(made['vorlage'], '3d-assets-shop')
            store.attach(made['id'], 'M-7', stufe=1)
            again = store.get(made['id'])
            self.assertEqual(again['tasks'], ['M-7'])
            self.assertEqual(again['stufen'][1]['tasks'], ['M-7'])
            self.assertEqual(again['stufen'][0]['tasks'], [])
            with self.assertRaises(ValueError):
                store.attach(made['id'], 'M-8', stufe=5)


class ThroughTheHub(unittest.TestCase):
    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-stufen-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)
        self.hub.new_project({'name': 'Prüfprojekt'})

    def test_a_template_becomes_an_intent_with_stages_and_a_stage_becomes_a_task(self):
        self.assertTrue(self.hub.intent_vorlagen()['vorlagen'])
        made = self.hub.intent_create({'vorlage': '3d-assets-shop'})
        self.assertEqual(made['title'], '3D-Assets über einen Etsy-Shop vertreiben')
        self.assertEqual(len(made['stufen']), 8)
        obj = self.hub.object_view('intent', made['id'])
        self.assertEqual(obj['state'], 'offen')
        self.assertEqual(obj['stufen'][0]['current'], True)
        self.assertIn('0 von 8 Stufen fertig', obj['summary'])
        # die erste Stufe wird zur Aufgabe – über denselben Verb-Weg wie jeder Knopf
        out = self.hub.act({'type': 'intent', 'id': made['id'], 'verb': 'aufgabe_machen', 'args': {'stufe': 0}})
        self.assertEqual(out['result']['stufe'], 0)
        obj = self.hub.object_view('intent', made['id'])
        self.assertEqual(obj['stufen'][0]['tasks'][0]['id'], out['result']['mission_id'])
        self.assertIn('Stufe 1 von 8', obj['stufen'][0]['tasks'][0]['title'])
        self.assertEqual(obj['stufen'][1]['tasks'], [])
        with self.assertRaises(ValueError):
            self.hub.act({'type': 'intent', 'id': made['id'], 'verb': 'aufgabe_machen', 'args': {'stufe': 99}})
        with self.assertRaises(ValueError):
            self.hub.intent_create({'vorlage': 'gibt-es-nicht'})

    def test_an_intent_without_stages_works_as_before(self):
        made = self.hub.intent_create({'title': 'Nur ein Satz', 'text': ''})
        self.assertEqual(made['stufen'], [])
        obj = self.hub.object_view('intent', made['id'])
        self.assertEqual(obj['state'], 'noch keine Aufgabe')
        out = self.hub.act({'type': 'intent', 'id': made['id'], 'verb': 'aufgabe_machen'})
        self.assertIsNone(out['result']['stufe'])


if __name__ == '__main__':
    unittest.main()
