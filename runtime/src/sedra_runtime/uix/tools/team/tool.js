// Werkzeug „Team“ (A3): Platzhalter für den Objekttyp `team`.
//
// In One Sedra (Shell `harness`) zeichnet die Shell die App selbst – Modus-Reiter und der Überblick aus mehreren Werkzeugen (`shells/harness/team.js`) – und lässt diese
// Fläche leer. In jeder anderen Shell steht hier ein Satz und je ein Knopf, der das Werkzeug einzeln öffnet: nichts geht verloren, nichts wird nachgebaut.
// Es ruft keine Route, hat keinen Speicher und öffnet nur über `ctx.shell.open`.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const MODI = [
    ['Posteingang', {type: 'decision', id: 'alle', title: 'Posteingang', collection: true}],
    ['Issues', {type: 'issue', id: 'alle', title: 'Issues', collection: true}],
    ['Vorhaben', {type: 'intent', id: 'alle', title: 'Vorhaben', collection: true}],
    ['Organigramm', {type: 'agent', id: 'alle', title: 'Organigramm', collection: true}],
    ['Routinen', {type: 'routine', id: 'alle', title: 'Routinen', collection: true}],
    ['Kosten', {type: 'meter', id: 'meter', title: 'Sedra Token'}]
  ];

  const tool = {
    id: 'team',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-team');
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note', 'Das Team ist eine App von One Sedra – dort mit Überblick und Modi in einem Reiter. Hier öffnest du die Werkzeuge einzeln.'));
      const zeile = d().el('div', 's-row');
      MODI.forEach(([label, objekt])=>zeile.append(d().button(label, ()=>ctx.shell.open(Object.assign({}, objekt)))));
      box.append(zeile);
      el.replaceChildren(box);
    },

    unmount(){ this.el.classList.remove('t-team'); this.el.replaceChildren(); },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraTeamPure = {MODI};
  if(typeof module !== 'undefined' && module.exports) module.exports = {MODI};
})();
