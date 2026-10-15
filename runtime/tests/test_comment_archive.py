import json
import unittest

from guppi_runtime.comment_archive import extract_comments, to_jsonl

SRC = '"""Mod."""\n# top\nclass Box:\n    def put(self, v):\n        """Put."""\n        return v  # tail\n'


class ExtractTest(unittest.TestCase):
    def test_comments_and_docstrings_come_with_line_owner_and_text(self):
        got = [(e["line"], e["kind"], e["owner"], e["inline"], e["text"]) for e in extract_comments(SRC)]
        self.assertEqual(got, [(1, "docstring", "<module>", False, "Mod."), (2, "comment", "<module>", False, "top"), (5, "docstring", "Box.put", False, "Put."), (6, "comment", "Box.put", True, "tail")])

    def test_unparseable_or_foreign_input_gives_nothing(self):
        for source in (None, 5, "", "def f(:\n  # x\n"):
            self.assertEqual(extract_comments(source), [])

    def test_a_hash_inside_a_string_is_no_comment(self):
        self.assertEqual(extract_comments('s = "# no"\n'), [])


class JsonlTest(unittest.TestCase):
    def test_one_sorted_json_object_per_line_with_the_meta_merged(self):
        text = to_jsonl(extract_comments(SRC)[:1], {"path": "m.py", "stage": "basics"})
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(json.loads(text), {"line": 1, "kind": "docstring", "owner": "<module>", "inline": False, "text": "Mod.", "path": "m.py", "stage": "basics"})
        self.assertEqual(to_jsonl([], {"a": 1}), "")


if __name__ == "__main__":
    unittest.main()
