/* Sedra IDE: Editorgruppen mit Reitern, Brotkrumen und dem eigenen Editorkern (kern_*.js), Minimap. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T, K = S.kern;
  const E = S.editor = {};
  let felder = []; /* je Gruppe: {pfad, v, male, zeiger, roll, ta} oder null */

  function nameVon(p) { return p === 'willkommen' ? T('wk_reiter') : S.dateien[p].name; }

  /* Die Datei bekommt ein Textmodell. d.inhalt bleibt als Text lesbar und setzbar (Speichern, Suche, Agent lesen ihn unverändert). */
  function bindeDatei(d) {
    if (d.doc) return d.doc;
    const doc = K.neu(d.inhalt);
    d.doc = doc;
    Object.defineProperty(d, 'inhalt', { get: function () { return doc.text(); }, set: function (t) { if (t !== doc.text()) doc.setzeText(t); }, enumerable: true, configurable: true });
    doc.an(function () { E.markiere(d.pfad); S.melde('inhalt', d.pfad); });
    return doc;
  }

  function reiter(g, gi, p) {
    const d = S.dateien[p];
    const akt = g.aktiv === p;
    const name = nameVon(p);
    const zu = el('button', {
      class: 'reiter-zu', type: 'button', tabindex: '-1', title: T('ed_schliessen', name), 'aria-label': T('ed_schliessen', name),
      on: { click: function (ev) { ev.stopPropagation(); S.schliesse(p, gi); } }
    }, [el('span', { class: 'punkt' }), S.sym('zu', 12)]);
    return el('div', {
      class: 'reiter' + (akt ? ' aktiv' : '') + (S.ungespeichert(p) ? ' ungespeichert' : ''),
      role: 'tab', 'aria-selected': akt ? 'true' : 'false', tabindex: akt ? '0' : '-1',
      title: p === 'willkommen' ? name : p, data: { pfad: p },
      on: {
        click: function () { S.oeffne(p, gi); },
        auxclick: function (ev) { if (ev.button === 1) { ev.preventDefault(); S.schliesse(p, gi); } },
        keydown: function (ev) {
          if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') {
            ev.preventDefault();
            const n = g.reiter.length;
            const ziel = g.reiter[(g.reiter.indexOf(p) + (ev.key === 'ArrowRight' ? 1 : n - 1)) % n];
            S.fokusReiter = { gi: gi, pfad: ziel };
            S.oeffne(ziel, gi);
          } else if (ev.key === 'Delete') { ev.preventDefault(); S.schliesse(p, gi); }
          else if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); S.oeffne(p, gi); }
        }
      }
    }, [
      S.sym(p === 'willkommen' ? 'marke' : 'datei', 14),
      el('span', { class: 'reiter-name' + (d && d.git ? ' name-' + d.git : ''), text: name }),
      d && d.git ? el('span', { class: 'git git-' + d.git, text: d.git, title: T(d.git === 'U' ? 'git_neu' : 'git_geaendert') }) : null,
      zu
    ]);
  }

  function brotkrumen(p) {
    const teile = [S.ARBEITSBEREICH].concat(p.split('/'));
    const k = el('div', { class: 'brotkrumen', 'aria-label': T('ed_brotkrumen') });
    teile.forEach(function (t, i) {
      if (i) k.appendChild(S.sym('pfeilR', 10));
      k.appendChild(el('span', { class: 'stueck', text: t }));
    });
    return k;
  }

  function fokusGruppe(gi) {
    if (S.aktiveGruppe !== gi) { S.aktiveGruppe = gi; S.melde('aktiv'); }
    const alle = S.q('editorbereich').children;
    for (let i = 0; i < alle.length; i++) alle[i].classList.toggle('im-fokus', i === gi);
  }

  /* Anzahl der gewählten Zeichen der Hauptauswahl (ohne den Text zusammenzusetzen). */
  function gewaehlt(doc, s) {
    const b = K.bereich(s);
    if (b.von.z === b.bis.z) return b.bis.s - b.von.s;
    let n = doc.zeilen[b.von.z].length - b.von.s + 1;
    for (let z = b.von.z + 1; z < b.bis.z; z++) n += doc.zeilen[z].length + 1;
    return n + b.bis.s;
  }

  function baueEditor(gi, d) {
    const doc = bindeDatei(d);
    const v = K.ansicht({
      doc: doc, sprache: d.sprache, name: T('ed_eingabe', d.name), sel: d.auswahl, umbruch: !!S.z.umbruch,
      melde: function (ansicht) {
        const k = ansicht.sel[ansicht.sel.length - 1];
        d.auswahl = ansicht.sel;
        S.melde('zeiger', { zeile: k.k.z + 1, spalte: k.k.s + 1, gi: gi, auswahl: gewaehlt(doc, k), cursor: ansicht.sel.length });
      }
    });
    K.eingabe(v);
    v.eingabe.addEventListener('focus', function () { fokusGruppe(gi); E_zeiger(); });
    function E_zeiger() { const k = v.sel[v.sel.length - 1]; S.melde('zeiger', { zeile: k.k.z + 1, spalte: k.k.s + 1, gi: gi, auswahl: gewaehlt(doc, k), cursor: v.sel.length }); }

    const mini = K.mini(v);
    const weg = v.zerstoere;
    v.zerstoere = function () { mini.zerstoere(); weg(); };

    felder[gi] = { pfad: d.pfad, v: v, ta: v.eingabe, roll: v.roll, zeiger: E_zeiger, male: function () { v.neuAufbauen(); } };
    return el('div', { class: 'ed-koerper', role: 'tabpanel', 'aria-label': d.name }, [v.element, mini.element]);
  }

  function gruppe(g, gi) {
    const leiste = el('div', { class: 'reiter-leiste', role: 'tablist', 'aria-label': T('ed_reiter', gi + 1) });
    g.reiter.forEach(function (p) { leiste.appendChild(reiter(g, gi, p)); });
    const aktionen = el('div', { class: 'gruppe-aktionen' }, [
      S.symKnopf('teilen', T('bf_teilen'), function () { S.aktiveGruppe = gi; S.teile(); }),
      S.gruppen.length > 1 ? S.symKnopf('zu', T('ed_gruppe_zu'), function () {
        S.gruppen.splice(gi, 1);
        S.aktiveGruppe = Math.min(S.aktiveGruppe, S.gruppen.length - 1);
        S.merke(); S.melde('editor');
      }) : null
    ]);
    const kasten = el('div', {
      class: 'gruppe' + (gi === S.aktiveGruppe ? ' im-fokus' : ''),
      on: { mousedown: function () { fokusGruppe(gi); } }
    }, [el('div', { class: 'gruppe-kopf' }, [leiste, aktionen])]);
    felder[gi] = null;
    if (g.aktiv === 'willkommen') kasten.appendChild(S.willkommen.baue());
    else if (S.dateien[g.aktiv]) {
      kasten.appendChild(brotkrumen(g.aktiv));
      kasten.appendChild(baueEditor(gi, S.dateien[g.aktiv]));
    }
    return kasten;
  }

  E.zeichnen = function (mitFokus) {
    felder.forEach(function (f) { if (f && f.v) f.v.zerstoere(); });
    const kasten = S.leere(S.q('editorbereich'));
    felder = [];
    S.gruppen.forEach(function (g, gi) { kasten.appendChild(gruppe(g, gi)); });
    felder.forEach(function (f) { if (f) f.v.neuAufbauen(); });
    if (S.fokusReiter) {
      const fr = S.fokusReiter;
      S.fokusReiter = null;
      const g = kasten.children[fr.gi];
      const r = g ? g.querySelector('.reiter.aktiv') : null;
      if (r) { r.focus(); S.melde('aktiv'); return; }
    }
    const f = felder[S.aktiveGruppe];
    if (f) { if (mitFokus) f.ta.focus(); f.zeiger(); }
    else S.melde('zeiger', null);
    S.melde('aktiv');
  };

  /* Ungespeichert-Punkt am Reiter setzen, ohne neu zu zeichnen. */
  E.markiere = function (pfad) {
    const offen = S.ungespeichert(pfad);
    const alle = S.q('editorbereich').querySelectorAll('.reiter');
    for (let i = 0; i < alle.length; i++) if (alle[i].dataset.pfad === pfad) alle[i].classList.toggle('ungespeichert', offen);
  };

  E.ansicht = function (gi) { const f = felder[gi == null ? S.aktiveGruppe : gi]; return f ? f.v : null; };

  E.geheZu = function (zeile, gi) {
    const f = felder[gi == null ? S.aktiveGruppe : gi];
    if (!f) return false;
    const v = f.v, z = Math.min(Math.max(1, zeile | 0), v.doc.zeilen.length) - 1;
    v.entfalteBei(z);
    v.setzeAuswahl([K.auswahl({ z: z, s: 0 })], false);
    f.ta.focus();
    v.roll.scrollTop = Math.max(0, v.zeilenY(z) - v.roll.clientHeight / 3);
    return true;
  };

  E.oeffneBei = function (pfad, zeile) {
    S.oeffne(pfad);
    E.geheZu(zeile);
  };

  E.alleWaehlen = function () {
    const v = E.ansicht();
    if (v) v.setzeAuswahl([K.auswahl({ z: 0, s: 0 }, { z: v.doc.zeilen.length - 1, s: v.doc.zeilen[v.doc.zeilen.length - 1].length })], false);
  };
  E.umbruchUm = function () { S.z.umbruch = !S.z.umbruch; S.merke(); S.melde('editor'); S.sag(T(S.z.umbruch ? 'ed_umbruch_an' : 'ed_umbruch_aus')); };
  E.faltAlle = function (zu) { const v = E.ansicht(); if (v) v.faltAlle(zu); };

  E.fokus = function () { const f = felder[S.aktiveGruppe]; if (f) f.ta.focus(); };
  E.zeilenZahl = function () { const f = felder[S.aktiveGruppe]; return f ? f.v.doc.zeilen.length : 0; };

  S.an('editor', function () { E.zeichnen(true); });
  S.an('gespeichert', function (p) { E.markiere(p); });
  S.an('sprache', function () { E.zeichnen(false); });
})(window);
