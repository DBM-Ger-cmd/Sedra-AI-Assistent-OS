import unittest
import sys
import os

# Add the current directory to the path so we can import agent_matcher
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from guppi_runtime.agent_manager.agent_matcher import version_at_least, qualification_rank, hard_filter, resource_fit, score_candidate, match
from guppi_runtime.agent_manager.agent_contracts import ContractError

class TestAgentMatcher(unittest.TestCase):
    
    def test_version_at_least_valid_cases(self):
        # Test cases where version >= minimum
        self.assertTrue(version_at_least("1.0.0", "1.0.0"))
        self.assertTrue(version_at_least("1.1.0", "1.0.0"))
        self.assertTrue(version_at_least("1.0.1", "1.0.0"))
        self.assertTrue(version_at_least("2.0.0", "1.0.0"))
        self.assertTrue(version_at_least("1.10.0", "1.9.0"))
        self.assertTrue(version_at_least("2.5.10", "2.5.9"))
        
    def test_version_at_least_invalid_cases(self):
        # Test cases where version < minimum
        self.assertFalse(version_at_least("0.9.9", "1.0.0"))
        self.assertFalse(version_at_least("1.8.9", "1.9.0"))
        self.assertFalse(version_at_least("2.4.9", "2.5.0"))
        
    def test_version_at_least_bad_version_format(self):
        # Test invalid version formats
        with self.assertRaises(ContractError) as cm:
            version_at_least("1.0", "1.0.0")
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            version_at_least("1.0.0.0", "1.0.0")
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            version_at_least("1.a.0", "1.0.0")
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            version_at_least(1, "1.0.0")
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            version_at_least("1.0.0", 1)
        self.assertEqual(cm.exception.code, "bad_version")
        
    def test_qualification_rank_valid_cases(self):
        # Test valid qualifications and their ranks
        self.assertEqual(qualification_rank("UNVERIFIED"), 0)
        self.assertEqual(qualification_rank("VERIFIED"), 1)
        self.assertEqual(qualification_rank("PROVEN"), 2)
        self.assertEqual(qualification_rank("TRUSTED"), 3)
        
    def test_qualification_rank_invalid_cases(self):
        # Test invalid qualifications
        with self.assertRaises(ContractError) as cm:
            qualification_rank("INVALID")
        self.assertEqual(cm.exception.code, "bad_qualification")
        
        with self.assertRaises(ContractError) as cm:
            qualification_rank(123)
        self.assertEqual(cm.exception.code, "bad_qualification")
        
        with self.assertRaises(ContractError) as cm:
            qualification_rank(None)
        self.assertEqual(cm.exception.code, "bad_qualification")










    def test_hard_filter_passes(self):
        # Test a candidate that passes all checks
        candidate = {
            "lifecycle": "ACTIVE",
            "admission": {"valid": True},
            "qualification": "TRUSTED",
            "capabilities": [
                {"id": "cap1", "version": "1.0.0", "side_effect": "read_only"}
            ]
        }
        requirement = {
            "must": [{"id": "cap1", "minimum_version": "1.0.0"}],
            "min_qualification": "VERIFIED",
            "effects_allowed": ["read_only"]
        }
        reasons = hard_filter(candidate, requirement)
        self.assertEqual(len(reasons), 0)

    def test_resource_fit_resource_unknown(self):
        # Test when free is None
        result = resource_fit({"cpu_cores": 2}, None)
        self.assertEqual(result["state"], "resource_unknown")
        self.assertIsNone(result["fit"])
        self.assertIsNone(result["max_ratio"])

        # Test when a requested resource is missing from free
        result = resource_fit({"cpu_cores": 2, "ram_mib": 1024}, {"cpu_cores": 4})
        self.assertEqual(result["state"], "resource_unknown")
        self.assertIsNone(result["fit"])
        self.assertIsNone(result["max_ratio"])

        # Test when a requested resource has None free value
        result = resource_fit({"cpu_cores": 2, "ram_mib": 1024}, {"cpu_cores": 4, "ram_mib": None})
        self.assertEqual(result["state"], "resource_unknown")
        self.assertIsNone(result["fit"])
        self.assertIsNone(result["max_ratio"])

    def test_resource_fit_queued_resource(self):
        # Test when requested resource exceeds free amount
        result = resource_fit({"cpu_cores": 2}, {"cpu_cores": 1})
        self.assertEqual(result["state"], "queued_resource")
        self.assertIsNone(result["fit"])
        self.assertIsNone(result["max_ratio"])

        # Test when free is 0
        result = resource_fit({"cpu_cores": 2}, {"cpu_cores": 0})
        self.assertEqual(result["state"], "queued_resource")
        self.assertIsNone(result["fit"])
        self.assertIsNone(result["max_ratio"])

        # Test when a requested resource exceeds free amount
        result = resource_fit({"cpu_cores": 2, "ram_mib": 1024}, {"cpu_cores": 4, "ram_mib": 512})
        self.assertEqual(result["state"], "queued_resource")
        self.assertIsNone(result["fit"])
        self.assertIsNone(result["max_ratio"])


    def test_score_candidate(self):
        # Test basic scoring
        candidate = {
            "capabilities": [
                {"id": "cap1", "version": "1.0.0"},
                {"id": "cap2", "version": "2.0.0"}
            ],
            "stats": {"successes": 5, "runs": 10},
            "resources": {"cpu_cores": 2, "ram_mib": 1024},
            "qualification": "VERIFIED",
            "available": "now"
        }
        
        requirement = {
            "can": [
                {"id": "cap1", "weight": 2, "minimum_version": "1.0.0"},
                {"id": "cap2", "weight": 3, "minimum_version": "1.0.0"}
            ]
        }
        
        snapshot = {"cpu_cores": 4, "ram_mib": 2048}
        
        result = score_candidate(candidate, requirement, snapshot)
        
        # Check that score is calculated correctly
        self.assertIn("score", result)
        self.assertIn("components", result)
        self.assertEqual(result["components"]["fit_for_purpose"], 1.0)  # Both capabilities satisfied
        self.assertEqual(result["components"]["success_rate"], (5 + 1) / (10 + 2))  # 6/12 = 0.5
        self.assertEqual(result["components"]["resource_fit"], 0.5)  # 1 - 2/4 = 0.5
        self.assertEqual(result["components"]["qualification"], 0.5)  # VERIFIED
        self.assertEqual(result["components"]["availability"], 1.0)  # "now"
        
        # Calculate expected score: 30*1.0 + 25*0.5 + 20*0.5 + 15*0.5 + 10*1.0 = 30 + 12.5 + 10 + 7.5 + 10 = 70.0
        expected_score = 30 * 1.0 + 25 * 0.5 + 20 * 0.5 + 15 * 0.5 + 10 * 1.0
        self.assertEqual(result["score"], round(expected_score, 2))


    def test_score_candidate_no_satisfying_capabilities(self):
        # Test when no capabilities satisfy the requirement
        candidate = {
            "capabilities": [
                {"id": "cap1", "version": "0.5.0"}  # Version too low
            ],
            "stats": {"successes": 3, "runs": 6},
            "resources": {"cpu_cores": 2},
            "qualification": "UNVERIFIED",
            "available": "sequential"
        }
        
        requirement = {
            "can": [
                {"id": "cap1", "weight": 2, "minimum_version": "1.0.0"},
                {"id": "cap2", "weight": 3, "minimum_version": "1.0.0"}  # Not present
            ]
        }
        
        snapshot = {"cpu_cores": 4}
        
        result = score_candidate(candidate, requirement, snapshot)
        
        self.assertEqual(result["components"]["fit_for_purpose"], 0.0)  # No capabilities satisfied
        self.assertEqual(result["components"]["success_rate"], (3 + 1) / (6 + 2))  # 4/8 = 0.5
        self.assertEqual(result["components"]["resource_fit"], 0.5)  # 1 - 2/4 = 0.5
        self.assertEqual(result["components"]["qualification"], 0.0)  # UNVERIFIED
        self.assertEqual(result["components"]["availability"], 0.5)  # "sequential"
        
        # Calculate expected score: 30*0.0 + 25*0.5 + 20*0.5 + 15*0.0 + 10*0.5 = 0 + 12.5 + 10 + 0 + 5 = 27.5
        expected_score = 30 * 0.0 + 25 * 0.5 + 20 * 0.5 + 15 * 0.0 + 10 * 0.5
        self.assertEqual(result["score"], round(expected_score, 2))


    def test_score_candidate_invalid_qualification(self):
        # Test with invalid qualification
        candidate = {
            "qualification": "INVALID_QUALIFICATION",
            "stats": {"successes": 5, "runs": 10},
            "available": "now"
        }
        
        requirement = {
            "can": [{"id": "cap1", "weight": 1}]
        }
        
        snapshot = {}
        
        result = score_candidate(candidate, requirement, snapshot)
        
        self.assertEqual(result["components"]["qualification"], 0.0)  # Invalid qualification returns 0.0







    def test_match_gaps_empty_candidate_list(self):
        # Test gaps when there are no candidates at all
        requirement = {
            "must": [{"id": "cap1", "minimum_version": "1.0.0"}],
            "min_qualification": "VERIFIED"
        }
        candidates = []
        snapshot = {"cpu_cores": 4}
        
        result = match(requirement, candidates, snapshot)
        
        self.assertEqual(result["gaps"], [{"missing_capabilities": ["cap1"]}])

    def test_match_gaps_no_satisfying_candidates(self):
        # Test gaps when there are candidates but none satisfy the requirement
        requirement = {
            "must": [{"id": "cap1", "minimum_version": "1.0.0"}],
            "min_qualification": "VERIFIED"
        }
        candidates = [
            {
                "agent_id": "agent1",
                "lifecycle": "ACTIVE",
                "capabilities": [{"id": "cap2", "version": "1.0.0"}]  # Different capability
            }
        ]
        snapshot = {"cpu_cores": 4}
        
        result = match(requirement, candidates, snapshot)
        
        self.assertEqual(result["gaps"], [{"missing_capabilities": ["cap1"]}])

    def test_match_gaps_with_satisfying_candidates(self):
        # Test gaps when there are candidates that satisfy the requirement
        requirement = {
            "must": [{"id": "cap1", "minimum_version": "1.0.0"}],
            "min_qualification": "VERIFIED"
        }
        candidates = [
            {
                "agent_id": "agent1",
                "lifecycle": "ACTIVE",
                "capabilities": [{"id": "cap1", "version": "1.0.0"}]
            }
        ]
        snapshot = {"cpu_cores": 4}
        
        result = match(requirement, candidates, snapshot)
        
        self.assertEqual(result["gaps"], [])

    def test_match_gaps_multiple_missing_capabilities(self):
        # Test gaps with multiple missing capabilities
        requirement = {
            "must": [
                {"id": "cap1", "minimum_version": "1.0.0"},
                {"id": "cap2", "minimum_version": "1.0.0"},
                {"id": "cap3", "minimum_version": "1.0.0"}
            ],
            "min_qualification": "VERIFIED"
        }
        candidates = [
            {
                "agent_id": "agent1",
                "lifecycle": "ACTIVE",
                "capabilities": [{"id": "cap1", "version": "1.0.0"}]
            }
        ]
        snapshot = {"cpu_cores": 4}
        
        result = match(requirement, candidates, snapshot)
        
        self.assertEqual(result["gaps"], [{"missing_capabilities": ["cap2", "cap3"]}])

if __name__ == '__main__':
    unittest.main()