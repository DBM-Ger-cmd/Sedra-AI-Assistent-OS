// Zusatzfunktionen des gemeinsamen Editors, als Methoden in den Editor gemischt (Datei bleibt unter der Zeilengrenze des UI-Vertrags):
// geführtes Einrichten, Startvorlagen, Selbstabbild von SEDRA und die Schnellaktionen am Knoten. `this` ist der Editor.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const M = ()=>root.sedraWorkflowModel;
  const P = ()=>root.sedraWorkflowProcess;
  function el(tag, cls, text){const x = document.createElement(tag);if(cls)x.className = cls;if(text !== undefined)x.textContent = text;return x;}
  function button(text, fn){const b = el('button', '', text);b.type = 'button';b.onclick = fn;return b;}
  root.sedraWorkflowExtras = function(options){
    return {
    // Geführtes Einrichten: Schritt für Schritt durch die Knoten, mit Hinweis je Art. Ändert nichts von selbst; Überspringen ist jederzeit möglich.
    guideOrder(){
      const doc = this.state.doc, byName = new Map(doc.nodes.map(n=>[n.name, n])), seen = new Set(), out = [];
      const start = doc.nodes.find(n=>n.type.endsWith('.manualTrigger')) || doc.nodes[0], queue = start ? [start] : [];
      while(queue.length){
        const n = queue.shift();if(seen.has(n.id))continue;seen.add(n.id);out.push(n);
        Object.values(doc.connections[n.name] || {}).forEach(branches=>branches.forEach(b=>b.forEach(e=>{const t = byName.get(e.node);if(t)queue.push(t);})));
      }
      doc.nodes.forEach(n=>{if(!seen.has(n.id))out.push(n);});
      return out.filter(n=>!n.type.endsWith('.stickyNote'));
    },
    guideHint(node){
      const I = root.sedraWorkflowIcons, meta = P().get(node), key = I ? I.key(node, meta) : 'unknown';
      const text = {manualTrigger: 'Womit beginnt der Ablauf? Name und Zweck des Auslösers prüfen.', start: 'Womit beginnt der Ablauf? Name und Zweck des Auslösers prüfen.', set: 'Welche Felder werden gesetzt? Die Parameter prüfen oder anpassen.',
        if: 'Nach welcher Bedingung verzweigt der Ablauf? Ja- und Nein-Weg prüfen.', decision: 'Nach welcher Bedingung verzweigt der Ablauf? Ja- und Nein-Weg prüfen.', noOp: 'Wohin geht das Ergebnis? Name so wählen, dass er sagt, was passiert.',
        human: 'Wer entscheidet hier? Rolle und Nachweis eintragen. Menschliche Schritte bleiben beim Menschen.', task: 'Was passiert in diesem Schritt? Rolle, Eingabe, Ergebnis und Nachweis prüfen.', end: 'Was ist das klare Ergebnis? Abschlusskriterium prüfen.'}[key];
      let gap = '';
      if(meta){const g = P().gaps({nodes: [node]});if(g.missing)gap = ' Noch offen: ' + g.items[0].fields.join(', ') + '.';}
      return (text || 'Name und Parameter prüfen.') + gap;
    },
    offerGuide(){
      this.guideOrderList = null;this.guideIndex = null;
      const box = this.guide;box.replaceChildren(el('p', '', 'Geführtes Einrichten: Schritt für Schritt durch alle Knoten, mit Hinweisen. Jederzeit überspringbar.'),
        (()=>{const b = button('Geführtes Einrichten starten', ()=>this.startGuide());b.className = 't-wf-primary';return b;})(), button('Geführtes Einrichten überspringen', ()=>this.endGuide()));box.hidden = false;
    },
    startGuide(){
      if(this.view !== 'canvas'){this.view = 'canvas';this.draw();}
      this.setTab('editor');this.guideOrderList = this.guideOrder();this.guideIndex = 0;this.renderGuide();
    },
    endGuide(){this.guide.hidden = true;this.guide.replaceChildren();this.guideIndex = null;this.guideOrderList = null;},
    renderGuide(){
      const list = this.guideOrderList || [];if(!list.length){this.endGuide();return;}
      const i = Math.max(0, Math.min(this.guideIndex, list.length - 1)), node = list[i];this.guideIndex = i;
      this.state.selected = node.id;this.inspectorOpen = true;this.inspect();if(this.canvas)this.canvas.draw();
      const box = this.guide;box.hidden = false;
      const head = el('p', 't-wf-guide-step', 'Schritt ' + (i + 1) + ' von ' + list.length + ' · ' + node.name);
      box.replaceChildren(head, el('p', '', this.guideHint(node)),
        button('Zurück zum vorigen Schritt', ()=>{this.guideIndex = i - 1;this.renderGuide();}),
        (()=>{const b = i + 1 < list.length ? button('Weiter zum nächsten Schritt', ()=>{this.guideIndex = i + 1;this.renderGuide();}) : button('Einrichten abschließen', ()=>{this.endGuide();this.notice('Geführtes Einrichten beendet. Speichern erzeugt die erste Revision.');});b.className = 't-wf-primary';return b;})(),
        button('Geführtes Einrichten überspringen', ()=>this.endGuide()));
      box.firstChild.nextSibling.nextSibling.disabled = i === 0;
    },
    async selfCheck(){
      const out = await this.call('workflow', null, 'selbstabbild_pruefen');if(this.dead)return;
      const sum = {fehlt: 0, gleich: 0, abweichend: 0};out.abweichung.forEach(x=>{sum[x.status] = (sum[x.status] || 0) + 1;});
      this.selfStatus.textContent = (out.probleme.length ? out.probleme.length + ' Schritt(e) stimmen nicht mehr mit den Quellen überein: ' + out.probleme.slice(0, 3).map(p=>p.ablauf + '.' + p.schritt + ' (' + p.grund + ')').join(', ') + '. ' : 'Alle Quellen stimmen. ')
        + 'Stand: ' + sum.gleich + ' aktuell, ' + sum.abweichend + ' abweichend, ' + sum.fehlt + ' noch nicht angelegt.';
    },
    async selfCreate(){
      const out = await this.call('workflow', null, 'selbstabbild_anlegen');if(this.dead)return;
      await this.refresh();
      this.selfStatus.textContent = out.ergebnis.map(x=>x.name.replace('SEDRA-Selbstabbild · ', '') + ': ' + x.status + ' (Revision ' + x.revision + ')').join(' · ');
      this.notice('Abläufe von SEDRA aus den Quellen erzeugt. Nur Darstellung, nicht ausführbar.');
    },
    renderTemplates(){
      const T = root.sedraWorkflowTemplates;if(!T || !this.templateBox)return;
      this.templateBox.replaceChildren();
      T.list().forEach(t=>{
        const card = el('article', 't-wf-card');card.append(el('h3', '', t.title), el('p', 't-wf-hint', t.description));
        const chips = el('div', 't-wf-chips');t.chips.forEach(kind=>chips.append(el('span', 't-wf-chip', root.sedraWorkflowIcons ? root.sedraWorkflowIcons.label(kind) : kind)));card.append(chips);
        card.append(button('Vorlage verwenden', ()=>{if(this.discard()){this.adopt(T.build(t.id), null, null);this.setTab('editor');this.notice('Aus Vorlage „' + t.title + '“ angelegt. Speichern erzeugt die erste Revision.');this.offerGuide();}}));
        card.setAttribute('aria-label', 'Vorlage ' + t.title);this.templateBox.append(card);
      });
    },
    // Eine Sitzung aus der App: SEDRA entwirft den Prozess in einer eigenen Harness-Sitzung (Vorlage „Prozessmodellierer“). Sie erscheint links unter „Sitzungen“;
    // der Entwurf kommt als Antrag in den Posteingang und wird erst nach der Freigabe des Captains angelegt.
    async sedraEntwerfen(text){
      const beschreibung = String(text || '').trim();
      if(beschreibung.length < 10)throw new Error('Bitte den Prozess mit ein paar Sätzen beschreiben.');
      const kopf = await this.ctx.api('/api/harness/sitzungen', {method: 'POST', body: {vorlage: 'prozessmodellierer', titel: ('Prozess: ' + beschreibung).slice(0, 60)}});
      const wunsch = 'Entwirf aus dieser Beschreibung einen Prozess für die Prozess-Apps und schlage ihn mit prozess_beantragen vor.\n\nBeschreibung:\n' + beschreibung;
      const out = await this.ctx.api('/api/harness/sitzungen/' + kopf.id + '/nachricht', {method: 'POST', body: {text: wunsch}});
      if(this.dead)return;
      if(out.status === 'kein_modell')this.notice('Sitzung ' + kopf.id + ' ist angelegt (links unter „Sitzungen“), aber es ist kein Modell geladen: ' + (out.grund || 'Modell in der Harness laden und die Nachricht dort senden.'), true);
      else this.notice('Sitzung ' + kopf.id + ' gestartet, sie steht links unter „Sitzungen“. Der Entwurf kommt als Antrag in den Posteingang (Freigaben); angelegt wird er erst nach deinem Ja.');
      return kopf.id;
    },
    edgeDelete(source, kind, index, target){
      this.change(()=>{const zweige = ((this.state.doc.connections[source] || {})[kind]) || [], z = zweige[index] || [];for(let k = z.length - 1; k >= 0; k--)if(z[k].node === target)z.splice(k, 1);});
      this.notice('Verbindung ' + source + ' nach ' + target + ' gelöscht. „Zurück“ stellt sie wieder her.');
    },
    // Aufräumen wie „Tidy up“ im n8n-Editor: Spalten nach Abstand vom Auslöser, Zeilen nach Reihenfolge; Notizen bleiben stehen
    tidy(){
      const doc = this.state.doc, byName = new Map(doc.nodes.map(n=>[n.name, n])), start = doc.nodes.find(n=>n.type.endsWith('.manualTrigger')) || doc.nodes[0];
      if(!start)return;
      const tiefe = new Map([[start.id, 0]]), reihe = [start];
      for(const n of reihe)Object.values(doc.connections[n.name] || {}).forEach(zweige=>zweige.forEach(z=>z.forEach(e=>{const t = byName.get(e.node);if(t && !tiefe.has(t.id)){tiefe.set(t.id, tiefe.get(n.id) + 1);reihe.push(t);}})));
      doc.nodes.filter(n=>!tiefe.has(n.id) && !n.type.endsWith('.stickyNote')).forEach(n=>{tiefe.set(n.id, 0);reihe.push(n);});
      const sz = options.style === 'scenario' ? [240, 200] : [224, 170], zeilen = new Map();
      this.change(()=>{reihe.forEach(n=>{const d = tiefe.get(n.id), z = zeilen.get(d) || 0;zeilen.set(d, z + 1);n.position = [d * sz[0], z * sz[1]];});});
      this.notice('Knoten geordnet. „Zurück“ stellt die alte Anordnung wieder her.');
    },
    // Parameteransicht (Eingabe, Parameter, Ausgabe) für die n8n-Darstellung; übernimmt Name und Parameter erst mit „Übernehmen“ als eine Änderung
    openNdv(id){
      const node = this.state.doc.nodes.find(n=>n.id === id), N = root.sedraWorkflowNdv;if(!node || !N)return;
      if(this.ndv)this.ndv.close();
      this.state.selected = id;this.inspectorOpen = false;this.inspect();if(this.canvas)this.canvas.draw();
      this.sampleData = this.sampleData || {text: 'Hallo aus SEDRA'};
      this.ndv = N.open({host: this.stage, doc: this.state.doc, node, sample: this.sampleData, setSample: v=>{this.sampleData = v;}, onClose: ()=>{this.ndv = null;},
        apply: (name, params)=>{this.change(()=>{if(name !== node.name)M().rename(this.state.doc, node.name, name);node.parameters = params;});this.notice('Parameter von „' + name + '“ übernommen.');}});
    },
    // Katalog wie im Knotenkatalog von n8n: Kategorien in fester Reihenfolge, nicht unterstützte Knoten sichtbar, aber gesperrt (im Austausch erhalten)
    catalogItems(palette){
      const CAT = {manualTrigger: 'Auslöser', set: 'Daten', if: 'Ablauf', noOp: 'Ablauf', stickyNote: 'Notiz'};
      const HINT = {manualTrigger: 'Startet den Ablauf von Hand', set: 'Felder setzen oder ändern', if: 'Verzweigt nach einer Bedingung', noOp: 'Reicht die Daten unverändert weiter', stickyNote: 'Notiz ohne Wirkung'};
      const ORDER = ['Auslöser', 'Daten', 'Ablauf', 'Aktionen', 'KI', 'Notiz', 'Mensch'];
      const items = palette.map(entry=>({label: entry.label, category: entry.make ? 'Mensch' : CAT[entry.kind] || 'Weitere', hint: entry.make ? 'Menschliche Entscheidung, keine Automatik' : HINT[entry.kind], keywords: entry.kind || '', entry}));
      const LOCKED = [['Auslöser', 'Schedule Trigger', 'Zeitplan'], ['Auslöser', 'Webhook', 'HTTP-Aufruf'], ['Auslöser', 'Form Trigger', 'Formular'], ['Daten', 'Code', 'Eigener Code'], ['Daten', 'Filter', 'Einträge filtern'],
        ['Ablauf', 'Switch', 'Mehrere Wege'], ['Ablauf', 'Merge', 'Wege zusammenführen'], ['Ablauf', 'Wait', 'Warten'], ['Aktionen', 'HTTP Request', 'Webanfrage'], ['Aktionen', 'Google Sheets', 'Tabellen'], ['KI', 'AI Agent', 'KI-Agent']];
      LOCKED.forEach(([category, label, kw])=>items.push({label, category, hint: 'Nur im Austausch erhalten, hier nicht ausführbar', keywords: kw, disabled: true}));
      return items.map((it, i)=>[ORDER.indexOf(it.category) < 0 ? 99 : ORDER.indexOf(it.category), i, it]).sort((a, b)=>a[0] - b[0] || a[1] - b[1]).map(x=>x[2]);
    },
    // Marke des letzten Laufs dieses Prozesses. Die Engine liefert nur das Endergebnis, darum gibt es eine Marke für den ganzen Lauf, keine je Knoten.
    updateRunChip(runs){
      if(!this.runChip)return;
      const mine = (runs || this.lastRuns || []).filter(r=>r.workflow_id && r.workflow_id === this.wid), last = mine[mine.length - 1];
      this.lastRuns = runs || this.lastRuns;
      this.runChip.hidden = !last;
      if(!last)return;
      const TEXT = {COMPLETE: 'abgeschlossen', CAPTAIN_REVIEW: 'wartet auf Freigabe', READY: 'bereit', EXECUTE: 'läuft', FAILED: 'fehlgeschlagen', PAUSED: 'pausiert', CLOSED: 'beendet'};
      this.runChip.textContent = 'Letzter Lauf: ' + (TEXT[last.state] || String(last.state).toLowerCase());
      this.runChip.className = 't-wf-runchip ' + (last.state === 'COMPLETE' ? 'ok' : last.state === 'FAILED' ? 'bad' : 'wait');
    },
    nodeAction(what, id){
      const node = this.state.doc.nodes.find(n=>n.id === id);if(!node)return;
      if(what === 'open' && options.ndv && !P().get(node)){this.openNdv(id);return;}
      if(what === 'open'){this.state.selected = id;this.inspectorOpen = true;this.inspect();return;}
      if(what === 'delete'){this.change(()=>{M().remove(this.state.doc, node.name);this.state.selected = null;});this.notice('Knoten „' + node.name + '“ entfernt. „Zurück“ stellt ihn wieder her.');return;}
      if(what === 'duplicate'){
        this.change(()=>{
          const copy = M().clone(node);copy.id = 'n-' + Date.now().toString(36) + Math.random().toString(16).slice(2, 8);
          let name = node.name + ' Kopie', k = 2;while(this.state.doc.nodes.some(x=>x.name === name))name = node.name + ' Kopie ' + k++;
          copy.name = name;copy.position = [node.position[0] + 40, node.position[1] + 70];
          const meta = P().get(copy);if(meta){meta.core_step = 0;P().set(copy, meta);}
          this.state.doc.nodes.push(copy);this.state.selected = copy.id;
        });
        this.notice('Knoten dupliziert (ohne Verbindungen).');
      }
    },
    };
  };
})();
