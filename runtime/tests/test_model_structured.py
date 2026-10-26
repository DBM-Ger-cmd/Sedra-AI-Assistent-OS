"""Build 17, Schritt 1: strukturierte Antworten vom lokalen Modell (models/structured.py, ModelRouter.chat(schema=…))."""
import unittest

from guppi_runtime.core.content_guard import ContentGuard
from guppi_runtime.models import structured
from guppi_runtime.models.base import BaseModelAdapter, ModelAdapterError
from guppi_runtime.models.router import ModelRouter

VORGABE = {'type': 'object', 'additionalProperties': False, 'required': ['id', 'name', 'raster'],
           'properties': {'id': {'type': 'string', 'pattern': '^[a-z][a-z0-9-]{1,30}$'},
                          'name': {'type': 'string', 'minLength': 1, 'maxLength': 40},
                          'raster': {'type': 'array', 'minItems': 1, 'maxItems': 6, 'items': {'type': 'string', 'enum': ['leiste', 'orte', 'werkstueck', 'gespraech']}},
                          'hoehe': {'type': 'integer', 'minimum': 40, 'maximum': 400}}}


class Scripted(BaseModelAdapter):
    id = 'fake'

    def __init__(self, replies):
        self.replies, self.calls, self.seen, self.kwargs = list(replies), 0, [], []

    def health(self): return True

    def chat(self, messages, model=None, **kwargs):
        self.calls += 1; self.seen.append(messages); self.kwargs.append(kwargs)
        return {'provider': self.id, 'model': model, 'content': self.replies.pop(0), 'usage': {}}


class Audit:
    def __init__(self): self.rows = []
    def append(self, event, **kw): self.rows.append((event, kw))


def router(*replies):
    r = ModelRouter(Audit()); r.content_guard = ContentGuard(mode='sandbox'); r.register(Scripted(replies)); return r


class DasSchema(unittest.TestCase):
    def test_the_subset_is_accepted_and_the_rest_refused_before_any_call(self):
        structured.check_schema(VORGABE)
        for bad, word in (({'type': 'object', 'properties': {'a': {'$ref': '#/x'}}}, '$ref'),
                          ({'type': 'object', 'properties': {'a': {'type': 'string'}}, 'additionalProperties': True}, 'additionalProperties'),
                          ({'type': 'object', 'properties': {'a': {'type': 'string', 'pattern': 'abc'}}}, 'pattern'),
                          ({'type': 'object', 'properties': {'a': {'type': 'number', 'minimum': 1}}}, 'integer'),
                          ({'type': 'object', 'properties': {'a': {'type': 'string', 'format': 'email'}}}, 'format'),
                          ({'type': 'object', 'properties': {'a': {'oneOf': []}}}, 'oneOf'),
                          ({'type': 'object', 'properties': {'a-b': {'type': 'string'}}}, 'Feldname'),
                          ({'type': 'array'}, 'items'), ({'type': 'object'}, 'properties'), ({'type': 'thing'}, 'type')):
            with self.assertRaises(structured.SchemaError, msg=word) as ctx:
                structured.check_schema(bad)
            self.assertIn(word, str(ctx.exception))

    def test_validate_says_in_sentences_what_is_wrong(self):
        ok = {'id': 'meine', 'name': 'Meine', 'raster': ['orte', 'werkstueck'], 'hoehe': 100}
        self.assertEqual(structured.validate(ok, VORGABE), [])
        errors = structured.validate({'id': 'X', 'raster': ['foo'], 'hoehe': 10, 'extra': 1}, VORGABE)
        text = ' '.join(errors)
        for word in ('„name“ fehlt', 'Muster', 'einer von', 'mindestens 40', '„extra“ gibt es nicht'):
            self.assertIn(word, text, errors)
        self.assertEqual(structured.validate({'id': 'a1', 'name': 'x', 'raster': [], 'hoehe': True}, VORGABE)[:2],
                         ['$.raster: mindestens 1 Einträge', '$.hoehe: muss eine ganze Zahl sein'])

    def test_a_nullable_type_list_is_accepted_and_checked(self):
        # 27.10.2026 (Betriebsstunde): das Schema des Unterarbeiters hat rueckfrage: ["string", "null"]; vorher TypeError "unhashable type: 'list'"
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['a', 'b'],
                  'properties': {'a': {'type': 'string'}, 'b': {'type': ['string', 'null'], 'maxLength': 5}}}
        structured.check_schema(schema)
        self.assertEqual(structured.validate({'a': 'x', 'b': None}, schema), [])
        self.assertEqual(structured.validate({'a': 'x', 'b': 'kurz'}, schema), [])
        self.assertTrue(structured.validate({'a': 'x', 'b': 7}, schema))
        self.assertTrue(structured.validate({'a': 'x', 'b': 'viel zu lang'}, schema))
        for bad in (['string'], ['string', 'integer'], ['string', 'string'], ['null', 'null'], ['string', 'null', 'integer'], ['gibtsnicht', 'null'], [['string'], 'null']):
            with self.assertRaises(structured.SchemaError, msg=str(bad)):
                structured.check_schema({'type': 'object', 'additionalProperties': False, 'properties': {'x': {'type': bad}}})

    def test_the_foreman_schema_passes_the_checker(self):
        from guppi_runtime.orchestra import decompose
        structured.check_schema(decompose.SCHEMA)
        self.assertEqual(structured.validate({'teilaufgaben': [{'titel': 'a', 'beschreibung': 'b', 'rolle': 'coder', 'blocker': [], 'akzeptanz': 'c'}], 'rueckfrage': None}, decompose.SCHEMA), [])

    def test_parse_strips_a_fence_and_names_bad_json(self):
        self.assertEqual(structured.parse('```json\n{"a": 1}\n```'), ({'a': 1}, None))
        self.assertEqual(structured.parse('{"a": 1}')[0], {'a': 1})
        self.assertIn('kein gültiges JSON', structured.parse('{"a": }')[1])
        self.assertIn('leer', structured.parse('')[1])


class DerAufruf(unittest.TestCase):
    def test_a_valid_answer_comes_back_parsed_in_one_round(self):
        r = router('{"id":"bruecke","name":"Brücke","raster":["orte","werkstueck","gespraech"]}')
        out = r.chat('M', [{'role': 'user', 'content': 'links Orte, rechts Werkstück, unten Gespräch'}], schema=VORGABE)
        self.assertEqual(out['parsed']['id'], 'bruecke')
        self.assertEqual(out['rounds'], 1)
        adapter = r.adapters['fake']
        self.assertEqual(adapter.kwargs[0]['response_format']['json_schema']['schema'], VORGABE)
        self.assertEqual(adapter.kwargs[0]['temperature'], 0)
        self.assertEqual(adapter.seen[0][0]['role'], 'system')
        self.assertIn('"raster"', adapter.seen[0][0]['content'])

    def test_the_schema_hint_comes_after_existing_system_messages(self):
        r = router('{"id":"a1","name":"A","raster":["orte"]}')
        r.chat('M', [{'role': 'system', 'content': 'Du bist SEDRA.'}, {'role': 'user', 'content': 'x'}], schema=VORGABE)
        roles = [m['role'] for m in r.adapters['fake'].seen[0]]
        self.assertEqual(roles, ['system', 'system', 'user'])
        self.assertEqual(r.adapters['fake'].seen[0][0]['content'], 'Du bist SEDRA.')

    def test_a_wrong_answer_goes_back_with_the_error_and_the_second_try_counts(self):
        r = router('```json\n{"id":"A B","name":"x","raster":["foo"]}\n```', '{"id":"a-b","name":"x","raster":["orte"]}')
        out = r.chat('M', [{'role': 'user', 'content': 'x'}], schema=VORGABE)
        self.assertEqual(out['rounds'], 2)
        second = r.adapters['fake'].seen[1]
        self.assertEqual(second[-2]['role'], 'assistant')
        self.assertIn('passt nicht zum Schema', second[-1]['content'])
        self.assertIn('Muster', second[-1]['content'])
        self.assertIn('MODEL_SCHEMA_RETRY', [e for e, _ in r.audit.rows])

    def test_after_three_rounds_it_fails_honestly(self):
        r = router('nix', 'immer noch nix', '{"id": 1}')
        with self.assertRaises(ModelAdapterError) as ctx:
            r.chat('M', [{'role': 'user', 'content': 'x'}], schema=VORGABE)
        self.assertTrue(str(ctx.exception).startswith('structured_output_failed:'))
        self.assertEqual(r.adapters['fake'].calls, 3)

    def test_every_round_goes_through_the_content_guard(self):
        r = router('nix', '{"id":"a1","name":"A","raster":["orte"]}')
        r.chat('M', [{'role': 'user', 'content': 'x'}], schema=VORGABE)
        self.assertEqual(r.content_guard.counts['SG_MODEL_CALL'], 2)

    def test_a_bad_schema_never_reaches_the_model(self):
        r = router('{"a":1}')
        with self.assertRaises(structured.SchemaError):
            r.chat('M', [{'role': 'user', 'content': 'x'}], schema={'type': 'object', 'properties': {'a': {'$ref': '#'}}})
        self.assertEqual(r.adapters['fake'].calls, 0)

    def test_without_schema_nothing_changed(self):
        r = router('Hallo.')
        out = r.chat('M', [{'role': 'user', 'content': 'x'}])
        self.assertEqual(out['content'], 'Hallo.')
        self.assertNotIn('parsed', out)
        self.assertNotIn('response_format', r.adapters['fake'].kwargs[0])


if __name__ == '__main__':
    unittest.main()
