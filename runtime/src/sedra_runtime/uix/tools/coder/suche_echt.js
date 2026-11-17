/* Sedra IDE: Suche im ganzen Projekt (Server, nur lesen) und Ersetzen im Editor. Gesperrte Dateien, Binärdateien und große Dateien erscheinen nicht.
   „Ersetzen“ ändert nur den Text im Editor (ungespeichert); auf die Platte kommt er erst über Speichern, also über den Antrag an die Freigaben. */
(function (root) {
  'use strict';
  const S = root.SIDE, el = S.el, T = S.T;
  const API = ['', 'api', 'uix', 'coder', 'suche', ''].join('/');      /* zusammengesetzt, siehe echt.js */
  const urspruenglich = S.ansichten.suche;
  const WARTE_MS = 300;
  let ersetzText = '';
  let zaehler = 0, timer = null;

  function maskiere(t) { return t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  S.sucheEcht = async function (frage, liste, kopf) {
    const nr = ++zaehler;
    S.leere(liste);
    if (!frage.trim()) { kopf.textContent = ''; liste.appendChild(el('div', { class: 'leer', text: T('su_hinweis_echt') })); return; }
    kopf.textContent = T('su_laeuft');
    let r;
    try { r = await S.ctx.api(API + encodeURIComponent(S.echt.projekt.id) + '/' + encodeURIComponent(frage)); }
    catch (e) { if (nr === zaehler) kopf.textContent = T('su_fehler'); return; }
    if (nr !== zaehler) return;                                      /* eine neuere Eingabe ist schon unterwegs */
    S.leere(liste);
    kopf.textContent = r.anzahl ? T('su_anzahl', r.anzahl) + (r.gekuerzt ? ' ' + T('su_gekuerzt') : '') : '';
    if (!r.anzahl) { liste.appendChild(el('div', { class: 'leer', text: T('su_nichts', frage) })); return; }
    const gruppen = {};
    r.treffer.forEach(function (t) { (gruppen[t.pfad] = gruppen[t.pfad] || []).push(t); });
    Object.keys(gruppen).forEach(function (pfad) {
      liste.appendChild(el('div', { class: 'su-datei', role: 'listitem' }, [
        S.sym('datei', 14), el('span', { class: 'zeile-name', text: pfad }), el('span', { class: 'zahl', text: String(gruppen[pfad].length) }),
        el('button', { class: 'knopf', type: 'button', data: { fid: 'su:ers:' + pfad }, title: T('su_ersetzen_datei', pfad),
          on: { click: function () { S.ersetzeInDatei(pfad, frage); } } }, [T('su_ersetzen')])
      ]));
      gruppen[pfad].forEach(function (t) {
        liste.appendChild(el('div', {
          class: 'listen-zeile', role: 'listitem', tabindex: '0', title: pfad + ':' + t.zeile, data: { fid: 'su:' + pfad + ':' + t.zeile },
          on: {
            click: async function () { await S.oeffneDatei(pfad); S.editor.oeffneBei(pfad, t.zeile); },
            keydown: async function (ev) { if (ev.key === 'Enter') { await S.oeffneDatei(pfad); S.editor.oeffneBei(pfad, t.zeile); } }
          }
        }, [el('span', { class: 'zeile-name', text: t.text }), el('span', { class: 'zeile-neben', text: String(t.zeile) })]));
      });
    });
  };

  /* Ersetzen nur im Editor: Datei laden, alle Treffer (Groß-/Kleinschreibung egal) durch den Text ersetzen, ungespeichert lassen. */
  S.ersetzeInDatei = async function (pfad, frage) {
    if (!ersetzText) { S.sag(T('su_ersetzen_leer')); return; }
    await S.oeffneDatei(pfad);
    const d = S.dateien[pfad];
    if (!d) return;
    let n = 0;
    const neu = d.inhalt.replace(new RegExp(maskiere(frage), 'gi'), function () { n += 1; return ersetzText; });
    if (!n) { S.sag(T('su_ersetzt_nichts', d.name)); return; }
    d.inhalt = neu;
    S.melde('editor'); S.melde('inhalt', pfad); S.melde('dateien');
    S.sag(T('su_ersetzt', n, d.name));
  };

  S.ansichten.suche = function () {
    if (S.quelle !== 'echt') return urspruenglich();
    const kopf = el('div', { class: 'leer', 'aria-live': 'polite' });
    const liste = el('div', { role: 'list', 'aria-live': 'polite' });
    const feld = el('input', {
      class: 'feld', type: 'search', id: 'suchfeld', placeholder: T('su_platz'), 'aria-label': T('su_platz'), data: { fid: 'su:feld' },
      on: { input: function () {
        S.sucheText = feld.value;
        if (timer) root.clearTimeout(timer);
        timer = root.setTimeout(function () { timer = null; S.sucheEcht(S.sucheText, liste, kopf); }, WARTE_MS);
      } }
    });
    const ers = el('input', {
      class: 'feld', type: 'text', placeholder: T('su_ersetzen_platz'), 'aria-label': T('su_ersetzen_platz'), data: { fid: 'su:ersetzen' },
      on: { input: function () { ersetzText = ers.value; } }
    });
    feld.value = S.sucheText; ers.value = ersetzText;
    S.sucheEcht(S.sucheText, liste, kopf);
    return { titel: T('an_suche'), inhalt: el('div', { class: 'seite-inhalt' }, [el('div', { class: 'feld-rand' }, [feld, ers]), kopf, liste]) };
  };
})(window);
