/* Sedra IDE: Aktivitaetsleiste und linke Seitenleiste (wechselt je nach Symbol). */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  S.ansichten = {};

  const OBEN = [
    { id: 'explorer', sym: 'dateien', key: 'an_explorer' },
    { id: 'suche', sym: 'suche', key: 'an_suche' },
    { id: 'quellcode', sym: 'zweig', key: 'an_quellcode' },
    { id: 'ausfuehren', sym: 'start', key: 'an_ausfuehren' },
    { id: 'erweiterungen', sym: 'bausteine', key: 'an_erweiterungen' },
    { id: 'agenten', sym: 'agent', key: 'an_agenten' }
  ];

  /* Einklappbarer Abschnitt; Zustand wird gemerkt. */
  S.abschnitt = function (id, titel, inhalt, extra) {
    const zu = !!S.z.zugeklappt[id];
    const kopf = el('button', {
      class: 'abschnitt-kopf', type: 'button', 'aria-expanded': zu ? 'false' : 'true', data: { fid: id },
      on: { click: function () { S.z.zugeklappt[id] = !S.z.zugeklappt[id]; S.merke(); S.melde('seite'); } }
    }, [S.sym('pfeilR', 12, 'pfeil'), el('span', { class: 'titel', text: titel }), extra || null]);
    inhalt.hidden = zu;
    return el('section', { class: 'abschnitt' }, [kopf, inhalt]);
  };

  S.zeigeAnsicht = function (id) {
    if (S.z.ansicht === id && S.z.seiteLinks) { S.setze('seiteLinks', false); return; }
    S.z.ansicht = id;
    S.z.seiteLinks = true;
    S.merke();
    S.melde('layout');
    S.melde('seite');
  };
  S.oeffneAnsicht = function (id) {
    S.z.ansicht = id;
    S.z.seiteLinks = true;
    S.merke();
    S.melde('layout');
    S.melde('seite');
  };

  function geaenderteZahl() {
    return Object.keys(S.dateien).filter(function (p) { return S.dateien[p].git || S.ungespeichert(p); }).length;
  }

  function leiste() {
    const kasten = S.leere(S.q('aktivleiste'));
    kasten.setAttribute('aria-label', T('an_leiste'));
    const oben = el('div', { class: 'aktiv-gruppe', role: 'toolbar', 'aria-orientation': 'vertical', 'aria-label': T('an_leiste') });
    OBEN.forEach(function (a) {
      const aktiv = S.z.seiteLinks && S.z.ansicht === a.id;
      const k = el('button', {
        class: 'aktiv-knopf' + (aktiv ? ' aktiv' : ''), type: 'button', title: T(a.key), 'aria-label': T(a.key),
        'aria-pressed': aktiv ? 'true' : 'false', data: { fid: 'al:' + a.id },
        on: { click: function () { S.zeigeAnsicht(a.id); } }
      }, [S.sym(a.sym, 22)]);
      if (a.id === 'quellcode' && S.z.beispiel) {
        const n = geaenderteZahl();
        if (n) k.appendChild(el('span', { class: 'marke-zahl', text: String(n), 'aria-label': T('an_aenderungen', n) }));
      }
      oben.appendChild(k);
    });
    const unten = el('div', { class: 'aktiv-gruppe' }, [
      el('button', { class: 'aktiv-knopf', type: 'button', title: T('an_konto'), 'aria-label': T('an_konto'), data: { fid: 'al:konto' },
        on: { click: function () { S.sag(T('an_konto_aus')); } } }, [S.sym('konto', 22)]),
      el('button', { class: 'aktiv-knopf', type: 'button', title: T('an_einstellungen'), 'aria-label': T('an_einstellungen'), data: { fid: 'al:einst' },
        on: { click: function () { S.fuehreAus('palette'); } } }, [S.sym('zahnrad', 22)])
    ]);
    kasten.appendChild(oben);
    kasten.appendChild(unten);
  }

  function seite() {
    const kasten = S.q('seite-links');
    S.mitFokus(kasten, function () {
      S.leere(kasten);
      const bau = S.ansichten[S.z.ansicht] || S.ansichten.explorer;
      const a = bau();
      kasten.setAttribute('aria-label', a.titel);
      kasten.appendChild(el('div', { class: 'seite-kopf' }, [
        el('span', { text: a.titel }),
        el('span', { class: 'knopf-reihe' }, a.aktionen || [])
      ]));
      kasten.appendChild(a.inhalt);
      if (a.fuss) kasten.appendChild(a.fuss);
    });
  }

  S.zeichneLinks = function () {
    S.mitFokus(S.q('aktivleiste'), leiste);
    seite();
  };

  ['seite', 'aktiv', 'dateien', 'sprache', 'daten', 'gespeichert'].forEach(function (n) { S.an(n, S.zeichneLinks); });
  S.an('layout', function () { S.mitFokus(S.q('aktivleiste'), leiste); });
  let warte = null;
  S.an('inhalt', function () {
    if (warte) root.clearTimeout(warte);
    warte = root.setTimeout(function () { warte = null; S.zeichneLinks(); }, 250);
  });
})(window);
