/* Sedra IDE: Agenten-Ansicht links (Agentenliste, Verlauf "Letzte", Eingabe, Plan/Act, Auto-Freigabe). Attrappe. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  S.agentGewaehlt = 'hermes';
  let entwurf = '';

  /* Nachricht in den Beispiel-Chat legen. Es wird nichts gesendet. */
  S.sende = function (text) {
    text = String(text || '').trim();
    if (!text) return;
    S.CHAT.push({ von: T('ch_ich'), ich: true, text: text });
    S.CHAT.push({ von: 'Hermes', ich: false, text: T('ch_antwort', T(S.z.agentModus === 'plan' ? 'ag_plan' : 'ag_act')) });
    S.melde('chat');
  };
  S.zeigeAgent = function (id) {
    S.agentGewaehlt = id;
    S.z.seiteRechts = true;
    S.z.rechtsReiter = 'detail';
    S.merke();
    S.melde('layout');
    S.melde('rechts');
    S.melde('seite');
  };

  function agentZeile(a) {
    return el('div', {
      class: 'listen-zeile' + (a.id === S.agentGewaehlt ? ' gewaehlt' : ''), role: 'listitem', tabindex: '0', data: { fid: 'ag:' + a.id },
      on: { click: function () { S.zeigeAgent(a.id); }, keydown: function (ev) { if (ev.key === 'Enter') S.zeigeAgent(a.id); } }
    }, [
      S.sym('agent', 14),
      el('span', { class: 'zeile-name', text: a.name }),
      el('span', { class: 'zustand ' + a.zustand, text: T('zs_' + a.zustand) })
    ]);
  }

  S.ansichten.agenten = function () {
    const agenten = el('div', { role: 'list' });
    (S.z.beispiel ? S.AGENTEN : []).forEach(function (a) { agenten.appendChild(agentZeile(a)); });
    if (!agenten.childElementCount) agenten.appendChild(el('div', { class: 'leer', text: T('leer_agenten') }));

    const letzte = el('div', { role: 'list' });
    (S.z.beispiel ? S.SITZUNGEN : []).forEach(function (s) {
      letzte.appendChild(el('button', {
        class: 'karte', type: 'button', role: 'listitem', data: { fid: 'lz:' + s.id },
        on: { click: function () { S.z.seiteRechts = true; S.z.rechtsReiter = 'sitzungen'; S.merke(); S.melde('layout'); S.melde('rechts'); } }
      }, [
        el('div', { class: 'karte-kopf' }, [el('span', { text: s.titel }), el('span', { class: 'zeile-neben', text: s.zeit })]),
        el('div', { class: 'karte-text', text: s.agent + ': ' + s.text })
      ]));
    });
    if (!letzte.childElementCount) letzte.appendChild(el('div', { class: 'leer', text: T('leer_sitzungen') }));

    const feld = el('textarea', {
      class: 'feld', placeholder: T('ag_platz'), 'aria-label': T('ag_platz'), data: { fid: 'ag:feld' },
      on: {
        input: function () { entwurf = feld.value; },
        keydown: function (ev) { if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); ab(); } }
      }
    });
    feld.value = entwurf;
    function ab() {
      if (!feld.value.trim()) return;
      S.sende(feld.value);
      entwurf = ''; feld.value = '';
      S.z.seiteRechts = true; S.z.rechtsReiter = 'chat'; S.merke();
      S.melde('layout'); S.melde('rechts');
    }
    function modus(m) {
      return el('button', {
        type: 'button', 'aria-pressed': S.z.agentModus === m ? 'true' : 'false', data: { fid: 'ag:m:' + m },
        on: { click: function () { S.z.agentModus = m; S.merke(); S.melde('seite'); } }
      }, [T('ag_' + m)]);
    }
    const auto = el('button', {
      class: 'listen-zeile', type: 'button', 'aria-pressed': S.z.autoFreigabe ? 'true' : 'false', data: { fid: 'ag:auto' },
      style: 'width:100%;padding-left:4px',
      on: { click: function () { S.z.autoFreigabe = !S.z.autoFreigabe; S.merke(); S.melde('seite'); } }
    }, [
      el('span', { class: 'zeile-name', text: T('ag_auto') + ' ' + T(S.z.autoFreigabe ? 'ag_auto_an' : 'ag_auto_aus') }),
      S.sym(S.z.autoFreigabe ? 'haken' : 'pfeilR', 12)
    ]);
    const fuss = el('div', { class: 'seite-fuss' }, [
      auto, feld,
      el('div', { class: 'knopf-reihe', style: 'margin-top:6px;justify-content:space-between' }, [
        el('span', { class: 'umschalter', role: 'group', 'aria-label': T('ag_modus') }, [modus('plan'), modus('act')]),
        S.symKnopf('senden', T('ch_senden'), ab, { data: { fid: 'ag:senden' } })
      ])
    ]);

    const inhalt = el('div', { class: 'seite-inhalt' }, [
      el('div', { class: 'agent-kopf' }, [S.sym('agent', 44), el('span', { text: T('ag_frage') }),
        S.z.beispiel ? el('span', { class: 'beispiel-marke', text: T('beispiel') }) : null]),
      S.abschnitt('abs:agenten', T('ag_liste'), agenten, el('span', { class: 'zahl', text: String(S.z.beispiel ? S.AGENTEN.length : 0) })),
      S.abschnitt('abs:letzte', T('ag_letzte'), letzte)
    ]);
    return { titel: T('an_agenten'), inhalt: inhalt, fuss: fuss };
  };
})(window);
