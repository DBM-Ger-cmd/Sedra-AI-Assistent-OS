// Werkzeug „Factory Studio“ (F3-01): Platzhalter für den Objekttyp `factory-studio`.
//
// In One Sedra (Shell `harness`) zeichnet die Shell die App selbst – Project Browser und Status Dashboard (lesend) in `shells/harness/factory_studio.js` – und lässt diese
// Fläche leer. In jeder anderen Shell steht hier ein Satz mit Hinweis auf die App. Es ruft keine Route, hat keinen Speicher und öffnet nur über `ctx.shell.open`.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'factory-studio',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-factory-studio');
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note', 'Die Factory Studio App ist eine App von One Sedra – Project Browser und Status Dashboard (lesend) in der Harness-Shell.'));
      el.replaceChildren(box);
    },

    unmount(){ this.el.classList.remove('t-factory-studio'); this.el.replaceChildren(); },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraFactoryStudioPure = {};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraFactoryStudioPure;
})();
