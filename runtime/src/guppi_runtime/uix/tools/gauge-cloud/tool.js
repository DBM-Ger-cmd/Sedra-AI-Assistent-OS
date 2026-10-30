// Instrument „Online-KI“ (kind: instrument) – one cell of the Cockpit strip. It shows whether a cloud provider is ready (the strip's
// `cloud` reading) and, on a click, switches the chat between local and cloud. The chat answers with `talk.mode` what it really uses.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'gauge-cloud',
    field: 'cloud',

    mount(el, ctx){
      this.el = el; this.ctx = ctx; this.mode = 'local';
      this.body = d().el('div');
      el.append(this.body);
      d().clickable(el, ()=>{
        // ohne bereiten Anbieter gibt es keinen Cloudweg: dann bleibt es lokal, und die Zelle sagt warum
        if(!this.ready){ this.update(this.reading, this.problem); return; }
        this.mode = this.mode === 'cloud' ? 'local' : 'cloud';
        ctx.bus.emit('talk.mode', {mode: this.mode});
        this.update(this.reading, this.problem);
      });
      ctx.bus.on('talk.mode', e=>{ if(e && (e.mode === 'local' || e.mode === 'cloud')) { this.mode = e.mode; this.update(this.reading, this.problem); } });
      this.update(null, null);
    },

    unmount(){ this.el.replaceChildren(); this.el.classList.remove('ok', 'warn', 'bad'); this.el.removeAttribute('role'); this.el.removeAttribute('tabindex'); this.el.onclick = this.el.onkeydown = null; this.el.title = ''; },   // HU-T18: der Container der Shell bleibt sauber

    // what the strip hands over: the whole reading, or (reading=null, problem) when the runtime did not answer
    update(reading, problem){
      this.reading = reading; this.problem = problem;
      const cell = (reading || {})[this.field] || null;
      this.ready = !!(cell && cell.tone === 'ok');
      this.el.classList.remove('ok', 'warn', 'bad');
      if(cell && cell.tone && cell.tone !== 'off') this.el.classList.add(cell.tone);
      const modeText = this.ready ? (this.mode === 'cloud' ? 'Gespräch: Cloud' : 'Gespräch: lokal') : '';
      this.body.replaceChildren(
        d().el('small', null, 'Online-KI'),
        d().el('b', null, problem ? '–' : (cell ? String(cell.value) : '…')),
        d().el('i', null, problem ? 'nicht lesbar' : (modeText || (cell ? cell.hint || '' : '')))
      );
      this.el.title = problem || (cell ? 'Online-KI: ' + cell.value + ' · ' + (cell.hint || '') : 'Online-KI');
    },

    summary(){ return {label: 'Online-KI', value: null, tone: 'off', hint: 'Ob ein Cloud-Anbieter bereit ist.'}; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
