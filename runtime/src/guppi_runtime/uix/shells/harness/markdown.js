// Harness-Shell – Markdown ohne rohes HTML (G2 §6): Überschriften, Listen, Code, Tabellen, fett/kursiv, Zitat.
// Alles wird als DOM-Knoten mit textContent gebaut – ein `<script>` im Modelltext bleibt Text. Codeblöcke bekommen einen Kopier-Knopf.
// Rein bis auf `render` (braucht document); `bloecke` prüft node.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;

  // Eine Liste (ul/ol) ab Zeile i: {art, start, punkte: [{text, inhalt: [Absatz | Code | Liste …]}]}; rein.
  // Leerzeilen zwischen Punkten trennen die Liste nicht (eine nummerierte Liste zählt weiter), eingerückte Zeilen gehören zum Punkt:
  // Fortsetzung, neuer Absatz, Codezaun oder eine Unterliste (ab zwei Leerzeichen mehr als der Punkt).
  const PUNKT = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
  const ZAUN = /^\s*(```|~~~)\s*([\w+-]*)\s*$/;
  function liste(zeilen, i){
    const n = zeilen.length;
    const m0 = zeilen[i].match(PUNKT);
    const basis = m0[1].length, geordnet = /\d/.test(m0[2]);
    const block = {art: geordnet ? 'ol' : 'ul', start: geordnet ? Number(m0[2].replace(/\D/g, '')) : 1, punkte: []};
    while(i < n){
      const m = zeilen[i].match(PUNKT);
      if(!m || m[1].length < basis || m[1].length >= basis + 2 || /\d/.test(m[2]) !== geordnet) break;
      const punkt = {text: m[3].trim(), inhalt: []};
      block.punkte.push(punkt); i++;
      while(i < n){
        let j = i; while(j < n && !zeilen[j].trim()) j++;
        if(j >= n){ i = j; break; }
        const z = zeilen[j], einzug = z.match(/^\s*/)[0].length, pm = z.match(PUNKT);
        if(einzug < basis + 2){ i = (pm ? j : i); break; }              // nächster Punkt dieser oder einer äußeren Ebene, sonst Ende der Liste
        if(pm){ const r = liste(zeilen, j); punkt.inhalt.push(r[0]); i = r[1]; continue; }
        const zaun = z.match(ZAUN);
        if(zaun){
          const code = []; i = j + 1;
          while(i < n && !zeilen[i].trim().startsWith(zaun[1])){ code.push(zeilen[i].slice(Math.min(einzug, zeilen[i].match(/^\s*/)[0].length))); i++; }
          i++; punkt.inhalt.push({art: 'code', sprache: zaun[2] || '', text: code.join('\n')}); continue;
        }
        const letzter = punkt.inhalt[punkt.inhalt.length - 1];
        if(j === i && !letzter) punkt.text += ' ' + z.trim();            // Fortsetzungszeile des Punkts
        else if(j === i && letzter.art === 'absatz') letzter.text += ' ' + z.trim();
        else punkt.inhalt.push({art: 'absatz', text: z.trim()});          // nach einer Leerzeile: ein neuer Absatz im Punkt
        i = j + 1;
      }
    }
    return [block, i];
  }

  // Text → Liste von Blöcken {art, …}; rein
  function bloecke(text){
    const zeilen = String(text || '').replace(/\r\n?/g, '\n').replace(/\t/g, '    ').split('\n');
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
      if(PUNKT.test(z)){ const r = liste(zeilen, i); out.push(r[0]); i = r[1]; continue; }
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

  // Ein Link wird nur zu einem Anker, wenn das Ziel http, https oder mailto ist; alles andere (javascript:, data:, relative Pfade) bleibt als Text stehen; rein
  function sichereUrl(u){
    try{
      const url = new URL(String(u));
      return ['http:', 'https:', 'mailto:'].indexOf(url.protocol) >= 0 ? url.href : null;
    }catch(_e){ return null; }
  }

  // Text → Teile {art: text | code | fett | kursiv | streich | link, text, url?}; rein.
  // `code`, **fett**/__fett__, *kursiv*/_kursiv_, ~~durchgestrichen~~, [Text](Adresse). _kursiv_ gilt nur zwischen Nicht-Wortzeichen (snake_case bleibt Text);
  // der Text eines Links darf fett/kursiv/durchgestrichen/Code sein, aber kein zweiter Link (tief).
  function teile(text, tief){
    const re = tief
      ? /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|~~[^~]+~~|\*[^*\s][^*]*\*|(?<![\w])_[^_\s][^_]*_(?![\w]))/g
      : /(`[^`]+`|\[[^\]\n]+\]\([^)\s]+\)|\*\*[^*]+\*\*|__[^_]+__|~~[^~]+~~|\*[^*\s][^*]*\*|(?<![\w])_[^_\s][^_]*_(?![\w]))/g;
    const out = [];
    let at = 0, hit;
    const roh = (von, bis)=>{ if(bis > von) out.push({art: 'text', text: text.slice(von, bis)}); };
    while((hit = re.exec(text))){
      const t = hit[0];
      let tok;
      if(t[0] === '`') tok = {art: 'code', text: t.slice(1, -1)};
      else if(t[0] === '['){
        const l = t.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
        const url = l && sichereUrl(l[2]);
        tok = url ? {art: 'link', text: l[1], url} : {art: 'text', text: t};          // unsicheres Ziel: der Text bleibt, wie er ist
      }
      else if(t.startsWith('**') || t.startsWith('__')) tok = {art: 'fett', text: t.slice(2, -2)};
      else if(t.startsWith('~~')) tok = {art: 'streich', text: t.slice(2, -2)};
      else tok = {art: 'kursiv', text: t.slice(1, -1)};
      roh(at, hit.index);
      out.push(tok);
      at = hit.index + t.length;
    }
    if(at < text.length) out.push({art: 'text', text: text.slice(at)});
    return out;
  }

  const ELEMENT = {code: 'code', fett: 'strong', kursiv: 'em', streich: 's'};
  function inline(el, text, tief){
    for(const t of teile(text, tief)){
      if(t.art === 'text'){ el.append(document.createTextNode(t.text)); continue; }
      if(t.art === 'link'){
        const a = document.createElement('a');
        a.href = t.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.title = t.url;
        inline(a, t.text, true); el.append(a); continue;
      }
      const n = document.createElement(ELEMENT[t.art]);
      if(t.art === 'code') n.textContent = t.text; else inline(n, t.text, true);
      el.append(n);
    }
    return el;
  }

  function kopieren(text, knopf){
    const fertig = ok=>{ knopf.textContent = ok ? 'Kopiert' : 'Nicht kopiert'; setTimeout(()=>{ knopf.textContent = 'Kopieren'; }, 1500); };
    try{ navigator.clipboard.writeText(text).then(()=>fertig(true), ()=>fertig(false)); }catch(_e){ fertig(false); }
  }

  const mk = (tag, cls)=>{ const n = document.createElement(tag); if(cls) n.className = cls; return n; };

  function knoten(b){
    {
      if(b.art === 'kopf'){ return inline(mk('h' + Math.min(6, b.stufe + 2)), b.text); }
      else if(b.art === 'absatz'){ return inline(mk('p'), b.text); }
      else if(b.art === 'zitat'){ return inline(mk('blockquote'), b.text); }
      else if(b.art === 'linie'){ return mk('hr'); }
      else if(b.art === 'ul' || b.art === 'ol'){
        const l = mk(b.art);
        if(b.art === 'ol' && b.start > 1) l.start = b.start;
        b.punkte.forEach(p=>{ const li = inline(mk('li'), p.text); (p.inhalt || []).forEach(x=>{ const k = knoten(x); if(k) li.append(k); }); l.append(li); });
        return l;
      }
      else if(b.art === 'tabelle'){
        const wrap = mk('div', 'hs-md-tab'); const t = mk('table'); const kopf = mk('tr');
        b.kopf.forEach(k=>kopf.append(inline(mk('th'), k)));
        const thead = mk('thead'); thead.append(kopf); const tbody = mk('tbody');
        b.reihen.forEach(r=>{ const tr = mk('tr'); r.forEach(c=>tr.append(inline(mk('td'), c))); tbody.append(tr); });
        t.append(thead, tbody); wrap.append(t); return wrap;
      }
      else if(b.art === 'code'){
        const wrap = mk('div', 'hs-md-code'); const leiste = mk('div', 'hs-md-code-kopf');
        const sprache = mk('span'); sprache.textContent = b.sprache || 'Code';
        const knopf = mk('button', 'hs-knopf hs-klein'); knopf.type = 'button'; knopf.textContent = 'Kopieren';
        knopf.addEventListener('click', ()=>kopieren(b.text, knopf));
        leiste.append(sprache, knopf);
        const pre = mk('pre'); const code = mk('code'); code.textContent = b.text; pre.append(code);
        wrap.append(leiste, pre); return wrap;
      }
    }
    return null;
  }

  function render(text){
    const box = document.createElement('div');
    box.className = 'hs-md';
    for(const b of bloecke(text)){ const k = knoten(b); if(k) box.append(k); }
    return box;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.markdown = {bloecke, render, teile, sichereUrl};
  if(typeof module !== 'undefined' && module.exports) module.exports = {bloecke, teile, sichereUrl};
})();
