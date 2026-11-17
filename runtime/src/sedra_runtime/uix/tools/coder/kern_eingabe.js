/* Sedra IDE: Editorkern, Eingabe. Ein verstecktes Textfeld fängt Tastatur, Eingabemethoden (IME) und Zwischenablage ab,
   die Maus setzt Cursor und Auswahlen. Alles wirkt nur auf das Textmodell des Editors; nichts wird gespeichert oder gesendet. */
(function (root) {
  'use strict';
  const S = root.SIDE, K = S.kern;
  const PAARE = { '(': ')', '[': ']', '{': '}', '"': '"', "'": "'" };
  const KOMMENTAR = { js: '// ', py: '# ', yaml: '# ' };
  const EINRUECKEN = { js: /[{[(]\s*$/, py: /:\s*$/, yaml: /:\s*$/ };

  K.eingabe = function (v) {
    const d = v.doc, ta = v.eingabe;
    let komponiert = false, zieht = false, ankerWort = null;

    function setze(sel, zeige) { v.setzeAuswahl(sel, zeige); }

    /* ---- Bewegen */
    function bewege(ev) {
      const shift = ev.shiftKey, ctrl = ev.ctrlKey || ev.metaKey, kl = v.spaltenProRow();
      const neu = v.sel.map(function (s) {
        const k = K.kopie(s.k), z = d.zeilen[k.z];
        let w = s.w, ziel = null;
        const vc = K.vspalte(z, k.s), row = kl ? Math.floor(vc / kl) : 0, imRow = kl ? vc - row * kl : vc;
        switch (ev.key) {
          case 'ArrowLeft':
            if (!shift && !K.leer(s)) { ziel = K.kopie(K.bereich(s).von); break; }
            ziel = ctrl ? (k.s > 0 ? { z: k.z, s: K.wortAnfang(z, k.s) } : (k.z > 0 ? { z: k.z - 1, s: d.zeilen[k.z - 1].length } : k))
              : (k.s > 0 ? { z: k.z, s: k.s - 1 } : (k.z > 0 ? { z: k.z - 1, s: d.zeilen[k.z - 1].length } : k));
            w = null; break;
          case 'ArrowRight':
            if (!shift && !K.leer(s)) { ziel = K.kopie(K.bereich(s).bis); break; }
            ziel = ctrl ? (k.s < z.length ? { z: k.z, s: K.wortEnde(z, k.s) } : (k.z < d.zeilen.length - 1 ? { z: k.z + 1, s: 0 } : k))
              : (k.s < z.length ? { z: k.z, s: k.s + 1 } : (k.z < d.zeilen.length - 1 ? { z: k.z + 1, s: 0 } : k));
            w = null; break;
          case 'ArrowUp': case 'ArrowDown': case 'PageUp': case 'PageDown': {
            const sp = ev.key.slice(0, 2) === 'Pa' ? v.zeilenSeite() : 1, hoch = ev.key === 'ArrowUp' || ev.key === 'PageUp';
            const col = w == null ? imRow : w;
            let zz = k.z, rr = row;
            for (let i = 0; i < sp; i++) {
              if (hoch) { if (kl && rr > 0) rr -= 1; else { const n = v.zeileOben(zz); if (n === zz) { rr = -1; break; } zz = n; rr = kl ? v.zeilenRows(zz) - 1 : 0; } }
              else { if (kl && rr < v.zeilenRows(zz) - 1) rr += 1; else { const n = v.zeileUnten(zz); if (n === zz) { rr = -2; break; } zz = n; rr = 0; } }
            }
            if (rr === -1) ziel = { z: zz, s: 0 }; else if (rr === -2) ziel = { z: zz, s: d.zeilen[zz].length };
            else ziel = { z: zz, s: K.sspalte(d.zeilen[zz], Math.min(rr * (kl || 0) + col, K.vspalte(d.zeilen[zz], d.zeilen[zz].length))) };
            w = col; break;
          }
          case 'Home': {
            if (ctrl) { ziel = { z: 0, s: 0 }; break; }
            const rein = /^[ \t]*/.exec(z)[0].length;
            ziel = { z: k.z, s: (k.s === rein || rein === z.length) ? 0 : rein }; w = null; break;
          }
          case 'End':
            ziel = ctrl ? { z: d.zeilen.length - 1, s: d.zeilen[d.zeilen.length - 1].length } : { z: k.z, s: z.length }; w = null; break;
          default: return s;
        }
        return { a: shift ? s.a : K.kopie(ziel), k: ziel, w: w == null ? K.vspalte(d.zeilen[ziel.z], ziel.s) % (kl || 1e9) : w };
      });
      setze(neu);
    }

    /* ---- Text */
    function tippe(text, art) {
      d.trenne && art === 'einfuegen' && d.trenne();
      setze(K.tippe(d, v.sel, text, art || 'tippen'));
    }

    function zeilenumbruch() {
      const marke = EINRUECKEN[v.sprache];
      const edits = v.sel.map(function (s, i) {
        const b = K.bereich(s), z = d.zeilen[b.von.z];
        let rein = /^[ \t]*/.exec(z)[0];
        const vor = z.slice(0, b.von.s), davor = vor.replace(/\s+$/, ''), danach = d.zeilen[b.bis.z][b.bis.s];
        if (rein.length > b.von.s) rein = rein.slice(0, b.von.s);
        if (marke && marke.test(vor)) {
          const zu = (davor.slice(-1) === '{' && danach === '}') || (davor.slice(-1) === '[' && danach === ']') || (davor.slice(-1) === '(' && danach === ')');
          if (zu) return { von: b.von, bis: b.bis, neu: '\n' + rein + '  \n' + rein, i: i, rel: [rein.length + 3, rein.length + 3] };
          rein += '  ';
        }
        return { von: b.von, bis: b.bis, neu: '\n' + rein, i: i };
      });
      setze(K.mehrfach(d, v.sel, edits, ''));
    }

    function klammer(ch) {
      const sp = v.sprache, zu = PAARE[ch];
      if ((ch === '"' || ch === "'") && (sp === 'md' || sp === 'txt')) return false;
      const alleLeer = v.sel.every(K.leer);
      if (alleLeer && ')]}"\''.indexOf(ch) >= 0 && v.sel.every(function (s) { return d.zeilen[s.k.z][s.k.s] === ch; })) {
        setze(v.sel.map(function (s) { const p = { z: s.k.z, s: s.k.s + 1 }; return { a: p, k: K.kopie(p), w: s.w }; }));
        return true;
      }
      if (!zu) return false;
      if ((ch === '"' || ch === "'") && v.sel.some(function (s) { return K.leer(s) && /\w/.test(d.zeilen[s.k.z][s.k.s - 1] || ''); })) return false;
      const edits = v.sel.map(function (s, i) {
        const b = K.bereich(s), t = d.textZwischen(b.von, b.bis);
        return { von: b.von, bis: b.bis, neu: ch + t + zu, i: i, rel: K.leer(s) ? [1, 1] : [1, 1 + t.length] };
      });
      setze(K.mehrfach(d, v.sel, edits, 'tippen'));
      return true;
    }

    function verarbeiteText(t) {
      t = t.replace(/\r\n?/g, '\n');
      if (!t) return;
      if (t.length === 1 && klammer(t)) return;
      tippe(t, t.indexOf('\n') >= 0 || t.length > 1 ? 'einfuegen' : 'tippen');
    }

    /* ---- Tastatur */
    ta.addEventListener('keydown', function (ev) {
      if (ev.isComposing || komponiert) return;
      const ctrl = ev.ctrlKey || ev.metaKey, alt = ev.altKey, shift = ev.shiftKey, k = ev.key;
      let getan = true;
      if (k.indexOf('Arrow') === 0 && !alt) bewege(ev);
      else if ((k === 'ArrowUp' || k === 'ArrowDown') && ctrl && alt) setze(K.cursorDazu(d, v.sel, k === 'ArrowDown'));
      else if ((k === 'ArrowUp' || k === 'ArrowDown') && alt && !ctrl) setze(shift ? K.zeileDoppeln(d, v.sel, k === 'ArrowDown') : K.zeileVerschieben(d, v.sel, k === 'ArrowDown'));
      else if (k === 'Home' || k === 'End' || k === 'PageUp' || k === 'PageDown') bewege(ev);
      else if (k === 'Enter' && !ctrl && !alt) zeilenumbruch();
      else if (k === 'Backspace' && !alt) setze(K.loesche(d, v.sel, false, ctrl));
      else if (k === 'Delete' && !alt) setze(K.loesche(d, v.sel, true, ctrl));
      else if (k === 'Tab' && !ctrl && !alt) { if (v.tabFrei) { v.tabFrei = false; return; } setze(K.einruecken(d, v.sel, shift, 2)); }
      else if (k === 'Escape') { if (v.sel.length > 1) setze([v.sel[v.sel.length - 1]]); else { v.tabFrei = true; S.sag(S.T('ed_tab_frei')); } }
      else if (ctrl && !alt && (k === 'a' || k === 'A')) setze([K.auswahl({ z: 0, s: 0 }, { z: d.zeilen.length - 1, s: d.zeilen[d.zeilen.length - 1].length })], false);
      else if (ctrl && !alt && (k === 'z' || k === 'Z') && !shift) { const r = d.zurueck(); if (r) setze(r); }
      else if (ctrl && !alt && ((k === 'y' || k === 'Y') || ((k === 'z' || k === 'Z') && shift))) { const r = d.wieder(); if (r) setze(r); }
      else if (ctrl && !alt && !shift && (k === 'd' || k === 'D')) setze(K.naechstesVorkommen(d, v.sel));
      else if (ctrl && !alt && shift && (k === 'l' || k === 'L')) setze(K.alleVorkommen(d, v.sel));
      else if (ctrl && !alt && shift && (k === 'k' || k === 'K')) setze(K.zeileLoeschen(d, v.sel));
      else if (ctrl && !alt && !shift && k === '/') setze(K.kommentar(d, v.sel, KOMMENTAR[v.sprache]));
      else if (alt && !ctrl && !shift && (k === 'z' || k === 'Z')) S.editor.umbruchUm();
      else if (ctrl && shift && ev.code === 'BracketLeft') v.faltUm(v.sel[v.sel.length - 1].k.z);
      else if (ctrl && shift && ev.code === 'BracketRight') { const z = v.sel[v.sel.length - 1].k.z; if (v.gefaltet[z]) v.faltUm(z); }
      else getan = false;
      if (getan) { ev.preventDefault(); ev.stopPropagation(); }
    });

    ta.addEventListener('input', function (ev) {
      if (komponiert || ev.isComposing) return;
      const t = ta.value; ta.value = '';
      verarbeiteText(t);
    });
    ta.addEventListener('compositionstart', function () { komponiert = true; });
    ta.addEventListener('compositionend', function () { komponiert = false; const t = ta.value; ta.value = ''; verarbeiteText(t); });

    /* ---- Zwischenablage */
    function kopiertext() {
      if (v.sel.every(K.leer)) return v.sel.map(function (s) { return d.zeilen[s.k.z] + '\n'; }).join('');
      return K.text(d, v.sel);
    }
    ta.addEventListener('copy', function (ev) { ev.clipboardData.setData('text/plain', kopiertext()); ev.preventDefault(); });
    ta.addEventListener('cut', function (ev) {
      ev.clipboardData.setData('text/plain', kopiertext()); ev.preventDefault();
      if (v.sel.every(K.leer)) setze(K.zeileLoeschen(d, v.sel)); else setze(K.loesche(d, v.sel, false, false));
    });
    ta.addEventListener('paste', function (ev) {
      ev.preventDefault();
      const t = (ev.clipboardData.getData('text/plain') || '').replace(/\r\n?/g, '\n');
      if (t) tippe(t, 'einfuegen');
    });

    /* ---- Maus */
    function wahlBei(ev) {
      const p = v.positionBei(ev.clientX, ev.clientY);
      const w = K.wortBei(d, p);
      if (ev.detail >= 3) return { a: { z: p.z, s: 0 }, k: p.z < d.zeilen.length - 1 ? { z: p.z + 1, s: 0 } : { z: p.z, s: d.zeilen[p.z].length } };
      if (ev.detail === 2) return { a: w.von, k: w.bis };
      return null;
    }
    v.roll.addEventListener('mousedown', function (ev) {
      if (ev.button !== 0) return;
      const rr = v.roll.getBoundingClientRect();
      if (ev.clientX > rr.right - 14 || ev.clientY > rr.bottom - 14) return;           /* Rollbalken */
      const t = ev.target;
      if (t.closest && t.closest('.kn-falz,.kn-punkte')) { const z = +(t.closest('[data-z]').dataset.z); v.faltUm(z); ev.preventDefault(); ta.focus(); return; }
      ev.preventDefault(); ta.focus();
      const p = v.positionBei(ev.clientX, ev.clientY);
      const imRand = ev.clientX - v.hoehe.getBoundingClientRect().left < v.nrBreite();
      if (imRand) { const z = p.z; setze([{ a: { z: z, s: 0 }, k: z < d.zeilen.length - 1 ? { z: z + 1, s: 0 } : { z: z, s: d.zeilen[z].length }, w: 0 }], false); return; }
      const mehr = wahlBei(ev);
      if (mehr) { ankerWort = mehr; setze(v.sel.slice(0, -1).concat([{ a: mehr.a, k: mehr.k, w: mehr.k.s }]), false); zieht = true; return; }
      ankerWort = null;
      if (ev.altKey) { setze(v.sel.concat([K.auswahl(p)]), false); zieht = true; return; }
      if (ev.shiftKey) { const l = v.sel[v.sel.length - 1]; setze(v.sel.slice(0, -1).concat([{ a: l.a, k: p, w: p.s }]), false); }
      else setze([K.auswahl(p)], false);
      zieht = true;
    });
    function beiMaus(ev) {
      if (!zieht || !v.roll.isConnected) return;
      const p = v.positionBei(ev.clientX, ev.clientY), l = v.sel[v.sel.length - 1];
      const anker = ankerWort ? (K.vergleiche(p, ankerWort.a) < 0 ? ankerWort.k : ankerWort.a) : l.a;
      setze(v.sel.slice(0, -1).concat([{ a: anker, k: p, w: p.s }]));
    }
    function mausOben() { zieht = false; }
    root.document.addEventListener('mousemove', beiMaus);
    root.document.addEventListener('mouseup', mausOben);
    const weg = v.zerstoere;
    v.zerstoere = function () { root.document.removeEventListener('mousemove', beiMaus); root.document.removeEventListener('mouseup', mausOben); weg(); };
    v.roll.addEventListener('dblclick', function (ev) { ev.preventDefault(); });
  };
})(window);
