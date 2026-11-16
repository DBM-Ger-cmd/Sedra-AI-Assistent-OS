// Werkzeug „Workflow Studio“: Platzhalter für den Objekttyp `workflow-studio`.
//
// In One Sedra (Shell `harness`) zeichnet die Shell die App selbst (shells/harness/workflow_studio.js) und lässt diese Fläche leer.
// In jeder anderen Shell steht hier ein Satz mit Hinweis auf die App. Es ruft keine Route, hat keinen Speicher.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'workflow-studio',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-workflow-studio');
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note', 'Das Workflow Studio ist eine App von One Sedra – n8n Workflows, Szenario Studio, Factory, Live und Freigaben in der Harness-Shell.'));
      el.replaceChildren(box);
    },

    unmount(){ this.el.classList.remove('t-workflow-studio'); this.el.replaceChildren(); },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraWorkflowStudioPure = {};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraWorkflowStudioPure;
})();
