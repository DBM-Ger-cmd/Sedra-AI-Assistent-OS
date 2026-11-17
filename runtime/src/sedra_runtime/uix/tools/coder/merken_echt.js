/* Sedra IDE: gemerkter Zustand. Der Rahmen hat keinen eigenen Speicher, deshalb liegt ein kleiner Zustand auf dem Server
   (gewähltes Projekt, Chat-Verlauf, offene Anträge, Schriftgröße). Nie Dateitext, nur was du im Chat geschrieben hast und Namen.
   Dazu die Schriftgröße des Editors (Strg+= / Strg+- / Strg+0). */
(function (root) {
  'use strict';
  const S = root.SIDE, T = S.T;
  const API = ['', 'api', 'uix', 'coder', 'zustand'].join('/');      /* zusammengesetzt, siehe echt.js */
  const SCHRIFT_STD = 13, SCHRIFT_MIN = 10, SCHRIFT_MAX = 24;
  const WARTE_MS = 1000;
  let timer = null, bereit = false;
  S.schrift = SCHRIFT_STD;
  S.zeilenHoehe = 19;

  /* ---- Schriftgröße: Zeilenhöhe folgt der Schrift (festes Zeilenraster des Editors). */
  function wende() {
    S.schrift = Math.max(SCHRIFT_MIN, Math.min(SCHRIFT_MAX, S.schrift));
    S.zeilenHoehe = Math.round(S.schrift * 19 / 13);
    if (S.wurzel) { S.wurzel.style.setProperty('--gr-mono', S.schrift + 'px'); S.wurzel.style.setProperty('--ed-zeile', S.zeilenHoehe + 'px'); }
  }
  S.schriftAendern = function (schritt) {
    S.schrift = schritt === 0 ? SCHRIFT_STD : S.schrift + schritt;
    wende();
    S.melde('editor');
    S.sag(T('schrift_gr', S.schrift));
    S.sichere();
  };

  /* ---- Zustand holen, merken, wiederherstellen */
  S.holeZustand = async function () {
    try { const r = await S.ctx.api(API); return r && r.zustand ? r.zustand : null; } catch (e) { return null; }
  };

  S.sichere = function () {
    if (!bereit || S.quelle !== 'echt' || !S.echt.projekt) return;
    if (timer) root.clearTimeout(timer);
    timer = root.setTimeout(async function () {
      timer = null;
      const antraege = Object.keys(S.antraege || {}).map(function (k) {
        const a = S.antraege[k];
        return { id: a.id, art: a.art || 'speichern', pfad: a.pfad || k, ziel: a.ziel || null };
      });
      const zustand = {
        projekt: S.echt.projekt.id, schrift: S.schrift, weg: S.wegGewaehlt || '',
        chat: S.CHAT.slice(1).map(function (c) { return { von: c.von, ich: !!c.ich, text: c.text }; }),
        verlauf: S.agentVerlauf || [], antraege: antraege
      };
      try { await S.ctx.api(API, { method: 'POST', body: { zustand: zustand } }); } catch (e) { /* nächste Änderung versucht es wieder */ }
    }, WARTE_MS);
  };

  S.stelleWiederHer = function (z) {
    S.schrift = z.schrift || SCHRIFT_STD;
    wende();
    S.wegGewaehlt = z.weg || S.wegGewaehlt;
    (z.chat || []).forEach(function (c) { S.CHAT.push({ von: c.von, ich: !!c.ich, text: c.text }); });
    S.agentVerlauf = z.verlauf || [];
    let n = 0;
    (z.antraege || []).forEach(function (a) {
      const schluessel = a.art === 'speichern' ? a.pfad : 'a:' + a.id;
      S.antraege[schluessel] = { id: a.id, art: a.art === 'speichern' ? undefined : a.art, pfad: a.pfad, ziel: a.ziel };
      n += 1;
    });
    bereit = true;
    S.melde('chat'); S.melde('editor'); S.melde('dateien');
    if (n) { S.planeAntraege(); S.sag(T('mk_wieder', n)); }
  };

  /* Ohne gemerkten Zustand (erste Nutzung) beginnt das Merken nach dem Laden. */
  S.an('dateien', function () { if (S.quelle === 'echt' && !bereit && S.echt.projekt) { bereit = true; wende(); } });
  S.an('chat', function () { S.sichere(); });
})(window);
