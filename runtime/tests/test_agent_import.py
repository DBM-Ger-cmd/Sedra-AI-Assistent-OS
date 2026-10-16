import unittest
from guppi_runtime.agent_manager.agent_import import parse_semver, template_ref, check_soul, preview_template
from guppi_runtime.agent_manager.agent_contracts import ContractError

class TestParseSemver(unittest.TestCase):
    
    def test_valid_semver(self):
        """Test valid semantic version strings."""
        self.assertEqual(parse_semver("1.2.3"), (1, 2, 3))
        self.assertEqual(parse_semver("0.0.0"), (0, 0, 0))
        self.assertEqual(parse_semver("10.20.30"), (10, 20, 30))
    
    def test_invalid_not_string(self):
        """Test that non-string inputs raise ContractError."""
        with self.assertRaises(ContractError) as cm:
            parse_semver(123)
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            parse_semver(None)
        self.assertEqual(cm.exception.code, "bad_version")
    
    def test_invalid_wrong_number_of_parts(self):
        """Test version strings with wrong number of parts."""
        with self.assertRaises(ContractError) as cm:
            parse_semver("1.2")
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            parse_semver("1.2.3.4")
        self.assertEqual(cm.exception.code, "bad_version")
    
    def test_invalid_empty_parts(self):
        """Test version strings with empty parts."""
        with self.assertRaises(ContractError) as cm:
            parse_semver("1..3")
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            parse_semver(".2.3")
        self.assertEqual(cm.exception.code, "bad_version")
    
    def test_invalid_non_numeric_parts(self):
        """Test version strings with non-numeric parts."""
        with self.assertRaises(ContractError) as cm:
            parse_semver("1.a.3")
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            parse_semver("1.2.-3")
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            parse_semver("1.2. 3")
        self.assertEqual(cm.exception.code, "bad_version")
    
    def test_invalid_negative_numbers(self):
        """Test version strings with negative numbers."""
        # This is actually handled by the regex check, so we expect it to fail
        with self.assertRaises(ContractError) as cm:
            parse_semver("1.-2.3")
        self.assertEqual(cm.exception.code, "bad_version")


class TestTemplateRef(unittest.TestCase):
    
    def test_valid_template(self):
        """Test valid template with id and version."""
        template = {
            "id": "my-template",
            "version": "1.2.3"
        }
        self.assertEqual(template_ref(template), "my-template@1.2.3")
        
        # Test with different valid id pattern
        template = {
            "id": "a1b2c3",
            "version": "0.0.0"
        }
        self.assertEqual(template_ref(template), "a1b2c3@0.0.0")
    
    def test_invalid_not_dict(self):
        """Test that non-dict inputs return None."""
        self.assertIsNone(template_ref("not_a_dict"))
        self.assertIsNone(template_ref(None))
        self.assertIsNone(template_ref(123))
    
    def test_missing_keys(self):
        """Test templates with missing keys."""
        template = {"id": "my-template"}
        self.assertIsNone(template_ref(template))
        
        template = {"version": "1.2.3"}
        self.assertIsNone(template_ref(template))
    
    def test_invalid_id_pattern(self):
        """Test templates with invalid id patterns."""
        # Invalid: starts with number
        template = {"id": "123abc", "version": "1.2.3"}
        self.assertIsNone(template_ref(template))
        
        # Invalid: contains uppercase
        template = {"id": "MyTemplate", "version": "1.2.3"}
        self.assertIsNone(template_ref(template))
        
        # Invalid: too short
        template = {"id": "ab", "version": "1.2.3"}
        self.assertIsNone(template_ref(template))
        
        # Invalid: contains invalid character
        template = {"id": "my@template", "version": "1.2.3"}
        self.assertIsNone(template_ref(template))
    
    def test_invalid_version(self):
        """Test templates with invalid versions."""
        template = {"id": "my-template", "version": "1.2"}
        self.assertIsNone(template_ref(template))
        
        template = {"id": "my-template", "version": "1.a.3"}
        self.assertIsNone(template_ref(template))
        
        template = {"id": "my-template", "version": "1.2.3.4"}
        self.assertIsNone(template_ref(template))
    
    def test_invalid_id_type(self):
        """Test templates with non-string id."""
        template = {"id": 123, "version": "1.2.3"}
        self.assertIsNone(template_ref(template))
    
    def test_invalid_version_type(self):
        """Test templates with non-string version."""
        template = {"id": "my-template", "version": 123}
        self.assertIsNone(template_ref(template))


class TestCheckSoul(unittest.TestCase):
    
    def test_soul_missing(self):
        """Test when template has no soul field."""
        template = {"id": "test"}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_missing"])
        
        # Test when template is not a dict
        template = "not_a_dict"
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_missing"])
        
        # Test when soul is not a dict
        template = {"soul": "not_a_dict"}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_missing"])
    
    def test_soul_missing_fields(self):
        """Test when soul is missing required fields."""
        template = {"soul": {"path": "test.txt"}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_missing"])
        
        template = {"soul": {"version": "1.0.0"}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_missing"])
        
        template = {"soul": {"sha256": "a" * 64}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_missing"])
    
    def test_soul_path_invalid(self):
        """Test when soul path is invalid."""
        template = {"soul": {"path": "", "version": "1.0.0", "sha256": "a" * 64}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_path"])
        
        template = {"soul": {"path": "/invalid", "version": "1.0.0", "sha256": "a" * 64}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_path"])
        
        template = {"soul": {"path": "invalid\\path", "version": "1.0.0", "sha256": "a" * 64}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_path"])
        
        template = {"soul": {"path": "invalid:path", "version": "1.0.0", "sha256": "a" * 64}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_path"])
        
        template = {"soul": {"path": "invalid\x00path", "version": "1.0.0", "sha256": "a" * 64}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_path"])
        
        template = {"soul": {"path": "invalid/../path", "version": "1.0.0", "sha256": "a" * 64}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_path"])
        
        template = {"soul": {"path": "invalid/./path", "version": "1.0.0", "sha256": "a" * 64}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_path"])
        
        template = {"soul": {"path": 123, "version": "1.0.0", "sha256": "a" * 64}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_path"])
    
    def test_soul_file_invalid(self):
        """Test when files is not a dict or file doesn't exist."""
        template = {"soul": {"path": "test.txt", "version": "1.0.0", "sha256": "a" * 64}}
        files = "not_a_dict"
        self.assertEqual(check_soul(template, files), ["soul_file"])
        
        template = {"soul": {"path": "test.txt", "version": "1.0.0", "sha256": "a" * 64}}
        files = {}
        self.assertEqual(check_soul(template, files), ["soul_file"])
        
        template = {"soul": {"path": "test.txt", "version": "1.0.0", "sha256": "a" * 64}}
        files = {"test.txt": "not_bytes"}
        self.assertEqual(check_soul(template, files), ["soul_file"])
    
    def test_soul_hash_invalid(self):
        """Test when hash is invalid."""
        template = {"soul": {"path": "test.txt", "version": "1.0.0", "sha256": "not_64_chars"}}
        files = {"test.txt": b"content"}
        self.assertEqual(check_soul(template, files), ["soul_hash"])
        
        template = {"soul": {"path": "test.txt", "version": "1.0.0", "sha256": "g" * 64}}
        files = {"test.txt": b"content"}
        self.assertEqual(check_soul(template, files), ["soul_hash"])
        
        template = {"soul": {"path": "test.txt", "version": "1.0.0", "sha256": 123}}
        files = {"test.txt": b"content"}
        self.assertEqual(check_soul(template, files), ["soul_hash"])
        
        template = {"soul": {"path": "test.txt", "version": "1.0.0", "sha256": "a" * 64}}
        files = {"test.txt": b"content"}
        self.assertEqual(check_soul(template, files), ["soul_hash"])
    




class TestPreviewTemplate(unittest.TestCase):
    def test_not_a_dict(self):
        """Test when template is not a dict"""
        result = preview_template("not_a_dict", {})
        expected = {"ok": False, "ref": None, "trust": "UNVERIFIED", "problems": ["not_a_template"]}
        self.assertEqual(result, expected)
        
        result = preview_template(None, {})
        expected = {"ok": False, "ref": None, "trust": "UNVERIFIED", "problems": ["not_a_template"]}
        self.assertEqual(result, expected)
        
        result = preview_template(123, {})
        expected = {"ok": False, "ref": None, "trust": "UNVERIFIED", "problems": ["not_a_template"]}
        self.assertEqual(result, expected)
        
        
        
        


# This file is meant to be run with: python3 -m unittest discover -s tests