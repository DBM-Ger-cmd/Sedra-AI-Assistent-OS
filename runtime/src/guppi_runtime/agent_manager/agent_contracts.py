import hashlib
import json
import re
from typing import Any, Dict, List, Union

class ContractError(ValueError):
    def __init__(self, code: str, message: str, field=None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.field = field



def check_version(version: str, supported_major: int = 1) -> tuple:
    """Check if a version string is valid and compatible.
    
    Args:
        version: A string of the form "<major>.<minor>" with two non-negative integers
        supported_major: The major version number that is supported
        
    Returns:
        tuple: (major, minor) as integers
        
    Raises:
        ContractError: If version is not a valid string format or has incompatible major version
    """
    # Check that version is a string
    if not isinstance(version, str):
        raise ContractError("bad_version", f"Version must be a string, got {type(version).__name__}")
    
    # Split the version string
    parts = version.split('.')
    
    # Check that we have exactly two parts
    if len(parts) != 2:
        raise ContractError("bad_version", f"Version must be in the format '<major>.<minor>', got '{version}'")
    
    major_str, minor_str = parts
    
    # Check that both parts are non-empty
    if not major_str or not minor_str:
        raise ContractError("bad_version", f"Version must be in the format '<major>.<minor>', got '{version}'")
    
    # Check that both parts contain only digits (0-9) - using re.fullmatch with [0-9]+ to ensure ASCII digits only
    if not re.fullmatch(r"[0-9]+", major_str) or not re.fullmatch(r"[0-9]+", minor_str):
        raise ContractError("bad_version", f"Version parts must be non-negative integers using ASCII digits only, got '{version}'")
    
    # Convert to integers
    major = int(major_str)
    minor = int(minor_str)
    
    # Check that major version is supported
    if major != supported_major:
        raise ContractError("incompatible_major", f"Supported major version is {supported_major}, got {major}")
    
    return (major, minor)

def validate_record(data: Dict[str, Any], spec: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """Validate a record against a specification.
    
    Args:
        data: The data to validate (must be a dict)
        spec: The specification with "required" and "optional" fields
        
    Returns:
        A deep copy of the data
        
    Raises:
        ContractError: If validation fails
    """
    # Check that data is a dict
    if not isinstance(data, dict):
        raise ContractError("bad_type", f"Data must be a dict, got {type(data).__name__}", field=None)
    
    # Extract required and optional fields from spec
    required_fields = spec.get("required", {})
    optional_fields = spec.get("optional", {})
    
    # Check for unknown fields (fields in data but not in required or optional)
    # If both required and optional are empty, all fields are allowed
    if required_fields or optional_fields:
        all_allowed_fields = set(required_fields.keys()) | set(optional_fields.keys())
        unknown_fields = set(data.keys()) - all_allowed_fields
        if unknown_fields:
            # Sort alphabetically to ensure consistent error reporting
            unknown_field = sorted(unknown_fields)[0]
            raise ContractError("unknown_field", f"Unknown field '{unknown_field}'", field=unknown_field)
    
    # Check for missing required fields
    missing_fields = set(required_fields.keys()) - set(data.keys())
    if missing_fields:
        # Sort alphabetically to ensure consistent error reporting
        missing_field = sorted(missing_fields)[0]
        raise ContractError("missing_field", f"Missing required field '{missing_field}'", field=missing_field)
    
    # Check types of fields - check all fields in data in alphabetical order
    all_fields_in_data = set(data.keys())
    for field_name in sorted(all_fields_in_data):
        # Determine the expected type
        if field_name in required_fields:
            type_name = required_fields[field_name]
        elif field_name in optional_fields:
            type_name = optional_fields[field_name]
        else:
            # This shouldn't happen due to unknown field check above, but just in case
            continue
            
        value = data[field_name]
        if not _check_type(value, type_name):
            raise ContractError("bad_type", f"Field '{field_name}' must be of type {type_name}, got {type(value).__name__}", field=field_name)
    
    # Return a deep copy of the data
    return json.loads(json.dumps(data))

def _check_type(value: Any, type_name: str) -> bool:
    """Check if a value matches the specified type name."""
    # Special handling for int - does NOT accept bool or float
    if type_name == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    
    # Special handling for bool - only accepts bool
    if type_name == "bool":
        return isinstance(value, bool)
    
    # For other types, use isinstance check
    type_map = {
        "str": str,
        "list": list,
        "dict": dict
    }
    
    if type_name in type_map:
        return isinstance(value, type_map[type_name])
    
    # If type_name is not recognized, return False
    return False

def _validate_canonical(obj: Any, path: str = "") -> None:
    """Recursively validate that an object contains only allowed types."""
    if isinstance(obj, dict):
        # Check that all keys are strings
        for key, value in obj.items():
            if not isinstance(key, str):
                raise ContractError("not_canonical", f"Dictionary keys must be strings, found {type(key).__name__} at {path}")
            _validate_canonical(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            _validate_canonical(value, f"{path}[{i}]")
    elif isinstance(obj, (str, int, bool)):
        # These are allowed
        pass
    elif isinstance(obj, float):
        # Check for finite floats
        if not (obj == obj and obj != float('inf') and obj != float('-inf')):
            raise ContractError("not_canonical", f"Float values must be finite, found {obj} at {path}")
    elif obj is None:
        # None is allowed
        pass
    else:
        # Everything else is not allowed
        raise ContractError("not_canonical", f"Object of type {type(obj).__name__} is not allowed at {path}")

def canonical_digest(obj: Any) -> str:
    """Calculate the canonical SHA-256 digest of an object."""
    # First validate that the object contains only allowed types
    _validate_canonical(obj)
    
    # Convert to canonical JSON
    canonical_json = json.dumps(obj, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
    
    # Calculate SHA-256 hash
    sha256_hash = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    return f"sha256:{sha256_hash}"

def make_id(prefix: str, payload: Any) -> str:
    """Create an ID from a prefix and payload.
    
    Args:
        prefix: A string of 2 to 6 lowercase ASCII letters a-z
        payload: The payload to digest
        
    Returns:
        A string in the format "prefix-digest" where digest is the first 12 hex chars of canonical_digest(payload)
        
    Raises:
        ContractError: If prefix is not a valid string
    """
    # Check that prefix is a string
    if not isinstance(prefix, str):
        raise ContractError("bad_prefix", f"Prefix must be a string, got {type(prefix).__name__}")
    
    # Check that prefix length is between 2 and 6
    if not (2 <= len(prefix) <= 6):
        raise ContractError("bad_prefix", f"Prefix must be between 2 and 6 characters long, got {len(prefix)}")
    
    # Check that prefix contains only lowercase ASCII letters a-z
    if not re.fullmatch(r"[a-z]+", prefix):
        raise ContractError("bad_prefix", f"Prefix must contain only lowercase ASCII letters a-z, got '{prefix}'")
    
    # Calculate the canonical digest and return prefix with first 12 hex chars
    digest = canonical_digest(payload)
    # Remove the "sha256:" prefix and take first 12 characters
    return f"{prefix}-{digest[7:19]}"

def seal(record: Dict[str, Any], spec: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """Seal a record by validating it and adding its digest.
    
    Args:
        record: The record to seal
        spec: The specification to validate against
        
    Returns:
        A dict with "record" and "digest" keys
    """
    # Validate the record
    validated_record = validate_record(record, spec)
    
    # Calculate the digest of the validated record
    digest = canonical_digest(validated_record)
    
    # Return the sealed envelope
    return {"record": validated_record, "digest": digest}

def open_sealed(sealed: Dict[str, Any], spec: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """Open a sealed record and verify its digest.
    
    Args:
        sealed: A dict with "record" and "digest" keys
        spec: The specification to validate against
        
    Returns:
        The validated record
        
    Raises:
        ContractError: If sealed is not a valid envelope or digest doesn't match
    """
    # Check that sealed is a dict with exactly "record" and "digest" keys
    if not isinstance(sealed, dict):
        raise ContractError("bad_envelope", f"Sealed must be a dict, got {type(sealed).__name__}")
    
    if set(sealed.keys()) != {"record", "digest"}:
        raise ContractError("bad_envelope", f"Sealed must have exactly 'record' and 'digest' keys, got {list(sealed.keys())}")
    
    # Validate the record
    validated_record = validate_record(sealed["record"], spec)
    
    # Calculate the digest of the validated record
    calculated_digest = canonical_digest(validated_record)
    
    # Compare with stored digest
    if calculated_digest != sealed["digest"]:
        raise ContractError("digest_mismatch", "Record digest does not match stored digest")
    
    # Return the validated record
    return validated_record