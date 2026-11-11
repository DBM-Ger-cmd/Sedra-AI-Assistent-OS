// Werkzeug „Translator“ (A3): Platzhalter für den Objekttyp `translator`.
//
// In One Sedra (Shell `harness`) zeichnet die Shell die App selbst – Wolke, vier Modus-Reiter, Zustand je Modus (`shells/harness/translator.js`) – und lässt diese
// Fläche leer. In jeder anderen Shell steht hier ein Satz und vier Knöpfe, die die vier Werkzeuge einzeln öffnen: nichts geht verloren, nichts wird nachgebaut.
// Es ruft keine Route, hat keinen Speicher und öffnet nur über `ctx.shell.open`.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const MODI = [
    ['Übersetzen', {type: 'uebersetzung', id: 'wolke', title: 'Übersetzen'}],
    ['News', {type: 'nachrichten', id: 'brief', title: 'Nachrichten'}],
    ['Aufnahme', {type: 'aufnahme', id: 'rekorder', title: 'Rekorder'}],
    ['Transkript', {type: 'transkript', id: 'alle', title: 'Transkripte'}]
  ];

  const tool = {
    id: 'translator',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-translator');
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note', 'Der Translator ist eine App von One Sedra – dort mit Wolke und vier Modi in einem Reiter. Hier öffnest du die vier Werkzeuge einzeln.'));
      const zeile = d().el('div', 's-row');
      MODI.forEach(([label, objekt])=>zeile.append(d().button(label, ()=>ctx.shell.open(Object.assign({}, objekt)))));
      box.append(zeile);
      el.replaceChildren(box);
    },

    unmount(){ this.el.classList.remove('t-translator'); this.el.replaceChildren(); },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraTranslatorPure = {MODI};
  if(typeof module !== 'undefined' && module.exports) module.exports = {MODI};
})();
