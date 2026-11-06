import json
from pathlib import Path
import tempfile
import unittest
from sedra_runtime.workflows.process import PREFIX, metadata
from sedra_runtime.workflows.schema import validate, report
from sedra_runtime.workflows.policy import assessment
from sedra_runtime.workflows.store import WorkflowStore
from sedra_runtime.workflows.versions import compare
from workflow_fixture import process_sample


class ProcessVersions(unittest.TestCase):
    def test_model_is_visible_and_cannot_execute_even_with_known_nodes(self):
        doc = process_sample(); self.assertEqual(validate(doc), doc)
        self.assertEqual(report(doc)['process']['core_steps'], 2)
        self.assertEqual(assessment(doc)['reason'], 'process_model_requires_implementation')
        for node in doc['nodes']: node.pop('disabled', None)
        self.assertFalse(assessment(doc)['executable'])

    def test_invalid_annotation_is_not_an_execution_escape(self):
        for value in ('broken', json.dumps({'schema': 1, 'kind': []})):
            doc = process_sample(); doc['nodes'][0]['notes'] = PREFIX + value
            with self.assertRaises(ValueError): validate(doc)

    def test_process_fields_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowStore(tmp); record = store.save(process_sample(), change_note='Erstentwurf')
            self.assertEqual(store.read(record['id'])['workflow'], process_sample())
            self.assertEqual(record['change_note'], 'Erstentwurf')
            self.assertEqual(len(record['record_digest']), 64)

    def test_edit_requires_reason_and_links_prior_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowStore(tmp); first = store.save(process_sample())
            doc = process_sample(); fields = metadata(doc['nodes'][1]); fields['role'] = 'Zweite Prüfrolle'
            doc['nodes'][1]['notes'] = PREFIX + json.dumps(fields)
            with self.assertRaisesRegex(ValueError, 'change_note_required'): store.save(doc, first['id'], 1)
            second = store.save(doc, first['id'], 1, 'Verantwortung präzisiert')
            self.assertEqual(second['previous_record_digest'], first['record_digest'])
            self.assertEqual(store.read(first['id'], 1), first)
            changes = [c for c in second['changes'] if c['field'] == 'Zuständige Rolle']
            self.assertEqual(changes[0]['before'], 'Prüfende Rolle')
            self.assertEqual(changes[0]['after'], 'Zweite Prüfrolle')

    def test_tampered_change_note_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowStore(tmp); first = store.save(process_sample())
            second = store.save(process_sample(), first['id'], 1, 'Überarbeitet')
            path = store.root / first['id'] / '000001.json'
            raw = json.loads(path.read_text()); raw['change_note'] = 'tampered';path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, 'version_chain'): store.read(first['id'], 2)

    def test_legacy_revision_can_be_extended_without_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowStore(tmp); first = store.save(process_sample())
            path = store.root / first['id'] / '000001.json'
            legacy = {k: first[k] for k in ('id', 'revision', 'digest', 'saved_at', 'workflow')}
            path.write_text(json.dumps(legacy))
            newer = store.save(process_sample(), first['id'], 1, 'Neue Dokumentation')
            self.assertEqual(store.read(first['id'])['revision'], 2)
            self.assertIsNotNone(newer['previous_record_digest'])

    def test_diff_tracks_branches_and_does_not_copy_credential_values(self):
        a, b = process_sample(), process_sample(); b['connections'] = {}
        b['nodes'][1]['credentials'] = {'password': 'secret-value'}
        changes = compare(a, b)
        self.assertTrue(any(c['field'] == 'Verbindungen' for c in changes))
        self.assertNotIn('secret-value', json.dumps(changes))
