import unittest

from guppi_runtime.agent_manager.code_collector import candidate_records, records_from_numstat

LOG = "@2026-10-08\n10\t2\tsrc/a.py\n5\t0\tsrc/b.py\n-\t-\timg/logo.png\n\n@2026-10-07\n7\t1\tsrc/a.py\n3\t3\tarchiv/old.py\n"


class NumstatTest(unittest.TestCase):
    def test_every_commit_of_a_day_is_counted_and_binary_files_are_skipped(self):
        self.assertEqual(records_from_numstat(LOG), [{"date": "2026-10-07", "author": "claude", "added": 10}, {"date": "2026-10-08", "author": "claude", "added": 15}])

    def test_guppi_paths_and_ignored_prefixes_split_the_totals(self):
        got = records_from_numstat(LOG, guppi_paths={"src/b.py"}, ignore_prefixes=("archiv/",))
        self.assertEqual(got, [{"date": "2026-10-07", "author": "claude", "added": 7}, {"date": "2026-10-08", "author": "claude", "added": 10}, {"date": "2026-10-08", "author": "guppi", "added": 5}])

    def test_bad_input_gives_nothing_instead_of_an_error(self):
        for text in (None, 5, "", "\n", "10\t0\tno_header.py\n", "@not-a-date\n9\t0\tx.py\n"):
            self.assertEqual(records_from_numstat(text), [])


class CandidateTest(unittest.TestCase):
    def test_only_the_latest_valid_attempt_of_each_spec_counts(self):
        entries = [{"spec": "a", "attempt": "attempt_01_20261008_100000", "lines": 5}, {"spec": "a", "attempt": "attempt_02_20261008_120000", "lines": 9},
                   {"spec": "b", "attempt": "salvaged_20261007_1411", "lines": 90}, {"spec": "c", "attempt": "attempt_01_20261007_090000", "lines": 3}]
        self.assertEqual(candidate_records(entries), [{"date": "2026-10-07", "author": "guppi", "added": 3}, {"date": "2026-10-08", "author": "guppi", "added": 9}])

    def test_bad_entries_are_skipped(self):
        self.assertEqual(candidate_records([None, "x", {"spec": "a", "attempt": "attempt_01_20261399_100000", "lines": 5}, {"spec": "a", "attempt": "attempt_01_20261008_100000", "lines": True}]), [])
        self.assertEqual(candidate_records(None), [])


if __name__ == "__main__":
    unittest.main()
