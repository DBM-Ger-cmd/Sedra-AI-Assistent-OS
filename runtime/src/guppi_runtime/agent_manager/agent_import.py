import re
import hashlib
from .agent_contracts import ContractError

def parse_semver(text):
    if not isinstance(text, str):
        raise ContractError("bad_version", f"Version must be a string, got {type(text).__name__}")
    
    parts = text.split('.')
    
    if len(parts) != 3:
        raise ContractError("bad_version", f"Version must have exactly 3 parts separated by dots, got '{text}'")
    
    result = []
    for i, part in enumerate(parts):
        if not isinstance(part, str):
            raise ContractError("bad_version", f"Version part {i+1} must be a string, got {type(part).__name__}")
        
        if not part:
            raise ContractError("bad_version", f"Version part {i+1} cannot be empty, got '{text}'")
        
        if not re.fullmatch(r"[0-9]+", part):
            raise ContractError("bad_version", f"Version part {i+1} must contain only ASCII digits 0-9, got '{part}'")
        
        result.append(int(part))
    
    return tuple(result)


def _is_valid_id_pattern(id_str):
    if not isinstance(id_str, str):
        return False
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{2,127}", id_str):
        return False
    return True


def _is_safe_path(path):
    if not isinstance(path, str):
        return False
    if not path:
        return False
    if path.startswith('/'):
        return False
    if '\\' in path:
        return False
    if ':' in path:
        return False
    if '\x00' in path:
        return False
    segments = path.split('/')
    for segment in segments:
        if segment == '.' or segment == '..':
            return False
    return True


def _check_soul_fields(template):
    if not isinstance(template, dict):
        return ["soul_missing"]
    if "soul" not in template or not isinstance(template["soul"], dict):
        return ["soul_missing"]
    
    soul = template["soul"]
    required_fields = ["path", "version", "sha256"]
    for field in required_fields:
        if field not in soul:
            return ["soul_missing"]
    
    return []


def check_soul(template, files):
    problem_codes = _check_soul_fields(template)
    if problem_codes:
        return problem_codes
    
    soul = template["soul"]
    
    path = soul["path"]
    if not _is_safe_path(path):
        return ["soul_path"]
    
    if not isinstance(files, dict):
        return ["soul_file"]
    if path not in files:
        return ["soul_file"]
    if not isinstance(files[path], bytes):
        return ["soul_file"]
    
    file_bytes = files[path]
    expected_hash = soul["sha256"]
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        return ["soul_hash"]
    if not all(c in '0123456789abcdef' for c in expected_hash):
        return ["soul_hash"]
    
    actual_hash = hashlib.sha256(file_bytes).hexdigest()
    if actual_hash != expected_hash:
        return ["soul_hash"]
    
    return []


def template_ref(template):
    if not isinstance(template, dict):
        return None
    
    if "id" not in template or not isinstance(template["id"], str):
        return None
    
    if "version" not in template or not isinstance(template["version"], str):
        return None
    
    if not _is_valid_id_pattern(template["id"]):
        return None
    
    try:
        version_tuple = parse_semver(template["version"])
    except ContractError:
        return None
    
    return f"{template['id']}@{template['version']}"


def check_permissions(template):
    if not isinstance(template, dict):
        return ["permissions_missing"]
    
    if "permissions" not in template:
        return ["permissions_missing"]
    
    perm = template["permissions"]
    if not isinstance(perm, dict):
        return ["permissions_missing"]
    
    problems = set()
    
    if "tools_allowed" not in perm or not isinstance(perm["tools_allowed"], list):
        problems.add("tools_allowed_type")
    else:
        tools = template.get("tools", [])
        if isinstance(tools, list):
            valid_tool_ids = set()
            for tool in tools:
                if isinstance(tool, dict) and "id" in tool:
                    valid_tool_ids.add(tool["id"])
            
            for tool_id in perm["tools_allowed"]:
                if not isinstance(tool_id, str):
                    problems.add("tools_allowed_type")
                    break
                if tool_id not in valid_tool_ids:
                    problems.add("tool_not_declared")
                    break
    
    if "workspace_mode" not in perm or perm["workspace_mode"] not in ("none", "read_only", "mission_write"):
        problems.add("workspace_mode")
    
    if "network_mode" not in perm or perm["network_mode"] != "deny":
        problems.add("network_not_denied")
    
    if "external_write" not in perm or perm["external_write"] is not False:
        problems.add("external_write_not_allowed")
    
    if "privileged" not in perm or perm["privileged"] is not False:
        problems.add("privileged_not_allowed")
    
    capabilities = template.get("capabilities", [])
    if isinstance(capabilities, list):
        for cap in capabilities:
            if isinstance(cap, dict) and "side_effect" in cap:
                side_effect = cap["side_effect"]
                if side_effect not in (
                    "read_only", "proposal_only", "preview", "reversible_write", 
                    "destructive_write", "external_side_effect", "privileged"
                ):
                    problems.add("unknown_effect")
                if side_effect in ("destructive_write", "external_side_effect", "privileged"):
                    problems.add("effect_not_allowed")
            else:
                problems.add("unknown_effect")
    
    return sorted(list(problems))


def preview_template(template, files):
    if not isinstance(template, dict):
        return {
            "ok": False,
            "ref": None,
            "trust": "UNVERIFIED",
            "problems": ["not_a_template"]
        }
    
    problems = set()
    if template.get("schema_version") != "guppi.agent-template/v1":
        problems.add("schema_version")
    
    if "id" not in template or not isinstance(template["id"], str):
        problems.add("bad_id")
    elif not _is_valid_id_pattern(template["id"]):
        problems.add("bad_id")
    
    if "version" not in template or not isinstance(template["version"], str):
        problems.add("bad_version")
    else:
        try:
            parse_semver(template["version"])
        except ContractError:
            problems.add("bad_version")
    
    initial_qualification = template.get("initial_qualification")
    if initial_qualification is None or initial_qualification not in ("DRAFT", "UNVERIFIED"):
        problems.add("claimed_trust")
    
    problems.update(check_soul(template, files))
    
    problems.update(check_permissions(template))
    
    return {
        "ok": len(problems) == 0,
        "ref": template_ref(template),
        "trust": "UNVERIFIED",
        "problems": sorted(list(problems))
    }