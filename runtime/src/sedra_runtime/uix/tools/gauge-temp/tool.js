// Instrument „Temperatur“ (kind: instrument) – eine Datenzelle der Taskleiste von One Sedra (SPEC_APPS_v1_AM1). Die Shell holt /api/strip und zeichnet die Zelle
// selbst (taskleiste.js, Beschriftung und Klick aus der `zelle` im Manifest); dieses Skript meldet das Instrument nur an und formt eine Lesung. Temperatur der Grafikkarte (aus dem Wert gpu abgeleitet).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'gauge-temp',
    field: 'temp',

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
        d().el('small', null, 'Temp'),
        d().el('b', null, problem ? '–' : (cell ? String(cell.value) : '…'))
      );
      this.el.title = problem || (cell ? 'Temp: ' + cell.value + ' · ' + (cell.hint || '') : 'Temp');
    },

    summary(){ return {label: 'Temp', value: null, tone: 'off', hint: 'Temperatur der Grafikkarte (aus dem Wert gpu abgeleitet).'}; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
