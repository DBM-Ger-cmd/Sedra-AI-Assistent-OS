/* Sedra IDE: Editorkern, Minimap. Eine Zeichenfläche zeigt die ganze Datei als Balken (Einrückung = Abstand links, Zeilenlänge = Breite, Kommentare blasser).
   Bei langen Dateien fasst ein Balken mehrere Zeilen zusammen, deshalb kostet sie bei 40000 Zeilen nicht mehr als bei 400. Der Rahmen zeigt den sichtbaren Ausschnitt;
   Klicken und Ziehen scrollt. Nur lesen, verändert nichts. */
(function (root) {
  'use strict';
  const S = root.SIDE, K = S.kern, el = S.el;
  const BREITE = 84, ZEILE_MAX = 3;
  const KOMMENTAR = /^\s*(#|\/\/|\/\*|\*|<!--|--)/;

  /* v: Ansicht des Kerns. Liefert { element, zeichne, zerstoere }. */
  K.mini = function (v) {
    const doc = v.doc;
    const flaeche = el('canvas', { class: 'ed-mini-flaeche', 'aria-hidden': 'true' });
    const sicht = el('div', { class: 'ed-mini-sicht', 'aria-hidden': 'true' });
    const element = el('div', { class: 'ed-mini', 'aria-hidden': 'true', title: S.T('ed_minimap') }, [flaeche, sicht]);
    let hoehe = 0, zeit = null, wache = null, zieht = false;

    function farbe() {
      const w = S.wurzel || root.document.body;
      return (root.getComputedStyle(w).getPropertyValue('--text-leise') || root.getComputedStyle(element).color).trim();
    }

    function zeichne() {
      zeit = null;
      if (!element.isConnected) return;
      const h = element.clientHeight;
      if (h < 10) return;
      hoehe = h;
      const dpr = root.devicePixelRatio || 1;
      flaeche.width = Math.round(BREITE * dpr); flaeche.height = Math.round(h * dpr);
      flaeche.style.width = BREITE + 'px'; flaeche.style.height = h + 'px';
      const c = flaeche.getContext('2d');
      if (!c) return;
      c.scale(dpr, dpr);
      c.fillStyle = farbe();
      const n = doc.zeilen.length;
      const zeilenH = Math.min(ZEILE_MAX, h / n), balken = Math.max(1, Math.min(2, zeilenH - 1)), reihen = zeilenH < ZEILE_MAX ? Math.max(1, Math.floor(h / 2)) : n;
      const proReihe = n / reihen;
      for (let r = 0; r < reihen; r++) {
        const von = Math.floor(r * proReihe), bis = Math.max(von + 1, Math.floor((r + 1) * proReihe));
        let laenge = 0, rein = 1e9, kommentar = true, belegt = false;
        for (let z = von; z < bis && z < n; z++) {
          const t = doc.zeilen[z];
          if (!t.trim()) continue;
          belegt = true;
          const e = /^[ \t]*/.exec(t)[0].length;
          if (e < rein) rein = e;
          if (t.length > laenge) laenge = t.length;
          if (!KOMMENTAR.test(t)) kommentar = false;
        }
        if (!belegt) continue;
        c.globalAlpha = kommentar ? 0.35 : 0.8;
        const x = 4 + Math.min(rein, 30) * 0.9, b = Math.max(2, Math.min(BREITE - x - 4, (laenge - rein) * 0.7));
        c.fillRect(x, r * (h / reihen), b, balken);
      }
      rahmen();
    }

    function rahmen() {
      if (!element.isConnected || !hoehe) return;
      const gesamt = Math.max(1, v.roll.scrollHeight), top = v.roll.scrollTop / gesamt * hoehe, hh = Math.max(10, Math.min(hoehe, v.roll.clientHeight / gesamt * hoehe));
      sicht.style.top = top + 'px'; sicht.style.height = hh + 'px';
    }

    function geheZu(cy) {
      const r = element.getBoundingClientRect();
      const gesamt = Math.max(1, v.roll.scrollHeight);
      v.roll.scrollTop = Math.max(0, (cy - r.top) / hoehe * gesamt - v.roll.clientHeight / 2);
    }
    element.addEventListener('mousedown', function (ev) { ev.preventDefault(); zieht = true; geheZu(ev.clientY); });
    function beiMaus(ev) { if (zieht) geheZu(ev.clientY); }
    function mausOben() { zieht = false; }
    root.document.addEventListener('mousemove', beiMaus);
    root.document.addEventListener('mouseup', mausOben);

    function spaeter() { if (zeit) root.clearTimeout(zeit); zeit = root.setTimeout(zeichne, doc.zeilen.length > 4000 ? 250 : 80); }
    const hoerer = function () { spaeter(); };
    doc.an(hoerer);
    function beiScroll() { if (!wache) wache = root.requestAnimationFrame(function () { wache = null; rahmen(); }); }
    v.roll.addEventListener('scroll', beiScroll);
    const beob = root.ResizeObserver ? new root.ResizeObserver(function () { spaeter(); }) : null;
    if (beob) beob.observe(element);
    root.setTimeout(zeichne, 0);

    return {
      element: element, zeichne: zeichne,
      zerstoere: function () {
        const i = doc.hoerer.indexOf(hoerer); if (i >= 0) doc.hoerer.splice(i, 1);
        if (zeit) root.clearTimeout(zeit);
        root.document.removeEventListener('mousemove', beiMaus); root.document.removeEventListener('mouseup', mausOben);
        v.roll.removeEventListener('scroll', beiScroll);
        if (beob) beob.disconnect();
      }
    };
  };
})(window);
