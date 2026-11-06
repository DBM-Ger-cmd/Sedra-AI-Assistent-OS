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
    nodeAction(what, id){
      const node = this.state.doc.nodes.find(n=>n.id === id);if(!node)return;
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
