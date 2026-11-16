/* Sedra IDE: Namensraum, DOM-Helfer, Texte, Symbole. Kein Netz, Texte nur ueber textContent. */
(function (root) {
  'use strict';
  const S = root.SIDE = root.SIDE || {};
  S.texte = S.texte || {};

  /* Text holen; {0}, {1} werden ersetzt. Fehlt der Schluessel, kommt Deutsch, sonst der Schluessel. */
  S.T = function (k) {
    const tab = S.texte[(S.z && S.z.sprache) || 'de'] || {};
    const de = S.texte.de || {};
    let t = Object.prototype.hasOwnProperty.call(tab, k) ? tab[k] : (Object.prototype.hasOwnProperty.call(de, k) ? de[k] : k);
    for (let i = 1; i < arguments.length; i++) t = t.split('{' + (i - 1) + '}').join(String(arguments[i]));
    return t;
  };

  S.el = function (tag, a, kinder) {
    const e = document.createElement(tag);
    a = a || {};
    Object.keys(a).forEach(function (k) {
      const v = a[k];
      if (v == null || v === false) return;
      if (k === 'class') e.className = v;
      else if (k === 'text') e.textContent = v;
      else if (k === 'on') Object.keys(v).forEach(function (n) { e.addEventListener(n, v[n]); });
      else if (k === 'data') Object.keys(v).forEach(function (n) { e.dataset[n] = v[n]; });
      else e.setAttribute(k, v === true ? '' : v);
    });
    (kinder || []).forEach(function (c) {
      if (c != null && c !== false) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return e;
  };
  S.leere = function (e) { while (e.firstChild) e.removeChild(e.firstChild); return e; };
  S.q = function (id) { return document.getElementById(id); };

  /* Neu zeichnen und den Tastaturfokus (Merkmal data-fid) behalten. */
  S.mitFokus = function (kasten, fn) {
    const a = document.activeElement;
    const fid = a && kasten.contains(a) && a.dataset ? a.dataset.fid : null;
    fn();
    if (!fid) return;
    const alle = kasten.querySelectorAll('[data-fid]');
    for (let i = 0; i < alle.length; i++) if (alle[i].dataset.fid === fid) { alle[i].focus(); return; }
  };

  /* Symbole: eigene Strichzeichnungen, 16er Raster. */
  const NS = 'http://www.w3.org/2000/svg'; /* nur Namensraum-Kennung, kein Netzabruf */
  const PFAD = {
    marke: 'M3 3h10v10H3z M6 6h4 M6 8h4 M6 10h2',
    dateien: 'M5 2h5l3 3v9H5z M10 2v3h3 M3 5v9h6',
    suche: 'M7 12A5 5 0 1 0 7 2a5 5 0 0 0 0 10z M11 11l3.5 3.5',
    zweig: 'M5 5v6 M5 5a1.5 1.5 0 1 0 0-3a1.5 1.5 0 0 0 0 3z M5 14a1.5 1.5 0 1 0 0-3a1.5 1.5 0 0 0 0 3z M11 7a1.5 1.5 0 1 0 0-3a1.5 1.5 0 0 0 0 3z M11 7c0 3-6 1.500-6 4',
    start: 'M5 3l8 5-8 5z',
    bausteine: 'M2 2h5v5H2z M2 9h5v5H2z M9 9h5v5H9z M10 2h4v4h-4z',
    agent: 'M4 6h8v7H4z M8 3v3 M6.500 9v1 M9.500 9v1 M2 9v2 M14 9v2',
    zahnrad: 'M8 10.500a2.500 2.500 0 1 0 0-5a2.500 2.500 0 0 0 0 5z M8 1v2 M8 13v2 M1 8h2 M13 8h2 M3 3l1.500 1.500 M11.500 11.500L13 13 M13 3l-1.500 1.500 M4.500 11.500L3 13',
    konto: 'M8 8a3 3 0 1 0 0-6a3 3 0 0 0 0 6z M2 14c0-3 3-4 6-4s6 1 6 4',
    pfeilR: 'M6 3l5 5-5 5',
    zu: 'M4 4l8 8 M12 4l-8 8',
    datei: 'M4 2h5l3 3v9H4z M9 2v3h3',
    ordner: 'M2 4h4l1.500 2H14v7H2z',
    links: 'M2 3h12v10H2z M6 3v10',
    unten: 'M2 3h12v10H2z M2 9h12',
    rechts: 'M2 3h12v10H2z M10 3v10',
    zurueck: 'M8 3L3 8l5 5 M3 8h10',
    vor: 'M8 3l5 5-5 5 M13 8H3',
    teilen: 'M2 3h12v10H2z M8 3v10',
    plus: 'M8 3v10 M3 8h10',
    senden: 'M2 8l12-5-5 12-2-5z',
    fehler: 'M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12z M6 6l4 4 M10 6l-4 4',
    warnung: 'M8 2l6.500 12h-13z M8 7v3 M8 12v0.500',
    uhr: 'M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12z M8 5v3l2 2',
    gliederung: 'M3 4h4 M5 8h8 M5 12h8 M3 4v8',
    verbinden: 'M3 13l4-4 M9 7l4-4 M6 6l4 4 M4 8l4 4 M8 4l4 4',
    thema: 'M8 14A6 6 0 1 0 8 2z M8 2v12',
    haken: 'M3 8l3.500 3.500L13 5'
  };
  S.sym = function (name, gr, klasse) {
    const s = document.createElementNS(NS, 'svg');
    s.setAttribute('viewBox', '0 0 16 16');
    s.setAttribute('width', gr || 16);
    s.setAttribute('height', gr || 16);
    s.setAttribute('fill', 'none');
    s.setAttribute('stroke', 'currentColor');
    s.setAttribute('stroke-width', '1.2');
    s.setAttribute('stroke-linecap', 'round');
    s.setAttribute('stroke-linejoin', 'round');
    s.setAttribute('aria-hidden', 'true');
    s.setAttribute('class', 'sym' + (klasse ? ' ' + klasse : ''));
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', PFAD[name] || PFAD.datei);
    s.appendChild(p);
    return s;
  };

  /* Knopf nur mit Symbol; Name fuer Vorleser und Kurzinfo. */
  S.symKnopf = function (sym, name, tun, extra) {
    const a = Object.assign({ class: 'sym-knopf', type: 'button', title: name, 'aria-label': name, on: { click: tun } }, extra || {});
    return S.el('button', a, [S.sym(sym, 16)]);
  };

  let meldeUhr = null;
  S.sag = function (text) {
    const m = S.q('meldung');
    if (!m) return;
    m.textContent = text;
    if (meldeUhr) root.clearTimeout(meldeUhr);
    meldeUhr = root.setTimeout(function () { m.textContent = ''; }, 4000);
  };
})(window);
