// Parameteransicht eines Knotens (nach dem Vorbild der Knotendetailansicht im n8n-Editor): links die Eingabe, in der Mitte die Parameter,
// rechts die Ausgabe. Die Ausgabe ist eine lokal berechnete Vorschau mit Beispieldaten, KEIN Lauf der Engine. Gerechnet wird nur, was das
// Ausführungsprofil kennt (Auslöser, Felder setzen, Bedingung, Weitergabe); alles andere wird als „nicht vorab berechenbar“ gezeigt.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const PATH = /^=\{\{\s*\$json((?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*\}\}$/;
  const NAME = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;
  const UNSAFE = ['__proto__', 'prototype', 'constructor'];
  const OPS = {string: ['equals', 'notEquals', 'contains', 'notContains', 'empty', 'notEmpty'], number: ['equals', 'notEquals', 'gt', 'gte', 'lt', 'lte'], boolean: ['true', 'false', 'equals', 'notEquals']};
  const OPNAME = {equals: 'ist gleich', notEquals: 'ist ungleich', contains: 'enthält', notContains: 'enthält nicht', empty: 'ist leer', notEmpty: 'ist nicht leer', gt: 'größer als', gte: 'größer oder gleich', lt: 'kleiner als', lte: 'kleiner oder gleich', true: 'ist wahr', false: 'ist falsch'};
  const SINGLE = ['empty', 'notEmpty', 'true', 'false'];
  const typeOf = n=>String((n && n.type) || '').split('.').pop();

  // ---- reine Logik (ohne DOM, getestet) ----
  function resolve(value, json){
    if(typeof value !== 'string') return value;
    const m = PATH.exec(value);
    if(!m) return value;
    let cur = json;
    for(const key of m[1].slice(1).split('.')){if(cur === null || typeof cur !== 'object' || UNSAFE.includes(key))return undefined;cur = cur[key];}
    return cur;
  }
  function previewSet(params, input){
    const rows = ((params.assignments || {}).assignments) || [];
    const out = params.includeOtherFields ? Object.assign({}, input) : {};
    rows.forEach(r=>{out[r.name] = resolve(r.value, input);});
    return out;
  }
  function condition(row, input, sensitive){
    let a = resolve(row.leftValue, input), b = resolve(row.rightValue, input);
    const op = (row.operator || {}).operation, kind = (row.operator || {}).type;
    if(kind === 'string'){
      a = a === undefined || a === null ? '' : String(a);b = b === undefined || b === null ? '' : String(b);
      if(!sensitive){a = a.toLowerCase();b = b.toLowerCase();}
      return {equals: a === b, notEquals: a !== b, contains: a.includes(b), notContains: !a.includes(b), empty: a === '', notEmpty: a !== ''}[op];
    }
    if(kind === 'number'){a = Number(a);b = Number(b);return {equals: a === b, notEquals: a !== b, gt: a > b, gte: a >= b, lt: a < b, lte: a <= b}[op];}
    if(kind === 'boolean'){return {true: a === true, false: a === false, equals: a === b, notEquals: a !== b}[op];}
    return undefined;
  }
  function previewIf(params, input){
    const c = params.conditions || {}, rows = c.conditions || [], sensitive = (c.options || {}).caseSensitive !== false;
    const results = rows.map(r=>condition(r, input, sensitive));
    if(results.some(x=>x === undefined)) return null;
    return (c.combinator || 'and') === 'or' ? results.some(Boolean) : results.every(Boolean);
  }
  // Rechnet den Beispieldatensatz durch den Graphen: je Knoten Eingabe und Ausgabe je Ausgang. Unbekannte Knoten brechen die Vorschau dort ab.
  function simulate(doc, sample){
    const byName = new Map(doc.nodes.map(n=>[n.name, n])), result = new Map(), start = doc.nodes.find(n=>typeOf(n) === 'manualTrigger');
    if(!start) return result;
    const queue = [[start, sample]], seen = new Set();
    while(queue.length){
      const [node, input] = queue.shift();
      if(seen.has(node.id)) continue;
      seen.add(node.id);
      const kind = typeOf(node);
      let outs = null, note = null;
      if(kind === 'manualTrigger') outs = [input];
      else if(kind === 'set') outs = [previewSet(node.parameters || {}, input)];
      else if(kind === 'noOp') outs = [input];
      else if(kind === 'if'){const r = previewIf(node.parameters || {}, input);outs = r === null ? null : r ? [input, null] : [null, input];}
      if(outs === null) note = 'nicht vorab berechenbar';
      result.set(node.name, {input, outs, note});
      if(outs) (((doc.connections[node.name] || {}).main) || []).forEach((branch, i)=>branch.forEach(e=>{const t = byName.get(e.node);if(t && outs[i] !== undefined && outs[i] !== null)queue.push([t, outs[i]]);}));
    }
    return result;
  }
  function upstream(doc, node){
    const out = [];
    Object.entries(doc.connections).forEach(([from, o])=>Object.values(o).forEach(branches=>branches.forEach((b, i)=>b.forEach(e=>{if(e.node === node.name && !out.some(x=>x.from === from))out.push({from, branch: i});}))));
    return out;
  }
  // prüft Parameter nach denselben Regeln wie das Ausführungsprofil (workflows/policy.py), damit nichts Ungültiges gespeichert wird
  function check(kind, p){
    if(kind === 'set'){
      const rows = (p.assignments || {}).assignments || [];
      if(!rows.length) throw new Error('Mindestens ein Feld setzen.');
      rows.forEach(r=>{
        if(!NAME.test(r.name || '') || UNSAFE.includes(r.name)) throw new Error('Feldname „' + (r.name || '') + '“ ist ungültig (Buchstaben, Ziffern, Unterstrich).');
        if(typeof r.value === 'string' && /\{\{|\}\}|^=/.test(r.value) && !PATH.test(r.value)) throw new Error('Ausdruck bei „' + r.name + '“ ist nicht erlaubt: nur ein Feldpfad wie $json.text.');
        if(r.type === 'number' && typeof r.value !== 'number' && !PATH.test(String(r.value))) throw new Error('„' + r.name + '“ braucht eine Zahl.');
      });
    }
    if(kind === 'if'){
      const rows = ((p.conditions || {}).conditions) || [];
      if(!rows.length) throw new Error('Mindestens eine Bedingung angeben.');
      rows.forEach(r=>{if(!(OPS[r.operator.type] || []).includes(r.operator.operation)) throw new Error('Operator passt nicht zum Typ.');});
    }
  }

  // ---- Oberfläche ----
  function el(tag, cls, text){const x = document.createElement(tag);if(cls)x.className = cls;if(text !== undefined)x.textContent = text;return x;}
  function button(text, fn, cls){const b = el('button', cls || '', text);b.type = 'button';b.onclick = fn;return b;}
  function field(label, node){const l = el('label', 't-ndv-field');l.append(el('span', '', label), node);return l;}
  function uid(){return root.crypto && root.crypto.randomUUID ? root.crypto.randomUUID() : 'a-' + Date.now() + '-' + Math.random().toString(16).slice(2);}
  const show = v=>v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v);

  function open(o){
    const doc = o.doc, node = o.node, kind = typeOf(node);
    const work = JSON.parse(JSON.stringify(node.parameters || {}));
    let name = node.name, sample = o.sample, focusInput = null;
    const box = el('section', 't-wf-ndv');box.setAttribute('role', 'dialog');box.setAttribute('aria-label', 'Parameteransicht ' + node.name);
    const head = el('div', 't-ndv-head'), title = el('input');title.value = name;title.setAttribute('aria-label', 'Knotenname');title.oninput = ()=>{name = title.value;};
    const msg = el('p', 't-wf-message');msg.hidden = true;msg.setAttribute('role', 'alert');
    const cols = el('div', 't-ndv-cols'), left = el('div', 't-ndv-col'), mid = el('div', 't-ndv-col t-ndv-mid'), right = el('div', 't-ndv-col');
    const close = ()=>{box.remove();if(o.onClose)o.onClose();};
    head.append(title, button('Übernehmen', apply, 't-wf-primary'), button('Schließen', close));head.lastChild.setAttribute('aria-label', 'Parameteransicht schließen');
    cols.append(left, mid, right);box.append(head, msg, cols);o.host.append(box);

    function note(text){msg.textContent = text;msg.hidden = !text;msg.classList.toggle('bad', !!text);}
    function apply(){
      try{
        check(kind, work);
        if(name !== node.name && !name.trim()) throw new Error('Der Name darf nicht leer sein.');
        o.apply(name, work);close();
      }catch(e){note(e.message);}
    }
    function refresh(){renderLeft();renderRight();}
    function renderLeft(){
      left.replaceChildren(el('h3', '', 'Eingabe'));
      const sim = simulate(Object.assign({}, doc, {nodes: doc.nodes.map(n=>n === node ? Object.assign({}, n, {parameters: work}) : n)}), sample), mine = sim.get(node.name);
      if(kind === 'manualTrigger'){
        const ta = el('textarea');ta.rows = 6;ta.value = JSON.stringify(sample, null, 2);ta.setAttribute('aria-label', 'Beispieldaten (JSON)');
        ta.onchange = ()=>{try{const v = JSON.parse(ta.value);if(!v || typeof v !== 'object' || Array.isArray(v))throw new Error('Beispieldaten müssen ein JSON-Objekt sein.');sample = v;if(o.setSample)o.setSample(v);note('');refresh();}catch(e){note(e.message);}};
        left.append(el('p', 't-wf-hint', 'Beispieldaten für die Vorschau. Beim echten Lauf kommen die Eingaben aus dem Lauf-Formular.'), ta);return;
      }
      const ups = upstream(doc, node);
      if(!ups.length){left.append(el('p', 't-wf-hint', 'Dieser Knoten hat noch keinen Vorgänger. Verbinde ihn, dann erscheinen hier die Eingabedaten.'));return;}
      left.append(el('p', 't-wf-hint', 'Von: ' + ups.map(u=>u.from).join(', ') + ' · Feld anklicken, um es als Ausdruck ins zuletzt gewählte Wertfeld einzusetzen.'));
      if(!mine || !mine.input){left.append(el('p', 't-wf-hint', 'Für diesen Weg gibt es mit den Beispieldaten keine Eingabe.'));return;}
      const list = el('div', 't-ndv-fields');
      Object.entries(mine.input).forEach(([k, v])=>{const b = button('', ()=>{if(focusInput){focusInput.inp.value = k;focusInput.expr.checked = true;focusInput.inp.dispatchEvent(new Event('input', {bubbles: true}));}});b.append(el('strong', '', k), el('span', '', ' ' + show(v)));b.title = 'Als $json.' + k + ' einsetzen';b.setAttribute('aria-label', 'Feld ' + k + ' einsetzen');list.append(b);});
      left.append(list);
    }
    function renderRight(){
      right.replaceChildren(el('h3', '', 'Ausgabe'), el('p', 't-wf-hint', 'Vorschau mit Beispieldaten, lokal berechnet. Nicht das Ergebnis eines Laufs der Engine.'));
      const sim = simulate(Object.assign({}, doc, {nodes: doc.nodes.map(n=>n === node ? Object.assign({}, n, {parameters: work}) : n)}), sample), mine = sim.get(node.name);
      if(!mine){right.append(el('p', 't-wf-hint', 'Für diesen Knoten gibt es mit den Beispieldaten keine Vorschau (kein Weg vom Auslöser).'));return;}
      if(!mine.outs){right.append(el('p', 't-wf-hint', 'Nicht vorab berechenbar.'));return;}
      mine.outs.forEach((data, i)=>{
        const label = kind === 'if' ? (i === 0 ? 'Ja-Weg' : 'Nein-Weg') : 'Ergebnis';
        const pre = el('pre', 't-ndv-out');pre.setAttribute('aria-label', label);pre.textContent = data === null ? 'kein Eintrag auf diesem Weg' : JSON.stringify(data, null, 2);
        right.append(el('h4', '', label), pre);
      });
    }
    function valueInput(initial, onChange, label){
      const wrap = el('div', 't-ndv-value'), inp = el('input'), expr = el('input');expr.type = 'checkbox';
      const isExpr = typeof initial === 'string' && PATH.test(initial);
      inp.value = isExpr ? initial.replace(/^=\{\{\s*\$json\./, '').replace(/\s*\}\}$/, '') : show(initial);expr.checked = isExpr;
      inp.setAttribute('aria-label', label);expr.setAttribute('aria-label', 'Ausdruck bei ' + label);
      const emit = ()=>{onChange(expr.checked ? '={{ $json.' + inp.value.trim().replace(/^\$json\./, '') + ' }}' : inp.value);refresh();};
      inp.oninput = emit;expr.onchange = emit;inp.onfocus = ()=>{focusInput = {inp, expr};};
      const lbl = el('label', 't-ndv-expr');lbl.append(expr, el('span', '', 'Ausdruck'));wrap.append(inp, lbl);return wrap;
    }
    function renderMid(){
      mid.replaceChildren(el('h3', '', 'Parameter'));
      if(kind === 'set') setForm();
      else if(kind === 'if') ifForm();
      else if(kind === 'stickyNote') noteForm();
      else mid.append(el('p', 't-wf-hint', kind === 'manualTrigger' ? 'Der Auslöser hat keine Parameter. Die Beispieldaten stehen links.' : 'Dieser Knoten hat keine Parameter.'));
    }
    function setForm(){
      const rows = ((work.assignments = work.assignments || {assignments: []}).assignments = work.assignments.assignments || []), list = el('div', 't-ndv-rows');
      const draw = ()=>{
        list.replaceChildren();
        rows.forEach((r, i)=>{
          const line = el('div', 't-ndv-row'), n = el('input');n.value = r.name || '';n.setAttribute('aria-label', 'Feldname');n.oninput = ()=>{r.name = n.value;refresh();};
          const t = el('select');['string', 'number', 'boolean'].forEach(k=>t.append(new Option(k, k)));t.value = r.type || 'string';t.setAttribute('aria-label', 'Datentyp');t.onchange = ()=>{r.type = t.value;refresh();};
          const v = valueInput(r.value, x=>{r.value = r.type === 'number' && x !== '' && !isNaN(Number(x)) && !PATH.test(x) ? Number(x) : r.type === 'boolean' && (x === 'true' || x === 'false') ? x === 'true' : x;}, 'Wert');
          line.append(n, t, v, button('Entfernen', ()=>{rows.splice(i, 1);draw();refresh();}));list.append(line);
        });
      };
      draw();
      const keep = el('input');keep.type = 'checkbox';keep.checked = !!work.includeOtherFields;keep.setAttribute('aria-label', 'Andere Felder behalten');keep.onchange = ()=>{work.includeOtherFields = keep.checked;refresh();};
      mid.append(list, button('Feld hinzufügen', ()=>{rows.push({id: uid(), name: 'feld', value: '', type: 'string'});draw();refresh();}), field('Andere Felder behalten', keep));
    }
    function ifForm(){
      const c = (work.conditions = work.conditions || {options: {caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2}, conditions: [], combinator: 'and'});
      c.conditions = c.conditions || [];c.options = c.options || {};const rows = c.conditions, list = el('div', 't-ndv-rows');
      const draw = ()=>{
        list.replaceChildren();
        rows.forEach((r, i)=>{
          r.operator = r.operator || {type: 'string', operation: 'equals'};
          const line = el('div', 't-ndv-row'), l = valueInput(r.leftValue, x=>{r.leftValue = x;}, 'Wert 1');
          const ty = el('select');Object.keys(OPS).forEach(k=>ty.append(new Option(k, k)));ty.value = r.operator.type;ty.setAttribute('aria-label', 'Typ');
          const op = el('select');op.setAttribute('aria-label', 'Operator');
          const fill = ()=>{op.replaceChildren();OPS[ty.value].forEach(k=>op.append(new Option(OPNAME[k], k)));op.value = OPS[ty.value].includes(r.operator.operation) ? r.operator.operation : OPS[ty.value][0];r.operator = {type: ty.value, operation: op.value};};
          fill();ty.onchange = ()=>{fill();draw();refresh();};op.onchange = ()=>{r.operator = {type: ty.value, operation: op.value};draw();refresh();};
          line.append(l, ty, op);
          if(!SINGLE.includes(r.operator.operation)) line.append(valueInput(r.rightValue, x=>{r.rightValue = r.operator.type === 'number' && x !== '' && !isNaN(Number(x)) && !PATH.test(x) ? Number(x) : x;}, 'Wert 2'));
          line.append(button('Entfernen', ()=>{rows.splice(i, 1);draw();refresh();}));list.append(line);
        });
      };
      draw();
      const comb = el('select');comb.append(new Option('Alle Bedingungen (UND)', 'and'), new Option('Eine Bedingung (ODER)', 'or'));comb.value = c.combinator || 'and';comb.setAttribute('aria-label', 'Verknüpfung');comb.onchange = ()=>{c.combinator = comb.value;refresh();};
      const cs = el('input');cs.type = 'checkbox';cs.checked = c.options.caseSensitive !== false;cs.setAttribute('aria-label', 'Groß- und Kleinschreibung beachten');cs.onchange = ()=>{c.options.caseSensitive = cs.checked;refresh();};
      mid.append(list, button('Bedingung hinzufügen', ()=>{rows.push({id: uid(), leftValue: '', rightValue: '', operator: {type: 'string', operation: 'equals'}});draw();refresh();}), field('Verknüpfung', comb), field('Groß- und Kleinschreibung beachten', cs));
    }
    function noteForm(){
      const t = el('textarea');t.rows = 6;t.value = work.content || '';t.setAttribute('aria-label', 'Inhalt der Notiz');t.oninput = ()=>{work.content = t.value;};
      const w = el('input'), h = el('input');w.type = h.type = 'number';w.value = work.width || 240;h.value = work.height || 120;w.setAttribute('aria-label', 'Breite');h.setAttribute('aria-label', 'Höhe');
      w.oninput = ()=>{work.width = Number(w.value) || 240;};h.oninput = ()=>{work.height = Number(h.value) || 120;};
      mid.append(field('Inhalt', t), field('Breite', w), field('Höhe', h));
    }
    renderMid();refresh();
    title.focus();
    box.addEventListener('keydown', e=>{if(e.key === 'Escape'){e.stopPropagation();close();}});
    return {el: box, close};
  }
  root.sedraWorkflowNdv = {open, simulate, previewSet, previewIf, resolve, check, upstream, OPS};
})();
