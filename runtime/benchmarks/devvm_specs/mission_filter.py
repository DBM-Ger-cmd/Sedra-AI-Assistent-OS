"""Search and filter for the bridge and the logbook (UIX analysis 2026-10-13, proposal 4.2 Nr. 8): from 30 missions on, the list of buttons is unwieldy.
`mission_filter.js` is the pure part: filter the compact missions of /api/missions by words, phases and open gates, group them by day, and the one-line text of
a mission. Classic browser script, judged on the host with node. Claude wires it into missions.js (openBridge) and status.js (openLogbook) after acceptance:
a text field, phase chips, a "nur mit offener Freigabe" switch. Reads only (guideline of UIX_ROADMAP.md).
Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/mission_filter)."""

NOTES = '''# Notes for mission_filter.js
A CLASSIC browser script: no modules, no import/export, no DOM access anywhere in the file. Functions and `var` names become globals of the page.
Never modify the arguments (not the list, not the missions); return new arrays. No comments and no docstrings, small helpers instead of copied code.
'''

JS_HEAD = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const box = { Math: Math, JSON: JSON, console: console, Array: Array, Date: Date, Number: Number, isNaN: isNaN, RegExp: RegExp };
vm.createContext(box); vm.runInContext(fs.readFileSync("mission_filter.js", "utf8"), box);
const plain = v => JSON.parse(JSON.stringify(v));
const M = [
  {mission_id: "M-A1", intent: "Erstelle ein Demo-Artefakt", objective: null, phase: "COMPLETE", pending_gates: 0, created_at: "2026-10-13T08:00:00+00:00"},
  {mission_id: "M-B2", intent: "Schalter job_supervisor.enabled auf an stellen", objective: null, phase: "READY", pending_gates: 1, created_at: "2026-10-13T09:30:00+00:00"},
  {mission_id: "M-C3", intent: "Chat-Sitzung mit dem lokalen Modell", objective: "Fragen beantworten", phase: "PAUSED", pending_gates: 2, created_at: "2026-10-12T22:10:00+00:00"},
  {mission_id: "M-D4", intent: null, objective: "Projekt Demo inspizieren", phase: "FAILED", pending_gates: 0, created_at: "2026-10-09T10:00:00+00:00"},
  {mission_id: "M-E5", intent: "Routing ändern: coder Kontext 8192 → 16384", objective: null, phase: "READY", pending_gates: 0, created_at: "2026-10-13T09:30:00+00:00"},
  {mission_id: "M-F6", intent: "Alte Mission ohne Datum", objective: null, phase: "COMPLETE", pending_gates: 0},
  {mission_id: "M-G7", intent: "Demo von letzter Woche", objective: null, phase: "COMPLETE", pending_gates: 0, created_at: "2026-10-06T07:00:00+00:00"},
  null, "junk", {mission_id: 5, phase: "READY"}
];
const ids = list => plain(list).map(m => m.mission_id);
'''

JS1 = r'''
assert.deepStrictEqual(plain(box.MISSION_PHASES), ["READY", "PAUSED", "CAPTAIN_REVIEW", "CANDIDATE_REVIEW", "REWORK", "COMPLETE", "FAILED"]);
const f = (q, p, g) => ids(box.filterMissions(M, q, p, g));
assert.deepStrictEqual(f("", null, false), ["M-B2", "M-E5", "M-A1", "M-C3", "M-D4", "M-G7", "M-F6", 5]);
assert.deepStrictEqual(f("demo", null, false), ["M-A1", "M-D4", "M-G7"]);
assert.deepStrictEqual(f("  DEMO   artefakt ", null, false), ["M-A1"]);
assert.deepStrictEqual(f("m-c3", null, false), ["M-C3"]);
assert.deepStrictEqual(f("fragen", null, false), ["M-C3"]);
assert.deepStrictEqual(f("nichts-da", null, false), []);
assert.deepStrictEqual(f("", ["READY"], false), ["M-B2", "M-E5", 5]);
assert.deepStrictEqual(f("", ["READY", "PAUSED"], false), ["M-B2", "M-E5", "M-C3", 5]);
assert.deepStrictEqual(f("", [], false), ["M-B2", "M-E5", "M-A1", "M-C3", "M-D4", "M-G7", "M-F6", 5]);
assert.deepStrictEqual(f("", "READY", false), ["M-B2", "M-E5", "M-A1", "M-C3", "M-D4", "M-G7", "M-F6", 5]);
assert.deepStrictEqual(f("", null, true), ["M-B2", "M-C3"]);
assert.deepStrictEqual(f("schalter", ["READY"], true), ["M-B2"]);
assert.deepStrictEqual(f("schalter", ["PAUSED"], true), []);
assert.deepStrictEqual(f(null, undefined, undefined), ["M-B2", "M-E5", "M-A1", "M-C3", "M-D4", "M-G7", "M-F6", 5]);
assert.deepStrictEqual(ids(box.filterMissions(null, "", null, false)), []);
assert.deepStrictEqual(ids(box.filterMissions("x", "", null, false)), []);
assert.deepStrictEqual(ids(box.filterMissions([{mission_id: "x", phase: "READY", pending_gates: "2"}], "", null, true)), []);
const same = [{mission_id: "s1", created_at: "2026-10-13T09:30:00+00:00"}, {mission_id: "s2", created_at: "2026-10-13T09:30:00+00:00"}, {mission_id: "s3", created_at: "2026-10-13T09:30:00+00:00"}];
assert.deepStrictEqual(ids(box.filterMissions(same, "", null, false)), ["s1", "s2", "s3"]);
const out = box.filterMissions(M, "", null, false); assert.strictEqual(out[0], M[1]);
const before = JSON.stringify(M); box.filterMissions(M, "demo", ["READY"], true); assert.strictEqual(JSON.stringify(M), before);
assert.notStrictEqual(box.filterMissions(M, "", null, false), M);
console.log("ok");
'''

JS2 = r'''
assert.deepStrictEqual(plain(box.MISSION_GROUPS), ["Heute", "Gestern", "Diese Woche", "Älter"]);
const g = (list, today) => plain(box.missionGroups(list, today)).map(x => [x.label, x.items.map(m => m.mission_id)]);
assert.deepStrictEqual(g(M, "2026-10-13"), [["Heute", ["M-A1", "M-B2", "M-E5"]], ["Gestern", ["M-C3"]], ["Diese Woche", ["M-D4"]], ["Älter", ["M-F6", "M-G7", 5]]]);
assert.deepStrictEqual(g(M, "2026-10-14"), [["Gestern", ["M-A1", "M-B2", "M-E5"]], ["Diese Woche", ["M-C3", "M-D4"]], ["Älter", ["M-F6", "M-G7", 5]]]);
assert.deepStrictEqual(g(M, "2026-10-12"), [["Heute", ["M-A1", "M-B2", "M-C3", "M-E5"]], ["Diese Woche", ["M-D4", "M-G7"]], ["Älter", ["M-F6", 5]]]);
assert.deepStrictEqual(g(M, "2026-10-19"), [["Diese Woche", ["M-A1", "M-B2", "M-E5"]], ["Älter", ["M-C3", "M-D4", "M-F6", "M-G7", 5]]]);
assert.deepStrictEqual(g(M, "2026-10-20"), [["Älter", ["M-A1", "M-B2", "M-C3", "M-D4", "M-E5", "M-F6", "M-G7", 5]]]);
assert.deepStrictEqual(g([{mission_id: "x", created_at: "2026-11-01T00:00:00+00:00"}], "2026-10-13"), [["Heute", ["x"]]]);
assert.deepStrictEqual(g([{mission_id: "x", created_at: "2026-10-13"}], "2026-10-13"), [["Heute", ["x"]]]);
assert.deepStrictEqual(g([{mission_id: "x", created_at: "gestern"}], "2026-10-13"), [["Älter", ["x"]]]);
assert.deepStrictEqual(g([{mission_id: "x", created_at: "2026-10-13T00:00:00+00:00"}], "kein datum"), [["Älter", ["x"]]]);
assert.deepStrictEqual(g([{mission_id: "x", created_at: "2026-10-13T00:00:00+00:00"}], null), [["Älter", ["x"]]]);
assert.deepStrictEqual(g([{mission_id: "y", created_at: "2026-03-01T00:00:00+00:00"}], "2026-03-02"), [["Gestern", ["y"]]]);
assert.deepStrictEqual(g([{mission_id: "y", created_at: "2026-02-28T00:00:00+00:00"}], "2026-03-01"), [["Gestern", ["y"]]]);
assert.deepStrictEqual(g([{mission_id: "y", created_at: "2026-12-31T23:00:00+00:00"}], "2027-01-06"), [["Diese Woche", ["y"]]]);
assert.deepStrictEqual(g([{mission_id: "y", created_at: "2026-12-30T23:00:00+00:00"}], "2027-01-06"), [["Älter", ["y"]]]);
assert.deepStrictEqual(g([], "2026-10-13"), []);
assert.deepStrictEqual(g(null, "2026-10-13"), []);
const before = JSON.stringify(M); box.missionGroups(M, "2026-10-13"); assert.strictEqual(JSON.stringify(M), before);

assert.strictEqual(box.missionLine(M[0]), "M-A1 · COMPLETE · Erstelle ein Demo-Artefakt");
assert.strictEqual(box.missionLine(M[1]), "M-B2 · READY · Schalter job_supervisor.enabled auf an stellen · 1 Freigabe offen");
assert.strictEqual(box.missionLine(M[2]), "M-C3 · PAUSED · Chat-Sitzung mit dem lokalen Modell · 2 Freigaben offen");
assert.strictEqual(box.missionLine(M[3]), "M-D4 · FAILED · Projekt Demo inspizieren");
assert.strictEqual(box.missionLine({mission_id: "M-X", intent: "a".repeat(61), phase: "READY"}), "M-X · READY · " + "a".repeat(60) + "…");
assert.strictEqual(box.missionLine({mission_id: "M-X", intent: "a".repeat(60), phase: "READY"}), "M-X · READY · " + "a".repeat(60));
assert.strictEqual(box.missionLine({mission_id: "M-Y"}), "M-Y · ? · ");
assert.strictEqual(box.missionLine({mission_id: "M-Z", phase: "READY", pending_gates: "3"}), "M-Z · READY · ");
assert.strictEqual(box.missionLine(null), " · ? · ");
console.log("ok");
'''

STAGES = [
    {"name": "filter",
     "task": """Create `mission_filter.js` (a classic browser script, see NOTES.md) with:
- `var MISSION_PHASES = ["READY", "PAUSED", "CAPTAIN_REVIEW", "CANDIDATE_REVIEW", "REWORK", "COMPLETE", "FAILED"]`.
- `filterMissions(list, query, phases, onlyGates)` -> a NEW array of the missions of list that match, newest first. A mission is a compact record
  {mission_id, intent, objective, phase, pending_gates, created_at}; entries of list that are not objects are dropped; a list that is not an array gives [].
  Words: the query (a non-string counts as "") lower-cased and split at whitespace, empty words dropped; every word must occur in the lower-cased text
  mission_id + " " + intent + " " + objective (a field that is not a string counts as ""). phases: when it is a non-empty array, the phase must be one of its entries; otherwise no phase filter.
  onlyGates: when truthy, pending_gates must be a number greater than 0.
  Order: by created_at descending as plain string comparison (a missing or non-string created_at counts as "" and so comes last); equal created_at keep the order of list (stable).
Never modify the arguments.""",
     "host_hidden": {"hidden_mission_filter_1.cjs": JS_HEAD + JS1}},
    {"name": "groups",
     "task": """Add to `mission_filter.js` (keep everything else):
- `var MISSION_GROUPS = ["Heute", "Gestern", "Diese Woche", "\\u00c4lter"]`.
- `missionGroups(list, today)` -> an array of {label, items} in the order of MISSION_GROUPS, only the non-empty groups; items keep the order of list. today is "YYYY-MM-DD".
  The day of a mission is the first 10 characters of created_at when they look like YYYY-MM-DD (use Date.UTC on the three numbers, so month lengths and leap years are right);
  diff = days from the mission's day to today. diff <= 0 -> "Heute" (a mission in the future counts as today), 1 -> "Gestern", 2..6 -> "Diese Woche", more -> "\\u00c4lter".
  A mission without a usable day, or a today that is not usable, goes to "\\u00c4lter". Entries that are not objects are dropped; a list that is not an array gives [].
- `missionLine(m)` -> mission_id + " \\u00b7 " + (phase or "?") + " \\u00b7 " + text, text = intent, or objective when intent is not a non-empty string, cut to 60 characters plus "\\u2026" when
  it was longer; when pending_gates is a number greater than 0 append " \\u00b7 1 Freigabe offen" for 1 and " \\u00b7 N Freigaben offen" for more. A field that is not a string counts as ""
  (a non-object m counts as {}).
Never modify the arguments.""",
     "host_hidden": {"hidden_mission_filter_1.cjs": JS_HEAD + JS1, "hidden_mission_filter_2.cjs": JS_HEAD + JS2}},
]
