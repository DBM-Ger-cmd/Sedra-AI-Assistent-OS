import unittest
from guppi_runtime.models.openai_local import OpenAICompatibleLocalAdapter, normalize_usage, split_harmony
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests


class FakeAdapter(OpenAICompatibleLocalAdapter):
    def __init__(self, reply):
        super().__init__('fake', 'http://127.0.0.1:1234')
        self.reply = reply

    def _request(self, method, path, payload=None):
        return self.reply


def reply(content, finish='stop', reasoning=None, usage=None):
    message = {'content': content}
    if reasoning is not None: message['reasoning_content'] = reasoning
    return {'choices': [{'message': message, 'finish_reason': finish}], 'usage': usage}


class OpenAILocalFieldsTest(unittest.TestCase):
    def chat(self, r):
        return FakeAdapter(r).chat([{'role': 'user', 'content': 'x'}], model='m')

    def test_normal_answer(self):
        out = self.chat(reply('pong', reasoning='thinking'))
        self.assertEqual(out['finish_reason'], 'stop')
        self.assertFalse(out['truncated'])
        self.assertFalse(out['empty_answer'])
        self.assertEqual(out['reasoning_chars'], len('thinking'))

    def test_reasoning_model_out_of_tokens_is_flagged_not_silent(self):
        out = self.chat(reply('', finish='length', reasoning='a' * 300))
        self.assertTrue(out['truncated'])
        self.assertTrue(out['empty_answer'])
        self.assertEqual(out['reasoning_chars'], 300)

    def test_missing_or_none_content(self):
        out = self.chat({'choices': [{'message': {'content': None}, 'finish_reason': None}]})
        self.assertTrue(out['empty_answer'])
        self.assertFalse(out['truncated'])
        self.assertEqual(out['reasoning_chars'], 0)
        self.assertIsNone(out['usage'])

    def test_whitespace_only_is_empty(self):
        self.assertTrue(self.chat(reply('  \n'))['empty_answer'])

    def test_reasoning_alias_field(self):
        r = reply('ok'); r['choices'][0]['message']['reasoning'] = 'abc'
        self.assertEqual(self.chat(r)['reasoning_chars'], 3)

    def test_usage_reasoning_tokens_are_part_of_output(self):
        u = normalize_usage({'prompt_tokens': 17, 'completion_tokens': 159, 'completion_tokens_details': {'reasoning_tokens': 155}})
        self.assertEqual(u, {'input_tokens': 17, 'output_tokens': 159, 'reasoning_tokens': 155})

    def test_usage_rejects_impossible_reasoning_tokens(self):
        u = normalize_usage({'prompt_tokens': 1, 'completion_tokens': 5, 'completion_tokens_details': {'reasoning_tokens': 9}})
        self.assertNotIn('reasoning_tokens', u)
        u = normalize_usage({'prompt_tokens': 1, 'completion_tokens': 5, 'completion_tokens_details': {'reasoning_tokens': True}})
        self.assertNotIn('reasoning_tokens', u)

    def test_raw_harmony_gives_the_final_channel_as_answer(self):
        # gpt-oss with --reasoning-format none, as seen on 2026-10-02 (server parser rejected `<|constrain|>JSON`)
        raw = ('<|channel|>analysis<|message|>Need to fix greet.<|end|><|start|>assistant<|channel|>final <|constrain|>JSON'
               '<|message|>{"changes":[]}')
        out = self.chat(reply(raw))
        self.assertEqual(out['content'], '{"changes":[]}')
        self.assertEqual(out['reasoning_chars'], len('Need to fix greet.'))
        self.assertFalse(out['empty_answer'])

    def test_harmony_without_final_is_an_empty_answer(self):
        out = self.chat(reply('<|channel|>analysis<|message|>still thinking', finish='length'))
        self.assertTrue(out['empty_answer']); self.assertTrue(out['truncated'])

    def test_plain_text_is_not_touched(self):
        self.assertIsNone(split_harmony('pong'))
        self.assertIsNone(split_harmony('a <|channel|> word without a message marker'))

    def test_usage_without_counts_is_none(self):
        self.assertIsNone(normalize_usage(None))
        self.assertIsNone(normalize_usage({'prompt_tokens': 1}))


if __name__ == '__main__':
    unittest.main()
