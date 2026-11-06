// Shared canvas owns no transport or state outside its supplied container.
// Zwei Darstellungen aus einer Zeichenfläche: Kacheln (n8n-Stil) und Kreismodule (Szenario-Stil).
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const NS = 'http://www.w3.org/2000/svg';
  // Maße je Darstellung: Kante des Knotens, Lage der Ausgänge (n Ausgänge, Nr.) und des Eingangs, relativ zur linken oberen Ecke.
  // Maße nach dem Vorbild des n8n-Editors (Raster 16, Knoten 6 Rasterfelder = 96)
  const TILE = {w: 96, h: 96, out: (i, n)=>[96, n === 2 ? 32 + i * 32 : 48], inn: [0, 48], pad: [90, 70, 140, 130], center: [48, 48]};
  const CIRCLE = {w: 120, h: 120, out: (i, n)=>[118, n === 2 ? 40 + i * 40 : 60], inn: [2, 60], pad: [70, 40, 130, 110], center: [60, 60]};
  function element(tag, attrs, text){
    const el = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([k, v])=>el.setAttribute(k, String(v)));
    if(text !== undefined) el.textContent = text;
    return el;
  }
  function wrap(text, max, lines){
    const out = [''];
    String(text).split(' ').forEach(word=>{
      if(out[out.length - 1] && (out[out.length - 1] + ' ' + word).length > max && out.length < lines) out.push('');
      out[out.length - 1] += (out[out.length - 1] ? ' ' : '') + word;
    });
    return out.map(line=>line.length > max + 4 ? line.slice(0, max + 3) + '…' : line);
  }
  function mount(container, state, handlers){
    const scenario = handlers.style === 'scenario', G = scenario ? CIRCLE : TILE;
    const wrapEl = document.createElement('div'); wrapEl.className = 't-wf-canvas' + (scenario ? ' scenario' : '');
    const svg = element('svg', {class: 't-wf-svg' + (scenario ? ' scenario' : ''), role: 'group', 'aria-label': scenario ? 'Szenarioansicht' : 'Workflow-Canvas'});
    const hint = document.createElement('p'); hint.className = 't-wf-hint';
    hint.textContent = handlers.readOnly ? 'Verdichtete Kernübersicht. Verbindungen fassen Zwischenschritte zusammen. Bearbeiten in der Gesamtansicht.' : 'Module ziehen, Hintergrund zum Verschieben ziehen, Mausrad zum Zoomen. Ausgang anklicken, dann Ziel wählen.';
    const controls = document.createElement('div'); controls.className = 't-wf-zoom'; controls.setAttribute('role', 'group'); controls.setAttribute('aria-label', 'Ansicht');
    [['Ansicht einpassen', '⤢', ()=>api.fit()], ['Zoom +', '+', ()=>api.zoom(1.2)], ['Zoom −', '−', ()=>api.zoom(1 / 1.2)], ['Auf Auswahl zentrieren', '◎', ()=>api.focus()], ['Aufräumen: Knoten ordnen', '⌗', ()=>{if(handlers.tidy && !handlers.readOnly)handlers.tidy();}]].forEach(([label, text, fn])=>{
      const b = document.createElement('button'); b.type = 'button'; b.className = 't-wf-zoom-btn'; b.textContent = text; b.setAttribute('aria-label', label); b.title = label; b.onclick = fn; controls.append(b);
    });
    const mini = document.createElement('div'); mini.className = 't-wf-minimap';
    const msvg = element('svg', {class: 't-wf-minimap-svg', role: 'img', 'aria-label': 'Minimap: Übersicht des ganzen Prozesses, anklicken zum Springen', preserveAspectRatio: 'xMidYMid meet'}); mini.append(msvg);
    wrapEl.append(svg, controls, mini);
    container.replaceChildren(hint, wrapEl);
    let edgeSel = null, edgeBars = [], lastDown = null, drag = null, pending = null, offset = [0, 0], zoom = 1, frame = null;
    const uid = Math.random().toString(16).slice(2), marker = 'wf-arrow-' + uid, grid = 'wf-grid-' + uid;
    function point(event){
      const pt = svg.createSVGPoint(); pt.x = event.clientX; pt.y = event.clientY;
      return pt.matrixTransform(svg.getScreenCTM().inverse());
    }
    function draw(){
      const doc = state.doc, nodes = doc.nodes;
      const minX = Math.min(0, ...nodes.map(n=>n.position[0])) - G.pad[1];
      const minY = Math.min(0, ...nodes.map(n=>n.position[1])) - G.pad[1];
      const width = Math.max(640, ...nodes.map(n=>n.position[0] - minX + G.pad[2] + 80));
      const height = Math.max(360, ...nodes.map(n=>n.position[1] - minY + G.pad[3] + 40));
      frame = {minX, minY, width, height};
      if(!drag || drag.pan) svg.setAttribute('viewBox', [minX + offset[0], minY + offset[1], width / zoom, height / zoom].join(' '));
      const defs = element('defs');
      const arrow = element('marker', {id: marker, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse'});
      arrow.append(element('path', {d: 'M 0 0 L 10 5 L 0 10 z', class: 't-wf-arrow'})); defs.append(arrow);
      const pattern = element('pattern', {id: grid, width: 16, height: 16, patternUnits: 'userSpaceOnUse'});
      pattern.append(element('circle', {cx: 1, cy: 1, r: 1, class: 't-wf-grid-dot'})); defs.append(pattern);
      svg.replaceChildren(defs);
      const view = svg.viewBox.baseVal;
      if(!scenario) svg.append(element('rect', {x: view.x, y: view.y, width: view.width, height: view.height, fill: 'url(#' + grid + ')', class: 't-wf-grid', 'pointer-events': 'none'}));
      const byName = new Map(nodes.map(n=>[n.name, n]));
      edgeBars = [];
      Object.entries(doc.connections).forEach(([source, out])=>Object.entries(out).forEach(([kind, branches])=>branches.forEach((branch, index)=>branch.forEach(edge=>{
        const a = byName.get(source), b = byName.get(edge.node); if(!a || !b) return;
        const count = a.type.endsWith('.if') ? 2 : 1, o = G.out(Math.min(index, count - 1), count);
        const gap = scenario ? 12 : 0;
        const x = a.position[0] + o[0] + gap, y = a.position[1] + o[1];
        const tx = b.position[0] + G.inn[0] - (scenario ? 14 : 0), ty = b.position[1] + G.inn[1];
        const d = Math.max(40, Math.abs(tx - x) / 2);
        const path = element('path', {d: `M ${x} ${y} C ${x + d} ${y}, ${tx - d} ${ty}, ${tx} ${ty}`, class: 't-wf-edge' + (scenario ? ' scenario' : ''), 'marker-end': scenario ? 'none' : 'url(#' + marker + ')'});
        path.append(element('title', {}, source + ' → ' + edge.node + ' (' + kind + ':' + index + ')')); svg.append(path);
        const key = source + '|' + kind + '|' + index + '|' + edge.node, chosen = edgeSel === key;
        if(chosen) path.classList.add('selected');
        if(!handlers.readOnly && handlers.edgeDelete){
          const hit = element('g', {class: 't-wf-edge-hitbox', 'aria-label': source + ' nach ' + edge.node + ' Verbindung wählen', role: 'button', tabindex: 0});
          hit.append(element('path', {d: path.getAttribute('d'), class: 't-wf-edge-hit'}), element('circle', {cx: (x + tx) / 2, cy: (y + ty) / 2, r: 9, class: 't-wf-edge-dot'}));
          const choose = event=>{event.stopPropagation();event.preventDefault();edgeSel = chosen ? null : key;draw();};
          hit.addEventListener('pointerdown', event=>event.stopPropagation());hit.addEventListener('click', choose);hit.addEventListener('keydown', event=>{if(event.key === 'Enter' || event.key === ' ')choose(event);});
          svg.append(hit);
          if(chosen){
            const mx = (x + tx) / 2, my = (y + ty) / 2, bar = element('g', {class: 't-wf-actions t-wf-edgebar', transform: `translate(${mx - 29} ${my - 13})`});
            [['plus', 'Schritt einfügen', ()=>handlers.edgeAdd && handlers.edgeAdd(source, index, edge.node)], ['trash', 'Verbindung löschen', ()=>handlers.edgeDelete(source, kind, index, edge.node)]].forEach(([icon, label, run], k)=>{
              const b = element('g', {class: 't-wf-act' + (icon === 'trash' ? ' danger' : ''), role: 'button', tabindex: 0, 'aria-label': source + ' nach ' + edge.node + ': ' + label, transform: `translate(${k * 32} 0)`});
              b.append(element('rect', {width: 26, height: 26, rx: 7, class: 't-wf-act-box'}));if(root.sedraWorkflowIcons)root.sedraWorkflowIcons.append(b, icon, 13, 13, 14);b.append(element('title', {}, label));
              const go = event=>{event.stopPropagation();event.preventDefault();edgeSel = null;run();};
              b.addEventListener('pointerdown', event=>event.stopPropagation());b.addEventListener('click', go);b.addEventListener('keydown', event=>{if(event.key === 'Enter' || event.key === ' ')go(event);});bar.append(b);
            });
            edgeBars.push(bar);
          }
        }
        if(a.type.endsWith('.if'))svg.append(element('text', {x: (x + tx) / 2, y: (y + ty) / 2 - 8, 'text-anchor': 'middle', class: 't-wf-edge-label'}, index === 0 ? 'Ja' : 'Nein'));
      }))));
      nodes.forEach((node, order)=>{
        const known = root.sedraWorkflowModel.types.some(t=>'n8n-nodes-base.' + t[0] === node.type && t[2] === node.typeVersion);
        const P = root.sedraWorkflowProcess, meta = P && P.get(node), I = root.sedraWorkflowIcons;
        const kindKey = I ? I.key(node, meta) : 'unknown';
        const g = element('g', {transform: `translate(${node.position[0]} ${node.position[1]})`, class: 't-wf-node mod-' + kindKey + (state.selected === node.id ? ' selected' : '') + (!known ? ' unsupported' : '') + (meta ? ' process ' + meta.mode : ''), tabindex: 0, role: 'button', 'aria-label': node.name});
        const subtitle = meta ? P.labels[meta.mode] : known ? (I ? I.label(kindKey) : node.type.split('.').pop()) : 'Erhalten · nicht ausführbar';
        const [cx, cy] = G.center;
        if(scenario){
          g.append(element('path', {d: 'M 8 44 A 14 14 0 0 0 8 76 Z', class: 't-wf-cap'}), element('path', {d: 'M 112 44 A 14 14 0 0 1 112 76 Z', class: 't-wf-cap'}));
          g.append(element('circle', {cx, cy, r: 50, class: 't-wf-module-ring'}));
          if(I) I.append(g, kindKey, cx, cy, 52);
          if(kindKey === 'manualTrigger' || kindKey === 'start'){const t = element('g', {class: 't-wf-trigger-mark'});t.append(element('circle', {cx: 22, cy: 96, r: 17}));if(I)I.append(t, 'bolt', 22, 96, 18);g.append(t);}
          const lines = wrap(node.name, 22, 2);
          lines.forEach((line, i)=>g.append(element('text', {x: cx, y: 142 + i * 18, 'text-anchor': 'middle', class: 't-wf-node-title'}, line)));
          const last = lines[lines.length - 1], bx = cx + last.length * 4.4 + 14, by = 142 + (lines.length - 1) * 18;
          g.append(element('rect', {x: bx - 9, y: by - 13, width: 20, height: 18, rx: 4, class: 't-wf-badge-rect'}), element('text', {x: bx + 1, y: by + 1, 'text-anchor': 'middle', class: 't-wf-badge-text'}, String(order + 1)));
          g.append(element('text', {x: cx, y: 142 + lines.length * 18 + 4, 'text-anchor': 'middle', class: 't-wf-node-type'}, subtitle));
        }else if(node.type.endsWith('.stickyNote')){
          // Haftnotiz wie im n8n-Editor: Fläche in der Größe der Parameter, Text aus `content`
          const w = Math.max(120, Math.min(600, Number(node.parameters.width) || 240)), h = Math.max(60, Math.min(500, Number(node.parameters.height) || 120));
          g.append(element('rect', {width: w, height: h, rx: 6, class: 't-wf-sticky'}));
          const per = Math.max(8, Math.floor((w - 20) / 6.6)), rows = Math.max(1, Math.floor((h - 18) / 16)), lines = [''];
          String(node.parameters.content || '').replace(/[#*_`]/g, '').split(/\s+/).forEach(wd=>{if((lines[lines.length - 1] + ' ' + wd).trim().length > per)lines.push('');lines[lines.length - 1] = (lines[lines.length - 1] + ' ' + wd).trim();});
          lines.slice(0, rows).forEach((line, i)=>g.append(element('text', {x: 10, y: 22 + i * 16, class: 't-wf-sticky-text'}, line)));
        }else{
          // Symbolsatz des Workflow-Diagramms: Oval = Start/Ende, Rechteck = Schritt, Raute = Entscheidung, Parallelogramm = Ein-/Ausgabe, Zylinder = Datenspeicher.
          // Ein Auslöser hat links die große Rundung und den Blitz davor (wie im n8n-Editor).
          const shape = meta ? meta.kind : '', trigger = !meta && kindKey === 'manualTrigger';
          if(state.selected === node.id) g.append(element('rect', {x: -6, y: -6, width: 108, height: 108, rx: 20, class: 't-wf-ring'}));
          if(shape === 'start' || shape === 'end') g.append(element('rect', {x: 0, y: 14, width: 96, height: 68, rx: 34, class: 't-wf-tile'}));
          else if(shape === 'decision') g.append(element('polygon', {points: '48,0 96,48 48,96 0,48', class: 't-wf-tile'}));
          else if(shape === 'data') g.append(element('polygon', {points: '20,14 96,14 76,82 0,82', class: 't-wf-tile'}));
          else if(shape === 'store') g.append(element('path', {d: 'M 8 24 C 8 8, 88 8, 88 24 L 88 72 C 88 88, 8 88, 8 72 Z M 8 24 C 8 40, 88 40, 88 24', class: 't-wf-tile'}));
          else if(trigger) g.append(element('path', {d: 'M 40 0 H 82 A 14 14 0 0 1 96 14 V 82 A 14 14 0 0 1 82 96 H 40 A 40 48 0 0 1 40 0 Z', class: 't-wf-tile'}));
          else g.append(element('rect', {width: 96, height: 96, rx: 14, class: 't-wf-tile'}));
          if(trigger && I){const bolt = I.append(g, 'bolt', -16, 48, 20);bolt.setAttribute('class', 't-wf-icon t-wf-bolt');}
          if(meta && meta.mode === 'automatable') g.append(element('circle', {cx: 90, cy: 6, r: 9, class: 't-wf-candidate'}), element('text', {x: 90, y: 10, 'text-anchor': 'middle', class: 't-wf-candidate-text'}, 'A'));
          if(I) I.append(g, kindKey, cx, cy, 44);
          if(!['manualTrigger', 'start'].includes(kindKey)) g.append(element('circle', {cx: 0, cy: 48, r: 4, class: 't-wf-in'}));
          const lines = wrap(node.name, 22, 2);
          lines.forEach((line, i)=>g.append(element('text', {x: cx, y: 118 + i * 16, 'text-anchor': 'middle', class: 't-wf-node-title'}, line)));
          g.append(element('text', {x: cx, y: 118 + lines.length * 16 + 2, 'text-anchor': 'middle', class: 't-wf-node-type'}, subtitle));
        }
        g.append(element('title', {}, node.name + '\n' + node.type));
        g.addEventListener('pointerdown', event=>{
          if(event.button !== 0 || event.target.classList.contains('t-wf-port') || event.target.closest('.t-wf-act, .t-wf-plus')) return;
          event.preventDefault();
          if(pending){ handlers.connect(pending.name, node.name, pending.branch); pending = null; hint.textContent = 'Verbindung angelegt.'; return; }
          const now = Date.now();
          if(lastDown && lastDown.id === node.id && now - lastDown.t < 400 && handlers.open){lastDown = null;handlers.open(node.id);}else lastDown = {id: node.id, t: now};
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
            const [px, py] = G.out(i, count);
            const port = element('circle', {cx: px, cy: py, r: scenario ? 9 : 7, class: 't-wf-port', tabindex: 0, role: 'button', 'aria-label': node.name + ' Ausgang ' + (count === 2 ? (i ? 'Nein' : 'Ja') : '0')});
            const begin = event=>{event.stopPropagation();pending = {name: node.name, branch: i};hint.textContent = 'Ziel für „' + node.name + '“ wählen (Escape bricht ab).';};
            port.addEventListener('click', begin); port.addEventListener('keydown', event=>{if(event.key === 'Enter')begin(event);});g.append(port);
          }
        }
        if(!handlers.readOnly && !node.type.endsWith('.stickyNote') && (!meta || meta.kind !== 'end')){
          // „+“ an jedem freien Ausgang: Folgeschritt anhängen (n8n und Make: der nächste Schritt entsteht direkt am Ende des letzten)
          const count = node.type.endsWith('.if') ? 2 : 1, main = (doc.connections[node.name] || {}).main || [];
          for(let i = 0; i < count; i++){
            if((main[i] || []).length) continue;
            const [px, py] = G.out(i, count), plus = element('g', {class: 't-wf-plus', role: 'button', tabindex: 0, 'aria-label': node.name + ' Folgeschritt hinzufügen'});
            const bx = px + (scenario ? 40 : 34);
            plus.append(element('path', {d: `M ${px + (scenario ? 14 : 8)} ${py} L ${bx - 14} ${py}`, class: 't-wf-plus-line'}));
            plus.append(scenario ? element('circle', {cx: bx, cy: py, r: 17, class: 't-wf-plus-box'}) : element('rect', {x: bx - 14, y: py - 14, width: 28, height: 28, rx: 7, class: 't-wf-plus-box'}));
            plus.append(element('text', {x: bx, y: py + 6, 'text-anchor': 'middle', class: 't-wf-plus-text'}, '+'));
            plus.append(element('title', {}, 'Folgeschritt hinzufügen'));
            const add = event=>{event.stopPropagation();event.preventDefault();handlers.addAfter && handlers.addAfter(node.name, i);};
            plus.addEventListener('pointerdown', event=>event.stopPropagation());plus.addEventListener('click', add);plus.addEventListener('keydown', event=>{if(event.key === 'Enter' || event.key === ' ')add(event);});
            g.append(plus);
          }
        }
        if(!handlers.readOnly && state.selected === node.id && handlers.act){
          // Schnellleiste am gewählten Knoten: Eigenschaften, Duplizieren, Löschen
          const bar = element('g', {class: 't-wf-actions', transform: `translate(${G.center[0] - 43} ${scenario ? -6 : -34})`});
          [['set', 'Eigenschaften öffnen', 'open'], ['copy', 'Duplizieren', 'duplicate'], ['trash', 'Löschen', 'delete']].forEach(([icon, label, what], k)=>{
            const b = element('g', {class: 't-wf-act' + (what === 'delete' ? ' danger' : ''), role: 'button', tabindex: 0, 'aria-label': node.name + ': ' + label, transform: `translate(${k * 30} 0)`});
            b.append(element('rect', {width: 26, height: 26, rx: 7, class: 't-wf-act-box'}));if(I)I.append(b, icon, 13, 13, 14);b.append(element('title', {}, label));
            const run = event=>{event.stopPropagation();event.preventDefault();handlers.act(what, node.id);};
            b.addEventListener('pointerdown', event=>event.stopPropagation());b.addEventListener('click', run);b.addEventListener('keydown', event=>{if(event.key === 'Enter' || event.key === ' ')run(event);});
            bar.append(b);
          });
          g.append(bar);
        }
        svg.append(g);
      });
      edgeBars.forEach(bar=>svg.append(bar));      // die Leiste einer gewählten Verbindung liegt über allem
      drawMini();
      if(handlers.drawn) handlers.drawn();
    }
    // Minimap: alle Knoten klein, dazu der sichtbare Ausschnitt. Klick oder Ziehen setzt die Mitte des Ausschnitts.
    function drawMini(){
      if(!frame) return;
      const v = svg.viewBox.baseVal;
      msvg.setAttribute('viewBox', [frame.minX, frame.minY, frame.width, frame.height].join(' '));
      msvg.replaceChildren();
      state.doc.nodes.forEach(n=>msvg.append(element('rect', {x: n.position[0], y: n.position[1], width: G.w, height: G.h, rx: 10, class: 't-wf-mini-node' + (state.selected === n.id ? ' selected' : '')})));
      msvg.append(element('rect', {x: v.x, y: v.y, width: v.width, height: v.height, class: 't-wf-mini-view'}));
    }
    let miniDrag = false;
    function jump(event){
      if(!frame) return;
      const pt = msvg.createSVGPoint(); pt.x = event.clientX; pt.y = event.clientY;
      const p = pt.matrixTransform(msvg.getScreenCTM().inverse());
      offset = [p.x - frame.width / zoom / 2 - frame.minX, p.y - frame.height / zoom / 2 - frame.minY];
      draw();
    }
    msvg.addEventListener('pointerdown', event=>{event.preventDefault();miniDrag = true;msvg.setPointerCapture(event.pointerId);jump(event);});
    msvg.addEventListener('pointermove', event=>{if(miniDrag)jump(event);});
    msvg.addEventListener('pointerup', ()=>{miniDrag = false;});
    msvg.addEventListener('pointercancel', ()=>{miniDrag = false;});
    svg.addEventListener('pointerdown', event=>{
      if(event.button !== 0 || event.target.closest('.t-wf-node'))return;
      if(edgeSel){edgeSel = null;draw();}
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
    svg.addEventListener('keydown', e=>{
      if(e.key === 'Escape'){pending = null;hint.textContent = 'Verbindung abgebrochen.';}
      if((e.key === 'Delete') && !handlers.readOnly && state.selected && handlers.act && e.target.closest && e.target.closest('.t-wf-node')){e.preventDefault();handlers.act('delete', state.selected);}
    });
    function setZoom(value){
      const previous = zoom;zoom = Math.max(0.5, Math.min(8, value));
      if(frame){offset = [offset[0] + frame.width / previous / 2 - frame.width / zoom / 2, offset[1] + frame.height / previous / 2 - frame.height / zoom / 2];}draw();
    }
    svg.addEventListener('wheel', event=>{event.preventDefault();setZoom(zoom * (event.deltaY < 0 ? 1.15 : 1 / 1.15));}, {passive: false});
    const api = {draw, zoom(value){setZoom(zoom * value);}, fit(){zoom = 1;offset = [0, 0];draw();},
      focus(){const n = state.doc.nodes.find(x=>x.id === state.selected);if(!n || !frame)return;zoom = Math.min(8, Math.max(1, frame.width / 550));offset = [n.position[0] - frame.minX - frame.width / zoom / 2 + G.center[0], n.position[1] - frame.minY - frame.height / zoom / 2 + G.center[1]];draw();},
      destroy(){container.replaceChildren();}};
    draw();
    return api;
  }
  root.sedraWorkflowCanvas = {mount};
})();
