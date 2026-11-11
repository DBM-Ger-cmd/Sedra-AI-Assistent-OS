"""Bau-Spec zellen: zellen.js, der reine Teil der Taskleiste der Harness-Shell (AM1, Stufe A1 der Roadmap, G3 Schritt S14, Kern ohne Anbindung).
Aus den Manifesten der Instrumente und der Auswahl (leiste.json) entstehen die Zellen der Taskleiste; dazu die Rueckfallliste und die Zuordnung Klick -> Ziel.
Vier Stufen S1 bis S4, je ein Node-Test auf dem Host (host_hidden, wie window_state); kein eigener Test des Modells. Klassisches Browser-Skript, JavaScript statt Python:
dieselbe Aufgabe wie die Python-Specs, aber in einer anderen Sprache (Vergleich der Coder). Claude verdrahtet taskleiste.js, leiste.json und shell.yaml spaeter von Hand.
S1 Rueckfallliste und Pruefung der Auswahl | S2 Zellen aus Manifesten | S3 Sonderfaelle | S4 Ziel eines Klicks.
Referenz: benchmarks/devvm_refs/zellen/zellen.js. Lauf: bau_schleife.py --projekt <Ordner> --spec zellen start "<Auftrag>"."""

NOTES = '''# Notes for zellen.js
A CLASSIC browser script: no modules, no import/export, no require, no DOM, no fetch and no storage access anywhere in the file. Plain JavaScript (ES2015 is fine), ASCII only.
Top-level `var` and `function` declarations are the interface (the page and the tests read them as globals); declare ZELLEN_RUECKFALL with `var`.
Never modify the arguments; return new objects and arrays. No comments, small helpers instead of copied code. Error messages are ASCII text exactly as written in the task.
'''

TASK_S1 = '''Create `zellen.js` with:
1. `var ZELLEN_RUECKFALL` = an array of exactly these 8 objects in this order, each with exactly the keys id, feld, label, ort, aktion, quelle (a missing value is null):
   gauge-decisions: feld decisions, label "Freigaben", ort null, aktion "freigaben", quelle null
   gauge-model: model, "Modell", ort "models", aktion "modellmenue", quelle null
   gauge-temp: temp, "Temp", ort "hardware", aktion null, quelle "gpu"
   gauge-vram: vram, "VRAM belegt", ort "hardware", aktion null, quelle "gpu"
   gauge-ram: ram, "RAM frei", ort "hardware", aktion null, quelle null
   gauge-server: server, "Modellserver", ort "models", aktion "modellmenue", quelle null
   gauge-scheduler: scheduler, "Scheduler", ort "slots", aktion null, quelle null
   gauge-state: state, "Zustand", ort "machine", aktion "einstellungen:system", quelle null
2. `function pruefeAuswahl(roh)` -> {zellen: [ids]}. roh is the content of the file leiste.json: either a text (then parse it as JSON) or an already parsed object. It throws an Error with exactly these messages (checked in this order):
   - roh is a text that is not valid JSON: "Leiste: Datei ist kein gueltiges JSON"
   - the parsed value is null, an array or not an object: "Leiste: Inhalt ist kein Objekt"
   - property `zellen` is not an array: "Leiste: zellen fehlt oder ist keine Liste"
   - `zellen` is empty: "Leiste: zellen ist leer"
   - `zellen` has more than 30 entries: "Leiste: hoechstens 30 Zellen"
   - then the entries in order: an entry that is not a text matching ^[a-z0-9-]{2,40}$ throws "Leiste: ungueltige Kennung " followed by String(entry); an entry that already appeared earlier throws "Leiste: Kennung doppelt: " followed by the id.
   Valid: return {zellen: <a new array with the same ids>}. Other properties of roh (for example "_hinweis") are ignored.'''

TASK_S2 = '''Add to `zellen.js`: `function zellenAusManifest(instrumente, auswahl)` -> {zellen, fehlend, ohneZelle} (three new arrays).
instrumente is an array of manifest objects {id, kind, trust, zelle}; auswahl is {zellen: [ids]} (the result of pruefeAuswahl). Go through auswahl.zellen in order; for every id:
- Look for the FIRST manifest in instrumente with that id, kind exactly "instrument" and trust exactly "CORE". If there is none: push the id to fehlend and go on.
- If it has no usable cell, push the id to ohneZelle and go on. Usable means: manifest.zelle is an object (not null, not an array) whose feld and label are non-empty texts.
- Otherwise push {id, feld, label, ort, aktion, quelle} to zellen, with feld and label from manifest.zelle and ort, aktion, quelle from manifest.zelle when it is a non-empty text, else null.
If instrumente is not an array it counts as empty; if auswahl is not an object with an array `zellen`, there are no ids (all three results empty).
Keep everything else in the file as it is.'''

TASK_S3 = '''Extend `zellenAusManifest` in `zellen.js` (keep everything else as it is) so these cases hold:
- An id that appears more than once in auswahl.zellen is handled only at its first appearance (later copies are skipped completely, they appear in none of the three arrays).
- Entries of auswahl.zellen that are not texts are skipped. Entries of instrumente that are null or not objects are skipped.
- A manifest with trust "COMMUNITY" or "CAPTAIN" or a kind other than "instrument" counts as not there: its id ends in fehlend (a foreign module must never get a cell). If a CORE instrument with the same id comes later in instrumente, that one is used.
- The arguments are never modified.
- The result for the 8 ids of ZELLEN_RUECKFALL (in that order) and the matching manifests must be equal to ZELLEN_RUECKFALL, with fehlend and ohneZelle empty.
Everything above may already work; make sure it does.'''

TASK_S4 = '''Add to `zellen.js`: `function aktionZiel(zelle)` -> the target of a click on a cell. zelle is an object with the optional texts aktion and ort. The result is a new object:
- zelle is not an object (null, text, number): {art: "keine"}.
- aktion is exactly "freigaben", "modellmenue" or "routermenue": {art: <that text>}.
- aktion is a text that matches the whole of ^einstellungen:([a-z]+)(/([a-z]+))?$ : {art: "einstellungen", gruppe: <first group>, punkt: <second name or null>}. Example: "einstellungen:system" gives gruppe "system" and punkt null; "einstellungen:modelle/ram" gives gruppe "modelle" and punkt "ram".
- otherwise, if ort is a non-empty text: {art: "ort", ort: <ort>}. (So an aktion that is unknown or malformed does not block the ort.)
- otherwise {art: "keine"}.
The aktion is checked before the ort. Keep everything else in the file as it is.'''

JS_HEAD = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const box = {console: console};
vm.createContext(box);
vm.runInContext(fs.readFileSync("zellen.js", "utf8"), box);
const ctx = v => vm.runInContext("(" + JSON.stringify(v) + ")", box);
const plain = v => JSON.parse(JSON.stringify(v));
const msg = f => { try { f(); } catch (e) { return e.message; } return null; };
const RF = [
  {id: "gauge-decisions", feld: "decisions", label: "Freigaben", ort: null, aktion: "freigaben", quelle: null},
  {id: "gauge-model", feld: "model", label: "Modell", ort: "models", aktion: "modellmenue", quelle: null},
  {id: "gauge-temp", feld: "temp", label: "Temp", ort: "hardware", aktion: null, quelle: "gpu"},
  {id: "gauge-vram", feld: "vram", label: "VRAM belegt", ort: "hardware", aktion: null, quelle: "gpu"},
  {id: "gauge-ram", feld: "ram", label: "RAM frei", ort: "hardware", aktion: null, quelle: null},
  {id: "gauge-server", feld: "server", label: "Modellserver", ort: "models", aktion: "modellmenue", quelle: null},
  {id: "gauge-scheduler", feld: "scheduler", label: "Scheduler", ort: "slots", aktion: null, quelle: null},
  {id: "gauge-state", feld: "state", label: "Zustand", ort: "machine", aktion: "einstellungen:system", quelle: null}
];
const IDS = RF.map(z => z.id);
const manifest = z => {
  const zelle = {feld: z.feld, label: z.label};
  if (z.ort) zelle.ort = z.ort;
  if (z.aktion) zelle.aktion = z.aktion;
  if (z.quelle) zelle.quelle = z.quelle;
  return {id: z.id, kind: "instrument", trust: "CORE", zelle: zelle};
};
const MAN = RF.map(manifest);
'''

JS1 = r'''
assert.deepStrictEqual(plain(box.ZELLEN_RUECKFALL), RF);
assert.deepStrictEqual(plain(box.pruefeAuswahl(ctx({zellen: ["gauge-ram", "gauge-model"]}))), {zellen: ["gauge-ram", "gauge-model"]});
assert.deepStrictEqual(plain(box.pruefeAuswahl('{"_hinweis": "x", "zellen": ["gauge-ram"], "mehr": 1}')), {zellen: ["gauge-ram"]});
const eingabe = ctx({zellen: ["ab", "cd"]});
const aus = box.pruefeAuswahl(eingabe);
assert.notStrictEqual(aus.zellen, eingabe.zellen);
assert.strictEqual(msg(() => box.pruefeAuswahl("{kaputt")), "Leiste: Datei ist kein gueltiges JSON");
assert.strictEqual(msg(() => box.pruefeAuswahl("")), "Leiste: Datei ist kein gueltiges JSON");
assert.strictEqual(msg(() => box.pruefeAuswahl("null")), "Leiste: Inhalt ist kein Objekt");
assert.strictEqual(msg(() => box.pruefeAuswahl("[1]")), "Leiste: Inhalt ist kein Objekt");
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx(5))), "Leiste: Inhalt ist kein Objekt");
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx({}))), "Leiste: zellen fehlt oder ist keine Liste");
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx({zellen: "ab"}))), "Leiste: zellen fehlt oder ist keine Liste");
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx({zellen: []}))), "Leiste: zellen ist leer");
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx({zellen: Array.from({length: 31}, (_, i) => "z" + (10 + i))}))), "Leiste: hoechstens 30 Zellen");
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx({zellen: Array.from({length: 30}, (_, i) => "z" + (10 + i))}))), null);
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx({zellen: ["ab", 5]}))), "Leiste: ungueltige Kennung 5");
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx({zellen: ["Ab"]}))), "Leiste: ungueltige Kennung Ab");
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx({zellen: ["a"]}))), "Leiste: ungueltige Kennung a");
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx({zellen: ["ab", "cd", "ab"]}))), "Leiste: Kennung doppelt: ab");
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx({zellen: ["ab", "ab", 7]}))), "Leiste: Kennung doppelt: ab");
assert.strictEqual(msg(() => box.pruefeAuswahl(ctx({zellen: ["ab", null]}))), "Leiste: ungueltige Kennung null");
'''

JS2 = r'''
const r = box.zellenAusManifest(ctx(MAN), ctx({zellen: ["gauge-ram", "gauge-decisions", "gauge-state"]}));
assert.deepStrictEqual(plain(r.zellen), [RF[4], RF[0], RF[7]]);
assert.deepStrictEqual(plain(r.fehlend), []);
assert.deepStrictEqual(plain(r.ohneZelle), []);
const r2 = box.zellenAusManifest(ctx(MAN), ctx({zellen: ["gauge-tasks", "gauge-ram", "gauge-nix"]}));
assert.deepStrictEqual(plain(r2.zellen), [RF[4]]);
assert.deepStrictEqual(plain(r2.fehlend), ["gauge-tasks", "gauge-nix"]);
const ohne = [
  {id: "a-eins", kind: "instrument", trust: "CORE"},
  {id: "a-zwei", kind: "instrument", trust: "CORE", zelle: null},
  {id: "a-drei", kind: "instrument", trust: "CORE", zelle: [1]},
  {id: "a-vier", kind: "instrument", trust: "CORE", zelle: {feld: "x1", label: ""}},
  {id: "a-fuenf", kind: "instrument", trust: "CORE", zelle: {feld: "", label: "L"}},
  {id: "a-sechs", kind: "instrument", trust: "CORE", zelle: {feld: 5, label: "L"}},
  {id: "a-sieben", kind: "instrument", trust: "CORE", zelle: {feld: "x1", label: "Lang"}}
];
const r3 = box.zellenAusManifest(ctx(ohne), ctx({zellen: ["a-eins", "a-zwei", "a-drei", "a-vier", "a-fuenf", "a-sechs", "a-sieben"]}));
assert.deepStrictEqual(plain(r3.ohneZelle), ["a-eins", "a-zwei", "a-drei", "a-vier", "a-fuenf", "a-sechs"]);
assert.deepStrictEqual(plain(r3.zellen), [{id: "a-sieben", feld: "x1", label: "Lang", ort: null, aktion: null, quelle: null}]);
const r4 = box.zellenAusManifest(ctx([{id: "a-eins", kind: "instrument", trust: "CORE", zelle: {feld: "x1", label: "L", ort: "", aktion: 5, quelle: "q"}}]), ctx({zellen: ["a-eins"]}));
assert.deepStrictEqual(plain(r4.zellen), [{id: "a-eins", feld: "x1", label: "L", ort: null, aktion: null, quelle: "q"}]);
const leer = {zellen: [], fehlend: [], ohneZelle: []};
assert.deepStrictEqual(plain(box.zellenAusManifest(ctx(MAN), ctx({zellen: []}))), leer);
assert.deepStrictEqual(plain(box.zellenAusManifest(null, ctx({zellen: ["ab"]}))), {zellen: [], fehlend: ["ab"], ohneZelle: []});
assert.deepStrictEqual(plain(box.zellenAusManifest(ctx(MAN), null)), leer);
assert.deepStrictEqual(plain(box.zellenAusManifest(ctx(MAN), ctx({zellen: "ab"}))), leer);
assert.deepStrictEqual(plain(box.zellenAusManifest(ctx(MAN), ctx({}))), leer);
assert.ok(Array.isArray(r.zellen));
assert.notStrictEqual(r.zellen[0], r2.zellen[0]);
'''

JS3 = r'''
const dopp = box.zellenAusManifest(ctx(MAN), ctx({zellen: ["gauge-ram", "gauge-nix", "gauge-ram", "gauge-nix"]}));
assert.deepStrictEqual(plain(dopp.zellen), [RF[4]]);
assert.deepStrictEqual(plain(dopp.fehlend), ["gauge-nix"]);
const roh = ctx({zellen: ["gauge-ram", 5, null, "gauge-model"]});
assert.deepStrictEqual(plain(box.zellenAusManifest(ctx(MAN), roh).zellen), [RF[4], RF[1]]);
const mix = [null, 5, "x", MAN[4], undefined];
assert.deepStrictEqual(plain(box.zellenAusManifest(ctx(mix), ctx({zellen: ["gauge-ram"]})).zellen), [RF[4]]);
const fremd = MAN.map(m => Object.assign({}, m, {trust: "COMMUNITY"}));
const rf = box.zellenAusManifest(ctx(fremd), ctx({zellen: IDS}));
assert.deepStrictEqual(plain(rf.zellen), []);
assert.deepStrictEqual(plain(rf.fehlend), IDS);
const cap = box.zellenAusManifest(ctx(MAN.map(m => Object.assign({}, m, {trust: "CAPTAIN"}))), ctx({zellen: ["gauge-ram"]}));
assert.deepStrictEqual(plain(cap.fehlend), ["gauge-ram"]);
const werkzeug = box.zellenAusManifest(ctx(MAN.map(m => Object.assign({}, m, {kind: "tool"}))), ctx({zellen: ["gauge-ram"]}));
assert.deepStrictEqual(plain(werkzeug.fehlend), ["gauge-ram"]);
const zwei = [Object.assign({}, MAN[4], {trust: "COMMUNITY", zelle: {feld: "boese", label: "X"}}), MAN[4]];
assert.deepStrictEqual(plain(box.zellenAusManifest(ctx(zwei), ctx({zellen: ["gauge-ram"]})).zellen), [RF[4]]);
const erst = [MAN[4], Object.assign({}, MAN[4], {zelle: {feld: "zweite", label: "Z"}})];
assert.deepStrictEqual(plain(box.zellenAusManifest(ctx(erst), ctx({zellen: ["gauge-ram"]})).zellen), [RF[4]]);
const alle = box.zellenAusManifest(ctx(MAN), ctx({zellen: IDS}));
assert.deepStrictEqual(plain(alle.zellen), plain(box.ZELLEN_RUECKFALL));
assert.deepStrictEqual(plain(alle.fehlend), []);
assert.deepStrictEqual(plain(alle.ohneZelle), []);
const mi = ctx(MAN), au = ctx({zellen: IDS});
const vorher = JSON.stringify([mi, au]);
box.zellenAusManifest(mi, au);
assert.strictEqual(JSON.stringify([mi, au]), vorher);
'''

JS4 = r'''
const z = o => plain(box.aktionZiel(ctx(o)));
assert.deepStrictEqual(z({aktion: "freigaben"}), {art: "freigaben"});
assert.deepStrictEqual(z({aktion: "modellmenue", ort: "models"}), {art: "modellmenue"});
assert.deepStrictEqual(z({aktion: "routermenue"}), {art: "routermenue"});
assert.deepStrictEqual(z({aktion: "einstellungen:system"}), {art: "einstellungen", gruppe: "system", punkt: null});
assert.deepStrictEqual(z({aktion: "einstellungen:modelle/ram", ort: "x1"}), {art: "einstellungen", gruppe: "modelle", punkt: "ram"});
assert.deepStrictEqual(z({ort: "hardware"}), {art: "ort", ort: "hardware"});
assert.deepStrictEqual(z({aktion: null, ort: "slots"}), {art: "ort", ort: "slots"});
assert.deepStrictEqual(z({aktion: "unbekannt", ort: "models"}), {art: "ort", ort: "models"});
assert.deepStrictEqual(z({aktion: "einstellungen:", ort: "models"}), {art: "ort", ort: "models"});
assert.deepStrictEqual(z({aktion: "einstellungen:a/b/c", ort: "models"}), {art: "ort", ort: "models"});
assert.deepStrictEqual(z({aktion: "einstellungen:Sys"}), {art: "keine"});
assert.deepStrictEqual(z({aktion: "freigaben "}), {art: "keine"});
assert.deepStrictEqual(z({aktion: 7, ort: ""}), {art: "keine"});
assert.deepStrictEqual(z({}), {art: "keine"});
assert.deepStrictEqual(z(null), {art: "keine"});
assert.deepStrictEqual(z("freigaben"), {art: "keine"});
assert.deepStrictEqual(z(5), {art: "keine"});
assert.deepStrictEqual(plain(box.aktionZiel(undefined)), {art: "keine"});
assert.deepStrictEqual(RF.map(c => plain(box.aktionZiel(ctx(c))).art), ["freigaben", "modellmenue", "ort", "ort", "ort", "modellmenue", "ort", "einstellungen"]);
'''

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "host_hidden": {"hidden_zellen_1.cjs": JS_HEAD + JS1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "host_hidden": {"hidden_zellen_1.cjs": JS_HEAD + JS1, "hidden_zellen_2.cjs": JS_HEAD + JS2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "host_hidden": {"hidden_zellen_2.cjs": JS_HEAD + JS2, "hidden_zellen_3.cjs": JS_HEAD + JS3}},
    {"name": "S4", "task": TASK_S4, "no_own_check": True, "host_hidden": {"hidden_zellen_3.cjs": JS_HEAD + JS3, "hidden_zellen_4.cjs": JS_HEAD + JS4}},
]
TASK = TASK_S1
HIDDEN = {}
