import unittest

from guppi_runtime.loop_guard import GUARDED_TOOLS, HISTORY_SIZE, LoopGuard, normalize_output, outcome_hash, signature

OK = {"stuck": False, "detector": None, "count": 0, "message": ""}


def guard(**kw):
    kw.setdefault("guarded", frozenset({"A", "B", "C"}))
    return LoopGuard(**kw)


def feed(g, calls):
    """calls: list of (tool, arg_value, output)"""
    for tool, val, out in calls:
        g.record(tool, {"v": val}, out)


class Hashing(unittest.TestCase):
    def test_signature_shape(self):
        s = signature("read_file", {"path": "a"})
        name, h = s.split(":")
        self.assertEqual(name, "read_file")
        self.assertEqual(len(h), 16)
        int(h, 16)

    def test_key_order_does_not_matter(self):
        self.assertEqual(signature("t", {"a": 1, "b": 2}), signature("t", {"b": 2, "a": 1}))

    def test_values_and_tools_matter(self):
        self.assertNotEqual(signature("t", {"a": 1}), signature("t", {"a": 2}))
        self.assertNotEqual(signature("t", {"a": 1}), signature("u", {"a": 1}))

    def test_nested_and_unicode_args(self):
        self.assertEqual(signature("t", {"x": {"b": [1, 2], "a": "ä"}}), signature("t", {"x": {"a": "ä", "b": [1, 2]}}))

    def test_unserializable_values_do_not_raise(self):
        signature("t", {"p": object})

    def test_outcome_hash(self):
        h = outcome_hash("x", False)
        self.assertEqual(len(h), 16)
        int(h, 16)
        self.assertNotEqual(outcome_hash("x", False), outcome_hash("x", True))
        self.assertNotEqual(outcome_hash("x", False), outcome_hash("y", False))

    def test_outcome_ignores_the_tail_after_the_limit(self):
        self.assertEqual(outcome_hash("a" * 2000 + "1", False), outcome_hash("a" * 2000 + "2", False))
        self.assertNotEqual(outcome_hash("a" * 1999 + "1", False), outcome_hash("a" * 1999 + "2", False))

    def test_non_string_output_is_accepted(self):
        self.assertEqual(outcome_hash(5, False), outcome_hash("5", False))


class GenericRepeat(unittest.TestCase):
    def test_empty_history_is_fine(self):
        self.assertEqual(guard().check("A", {"v": 1}), OK)

    def test_third_identical_call_is_still_allowed(self):
        g = guard()
        feed(g, [("A", 1, "same")] * 2)
        self.assertEqual(g.check("A", {"v": 1}), OK)

    def test_fourth_identical_call_is_stuck(self):
        g = guard()
        feed(g, [("A", 1, "same")] * 3)
        out = g.check("A", {"v": 1})
        self.assertEqual((out["stuck"], out["detector"], out["count"]), (True, "generic_repeat", 4))
        self.assertIn("A", out["message"])
        self.assertIn("4", out["message"])

    def test_check_does_not_change_anything(self):
        g = guard()
        feed(g, [("A", 1, "same")] * 3)
        g.check("A", {"v": 1})
        g.check("A", {"v": 1})
        self.assertEqual(g.recorded_count, 3)
        self.assertTrue(g.check("A", {"v": 1})["stuck"])

    def test_different_arguments_are_not_a_repeat(self):
        g = guard()
        feed(g, [("A", 1, "same"), ("A", 2, "same"), ("A", 3, "same")])
        self.assertEqual(g.check("A", {"v": 4}), OK)

    def test_a_changing_result_is_progress(self):
        g = guard()
        feed(g, [("A", 1, "r1"), ("A", 1, "r2"), ("A", 1, "r3")])
        self.assertEqual(g.check("A", {"v": 1}), OK)

    def test_only_the_newest_equal_results_count(self):
        g = guard()
        feed(g, [("A", 1, "old")] * 5 + [("A", 1, "new")] * 2)
        self.assertEqual(g.check("A", {"v": 1}), OK)           # streak is 2, the 5 old ones differ
        g.record("A", {"v": 1}, "new")
        self.assertEqual(g.check("A", {"v": 1})["count"], 4)   # streak 3 + 1

    def test_other_calls_in_between_are_skipped(self):
        g = guard()
        feed(g, [("A", 1, "s"), ("B", 9, "x"), ("A", 1, "s"), ("C", 8, "y"), ("A", 1, "s")])
        out = g.check("A", {"v": 1})
        self.assertEqual((out["stuck"], out["detector"], out["count"]), (True, "generic_repeat", 4))

    def test_errors_count_as_a_different_outcome_than_success(self):
        g = guard()
        g.record("A", {"v": 1}, "same", True)
        g.record("A", {"v": 1}, "same", False)
        g.record("A", {"v": 1}, "same", True)
        self.assertEqual(g.check("A", {"v": 1}), OK)

    def test_repeated_errors_are_stuck_too(self):
        g = guard()
        for _ in range(3):
            g.record("A", {"v": 1}, "boom", True)
        self.assertTrue(g.check("A", {"v": 1})["stuck"])

    def test_custom_threshold(self):
        g = guard(repeat_threshold=2)
        feed(g, [("A", 1, "s")])
        out = g.check("A", {"v": 1})
        self.assertEqual((out["stuck"], out["count"]), (True, 2))


class PingPong(unittest.TestCase):
    def test_alternating_without_progress_is_stuck(self):
        g = guard()
        feed(g, [("A", 1, "a"), ("B", 2, "b"), ("A", 1, "a"), ("B", 2, "b"), ("A", 1, "a")])
        out = g.check("B", {"v": 2})
        self.assertEqual((out["stuck"], out["detector"], out["count"]), (True, "ping_pong", 6))
        self.assertIn("6", out["message"])

    def test_one_step_earlier_is_still_allowed(self):
        g = guard()
        feed(g, [("B", 2, "b"), ("A", 1, "a"), ("B", 2, "b"), ("A", 1, "a")])
        self.assertEqual(g.check("B", {"v": 2}), OK)

    def test_the_next_call_must_continue_the_pattern(self):
        g = guard(repeat_threshold=99, ping_pong_threshold=3)
        feed(g, [("A", 1, "a"), ("B", 2, "b"), ("A", 1, "a")])
        self.assertEqual(g.check("A", {"v": 1}), OK)           # A after A is not an alternation
        self.assertEqual(g.check("C", {"v": 3}), OK)
        self.assertEqual(g.check("B", {"v": 2})["detector"], "ping_pong")

    def test_progress_in_one_side_breaks_it(self):
        g = guard()
        feed(g, [("A", 1, "a1"), ("B", 2, "b"), ("A", 1, "a2"), ("B", 2, "b"), ("A", 1, "a3")])
        self.assertEqual(g.check("B", {"v": 2}), OK)

    def test_a_third_call_in_the_pattern_breaks_it(self):
        g = guard()
        feed(g, [("A", 1, "a"), ("B", 2, "b"), ("A", 1, "a"), ("C", 3, "c"), ("A", 1, "a")])
        self.assertEqual(g.check("B", {"v": 2}), OK)

    def test_alternation_counts_only_the_newest_alternating_tail(self):
        g = guard()
        feed(g, [("C", 3, "c"), ("C", 4, "c"), ("A", 1, "a"), ("B", 2, "b"), ("A", 1, "a"), ("B", 2, "b"), ("A", 1, "a")])
        self.assertEqual(g.check("B", {"v": 2})["count"], 6)

    def test_custom_threshold(self):
        g = guard(ping_pong_threshold=4)
        feed(g, [("A", 1, "a"), ("B", 2, "b"), ("A", 1, "a")])
        out = g.check("B", {"v": 2})
        self.assertEqual((out["stuck"], out["detector"], out["count"]), (True, "ping_pong", 4))

    def test_generic_repeat_wins_when_both_apply(self):
        g = guard()
        feed(g, [("A", 1, "a"), ("B", 2, "b")] * 3)
        out = g.check("A", {"v": 1})
        self.assertEqual((out["detector"], out["count"]), ("generic_repeat", 4))


class Window(unittest.TestCase):
    def test_default_size(self):
        self.assertEqual(HISTORY_SIZE, 24)

    def test_the_window_is_capped(self):
        g = guard()
        feed(g, [("A", i, "x") for i in range(30)])
        self.assertEqual(g.recorded_count, 24)

    def test_old_entries_fall_out_of_the_window(self):
        g = guard(history_size=5)
        feed(g, [("A", 1, "s")] * 3)
        feed(g, [("B", i, "x") for i in range(5)])
        self.assertEqual(g.check("A", {"v": 1}), OK)

    def test_reset(self):
        g = guard()
        feed(g, [("A", 1, "s")] * 3)
        g.reset()
        self.assertEqual((g.recorded_count, g.check("A", {"v": 1})), (0, OK))


class Guarded(unittest.TestCase):
    def test_unguarded_tools_are_never_stuck(self):
        g = guard()
        feed(g, [("Z", 1, "s")] * 10)
        self.assertEqual(g.check("Z", {"v": 1}), OK)

    def test_unguarded_tools_are_still_remembered(self):
        g = guard()
        feed(g, [("Z", 1, "s")] * 3)
        self.assertEqual(g.recorded_count, 3)

    def test_unguarded_tools_do_not_form_the_other_side_of_a_ping_pong(self):
        g = guard()
        feed(g, [("A", 1, "a"), ("Z", 2, "z"), ("A", 1, "a"), ("Z", 2, "z"), ("A", 1, "a")])
        self.assertEqual(g.check("Z", {"v": 2}), OK)

    def test_tool_names_may_contain_a_colon(self):
        g = LoopGuard(guarded=frozenset({"mcp:read", "B"}))
        for tool, val, out in [("mcp:read", 1, "a"), ("B", 2, "b"), ("mcp:read", 1, "a"), ("B", 2, "b"), ("mcp:read", 1, "a")]:
            g.record(tool, {"v": val}, out)
        out = g.check("B", {"v": 2})
        self.assertEqual((out["stuck"], out["detector"], out["count"]), (True, "ping_pong", 6))
        g = LoopGuard(guarded=frozenset({"mcp:read", "B"}))      # mirrored: the colon tool is the one that comes next
        for tool, val, out in [("B", 2, "b"), ("mcp:read", 1, "a"), ("B", 2, "b"), ("mcp:read", 1, "a"), ("B", 2, "b")]:
            g.record(tool, {"v": val}, out)
        out = g.check("mcp:read", {"v": 1})
        self.assertEqual((out["stuck"], out["detector"], out["count"]), (True, "ping_pong", 6))
        h = LoopGuard(guarded=frozenset({"mcp:read"}))
        for _ in range(3):
            h.record("mcp:read", {"v": 1}, "same")
        self.assertTrue(h.check("mcp:read", {"v": 1})["stuck"])
        h.record("mcp:write", {"v": 1}, "x")      # a different, unguarded tool whose name starts like the guarded one
        self.assertEqual(h.check("mcp:write", {"v": 1}), OK)

    def test_default_guarded_tools(self):
        self.assertIn("read_file", GUARDED_TOOLS)
        g = LoopGuard()
        for _ in range(3):
            g.record("read_file", {"path": "x"}, "same")
        self.assertTrue(g.check("read_file", {"path": "x"})["stuck"])
        self.assertEqual(LoopGuard().check("write_file", {}), OK)


class Normalisation(unittest.TestCase):
    """StarNet lesson (2026-10-04): host-generated volatility must not hide a repeated result."""

    def test_each_volatile_pattern_is_replaced(self):
        cases = [
            ("done at 2026-10-04T10:58:58.242359+00:00", "done at <time>"),
            ("done at 2026-10-04 10:58:58Z", "done at <time>"),
            ("id 123e4567-e89b-12d3-a456-426614174000 ok", "id <uuid> ok"),
            ("job SDJ-0129D3B24C54 and SBX-aad1a3426b264a21bfacc9c64a846fe8", "job SDJ-<id> and SBX-<id>"),
            ("gate HG-0CC22A18 mission M-BE2CAA0A cand CAND-2FE3E1B54730", "gate HG-<id> mission M-<id> cand CAND-<id>"),
            ("event EVT-006274", "event EVT-<id>"),
            ("at 0x7ffd1234abcd", "at 0x<hex>"),
            ("sha de8d3e0c2afa1442e96ee7c21150e46a", "sha <hex>"),
            ("took 1.2s then 350ms then 3 min then 12 seconds", "took <duration> then <duration> then <duration> then <duration>"),
            ("process pid 4711 and PID=99", "process pid <n> and pid <n>"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(normalize_output(text), expected)

    def test_ordinary_text_and_numbers_are_left_alone(self):
        for text in ("Port out of range 0-65535", "3 tests failed", "10 sources found", "line 88 of file", "aaaaaaaaaaaaaaaaaaaa1", "M-x and SDJ-12"):
            with self.subTest(text=text):
                self.assertEqual(normalize_output(text), text)

    def test_whitespace_runs_collapse(self):
        self.assertEqual(normalize_output("  a \n\t b   c  "), "a b c")

    def test_the_same_result_with_other_volatility_is_one_outcome(self):
        a = "FAIL job SDJ-0129D3B24C54 after 3.2s at 2026-10-04T10:00:00Z"
        b = "FAIL job SDJ-55E88D2A054C after 41ms at 2026-10-04T12:30:15Z"
        self.assertEqual(outcome_hash(a, True), outcome_hash(b, True))
        self.assertNotEqual(outcome_hash(a, True), outcome_hash(a, False))
        self.assertNotEqual(outcome_hash(a, True), outcome_hash("PASS job SDJ-0129D3B24C54 after 3.2s", True))

    def test_a_repeat_behind_a_timestamp_is_still_stuck(self):
        g = guard()
        for n in range(3):
            g.record("A", {"v": 1}, f"same result at 2026-10-04T10:00:0{n}Z after {n}.5s")
        self.assertTrue(g.check("A", {"v": 1})["stuck"])

    def test_normalisation_happens_before_the_cut(self):
        long_prefix = "x" * 1985
        a = long_prefix + " 2026-10-04T10:00:00Z tail-one"
        b = long_prefix + " 2026-10-05T11:11:11Z tail-one"
        self.assertEqual(outcome_hash(a, False), outcome_hash(b, False))

    def test_a_guard_can_skip_normalisation(self):
        g = LoopGuard(guarded=frozenset({"A"}), normalize=False)
        for n in range(3):
            g.record("A", {"v": 1}, f"deadbeef0123456{n}")
        self.assertFalse(g.check("A", {"v": 1})["stuck"])             # three different digests: three different outcomes
        h = LoopGuard(guarded=frozenset({"A"}))
        for n in range(3):
            h.record("A", {"v": 1}, f"deadbeef0123456{n}")
        self.assertTrue(h.check("A", {"v": 1})["stuck"])              # normalised: the digest is volatile, so the repeat shows


class WarnLevel(unittest.TestCase):
    def test_ok_warn_stuck_in_order(self):
        g = guard()
        levels = []
        for _ in range(4):
            levels.append(g.level("A", {"v": 1})["level"])
            g.record("A", {"v": 1}, "same")
        self.assertEqual(levels, ["ok", "ok", "warn", "stuck"])

    def test_warn_carries_the_check_fields_and_a_warning_text(self):
        g = guard()
        for _ in range(2):
            g.record("A", {"v": 1}, "same")
        out = g.level("A", {"v": 1})
        self.assertEqual((out["level"], out["stuck"], out["detector"], out["count"]), ("warn", True, "generic_repeat", 3))
        self.assertTrue(out["message"].startswith("warning:"))
        self.assertEqual(g.check("A", {"v": 1})["stuck"], False)      # check itself is unchanged: not yet stuck

    def test_stuck_is_reported_as_stuck_and_unchanged(self):
        g = guard()
        feed(g, [("A", 1, "same")] * 3)
        out = g.level("A", {"v": 1})
        self.assertEqual((out["level"], out["stuck"], out["detector"], out["count"]), ("stuck", True, "generic_repeat", 4))
        self.assertNotIn("warning", out["message"])

    def test_ping_pong_warns_one_step_early(self):
        g = guard(repeat_threshold=99)
        feed(g, [("A", 1, "a"), ("B", 2, "b"), ("A", 1, "a"), ("B", 2, "b")])
        out = g.level("A", {"v": 1})
        self.assertEqual((out["level"], out["detector"]), ("warn", "ping_pong"))

    def test_progress_and_unguarded_tools_stay_ok(self):
        g = guard()
        feed(g, [("A", 1, "r1"), ("A", 1, "r2")])
        self.assertEqual(g.level("A", {"v": 1})["level"], "ok")
        feed(g, [("Z", 1, "s")] * 5)
        self.assertEqual(g.level("Z", {"v": 1})["level"], "ok")

    def test_a_warning_needs_an_earlier_occurrence(self):
        self.assertEqual(guard().level("A", {"v": 1})["level"], "ok")
        g = guard(repeat_threshold=2)
        self.assertEqual(g.level("A", {"v": 1})["level"], "ok")
        g.record("A", {"v": 1}, "same")
        self.assertEqual(g.level("A", {"v": 1})["level"], "stuck")      # threshold 2: no room for a warning step

    def test_level_does_not_change_the_history(self):
        g = guard()
        feed(g, [("A", 1, "same")] * 2)
        g.level("A", {"v": 1})
        self.assertEqual(g.recorded_count, 2)

    def test_a_wider_margin_warns_earlier(self):
        g = guard()
        g.record("A", {"v": 1}, "same")
        self.assertEqual(g.level("A", {"v": 1})["level"], "ok")
        self.assertEqual(g.level("A", {"v": 1}, warn_margin=2)["level"], "warn")


if __name__ == "__main__":
    unittest.main()
