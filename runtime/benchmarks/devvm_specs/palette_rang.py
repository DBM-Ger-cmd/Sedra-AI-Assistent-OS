"""Bau-Spec palette_rang: der rechnende Kern der Befehlspalette Strg+K (UIX-Roadmap X4, "Weniger Klicks"; die App Uebersicht nennt sie als nicht gebaut): Eingabe normalisieren, Treffer bewerten, Eintraege der Palette ordnen.
Zwei Stufen, je ein versteckter Node-Test (ein klassisches Browser-Skript, wie window_state.js); kein eigener Test des Modells. Der Bau liefert nur das Skript palette_rang.js (Zielort spaeter uix/ui/palette_rang.js): kein DOM, kein Speicher, keine Zeit.
Das Fenster der Palette, die Tastenbelegung, die Eintragsliste aus den Manifesten und das Oeffnen der App macht Claude spaeter von Hand (Vertrag der Harness-Shell, Dateien hoechstens 400 Zeilen, keine neuen setInterval).
S1 Normalisieren und Punkte | S2 Eintraege ordnen und begrenzen.
Referenz: benchmarks/devvm_refs/palette_rang/palette_rang.js."""

NOTES = '''# Notizen palette_rang.js
Ein KLASSISCHES Browser-Skript: keine Module, kein import/export, kein DOM-, Speicher- oder Zeitzugriff in der Datei. Funktionen und `var`-Namen werden Globale der Seite. Die Argumente werden nie veraendert; Ergebnisse sind neue Werte (ausser dort, wo steht, dass dasselbe Objekt zurueckkommt).
Keine Kommentare, keine Docstrings, kleine Hilfsfunktionen statt kopiertem Code. Kein eigener Test.
'''

TASK_S1 = """Lege `palette_rang.js` an (klassisches Browser-Skript, siehe NOTES) mit zwei Funktionen:
- `palNorm(s)` -> String: ist s kein String, ""; sonst s in Kleinbuchstaben (toLowerCase), jede Folge von Leerraum (auch Tabulator und Zeilenumbruch) durch ein einzelnes Leerzeichen ersetzt, am Anfang und Ende bereinigt (trim).
- `palPunkte(eingabe, text)` -> Zahl: q = palNorm(eingabe), t = palNorm(text). Ist q oder t leer: 0. Sonst die erste zutreffende Stufe: t === q: 100; t beginnt mit q: 80; ein Wort von t (t an Leerzeichen geteilt) beginnt mit q: 60; q kommt in t vor, aber nicht am Anfang: 40; alle Zeichen von q (ohne Leerzeichen) kommen in t in dieser Reihenfolge vor, nicht unbedingt nebeneinander: 20; sonst 0.
Die Argumente werden nie veraendert."""

TASK_S2 = """Ergaenze `palette_rang.js` (alles andere bleibt): `palRang(eingabe, eintraege, max)` -> neues Array. eintraege ist ein Array von Objekten {id, name, woerter?}; gueltig ist ein Eintrag, der ein Objekt (nicht null) mit einer nicht leeren String-id und einem String-name ist; alle anderen Eintraege werden uebersprungen; ist eintraege kein Array, ist das Ergebnis [].
Anzahl: m = Math.floor(max), wenn max eine endliche Zahl >= 1 ist, sonst 8.
Ist palNorm(eingabe) leer (auch bei Nicht-String), kommen die ersten m gueltigen Eintraege in der Reihenfolge der Eingabe zurueck.
Sonst bekommt jeder gueltige Eintrag die Punktzahl p = palPunkte(eingabe, name); ist woerter ein Array, ist p ausserdem das Maximum aus p und palPunkte(eingabe, w) - 10 fuer jedes w in woerter (Eintraege, die keine Strings sind, zaehlen 0 Punkte). Eintraege mit p <= 0 kommen nicht vor. Sortiert wird nach p absteigend, bei Gleichstand nach palNorm(name) aufsteigend (Vergleich mit < auf den Strings), bei erneutem Gleichstand nach der Position in der Eingabe. Das Ergebnis sind die ersten m Eintraege (dieselben Objekte, keine Kopien).
Die Argumente werden nie veraendert."""

JS_HEAD = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const box = { Math: Math, JSON: JSON, console: console, Array: Array, isFinite: isFinite, isNaN: isNaN, String: String, Number: Number, Object: Object, RegExp: RegExp };
vm.createContext(box); vm.runInContext(fs.readFileSync("palette_rang.js", "utf8"), box);
const plain = v => JSON.parse(JSON.stringify(v));
'''

JS1 = r'''
assert.strictEqual(box.palNorm("  Start   Menü  "), "start menü");
assert.strictEqual(box.palNorm("ÄÖÜ"), "äöü");
assert.strictEqual(box.palNorm("a\t\nb"), "a b");
assert.strictEqual(box.palNorm(null), "");
assert.strictEqual(box.palNorm(5), "");
const P = box.palPunkte;
assert.strictEqual(P("Logbuch", "logbuch"), 100);
assert.strictEqual(P("  LOG buch ", "Log  Buch"), 100);
assert.strictEqual(P("log", "Logbuch"), 80);
assert.strictEqual(P("buch", "Das Logbuch Buch"), 60);
assert.strictEqual(P("gbu", "Logbuch"), 40);
assert.strictEqual(P("start men", "Datei Start Menü"), 40);
assert.strictEqual(P("lgh", "Logbuch"), 20);
assert.strictEqual(P("a b", "xaxbx"), 20);
assert.strictEqual(P("ba", "ab"), 0);
assert.strictEqual(P("xyz", "Logbuch"), 0);
assert.strictEqual(P("", "Logbuch"), 0);
assert.strictEqual(P("log", ""), 0);
assert.strictEqual(P(null, "Logbuch"), 0);
assert.strictEqual(P("log", 5), 0);
console.log("ok");
'''

JS2 = r'''
const E = [{id: "a", name: "Aufgaben"}, {id: "b", name: "Logbuch", woerter: ["protokoll", "journal"]}, {id: "c", name: "Modus und Grenzen"}, {id: "d", name: "Module"}, {id: "e", name: "Einstellungen"}];
const ids = r => r.map(e => e.id);
const R = box.palRang;
assert.deepStrictEqual(plain(ids(R("aufg", E))), ["a"]);
assert.deepStrictEqual(plain(ids(R("mod", E))), ["d", "c"]);
assert.deepStrictEqual(plain(ids(R("modul", [{id: "y", name: "Module"}, {id: "x", name: "Modul"}]))), ["x", "y"]);
assert.deepStrictEqual(plain(ids(R("protok", E))), ["b"]);
assert.deepStrictEqual(plain(ids(R("journal", [{id: "q", name: "Alpha", woerter: ["journal"]}, {id: "p", name: "Journal"}]))), ["p", "q"]);
assert.deepStrictEqual(plain(ids(R("", E, 3))), ["a", "b", "c"]);
assert.deepStrictEqual(plain(ids(R("   ", E, 2))), ["a", "b"]);
assert.deepStrictEqual(plain(ids(R(null, E, 2))), ["a", "b"]);
const viele = []; for (let i = 0; i < 10; i++) viele.push({id: "i" + i, name: "Eintrag " + i});
assert.strictEqual(R("", viele).length, 8);
assert.deepStrictEqual(plain([0, -1, NaN, "3", null, undefined, Infinity].map(m => R("eintrag", viele, m).length)), [8, 8, 8, 8, 8, 8, 8]);
assert.strictEqual(R("eintrag", viele, 2).length, 2);
assert.strictEqual(R("eintrag", viele, 2.7).length, 2);
assert.strictEqual(R("aufg", E)[0], E[0]);
assert.deepStrictEqual(plain(ids(R("a", [null, "x", 5, {id: "", name: "A"}, {name: "A"}, {id: "z"}, {id: "ok", name: "Aaa"}]))), ["ok"]);
assert.deepStrictEqual(plain(R("a", null)), []);
assert.deepStrictEqual(plain(R("qqq", E)), []);
assert.deepStrictEqual(plain(ids(R("gleich", [{id: "2", name: "Gleich"}, {id: "1", name: "Gleich"}]))), ["2", "1"]);
assert.deepStrictEqual(plain(ids(R("ab", [{id: "s", name: "xaxbx"}, {id: "t", name: "ab"}]))), ["t", "s"]);
assert.deepStrictEqual(plain(ids(R("jour", [{id: "w", name: "Nichts", woerter: "journal"}, {id: "v", name: "Nichts", woerter: [5, null, "journal"]}]))), ["v"]);
const kopie = JSON.stringify(E); R("mod", E, 1); assert.strictEqual(JSON.stringify(E), kopie);
console.log("ok");
'''

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "host_hidden": {"hidden_palette_1.cjs": JS_HEAD + JS1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "host_hidden": {"hidden_palette_1.cjs": JS_HEAD + JS1, "hidden_palette_2.cjs": JS_HEAD + JS2}},
]
TASK = TASK_S1
HIDDEN = {}
