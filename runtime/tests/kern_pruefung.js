/* Prüfung des Editorkerns (Textmodell und Auswahlen) in Node, ohne Browser. Aufruf: node kern_pruefung.js <Ordner der Kern-Dateien>. Beendet mit Fehlercode bei der ersten falschen Annahme. */
'use strict';
const assert = require('assert');
const path = require('path');
const ordner = process.argv[2];
globalThis.window = globalThis;
globalThis.SIDE = {};
require(path.join(ordner, 'kern_modell.js'));
require(path.join(ordner, 'kern_auswahl.js'));
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
  assert.strictEqual(K.faltEnde(d, 0), 3, 'Leerzeile mitten im Bereich gehört dazu');
  assert.strictEqual(K.faltEnde(d, 4), 5, 'Zeile z leitet den eingerückten Rest ein');
  assert.strictEqual(K.faltEnde(d, 1), -1);
  assert.strictEqual(K.istFaltStart(d, 0), true);
  assert.strictEqual(K.istFaltStart(d, 2), false, 'Leerzeile ist kein Start');
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

console.log('kern ok');
