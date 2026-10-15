import json, tempfile, unittest
from pathlib import Path
from guppi_runtime.cli import main
from guppi_runtime.devenv.lesson_store import default_path, lesson_for, manage

TEXT = "Wrap library errors in your own error class before they leave the module."


class LessonStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = default_path(self.tmp.name)

    def test_a_card_is_used_only_after_the_captain_approves_it(self):
        self.assertIsNone(lesson_for(self.path, "wrap library errors in a module"))
        card = manage(self.path, "propose", text=TEXT, source="run-1", now=1000.0)["proposed"]
        self.assertIsNone(lesson_for(self.path, "wrap library errors in a module"))
        manage(self.path, "approve", card_id=card, now=1000.0)
        self.assertEqual(lesson_for(self.path, "wrap library errors in a module", now=2000.0), TEXT)
        used = manage(self.path, "list")["cards"][0]
        self.assertEqual((used["state"], used["uses"], used["last_used"]), ("active", 1, 2000.0))
        self.assertIsNone(lesson_for(self.path, "something about sockets"))

    def test_reject_sweep_and_bad_requests(self):
        card = manage(self.path, "propose", text=TEXT, source="run-1", now=1000.0)["proposed"]
        manage(self.path, "reject", card_id=card, reason="too vague")
        self.assertEqual(manage(self.path, "list")["cards"][0]["state"], "archived")
        with self.assertRaises(ValueError): manage(self.path, "approve", card_id=card)
        with self.assertRaises(ValueError): manage(self.path, "propose", text="short", source="x")
        with self.assertRaises(ValueError): manage(self.path, "burn")
        second = manage(self.path, "propose", text=TEXT.replace("Wrap", "Always wrap"), source="run-2", now=1000.0)["proposed"]
        manage(self.path, "approve", card_id=second, now=1000.0)
        self.assertEqual(len(manage(self.path, "sweep", now=1000.0 + 20 * 86400)["swept"]), 1)

    def test_a_damaged_file_is_no_lesson_and_is_not_replaced(self):
        self.path.parent.mkdir(parents=True); self.path.write_text("{broken", encoding="utf-8")
        self.assertIsNone(lesson_for(self.path, "wrap library errors"))
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{broken")

    def test_the_command_line_reaches_the_store(self):
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--root", self.tmp.name, "lessons", "propose", "--text", TEXT]), 0)
            self.assertEqual(main(["--root", self.tmp.name, "lessons", "approve", "--id", "x"]), 2)
        self.assertIn('"proposed"', out.getvalue()); self.assertIn('"refused"', out.getvalue())


if __name__ == "__main__":
    unittest.main()
