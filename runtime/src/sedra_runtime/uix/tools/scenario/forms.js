// Scenario-specific module and mapping forms. Transport and revisions stay shared.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  function el(tag, text){const x = document.createElement(tag);if(text !== undefined)x.textContent = text;return x;}
  function button(text, run){const b = el('button', text);b.type = 'button';b.onclick = run;return b;}
  function input(label, value){const x = el('input');x.setAttribute('aria-label', label);x.value = value === undefined ? '' : value;return x;}
  function choice(label, values, value){const x = el('select');x.setAttribute('aria-label', label);values.forEach(v=>x.append(new Option(v, v)));x.value = value;return x;}
  function typed(value, kind){
    if(kind === 'number'){const n = Number(value);if(!value.trim() || !Number.isFinite(n))throw new Error('Eine gültige Zahl eingeben.');return n;}
    if(kind === 'boolean'){if(!['true', 'false'].includes(value))throw new Error('Für Wahr/Falsch true oder false eingeben.');return value === 'true';}
    return value;
  }
  function inspect(container, node, change, error){
    const form = el('section');form.className = 't-sc-mapping';form.append(el('h3', 'Modul konfigurieren'));
    if(node.type === 'n8n-nodes-base.set' && (!node.parameters.mode || node.parameters.mode === 'manual')){
      form.append(el('p', 'Felder zuordnen: feste Werte oder ein Feld aus dem eingehenden Datenbündel.'));
      const rows = [], list = el('div');form.append(list);
      function row(value){
        const box = el('div');box.className = 't-sc-field';
        const name = input('Zielfeld', value.name || '');
        const type = choice('Datentyp', ['string', 'number', 'boolean'], value.type || 'string');
        const expression = typeof value.value === 'string' && /^=\{\{\s*\$json\./.test(value.value);
        const source = choice('Wertquelle', ['Fester Wert', 'Eingangsfeld'], expression ? 'Eingangsfeld' : 'Fester Wert');
        const text = input('Wert oder Feldpfad', expression ? value.value.replace(/^=\{\{\s*\$json\./, '').replace(/\s*\}\}$/, '') : String(value.value === undefined ? '' : value.value));
        const item = {box, name, type, source, text, original: value};rows.push(item);
        box.append(el('span', 'Zielfeld / Typ / Quelle / Wert'), name, type, source, text, button('Zuordnung entfernen', ()=>{rows.splice(rows.indexOf(item), 1);box.remove();}));list.append(box);
      }
      const assignments = ((node.parameters.assignments || {}).assignments || []);assignments.forEach(row);
      form.append(button('Feld hinzufügen', ()=>row({})), button('Feldzuordnung übernehmen', ()=>{
        try{
          if(!rows.length)throw new Error('Mindestens ein Feld zuordnen.');
          const values = rows.map(r=>{
            if(!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(r.name.value) || ['__proto__', 'constructor', 'prototype'].includes(r.name.value))throw new Error('Zielfeld ist ungültig.');
            let value;
            if(r.source.value === 'Eingangsfeld'){
              if(!/^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$/.test(r.text.value) || r.text.value.split('.').some(k=>['__proto__', 'constructor', 'prototype'].includes(k)))throw new Error('Einfachen Feldpfad eingeben, etwa rechnung.betrag.');
              value = '={{ $json.' + r.text.value + ' }}';
            }else value = typed(r.text.value, r.type.value);
            return Object.assign({}, r.original, {id: r.original.id || root.crypto.randomUUID(), name: r.name.value, type: r.type.value, value});
          });
          change(()=>{node.parameters = Object.assign({}, node.parameters, {mode: 'manual', assignments: {assignments: values}});});
        }catch(e){error(e.message);}
      }));
    }else if(node.type === 'n8n-nodes-base.if'){
      form.append(el('p', 'Router mit zwei Wegen: Filter erfüllt (Ja) oder nicht erfüllt (Nein).'));
      const conditions = node.parameters.conditions || {}, existing = (conditions.conditions || [])[0] || {};
      const left = input('Filterwert / Datenpfad', existing.leftValue || '={{ $json.status }}');
      const type = choice('Filtertyp', ['string', 'number', 'boolean'], (existing.operator || {}).type || 'string');
      const operation = choice('Filtervergleich', ['equals', 'notEquals', 'contains', 'notContains', 'empty', 'notEmpty', 'gt', 'gte', 'lt', 'lte', 'true', 'false'], (existing.operator || {}).operation || 'equals');
      const right = input('Vergleichswert', existing.rightValue === undefined ? '' : String(existing.rightValue));
      form.append(el('label', 'Filterwert'), left, type, operation, right, button('Filter übernehmen', ()=>{
        try{
          const allowed = {string: ['equals', 'notEquals', 'contains', 'notContains', 'empty', 'notEmpty'], number: ['equals', 'notEquals', 'gt', 'gte', 'lt', 'lte'], boolean: ['true', 'false', 'equals', 'notEquals']};
          if(!allowed[type.value].includes(operation.value))throw new Error('Vergleich passt nicht zum Datentyp.');
          const single = ['empty', 'notEmpty', 'true', 'false'].includes(operation.value);
          const item = Object.assign({}, existing, {id: existing.id || root.crypto.randomUUID(), leftValue: left.value, rightValue: single ? '' : typed(right.value, type.value), operator: {type: type.value, operation: operation.value}});
          const p = root.sedraWorkflowModel.clone(node.parameters);
          p.conditions = Object.assign({}, conditions, {conditions: [item].concat((conditions.conditions || []).slice(1))});
          change(()=>{node.parameters = p;});
        }catch(e){error(e.message);}
      }));
    }else{
      form.append(el('p', node.type.endsWith('.manualTrigger') ? 'Manueller Auslöser. Startdaten werden beim Lauf übergeben.' : node.type.endsWith('.noOp') ? 'Übergabemodul ohne eigene Fachautomatik. Eine Prozessbeschreibung kann menschliche Aufgaben kennzeichnen.' : 'Dieses importierte Modul bleibt erhalten. Technische Parameter in n8n Workflows bearbeiten.'));
    }
    container.append(form);
  }
  function run(container, record){
    container.replaceChildren(el('h3', 'Bündel und Laufstatus'), el('p', record.mission_id + ' · ' + record.state));
    if(!record.result){container.append(el('p', 'Noch keine Engine-Ausgabe.'));return;}
    if(record.result.error)container.append(el('p', 'Fehler: ' + record.result.error));
    if(!Object.prototype.hasOwnProperty.call(record.result, 'output'))return;
    const data = record.result.output, items = Array.isArray(data) ? data : [data];
    container.append(el('p', items.length + ' Bündel aus der tatsächlichen Engine-Antwort.'));
    items.forEach((item, i)=>{const details = el('details');details.append(el('summary', 'Bündel ' + (i + 1)));const body = el('pre', JSON.stringify(item, null, 2));details.append(body);container.append(details);});
  }
  root.sedraScenarioForms = {inspect, run};
})();
