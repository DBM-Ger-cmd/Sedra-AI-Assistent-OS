/* Sedra IDE: Editorgruppen mit Reitern, Brotkrumen, eigenem Texteditor (textarea ueber gefaerbter Ebene), Minimap. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  const E = S.editor = {};
  function LHW() { return S.zeilenHoehe || 19; } /* gleich --ed-zeile */
  let felder = []; /* je Gruppe: {pfad, ta, male, zeiger, roll} oder null */
  let tabFrei = false;

  function nameVon(p) { return p === 'willkommen' ? T('wk_reiter') : S.dateien[p].name; }

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

  function baueEditor(gi, d) {
    const zeilen = el('div', { class: 'ed-zeilen', 'aria-hidden': 'true' });
    const farbe = el('pre', { class: 'ed-farbe', 'aria-hidden': 'true' });
    const aktiv = el('div', { class: 'ed-aktiv' });
    const ta = el('textarea', {
      class: 'ed-eingabe', spellcheck: 'false', autocomplete: 'off', autocapitalize: 'off', wrap: 'off',
      'aria-label': T('ed_eingabe', d.name), 'aria-multiline': 'true'
    });
    ta.value = d.inhalt;
    const mini = el('pre', { class: 'ed-mini', 'aria-hidden': 'true', title: T('ed_minimap') });
    const roll = el('div', { class: 'ed-roll' }, [zeilen, el('div', { class: 'ed-flaeche' }, [aktiv, farbe, ta])]);
    let hier = -1;

    function male() {
      S.syntax.faerbe(farbe, ta.value + '\n', d.sprache);
      S.syntax.faerbe(mini, ta.value, d.sprache);
      const n = ta.value.split('\n').length;
      while (zeilen.childElementCount < n) zeilen.appendChild(el('div', { text: String(zeilen.childElementCount + 1) }));
      while (zeilen.childElementCount > n) zeilen.removeChild(zeilen.lastChild);
    }
    function zeiger(ohneRollen) {
      const vor = ta.value.slice(0, ta.selectionStart);
      const z = vor.split('\n').length;
      const sp = vor.length - vor.lastIndexOf('\n');
      aktiv.style.top = ((z - 1) * LHW()) + 'px';
      if (hier !== z) {
        if (zeilen.children[hier - 1]) zeilen.children[hier - 1].classList.remove('hier');
        if (zeilen.children[z - 1]) zeilen.children[z - 1].classList.add('hier');
        hier = z;
      }
      if (!ohneRollen) {
        const oben = (z - 1) * LHW();
        if (oben < roll.scrollTop) roll.scrollTop = oben;
        else if (oben + LHW() > roll.scrollTop + roll.clientHeight) roll.scrollTop = oben + LHW() - roll.clientHeight;
      }
      S.melde('zeiger', { zeile: z, spalte: sp, gi: gi, auswahl: ta.selectionEnd - ta.selectionStart });
    }
    function geaendert() {
      d.inhalt = ta.value;
      male();
      zeiger();
      felder.forEach(function (f, i) {
        if (f && i !== gi && f.pfad === d.pfad) { f.ta.value = d.inhalt; f.male(); }
      });
      E.markiere(d.pfad);
      S.melde('inhalt', d.pfad);
    }

    ta.addEventListener('input', geaendert);
    ta.addEventListener('focus', function () { fokusGruppe(gi); zeiger(true); });
    ['keyup', 'click', 'select'].forEach(function (n) { ta.addEventListener(n, function () { zeiger(); }); });
    ta.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') { tabFrei = true; S.sag(T('ed_tab_frei')); return; }
      if (ev.key !== 'Tab' || ev.ctrlKey || ev.altKey || ev.metaKey) return;
      if (tabFrei) { tabFrei = false; return; }
      ev.preventDefault();
      if (ev.shiftKey) {
        const anfang = ta.value.lastIndexOf('\n', ta.selectionStart - 1) + 1;
        if (ta.value.substr(anfang, 2) === '  ') ta.setRangeText('', anfang, anfang + 2, 'preserve');
      } else ta.setRangeText('  ', ta.selectionStart, ta.selectionEnd, 'end');
      geaendert();
    });
    mini.addEventListener('click', function (ev) {
      const r = mini.getBoundingClientRect();
      const z = Math.max(1, Math.round((ev.clientY - r.top - 2) / 3) + 1);
      E.geheZu(z, gi);
    });

    male();
    felder[gi] = { pfad: d.pfad, ta: ta, male: male, zeiger: zeiger, roll: roll };
    return el('div', { class: 'ed-koerper', role: 'tabpanel', 'aria-label': d.name }, [roll, mini]);
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
    const kasten = S.leere(S.q('editorbereich'));
    felder = [];
    S.gruppen.forEach(function (g, gi) { kasten.appendChild(gruppe(g, gi)); });
    if (S.fokusReiter) {
      const fr = S.fokusReiter;
      S.fokusReiter = null;
      const g = kasten.children[fr.gi];
      const r = g ? g.querySelector('.reiter.aktiv') : null;
      if (r) { r.focus(); S.melde('aktiv'); return; }
    }
    const f = felder[S.aktiveGruppe];
    if (f) { if (mitFokus) f.ta.focus(); f.zeiger(true); }
    else S.melde('zeiger', null);
    S.melde('aktiv');
  };

  /* Ungespeichert-Punkt am Reiter setzen, ohne neu zu zeichnen. */
  E.markiere = function (pfad) {
    const offen = S.ungespeichert(pfad);
    const alle = S.q('editorbereich').querySelectorAll('.reiter');
    for (let i = 0; i < alle.length; i++) if (alle[i].dataset.pfad === pfad) alle[i].classList.toggle('ungespeichert', offen);
  };

  E.geheZu = function (zeile, gi) {
    const f = felder[gi == null ? S.aktiveGruppe : gi];
    if (!f) return false;
    const zeilen = f.ta.value.split('\n');
    const z = Math.min(Math.max(1, zeile | 0), zeilen.length);
    let pos = 0;
    for (let i = 0; i < z - 1; i++) pos += zeilen[i].length + 1;
    f.ta.focus();
    f.ta.setSelectionRange(pos, pos);
    f.zeiger();
    f.roll.scrollTop = Math.max(0, (z - 1) * LHW() - f.roll.clientHeight / 3);
    return true;
  };

  E.oeffneBei = function (pfad, zeile) {
    S.oeffne(pfad);
    E.geheZu(zeile);
  };

  E.fokus = function () { const f = felder[S.aktiveGruppe]; if (f) f.ta.focus(); };
  E.zeilenZahl = function () { const f = felder[S.aktiveGruppe]; return f ? f.ta.value.split('\n').length : 0; };

  S.an('editor', function () { E.zeichnen(true); });
  S.an('gespeichert', function (p) { E.markiere(p); });
  S.an('sprache', function () { E.zeichnen(false); });
})(window);
