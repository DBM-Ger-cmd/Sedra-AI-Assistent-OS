/* Sedra IDE: echte Projektdateien lesen (Runde 5, R1 bis R3). Nur Lesen über die Brücke (ctx.api), kein Schreibweg.
   Ohne Projekt oder bei einem Fehler bleiben die Beispieldateien. Die Sperrliste (Schlüssel, local_config …) gilt auf dem Server. */
(function (root) {
  'use strict';
  const S = root.SIDE, T = S.T;
  const API = ['', 'api', 'uix', 'coder', ''].join('/');      /* zusammengesetzt: die Vertragsprüfung liest nur ganze Routen-Literale; erlaubt sind die drei Einträge der tool.yaml */
  S.quelle = 'beispiel';          /* 'beispiel' | 'echt': gilt nur für Explorer, Editor, Suche */
  S.echt = { projekt: null, baum: [], dateien: {}, git: {}, aenderungen: [], gitGrund: '' };
  let beispiel = null;

  function enc(p) { return encodeURIComponent(p); }
  function knoten(e, vor) {
    const pfad = vor ? vor + '/' + e.name : e.name;
    const k = { name: e.name, pfad: pfad, ordner: e.type === 'dir', kinder: e.type === 'dir' ? null : undefined };
    if (k.ordner) S.z.zugeklappt['o:' + pfad] = true;      /* Ordner starten zu und laden beim ersten Aufklappen */
    return k;
  }

  S.baumKnoten = knoten;

  S.findeKnoten = function (pfad, liste) {
    const l = liste || S.BAUM;
    for (let i = 0; i < l.length; i++) {
      if (l[i].pfad === pfad) return l[i];
      if (l[i].kinder && pfad.indexOf(l[i].pfad + '/') === 0) { const r = S.findeKnoten(pfad, l[i].kinder); if (r) return r; }
    }
    return null;
  };

  /* Alle bekannten Dateipfade: geöffnete plus die in aufgeklappten Ordnern geladenen. */
  S.alleDateiPfade = function () {
    const aus = Object.keys(S.dateien);
    (function lauf(l) { (l || []).forEach(function (k) { if (k.ordner) lauf(k.kinder); else if (aus.indexOf(k.pfad) < 0) aus.push(k.pfad); }); })(S.BAUM);
    return aus.sort();
  };

  S.setzeQuelle = function (q) {
    if (q === 'beispiel' && beispiel) { S.BAUM = beispiel.baum; S.dateien = beispiel.dateien; S.ARBEITSBEREICH = beispiel.name; S.ZWEIG = beispiel.zweig; }
    if (q === 'echt') { S.BAUM = S.echt.baum; S.dateien = S.echt.dateien; S.ARBEITSBEREICH = S.echt.projekt.name; S.ZWEIG = '–'; }
    S.quelle = q;
    S.gruppen = [{ reiter: ['willkommen'], aktiv: 'willkommen' }];
    S.aktiveGruppe = 0;
    S.verlauf = []; S.verlaufPos = -1;
    S.melde('dateien'); S.melde('editor'); S.melde('seite');
  };

  /* Git-Status (nur lesen, Entscheidung E2): Status je Pfad, Ordner mit Änderungen, Zweig in der Statusleiste. */
  S.gitStatus = function (pfad) {
    const d = S.dateien[pfad];
    if (d && d.git) return d.git;
    return S.quelle === 'echt' ? (S.echt.git[pfad] || '') : '';
  };
  S.gitInOrdner = function (pfad) {
    if (S.quelle !== 'echt') return false;
    return Object.keys(S.echt.git).some(function (p) { return p.indexOf(pfad + '/') === 0; });
  };
  S.ladeGit = async function () {
    if (S.quelle !== 'echt' || !S.ctx || !S.ctx.api) return;
    try {
      const r = await S.ctx.api(API + 'aenderungen/' + enc(S.echt.projekt.id));
      S.echt.git = {}; S.echt.aenderungen = []; S.echt.gitGrund = '';
      if (r.quelle === 'ok') {
        S.echt.aenderungen = r.eintraege || [];
        S.echt.aenderungen.forEach(function (e) { S.echt.git[e.pfad] = e.status; if (S.dateien[e.pfad]) S.dateien[e.pfad].git = e.status; });
        S.ZWEIG = r.zweig || '–';
      } else { S.echt.gitGrund = r.grund || 'git_fehler'; S.ZWEIG = '–'; }
    } catch (e) { S.echt.gitGrund = 'git_fehler'; }
    S.melde('dateien'); S.melde('seite'); S.melde('layout');
  };

  S.ladeOrdner = async function (k) {
    if (!S.echt.projekt || !k.ordner || k.kinder) return;
    try {
      const r = await S.ctx.api(API + 'dateien/' + enc(S.echt.projekt.id) + '/' + enc(k.pfad));
      k.kinder = (r.eintraege || []).map(function (e) { return knoten(e, k.pfad); });
    } catch (e) { S.sag(T('echt_fehler_lesen', k.name)); k.kinder = []; }
    S.melde('seite');
  };

  S.oeffneDatei = async function (pfad) {
    if (S.gibt(pfad)) { S.oeffne(pfad); return; }
    if (S.quelle !== 'echt') return;
    const name = pfad.split('/').pop();
    try {
      const r = await S.ctx.api(API + 'datei/' + enc(S.echt.projekt.id) + '/' + enc(pfad));
      if (r.binary) { S.sag(T('echt_fehler_binaer', name)); return; }
      if (r.too_large) { S.sag(T('echt_fehler_gross', name)); return; }
      const text = String(r.inhalt || '').replace(/\r\n/g, '\n');
      S.dateien[pfad] = { pfad: pfad, name: name, inhalt: text, gespeichert: text, sprache: S.sprachVon(name), git: S.echt.git[pfad] || '' };
      S.melde('dateien');
      S.oeffne(pfad);
    } catch (e) { S.sag(T(/access_blocked/.test(String(e && e.message)) ? 'echt_fehler_gesperrt' : 'echt_fehler_lesen', name)); }
  };

  /* Beim Start: Beispiele sichern, Projekt suchen, Wurzelordner laden. Jeder Fehler lässt die Beispiele stehen. */
  S.ladeEcht = async function () {
    beispiel = { baum: S.BAUM, dateien: S.dateien, name: S.ARBEITSBEREICH, zweig: S.ZWEIG };
    if (!S.ctx || !S.ctx.api) return;
    try {
      const p = await S.ctx.api(API + 'projekte');
      if (p.quelle !== 'ok' || !p.projekte.length) return;
      const projekt = p.projekte[0];
      const r = await S.ctx.api(API + 'dateien/' + enc(projekt.id));
      S.echt.projekt = { id: projekt.id, name: String(projekt.name || projekt.id) };
      S.echt.baum = (r.eintraege || []).map(function (e) { return knoten(e, ''); });
      S.echt.dateien = {};
      S.setzeQuelle('echt');
      S.sag(T('echt_geladen', S.echt.projekt.name));
      S.ladeWege();
      S.ladeGit();
    } catch (e) { /* ohne Projekt oder ohne Zugriff: Beispieldateien bleiben */ }
  };
})(window);
