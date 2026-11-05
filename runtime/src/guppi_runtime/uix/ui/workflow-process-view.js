// Shared SIPOC, detail fields and revision history, only in the supplied container.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const P = ()=>root.sedraWorkflowProcess;
  function el(tag, cls, text){const x = document.createElement(tag);if(cls)x.className = cls;if(text !== undefined)x.textContent = text;return x;}
  function button(text, fn){const b = el('button', '', text);b.type = 'button';b.onclick = fn;return b;}
  function select(label, choices, value){
    const s = el('select');s.setAttribute('aria-label', label);
    choices.forEach(([key, title])=>s.append(new Option(title, key)));s.value = value;return s;
  }
  function table(container, headings, rows){
    const wrap = el('div', 't-wf-table-scroll'), t = el('table', 't-wf-table');
    const head = el('thead'), line = el('tr');headings.forEach(h=>line.append(el('th', '', h)));head.append(line);t.append(head);
    const body = el('tbody');rows.forEach(cells=>{const tr = el('tr');cells.forEach(value=>{
      const td = el('td');if(value && value.nodeType)td.append(value);else td.textContent = String(value === undefined || value === null ? '—' : value);tr.append(td);
    });body.append(tr);});t.append(body);wrap.append(t);container.append(wrap);
  }
  function render(container, doc, view, open){
    container.replaceChildren();
    container.append(el('h3', '', view === 'sipoc' ? 'SIPOC · Kernprozess' : 'Alle Schritte und Prüfpunkte'),
      el('p', 't-wf-hint', 'Prozessmodell. Ergänzungen und vorgeschlagene Rollen müssen fachlich bestätigt werden.'));
    const rows = view === 'sipoc' ? P().cores(doc) : P().rows(doc);
    if(!rows.length){container.append(el('p', '', 'Noch keine Prozessbeschreibungen. Knoten wählen und eine Beschreibung ergänzen.'));return;}
    if(view === 'sipoc')table(container, ['Lieferanten', 'Input', 'Prozess', 'Output', 'Kunden / Empfänger'], rows.map(({node, meta})=>[
      meta.supplier, meta.input, button(node.name, ()=>open(node.id)), meta.output, meta.customer]));
    else table(container, ['Schritt', 'Rolle / Arbeitsweise', 'Ein- und Ausgabe', 'Nachweis / Abschluss', 'Herkunft'], rows.map(({node, meta})=>[
      button(node.name, ()=>open(node.id)), (meta.role || 'Rolle offen') + '\n' + (meta.role_status === 'confirmed' ? 'Bestätigt' : 'Rolle vorgeschlagen') + '\n' + P().labels[meta.mode],
      'Input: ' + (meta.input || 'offen') + '\nOutput: ' + (meta.output || 'offen'),
      (meta.evidence || 'Nachweis offen') + '\nAbschluss: ' + (meta.completion || 'offen'), P().labels[meta.source]]));
  }
  function editor(container, node, apply){
    const old = P().get(node);
    if(!old){container.append(button('Prozessbeschreibung hinzufügen', ()=>apply(P().blank(node))));return;}
    const form = el('div', 't-wf-process-fields');form.append(el('h3', '', 'Prozessbeschreibung'));
    const fields = {};
    const enums = {kind: ['Schrittart', ['start', 'task', 'decision', 'end', 'annotation']],
      mode: ['Arbeitsweise', ['manual', 'assisted', 'automatable']], source: ['Herkunft', ['board', 'proposal']],
      role_status: ['Rollenstatus', ['proposal', 'confirmed']]};
    Object.entries(enums).forEach(([key, [label, choices]])=>{
      const titles = choices.map(k=>[k, key === 'role_status' && k === 'proposal' ? 'Vorgeschlagen' : P().labels[k]]);
      const input = select(label, titles, old[key]);fields[key] = input;
      const wrap = el('label', '', label);wrap.append(input);form.append(wrap);
    });
    const core = el('input');core.type = 'number';core.min = '0';core.max = '32';core.value = old.core_step || 0;core.setAttribute('aria-label', 'Kernschritt-Nummer');fields.core_step = core;
    const label = el('label', '', 'Kernschritt-Nummer (0 = ergänzender Schritt)');label.append(core);form.append(label);
    const labels = {supplier: 'Lieferant', input: 'Eingabe', output: 'Ergebnis', customer: 'Empfänger', role: 'Zuständige Rolle',
      evidence: 'Nachweis', completion: 'Abschlusskriterium', exception: 'Ausnahme / Stopp', automation_reason: 'Automatisierungsbegründung', risk: 'Risiko / Hypothese'};
    Object.entries(labels).forEach(([key, title])=>{
      const input = el('textarea');input.rows = 2;input.maxLength = 4000;input.value = old[key] || '';input.setAttribute('aria-label', title);fields[key] = input;
      const wrap = el('label', '', title);wrap.append(input);form.append(wrap);
    });
    form.append(button('Prozessbeschreibung übernehmen', ()=>{
      const value = Object.assign({}, old);
      Object.entries(fields).forEach(([k, field])=>{value[k] = k === 'core_step' ? Number(field.value) : field.value;});
      if(!Number.isInteger(value.core_step) || value.core_step < 0 || value.core_step > 32)return;
      apply(value);
    }));container.append(form);
  }
  function diff(container, changes){
    container.replaceChildren();
    if(!changes.length){container.append(el('p', '', 'Keine Änderungen zwischen diesen Fassungen.'));return;}
    const value = v=>{let s = typeof v === 'string' ? v : JSON.stringify(v);return s && s.length > 700 ? s.slice(0, 700) + ' … [gekürzt]' : s || '—';};
    table(container, ['Schritt', 'Änderung', 'Vorher', 'Nachher'], changes.map(c=>[c.node, c.field, value(c.before), value(c.after)]));
  }
  function history(container, versions, compare, restore){
    container.replaceChildren();
    if(!versions.length){container.append(el('p', 't-wf-hint', 'Nach dem ersten Speichern erscheint hier die Versionshistorie.'));return;}
    const controls = el('div', 't-wf-toolbar');
    const choices = versions.map(v=>[String(v.revision), 'Revision ' + v.revision]);
    const from = select('Vergleich von Revision', choices, String(versions[Math.max(0, versions.length - 2)].revision));
    const to = select('Vergleich bis Revision', choices, String(versions[versions.length - 1].revision));
    const differences = el('div');
    controls.append(from, to, button('Versionen vergleichen', ()=>compare(Number(from.value), Number(to.value), differences)));
    container.append(controls);
    table(container, ['Version', 'Zeitpunkt', 'Änderungsgrund', 'Umfang', 'Aktion'], versions.slice().reverse().map(v=>[
      'Revision ' + v.revision, new Date(v.saved_at).toLocaleString('de-DE'), v.change_note || 'Ältere Fassung ohne Änderungsnotiz',
      String((v.changes || []).length) + ' Änderungen', button('Revision ' + v.revision + ' als Entwurf', ()=>restore(v.revision))]));
    container.append(differences);
  }
  root.sedraWorkflowProcessView = {render, editor, history, diff};
})();
