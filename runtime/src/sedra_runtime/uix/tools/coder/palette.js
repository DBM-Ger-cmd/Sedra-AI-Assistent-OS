/* Sedra IDE: Befehlspalette mit Fuzzy-Suche. ">" Befehle, ":" Zeile, sonst Dateien. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  const P = S.palette = {};
  let feld = null, liste = null, treffer = [], wahl = 0, vorher = null;

  /* Teilfolge suchen; gibt {punkte, stellen} oder null. */
  P.passt = function (q, text) {
    q = q.toLowerCase();
    const t = text.toLowerCase();
    if (!q) return { punkte: 0, stellen: [] };
    const stellen = [];
    let punkte = 0, ti = 0, letzte = -2;
    for (let qi = 0; qi < q.length; qi++) {
      const c = q[qi];
      if (c === ' ') continue;
      const i = t.indexOf(c, ti);
      if (i < 0) return null;
      punkte += 1;
      if (i === letzte + 1) punkte += 3;
      if (i === 0 || /[\s/_.\-:]/.test(t[i - 1])) punkte += 2;
      stellen.push(i);
      letzte = i;
      ti = i + 1;
    }
    return { punkte: punkte - t.length / 200, stellen: stellen };
  };

  function mitTreffern(text, stellen) {
    const s = el('span');
    let pos = 0;
    stellen.forEach(function (i) {
      if (i > pos) s.appendChild(document.createTextNode(text.slice(pos, i)));
      s.appendChild(el('span', { class: 'treffer', text: text[i] }));
      pos = i + 1;
    });
    if (pos < text.length) s.appendChild(document.createTextNode(text.slice(pos)));
    return s;
  }

  function sammle(roh) {
    const aus = [];
    if (roh[0] === ':') {
      const n = parseInt(roh.slice(1), 10);
      const max = S.editor.zeilenZahl();
      if (!max) return [{ text: T('pl_keine_datei'), neben: '', stellen: [], tun: null }];
      return [{ text: n > 0 ? T('pl_gehe_zeile', Math.min(n, max)) : T('pl_zeile_hinweis', max), neben: '', stellen: [], tun: n > 0 ? function () { S.editor.geheZu(n); } : null }];
    }
    if (roh[0] === '>') {
      const q = roh.slice(1).trim();
      S.befehle.forEach(function (b) {
        const text = T('bf_' + b.id);
        const m = P.passt(q, text);
        if (m) aus.push({ text: text, neben: S.kuerzelVon(b.id), stellen: m.stellen, punkte: m.punkte, tun: b.tun });
      });
    } else {
      const q = roh.trim();
      S.alleDateiPfade().forEach(function (p) {
        const m = P.passt(q, p);
        if (m) aus.push({ text: p, neben: S.ungespeichert(p) ? T('ex_ungespeichert') : '', stellen: m.stellen, punkte: m.punkte, tun: function () { S.oeffneDatei(p); } });
      });
    }
    if (roh.replace(/^>/, '').trim()) aus.sort(function (a, b) { return b.punkte - a.punkte; });
    return aus;
  }

  function male() {
    treffer = sammle(feld.value);
    wahl = Math.min(wahl, Math.max(0, treffer.length - 1));
    S.leere(liste);
    if (!treffer.length) { liste.appendChild(el('div', { class: 'palette-leer', text: T('pl_nichts') })); feld.removeAttribute('aria-activedescendant'); return; }
    treffer.forEach(function (t, i) {
      liste.appendChild(el('div', {
        class: 'palette-zeile' + (i === wahl ? ' gewaehlt' : ''), role: 'option', id: 'pl-' + i, 'aria-selected': i === wahl ? 'true' : 'false',
        on: { click: function () { wahl = i; nimm(); }, mousemove: function () { if (wahl !== i) { wahl = i; markiere(); } } }
      }, [mitTreffern(t.text, t.stellen), el('span', { class: 'neben', text: t.neben })]));
    });
    feld.setAttribute('aria-activedescendant', 'pl-' + wahl);
  }
  function markiere() {
    for (let i = 0; i < liste.children.length; i++) {
      const an = i === wahl;
      liste.children[i].classList.toggle('gewaehlt', an);
      liste.children[i].setAttribute('aria-selected', an ? 'true' : 'false');
      if (an) liste.children[i].scrollIntoView({ block: 'nearest' });
    }
    feld.setAttribute('aria-activedescendant', 'pl-' + wahl);
  }
  function nimm() {
    const t = treffer[wahl];
    if (!t || !t.tun) return;
    P.schliesse();
    t.tun();
  }

  P.offen = function () { return !S.q('palette').hidden; };
  P.schliesse = function (ohneFokus) {
    const k = S.q('palette');
    if (k.hidden) return;
    k.hidden = true;
    S.leere(k);
    if (!ohneFokus && vorher && document.contains(vorher)) vorher.focus();
    vorher = null;
  };
  P.oeffne = function (vor) {
    const k = S.q('palette');
    if (!k.hidden) { feld.value = vor; wahl = 0; male(); feld.focus(); return; }
    vorher = document.activeElement;
    feld = el('input', {
      class: 'palette-feld', type: 'text', role: 'combobox', 'aria-expanded': 'true', 'aria-controls': 'pl-liste', 'aria-autocomplete': 'list',
      'aria-label': T('pl_feld'), placeholder: T('pl_platz'), autocomplete: 'off', spellcheck: 'false'
    });
    liste = el('div', { class: 'palette-liste', role: 'listbox', id: 'pl-liste', 'aria-label': T('pl_feld') });
    feld.value = vor;
    feld.addEventListener('input', function () { wahl = 0; male(); });
    feld.addEventListener('keydown', function (ev) {
      if (ev.key === 'ArrowDown') { ev.preventDefault(); if (treffer.length) { wahl = (wahl + 1) % treffer.length; markiere(); } }
      else if (ev.key === 'ArrowUp') { ev.preventDefault(); if (treffer.length) { wahl = (wahl + treffer.length - 1) % treffer.length; markiere(); } }
      else if (ev.key === 'Enter') { ev.preventDefault(); nimm(); }
      else if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); P.schliesse(); }
      else if (ev.key === 'Tab') ev.preventDefault();
    });
    S.leere(k);
    k.appendChild(el('div', { class: 'palette-kasten', role: 'dialog', 'aria-modal': 'true', 'aria-label': T('bf_palette') }, [feld, liste]));
    k.hidden = false;
    wahl = 0;
    male();
    feld.focus();
    feld.setSelectionRange(feld.value.length, feld.value.length);
  };

  document.addEventListener('mousedown', function (ev) {
    if (P.offen() && ev.target === S.q('palette')) P.schliesse();
  });
})(window);
