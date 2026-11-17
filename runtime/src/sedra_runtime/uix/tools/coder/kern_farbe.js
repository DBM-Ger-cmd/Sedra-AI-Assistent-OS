/* Sedra IDE: Editorkern, Farben je Zeile. Mehrzeilige Stellen (Python-Docstrings, JS-Template-Strings und Blockkommentare, CSS-Kommentare, HTML-Kommentare,
   Markdown-Codeblöcke, YAML-Textblöcke) merkt sich der Kern je Zeile als Zustand am Zeilenanfang; die eigentliche Färbung steht in syntax.js.
   Die Zustände (blockZustaende) arbeiten ohne Oberfläche und sind in Node prüfbar. */
(function (root) {
  'use strict';
  const S = root.SIDE, K = S.kern;
  const TAB = 4, LANG = 3000;

  K.vtext = function (zeile) {                     /* Tabulatoren als Leerzeichen bis zum nächsten Tabstopp (für die Anzeige) */
    if (zeile.indexOf('\t') < 0) return zeile;
    let aus = '', v = 0;
    for (let i = 0; i < zeile.length; i++) {
      if (zeile.charCodeAt(i) === 9) { const w = TAB - (v % TAB); aus += ' '.repeat(w); v += w; } else { aus += zeile[i]; v += 1; }
    }
    return aus;
  };

  const YAML_BLOCK = /(?::|^\s*-)\s*[|>][+-]?\d*\s*(?:#.*)?$/;
  function einr(t) { const m = /^[ \t]*/.exec(t)[0]; return t.trim() === '' ? -1 : m.length; }

  /* Zustand nach einer Zeile, ausgehend vom Zustand davor. '' = nichts offen. */
  function weiter(sprache, st, t) {
    if (sprache === 'md') return /^\s*```/.test(t) ? (st === '```' ? '' : '```') : st;
    if (sprache === 'yaml') {
      if (st) { const n = einr(t); if (n >= 0 && n <= +st.slice(1)) st = ''; else return st; }
      return YAML_BLOCK.test(t) ? 'y' + Math.max(0, einr(t)) : '';
    }
    const strings = sprache === 'py' ? ['"""', "'''"] : null;
    for (let i = 0; i < t.length; i++) {
      if (st) {
        if (t.startsWith(st, i)) { i += st.length - 1; st = ''; } else if (t[i] === '\\' && st !== '*/' && st !== '-->') i += 1;
        continue;
      }
      if (sprache === 'py') {
        if (t[i] === '#') break;
        if (t.startsWith(strings[0], i)) { st = strings[0]; i += 2; } else if (t.startsWith(strings[1], i)) { st = strings[1]; i += 2; }
        else if (t[i] === '"' || t[i] === "'") { const q = t[i]; i += 1; while (i < t.length && t[i] !== q) { if (t[i] === '\\') i += 1; i += 1; } }
      } else if (sprache === 'js' || sprache === 'css') {
        if (sprache === 'js' && t.startsWith('//', i)) break;
        if (t.startsWith('/*', i)) { st = '*/'; i += 1; }
        else if (sprache === 'js' && t[i] === '`') st = '`';
        else if (t[i] === '"' || t[i] === "'") { const q = t[i]; i += 1; while (i < t.length && t[i] !== q) { if (t[i] === '\\') i += 1; i += 1; } }
      } else if (sprache === 'html') {
        if (t.startsWith('<!--', i)) { st = '-->'; i += 3; }
      }
    }
    return st;
  }

  K.blockZustaende = function (doc, sprache) {
    const cache = { bis: 0, w: [''] };
    cache.hole = function (z) {
      while (cache.bis < z && cache.bis < doc.zeilen.length) {
        cache.w[cache.bis + 1] = weiter(sprache, cache.w[cache.bis], doc.zeilen[cache.bis]);
        cache.bis += 1;
      }
      return cache.w[z] || '';
    };
    cache.ab = function (z) { cache.bis = Math.min(cache.bis, z); cache.w.length = cache.bis + 1; };
    return cache;
  };

  function art(zustand) { return zustand === '*/' || zustand === '-->' ? 'kommentar' : 'text'; }

  /* Eine Zeile in das Element ziel färben (mit Zustand am Zeilenanfang). */
  K.faerbeZeile = function (ziel, zeile, sprache, zustand) {
    const t = K.vtext(zeile), el = S.el;
    if (t.length > LANG || !S.syntax) { S.leere(ziel).appendChild(root.document.createTextNode(t)); return; }
    if (sprache === 'md' && (zustand === '```' || /^\s*```/.test(t))) { S.leere(ziel).appendChild(el('span', { class: 'syn-text', text: t })); return; }
    if (zustand && zustand[0] === 'y') {                       /* YAML-Textblock: die Zeile, die ihn beendet (nicht tiefer eingerückt), wird wieder normal gefärbt */
      const n = einr(t);
      if (n >= 0 && n <= +zustand.slice(1)) zustand = '';
    }
    if (zustand && (zustand[0] === 'y' || zustand === '```')) { S.leere(ziel).appendChild(el('span', { class: 'syn-text', text: t })); return; }
    if (zustand) {
      const i = t.indexOf(zustand);
      if (i < 0) { S.leere(ziel).appendChild(el('span', { class: 'syn-' + art(zustand), text: t })); return; }
      const kopf = el('span', { class: 'syn-' + art(zustand), text: t.slice(0, i + zustand.length) }), hinten = el('span');
      S.syntax.faerbe(hinten, t.slice(i + zustand.length), sprache);
      S.leere(ziel).appendChild(kopf); ziel.appendChild(hinten);
      return;
    }
    S.syntax.faerbe(ziel, t, sprache);
  };
})(typeof window !== 'undefined' ? window : globalThis);
