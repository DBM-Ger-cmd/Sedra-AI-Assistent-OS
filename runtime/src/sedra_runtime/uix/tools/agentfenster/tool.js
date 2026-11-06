// Werkzeug „Agentenfenster“ (Spec 4, D4.2.5): das Gespräch mit einem Agenten, daneben seine Issues, Läufe und sein Budget.
// Die Shell öffnet ein Fenster je Agent (Stapel `pc-stack`) und mountet dieses Werkzeug je Fenster einmal: darum führt es eine
// Instanz je Container (Nachtrag N2) – der Zustand liegt in `instanzen`, nie in `this`. Der Verlauf liegt beim Server
// (`gespraech`, Spec 1); die Eingabe erscheint nur, wenn der Server das Verb `anweisen` anbietet. Kein Zeitgeber.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const V = ()=>root.sedraAgentfensterVerlauf;
  const MASCHINENRAUM = {type: 'machine', id: 'machine', title: 'Maschinenraum'};
  const POSTEINGANG = {type: 'decision', id: 'alle', title: 'Posteingang', collection: true};
  const LIMIT = 50;
  const instanzen = new Map();          // Container -> Instanz

  function fehlerArt(text){
    const t = String(text || '');
    if(t.indexOf('unknown_object_type') >= 0) return 'aus';
    return t.indexOf('orchestra_busy') >= 0 ? 'belegt' : 'lesefehler';
  }

  function ergebnisSatz(out){
    if(out && (out.needs_gate || (out.result && (out.result.decision || out.result.gate_id || out.result.status === 'pending'))))
      return 'Antrag liegt im Posteingang.';
    return 'Erledigt.';
  }

  // Ein neuer Schlüssel je Anweisung: derselbe Schlüssel erzeugt beim Server nie zwei Nachrichten (Doppelklick, Wiederholung)
  function neuerSchluessel(){
    const c = root.crypto;
    if(c && typeof c.randomUUID === 'function') return c.randomUUID();
    return 'k-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);
  }

  const missing = o=>!o || o.missing || o.state === 'nicht gefunden';
  const status = a=>a.arbeitet ? 'arbeitet' : String(a.status || a.state || '');
  const istUnterarbeiter = a=>a.rolle === 'unterarbeiter' || (!a.rolle && !a.reports_to);      // der eine Agent ohne Vorgesetzten (OP-6)

  function makeInstanz(el, ctx){
    const id = String((ctx.object || {}).id || '');
    const wer = 'Agent ' + String((ctx.object || {}).title || id) + ': ';      // jedes Fenster sagt, wessen Fenster es ist – auch leer
    const s = {agent: null, fehler: null, nachrichten: [], mehr: false, gespraechFehler: null, issues: null, hinweis: null,
               entwurf: '', schluessel: null, offen: true, aelter: false, alleIssues: []};
    let running = null, again = false;
    const post = body=>ctx.api('/api/objects', {method: 'POST', body});

    // Der Agent aus der Liste (rein genug): gefunden – er; nicht gefunden – je nach `quelle` aus, ausgefallen oder „gibt es nicht mehr“
    function agentAusListe(liste){
      const hit = ((liste || {}).items || []).find(x=>String(x.id) === id);
      const z = ((liste || {}).quelle || {}).zustand;
      s.quelle = (liste || {}).quelle || null;
      if(hit){ s.agent = hit; return; }
      s.agent = null;
      if(z === 'bereit') s.agent = {type: 'agent', id, missing: true, actions: [], links: []};
      else if(z === 'fehler') throw new Error('Die Orchestrierung ist ausgefallen: ' + ((s.quelle || {}).grund || 'ohne Grund') + '.');
      else throw new Error('unknown_object_type');
    }

    async function lesen(){
      if(!s.offen) return;
      // Aus der Liste, nicht aus der Einzelansicht: die Liste trägt `quelle` und antwortet auch, wenn die Orchestrierung aus ist
      try{ agentAusListe(await post({type: 'agent'})); s.fehler = null; }
      catch(err){ s.agent = null; s.fehler = err.message || String(err); }
      if(s.agent && !missing(s.agent)){
        const [g, i] = await Promise.all([post({type: 'gespraech', agent: id, limit: LIMIT}).then(x=>({x}), e=>({e})),
                                          post({type: 'issue'}).then(x=>({x}), e=>({e}))]);
        if(g.e){ s.gespraechFehler = g.e.message || String(g.e); }
        else{ s.gespraechFehler = null; s.nachrichten = V().mergeMessages(s.nachrichten, g.x.items || []); if(!s.aelter) s.mehr = !!g.x.mehr; }      // nach „Ältere laden“ zählt dessen Antwort
        s.issues = i.e ? null : ((i.x.items || []).filter(x=>String(x.bearbeiter || x.assignee || '') === id));
        s.alleIssues = i.e ? [] : (i.x.items || []);
      }
      zeichnen();
    }
    function schub(){
      if(running){ again = true; return running; }
      running = lesen().finally(()=>{ running = null; if(again){ again = false; schub(); } });
      return running;
    }

    async function aelter(){
      const first = s.nachrichten[0];
      if(!first) return;
      try{
        const g = await post({type: 'gespraech', agent: id, vor: first.id, limit: LIMIT});
        s.nachrichten = V().mergeMessages(g.items || [], s.nachrichten);
        s.mehr = !!g.mehr; s.aelter = true;
      }catch(err){ s.hinweis = {text: 'Ältere nicht lesbar: ' + (err.message || err), bad: true}; }
      zeichnen();
    }

    async function verb(v, args){
      if(v.confirm && !confirm(v.confirm)) return;
      try{
        const out = await ctx.api('/api/actions', {method: 'POST', body: {type: 'agent', id, verb: v.verb, args: args || {}}});
        s.hinweis = {text: (v.label || v.verb) + ': ' + ergebnisSatz(out)};
        return out;
      }catch(err){ s.hinweis = {text: err.message || String(err), bad: true}; throw err; }
      finally{ zeichnen(); }
    }

    async function senden(text){
      const t = String(text || '').trim();
      s.entwurf = text;
      if(!t){ s.hinweis = {text: 'Erst etwas schreiben – eine leere Anweisung wird nichts.', bad: true}; zeichnen(); return; }
      if(!s.schluessel) s.schluessel = neuerSchluessel();
      const v = (s.agent.actions || []).find(a=>a.verb === 'anweisen');
      try{ await verb(v, {text: t, key: s.schluessel}); }
      catch(_e){ return; }                         // abgewiesen: der Satz des Servers steht über der Eingabe, der Text bleibt
      s.entwurf = ''; s.schluessel = null;
      zeichnen();
      schub();
    }

    function abschnitt(titel){
      const box = d().el('section', 't-af-part');
      box.append(d().el('h5', 's-head', titel));
      return box;
    }

    function kopf(a){
      const box = d().el('div', 's-col t-af-head');
      const row = d().el('div', 's-row');
      const dot = d().el('i', 't-af-dot ' + status(a)); dot.setAttribute('aria-hidden', 'true');
      row.append(dot, d().el('span', null, (a.rolle || '') + (a.rolle ? ' · ' : '') + status(a)));
      const offen = Number(a.offene_entscheidungen) || 0;
      if(offen){
        row.append(d().el('span', 't-af-badge', String(offen)));
        row.append(d().button('Im Posteingang', ()=>ctx.shell.open(POSTEINGANG)));
      }
      box.append(row);
      const b = a.budget;
      if(b && typeof b.prozent === 'number'){
        const p = Math.max(0, Math.round(b.prozent));
        const wrap = d().el('div', 't-af-budget ' + (b.stufe || 'ok'));
        const track = d().el('div', 't-af-track'), fill = d().el('div', 't-af-fill');
        fill.style.width = Math.min(100, p) + '%'; track.append(fill);
        const euro = typeof b.verbraucht_eur_cent === 'number' && typeof b.grenze_eur_cent === 'number'
          ? ' · ' + (b.verbraucht_eur_cent / 100).toFixed(2).replace('.', ',') + ' / ' + (b.grenze_eur_cent / 100).toFixed(2).replace('.', ',') + ' €' : '';
        const token = typeof b.verbraucht_token === 'number' && typeof b.grenze_token === 'number'
          ? ' · ' + b.verbraucht_token.toLocaleString('de-DE') + ' / ' + b.grenze_token.toLocaleString('de-DE') + ' Token' : '';
        wrap.append(track, d().el('small', null, 'Budget ' + p + ' %' + token + euro));
        box.append(wrap);
      }else box.append(d().el('small', 's-muted', 'Budget: noch keine Daten'));
      if(istUnterarbeiter(a)) box.append(d().el('small', 's-muted', 'nimmt Anweisungen an und verteilt sie'));
      if(status(a) === 'pausiert') box.append(d().el('div', 's-note warn', 'pausiert – die Anweisung wartet bis zum Fortsetzen'));
      if(b && b.stufe === 'gestoppt') box.append(d().el('div', 's-note bad', 'Budget aufgebraucht – Entscheidung im Posteingang'));
      return box;
    }

    function nachricht(m){
      const row = d().el('div', 't-af-msg ' + (m.rolle || 'system'));
      row.dataset.msg = String(m.id);
      const head = d().el('div', 's-row s-small');
      head.append(d().el('b', null, m.rolle === 'captain' ? 'Captain' : m.rolle === 'agent' ? ((s.agent && s.agent.title) || 'Agent') : 'System'),
                  d().el('span', 's-muted', d().fmtTime(m.ts)));
      const cloud = V().cloudText(m);
      if(cloud) head.append(d().el('span', 't-af-cloud', cloud));
      row.append(head, d().el('div', 't-af-text', String(m.summary || m.text || m.title || '')));
      const st = V().statusText(m);
      if(st) row.append(d().el('small', 't-af-status ' + (m.status || m.state || ''), st));
      if(m.issue_id){ const link = d().el('span', 't-af-link s-small', 'Issue ' + m.issue_id); d().clickable(link, ()=>ctx.shell.open({type: 'issue', id: m.issue_id, title: m.issue_id})); row.append(link); }
      return row;
    }

    function gespraech(a){
      const box = abschnitt('Gespräch');
      if(s.gespraechFehler){
        if(fehlerArt(s.gespraechFehler) === 'aus') box.append(d().empty('Gespräche gibt es mit der Orchestrierung.'));
        else box.append(d().el('div', 's-note bad', 'Das Gespräch ist nicht lesbar: ' + s.gespraechFehler), d().button('Noch einmal lesen', ()=>schub()));
        return box;
      }
      if(s.mehr) box.append(d().button('Ältere laden', ()=>aelter()));
      if(!s.nachrichten.length){
        box.append(d().empty('Noch nichts gesagt. Eine Anweisung wird zur Aufgabe.'));
        box.append(d().el('small', 's-muted', 'Der Agent antwortet nicht sofort: sein Lauf braucht eine Freigabe im Posteingang.'));
      }
      V().byDay(s.nachrichten).forEach(t=>{
        box.append(d().el('div', 't-af-day', t.label));
        t.items.forEach(m=>box.append(nachricht(m)));
      });
      if(istUnterarbeiter(a)){
        const letzte = s.nachrichten.filter(m=>m.rolle === 'captain' && m.issue_id).pop();
        const teile = letzte ? (s.alleIssues || []).filter(i=>String(i.eltern_id || i.parent_id || '') === String(letzte.issue_id)) : [];
        if(teile.length){
          box.append(d().el('small', 's-muted', 'Teilaufgaben der letzten Anweisung:'));
          teile.forEach(i=>{ const l = d().el('div', 't-af-link s-small', i.title + ' (' + i.id + ')'); d().clickable(l, ()=>ctx.shell.open({type: 'issue', id: i.id, title: i.title})); box.append(l); });
        }
      }
      const anweisen = (a.actions || []).find(v=>v.verb === 'anweisen');
      if(anweisen && status(a) !== 'beendet'){
        const form = d().el('form', 's-col t-af-input');
        const input = d().el('textarea'); input.rows = 2; input.maxLength = 8000; input.placeholder = 'Anweisung …';
        input.setAttribute('aria-label', 'Anweisung an ' + (a.title || id));
        input.value = s.entwurf;
        input.oninput = ()=>{ if(input.value !== s.entwurf){ s.entwurf = input.value; s.schluessel = null; } };
        form.append(input, d().button(anweisen.label || 'Senden', ()=>senden(input.value), 'p'));
        form.onsubmit = e=>e.preventDefault();
        box.append(form);
      }
      return box;
    }

    function issues(){
      const box = abschnitt('Issues');
      if(s.issues === null) box.append(d().el('small', 's-muted', 'Issues gibt es mit der Orchestrierung.'));
      else if(!s.issues.length) box.append(d().el('small', 's-muted', 'Keine Issues bei diesem Agenten.'));
      else s.issues.forEach(i=>{
        const row = d().el('div', 's-row s-small t-af-link');
        row.append(d().el('span', null, i.title || i.id), d().el('span', 's-muted', String(i.zustand || i.state || '')));
        d().clickable(row, ()=>ctx.shell.open({type: 'issue', id: i.id, title: i.title || i.id}));
        box.append(row);
      });
      return box;
    }

    function laeufe(a){
      const box = abschnitt('Läufe');
      const list = Array.isArray(a.laeufe) ? a.laeufe
        : (s.issues || []).filter(i=>i.mission_id).map(i=>({mission_id: i.mission_id, zustand: i.zustand || i.state, titel: i.title}));
      if(!list.length) box.append(d().el('small', 's-muted', 'Noch keine Läufe.'));
      list.slice(-10).forEach(l=>{
        const row = d().el('div', 's-row s-small t-af-link');
        row.append(d().el('span', null, 'Mission ' + l.mission_id), d().el('span', 's-muted', [l.titel, l.zustand, l.ts ? d().fmtTime(l.ts) : ''].filter(Boolean).join(' · ')));
        d().clickable(row, ()=>ctx.shell.open({type: 'task', id: l.mission_id, title: l.titel || l.mission_id}));
        box.append(row);
      });
      return box;
    }

    function zeichnen(){
      if(!s.offen) return;
      const box = d().el('div', 's-col');
      if(s.hinweis) box.append(d().el('div', 's-note' + (s.hinweis.bad ? ' bad' : ''), s.hinweis.text));
      if(s.fehler){
        const art = fehlerArt(s.fehler);
        if(art === 'aus'){
          box.append(d().el('div', 's-note', wer + 'Die Orchestrierung ist ausgeschaltet (Schalter „orchestra“). Sobald sie läuft, sprichst du hier mit dem Agenten.'),
                     d().button('Maschinenraum öffnen', ()=>ctx.shell.open(MASCHINENRAUM)));
        }else box.append(d().el('div', 's-note bad', wer + (art === 'belegt' ? 'Die Datenbank ist gerade belegt.' : 'nicht lesbar: ' + s.fehler)),
                         d().button('Noch einmal lesen', ()=>schub()));
        return el.replaceChildren(box);
      }
      const a = s.agent;
      if(missing(a)){
        box.append(d().empty(wer + 'Diesen Agenten gibt es nicht mehr. Das Fenster schließt ✕ oben.'));
        return el.replaceChildren(box);
      }
      box.append(kopf(a), gespraech(a), issues(), laeufe(a));
      el.replaceChildren(box);
    }

    const inst = {
      id, schub, s,
      start(){
        el.classList.add('t-agentfenster');
        ctx.bus.on('agent.changed', e=>{ if(String(e.id) === id) schub(); });
        ctx.bus.on('issue.changed', ()=>schub());
        ctx.bus.on('budget.warning', e=>{ if(String(e.agent_id) === id) schub(); });
        ctx.bus.on('decision.pending', e=>{ if(!e.agent_id || String(e.agent_id) === id) schub(); });
        ctx.bus.on('decision.answered', ()=>schub());
        ctx.bus.on('desk.resync', ()=>schub());
        return schub();
      },
      stop(){ s.offen = false; el.classList.remove('t-agentfenster'); el.replaceChildren(); },
      // Die Verben des Agenten ohne die Eingabe: sie stehen im Kopf des Fensters (pausieren, fortsetzen, beenden …)
      actions(){
        if(!s.agent || missing(s.agent)) return [];
        return (s.agent.actions || []).filter(v=>v.verb !== 'anweisen').map(v=>({label: v.label || v.verb, run: ()=>verb(v).catch(()=>{})}));
      }
    };
    return inst;
  }

  const tool = {
    id: 'agentfenster',
    mount(el, ctx){
      const old = instanzen.get(el);
      if(old) old.stop();
      const inst = makeInstanz(el, ctx);
      instanzen.set(el, inst);
      return inst.start();
    },
    unmount(el){
      const inst = instanzen.get(el);
      if(!inst) return;
      inst.stop();
      instanzen.delete(el);
    },
    actions(el){ const inst = instanzen.get(el); return inst ? inst.actions() : []; },
    instanzen
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraAgentfensterPure = {fehlerArt, ergebnisSatz, neuerSchluessel};
  if(typeof module !== 'undefined' && module.exports) module.exports = {fehlerArt, ergebnisSatz, neuerSchluessel, tool};
})();
