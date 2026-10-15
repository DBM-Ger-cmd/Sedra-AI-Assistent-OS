// Werkzeug „Kandidat“ – das Werkstück: was GUPPI an den Dateien ändern will, Zeile für Zeile (COCKPIT_MODUL_v1 §1, Regel 5).
// Der Diff wird hier gerechnet und gezeichnet, ohne Bibliothek: eine LCS-Tabelle über die Zeilen reicht für Dateien dieser Größe,
// und sie bleibt lesbar – diff2html lag nur als Vorschlag im Konzept, eine Abhängigkeit ist dafür nicht nötig.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const MAX = 2000;                 // Zeilen je Datei; darüber zeigt das Werkzeug den Einheitsdiff des Berichts

  // Die Zeilen zweier Fassungen zu einer Liste {kind:'gleich'|'raus'|'rein', a, b, text} (rein, von node geprüft).
  function diffLines(before, after){
    const A = String(before == null ? '' : before).split('\n'), B = String(after == null ? '' : after).split('\n');
    if(A.length > MAX || B.length > MAX) return null;
    // Gemeinsamer Rumpf vorne und hinten weg: der Rest ist klein genug für die Tabelle
    let head = 0;
    while(head < A.length && head < B.length && A[head] === B[head]) head++;
    let tail = 0;
    while(tail < A.length - head && tail < B.length - head && A[A.length - 1 - tail] === B[B.length - 1 - tail]) tail++;
    const a = A.slice(head, A.length - tail), b = B.slice(head, B.length - tail);
    const n = a.length, m = b.length;
    const table = Array.from({length: n + 1}, ()=>new Uint32Array(m + 1));
    for(let i = n - 1; i >= 0; i--)
      for(let j = m - 1; j >= 0; j--)
        table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    const out = [];
    for(let k = 0; k < head; k++) out.push({kind: 'gleich', a: k + 1, b: k + 1, text: A[k]});
    let i = 0, j = 0;
    while(i < n && j < m){
      if(a[i] === b[j]){ out.push({kind: 'gleich', a: head + i + 1, b: head + j + 1, text: a[i]}); i++; j++; }
      else if(table[i + 1][j] >= table[i][j + 1]){ out.push({kind: 'raus', a: head + i + 1, b: null, text: a[i]}); i++; }
      else { out.push({kind: 'rein', a: null, b: head + j + 1, text: b[j]}); j++; }
    }
    while(i < n){ out.push({kind: 'raus', a: head + i + 1, b: null, text: a[i]}); i++; }
    while(j < m){ out.push({kind: 'rein', a: null, b: head + j + 1, text: b[j]}); j++; }
    for(let k = 0; k < tail; k++) out.push({kind: 'gleich', a: A.length - tail + k + 1, b: B.length - tail + k + 1, text: A[A.length - tail + k]});
    return out;
  }

  // Lange gleiche Strecken zusammenfalten: drei Zeilen Umgebung reichen (rein)
  function collapse(rows, context){
    const keep = new Set();
    const around = context === undefined ? 3 : context;
    rows.forEach((r, i)=>{
      if(r.kind === 'gleich') return;
      for(let k = Math.max(0, i - around); k <= Math.min(rows.length - 1, i + around); k++) keep.add(k);
    });
    const out = [];
    let skipped = 0;
    rows.forEach((r, i)=>{
      if(keep.has(i)){
        if(skipped){ out.push({kind: 'luecke', text: skipped + ' unveränderte Zeile' + (skipped === 1 ? '' : 'n')}); skipped = 0; }
        out.push(r);
      }else skipped++;
    });
    if(skipped) out.push({kind: 'luecke', text: skipped + ' unveränderte Zeile' + (skipped === 1 ? '' : 'n')});
    return out;
  }

  function counts(rows){
    return {rein: rows.filter(r=>r.kind === 'rein').length, raus: rows.filter(r=>r.kind === 'raus').length};
  }

  const tool = {
    id: 'candidate',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-cand');
      this.mission = ctx.object && ctx.object.id;
      ctx.bus.on('task.changed', e=>{ if(e.id === this.mission) this.refresh(); });
      ctx.bus.on('decision.answered', ()=>this.refresh());
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-cand'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let obj, diff;
      try{
        [obj, diff] = await Promise.all([
          this.ctx.api('/api/objects', {method: 'POST', body: {type: 'candidate', id: this.mission}}),
          this.ctx.api('/api/candidate/diff', {method: 'POST', body: {mission_id: this.mission}})
        ]);
      }catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Kandidat nicht lesbar: ' + err.message)); return; }
      this.object = obj;
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note' + (obj.state === 'übernommen' ? ' ok' : obj.state === 'braucht Durchsicht' ? ' bad' : ''), obj.summary));
      (diff.files || []).forEach(f=>box.append(this.file(f)));
      if(!(diff.files || []).length && (diff.unified || []).length)
        (diff.unified || []).forEach(text=>box.append(d().el('pre', 's-pre', text)));
      this.el.replaceChildren(box);
    },

    file(f){
      const card = d().el('div', 't-cand-file');
      const rows = diffLines(f.before, f.after);
      const head = d().el('div', 't-cand-head');
      head.append(d().el('b', null, f.path));
      if(rows){
        const c = counts(rows);
        head.append(d().el('small', 't-cand-count', '+' + c.rein + ' −' + c.raus));
      }
      card.append(head);
      if(f.note) card.append(d().el('div', 's-note warn', f.note));
      if(!rows){
        card.append(d().el('div', 's-small s-muted', 'Zu groß für die Zeilenansicht – hier der Diff, wie der Bericht ihn schreibt.'));
        return card;
      }
      const table = d().el('div', 't-cand-diff');
      collapse(rows).forEach(r=>{
        if(r.kind === 'luecke'){
          table.append(d().el('div', 't-cand-gap', '⋯ ' + r.text));
          return;
        }
        const line = d().el('div', 't-cand-line ' + r.kind);
        line.append(d().el('span', 't-cand-no', r.a === null ? '' : String(r.a)));
        line.append(d().el('span', 't-cand-no', r.b === null ? '' : String(r.b)));
        line.append(d().el('span', 't-cand-sign', r.kind === 'rein' ? '+' : r.kind === 'raus' ? '−' : ' '));
        line.append(d().el('code', 't-cand-text', r.text === '' ? ' ' : r.text));
        table.append(line);
      });
      card.append(table);
      return card;
    },

    // Die Verben kommen vom Desk: welche jetzt gelten, entscheidet der Zustand des Objekts (§10.2)
    actions(){
      const obj = this.object;
      if(!obj) return [];
      return (obj.actions || []).map(a=>({label: a.label, run: async()=>{
        if(a.confirm && !confirm(a.confirm)) return;
        await this.ctx.api('/api/actions', {method: 'POST', body: {type: 'candidate', id: this.mission, verb: a.verb}});
        await this.refresh();
      }}));
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraCandidatePure = {diffLines, collapse, counts};
  if(typeof module !== 'undefined' && module.exports) module.exports = {diffLines, collapse, counts};
})();
