// Werkzeug „Besatzung“ – who is on board: the Captain, SEDRA, the roles from the recipes, and the agents that really exist.
// Demo rows and real rows are never mixed (the Build-5 rule): what the agent manager has not created is named as a role, not an agent.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // roles out of the routing recipes: 'coder.local_primary' -> Coder (pure)
  function rolesFromRecipes(recipes){
    const byRole = new Map();
    (recipes || []).forEach(r=>{
      (r.roles || []).forEach(role=>{
        const name = String(role).replace(/[._-]/g, ' ').trim();
        const label = name.charAt(0).toUpperCase() + name.slice(1);
        if(!byRole.has(label)) byRole.set(label, []);
        byRole.get(label).push({recipe: r.id, loaded: !!r.loaded, enabled: !!r.enabled});
      });
    });
    return [...byRole.entries()].map(([role, recipes])=>({role, recipes})).sort((a, b)=>a.role.localeCompare(b.role));
  }

  const tool = {
    id: 'crew',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-crew');
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-crew'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      const [agents, models] = await Promise.all([this.ctx.api('/api/agents').catch(e=>({error: e.message})), this.ctx.api('/api/models').catch(()=>({}))]);
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note', 'Der Captain entscheidet, SEDRA plant und baut. Darunter stehen die Rollen – jede Rolle ist ein Rezept, kein eigener Prozess.'));
      if(agents.error){ box.append(d().el('div', 's-note bad', 'Besatzung nicht lesbar: ' + agents.error)); this.el.replaceChildren(box); return; }

      const instances = agents.instances || [], assignments = agents.assignments || [];
      box.append(d().el('h5', 's-head', 'Rollen'));
      rolesFromRecipes(models.recipes).forEach(r=>{
        const row = d().el('div', 't-crew-row');
        row.append(d().el('b', null, r.role));
        row.append(d().el('small', 's-muted', r.recipes.map(x=>x.recipe + (x.loaded ? ' (geladen)' : x.enabled ? '' : ' (aus)')).join(' · ')));
        box.append(row);
      });

      box.append(d().el('h5', 's-head', 'Agenten · ' + instances.length));
      if(agents.demo) box.append(d().el('div', 's-note warn', 'Noch keine Agenten-Datenbank auf diesem PC: was hier steht, sind Vorlagen, keine laufenden Agenten.'));
      if(!instances.length) box.append(d().empty('Keine Agenten an Bord. Eine Instanz entsteht nur über eine Freigabe.'));
      instances.forEach(a=>{
        const row = d().el('div', 't-crew-row');
        row.append(d().el('b', null, a.name || a.agent_id || a.id), d().el('small', 's-muted', a.state || a.status || ''));
        box.append(row);
      });
      const running = assignments.filter(a=>a.state === 'running');
      if(running.length) box.append(d().el('small', 's-muted', running.length + ' Zuweisung' + (running.length === 1 ? '' : 'en') + ' läuft gerade.'));
      this.el.replaceChildren(box);
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraCrewPure = {rolesFromRecipes};
  if(typeof module !== 'undefined' && module.exports) module.exports = {rolesFromRecipes};
})();
