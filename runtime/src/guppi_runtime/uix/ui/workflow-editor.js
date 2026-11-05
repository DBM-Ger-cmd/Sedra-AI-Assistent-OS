(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const M = ()=>root.sedraWorkflowModel;
  const P = ()=>root.sedraWorkflowProcess;
  const PV = ()=>root.sedraWorkflowProcessView;
  function el(tag, cls, text){const x = document.createElement(tag);if(cls)x.className = cls;if(text !== undefined)x.textContent = text;return x;}
  function button(text, fn){const b = el('button', '', text);b.type = 'button';b.onclick = fn;return b;}
  function controller(options){return {
    id: options.id,
    mount(container, ctx){
      this.el = container; this.ctx = ctx; this.dead = false; this.history = []; this.future = []; this.off = [];
      this.state = {doc: M().example(), selected: null}; this.wid = null; this.revision = null; this.saved = null; this.records = [];this.view = 'canvas';this.style = options.style;
      this.el.classList.add('t-workflow', options.className); this.build(); this.draw();
      this.busy = true;this.el.inert = true;this.el.setAttribute('aria-busy', 'true');
      this.off.push(ctx.bus.on('task.changed', ()=>this.refreshRuns()));
      this.off.push(ctx.bus.on('decision.answered', ()=>this.refreshRuns()));
      return this.refresh().then(()=>{
        if(ctx.object && ctx.object.type === options.objectType && ctx.object.id !== 'alle') return this.load(ctx.object.id, true);
        if(ctx.object && ctx.object.type === 'workflow_run') return this.showRun(ctx.object.id);
      }).finally(()=>{this.busy = false;if(!this.dead){this.el.inert = false;this.el.removeAttribute('aria-busy');}});
    },
    unmount(){this.dead = true;this.off.forEach(fn=>fn());if(this.canvas)this.canvas.destroy();this.el.replaceChildren();this.el.classList.remove('t-workflow', options.className);},
    shown(){if(this.wid && !this.dirty())this.safe(()=>this.load(this.wid, true));},
    async call(type, id, verb, args){
      const out = await this.ctx.api('/api/actions', {method: 'POST', body: {type, id, verb, args: args || {}}}); return out.result;
    },
    async safe(fn){
      if(this.busy) return;
      this.busy = true; this.el.setAttribute('aria-busy', 'true');
      try{await fn();}catch(error){if(!this.dead)this.notice(error.message, true);}
      finally{this.busy = false;if(!this.dead)this.el.removeAttribute('aria-busy');}
    },
    notice(text, bad){this.message.textContent = text;this.message.classList.toggle('bad', !!bad);},
    checkpoint(){this.history.push(M().clone(this.state.doc));if(this.history.length > 50)this.history.shift();this.future = [];},
    change(fn){this.checkpoint();fn();this.draw();},
    build(){
      const head = el('div', 't-wf-header');head.append(el('h2', '', options.title), el('span', 't-wf-badge', 'Gemeinsamer Prozessbestand · 0.2'));
      this.message = el('p', 't-wf-message', 'Prozess zeichnen oder eine n8n-JSON-Datei importieren.');this.message.setAttribute('role', 'status');
      this.engine = el('p', 't-wf-hint');
      const bar = el('div', 't-wf-toolbar');
      this.file = el('input');this.file.type = 'file';this.file.accept = '.json,application/json';this.file.hidden = true;
      this.file.onchange = ()=>this.safe(async()=>{
        const f = this.file.files[0]; if(!f)return;if(f.size > 1000000)throw new Error('Datei ist größer als 1 MB.');
        if(!this.discard())return;
        const checked = await this.call('workflow', null, 'pruefen', {text: await f.text()});
        if(this.importRevision){
          this.change(()=>{this.state.doc = M().clone(checked.workflow);this.state.selected = null;});
          this.changeNote.value = 'Überarbeitete Prozessdatei als neue Version importiert';this.notice('Als Entwurf zur aktuellen Version importiert. Speichern erzeugt eine neue Revision.');
        }else{
          this.adopt(checked.workflow, null, null);this.notice('Importiert. Unbekannte Felder und Knoten bleiben erhalten.');
        }
        this.file.value = '';this.importRevision = false;
      });
      bar.append(button('Beispiel', ()=>{if(this.discard())this.adopt(M().example(), null, null);}),
        button('Importieren', ()=>{this.importRevision = false;this.file.click();}),
        button('Als neue Version importieren', ()=>{if(!this.wid){this.notice('Zuerst die Ausgangsfassung speichern oder laden.', true);return;}this.importRevision = true;this.file.click();}),
        button('Speichern', ()=>this.safe(()=>this.save())),
        button('Exportieren', ()=>this.export(false)), button('Bereinigter Export', ()=>this.export(true)),
        button('Prüfen', ()=>this.safe(()=>this.check())), button('Zurück', ()=>this.undo(false)), button('Wiederholen', ()=>this.undo(true)));
      this.picker = el('select');this.picker.setAttribute('aria-label', 'Gespeicherte Workflows');
      this.picker.onchange = ()=>{if(this.picker.value)this.safe(()=>this.load(this.picker.value));};bar.append(this.picker);
      const titleRow = el('div', 't-wf-toolbar');this.title = el('input');this.title.setAttribute('aria-label', 'Workflow-Titel');
      this.title.onchange = ()=>this.change(()=>{this.state.doc.name = this.title.value;});
      this.version = el('span', 't-wf-hint'); titleRow.append(this.title, this.version);
      const versionRow = el('div', 't-wf-toolbar');this.changeNote = el('input');this.changeNote.maxLength = 500;this.changeNote.placeholder = 'Was wurde geändert?';this.changeNote.setAttribute('aria-label', 'Änderungsgrund');versionRow.append(el('label', '', 'Änderungsgrund'), this.changeNote);
      const history = el('details', 't-wf-history');history.append(el('summary', '', 'Versionshistorie und Vergleich'));this.historyBox = el('div');history.append(this.historyBox);
      const views = el('div', 't-wf-toolbar');
      this.viewSelect = el('select');this.viewSelect.setAttribute('aria-label', 'Prozessansicht');
      [['canvas', 'Gesamtprozess'], ['core', 'Kernschritte · verdichtet'], ['sipoc', 'SIPOC'], ['details', 'Alle Schritte / Prüfpunkte']].forEach(([k, v])=>this.viewSelect.append(new Option(v, k)));
      this.viewSelect.onchange = ()=>{this.view = this.viewSelect.value;this.draw();};
      views.append(this.viewSelect, button('In ' + options.otherTitle + ' öffnen', ()=>{
        if(this.dirty()){this.notice('Für den Wechsel zuerst speichern. Beide Apps teilen gespeicherte Versionen.', true);return;}
        this.ctx.shell.open({type: options.otherType, id: this.wid || 'alle', title: options.otherTitle});
      }));
      this.processBanner = el('p', 't-wf-process-banner');
      const palette = el('div', 't-wf-toolbar');this.palette = palette;
      (options.palette || M().types.map(([kind, label])=>({kind, label}))).forEach(item=>palette.append(button('+ ' + item.label, ()=>this.change(()=>{
        const n = item.make ? item.make(this.state.doc.nodes) : M().node(item.kind, this.state.doc.nodes);this.state.doc.nodes.push(n);this.state.selected = n.id;this.view = 'canvas';
      }))));
      palette.append(button('Vergrößern', ()=>{if(this.canvas)this.canvas.zoom(1.2);}), button('Verkleinern', ()=>{if(this.canvas)this.canvas.zoom(1 / 1.2);}),
        button('Einpassen', ()=>{if(this.canvas)this.canvas.fit();}), button('Zur Auswahl', ()=>{if(this.canvas)this.canvas.focus();}));
      const grid = el('div', 't-wf-grid');this.surface = el('section', 't-wf-surface');this.inspector = el('aside', 't-wf-inspector');grid.append(this.surface, this.inspector);
      this.report = el('pre', 't-wf-report');this.report.setAttribute('aria-label', 'Kompatibilitätsbericht');
      const run = el('section', 't-wf-run');this.runSection = run;run.append(el('h3', '', options.runTitle || 'Ausführungen'));
      this.input = el('textarea');this.input.value = '{}';this.input.setAttribute('aria-label', 'Laufeingaben als JSON');this.input.rows = 3;
      run.append(el('p', 't-wf-hint', 'Nur geprüfte Datenknoten. Zugangsdaten werden in der lokalen n8n-Testinstanz eingerichtet. Eine Freigabe ist immer erforderlich.'), this.input,
        button('Lauf zur Freigabe vorlegen', ()=>this.safe(async()=>{
          if(!this.wid || this.dirty())throw new Error('Workflow zuerst speichern.');
          const out = await this.call('workflow', this.wid, 'starten', {revision: this.revision, inputs: JSON.parse(this.input.value)});
          this.runId = out.id;await this.showRun(out.id);this.notice('Mission angelegt. Freigabe im Posteingang prüfen, dann hier fortsetzen.');
        })), button('Posteingang öffnen', ()=>this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Freigaben'})),
        button('Nach Freigabe fortsetzen', ()=>this.safe(async()=>{if(!this.runId)throw new Error('Zuerst einen Lauf wählen.');await this.call('workflow_run', this.runId, 'fortsetzen');await this.showRun(this.runId);})),
        button('Lauf beenden', ()=>this.safe(async()=>{if(!this.runId)throw new Error('Zuerst einen Lauf wählen.');await this.call('workflow_run', this.runId, 'abbrechen');await this.showRun(this.runId);})),
        button('Aktualisieren', ()=>this.safe(()=>this.refreshRuns())));
      this.runs = el('div', 't-wf-runs');this.output = el(options.renderRun ? 'div' : 'pre', 't-wf-output');this.output.setAttribute('aria-label', 'Laufergebnis');run.append(this.runs, this.output);
      this.el.replaceChildren(head, this.engine, bar, titleRow, versionRow, history, views, this.processBanner, palette, this.file, this.message, grid, this.report, run);
      this.el.addEventListener('keydown', event=>{
        if((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z' && !['INPUT', 'TEXTAREA'].includes(event.target.tagName)){
          event.preventDefault();this.undo(event.shiftKey);
        }
      });
    },
    dirty(){return JSON.stringify(this.state.doc) !== this.saved;},
    discard(){return !this.dirty() || root.confirm('Nicht gespeicherte Änderungen verwerfen?');},
    adopt(doc, id, revision){
      this.state.doc = M().clone(doc);this.state.selected = null;this.wid = id;this.revision = revision;
      this.saved = id ? JSON.stringify(doc) : null;this.history = [];this.future = [];this.revisions = [];this.report.textContent = '';
      this.view = P().cores(doc).length > 1 ? 'core' : 'canvas';this.changeNote.value = id ? '' : 'Erstfassung';this.draw();if(!id)PV().history(this.historyBox, [], null, null);
    },
    undo(redo){
      const from = redo ? this.future : this.history, to = redo ? this.history : this.future;
      if(!from.length)return;to.push(M().clone(this.state.doc));this.state.doc = from.pop();this.draw();
    },
    draw(){
      if(this.dead)return;this.title.value = this.state.doc.name;
      const model = P().has(this.state.doc), core = this.view === 'core';
      this.viewSelect.value = this.view;
      this.runSection.hidden = model;this.processBanner.hidden = !model;
      this.engine.hidden = model;this.palette.hidden = model && core;this.report.hidden = model;
      this.processBanner.textContent = 'Prozessmodell · ' + P().cores(this.state.doc).length + ' Kernschritte · ' + P().rows(this.state.doc).filter(r=>r.meta.source === 'proposal').length + ' ergänzte Vorschläge. Fachliche und technische Ausführung sind noch nicht eingerichtet.';
      this.version.textContent = (this.wid ? 'Revision ' + this.revision : 'Neuer Entwurf') + (this.dirty() ? ' · ungespeichert' : ' · gespeichert');
      if(this.canvas)this.canvas.destroy();
      this.canvas = null;
      if(['sipoc', 'details'].includes(this.view)){
        PV().render(this.surface, this.state.doc, this.view, id=>{this.state.selected = id;this.inspect();});this.inspect();return;
      }
      const visual = core ? {doc: P().coreProjection(this.state.doc), selected: this.state.selected} : this.state;
      this.canvas = root.sedraWorkflowCanvas.mount(this.surface, visual, {
        style: this.style, readOnly: core,
        select: id=>{this.state.selected = id;this.inspect();}, checkpoint: ()=>this.checkpoint(),
        change: ()=>{this.version.textContent = 'Ungespeicherte Änderungen';this.inspect();},
        connect: (a, b, branch)=>{try{this.change(()=>M().connect(this.state.doc, a, b, branch));}catch(e){this.notice(e.message, true);}}
      });this.inspect();
    },
    inspect(){
      const box = this.inspector;box.replaceChildren(el('h3', '', 'Eigenschaften'));
      box.hidden = this.view !== 'canvas' && !this.state.selected;
      if(this.wid && this.revisions && this.revisions.length){
        const versions = el('select');versions.setAttribute('aria-label', 'Frühere Revision');
        this.revisions.forEach(r=>versions.append(new Option('Revision ' + r, String(r))));versions.value = String(this.revision);
        box.append(versions, button('Revision als Entwurf laden', ()=>this.safe(async()=>{
          if(!this.discard())return;
          const previous = await this.call('workflow', null, 'revision_lesen', {id: this.wid, revision: Number(versions.value)});
          this.change(()=>{this.state.doc = M().clone(previous.workflow);this.state.selected = null;});this.changeNote.value = 'Revision ' + previous.revision + ' als neuen Entwurf übernommen';
          this.notice('Frühere Fassung als Entwurf geladen. Speichern legt eine neue Revision an.');
        })));
      }
      const select = el('select');select.setAttribute('aria-label', 'Knoten auswählen');select.append(new Option('Knoten wählen', ''));
      this.state.doc.nodes.forEach(n=>select.append(new Option(n.name, n.id)));select.value = this.state.selected || '';
      select.onchange = ()=>{this.state.selected = select.value;this.draw();};box.append(select);
      const node = this.state.doc.nodes.find(n=>n.id === this.state.selected);
      if(node){
        const name = el('input');name.value = node.name;name.setAttribute('aria-label', 'Knotenname');
        const params = el('textarea');params.rows = 12;params.value = JSON.stringify(node.parameters, null, 2);params.setAttribute('aria-label', 'Knotenparameter als JSON');
        PV().editor(box, node, values=>this.change(()=>P().set(node, values)));
        if(options.inspector){
          options.inspector(box, node, fn=>this.change(fn), message=>this.notice(message, true));
          const moduleName = el('input');moduleName.value = node.name;moduleName.setAttribute('aria-label', 'Modulname');
          box.append(moduleName, button('Modulname übernehmen', ()=>{try{this.change(()=>M().rename(this.state.doc, node.name, moduleName.value));}catch(e){this.notice(e.message, true);}}),
            button('Modul entfernen', ()=>this.change(()=>{M().remove(this.state.doc, node.name);this.state.selected = null;})),
            button('Im Gesamtprozess zeigen', ()=>{this.view = 'canvas';this.draw();this.canvas.focus();}));
        }else{
        const technical = el('details');technical.append(el('summary', '', 'Technische n8n-Eigenschaften'));technical.open = !P().get(node);
        technical.append(el('p', 't-wf-hint', node.type + ' · v' + node.typeVersion), name, params,
          button('Parameter übernehmen', ()=>{try{
            const value = JSON.parse(params.value);if(!value || Array.isArray(value) || typeof value !== 'object')throw new Error('Parameter müssen ein JSON-Objekt sein.');
            this.change(()=>{M().rename(this.state.doc, node.name, name.value);node.parameters = value;});
          }catch(e){this.notice(e.message, true);}}),
          button('Knoten entfernen', ()=>this.change(()=>{M().remove(this.state.doc, node.name);this.state.selected = null;})));
        box.append(technical, button('Im Gesamtprozess zeigen', ()=>{this.view = 'canvas';this.draw();this.canvas.focus();}));
        }
      }
      if(this.view !== 'canvas')return;
      box.append(el('h3', '', options.routeTitle || 'Verbindungen'));
      const from = el('select'), to = el('select'), branch = el('select');
      from.setAttribute('aria-label', 'Quelle');to.setAttribute('aria-label', 'Ziel');branch.setAttribute('aria-label', 'Ausgang');
      this.state.doc.nodes.forEach(n=>{from.append(new Option(n.name, n.name));to.append(new Option(n.name, n.name));});
      branch.append(new Option('0 / Ja', '0'), new Option('1 / Nein', '1'));
      box.append(from, branch, to, button('Verbinden', ()=>{try{this.change(()=>M().connect(this.state.doc, from.value, to.value, Number(branch.value)));}catch(e){this.notice(e.message, true);}}));
      const edges = el('select');edges.setAttribute('aria-label', 'Verbindung entfernen');const edgeChoices = [];
      Object.entries(this.state.doc.connections).forEach(([source, out])=>Object.entries(out).forEach(([kind, branches])=>branches.forEach((b, bi)=>b.forEach((e, ei)=>{
        edgeChoices.push([source, kind, bi, ei]);edges.append(new Option(source + ' → ' + e.node + ' · ' + kind + ':' + bi, String(edgeChoices.length - 1)));
      }))));
      box.append(edges, button('Verbindung entfernen', ()=>{if(edges.value === '')return;const [s, k, b, e] = edgeChoices[Number(edges.value)];this.change(()=>this.state.doc.connections[s][k][b].splice(e, 1));}));
    },
    async refresh(){
      const data = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'workflow', id: 'alle'}});
      if(this.dead)return;this.records = data.items || [];this.picker.replaceChildren(new Option('Gespeicherten Workflow wählen', ''));
      this.records.forEach(r=>this.picker.append(new Option(r.title + ' · r' + r.revision, r.id)));this.picker.value = this.wid || '';
      this.engine.textContent = data.engine.enabled ? 'Lokale n8n-Verbindung konfiguriert: ' + data.engine.base_url : 'n8n-Ausführung aus. Import, Editor, Versionen und Export sind verfügbar.';
      this.renderRuns(data.runs || []);
      await this.loadHistory();
    },
    async load(id, initial){
      if(!initial && !this.discard())return;
      const record = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'workflow', id}});
      if(this.dead)return;this.adopt(record.workflow, record.id, record.revision);this.revisions = record.revisions || [];this.inspect();this.showCheck(record.compatibility, record.execution);
      this.picker.value = record.id;
      await this.loadHistory();
      this.notice('Revision ' + record.revision + ' geladen. Gemeinsamer Prozessbestand.');
    },
    async save(){
      const snapshot = M().clone(this.state.doc), base = this.revision;
      const record = await this.call('workflow', this.wid, this.wid ? 'speichern' : 'importieren', {workflow: snapshot, base_revision: base, change_note: this.changeNote.value.trim() || undefined});
      if(this.dead)return;this.wid = record.id;this.revision = record.revision;this.revisions = record.revisions || [];this.saved = JSON.stringify(snapshot);
      await this.refresh();this.draw();this.showCheck(record.compatibility, record.execution);this.notice('Revision ' + record.revision + ' gespeichert.');
      this.changeNote.value = '';
    },
    async check(){const checked = await this.call('workflow', null, 'pruefen', {workflow: this.state.doc});if(!this.dead)this.showCheck(checked, checked.execution);},
    showCheck(info, execution){
      const reason = execution.reason === 'process_model_requires_implementation' ? 'Prozessmodell: menschliche Schritte und Freigaben müssen erst angebunden werden.' : execution.reason;
      this.report.textContent = (execution.executable ? 'Ausführungsprofil erfüllt. Captain-Freigabe bleibt erforderlich.' : 'Nur Austausch / Modellierung: ' + reason) + '\n' + (info.warnings || []).join('\n');
    },
    async loadHistory(){
      if(!this.wid){PV().history(this.historyBox, [], null, null);return;}
      const id = this.wid, result = await this.call('workflow', null, 'versionen', {id});if(this.dead || id !== this.wid)return;
      PV().history(this.historyBox, result.versions, (a, b, box)=>this.safe(async()=>{
        const out = await this.call('workflow', null, 'vergleichen', {id, from_revision: a, to_revision: b});PV().diff(box, out.changes);
      }), rev=>this.safe(async()=>{
        if(!this.discard())return;const previous = await this.call('workflow', null, 'revision_lesen', {id, revision: rev});
        this.change(()=>{this.state.doc = M().clone(previous.workflow);this.state.selected = null;});this.changeNote.value = 'Revision ' + rev + ' als neuen Entwurf übernommen';
      }));
    },
    export(clean){
      if(!clean && !root.confirm('Originalexport kann Zugangsdaten-Referenzen und geheime Werte enthalten. Nur an berechtigte Empfänger weitergeben. Exportieren?'))return;
      const value = clean ? M().sharing(this.state.doc) : this.state.doc;
      const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type: 'application/json'}));
      const link = el('a');link.href = url;link.download = 'sedra-workflow' + (clean ? '-bereinigt' : '') + '.json';this.el.append(link);link.click();link.remove();URL.revokeObjectURL(url);
      this.notice(clean ? 'Bereinigter Export: freie Texte vor Weitergabe zusätzlich prüfen; entfernte Werte müssen in n8n neu eingerichtet werden.' : 'n8n-JSON exportiert.');
    },
    renderRuns(runs){this.runs.replaceChildren();runs.slice().reverse().forEach(run=>this.runs.append(button(run.title + ' · ' + run.state, ()=>this.safe(()=>this.showRun(run.id)))));},
    async refreshRuns(){
      if(this.dead)return;
      try{const data = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'workflow_run'}});if(!this.dead)this.renderRuns(data.items || []);if(this.runId)await this.showRun(this.runId);}catch(e){if(!this.dead)this.notice(e.message, true);}
    },
    async showRun(id){
      const run = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'workflow_run', id}});
      if(this.dead)return;this.runId = id;
      if(options.renderRun)options.renderRun(this.output, run);
      else this.output.textContent = JSON.stringify({mission: id, revision: run.revision, phase: run.state, steps: run.steps, wait: run.wait, result: run.result, artifacts: run.artifacts}, null, 2);
    }
  };}
  function create(options){
    const instances = new WeakMap();
    return {id: options.id,
      mount(el, ctx){const instance = controller(options);instances.set(el, instance);return instance.mount(el, ctx);},
      unmount(el){const instance = instances.get(el);if(instance){instance.unmount();instances.delete(el);}},
      shown(el){const instance = instances.get(el);if(instance)instance.shown();},
      actions(){return [];}};
  }
  root.sedraWorkflowEditor = {create};
})();
