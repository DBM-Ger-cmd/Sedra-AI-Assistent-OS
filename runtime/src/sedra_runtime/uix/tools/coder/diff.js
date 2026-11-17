/* Sedra IDE: Diff-Ansicht (nur lesen). Stellt den Stand im letzten Commit (Server, `git show HEAD:<pfad>`) neben den Text im Editor.
   Zeilenvergleich im Browser; sehr große Unterschiede werden nur als „ersetzt“ gezeigt. Nichts wird geschrieben. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  const API = ['', 'api', 'uix', 'coder', 'original', ''].join('/');      /* zusammengesetzt, siehe echt.js */
  const DP_MAX = 1200;                                                    /* Zeilen im geänderten Mittelteil, darüber kein Feinvergleich */
  const D = S.diff = {};

  /* Zeilenliste -> [{ art: 'gleich'|'weg'|'neu', alt, neu, text }] (gleicher Anfang und gleiches Ende werden abgezogen, dazwischen LCS). */
  D.vergleiche = function (a, b) {
    let von = 0;
    while (von < a.length && von < b.length && a[von] === b[von]) von += 1;
    let ea = a.length, eb = b.length;
    while (ea > von && eb > von && a[ea - 1] === b[eb - 1]) { ea -= 1; eb -= 1; }
    const aus = [];
    for (let i = 0; i < von; i++) aus.push({ art: 'gleich', alt: i + 1, neu: i + 1, text: a[i] });
    const ma = a.slice(von, ea), mb = b.slice(von, eb);
    if (ma.length > DP_MAX || mb.length > DP_MAX) {
      ma.forEach(function (t, i) { aus.push({ art: 'weg', alt: von + i + 1, neu: null, text: t }); });
      mb.forEach(function (t, i) { aus.push({ art: 'neu', alt: null, neu: von + i + 1, text: t }); });
    } else {
      const n = ma.length, m = mb.length, l = [];
      for (let i = 0; i <= n; i++) l.push(new Array(m + 1).fill(0));
      for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) l[i][j] = ma[i] === mb[j] ? l[i + 1][j + 1] + 1 : Math.max(l[i + 1][j], l[i][j + 1]);
      let i = 0, j = 0;
      while (i < n || j < m) {
        if (i < n && j < m && ma[i] === mb[j]) { aus.push({ art: 'gleich', alt: von + i + 1, neu: von + j + 1, text: ma[i] }); i += 1; j += 1; }
        else if (j < m && (i >= n || l[i][j + 1] >= l[i + 1][j])) { aus.push({ art: 'neu', alt: null, neu: von + j + 1, text: mb[j] }); j += 1; }
        else { aus.push({ art: 'weg', alt: von + i + 1, neu: null, text: ma[i] }); i += 1; }
      }
    }
    for (let i = ea; i < a.length; i++) aus.push({ art: 'gleich', alt: i + 1, neu: i - ea + eb + 1, text: a[i] });
    return aus;
  };

  /* Nebeneinander: links der Commit, rechts der Editor; Löschungen und Ergänzungen stehen in einer Zeile, wenn sie aufeinander folgen. */
  D.paare = function (zeilen) {
    const aus = [];
    for (let i = 0; i < zeilen.length; i++) {
      const z = zeilen[i];
      if (z.art === 'gleich') { aus.push({ links: z, rechts: z }); continue; }
      const weg = [], neu = [];
      while (i < zeilen.length && zeilen[i].art !== 'gleich') { (zeilen[i].art === 'weg' ? weg : neu).push(zeilen[i]); i += 1; }
      i -= 1;
      for (let k = 0; k < Math.max(weg.length, neu.length); k++) aus.push({ links: weg[k] || null, rechts: neu[k] || null });
    }
    return aus;
  };

  function spalte(klasse, z, seite) {
    const nr = z ? (seite === 'l' ? z.alt : z.neu) : '';
    return [el('span', { class: 'df-nr', text: nr ? String(nr) : '' }),
      el('span', { class: 'df-text ' + (z ? (z.art === 'gleich' ? '' : klasse) : 'df-leer'), text: z ? z.text : '' })];
  }

  D.zu = function () {
    const alt = S.q('editorbereich').querySelector('.diff-ueber');
    if (alt) alt.remove();
    S.diffPfad = null;
  };

  function baue(pfad, original, aktuell) {
    const zeilen = D.vergleiche(original.split('\n'), aktuell.split('\n'));
    const geaendert = zeilen.filter(function (z) { return z.art !== 'gleich'; }).length;
    const raster = el('div', { class: 'df-raster', role: 'table', 'aria-label': T('df_titel', pfad) });
    D.paare(zeilen).forEach(function (p) {
      const hinten = p.rechts && p.rechts.art === 'neu', vorne = p.links && p.links.art === 'weg';
      raster.appendChild(el('div', { class: 'df-zeile', role: 'row' },
        spalte('df-weg', vorne ? p.links : (p.links && p.links.art === 'gleich' ? p.links : null), 'l')
          .concat(spalte('df-neu', hinten ? p.rechts : (p.rechts && p.rechts.art === 'gleich' ? p.rechts : null), 'r'))));
    });
    const kopf = el('div', { class: 'df-kopf' }, [
      el('span', { class: 'df-titel', text: T('df_titel', pfad) }),
      el('span', { class: 'zeile-neben', text: geaendert ? T('df_anzahl', geaendert) : T('df_gleich') }),
      el('span', { class: 'platz' }),
      el('button', { class: 'knopf', type: 'button', data: { fid: 'df:datei' }, on: { click: function () { D.zu(); S.oeffneDatei(pfad); } } }, [T('df_datei')]),
      S.symKnopf('zu', T('df_zu'), D.zu, { data: { fid: 'df:zu' } })
    ]);
    const spaltenKopf = el('div', { class: 'df-spalten' }, [el('span', { text: T('df_links') }), el('span', { text: T('df_rechts') })]);
    const ueber = el('div', { class: 'diff-ueber', role: 'region', 'aria-label': T('df_titel', pfad),
      on: { keydown: function (ev) { if (ev.key === 'Escape') D.zu(); } } }, [kopf, spaltenKopf, raster]);
    return ueber;
  }

  /* Pfad öffnen und Diff zeigen. Neue Datei (nicht im Commit): alles ist neu. */
  D.zeige = async function (pfad) {
    if (S.quelle !== 'echt' || !S.ctx || !S.ctx.api) return;
    await S.oeffneDatei(pfad);
    const d = S.dateien[pfad];
    if (!d) return;
    let original = '';
    try {
      const r = await S.ctx.api(API + encodeURIComponent(S.echt.projekt.id) + '/' + encodeURIComponent(pfad));
      if (r.quelle === 'ok') original = r.inhalt;
      else if (r.grund !== 'neu') { S.sag(T(['kein_git', 'zu_gross', 'binaer', 'git_zeit'].indexOf(r.grund) >= 0 ? 'df_fehler_' + r.grund : 'df_fehler_sonst')); return; }
    } catch (e) { S.sag(T('df_fehler_sonst')); return; }
    D.zu();
    const bereich = S.q('editorbereich');
    const gruppe = bereich.children[S.aktiveGruppe] || bereich.firstChild;
    if (!gruppe) return;
    S.diffPfad = pfad;
    gruppe.appendChild(baue(pfad, original, d.inhalt));
    const z = gruppe.querySelector('.df-zu, [data-fid="df:zu"]');
    if (z) z.focus();
  };

  S.an('editor', function () { S.diffPfad = null; });
})(window);
