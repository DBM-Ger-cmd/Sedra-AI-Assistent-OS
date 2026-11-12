(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const M = ()=>root.sedraWorkflowModel;
  const P = ()=>root.sedraWorkflowProcess;
  const PV = ()=>root.sedraWorkflowProcessView;
  function el(tag, cls, text){const x = document.createElement(tag);if(cls)x.className = cls;if(text !== undefined)x.textContent = text;return x;}
  function button(text, fn){const b = el('button', '', text);b.type = 'button';b.onclick = fn;return b;}
  function controller(options){return {
    id: options.id,
    ...root.sedraWorkflowLokal(),      // Eingabedatei und lokale Tabellen des SEDRA-Eigenablaufs (workflow-lokal.js)
    ...root.sedraWorkflowSchritte(),      // geführte Schritte der Seite „Ausführungen“ (workflow-schritte.js)
    ...root.sedraWorkflowExtras(options),      // Geführtes Einrichten, Vorlagen, Selbstabbild und Schnellaktionen (workflow-extras.js)
    mount(container, ctx){
      this.el = container; this.ctx = ctx; this.dead = false; this.history = []; this.future = []; this.off = [];
      this.state = {doc: M().example(), selected: null}; this.wid = null; this.revision = null; this.saved = null; this.records = [];this.view = 'canvas';this.style = options.style;
      this.el.classList.add('t-workflow', options.className); this.build(); this.draw();
      if(root.sedraWorkflowLive)this.live = root.sedraWorkflowLive.attach(this);
      if(root.sedraWorkflowNotaus)this.notaus = root.sedraWorkflowNotaus.attach(this);      // der rote Knopf (workflow-notaus.js)
      if(root.sedraWorkflowChat)this.chat = root.sedraWorkflowChat.attach(this);      // Chat zum Prozess (workflow-chat.js)
      this.busy = true;this.el.inert = true;this.el.setAttribute('aria-busy', 'true');
      this.off.push(ctx.bus.on('task.changed', ()=>this.refreshRuns()));
      this.off.push(ctx.bus.on('decision.answered', ()=>this.refreshRuns()));
      return this.refresh().then(()=>{
        if(ctx.object && ctx.object.type === options.objectType && ctx.object.id !== 'alle') return this.load(ctx.object.id, true);
        if(ctx.object && ctx.object.type === 'workflow_run') return this.showRun(ctx.object.id);
      }).finally(()=>{this.busy = false;if(!this.dead){this.el.inert = false;this.el.removeAttribute('aria-busy');}});
    },
    unmount(){this.dead = true;this.off.forEach(fn=>fn());if(this.chat)this.chat.destroy();if(this.live)this.live.destroy();if(this.notaus)this.notaus.destroy();if(this.canvas)this.canvas.destroy();this.el.replaceChildren();this.el.classList.remove('t-workflow', options.className);this.el.removeAttribute('data-wf-theme');},
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
      this.applyTheme(this.storedTheme() || (root.document.documentElement.dataset.theme === 'klar' ? 'light' : 'dark'));
      this.themeButton = button('', ()=>{const next = this.el.dataset.wfTheme === 'light' ? 'dark' : 'light';this.applyTheme(next);try{root.localStorage.setItem('sedra.wf.theme', next);}catch(e){}});
      this.themeButton.className = 't-wf-theme';head.append(this.themeButton);this.applyTheme(this.el.dataset.wfTheme);
      this.message = el('p', 't-wf-message', 'Prozess zeichnen oder eine n8n-JSON-Datei importieren.');this.message.setAttribute('role', 'status');
      this.engine = el('p', 't-wf-hint');
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
        this.file.value = '';this.importRevision = false;this.setTab('editor');
      });
      // Obere Leiste: Name, Stand, Änderungsgrund, Speichern, Zurück/Wiederholen, Menü „Mehr“.
      const top = el('div', 't-wf-toolbar t-wf-top');
      this.title = el('input');this.title.setAttribute('aria-label', 'Workflow-Titel');
      this.title.onchange = ()=>this.change(()=>{this.state.doc.name = this.title.value;});
      this.version = el('span', 't-wf-hint');
      this.changeNote = el('input');this.changeNote.maxLength = 500;this.changeNote.placeholder = 'Was wurde geändert?';this.changeNote.setAttribute('aria-label', 'Änderungsgrund');
      const menu = el('details', 't-wf-menu');menu.append(el('summary', '', 'Mehr'));const list = el('div', 't-wf-menu-list');menu.append(list);this.menu = menu;
      const item = (text, fn)=>list.append(button(text, ()=>{menu.open = false;fn();}));
      item('Beispiel', ()=>{if(this.discard())this.adopt(M().example(), null, null);});
      item('Importieren', ()=>{this.importRevision = false;this.file.click();});
      item('Als neue Version importieren', ()=>{if(!this.wid){this.notice('Zuerst die Ausgangsfassung speichern oder laden.', true);return;}this.importRevision = true;this.file.click();});
      item('Exportieren', ()=>this.export(false));item('Bereinigter Export', ()=>this.export(true));item('Prüfen', ()=>this.safe(()=>this.check()));
      top.append(this.title, this.version, this.changeNote, (()=>{const b = button('Speichern', ()=>this.safe(()=>this.save()));b.className = 't-wf-primary';return b;})(), button('Zurück', ()=>this.undo(false)), button('Wiederholen', ()=>this.undo(true)), menu);
      // Reiter
      this.tabButtons = {};this.panels = {};
      const tabs = el('div', 't-wf-tabs');tabs.setAttribute('role', 'tablist');
      [['overview', options.overviewTitle || 'Übersicht'], ['templates', 'Vorlagen'], ['editor', 'Editor'], ['versions', 'Versionen'], ['runs', options.runTitle || 'Ausführungen'], ['live', 'Live']].forEach(([key, text])=>{
        const b = button('', ()=>this.setTab(key));b.append(el('span', 't-wf-tab-label', text));b.dataset.icon = {overview: '⌂', templates: '▦', editor: '✎', versions: '⟲', runs: '▶', live: '◉'}[key];b.setAttribute('aria-label', text);b.title = text;b.setAttribute('role', 'tab');b.className = 't-wf-tab';this.tabButtons[key] = b;tabs.append(b);
        this.panels[key] = el('section', 't-wf-panel');this.panels[key].setAttribute('role', 'tabpanel');
      });
      // Übersicht
      const find = el('input');find.type = 'search';find.placeholder = 'Suchen …';find.setAttribute('aria-label', 'Prozesse suchen');find.oninput = ()=>this.renderCards(find.value);
      this.cards = el('div', 't-wf-cards');this.findBox = find;
      this.templateBox = el('div', 't-wf-cards');
      this.selfBox = el('div', 't-wf-selfbox');this.selfStatus = el('p', 't-wf-hint', 'SEDRA kann seine eigenen Abläufe als Prozessmodelle zeigen: aus den Quellen im Code erzeugt, nur Darstellung, nie ausführbar.');
      this.selfBox.append(this.selfStatus, button('Selbstabbild prüfen', ()=>this.safe(()=>this.selfCheck())), button('Abläufe von SEDRA anlegen oder aktualisieren', ()=>this.safe(()=>this.selfCreate())));
      // Startseite: Begrüßung, drei Wege zum Anfangen, gespeicherte Arbeit mit Suche, Abläufe von SEDRA
      const hero = el('div', 't-wf-hero');hero.append(el('h2', '', 'Was automatisieren wir heute?'), el('p', 't-wf-hint', 'Von vorn beginnen, mit einer Vorlage starten oder gespeicherte Arbeit öffnen. Läufe starten nur mit Freigabe des Captains.'));
      const starts = el('div', 't-wf-starts');
      const start = (title, text, fn, primary)=>{const b = button('', fn);b.className = 't-wf-start' + (primary ? ' t-wf-primary' : '');b.append(el('strong', '', title), el('span', '', text));return b;};
      starts.append(start(options.newTitle || 'Neuer Workflow', 'Leere Fläche mit einem Auslöser', ()=>{if(this.discard()){this.adopt(this.blank(), null, null);this.setTab('editor');this.notice('Neuer Entwurf. Erster Schritt: „Knoten hinzufügen“.');}}, true),
        start('n8n-Workflow importieren', 'Datei, Ziehen oder Einfügen, mit Vorschau', ()=>{this.importBox.el.scrollIntoView({block: 'center'});this.importBox.el.classList.add('t-wf-flash');}),
        start('Aus Vorlage beginnen', 'Muster A, B und C mit geführtem Einrichten', ()=>this.setTab('templates')),
        start('Abläufe von SEDRA', 'SEDRA bildet seine eigenen Abläufe ab', ()=>{this.selfBox.scrollIntoView({block: 'center'});this.selfBox.classList.add('t-wf-flash');}));
      const ask = el('div', 't-wf-ask');const askText = el('textarea');askText.rows = 3;askText.maxLength = 3000;askText.setAttribute('aria-label', 'Prozess beschreiben');
      askText.placeholder = 'Beschreibe den Prozess in ein paar Sätzen, z. B. „Eine Event-Anfrage kommt per Formular, wird geprüft, bei Standardgröße bestätigt, sonst an einen Menschen weitergegeben.“';
      const askBtn = button('Von SEDRA entwerfen lassen', ()=>this.safe(async()=>{await this.sedraEntwerfen(askText.value);askText.value = '';}));askBtn.className = 't-wf-primary';
      ask.append(askText, el('p', 't-wf-hint', 'SEDRA startet dafür eine eigene Sitzung (links unter „Sitzungen“). Der Entwurf wartet im Posteingang auf dein Ja und ist nie ausführbar.'), askBtn);
      this.picker = el('select');this.picker.setAttribute('aria-label', 'Gespeicherte Workflows');
      this.picker.onchange = ()=>{if(this.picker.value)this.safe(async()=>{await this.load(this.picker.value);this.setTab('editor');});};
      this.importBox = root.sedraWorkflowImport.attach(this);
      this.panels.overview.append(hero, ask, starts, this.importBox.el, el('h3', '', 'Zuletzt gespeichert'), el('div', 't-wf-toolbar', ''), this.cards, el('h3', '', 'Abläufe von SEDRA (Selbstabbild)'), this.selfBox);
      this.panels.templates.append(el('p', 't-wf-hint', 'Eigene Startvorlagen von SEDRA. Muster A: Auslöser, dann Aktion. Muster B: mit Bedingung. Muster C: mit KI-Schritt (nur als Prozessmodell). Nach dem Anlegen führt das geführte Einrichten durch die Schritte.'), this.templateBox);
      this.renderTemplates();
      this.panels.overview.querySelector('.t-wf-toolbar').append(find, this.picker);
      // Editor
      const views = el('div', 't-wf-toolbar');
      this.viewSelect = el('select');this.viewSelect.setAttribute('aria-label', 'Prozessansicht');
      [['canvas', 'Gesamtprozess'], ['core', 'Kernschritte · verdichtet'], ['sipoc', 'SIPOC'], ['details', 'Alle Schritte / Prüfpunkte']].forEach(([k, v])=>this.viewSelect.append(new Option(v, k)));
      this.viewSelect.onchange = ()=>{this.view = this.viewSelect.value;this.draw();};
      views.append(this.viewSelect, button('Geführt einrichten', ()=>this.startGuide()), button('In ' + options.otherTitle + ' öffnen', ()=>{
        if(this.dirty()){this.notice('Für den Wechsel zuerst speichern. Beide Apps teilen gespeicherte Versionen.', true);return;}
        this.ctx.shell.open({type: options.otherType, id: this.wid || 'alle', title: options.otherTitle});
      }));
      this.processBanner = el('p', 't-wf-process-banner');this.bannerText = el('span');this.bannerChat = button('Im Chat besprechen', ()=>{if(this.chat)this.chat.open('Erkläre mir diesen Hinweis zum Prozess und was ich als Nächstes tun sollte: ' + this.bannerText.textContent);});this.bannerChat.className = 't-wf-banner-chat';this.bannerChat.title = 'Den Hinweis mit SEDRA besprechen';this.processBanner.append(this.bannerText, ' ', this.bannerChat);
      this.stage = el('div', 't-wf-stage');this.surface = el('section', 't-wf-surface');this.inspector = el('aside', 't-wf-inspector');this.inspector.hidden = true;
      this.fab = el('div', 't-wf-fab');
      this.addButton = button('+', ()=>this.openPicker());this.addButton.setAttribute('aria-label', 'Knoten hinzufügen');this.addButton.title = 'Knoten hinzufügen';
      this.propsButton = button('☰', ()=>{this.inspectorOpen = !this.inspectorOpen;this.inspect();});this.propsButton.setAttribute('aria-label', 'Eigenschaften');this.propsButton.title = 'Eigenschaften';
      this.guide = el('div', 't-wf-guide');this.guide.hidden = true;this.guide.setAttribute('role', 'region');this.guide.setAttribute('aria-label', 'Geführtes Einrichten');
      this.runChip = button('', ()=>this.setTab('runs'));this.runChip.hidden = true;this.runChip.title = 'Zu den Ausführungen';this.stage.append(this.runChip);
      this.fab.append(this.addButton, this.propsButton);this.stage.append(this.surface, this.fab, this.inspector, this.guide);
      this.stage.addEventListener('keydown', event=>{if(event.key === 'Escape' && this.inspectorOpen && !event.defaultPrevented){this.inspectorOpen = false;this.inspect();}});
      this.report = el('pre', 't-wf-report');this.report.setAttribute('aria-label', 'Kompatibilitätsbericht');
      this.bottom = el('div', 't-wf-bottombar');this.bottom.hidden = !options.runBar;
      const once = button(options.runLabel || 'Einmal ausführen', ()=>this.submitRun());once.className = 't-wf-primary';once.title = 'Legt einen Lauf zur Freigabe vor. Ausgeführt wird erst nach Captain-Freigabe.';
      const plan = button('Zeitplan: aus', ()=>{});plan.disabled = true;plan.title = 'Zeitpläne gibt es im Adapter nicht. Läufe starten nur von Hand und mit Freigabe.';
      const settings = button('Einstellungen', ()=>{this.inspectorOpen = !this.inspectorOpen;this.inspect();});
      this.bottom.append(...[once, options.noSchedule ? null : plan, settings].filter(Boolean), button('Posteingang', ()=>this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Freigaben'})));
      this.panels.editor.append(views, this.processBanner, this.stage, this.bottom, this.report);
      // Versionen
      const history = el('details', 't-wf-history');history.open = true;history.append(el('summary', '', 'Versionshistorie und Vergleich'));this.historyBox = el('div');history.append(this.historyBox);
      this.panels.versions.append(history);
      // Ausführungen
      const run = el('section', 't-wf-run');this.runSection = run;run.append(el('h3', '', options.runTitle || 'Ausführungen'));
      this.input = el('textarea');this.input.value = '{}';this.input.setAttribute('aria-label', 'Laufeingaben als JSON');this.input.rows = 3;
      run.append(el('p', 't-wf-hint', 'Nur geprüfte Datenknoten. Zugangsdaten werden in der lokalen n8n-Testinstanz eingerichtet. Eine Freigabe ist immer erforderlich.'), this.input,
        button('Lauf zur Freigabe vorlegen', ()=>this.submitRun()), button('Posteingang öffnen', ()=>this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Freigaben'})),
        button('Nach Freigabe fortsetzen', ()=>this.safe(async()=>{if(!this.runId)throw new Error('Zuerst einen Lauf wählen.');await this.call('workflow_run', this.runId, 'fortsetzen');await this.showRun(this.runId);})),
        button('Lauf beenden', ()=>this.safe(async()=>{if(!this.runId)throw new Error('Zuerst einen Lauf wählen.');await this.call('workflow_run', this.runId, 'abbrechen');await this.showRun(this.runId);})),
        button('Aktualisieren', ()=>this.safe(()=>this.refreshRuns())));
      this.buildLokal(run);this.buildSchritte(run);
      this.runs = el('div', 't-wf-runs');this.output = el(options.renderRun ? 'div' : 'pre', 't-wf-output');this.output.setAttribute('aria-label', 'Laufergebnis');run.append(this.runs, this.output);
      this.panels.runs.append(run);
            // Seitenleiste links (Übersicht, Vorlagen, Editor, Versionen, Ausführungen), rechts die Fläche; die obere Leiste gehört zur Arbeit am Prozess
      this.top = top;tabs.setAttribute('aria-orientation', 'vertical');tabs.className = 't-wf-rail t-wf-tabs';
      const content = el('div', 't-wf-content');content.append(top, this.panels.overview, this.panels.templates, this.panels.editor, this.panels.versions, this.panels.runs, this.panels.live);
      const body = el('div', 't-wf-body'), railbox = el('div', 't-wf-railbox');
      const fold = button('«', ()=>{const zu = !body.classList.contains('t-wf-collapsed');body.classList.toggle('t-wf-collapsed', zu);setFold(zu);try{root.localStorage.setItem('sedra.wf.rail', zu ? 'zu' : 'auf');}catch(e){}});
      const setFold = zu=>{fold.textContent = zu ? '»' : '«';fold.setAttribute('aria-label', zu ? 'Seitenleiste ausklappen' : 'Seitenleiste einklappen');fold.setAttribute('aria-expanded', String(!zu));fold.title = fold.getAttribute('aria-label');};
      let gemerkt = null;try{gemerkt = root.localStorage.getItem('sedra.wf.rail');}catch(e){}
      body.classList.toggle('t-wf-collapsed', gemerkt === 'zu');setFold(gemerkt === 'zu');fold.className = 't-wf-fold';
      railbox.append(fold, tabs);body.append(railbox, content);
      this.el.replaceChildren(head, this.engine, this.message, body, this.file);
      this.setTab(this.tab || 'editor');
      this.el.addEventListener('keydown', event=>{
        if((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z' && !['INPUT', 'TEXTAREA'].includes(event.target.tagName)){
          event.preventDefault();this.undo(event.shiftKey);
        }
      });
    },
    submitRun(){return this.safe(async()=>{
      if(!this.wid || this.dirty())throw new Error('Workflow zuerst speichern.');
      const out = await this.call('workflow', this.wid, 'starten', {revision: this.revision, inputs: JSON.parse(this.input.value)});
      this.runId = out.id;await this.showRun(out.id);this.notice('Mission angelegt. Freigabe im Posteingang prüfen, dann hier fortsetzen.');
    });},
    placeInspector(){
      const box = this.inspector;if(!box)return;
      const reset = ()=>{box.style.left = '';box.style.top = '';box.style.right = '';};
      if(options.style !== 'scenario' || box.hidden){reset();return;}
      const n = this.surface.querySelector('.t-wf-node.selected');if(!n){reset();return;}
      const s = this.stage.getBoundingClientRect(), r = n.getBoundingClientRect();if(!s.width)return;
      const at = root.sedraWorkflowDialog.place({w: s.width, h: s.height}, {w: box.offsetWidth || 360, h: Math.min(box.offsetHeight || 320, s.height - 24)}, {x: r.left - s.left, y: r.top - s.top, w: r.width, h: r.height});
      box.style.right = 'auto';box.style.left = at.left + 'px';box.style.top = at.top + 'px';
    },
    blank(){const doc = M().example();doc.name = options.newTitle === 'Neues Szenario' ? 'Neues Szenario' : 'Neuer Workflow';doc.nodes = [M().node('manualTrigger', [])];doc.connections = {};return doc;},
    setTab(name){
      const model = this.state && P().has(this.state.doc);
      if(name === 'runs' && model) name = 'editor';
      this.tab = name;if(this.top)this.top.hidden = name === 'overview' || name === 'templates';
      Object.entries(this.panels).forEach(([key, panel])=>{panel.hidden = key !== name;});
      if(this.live){if(name === 'live')this.live.start();else this.live.stop();}      // Live-Reiter fragt nur, solange er offen ist (workflow-live.js)
      Object.entries(this.tabButtons).forEach(([key, b])=>{b.setAttribute('aria-selected', String(key === name));b.classList.toggle('active', key === name);});
    },
    renderCards(filter){
      if(!this.cards)return;
      const q = String(filter === undefined ? this.findBox.value : filter).toLocaleLowerCase('de');
      this.cards.replaceChildren();
      const rows = (this.records || []).filter(r=>!q || String(r.title).toLocaleLowerCase('de').includes(q));
      if(!rows.length){this.cards.append(el('p', 't-wf-hint', q ? 'Keine Treffer.' : 'Noch nichts gespeichert. Mit „' + (options.newTitle || 'Neuer Workflow') + '“ beginnen oder ein Beispiel laden (Menü „Mehr“).'));return;}
      rows.forEach(r=>{
        const card = el('article', 't-wf-card');card.append(el('h3', '', r.title), el('p', 't-wf-hint', 'Revision ' + r.revision));
        card.append(button('Öffnen', ()=>this.safe(async()=>{await this.load(r.id);this.setTab('editor');})));this.cards.append(card);
      });
    },
    openPicker(after, insert){
      if(this.view !== 'canvas')return;
      const palette = options.palette || M().types.map(([kind, label])=>({kind, label}));
      const items = this.catalogItems(palette);
      root.sedraWorkflowPicker.open({host: this.stage, items, title: 'Knoten hinzufügen', onPick: choice=>{
        const entry = choice.entry;
        this.change(()=>{const n = entry.make ? entry.make(this.state.doc.nodes) : M().node(entry.kind, this.state.doc.nodes);this.state.doc.nodes.push(n);this.state.selected = n.id;this.view = 'canvas';
          if(insert){const src = this.state.doc.nodes.find(x=>x.name === insert.from), dst = this.state.doc.nodes.find(x=>x.name === insert.to);
            if(src && dst && !n.type.endsWith('.stickyNote')){
              const schritt = options.style === 'scenario' ? 240 : 224, x = dst.position[0];
              this.state.doc.nodes.forEach(o=>{if(o !== n && o.position[0] >= x)o.position = [o.position[0] + schritt, o.position[1]];});      // nachfolgende Knoten rücken nach rechts (wie im n8n-Editor)
              n.position = [x, dst.position[1]];
              const zweig = ((this.state.doc.connections[src.name] || {}).main || [])[insert.branch] || [];
              for(let k = zweig.length - 1; k >= 0; k--)if(zweig[k].node === dst.name)zweig.splice(k, 1);
              M().connect(this.state.doc, src.name, n.name, insert.branch);M().connect(this.state.doc, n.name, dst.name, 0);
            }
          }
          if(after){const src = this.state.doc.nodes.find(x=>x.name === after.name);if(src){n.position = [src.position[0] + (options.style === 'scenario' ? 210 : 170), src.position[1] + after.branch * 90];if(!n.type.endsWith('.stickyNote'))M().connect(this.state.doc, src.name, n.name, after.branch);}}
        });
      }});
    },
    storedTheme(){try{const v = root.localStorage.getItem('sedra.wf.theme');return v === 'light' || v === 'dark' ? v : null;}catch(e){return null;}},
    applyTheme(theme){
      this.el.dataset.wfTheme = theme;
      if(this.themeButton){this.themeButton.textContent = theme === 'light' ? 'Dunkel' : 'Hell';this.themeButton.setAttribute('aria-label', 'Farbthema wechseln, aktuell ' + (theme === 'light' ? 'hell' : 'dunkel'));}
    },
    dirty(){return JSON.stringify(this.state.doc) !== this.saved;},
    discard(){return !this.dirty() || root.confirm('Nicht gespeicherte Änderungen verwerfen?');},
    adopt(doc, id, revision){
      if(this.guide)this.endGuide();
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
      this.runSection.hidden = model;this.tabButtons.runs.hidden = model;if(model && this.tab === 'runs')this.setTab('editor');this.processBanner.hidden = !model;
      this.engine.hidden = model;this.addButton.hidden = (model && core) || this.view !== 'canvas';this.bottom.hidden = !options.runBar || model;this.report.hidden = model;
      this.bannerText.textContent = 'Prozessmodell · ' + P().cores(this.state.doc).length + ' Kernschritte · ' + P().rows(this.state.doc).filter(r=>r.meta.source === 'proposal').length + ' ergänzte Vorschläge. ' + (() => {const g = P().gaps(this.state.doc);return g.missing ? 'Lücken: ' + g.missing + ' Angaben fehlen in ' + g.steps + ' Schritten (z. B. ' + g.items[0].name + ': ' + g.items[0].fields.join(', ') + '). ' : 'Alle Pflichtangaben sind ausgefüllt. ';})() + 'Fachliche und technische Ausführung sind noch nicht eingerichtet.';
      this.version.textContent = (this.wid ? 'Revision ' + this.revision : 'Neuer Entwurf') + (this.dirty() ? ' · ungespeichert' : ' · gespeichert');
      if(this.canvas)this.canvas.destroy();
      this.canvas = null;
      if(['sipoc', 'details'].includes(this.view)){
        PV().render(this.surface, this.state.doc, this.view, id=>{this.state.selected = id;this.inspectorOpen = true;this.inspect();});this.inspect();return;
      }
      const visual = core ? {doc: P().coreProjection(this.state.doc), selected: this.state.selected} : this.state;
      this.canvas = root.sedraWorkflowCanvas.mount(this.surface, visual, {
        style: this.style, readOnly: core,
        select: id=>{this.state.selected = id;this.inspect();}, open: id=>this.nodeAction('open', id), addAfter: (name, branch)=>this.openPicker({name, branch}), edgeAdd: (from, branch, to)=>this.openPicker(null, {from, branch, to}), edgeDelete: (a, k, i, b)=>this.edgeDelete(a, k, i, b), tidy: ()=>this.tidy(), act: (what, id)=>this.nodeAction(what, id), drawn: ()=>this.placeInspector(), checkpoint: ()=>this.checkpoint(),
        change: ()=>{this.version.textContent = 'Ungespeicherte Änderungen';this.inspect();},
        connect: (a, b, branch)=>{try{this.change(()=>M().connect(this.state.doc, a, b, branch));}catch(e){this.notice(e.message, true);}}
      });this.inspect();
    },
    inspect(){
      const box = this.inspector;const bar = el('div', 't-wf-inspector-head');const closeBtn = button('✕', ()=>{this.inspectorOpen = false;this.inspect();});closeBtn.setAttribute('aria-label', 'Eigenschaften schließen');bar.append(el('h3', '', 'Eigenschaften'), closeBtn);box.replaceChildren(bar);
      box.hidden = !this.inspectorOpen;root.requestAnimationFrame(()=>{if(!this.dead)this.placeInspector();});this.propsButton.setAttribute('aria-pressed', String(!!this.inspectorOpen));
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
      this.engine.textContent = data.engine.enabled ? 'Lokale n8n-Verbindung konfiguriert: ' + data.engine.base_url : 'n8n-Ausführung aus. Import, Editor, Versionen und Export sind verfügbar.' + (data.eigenablauf ? (data.eigenablauf.node ? ' Der SEDRA-Eigenablauf läuft lokal, ohne n8n.' : ' Für den SEDRA-Eigenablauf fehlt Node.js.') : '');
      this.listeTabellen(data.tabellen);
      this.renderRuns(data.runs || []);this.updateRunChip(data.runs || []);this.renderCards();
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
      this.exec = execution;this.updateSteps();
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
      if(this.dead)return;this.runId = id;this.runState = run.state;this.runWf = run.workflow_id;this.updateSteps();
      if(options.renderRun)options.renderRun(this.output, run);
      else if(this.lokalRender(run)){}
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
