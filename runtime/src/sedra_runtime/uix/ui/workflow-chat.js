// Das Chat-Fenster im Editor der Workflow-Darstellungen (n8n Workflows und Szenario Studio): man spricht mit SEDRA über den offenen Prozess.
// Die Sitzung ist eine Harness-Sitzung mit der Vorlage „N8N Workflow Manager“ und erscheint links unter „Sitzungen“. SEDRA bekommt mit jeder
// Frage den Stand des Prozesses (Schritte, Verbindungen, markierter Schritt) mit. SEDRA ändert den Prozess nie selbst: ein Vorschlag kommt
// als Antrag (prozess_beantragen) in den Posteingang und gilt erst nach der Freigabe. Die Antwort wird abgefragt (kein Datenstrom).
// `kontextText`, `nachrichtenVon`, `frageVon` und `kurz` sind rein; die Oberfläche (`attach`) hängt am Editor und liegt rechts auf der Fläche.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const TRENNER = '\n--- Frage ---\n';
  const MAX_KONTEXT = 3500, TAKT = 1200, WARTEN_MS = 300000;
  const ANREGUNGEN = [['Erkläre den Prozess', 'Erkläre mir diesen Prozess Schritt für Schritt in einfachen Worten.'],
                      ['Finde Lücken', 'Finde Lücken, Sackgassen und Schleifen ohne Ausweg in diesem Prozess.'],
                      ['Schlage eine Verbesserung vor', 'Schlage eine Verbesserung dieses Prozesses vor und stelle sie als Antrag.']];

  function kurz(text, max){ const t = String(text == null ? '' : text); return t.length > max ? t.slice(0, Math.max(0, max - 1)) + '…' : t; }

  // Der Stand des Prozesses als Text für das Modell (rein). doc: {name?, nodes, connections}; art(node) → Beschriftung der Art (oder null)
  function kontextText(doc, opt){
    const o = opt || {}, art = o.art || (()=>null), ausgewaehlt = o.ausgewaehlt || null;
    const nodes = (doc && doc.nodes || []).filter(n=>!/\.stickyNote$/.test(n.type || ''));
    const zeilen = ['Prozess „' + kurz(o.titel || (doc && doc.name) || 'ohne Titel', 80) + '“, ' + nodes.length + ' Schritte.'];
    nodes.forEach((n, i)=>zeilen.push((i + 1) + '. ' + kurz(n.name, 80) + ' (' + (art(n) || String(n.type || '').split('.').pop()) + ')' + (ausgewaehlt === n.id ? ' [markiert]' : '')));
    const wege = [];
    Object.keys((doc && doc.connections) || {}).forEach(von=>Object.keys(doc.connections[von] || {}).forEach(kind=>((doc.connections[von][kind]) || []).forEach((zweig, ast)=>(zweig || []).forEach(e=>{
      const wiePruefung = nodes.some(n=>n.name === von && /\.if$/.test(n.type || ''));
      wege.push(kurz(von, 60) + ' → ' + kurz(e.node, 60) + (wiePruefung ? (ast === 0 ? ' (Ja)' : ' (Nein)') : ''));
    }))));
    if(wege.length) zeilen.push('Verbindungen: ' + wege.join('; ') + '.');
    return kurz(zeilen.join('\n'), MAX_KONTEXT);
  }
  // Was an das Modell geht: Stand des Prozesses, Trenner, Frage (rein)
  function frageVon(kontext, frage){ return 'Stand des Prozesses, auf den sich die Frage bezieht (nur lesen, nicht ändern):\n' + kontext + TRENNER + String(frage || '').trim(); }
  // Verlauf der Sitzung → [{rolle, text}] ohne den Stand des Prozesses in den Fragen (rein)
  function nachrichtenVon(eintraege){
    const out = [];
    (eintraege || []).forEach(e=>{
      if(!e || typeof e !== 'object') return;
      if(e.typ === 'captain'){ const t = String(e.text || ''), i = t.indexOf(TRENNER); out.push({rolle: 'captain', text: i >= 0 ? t.slice(i + TRENNER.length) : t}); }
      else if(e.typ === 'modell' && (e.text || e.ende === 'fehler')) out.push({rolle: 'modell', text: e.text || '', fehler: e.ende === 'fehler' ? String(e.grund || 'Die Antwort ist fehlgeschlagen.') : null});
    });
    return out;
  }

  const el = (tag, cls, text)=>{ const x = document.createElement(tag); if(cls) x.className = cls; if(text !== undefined) x.textContent = text; return x; };
  const knopf = (text, fn, cls)=>{ const b = el('button', cls || '', text); b.type = 'button'; b.onclick = fn; return b; };

  // Chat an einen Editor hängen (controller: der Editor mit stage, ctx, state, fab, dead). Gibt {open, close, destroy, panel} zurück.
  function attach(c){
    let sitzung = null, laufend = false, zaehler = null, alt = [], hinweis = '', hinweisSchlecht = false, entwurf = '';
    const panel = el('aside', 't-wf-chat'); panel.hidden = true;
    panel.setAttribute('role', 'region'); panel.setAttribute('aria-label', 'Chat zum Prozess');
    const kopf = el('div', 't-wf-chat-kopf'); kopf.append(el('b', '', 'Chat zum Prozess'));
    const neu = knopf('Neue Sitzung', ()=>{ if(laufend) return; sitzung = null; alt = []; hinweis = ''; zeichne(); }); neu.title = 'Ein neues Gespräch beginnen';
    const zu = knopf('×', ()=>api.close()); zu.setAttribute('aria-label', 'Chat schließen'); zu.title = 'Chat schließen';
    kopf.append(neu, zu);
    const liste = el('div', 't-wf-chat-liste'); liste.setAttribute('aria-live', 'polite'); liste.setAttribute('aria-label', 'Gespräch');
    const anreg = el('div', 't-wf-chat-anregungen');
    const feld = el('textarea', 't-wf-chat-feld'); feld.rows = 2; feld.setAttribute('aria-label', 'Frage an SEDRA zum Prozess'); feld.placeholder = 'Frage zum Prozess …';
    const senden = knopf('Senden', ()=>absenden(), 't-wf-chat-senden'); senden.setAttribute('aria-label', 'Frage senden');
    feld.addEventListener('input', ()=>{ entwurf = feld.value; });
    feld.addEventListener('keydown', e=>{ if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); absenden(); } else if(e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); api.close(); } });
    const fuss = el('small', 't-wf-chat-fuss', 'SEDRA ändert den Prozess nie selbst: Vorschläge kommen als Antrag in den Posteingang.');
    ANREGUNGEN.forEach(([titel, text])=>anreg.append(knopf(titel, ()=>{ feld.value = text; entwurf = text; feld.focus(); }, 't-wf-chat-anregung')));
    const reihe = el('div', 't-wf-chat-reihe'); reihe.append(feld, senden);
    panel.append(kopf, liste, anreg, reihe, fuss);
    c.stage.append(panel);

    function zeichne(){
      liste.replaceChildren();
      if(!alt.length && !laufend && !hinweis) liste.append(el('p', 't-wf-chat-leer', 'Frag SEDRA zu diesem Prozess. SEDRA kennt die Schritte und Verbindungen und, wenn du einen Schritt markiert hast, auch diesen.'));
      alt.forEach(n=>{ const b = el('div', 't-wf-chat-nachricht ' + n.rolle + (n.fehler ? ' fehler' : '')); b.append(el('small', 's-muted', n.rolle === 'captain' ? 'Du' : 'SEDRA'), el('div', '', n.fehler || n.text)); liste.append(b); });
      if(laufend) liste.append(el('p', 't-wf-chat-wartet', 'SEDRA antwortet …'));
      if(hinweis) liste.append(el('p', 't-wf-chat-hinweis' + (hinweisSchlecht ? ' fehler' : ''), hinweis));
      senden.disabled = laufend; neu.disabled = laufend;
      if(liste.scrollTo) liste.scrollTo(0, liste.scrollHeight);
    }
    const api_ = (path, optionen)=>c.ctx.api(path, optionen);
    async function holen(){
      const s = await api_('/api/harness/sitzungen/' + sitzung);
      alt = nachrichtenVon(s.eintraege || []);
      return s;
    }
    async function absenden(){
      const frage = feld.value.trim();
      if(!frage || laufend) return;
      hinweis = ''; hinweisSchlecht = false; laufend = true; zeichne();
      try{
        if(!sitzung){
          const titel = 'Prozess: ' + kurz((c.state.doc && c.state.doc.name) || 'ohne Titel', 50);
          const kopfNeu = await api_('/api/harness/sitzungen', {method: 'POST', body: {vorlage: 'n8n-workflow-manager', titel}});
          sitzung = kopfNeu.id;
        }
        const art = n=>{ const P = root.sedraWorkflowProcess, m = P && P.get ? P.get(n) : null; return m && P.labels ? P.labels[m.mode] : null; };
        const kontext = kontextText(c.state.doc, {art, ausgewaehlt: c.state.selected, titel: c.state.doc && c.state.doc.name});
        const aus = await api_('/api/harness/sitzungen/' + sitzung + '/nachricht', {method: 'POST', body: {text: frageVon(kontext, frage)}});
        if(aus && aus.status === 'kein_modell'){        // die Frage bleibt im Feld, es ging nichts an die Sitzung
          laufend = false; hinweis = String(aus.grund || 'Kein Modell geladen – in der Harness ein Modell wählen.') + ' Deine Frage steht noch im Feld.'; hinweisSchlecht = true; await holen(); zeichne(); return;
        }
        feld.value = ''; entwurf = '';
        await holen();
        const ende = Date.now() + WARTEN_MS;
        while(!c.dead && !zaehler && Date.now() < ende){
          await new Promise(ok=>{ zaehler = setTimeout(()=>{ zaehler = null; ok(); }, TAKT); });
          if(c.dead) return;
          const s = await holen(); zeichne();
          if(!s.laeuft) break;
        }
        laufend = false; hinweis = '';
      }catch(err){
        laufend = false; hinweis = 'Das Gespräch ist fehlgeschlagen: ' + kurz(err && err.message || err, 160); hinweisSchlecht = true;
      }
      if(!c.dead) zeichne();
    }
    const api = {
      panel, open(vorbelegt){
        panel.hidden = false;
        if(vorbelegt){ feld.value = vorbelegt; entwurf = vorbelegt; }
        zeichne(); feld.focus();
      },
      close(){ panel.hidden = true; },
      toggle(){ if(panel.hidden) api.open(); else api.close(); },
      destroy(){ if(zaehler) clearTimeout(zaehler); zaehler = null; panel.remove(); },
      get sitzung(){ return sitzung; }
    };
    const auf = knopf('Chat', ()=>api.toggle(), 't-wf-chat-auf'); auf.setAttribute('aria-label', 'Chat zum Prozess öffnen oder schließen'); auf.title = 'Mit SEDRA über diesen Prozess sprechen';
    c.fab.append(auf);
    zeichne();
    return api;
  }

  root.sedraWorkflowChat = {attach, kontextText, frageVon, nachrichtenVon, kurz, TRENNER};
  if(typeof module !== 'undefined' && module.exports) module.exports = {kontextText, frageVon, nachrichtenVon, kurz, TRENNER};
})();
