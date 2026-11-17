/* Sedra IDE: Editorkern, Textmodell (ohne Oberfläche, deshalb auch in Node prüfbar).
   Ein Dokument ist eine Liste von Zeilen. Jede Änderung ist {von, bis, alt, neu} (Positionen {z, s}, beide 0-basiert) und läuft über ersetze();
   Rückgängig und Wiederholen arbeiten mit Gruppen solcher Änderungen samt Auswahl davor und danach. Aufeinanderfolgendes Tippen wird zusammengefasst. */
(function (root) {
  'use strict';
  const S = root.SIDE = root.SIDE || {};
  const K = S.kern = S.kern || {};
  const ZUSAMMEN_MS = 700;           /* Tippen innerhalb dieser Zeit ist ein Schritt für Rückgängig */
  const VERLAUF_MAX = 500;

  K.pos = function (z, s) { return { z: z, s: s }; };
  K.vergleiche = function (a, b) { return a.z !== b.z ? a.z - b.z : a.s - b.s; };
  K.gleich = function (a, b) { return a.z === b.z && a.s === b.s; };
  K.kopie = function (p) { return { z: p.z, s: p.s }; };

  /* Position hinter eingefügtem Text. */
  K.endeNach = function (von, text) {
    const t = text.split('\n');
    return t.length === 1 ? { z: von.z, s: von.s + t[0].length } : { z: von.z + t.length - 1, s: t[t.length - 1].length };
  };

  /* Zwei Auswahllisten stehen an denselben Stellen (Tippen im selben Zug, auch mit mehreren Cursorn). */
  function gleicheCursor(x, y) {
    if (x.length !== y.length) return false;
    for (let i = 0; i < x.length; i++) if (!K.gleich(x[i].k, y[i].k) || !K.gleich(x[i].a, y[i].a)) return false;
    return true;
  }

  K.neu = function (text) {
    const d = {
      zeilen: String(text == null ? '' : text).split('\n'),
      version: 0, verlauf: [], vorne: [], hoerer: [],
      zwischen: null, letzteZeit: 0, letzteArt: ''
    };
    let cache = null, cacheVersion = -1;
    d.text = function () {
      if (cacheVersion !== d.version) { cache = d.zeilen.join('\n'); cacheVersion = d.version; }
      return cache;
    };
    d.an = function (fn) { d.hoerer.push(fn); };
    d.klemme = function (p) {
      const z = Math.max(0, Math.min(d.zeilen.length - 1, p.z));
      return { z: z, s: Math.max(0, Math.min(d.zeilen[z].length, p.s)) };
    };
    d.textZwischen = function (von, bis) {
      if (von.z === bis.z) return d.zeilen[von.z].slice(von.s, bis.s);
      const t = [d.zeilen[von.z].slice(von.s)];
      for (let z = von.z + 1; z < bis.z; z++) t.push(d.zeilen[z]);
      t.push(d.zeilen[bis.z].slice(0, bis.s));
      return t.join('\n');
    };

    /* Eine Änderung anwenden (ohne Verlauf). Liefert {von, bis, alt, neu}, wobei bis das Ende des ersetzten Bereichs vorher war. */
    d.wende = function (von, bis, neu) {
      von = d.klemme(von); bis = d.klemme(bis);
      if (K.vergleiche(von, bis) > 0) { const t = von; von = bis; bis = t; }
      const alt = d.textZwischen(von, bis);
      const kopf = d.zeilen[von.z].slice(0, von.s), rumpf = d.zeilen[bis.z].slice(bis.s);
      const teile = neu.split('\n');
      teile[0] = kopf + teile[0];
      teile[teile.length - 1] += rumpf;
      d.zeilen.splice.apply(d.zeilen, [von.z, bis.z - von.z + 1].concat(teile));
      d.version += 1;
      const a = { von: von, bis: bis, alt: alt, neu: neu };
      d.hoerer.forEach(function (h) { h(a); });
      return a;
    };

    /* Gruppe von Änderungen als einen Schritt buchen. aenderungen in der Reihenfolge, in der sie angewendet wurden. */
    d.buche = function (aenderungen, vorher, nachher, art) {
      if (!aenderungen.length) return;
      const jetzt = Date.now();
      const letzte = d.verlauf[d.verlauf.length - 1];
      if (art && art === d.letzteArt && letzte && jetzt - d.letzteZeit < ZUSAMMEN_MS && gleicheCursor(letzte.nachher, vorher)) {
        letzte.aenderungen = letzte.aenderungen.concat(aenderungen);
        letzte.nachher = nachher;
      } else {
        d.verlauf.push({ aenderungen: aenderungen, vorher: vorher, nachher: nachher });
        if (d.verlauf.length > VERLAUF_MAX) d.verlauf.shift();
      }
      d.vorne = [];
      d.letzteArt = art || ''; d.letzteZeit = jetzt;
    };
    d.trenne = function () { d.letzteArt = ''; };

    function umkehren(a) {
      const ende = K.endeNach(a.von, a.neu);
      d.wende(a.von, ende, a.alt);
    }
    d.zurueck = function () {
      const g = d.verlauf.pop();
      if (!g) return null;
      for (let i = g.aenderungen.length - 1; i >= 0; i--) umkehren(g.aenderungen[i]);
      d.vorne.push(g); d.letzteArt = '';
      return g.vorher;
    };
    d.wieder = function () {
      const g = d.vorne.pop();
      if (!g) return null;
      g.aenderungen.forEach(function (a) { d.wende(a.von, a.bis, a.neu); });
      d.verlauf.push(g); d.letzteArt = '';
      return g.nachher;
    };
    d.setzeText = function (text) {
      d.zeilen = String(text).split('\n');
      d.version += 1; d.verlauf = []; d.vorne = []; d.letzteArt = '';
      d.hoerer.forEach(function (h) { h({ ganz: true }); });
    };
    return d;
  };

  /* ---- Gliederung nach Einrückung: Faltbereiche. Eine Zeile beginnt einen Bereich, wenn die nächste nichtleere Zeile weiter eingerückt ist. */
  K.einrueckung = function (zeile) {
    let n = 0;
    for (let i = 0; i < zeile.length; i++) { const c = zeile.charCodeAt(i); if (c === 32) n += 1; else if (c === 9) n += 4; else return n; }
    return -1;                                           /* leere oder nur aus Leerraum bestehende Zeile */
  };
  K.faltEnde = function (d, z) {
    const e0 = K.einrueckung(d.zeilen[z]);
    if (e0 < 0) return -1;
    let ende = -1, naechste = z + 1;
    while (naechste < d.zeilen.length && K.einrueckung(d.zeilen[naechste]) < 0) naechste += 1;
    if (naechste >= d.zeilen.length || K.einrueckung(d.zeilen[naechste]) <= e0) return -1;
    for (let i = naechste; i < d.zeilen.length; i++) {
      const e = K.einrueckung(d.zeilen[i]);
      if (e < 0) continue;
      if (e <= e0) break;
      ende = i;
    }
    return ende;
  };
  K.istFaltStart = function (d, z) { return K.faltEnde(d, z) > z; };
})(typeof window !== 'undefined' ? window : globalThis);
