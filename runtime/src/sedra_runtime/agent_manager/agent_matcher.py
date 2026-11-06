from .agent_contracts import ContractError

def _validate_version_str(version_str):
    """Validate that version string is in format '<n>.<n>.<n>' with ASCII digits only."""
    if not isinstance(version_str, str):
        raise ContractError("bad_version", f"Version must be a string, got {type(version_str).__name__}")
    
    parts = version_str.split('.')
    
    if len(parts) != 3:
        raise ContractError("bad_version", f"Version must be in the format '<major>.<minor>.<patch>', got '{version_str}'")
    
    for part in parts:
        if not part or not part.isdigit():
            raise ContractError("bad_version", f"Version parts must be non-empty integers using ASCII digits only, got '{version_str}'")

def version_at_least(version, minimum):
    """Check if version is greater than or equal to minimum."""
    _validate_version_str(version)
    _validate_version_str(minimum)
    
    version_parts = [int(x) for x in version.split('.')]
    minimum_parts = [int(x) for x in minimum.split('.')]
    
    for v, m in zip(version_parts, minimum_parts):
        if v > m:
            return True
        if v < m:
            return False
    
    # All parts are equal, so version >= minimum
    return True


def _validate_qualification(qualification):
    """Validate that qualification is a valid string."""
    if not isinstance(qualification, str):
        raise ContractError("bad_qualification", f"Qualification must be a string, got {type(qualification).__name__}")
    
    valid_qualifications = {"UNVERIFIED", "VERIFIED", "PROVEN", "TRUSTED"}
    if qualification not in valid_qualifications:
        raise ContractError("bad_qualification", f"Invalid qualification '{qualification}'")


def qualification_rank(q):
    """Return the rank of a qualification."""
    _validate_qualification(q)
    
    rank_map = {
        "UNVERIFIED": 0,
        "VERIFIED": 1,
        "PROVEN": 2,
        "TRUSTED": 3
    }
    
    return rank_map[q]


def _get_candidate_capability_versions(candidate, capability_id):
    """Get all versions of a capability from a candidate."""
    versions = []
    for cap in candidate.get("capabilities", []):
        if cap.get("id") == capability_id:
            versions.append(cap.get("version"))
    return versions


def _get_candidate_capability_with_highest_version(candidate, capability_id):
    """Get the capability with the highest version for a given id."""
    versions = _get_candidate_capability_versions(candidate, capability_id)
    if not versions:
        return None
    
    # Find the highest version
    highest_version = versions[0]
    for version in versions[1:]:
        if version_at_least(version, highest_version):
            highest_version = version
    
    # Return the first capability with the highest version
    for cap in candidate.get("capabilities", []):
        if cap.get("id") == capability_id and cap.get("version") == highest_version:
            return cap
    return None


def _resource_unknown(requested, free):
    """Check if any requested resource has unknown free amount."""
    if free is None:
        # If free is None, any requested resource with positive amount is unknown
        for resource, needed in requested.items():
            if needed is not None and needed > 0:
                return True
        return False
    for resource, needed in requested.items():
        if needed is not None and needed > 0:
            if resource not in free or free[resource] is None:
                return True
    return False


def _resource_exceeded(requested, free):
    """Check if any requested resource needs more than is free."""
    if free is None:
        # If free is None, any requested resource with positive amount exceeds (since we don't know free)
        for resource, needed in requested.items():
            if needed is not None and needed > 0:
                return True
        return False
    for resource, needed in requested.items():
        if needed is not None and needed > 0:
            if resource not in free or free[resource] is None or free[resource] < needed:
                return True
    return False


def resource_fit(requested, free):
    """Calculate resource fit between requested and free amounts.
    
    Args:
        requested: dict of resource name -> needed amount
        free: dict of free amounts after system reserve, or None
        
    Returns:
        dict with "state", "fit", and "max_ratio" keys
    """
    # Check for unknown resources first
    if _resource_unknown(requested, free):
        return {"state": "resource_unknown", "fit": None, "max_ratio": None}
    
    # Check for exceeded resources
    if _resource_exceeded(requested, free):
        return {"state": "queued_resource", "fit": None, "max_ratio": None}
    
    # Calculate fit and max_ratio
    counted_resources = 0
    min_fit = 1.0
    max_ratio = 0.0
    
    for resource, needed in requested.items():
        if needed is not None and needed > 0:
            counted_resources += 1
            free_amount = free.get(resource, 0) if free is not None else 0
            if free_amount > 0:
                ratio = float(needed) / float(free_amount)
                fit = 1.0 - ratio
                min_fit = min(min_fit, fit)
                max_ratio = max(max_ratio, ratio)
            else:
                # If free is 0, fit is 0 and max_ratio is infinity
                min_fit = 0.0
                max_ratio = float('inf')
    
    # If no counted resources, fit is 1.0 and max_ratio is 0.0
    if counted_resources == 0:
        min_fit = 1.0
        max_ratio = 0.0
    
    return {"state": "ok", "fit": min_fit, "max_ratio": max_ratio}


def _fit_for_purpose(candidate, requirement):
    """Calculate fit for purpose score."""
    can_list = requirement.get("can", [])
    
    # If can is empty or missing, return 1.0
    if not can_list:
        return 1.0
    
    total_weight = 0
    satisfied_weight = 0
    
    for item in can_list:
        capability_id = item.get("id")
        weight = item.get("weight", 1)
        minimum_version = item.get("minimum_version")
        
        total_weight += weight
        
        # Check if candidate has capability with that id and version
        for cap in candidate.get("capabilities", []):
            if cap.get("id") == capability_id:
                if minimum_version is None or version_at_least(cap.get("version"), minimum_version):
                    satisfied_weight += weight
                    break
    
    # If no weights, return 1.0
    if total_weight == 0:
        return 1.0
    
    return satisfied_weight / total_weight


def _success_rate(candidate):
    """Calculate success rate score."""
    stats = candidate.get("stats", {})
    successes = stats.get("successes", 0)
    runs = stats.get("runs", 0)
    
    # (s + 1) / (n + 2)
    return (successes + 1) / (runs + 2)


def _resource_fit_score(candidate, snapshot):
    """Calculate resource fit score."""
    resource_result = resource_fit(candidate.get("resources", {}), snapshot)
    
    # If state is not "ok", return 0.0
    if resource_result.get("state") != "ok":
        return 0.0
    
    # Return the fit value
    return resource_result.get("fit", 0.0)


def _qualification_score(candidate):
    """Calculate qualification score."""
    qualification = candidate.get("qualification")
    
    qualification_map = {
        "UNVERIFIED": 0.0,
        "VERIFIED": 0.5,
        "PROVEN": 0.8,
        "TRUSTED": 1.0
    }
    
    return qualification_map.get(qualification, 0.0)


def _availability_score(candidate):
    """Calculate availability score."""
    availability = candidate.get("available", "")
    
    availability_map = {
        "now": 1.0,
        "sequential": 0.5
    }
    
    return availability_map.get(availability, 0.0)


def score_candidate(candidate, requirement, snapshot):
    """Score a candidate based on requirement and snapshot.
    
    Returns a dict with "score" and "components" keys.
    Score is weighted sum of components: 30*fit_for_purpose + 25*success_rate + 20*resource_fit + 15*qualification + 10*availability
    """
    # Calculate individual components
    fit_for_purpose = _fit_for_purpose(candidate, requirement)
    success_rate = _success_rate(candidate)
    resource_fit_score = _resource_fit_score(candidate, snapshot)
    qualification = _qualification_score(candidate)
    availability = _availability_score(candidate)
    
    # Calculate weighted score
    score = (30 * fit_for_purpose + 
             25 * success_rate + 
             20 * resource_fit_score + 
             15 * qualification + 
             10 * availability)
    
    # Round to 2 decimal places
    score = round(score, 2)
    
    return {
        "score": score,
        "components": {
            "fit_for_purpose": fit_for_purpose,
            "success_rate": success_rate,
            "resource_fit": resource_fit_score,
            "qualification": qualification,
            "availability": availability
        }
    }


def hard_filter(candidate, requirement):
    """Filter candidates based on hard requirements.
    
    Returns a list of exclusion reasons. An empty list means the candidate passes.
    Each reason is a dict with "reason_code", "requirement", and "candidate".
    """
    reasons = []
    
    # Check 1: lifecycle
    if candidate.get("lifecycle") != "ACTIVE":
        reasons.append({
            "reason_code": "lifecycle",
            "requirement": "ACTIVE",
            "candidate": candidate.get("lifecycle")
        })
    
    # Check 2: admission
    admission = candidate.get("admission")
    if isinstance(admission, dict) and admission.get("revoked") is True:
        reasons.append({
            "reason_code": "admission_revoked",
            "requirement": "valid",
            "candidate": "revoked"
        })
    elif not isinstance(admission, dict) or admission.get("valid") != True:
        reasons.append({
            "reason_code": "admission_invalid",
            "requirement": "valid",
            "candidate": "invalid"
        })
    
    # Check 3: qualification
    candidate_qualification = candidate.get("qualification")
    min_qualification = requirement.get("min_qualification")
    
    # Unknown candidate qualification counts as lower than everything
    if candidate_qualification is None:
        candidate_rank = -1
    else:
        try:
            candidate_rank = qualification_rank(candidate_qualification)
        except ContractError:
            # Invalid qualification counts as lower than everything
            candidate_rank = -1
    
    try:
        min_rank = qualification_rank(min_qualification)
    except ContractError:
        # Invalid min_qualification, but we still want to check
        min_rank = -1
    
    if candidate_rank < min_rank:
        reasons.append({
            "reason_code": "qualification_too_low",
            "requirement": min_qualification,
            "candidate": candidate_qualification
        })
    
    # Check 4: must requirements
    must_list = requirement.get("must", [])
    for must_req in must_list:
        capability_id = must_req.get("id")
        minimum_version = must_req.get("minimum_version")
        
        # Check if candidate has capability with that id
        capability_versions = _get_candidate_capability_versions(candidate, capability_id)
        if not capability_versions:
            reasons.append({
                "reason_code": "missing_capability",
                "requirement": capability_id,
                "candidate": None
            })
        else:
            # Find capabilities that satisfy the minimum version
            satisfying_caps = []
            for cap in candidate.get("capabilities", []):
                if cap.get("id") == capability_id and version_at_least(cap.get("version"), minimum_version):
                    satisfying_caps.append(cap)
            
            if not satisfying_caps:
                # Find the highest version of this capability
                highest_version = None
                for version in capability_versions:
                    if highest_version is None or version_at_least(version, highest_version):
                        highest_version = version
                
                reasons.append({
                    "reason_code": "version_incompatible",
                    "requirement": minimum_version,
                    "candidate": highest_version
                })
            else:
                # Take the first satisfying capability
                cap = satisfying_caps[0]
                side_effect = cap.get("side_effect")
                
                # Check if side_effect is valid
                valid_side_effects = {
                    "read_only", "proposal_only", "preview", 
                    "reversible_write", "destructive_write", 
                    "external_side_effect", "privileged"
                }
                
                if side_effect is None or side_effect not in valid_side_effects:
                    reasons.append({
                        "reason_code": "effect_unclassified",
                        "requirement": capability_id,
                        "candidate": side_effect
                    })
                elif side_effect not in requirement.get("effects_allowed", []):
                    reasons.append({
                        "reason_code": "effect_not_allowed",
                        "requirement": capability_id,
                        "candidate": side_effect
                    })
    
    return reasons


def _get_missing_capabilities(requirement, candidates):
    """Get list of capability IDs from requirement that are missing from candidates."""
    must_list = requirement.get("must", [])
    must_ids = {must_req.get("id") for must_req in must_list}
    
    # Get all capability IDs from candidates
    candidate_ids = set()
    for candidate in candidates:
        for cap in candidate.get("capabilities", []):
            candidate_ids.add(cap.get("id"))
    
    # Return missing IDs
    return list(must_ids - candidate_ids)


def _get_satisfying_capabilities(requirement, candidates):
    """Get list of capability IDs from requirement that have satisfying candidates."""
    must_list = requirement.get("must", [])
    satisfying_ids = set()
    
    for must_req in must_list:
        capability_id = must_req.get("id")
        minimum_version = must_req.get("minimum_version")
        
        # Check if any candidate has this capability with satisfying version
        for candidate in candidates:
            for cap in candidate.get("capabilities", []):
                if cap.get("id") == capability_id and version_at_least(cap.get("version"), minimum_version):
                    satisfying_ids.add(capability_id)
                    break
    
    return list(satisfying_ids)


def match(requirement, candidates, snapshot):
    """Match candidates against a requirement.
    
    Returns a dict with keys "matcher_version", "eligible", "excluded", "queued", "gaps".
    """
    # Initialize result structure
    result = {
        "matcher_version": "1",
        "eligible": [],
        "excluded": [],
        "queued": [],
        "gaps": []
    }
    
    # Process each candidate
    for candidate in candidates:
        agent_id = candidate.get("agent_id")
        
        # Apply hard filter
        reasons = hard_filter(candidate, requirement)
        if reasons:
            result["excluded"].append({
                "agent_id": agent_id,
                "reasons": reasons
            })
            continue
        
        # Check resource fit
        resource_result = resource_fit(candidate.get("resources", {}), snapshot)
        state = resource_result.get("state")
        if state == "resource_unknown" or state == "queued_resource":
            result["queued"].append({
                "agent_id": agent_id,
                "reason_code": state
            })
            continue
        
        # Candidate is eligible - score it
        score_result = score_candidate(candidate, requirement, snapshot)
        result["eligible"].append({
            "agent_id": agent_id,
            "score": score_result["score"],
            "components": score_result["components"],
            "max_ratio": resource_result["max_ratio"]
        })
    
    # Sort results
    result["eligible"].sort(key=lambda x: (-x["score"], x["max_ratio"], x["agent_id"]))
    result["excluded"].sort(key=lambda x: x["agent_id"])
    result["queued"].sort(key=lambda x: x["agent_id"])
    
    # Calculate gaps
    if not result["eligible"] and not result["queued"]:
        missing_capabilities = _get_missing_capabilities(requirement, candidates)
        if missing_capabilities:
            result["gaps"] = [{"missing_capabilities": sorted(missing_capabilities)}]
    
    return result