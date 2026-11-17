/* Sedra IDE: Explorer (Offene Editoren, Ordnerbaum, Gliederung, Zeitachse). */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;

  function hatGit(k) {
    if (!k.kinder) { const d = S.dateien[k.pfad]; return !!(d && d.git); }
    return k.kinder.some(hatGit);
  }

  function baumZeile(k, tiefe, aktivPfad) {
    const ordner = !!(k.kinder || k.ordner);
    const zu = ordner && !!S.z.zugeklappt['o:' + k.pfad];
    const d = S.dateien[k.pfad];
    const z = el('div', {
      class: 'baum-zeile' + (k.pfad === aktivPfad ? ' gewaehlt' : ''), role: 'treeitem', tabindex: '-1',
      'aria-level': String(tiefe + 1), 'aria-expanded': ordner ? (zu ? 'false' : 'true') : null,
      'aria-selected': k.pfad === aktivPfad ? 'true' : 'false', title: k.pfad,
      data: { fid: 'b:' + k.pfad, pfad: k.pfad, ordner: ordner ? '1' : '' }
    }, [
      ordner ? S.sym('pfeilR', 12, 'pfeil' + (zu ? '' : ' offen')) : S.sym('datei', 14),
      el('span', { class: 'zeile-name' + (d && d.git ? ' name-' + d.git : ''), text: k.name }),
      ordner ? (hatGit(k) ? el('span', { class: 'git-punkt', title: T('git_enthaelt') }) : null)
        : (d && d.git ? el('span', { class: 'git git-' + d.git, text: d.git }) : null)
    ]);
    z.style.paddingLeft = (8 + tiefe * 12) + 'px';
    return z;
  }

  function fuelle(kasten, knoten, tiefe, aktivPfad) {
    knoten.forEach(function (k) {
      kasten.appendChild(baumZeile(k, tiefe, aktivPfad));
      if (k.kinder && !S.z.zugeklappt['o:' + k.pfad]) fuelle(kasten, k.kinder, tiefe + 1, aktivPfad);
    });
  }

  function waehle(z) {
    if (!z) return;
    const p = z.dataset.pfad;
    if (z.dataset.ordner) {
      S.z.zugeklappt['o:' + p] = !S.z.zugeklappt['o:' + p]; S.merke(); S.melde('seite');
      const k = S.z.zugeklappt['o:' + p] ? null : S.findeKnoten(p);
      if (k && k.ordner && !k.kinder) S.ladeOrdner(k);
    } else S.oeffneDatei(p);
  }

  function baum(aktivPfad) {
    const kasten = el('div', { role: 'tree', 'aria-label': T('ex_ordner') });
    if (S.quelle === 'beispiel' && !S.z.beispiel) { kasten.appendChild(el('div', { class: 'leer', text: T('leer_ordner') })); }
    else fuelle(kasten, S.BAUM, 0, aktivPfad);
    Object.keys(S.dateien).filter(function (p) { return S.dateien[p].neu; }).forEach(function (p) {
      kasten.appendChild(baumZeile({ name: S.dateien[p].name, pfad: p }, 0, aktivPfad));
    });
    const alle = kasten.querySelectorAll('.baum-zeile');
    const start = kasten.querySelector('.baum-zeile.gewaehlt') || alle[0];
    if (start) start.tabIndex = 0;

    kasten.addEventListener('click', function (ev) { waehle(ev.target.closest('.baum-zeile')); });
    kasten.addEventListener('keydown', function (ev) {
      const z = ev.target.closest('.baum-zeile');
      if (!z) return;
      const liste = Array.prototype.slice.call(kasten.querySelectorAll('.baum-zeile'));
      const i = liste.indexOf(z);
      let ziel = null;
      if (ev.key === 'ArrowDown') ziel = liste[i + 1];
      else if (ev.key === 'ArrowUp') ziel = liste[i - 1];
      else if (ev.key === 'Home') ziel = liste[0];
      else if (ev.key === 'End') ziel = liste[liste.length - 1];
      else if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); waehle(z); return; }
      else if (ev.key === 'ArrowRight' && z.dataset.ordner) {
        ev.preventDefault();
        if (z.getAttribute('aria-expanded') === 'false') waehle(z); else ziel = liste[i + 1];
      } else if (ev.key === 'ArrowLeft') {
        ev.preventDefault();
        if (z.dataset.ordner && z.getAttribute('aria-expanded') === 'true') { waehle(z); return; }
        const eltern = z.dataset.pfad.split('/').slice(0, -1).join('/');
        ziel = liste.filter(function (x) { return x.dataset.pfad === eltern; })[0];
      } else return;
      if (ziel) { ev.preventDefault(); z.tabIndex = -1; ziel.tabIndex = 0; ziel.focus(); }
    });
    return kasten;
  }

  function offeneEditoren(aktivPfad) {
    const kasten = el('div', { role: 'list' });
    S.gruppen.forEach(function (g, gi) {
      g.reiter.forEach(function (p) {
        const name = p === 'willkommen' ? T('wk_reiter') : S.dateien[p].name;
        const hier = gi === S.aktiveGruppe && g.aktiv === p;
        kasten.appendChild(el('div', {
          class: 'listen-zeile' + (hier ? ' gewaehlt' : ''), role: 'listitem', tabindex: '0', data: { fid: 'oe:' + gi + ':' + p },
          on: {
            click: function () { S.oeffne(p, gi); },
            keydown: function (ev) { if (ev.key === 'Enter') S.oeffne(p, gi); if (ev.key === 'Delete') S.schliesse(p, gi); }
          }
        }, [
          S.sym(p === 'willkommen' ? 'marke' : 'datei', 14),
          el('span', { class: 'zeile-name', text: name }),
          S.ungespeichert(p) ? el('span', { class: 'zeile-neben', text: T('ex_ungespeichert') }) : null,
          S.gruppen.length > 1 ? el('span', { class: 'zeile-neben', text: T('ex_gruppe', gi + 1) }) : null
        ]));
      });
    });
    return kasten;
  }

  function gliederung() {
    const kasten = el('div', { role: 'list' });
    const d = S.aktiveDatei();
    const punkte = d ? S.syntax.gliederung(d.inhalt, d.sprache) : [];
    if (!punkte.length) { kasten.appendChild(el('div', { class: 'leer', text: T(d ? 'leer_gliederung' : 'leer_keine_datei') })); return kasten; }
    punkte.forEach(function (p, i) {
      const z = el('div', {
        class: 'listen-zeile', role: 'listitem', tabindex: '0', data: { fid: 'gl:' + i },
        on: {
          click: function () { S.editor.geheZu(p.zeile); },
          keydown: function (ev) { if (ev.key === 'Enter') S.editor.geheZu(p.zeile); }
        }
      }, [
        S.sym('gliederung', 12),
        el('span', { class: 'zeile-name', text: p.name }),
        el('span', { class: 'zeile-neben', text: T('gl_' + p.art) + ' ' + p.zeile })
      ]);
      z.style.paddingLeft = (20 + p.tiefe * 12) + 'px';
      kasten.appendChild(z);
    });
    return kasten;
  }

  function zeitachse() {
    const kasten = el('div', { role: 'list' });
    const liste = S.quelle === 'beispiel' && S.z.beispiel ? S.ZEITACHSE : [];
    if (!liste.length) kasten.appendChild(el('div', { class: 'leer', text: T('leer_zeitachse') }));
    liste.forEach(function (e) {
      kasten.appendChild(el('div', { class: 'listen-zeile', role: 'listitem' }, [
        S.sym('uhr', 12), el('span', { class: 'zeile-name', text: e.text }), el('span', { class: 'zeile-neben', text: e.zeit })
      ]));
    });
    return kasten;
  }

  S.ansichten.explorer = function () {
    const aktivPfad = (S.aktiveDatei() || {}).pfad;
    let offen = 0;
    S.gruppen.forEach(function (g) { offen += g.reiter.length; });
    const inhalt = el('div', { class: 'seite-inhalt' }, [
      S.abschnitt('abs:offen', T('ex_offen'), offeneEditoren(aktivPfad), el('span', { class: 'zahl', text: String(offen) })),
      S.abschnitt('abs:baum', S.ARBEITSBEREICH, baum(aktivPfad),
        S.quelle === 'echt' ? el('span', { class: 'beispiel-marke', text: T('echt_marke') })
          : (S.z.beispiel ? el('span', { class: 'beispiel-marke', text: T('beispiel') }) : null)),
      S.abschnitt('abs:gliederung', T('ex_gliederung'), gliederung()),
      S.abschnitt('abs:zeitachse', T('ex_zeitachse'), zeitachse())
    ]);
    return {
      titel: T('an_explorer'), inhalt: inhalt,
      aktionen: [S.symKnopf('plus', T('bf_neueDatei'), function () { S.fuehreAus('neueDatei'); }, { data: { fid: 'ex:neu' } })]
    };
  };
})(window);
