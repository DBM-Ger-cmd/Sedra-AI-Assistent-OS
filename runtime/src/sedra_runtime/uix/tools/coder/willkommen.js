/* Sedra IDE: Willkommensseite (Start, Zuletzt, Einfuehrungen). */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  const W = S.willkommen = {};

  function verweis(sym, text, tun, neben) {
    return el('button', { class: 'wk-verweis', type: 'button', on: { click: tun } }, [
      S.sym(sym, 16), el('span', { text: text }), neben ? el('span', { class: 'neben', text: neben }) : null
    ]);
  }
  function karte(titel, text, tun) {
    return el('button', { class: 'wk-karte', type: 'button', on: { click: tun } }, [
      el('strong', { text: titel }), el('span', { text: text })
    ]);
  }

  W.baue = function () {
    const start = el('div', { class: 'wk-liste' }, [
      verweis('plus', T('wk_neu'), function () { S.fuehreAus('neueDatei'); }),
      verweis('datei', T('wk_oeffnen'), function () { S.fuehreAus('dateiSuche'); }),
      verweis('ordner', T('wk_ordner'), function () { S.fuehreAus('ansichtExplorer'); }),
      verweis('verbinden', T('wk_verbinden'), function () { S.sag(T('wk_verbinden_aus')); })
    ]);
    const zuletzt = el('div', { class: 'wk-liste' });
    const pfade = S.z.beispiel ? ['src/start.js', 'docs/plan.md', 'config/shell.yaml', 'README.md'] : [];
    pfade.filter(S.gibt).forEach(function (p) {
      const i = p.lastIndexOf('/');
      zuletzt.appendChild(verweis('datei', p.slice(i + 1), function () { S.oeffne(p); }, i > 0 ? p.slice(0, i) : S.ARBEITSBEREICH));
    });
    if (!zuletzt.childElementCount) zuletzt.appendChild(el('span', { class: 'neben', text: T('leer_zuletzt') }));

    const rechts = el('div', {}, [
      el('h2', { text: T('wk_einfuehrungen') }),
      karte(T('wk_e1_titel'), T('wk_e1_text'), function () { S.fuehreAus('palette'); }),
      karte(T('wk_e2_titel'), T('wk_e2_text'), function () { S.fuehreAus('teilen'); }),
      karte(T('wk_e3_titel'), T('wk_e3_text'), function () { S.fuehreAus('ansichtAgenten'); }),
      karte(T('wk_e4_titel'), T('wk_e4_text'), function () { S.fuehreAus('thema'); })
    ]);
    const links = el('div', {}, [
      el('h2', { text: T('wk_start') }), start,
      el('h2', { text: T('wk_zuletzt') }), zuletzt
    ]);
    return el('div', { class: 'willkommen', role: 'tabpanel', 'aria-label': T('wk_reiter') }, [
      el('div', { class: 'wk-innen' }, [
        el('h1', { text: T('wk_titel') }),
        el('p', { class: 'wk-unter', text: T('wk_unter') }),
        el('div', { class: 'wk-spalten' }, [links, rechts])
      ])
    ]);
  };
})(window);
