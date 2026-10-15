"""Path health for GUPPI's own VM and prepared candidates. Read-only: it reports, it never changes anything.

Why (2026-10-02, two real failures on the Captain's PC):
  1. msb (microsandbox 0.7.4) is not long-path aware. It writes files such as
     <backend_home>\\sandboxes\\<vm name>\\runtime\\.runtime-boot-id.<pid>.<number>.tmp
     A 154-character backend_home plus a 43-character VM name gave 262 characters and the VM did not start.
     Measured: everything after backend_home and the VM name adds MSB_SUFFIX = 65 characters.
  2. After the project folder was renamed, prepared candidates still pointed at the old folder (their `host_root`),
     so they had to be generated again.

Only the standard library may be used. Paths are Windows-style strings; compare them case-insensitively and treat
"/" and "\\" as the same separator.
"""

MSB_SUFFIX = 65          # measured, see above
WINDOWS_LIMIT = 260      # MAX_PATH; the longest usable path is WINDOWS_LIMIT - 1 characters


def vm_path_budget(backend_home, name_length=18, limit=WINDOWS_LIMIT):
    """How long the longest path of a VM will be.

    Returns {"longest": int, "limit": limit, "spare": int, "ok": bool} where
    longest = len(backend_home) + name_length + MSB_SUFFIX, spare = (limit - 1) - longest, ok = spare >= 0.
    A trailing separator on backend_home does not count."""
    # Remove any trailing path separators (both \\ and /) – they do not count towards the length
    bh = backend_home.rstrip("\\/")
    longest = len(bh) + name_length + MSB_SUFFIX
    spare = (limit - 1) - longest
    ok = spare >= 0
    return {"longest": longest, "limit": limit, "spare": spare, "ok": ok}


def _normalize_path(p):
    """Normalize a Windows path for comparison.

    * Replace forward slashes with backslashes.
    * Strip trailing separators.
    * Convert to lower case for case-insensitive comparison.
    """
    # Replace forward slashes with backslashes
    p = p.replace("/", "\\")
    # Strip trailing separators
    p = p.rstrip("\\")
    # Convert to lower case
    return p.lower()


def stale_bindings(current_root, reports):
    """Mission ids of prepared candidates that are bound to another folder.

    `reports` is a list of dicts {"mission_id": str, "host_root": str}. A report is stale when its host_root is not
    current_root itself and not inside it. A sibling folder whose name only starts the same ("...\\GUPPI_OS2") is NOT inside.
    Returns the stale mission ids sorted, without duplicates."""
    norm_current = _normalize_path(current_root)
    stale_ids = set()
    for report in reports:
        mission_id = report.get("mission_id")
        host_root = _normalize_path(report.get("host_root", ""))
        # If host_root is exactly the current root, it is not stale
        if host_root == norm_current:
            continue
        # If host_root starts with current_root + separator, it is inside
        # Ensure separator is backslash
        sep = "\\"
        if host_root.startswith(norm_current + sep):
            continue
        stale_ids.add(mission_id)
    return sorted(stale_ids)


def path_health(current_root, backend_home, reports, name_length=18, limit=WINDOWS_LIMIT):
    """One report: {"status": "OK" | "ATTENTION", "vm_path": <vm_path_budget>, "stale_missions": [...], "actions": [...]}.

    actions (in this order, only those that apply):
      "shorten_project_path"  when the VM path budget is not ok
      "regenerate_candidates" when there are stale missions
    status is "OK" when there are no actions, otherwise "ATTENTION"."""
    vm_path = vm_path_budget(backend_home, name_length=name_length, limit=limit)
    stale_missions = stale_bindings(current_root, reports)
    actions = []
    if not vm_path["ok"]:
        actions.append("shorten_project_path")
    if stale_missions:
        actions.append("regenerate_candidates")
    status = "OK" if not actions else "ATTENTION"
    return {
        "status": status,
        "vm_path": vm_path,
        "stale_missions": stale_missions,
        "actions": actions,
    }
