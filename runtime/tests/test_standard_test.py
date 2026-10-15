"""Standardtest (models/standard_test.py): plan, stability, coder check and recommendation, with fake server and clock."""
import unittest

from guppi_runtime.models import standard_test as st

TIERS = [4096, 8192, 16384, 32768, 65536, 131072]


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 1.0
        return self.t


class StandardTestTests(unittest.TestCase):
    def test_plan_contexts_per_duration(self):
        self.assertEqual([t["context"] for t in st.plan("schnell", ["tokens"], TIERS, 65536)["trials"]], [65536])
        self.assertEqual([t["context"] for t in st.plan("standard", ["tokens"], TIERS, 65536)["trials"]], [16384, 32768, 65536])
        self.assertEqual(st.plan("langzeit", ["tokens"], TIERS, 65536)["seconds"], 5400)
        self.assertNotIn(131072, [t["context"] for t in st.plan("langzeit", ["tokens"], TIERS, 65536)["trials"]])

    def test_plan_rejects_unknown_input(self):
        with self.assertRaises(ValueError):
            st.plan("schnell", [], TIERS, 65536)
        with self.assertRaises(ValueError):
            st.plan("kurz", ["tokens"], TIERS, 65536)

    def test_coder_answer_is_parsed_not_run(self):
        self.assertTrue(st._code_ok("```python\ndef fib(n):\n    return n\n```", "fib"))
        self.assertFalse(st._code_ok("```python\ndef fib(n:\n```", "fib"))
        self.assertFalse(st._code_ok("```python\ndef other(n):\n    return n\n```", "fib"))

    def test_errors_mark_context_unstable(self):
        def bad(path, body):
            raise RuntimeError("boom")
        r = st.measure(bad, 100, ["stabilitaet"], clock=Clock())
        self.assertFalse(r["stable"])
        self.assertGreater(r["errors"], st.MAX_ERRORS)

    def test_measure_collects_speed_and_coder(self):
        def post(path, body):
            if "Antworte nur mit Code" in body["prompt"]:
                return {"content": "```python\ndef fib(n):\n    return n\n```"}
            return {"timings": {"predicted_per_second": 20.0, "prompt_per_second": 500.0}}
        r = st.measure(post, 60, ["tokens", "lesen_schreiben", "coder"], clock=Clock())
        self.assertEqual(r["tokens_per_s"], 20.0)
        self.assertEqual(r["read_per_s"], 500.0)
        self.assertTrue(r["stable"])

    def test_recommendation_prefers_stable_and_most_criteria(self):
        results = [
            {"context": 16384, "status": "ok", "stable": True, "tokens_per_s": 30, "read_per_s": 400, "coder_pass": 0.66},
            {"context": 65536, "status": "ok", "stable": True, "tokens_per_s": 25, "read_per_s": 380, "coder_pass": 1.0},
            {"context": 32768, "status": "ok", "stable": False, "tokens_per_s": 40, "read_per_s": 500, "coder_pass": 1.0},
        ]
        rec = st.recommend(results, ["tokens", "lesen_schreiben", "coder"])
        self.assertNotEqual(rec["context"], 32768)           # unstable never wins
        self.assertEqual(rec["per_criterion"]["tokens"], 16384)
        self.assertEqual(rec["per_criterion"]["coder"], 65536)

    def test_run_skips_contexts_that_do_not_load(self):
        plan = st.plan("standard", ["tokens"], TIERS, 65536)
        def reload(ctx):
            return ctx != 32768
        def post(path, body):
            return {"timings": {"predicted_per_second": 10.0}}
        out = st.run(plan, post, reload, clock=Clock())
        statuses = {r["context"]: r["status"] for r in out["results"]}
        self.assertEqual(statuses[32768], "nicht_geladen")
        self.assertEqual(statuses[16384], "ok")


if __name__ == "__main__":
    unittest.main()
