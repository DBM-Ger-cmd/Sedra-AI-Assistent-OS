// Paperclip-Shell – die Kopfzeile (Entwurf D, Spec §5.1/§5.2).
// Titel der Seite, „Zurück“, die Verben des Werkstücks, und ein Suchfeld. Das Suchfeld ist die Ortskunde (ui/places.js),
// kein zweites Gespräch: ein Ort öffnet sich, ein Auftrag oder eine Frage wandert in die Schublade – gesendet wird nur dort
// (Regel 1: ein Eingabefeld, das an SEDRA schickt).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  function makeTopbar(host, shell){
    let title, back, verbs, input, results;

    function build(){
      host.replaceChildren();
      back = d().el('button', 's-btn pc-back', '‹ Zurück');
      back.onclick = ()=>shell.pages.back();
      title = d().el('h1', null, 'Dashboard');
      verbs = d().el('div', 'pc-verbs'); verbs.dataset.verbs = '';              // Vertragsmarke für die Abnahme
      const spacer = d().el('span', 'pc-spacer');
      const search = d().el('div', 'pc-search');
      input = d().el('input');
      input.placeholder = 'Ort suchen oder SEDRA etwas sagen …  Strg+K';
      input.setAttribute('aria-label', 'Ort suchen');
      results = d().el('div', 'pc-search-results');
      results.hidden = true;
      search.append(input, results);
      input.oninput = ()=>draw();
      input.onkeydown = e=>{
        if(e.key === 'Enter'){ e.preventDefault(); choose(0); }
        else if(e.key === 'Escape'){ close(); input.blur(); }
      };
      input.onfocus = ()=>draw();
      // Stufe 6 (S6-E1): Rekorder und Umschalter rechts in der Kopfleiste, nicht schwebend über der Seite
      const platz = d().el('div', 'pc-sx-platz');
      host.append(back, title, verbs, spacer, search, platz);        // der Weg zum Gespräch ist der Knopf rechts unten – einer reicht
      if(root.sedraWechsel && root.sedraWechsel.inLeiste) root.sedraWechsel.inLeiste(platz);
      document.addEventListener('mousedown', e=>{ if(!search.contains(e.target)) close(); });
    }

    // Die Zeilen unter dem Suchfeld: Orte zuerst, wenn der Text wie Navigation aussieht; sonst „an SEDRA“ zuerst
    function draw(){
      const rows = root.sedraPlaces.paletteRows(input.value).slice(0, 8);
      results.replaceChildren();
      rows.forEach((r, i)=>{
        const row = d().el('div', 'pc-search-row' + (i === 0 ? ' on' : ''));
        row.append(d().el('b', null, r.label), d().el('small', null, r.hint || ''));
        d().clickable(row, ()=>choose(i));
        results.append(row);
      });
      results.hidden = !rows.length;
      results.rows = rows;
    }

    function choose(i){
      const r = (results.rows || [])[i];
      if(!r) return;
      close();
      if(r.object){ shell.openObject(r.object); input.value = ''; return; }
      // kein Ort: in die Schublade damit, dort wird gesendet
      shell.handTo(input.value);
      input.value = '';
    }

    function close(){ results.hidden = true; }
    function focus(){ input.focus(); input.select(); draw(); }

    function setPage(page, history){
      title.textContent = page.object.title || page.object.type;
      back.disabled = history.length < 2;
      verbs.replaceChildren();
      shell.pages.actions().forEach(a=>{
        verbs.append(d().button(a.label, async()=>{ await a.run(); setPage(page, history); }));
      });
    }

    return {build, setPage, focus, close, isOpen: ()=>!results.hidden};
  }

  root.sedraPcTopbar = {makeTopbar};
})();
