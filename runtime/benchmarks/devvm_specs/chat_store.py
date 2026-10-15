"""Chat history that survives a reload (UIX analysis 2026-10-13, proposal 4.1 Nr. 2): the Companion chat (js/chat.js) is empty after F5 or a server restart.
`chat_store.js` is the pure part: pack the history for sessionStorage, unpack and check it (version, age, shape), and a one-line summary for the greeting.
Classic browser script, judged on the host with node. Claude wires it into chat.js after acceptance (save after every turn, restore in initChat, check the
session mission with /api/mission/details). It stores only what the page shows; the runtime state stays in the runtime (guideline of UIX_ROADMAP.md).
Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/chat_store)."""

NOTES = '''# Notes for chat_store.js
A CLASSIC browser script: no modules, no import/export, no DOM or storage access anywhere in the file (the page does the storing). Functions and `var` names become
globals of the page. Never modify the arguments; return new objects. No comments and no docstrings, small helpers instead of copied code.
'''

JS_HEAD = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const box = { Math: Math, JSON: JSON, console: console, Array: Array, isFinite: isFinite };
vm.createContext(box); vm.runInContext(fs.readFileSync("chat_store.js", "utf8"), box);
const plain = v => JSON.parse(JSON.stringify(v));
const H = [{role: "user", content: "Hallo"}, {role: "assistant", content: "Guten Tag, Captain."}, {role: "system", content: "weg"}, {role: "user", content: 7}, "junk", null,
           {role: "user", content: "Plane den Umbau"}];
'''

JS1 = r'''
assert.strictEqual(box.CHAT_STORE_KEY, "guppi.chat.v1");
assert.strictEqual(box.CHAT_STORE_TURNS, 40);
assert.strictEqual(box.CHAT_STORE_MAX_AGE_MS, 7 * 864e5);
assert.strictEqual(box.CHAT_STORE_CHARS, 4000);
const p = plain(box.packChat(H, "M-1", {id: "PRJ-1", name: "Demo"}, 1000));
assert.deepStrictEqual(p, {v: 1, saved: 1000, mission: "M-1", project: {id: "PRJ-1", name: "Demo"},
  history: [{role: "user", content: "Hallo"}, {role: "assistant", content: "Guten Tag, Captain."}, {role: "user", content: "Plane den Umbau"}]});
assert.deepStrictEqual(plain(box.packChat(null, null, null, 5)), {v: 1, saved: 5, mission: null, project: null, history: []});
assert.deepStrictEqual(plain(box.packChat("x", "", undefined, "now")), {v: 1, saved: 0, mission: null, project: null, history: []});
assert.strictEqual(plain(box.packChat([], 12, {id: "a", name: "b"}, 1)).mission, null);
assert.strictEqual(plain(box.packChat([], "M", {id: "", name: "b"}, 1)).project, null);
assert.strictEqual(plain(box.packChat([], "M", {id: "a"}, 1)).project, null);
assert.deepStrictEqual(plain(box.packChat([], "M", {id: "a", name: "b", extra: 1}, 1)).project, {id: "a", name: "b"});
const long = "x".repeat(5000);
assert.strictEqual(plain(box.packChat([{role: "assistant", content: long}], null, null, 1)).history[0].content.length, 4000);
const many = []; for (let i = 0; i < 45; i++) many.push({role: i % 2 ? "assistant" : "user", content: "n" + i});
const kept = plain(box.packChat(many, null, null, 1)).history;
assert.strictEqual(kept.length, 40); assert.strictEqual(kept[0].content, "n5"); assert.strictEqual(kept[39].content, "n44");
const before = JSON.stringify(H); box.packChat(H, "M", {id: "a", name: "b"}, 1); assert.strictEqual(JSON.stringify(H), before);
const turn = {role: "user", content: long}; box.packChat([turn], null, null, 1); assert.strictEqual(turn.content.length, 5000);
console.log("ok");
'''

JS2 = r'''
const saved = JSON.stringify(box.packChat(H, "M-1", {id: "PRJ-1", name: "Demo"}, 1000));
const u = plain(box.unpackChat(saved, 4000));
assert.deepStrictEqual(u, {history: [{role: "user", content: "Hallo"}, {role: "assistant", content: "Guten Tag, Captain."}, {role: "user", content: "Plane den Umbau"}],
  mission: "M-1", project: {id: "PRJ-1", name: "Demo"}, age_ms: 3000});
assert.strictEqual(box.unpackChat(saved, 1000).age_ms, 0);
assert.strictEqual(box.unpackChat(saved, 1000 + 7 * 864e5).age_ms, 7 * 864e5);
assert.strictEqual(box.unpackChat(saved, 1001 + 7 * 864e5), null);
assert.strictEqual(box.unpackChat(saved, 999), null);
assert.strictEqual(box.unpackChat(saved, "4000"), null);
assert.strictEqual(box.unpackChat(null, 4000), null);
assert.strictEqual(box.unpackChat("{nope", 4000), null);
assert.strictEqual(box.unpackChat("[]", 4000), null);
assert.strictEqual(box.unpackChat("null", 4000), null);
assert.strictEqual(box.unpackChat(JSON.stringify({v: 2, saved: 1, history: []}), 4000), null);
assert.strictEqual(box.unpackChat(JSON.stringify({v: 1, saved: "1", history: []}), 4000), null);
assert.deepStrictEqual(plain(box.unpackChat(JSON.stringify({v: 1, saved: 10}), 20)), {history: [], mission: null, project: null, age_ms: 10});
assert.deepStrictEqual(plain(box.unpackChat(JSON.stringify({v: 1, saved: 10, history: "x", mission: 5, project: {id: "a"}}), 20)), {history: [], mission: null, project: null, age_ms: 10});
const bad = JSON.stringify({v: 1, saved: 10, history: [{role: "user", content: "y".repeat(4100)}, {role: "tool", content: "no"}, {role: "assistant"}]});
const ub = plain(box.unpackChat(bad, 10));
assert.strictEqual(ub.history.length, 1); assert.strictEqual(ub.history[0].content.length, 4000);
const many = []; for (let i = 0; i < 50; i++) many.push({role: "user", content: "m" + i});
const um = plain(box.unpackChat(JSON.stringify({v: 1, saved: 0, history: many}), 0)).history;
assert.strictEqual(um.length, 40); assert.strictEqual(um[0].content, "m10");

assert.strictEqual(box.chatSummary([]), "");
assert.strictEqual(box.chatSummary(null), "");
assert.strictEqual(box.chatSummary([{role: "system", content: "x"}]), "");
assert.strictEqual(box.chatSummary(H), "Verlauf mit 3 Nachrichten wiederhergestellt (zuletzt: Plane den Umbau).");
assert.strictEqual(box.chatSummary([{role: "user", content: "Hi"}]), "Verlauf mit 1 Nachricht wiederhergestellt (zuletzt: Hi).");
assert.strictEqual(box.chatSummary([{role: "assistant", content: "Hallo"}, {role: "assistant", content: "Noch da?"}]), "Verlauf mit 2 Nachrichten wiederhergestellt.");
const sixty = "a".repeat(60), sixtyone = "b".repeat(61);
assert.strictEqual(box.chatSummary([{role: "user", content: sixty}]), "Verlauf mit 1 Nachricht wiederhergestellt (zuletzt: " + sixty + ").");
assert.strictEqual(box.chatSummary([{role: "user", content: sixtyone}]), "Verlauf mit 1 Nachricht wiederhergestellt (zuletzt: " + "b".repeat(60) + "…).");
assert.strictEqual(box.chatSummary([{role: "user", content: "erste"}, {role: "assistant", content: "a"}, {role: "user", content: "letzte"}, {role: "assistant", content: "b"}]),
  "Verlauf mit 4 Nachrichten wiederhergestellt (zuletzt: letzte).");
const before = JSON.stringify(H); box.unpackChat(saved, 2000); box.chatSummary(H); assert.strictEqual(JSON.stringify(H), before);
console.log("ok");
'''

STAGES = [
    {"name": "pack",
     "task": """Create `chat_store.js` (a classic browser script, see NOTES.md) with:
- `var CHAT_STORE_KEY = "guppi.chat.v1"`, `var CHAT_STORE_TURNS = 40`, `var CHAT_STORE_MAX_AGE_MS = 7 * 864e5`, `var CHAT_STORE_CHARS = 4000`.
- `packChat(history, mission, project, now)` -> a plain object {v: 1, saved, mission, project, history} that the page will store as JSON:
  saved = now if now is a number, else 0; mission = mission if it is a non-empty string, else null;
  project = {id, name} if project is an object whose id is a non-empty string and whose name is a string (other keys dropped), else null;
  history: from the array history keep only objects whose role is "user" or "assistant" and whose content is a string, as new objects {role, content} with content cut to CHAT_STORE_CHARS characters;
  keep only the LAST CHAT_STORE_TURNS of them (order kept). A history that is not an array counts as []. Never modify the arguments.""",
     "host_hidden": {"hidden_chat_store_1.cjs": JS_HEAD + JS1}},
    {"name": "unpack",
     "task": """Add to `chat_store.js` (keep everything else):
- `unpackChat(raw, now)` -> {history, mission, project, age_ms} or null. null when raw is not a string, now is not a number, raw is not valid JSON, the JSON is not an object
  (arrays and null count as not an object), v is not 1, saved is not a number, or age = now - saved is negative or larger than CHAT_STORE_MAX_AGE_MS (exactly the maximum is still fine).
  Otherwise history, mission and project are cleaned with the SAME rules as in packChat (shape, cut, last CHAT_STORE_TURNS; a missing history is []) and age_ms = age.
- `chatSummary(history)` -> one German line for the greeting after a restore. Clean the history with the same rules first. Empty -> "". Else
  head = "Verlauf mit " + (n === 1 ? "1 Nachricht" : n + " Nachrichten") + " wiederhergestellt" with n = number of cleaned turns.
  If there is a user turn, take the content of the LAST user turn, cut to 60 characters plus "\\u2026" when it was longer, and return head + " (zuletzt: " + text + ")." ; without a user turn return head + ".".
Never modify the arguments.""",
     "host_hidden": {"hidden_chat_store_1.cjs": JS_HEAD + JS1, "hidden_chat_store_2.cjs": JS_HEAD + JS2}},
]
