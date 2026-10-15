import unittest
import json
import hashlib
from guppi_runtime.agent_manager.agent_contracts import ContractError, canonical_digest, check_version, validate_record

class TestAgentContracts(unittest.TestCase):
    
    def test_contract_error_init(self):
        """Test ContractError initialization."""
        error = ContractError("test_code", "test message", "field_name")
        self.assertEqual(error.code, "test_code")
        self.assertEqual(error.field, "field_name")
        self.assertEqual(str(error), "test_code: test message")
        
        # Test without field
        error2 = ContractError("test_code2", "test message 2")
        self.assertEqual(error2.code, "test_code2")
        self.assertIsNone(error2.field)
        self.assertEqual(str(error2), "test_code2: test message 2")
    
    def test_canonical_digest_basic(self):
        """Test basic canonical digest functionality."""
        # Test with simple dict
        obj = {"name": "John", "age": 30}
        digest = canonical_digest(obj)
        self.assertTrue(digest.startswith("sha256:"))
        self.assertEqual(len(digest), 71)  # "sha256:" + 64 hex chars
        
        # Verify it's the expected canonical JSON
        canonical_json = json.dumps(obj, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
        expected_digest = "sha256:" + hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
        self.assertEqual(digest, expected_digest)
    
    def test_canonical_digest_complex(self):
        """Test canonical digest with complex nested objects."""
        obj = {
            "users": [
                {"name": "Alice", "active": True},
                {"name": "Bob", "active": False}
            ],
            "count": 2,
            "metadata": {
                "version": "1.0",
                "timestamp": "2023-01-01"
            }
        }
        digest = canonical_digest(obj)
        self.assertTrue(digest.startswith("sha256:"))
        
        # Verify canonical JSON format
        canonical_json = json.dumps(obj, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
        expected_digest = "sha256:" + hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
        self.assertEqual(digest, expected_digest)
    
    def test_canonical_digest_string(self):
        """Test canonical digest with string values."""
        obj = {"message": "Hello, world!", "code": 200}
        digest = canonical_digest(obj)
        self.assertTrue(digest.startswith("sha256:"))
        
        canonical_json = json.dumps(obj, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
        expected_digest = "sha256:" + hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
        self.assertEqual(digest, expected_digest)
    
    def test_canonical_digest_special_chars(self):
        """Test canonical digest with special characters."""
        obj = {"message": "Hello 世界", "emoji": "😀"}
        digest = canonical_digest(obj)
        self.assertTrue(digest.startswith("sha256:"))
        
        canonical_json = json.dumps(obj, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
        expected_digest = "sha256:" + hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
        self.assertEqual(digest, expected_digest)
    
    def test_canonical_digest_invalid_types(self):
        """Test that invalid types raise ContractError."""
        # Test with tuple (not allowed)
        with self.assertRaises(ContractError) as cm:
            canonical_digest(("a", "b"))
        self.assertEqual(cm.exception.code, "not_canonical")
        
        # Test with set (not allowed)
        with self.assertRaises(ContractError) as cm:
            canonical_digest({"a", "b"})
        self.assertEqual(cm.exception.code, "not_canonical")
        
        # Test with bytes (not allowed)
        with self.assertRaises(ContractError) as cm:
            canonical_digest(b"hello")
        self.assertEqual(cm.exception.code, "not_canonical")
        
        # Test with non-str dict keys (not allowed)
        with self.assertRaises(ContractError) as cm:
            canonical_digest({1: "value"})
        self.assertEqual(cm.exception.code, "not_canonical")
        
        # Test with NaN (not allowed)
        with self.assertRaises(ContractError) as cm:
            canonical_digest({"value": float('nan')})
        self.assertEqual(cm.exception.code, "not_canonical")
        
        # Test with infinity (not allowed)
        with self.assertRaises(ContractError) as cm:
            canonical_digest({"value": float('inf')})
        self.assertEqual(cm.exception.code, "not_canonical")
        
        # Test with None (allowed)
        digest = canonical_digest(None)
        self.assertTrue(digest.startswith("sha256:"))
        
        # Test with float (allowed)
        digest = canonical_digest(3.14)
        self.assertTrue(digest.startswith("sha256:"))
        
        # Test with bool (allowed)
        digest = canonical_digest(True)
        self.assertTrue(digest.startswith("sha256:"))

    def test_check_version_valid(self):
        """Test valid version checking."""
        # Test with default supported major version (1)
        result = check_version("1.0")
        self.assertEqual(result, (1, 0))
        
        result = check_version("1.5")
        self.assertEqual(result, (1, 5))
        
        result = check_version("1.10")
        self.assertEqual(result, (1, 10))
        
        # Test with custom supported major version
        result = check_version("2.0", supported_major=2)
        self.assertEqual(result, (2, 0))
        
        result = check_version("2.7", supported_major=2)
        self.assertEqual(result, (2, 7))

    def test_check_version_invalid_types(self):
        """Test version checking with invalid types."""
        # Test with non-string input
        with self.assertRaises(ContractError) as cm:
            check_version(123)
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            check_version(None)
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            check_version([])
        self.assertEqual(cm.exception.code, "bad_version")

    def test_check_version_invalid_format(self):
        """Test version checking with invalid formats."""
        # Test with too many parts
        with self.assertRaises(ContractError) as cm:
            check_version("1.2.3")
        self.assertEqual(cm.exception.code, "bad_version")
        
        # Test with too few parts
        with self.assertRaises(ContractError) as cm:
            check_version("1")
        self.assertEqual(cm.exception.code, "bad_version")
        
        # Test with empty parts
        with self.assertRaises(ContractError) as cm:
            check_version("1.")
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            check_version(".2")
        self.assertEqual(cm.exception.code, "bad_version")
        
        # Test with non-numeric parts
        with self.assertRaises(ContractError) as cm:
            check_version("a.2")
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            check_version("1.b")
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            check_version("1.2.3.4")
        self.assertEqual(cm.exception.code, "bad_version")

    def test_check_version_incompatible_major(self):
        """Test version checking with incompatible major version."""
        # Test with major version that doesn't match supported
        with self.assertRaises(ContractError) as cm:
            check_version("2.0")
        self.assertEqual(cm.exception.code, "incompatible_major")
        
        with self.assertRaises(ContractError) as cm:
            check_version("0.5")
        self.assertEqual(cm.exception.code, "incompatible_major")
        
        # Test with custom supported major version
        with self.assertRaises(ContractError) as cm:
            check_version("3.0", supported_major=2)
        self.assertEqual(cm.exception.code, "incompatible_major")

    def test_check_version_non_ascii_digits(self):
        """Test that non-ASCII digits raise ContractError."""
        # Test with Arabic-Indic digits (Unicode digits)
        with self.assertRaises(ContractError) as cm:
            check_version("\u0661.\u0660")  # Arabic-Indic 1.0
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            check_version("1.\u0662")  # ASCII 1, Arabic-Indic 2
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            check_version("\u0663.\u0660")  # Arabic-Indic 3.0
        self.assertEqual(cm.exception.code, "bad_version")
        
        # Test with other Unicode digits
        with self.assertRaises(ContractError) as cm:
            check_version("1\u00B2.0")  # Superscript 2
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            check_version("1.0\u00B2")  # Superscript 2
        self.assertEqual(cm.exception.code, "bad_version")

    def test_check_version_non_ascii_digits(self):
        """Test that non-ASCII digits raise ContractError."""
        # Test with Arabic-Indic digits (Unicode digits)
        with self.assertRaises(ContractError) as cm:
            check_version("\u0661.\u0660")  # Arabic-Indic 1.0
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            check_version("1.\u0662")  # ASCII 1, Arabic-Indic 2
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            check_version("\u0663.\u0660")  # Arabic-Indic 3.0
        self.assertEqual(cm.exception.code, "bad_version")
        
        # Test with other Unicode digits
        with self.assertRaises(ContractError) as cm:
            check_version("1\u00B2.0")  # Superscript 2
        self.assertEqual(cm.exception.code, "bad_version")
        
        with self.assertRaises(ContractError) as cm:
            check_version("1.0\u00B2")  # Superscript 2
        self.assertEqual(cm.exception.code, "bad_version")

    def test_validate_record_basic(self):
        """Test basic validate_record functionality."""
        spec = {
            "required": {"name": "str", "age": "int"},
            "optional": {"email": "str"}
        }
        
        data = {"name": "John", "age": 30, "email": "john@example.com"}
        result = validate_record(data, spec)
        
        # Should return a copy of the data
        self.assertEqual(result, data)
        self.assertIsNot(result, data)  # Should be a different object
        
        # Test with only required fields
        data2 = {"name": "Jane", "age": 25}
        result2 = validate_record(data2, spec)
        self.assertEqual(result2, data2)
        self.assertIsNot(result2, data2)

    def test_validate_record_bad_type(self):
        """Test validate_record with bad data type."""
        spec = {"required": {"name": "str"}}
        
        # Test with non-dict data
        with self.assertRaises(ContractError) as cm:
            validate_record("not a dict", spec)
        self.assertEqual(cm.exception.code, "bad_type")
        self.assertIsNone(cm.exception.field)

    def test_validate_record_unknown_field(self):
        """Test validate_record with unknown field."""
        spec = {
            "required": {"name": "str"},
            "optional": {"age": "int"}
        }
        
        # Test with unknown field
        data = {"name": "John", "unknown_field": "value"}
        with self.assertRaises(ContractError) as cm:
            validate_record(data, spec)
        self.assertEqual(cm.exception.code, "unknown_field")
        self.assertEqual(cm.exception.field, "unknown_field")

    def test_validate_record_missing_required_field(self):
        """Test validate_record with missing required field."""
        spec = {
            "required": {"name": "str", "age": "int"},
            "optional": {"email": "str"}
        }
        
        # Test with missing required field
        data = {"name": "John"}  # Missing age
        with self.assertRaises(ContractError) as cm:
            validate_record(data, spec)
        self.assertEqual(cm.exception.code, "missing_field")
        self.assertEqual(cm.exception.field, "age")

    def test_validate_record_bad_type_field(self):
        """Test validate_record with field of wrong type."""
        spec = {
            "required": {"name": "str", "age": "int"},
            "optional": {"active": "bool"}
        }
        
        # Test with wrong type for required field
        data = {"name": "John", "age": "not_an_int"}  # age should be int
        with self.assertRaises(ContractError) as cm:
            validate_record(data, spec)
        self.assertEqual(cm.exception.code, "bad_type")
        self.assertEqual(cm.exception.field, "age")
        
        # Test with wrong type for optional field
        data2 = {"name": "John", "age": 30, "active": "not_a_bool"}  # active should be bool
        with self.assertRaises(ContractError) as cm:
            validate_record(data2, spec)
        self.assertEqual(cm.exception.code, "bad_type")
        self.assertEqual(cm.exception.field, "active")

    def test_validate_record_int_type_checking(self):
        """Test that int type does not accept bool or float."""
        spec = {"required": {"count": "int"}}
        
        # Test with int (should work)
        data = {"count": 42}
        result = validate_record(data, spec)
        self.assertEqual(result, data)
        
        # Test with bool (should fail)
        data2 = {"count": True}
        with self.assertRaises(ContractError) as cm:
            validate_record(data2, spec)
        self.assertEqual(cm.exception.code, "bad_type")
        self.assertEqual(cm.exception.field, "count")
        
        # Test with float (should fail)
        data3 = {"count": 42.0}
        with self.assertRaises(ContractError) as cm:
            validate_record(data3, spec)
        self.assertEqual(cm.exception.code, "bad_type")
        self.assertEqual(cm.exception.field, "count")

    def test_validate_record_bool_type_checking(self):
        """Test that bool type only accepts bool."""
        spec = {"required": {"active": "bool"}}
        
        # Test with bool (should work)
        data = {"active": True}
        result = validate_record(data, spec)
        self.assertEqual(result, data)
        
        # Test with int (should fail)
        data2 = {"active": 1}
        with self.assertRaises(ContractError) as cm:
            validate_record(data2, spec)
        self.assertEqual(cm.exception.code, "bad_type")
        self.assertEqual(cm.exception.field, "active")

    def test_validate_record_empty_specs(self):
        """Test validate_record with empty specs."""
        spec = {}  # No required or optional fields
        
        data = {"name": "John"}
        result = validate_record(data, spec)
        self.assertEqual(result, data)

    def test_validate_record_no_required_fields(self):
        """Test validate_record with no required fields."""
        spec = {"optional": {"name": "str"}}
        
        data = {"name": "John"}
        result = validate_record(data, spec)
        self.assertEqual(result, data)
        
        # Test with no fields at all
        data2 = {}
        result2 = validate_record(data2, spec)
        self.assertEqual(result2, data2)

    def test_validate_record_no_optional_fields(self):
        """Test validate_record with no optional fields."""
        spec = {"required": {"name": "str"}}
        
        data = {"name": "John"}
        result = validate_record(data, spec)
        self.assertEqual(result, data)
        
        # Test with extra fields (should fail)
        data2 = {"name": "John", "extra": "field"}
        with self.assertRaises(ContractError) as cm:
            validate_record(data2, spec)
        self.assertEqual(cm.exception.code, "unknown_field")

if __name__ == '__main__':
    unittest.main()