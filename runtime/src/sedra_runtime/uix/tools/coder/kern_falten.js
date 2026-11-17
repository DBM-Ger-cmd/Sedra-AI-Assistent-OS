/* Sedra IDE: Editorkern, Faltbereiche (ohne Oberfläche, in Node prüfbar).
   Welche Zeile einen Bereich beginnt, hängt von der Sprache ab:
   - JS, JSON, CSS: Klammern { [ ( über mehrere Zeilen und Blockkommentare (keine Einrückung)
   - Python: Docstrings (inklusive Schlussquotes), sonst Einrückung
   - Markdown: Überschriften (bis zur nächsten gleich hohen oder höheren) und Codeblöcke
   - alles andere (YAML, Shell, HTML, Text): Einrückung
   Das Ergebnis ist die letzte Zeile des Bereichs (die ausgeblendet wird) oder -1. Es wird je Dokumentversion zwischengespeichert. */
(function (root) {
  'use strict';
  const K = root.SIDE.kern;
  const SUCHE_MAX = 20000;                              /* so viele Zeilen weit wird nach der schließenden Klammer gesucht */
  const KLAMMER = { '{': '}', '[': ']', '(': ')' };
  const LINIE = { js: '//', sh: '#', py: '#', yaml: '#' };

  /* Klammern einer Zeile außerhalb von Zeichenketten und Zeilenkommentaren: [{ z: Zeichen, i: Index }] */
  function klammern(t, sprache) {
    const aus = [], lk = LINIE[sprache];
    for (let i = 0; i < t.length; i++) {
      const c = t[i];
      if (lk && t.startsWith(lk, i)) break;
      if (c === '"' || c === "'" || (c === '`' && sprache === 'js')) { i += 1; while (i < t.length && t[i] !== c) { if (t[i] === '\\') i += 1; i += 1; } continue; }
      if (c === '{' || c === '[' || c === '(' || c === '}' || c === ']' || c === ')') aus.push({ z: c, i: i });
    }
    return aus;
  }

  /* Unzugeordnete öffnende Klammern der Zeile (die erste ist die äußerste). */
  function offene(t, sprache) {
    const stapel = [];
    klammern(t, sprache).forEach(function (k) {
      if (KLAMMER[k.z]) stapel.push(k);
      else if (stapel.length && KLAMMER[stapel[stapel.length - 1].z] === k.z) stapel.pop();
    });
    return stapel;
  }

  function klammerEnde(d, z, sprache) {
    const o = offene(d.zeilen[z], sprache)[0];
    if (!o) return -1;
    const zu = KLAMMER[o.z];
    let tiefe = 0;
    const bis = Math.min(d.zeilen.length, z + SUCHE_MAX);
    for (let n = z; n < bis; n++) {
      const ks = klammern(d.zeilen[n], sprache);
      for (let m = 0; m < ks.length; m++) {
        if (n === z && ks[m].i < o.i) continue;
        if (ks[m].z === o.z) tiefe += 1;
        else if (ks[m].z === zu) { tiefe -= 1; if (tiefe === 0) return n > z + 1 ? n - 1 : -1; }
      }
    }
    return -1;
  }

  /* Kommentar oder Docstring über mehrere Zeilen: bis einschließlich der Zeile mit dem Schluss. */
  function blockEnde(d, z, sprache) {
    const t = d.zeilen[z];
    let auf = null, zu = null;
    if ((sprache === 'js' || sprache === 'css') && /\/\*/.test(t) && !/\*\//.test(t.slice(t.indexOf('/*') + 2))) { auf = '/*'; zu = '*/'; }
    else if (sprache === 'html' && /<!--/.test(t) && t.indexOf('-->', t.indexOf('<!--')) < 0) { auf = '<!--'; zu = '-->'; }
    else if (sprache === 'py') { const q = /("""|''')/.exec(t); if (q && t.indexOf(q[1], q.index + 3) < 0) { auf = q[1]; zu = q[1]; } }
    if (!auf) return -1;
    for (let n = z + 1; n < d.zeilen.length && n < z + SUCHE_MAX; n++) if (d.zeilen[n].indexOf(zu) >= 0) return n;
    return -1;
  }

  /* Markdown: Überschriften und Codeblöcke (Überschriften in Codeblöcken zählen nicht). */
  function mdKarte(d) {
    const ende = {}, ueb = [];
    let offen = -1;
    for (let z = 0; z < d.zeilen.length; z++) {
      const t = d.zeilen[z];
      if (/^\s*```/.test(t)) { if (offen < 0) offen = z; else { if (z > offen) ende[offen] = z; offen = -1; } continue; }
      if (offen >= 0) continue;
      const m = /^(#{1,6})\s/.exec(t);
      if (m) ueb.push({ z: z, n: m[1].length });
    }
    ueb.forEach(function (h, i) {
      let bis = d.zeilen.length - 1;
      for (let k = i + 1; k < ueb.length; k++) if (ueb[k].n <= h.n) { bis = ueb[k].z - 1; break; }
      while (bis > h.z && d.zeilen[bis].trim() === '') bis -= 1;
      if (bis > h.z) ende[h.z] = bis;
    });
    return ende;
  }

  function einrueckungsEnde(d, z) {
    const e0 = K.einrueckung(d.zeilen[z]);
    if (e0 < 0) return -1;
    let ende = -1, n = z + 1;
    while (n < d.zeilen.length && K.einrueckung(d.zeilen[n]) < 0) n += 1;
    if (n >= d.zeilen.length || K.einrueckung(d.zeilen[n]) <= e0) return -1;
    for (let i = n; i < d.zeilen.length; i++) {
      const e = K.einrueckung(d.zeilen[i]);
      if (e < 0) continue;
      if (e <= e0) break;
      ende = i;
    }
    return ende;
  }

  K.faltEnde = function (d, z, sprache) {
    sprache = sprache || '';
    let c = d.faltCache;
    if (!c || c.v !== d.version || c.s !== sprache) { c = d.faltCache = { v: d.version, s: sprache, m: {}, md: null }; }
    if (z in c.m) return c.m[z];
    let e = -1;
    if (sprache === 'md') { c.md = c.md || mdKarte(d); e = c.md[z] == null ? -1 : c.md[z]; }
    else {
      e = blockEnde(d, z, sprache);
      if (e < 0 && (sprache === 'js' || sprache === 'json' || sprache === 'css')) e = klammerEnde(d, z, sprache);
      if (e < 0 && sprache !== 'json' && sprache !== 'js' && sprache !== 'css') e = einrueckungsEnde(d, z);      /* Klammersprachen: nur echte Klammern, keine Einrückung */
    }
    c.m[z] = e > z ? e : -1;
    return c.m[z];
  };
  K.istFaltStart = function (d, z, sprache) { return K.faltEnde(d, z, sprache) > z; };
})(typeof window !== 'undefined' ? window : globalThis);
