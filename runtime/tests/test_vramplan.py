"""Spec 2, S2.C1: VRAM arithmetic of the model scheduler (limit 11.5 GB including the reserve of 0.7 GB). No GPU, no files."""
import ast
import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.jobs.vramplan import fits, max_slots, server_need  # noqa: E402


class ServerNeed(unittest.TestCase):
    def test_weights_once_kv_per_slot(self):
        self.assertEqual(server_need(9.0, 0.5, 1), {"vram_gb": 9.5, "ram_gb": 0.0})
        self.assertEqual(server_need(9.0, 0.5, 4, compute_gb=0.4, ram_gb=2.0), {"vram_gb": 11.4, "ram_gb": 2.0})

    def test_kv_zero(self):
        self.assertEqual(server_need(8, 0, 8)["vram_gb"], 8.0)

    def test_refusals(self):
        for slots in (0, 9, "2", None, True):
            with self.assertRaises(ValueError) as ctx:
                server_need(9.0, 0.5, slots)
            self.assertEqual(str(ctx.exception), "slots_invalid")
        for bad in (-1, "9", None, True):
            with self.assertRaises(ValueError) as ctx:
                server_need(bad, 0.5, 2)
            self.assertEqual(str(ctx.exception), "value_invalid")
        with self.assertRaises(ValueError):
            server_need(9.0, 0.5, 2, compute_gb=-0.1)


class Fits(unittest.TestCase):
    def test_fits(self):
        self.assertIsNone(fits(10.8, 11.5, 0.7, 12.0))
        self.assertIsNone(fits(5, 11.5, 0.7, 6.0))

    def test_limit_includes_reserve(self):
        out = fits(10.81, 11.5, 0.7, 12.0)
        self.assertEqual(out, {"need_gb": 10.81, "measured_free_gb": 12.0, "limit_gb": 11.5, "reserve_gb": 0.7, "reason": "limit"})

    def test_measured_free_minus_reserve(self):
        self.assertIsNone(fits(8.0, 11.5, 0.7, 8.7))
        out = fits(8.01, 11.5, 0.7, 8.7)
        self.assertEqual((out["reason"], out["need_gb"], out["measured_free_gb"]), ("frei", 8.01, 8.7))

    def test_limit_wins_when_both_fail(self):
        self.assertEqual(fits(11.0, 11.5, 0.7, 2.0)["reason"], "limit")

    def test_refusals(self):
        for args in ((-1, 11.5, 0.7, 5), (1, "11.5", 0.7, 5), (1, 11.5, None, 5), (1, 11.5, 0.7, True)):
            with self.assertRaises(ValueError) as ctx:
                fits(*args)
            self.assertEqual(str(ctx.exception), "value_invalid")


class MaxSlots(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(max_slots(9.0, 0.5, 0.0, 11.5, 0.7), 3)
        self.assertEqual(max_slots(9.0, 0.5, 0.0, 11.5, 0.7, cap=2), 2)
        self.assertEqual(max_slots(9.0, 0.7, 0.0, 11.5, 0.7), 2)
        self.assertEqual(max_slots(5.0, 0.0, 0.0, 11.5, 0.7), 8)

    def test_exact_edge(self):
        self.assertEqual(max_slots(9.0, 0.45, 0.0, 11.7, 0.7), 4)

    def test_zero_when_nothing_fits(self):
        self.assertEqual(max_slots(10.9, 0.5, 0.0, 11.5, 0.7), 0)
        self.assertEqual(max_slots(10.5, 0.5, 0.2, 11.5, 0.7), 0)

    def test_agrees_with_server_need(self):
        for kv in (0.3, 0.5, 0.7):
            n = max_slots(8.0, kv, 0.4, 11.5, 0.7)
            self.assertIsNone(fits(server_need(8.0, kv, n, 0.4)["vram_gb"], 11.5, 0.7, 12.0) if n else None)
            if 0 < n < 8:
                self.assertEqual(fits(server_need(8.0, kv, n + 1, 0.4)["vram_gb"], 11.5, 0.7, 12.0)["reason"], "limit")

    def test_refusals(self):
        with self.assertRaises(ValueError):
            max_slots(9, 0.5, 0, 11.5, 0.7, cap=9)
        with self.assertRaises(ValueError):
            max_slots(-9, 0.5, 0, 11.5)


class Boundary(unittest.TestCase):
    def test_pure_module(self):
        tree = ast.parse((RUNTIME / "src" / "guppi_runtime" / "jobs" / "vramplan.py").read_text(encoding="utf-8"))
        imported = {n.module if isinstance(n, ast.ImportFrom) else a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                    for a in (n.names if isinstance(n, ast.Import) else [None])}
        self.assertEqual(imported - {"__future__"}, set())


if __name__ == "__main__":
    unittest.main()
