"""Zielkette (Spec 1, D1.1 `chain.py`, ORC-13, S1.C1): Glieder in der Reihenfolge Vorhaben, Projekt, Eltern (Wurzel zuerst),
Aufgabe; fehlt ein Glied, steht „Glied nicht gefunden“; der Text ist höchstens `max_chars` lang, gekürzt von vorn, die Aufgabe
bleibt vollständig."""
import unittest

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.orchestra import chain

TASK = {'id': 'T3', 'title': 'Test schreiben', 'description': 'Prüft den Parser.', 'goal_ref': 'V1', 'project_id': 'P1', 'parent_id': 'T2'}
PARENTS = [{'id': 'T1', 'title': 'Wurzel', 'parent_id': None}, {'id': 'T2', 'title': 'Zwischen', 'parent_id': 'T1'}]
GOAL = {'id': 'V1', 'titel': 'Parser 2.0'}
PROJECT = {'id': 'P1', 'titel': 'Werkbank'}


class Order(unittest.TestCase):
    def test_links_go_goal_project_parents_root_first_task(self):
        out = chain.build(TASK, PARENTS, PROJECT, GOAL)
        self.assertEqual([(g['art'], g['id'], g['titel']) for g in out['glieder']],
                         [('vorhaben', 'V1', 'Parser 2.0'), ('projekt', 'P1', 'Werkbank'), ('eltern', 'T1', 'Wurzel'),
                          ('eltern', 'T2', 'Zwischen'), ('aufgabe', 'T3', 'Test schreiben')])
        lines = out['text'].split('\n')
        self.assertEqual(lines[0], '=== Zielkette (Daten) ===')
        self.assertEqual(lines[-1], '=== Ende Zielkette ===')
        self.assertEqual(lines[1:-1], ['Vorhaben V1: Parser 2.0', 'Projekt P1: Werkbank', 'Elternaufgabe T1: Wurzel',
                                       'Elternaufgabe T2: Zwischen', 'Aufgabe T3: Test schreiben', 'Prüft den Parser.'])

    def test_a_task_without_goal_project_or_parent_is_only_the_task(self):
        task = {'id': 'T9', 'title': 'Allein', 'goal_ref': None, 'project_id': None, 'parent_id': None}
        out = chain.build(task, [], None, None)
        self.assertEqual(out['glieder'], [{'art': 'aufgabe', 'id': 'T9', 'titel': 'Allein'}])
        self.assertEqual(out['text'], '=== Zielkette (Daten) ===\nAufgabe T9: Allein\n=== Ende Zielkette ===')

    def test_title_or_titel_are_both_read(self):
        out = chain.build(TASK, PARENTS, {'id': 'P1', 'title': 'Englisch'}, GOAL)
        self.assertEqual(out['glieder'][1]['titel'], 'Englisch')


class Missing(unittest.TestCase):
    def test_a_deleted_goal_or_project_is_a_link_not_found(self):
        out = chain.build(TASK, PARENTS, None, None)
        self.assertEqual(out['glieder'][:2], [{'art': 'vorhaben', 'id': 'V1', 'titel': None}, {'art': 'projekt', 'id': 'P1', 'titel': None}])
        self.assertIn('Vorhaben V1: Glied nicht gefunden', out['text'])
        self.assertIn('Projekt P1: Glied nicht gefunden', out['text'])

    def test_a_missing_parent_above_the_known_ones_is_a_link_not_found(self):
        parents = [{'id': 'T2', 'title': 'Zwischen', 'parent_id': 'T1'}]
        out = chain.build(TASK, parents, PROJECT, GOAL)
        self.assertEqual([(g['art'], g['id'], g['titel']) for g in out['glieder'][2:]],
                         [('eltern', 'T1', None), ('eltern', 'T2', 'Zwischen'), ('aufgabe', 'T3', 'Test schreiben')])
        out = chain.build(TASK, [], PROJECT, GOAL)
        self.assertEqual(out['glieder'][2], {'art': 'eltern', 'id': 'T2', 'titel': None})
        self.assertIn('Elternaufgabe T2: Glied nicht gefunden', out['text'])

    def test_an_empty_title_counts_as_missing(self):
        out = chain.build(TASK, PARENTS, PROJECT, {'id': 'V1', 'titel': ''})
        self.assertIsNone(out['glieder'][0]['titel'])


class Bound(unittest.TestCase):
    def test_the_text_is_cut_from_the_front_and_the_task_stays_whole(self):
        parents = [{'id': f'T{i}', 'title': 'Elternaufgabe mit langem Titel ' + 'x' * 40, 'parent_id': f'T{i - 1}' if i else None}
                   for i in range(20)]
        task = dict(TASK, parent_id='T19', description='Beschreibung ' + 'y' * 300)
        out = chain.build(task, parents, PROJECT, GOAL, max_chars=600)
        self.assertLessEqual(len(out['text']), 600)
        self.assertTrue(out['text'].startswith('=== Zielkette (Daten) ===\n(gekürzt)\n'))
        self.assertTrue(out['text'].endswith('Aufgabe T3: Test schreiben\nBeschreibung ' + 'y' * 300 + '\n=== Ende Zielkette ==='))
        self.assertNotIn('Vorhaben V1', out['text'])
        self.assertIn('Elternaufgabe T19:', out['text'])
        self.assertEqual(len(out['glieder']), 23, 'die Glieder bleiben vollständig, gekürzt wird nur der Text')

    def test_the_default_limit_is_4000_and_a_short_chain_is_not_cut(self):
        out = chain.build(TASK, PARENTS, PROJECT, GOAL)
        self.assertNotIn('(gekürzt)', out['text'])
        long_parents = [{'id': f'T{i}', 'title': 'z' * 200, 'parent_id': None} for i in range(40)]
        out = chain.build(dict(TASK, parent_id='T39'), long_parents, PROJECT, GOAL)
        self.assertLessEqual(len(out['text']), 4000)

    def test_a_task_longer_than_the_limit_is_still_complete(self):
        task = dict(TASK, description='w' * 5000)
        out = chain.build(task, PARENTS, PROJECT, GOAL, max_chars=1000)
        self.assertIn('w' * 5000, out['text'])
        self.assertNotIn('Elternaufgabe', out['text'])


if __name__ == '__main__':
    unittest.main()
