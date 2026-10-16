import json, tempfile, unittest
from pathlib import Path
from guppi_runtime.knowledge import KnowledgeStore


class LessonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = KnowledgeStore(Path(self.tmp.name) / 'records.jsonl')
        self.store.add_lesson('regex', 'A: regex lesson', triggers=['re.match(', 're.search(', 'import re'])
        self.store.add_lesson('port', 'B: port lesson', triggers=['regex', 'digits', 'port'])
        self.store.add_lesson('wrap', 'C: wrap library errors', triggers=['raise valueerror('])
        self.store.add_lesson('url', 'D: urlparse lesson', triggers=['urlparse', '.port'])
    def names(self, **kw):
        return [r['content']['summary'][0] for r in self.store.lessons_for(self.text, **kw)]
    text = 'import re\nmatch = re.match(r"x", s)\nraise ValueError("bad")\nsettings["port"] = urlparse(u).port'

    def test_without_the_new_options_nothing_changed(self):
        self.assertEqual(self.names(), ['A', 'B', 'C', 'D'])                                          # oldest first, as always
        self.assertEqual(self.names(limit=2), ['A', 'B'])
        self.assertEqual(self.store.lessons_for(123), []); self.assertEqual(KnowledgeStore(Path(self.tmp.name) / 'none.jsonl').lessons_for('x'), [])

    def test_ranked_lessons_put_the_best_fit_first(self):
        # A matches 2 triggers (`re.match(`, `import re`), D 2 (`urlparse`, `.port`) but shorter ones, B 1 (`port`; `regex` and `digits` do not occur), C 1 (`raise valueerror(`)
        order = self.names(rank=True)
        self.assertEqual(order[0], 'A'); self.assertEqual(order[1], 'D'); self.assertEqual(set(order), {'A', 'B', 'C', 'D'})
        self.assertEqual(self.names(rank=True, limit=1), ['A'])

    def test_a_generic_word_alone_does_not_attach_a_lesson(self):
        self.text = 'def get(settings, key):\n    return settings["port"]'
        self.assertEqual(self.names(), ['B'])                                                          # before: the unicode-digit lesson for a dict lookup
        self.assertEqual(self.names(rank=True, min_specificity=8), [])
        self.text = 'raise ValueError("x")'
        self.assertEqual(self.names(rank=True, min_specificity=8, limit=1), ['C'])                      # a specific trigger is enough on its own

    def test_equal_scores_keep_their_age_order_and_inactive_lessons_never_match(self):
        self.store.add_lesson('twin', 'E: twin of C', triggers=['raise valueerror('])
        self.text = 'raise ValueError("x")'
        self.assertEqual(self.names(rank=True), ['C', 'E'])
        lines = self.store.path.read_text(encoding='utf-8').splitlines()
        first = json.loads(lines[2]); self.assertEqual(first['status'], 'active'); first['status'] = 'archived'; lines[2] = json.dumps(first)
        self.store.path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.assertEqual(self.names(rank=True), ['E'])


if __name__ == '__main__':
    unittest.main()
