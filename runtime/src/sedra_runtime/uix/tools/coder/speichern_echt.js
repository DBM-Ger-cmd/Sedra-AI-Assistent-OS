/* Sedra IDE: Speichern (Entscheidung E4). Der Coder schreibt nie selbst: Ctrl+S schickt einen Antrag an die Freigaben.
   Stimmt der Captain dort zu, schreibt der Server genau diese Änderung; erst dann gilt die Datei hier als gespeichert.
   Ändert sich die Datei auf der Platte vorher, greift die Freigabe nicht und der Antrag muss neu gestellt werden. */
(function (root) {
  'use strict';
  const S = root.SIDE, T = S.T;
  const API = ['', 'api', 'uix', 'coder', 'speichern'].join('/');      /* zusammengesetzt, siehe echt.js */
  const TAKT_MS = 3000;
  const RUNDEN_MAX = 400;                                              /* rund 20 Minuten, danach ist der Antrag vergessen (die Freigabe bleibt offen) */
  S.antraege = {};              /* pfad -> { id, inhalt } : Anträge, die auf die Zustimmung warten */
  let zeit = null, runden = 0;

  function fehlerText(e) {
    const m = String((e && e.message) || '');
    const k = /file_changed_repeat_request|captain_approval|already_applied|keine_aenderung|access_blocked|datei_zu_gross|datei_nicht_lesbar|ziel_ist_ordner|content_too_large|invalid_path|write_failed/.exec(m);
    return k ? T('sp_fehler_' + k[0]) : T('sp_fehler_sonst');
  }

  S.antragOffen = function (pfad) { return !!S.antraege[pfad]; };

  S.speichereEcht = async function (pfad) {
    const d = S.dateien[pfad];
    if (!d || !S.ungespeichert(pfad)) return;
    if (S.antraege[pfad]) { S.sag(T('sp_wartet', d.name)); return; }
    try {
      const r = await S.ctx.api(API, { method: 'POST', body: { projekt: S.echt.projekt.id, pfad: pfad, inhalt: d.inhalt } });
      S.antraege[pfad] = { id: r.mission_id, inhalt: d.inhalt };
      S.sag(T(r.neu ? 'sp_antrag_neu' : 'sp_antrag', d.name, r.hinzu, r.weg));
      S.melde('dateien');
      planeTakt();
    } catch (e) { S.sag(fehlerText(e)); }
  };

  S.alleSpeichernEcht = function () {
    const offen = Object.keys(S.dateien).filter(function (p) { return S.ungespeichert(p) && !S.antraege[p]; });
    if (!offen.length) { S.sag(T('sp_nichts')); return; }
    offen.forEach(function (p) { S.speichereEcht(p); });
  };

  function fertig(pfad, text) { delete S.antraege[pfad]; S.sag(text); S.melde('dateien'); }

  S.pruefeAntraege = async function () {
    const pfade = Object.keys(S.antraege);
    for (let i = 0; i < pfade.length; i++) {
      const pfad = pfade[i], a = S.antraege[pfad], d = S.dateien[pfad];
      try {
        const st = await S.ctx.api(API + '/' + encodeURIComponent(a.id));
        if (st.status === 'abgelehnt') { fertig(pfad, T('sp_abgelehnt', d ? d.name : pfad)); continue; }
        if (st.status !== 'freigegeben') continue;
        await S.ctx.api(API + '/anwenden', { method: 'POST', body: { mission_id: a.id } });
        if (d) { d.gespeichert = a.inhalt; S.melde('gespeichert', pfad); }
        fertig(pfad, T('sp_angewendet', d ? d.name : pfad));
        S.ladeGit();
      } catch (e) { fertig(pfad, fehlerText(e)); }
    }
  };

  function planeTakt() {
    if (zeit !== null || !Object.keys(S.antraege).length) return;
    zeit = setTimeout(async function () {
      zeit = null; runden += 1;
      await S.pruefeAntraege();
      if (runden >= RUNDEN_MAX) { Object.keys(S.antraege).forEach(function (p) { fertig(p, T('sp_zeit', p)); }); runden = 0; return; }
      if (!Object.keys(S.antraege).length) runden = 0;
      planeTakt();
    }, TAKT_MS);
  }
})(window);
