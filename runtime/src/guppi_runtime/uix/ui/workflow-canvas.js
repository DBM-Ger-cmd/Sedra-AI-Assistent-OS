// Shared canvas owns no transport or state outside its supplied container.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const NS = 'http://www.w3.org/2000/svg';
  function element(tag, attrs, text){
    const el = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([k, v])=>el.setAttribute(k, String(v)));
    if(text !== undefined) el.textContent = text;
    return el;
  }
  function mount(container, state, handlers){
    const scenario = handlers.style === 'scenario';
    const svg = element('svg', {class: 't-wf-svg' + (scenario ? ' scenario' : ''), role: 'group', 'aria-label': scenario ? 'Szenarioansicht' : 'Workflow-Canvas'});
    const hint = document.createElement('p'); hint.className = 't-wf-hint';
    hint.textContent = handlers.readOnly ? 'Verdichtete Kernübersicht. Verbindungen fassen Zwischenschritte zusammen. Bearbeiten in der Gesamtansicht.' : 'Module ziehen, Hintergrund zum Verschieben ziehen, Mausrad zum Zoomen. Ausgang anklicken, dann Ziel wählen.';
    container.replaceChildren(hint, svg);
    let drag = null, pending = null, offset = [0, 0], zoom = 1, frame = null;
    const marker = 'wf-arrow-' + Math.random().toString(16).slice(2);
    function point(event){
      const pt = svg.createSVGPoint(); pt.x = event.clientX; pt.y = event.clientY;
      return pt.matrixTransform(svg.getScreenCTM().inverse());
    }
    function draw(){
      const doc = state.doc, nodes = doc.nodes;
      const minX = Math.min(0, ...nodes.map(n=>n.position[0])) - 45;
      const minY = Math.min(0, ...nodes.map(n=>n.position[1])) - 35;
      const width = Math.max(800, ...nodes.map(n=>n.position[0] - minX + 270));
      const height = Math.max(420, ...nodes.map(n=>n.position[1] - minY + (scenario ? 210 : 150)));
      frame = {minX, minY, width, height};
      if(!drag || drag.pan) svg.setAttribute('viewBox', [minX + offset[0], minY + offset[1], width / zoom, height / zoom].join(' '));
      const defs = element('defs');
      const arrow = element('marker', {id: marker, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse'});
      arrow.append(element('path', {d: 'M 0 0 L 10 5 L 0 10 z', class: 't-wf-arrow'})); defs.append(arrow);
      svg.replaceChildren(defs);
      const byName = new Map(nodes.map(n=>[n.name, n]));
      Object.entries(doc.connections).forEach(([source, out])=>Object.entries(out).forEach(([kind, branches])=>branches.forEach((branch, index)=>branch.forEach(edge=>{
        const a = byName.get(source), b = byName.get(edge.node); if(!a || !b) return;
        const x = a.position[0] + (scenario ? 156 : 220), y = a.position[1] + (scenario ? 50 : 36 + index * 22);
        const tx = b.position[0] + (scenario ? 64 : 0), ty = b.position[1] + (scenario ? 50 : 44);
        const path = element('path', {d: `M ${x} ${y} C ${x + 65} ${y}, ${tx - 65} ${ty}, ${tx} ${ty}`, class: 't-wf-edge', 'marker-end': 'url(#' + marker + ')'});
        path.append(element('title', {}, source + ' → ' + edge.node + ' (' + kind + ':' + index + ')')); svg.append(path);
        if(a.type.endsWith('.if'))svg.append(element('text', {x: (x + tx) / 2, y: (y + ty) / 2 - 8, class: 't-wf-edge-label'}, index === 0 ? 'Ja' : 'Nein'));
      }))));
      nodes.forEach(node=>{
        const known = root.sedraWorkflowModel.types.some(t=>'n8n-nodes-base.' + t[0] === node.type && t[2] === node.typeVersion);
        const P = root.sedraWorkflowProcess, meta = P && P.get(node);
        const g = element('g', {transform: `translate(${node.position[0]} ${node.position[1]})`, class: 't-wf-node' + (state.selected === node.id ? ' selected' : '') + (!known ? ' unsupported' : '') + (meta ? ' process ' + meta.mode : ''), tabindex: 0, role: 'button', 'aria-label': node.name});
        if(scenario){
          g.append(element('circle', {cx: 110, cy: 50, r: 44, class: 't-wf-module-ring'}));
          const icon = meta ? ({start: '▶', decision: '◇', end: '✓', task: meta.mode === 'manual' ? '♙' : '▤'}[meta.kind] || '·') : ({manualTrigger: '▶', set: '▤', if: '◇', noOp: '➜', stickyNote: '≡'}[node.type.split('.').pop()] || '?');
          g.append(element('text', {x: 110, y: 62, 'text-anchor': 'middle', class: 't-wf-module-icon'}, icon));
          const words = node.name.split(' '), lines = [''];words.forEach(w=>{if((lines[lines.length - 1] + w).length > 26 && lines.length < 3)lines.push('');lines[lines.length - 1] += w + ' ';});
          lines.forEach((line, i)=>g.append(element('text', {x: 110, y: 118 + i * 17, 'text-anchor': 'middle', class: 't-wf-node-title'}, line.trim())));
          g.append(element('text', {x: 110, y: 172, 'text-anchor': 'middle', class: 't-wf-node-type'}, meta ? P.labels[meta.mode] : node.type.split('.').pop()));
        }else{
          g.append(element('rect', {width: 220, height: 105, rx: meta && ['start', 'end'].includes(meta.kind) ? 35 : 12}));
          const chunks = [''];node.name.split(' ').forEach(word=>{if((chunks[chunks.length - 1] + word).length > 27 && chunks.length < 2)chunks.push('');chunks[chunks.length - 1] += word + ' ';});
          chunks.forEach((line, i)=>g.append(element('text', {x: 12, y: 24 + 17 * i, class: 't-wf-node-title'}, line)));
          g.append(element('text', {x: 12, y: 68, class: 't-wf-node-type'}, meta ? P.labels[meta.mode] : node.type.split('.').pop() + ' · v' + node.typeVersion));
          g.append(element('text', {x: 12, y: 88, class: 't-wf-node-type'}, meta ? P.labels[meta.source] : known ? 'Bearbeitbar' : 'Erhalten · nicht ausführbar'));
        }
        g.append(element('title', {}, node.name + '\n' + node.type));
        g.addEventListener('pointerdown', event=>{
          if(event.button !== 0 || event.target.classList.contains('t-wf-port')) return;
          event.preventDefault();
          if(pending){ handlers.connect(pending.name, node.name, pending.branch); pending = null; hint.textContent = 'Verbindung angelegt.'; return; }
          handlers.select(node.id);
          if(handlers.readOnly){draw();return;}
          handlers.checkpoint();
          const pt = point(event); drag = {node, x: pt.x, y: pt.y, original: node.position.slice()}; svg.setPointerCapture(event.pointerId);
        });
        g.addEventListener('keydown', event=>{
          if(['Enter', ' '].includes(event.key)){event.preventDefault();handlers.select(node.id);draw();}
          const delta = {ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, -10], ArrowDown: [0, 10]}[event.key];
          if(delta && !handlers.readOnly){event.preventDefault();handlers.checkpoint();node.position = node.position.map((v, i)=>Math.max(-100000, Math.min(100000, v + delta[i])));handlers.change();draw();}
        });
        if(!handlers.readOnly && !node.type.endsWith('.stickyNote') && (!meta || meta.kind !== 'end')){
          const count = node.type.endsWith('.if') ? 2 : 1;
          for(let i = 0; i < count; i++){
            const port = element('circle', {cx: scenario ? 154 : 220, cy: scenario ? 40 + i * 22 : 36 + i * 22, r: 8, class: 't-wf-port', tabindex: 0, role: 'button', 'aria-label': node.name + ' Ausgang ' + (count === 2 ? (i ? 'Nein' : 'Ja') : '0')});
            const begin = event=>{event.stopPropagation();pending = {name: node.name, branch: i};hint.textContent = 'Ziel für „' + node.name + '“ wählen (Escape bricht ab).';};
            port.addEventListener('click', begin); port.addEventListener('keydown', event=>{if(event.key === 'Enter')begin(event);});g.append(port);
          }
        }
        svg.append(g);
      });
    }
    svg.addEventListener('pointerdown', event=>{
      if(event.button !== 0 || event.target.closest('.t-wf-node'))return;
      const view = svg.viewBox.baseVal;
      drag = {pan: true, x: event.clientX, y: event.clientY, original: offset.slice(), sx: view.width / svg.clientWidth, sy: view.height / svg.clientHeight};
      svg.setPointerCapture(event.pointerId);
    });
    svg.addEventListener('pointermove', event=>{
      if(!drag) return;
      if(drag.pan){offset = [drag.original[0] - (event.clientX - drag.x) * drag.sx, drag.original[1] - (event.clientY - drag.y) * drag.sy];draw();return;}
      const pt = point(event);
      drag.node.position = [drag.original[0] + pt.x - drag.x, drag.original[1] + pt.y - drag.y].map(v=>Math.max(-100000, Math.min(100000, Math.round(v))));
      draw();
    });
    svg.addEventListener('pointerup', ()=>{if(drag){const changed = !drag.pan;drag = null;if(changed)handlers.change();draw();}});
    svg.addEventListener('pointercancel', ()=>{drag = null;draw();});
    svg.addEventListener('keydown', e=>{if(e.key === 'Escape'){pending = null;hint.textContent = 'Verbindung abgebrochen.';}});
    function setZoom(value){
      const previous = zoom;zoom = Math.max(0.5, Math.min(8, value));
      if(frame){offset = [offset[0] + frame.width / previous / 2 - frame.width / zoom / 2, offset[1] + frame.height / previous / 2 - frame.height / zoom / 2];}draw();
    }
    svg.addEventListener('wheel', event=>{event.preventDefault();setZoom(zoom * (event.deltaY < 0 ? 1.15 : 1 / 1.15));}, {passive: false});
    draw();
    return {draw, zoom(value){setZoom(zoom * value);}, fit(){zoom = 1;offset = [0, 0];draw();},
      focus(){const n = state.doc.nodes.find(x=>x.id === state.selected);if(!n || !frame)return;zoom = Math.min(8, Math.max(1, frame.width / 550));offset = [n.position[0] - frame.minX - frame.width / zoom / 2 + 110, n.position[1] - frame.minY - frame.height / zoom / 2 + 70];draw();},
      destroy(){container.replaceChildren();}};
  }
  root.sedraWorkflowCanvas = {mount};
})();
