/* Sedra IDE: Befehle und Tastenkuerzel. Jeder Befehl hat einen Text "bf_<id>". */
(function (root) {
  'use strict';
  const S = root.SIDE, T = S.T;

  function ansicht(id) { return function () { S.oeffneAnsicht(id); S.fokusFid(S.q('aktivleiste'), 'al:' + id); }; }
  function suchen() {
    S.oeffneAnsicht('suche');
    const f = S.q('suchfeld');
    if (f) { f.focus(); f.select(); }
  }
  function ersteFokus(kasten) {
    return kasten.querySelector('[tabindex="0"], textarea, input, button:not([tabindex="-1"])');
  }
  /* F6: Fokus der Reihe nach durch die sichtbaren Bereiche. */
  function bereichWechsel(rueck) {
    const ids = ['editorbereich', 'panel', 'seite-rechts', 'aktivleiste', 'seite-links', 'kopf'].filter(function (id) { return !S.q(id).hidden; });
    let hier = -1;
    ids.forEach(function (id, i) { if (S.q(id).contains(document.activeElement)) hier = i; });
    for (let n = 1; n <= ids.length; n++) {
      const ziel = ersteFokus(S.q(ids[(hier + (rueck ? -n : n) + ids.length * 2) % ids.length]));
      if (ziel) { ziel.focus(); return; }
    }
  }

  S.befehle = [
    { id: 'palette', k: ['Ctrl+Shift+P', 'F1'], tun: function () { S.palette.oeffne('>'); } },
    { id: 'dateiSuche', k: ['Ctrl+P'], tun: function () { S.palette.oeffne(''); } },
    { id: 'geheZeile', k: ['Ctrl+G'], tun: function () { S.palette.oeffne(':'); } },
    { id: 'seiteLinks', k: ['Ctrl+B'], tun: function () { S.setze('seiteLinks', !S.z.seiteLinks); } },
    { id: 'panel', k: ['Ctrl+J'], tun: function () { S.setze('panel', !S.z.panel); } },
    { id: 'seiteRechts', k: ['Ctrl+Alt+B'], tun: function () { S.setze('seiteRechts', !S.z.seiteRechts); } },
    { id: 'reiterVor', k: ['Alt+PageDown'], tun: function () { S.reiterWechsel(1); } },
    { id: 'reiterZurueck', k: ['Alt+PageUp'], tun: function () { S.reiterWechsel(-1); } },
    { id: 'schliessen', k: ['Alt+W'], tun: function () { const g = S.gruppen[S.aktiveGruppe]; if (g && g.aktiv) S.schliesse(g.aktiv); } },
    { id: 'speichern', k: ['Ctrl+S'], tun: function () {
      const d = S.aktiveDatei();
      if (d && S.quelle === 'echt') { S.speichereEcht(d.pfad); return; }
      if (d) { S.speichere(d.pfad); S.sag(T('ed_gespeichert', d.name)); }
    } },
    { id: 'alleSpeichern', k: ['Ctrl+Alt+S'], tun: function () {
      if (S.quelle === 'echt') { S.alleSpeichernEcht(); return; }
      Object.keys(S.dateien).forEach(function (p) { if (S.ungespeichert(p)) S.speichere(p); });
      S.sag(T('ed_alle_gespeichert'));
    } },
    { id: 'teilen', k: ['Ctrl+\\', 'Ctrl+Alt+\\', 'Alt+G'], tun: function () { S.teile(); } },
    { id: 'neueDatei', k: ['Alt+N'], tun: function () { S.neueDatei(); } },
    { id: 'suchenDatei', k: ['Ctrl+F'], tun: suchen },
    { id: 'suchen', k: ['Ctrl+Shift+F'], tun: suchen },
    { id: 'allesWaehlen', k: [], tun: function () {
      S.editor.fokus();
      const a = document.activeElement;
      if (a && a.select) a.select();
    } },
    { id: 'ansichtExplorer', k: ['Ctrl+Shift+E'], tun: ansicht('explorer') },
    { id: 'ansichtQuellcode', k: ['Ctrl+Shift+G'], tun: ansicht('quellcode') },
    { id: 'ansichtAusfuehren', k: ['Ctrl+Shift+D'], tun: ansicht('ausfuehren') },
    { id: 'ansichtErweiterungen', k: ['Ctrl+Shift+X'], tun: ansicht('erweiterungen') },
    { id: 'ansichtAgenten', k: ['Ctrl+Alt+A'], tun: ansicht('agenten') },
    { id: 'terminal', k: ['Alt+T'], tun: function () { S.fokusTerminal(); } },
    { id: 'lauf', k: ['F5'], tun: function () { S.lauf((S.aktiveDatei() || {}).pfad || 'src/start.js'); } },
    { id: 'fokusEditor', k: ['Alt+E'], tun: function () { S.editor.fokus(); } },
    { id: 'bereichVor', k: ['F6'], tun: function () { bereichWechsel(false); } },
    { id: 'bereichZurueck', k: ['Shift+F6'], tun: function () { bereichWechsel(true); } },
    { id: 'zurueck', k: ['Alt+ArrowLeft'], tun: function () { S.geheVerlauf(-1); } },
    { id: 'vor', k: ['Alt+ArrowRight'], tun: function () { S.geheVerlauf(1); } },
    { id: 'willkommen', k: [], tun: function () { S.oeffne('willkommen'); } },
    { id: 'thema', k: [], tun: function () {
      S.z.thema = S.z.thema === 'hell' ? 'dunkel' : 'hell';
      S.merke(); S.wendeAn(); S.melde('layout');
    } },
    { id: 'sprache', k: [], tun: function () {
      S.z.sprache = S.z.sprache === 'de' ? 'en' : 'de';
      S.merke(); S.wendeAn(); S.melde('sprache');
    } },
    { id: 'beispieldaten', k: [], tun: function () {
      S.z.beispiel = !S.z.beispiel;
      S.merke(); S.melde('daten'); S.melde('editor');
      S.sag(T(S.z.beispiel ? 'bsp_an' : 'bsp_aus'));
    } },
    { id: 'layoutStandard', k: [], tun: function () {
      S.z.seiteLinks = true; S.z.seiteRechts = true; S.z.panel = true;
      S.z.breiteLinks = 280; S.z.breiteRechts = 320; S.z.hoehePanel = 220; S.z.zugeklappt = { 'abs:zeitachse': true };
      S.merke(); S.melde('layout'); S.melde('seite');
    } },
    { id: 'ueber', k: [], tun: function () { S.sag(T('ueber_text')); } }
  ];

  const nachId = {}, nachTaste = {};
  S.befehle.forEach(function (b) {
    nachId[b.id] = b;
    b.k.forEach(function (k) { nachTaste[k] = b; });
  });
  S.fuehreAus = function (id) { const b = nachId[id]; if (b) b.tun(); };
  S.kuerzelVon = function (id) { const b = nachId[id]; return b && b.k.length ? b.k[0].replace('Ctrl', T('taste_strg')).replace('Shift', T('taste_umschalt')) : ''; };

  function tastenName(ev) {
    let k = ev.key;
    if (k === 'Control' || k === 'Shift' || k === 'Alt' || k === 'Meta') return '';
    if (k.length === 1) k = k.toUpperCase();
    return (ev.ctrlKey || ev.metaKey ? 'Ctrl+' : '') + (ev.altKey ? 'Alt+' : '') + (ev.shiftKey ? 'Shift+' : '') + k;
  }
  S.tastenName = tastenName;

  document.addEventListener('keydown', function (ev) {
    const name = tastenName(ev);
    if (!name) return;
    const b = nachTaste[name];
    if (!b) return;
    /* Alt+Pfeil in Textfeldern nicht abfangen (Wortsprung bleibt beim Feld). */
    if ((b.id === 'zurueck' || b.id === 'vor') && /^(TEXTAREA|INPUT)$/.test(document.activeElement.tagName)) return;
    ev.preventDefault();
    if (S.palette.offen() && b.id !== 'palette' && b.id !== 'dateiSuche' && b.id !== 'geheZeile') S.palette.schliesse();
    b.tun();
  });
})(window);
