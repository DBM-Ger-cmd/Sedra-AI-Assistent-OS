"""Bau-Spec bruecke_filter: was eine fremde App ueber die Bruecke sehen und senden darf (AM3-16 bis AM3-18, AM3-20, AM3-23, Stufe A4, Kern ohne Anbindung).
Drei Stufen S1 bis S3, je ein Node-Test auf dem Host (host_hidden); kein eigener Test des Modells. Klassisches Browser-Skript bruecke_filter.js; Claude verdrahtet es spaeter in ui/bruecke.js von Hand.
S1 Ereignisse filtern | S2 Hinweise bereinigen | S3 Drossel und Zellen-Nachricht.
Referenz: benchmarks/devvm_refs/bruecke_filter/bruecke_filter.js. Lauf: bau_schleife.py --projekt <Ordner> --spec bruecke_filter start "<Auftrag>"."""

NOTES = '''# Notes for bruecke_filter.js
A CLASSIC browser script: no modules, no import/export, no require, no DOM, no fetch, no storage, no timers inside the file. Plain JavaScript (ES2015 is fine), ASCII only.
Top-level `var` and `function` declarations are the interface (the page and the tests read them as globals); declare constants with `var`.
Never modify the arguments; return new objects. No comments, small helpers instead of copied code.
'''

TASK_S1 = '''Create `bruecke_filter.js` with `function filterEreignis(name, payload)`: what a foreign app may see of an event. It returns the object the app may receive, or null when the app must not get the event at all.
- name is not a text: null.
- Public events: the names system.state, model.changed, desk.resync, tools.refresh, slot.changed. The result is payload itself (the same value); when payload is undefined the result is a new empty object {}.
- Content events are cut down to a fixed list of keys. For these names the result is a NEW object that holds only the listed keys that exist as own properties of payload AND whose value is a text, a number or a boolean (objects, arrays, null and undefined are dropped):
  decision.pending and decision.answered: id, kind, way
  task.changed: id, phase
  object.open: type, id
  agent.changed and issue.changed: id
  budget.warning: agent_id, stufe
  If payload is not an object (null, text, number, undefined) the result is an empty new object {}.
- Every other name gets null: live.line, talk.context, desk.error, every name that starts with harness., and every name that is not mentioned above (also inherited names such as "constructor", "toString", "__proto__").
Keep the code simple; declare the two name lists as `var EREIGNIS_OEFFENTLICH` (array) and `var EREIGNIS_SCHLUESSEL` (object name -> array of keys).'''

TASK_S2 = '''Add to `bruecke_filter.js` (keep everything else): `function bereinigeHinweis(appName, text, ton)`: the notice a foreign app may show in the shell.
- If appName or text is not a text, return null.
- Remove every control character from text (the characters U+0000 to U+001F and U+007F) and trim spaces at both ends. If nothing is left, return null.
- The result is {text: <appName + ": " + cleaned text, cut to at most 200 characters (the first 200)>, ton: "note"}. The tone is always "note", whatever ton says (ton is ignored).
The arguments are never modified.'''

TASK_S3 = '''Add to `bruecke_filter.js` (keep everything else):
1. `function drossel(intervallMs)` returns a NEW function `erlaubt(schluessel, jetztMs)` -> boolean with its own memory per drossel. For each key (String(schluessel)) the function remembers the time of the last call that returned true. A call returns false when that key already has a remembered time and jetztMs minus that time is smaller than intervallMs (and then the remembered time stays as it was); otherwise it returns true and remembers jetztMs. Keys are independent of each other; keys such as "constructor" or "__proto__" behave like any other key. Two drossel functions do not share memory.
2. `function pruefeZelle(msg)` checks the message of a foreign cell: {wert, hinweis, ton}. Return null when msg is null or not an object, or when wert is not a non-empty text. Otherwise return a NEW object {wert, hinweis, ton}: wert cut to at most 24 characters (the first 24); hinweis cut to at most 80 characters when it is a text, else ""; ton is "ok", "warn" or "off" when msg.ton is exactly one of these, else "off" (so "bad" becomes "off").'''

JS_HEAD = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const box = {console: console};
vm.createContext(box);
vm.runInContext(fs.readFileSync("bruecke_filter.js", "utf8"), box);
const ctx = v => vm.runInContext("(" + JSON.stringify(v) + ")", box);
const plain = v => JSON.parse(JSON.stringify(v));
'''

JS1 = r'''
const f = (n, p) => box.filterEreignis(n, p === undefined ? undefined : ctx(p));
assert.deepStrictEqual(plain(f("system.state", {a: 1, b: {c: 2}})), {a: 1, b: {c: 2}});
assert.deepStrictEqual(plain(f("model.changed", {model: "x"})), {model: "x"});
assert.deepStrictEqual(plain(f("desk.resync", undefined)), {});
assert.deepStrictEqual(plain(f("tools.refresh", {})), {});
assert.deepStrictEqual(plain(f("slot.changed", {slots: 3})), {slots: 3});
const p = ctx({a: 1});
assert.strictEqual(box.filterEreignis("system.state", p), p);
assert.deepStrictEqual(plain(f("decision.pending", {id: "D-1", kind: "request:install", way: "freigeben", title: "geheim", text: "geheim"})), {id: "D-1", kind: "request:install", way: "freigeben"});
assert.deepStrictEqual(plain(f("decision.answered", {id: "D-1", title: "geheim"})), {id: "D-1"});
assert.deepStrictEqual(plain(f("task.changed", {id: "T-1", phase: "EXECUTE", title: "geheim"})), {id: "T-1", phase: "EXECUTE"});
assert.deepStrictEqual(plain(f("object.open", {type: "task", id: "T-1", extra: 1})), {type: "task", id: "T-1"});
assert.deepStrictEqual(plain(f("agent.changed", {id: "A-1", name: "x"})), {id: "A-1"});
assert.deepStrictEqual(plain(f("issue.changed", {id: "I-1", text: "x"})), {id: "I-1"});
assert.deepStrictEqual(plain(f("budget.warning", {agent_id: "A-1", stufe: 2, betrag: 5})), {agent_id: "A-1", stufe: 2});
assert.deepStrictEqual(plain(f("task.changed", {id: {x: 1}, phase: [1], extra: true})), {});
assert.deepStrictEqual(plain(f("task.changed", {id: null, phase: undefined})), {});
assert.deepStrictEqual(plain(f("task.changed", {id: 0, phase: false})), {id: 0, phase: false});
assert.deepStrictEqual(plain(f("task.changed", {hasOwnProperty: 5, id: "x"})), {id: "x"});
assert.deepStrictEqual(plain(box.filterEreignis("task.changed", vm.runInContext("Object.assign(Object.create(null), {id: 'x', phase: 'p', geheim: 1})", box))), {id: "x", phase: "p"});
assert.deepStrictEqual(plain(f("task.changed", null)), {});
assert.deepStrictEqual(plain(f("task.changed", "text")), {});
assert.deepStrictEqual(plain(f("task.changed", undefined)), {});
for (const n of ["live.line", "talk.context", "desk.error", "harness.token", "harness.", "nix.event", "constructor", "toString", "__proto__", "hasOwnProperty", ""]) {
  assert.strictEqual(f(n, {id: "x"}), null, n);
}
assert.strictEqual(box.filterEreignis(5, {}), null);
assert.strictEqual(box.filterEreignis(null, {}), null);
assert.strictEqual(box.filterEreignis(undefined, {}), null);
const q = ctx({id: "D-1", title: "x"});
f("decision.pending", {id: "D-1", title: "x"});
box.filterEreignis("decision.pending", q);
assert.deepStrictEqual(plain(q), {id: "D-1", title: "x"});
assert.ok(box.EREIGNIS_OEFFENTLICH.length === 5);
assert.ok("budget.warning" in box.EREIGNIS_SCHLUESSEL);
'''

JS2 = r'''
const h = (a, t, ton) => box.bereinigeHinweis(a, t, ton);
assert.deepStrictEqual(plain(h("Rechnung", "fertig", "ok")), {text: "Rechnung: fertig", ton: "note"});
assert.deepStrictEqual(plain(h("A", "x")), {text: "A: x", ton: "note"});
assert.deepStrictEqual(plain(h("A", "x", "bad")), {text: "A: x", ton: "note"});
assert.deepStrictEqual(plain(h("A", "  x  ", "warn")), {text: "A: x", ton: "note"});
assert.deepStrictEqual(plain(h("A", "a\u0000b\u001fc\u007fd\ne\tf", "ok")), {text: "A: abcdef", ton: "note"});
assert.strictEqual(h("A", "", "ok"), null);
assert.strictEqual(h("A", "   ", "ok"), null);
assert.strictEqual(h("A", "\u0001\u0002", "ok"), null);
assert.strictEqual(h("A", 5, "ok"), null);
assert.strictEqual(h("A", null, "ok"), null);
assert.strictEqual(h("A", undefined, "ok"), null);
assert.strictEqual(h(5, "x", "ok"), null);
assert.strictEqual(h(undefined, "x", "ok"), null);
assert.strictEqual(h("A", "x".repeat(300), "ok").text.length, 200);
assert.strictEqual(h("A", "x".repeat(300), "ok").text, ("A: " + "x".repeat(300)).slice(0, 200));
assert.strictEqual(h("A", "x".repeat(197), "ok").text.length, 200);
assert.strictEqual(h("A", "x".repeat(196), "ok").text, "A: " + "x".repeat(196));
assert.strictEqual(h("A".repeat(250), "x", "ok").text, "A".repeat(200));
assert.strictEqual(h("A", "xäö", "ok").text, "A: xäö");
'''

JS3 = r'''
const d = box.drossel(5000);
assert.strictEqual(typeof d, "function");
assert.strictEqual(d("app1", 1000), true);
assert.strictEqual(d("app1", 2000), false);
assert.strictEqual(d("app1", 5999), false);
assert.strictEqual(d("app1", 6000), true);
assert.strictEqual(d("app1", 7000), false);
assert.strictEqual(d("app2", 7000), true);
assert.strictEqual(d("app2", 7001), false);
assert.strictEqual(d("constructor", 0), true);
assert.strictEqual(d("constructor", 100), false);
assert.strictEqual(d("__proto__", 0), true);
assert.strictEqual(d("__proto__", 100), false);
assert.strictEqual(d(5, 0), true);
assert.strictEqual(d("5", 1), false);
const e = box.drossel(5000);
assert.strictEqual(e("app1", 2000), true);
assert.strictEqual(box.drossel(0)("a", 1), true);
const n = box.drossel(1000);
assert.strictEqual(n("z", 0), true);
assert.strictEqual(n("z", 0), false);
assert.strictEqual(n("z", 999), false);
assert.strictEqual(n("z", 1000), true);
const z = m => { const r = box.pruefeZelle(ctx(m)); return r === null ? null : plain(r); };
assert.deepStrictEqual(z({wert: "12 GB", hinweis: "RAM frei", ton: "ok"}), {wert: "12 GB", hinweis: "RAM frei", ton: "ok"});
assert.deepStrictEqual(z({wert: "x", ton: "warn"}), {wert: "x", hinweis: "", ton: "warn"});
assert.deepStrictEqual(z({wert: "x"}), {wert: "x", hinweis: "", ton: "off"});
assert.deepStrictEqual(z({wert: "x", ton: "bad"}), {wert: "x", hinweis: "", ton: "off"});
assert.deepStrictEqual(z({wert: "x", ton: "OK"}), {wert: "x", hinweis: "", ton: "off"});
assert.deepStrictEqual(z({wert: "x", ton: "off", hinweis: 5}), {wert: "x", hinweis: "", ton: "off"});
assert.strictEqual(z({wert: "x".repeat(40)}).wert, "x".repeat(24));
assert.strictEqual(z({wert: "x".repeat(24)}).wert, "x".repeat(24));
assert.strictEqual(z({wert: "x", hinweis: "h".repeat(120)}).hinweis, "h".repeat(80));
assert.strictEqual(z({wert: ""}), null);
assert.strictEqual(z({wert: 5}), null);
assert.strictEqual(z({hinweis: "x"}), null);
assert.strictEqual(z(null), null);
assert.strictEqual(box.pruefeZelle("x"), null);
assert.strictEqual(box.pruefeZelle(undefined), null);
assert.strictEqual(box.pruefeZelle(5), null);
const m0 = ctx({wert: "x".repeat(40), extra: 1});
const r0 = box.pruefeZelle(m0);
assert.notStrictEqual(r0, m0);
assert.strictEqual(m0.wert.length, 40);
assert.deepStrictEqual(Object.keys(plain(r0)).sort(), ["hinweis", "ton", "wert"]);
'''

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "host_hidden": {"hidden_bruecke_1.cjs": JS_HEAD + JS1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "host_hidden": {"hidden_bruecke_1.cjs": JS_HEAD + JS1, "hidden_bruecke_2.cjs": JS_HEAD + JS2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "host_hidden": {"hidden_bruecke_2.cjs": JS_HEAD + JS2, "hidden_bruecke_3.cjs": JS_HEAD + JS3}},
]
TASK = TASK_S1
HIDDEN = {}
