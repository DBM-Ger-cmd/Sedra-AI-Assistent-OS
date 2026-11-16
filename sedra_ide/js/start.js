/* Sedra IDE: Layout anwenden, Teiler zum Ziehen, Start. */
(function (root) {
  'use strict';
  const S = root.SIDE, T = S.T;

  function klemme(k, v) { const g = S.GRENZEN[k]; return Math.min(g[1], Math.max(g[0], Math.round(v))); }

  /* Sprache und Thema auf das Dokument legen. */
  S.wendeAn = function () {
    document.documentElement.lang = S.z.sprache;
    document.documentElement.dataset.theme = S.z.thema === 'hell' ? 'hell' : 'dunkel';
    document.title = T('titel');
    const s = S.q('sprung');
    if (s) s.textContent = T('sprung');
  };

  function layout() {
    const l = S.q('seite-links'), r = S.q('seite-rechts'), p = S.q('panel');
    const tl = S.q('teiler-links'), tr = S.q('teiler-rechts'), tp = S.q('teiler-panel');
    l.hidden = tl.hidden = !S.z.seiteLinks;
    r.hidden = tr.hidden = !S.z.seiteRechts;
    p.hidden = tp.hidden = !S.z.panel;
    /* Auf schmalen Fenstern bleibt dem Editor eine Mindestbreite. */
    const frei = Math.max(0, root.innerWidth - 44 - 200);
    let bl = klemme('breiteLinks', S.z.breiteLinks), br = klemme('breiteRechts', S.z.breiteRechts);
    if ((S.z.seiteLinks ? bl : 0) + (S.z.seiteRechts ? br : 0) > frei) {
      br = Math.max(S.GRENZEN.breiteRechts[0], Math.min(br, frei - (S.z.seiteLinks ? bl : 0)));
      bl = Math.max(S.GRENZEN.breiteLinks[0], Math.min(bl, frei - (S.z.seiteRechts ? br : 0)));
    }
    l.style.width = bl + 'px';
    r.style.width = br + 'px';
    const hp = Math.min(klemme('hoehePanel', S.z.hoehePanel), Math.max(S.GRENZEN.hoehePanel[0], root.innerHeight - 220));
    p.style.height = hp + 'px';
    [[tl, 'breiteLinks', bl], [tr, 'breiteRechts', br], [tp, 'hoehePanel', hp]].forEach(function (x) {
      x[0].setAttribute('aria-valuenow', String(x[2]));
      x[0].setAttribute('aria-valuemin', String(S.GRENZEN[x[1]][0]));
      x[0].setAttribute('aria-valuemax', String(S.GRENZEN[x[1]][1]));
    });
    tl.setAttribute('aria-label', T('tl_links'));
    tr.setAttribute('aria-label', T('tl_rechts'));
    tp.setAttribute('aria-label', T('tl_panel'));
  }

  /* Teiler: Ziehen mit der Maus, Pfeiltasten mit der Tastatur. richtung 1 = waechst nach rechts/unten. */
  function teiler(id, schluessel, achse, richtung) {
    const t = S.q(id);
    t.addEventListener('pointerdown', function (ev) {
      ev.preventDefault();
      const start = achse === 'x' ? ev.clientX : ev.clientY;
      const wert = S.z[schluessel];
      t.classList.add('zieht');
      document.body.classList.add('zieht');
      t.setPointerCapture(ev.pointerId);
      function zieh(e) {
        const jetzt = achse === 'x' ? e.clientX : e.clientY;
        S.z[schluessel] = klemme(schluessel, wert + (jetzt - start) * richtung);
        layout();
      }
      function ende() {
        t.removeEventListener('pointermove', zieh);
        t.removeEventListener('pointerup', ende);
        t.removeEventListener('pointercancel', ende);
        t.classList.remove('zieht');
        document.body.classList.remove('zieht');
        S.merke();
      }
      t.addEventListener('pointermove', zieh);
      t.addEventListener('pointerup', ende);
      t.addEventListener('pointercancel', ende);
    });
    t.addEventListener('keydown', function (ev) {
      const plus = achse === 'x' ? 'ArrowRight' : 'ArrowDown', minus = achse === 'x' ? 'ArrowLeft' : 'ArrowUp';
      if (ev.key !== plus && ev.key !== minus) return;
      ev.preventDefault();
      S.z[schluessel] = klemme(schluessel, S.z[schluessel] + (ev.key === plus ? 16 : -16) * richtung);
      S.merke();
      layout();
    });
    t.addEventListener('dblclick', function () { S.fuehreAus('layoutStandard'); });
  }

  function start() {
    S.wendeAn();
    teiler('teiler-links', 'breiteLinks', 'x', 1);
    teiler('teiler-rechts', 'breiteRechts', 'x', -1);
    teiler('teiler-panel', 'hoehePanel', 'y', -1);
    S.an('layout', layout);
    S.an('sprache', layout);
    root.addEventListener('resize', layout);
    layout();
    S.zeichneKopf();
    S.zeichneLinks();
    S.zeichneRechts();
    S.zeichnePanel();
    S.editor.zeichnen(false);
    S.zeichneStatus();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})(window);
