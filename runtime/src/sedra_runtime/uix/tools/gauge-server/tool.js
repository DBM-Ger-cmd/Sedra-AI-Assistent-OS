// Instrument „Modellserver“ (kind: instrument) – eine Datenzelle der Taskleiste von One Sedra (SPEC_APPS_v1_AM1). Die Shell holt /api/strip und zeichnet die Zelle
// selbst (taskleiste.js, Beschriftung und Klick aus der `zelle` im Manifest); dieses Skript meldet das Instrument nur an und formt eine Lesung. Läuft der Modellserver, und welches Modell trägt er.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'gauge-server',
    field: 'server',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      this.body = d().el('div');
      el.append(this.body);
      this.update(null, null);
    },

    unmount(){ this.el.replaceChildren(); this.el.classList.remove('ok', 'warn', 'bad'); this.el.title = ''; },

    update(reading, problem){
      const cell = (reading || {})[this.field] || null;
      this.el.classList.remove('ok', 'warn', 'bad');
      if(cell && cell.tone && cell.tone !== 'off') this.el.classList.add(cell.tone);
      this.body.replaceChildren(
        d().el('small', null, 'Modellserver'),
        d().el('b', null, problem ? '–' : (cell ? String(cell.value) : '…'))
      );
      this.el.title = problem || (cell ? 'Modellserver: ' + cell.value + ' · ' + (cell.hint || '') : 'Modellserver');
    },

    summary(){ return {label: 'Modellserver', value: null, tone: 'off', hint: 'Läuft der Modellserver, und welches Modell trägt er.'}; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
