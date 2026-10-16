import unittest

from loop_guard import GUARDED_TOOLS, HISTORY_SIZE, LoopGuard, outcome_hash, signature

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


if __name__ == "__main__":
    unittest.main()
