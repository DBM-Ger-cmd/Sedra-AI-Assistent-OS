/* Sedra IDE: Ansichten Suche, Quellcodeverwaltung, Ausfuehren, Erweiterungen (Attrappen mit Beispieldaten). */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  S.sucheText = '';
  let erwFilter = '';

  function marke() { return S.z.beispiel ? el('span', { class: 'beispiel-marke', text: T('beispiel') }) : null; }

  /* Suche ueber alle Beispieldateien. */
  function treffer(kasten) {
    S.leere(kasten);
    const q = S.sucheText.trim().toLowerCase();
    if (!q) { kasten.appendChild(el('div', { class: 'leer', text: T(S.quelle === 'echt' ? 'su_hinweis_echt' : 'su_hinweis') })); return; }
    let n = 0;
    Object.keys(S.dateien).sort().forEach(function (p) {
      S.dateien[p].inhalt.split('\n').forEach(function (zeile, i) {
        if (zeile.toLowerCase().indexOf(q) < 0 || n >= 200) return;
        n += 1;
        kasten.appendChild(el('div', {
          class: 'listen-zeile', role: 'listitem', tabindex: '0', title: p + ':' + (i + 1),
          on: {
            click: function () { S.editor.oeffneBei(p, i + 1); },
            keydown: function (ev) { if (ev.key === 'Enter') S.editor.oeffneBei(p, i + 1); }
          }
        }, [el('span', { class: 'zeile-name', text: zeile.trim() }), el('span', { class: 'zeile-neben', text: S.dateien[p].name + ':' + (i + 1) })]));
      });
    });
    if (!n) kasten.appendChild(el('div', { class: 'leer', text: T('su_nichts', S.sucheText) }));
    else kasten.insertBefore(el('div', { class: 'leer', text: T('su_anzahl', n) }), kasten.firstChild);
  }
  S.ansichten.suche = function () {
    const liste = el('div', { role: 'list', 'aria-live': 'polite' });
    const feld = el('input', {
      class: 'feld', type: 'search', id: 'suchfeld', placeholder: T('su_platz'), 'aria-label': T('su_platz'), data: { fid: 'su:feld' },
      on: { input: function () { S.sucheText = feld.value; treffer(liste); } }
    });
    feld.value = S.sucheText;
    treffer(liste);
    return { titel: T('an_suche'), inhalt: el('div', { class: 'seite-inhalt' }, [el('div', { class: 'feld-rand' }, [feld]), liste]) };
  };

  S.ansichten.quellcode = function () {
    const liste = el('div', { role: 'list' });
    const echt = S.quelle === 'echt';
    if (echt) liste.appendChild(el('button', { class: 'knopf', type: 'button', data: { fid: 'qc:neu' }, on: { click: function () { S.ladeGit(); } } }, [T('qc_aktualisieren')]));
    const pfade = echt ? S.echt.aenderungen.map(function (e) { return e.pfad; })
      : (S.z.beispiel ? Object.keys(S.dateien).sort().filter(function (p) { return S.dateien[p].git || S.ungespeichert(p); }) : []);
    pfade.forEach(function (p) {
      const d = { name: p.split('/').pop() };
      const m = S.gitStatus(p) || 'M';
      liste.appendChild(el('div', {
        class: 'listen-zeile', role: 'listitem', tabindex: '0', title: p, data: { fid: 'qc:' + p },
        on: { click: function () { S.oeffneDatei(p); }, keydown: function (ev) { if (ev.key === 'Enter') S.oeffneDatei(p); } }
      }, [S.sym('datei', 14), el('span', { class: 'zeile-name name-' + m, text: d.name }),
        el('span', { class: 'zeile-neben', text: p.indexOf('/') > 0 ? p.slice(0, p.lastIndexOf('/')) : '' }),
        el('span', { class: 'git git-' + m, text: m })]));
    });
    if (!pfade.length) liste.appendChild(el('div', { class: 'leer', text: T(echt ? (S.echt.gitGrund ? 'qc_git_fehlt' : 'qc_echt_hinweis') : 'leer_aenderungen') }));
    const text = el('input', { class: 'feld', type: 'text', placeholder: T('qc_nachricht'), 'aria-label': T('qc_nachricht'), data: { fid: 'qc:feld' } });
    const kopf = el('div', { class: 'feld-rand' }, [
      text,
      el('div', { class: 'knopf-reihe', style: 'margin-top:6px' }, [
        el('button', { class: 'knopf', type: 'button', data: { fid: 'qc:ok' }, on: { click: function () { S.sag(T('qc_attrappe')); } } }, [S.sym('haken', 14), T('qc_uebernehmen')]),
        marke()
      ])
    ]);
    return {
      titel: T('an_quellcode'),
      inhalt: el('div', { class: 'seite-inhalt' }, [kopf,
        S.abschnitt('abs:aenderungen', T('qc_aenderungen'), liste, el('span', { class: 'zahl blau', text: String(pfade.length) }))])
    };
  };

  S.ansichten.ausfuehren = function () {
    const liste = el('div', { role: 'list' });
    const laeufe = S.z.beispiel ? [['src/start.js', 'au_lauf_js'], ['tests/test_start.py', 'au_lauf_test']] : [];
    laeufe.forEach(function (l) {
      liste.appendChild(el('div', {
        class: 'listen-zeile', role: 'listitem', tabindex: '0', data: { fid: 'au:' + l[0] },
        on: { click: function () { S.lauf(l[0]); }, keydown: function (ev) { if (ev.key === 'Enter') S.lauf(l[0]); } }
      }, [S.sym('start', 12), el('span', { class: 'zeile-name', text: T(l[1]) }), el('span', { class: 'zeile-neben', text: l[0] })]));
    });
    if (!laeufe.length) liste.appendChild(el('div', { class: 'leer', text: T('leer_laeufe') }));
    const kopf = el('div', { class: 'feld-rand knopf-reihe' }, [
      el('button', { class: 'knopf', type: 'button', data: { fid: 'au:start' }, on: { click: function () { S.lauf((S.aktiveDatei() || {}).pfad || 'src/start.js'); } } },
        [S.sym('start', 14), T('au_start')]),
      marke()
    ]);
    return { titel: T('an_ausfuehren'), inhalt: el('div', { class: 'seite-inhalt' }, [kopf, S.abschnitt('abs:laeufe', T('au_laeufe'), liste)]) };
  };
  /* Kein echter Start: schreibt nur eine Beispielzeile in die Ausgabe. */
  S.lauf = function (pfad) {
    S.AUSGABE.push({ art: 'leise', text: '[' + new Date().toTimeString().slice(0, 8) + '] ' + T('au_gestartet', pfad) });
    S.z.panel = true;
    S.z.panelReiter = 'ausgabe';
    S.merke();
    S.melde('layout');
    S.melde('panel');
  };

  function erwZeile(e) {
    return el('div', { class: 'erw', role: 'listitem' }, [
      el('div', { class: 'erw-bild' }, [S.sym('bausteine', 20)]),
      el('div', { class: 'erw-text' }, [el('strong', { text: e.name }), el('span', { text: T(e.text_key) })]),
      e.installiert ? null : el('button', { class: 'knopf', type: 'button', data: { fid: 'erw:' + e.name },
        on: { click: function () { S.sag(T('erw_attrappe')); } } }, [T('erw_installieren')])
    ]);
  }
  function erwListen(inst, empf) {
    const q = erwFilter.trim().toLowerCase();
    S.leere(inst); S.leere(empf);
    const alle = (S.z.beispiel ? S.ERWEITERUNGEN : []).filter(function (e) { return !q || e.name.toLowerCase().indexOf(q) >= 0; });
    alle.forEach(function (e) { (e.installiert ? inst : empf).appendChild(erwZeile(e)); });
    [inst, empf].forEach(function (k) { if (!k.childElementCount) k.appendChild(el('div', { class: 'leer', text: T('leer_erweiterungen') })); });
  }
  S.ansichten.erweiterungen = function () {
    const inst = el('div', { role: 'list' }), empf = el('div', { role: 'list' });
    const feld = el('input', {
      class: 'feld', type: 'search', placeholder: T('erw_platz'), 'aria-label': T('erw_platz'), data: { fid: 'erw:feld' },
      on: { input: function () { erwFilter = feld.value; erwListen(inst, empf); } }
    });
    feld.value = erwFilter;
    erwListen(inst, empf);
    const alle = S.z.beispiel ? S.ERWEITERUNGEN : [];
    const nInst = alle.filter(function (e) { return e.installiert; }).length;
    return {
      titel: T('an_erweiterungen'),
      inhalt: el('div', { class: 'seite-inhalt' }, [
        el('div', { class: 'feld-rand' }, [feld]),
        S.abschnitt('abs:erwInst', T('erw_installiert'), inst, el('span', { class: 'zahl blau', text: String(nInst) })),
        S.abschnitt('abs:erwEmpf', T('erw_empfohlen'), empf, el('span', { class: 'zahl blau', text: String(alle.length - nInst) }))
      ])
    };
  };
})(window);
