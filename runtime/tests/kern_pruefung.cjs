/* Prüfung des Editorkerns (Textmodell, Auswahlen, Falten, Farb-Zustände, Syntax-Zerlegung) in Node, ohne Browser. Aufruf: node kern_pruefung.cjs <Ordner der Kern-Dateien>. Beendet mit Fehlercode bei der ersten falschen Annahme. */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ordner = process.argv[2];
globalThis.window = globalThis;
globalThis.SIDE = { leere: (x) => x };
// Als Skripte laden (nicht als Module), damit ein package.json mit "type": "module" weiter oben im Verzeichnisbaum nicht stört.
for (const n of ['kern_modell.js', 'kern_auswahl.js', 'kern_farbe.js', 'kern_falten.js', 'syntax.js']) vm.runInThisContext(fs.readFileSync(path.join(ordner, n), 'utf8'), { filename: n });
const K = SIDE.kern;
const P = (z, s) => ({ z, s });
const tipp = (d, sel, t) => K.tippe(d, sel, t);
const Z = (d) => JSON.stringify(d.zeilen);

// ---- Modell: ersetzen, Rückgängig, Wiederholen
{
  const d = K.neu('abc\ndef\nghi');
  let sel = [K.auswahl(P(0, 1))];
  sel = tipp(d, sel, 'X');
  assert.strictEqual(Z(d), '["aXbc","def","ghi"]');
  assert.deepStrictEqual(sel[0].k, P(0, 2));
  sel = tipp(d, sel, 'Y');
  assert.strictEqual(d.verlauf.length, 1, 'Tippen im selben Zug ist ein Schritt');
  assert.deepStrictEqual(d.zurueck()[0].k, P(0, 1));
  assert.strictEqual(Z(d), '["abc","def","ghi"]');
  d.wieder();
  assert.strictEqual(Z(d), '["aXYbc","def","ghi"]');
  const g = K.neu('ab');
  const s2 = tipp(g, [K.auswahl(P(0, 1))], '1\n2\n3');
  assert.strictEqual(Z(g), '["a1","2","3b"]');
  assert.deepStrictEqual(s2[0].k, P(2, 1));
  g.zurueck();
  assert.strictEqual(Z(g), '["ab"]');
  assert.strictEqual(K.neu('').zeilen.length, 1, 'leeres Dokument hat eine Zeile');
  assert.deepStrictEqual(K.neu('a\r\nb').zeilen, ['a\r', 'b'], 'das Modell trennt nur an LF (der Editor bekommt LF-Text)');
}

// ---- Mehrfach-Cursor: Tippen, Löschen, Rückgängig als ein Schritt
{
  const d = K.neu('a\nb\nc');
  let sel = [K.auswahl(P(0, 0)), K.auswahl(P(1, 0)), K.auswahl(P(2, 0))];
  sel = tipp(d, sel, '> ');
  assert.strictEqual(Z(d), '["> a","> b","> c"]');
  assert.deepStrictEqual(sel.map(s => s.k.s), [2, 2, 2]);
  sel = tipp(d, sel, 'x');
  assert.strictEqual(d.verlauf.length, 1, 'mit Mehrfach-Cursor wird Tippen ebenfalls zusammengefasst');
  sel = K.loesche(d, sel, false, false);
  sel = K.loesche(d, sel, false, false);
  assert.strictEqual(Z(d), '[">a",">b",">c"]');
  d.zurueck();
  assert.strictEqual(d.zeilen[0].length >= 2, true);
  // verteilt: gleich viele Zeilen wie Cursor
  const e = K.neu('1\n2\n3');
  const s3 = K.tippe(e, [K.auswahl(P(0, 1)), K.auswahl(P(1, 1)), K.auswahl(P(2, 1))], 'a\nb\nc');
  assert.strictEqual(Z(e), '["1a","2b","3c"]');
  assert.strictEqual(s3.length, 3);
  // Cursor auf gleicher Stelle verschmelzen
  assert.strictEqual(K.normalisiere([K.auswahl(P(0, 1)), K.auswahl(P(0, 1))]).length, 1);
  assert.strictEqual(K.normalisiere([K.auswahl(P(0, 1), P(0, 4)), K.auswahl(P(0, 2), P(0, 6))]).length, 1, 'überlappende Auswahlen verschmelzen');
}

// ---- Löschen: Zeichen, Wort, Zeilenumbruch, Klammerpaar
{
  const d = K.neu('foo bar\nbaz');
  let sel = [K.auswahl(P(0, 7))];
  sel = K.loesche(d, sel, false, true);
  assert.strictEqual(d.zeilen[0], 'foo ');
  sel = [K.auswahl(P(1, 0))];
  K.loesche(d, sel, false, false);
  assert.strictEqual(Z(d), '["foo baz"]', 'Rückwärtslöschen am Zeilenanfang verbindet die Zeilen');
  const p = K.neu('f()');
  K.loesche(p, [K.auswahl(P(0, 2))], false, false);
  assert.strictEqual(p.zeilen[0], 'f', 'leeres Klammerpaar wird zusammen entfernt');
  const q = K.neu('abc');
  K.loesche(q, [K.auswahl(P(0, 0))], false, false);
  K.loesche(q, [K.auswahl(P(0, 3))], true, false);
  assert.strictEqual(q.zeilen[0], 'abc', 'am Anfang/Ende gibt es nichts zu löschen');
}

// ---- Zeilenwerkzeuge
{
  const d = K.neu('a\nb\nc\nd');
  let sel = [K.auswahl(P(1, 0))];
  sel = K.zeileVerschieben(d, sel, true);
  assert.strictEqual(Z(d), '["a","c","b","d"]'); assert.strictEqual(sel[0].k.z, 2);
  sel = K.zeileVerschieben(d, sel, false);
  assert.strictEqual(Z(d), '["a","b","c","d"]');
  sel = K.zeileVerschieben(d, [K.auswahl(P(0, 0))], false);
  assert.strictEqual(Z(d), '["a","b","c","d"]', 'oberste Zeile lässt sich nicht nach oben schieben');
  sel = K.zeileDoppeln(d, [K.auswahl(P(0, 0), P(1, 1))], true);
  assert.strictEqual(Z(d), '["a","b","a","b","c","d"]'); assert.strictEqual(sel[0].a.z, 2);
  sel = K.zeileLoeschen(d, [K.auswahl(P(2, 0), P(3, 0))]);
  assert.strictEqual(Z(d), '["a","b","b","c","d"]', 'Auswahl bis zum Anfang der nächsten Zeile löscht diese nicht mit');
  const k = K.neu('x = 1\n\ny = 2');
  K.kommentar(k, [K.auswahl(P(0, 0), P(2, 3))], '# ');
  assert.strictEqual(Z(k), '["# x = 1","","# y = 2"]');
  K.kommentar(k, [K.auswahl(P(0, 0), P(2, 3))], '# ');
  assert.strictEqual(Z(k), '["x = 1","","y = 2"]');
  const e = K.neu('a\n  b');
  K.einruecken(e, [K.auswahl(P(0, 0), P(1, 2))], false, 2);
  assert.strictEqual(Z(e), '["  a","    b"]');
  K.einruecken(e, [K.auswahl(P(0, 0), P(1, 2))], true, 2);
  assert.strictEqual(Z(e), '["a","  b"]');
  const t = K.neu('ab'); K.einruecken(t, [K.auswahl(P(0, 1))], false, 2);
  assert.strictEqual(t.zeilen[0], 'a  b', 'Tab ohne Mehrzeilenauswahl fügt Leerzeichen ein');
}

// ---- Mehrfach-Cursor: Zeilen darüber/darunter, nächstes Vorkommen, alle Vorkommen
{
  const d = K.neu('abc\nde\nfghij');
  let sel = K.cursorDazu(d, [K.auswahl(P(0, 3))], true);
  assert.strictEqual(sel.length, 2); assert.deepStrictEqual(sel[1].k, P(1, 2), 'Spalte wird auf die Zeilenlänge begrenzt');
  sel = K.cursorDazu(d, sel, true);
  assert.deepStrictEqual(sel[2].k, P(2, 3), 'Wunschspalte bleibt');
  const e = K.neu('abc x abc y abc');
  let s = K.naechstesVorkommen(e, [K.auswahl(P(0, 1))]);
  s = K.naechstesVorkommen(e, s); s = K.naechstesVorkommen(e, s);
  assert.deepStrictEqual(s.map(x => x.a.s + '-' + x.k.s), ['0-3', '6-9', '12-15']);
  K.tippe(e, s, 'Q');
  assert.strictEqual(e.text(), 'Q x Q y Q');
  const f = K.neu('ab ab\nab');
  assert.strictEqual(K.alleVorkommen(f, [K.auswahl(P(0, 0), P(0, 2))]).length, 3);
}

// ---- Falten nach Einrückung
{
  const d = K.neu('def a():\n  x\n\n  y\nz\n  w');
  assert.strictEqual(K.faltEnde(d, 0, ''), 3, 'Leerzeile mitten im Bereich gehört dazu');
  assert.strictEqual(K.faltEnde(d, 4, ''), 5, 'Zeile z leitet den eingerückten Rest ein');
  assert.strictEqual(K.faltEnde(d, 1, ''), -1);
  assert.strictEqual(K.istFaltStart(d, 0, ''), true);
  assert.strictEqual(K.istFaltStart(d, 2, ''), false, 'Leerzeile ist kein Start');
}

// ---- Größe: viele Zeilen bleiben schnell
{
  const zeilen = []; for (let i = 0; i < 60000; i++) zeilen.push('zeile ' + i + ' ' + 'x'.repeat(20));
  const t0 = Date.now();
  const d = K.neu(zeilen.join('\n'));
  let sel = [K.auswahl(P(30000, 3))];
  for (let i = 0; i < 200; i++) sel = tipp(d, sel, 'a');
  d.text();
  assert.ok(Date.now() - t0 < 4000, 'Tippen in einer Datei mit 60000 Zeilen dauert zu lange: ' + (Date.now() - t0) + ' ms');
  assert.strictEqual(d.zeilen.length, 60000);
}

// ---- Falten je Sprache
{
  const F = (zeilen, z, sp) => K.faltEnde(K.neu(zeilen.join('\n')), z, sp);
  assert.strictEqual(F(['function f() {', '  a();', '}'], 0, 'js'), 1, 'Klammer: schließende Zeile bleibt sichtbar');
  assert.strictEqual(F(['if (x) {', '  a();', '} else {', '  b();', '}'], 0, 'js'), 1);
  assert.strictEqual(F(['if (x) {', '  a();', '} else {', '  b();', '}'], 2, 'js'), 3, 'Zeile mit } else { beginnt einen eigenen Bereich');
  assert.strictEqual(F(['{ a: 1 }', 'x'], 0, 'js'), -1, 'Klammer in einer Zeile');
  assert.strictEqual(F(['a', '  b'], 0, 'js'), -1, 'JS faltet nicht nach Einrückung');
  assert.strictEqual(F(['x = "{"', 'y'], 0, 'js'), -1, 'Klammern in Zeichenketten zählen nicht');
  assert.strictEqual(F(['x = 1 // {', 'y'], 0, 'js'), -1, 'Klammern in Zeilenkommentaren zählen nicht');
  assert.strictEqual(F(['f({', '  a: 1', '})'], 0, 'js'), 1, 'äußerste Klammer zuerst');
  assert.strictEqual(F(['{', '"a": [', '1,', '2', '],', '"b": 2', '}'], 0, 'json'), 5);
  assert.strictEqual(F(['{', '"a": [', '1,', '2', '],', '"b": 2', '}'], 1, 'json'), 3);
  assert.strictEqual(F(['a {', '  color: red;', '}'], 0, 'css'), 1);
  assert.strictEqual(F(['/*', ' * x', ' */', 'y'], 0, 'js'), 2, 'Blockkommentar bis einschließlich Schluss');
  assert.strictEqual(F(['def f():', '    """doc', '    mehr', '    """', '    return 1'], 0, 'py'), 4);
  assert.strictEqual(F(['def f():', '    """doc', '    mehr', '    """', '    return 1'], 1, 'py'), 3, 'Docstring inklusive Schlussquotes');
  assert.strictEqual(F(['# A', 'text', '## B', 'x', '# C'], 0, 'md'), 3);
  assert.strictEqual(F(['# A', 'text', '## B', 'x', '# C'], 2, 'md'), 3);
  assert.strictEqual(F(['# A', '', 'x', '', '# C'], 0, 'md'), 2, 'Leerzeilen am Ende zählen nicht zum Abschnitt');
  assert.strictEqual(F(['```', 'code', '```', 'y'], 0, 'md'), 2, 'Codeblock');
  assert.strictEqual(F(['```', '# kein Titel', '```'], 1, 'md'), -1, 'Überschrift im Codeblock zählt nicht');
  assert.strictEqual(F(['k:', '  a: 1', '  b: 2', 'z: 3'], 0, 'yaml'), 2, 'YAML nach Einrückung');
  // HTML: Tag-Paare
  assert.strictEqual(F(['<div>', '  <p>a</p>', '  <ul>', '    <li>x</li>', '  </ul>', '</div>'], 0, 'html'), 4, 'äußeres Tag, schließende Zeile bleibt sichtbar');
  assert.strictEqual(F(['<div>', '  <p>a</p>', '  <ul>', '    <li>x</li>', '  </ul>', '</div>'], 2, 'html'), 3, 'inneres Tag');
  assert.strictEqual(F(['<div>', '  <p>a</p>', '  <ul>', '    <li>x</li>', '  </ul>', '</div>'], 1, 'html'), -1, 'Tag und Schluss in einer Zeile');
  assert.strictEqual(F(['<div', '  class="a"', '  id="b">', '  x', '</div>'], 0, 'html'), 3, 'Tag mit Attributen über mehrere Zeilen');
  assert.strictEqual(F(['<div>', '<br>', '<img src=x>', '<input/>', '</div>'], 0, 'html'), 3, 'leere Tags zählen nicht');
  assert.strictEqual(F(['<script>', 'if (a < b) {', '  x();', '</script>'], 0, 'html'), 2, 'Inhalt von script wird nicht als Tags gelesen');
  assert.strictEqual(F(['<!-- <div> -->', '<p>', '  x', '</p>'], 0, 'html'), -1, 'Tags im Kommentar zählen nicht');
  assert.strictEqual(F(['<!-- a', '  b', '-->', '<p>x</p>'], 0, 'html'), 2, 'Kommentar über mehrere Zeilen');
  assert.strictEqual(F(['<ul>', '  <li>a', '  <li>b', '</ul>'], 0, 'html'), 2, 'offene li ohne Schluss stören das äußere Paar nicht');
  assert.strictEqual(F(['<div>', 'x'], 0, 'html'), -1, 'nie geschlossen');
  // Shell: Blockwörter am Befehlsanfang
  assert.strictEqual(F(['if x; then', '  a', 'else', '  b', 'fi'], 0, 'sh'), 3, 'if bis vor fi');
  assert.strictEqual(F(['if x; then', '  a', 'else', '  b', 'fi'], 2, 'sh'), 3, 'else-Zweig');
  assert.strictEqual(F(['if x; then', '  a', 'elif y; then', '  b', '  c', 'fi'], 2, 'sh'), 4, 'elif-Zweig');
  assert.strictEqual(F(['for i in 1 2; do', '  echo $i', 'done'], 0, 'sh'), 1);
  assert.strictEqual(F(['while true', 'do', '  x', 'done'], 0, 'sh'), 2, 'do in eigener Zeile');
  assert.strictEqual(F(['case $x in', '  a) echo;;', 'esac'], 0, 'sh'), 1);
  assert.strictEqual(F(['for a in 1; do', '  if b; then', '    c', '  fi', 'done'], 0, 'sh'), 3, 'verschachtelt: äußere Schleife');
  assert.strictEqual(F(['for a in 1; do', '  if b; then', '    c', '  fi', 'done'], 1, 'sh'), 2, 'verschachtelt: innere Bedingung');
  assert.strictEqual(F(['f() {', '  a', '}'], 0, 'sh'), 1, 'Funktion mit Klammern');
  assert.strictEqual(F(['echo "if x; then"', 'y'], 0, 'sh'), -1, 'Blockwörter in Zeichenketten zählen nicht');
  assert.strictEqual(F(['# if x', '  y'], 0, 'sh'), -1, 'Kommentar');
  assert.strictEqual(F(['echo done if', '  y'], 0, 'sh'), -1, 'Blockwörter als Argument zählen nicht');
  assert.strictEqual(F(['a', '  b'], 0, 'sh'), -1, 'Shell faltet nicht nach Einrückung');
  const d = K.neu('a:\n  b\nc');
  assert.strictEqual(K.istFaltStart(d, 0, 'yaml'), true);
  d.zeilen[1] = 'b'; d.version += 1;
  assert.strictEqual(K.faltEnde(d, 0, 'yaml'), -1, 'Zwischenspeicher gilt nur für diese Version');
}

// ---- Farb-Zustände am Zeilenanfang
{
  const Z = (zeilen, sp) => { const c = K.blockZustaende(K.neu(zeilen.join('\n')), sp); return zeilen.map((x, i) => c.hole(i)); };
  assert.deepStrictEqual(Z(['x = """a', 'b', 'c"""', 'y'], 'py'), ['', '"""', '"""', '']);
  assert.deepStrictEqual(Z(['s = "a # b"', 'y = 1  # """', 'z'], 'py'), ['', '', ''], 'Anführungszeichen und Kommentare täuschen keinen Block vor');
  assert.deepStrictEqual(Z(['/* a', 'b */ x', 'y'], 'js'), ['', '*/', '']);
  assert.deepStrictEqual(Z(['x = `a', '${b}', 'c`;', 'y'], 'js'), ['', '`', '`', '']);
  assert.deepStrictEqual(Z(['// /* kein Block', 'y'], 'js'), ['', '']);
  assert.deepStrictEqual(Z(['/* a', 'b */', 'y'], 'css'), ['', '*/', '']);
  assert.deepStrictEqual(Z(['<!-- a', 'b -->', '<p>'], 'html'), ['', '-->', '']);
  assert.deepStrictEqual(Z(['text', '```py', 'x = 1', '```', 'text'], 'md'), ['', '', '```', '```', '']);
  assert.deepStrictEqual(Z(['k: |', '  zeile', '  zeile2', 'other: 1', 'x: 2'], 'yaml'), ['', 'y0', 'y0', 'y0', ''], 'die beendende Zeile sieht den Block noch (die Färbung entscheidet dort)');
  assert.deepStrictEqual(Z(['a:', '  k: >-', '    x', '', '    y', '  m: 2'], 'yaml'), ['', '', 'y2', 'y2', 'y2', 'y2']);
  const dd = K.neu('x = """a\nb\nc"""'); const c = K.blockZustaende(dd, 'py');
  assert.strictEqual(c.hole(2), '"""');
  dd.zeilen[0] = 'x = 1'; c.ab(0);
  assert.strictEqual(c.hole(2), '', 'nach dem Löschen der Öffnung ist nichts mehr offen');
}

// ---- Syntax: Zerlegung (ohne Oberfläche)
{
  const X = SIDE.syntax;
  const arten = (sp, t) => X.zerlege(t, sp).filter((s) => s.art).map((s) => s.art + ':' + s.t);
  assert.deepStrictEqual(arten('json', '{"a": [1, true, "x"], "b": null}'), ['schluessel:"a"', 'zahl:1', 'wort:true', 'text:"x"', 'schluessel:"b"', 'wort:null']);
  assert.deepStrictEqual(arten('css', 'a.k { color: #fff; margin: 10px; } /* c */ @media'), ['typ:.k', 'schluessel:color', 'zahl:#fff', 'schluessel:margin', 'zahl:10px', 'kommentar:/* c */', 'wort:@media']);
  assert.deepStrictEqual(arten('html', '<div class="x" id=y>hi &amp; <!-- c --></div>').slice(0, 4), ['wort:<div', 'schluessel:class', 'text:"x"', 'schluessel:id']);
  assert.deepStrictEqual(arten('sh', 'if [ $X ]; then echo "hi" # c'), ['wort:if', 'typ:$X', 'wort:then', 'wort:echo', 'text:"hi"', 'kommentar:# c']);
  assert.deepStrictEqual(arten('py', 'def f(): return None  # x'), ['wort:def', 'funktion:f', 'wort:return', 'wort:None', 'kommentar:# x']);
  assert.deepStrictEqual(X.zerlege('irgendwas', 'txt'), [{ t: 'irgendwas', art: '' }]);
  assert.ok(['json', 'css', 'html', 'sh', 'js', 'py', 'yaml', 'md'].every((s) => X.SPRACHEN.indexOf(s) >= 0));
}

console.log('kern ok');
