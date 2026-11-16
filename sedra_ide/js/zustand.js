/* Sedra IDE: Zustand, Merken (localStorage nur hier, immer abgesichert), Ereignisse, Dateimodell. */
(function (root) {
  'use strict';
  const S = root.SIDE = root.SIDE || {};

  const hoerer = {};
  S.an = function (name, fn) { (hoerer[name] = hoerer[name] || []).push(fn); };
  S.melde = function (name, daten) { (hoerer[name] || []).slice().forEach(function (fn) { fn(daten); }); };

  const KEY = 'sedra.ide.zustand';
  function lesen() {
    try {
      const t = root.localStorage.getItem(KEY);
      const o = t ? JSON.parse(t) : {};
      return o && typeof o === 'object' ? o : {};
    } catch (e) { return {}; }
  }
  function schreiben(o) {
    try { root.localStorage.setItem(KEY, JSON.stringify(o)); return true; } catch (e) { return false; }
  }

  const STD = {
    sprache: 'de', thema: 'dunkel', beispiel: true,
    seiteLinks: true, seiteRechts: true, panel: true,
    ansicht: 'explorer', panelReiter: 'terminal', rechtsReiter: 'chat',
    breiteLinks: 280, breiteRechts: 320, hoehePanel: 220,
    zugeklappt: { 'abs:zeitachse': true }, offen: null, agentModus: 'plan', autoFreigabe: false
  };
  const alt = lesen();
  const z = S.z = {};
  Object.keys(STD).forEach(function (k) {
    z[k] = (typeof alt[k] === typeof STD[k] || (STD[k] === null && alt[k])) ? alt[k] : STD[k];
  });
  if (!z.zugeklappt || typeof z.zugeklappt !== 'object') z.zugeklappt = {};
  S.GRENZEN = { breiteLinks: [170, 600], breiteRechts: [220, 640], hoehePanel: [90, 560] };

  S.merke = function () {
    z.offen = { gruppen: S.gruppen, aktiv: S.aktiveGruppe };
    schreiben(z);
  };
  S.setze = function (k, v) { z[k] = v; S.merke(); S.melde('layout'); };

  /* Dateimodell (Beispieldaten, nur im Speicher). */
  S.dateien = {};
  S.gruppen = [{ reiter: ['willkommen'], aktiv: 'willkommen' }];
  S.aktiveGruppe = 0;
  S.verlauf = [];
  S.verlaufPos = -1;

  S.sprachVon = function (name) {
    const e = (name.split('.').pop() || '').toLowerCase();
    return { js: 'js', py: 'py', yaml: 'yaml', yml: 'yaml', md: 'md' }[e] || 'txt';
  };
  S.gibt = function (p) { return p === 'willkommen' || Object.prototype.hasOwnProperty.call(S.dateien, p); };
  S.ungespeichert = function (p) { const d = S.dateien[p]; return !!d && d.inhalt !== d.gespeichert; };
  S.aktiveDatei = function () {
    const g = S.gruppen[S.aktiveGruppe];
    return g && g.aktiv !== 'willkommen' ? S.dateien[g.aktiv] || null : null;
  };

  /* Gemerkte Reiter wiederherstellen, nur vorhandene Pfade. */
  S.stelleHer = function () {
    const o = z.offen;
    if (!o || !Array.isArray(o.gruppen)) return;
    const gs = [];
    o.gruppen.forEach(function (g) {
      if (!g || !Array.isArray(g.reiter)) return;
      const r = g.reiter.filter(function (p) { return typeof p === 'string' && S.gibt(p); });
      if (r.length) gs.push({ reiter: r, aktiv: r.indexOf(g.aktiv) >= 0 ? g.aktiv : r[0] });
    });
    if (gs.length) { S.gruppen = gs.slice(0, 3); S.aktiveGruppe = Math.min(o.aktiv | 0, S.gruppen.length - 1); }
  };

  S.oeffne = function (pfad, gi, ohneVerlauf) {
    if (!S.gibt(pfad)) return;
    const g = S.gruppen[gi == null ? S.aktiveGruppe : gi] || S.gruppen[0];
    if (g.reiter.indexOf(pfad) < 0) g.reiter.push(pfad);
    g.aktiv = pfad;
    S.aktiveGruppe = S.gruppen.indexOf(g);
    if (!ohneVerlauf && S.verlauf[S.verlaufPos] !== pfad) {
      S.verlauf = S.verlauf.slice(0, S.verlaufPos + 1);
      S.verlauf.push(pfad);
      S.verlaufPos = S.verlauf.length - 1;
    }
    S.merke();
    S.melde('editor');
  };

  S.schliesse = function (pfad, gi) {
    gi = gi == null ? S.aktiveGruppe : gi;
    const g = S.gruppen[gi];
    if (!g) return;
    const i = g.reiter.indexOf(pfad);
    if (i < 0) return;
    g.reiter.splice(i, 1);
    if (g.aktiv === pfad) g.aktiv = g.reiter[Math.min(i, g.reiter.length - 1)] || null;
    if (!g.reiter.length) {
      if (S.gruppen.length > 1) {
        S.gruppen.splice(gi, 1);
        S.aktiveGruppe = Math.min(S.aktiveGruppe, S.gruppen.length - 1);
      } else { g.reiter = ['willkommen']; g.aktiv = 'willkommen'; }
    }
    S.merke();
    S.melde('editor');
  };

  S.teile = function () {
    if (S.gruppen.length >= 3) { S.sag(S.T('ed_teilen_voll')); return; }
    const g = S.gruppen[S.aktiveGruppe];
    S.gruppen.splice(S.aktiveGruppe + 1, 0, { reiter: [g.aktiv], aktiv: g.aktiv });
    S.aktiveGruppe += 1;
    S.merke();
    S.melde('editor');
  };

  S.reiterWechsel = function (schritt) {
    const g = S.gruppen[S.aktiveGruppe];
    if (!g || g.reiter.length < 2) return;
    const n = g.reiter.length;
    S.oeffne(g.reiter[(g.reiter.indexOf(g.aktiv) + schritt + n) % n]);
  };

  S.speichere = function (pfad) {
    const d = S.dateien[pfad];
    if (!d) return;
    d.gespeichert = d.inhalt;
    S.melde('gespeichert', pfad);
  };

  let neuNr = 0;
  S.neueDatei = function () {
    let p;
    do { neuNr += 1; p = 'unbenannt-' + neuNr + '.txt'; } while (S.dateien[p]);
    S.dateien[p] = { pfad: p, name: p, inhalt: '', gespeichert: '', sprache: 'txt', git: 'U', neu: true };
    S.melde('dateien');
    S.oeffne(p);
  };

  S.geheVerlauf = function (schritt) {
    const i = S.verlaufPos + schritt;
    if (i < 0 || i >= S.verlauf.length) return;
    S.verlaufPos = i;
    S.oeffne(S.verlauf[i], null, true);
  };
})(window);
