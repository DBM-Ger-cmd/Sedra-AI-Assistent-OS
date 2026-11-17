/* Sedra IDE: Editorkern, Auswahlen und Änderungen (ohne Oberfläche, in Node prüfbar).
   Eine Auswahl ist {a, k, w}: Anker a, Kopf (Cursor) k, w = gewünschte Spalte für Auf/Ab. Es gibt immer mindestens eine; mehrere sind Mehrfach-Cursor.
   Alle Änderungen laufen über mehrfach(): Änderungen von oben nach unten anwenden, Auswahlen mitführen, als einen Schritt für Rückgängig buchen. */
(function (root) {
  'use strict';
  const K = root.SIDE.kern;
  const WORT = /[A-Za-z0-9_$À-ɏ]/;

  K.auswahl = function (a, k) { return { a: K.kopie(a), k: K.kopie(k || a), w: (k || a).s }; };
  K.bereich = function (s) { return K.vergleiche(s.a, s.k) <= 0 ? { von: s.a, bis: s.k } : { von: s.k, bis: s.a }; };
  K.leer = function (s) { return K.gleich(s.a, s.k); };

  K.normalisiere = function (sel) {
    const l = sel.map(function (s) { return { a: K.kopie(s.a), k: K.kopie(s.k), w: s.w }; });
    l.sort(function (x, y) { return K.vergleiche(K.bereich(x).von, K.bereich(y).von); });
    const aus = [];
    l.forEach(function (s) {
      const v = aus[aus.length - 1];
      if (v && K.vergleiche(K.bereich(s).von, K.bereich(v).bis) <= 0 && (!K.leer(s) || !K.leer(v) || K.gleich(s.k, v.k))) {
        const bis = K.vergleiche(K.bereich(s).bis, K.bereich(v).bis) > 0 ? K.bereich(s).bis : K.bereich(v).bis, von = K.bereich(v).von;
        const rueck = K.vergleiche(v.a, v.k) > 0;
        v.a = K.kopie(rueck ? bis : von); v.k = K.kopie(rueck ? von : bis);
      } else aus.push(s);
    });
    return aus;
  };

  /* Position p durch eine angewendete Änderung a führen. */
  function fuehre(p, a, endeNeu) {
    if (K.vergleiche(p, a.von) <= 0) return p;
    if (K.vergleiche(p, a.bis) < 0) return K.kopie(endeNeu);
    if (p.z === a.bis.z) return { z: endeNeu.z, s: endeNeu.s + (p.s - a.bis.s) };
    return { z: p.z + (endeNeu.z - a.bis.z), s: p.s };
  }

  /* edits: [{von, bis, neu, i?, rel?}] ohne Überlappung. i = Index der Auswahl, die danach hinter (oder, mit rel, auf) dem neuen Text steht.
     Gibt die neuen Auswahlen zurück und bucht einen Schritt. */
  K.mehrfach = function (d, sel, edits, art) {
    const vorher = sel.map(function (s) { return { a: K.kopie(s.a), k: K.kopie(s.k), w: s.w }; });
    const e = edits.map(function (x) { return { von: K.kopie(x.von), bis: K.kopie(x.bis), neu: x.neu, i: x.i == null ? -1 : x.i, rel: x.rel }; });
    e.sort(function (x, y) { return K.vergleiche(x.von, y.von); });
    const stand = sel.map(function (s) { return { a: K.kopie(s.a), k: K.kopie(s.k), w: s.w }; });
    const getan = [];
    const feste = {};
    for (let n = 0; n < e.length; n++) {
      const x = e[n];
      const a = d.wende(x.von, x.bis, x.neu);
      getan.push(a);
      const ende = K.endeNach(a.von, a.neu);
      stand.forEach(function (s) { s.a = fuehre(s.a, a, ende); s.k = fuehre(s.k, a, ende); });
      for (const k in feste) { feste[k].a = fuehre(feste[k].a, a, ende); feste[k].k = fuehre(feste[k].k, a, ende); }
      for (let m = n + 1; m < e.length; m++) { e[m].von = fuehre(e[m].von, a, ende); e[m].bis = fuehre(e[m].bis, a, ende); }
      if (x.i >= 0) {
        const anfang = a.von;
        const a1 = x.rel ? K.endeNach(anfang, x.neu.slice(0, x.rel[0])) : ende, k1 = x.rel ? K.endeNach(anfang, x.neu.slice(0, x.rel[1])) : ende;
        feste[x.i] = { a: a1, k: k1, w: k1.s };
      }
    }
    const nachher = stand.map(function (s, i) { return feste[i] ? { a: feste[i].a, k: feste[i].k, w: feste[i].w } : { a: s.a, k: s.k, w: s.k.s }; });
    const norm = K.normalisiere(nachher);
    d.buche(getan, vorher, norm, art);
    return norm;
  };

  /* ---- Tippen und Löschen */
  K.tippe = function (d, sel, text, art) {
    const zeilen = text.split('\n');
    const verteilt = sel.length > 1 && zeilen.length === sel.length;
    const geordnet = sel.map(function (s, i) { return i; }).sort(function (x, y) { return K.vergleiche(K.bereich(sel[x]).von, K.bereich(sel[y]).von); });
    return K.mehrfach(d, sel, sel.map(function (s, i) {
      const b = K.bereich(s);
      return { von: b.von, bis: b.bis, neu: verteilt ? zeilen[geordnet.indexOf(i)] : text, i: i };
    }), art || 'tippen');
  };

  function wortAnfang(zeile, s) {
    let i = s;
    while (i > 0 && /\s/.test(zeile[i - 1])) i -= 1;
    if (i > 0 && WORT.test(zeile[i - 1])) { while (i > 0 && WORT.test(zeile[i - 1])) i -= 1; }
    else if (i > 0) i -= 1;
    return i;
  }
  function wortEnde(zeile, s) {
    let i = s;
    while (i < zeile.length && /\s/.test(zeile[i])) i += 1;
    if (i < zeile.length && WORT.test(zeile[i])) { while (i < zeile.length && WORT.test(zeile[i])) i += 1; }
    else if (i < zeile.length) i += 1;
    return i;
  }
  K.wortAnfang = wortAnfang; K.wortEnde = wortEnde;
  const PAARE = { '(': ')', '[': ']', '{': '}', '"': '"', "'": "'" };

  K.loesche = function (d, sel, vor, wort) {
    return K.mehrfach(d, sel, sel.map(function (s, i) {
      if (!K.leer(s)) { const b = K.bereich(s); return { von: b.von, bis: b.bis, neu: '', i: i }; }
      const p = s.k, z = d.zeilen[p.z];
      if (!vor) {
        if (p.s > 0) {
          const z0 = wort ? wortAnfang(z, p.s) : p.s - 1;
          const paar = !wort && PAARE[z[p.s - 1]] && PAARE[z[p.s - 1]] === z[p.s];
          return { von: { z: p.z, s: z0 }, bis: { z: p.z, s: paar ? p.s + 1 : p.s }, neu: '', i: i };
        }
        return p.z > 0 ? { von: { z: p.z - 1, s: d.zeilen[p.z - 1].length }, bis: p, neu: '', i: i } : { von: p, bis: p, neu: '', i: i };
      }
      if (p.s < z.length) return { von: p, bis: { z: p.z, s: wort ? wortEnde(z, p.s) : p.s + 1 }, neu: '', i: i };
      return p.z < d.zeilen.length - 1 ? { von: p, bis: { z: p.z + 1, s: 0 }, neu: '', i: i } : { von: p, bis: p, neu: '', i: i };
    }), 'loeschen');
  };

  /* ---- Zeilen: Blöcke aus den Auswahlen bilden (zusammenhängende Zeilen, ohne Doppelte) */
  K.zeilenBloecke = function (d, sel) {
    const bl = [];
    sel.forEach(function (s) {
      const b = K.bereich(s);
      let z2 = b.bis.z;
      if (b.bis.s === 0 && b.bis.z > b.von.z) z2 -= 1;                  /* Auswahl endet am Zeilenanfang: diese Zeile gehört nicht dazu */
      bl.push({ z1: b.von.z, z2: Math.max(b.von.z, z2) });
    });
    bl.sort(function (x, y) { return x.z1 - y.z1; });
    const aus = [];
    bl.forEach(function (b) {
      const v = aus[aus.length - 1];
      if (v && b.z1 <= v.z2 + 1) v.z2 = Math.max(v.z2, b.z2); else aus.push({ z1: b.z1, z2: b.z2 });
    });
    return aus;
  };

  /* Alle Zeilen der Blöcke bearbeiten: fn(zeile, nr) -> neue Zeile. Auswahlen bleiben auf ihren Zeilen. */
  K.zeilenAendern = function (d, sel, fn, art) {
    const edits = [];
    K.zeilenBloecke(d, sel).forEach(function (b) {
      for (let z = b.z1; z <= b.z2; z++) {
        const alt = d.zeilen[z], neu = fn(alt, z);
        if (neu !== alt) edits.push({ von: { z: z, s: 0 }, bis: { z: z, s: alt.length }, neu: neu });
      }
    });
    return edits.length ? K.mehrfach(d, sel, edits, art || '') : sel;
  };

  K.kommentar = function (d, sel, marke) {
    if (!marke) return sel;
    const lang = marke.trimEnd();
    const zeilen = [];
    K.zeilenBloecke(d, sel).forEach(function (b) { for (let z = b.z1; z <= b.z2; z++) if (d.zeilen[z].trim()) zeilen.push(d.zeilen[z]); });
    const alle = zeilen.length && zeilen.every(function (z) { return z.trimStart().indexOf(lang) === 0; });
    return K.zeilenAendern(d, sel, function (z) {
      if (!z.trim()) return z;
      const rein = /^[ \t]*/.exec(z)[0], rest = z.slice(rein.length);
      return alle ? rein + (rest.indexOf(marke) === 0 ? rest.slice(marke.length) : rest.slice(lang.length)) : rein + marke + rest;
    });
  };

  K.einruecken = function (d, sel, rueck, breite) {
    const eins = ' '.repeat(breite || 2);
    const mehr = sel.some(function (s) { return !K.leer(s) && K.bereich(s).von.z !== K.bereich(s).bis.z; });
    if (!rueck && !mehr) return K.tippe(d, sel, eins);
    return K.zeilenAendern(d, sel, function (z) {
      if (!rueck) return z.trim() ? eins + z : z;
      return z.indexOf(eins) === 0 ? z.slice(eins.length) : z.replace(/^[ \t]/, '');
    });
  };

  K.zeileLoeschen = function (d, sel) {
    const edits = K.zeilenBloecke(d, sel).map(function (b) {
      const ende = d.zeilen.length - 1;
      if (b.z2 < ende) return { von: { z: b.z1, s: 0 }, bis: { z: b.z2 + 1, s: 0 }, neu: '' };
      return b.z1 > 0 ? { von: { z: b.z1 - 1, s: d.zeilen[b.z1 - 1].length }, bis: { z: b.z2, s: d.zeilen[b.z2].length }, neu: '' } : { von: { z: 0, s: 0 }, bis: { z: b.z2, s: d.zeilen[b.z2].length }, neu: '' };
    });
    return K.mehrfach(d, sel, edits, '');
  };

  K.zeileDoppeln = function (d, sel, runter) {
    const bloecke = K.zeilenBloecke(d, sel);
    const edits = bloecke.map(function (b) {
      const block = d.zeilen.slice(b.z1, b.z2 + 1).join('\n');
      return runter ? { von: { z: b.z2, s: d.zeilen[b.z2].length }, bis: { z: b.z2, s: d.zeilen[b.z2].length }, neu: '\n' + block }
        : { von: { z: b.z1, s: 0 }, bis: { z: b.z1, s: 0 }, neu: block + '\n' };
    });
    const neu = K.mehrfach(d, sel, edits, '');
    if (!runter) return neu;
    return neu.map(function (s) {                       /* nach unten doppeln: der Cursor geht in die Kopie */
      const b = bloecke.filter(function (x) { return s.k.z >= x.z1 && s.k.z <= x.z2; })[0];
      const dz = b ? b.z2 - b.z1 + 1 : 0;
      return { a: { z: s.a.z + dz, s: s.a.s }, k: { z: s.k.z + dz, s: s.k.s }, w: s.w };
    });
  };

  /* Blöcke um eine Zeile verschieben (Tausch mit der Nachbarzeile); die Auswahlen gehen mit. */
  K.zeileVerschieben = function (d, sel, runter) {
    const bl = K.zeilenBloecke(d, sel).filter(function (b) { return runter ? b.z2 < d.zeilen.length - 1 : b.z1 > 0; });
    const frei = bl;
    if (!frei.length) return sel;
    const vorher = sel.map(function (s) { return { a: K.kopie(s.a), k: K.kopie(s.k), w: s.w }; });
    const getan = [];
    frei.slice().reverse().forEach(function (b) {
      const nb = runter ? b.z2 + 1 : b.z1 - 1, block = d.zeilen.slice(b.z1, b.z2 + 1).join('\n'), nachbar = d.zeilen[nb];
      const von = runter ? { z: b.z1, s: 0 } : { z: nb, s: 0 }, bis = runter ? { z: nb, s: nachbar.length } : { z: b.z2, s: d.zeilen[b.z2].length };
      getan.push(d.wende(von, bis, runter ? nachbar + '\n' + block : block + '\n' + nachbar));
    });
    const dz = runter ? 1 : -1;
    const neu = sel.map(function (s) {
      const b = frei.filter(function (x) { return s.k.z >= x.z1 && s.k.z <= x.z2; })[0];
      return b ? { a: { z: s.a.z + dz, s: s.a.s }, k: { z: s.k.z + dz, s: s.k.s }, w: s.w } : s;
    });
    const norm = K.normalisiere(neu);
    d.buche(getan, vorher, norm, '');
    return norm;
  };

  /* ---- Mehrfach-Cursor */
  K.cursorDazu = function (d, sel, runter) {
    const l = sel.slice(), s = runter ? sel[sel.length - 1] : sel[0], z = s.k.z + (runter ? 1 : -1);
    if (z < 0 || z >= d.zeilen.length) return sel;
    const p = { z: z, s: Math.min(s.w == null ? s.k.s : s.w, d.zeilen[z].length) };
    l.push({ a: p, k: K.kopie(p), w: s.w });
    return K.normalisiere(l);
  };

  K.wortBei = function (d, p) {
    const z = d.zeilen[p.z];
    let a = p.s, b = p.s;
    while (a > 0 && WORT.test(z[a - 1])) a -= 1;
    while (b < z.length && WORT.test(z[b])) b += 1;
    return { von: { z: p.z, s: a }, bis: { z: p.z, s: b } };
  };

  K.naechstesVorkommen = function (d, sel) {
    const letzte = sel[sel.length - 1];
    if (K.leer(letzte)) {
      const w = K.wortBei(d, letzte.k);
      if (K.gleich(w.von, w.bis)) return sel;
      return sel.slice(0, -1).concat([{ a: w.von, k: w.bis, w: w.bis.s }]);
    }
    const b = K.bereich(letzte);
    if (b.von.z !== b.bis.z) return sel;
    const wort = d.zeilen[b.von.z].slice(b.von.s, b.bis.s);
    for (let versuch = 0; versuch < d.zeilen.length + 1; versuch++) {
      const z = (b.bis.z + versuch) % d.zeilen.length, ab = versuch === 0 ? b.bis.s : 0;
      const i = d.zeilen[z].indexOf(wort, ab);
      if (i >= 0 && !(z === b.von.z && i === b.von.s && sel.some(function (s) { return K.gleich(K.bereich(s).von, { z: z, s: i }); }))) {
        if (sel.some(function (s) { return K.gleich(K.bereich(s).von, { z: z, s: i }); })) continue;
        return K.normalisiere(sel.concat([{ a: { z: z, s: i }, k: { z: z, s: i + wort.length }, w: i + wort.length }]));
      }
    }
    return sel;
  };

  K.alleVorkommen = function (d, sel) {
    const w = K.leer(sel[0]) ? K.wortBei(d, sel[0].k) : K.bereich(sel[0]);
    if (w.von.z !== w.bis.z || K.gleich(w.von, w.bis)) return sel;
    const wort = d.zeilen[w.von.z].slice(w.von.s, w.bis.s), aus = [];
    d.zeilen.forEach(function (zeile, z) {
      let i = zeile.indexOf(wort);
      while (i >= 0 && aus.length < 2000) { aus.push({ a: { z: z, s: i }, k: { z: z, s: i + wort.length }, w: i + wort.length }); i = zeile.indexOf(wort, i + Math.max(1, wort.length)); }
    });
    return aus.length ? aus : sel;
  };

  K.text = function (d, sel) {
    return sel.map(function (s) { const b = K.bereich(s); return d.textZwischen(b.von, b.bis); }).join('\n');
  };
})(typeof window !== 'undefined' ? window : globalThis);
