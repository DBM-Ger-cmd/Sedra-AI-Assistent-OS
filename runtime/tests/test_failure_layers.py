import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

from failure_layers import classify, report, tally  # noqa: E402

LOG = """\
10:00:00    agent planner                qwen3.6-35b-a3b        hand_in      3 calls   20.0 s 400 tokens, 3000 prompt, peak 2000
10:05:00    agent solo developer (step 1/2) qwen3.6-35b-a3b        hand_in     10 calls  100.0 s 3000 tokens, 9000 prompt, peak 5000
10:09:00    agent solo developer (step 2/2) qwen3.6-35b-a3b        turns       45 calls  300.0 s 9000 tokens, 90000 prompt, peak 20000
10:09:01    stage a: hidden PASSED (own check accepted=UNJUDGED, own tests none, 400.0 s)
10:15:00    agent solo developer         qwen3.6-35b-a3b        error       23 calls  500.0 s 19000 tokens, 500000 prompt  error: HTTPError: HTTP Error 400: Bad Request
10:20:00    agent solo developer (rework 1) qwen3.6-35b-a3b        answer_cut  18 calls  500.0 s 30000 tokens, 300000 prompt
10:25:00    agent solo developer (rework 2) qwen3.6-35b-a3b        hand_in     35 calls  200.0 s 8000 tokens, 700000 prompt
10:25:01    stage b: hidden FAILED (own check accepted=UNJUDGED, own tests none, 1200.0 s)
10:30:00    agent solo developer         qwen3.6-35b-a3b        error        3 calls    5.0 s 0 tokens, 0 prompt  error: HTTPError: HTTP Error 500: boom
10:35:00    agent solo developer (rework 1) qwen3.6-35b-a3b        hand_in     12 calls   60.0 s 2000 tokens, 8000 prompt
10:35:01    stage c: hidden PASSED (own check accepted=UNJUDGED, own tests none, 70.0 s)
"""


class LayerTests(unittest.TestCase):
    def test_every_end_goes_to_its_layer(self):
        self.assertEqual(classify("error", None, "HTTP Error 400"), "connection")
        self.assertEqual(classify("error", None, "HTTP Error 500"), "server")
        self.assertEqual([classify(e) for e in ("answer_cut", "runaway", "loop", "turns", "time", "no_tool_call")], ["behaviour", "behaviour", "behaviour", "budget", "budget", "connection"])
        self.assertEqual((classify("hand_in", True), classify("hand_in", False)), ("ok", "understanding"))

    def test_a_protocol_is_tallied_per_layer(self):
        table = tally(LOG.splitlines())
        self.assertEqual({k: v[0] for k, v in table.items()}, {"ok": 2, "budget": 1, "connection": 1, "behaviour": 1, "understanding": 1, "server": 1})
        self.assertEqual(table["behaviour"], [1, 500.0, 30000])
        text = report([])
        self.assertIn("1 Server/Modell", text)


if __name__ == "__main__":
    unittest.main()
