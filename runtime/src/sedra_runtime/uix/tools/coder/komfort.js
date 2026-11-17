/* Sedra IDE: Suchen und Ersetzen in der Datei (Strg+F) für den Editorkern. Alles passiert nur im Text des Editors, nichts wird gespeichert oder gesendet.
   Die Tasten des Editors (Einrücken, Klammern, Kommentar, Zeilen, Mehrfach-Cursor, Falten, Umbruch) stehen in kern_eingabe.js. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T, K = S.kern;
  const F = S.komfort = {};
  let leiste = null;

  F.zu = function () {
    if (leiste) { leiste.remove(); leiste = null; }
    S.editor.fokus();
  };

  /* Alle Treffer (Groß-/Kleinschreibung egal) als Bereiche {von, bis} in Zeilen und Spalten. */
  function treffer(doc, q) {
    const aus = [];
    if (!q) return aus;
    const n = q.toLowerCase();
    if (n.indexOf('\n') >= 0) return aus;
    for (let z = 0; z < doc.zeilen.length && aus.length < 5000; z++) {
      const t = doc.zeilen[z].toLowerCase();
      let i = t.indexOf(n);
      while (i >= 0 && aus.length < 5000) { aus.push({ von: { z: z, s: i }, bis: { z: z, s: i + n.length } }); i = t.indexOf(n, i + Math.max(1, n.length)); }
    }
    return aus;
  }

  F.finde = function () {
    const v = S.editor.ansicht();
    if (!v) return false;
    const doc = v.doc, gruppe = S.q('editorbereich').children[S.aktiveGruppe];
    if (leiste) leiste.remove();
    const s0 = v.sel[v.sel.length - 1], b0 = K.bereich(s0);
    const vorauswahl = !K.leer(s0) && b0.von.z === b0.bis.z ? doc.zeilen[b0.von.z].slice(b0.von.s, b0.bis.s) : '';
    const info = el('span', { class: 'zeile-neben', 'aria-live': 'polite' });
    const feld = el('input', { class: 'feld', type: 'text', placeholder: T('kf_suchen'), 'aria-label': T('kf_suchen'), data: { fid: 'kf:feld' } });
    const ers = el('input', { class: 'feld', type: 'text', placeholder: T('kf_ersetzen'), 'aria-label': T('kf_ersetzen'), data: { fid: 'kf:ersetzen' } });
    feld.value = vorauswahl;

    function springe(richtung) {
      const liste = treffer(doc, feld.value);
      info.textContent = feld.value ? (liste.length ? T('kf_anzahl', liste.length) : T('kf_keine')) : '';
      if (!liste.length) return;
      const k = v.sel[v.sel.length - 1], b = K.bereich(k);
      let i;
      if (richtung > 0) { i = liste.findIndex(function (t) { return K.vergleiche(t.von, b.bis) >= 0 && !(K.gleich(t.von, b.von) && K.gleich(t.bis, b.bis)); }); if (i < 0) i = 0; }
      else { i = -1; for (let n = liste.length - 1; n >= 0; n--) if (K.vergleiche(liste[n].von, b.von) < 0) { i = n; break; } if (i < 0) i = liste.length - 1; }
      v.setzeAuswahl([{ a: liste[i].von, k: liste[i].bis, w: liste[i].bis.s }], false);
      v.roll.scrollTop = Math.max(0, v.zeilenY(liste[i].von.z) - v.roll.clientHeight / 3);
      feld.focus();
      info.textContent = T('kf_von', i + 1, liste.length);
    }
    function ersetzeEins() {
      const k = v.sel[v.sel.length - 1], b = K.bereich(k);
      if (!feld.value || K.leer(k) || doc.textZwischen(b.von, b.bis).toLowerCase() !== feld.value.toLowerCase()) { springe(1); return; }
      v.setzeAuswahl(K.tippe(doc, [k], ers.value, ''), false);
      springe(1);
    }
    function ersetzeAlle() {
      const liste = treffer(doc, feld.value);
      if (!liste.length) return;
      v.setzeAuswahl(K.mehrfach(doc, v.sel, liste.map(function (t) { return { von: t.von, bis: t.bis, neu: ers.value }; }), ''), false);
      S.sag(T('kf_ersetzt', liste.length));
      info.textContent = '';
    }
    feld.addEventListener('input', function () { springe(1); });
    feld.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); springe(ev.shiftKey ? -1 : 1); } });
    ers.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); ersetzeEins(); } });
    leiste = el('div', { class: 'finde-leiste', role: 'search', 'aria-label': T('kf_suchen'),
      on: { keydown: function (ev) { if (ev.key === 'Escape') { ev.stopPropagation(); F.zu(); } } } }, [
      feld, ers, info,
      el('button', { class: 'knopf', type: 'button', data: { fid: 'kf:zurueck' }, title: T('kf_vorher'), on: { click: function () { springe(-1); } } }, ['↑']),
      el('button', { class: 'knopf', type: 'button', data: { fid: 'kf:weiter' }, title: T('kf_weiter'), on: { click: function () { springe(1); } } }, ['↓']),
      el('button', { class: 'knopf', type: 'button', data: { fid: 'kf:eins' }, on: { click: ersetzeEins } }, [T('kf_eins')]),
      el('button', { class: 'knopf', type: 'button', data: { fid: 'kf:alle' }, on: { click: ersetzeAlle } }, [T('kf_alle')]),
      S.symKnopf('zu', T('kf_zu'), F.zu, { data: { fid: 'kf:zu' } })
    ]);
    gruppe.appendChild(leiste);
    feld.focus(); feld.select();
    if (vorauswahl) springe(1);
    return true;
  };

  S.an('editor', function () { leiste = null; });
})(window);
