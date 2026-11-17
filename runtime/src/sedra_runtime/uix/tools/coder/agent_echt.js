/* Sedra IDE: Agenten-Anbindung (echte Modelle). Nur Fragen und Antworten als Text, kein Schreibweg.
   Wege: das lokale Modell und eingeschaltete Cloud-Anbieter (Hauptschalter und Anbieter stellt der Captain in den Einstellungen ein).
   Als Kontext gehen die geöffneten Dateien mit (bis zu 5); gesperrte Dateien (Sperrliste) bleiben auf dem Server draußen. */
(function (root) {
  'use strict';
  const S = root.SIDE, T = S.T;
  const API = ['', 'api', 'uix', 'coder', ''].join('/');      /* zusammengesetzt, siehe echt.js */
  const KONTEXT_MAX = 5;
  const urspruenglich = S.sende;
  S.wege = [];              /* [{ id, name, route, provider, model }], nur bereite */
  S.wegGewaehlt = null;
  S.wegeGeladen = false;
  S.agentVerlauf = [];      /* [{ role, content }] für den Zusammenhang der Antworten */
  let laeuft = false;

  S.ladeWege = async function () {
    S.wege = []; S.wegeGeladen = false;
    if (S.quelle !== 'echt' || !S.ctx || !S.ctx.api) return;
    try {
      const m = await S.ctx.api(API + 'modelle');
      if (m.lokal && m.lokal.bereit) S.wege.push({ id: 'lokal', name: T('weg_lokal', m.lokal.modell), route: 'lokal' });
      ((m.cloud && m.cloud.anbieter) || []).forEach(function (a) {
        S.wege.push({ id: 'cloud:' + a.id, name: T('weg_cloud', a.id, a.modell), route: 'cloud', provider: a.id, model: a.modell });
      });
    } catch (e) { /* ohne Antwort bleibt die Liste leer, der Hinweis erklärt es */ }
    S.wegeGeladen = true;
    if (!S.wege.some(function (w) { return w.id === S.wegGewaehlt; })) S.wegGewaehlt = S.wege.length ? S.wege[0].id : null;
    S.melde('seite');
  };

  S.waehleWeg = function (id) { S.wegGewaehlt = id; S.melde('seite'); };

  /* Geöffnete Dateien, die es im Projekt wirklich gibt: die aktive zuerst. */
  function kontextDateien() {
    const g = S.gruppen[S.aktiveGruppe] || S.gruppen[0];
    const alle = [];
    if (g && g.aktiv) alle.push(g.aktiv);
    S.gruppen.forEach(function (x) { x.reiter.forEach(function (p) { if (alle.indexOf(p) < 0) alle.push(p); }); });
    return alle.filter(function (p) { return S.dateien[p] && p !== 'willkommen'; }).slice(0, KONTEXT_MAX);
  }

  function grundText(res) {
    if (res.status === 'no_model') return T('ag_kein_modell');
    if (res.status === 'blocked') return T('ag_gesperrt_schutz', (res.gruende || []).join(', '));
    return T('ag_fehler', (res.gruende || [res.status || '?']).join(', '));
  }

  function antworte(zeile, res) {
    const info = (res.kontext || []).length ? T('ag_kontext', res.kontext.length) : T('ag_ohne_kontext');
    const aus = (res.ausgelassen || []).length ? ' ' + T('ag_ausgelassen', res.ausgelassen.map(function (a) { return a.pfad + ' (' + T('ag_grund_' + a.grund) + ')'; }).join(', ')) : '';
    if (res.status === 'completed') {
      zeile.text = res.antwort;
      zeile.von = (res.modell || '?') + ' · ' + info + aus;
      S.agentVerlauf.push({ role: 'assistant', content: res.antwort });
    } else { zeile.text = grundText(res); zeile.von = T('ag_hinweis') + aus; }
  }

  S.sende = async function (text) {
    if (S.quelle !== 'echt') { urspruenglich(text); return; }
    text = String(text || '').trim();
    if (!text) return;
    if (laeuft) { S.sag(T('ag_laeuft')); return; }
    const weg = S.wege.filter(function (w) { return w.id === S.wegGewaehlt; })[0];
    S.CHAT.push({ von: T('ch_ich'), ich: true, text: text });
    if (!weg) { S.CHAT.push({ von: T('ag_hinweis'), ich: false, text: T('ag_kein_weg') }); S.melde('chat'); return; }
    const zeile = { von: weg.name, ich: false, text: T('ag_denkt') };
    S.CHAT.push(zeile);
    S.melde('chat');
    laeuft = true;
    const body = { projekt: S.echt.projekt.id, text: text, route: weg.route, modus: S.z.agentModus === 'act' ? 'act' : 'plan',
      dateien: kontextDateien(), history: S.agentVerlauf.slice(-8) };
    if (weg.route === 'cloud') { body.provider = weg.provider; body.model = weg.model; }
    try {
      const res = await S.ctx.api(API + 'agent', { method: 'POST', body: body });
      S.agentVerlauf.push({ role: 'user', content: text });
      antworte(zeile, res);
    } catch (e) {
      zeile.von = T('ag_hinweis');
      zeile.text = T('ag_fehler', String((e && e.message) || '?').slice(0, 80));
    }
    laeuft = false;
    S.melde('chat');
  };
})(window);
