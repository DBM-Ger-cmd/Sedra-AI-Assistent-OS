import importlib.util
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.rework_watch import MAX_ENTRIES, START, ReworkWatch, candidate_key, failure_signature, hint_key, same_as_earlier

FEEDBACK_1 = """REPRO test_ports (test_uix_window.Ports.test_ports): AssertionError: 'Port out of range 0-65535' != 'uix_url_not_allowed'
REPRO   input 'http://127.0.0.1:65535/': expected the URL back, got ValueError: Port out of range 0-65535 at uix_window.py:88: parsed.port <- uix_window.py:40: check(url)
FAIL: test_ports (test_uix_window.Ports.test_ports)
Traceback (most recent call last):
  File "/work/uix_window.py", line 88, in check_uix_url
AssertionError: 'Port out of range 0-65535' != 'uix_url_not_allowed'"""
# the same cause from a different candidate: other line numbers, other path, other address
FEEDBACK_2 = """REPRO test_ports (test_uix_window.Ports.test_ports): AssertionError: 'Port out of range 0-65535' != 'uix_url_not_allowed'
REPRO   input 'http://127.0.0.1:65535/': expected the URL back, got ValueError: Port out of range 0-65535 at C:\\p\\uix_window.py:131: parsed.port
FAIL: test_ports (test_uix_window.Ports.test_ports)
Traceback (most recent call last):
  File "C:\\p\\uix_window.py", line 131, in check_uix_url
AssertionError: 'Port out of range 0-65535' != 'uix_url_not_allowed'"""
FEEDBACK_OTHER = """REPRO test_dollar (test_uix_window.Url.test_dollar): AssertionError: 'ok' != 'uix_url_not_allowed'
REPRO   input 'http://127.0.0.1:8080/\\n': expected uix_url_not_allowed, got no exception
FAIL: test_dollar (test_uix_window.Url.test_dollar)"""


def fails(watch, *signatures, hint=None):
    for s in signatures:
        watch.record(s, hint)
    return watch


class Signature(unittest.TestCase):
    def test_same_cause_in_another_candidate_has_the_same_signature(self):
        self.assertEqual(failure_signature("test", FEEDBACK_1), failure_signature("test", FEEDBACK_2))

    def test_another_failure_has_another_signature(self):
        self.assertNotEqual(failure_signature("test", FEEDBACK_1), failure_signature("test", FEEDBACK_OTHER))

    def test_another_input_is_another_failure(self):
        other = FEEDBACK_1.replace("65535/", "80/")
        self.assertNotEqual(failure_signature("test", FEEDBACK_1), failure_signature("test", other))

    def test_line_order_and_duplicates_do_not_matter(self):
        lines = FEEDBACK_1.splitlines()
        self.assertEqual(failure_signature("test", FEEDBACK_1), failure_signature("test", "\n".join(reversed(lines + lines[:2]))))

    def test_without_repro_lines_failing_tests_and_exceptions_count(self):
        a = "FAIL: test_a (m.C.test_a)\nTraceback (most recent call last):\n  File \"x.py\", line 3, in f\nAssertionError: 1 != 2"
        b = "FAIL: test_a (m.C.test_a)\nTraceback (most recent call last):\n  File \"y.py\", line 9, in f\nAssertionError: 1 != 2"
        c = "FAIL: test_b (m.C.test_b)\nAssertionError: 1 != 2"
        self.assertEqual(failure_signature("test", a), failure_signature("test", b))
        self.assertNotEqual(failure_signature("test", a), failure_signature("test", c))

    def test_kinds_are_prefixed_and_never_equal(self):
        s = {failure_signature("test", "x"), failure_signature("gen", "x"), failure_signature("review")}
        self.assertEqual(len(s), 3)
        self.assertTrue(failure_signature("gen", "model_answer_truncated").startswith("gen:"))
        self.assertEqual(failure_signature("gen", " Model_Answer_Truncated "), failure_signature("gen", "model_answer_truncated"))

    def test_a_detail_after_the_error_class_is_ignored(self):
        self.assertEqual(failure_signature("gen", "model_output_schema_invalid: answered {'a': 1} instead"),
                         failure_signature("gen", "model_output_schema_invalid: answered something else"))
        self.assertNotEqual(failure_signature("gen", "model_answer_empty"), failure_signature("gen", "model_answer_truncated"))

    def test_hint_key(self):
        self.assertIsNone(hint_key(None))
        self.assertIsNone(hint_key("  "))
        self.assertEqual(hint_key("look at the port check"), hint_key(" look at the port check "))
        self.assertNotEqual(hint_key("a"), hint_key("b"))


class Repeat(unittest.TestCase):
    A = failure_signature("test", FEEDBACK_1)

    def test_a_fresh_watch_allows_everything(self):
        out = ReworkWatch().check()
        self.assertFalse(out["stuck"])
        self.assertIsNone(out["repeated_failure"])

    def test_after_two_identical_failures_the_third_generation_is_stalled(self):
        w = fails(ReworkWatch(), self.A, self.A)
        out = w.check()
        self.assertEqual((out["stuck"], out["detector"], out["count"]), (True, "generic_repeat", 3))
        self.assertEqual(out["repeated_failure"], self.A)
        self.assertIn("stalled", out["message"])

    def test_one_failure_and_a_second_attempt_are_allowed(self):
        self.assertFalse(fails(ReworkWatch(), self.A).check()["stuck"])
        self.assertFalse(fails(ReworkWatch(), self.A, failure_signature("test", FEEDBACK_OTHER)).check()["stuck"])

    def test_progress_resets_the_streak(self):
        other = failure_signature("test", FEEDBACK_OTHER)
        self.assertFalse(fails(ReworkWatch(), self.A, self.A, other).check()["stuck"])
        self.assertFalse(fails(ReworkWatch(), self.A, self.A, other, self.A).check()["stuck"])

    def test_repeated_truncation_is_stalled_too(self):
        t = failure_signature("gen", "model_answer_truncated")
        self.assertTrue(fails(ReworkWatch(), t, t).check()["stuck"])

    def test_a_new_hint_allows_the_next_generation(self):
        w = fails(ReworkWatch(), self.A, self.A)
        self.assertTrue(w.check()["stuck"])
        self.assertTrue(w.check(hint=None)["stuck"])
        self.assertFalse(w.check(hint="the port is parsed before the range check")["stuck"])

    def test_after_a_hint_the_streak_counts_anew(self):
        h = "the port is parsed before the range check"
        w = fails(ReworkWatch(), self.A, self.A)
        fails(w, self.A, self.A, hint=h)           # both attempts with the hint ended in A again
        self.assertTrue(w.check(hint=h)["stuck"])
        self.assertFalse(w.check(hint="another hint")["stuck"])

    def test_check_does_not_change_the_history(self):
        w = fails(ReworkWatch(), self.A, self.A)
        w.check()
        w.check()
        self.assertEqual(len(w.entries), 2)


class PingPong(unittest.TestCase):
    A = failure_signature("test", FEEDBACK_1)
    B = failure_signature("test", FEEDBACK_OTHER)

    def test_alternating_failures_are_stalled_after_four(self):
        out = fails(ReworkWatch(), self.A, self.B, self.A, self.B).check()
        self.assertEqual((out["stuck"], out["detector"], out["count"]), (True, "ping_pong", 4))
        self.assertEqual(out["repeated_failure"], self.B)

    def test_three_alternating_failures_are_still_allowed(self):
        self.assertFalse(fails(ReworkWatch(), self.A, self.B, self.A).check()["stuck"])

    def test_a_third_failure_breaks_the_pattern(self):
        c = failure_signature("gen", "model_answer_empty")
        self.assertFalse(fails(ReworkWatch(), self.A, self.B, c, self.B).check()["stuck"])

    def test_a_hint_allows_the_next_generation(self):
        w = fails(ReworkWatch(), self.A, self.B, self.A, self.B)
        self.assertTrue(w.check()["stuck"])
        self.assertFalse(w.check(hint="the two fixes undo each other")["stuck"])


class Persistence(unittest.TestCase):
    def test_round_trip_through_the_state(self):
        a = failure_signature("test", FEEDBACK_1)
        state = {}
        w = fails(ReworkWatch(), a, a)
        w.save(state)
        again = ReworkWatch.load(state)
        self.assertEqual(again.entries, w.entries)
        self.assertEqual(again.check(), w.check())
        self.assertTrue(again.check()["stuck"])

    def test_loading_a_state_without_history(self):
        self.assertEqual(ReworkWatch.load({}).entries, [])
        self.assertEqual(ReworkWatch.load({}).last_outcome, START)

    def test_the_history_is_capped(self):
        w = ReworkWatch()
        for i in range(MAX_ENTRIES + 10):
            w.record(f"gen:{i}")
        self.assertEqual(len(w.entries), MAX_ENTRIES)
        self.assertEqual(w.entries[-1]["outcome"], f"gen:{MAX_ENTRIES + 9}")

    def test_custom_thresholds(self):
        a = failure_signature("test", FEEDBACK_1)
        self.assertTrue(fails(ReworkWatch(repeat_threshold=2), a).check()["stuck"])
        self.assertFalse(fails(ReworkWatch(repeat_threshold=4), a, a).check()["stuck"])


def _harness():
    spec = importlib.util.spec_from_file_location("e1_golden_path_under_test", Path(__file__).resolve().parents[1] / "benchmarks" / "e1_golden_path.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Audit:
    def __init__(self):
        self.events = []

    def append(self, event_type, **kw):
        self.events.append((event_type, kw))


class _Runtime:
    """Only what the stalled path and the watch stages touch; anything else (a model, a project) would raise AttributeError."""

    def __init__(self):
        self.audit = _Audit()


class HarnessGate(unittest.TestCase):
    def setUp(self):
        self.harness = _harness()
        self.rt = _Runtime()
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def stalled_state(self):
        state = {"job_id": "SDJ-X"}
        t = failure_signature("gen", "model_answer_truncated")
        fails(ReworkWatch(), t, t).save(state)
        return state

    def test_generate_stops_before_loading_anything_when_the_watch_says_stuck(self):
        out = self.harness.generate_stage(self.rt, self.project, self.stalled_state())
        self.assertEqual((out["status"], out["detector"], out["count"]), ("rework_stalled", "generic_repeat", 3))
        self.assertIn("captain_hint", " ".join(out["options"]))
        event, kw = self.rt.audit.events[0]
        self.assertEqual(event, "REWORK_STALLED")
        self.assertEqual(kw["payload"]["job_id"], "SDJ-X")

    def test_a_captain_hint_gets_past_the_gate(self):
        state = self.stalled_state()
        state["captain_hint"] = "the model never finishes; shorten the objective"
        with self.assertRaises((AttributeError, KeyError)):           # past the gate it needs a project and a model: not here
            self.harness.generate_stage(self.rt, self.project, state)
        self.assertEqual(self.rt.audit.events, [])

    def test_watch_stage_shows_the_verdict_and_reset_forgets_it(self):
        state = self.stalled_state()
        self.harness.SC = dict(self.harness.SC, name="demo")
        shown = self.harness.watch_stage(self.rt, self.project, state)
        self.assertEqual(len(shown["entries"]), 2)
        self.assertTrue(shown["next_generation"]["stuck"])
        out = self.harness.watch_reset_stage(self.rt, self.project, state)
        self.assertEqual(out, {"status": "watch_reset", "forgotten": 2})
        self.assertNotIn("rework_watch", state)
        self.assertEqual(len(state["rework_watch_resets"][0]["entries"]), 2)
        self.assertEqual(self.rt.audit.events[-1][0], "REWORK_WATCH_RESET")
        self.assertFalse(self.harness.watch_stage(self.rt, self.project, state)["next_generation"]["stuck"])


CAND = [{"path": "ui.py", "content": "def check(url):\n    return url\n"}]


class CandidateKey(unittest.TestCase):
    def test_line_endings_and_whitespace_runs_do_not_matter(self):
        crlf = [{"path": "ui.py", "content": "def check(url):\r\n    return   url\r\n\r\n"}]
        self.assertEqual(candidate_key(CAND), candidate_key(crlf))

    def test_one_character_is_another_candidate(self):
        other = [{"path": "ui.py", "content": "def check(url):\n    return url.\n"}]
        self.assertNotEqual(candidate_key(CAND), candidate_key(other))

    def test_comments_count(self):
        commented = [{"path": "ui.py", "content": "def check(url):  # fixed\n    return url\n"}]
        self.assertNotEqual(candidate_key(CAND), candidate_key(commented))

    def test_the_path_counts_and_file_order_does_not(self):
        renamed = [{"path": "ui2.py", "content": CAND[0]["content"]}]
        self.assertNotEqual(candidate_key(CAND), candidate_key(renamed))
        two = [{"path": "a.py", "content": "x"}, {"path": "b.py", "content": "y"}]
        self.assertEqual(candidate_key(two), candidate_key(list(reversed(two))))

    def test_nothing_has_a_stable_key(self):
        self.assertEqual(candidate_key(None), candidate_key([]))
        self.assertEqual(len(candidate_key(CAND)), 16)


class SameAsEarlier(unittest.TestCase):
    def test_no_candidate_or_no_history(self):
        self.assertIsNone(same_as_earlier(None, {}))
        self.assertIsNone(same_as_earlier(CAND, {}))

    def test_the_previous_attempt_is_named_first(self):
        state = {"previous_candidate": CAND, "discarded_generations": [{"candidate": CAND}]}
        self.assertEqual(same_as_earlier(CAND, state), "the previous attempt")

    def test_an_older_attempt_is_named_by_its_number(self):
        other = [{"path": "ui.py", "content": "different"}]
        state = {"previous_candidate": other, "discarded_generations": [{"reason": "x"}, {"candidate": other}, {"candidate": CAND}]}
        self.assertEqual(same_as_earlier(CAND, state), "attempt 3")

    def test_a_different_candidate_is_not_a_repeat(self):
        other = [{"path": "ui.py", "content": "different"}]
        self.assertIsNone(same_as_earlier(other, {"previous_candidate": CAND, "discarded_generations": [{"candidate": CAND}]}))


class HarnessCandidateGate(unittest.TestCase):
    def setUp(self):
        self.harness = _harness()

    def state(self, **extra):
        return {"job_id": "SDJ-X", "mission_id": "M-1", "coder": {"model": "m"}, "generation": "completed", "candidate": CAND,
                "mission_phase": "CANDIDATE_REVIEW", "candidate_id": "CAND-1", "previous_candidate": CAND, **extra}

    def test_an_identical_candidate_is_refused_recorded_and_discarded(self):
        state, watch = self.state(), ReworkWatch()
        out = self.harness.refuse_repeated_candidate(state, watch)
        self.assertEqual((out["status"], out["out"]["status"]), ("generation_failed", "refused"))
        self.assertIn("candidate_unchanged", out["out"]["error"])
        self.assertIn("no test was run", out["out"]["error"])
        for key in ("mission_id", "candidate", "candidate_id", "mission_phase", "coder", "generation"):
            self.assertNotIn(key, state)                                   # generate can run again
        self.assertEqual(state["discarded_generations"][-1]["generation"], "refused")
        self.assertIn("same as the previous attempt", state["discarded_generations"][-1]["reason"])
        self.assertEqual(ReworkWatch.load(state).entries[-1]["outcome"], failure_signature("gen", "candidate_unchanged"))

    def test_two_identical_candidates_in_a_row_stall_the_next_generation(self):
        state, watch = self.state(), ReworkWatch()
        self.harness.refuse_repeated_candidate(state, watch)
        state.update(candidate=CAND, mission_id="M-2")
        self.harness.refuse_repeated_candidate(state, watch)
        self.assertTrue(ReworkWatch.load(state).check()["stuck"])

    def test_a_different_candidate_passes_and_leaves_the_state_alone(self):
        state = self.state(candidate=[{"path": "ui.py", "content": "def check(url):\n    return None\n"}])
        before = dict(state)
        self.assertIsNone(self.harness.refuse_repeated_candidate(state, ReworkWatch()))
        self.assertEqual(state, before)

    def test_discard_generation_clears_the_mission_so_generate_is_not_answered_exists(self):
        state = {"mission_id": "M-9", "generation": "refused", "candidate": None, "coder": {"m": 1}}
        self.harness.discard_generation(state, "unusable model answer: model_answer_truncated")
        self.assertNotIn("mission_id", state)
        self.assertEqual(state["discarded_generations"][0]["mission_id"], "M-9")


if __name__ == "__main__":
    unittest.main()
