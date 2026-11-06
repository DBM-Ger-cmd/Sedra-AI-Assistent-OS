// Durchsuchbare Knoten-/Modulauswahl, nach Kategorien gegliedert. Die reine Suche (filter) ist ohne DOM testbar.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const fold = text=>String(text || '').toLocaleLowerCase('de').normalize('NFD').replace(/[̀-ͯ]/g, '');
  // items: [{label, category, hint, keywords}] -> gefiltert, nach Kategorie in Eingabereihenfolge gruppiert.
  function filter(items, query){
    const words = fold(query).split(/\s+/).filter(Boolean);
    const hit = items.filter(item=>{const hay = fold([item.label, item.category, item.hint, item.keywords].join(' '));return words.every(w=>hay.includes(w));});
    const groups = [];
    hit.forEach(item=>{
      const name = item.category || 'Weitere';
      let g = groups.find(x=>x.category === name); if(!g){g = {category: name, items: []};groups.push(g);}
      g.items.push(item);
    });
    return groups;
  }
  function open(options){
    const host = options.host, opener = document.activeElement;
    const box = document.createElement('section'); box.className = 't-wf-picker'; box.setAttribute('role', 'dialog'); box.setAttribute('aria-label', options.title || 'Knoten hinzufügen');
    const input = document.createElement('input'); input.type = 'search'; input.placeholder = 'Suchen …'; input.setAttribute('aria-label', 'Knoten suchen');
    const list = document.createElement('div'); list.className = 't-wf-picker-list'; list.setAttribute('role', 'listbox');
    box.append(input, list); host.append(box);
    let rows = [], active = 0, closed = false;
    function shut(){if(closed)return;closed = true;box.remove();if(opener && opener.isConnected && opener.focus)opener.focus();}
    function pick(item){shut();options.onPick(item);}
    function mark(){rows.forEach((r, i)=>{r.b.classList.toggle('active', i === active);r.b.setAttribute('aria-selected', String(i === active));});}
    function render(){
      list.replaceChildren(); rows = [];
      const groups = filter(options.items, input.value);
      if(!groups.length){const e = document.createElement('p'); e.className = 't-wf-picker-empty'; e.textContent = 'Keine Treffer.'; list.append(e); return;}
      groups.forEach(g=>{
        const h = document.createElement('div'); h.className = 't-wf-picker-cat'; h.textContent = g.category; list.append(h);
        g.items.forEach(item=>{
          const b = document.createElement('button'); b.type = 'button'; b.className = 't-wf-picker-item'; b.setAttribute('role', 'option');
          const t = document.createElement('span'); t.textContent = item.label; b.append(t);
          if(item.hint){const s = document.createElement('small'); s.textContent = item.hint; b.append(s);}
          if(item.disabled){b.setAttribute('aria-disabled', 'true');b.classList.add('disabled');b.onclick = ()=>{};}else b.onclick = ()=>pick(item);
          rows.push({b, item}); list.append(b);
        });
      });
      active = Math.min(active, rows.length - 1); mark();
    }
    input.addEventListener('input', ()=>{active = 0;render();});
    box.addEventListener('keydown', event=>{
      if(event.key === 'Escape'){event.stopPropagation();shut();}
      else if(event.key === 'ArrowDown' && rows.length){event.preventDefault();active = (active + 1) % rows.length;mark();rows[active].b.scrollIntoView({block: 'nearest'});}
      else if(event.key === 'ArrowUp' && rows.length){event.preventDefault();active = (active - 1 + rows.length) % rows.length;mark();rows[active].b.scrollIntoView({block: 'nearest'});}
      else if(event.key === 'Enter' && event.target === input && rows[active] && !rows[active].item.disabled){event.preventDefault();pick(rows[active].item);}
    });
    render(); input.focus();
    return {el: box, close: shut};
  }
  root.sedraWorkflowPicker = {open, filter};
})();
