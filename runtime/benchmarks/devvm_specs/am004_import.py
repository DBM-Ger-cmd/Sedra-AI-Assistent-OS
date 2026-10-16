"""AM-004 (Agent Manager, safe template import preview), third self-development build (2026-10-07). Pure stdlib on already parsed data (the microVM image has no PyYAML; the YAML loading is host glue).
Four small stages with hidden tests written outside the models, and a last stage "all". The workspace is seeded with the accepted AM-002 candidate (`agent_contracts.py`). Build only, no integration."""

NOTES = '''# Notes for agent_import
Pure Python 3 standard library, no file or network access, never modify the arguments, no comments, small private helpers instead of copied checks. Uses `ContractError` from `agent_contracts.py` (do not change that file).
A template is a plain dict (already parsed from YAML); `files` maps a relative path to the bytes of that file. An import preview NEVER trusts anything: the result trust is always "UNVERIFIED", and nothing is executed.
'''

COMMON = r'''
import copy, hashlib
from agent_contracts import ContractError
from agent_import import IMPORTS

SOUL = b"# SOUL\nBe careful.\n"
GOOD = {
    "schema_version": "guppi.agent-template/v1", "id": "guppi.agent.coder", "version": "1.0.0", "role": "Coder",
    "soul": {"path": "SOUL.md", "version": "1.0.0", "sha256": hashlib.sha256(SOUL).hexdigest()},
    "capabilities": [{"id": "guppi.code.candidate", "version": "1.0.0", "side_effect": "reversible_write"}],
    "tools": [{"id": "workspace.read", "version": "1.0.0", "sha256": "a" * 64}, {"id": "tests.run", "version": "1.0.0", "sha256": "b" * 64}],
    "permissions": {"tools_allowed": ["workspace.read", "tests.run"], "workspace_mode": "mission_write", "network_mode": "deny", "external_write": False, "privileged": False},
    "initial_qualification": "DRAFT",
}
FILES = {"SOUL.md": SOUL}


def variant(**changes):
    t = copy.deepcopy(GOOD)
    for k, v in changes.items():
        if v is DELETE: t.pop(k, None)
        else: t[k] = v
    return t


DELETE = object()
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


T1 = r"""
assert parse_semver("1.2.3") == (1, 2, 3) and parse_semver("0.0.10") == (0, 0, 10) and parse_semver("10.20.30") == (10, 20, 30)
for bad in ("1.2", "1.2.3.4", "v1.2.3", "1.2.x", "", " 1.2.3", "1.2.3 ", "1.-2.3", "١.2.3", None, 5, ["1", "2", "3"]):
    try: parse_semver(bad)
    except ContractError as exc: assert exc.code == "bad_version", exc.code
    else: raise AssertionError(f"accepted {bad!r}")
assert template_ref(GOOD) == "guppi.agent.coder@1.0.0"
assert template_ref(variant(id="ab")) is None and template_ref(variant(id="Guppi.Agent")) is None and template_ref(variant(id="1abc")) is None and template_ref(variant(id="a" * 129)) is None
assert template_ref(variant(id="a" * 128)) == "a" * 128 + "@1.0.0"
assert template_ref(variant(version="1.0")) is None and template_ref(variant(id=DELETE)) is None and template_ref(variant(version=DELETE)) is None
assert template_ref(variant(id=5)) is None and template_ref("x") is None and template_ref(None) is None and template_ref([]) is None
assert template_ref(variant(id="a.b-c_d9")) == "a.b-c_d9@1.0.0"
snap = copy.deepcopy(GOOD); template_ref(GOOD); assert GOOD == snap
"""

T2 = r"""
assert check_soul(GOOD, FILES) == []
assert check_soul(GOOD, {"SOUL.md": SOUL + b"tampered"}) == ["soul_hash"]
assert check_soul(GOOD, {}) == ["soul_file"] and check_soul(GOOD, {"other.md": SOUL}) == ["soul_file"]
for p in ("/etc/passwd", "../SOUL.md", "a/../SOUL.md", "a\\SOUL.md", "C:SOUL.md", "", "..", "./../x", "a/./..", "\x00x"):
    t = variant(soul={**GOOD["soul"], "path": p})
    assert check_soul(t, {p: SOUL, "SOUL.md": SOUL}) == ["soul_path"], (p, check_soul(t, {p: SOUL, "SOUL.md": SOUL}))
assert check_soul(variant(soul={**GOOD["soul"], "path": 5}), FILES) == ["soul_path"]
assert check_soul(variant(soul={**GOOD["soul"], "path": "souls/coder/SOUL.md"}), {"souls/coder/SOUL.md": SOUL}) == []
for bad in ("A" * 64, "abc", "z" * 64, 5, None, hashlib.sha256(SOUL).hexdigest().upper()):
    assert check_soul(variant(soul={**GOOD["soul"], "sha256": bad}), FILES) == ["soul_hash"], bad
for bad in (DELETE, None, "SOUL.md", [], {}, {"path": "SOUL.md"}, {"sha256": "a" * 64}):
    assert check_soul(variant(soul=bad), FILES) == ["soul_missing"], bad
assert check_soul("x", FILES) == ["soul_missing"] and check_soul(None, FILES) == ["soul_missing"]
assert check_soul(GOOD, {"SOUL.md": "text"}) == ["soul_file"] and check_soul(GOOD, None) == ["soul_file"]
snap = copy.deepcopy(GOOD); fs = dict(FILES); check_soul(GOOD, FILES); assert GOOD == snap and FILES == fs
"""

T3 = r"""
assert check_permissions(GOOD) == []
assert check_permissions(variant(permissions=DELETE)) == ["permissions_missing"] and check_permissions(variant(permissions=[])) == ["permissions_missing"] and check_permissions("x") == ["permissions_missing"]
def perm(**ch): return variant(permissions={**GOOD["permissions"], **ch})
assert check_permissions(perm(tools_allowed=["workspace.read", "shell.run"])) == ["tool_not_declared"]
assert check_permissions(perm(tools_allowed=["shell.run", "net.get"])) == ["tool_not_declared"]
assert check_permissions(perm(tools_allowed="workspace.read")) == ["tools_allowed_type"] and check_permissions(perm(tools_allowed=[5])) == ["tools_allowed_type"]
assert check_permissions(perm(tools_allowed=[])) == []
assert check_permissions(perm(workspace_mode="write_all")) == ["workspace_mode"]
for m in ("none", "read_only", "mission_write"): assert check_permissions(perm(workspace_mode=m)) == []
assert check_permissions(perm(network_mode="allow")) == ["network_not_denied"] and check_permissions(perm(network_mode=None)) == ["network_not_denied"]
assert check_permissions(perm(external_write=True)) == ["external_write_not_allowed"] and check_permissions(perm(external_write="no")) == ["external_write_not_allowed"]
assert check_permissions(perm(privileged=True)) == ["privileged_not_allowed"] and check_permissions(perm(privileged=0)) == ["privileged_not_allowed"]
p = copy.deepcopy(GOOD["permissions"]); del p["privileged"]
assert check_permissions(variant(permissions=p)) == ["privileged_not_allowed"]
assert check_permissions(perm(network_mode="allow", privileged=True, workspace_mode="x")) == ["network_not_denied", "privileged_not_allowed", "workspace_mode"]
def cap(effect): return variant(capabilities=[{"id": "x.y.z", "version": "1.0.0", "side_effect": effect}])
for e in ("read_only", "proposal_only", "preview", "reversible_write"): assert check_permissions(cap(e)) == [], e
for e in ("destructive_write", "external_side_effect", "privileged"): assert check_permissions(cap(e)) == ["effect_not_allowed"], e
assert check_permissions(cap("delete_everything")) == ["unknown_effect"] and check_permissions(cap(None)) == ["unknown_effect"]
assert check_permissions(variant(capabilities=[])) == [] and check_permissions(variant(capabilities=DELETE)) == []
assert check_permissions(variant(capabilities=["x"])) == ["unknown_effect"]
assert check_permissions(variant(tools=DELETE)) == ["tool_not_declared"]
snap = copy.deepcopy(GOOD); check_permissions(GOOD); assert GOOD == snap
"""

T4 = r"""
r = preview_template(GOOD, FILES)
assert r == {"ok": True, "ref": "guppi.agent.coder@1.0.0", "trust": "UNVERIFIED", "problems": []}, r
bad = preview_template(variant(initial_qualification="TRUSTED"), FILES)
assert bad == {"ok": False, "ref": "guppi.agent.coder@1.0.0", "trust": "UNVERIFIED", "problems": ["claimed_trust"]}, bad
for q in ("PROVEN", "trusted", None, 5): assert preview_template(variant(initial_qualification=q), FILES)["problems"] == ["claimed_trust"], q
for q in ("DRAFT", "UNVERIFIED"): assert preview_template(variant(initial_qualification=q), FILES)["ok"] is True
assert preview_template(variant(initial_qualification=DELETE), FILES)["problems"] == ["claimed_trust"]
assert preview_template(variant(schema_version="guppi.agent-template/v2"), FILES)["problems"] == ["schema_version"]
x = preview_template(variant(id="Bad Id"), FILES); assert x["ref"] is None and x["problems"] == ["bad_id"] and x["ok"] is False
x = preview_template(variant(version="1.x"), FILES); assert x["ref"] is None and x["problems"] == ["bad_version"]
x = preview_template(variant(), {"SOUL.md": b"changed"}); assert x["problems"] == ["soul_hash"] and x["ok"] is False and x["trust"] == "UNVERIFIED"
x = preview_template(variant(initial_qualification="TRUSTED", soul=DELETE, permissions=DELETE), {})
assert x["problems"] == ["claimed_trust", "permissions_missing", "soul_missing"], x
x = preview_template(variant(id="x", schema_version="v0"), {})
assert x["problems"] == ["bad_id", "schema_version", "soul_file"] and x["ref"] is None, x
for junk in (None, "x", 5, [], [GOOD]):
    assert preview_template(junk, FILES) == {"ok": False, "ref": None, "trust": "UNVERIFIED", "problems": ["not_a_template"]}, junk
assert preview_template({}, FILES)["ok"] is False and preview_template({}, FILES)["trust"] == "UNVERIFIED"
for weird in ({"id": object(), "soul": object(), "permissions": {"tools_allowed": object()}, "capabilities": object(), "tools": object()},):
    r = preview_template(weird, FILES); assert r["ok"] is False and r["trust"] == "UNVERIFIED" and r["problems"] == sorted(set(r["problems"]))
snap = copy.deepcopy(GOOD); fs = dict(FILES); preview_template(GOOD, FILES); assert GOOD == snap and FILES == fs
"""

NAMES = "parse_semver, template_ref, check_soul, check_permissions, preview_template"
FULL = T1 + T2 + T3 + T4

STYLE = " No comments. Put repeated checks into small private helpers. Never modify the arguments."

STAGES = [
    {"name": "refs",
     "task": """In this workspace `agent_contracts.py` already exists (do not change it; it has `ContractError(code, message, field=None)` with `.code`). Create `agent_import.py` (Python 3 standard library only, no file or network access).
Add `parse_semver(text) -> tuple`: `text` must be a str of the form "<n>.<n>.<n>" with three non-negative integers made of the ASCII digits 0-9 only (no spaces, signs or other parts), otherwise raise `ContractError("bad_version", ...)`; return the three ints.
Add `template_ref(template) -> str or None`: `template` is a dict; return "<id>@<version>" when `template["id"]` is a str that fully matches the pattern `[a-z][a-z0-9_.-]{2,127}` and `template["version"]` is accepted by `parse_semver`; in every other case (also when `template` is not a dict, or a key is missing or not a str) return None. It never raises.""" + STYLE + """ Add `tests/test_agent_import.py` (unittest) with your own tests.""",
     "hidden": {"hidden_u1.py": hidden("parse_semver, template_ref", T1)}},
    {"name": "soul",
     "task": """In the existing `agent_import.py` (keep the other functions) add `check_soul(template, files) -> list` that returns a sorted list of problem codes (str) and never raises. `files` maps a relative path (str) to the bytes of that file.
`template["soul"]` must be a dict with the keys "path" (str), "version" and "sha256"; if `template` is not a dict, or `soul` is not a dict, or one of the three keys is missing: return exactly ["soul_missing"].
Otherwise: a path that is not a str, is empty, starts with "/", contains a backslash, a colon, a NUL character, or has a ".." or "." segment (segments are the parts between "/") is unsafe: return exactly ["soul_path"].
For a safe path: if `files` is not a dict, or has no entry for the path, or the entry is not `bytes`: return exactly ["soul_file"]. Otherwise the field `sha256` must be a str of exactly 64 lowercase hex characters AND equal `hashlib.sha256(<bytes>).hexdigest()`; if not, return exactly ["soul_hash"]. When everything is fine return [].""" + STYLE + """ Add tests to `tests/test_agent_import.py`.""",
     "hidden": {"hidden_u2.py": hidden("check_soul", T2)}},
    {"name": "permissions",
     "task": """In the existing `agent_import.py` (keep the other functions) add `check_permissions(template) -> list` that returns a sorted list of unique problem codes (str) and never raises.
If `template` is not a dict or `template["permissions"]` is missing or not a dict: return exactly ["permissions_missing"]. Otherwise let `perm` be that dict; add the codes:
- "tools_allowed_type" when `perm["tools_allowed"]` is not a list of str (a missing key counts as an empty list); otherwise "tool_not_declared" (once) when any listed id is not the "id" of an entry in `template["tools"]` (a missing or invalid `tools` counts as no tools; entries that are not dicts are ignored);
- "workspace_mode" when `perm["workspace_mode"]` is not one of "none", "read_only", "mission_write";
- "network_not_denied" when `perm["network_mode"]` is not exactly "deny";
- "external_write_not_allowed" when `perm["external_write"]` is not exactly False (a missing key counts); "privileged_not_allowed" when `perm["privileged"]` is not exactly False (a missing key counts; 0 is not False here, use `is False`);
- for every entry of `template["capabilities"]` (a missing capabilities means none; a non-list counts as none; an entry that is not a dict counts as an unknown effect): its "side_effect" must be one of "read_only", "proposal_only", "preview", "reversible_write", "destructive_write", "external_side_effect", "privileged", otherwise add "unknown_effect"; and when it is one of "destructive_write", "external_side_effect", "privileged" add "effect_not_allowed".""" + STYLE + """ Add tests to `tests/test_agent_import.py`.""",
     "hidden": {"hidden_u3.py": hidden("check_permissions", T3)}},
    {"name": "preview",
     "task": """In the existing `agent_import.py` (keep the other functions) add `preview_template(template, files) -> dict` that never raises and never trusts the template. If `template` is not a dict return exactly {"ok": False, "ref": None, "trust": "UNVERIFIED", "problems": ["not_a_template"]}.
Otherwise the result is {"ok": <no problems>, "ref": template_ref(template), "trust": "UNVERIFIED", "problems": <sorted list of unique codes>} where the problems are the union of: "schema_version" when `template["schema_version"]` is not exactly "guppi.agent-template/v1"; "bad_id" when `template["id"]` is not a str fully matching `[a-z][a-z0-9_.-]{2,127}` (missing counts); "bad_version" when `template["version"]` is not accepted by `parse_semver` (missing counts);
"claimed_trust" when `template["initial_qualification"]` is not "DRAFT" or "UNVERIFIED" (a missing key counts); and everything returned by `check_soul(template, files)` and `check_permissions(template)`. The trust is ALWAYS "UNVERIFIED", whatever the template claims. Reuse the helper functions, do not copy their checks.""" + STYLE + """ Add tests to `tests/test_agent_import.py`.""",
     "hidden": {"hidden_u4.py": hidden("preview_template", T4)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_agent_import.py` and read `agent_import.py` once more. Make sure all functions (parse_semver, template_ref, check_soul, check_permissions, preview_template) work together, that no check is copied into several functions, and that there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_full_u.py": hidden(NAMES, FULL)}},
]
