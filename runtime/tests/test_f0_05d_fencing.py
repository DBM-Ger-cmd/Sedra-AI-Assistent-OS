"""F0-05D: Einheitstests fuer Fencing/Recovery-Verträge (jobs/fencing.py).

Keine externen Abhaengigkeiten, kein Modell, kein Netzwerk. Laufbar mit unittest.
"""
from __future__ import annotations

import unittest

from sedra_runtime.jobs.fencing import (  # noqa: E402
    FENCE_ALLOW,
    FENCE_BLOCK_FOREIGN_LEASE,
    FENCE_BLOCK_NO_LIVE_PROCESS,
    LEASE_OWNER,
    RESOLUTION_ABORT,
    RESOLUTION_RETRY_READONLY,
    fence_check,
    recovery_verdict,
)


class FenceCheckTest(unittest.TestCase):
    def test_live_process_is_allowed(self):
        res = fence_check("owner-a", "res-1", live_process=True, foreign_lease_owner=None)
        self.assertEqual(res["decision"], FENCE_ALLOW)

    def test_foreign_lease_is_blocked(self):
        res = fence_check(
            "owner-a", "res-1", live_process=False, foreign_lease_owner="owner-b"
        )
        self.assertEqual(res["decision"], FENCE_BLOCK_FOREIGN_LEASE)
        self.assertIn("owner-b", res["reason"])

    def test_own_lease_is_allowed(self):
        res = fence_check(
            "owner-a", "res-1", live_process=False, foreign_lease_owner="owner-a"
        )
        self.assertEqual(res["decision"], FENCE_ALLOW)

    def test_no_process_no_lease_is_blocked(self):
        res = fence_check("owner-a", "res-1", live_process=False, foreign_lease_owner=None)
        self.assertEqual(res["decision"], FENCE_BLOCK_NO_LIVE_PROCESS)


class RecoveryVerdictTest(unittest.TestCase):
    def test_mutating_unknown_outcome_is_dead(self):
        res = recovery_verdict(
            RESOLUTION_ABORT, is_mutating=True, outcome_known=False, gate_authorized=True
        )
        self.assertEqual(res["verdict"], "dead")
        self.assertFalse(res["gate_required"])

    def test_retry_readonly_on_mutating_is_blocked(self):
        res = recovery_verdict(
            RESOLUTION_RETRY_READONLY,
            is_mutating=True,
            outcome_known=True,
            gate_authorized=True,
        )
        self.assertEqual(res["verdict"], "blocked")

    def test_retry_readonly_on_readonly_requires_gate(self):
        res = recovery_verdict(
            RESOLUTION_RETRY_READONLY,
            is_mutating=False,
            outcome_known=True,
            gate_authorized=False,
        )
        self.assertEqual(res["verdict"], "captain_required")
        self.assertTrue(res["gate_required"])

    def test_authorized_recovery_is_completed(self):
        res = recovery_verdict(
            RESOLUTION_ABORT,
            is_mutating=False,
            outcome_known=True,
            gate_authorized=True,
        )
        self.assertEqual(res["verdict"], "completed")


class LeaseOwnerTest(unittest.TestCase):
    def test_lease_owner_is_not_empty(self):
        self.assertIsInstance(LEASE_OWNER, str)
        self.assertGreater(len(LEASE_OWNER), 0)


if __name__ == "__main__":
    unittest.main()
