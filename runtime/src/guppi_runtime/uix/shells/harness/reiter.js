// Harness-Shell – die Reiterleiste (HS-03): ein Reiter je Sitzung; „+“ öffnet eine neue, die mittlere Maustaste schließt.
// Reihenfolge und aktiver Reiter bleiben je Browser in localStorage `sedra.harness.reiter` (nur IDs, nie Inhalt).
// Eine neue Sitzung ist zuerst ein Entwurf (`neu-…`) ohne Datei; die Datei entsteht mit der ersten Nachricht.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const KEY = 'sedra.harness.reiter';
  const ID = /^S-[0-9A-F]{8}$/;
  let zaehler = 0;

  function stand(S){ return S._reiter || (S._reiter = {liste: [], aktiv: null}); }

  function speichern(S){
    const r = stand(S);
    try{ localStorage.setItem(KEY, JSON.stringify({liste: r.liste.filter(id=>ID.test(id)), aktiv: ID.test(r.aktiv || '') ? r.aktiv : null})); }catch(_e){}
  }

  function titel(S, id){
    if(String(id).startsWith('diff:')) return 'Diff ' + id.slice(5);
    if(!ID.test(id)) return 'Neue Sitzung';
    const s = S.sitzung(id);
    return (s && s.titel) || 'Ohne Titel';
  }

  function zeichnen(S){
    const r = stand(S);
    const leiste = S.el.reiter;
    const kids = r.liste.map(id=>{
      const tab = d().el('div', 'hs-tab' + (id === r.aktiv ? ' on' : ''));
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-selected', id === r.aktiv ? 'true' : 'false');
      tab.tabIndex = 0;
      tab.dataset.reiter = id;
      const s = S.sitzung(id);
      const a = S.ansichten.get(id);
      if((s && s.laeuft) || (a && a.laeuft())) tab.classList.add('laeuft');
      const name = d().el('span', 'hs-tab-name', titel(S, id));
      name.title = titel(S, id);
      const zu = d().el('button', 'hs-tab-zu', '×'); zu.type = 'button'; zu.setAttribute('aria-label', 'Reiter schließen'); zu.tabIndex = -1;
      zu.onclick = e=>{ e.stopPropagation(); schliessen(S, id); };
      tab.append(name, zu);
      tab.onclick = ()=>aktivieren(S, id);
      tab.onkeydown = e=>{ if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); aktivieren(S, id); } };
      tab.onauxclick = e=>{ if(e.button === 1){ e.preventDefault(); schliessen(S, id); } };
      tab.onmousedown = e=>{ if(e.button === 1) e.preventDefault(); };      // kein Rollen mit der mittleren Taste
      return tab;
    });
    const plus = d().el('button', 'hs-tab-plus', '+'); plus.type = 'button';
    plus.title = 'Neue Sitzung'; plus.setAttribute('aria-label', 'Neue Sitzung');
    plus.onclick = ()=>neu(S);
    leiste.replaceChildren(...kids, plus);
    const on = leiste.querySelector('.hs-tab.on');
    if(on && on.scrollIntoView) on.scrollIntoView({block: 'nearest', inline: 'nearest'});
  }

  function aktivieren(S, id){
    const r = stand(S);
    if(r.liste.indexOf(id) < 0) r.liste.push(id);
    r.aktiv = id;
    speichern(S);
    S.zeigen(id);
    zeichnen(S);
    root.sedraHarness.seite.zeichnen(S);
    root.sedraHarness.taskleiste.zeichnen(S);
  }

  function oeffnen(S, id){ aktivieren(S, id); }

  function neu(S){
    const r = stand(S);
    const leer = r.liste.find(id=>!ID.test(id) && !String(id).startsWith('diff:'));          // ein offener Entwurf genügt
    aktivieren(S, leer || ('neu-' + (++zaehler)));
    root.sedraHarness.eingabe.fokus(S);
  }

  function schliessen(S, id){
    const r = stand(S);
    const at = r.liste.indexOf(id);
    if(at < 0) return;
    r.liste.splice(at, 1);
    S.verwerfen(id);
    if(r.aktiv === id){
      r.aktiv = r.liste[Math.min(at, r.liste.length - 1)] || null;
      if(!r.aktiv){ neu(S); return; }
      S.zeigen(r.aktiv);
    }
    speichern(S);
    zeichnen(S);
    root.sedraHarness.seite.zeichnen(S);
    root.sedraHarness.taskleiste.zeichnen(S);
  }

  // Ein Entwurf wurde zur Sitzung: derselbe Reiter, neue ID
  function umbenennen(S, alt, neuId){
    const r = stand(S);
    const at = r.liste.indexOf(alt);
    if(at >= 0) r.liste[at] = neuId;
    if(r.aktiv === alt) r.aktiv = neuId;
    const a = S.ansichten.get(alt);
    if(a){ S.ansichten.delete(alt); S.ansichten.set(neuId, a); }
    speichern(S);
    zeichnen(S);
  }

  function wiederherstellen(S){
    let gemerkt = {liste: [], aktiv: null};
    try{ gemerkt = JSON.parse(localStorage.getItem(KEY) || '{}') || gemerkt; }catch(_e){}
    const da = new Set(S.sitzungen.map(s=>s.id));           // nur, was es noch gibt – sonst gäbe es 404 beim Laden
    const r = stand(S);
    r.liste = (Array.isArray(gemerkt.liste) ? gemerkt.liste : []).filter(id=>ID.test(id) && da.has(id));
    const aktiv = r.liste.indexOf(gemerkt.aktiv) >= 0 ? gemerkt.aktiv : r.liste[0];
    if(aktiv) aktivieren(S, aktiv); else neu(S);
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.reiter = {mount: S=>zeichnen(S), zeichnen, titel: S=>zeichnen(S), aktivieren, oeffnen, neu, schliessen, umbenennen,
                              wiederherstellen, aktiv: S=>stand(S).aktiv, liste: S=>stand(S).liste.slice(), KEY};
})();
