"""Phase 0.1: append-only logs stay consistent under concurrent writers and need no full scan."""
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from guppi_runtime.core.audit import AuditLog
from guppi_runtime.selfdev.development_evidence import DevelopmentEvidenceStore
from guppi_runtime.core.util import read_last_jsonl, append_lock
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

SRC = str(Path(__file__).resolve().parents[1] / "src")

WORKER = """
import sys
sys.path.insert(0, sys.argv[1])
from guppi_runtime.core.audit import AuditLog
log = AuditLog(sys.argv[2])
for i in range(int(sys.argv[3])):
    log.append("PROC_EVENT", component="proc"+sys.argv[4], payload={"i": i})
"""


class ReadLastJsonlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "log.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_and_empty(self):
        self.assertIsNone(read_last_jsonl(self.path))
        self.path.write_bytes(b"")
        self.assertIsNone(read_last_jsonl(self.path))
        self.path.write_bytes(b"\n\n  \n")
        self.assertIsNone(read_last_jsonl(self.path))

    def test_single_line_without_newline(self):
        self.path.write_bytes(b'{"a":1}')
        self.assertEqual(read_last_jsonl(self.path), {"a": 1})

    def test_trailing_blank_lines_and_crlf(self):
        self.path.write_bytes(b'{"a":1}\r\n{"a":2}\r\n\r\n\n')
        self.assertEqual(read_last_jsonl(self.path), {"a": 2})

    def test_line_longer_than_read_chunk(self):
        big = {"a": 3, "blob": "x" * 50000, "text": "äöü€"}
        self.path.write_bytes(b'{"a":1}\n' + json.dumps(big, ensure_ascii=False).encode() + b"\n")
        self.assertEqual(read_last_jsonl(self.path), big)

    def test_corrupt_tail_raises_instead_of_being_ignored(self):
        self.path.write_bytes(b'{"a":1}\n{"a":')
        with self.assertRaises(ValueError):
            read_last_jsonl(self.path)


class AuditConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "audit" / "events.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _assert_consistent(self, expected):
        events = [json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertEqual(len(events), expected)
        ids = [e["event_id"] for e in events]
        self.assertEqual(ids, [f"EVT-{i:06d}" for i in range(1, expected + 1)])
        self.assertTrue(AuditLog(self.path).verify_chain())

    def test_threads_do_not_fork_chain_or_duplicate_ids(self):
        log = AuditLog(self.path)
        errors = []

        def run(n):
            try:
                for i in range(25):
                    log.append("T", component=f"t{n}", payload={"i": i})
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(repr(exc))

        threads = [threading.Thread(target=run, args=(n,)) for n in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        self._assert_consistent(200)

    def test_separate_log_instances_in_one_process_stay_consistent(self):
        a, b = AuditLog(self.path), AuditLog(self.path)
        for i in range(30):
            (a if i % 2 else b).append("X", payload={"i": i})
        self._assert_consistent(30)

    def test_processes_do_not_fork_chain_or_duplicate_ids(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        procs = [subprocess.Popen([sys.executable, "-c", WORKER, SRC, str(self.path), "20", str(n)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) for n in range(4)]
        for p in procs:
            out, err = p.communicate(timeout=120)
            self.assertEqual(p.returncode, 0, err.decode(errors="replace"))
        self._assert_consistent(80)

    def test_append_cost_does_not_grow_with_log_size(self):
        log = AuditLog(self.path)
        for i in range(3000):
            log.append("FILL", payload={"i": i, "pad": "x" * 200})
        started = time.perf_counter()
        for i in range(100):
            log.append("TAIL", payload={"i": i})
        elapsed = time.perf_counter() - started
        # Old behaviour parsed the whole file per append (3000+ lines each time).
        # Generous bound: only catches a return to O(n), not machine speed.
        self.assertLess(elapsed, 10.0, f"100 appends took {elapsed:.2f}s on a 3000-line log")
        self.assertTrue(log.verify_chain())

    def test_lock_times_out_instead_of_hanging(self):
        started = time.monotonic()
        with append_lock(self.path, timeout=5):
            result = {}

            def contender():
                try:
                    with append_lock(self.path, timeout=0.2):
                        result["entered"] = True
                except RuntimeError as exc:
                    result["error"] = str(exc)

            # A second *process* is the real contender; a thread is serialized by the in-process lock.
            code = ("import sys; sys.path.insert(0, sys.argv[1]);"
                    "from guppi_runtime.core.util import append_lock;"
                    "from pathlib import Path\n"
                    "try:\n"
                    "    with append_lock(Path(sys.argv[2]), timeout=0.3): print('entered')\n"
                    "except RuntimeError as e: print(e)\n")
            out = subprocess.run([sys.executable, "-c", code, SRC, str(self.path)],
                                 capture_output=True, text=True, timeout=60).stdout.strip()
        self.assertEqual(out, "append_lock_timeout")
        self.assertLess(time.monotonic() - started, 30)


class EvidenceConcurrencyTests(unittest.TestCase):
    def test_threads_keep_evidence_chain_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DevelopmentEvidenceStore(Path(tmp) / "evidence.jsonl")
            errors = []

            def run(n):
                try:
                    for i in range(15):
                        store.add("test_run", job_id=f"SDJ-{n:012X}", payload={"i": i})
                except Exception as exc:  # pragma: no cover
                    errors.append(repr(exc))

            threads = [threading.Thread(target=run, args=(n,)) for n in range(6)]
            for t in threads: t.start()
            for t in threads: t.join()
            self.assertEqual(errors, [])
            self.assertEqual(len(store.list()), 90)
            self.assertTrue(store.verify_chain())


if __name__ == "__main__":
    unittest.main()
