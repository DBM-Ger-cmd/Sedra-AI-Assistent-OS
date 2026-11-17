/* Sedra IDE: Editorkern, Darstellung. Nur sichtbare Zeilen werden gezeichnet (Fenster über einer Höhenfläche), dadurch bleiben auch große Dateien flüssig.
   Zeilenumbruch rechnet mit fester Zeichenbreite (Festschrift), Falten blendet Zeilen nach Einrückung aus. Cursor und Auswahlen liegen als eigene Ebene darüber.
   Die Eingabe (Tastatur, Maus, Zwischenablage) steht in kern_eingabe.js. */
(function (root) {
  'use strict';
  const S = root.SIDE, K = S.kern, el = S.el;
  const TAB = 4, UEBERSTAND = 12, TEXT_RAND = 8;

  function vspalte(zeile, s) {
    if (zeile.indexOf('\t') < 0) return s;
    let v = 0;
    for (let i = 0; i < s; i++) v += zeile.charCodeAt(i) === 9 ? TAB - (v % TAB) : 1;
    return v;
  }
  function sspalte(zeile, v) {
    if (zeile.indexOf('\t') < 0) return Math.max(0, Math.min(zeile.length, Math.round(v)));
    let c = 0, i = 0;
    while (i < zeile.length) { const w = zeile.charCodeAt(i) === 9 ? TAB - (c % TAB) : 1; if (c + w / 2 > v) break; c += w; i += 1; }
    return i;
  }

  /* opts: { doc, sprache, name, umbruch, melde(zeiger) }. Liefert die Ansicht v. */
  K.ansicht = function (opts) {
    const doc = opts.doc;
    const v = { doc: doc, sel: opts.sel || [K.auswahl({ z: 0, s: 0 })], umbruch: !!opts.umbruch, gefaltet: {}, sprache: opts.sprache };
    let LH = S.zeilenHoehe || 19, charW = 8, cols = 0, nrBreite = 52;
    let sicht = [], oben = [], zeilenRows = [], gesamt = 1, breit = 0;
    let zustaende = K.blockZustaende(doc, v.sprache);
    let neuZeichnen = true, wache = null, fensterVon = 0, fensterBis = -1;

    const hoehe = el('div', { class: 'kn-hoehe' });
    const fenster = el('div', { class: 'kn-fenster' });
    const ueber = el('div', { class: 'kn-ueber', 'aria-hidden': 'true' });
    const unter = el('div', { class: 'kn-unter', 'aria-hidden': 'true' });       /* Auswahl und aktive Zeile liegen unter dem Text, der Cursor darüber */
    const roll = el('div', { class: 'kn-roll', role: 'region', 'aria-label': opts.name }, [hoehe]);
    hoehe.appendChild(unter); hoehe.appendChild(fenster); hoehe.appendChild(ueber);
    const eingabe = el('textarea', { class: 'kn-eingabe ed-eingabe', spellcheck: 'false', autocomplete: 'off', autocapitalize: 'off', 'aria-label': opts.name, 'aria-multiline': 'true', wrap: 'off' });
    roll.appendChild(eingabe);
    v.roll = roll; v.eingabe = eingabe; v.hoehe = hoehe;
    v.element = el('div', { class: 'kn-wurzel' }, [roll]);

    let gemessen = false;
    function messen() {
      LH = S.zeilenHoehe || 19;
      if (!gemessen) {                                       /* Zeichenbreite der Festschrift einmal messen (der Editor wird bei Schriftwechsel neu gebaut) */
        const probe = el('span', { class: 'kn-probe', text: 'M'.repeat(60) });
        hoehe.appendChild(probe);
        const w = probe.getBoundingClientRect().width / 60;
        probe.remove();
        if (w > 1) { charW = w; gemessen = true; }
      }
      nrBreite = Math.max(3, String(doc.zeilen.length).length) * charW + 34;
      const platz = roll.clientWidth - nrBreite - TEXT_RAND * 2;
      cols = v.umbruch && platz > 0 ? Math.max(8, Math.floor(platz / charW)) : 0;
    }

    function rows(z) {
      if (!cols) return 1;
      const l = doc.zeilen[z];
      return Math.max(1, Math.ceil(vspalte(l, l.length) / cols));
    }

    /* Sichtbare Zeilen (ohne gefaltete) und Zeilenhöhen aufbauen. */
    function aufbauen() {
      messen();
      sicht = []; oben = []; zeilenRows = [];
      let r = 0, z = 0, maxV = 0;
      const n = doc.zeilen.length;
      while (z < n) {
        sicht.push(z); oben.push(r);
        const k = rows(z);
        zeilenRows[z] = k; r += k;
        if (!cols) { const l = doc.zeilen[z]; if (l.length > maxV) maxV = l.length; }
        const ende = v.gefaltet[z] ? K.faltEnde(doc, z, v.sprache) : -1;
        z = ende > z ? ende + 1 : z + 1;
      }
      gesamt = Math.max(1, r);
      breit = cols ? 0 : maxV * charW + 40;
      hoehe.style.height = (gesamt * LH + 60) + 'px';
      hoehe.style.minWidth = cols ? '' : (nrBreite + breit + TEXT_RAND * 2) + 'px';
    }

    function sichtIndex(z) {                                /* Index in sicht[] der Zeile z oder der gefalteten Startzeile, die sie verbirgt */
      let a = 0, b = sicht.length - 1;
      while (a < b) { const m = (a + b + 1) >> 1; if (sicht[m] <= z) a = m; else b = m - 1; }
      return a;
    }
    v.zeileSichtbar = function (z) { return sicht[sichtIndex(z)] === z; };
    v.zeileOben = function (z) { const i = sichtIndex(z); return sicht[Math.max(0, (sicht[i] === z ? i : i + 1) - 1)]; };
    v.zeileUnten = function (z) { const i = sichtIndex(z); return sicht[Math.min(sicht.length - 1, i + 1)]; };
    v.zeilenY = function (z) { const i = sichtIndex(z); return oben[i] * LH; };

    let tcVersion = -1, tc = {};                               /* gefärbte Zeilen der aktuellen Version, damit Scrollen nicht neu färbt */
    function zeichneZeile(z) {
      const l = doc.zeilen[z];
      if (tcVersion !== doc.version) { tc = {}; tcVersion = doc.version; }
      let text;
      if (tc[z]) text = tc[z].cloneNode(true);
      else {
        text = el('span', { class: 'kn-text' });
        K.faerbeZeile(text, l, v.sprache, zustaende.hole(z));
        tc[z] = text.cloneNode(true);
      }
      if (cols) { text.classList.add('kn-umbruch'); text.style.width = (cols * charW) + 'px'; }
      const faltbar = K.istFaltStart(doc, z, v.sprache);
      const nr = el('span', { class: 'kn-nr' + (z === v.sel[v.sel.length - 1].k.z ? ' hier' : ''), style: 'width:' + nrBreite + 'px' }, [
        faltbar ? el('button', { class: 'kn-falz' + (v.gefaltet[z] ? ' zu' : ''), type: 'button', tabindex: '-1', 'aria-label': v.gefaltet[z] ? 'Ausklappen' : 'Einklappen',
          data: { z: String(z) } }, [v.gefaltet[z] ? '▸' : '▾']) : null, String(z + 1)]);
      const zeile = el('div', { class: 'kn-zeile', style: 'height:' + (zeilenRows[z] * LH) + 'px', data: { z: String(z) } }, [nr, text]);
      if (v.gefaltet[z]) text.appendChild(el('span', { class: 'kn-punkte', text: ' …', data: { z: String(z) } }));
      return zeile;
    }

    function fensterZeichnen() {
      const r0 = Math.max(0, Math.floor(roll.scrollTop / LH) - UEBERSTAND);
      const r1 = Math.ceil((roll.scrollTop + roll.clientHeight) / LH) + UEBERSTAND;
      let a = 0, b = sicht.length - 1;
      while (a < b) { const m = (a + b + 1) >> 1; if (oben[m] <= r0) a = m; else b = m - 1; }
      S.leere(fenster);
      const erste = a;
      let i = erste;
      for (; i < sicht.length && oben[i] <= r1; i++) fenster.appendChild(zeichneZeile(sicht[i]));
      fensterVon = erste; fensterBis = i - 1;
      fenster.style.transform = 'translateY(' + (oben[erste] * LH) + 'px)';
      ueberZeichnen();
    }

    function ueberZeichnen() {
      S.leere(ueber); S.leere(unter);
      const r0 = roll.scrollTop - LH * UEBERSTAND, r1 = roll.scrollTop + roll.clientHeight + LH * UEBERSTAND;
      const x0 = nrBreite + TEXT_RAND;
      v.sel.forEach(function (s, idx) {
        const b = K.bereich(s);
        if (!K.leer(s)) {
          for (let fi = fensterVon; fi <= fensterBis; fi++) {
            const z = sicht[fi];
            if (z < b.von.z || z > b.bis.z) continue;
            const y0 = v.zeilenY(z);
            if (y0 + zeilenRows[z] * LH < r0 || y0 > r1) continue;
            const l = doc.zeilen[z], vl = vspalte(l, l.length);
            const vs = z === b.von.z ? vspalte(l, b.von.s) : 0, ve = z === b.bis.z ? vspalte(l, b.bis.s) : vl + 1;
            const kl = cols || 1e9;
            for (let r = Math.floor(vs / kl); r <= Math.floor(Math.max(vs, ve - 1) / kl) && r < zeilenRows[z]; r++) {
              const ab = Math.max(vs, r * kl) - r * kl, bis = Math.min(ve, (r + 1) * kl) - r * kl;
              if (bis <= ab && !(z < b.bis.z && vl === 0)) continue;
              unter.appendChild(el('div', { class: 'kn-wahl', style: 'top:' + (y0 + r * LH) + 'px;left:' + (x0 + ab * charW) + 'px;width:' + (Math.max(bis - ab, 0.5) * charW) + 'px;height:' + LH + 'px' }));
            }
          }
        }
        const k = s.k;
        if (K.leer(s) && idx === v.sel.length - 1 && v.zeileSichtbar(k.z)) unter.appendChild(el('div', { class: 'kn-aktiv', style: 'top:' + v.zeilenY(k.z) + 'px;height:' + (zeilenRows[k.z] * LH) + 'px' }));
        if (v.zeileSichtbar(k.z)) {
          const l = doc.zeilen[k.z], vc = vspalte(l, k.s), kl = cols || 1e9, row = Math.min(zeilenRows[k.z] - 1, Math.floor(vc / kl));
          const x = x0 + (vc - row * kl) * charW, y = v.zeilenY(k.z) + row * LH;
          ueber.appendChild(el('div', { class: 'kn-cursor' + (idx === v.sel.length - 1 ? ' haupt' : ''), style: 'top:' + y + 'px;left:' + x + 'px;height:' + LH + 'px' }));
          if (idx === v.sel.length - 1) { eingabe.style.top = y + 'px'; eingabe.style.left = x + 'px'; eingabe.style.height = LH + 'px'; }
        }
      });
    }

    v.zeichne = function () {
      if (!roll.isConnected) return;
      if (neuZeichnen) { aufbauen(); neuZeichnen = false; }
      fensterZeichnen();
    };
    v.neuAufbauen = function () { neuZeichnen = true; v.zeichne(); };

    /* Cursor sichtbar halten */
    v.zeigeKopf = function () {
      const k = v.sel[v.sel.length - 1].k;
      v.entfalteBei(k.z);
      const l = doc.zeilen[k.z], vc = vspalte(l, k.s), kl = cols || 1e9, row = Math.min(zeilenRows[k.z] - 1, Math.floor(vc / kl));
      const y = v.zeilenY(k.z) + row * LH;
      if (y < roll.scrollTop) roll.scrollTop = y;
      else if (y + LH > roll.scrollTop + roll.clientHeight - 4) roll.scrollTop = y + LH - roll.clientHeight + 4;
      if (!cols) {
        const x = nrBreite + TEXT_RAND + (vc - row * kl) * charW;
        if (x < roll.scrollLeft + nrBreite + 20) roll.scrollLeft = Math.max(0, x - nrBreite - 40);
        else if (x > roll.scrollLeft + roll.clientWidth - 24) roll.scrollLeft = x - roll.clientWidth + 60;
      }
    };

    v.setzeAuswahl = function (sel, zeige) {
      v.sel = K.normalisiere(sel);
      if (neuZeichnen) { aufbauen(); neuZeichnen = false; }
      if (zeige !== false) v.zeigeKopf();
      fensterZeichnen();
      if (opts.melde) opts.melde(v);
    };

    /* ---- Falten */
    v.entfalteBei = function (z) {
      let geaendert = false;
      Object.keys(v.gefaltet).forEach(function (k) {
        const s = +k, e = K.faltEnde(doc, s, v.sprache);
        if (v.gefaltet[k] && z > s && z <= e) { delete v.gefaltet[k]; geaendert = true; }
      });
      if (geaendert) { neuZeichnen = true; aufbauen(); neuZeichnen = false; fensterZeichnen(); }
    };
    v.faltUm = function (z) {
      if (!K.istFaltStart(doc, z, v.sprache)) return;
      if (v.gefaltet[z]) delete v.gefaltet[z]; else v.gefaltet[z] = true;
      const k = v.sel[v.sel.length - 1].k;                 /* Cursor in einem nun versteckten Bereich: auf die Startzeile setzen */
      if (v.gefaltet[z] && k.z > z && k.z <= K.faltEnde(doc, z, v.sprache)) v.sel = [K.auswahl({ z: z, s: Math.min(k.s, doc.zeilen[z].length) })];
      v.neuAufbauen();
    };
    v.faltAlle = function (zu) {
      v.gefaltet = {};
      if (zu) for (let z = 0; z < doc.zeilen.length; z++) if (K.istFaltStart(doc, z, v.sprache)) { v.gefaltet[z] = true; z = K.faltEnde(doc, z, v.sprache); }
      v.sel = [K.auswahl({ z: Math.min(v.sel[0].k.z, doc.zeilen.length - 1), s: 0 })];
      v.neuAufbauen();
    };
    v.umbruchUm = function () { v.umbruch = !v.umbruch; roll.scrollLeft = 0; v.neuAufbauen(); return v.umbruch; };

    /* ---- Treffer: Pixel -> Position */
    v.positionBei = function (cx, cy) {
      const rr = hoehe.getBoundingClientRect();
      const y = Math.max(0, cy - rr.top), x = cx - rr.left - nrBreite - TEXT_RAND;
      const r = Math.min(gesamt - 1, Math.floor(y / LH));
      let a = 0, b = sicht.length - 1;
      while (a < b) { const m = (a + b + 1) >> 1; if (oben[m] <= r) a = m; else b = m - 1; }
      const z = sicht[a], row = r - oben[a];
      const vc = Math.max(0, Math.round(x / charW)) + row * (cols || 0);
      return { z: z, s: sspalte(doc.zeilen[z], Math.min(vc, vspalte(doc.zeilen[z], doc.zeilen[z].length))) };
    };
    v.zeilenSeite = function () { return Math.max(1, Math.floor(roll.clientHeight / LH) - 1); };
    v.spaltenProRow = function () { return cols; };
    v.zeilenRows = function (z) { return zeilenRows[z] || 1; };
    v.nrBreite = function () { return nrBreite; };

    /* ---- Änderungen am Dokument: Fenster neu, gefaltete Zeilen nachführen */
    function beiAenderung(a) {
      v.sel = v.sel.map(function (s) { return { a: doc.klemme(s.a), k: doc.klemme(s.k), w: s.w }; });      /* Änderung aus einer anderen Ansicht derselben Datei */
      if (a.ganz) { v.gefaltet = {}; zustaende = K.blockZustaende(doc, v.sprache); } else {
        const alt = a.alt.split('\n').length, neu = a.neu.split('\n').length, dz = neu - alt;
        zustaende.ab(a.von.z);
        if (dz !== 0) {
          const g = {};
          Object.keys(v.gefaltet).forEach(function (k) {
            const z = +k;
            if (z < a.von.z) g[z] = true; else if (z > a.bis.z) g[z + dz] = true;
          });
          v.gefaltet = g;
        }
      }
      neuZeichnen = true;
      if (!wache) wache = root.requestAnimationFrame(function () { wache = null; if (roll.isConnected) v.zeichne(); });
    }
    doc.an(beiAenderung);
    v.zerstoere = function () { const i = doc.hoerer.indexOf(beiAenderung); if (i >= 0) doc.hoerer.splice(i, 1); if (v.beob) v.beob.disconnect(); };

    roll.addEventListener('scroll', function () { fensterZeichnen(); });
    if (root.ResizeObserver) { v.beob = new root.ResizeObserver(function () { if (roll.isConnected && roll.clientWidth > 0) { neuZeichnen = true; v.zeichne(); } }); v.beob.observe(roll); }

    v.zeichne();
    return v;
  };
})(window);
