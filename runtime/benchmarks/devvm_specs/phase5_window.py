"""Phase 5, part B (Captain 2026-10-06, build approved, integration not): the DevVM window of the UIX, read-only, with the live ticker as a tab.

GUPPI builds `devvm.js` in a DevVM workspace (the broker allows .js now). The python microVM cannot judge JavaScript, so the acceptance tests run on the HOST with node
(`host_hidden`, see devvm_build.host_node). The view model is a pure function (no DOM) and is tested; the DOM part is checked for syntax and for the functions that must exist;
the Captain's side (not GUPPI) looks at it in the browser afterwards. Nothing is integrated into uix/.
"""

NOTES = '''# Notes for the DevVM window

The UIX is a set of classic scripts (no modules) that share one global scope. A script may read the page with `document`, but the first stage works WITHOUT the DOM.
The data comes from `GET /api/devvm`, a JSON object (read-only) with these keys, produced on the server:

    {"missions": [{"mission_id": "M-A", "files": ["a.py"], "file_count": 1, "truncated": false, "log": [{"commit": "ab12cd34", "message": "task", "time": "..."}],
                   "uncommitted": {"added": 0, "modified": 1, "deleted": 0}, "usage": {...}},
                  {"mission_id": "M-X", "error": "RuntimeError: broke"}],
     "agents":  [{"mission_id": "M-A", "time": "2026-10-06T10:00:01Z", "role": "coder", "label": "coder (alone)", "model": "jan-code-4b", "stopped_by": "hand_in", "calls": 7, "seconds": 6.3, "depth": 1}],
     "steps":   [{"mission_id": "M-A", "time": "2026-10-06T10:00:03Z", "title": "task", "accepted": true, "rounds": 1, "unjudged": false, "mode": "escalating"}],
     "runs":    [{"mission_id": "M-A", "time": "2026-10-06T10:00:06Z", "accepted": true, "agent_runs": 2, "seconds": 66.3, "swaps": 2, "mode": "escalating"}],
     "ticker":  ["10:00:06 M-A run done: ACCEPTED"]}

Existing windows in the UIX are `<div class="window" id="...">` with a `.titlebar` (title in a span, `.controls` with three `.ctrl` buttons) and a `.content` area; helper functions that exist
in the page: `showWindow(id)`, `closeWindow(id)`, `minimizeWindow(id)`, `toggleMaximize(id)`, `api(path)` (returns a promise with the parsed JSON), `el(tag, className, text)` (creates an element).
'''

STAGE1 = '''Create `devvm.js`, a classic browser script (no modules, no imports, no DOM access at the top level) with a pure function

    devvmViewModel(data)

that turns the data object described in NOTES.md into display lines for four tabs. Missing keys of `data` count as empty lists; the function never throws and never changes `data`.
It returns {"counts": {"missions": n, "agents": n, "steps": n, "runs": n}, "files": [...], "agents": [...], "results": [...], "ticker": [...]} where every list entry is a plain string.
`hms(t)` below means characters 11 to 19 of the ISO timestamp string `t` (e.g. "2026-10-06T10:00:01Z" gives "10:00:01"), or "--:--:--" when `t` is missing or shorter than 19 characters.
A missing value (null or undefined) is written as "?", a missing mission id as "-".

"files": for every mission in `data.missions`, in the given order:
    a mission with an "error": one line  `<mission_id>: Fehler: <error>`
    otherwise a header line  `<mission_id>: <file_count> Dateien<" (gekuerzt)" when truncated>, offen +<added> ~<modified> -<deleted>`  followed by one line  `  <path>`  (two spaces) for every file.
"agents": one line per row of `data.agents`, in the given order:  `<hms(time)> <mission_id> <label, or role when there is no label> [<model>] <stopped_by> <calls> Aufrufe, <seconds> s`
"results": the rows of `data.steps` and `data.runs` together, NEWEST FIRST by their time string (when two rows have the same time, the step comes before the run):
    step:  `<hms(time)> <mission_id> Schritt <title>: angenommen`  or `...: abgelehnt` (accepted true / not true), then " (ungeprueft)" when unjudged is true
    run:   `<hms(time)> <mission_id> Lauf: angenommen`  or `...: abgelehnt`, then `, <agent_runs> Agentenlaeufe, <seconds> s, <swaps> Wechsel`
"ticker": a copy of `data.ticker` (strings), unchanged.

At the very end of the file add:  if (typeof module !== "undefined" && module.exports) module.exports = { devvmViewModel };'''

STAGE2 = '''In the existing `devvm.js` (keep `devvmViewModel` and the export line, extend the export with the new functions) add the window, read-only, in the style of the other UIX windows (see NOTES.md).

    renderDevvm(box, model)   box is a DOM element, model is the result of devvmViewModel: it fills `box` with a row of four tab buttons "Dateien", "Agenten", "Ergebnisse", "Live" and one
                              list per tab (a <pre> or a list element with one line per entry); only the active tab is visible; the first tab is active at start; clicking a tab button
                              switches the visible list; the tab buttons show the counts where they exist (e.g. "Agenten (3)"); an empty list shows the line "Noch nichts."
    openDevvm()               creates the window ONCE: a <div class="window" id="devvmWindow"> with the same structure as the other windows (a .titlebar with a span "GUPPI DevVM" and a .controls
                              block with three .ctrl buttons for minimize, maximize and close that call minimizeWindow('devvmWindow'), toggleMaximize('devvmWindow') and closeWindow('devvmWindow'),
                              and a .content area with id "devvmBody"), appends it to the element with id "desktop", shows it with showWindow('devvmWindow') and calls refreshDevvm().
    refreshDevvm()            fetches api('/api/devvm'), builds the model and shows it in #devvmBody. It must NOT redraw when nothing changed (compare the model as JSON with the last one)
                              and must keep the scroll position and the active tab of the user. On an error it shows one line "DevVM nicht verfuegbar: <message>" and keeps the last view.
    A timer calls refreshDevvm() every 5 seconds, but ONLY while the window #devvmWindow has the class "focused" and the page is visible (document.hidden is false); the timer is started
    once, by openDevvm(). The window only reads: no button or call may write or start anything.
Do not edit any other file.'''

HOST1 = r'''
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync("devvm.js", "utf8");
const sandbox = { module: { exports: {} }, console };
vm.createContext(sandbox); vm.runInContext(src, sandbox);
const { devvmViewModel } = sandbox.module.exports;
const assert = require("assert");
const eq = (a, b) => assert.strictEqual(JSON.stringify(a), JSON.stringify(b));      // objects of the vm context have another prototype: compare as JSON
assert.strictEqual(typeof devvmViewModel, "function");
const data = {
  missions: [{ mission_id: "M-A", files: ["a.py", "t/b.py"], file_count: 5, truncated: true, log: [], uncommitted: { added: 1, modified: 2, deleted: 0 }, usage: {} }, { mission_id: "M-X", error: "RuntimeError: broke" }],
  agents: [{ mission_id: "M-A", time: "2026-10-06T10:00:01Z", role: "coder", label: "coder (alone)", model: "jan-code-4b", stopped_by: "hand_in", calls: 7, seconds: 6.3, depth: 1 },
           { mission_id: null, time: null, role: "planner", label: null, model: null, stopped_by: "turns", calls: 3, seconds: null, depth: 1 }],
  steps: [{ mission_id: "M-A", time: "2026-10-06T10:00:06Z", title: "task", accepted: true, rounds: 1, unjudged: false, mode: "e" },
          { mission_id: "M-A", time: "2026-10-06T10:00:04Z", title: "t2", accepted: false, rounds: 3, unjudged: true, mode: null }],
  runs: [{ mission_id: "M-B", time: "2026-10-06T10:00:06Z", accepted: true, agent_runs: 2, seconds: 66.3, swaps: 2, mode: "e" }],
  ticker: ["10:00:06 M-B run done: ACCEPTED", "10:00:01 M-A coder (alone) hand_in 7 calls"],
};
const snapshot = JSON.stringify(data);
const m = devvmViewModel(data);
assert.strictEqual(JSON.stringify(data), snapshot, "data was changed");
eq(m.counts, { missions: 2, agents: 2, steps: 2, runs: 1 });
eq(m.files, ["M-A: 5 Dateien (gekuerzt), offen +1 ~2 -0", "  a.py", "  t/b.py", "M-X: Fehler: RuntimeError: broke"]);
eq(m.agents, ["10:00:01 M-A coder (alone) [jan-code-4b] hand_in 7 Aufrufe, 6.3 s", "--:--:-- - planner [?] turns 3 Aufrufe, ? s"]);
eq(m.results, ["10:00:06 M-A Schritt task: angenommen", "10:00:06 M-B Lauf: angenommen, 2 Agentenlaeufe, 66.3 s, 2 Wechsel", "10:00:04 M-A Schritt t2: abgelehnt (ungeprueft)"]);
eq(m.ticker, data.ticker); assert.notStrictEqual(m.ticker, data.ticker);
const empty = devvmViewModel({});
eq(empty, { counts: { missions: 0, agents: 0, steps: 0, runs: 0 }, files: [], agents: [], results: [], ticker: [] });
eq(devvmViewModel(undefined).files, []);
console.log("ok");
'''

HOST2 = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const src = fs.readFileSync("devvm.js", "utf8");
const sandbox = { module: { exports: {} }, console, setInterval: () => 0, document: { hidden: false } };
vm.createContext(sandbox); vm.runInContext(src, sandbox);
const ex = sandbox.module.exports;
for (const name of ["devvmViewModel", "renderDevvm", "openDevvm", "refreshDevvm"]) {
  const f = ex[name] || sandbox[name];
  assert.strictEqual(typeof f, "function", name + " is missing");
}
assert.ok(/\/api\/devvm/.test(src), "the window must read /api/devvm");
assert.ok(/focused/.test(src) && /hidden/.test(src), "the timer must check the focus and document.hidden");
assert.ok(!/method\s*:\s*['"](POST|PUT|DELETE|PATCH)/i.test(src), "the window is read-only");
assert.ok(/devvmWindow/.test(src) && /devvmBody/.test(src));
console.log("ok");
'''

HOST3 = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const src = fs.readFileSync("devvm.js", "utf8");

// ---- a small fake DOM, just enough for the window code (no layout, no events except click) ----
class Node {
  constructor(tag) { this.tagName = String(tag).toUpperCase(); this.children = []; this.parent = null; this.style = {}; this.attrs = {}; this._text = ""; this.listeners = {}; this.scrollTop = 0; this.onclick = null; this.cls = new Set(); this.id = ""; this.title = ""; this.hidden = false;
    const self = this; this.classList = { add: (...c) => c.forEach((x) => self.cls.add(x)), remove: (...c) => c.forEach((x) => self.cls.delete(x)), contains: (c) => self.cls.has(c), toggle: (c, f) => { const on = f === undefined ? !self.cls.has(c) : f; on ? self.cls.add(c) : self.cls.delete(c); return on; } }; }
  get className() { return [...this.cls].join(" "); }
  set className(v) { this.cls = new Set(String(v || "").split(/\s+/).filter(Boolean)); }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); }
  set textContent(v) { this.children = []; this._text = v === null || v === undefined ? "" : String(v); }
  get innerHTML() { return this._html !== undefined ? this._html : this.children.map((c) => c.innerHTML).join(""); }
  set innerHTML(v) { this.children = []; this._text = ""; this._html = undefined; if (v) { const t = new Node("span"); t._text = String(v).replace(/<[^>]*>/g, ""); this.append(t); } }
  get innerText() { return this.visibleText(); }
  visibleText() { if (this.style.display === "none" || this.hidden) return ""; return this._text + this.children.map((c) => c.visibleText()).join("\n"); }
  appendChild(c) { if (c.parent) c.parent.children = c.parent.children.filter((x) => x !== c); c.parent = this; this.children.push(c); return c; }
  append(...cs) { cs.forEach((c) => { if (typeof c === "string") { const t = new Node("span"); t._text = c; this.appendChild(t); } else this.appendChild(c); }); }
  prepend(c) { c.parent = this; this.children.unshift(c); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((x) => x !== this); this.parent = null; }
  replaceChildren(...cs) { this.children = []; this._text = ""; this.append(...cs); }
  setAttribute(k, v) { this.attrs[k] = v; if (k === "id") this.id = v; if (k === "class") this.className = v; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  click() { if (this.onclick) this.onclick({ target: this }); (this.listeners.click || []).forEach((f) => f({ target: this })); }
  all() { return this.children.flatMap((c) => [c, ...c.all()]); }
  matches(sel) { return sel.split(",").some((s) => { s = s.trim(); let ok = true; const id = s.match(/#([\w-]+)/); if (id) ok = ok && this.id === id[1]; (s.match(/\.[\w-]+/g) || []).forEach((c) => { ok = ok && this.cls.has(c.slice(1)); }); const tag = s.match(/^[a-zA-Z]+/); if (tag) ok = ok && this.tagName === tag[0].toUpperCase(); return ok; }); }
  querySelectorAll(sel) { return this.all().filter((n) => n.matches(sel)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  contains(n) { return n === this || this.all().includes(n); }
}
const root = new Node("div"); const desktop = new Node("div"); desktop.id = "desktop"; root.append(desktop);
const timers = [];
let apiData, apiFail = false, apiCalls = 0, focusedId = null;
const document = { hidden: false, getElementById: (id) => root.all().find((n) => n.id === id) || null, createElement: (t) => new Node(t), querySelectorAll: (s) => root.querySelectorAll(s) };
const sandbox = {
  module: { exports: {} }, console, document, JSON, Promise, Object, Array, String, Number, Math, Date,
  setInterval: (f, ms) => { timers.push({ f, ms }); return timers.length; }, clearInterval: () => { timers.cleared = (timers.cleared || 0) + 1; }, setTimeout: (f) => { f(); return 0; },
  api: (p) => { apiCalls++; return apiFail ? Promise.reject(new Error("boom")) : Promise.resolve(JSON.parse(JSON.stringify(apiData))); },
  el: (tag, cls, text) => { const n = new Node(tag); if (cls) n.className = cls; if (text !== undefined && text !== null) n.textContent = text; return n; },
  showWindow: (id) => { const w = document.getElementById(id); w.classList.add("active"); w.classList.add("focused"); },
  closeWindow: () => {}, minimizeWindow: () => {}, toggleMaximize: () => {},
};
sandbox.window = sandbox;
vm.createContext(sandbox); vm.runInContext(src, sandbox);
const ex = sandbox.module.exports;
const openDevvm = ex.openDevvm || sandbox.openDevvm, refreshDevvm = ex.refreshDevvm || sandbox.refreshDevvm;
const flush = () => new Promise((r) => setImmediate(r));
const base = () => ({ missions: [{ mission_id: "M-A", files: ["a.py", "t/b.py"], file_count: 2, truncated: false, log: [], uncommitted: { added: 1, modified: 0, deleted: 0 }, usage: {} }],
  agents: [{ mission_id: "M-A", time: "2026-10-06T10:00:01Z", role: "coder", label: "coder (alone)", model: "jan", stopped_by: "hand_in", calls: 7, seconds: 6.3, depth: 1 }], steps: [], runs: [], ticker: ["10:00:06 M-A run done: ACCEPTED"] });
const button = (name) => root.querySelectorAll("button").find((b) => b.textContent.startsWith(name)) || assert.fail("no tab button " + name);
const win = () => document.getElementById("devvmWindow"), body = () => document.getElementById("devvmBody");

(async () => {
  apiData = base();
  openDevvm(); openDevvm();
  assert.strictEqual(root.querySelectorAll("#devvmWindow").length, 1, "the window must be created once");
  assert.ok(/Lade/.test(body().textContent), "before the data arrive the body shows: Lade ...");
  await flush(); await flush();
  assert.ok(button("Dateien") && button("Agenten") && button("Ergebnisse") && button("Live"));
  assert.ok(/Agenten \(1\)/.test(button("Agenten").textContent) && /Dateien \(1\)/.test(button("Dateien").textContent), "counts in the tab buttons");
  assert.ok(/a\.py/.test(body().innerText) && !/hand_in/.test(body().innerText), "only the first tab is visible at start");
  assert.strictEqual(timers.length, 1, "exactly one timer"); assert.strictEqual(timers[0].ms, 5000);
  // the controls
  const ctrls = win().querySelectorAll(".ctrl"); assert.deepStrictEqual(ctrls.map((c) => c.title), ["Minimieren", "Maximieren", "Schliessen"]); assert.ok(ctrls[2].cls.has("close"));
  // switch tab, refresh with unchanged data: nothing may change, not the DOM, not the tab
  button("Agenten").click();
  assert.ok(/hand_in/.test(body().innerText) && !/a\.py/.test(body().innerText), "the second tab is visible after the click");
  const firstChild = body().children[0], before = body().children.length;
  await refreshDevvm(); await flush(); await flush();
  assert.strictEqual(body().children[0], firstChild, "after refreshDevvm() with data equal to the last data, the first child of #devvmBody must still be the SAME element object (do not clear, re-create or re-render anything; just return when JSON.stringify(model) equals the last model)");
  assert.ok(/hand_in/.test(body().innerText) && !/Lade/.test(body().innerText), "the tab stays and Lade ... is gone");
  // changed data: redraw, the active tab stays
  apiData = base(); apiData.agents.push({ mission_id: "M-B", time: "2026-10-06T10:00:09Z", role: "planner", label: "planner", model: "q", stopped_by: "turns", calls: 3, seconds: 1, depth: 1 });
  await refreshDevvm(); await flush(); await flush();
  assert.ok(/Agenten \(2\)/.test(button("Agenten").textContent) && /turns/.test(body().innerText) && !/a\.py/.test(body().innerText), "changed data: redrawn and the active tab is kept");
  // error: the last view is kept
  apiFail = true; await refreshDevvm(); await flush(); await flush(); apiFail = false;
  assert.ok(/turns/.test(win().innerText) && /DevVM nicht verfuegbar: boom/.test(win().innerText), "an error keeps the last view and names the error");
  // the timer tick: only while focused and visible
  const tick = timers[0].f; apiCalls = 0;
  win().classList.remove("focused"); await tick(); await flush(); assert.strictEqual(apiCalls, 0, "not focused: no request");
  win().classList.add("focused"); document.hidden = true; await tick(); await flush(); assert.strictEqual(apiCalls, 0, "page hidden: no request");
  document.hidden = false; await tick(); await flush(); assert.strictEqual(apiCalls, 1, "focused and visible: one request");
  assert.ok(!timers.cleared, "the timer is never cleared"); assert.strictEqual(timers.length, 1);
  openDevvm(); assert.strictEqual(timers.length, 1, "opening again does not start a second timer");
  console.log("ok");
})().catch((e) => { console.error("FAILED: " + String((e && e.message) || e).split(String.fromCharCode(10))[0]); process.exit(1); });
'''

STAGES = [
    {"name": "view_model", "task": STAGE1, "host_hidden": {"hidden_b1.cjs": HOST1}},
    {"name": "window", "task": STAGE2, "host_hidden": {"hidden_b1.cjs": HOST1, "hidden_b2.cjs": HOST2, "hidden_b3.cjs": HOST3}},
]
