"""GUPPI Chat, steps 1 and 2 of docs/AUFTRAG_GUPPI_CHAT_AUSBAU_2026-10-13.md (Captain 2026-10-13: window like the Claude Desktop app; what is not too big, GUPPI builds).
Step 1: `cchat_store.py`, sessions as files (pure logic, directory as argument; judged in the microVM). Step 2: `sse.py` (server side frames) and `cchat_stream.js` (browser side
parser, classic script, judged on the host with node). Claude wires both into uix_server.py and claude_chat.js after acceptance. Claude wrote this file, the hidden tests and the
references (benchmarks/devvm_refs/cchat_store, benchmarks/devvm_refs/cchat_stream)."""

NOTES = '''# Notes for the chat steps
Python: standard library only, no network, files only inside the given directory. JavaScript: a CLASSIC script (no modules, no import/export, no DOM access at the top level);
functions become globals of the page. Never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
'''

STORE_1 = r'''
import tempfile, os, json
from pathlib import Path
from cchat_store import ChatStore, valid_id
for ok in ("1760000000000", "1234567890", "1234567890123456"):
    assert valid_id(ok) is True
for bad in ("123456789", "12345678901234567", "12345abc90", "1760000000000\n", "../1760000000", "", None, 1760000000000, "17600 00000"):
    assert valid_id(bad) is False
root = Path(tempfile.mkdtemp()) / "new" / "chats"
s = ChatStore(root)
assert root.is_dir()
assert s.list() == [] and s.get("1760000000001") is None and s.delete("1760000000001") is False
a = s.put("1760000000001", {"title": "  Hallo  ", "updated": 5, "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ja", "model": "qwen"}]})
assert a == {"id": "1760000000001", "title": "Hallo", "updated": 5, "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ja", "model": "qwen"}]}
assert s.get("1760000000001") == a
assert (root / "1760000000001.json").is_file() and json.loads((root / "1760000000001.json").read_text(encoding="utf-8")) == a
s.put("1760000000002", {"title": "", "updated": 9, "messages": []})
s.put("1760000000003", {"title": "Mitte", "updated": 7, "messages": [{"role": "user", "content": "x"}]})
assert s.list() == [{"id": "1760000000002", "title": "Neuer Chat", "updated": 9, "count": 0}, {"id": "1760000000003", "title": "Mitte", "updated": 7, "count": 1}, {"id": "1760000000001", "title": "Hallo", "updated": 5, "count": 2}]
s.put("1760000000001", {"title": "Neu", "updated": 5, "messages": []})
assert [r["id"] for r in s.list()] == ["1760000000002", "1760000000003", "1760000000001"] and s.get("1760000000001")["title"] == "Neu"
s.put("1760000000004", {"title": "gleich", "updated": 9, "messages": []})
assert [r["id"] for r in s.list()][:2] == ["1760000000004", "1760000000002"]
assert s.delete("1760000000004") is True and s.delete("1760000000004") is False and s.get("1760000000004") is None
assert sorted(p.name for p in root.iterdir()) == ["1760000000001.json", "1760000000002.json", "1760000000003.json"]
for bad_id in ("../x", "abc", "", None, "123456789", "1760000000000\n"):
    try:
        s.put(bad_id, {"title": "t", "messages": []}); assert False
    except ValueError as e:
        assert str(e) == "invalid_id"
    assert s.get(bad_id) is None and s.delete(bad_id) is False
print("ok")
'''

STORE_2 = r'''
import tempfile, os, json
from pathlib import Path
from cchat_store import ChatStore
root = Path(tempfile.mkdtemp())
s = ChatStore(str(root))
for bad in (None, "x", 5, [], {"title": "t"}, {"title": "t", "messages": "no"}, {"messages": None}):
    try:
        s.put("1760000000001", bad); assert False
    except ValueError as e:
        assert str(e) == "invalid_session"
assert list(root.iterdir()) == []
long = s.put("1760000000001", {"title": "T" * 200, "updated": True, "messages": [
    {"role": "user", "content": "u" * 30000}, {"role": "system", "content": "x"}, {"role": "user", "content": 5}, "junk", {"content": "no role"},
    {"role": "user", "content": "k", "model": "m"}, {"role": "assistant", "content": "a", "model": "m" * 200}, {"role": "assistant", "content": "b", "model": 3}]})
assert long["title"] == "T" * 80 and long["updated"] == 0
assert [m["role"] for m in long["messages"]] == ["user", "user", "assistant", "assistant"]
assert len(long["messages"][0]["content"]) == 20000
assert "model" not in long["messages"][1] and long["messages"][2]["model"] == "m" * 80 and "model" not in long["messages"][3]
many = s.put("1760000000002", {"title": "viele", "updated": -4, "messages": [{"role": "user", "content": str(i)} for i in range(250)]})
assert len(many["messages"]) == 200 and many["messages"][0]["content"] == "50" and many["messages"][-1]["content"] == "249" and many["updated"] == 0
src = {"title": "x", "updated": 3, "messages": [{"role": "user", "content": "q"}]}
import copy; before = copy.deepcopy(src); s.put("1760000000003", src); assert src == before
(root / "1760000000009.json").write_text("{kaputt", encoding="utf-8")
(root / "1760000000008.json").write_text("[1, 2]", encoding="utf-8")
(root / "notanid.json").write_text(json.dumps({"title": "n", "messages": []}), encoding="utf-8")
(root / "1760000000007.txt").write_text("x", encoding="utf-8")
assert s.get("1760000000009") is None and s.get("1760000000008") is None
assert sorted(r["id"] for r in s.list()) == ["1760000000001", "1760000000002", "1760000000003"]
assert not any(p.suffix == ".tmp" for p in root.iterdir())
big = ChatStore(Path(tempfile.mkdtemp()))
for i in range(200):
    big.put(str(1760000000000 + i), {"title": str(i), "updated": 100 + i, "messages": []})
assert len(big.list()) == 200
big.put("1760000000500", {"title": "neu", "updated": 400, "messages": []})
ids = [r["id"] for r in big.list()]
assert len(ids) == 200 and ids[0] == "1760000000500" and "1760000000000" not in ids and "1760000000001" in ids
big.put("1760000000199", {"title": "gleiche id", "updated": 500, "messages": []})
ids = [r["id"] for r in big.list()]
assert len(ids) == 200 and ids[0] == "1760000000199" and "1760000000001" in ids
print("ok")
'''

SSE_PY = r'''
import json
from sse import sse_frame, stream_frames
assert sse_frame({"delta": "a"}) == b'data: {"delta":"a"}\n\n'
assert sse_frame({"delta": "Grüße \"x\"\n"}) == 'data: {"delta":"Grüße \\"x\\"\\n"}\n\n'.encode("utf-8")
def frames(deltas, model="m", **kw):
    raw = b"".join(stream_frames(deltas, model, **kw))
    return [json.loads(b[len(b"data: "):]) for b in raw.split(b"\n\n") if b]
assert frames(["Hal", "lo", " Welt"]) == [{"delta": "Hal"}, {"delta": "lo"}, {"delta": " Welt"}, {"done": True, "model": "m", "truncated": False}]
assert frames([]) == [{"done": True, "model": "m", "truncated": False}]
assert frames(["a", "", None, 5, b"x", "b"]) == [{"delta": "a"}, {"delta": "b"}, {"done": True, "model": "m", "truncated": False}]
assert frames(iter(["ab", "cd"])) [-1]["truncated"] is False
assert frames(["abcd", "efgh", "ij"], max_chars=6) == [{"delta": "abcd"}, {"delta": "ef"}, {"done": True, "model": "m", "truncated": True}]
assert frames(["abcd", "efgh"], max_chars=4) == [{"delta": "abcd"}, {"done": True, "model": "m", "truncated": False}]
assert frames(["abcd"], max_chars=4) == [{"delta": "abcd"}, {"done": True, "model": "m", "truncated": False}]
seen = []
def gen():
    for d in ("ab", "cd", "ef", "gh"):
        seen.append(d); yield d
list(stream_frames(gen(), "m", max_chars=4)); assert seen == ["ab", "cd"]
def boom():
    yield "ok"
    raise RuntimeError("x" * 300)
out = frames(boom())
assert out[0] == {"delta": "ok"} and out[1] == {"done": True, "model": "m", "truncated": False, "error": "x" * 200} and len(out) == 2
f = stream_frames(["a"], "m"); assert iter(f) is f
print("ok")
'''

JS_HEAD = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const box = { JSON: JSON, String: String, Array: Array, console: console };
vm.createContext(box); vm.runInContext(fs.readFileSync("cchat_stream.js", "utf8"), box);
const J = x => JSON.parse(JSON.stringify(x));
'''

JS_TEST = r'''
const P = (s) => J(box.parseSse(s));
assert.deepStrictEqual(P(""), { events: [], rest: "" });
assert.deepStrictEqual(P('data: {"delta":"a"}'), { events: [], rest: 'data: {"delta":"a"}' });
assert.deepStrictEqual(P('data: {"delta":"a"}\n\n'), { events: [{ delta: "a" }], rest: "" });
assert.deepStrictEqual(P('data: {"delta":"a"}\n\ndata: {"delta":"b"}\n\ndata: {"del'), { events: [{ delta: "a" }, { delta: "b" }], rest: 'data: {"del' });
assert.deepStrictEqual(P('data: {"delta":"a"}\r\n\r\ndata: {"done":true}\r\n\r\n'), { events: [{ delta: "a" }, { done: true }], rest: "" });
assert.deepStrictEqual(P('data: kaputt\n\ndata: [1]\n\ndata: 5\n\ndata: null\n\n: kommentar\n\nevent: x\n\ndata: {"delta":"ok"}\n\n'), { events: [{ delta: "ok" }], rest: "" });
assert.deepStrictEqual(P('data: {"delta":\ndata: "zwei"}\n\n'), { events: [{ delta: "zwei" }], rest: "" });
assert.deepStrictEqual(P('event: msg\ndata: {"delta":"x"}\nid: 4\n\n'), { events: [{ delta: "x" }], rest: "" });
assert.deepStrictEqual(P('data: {"delta":"Grüße\\n"}\n\n'), { events: [{ delta: "Grüße\n" }], rest: "" });
let buf = "", st = box.newStreamState();
assert.deepStrictEqual(J(st), { text: "", done: false, model: "", truncated: false, error: "" });
for (const chunk of ['data: {"delta":"Hal', 'lo"}\n\ndata: {"delta":" Wel', 't"}\n\ndata: {"done":true,"model":"qwen","trunc', 'ated":true}\n\n']) {
  buf += chunk; const r = box.parseSse(buf); buf = r.rest;
  for (const ev of r.events) st = box.applyEvent(st, ev);
}
assert.deepStrictEqual(J(st), { text: "Hallo Welt", done: true, model: "qwen", truncated: true, error: "" });
const s0 = box.newStreamState(), s1 = box.applyEvent(s0, { delta: "x" });
assert.deepStrictEqual(J(s0), { text: "", done: false, model: "", truncated: false, error: "" }); assert.strictEqual(s1.text, "x");
assert.deepStrictEqual(J(box.applyEvent(s1, { delta: 5 })), J(s1));
assert.deepStrictEqual(J(box.applyEvent(s1, { done: true, model: 3, truncated: "ja" })), { text: "x", done: true, model: "", truncated: false, error: "" });
assert.deepStrictEqual(J(box.applyEvent(s1, { done: false })), J(s1));
assert.deepStrictEqual(J(box.applyEvent(s1, { error: "kaputt", done: true, model: "m", truncated: false })), { text: "x", done: true, model: "m", truncated: false, error: "kaputt" });
assert.deepStrictEqual(J(box.applyEvent(s1, {})), J(s1));
console.log("ok");
'''

STAGES = [
    {"name": "store_basic",
     "task": """Create `cchat_store.py` (Python 3 standard library only) for chat sessions stored as files.
- `valid_id(value)` -> True only for a str made of 10 to 16 ASCII digits and nothing else (no trailing newline); everything else (also non-strings) False.
- `class ChatStore(root)`: root is a str or Path; create the directory (with parents) if it is missing. A session is the file `<root>/<id>.json`.
- `put(session_id, data)`: ValueError("invalid_id") for an invalid id (checked first). Stores the session as UTF-8 JSON (ensure_ascii False) and returns the stored dict {"id", "title", "updated", "messages"}. data must be a dict with a list "messages", otherwise ValueError("invalid_session"). title: the stripped str cut to 80 characters, or "Neuer Chat" when missing, not a str or empty. updated: data["updated"] if it is an int (not a bool) >= 0, else 0. messages: keep the entries that are dicts with role "user" or "assistant" and a str content (content cut to 20000 characters); a kept assistant message keeps "model" only if it is a non-empty str (cut to 80 characters); other keys are dropped; invalid entries are skipped.
- `get(session_id)` -> the stored dict, or None (invalid id, missing file, unreadable or invalid JSON, not a dict with a list "messages").
- `list()` -> [{"id", "title", "updated", "count": number of messages}] of all readable sessions, sorted by updated descending, ties by id descending; files whose name is not `<valid id>.json` and unreadable files are skipped.
- `delete(session_id)` -> True when the file existed and was removed, else False (also for an invalid id).
Never modify the arguments, no comments, no docstrings.""",
     "hidden": {"hidden_cchat_1.py": STORE_1}},
    {"name": "store_limits",
     "task": """Extend `cchat_store.py` (keep everything else working):
- `put` keeps only the LAST 200 messages of a session (after dropping the invalid ones).
- `put` never leaves a half written file: write to `<id>.tmp` in the same directory, then os.replace it onto `<id>.json`; no `.tmp` file stays behind. A rejected put (ValueError) must not create any file.
- At most 200 sessions: before writing a session with a NEW id, if 200 other sessions already exist delete the ones that are oldest by (updated, id) so that 199 others remain; writing an id that already exists never deletes anything.""",
     "hidden": {"hidden_cchat_1.py": STORE_1, "hidden_cchat_2.py": STORE_2}},
    {"name": "sse_py",
     "task": """Create `sse.py` (Python 3 standard library only):
- `sse_frame(obj)` -> bytes: b"data: " + compact JSON of obj (json.dumps with ensure_ascii=False and separators (",", ":"), UTF-8) + b"\\n\\n".
- `stream_frames(deltas, model, max_chars=8000)`: a generator over the iterable `deltas` that yields one frame per text piece: {"delta": piece}. Skip anything that is not a non-empty str. At most max_chars characters in total: cut the piece that crosses the limit exactly at the limit, then stop reading `deltas` at once (do not pull more items). The last frame is always {"done": True, "model": model, "truncated": bool}; truncated is True only when the piece cut at the limit had more text than was kept (reaching the limit exactly is not truncated, and no further item is read to find out). If iterating `deltas` raises an Exception, stop and add "error": str(exception)[:200] to the last frame.""",
     "hidden": {"hidden_cchat_3.py": SSE_PY}},
    {"name": "sse_js",
     "task": """Create `cchat_stream.js` (a classic browser script, see NOTES.md) with:
- `newStreamState()` -> {text: "", done: false, model: "", truncated: false, error: ""}.
- `parseSse(buffer)` -> {events, rest}: convert "\\r\\n" to "\\n" first. Everything up to the LAST blank line ("\\n\\n") is complete: split it into blocks at each "\\n\\n"; for each block take the lines that start with "data: ", remove that prefix and join them with "\\n"; JSON.parse the result; keep it only if it parsed to a plain object (not null, not an array, not a number or string); skip blocks that fail to parse or have no data line (comments, "event:" and "id:" lines are ignored). `rest` is the text after the last blank line (the whole text when there is none), to be put in front of the next chunk.
- `applyEvent(state, ev)` -> a NEW state (never changes state): a str ev.delta is appended to text; ev.done === true sets done, model (ev.model if it is a str, else "") and truncated (true only when ev.truncated === true); a str ev.error sets error; other fields are ignored.""",
     "host_hidden": {"hidden_cchat_4.cjs": JS_HEAD + JS_TEST}},
]
