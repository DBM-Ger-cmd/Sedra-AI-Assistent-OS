"""AM-002 (Agent Manager, neutral contracts), first self-development build (2026-10-06). Built in four small stages in the same workspace, each with its own hidden test written by
Claude (the models never see it): the planner's own check forgets edge cases (docs/DEVVM_PHASE5_BERICHT_2026-10-06.md), so acceptance comes from outside.
Scope is a small, pure-stdlib core of the AM-002 ticket (strict validation, canonical digests, version check, sealed records), not the full contract set.
Build only, no integration: the result stays a candidate under runtime_data/devvm_candidates/."""

NOTES = '''# Notes for agent_contracts
Pure Python 3 standard library, no file or network access, never modify the arguments. Errors are always `ContractError` (a ValueError subclass) with a `code` and an optional `field`.
Part of the GUPPI Agent Manager (ticket AM-002). Built as a candidate only.
'''

COMMON = r'''
import copy
from agent_contracts import IMPORTS

SPEC = {"required": {"name": "str", "count": "int"}, "optional": {"flag": "bool", "tags": "list", "meta": "dict"}}


def raises(code, fn, *args, field="__any__", **kw):
    try:
        fn(*args, **kw)
    except ContractError as exc:
        assert isinstance(exc, ValueError) and exc.code == code, (code, exc.code, str(exc))
        if field != "__any__": assert exc.field == field, (field, exc.field)
        return
    raise AssertionError(f"no ContractError {code}")
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports + ", ContractError").replace("BODY", body)


S1 = r'''
d = canonical_digest({"b": [1, 2, {"z": None, "a": True}], "a": "x"})
assert d == canonical_digest({"a": "x", "b": [1, 2, {"a": True, "z": None}]}), d
assert d.startswith("sha256:") and len(d) == 7 + 64 and all(c in "0123456789abcdef" for c in d[7:]), d
import hashlib
assert canonical_digest({"a": 1}) == "sha256:" + hashlib.sha256(b'{"a":1}').hexdigest()
assert canonical_digest("ä") == "sha256:" + hashlib.sha256('"ä"'.encode("utf-8")).hexdigest()
assert canonical_digest([1, 2]) != canonical_digest([2, 1]) and canonical_digest(1) != canonical_digest("1")
assert canonical_digest(None) == "sha256:" + hashlib.sha256(b"null").hexdigest()
src = {"k": [1, {"x": 2}]}; snap = copy.deepcopy(src); canonical_digest(src); assert src == snap
for bad in (float("nan"), float("inf"), {1: "a"}, {"a": {1, 2}}, [b"x"], (1, 2), {"a": object()}, {"a": [float("-inf")]}):
    raises("not_canonical", canonical_digest, bad)
assert canonical_digest({"a": 1.5}).startswith("sha256:")
'''

S2 = r'''
assert check_version("1.0") == (1, 0) and check_version("1.12") == (1, 12) and check_version("2.3", supported_major=2) == (2, 3)
raises("incompatible_major", check_version, "2.0")
raises("incompatible_major", check_version, "0.9")
raises("incompatible_major", check_version, "1.0", supported_major=3)
for bad in ("1", "v1", "1.", ".1", "1.2.3", "a.b", "", " 1.0", "1.0 ", "1.-1", "١.0", None, 1, 1.0, ["1", "0"]):
    raises("bad_version", check_version, bad)
'''

S3 = r'''
good = {"name": "a", "count": 3}
src = {"name": "a", "count": 3, "flag": False, "tags": ["x"], "meta": {"k": [1]}}
snap = copy.deepcopy(src)
out = validate_record(src, SPEC)
assert out == src and out is not src and out["tags"] is not src["tags"] and out["meta"]["k"] is not src["meta"]["k"] and src == snap
assert validate_record(good, SPEC) == good
raises("unknown_field", validate_record, {**good, "extra": 1}, SPEC, field="extra")
raises("unknown_field", validate_record, {**good, "zeta": 1, "beta": 2}, SPEC, field="beta")
raises("missing_field", validate_record, {"name": "a"}, SPEC, field="count")
raises("missing_field", validate_record, {}, SPEC, field="count")
raises("bad_type", validate_record, {"name": 1, "count": 3}, SPEC, field="name")
raises("bad_type", validate_record, {"name": "a", "count": "3"}, SPEC, field="count")
raises("bad_type", validate_record, {"name": "a", "count": True}, SPEC, field="count")
raises("bad_type", validate_record, {"name": "a", "count": 1.0}, SPEC, field="count")
raises("bad_type", validate_record, {**good, "flag": 1}, SPEC, field="flag")
raises("bad_type", validate_record, {**good, "tags": ("x",)}, SPEC, field="tags")
raises("bad_type", validate_record, {**good, "meta": []}, SPEC, field="meta")
for notdict in (None, [], "x", 3):
    raises("bad_type", validate_record, notdict, SPEC, field=None)
# order: unknown fields first, then missing, then types
raises("unknown_field", validate_record, {"name": 1, "extra": 1}, SPEC, field="extra")
raises("missing_field", validate_record, {"name": 1}, SPEC, field="count")
raises("bad_type", validate_record, {"name": 1, "count": "x", "flag": "y"}, SPEC, field="count")
raises("bad_type", validate_record, {"name": 1, "count": 1, "flag": "y"}, SPEC, field="flag")
'''

S4 = r'''
a = make_id("agt", {"x": 1, "y": [2]})
assert a == make_id("agt", {"y": [2], "x": 1}) and a != make_id("agt", {"x": 2, "y": [2]}) and a != make_id("tpl", {"x": 1, "y": [2]})
assert a.startswith("agt-") and len(a) == 4 + 12 and a[4:] == canonical_digest({"x": 1, "y": [2]})[7:19], a
for bad in ("", "a", "toolong1", "Agt", "ag1", "ag-", "ag t", None, 5):
    raises("bad_prefix", make_id, bad, {})
assert make_id("ab", {}).startswith("ab-") and make_id("abcdef", {}).startswith("abcdef-")
rec = {"name": "coder", "count": 2, "tags": ["a"]}
snap = copy.deepcopy(rec)
env = seal(rec, SPEC)
assert set(env) == {"record", "digest"} and env["record"] == rec and env["record"] is not rec and env["digest"] == canonical_digest(rec) and rec == snap
envsnap = copy.deepcopy(env)
assert open_sealed(env, SPEC) == rec and env == envsnap
raises("unknown_field", seal, {**rec, "bogus": 1}, SPEC, field="bogus")
raises("missing_field", seal, {"name": "x"}, SPEC, field="count")
t = copy.deepcopy(env); t["record"]["count"] = 3
raises("digest_mismatch", open_sealed, t, SPEC)
t = copy.deepcopy(env); t["digest"] = "sha256:" + "0" * 64
raises("digest_mismatch", open_sealed, t, SPEC)
t = copy.deepcopy(env); t["record"]["bogus"] = 1
raises("unknown_field", open_sealed, t, SPEC, field="bogus")
t = copy.deepcopy(env); t["record"]["count"] = "3"
raises("bad_type", open_sealed, t, SPEC, field="count")
for bad in (None, [], "x", {"record": rec}, {"digest": env["digest"]}, {**env, "extra": 1}):
    raises("bad_envelope", open_sealed, bad, SPEC)
'''

NAMES = "ContractError, canonical_digest, check_version, validate_record, make_id, seal, open_sealed"

STAGES = [
    {"name": "digest",
     "task": '''In this workspace create `agent_contracts.py` (pure Python 3 standard library, no file or network access, never modify the arguments).
It defines `class ContractError(ValueError)` with the constructor `ContractError(code, message, field=None)` and the attributes `.code` and `.field`; `str(error)` is "<code>: <message>".
It also defines `canonical_digest(obj) -> str`: the SHA-256 of the canonical JSON of `obj`, returned as "sha256:" followed by the 64 lowercase hex characters. Canonical JSON means keys sorted, no whitespace
(separators "," and ":"), non-ASCII characters NOT escaped, encoded as UTF-8. Only dict (with str keys only, at any depth), list, str, int, finite float, bool and None are allowed (at any depth). Anything else
(tuple, set, bytes, other objects, non-str keys, NaN, infinity) raises `ContractError("not_canonical", ...)`.
Add `tests/test_agent_contracts.py` (unittest) with your own tests.''',
     "hidden": {"hidden_s1.py": hidden("canonical_digest", S1)}},
    {"name": "version",
     "task": '''In the existing `agent_contracts.py` (keep the other functions) add `check_version(version, supported_major=1) -> tuple`. `version` must be a str of the form "<major>.<minor>" with two non-negative integers made of the ASCII
digits 0 to 9 (no spaces, no signs, no other parts). Anything else, including values that are not a str, raises `ContractError("bad_version", ...)`. When the major number differs from `supported_major` raise
`ContractError("incompatible_major", ...)`. Otherwise return `(major, minor)` as ints. Add tests to `tests/test_agent_contracts.py`.''',
     "hidden": {"hidden_s2.py": hidden("check_version", S2)}},
    {"name": "validate_record",
     "task": '''In the existing `agent_contracts.py` (keep the other functions) add `validate_record(data, spec) -> dict`. `spec` is {"required": {field: type_name}, "optional": {field: type_name}} (both keys may be missing and then mean no fields);
`type_name` is one of "str", "int", "bool", "list", "dict". `data` must be a dict, otherwise raise `ContractError("bad_type", ..., field=None)`. Checks in this order, always reporting the first problem with `field` set to the field name:
1. a field of `data` that is in neither `required` nor `optional` (names sorted alphabetically): code "unknown_field"; 2. a required field that is missing (sorted): code "missing_field"; 3. a field whose value has the wrong type (sorted):
code "bad_type". The type "int" does NOT accept a bool or a float; "bool" accepts only a bool. Return a deep copy of `data`; the argument is never modified. Add tests to `tests/test_agent_contracts.py`.''',
     "hidden": {"hidden_s3.py": hidden("validate_record", S3)}},
    {"name": "seal",
     "task": '''In the existing `agent_contracts.py` (keep the other functions) add three functions.
`make_id(prefix, payload) -> str`: `prefix` must be a str of 2 to 6 lowercase ASCII letters a-z, otherwise raise `ContractError("bad_prefix", ...)`; the result is the prefix, a "-", and the first 12 hex characters of `canonical_digest(payload)` (without the "sha256:" part).
`seal(record, spec) -> dict`: validates `record` with `validate_record(record, spec)` and returns `{"record": <the validated copy>, "digest": canonical_digest(<the validated copy>)}`.
`open_sealed(sealed, spec) -> dict`: `sealed` must be a dict with exactly the keys "record" and "digest", otherwise raise `ContractError("bad_envelope", ...)`. Then validate the record with `validate_record` (its errors pass through unchanged),
then compare `canonical_digest(record)` with the stored digest and raise `ContractError("digest_mismatch", ...)` if they differ. Return the validated copy of the record. No argument is modified.
Add tests to `tests/test_agent_contracts.py`.''',
     "hidden": {"hidden_s4.py": hidden(NAMES, S1 + S2 + S3 + S4)}},
]
