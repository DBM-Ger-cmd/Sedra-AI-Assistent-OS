// Sea chart of a mission: harbour (start) → one buoy per plan step → destination; the ship sits where the mission is, a barrier marks an open gate.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.
// chartModel() is pure (mission record in, plain object out) so it can be judged with node; renderSeaChart() draws it as inline SVG.

const CHART_PHASES = ['NEW', 'UNDERSTAND', 'PLAN', 'READY', 'EXECUTE', 'VERIFY', 'COMPLETE'];

// {stops: [{id, label, state}], ship: position 0..stops-1 (float), barrier: position or null, phase, tone: 'ok'|'warn'|'bad'|'run'}
function chartModel(m){
  const mission = m && typeof m === 'object' ? m : {};
  const phase = String((mission.lifecycle || {}).phase || 'NEW');
  const steps = Array.isArray((mission.plan || {}).steps) ? mission.plan.steps : [];
  const done = Array.isArray((mission.execution || {}).results) ? mission.execution.results.length : 0;
  const pending = Array.isArray((mission.human_gates || {}).pending) ? mission.human_gates.pending.length : 0;
  const stops = [{id: 'start', label: 'Hafen', state: 'done'}];
  steps.forEach((st, i) => {
    const label = String(st.description || st.action || st.id || ('Schritt ' + (i + 1)));
    const state = phase === 'COMPLETE' || i < done ? 'done' : (i === done && (phase === 'EXECUTE' || phase === 'VERIFY' || phase === 'REWORK')) ? 'active' : 'open';
    stops.push({id: String(st.id || i + 1), label: label.length > 28 ? label.slice(0, 28) + '…' : label, state});
  });
  stops.push({id: 'goal', label: 'Ziel', state: phase === 'COMPLETE' ? 'done' : phase === 'FAILED' ? 'fail' : 'open'});
  const last = stops.length - 1;
  let ship;
  if(phase === 'COMPLETE') ship = last;
  else if(phase === 'VERIFY') ship = Math.max(0, last - 0.5);
  else if(phase === 'EXECUTE' || phase === 'REWORK' || phase === 'CANDIDATE_REVIEW') ship = Math.min(last - 0.5, Math.min(done, steps.length) + 0.5);
  else if(phase === 'FAILED') ship = Math.min(last - 0.5, Math.min(done, steps.length) + 0.5);
  else if(phase === 'PAUSED' || phase === 'CAPTAIN_REVIEW') ship = Math.min(last - 0.5, Math.min(done, steps.length) + (done ? 0.5 : 0));
  else ship = 0;                                                       // NEW, UNDERSTAND, PLAN, READY: still in the harbour
  const tone = phase === 'FAILED' ? 'bad' : phase === 'COMPLETE' ? 'ok' : (pending || phase === 'PAUSED' || phase === 'CAPTAIN_REVIEW') ? 'warn' : (phase === 'EXECUTE' || phase === 'VERIFY') ? 'run' : 'ok';
  const barrier = pending ? Math.min(last, Math.floor(ship) + 1) : null;
  return {stops, ship: Math.max(0, Math.min(last, ship)), barrier, phase, tone, pending};
}

function svgEl(tag, attrs, text){
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, String(v)));
  if(text !== undefined) e.textContent = text;
  return e;
}

// width in CSS pixels is left to the container (viewBox scales); height 72
function renderSeaChart(m){
  const model = chartModel(m);
  const n = model.stops.length, W = 600, H = 72, left = 28, right = W - 28, y = 40;
  const x = i => n > 1 ? left + (right - left) * i / (n - 1) : left;
  const svg = svgEl('svg', {viewBox: '0 0 ' + W + ' ' + H, class: 'sea-chart tone-' + model.tone, role: 'img',
    'aria-label': 'Seekarte: ' + model.stops.map(s => s.label).join(' → ') + ' · Schiff bei ' + model.phase + (model.pending ? ' · ' + model.pending + ' Freigabe(n) offen' : '')});
  svg.append(svgEl('rect', {x: 0, y: 0, width: W, height: H, rx: 6, class: 'sea'}));
  svg.append(svgEl('path', {d: 'M' + left + ' ' + y + ' L' + right + ' ' + y, class: 'route'}));
  if(model.ship > 0) svg.append(svgEl('path', {d: 'M' + left + ' ' + y + ' L' + x(model.ship) + ' ' + y, class: 'wake'}));
  model.stops.forEach((s, i) => {
    const g = svgEl('g', {class: 'stop ' + s.state, transform: 'translate(' + x(i) + ' ' + y + ')'});
    if(i === 0) g.append(svgEl('path', {d: 'M-7 6 L-7 -6 L7 -6 L7 6 Z M-9 6 L9 6', class: 'harbour'}));
    else if(i === n - 1) g.append(svgEl('path', {d: 'M0 -9 L0 9 M0 -9 L9 -5 L0 -1', class: 'flag'}));
    else g.append(svgEl('circle', {r: 5, class: 'buoy'}));
    const label = svgEl('text', {y: i % 2 ? -14 : 22, 'text-anchor': i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle', class: 'label'}, s.label);
    g.append(label); svg.append(g);
  });
  if(model.barrier !== null){
    const bx = x(model.barrier) - (right - left) / (n - 1) / 2;
    svg.append(svgEl('path', {d: 'M' + bx + ' ' + (y - 12) + ' L' + bx + ' ' + (y + 12), class: 'barrier'}));
    svg.append(svgEl('text', {x: bx, y: y - 15, 'text-anchor': 'middle', class: 'barrier-label'}, 'Freigabe'));
  }
  const shipX = model.ship === 0 ? x(0) + 18 : model.ship >= n - 1 ? x(n - 1) - 18 : x(model.ship);      // next to the harbour or the flag, not on top of it
  const ship = svgEl('g', {class: 'ship', transform: 'translate(' + shipX + ' ' + y + ')'});
  ship.append(svgEl('path', {d: 'M-9 2 L9 2 L6 7 L-6 7 Z', class: 'hull'}), svgEl('path', {d: 'M0 2 L0 -9 L6 -4 L0 -4', class: 'sail'}));
  svg.append(ship);
  return svg;
}
