// Harness-Shell – Markdown ohne rohes HTML (G2 §6): Überschriften, Listen, Code, Tabellen, fett/kursiv, Zitat.
// Alles wird als DOM-Knoten mit textContent gebaut – ein `<script>` im Modelltext bleibt Text. Codeblöcke bekommen einen Kopier-Knopf.
// Rein bis auf `render` (braucht document); `bloecke` prüft node.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;

  // Text → Liste von Blöcken {art, …}; rein
  function bloecke(text){
    const zeilen = String(text || '').replace(/\r\n?/g, '\n').split('\n');
    const out = [];
    let i = 0;
    while(i < zeilen.length){
      const z = zeilen[i];
      const zaun = z.match(/^\s*(```|~~~)\s*([\w+-]*)\s*$/);
      if(zaun){
        const code = []; i++;
        while(i < zeilen.length && !zeilen[i].trim().startsWith(zaun[1])){ code.push(zeilen[i]); i++; }
        out.push({art: 'code', sprache: zaun[2] || '', text: code.join('\n')}); i++; continue;
      }
      if(!z.trim()){ i++; continue; }
      const h = z.match(/^(#{1,6})\s+(.*)$/);
      if(h){ out.push({art: 'kopf', stufe: h[1].length, text: h[2].replace(/\s+#+\s*$/, '')}); i++; continue; }
      if(/^\s*([-*_])(\s*\1){2,}\s*$/.test(z)){ out.push({art: 'linie'}); i++; continue; }
      if(/^\s*\|.*\|\s*$/.test(z) && i + 1 < zeilen.length && /^\s*\|?\s*:?-{2,}/.test(zeilen[i + 1])){
        const zelle = s=>s.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(x=>x.trim());
        const kopf = zelle(z); const reihen = []; i += 2;
        while(i < zeilen.length && /^\s*\|.*\|\s*$/.test(zeilen[i])){ reihen.push(zelle(zeilen[i])); i++; }
        out.push({art: 'tabelle', kopf, reihen}); continue;
      }
      const liste = z.match(/^\s*([-*+]|\d+[.)])\s+(.*)$/);
      if(liste){
        const geordnet = /\d/.test(liste[1]); const punkte = [];
        while(i < zeilen.length){
          const m = zeilen[i].match(/^\s*([-*+]|\d+[.)])\s+(.*)$/);
          if(m && /\d/.test(m[1]) === geordnet){ punkte.push(m[2]); i++; }
          else if(zeilen[i].trim() && /^\s{2,}/.test(zeilen[i]) && punkte.length){ punkte[punkte.length - 1] += ' ' + zeilen[i].trim(); i++; }
          else break;
        }
        out.push({art: geordnet ? 'ol' : 'ul', punkte}); continue;
      }
      if(/^\s*>/.test(z)){
        const teile = [];
        while(i < zeilen.length && /^\s*>/.test(zeilen[i])){ teile.push(zeilen[i].replace(/^\s*>\s?/, '')); i++; }
        out.push({art: 'zitat', text: teile.join(' ')}); continue;
      }
      const absatz = [];
      while(i < zeilen.length && zeilen[i].trim() && !/^(#{1,6}\s|\s*```|\s*~~~|\s*([-*+]|\d+[.)])\s|\s*>)/.test(zeilen[i])){ absatz.push(zeilen[i].trim()); i++; }
      if(!absatz.length){ absatz.push(z.trim()); i++; }
      out.push({art: 'absatz', text: absatz.join(' ')});
    }
    return out;
  }

  // `code`, **fett**, *kursiv* – als Knoten; alles andere bleibt Text
  function inline(el, text){
    const re = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*\s][^*]*\*)/g;
    let at = 0, m;
    while((m = re.exec(text))){
      if(m.index > at) el.append(document.createTextNode(text.slice(at, m.index)));
      const t = m[0];
      let n;
      if(t[0] === '`'){ n = document.createElement('code'); n.textContent = t.slice(1, -1); }
      else if(t.startsWith('**') || t.startsWith('__')){ n = document.createElement('strong'); n.textContent = t.slice(2, -2); }
      else { n = document.createElement('em'); n.textContent = t.slice(1, -1); }
      el.append(n); at = m.index + t.length;
    }
    if(at < text.length) el.append(document.createTextNode(text.slice(at)));
    return el;
  }

  function kopieren(text, knopf){
    const fertig = ok=>{ knopf.textContent = ok ? 'Kopiert' : 'Nicht kopiert'; setTimeout(()=>{ knopf.textContent = 'Kopieren'; }, 1500); };
    try{ navigator.clipboard.writeText(text).then(()=>fertig(true), ()=>fertig(false)); }catch(_e){ fertig(false); }
  }

  function render(text){
    const box = document.createElement('div');
    box.className = 'hs-md';
    const mk = (tag, cls)=>{ const n = document.createElement(tag); if(cls) n.className = cls; return n; };
    for(const b of bloecke(text)){
      if(b.art === 'kopf'){ box.append(inline(mk('h' + Math.min(6, b.stufe + 2)), b.text)); }
      else if(b.art === 'absatz'){ box.append(inline(mk('p'), b.text)); }
      else if(b.art === 'zitat'){ box.append(inline(mk('blockquote'), b.text)); }
      else if(b.art === 'linie'){ box.append(mk('hr')); }
      else if(b.art === 'ul' || b.art === 'ol'){ const l = mk(b.art); b.punkte.forEach(p=>l.append(inline(mk('li'), p))); box.append(l); }
      else if(b.art === 'tabelle'){
        const wrap = mk('div', 'hs-md-tab'); const t = mk('table'); const kopf = mk('tr');
        b.kopf.forEach(k=>kopf.append(inline(mk('th'), k)));
        const thead = mk('thead'); thead.append(kopf); const tbody = mk('tbody');
        b.reihen.forEach(r=>{ const tr = mk('tr'); r.forEach(c=>tr.append(inline(mk('td'), c))); tbody.append(tr); });
        t.append(thead, tbody); wrap.append(t); box.append(wrap);
      }
      else if(b.art === 'code'){
        const wrap = mk('div', 'hs-md-code'); const leiste = mk('div', 'hs-md-code-kopf');
        const sprache = mk('span'); sprache.textContent = b.sprache || 'Code';
        const knopf = mk('button', 'hs-knopf hs-klein'); knopf.type = 'button'; knopf.textContent = 'Kopieren';
        knopf.addEventListener('click', ()=>kopieren(b.text, knopf));
        leiste.append(sprache, knopf);
        const pre = mk('pre'); const code = mk('code'); code.textContent = b.text; pre.append(code);
        wrap.append(leiste, pre); box.append(wrap);
      }
    }
    return box;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.markdown = {bloecke, render};
  if(typeof module !== 'undefined' && module.exports) module.exports = {bloecke};
})();
