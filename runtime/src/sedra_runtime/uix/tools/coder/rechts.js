/* Sedra IDE: rechte Leiste (Chat, Sitzungen, Live-Coding, Agent-Detail). Attrappe mit Beispieldaten. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  const REITER = ['chat', 'sitzungen', 'live', 'detail'];
  let entwurf = '';

  function leer(key) { return el('div', { class: 'leer', text: T(key) }); }
  function quelle() { return el('div', { class: 'leer' }, [el('span', { class: 'beispiel-marke', text: T('beispiel') }), ' ' + T('quelle_beispiel')]); }

  function chat() {
    const liste = el('div', { class: 'chat-liste', role: 'log', 'aria-live': 'polite', 'aria-label': T('re_chat') });
    const zeilen = S.z.beispiel ? S.CHAT : S.CHAT.filter(function (c, i) { return i > 0; });
    if (!zeilen.length) liste.appendChild(leer('leer_chat'));
    zeilen.forEach(function (c) {
      liste.appendChild(el('div', { class: 'blase' + (c.ich ? ' ich' : '') }, [el('span', { class: 'von', text: c.von }), c.text]));
    });
    const feld = el('textarea', {
      class: 'feld', placeholder: T('ch_platz'), 'aria-label': T('ch_platz'), data: { fid: 're:feld' },
      on: {
        input: function () { entwurf = feld.value; },
        keydown: function (ev) { if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); ab(); } }
      }
    });
    feld.value = entwurf;
    function ab() { const t = feld.value; entwurf = ''; feld.value = ''; S.sende(t); }
    const fuss = el('div', { class: 'seite-fuss' }, [
      feld,
      el('div', { class: 'knopf-reihe', style: 'margin-top:6px;justify-content:space-between' }, [
        el('span', { class: 'zeile-neben', text: T('ch_hinweis') }),
        S.symKnopf('senden', T('ch_senden'), ab, { data: { fid: 're:senden' } })
      ])
    ]);
    root.setTimeout(function () { liste.scrollTop = liste.scrollHeight; }, 0);
    return [liste, fuss];
  }

  function sitzungen() {
    const k = el('div', { class: 'seite-inhalt', role: 'list' });
    const liste = S.z.beispiel ? S.SITZUNGEN : [];
    if (!liste.length) { k.appendChild(leer('leer_sitzungen')); return [k]; }
    k.appendChild(quelle());
    liste.forEach(function (s) {
      k.appendChild(el('button', {
        class: 'karte', type: 'button', role: 'listitem', data: { fid: 'rs:' + s.id },
        on: { click: function () { S.sag(T('re_sitzung_attrappe', s.titel)); } }
      }, [
        el('div', { class: 'karte-kopf' }, [el('span', { text: s.titel }), el('span', { class: 'zeile-neben', text: s.zeit })]),
        el('div', { class: 'karte-text', text: s.agent + ': ' + s.text })
      ]));
    });
    return [k];
  }

  function live() {
    const k = el('div', { class: 'seite-inhalt' });
    const liste = S.z.beispiel ? S.EREIGNISSE : [];
    if (!liste.length) { k.appendChild(leer('leer_live')); return [k]; }
    k.appendChild(quelle());
    const log = el('div', { role: 'log', 'aria-label': T('re_live') });
    liste.forEach(function (e, i) {
      const z = el('div', {
        class: 'ereignis listen-zeile', tabindex: e.datei ? '0' : null, title: e.datei || '', data: { fid: 'lv:' + i },
        on: {
          click: function () { if (e.datei) S.editor.oeffneBei(e.datei, e.zeile); },
          keydown: function (ev) { if (ev.key === 'Enter' && e.datei) S.editor.oeffneBei(e.datei, e.zeile); }
        }
      }, [
        el('span', { class: 'zeit', text: e.zeit }), el('span', { class: 'wer', text: e.wer }),
        el('span', { class: 'zeile-name', text: T('ev_' + e.art) + ' ' + e.text })
      ]);
      z.style.paddingLeft = '12px';
      log.appendChild(z);
    });
    k.appendChild(log);
    k.appendChild(el('div', { class: 'feld-rand' }, [
      el('button', { class: 'knopf still', type: 'button', data: { fid: 'lv:mehr' }, on: { click: function () {
        const v = S.EREIGNIS_VORRAT[S.EREIGNISSE.length % S.EREIGNIS_VORRAT.length];
        S.EREIGNISSE.push(Object.assign({ zeit: new Date().toTimeString().slice(0, 8) }, v));
        S.melde('rechts');
      } } }, [S.sym('plus', 12), T('re_live_mehr')])
    ]));
    return [k];
  }

  function detail() {
    const k = el('div', { class: 'seite-inhalt' });
    const a = S.z.beispiel ? S.AGENTEN.filter(function (x) { return x.id === S.agentGewaehlt; })[0] : null;
    if (!a) { k.appendChild(leer('leer_detail')); return [k]; }
    k.appendChild(el('div', { class: 'agent-kopf' }, [S.sym('agent', 36), el('span', { text: a.name }),
      el('span', { class: 'zustand ' + a.zustand, text: T('zs_' + a.zustand) })]));
    k.appendChild(quelle());
    [['dt_rolle', T(a.rolle_key)], ['dt_auftrag', a.auftrag], ['dt_datei', a.datei || T('dt_keine')],
      ['dt_schritte', String(a.schritte)], ['dt_seit', a.seit]].forEach(function (p) {
      k.appendChild(el('div', { class: 'eigenschaft' }, [el('span', { text: T(p[0]) }), el('span', { text: p[1] })]));
    });
    const wahl = el('div', { class: 'feld-rand knopf-reihe' });
    S.AGENTEN.forEach(function (x) {
      wahl.appendChild(el('button', {
        class: 'knopf' + (x.id === a.id ? '' : ' still'), type: 'button', 'aria-pressed': x.id === a.id ? 'true' : 'false', data: { fid: 'dt:' + x.id },
        on: { click: function () { S.agentGewaehlt = x.id; S.melde('rechts'); S.melde('seite'); } }
      }, [x.name]));
    });
    k.appendChild(wahl);
    if (a.datei) k.appendChild(el('div', { class: 'feld-rand' }, [
      el('button', { class: 'knopf still', type: 'button', data: { fid: 'dt:datei' }, on: { click: function () { S.oeffne(a.datei); } } }, [S.sym('datei', 12), T('dt_oeffnen')])
    ]));
    return [k];
  }

  const BAU = { chat: chat, sitzungen: sitzungen, live: live, detail: detail };

  S.zeichneRechts = function () {
    const kasten = S.q('seite-rechts');
    S.mitFokus(kasten, function () {
      S.leere(kasten);
      kasten.setAttribute('aria-label', T('re_leiste'));
      const zeile = el('div', { class: 'reiter-zeile', role: 'tablist', 'aria-label': T('re_leiste') });
      REITER.forEach(function (r) {
        const an = S.z.rechtsReiter === r;
        zeile.appendChild(el('button', {
          class: 'pr', type: 'button', role: 'tab', 'aria-selected': an ? 'true' : 'false', tabindex: an ? '0' : '-1', data: { fid: 'rr:' + r },
          on: {
            click: function () { S.z.rechtsReiter = r; S.merke(); S.zeichneRechts(); },
            keydown: function (ev) { S.reiterTasten(ev, REITER, r, function (n) { S.z.rechtsReiter = n; S.merke(); S.zeichneRechts(); S.fokusFid(kasten, 'rr:' + n); }); }
          }
        }, [T('re_' + r)]));
      });
      zeile.appendChild(el('span', { class: 'platz' }));
      zeile.appendChild(S.symKnopf('zu', T('bf_seiteRechts'), function () { S.setze('seiteRechts', false); }, { data: { fid: 'rr:zu' } }));
      kasten.appendChild(zeile);
      const teile = (BAU[S.z.rechtsReiter] || chat)();
      const koerper = el('div', { class: 'panel-inhalt', role: 'tabpanel', 'aria-label': T('re_' + S.z.rechtsReiter) }, teile);
      kasten.appendChild(koerper);
    });
  };

  /* Pfeiltasten in einer Reiterzeile. */
  S.reiterTasten = function (ev, liste, hier, wechsel) {
    if (ev.key !== 'ArrowRight' && ev.key !== 'ArrowLeft') return;
    ev.preventDefault();
    const n = liste.length;
    wechsel(liste[(liste.indexOf(hier) + (ev.key === 'ArrowRight' ? 1 : n - 1)) % n]);
  };
  S.fokusFid = function (kasten, fid) {
    const alle = kasten.querySelectorAll('[data-fid]');
    for (let i = 0; i < alle.length; i++) if (alle[i].dataset.fid === fid) { alle[i].focus(); return; }
  };

  ['rechts', 'chat', 'sprache', 'daten'].forEach(function (n) { S.an(n, S.zeichneRechts); });
})(window);
