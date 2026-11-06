import json
from pathlib import Path
import tempfile
import unittest
from sedra_runtime.workflows.schema import validate, strict_json, redacted
from sedra_runtime.workflows.policy import executable, assessment
from sedra_runtime.workflows.store import WorkflowStore
from workflow_fixture import sample


class Interchange(unittest.TestCase):
    def test_unknown_fields_and_nodes_roundtrip(self):
        doc = sample(); doc['future'] = {'anything': [1, False]}
        doc['nodes'][1].update(type='community.unknown', future={'x': 'y'})
        with tempfile.TemporaryDirectory() as folder:
            store = WorkflowStore(folder); saved = store.save(doc)
            self.assertEqual(store.read(saved['id'])['workflow'], doc)
            self.assertFalse(assessment(doc)['executable'])

    def test_invalid_json_duplicates_and_nonfinite(self):
        for raw in ('{"name":"a","name":"b"}', '{"x":NaN}', '{'):
            with self.assertRaises(ValueError):
                strict_json(raw)

    def test_duplicate_node_identity_and_dangling_edge(self):
        for field in ('id', 'name'):
            doc = sample(); doc['nodes'][1][field] = doc['nodes'][0][field]
            with self.assertRaises(ValueError): validate(doc)
        doc = sample(); doc['connections']['Start']['main'][0][0]['node'] = 'missing'
        with self.assertRaises(ValueError): validate(doc)

    def test_revision_conflict_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            store = WorkflowStore(folder); first = store.save(sample())
            newer = sample(); newer['name'] = 'Second'
            second = store.save(newer, first['id'], 1)
            with self.assertRaisesRegex(ValueError, 'conflict'): store.save(sample(), first['id'], 1)
            self.assertEqual(store.read(first['id'], 1), first)
            self.assertEqual(store.read(first['id']), second)

    def test_invalid_id_cannot_escape_store(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError): WorkflowStore(folder).read('../../x')

    def test_changed_revision_fails_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            store = WorkflowStore(folder); record = store.save(sample())
            path = store.root / record['id'] / '000001.json'
            value = json.loads(path.read_text()); value['workflow']['name'] = 'tampered'
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'integrity'): store.read(record['id'])

    def test_redacted_export_does_not_modify_original(self):
        doc = sample(); doc['nodes'][1]['credentials'] = {'id': 'private'}
        doc['nodes'][1]['parameters']['authorization'] = 'secret'
        clean = redacted(doc)
        self.assertEqual(doc['nodes'][1]['credentials'], {'id': 'private'})
        self.assertEqual(clean['nodes'][1]['credentials'], '[REDACTED]')
        self.assertNotIn('secret', json.dumps(clean))


class ExecutionProfile(unittest.TestCase):
    def test_supported_data_pipeline(self):
        self.assertEqual(len(executable(sample())['nodes']), 2)

    def test_unsupported_versions_code_and_credentials(self):
        for patch in ({'typeVersion': 99}, {'type': 'n8n-nodes-base.code'}, {'credentials': {'x': 'y'}}, {'continueOnFail': True}):
            doc = sample(); doc['nodes'][1].update(patch)
            self.assertFalse(assessment(doc)['executable'])

    def test_arbitrary_expressions_blocked_even_in_metadata_parameters(self):
        for key in ('value', 'id'):
            doc = sample(); doc['nodes'][1]['parameters']['assignments']['assignments'][0][key] = '={{ $env.SECRET }}'
            self.assertFalse(assessment(doc)['executable'])

    def test_simple_data_path_supported(self):
        doc = sample(); doc['nodes'][1]['parameters']['assignments']['assignments'][0]['value'] = '={{ $json.text }}'
        self.assertTrue(assessment(doc)['executable'])

    def test_cycles_and_unreachable_nodes_blocked(self):
        doc = sample(); doc['connections']['Set'] = {'main': [[{'node': 'Start', 'type': 'main', 'index': 0}]]}
        self.assertFalse(assessment(doc)['executable'])
        doc = sample(); doc['connections'] = {}
        self.assertFalse(assessment(doc)['executable'])

    def test_pinned_data_and_unclassified_options_blocked(self):
        doc = sample(); doc['pinData'] = {'Start': [{'json': {'text': 'hidden'}}]}
        self.assertFalse(assessment(doc)['executable'])
        doc = sample(); doc['nodes'][1]['parameters']['options']['arbitrary'] = True
        self.assertFalse(assessment(doc)['executable'])

    def test_original_settings_are_preserved_but_not_executed(self):
        doc = sample(); doc['settings']['errorWorkflow'] = 'external'
        safe = executable(doc)
        self.assertNotIn('errorWorkflow', safe['settings'])
        self.assertEqual(doc['settings']['errorWorkflow'], 'external')
