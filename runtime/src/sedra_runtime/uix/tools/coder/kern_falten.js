/* Sedra IDE: Editorkern, Faltbereiche (ohne Oberfläche, in Node prüfbar).
   Welche Zeile einen Bereich beginnt, hängt von der Sprache ab:
   - JS, JSON, CSS: Klammern { [ ( über mehrere Zeilen und Blockkommentare (keine Einrückung)
   - Python: Docstrings (inklusive Schlussquotes), sonst Einrückung
   - Markdown: Überschriften (bis zur nächsten gleich hohen oder höheren) und Codeblöcke
   - HTML: Tag-Paare über mehrere Zeilen (ohne leere Tags, Kommentare, Inhalt von script und style)
   - Shell: if/fi, for/while/until/select/done, case/esac, else- und elif-Zweige, Klammern
   - YAML, Text: Einrückung
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

  function setze(karte, z, ende) { if (ende > z && (karte[z] == null || ende > karte[z])) karte[z] = ende; }

  /* HTML: Tag-Paare über mehrere Zeilen (auch Tags mit Attributen über mehrere Zeilen). Der Inhalt von <script> und <style> wird übersprungen,
     leere Tags (br, img, …), Kommentare und selbstschließende Tags zählen nicht. Die Zeile mit dem schließenden Tag bleibt sichtbar. */
  const LEER = { area: 1, base: 1, br: 1, col: 1, embed: 1, hr: 1, img: 1, input: 1, link: 1, meta: 1, param: 1, source: 1, track: 1, wbr: 1 };
  function htmlKarte(d) {
    const karte = {}, text = d.text(), starts = [0];
    for (let i = 0; i < d.zeilen.length; i++) starts.push(starts[i] + d.zeilen[i].length + 1);
    const zeile = function (off) { let a = 0, b = d.zeilen.length - 1; while (a < b) { const m = (a + b + 1) >> 1; if (starts[m] <= off) a = m; else b = m - 1; } return a; };
    const re = /<!--[\s\S]*?-->|<(\/?)([A-Za-z][\w:-]*)((?:"[^"]*"|'[^']*'|[^'">])*)>/g, stapel = [];
    let m;
    while ((m = re.exec(text)) !== null) {
      if (m[2] === undefined) continue;                                        /* Kommentar */
      const name = m[2].toLowerCase(), z = zeile(m.index);
      if (m[1]) {
        for (let i = stapel.length - 1; i >= 0; i--) if (stapel[i].n === name) { setze(karte, stapel[i].z, z - 1); stapel.length = i; break; }
      } else if (!LEER[name] && m[3].slice(-1) !== '/') {
        stapel.push({ n: name, z: z });
        if (name === 'script' || name === 'style') { const zu = text.toLowerCase().indexOf('</' + name, re.lastIndex); if (zu > 0) re.lastIndex = zu; }
      }
    }
    return karte;
  }

  /* Shell: if…fi, for/while/until/select…done, case…esac (am Anfang eines Befehls), dazu else/elif-Zweige und Klammern { } ( ). */
  const SH_AUF = { if: 'fi', for: 'done', while: 'done', until: 'done', select: 'done', case: 'esac' };
  function shBefehle(t) {                                                       /* Zeile ohne Zeichenketten und Kommentar, in Befehle zerlegt */
    const s = t.replace(/"(?:\\.|[^"\\])*"|'[^']*'/g, '""').replace(/(^|\s)#.*$/, '$1');
    return s.split(/;|&&|\|\||\|/).map(function (x) { return x.replace(/^[\s({]+/, ''); });
  }
  function shellKarte(d) {
    const karte = {}, stapel = [];
    for (let z = 0; z < d.zeilen.length; z++) {
      shBefehle(d.zeilen[z]).forEach(function (b) {
        const w = /^[A-Za-z]+/.exec(b);
        if (!w) return;
        const k = w[0];
        if (SH_AUF[k]) stapel.push({ zu: SH_AUF[k], z: z, zweig: -1 });
        else if ((k === 'else' || k === 'elif') && stapel.length) {
          const t = stapel[stapel.length - 1];
          if (t.zweig >= 0) setze(karte, t.zweig, z - 1);
          t.zweig = z;
        } else if (k === 'fi' || k === 'done' || k === 'esac') {
          for (let i = stapel.length - 1; i >= 0; i--) if (stapel[i].zu === k) {
            if (stapel[i].zweig >= 0) setze(karte, stapel[i].zweig, z - 1);
            setze(karte, stapel[i].z, z - 1);
            stapel.length = i; break;
          }
        }
      });
    }
    return karte;
  }

  K.faltEnde = function (d, z, sprache) {
    sprache = sprache || '';
    let c = d.faltCache;
    if (!c || c.v !== d.version || c.s !== sprache) { c = d.faltCache = { v: d.version, s: sprache, m: {}, md: null }; }
    if (z in c.m) return c.m[z];
    let e = -1;
    if (sprache === 'md') { c.md = c.md || mdKarte(d); e = c.md[z] == null ? -1 : c.md[z]; }
    else if (sprache === 'html') {
      c.md = c.md || htmlKarte(d);
      e = blockEnde(d, z, sprache);
      if (e < 0) e = c.md[z] == null ? -1 : c.md[z];
    } else {
      e = blockEnde(d, z, sprache);
      if (e < 0 && sprache === 'sh') { c.md = c.md || shellKarte(d); e = c.md[z] == null ? -1 : c.md[z]; }
      if (e < 0 && (sprache === 'js' || sprache === 'json' || sprache === 'css' || sprache === 'sh')) e = klammerEnde(d, z, sprache);
      if (e < 0 && sprache !== 'json' && sprache !== 'js' && sprache !== 'css' && sprache !== 'sh') e = einrueckungsEnde(d, z);      /* Klammer- und Blocksprachen: nur echte Strukturen, keine Einrückung */
    }
    c.m[z] = e > z ? e : -1;
    return c.m[z];
  };
  K.istFaltStart = function (d, z, sprache) { return K.faltEnde(d, z, sprache) > z; };
})(typeof window !== 'undefined' ? window : globalThis);
