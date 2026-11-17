/* Sedra IDE: obere Leiste (Menue, Zurueck/Vor, Suchfeld, Schalter) und Statusleiste. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;

  const MENUE = [
    { id: 'datei', punkte: ['neueDatei', 'dateiSuche', '-', 'speichern', 'alleSpeichern', '-', 'schliessen'] },
    { id: 'bearbeiten', punkte: ['suchenDatei', 'suchen', 'geheZeile'] },
    { id: 'auswahl', punkte: ['allesWaehlen'] },
    { id: 'ansicht', punkte: ['palette', '-', 'seiteLinks', 'panel', 'seiteRechts', 'teilen', '-', 'ansichtExplorer', 'ansichtQuellcode',
      'ansichtAusfuehren', 'ansichtErweiterungen', 'ansichtAgenten', '-', 'thema', 'sprache', 'beispieldaten', 'layoutStandard'] },
    { id: 'gehe', punkte: ['zurueck', 'vor', '-', 'dateiSuche', 'geheZeile', '-', 'reiterVor', 'reiterZurueck', 'fokusEditor', 'bereichVor'] },
    { id: 'ausfuehren', punkte: ['lauf'] },
    { id: 'terminal', punkte: ['terminal'] },
    { id: 'hilfe', punkte: ['willkommen', 'palette', 'ueber'] }
  ];
  let offen = null; /* {id, kasten, knopf} */

  function zu(mitFokus) {
    if (!offen) return;
    const o = offen;
    offen = null;
    if (o.kasten.parentNode) o.kasten.parentNode.removeChild(o.kasten);
    o.knopf.setAttribute('aria-expanded', 'false');
    if (mitFokus) o.knopf.focus();
  }
  function auf(m, knopf) {
    zu(false);
    const kasten = el('div', { class: 'menue', role: 'menu', 'aria-label': T('mn_' + m.id) });
    m.punkte.forEach(function (id) {
      if (id === '-') { kasten.appendChild(el('div', { class: 'menue-trenner', role: 'separator' })); return; }
      kasten.appendChild(el('button', {
        class: 'menue-punkt', type: 'button', role: 'menuitem', tabindex: '-1',
        on: { click: function () { zu(true); S.fuehreAus(id); } }
      }, [el('span', { text: T('bf_' + id) }), el('span', { class: 'kuerzel', text: S.kuerzelVon(id) })]));
    });
    const r = knopf.getBoundingClientRect();
    kasten.style.left = Math.round(r.left) + 'px';
    kasten.style.top = Math.round(r.bottom + 2) + 'px';
    kasten.addEventListener('keydown', function (ev) {
      const p = Array.prototype.slice.call(kasten.querySelectorAll('.menue-punkt'));
      const i = p.indexOf(document.activeElement);
      if (ev.key === 'ArrowDown') { ev.preventDefault(); p[(i + 1) % p.length].focus(); }
      else if (ev.key === 'ArrowUp') { ev.preventDefault(); p[(i + p.length - 1) % p.length].focus(); }
      else if (ev.key === 'Home') { ev.preventDefault(); p[0].focus(); }
      else if (ev.key === 'End') { ev.preventDefault(); p[p.length - 1].focus(); }
      else if (ev.key === 'Escape') { ev.preventDefault(); zu(true); }
      else if (ev.key === 'Tab') { zu(false); }
      else if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') {
        ev.preventDefault();
        const k = Array.prototype.slice.call(document.querySelectorAll('.menue-knopf'));
        const n = k[(k.indexOf(knopf) + (ev.key === 'ArrowRight' ? 1 : k.length - 1)) % k.length];
        n.click();
      }
    });
    S.wurzel.appendChild(kasten);
    knopf.setAttribute('aria-expanded', 'true');
    offen = { id: m.id, kasten: kasten, knopf: knopf };
    const erster = kasten.querySelector('.menue-punkt');
    if (erster) erster.focus();
  }
  document.addEventListener('mousedown', function (ev) {
    if (offen && !offen.kasten.contains(ev.target) && !ev.target.closest('.menue-knopf')) zu(false);
  });

  function schalter(sym, id, an) {
    return S.symKnopf(sym, T('bf_' + id) + (S.kuerzelVon(id) ? ' (' + S.kuerzelVon(id) + ')' : ''), function () { S.fuehreAus(id); },
      { 'aria-pressed': an ? 'true' : 'false', data: { fid: 'kp:' + id } });
  }

  S.zeichneKopf = function () {
    zu(false);
    const kasten = S.q('kopf');
    S.mitFokus(kasten, function () {
      S.leere(kasten);
      const leiste = el('div', { class: 'menue-leiste', role: 'menubar', 'aria-label': T('mn_leiste') });
      MENUE.forEach(function (m) {
        const k = el('button', {
          class: 'menue-knopf', type: 'button', role: 'menuitem', 'aria-haspopup': 'menu', 'aria-expanded': 'false', data: { fid: 'mn:' + m.id },
          on: {
            click: function () { if (offen && offen.id === m.id) zu(true); else auf(m, k); },
            mouseenter: function () { if (offen && offen.id !== m.id) auf(m, k); },
            keydown: function (ev) { if (ev.key === 'ArrowDown') { ev.preventDefault(); auf(m, k); } }
          }
        }, [T('mn_' + m.id)]);
        leiste.appendChild(k);
      });
      const zurueck = S.symKnopf('zurueck', T('bf_zurueck'), function () { S.geheVerlauf(-1); }, { data: { fid: 'kp:zurueck' } });
      const vor = S.symKnopf('vor', T('bf_vor'), function () { S.geheVerlauf(1); }, { data: { fid: 'kp:vor' } });
      zurueck.disabled = S.verlaufPos <= 0;
      vor.disabled = S.verlaufPos >= S.verlauf.length - 1;
      kasten.appendChild(el('div', { class: 'marke', title: 'Sedra IDE' }, [S.sym('marke', 18)]));
      kasten.appendChild(leiste);
      kasten.appendChild(el('div', { class: 'kopf-mitte' }, [
        zurueck, vor,
        el('button', { class: 'kopf-suche', type: 'button', title: T('bf_dateiSuche'), data: { fid: 'kp:suche' }, on: { click: function () { S.fuehreAus('dateiSuche'); } } },
          [S.sym('suche', 13), el('span', { text: S.ARBEITSBEREICH })])
      ]));
      kasten.appendChild(el('div', { class: 'kopf-rechts' }, [
        schalter('thema', 'thema', S.z.thema === 'hell'),
        schalter('links', 'seiteLinks', S.z.seiteLinks),
        schalter('unten', 'panel', S.z.panel),
        schalter('rechts', 'seiteRechts', S.z.seiteRechts)
      ]));
    });
  };

  /* Statusleiste */
  let zeiger = null;
  function zelle(text, titel, tun, fid, extra) {
    const a = { class: 'status-zelle' + (extra ? ' ' + extra : ''), title: titel || null };
    if (!tun) return el('span', a, [text]);
    a.type = 'button'; a.on = { click: tun }; a.data = { fid: fid };
    return el('button', a, typeof text === 'string' ? [text] : text);
  }
  S.zeichneStatus = function () {
    const kasten = S.q('status');
    S.mitFokus(kasten, function () {
      S.leere(kasten);
      const d = S.aktiveDatei();
      const h = S.syntax.alleHinweise();
      const fehler = h.filter(function (x) { return x.art === 'fehler'; }).length;
      const links = el('div', { class: 'status-teil' }, [
        zelle([S.sym('ordner', 12), S.ARBEITSBEREICH], T('st_ordner'), function (ev) {
          if (S.quelle === 'echt' && S.echt.projekte.length > 1 && S.verwalten) S.verwalten.projektMenue(ev);
          else S.fuehreAus('ansichtExplorer');
        }, 'st:ordner'),
        zelle([S.sym('zweig', 12), S.ZWEIG], T('st_zweig'), function () { S.fuehreAus('ansichtQuellcode'); }, 'st:zweig'),
        zelle([S.sym('fehler', 12), String(fehler), S.sym('warnung', 12), String(h.length - fehler)],
          T('st_probleme', fehler, h.length - fehler), function () { S.z.panel = true; S.z.panelReiter = 'probleme'; S.merke(); S.melde('layout'); S.melde('panel'); }, 'st:probleme'),
        S.z.beispiel ? zelle(T('beispiel'), T('quelle_beispiel'), null, null, 'hinweis') : null
      ]);
      const rechts = el('div', { class: 'status-teil' });
      if (d) {
        const z = zeiger || { zeile: 1, spalte: 1, auswahl: 0 };
        rechts.appendChild(zelle(T('st_zeile', z.zeile, z.spalte) + (z.auswahl ? ' ' + T('st_auswahl', z.auswahl) : ''), T('bf_geheZeile'),
          function () { S.fuehreAus('geheZeile'); }, 'st:zeile'));
        rechts.appendChild(zelle(T('st_einrueckung'), null));
        rechts.appendChild(zelle('UTF-8', T('st_kodierung')));
        rechts.appendChild(zelle('LF', T('st_zeilenende')));
        rechts.appendChild(zelle({ js: 'JavaScript', py: 'Python', yaml: 'YAML', md: 'Markdown', txt: T('st_text') }[d.sprache] || d.sprache, T('st_sprache')));
      }
      rechts.appendChild(zelle(S.z.sprache.toUpperCase(), T('bf_sprache'), function () { S.fuehreAus('sprache'); }, 'st:sprache'));
      kasten.appendChild(links);
      kasten.appendChild(rechts);
    });
  };

  S.an('zeiger', function (z) { zeiger = z; S.zeichneStatus(); });
  ['aktiv', 'sprache', 'daten', 'dateien'].forEach(function (n) { S.an(n, S.zeichneStatus); });
  ['aktiv', 'sprache', 'layout'].forEach(function (n) { S.an(n, S.zeichneKopf); });
  let warte = null;
  S.an('inhalt', function () {
    if (warte) root.clearTimeout(warte);
    warte = root.setTimeout(function () { warte = null; S.zeichneStatus(); }, 300);
  });
})(window);
