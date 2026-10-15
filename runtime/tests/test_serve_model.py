import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

from serve_model import summarize  # noqa: E402

LOG = ("0.17.792.385 I slot print_timing: id  0 | task 0 | prompt eval time =    8000.00 ms /  1600 tokens (    5.00 ms per token,   200.00 tokens per second)\n"
       "0.17.792.389 I slot print_timing: id  0 | task 0 |        eval time =    2000.00 ms /    90 tokens (   22.22 ms per token,    45.00 tokens per second)\n"
       "0.17.792.390 I slot print_timing: id  0 | task 0 |       total time =   10000.00 ms /  1690 tokens\n"
       "0.20.000.000 I slot print_timing: id  0 | task 1 | prompt processing, n_tokens =    677, progress = 0.40, t =   3.13 s / 216.46 tokens per second\n"
       "0.21.792.385 I slot print_timing: id  0 | task 1 | prompt eval time =    2000.00 ms /   400 tokens (    5.00 ms per token,   200.00 tokens per second)\n"
       "0.21.792.389 I slot print_timing: id  0 | task 1 |        eval time =    2000.00 ms /   110 tokens (   18.18 ms per token,    55.00 tokens per second)\n"
       "0.21.792.390 I slot print_timing: id  0 | task 1 |       total time =    4000.00 ms /   510 tokens\n")


class ServeStatsTest(unittest.TestCase):
    def test_the_summary_adds_up_the_requests_of_a_session(self):
        self.assertEqual(summarize(LOG), {"requests": 2, "prompt_tokens": 2000, "prompt_tps": 200.0, "generated_tokens": 200, "gen_tps": 50.0, "busy_seconds": 14.0})

    def test_an_empty_or_foreign_log_gives_zeros_and_no_speeds(self):
        self.assertEqual(summarize(""), {"requests": 0, "prompt_tokens": 0, "prompt_tps": None, "generated_tokens": 0, "gen_tps": None, "busy_seconds": 0.0})
        self.assertEqual(summarize("load_tensors: done\nsomething else\n")["requests"], 0)


if __name__ == "__main__":
    unittest.main()
