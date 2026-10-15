import os
import unittest

from guppi_runtime.agent_manager.agent_contracts import ContractError
from guppi_runtime.agent_manager.yaml_loader import MAX_BYTES, MAX_DEPTH, load_strict

ARCHIVE = r"C:\Users\<user>\AppData\Local\Temp\claude\C--Users-<user>\f0a5651b-ba8d-432f-be11-58e72b5ca9ea\scratchpad\am\GUPPI_Agent_Manager_Developer_Archive_v1.0\examples"


class StrictYamlTest(unittest.TestCase):
    def refused(self, text, part=""):
        with self.assertRaises(ContractError) as ctx:
            load_strict(text)
        self.assertEqual(ctx.exception.code, "yaml_refused")
        self.assertIn(part, str(ctx.exception))

    def test_plain_documents_load(self):
        self.assertEqual(load_strict("a: 1\nb: [x, 2.5, true, null]\nc: {d: e}\n"), {"a": 1, "b": ["x", 2.5, True, None], "c": {"d": "e"}})
        self.assertEqual(load_strict(b"- 1\n- two\n"), [1, "two"])
        self.assertEqual(load_strict("hello"), "hello")

    def test_duplicate_keys_refused(self):
        self.refused("a: 1\na: 2\n", "duplicate key 'a'")
        self.refused("outer:\n  k: 1\n  k: 2\n", "duplicate key 'k'")
        self.refused("- {x: 1, x: 2}\n", "duplicate key")

    def test_anchors_aliases_tags_refused(self):
        self.refused("a: &x 1\nb: *x\n")
        self.refused("a: &x [1]\n")
        self.refused("a: !!str 5\n", "tags")
        self.refused("a: !custom {b: 1}\n", "tags")
        self.refused("base: {a: 1}\nd:\n  <<: {a: 2}\n", "merge")

    def test_keys_must_be_plain_strings(self):
        self.refused("1: a\n", "string keys")
        self.refused("true: a\n", "string keys")
        self.refused("? [a, b]\n: c\n", "string keys")
        self.refused("~: a\n", "string keys")

    def test_other_value_types_and_numbers_refused(self):
        self.refused("a: .inf\n", "non-finite")
        self.refused("a: .nan\n", "non-finite")
        self.refused("when: 2026-10-06\n", "date")
        self.refused("when: 2026-10-06 10:00:00\n", "datetime")
        self.assertEqual(load_strict("when: '2026-10-06T10:00:00Z'\n"), {"when": "2026-10-06T10:00:00Z"})

    def test_limits_and_documents(self):
        self.refused("a: " + "x" * MAX_BYTES, "larger")
        self.refused("[" * (MAX_DEPTH + 1) + "]" * (MAX_DEPTH + 1), "deep")
        self.assertIsNotNone(load_strict("[" * MAX_DEPTH + "]" * MAX_DEPTH))
        self.refused("a: 1\n---\nb: 2\n", "exactly one")
        self.refused("", "exactly one")
        self.refused("a: [1\n", "not valid YAML")
        self.refused(b"a: \xff\xfe\n", "not valid YAML")
        self.refused(5, "text or bytes")

    @unittest.skipUnless(os.path.isdir(ARCHIVE), "archive examples are not on this machine")
    def test_archive_examples_load(self):
        found = 0
        for root, _, names in os.walk(ARCHIVE):
            for name in names:
                if name.endswith((".yaml", ".yml")):
                    with open(os.path.join(root, name), "rb") as handle:
                        self.assertIsInstance(load_strict(handle.read()), dict, name)
                    found += 1
        self.assertGreaterEqual(found, 5)


if __name__ == "__main__":
    unittest.main()
