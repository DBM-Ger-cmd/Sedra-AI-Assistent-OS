/* Sedra IDE: Editor-Komfort im eigenen Texteditor (textarea). Alles passiert nur im Text des Editors, nichts wird gespeichert oder gesendet.
   Tasten: Enter rückt ein, Klammern und Anführungszeichen schließen sich, Strg+/ kommentiert, Alt+Hoch/Runter verschiebt Zeilen,
   Umschalt+Alt+Hoch/Runter verdoppelt sie, Strg+Umschalt+K löscht die Zeile, Strg+D wählt das nächste Vorkommen, Strg+F sucht und ersetzt in der Datei.
   Änderungen laufen über execCommand('insertText'), damit Rückgängig (Strg+Z) im Editor weiter funktioniert. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  const K = S.komfort = {};
  const PAARE = { '(': ')', '[': ']', '{': '}', '"': '"', "'": "'" };
  const KOMMENTAR = { js: '// ', py: '# ', yaml: '# ' };
  const EINRUECKEN = { js: /[{[(]\s*$/, py: /:\s*$/, yaml: /:\s*$/ };

  function sprache() { const d = S.aktiveDatei(); return d ? d.sprache : 'txt'; }

  /* Text ersetzen und Auswahl setzen; Rückgängig bleibt erhalten (execCommand), Ersatz: setRangeText + input. */
  function ersetze(ta, von, bis, text, selVon, selBis) {
    ta.focus();
    ta.setSelectionRange(von, bis);
    if (!root.document.execCommand('insertText', false, text)) {
      ta.setRangeText(text, von, bis, 'end');
      ta.dispatchEvent(new root.Event('input', { bubbles: true }));
    }
    ta.setSelectionRange(selVon == null ? von + text.length : selVon, selBis == null ? (selVon == null ? von + text.length : selVon) : selBis);
  }

  function zeilenGrenzen(ta) {
    const t = ta.value;
    const von = t.lastIndexOf('\n', ta.selectionStart - 1) + 1;
    let ende = t.indexOf('\n', ta.selectionEnd > ta.selectionStart && t[ta.selectionEnd - 1] === '\n' ? ta.selectionEnd - 1 : ta.selectionEnd);
    if (ende < 0) ende = t.length;
    return { von: von, ende: ende };
  }

  function enter(ta) {
    const t = ta.value, s = ta.selectionStart;
    const zeileVon = t.lastIndexOf('\n', s - 1) + 1;
    const zeile = t.slice(zeileVon, s);
    let rein = /^[ \t]*/.exec(zeile)[0];
    const rx = EINRUECKEN[sprache()];
    const davor = zeile.replace(/\s+$/, '');
    const naechstes = t[ta.selectionEnd];
    if (rx && rx.test(zeile)) {
      const schliesst = (davor.slice(-1) === '{' && naechstes === '}') || (davor.slice(-1) === '[' && naechstes === ']') || (davor.slice(-1) === '(' && naechstes === ')');
      if (schliesst) { ersetze(ta, s, ta.selectionEnd, '\n' + rein + '  \n' + rein, s + 1 + rein.length + 2); return; }
      rein += '  ';
    }
    ersetze(ta, s, ta.selectionEnd, '\n' + rein);
  }

  function klammer(ta, ev) {
    const z = ev.key, zu = PAARE[z], t = ta.value, s = ta.selectionStart, e = ta.selectionEnd;
    const sp = sprache();
    if ((z === '"' || z === "'") && (sp === 'md' || sp === 'txt')) return false;
    if (s === e && (z === ')' || z === ']' || z === '}' || z === '"' || z === "'") && t[s] === z) { ta.setSelectionRange(s + 1, s + 1); return true; }
    if (!zu) return false;
    if (s !== e) { ersetze(ta, s, e, z + t.slice(s, e) + zu, s + 1, e + 1); return true; }
    if ((z === '"' || z === "'") && /\w/.test(t[s - 1] || '')) return false;          /* Apostroph im Wort */
    ersetze(ta, s, e, z + zu, s + 1);
    return true;
  }

  function zurueck(ta) {
    const t = ta.value, s = ta.selectionStart;
    if (s !== ta.selectionEnd || s < 1) return false;
    const a = t[s - 1], b = t[s];
    if (PAARE[a] && PAARE[a] === b) { ersetze(ta, s - 1, s + 1, ''); return true; }
    return false;
  }

  function kommentar(ta) {
    const m = KOMMENTAR[sprache()];
    if (!m) return;
    const g = zeilenGrenzen(ta), teil = ta.value.slice(g.von, g.ende).split('\n');
    const lang = m.trimEnd();
    const alle = teil.filter(function (z) { return z.trim(); }).every(function (z) { return z.trimStart().indexOf(lang) === 0; });
    const neu = teil.map(function (z) {
      if (!z.trim()) return z;
      const rein = /^[ \t]*/.exec(z)[0], rest = z.slice(rein.length);
      return alle ? rein + rest.replace(new RegExp('^' + lang.replace(/[/#]/g, '\\$&') + ' ?'), '') : rein + m + rest;
    }).join('\n');
    ersetze(ta, g.von, g.ende, neu, g.von, g.von + neu.length);
  }

  function verschiebe(ta, runter) {
    const t = ta.value, g = zeilenGrenzen(ta);
    if (runter) {
      if (g.ende >= t.length) return;
      const naechsteEnde = t.indexOf('\n', g.ende + 1) < 0 ? t.length : t.indexOf('\n', g.ende + 1);
      const unten = t.slice(g.ende + 1, naechsteEnde), block = t.slice(g.von, g.ende);
      ersetze(ta, g.von, naechsteEnde, unten + '\n' + block, g.von + unten.length + 1, g.von + unten.length + 1 + block.length);
    } else {
      if (g.von === 0) return;
      const vorVon = t.lastIndexOf('\n', g.von - 2) + 1, oben = t.slice(vorVon, g.von - 1), block = t.slice(g.von, g.ende);
      ersetze(ta, vorVon, g.ende, block + '\n' + oben, vorVon, vorVon + block.length);
    }
  }

  function verdopple(ta, runter) {
    const g = zeilenGrenzen(ta), block = ta.value.slice(g.von, g.ende);
    ersetze(ta, g.ende, g.ende, '\n' + block, runter ? g.ende + 1 : g.von, runter ? g.ende + 1 + block.length : g.von + block.length);
  }

  function zeileLoeschen(ta) {
    const t = ta.value, g = zeilenGrenzen(ta);
    const bis = g.ende < t.length ? g.ende + 1 : g.ende, von = g.ende >= t.length && g.von > 0 ? g.von - 1 : g.von;
    ersetze(ta, von, bis, '');
  }

  function naechstes(ta) {
    const t = ta.value;
    if (ta.selectionStart === ta.selectionEnd) {
      const s = ta.selectionStart;
      let a = s, b = s;
      while (a > 0 && /\w/.test(t[a - 1])) a -= 1;
      while (b < t.length && /\w/.test(t[b])) b += 1;
      if (a !== b) ta.setSelectionRange(a, b);
      return;
    }
    const wort = t.slice(ta.selectionStart, ta.selectionEnd);
    let i = t.indexOf(wort, ta.selectionEnd);
    if (i < 0) i = t.indexOf(wort);
    if (i >= 0) ta.setSelectionRange(i, i + wort.length);
  }

  const TASTEN = {
    Enter: function (ta, ev) { if (ev.ctrlKey || ev.altKey || ev.shiftKey || ev.metaKey) return false; enter(ta); return true; },
    Backspace: function (ta, ev) { return !(ev.ctrlKey || ev.altKey || ev.metaKey) && zurueck(ta); },
    '/': function (ta, ev) { if (!ev.ctrlKey) return false; kommentar(ta); return true; },
    ArrowUp: function (ta, ev) { if (!ev.altKey || ev.ctrlKey) return false; if (ev.shiftKey) verdopple(ta, false); else verschiebe(ta, false); return true; },
    ArrowDown: function (ta, ev) { if (!ev.altKey || ev.ctrlKey) return false; if (ev.shiftKey) verdopple(ta, true); else verschiebe(ta, true); return true; },
    K: function (ta, ev) { if (!(ev.ctrlKey && ev.shiftKey)) return false; zeileLoeschen(ta); return true; },
    k: function (ta, ev) { if (!(ev.ctrlKey && ev.shiftKey)) return false; zeileLoeschen(ta); return true; },
    d: function (ta, ev) { if (!ev.ctrlKey || ev.shiftKey || ev.altKey) return false; naechstes(ta); return true; }
  };

  root.document.addEventListener('keydown', function (ev) {
    const ta = ev.target;
    if (!ta || !ta.classList || !ta.classList.contains('ed-eingabe') || ev.isComposing) return;
    const f = TASTEN[ev.key];
    let getan = false;
    if (f) getan = f(ta, ev);
    else if (!ev.ctrlKey && !ev.altKey && !ev.metaKey && ev.key.length === 1 && (PAARE[ev.key] || ')]}'.indexOf(ev.key) >= 0)) getan = klammer(ta, ev);
    if (getan) { ev.preventDefault(); ev.stopPropagation(); }
  }, true);

  /* ---- Suchen und Ersetzen in der Datei (Strg+F): nur im Text des Editors. */
  let leiste = null;

  K.zu = function () {
    if (leiste) { leiste.remove(); leiste = null; }
    S.editor.fokus();
  };

  function treffer(ta, q) {
    const aus = [];
    if (!q) return aus;
    const t = ta.value.toLowerCase(), n = q.toLowerCase();
    let i = t.indexOf(n);
    while (i >= 0 && aus.length < 5000) { aus.push(i); i = t.indexOf(n, i + Math.max(1, n.length)); }
    return aus;
  }

  K.finde = function () {
    const gruppe = S.q('editorbereich').children[S.aktiveGruppe];
    const ta = gruppe && gruppe.querySelector('.ed-eingabe');
    if (!ta) return false;
    if (leiste) leiste.remove();
    const vorauswahl = ta.selectionStart !== ta.selectionEnd && ta.value.slice(ta.selectionStart, ta.selectionEnd).indexOf('\n') < 0 ? ta.value.slice(ta.selectionStart, ta.selectionEnd) : '';
    const info = el('span', { class: 'zeile-neben', 'aria-live': 'polite' });
    const feld = el('input', { class: 'feld', type: 'text', placeholder: T('kf_suchen'), 'aria-label': T('kf_suchen'), data: { fid: 'kf:feld' } });
    const ers = el('input', { class: 'feld', type: 'text', placeholder: T('kf_ersetzen'), 'aria-label': T('kf_ersetzen'), data: { fid: 'kf:ersetzen' } });
    feld.value = vorauswahl;
    function springe(richtung) {
      const liste = treffer(ta, feld.value);
      info.textContent = feld.value ? (liste.length ? T('kf_anzahl', liste.length) : T('kf_keine')) : '';
      if (!liste.length) return;
      const ab = richtung > 0 ? ta.selectionEnd : ta.selectionStart;
      let i = richtung > 0 ? liste.findIndex(function (p) { return p >= ab; }) : -1;
      if (richtung < 0) { for (let k = liste.length - 1; k >= 0; k--) if (liste[k] < ab) { i = k; break; } if (i < 0) i = liste.length - 1; }
      else if (i < 0) i = 0;
      ta.setSelectionRange(liste[i], liste[i] + feld.value.length);
      S.editor.geheZu(ta.value.slice(0, liste[i]).split('\n').length);
      ta.setSelectionRange(liste[i], liste[i] + feld.value.length);
      feld.focus();
      info.textContent = T('kf_von', i + 1, liste.length);
    }
    function ersetzeEins() {
      if (!feld.value || ta.value.slice(ta.selectionStart, ta.selectionEnd).toLowerCase() !== feld.value.toLowerCase()) { springe(1); return; }
      ersetze(ta, ta.selectionStart, ta.selectionEnd, ers.value);
      springe(1);
    }
    function ersetzeAlle() {
      const liste = treffer(ta, feld.value);
      if (!liste.length) return;
      const neu = ta.value.replace(new RegExp(feld.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), function () { return ers.value; });
      ersetze(ta, 0, ta.value.length, neu, 0);
      S.sag(T('kf_ersetzt', liste.length));
      info.textContent = '';
    }
    feld.addEventListener('input', function () { springe(1); });
    feld.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); springe(ev.shiftKey ? -1 : 1); } });
    ers.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); ersetzeEins(); } });
    leiste = el('div', { class: 'finde-leiste', role: 'search', 'aria-label': T('kf_suchen'),
      on: { keydown: function (ev) { if (ev.key === 'Escape') { ev.stopPropagation(); K.zu(); } } } }, [
      feld, ers, info,
      el('button', { class: 'knopf', type: 'button', data: { fid: 'kf:zurueck' }, title: T('kf_vorher'), on: { click: function () { springe(-1); } } }, ['↑']),
      el('button', { class: 'knopf', type: 'button', data: { fid: 'kf:weiter' }, title: T('kf_weiter'), on: { click: function () { springe(1); } } }, ['↓']),
      el('button', { class: 'knopf', type: 'button', data: { fid: 'kf:eins' }, on: { click: ersetzeEins } }, [T('kf_eins')]),
      el('button', { class: 'knopf', type: 'button', data: { fid: 'kf:alle' }, on: { click: ersetzeAlle } }, [T('kf_alle')]),
      S.symKnopf('zu', T('kf_zu'), K.zu, { data: { fid: 'kf:zu' } })
    ]);
    gruppe.appendChild(leiste);
    feld.focus(); feld.select();
    if (vorauswahl) springe(1);
    return true;
  };

  S.an('editor', function () { leiste = null; });
})(window);
