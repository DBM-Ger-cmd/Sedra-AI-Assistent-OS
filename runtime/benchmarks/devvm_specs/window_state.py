"""Window state that is remembered (UIX analysis 2026-10-13, proposal 4.2 Nr. 6): position, size, maximized and open/closed per window in localStorage,
plus "Fenster anordnen" (cascade). `window_state.js` is the pure part: clamp a box to the desktop, cascade positions, pack the list for storage, unpack
and check it. Classic browser script, judged on the host with node. Claude wires it into desktop.js/main.js after acceptance (save on move, resize,
open, close; restore at start; a menu entry that cascades the open windows). Display convenience only, no runtime state (guideline of UIX_ROADMAP.md).
Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/window_state)."""

NOTES = '''# Notes for window_state.js
A CLASSIC browser script: no modules, no import/export, no DOM or storage access anywhere in the file (the page does the storing and the moving).
Functions and `var` names become globals of the page. Never modify the arguments; return new objects. No comments and no docstrings, small helpers instead of copied code.
'''

JS_HEAD = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const box = { Math: Math, JSON: JSON, console: console, Array: Array, isFinite: isFinite, isNaN: isNaN };
vm.createContext(box); vm.runInContext(fs.readFileSync("window_state.js", "utf8"), box);
const plain = v => JSON.parse(JSON.stringify(v));
const DESK = {width: 1366, height: 730};
'''

JS1 = r'''
assert.strictEqual(box.WINDOW_STATE_KEY, "guppi.windows.v1");
assert.deepStrictEqual(plain(box.WINDOW_MIN), {width: 320, height: 200});
assert.deepStrictEqual(plain(box.WINDOW_KEEP), {width: 80, height: 70});
const cb = (b, d, m) => plain(box.clampBox(b, d, m));
assert.deepStrictEqual(cb({left: 100, top: 50, width: 600, height: 400}, DESK, {width: 320, height: 200}), {left: 100, top: 50, width: 600, height: 400});
assert.deepStrictEqual(cb({left: -5, top: -1, width: 600, height: 400}, DESK, {width: 320, height: 200}), {left: 0, top: 0, width: 600, height: 400});
assert.deepStrictEqual(cb({left: 2000, top: 900, width: 600, height: 400}, DESK, {width: 320, height: 200}), {left: 1286, top: 660, width: 600, height: 400});
assert.deepStrictEqual(cb({left: 0, top: 0, width: 100, height: 50}, DESK, {width: 320, height: 200}), {left: 0, top: 0, width: 320, height: 200});
assert.deepStrictEqual(cb({left: 0, top: 0, width: 5000, height: 5000}, DESK, {width: 320, height: 200}), {left: 0, top: 0, width: 1366, height: 730});
assert.deepStrictEqual(cb({left: 0, top: 0, width: 5000, height: 5000}, {width: 200, height: 100}, {width: 320, height: 200}), {left: 0, top: 0, width: 320, height: 200});
assert.deepStrictEqual(cb({left: 10.4, top: 10.6, width: 400.5, height: 300.49}, DESK, {width: 320, height: 200}), {left: 10, top: 11, width: 401, height: 300});
assert.deepStrictEqual(cb({left: "a", top: null, width: NaN, height: Infinity}, DESK, {width: 320, height: 200}), {left: 0, top: 0, width: 320, height: 200});
assert.deepStrictEqual(cb(null, DESK, {width: 320, height: 200}), {left: 0, top: 0, width: 320, height: 200});
assert.deepStrictEqual(cb({left: 100, top: 100, width: 400, height: 300}, null, {width: 320, height: 200}), {left: 0, top: 0, width: 320, height: 200});
assert.deepStrictEqual(cb({left: 100, top: 100, width: 400, height: 300}, DESK, null), {left: 100, top: 100, width: 400, height: 300});
assert.deepStrictEqual(cb({left: 100, top: 100, width: 100, height: 100}, DESK, {width: 500, height: 450}), {left: 100, top: 100, width: 500, height: 450});
const src = {left: 2000, top: 900, width: 600, height: 400}; box.clampBox(src, DESK, {width: 320, height: 200}); assert.deepStrictEqual(src, {left: 2000, top: 900, width: 600, height: 400});

const cc = (i, d, s) => plain(box.cascadeBox(i, d, s));
assert.deepStrictEqual(cc(0, DESK, {width: 700, height: 500}), {left: 24, top: 24, width: 700, height: 500});
assert.deepStrictEqual(cc(1, DESK, {width: 700, height: 500}), {left: 52, top: 52, width: 700, height: 500});
assert.deepStrictEqual(cc(7, DESK, {width: 700, height: 500}), {left: 220, top: 220, width: 700, height: 500});
assert.deepStrictEqual(cc(8, DESK, {width: 700, height: 500}), {left: 24, top: 24, width: 700, height: 500});
assert.deepStrictEqual(cc(9, DESK, {width: 700, height: 500}), {left: 52, top: 52, width: 700, height: 500});
assert.deepStrictEqual(cc(-3, DESK, {width: 700, height: 500}), {left: 24, top: 24, width: 700, height: 500});
assert.deepStrictEqual(cc(2.9, DESK, {width: 700, height: 500}), {left: 80, top: 80, width: 700, height: 500});
assert.deepStrictEqual(cc("x", DESK, {width: 700, height: 500}), {left: 24, top: 24, width: 700, height: 500});
assert.deepStrictEqual(cc(0, DESK, null), {left: 24, top: 24, width: 320, height: 200});
assert.deepStrictEqual(cc(3, {width: 400, height: 300}, {width: 900, height: 900}), {left: 108, top: 108, width: 400, height: 300});
assert.deepStrictEqual(cc(0, DESK, {width: 100, height: 100}), {left: 24, top: 24, width: 320, height: 200});
console.log("ok");
'''

JS2 = r'''
const L = [{id: "b", open: true, minimized: false, maximized: false, box: {left: 10.2, top: 20, width: 500, height: 400}, z: 30},
           {id: "a", open: true, minimized: true, maximized: 1, box: {left: 0, top: 0, width: 600, height: 300}, z: 25},
           {id: "", open: true, box: {}, z: 1}, {open: true, z: 2}, null, "junk",
           {id: "c", open: 0, box: null},
           {id: "d", open: true, box: {left: "x", top: 5}, z: 25}];
const p = plain(box.packWindows(L, 777));
assert.deepStrictEqual(p, {v: 1, saved: 777, windows: [
  {id: "c", open: false, minimized: false, maximized: false, box: {left: 0, top: 0, width: 0, height: 0}, z: 0},
  {id: "a", open: true, minimized: true, maximized: true, box: {left: 0, top: 0, width: 600, height: 300}, z: 25},
  {id: "d", open: true, minimized: false, maximized: false, box: {left: 0, top: 5, width: 0, height: 0}, z: 25},
  {id: "b", open: true, minimized: false, maximized: false, box: {left: 10, top: 20, width: 500, height: 400}, z: 30}]});
assert.deepStrictEqual(plain(box.packWindows(null, 1)), {v: 1, saved: 1, windows: []});
assert.deepStrictEqual(plain(box.packWindows([], "t")), {v: 1, saved: 0, windows: []});
assert.strictEqual(plain(box.packWindows([{id: "a", z: 2.6}], 0)).windows[0].z, 3);
const before = JSON.stringify(L); box.packWindows(L, 1); assert.strictEqual(JSON.stringify(L), before);

const known = ["a", "b", "c", "guppiWindow"];
const saved = JSON.stringify(box.packWindows(L, 777));
const u = plain(box.unpackWindows(saved, known, DESK));
assert.deepStrictEqual(u, [
  {id: "c", open: false, minimized: false, maximized: false, box: {left: 0, top: 0, width: 320, height: 200}},
  {id: "a", open: true, minimized: true, maximized: true, box: {left: 0, top: 0, width: 600, height: 300}},
  {id: "b", open: true, minimized: false, maximized: false, box: {left: 10, top: 20, width: 500, height: 400}}]);
assert.deepStrictEqual(plain(box.unpackWindows(saved, ["b"], {width: 300, height: 200})), [{id: "b", open: true, minimized: false, maximized: false, box: {left: 10, top: 20, width: 320, height: 200}}]);
assert.deepStrictEqual(plain(box.unpackWindows(saved, [], DESK)), []);
assert.strictEqual(box.unpackWindows(saved, "a", DESK), null);
assert.strictEqual(box.unpackWindows(null, known, DESK), null);
assert.strictEqual(box.unpackWindows("{", known, DESK), null);
assert.strictEqual(box.unpackWindows("[]", known, DESK), null);
assert.strictEqual(box.unpackWindows(JSON.stringify({v: 2, windows: []}), known, DESK), null);
assert.strictEqual(box.unpackWindows(JSON.stringify({v: 1, windows: "x"}), known, DESK), null);
assert.deepStrictEqual(plain(box.unpackWindows(JSON.stringify({v: 1, windows: []}), known, DESK)), []);
const twice = JSON.stringify({v: 1, saved: 0, windows: [{id: "a", open: true, box: {left: 1, top: 1, width: 400, height: 300}}, {id: "a", open: false, box: {left: 9, top: 9, width: 400, height: 300}}, {id: "zz", open: true}]});
assert.deepStrictEqual(plain(box.unpackWindows(twice, known, DESK)), [{id: "a", open: true, minimized: false, maximized: false, box: {left: 1, top: 1, width: 400, height: 300}}]);
const far = JSON.stringify({v: 1, windows: [{id: "guppiWindow", open: true, box: {left: 5000, top: 5000, width: 9000, height: 9000}}]});
assert.deepStrictEqual(plain(box.unpackWindows(far, known, DESK))[0].box, {left: 1286, top: 660, width: 1366, height: 730});
console.log("ok");
'''

STAGES = [
    {"name": "clamp",
     "task": """Create `window_state.js` (a classic browser script, see NOTES.md) with:
- `var WINDOW_STATE_KEY = "guppi.windows.v1"`, `var WINDOW_MIN = {width: 320, height: 200}`, `var WINDOW_KEEP = {width: 80, height: 70}` (how much of a window must stay on the desktop).
- `clampBox(box, desk, min)` -> a new {left, top, width, height} of integers (Math.round) that fits the desktop. box, desk and min are objects with number fields;
  any field that is not a finite number counts as 0 for left/top and as the minimum for width/height; a missing object counts as {} (desk then has width 0 and height 0; a missing min means WINDOW_MIN).
  width = max(min.width, min(box.width, max(min.width, desk.width))), height the same with the heights;
  left = max(0, min(box.left, desk.width - WINDOW_KEEP.width)), top = max(0, min(box.top, desk.height - WINDOW_KEEP.height)).
- `cascadeBox(index, desk, size)` -> the box of the index-th window in a cascade: i = max(0, floor(index)) modulo 8 (a non-number index counts as 0); offset = 24 + i * 28;
  the result is clampBox({left: offset, top: offset, width: size.width, height: size.height}, desk, WINDOW_MIN) (a missing size or field means the WINDOW_MIN value).
Never modify the arguments.""",
     "host_hidden": {"hidden_window_state_1.cjs": JS_HEAD + JS1}},
    {"name": "store",
     "task": """Add to `window_state.js` (keep everything else):
- `packWindows(list, now)` -> {v: 1, saved, windows}; saved = now if it is a number, else 0. From the array list keep the entries that are objects with a non-empty string id, each as a
  NEW object {id, open, minimized, maximized, box, z}: open/minimized/maximized as booleans (!!), box = {left, top, width, height} rounded integers (a missing box or a field that is not a
  finite number counts as 0), z = rounded integer (missing counts as 0). Sort the kept windows by z ascending; equal z keep their order in list. A list that is not an array gives windows: [].
- `unpackWindows(raw, knownIds, desk)` -> an array or null. null when raw is not a string, knownIds is not an array, raw is not valid JSON, the JSON is not an object (arrays and null count as not an
  object), v is not 1 or windows is not an array. Otherwise clean every entry like packWindows does, keep only ids that are in knownIds and the FIRST entry of every id, and return
  {id, open, minimized, maximized, box} per window (no z) with box = clampBox(box, desk, WINDOW_MIN), in the stored order.
Never modify the arguments.""",
     "host_hidden": {"hidden_window_state_1.cjs": JS_HEAD + JS1, "hidden_window_state_2.cjs": JS_HEAD + JS2}},
]
