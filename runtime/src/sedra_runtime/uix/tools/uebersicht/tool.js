// Werkzeug „Übersicht“ (A3): Platzhalter für den Objekttyp `uebersicht`.
//
// In One Sedra (Shell `harness`) zeichnet die Shell die App selbst – den Baum der Gesamtlage (`shells/harness/uebersicht.js`) – und lässt diese Fläche leer.
// In jeder anderen Shell steht hier ein Satz: nichts wird nachgebaut. Es ruft keine Route, hat keinen Speicher und öffnet nichts.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'uebersicht',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-uebersicht');
      el.replaceChildren(d().el('div', 's-note', 'Die Übersicht ist eine App von One Sedra – dort mit allen Apps nach Gruppen und ihrem Zustand. Hier gibt es den Baum links in der Shell „cockpit“.'));
    },

    unmount(){ this.el.classList.remove('t-uebersicht'); this.el.replaceChildren(); },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  if(typeof module !== 'undefined' && module.exports) module.exports = {};
})();
