/* Sedra IDE: Syntaxfarben und Gliederung fuer JS, Python, YAML, Markdown. Ausgabe nur ueber textContent. */
(function (root) {
  'use strict';
  const S = root.SIDE;
  const X = S.syntax = {};

  function menge(t) { const m = {}; t.split(' ').forEach(function (w) { m[w] = true; }); return m; }
  const WORT = {
    js: menge('const let var function return if else for while do class new import export from default async await try catch finally throw typeof instanceof this super null true false undefined of in switch case break continue extends static get set delete void yield'),
    sh: menge('if then else elif fi for do done while until case esac in function select time export local readonly return break continue exit set unset shift source alias echo cd test'),
    py: menge('def class return if elif else for while import from as with try except finally raise pass None True False and or not in is lambda yield async await self break continue global nonlocal assert del')
  };

  /* Je Sprache: ein Ausdruck, je Gruppe eine Art. Art "name" wird gegen die Wortliste geprueft. */
  const REGEL = {
    js: {
      re: /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\[\s\S]|[^`\\])*`)|(\b\d[\w.]*)|([A-Za-z_$][\w$]*)(?=\s*\()|([A-Za-z_$][\w$]*)/g,
      art: ['kommentar', 'text', 'zahl', 'aufruf', 'name']
    },
    py: {
      re: /(#[^\n]*)|([fFrRbB]?"""[\s\S]*?"""|[fFrRbB]?'''[\s\S]*?'''|[fFrRbB]?"(?:\\.|[^"\\\n])*"|[fFrRbB]?'(?:\\.|[^'\\\n])*')|(\b\d[\w.]*)|(@[\w.]+)|([A-Za-z_]\w*)(?=\s*\()|([A-Za-z_]\w*)/g,
      art: ['kommentar', 'text', 'zahl', 'typ', 'aufruf', 'name']
    },
    yaml: {
      re: /(#[^\n]*)|("(?:\\.|[^"\\\n])*"|'[^'\n]*')|(^[ \t]*(?:- )?[A-Za-z_][\w.-]*(?=[ \t]*:))|(\b\d[\d.]*\b)|(\b(?:true|false|null|yes|no|ja|nein)\b)/gm,
      art: ['kommentar', 'text', 'schluessel', 'zahl', 'wort']
    },
    json: {
      re: /("(?:\\.|[^"\\\n])*"(?=\s*:))|("(?:\\.|[^"\\\n])*")|(-?\b\d[\d.eE+\-]*\b)|(\b(?:true|false|null)\b)/g,
      art: ['schluessel', 'text', 'zahl', 'wort']
    },
    css: {
      re: /(\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|(@[\w-]+)|(#[0-9a-fA-F]{3,8}\b)|(-?\b\d[\d.]*(?:px|em|rem|%|vh|vw|ms|s|deg|fr)?)|([\w-]+)(?=\s*:)|([.#][A-Za-z_][\w-]*)/g,
      art: ['kommentar', 'text', 'wort', 'zahl', 'zahl', 'schluessel', 'typ']
    },
    html: {
      re: /(<!--[\s\S]*?-->)|("[^"\n]*"|'[^'\n]*')|(<\/?[A-Za-z][\w:-]*)|([A-Za-z_:][\w:.-]*)(?==)|(&[#\w]+;)|(\/?>)/g,
      art: ['kommentar', 'text', 'wort', 'schluessel', 'zahl', 'wort']
    },
    sh: {
      re: /(#[^\n]*)|("(?:\\.|[^"\\\n])*"|'[^'\n]*')|(\$\{[^}\n]*\}|\$[A-Za-z_]\w*|\$[0-9@#?!*$-])|(\b\d+\b)|([A-Za-z_][\w-]*)/g,
      art: ['kommentar', 'text', 'typ', 'zahl', 'name']
    },
    md: {
      re: /(^#{1,6} [^\n]*)|(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(^[ \t]*(?:[-*]|\d+\.) )|(\[[^\]\n]+\]\([^)\n]+\))/gm,
      art: ['titel', 'text', 'typ', 'schluessel', 'funktion']
    }
  };

  function stueck(ziel, text, art) {
    if (!text) return;
    if (!art) { ziel.appendChild(document.createTextNode(text)); return; }
    const sp = document.createElement('span');
    sp.className = 'syn-' + art;
    sp.textContent = text;
    ziel.appendChild(sp);
  }

  function artVon(roh, wort, sprache) {
    const liste = WORT[sprache] || {};
    const istWort = Object.prototype.hasOwnProperty.call(liste, wort);
    if (roh === 'aufruf') return istWort ? 'wort' : 'funktion';
    if (roh === 'name') {
      if (istWort) return 'wort';
      return sprache !== 'sh' && /^[A-Z][a-z]/.test(wort) ? 'typ' : '';
    }
    return roh;
  }

  /* Text in Stücke [{ t, art }] zerlegen (art '' = ungefärbt). Ohne Oberfläche, deshalb auch in Node prüfbar. */
  X.zerlege = function (text, sprache) {
    const r = REGEL[sprache], aus = [];
    if (!r) return [{ t: text, art: '' }];
    r.re.lastIndex = 0;
    let pos = 0, m;
    while ((m = r.re.exec(text)) !== null) {
      if (m[0] === '') { r.re.lastIndex += 1; continue; }
      if (m.index > pos) aus.push({ t: text.slice(pos, m.index), art: '' });
      let roh = '';
      for (let i = 1; i < m.length; i++) if (m[i] !== undefined) { roh = r.art[i - 1]; break; }
      aus.push({ t: m[0], art: artVon(roh, m[0], sprache) });
      pos = m.index + m[0].length;
    }
    if (pos < text.length) aus.push({ t: text.slice(pos), art: '' });
    return aus;
  };
  X.SPRACHEN = Object.keys(REGEL);

  /* Faerbt text in das Element ziel (wird geleert). */
  X.faerbe = function (ziel, text, sprache) {
    const frag = document.createDocumentFragment();
    X.zerlege(text, sprache).forEach(function (st) { stueck(frag, st.t, st.art); });
    S.leere(ziel).appendChild(frag);
  };

  /* Gliederung: Liste {name, zeile, art, tiefe}. */
  const GLIED = {
    js: [[/^\s*class\s+([A-Za-z_$][\w$]*)/, 'klasse'], [/^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/, 'funktion'],
      [/^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=/, 'wert'], [/^\s{2}(?!if|for|while|switch|return)([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{/, 'methode']],
    py: [[/^\s*class\s+([A-Za-z_]\w*)/, 'klasse'], [/^(\s*)def\s+([A-Za-z_]\w*)/, 'funktion']],
    yaml: [[/^([A-Za-z_][\w.-]*)\s*:/, 'schluessel'], [/^ {2}([A-Za-z_][\w.-]*)\s*:/, 'unter']],
    md: [[/^(#{1,6})\s+(.*)$/, 'titel']]
  };
  X.gliederung = function (text, sprache) {
    const regeln = GLIED[sprache];
    const aus = [];
    if (!regeln) return aus;
    text.split('\n').forEach(function (zeile, i) {
      for (let k = 0; k < regeln.length; k++) {
        const m = regeln[k][0].exec(zeile);
        if (!m) continue;
        const art = regeln[k][1];
        let name = m[m.length - 1], tiefe = 0;
        if (art === 'titel') tiefe = m[1].length - 1;
        else if (art === 'methode' || art === 'unter') tiefe = 1;
        else if (art === 'funktion' && sprache === 'py') tiefe = m[1].length ? 1 : 0;
        aus.push({ name: name, zeile: i + 1, art: art, tiefe: tiefe });
        break;
      }
    });
    return aus;
  };

  /* Einfache Hinweise fuer das Panel "Probleme" (Beispielregeln, kein echter Pruefer). */
  X.hinweise = function (d) {
    const aus = [];
    d.inhalt.split('\n').forEach(function (zeile, i) {
      if (/\bTODO\b/.test(zeile)) aus.push({ art: 'warnung', key: 'pb_todo', datei: d.pfad, zeile: i + 1 });
      if (/[ \t]+$/.test(zeile)) aus.push({ art: 'warnung', key: 'pb_leerraum', datei: d.pfad, zeile: i + 1 });
      if (/\t/.test(zeile) && d.sprache === 'yaml') aus.push({ art: 'fehler', key: 'pb_tab_yaml', datei: d.pfad, zeile: i + 1 });
    });
    return aus;
  };
  X.alleHinweise = function () {
    let aus = [];
    Object.keys(S.dateien).sort().forEach(function (p) { aus = aus.concat(X.hinweise(S.dateien[p])); });
    return aus;
  };
})(window);
