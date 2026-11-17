/* Sedra IDE: unteres Panel (Terminal, Ausgabe, Probleme, Debug-Konsole, Live-Logs). Terminal führt keine Befehle aus (Entscheidung E5): es zeigt nur, was der Coder schon geladen hat. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  const REITER = ['terminal', 'ausgabe', 'probleme', 'debug', 'logs'];
  const term = []; /* {art, text} */
  const eingaben = [];
  let eingabePos = 0;

  function zeilen(liste, leerKey) {
    const k = el('div', { class: 'mono-liste', role: 'log', tabindex: '0' });
    if (!liste.length) k.appendChild(el('div', { class: 'z-leise', text: T(leerKey) }));
    liste.forEach(function (z) { k.appendChild(el('div', { class: z.art ? 'z-' + z.art : '', text: z.text })); });
    root.setTimeout(function () { k.scrollTop = k.scrollHeight; }, 0);
    return k;
  }
  function schreib(text, art) { term.push({ art: art || '', text: text }); }

  /* Befehle des Terminals: nur Anzeige der geladenen Daten, kein Aufruf des Servers, nichts wird auf dem Rechner ausgeführt (E5). */
  function fuehre(zeile) {
    schreib('sedra> ' + zeile, 'leise');
    const teile = zeile.trim().split(/\s+/);
    const b = (teile[0] || '').toLowerCase();
    const arg = teile.slice(1).join(' ');
    if (!b) return;
    if (b === 'hilfe' || b === 'help') schreib(T('tm_hilfe'));
    else if (b === 'ls' || b === 'dir') {
      const alle = S.quelle === 'echt' ? S.alleDateiPfade() : Object.keys(S.dateien).sort();
      const l = arg ? alle.filter(function (x) { return x.indexOf(arg.replace(/\/$/, '') + '/') === 0 || x === arg; }) : alle;
      schreib(l.length ? l.join('\n') : T('tm_keine_datei', arg));
      if (S.quelle === 'echt') schreib(T('tm_ls_hinweis'), 'leise');
    } else if (b === 'cat' || b === 'type') {
      if (S.dateien[arg]) schreib(S.dateien[arg].inhalt);
      else if (S.quelle === 'echt' && S.alleDateiPfade().indexOf(arg) >= 0) schreib(T('tm_erst_oeffnen', arg), 'warnung');
      else schreib(T('tm_keine_datei', arg), 'fehler');
    } else if (b === 'open' || b === 'oeffne') {
      if (S.quelle === 'echt' && S.alleDateiPfade().indexOf(arg) >= 0) { S.oeffneDatei(arg); schreib(T('tm_geoeffnet', arg), 'ok'); }
      else if (S.dateien[arg]) { S.oeffne(arg); schreib(T('tm_geoeffnet', arg), 'ok'); } else schreib(T('tm_keine_datei', arg), 'fehler');
    } else if (b === 'echo') schreib(arg);
    else if (b === 'status') {
      const p = S.quelle === 'echt' ? S.echt.aenderungen.map(function (e) { return e.pfad; }) : Object.keys(S.dateien).sort().filter(function (x) { return S.dateien[x].git || S.ungespeichert(x); });
      schreib(p.length ? p.map(function (x) { return (S.gitStatus(x) || 'M') + '  ' + x; }).join('\n') : T('leer_aenderungen'));
    } else if (b === 'agenten') schreib(S.AGENTEN.map(function (a) { return a.name + '  ' + T('zs_' + a.zustand); }).join('\n'));
    else if (b === 'clear' || b === 'cls') term.length = 0;
    else schreib(T(S.quelle === 'echt' ? 'tm_unbekannt_echt' : 'tm_unbekannt', b), 'warnung');
  }

  function terminal() {
    const gruss = S.z.beispiel || S.quelle === 'echt' ? [{ art: 'leise', text: T(S.quelle === 'echt' ? 'tm_gruss_echt' : 'tm_gruss') }] : [];
    const liste = zeilen(gruss.concat(term), 'leer_terminal');
    const feld = el('input', {
      type: 'text', id: 'term-feld', autocomplete: 'off', spellcheck: 'false', 'aria-label': T('tm_eingabe'), data: { fid: 'tm:feld' },
      on: { keydown: function (ev) {
        if (ev.key === 'Enter') {
          const t = feld.value;
          if (t.trim()) eingaben.push(t);
          eingabePos = eingaben.length;
          fuehre(t);
          zeichne();
        } else if (ev.key === 'ArrowUp' && eingabePos > 0) { ev.preventDefault(); eingabePos -= 1; feld.value = eingaben[eingabePos]; }
        else if (ev.key === 'ArrowDown') { ev.preventDefault(); eingabePos = Math.min(eingaben.length, eingabePos + 1); feld.value = eingaben[eingabePos] || ''; }
      } }
    });
    return [liste, el('div', { class: 'term-zeile' }, [el('label', { for: 'term-feld', text: 'sedra>' }), feld])];
  }

  function probleme() {
    const k = el('div', { role: 'list', class: 'seite-inhalt' });
    const liste = S.syntax.alleHinweise();
    if (!liste.length) k.appendChild(el('div', { class: 'leer', text: T('leer_probleme') }));
    liste.forEach(function (p, i) {
      k.appendChild(el('div', {
        class: 'problem', role: 'listitem', tabindex: '0', data: { fid: 'pb:' + i },
        on: {
          click: function () { S.editor.oeffneBei(p.datei, p.zeile); },
          keydown: function (ev) { if (ev.key === 'Enter') S.editor.oeffneBei(p.datei, p.zeile); }
        }
      }, [
        el('span', { class: p.art }, [S.sym(p.art === 'fehler' ? 'fehler' : 'warnung', 14)]),
        el('span', { text: T(p.key) }),
        el('span', { class: 'zeile-neben', text: p.datei + ' [' + T('st_zeile_kurz', p.zeile) + ']' })
      ]));
    });
    return [k];
  }

  function debug() {
    const feld = el('input', {
      type: 'text', id: 'debug-feld', autocomplete: 'off', 'aria-label': T('db_eingabe'), data: { fid: 'db:feld' },
      on: { keydown: function (ev) {
        if (ev.key !== 'Enter' || !feld.value.trim()) return;
        S.DEBUG.push({ art: '', text: '> ' + feld.value });
        S.DEBUG.push({ art: 'leise', text: T('db_attrappe') });
        zeichne();
      } }
    });
    return [zeilen(S.z.beispiel ? S.DEBUG : [], 'leer_debug'), el('div', { class: 'term-zeile' }, [el('label', { for: 'debug-feld', text: '>' }), feld])];
  }

  const BAU = {
    terminal: terminal,
    ausgabe: function () { return [zeilen(S.z.beispiel ? S.AUSGABE : [], 'leer_ausgabe')]; },
    probleme: probleme,
    debug: debug,
    logs: function () { return [zeilen(S.z.beispiel ? S.LOGS : [], 'leer_logs')]; }
  };

  function zeichne() {
    const kasten = S.q('panel');
    S.mitFokus(kasten, function () {
      S.leere(kasten);
      kasten.setAttribute('aria-label', T('pn_panel'));
      const zeile = el('div', { class: 'reiter-zeile', role: 'tablist', 'aria-label': T('pn_panel') });
      const zahl = S.syntax.alleHinweise().length;
      REITER.forEach(function (r) {
        const an = S.z.panelReiter === r;
        const k = el('button', {
          class: 'pr', type: 'button', role: 'tab', 'aria-selected': an ? 'true' : 'false', tabindex: an ? '0' : '-1', data: { fid: 'pr:' + r },
          on: {
            click: function () { S.z.panelReiter = r; S.merke(); zeichne(); },
            keydown: function (ev) { S.reiterTasten(ev, REITER, r, function (n) { S.z.panelReiter = n; S.merke(); zeichne(); S.fokusFid(kasten, 'pr:' + n); }); }
          }
        }, [T('pn_' + r)]);
        if (r === 'probleme' && zahl) k.appendChild(el('span', { class: 'zahl', text: String(zahl), style: 'margin-left:6px' }));
        zeile.appendChild(k);
      });
      zeile.appendChild(el('span', { class: 'platz' }));
      if (S.z.beispiel) zeile.appendChild(el('span', { class: 'beispiel-marke', text: T('beispiel') }));
      zeile.appendChild(S.symKnopf('zu', T('bf_panel'), function () { S.setze('panel', false); }, { data: { fid: 'pr:zu' } }));
      kasten.appendChild(zeile);
      kasten.appendChild(el('div', { class: 'panel-inhalt', role: 'tabpanel', 'aria-label': T('pn_' + S.z.panelReiter) }, (BAU[S.z.panelReiter] || terminal)()));
    });
  }
  S.zeichnePanel = zeichne;
  S.fokusTerminal = function () {
    S.z.panel = true; S.z.panelReiter = 'terminal'; S.merke();
    S.melde('layout'); zeichne();
    const f = S.q('term-feld');
    if (f) f.focus();
  };

  ['panel', 'sprache', 'daten', 'dateien'].forEach(function (n) { S.an(n, zeichne); });
  let warte = null;
  S.an('inhalt', function () {
    if (S.z.panelReiter !== 'probleme') return;
    if (warte) root.clearTimeout(warte);
    warte = root.setTimeout(function () { warte = null; zeichne(); }, 300);
  });
})(window);
