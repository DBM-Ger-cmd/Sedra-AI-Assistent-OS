/* Sedra IDE: Dateiverwaltung im Explorer (neuer Ordner, Umbenennen, Löschen). Der Coder verändert nie selbst etwas:
   jede Aktion ist ein Antrag an die Freigaben (speichern_echt.js stellt ihn und fragt den Stand ab). Gelöscht werden nur Dateien und leere Ordner.
   Hier stehen das Kontextmenü, der kleine Dialog (der Rahmen erlaubt kein prompt/confirm) und das Neuladen des Baums nach einer ausgeführten Änderung. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  const API = ['', 'api', 'uix', 'coder', 'dateien', ''].join('/');      /* zusammengesetzt, siehe echt.js */
  const V = S.verwalten = {};
  let offenesMenue = null;

  function eltern(p) { return p.split('/').slice(0, -1).join('/'); }

  /* ---- Dialog: Titel, Hinweis, optional ein Textfeld; Enter bestätigt, Escape bricht ab, der Fokus kehrt zurück. */
  V.dialog = function (titel, hinweis, wert, ok) {
    const vorher = root.document.activeElement;
    const ueber = el('div', { class: 'dlg-ueber' });
    const feld = wert == null ? null : el('input', { class: 'feld', type: 'text', 'aria-label': titel, data: { fid: 'dlg:feld' } });
    if (feld) feld.value = wert;
    function zu() { ueber.remove(); if (vorher && vorher.focus) vorher.focus(); }
    function bestaetige() { const t = feld ? feld.value.trim() : ''; if (feld && !t) return; zu(); ok(t); }
    const kasten = el('div', { class: 'dlg', role: 'dialog', 'aria-modal': 'true', 'aria-label': titel,
      on: { keydown: function (ev) { if (ev.key === 'Escape') { ev.stopPropagation(); zu(); } else if (ev.key === 'Enter') { ev.preventDefault(); bestaetige(); } } } }, [
      el('div', { class: 'dlg-titel', text: titel }),
      hinweis ? el('div', { class: 'zeile-neben', text: hinweis }) : null,
      feld,
      el('div', { class: 'knopf-reihe' }, [
        el('button', { class: 'knopf', type: 'button', data: { fid: 'dlg:ok' }, on: { click: bestaetige } }, [T('vw_ok')]),
        el('button', { class: 'knopf', type: 'button', data: { fid: 'dlg:abbruch' }, on: { click: zu } }, [T('vw_abbruch')])
      ])
    ]);
    ueber.appendChild(kasten);
    root.document.body.appendChild(ueber);
    const ziel = feld || kasten.querySelector('[data-fid="dlg:ok"]');
    ziel.focus();
    if (feld) feld.setSelectionRange(feld.value.length, feld.value.length);
  };

  /* ---- Kontextmenü: Rechtsklick oder F2/Entf auf einer Zeile des Baums. */
  function schliesseMenue() { if (offenesMenue) { offenesMenue.remove(); offenesMenue = null; } }

  V.umbenennen = function (pfad) {
    V.dialog(T('vw_umbenennen_titel', pfad), T('vw_hinweis_antrag'), pfad, function (neu) { S.verwalteEcht('umbenennen', pfad, neu.replace(/\\/g, '/')); });
  };
  V.loeschen = function (pfad) {
    V.dialog(T('vw_loeschen_titel', pfad), T('vw_loeschen_hinweis'), null, function () { S.verwalteEcht('loeschen', pfad); });
  };
  V.neuerOrdner = function (vor) {
    V.dialog(T('vw_ordner_titel'), T('vw_hinweis_antrag'), vor ? vor + '/' : '', function (name) { S.verwalteEcht('ordner', name.replace(/\\/g, '/')); });
  };

  V.menue = function (ev, pfad, istOrdner) {
    if (S.quelle !== 'echt') return;
    schliesseMenue();
    const punkte = [];
    if (istOrdner) punkte.push(['ordner', T('vw_neuer_ordner'), function () { V.neuerOrdner(pfad); }]);
    punkte.push(['umbenennen', T('vw_umbenennen'), function () { V.umbenennen(pfad); }]);
    punkte.push(['loeschen', T('vw_loeschen'), function () { V.loeschen(pfad); }]);
    const m = el('div', { class: 'kontextmenue', role: 'menu', 'aria-label': pfad, style: 'left:' + Math.min(ev.clientX, root.innerWidth - 190) + 'px;top:' + Math.min(ev.clientY, root.innerHeight - 110) + 'px' },
      punkte.map(function (p) {
        return el('button', { class: 'menue-punkt', type: 'button', role: 'menuitem', data: { fid: 'vm:' + p[0] },
          on: { click: function () { schliesseMenue(); p[2](); } } }, [p[1]]);
      }));
    root.document.body.appendChild(m);
    offenesMenue = m;
    m.firstChild.focus();
    m.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { schliesseMenue(); return; }
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
      e.preventDefault();
      const alle = Array.prototype.slice.call(m.children), i = alle.indexOf(root.document.activeElement);
      alle[(i + (e.key === 'ArrowDown' ? 1 : alle.length - 1)) % alle.length].focus();
    });
  };
  root.document.addEventListener('mousedown', function (ev) { if (offenesMenue && !offenesMenue.contains(ev.target)) schliesseMenue(); });

  /* ---- Nach einer ausgeführten Änderung: den betroffenen Ordner neu lesen (die Wurzel ersetzt die Liste an Ort und Stelle). */
  S.baumNeu = async function (ordner) {
    if (S.quelle !== 'echt' || !S.echt.projekt) return;
    try {
      if (!ordner) {
        const r = await S.ctx.api(API + encodeURIComponent(S.echt.projekt.id));
        const neu = (r.eintraege || []).map(function (e) { return S.baumKnoten(e, ''); });
        S.echt.baum.splice(0, S.echt.baum.length);
        neu.forEach(function (k) { S.echt.baum.push(k); });
      } else {
        const k = S.findeKnoten(ordner);
        if (!k || !k.ordner) return;
        k.kinder = null;
        await S.ladeOrdner(k);
      }
    } catch (e) { /* der Baum bleibt, wie er war */ }
    S.melde('dateien'); S.melde('seite');
  };

  S.nachVerwalten = async function (a) {
    const betroffen = [a.pfad];
    if (a.art === 'umbenennen' || a.art === 'loeschen') {
      Object.keys(S.dateien).forEach(function (p) {
        if (p === a.pfad || p.indexOf(a.pfad + '/') === 0) { if (!S.ungespeichert(p)) { for (let gi = S.gruppen.length - 1; gi >= 0; gi--) S.schliesse(p, gi); delete S.dateien[p]; } }
      });
    }
    if (a.ziel) betroffen.push(a.ziel);
    const ordner = [];
    betroffen.forEach(function (p) { const e = eltern(p); if (ordner.indexOf(e) < 0) ordner.push(e); });
    for (let i = 0; i < ordner.length; i++) await S.baumNeu(ordner[i]);
    S.ladeGit();
  };
})(window);
