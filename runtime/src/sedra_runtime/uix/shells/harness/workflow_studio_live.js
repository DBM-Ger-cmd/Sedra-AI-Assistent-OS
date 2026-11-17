// Harness-Shell, Workflow Studio: Live & Debugger – der Notaus (STOPP), die Läufe und der Lauf zur Freigabe. Teil von workflow_studio.js.
// Dieselben Verben wie der Editor (fabrik_stopp, fabrik_status, fabrik_freigeben, fortsetzen, abbrechen). Kein Takt: der Stand wird
// bei jeder Anzeige und per Knopf gelesen.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const G = root.sedraHarness.workflow_studio_geteilt;
  const d = G.d, luecken = G.luecken;
  const TAKT = 4000;

  // Der Notaus-Bericht in einem Satz (wie ui/workflow-notaus.js), rein.
  function berichtText(b){
    const n = x=>(x || []).length, t = [];
    t.push(n(b && b.laeufe) + (n(b && b.laeufe) === 1 ? ' Lauf gestoppt' : ' Läufe gestoppt'));
    t.push(n(b && b.aufgaben) + (n(b && b.aufgaben) === 1 ? ' Aufgabe zurückgenommen' : ' Aufgaben zurückgenommen'));
    if(b && b.bau) t.push('Bau-Lauf beendet');
    if(n(b && b.antworten)) t.push(n(b.antworten) + (n(b.antworten) === 1 ? ' Antwort abgebrochen' : ' Antworten abgebrochen'));
    const f = (b && b.fehler) || [];
    return 'Fabrik angehalten: ' + t.join(', ') + '.' + (f.length ? ' Nicht alles ließ sich stoppen (' + f.length + '): ' + f.slice(0, 2).join('; ') : '');
  }

  // Der Notaus (STOPP) im Live & Debugger: dieselben Verben wie der rote Knopf des Editors. Anhalten braucht keine Rückfrage;
  // das Freigeben fragt noch einmal nach. Der Stand wird alle paar Sekunden gelesen.
  function baueNotaus(api){
    const box = d().el('section', 'hs-ws-notaus'); box.setAttribute('aria-label', 'Notaus der Fabrik');
    const stopp = d().el('button', 'hs-ws-stopp', '■ STOPP'); stopp.type = 'button';
    stopp.setAttribute('aria-label', 'Fabrik anhalten (Notaus)');
    stopp.title = 'Hält die Fabrik sofort an: Läufe stoppen, Aufgaben zurücknehmen, nichts startet neu';
    const stand = d().el('p', 'hs-ws-hinweis', 'Stand wird gelesen …');
    const meldung = d().el('p', 'hs-ws-hinweis');
    const frei = d().el('button', 'hs-ws-knopf', 'Fabrik freigeben …'); frei.type = 'button'; frei.hidden = true;
    const rueckfrage = d().el('div', 'hs-ws-knoepfe'); rueckfrage.hidden = true;
    const ja = d().el('button', 'hs-ws-knopf primary', 'Ja, freigeben'); ja.type = 'button';
    const nein = d().el('button', 'hs-ws-knopf', 'Abbrechen'); nein.type = 'button';
    rueckfrage.append(d().el('span', 'hs-ws-hinweis', 'Wirklich freigeben? Danach darf die Fabrik wieder starten.'), ja, nein);
    box.append(stand, stopp, meldung, frei, rueckfrage);
    let angehalten = false, arbeitet = false, standLaedt = false, aktionsStand = 0;
    const verb = (name, args)=>api('/api/actions', {method: 'POST', body: {type: 'workflow', id: null, verb: name, args: args || {}}}).then(out=>out.result || out);
    function zeichnen(){
      stand.textContent = angehalten ? 'FABRIK ANGEHALTEN – es startet nichts Neues.' : 'Die Fabrik ist freigegeben. Der Notaus hält alle Läufe sofort an.';
      frei.hidden = !angehalten; stopp.disabled = arbeitet;
    }
    async function lesenStand(){
      if(document.hidden || !box.isConnected || box.offsetParent === null) return;   // in einem versteckten Modus nicht abfragen
      if(standLaedt || arbeitet) return;standLaedt=true;const version=aktionsStand;
      try{ const r = await verb('fabrik_status'); if(version===aktionsStand){angehalten = !!r.angehalten;zeichnen();} }
      catch(err){ stand.textContent = 'Stand nicht lesbar: ' + (err.message || err); }
      finally{standLaedt=false;}
    }
    stopp.onclick = async()=>{
      if(arbeitet) return; arbeitet = true;aktionsStand++;zeichnen(); meldung.textContent = '';
      try{ const r = await verb('fabrik_stopp'); meldung.textContent = berichtText(r); angehalten = true; }
      catch(err){ meldung.textContent = 'Das Anhalten ist fehlgeschlagen: ' + String(err.message || err).slice(0, 120) + ' – noch einmal drücken.'; }
      finally{ arbeitet = false; zeichnen(); }
    };
    frei.onclick = ()=>{ rueckfrage.hidden = false; frei.hidden = true; ja.focus(); };
    nein.onclick = ()=>{ rueckfrage.hidden = true; frei.hidden = false; };
    ja.onclick = async()=>{
      if(arbeitet) return; arbeitet = true;aktionsStand++;ja.disabled = true;
      try{ await verb('fabrik_freigeben'); angehalten = false; meldung.textContent = 'Die Fabrik ist wieder freigegeben.'; rueckfrage.hidden = true; }
      catch(err){ meldung.textContent = 'Das Freigeben ist fehlgeschlagen: ' + String(err.message || err).slice(0, 120); }
      finally{ arbeitet = false; ja.disabled = false; zeichnen(); }
    };
    lesenStand();
    const timer=setInterval(lesenStand,TAKT);
    return {box, aktualisieren: lesenStand, abbauen(){clearInterval(timer);box.replaceChildren();}};
  }

  // Der Lauf im Live & Debugger: zeigt den Workflow, den der Startassistent zuletzt gestartet hat, und legt ihn zur Freigabe vor.
  // Den Lauf selbst startet erst die Freigabe (Verb starten, mit Gate). Ohne gewählten Workflow bleibt der Knopf aus.
  function baueLauf(api){
    const box = d().el('section', 'hs-ws-lauf'); box.setAttribute('aria-label', 'Lauf des Workflows');
    const kontext = d().el('p', 'hs-ws-hinweis', 'Kein Workflow gewählt. Im Startassistenten einen Workflow wählen und „Starten“ drücken.');
    const knopf = d().el('button', 'hs-ws-knopf primary', 'Lauf zur Freigabe vorlegen'); knopf.type = 'button'; knopf.disabled = true;
    const meldung = d().el('p', 'hs-ws-hinweis');
    let rec = null;
    function setze(r){
      rec = r;
      if(!r){ kontext.textContent = 'Kein Workflow gewählt.'; }
      else{
        const laufbar = !!(r.execution && r.execution.executable);
        const offen = laufbar ? 0 : luecken(r.workflow).length;
        kontext.textContent = r.workflow.name + ' · Revision ' + r.revision + (laufbar ? ' · ausführbar' : offen ? ' · ' + offen + ' Schritt(e) noch offen' : ' · vollständig beschrieben');
      }
      knopf.disabled = !r; meldung.textContent = '';
    }
    knopf.onclick = async()=>{
      if(!rec) return;
      knopf.disabled = true; meldung.textContent = 'Lege den Lauf zur Freigabe vor …';
      try{
        const out = await api('/api/actions', {method: 'POST', body: {type: 'workflow', id: rec.id, verb: 'starten', args: {revision: rec.revision, inputs: {}}}});
        const r = out.result || out;
        meldung.textContent = 'Lauf angelegt' + (r.id ? ' (' + r.id + ')' : '') + '. Die Freigabe erscheint im Posteingang; danach läuft er hier weiter.';
      }catch(err){ meldung.textContent = 'Der Lauf wurde nicht angelegt: ' + String(err.message || err).slice(0, 160); }
      finally{ knopf.disabled = !rec; }
    };
    box.append(kontext, knopf, meldung);
    return {box, setze, abbauen(){ box.replaceChildren(); }};
  }

  // Die Läufe im Live & Debugger: alle Läufe der gespeicherten Workflows, Einzelansicht mit Schritten, Warteanzeige und Ergebnis,
  // und die beiden Wege aus einem Lauf: nach der Freigabe weiterlaufen lassen (Verb fortsetzen) oder beenden (Verb abbrechen).
  // Die Verben und Felder entsprechen dem Editor. Liest alle 4 Sekunden, nur solange der Modus sichtbar ist.
  function baueLaeufe(api,options={}){
    const box = d().el('section', 'hs-ws-laeufe'); box.setAttribute('aria-label', 'Läufe');
    const kopf = d().el('div', 'hs-ws-knoepfe');
    const aktualisieren = d().el('button', 'hs-ws-knopf', 'Aktualisieren'); aktualisieren.type = 'button';
    kopf.append(d().el('h4', 'hs-ws-karten-titel', 'Läufe'), aktualisieren);
    const stand = d().el('p', 'hs-ws-hinweis', 'Lade die Läufe …');
    const liste = d().el('div', 'hs-ws-liste');
    const detail = d().el('div', 'hs-ws-karte'); detail.hidden = true;
    const suche = d().el('input','hs-ws-eingabe'); suche.type='search';suche.placeholder='Läufe nach Name oder Kennung suchen …';suche.setAttribute('aria-label','Läufe suchen');
    const filter = d().el('select','hs-ws-wahl');filter.setAttribute('aria-label','Laufstatus filtern');
    [['','Alle Zustände'],['PAUSED','Pausiert'],['COMPLETE','Abgeschlossen'],['EXECUTE','In Ausführung'],['CAPTAIN_REVIEW','Freigabe erforderlich'],['FAILED','Fehlgeschlagen']].forEach(([wert,label])=>filter.append(new Option(label,wert)));
    const werkzeuge = d().el('div','hs-ws-knoepfe');werkzeuge.append(suche,filter);
    detail.className='hs-ws-debug-detail';
    if(options.shared){const history=d().el('details','hs-ws-laufhistorie');history.append(d().el('summary','','Andere Läufe / Suche'),werkzeuge,stand,liste);box.append(kopf,history,detail);}else box.append(kopf,werkzeuge,stand,liste,detail);
    stand.setAttribute('role','status');
    let gewaehlt = null, daten = [], debuggerAnsicht = null, tot = false, anfrage = 0, letzterStand = '', laedt = false;
    function filtern(){
      const query=suche.value.trim().toLocaleLowerCase('de');
      let anzahl=0;
      Array.from(liste.children).forEach((zeile,i)=>{
        const r=daten[i];zeile.hidden=!(r.title+' '+r.id).toLocaleLowerCase('de').includes(query)||(filter.value && r.state!==filter.value);
        if(!zeile.hidden) anzahl++;
      });
      stand.textContent = daten.length ? anzahl+' von '+daten.length+' Läufen · Wähle „Untersuchen“ für Diagramm und Verlauf.' : 'Noch kein Lauf. Bereite einen Workflow im Startassistenten vor.';
    }
    suche.oninput=filtern;filter.onchange=filtern;
    const sichtbar = ()=>!document.hidden && box.isConnected && box.offsetParent !== null;
    const aktion = (verb, id)=>api('/api/actions', {method: 'POST', body: {type: 'workflow_run', id, verb, args: {}}}).then(out=>out.result || out);
    async function laden(){
      if(!sichtbar() || laedt || (options.paused && options.paused())) return;
      laedt=true;
      try{
        const data = await api('/api/objects', {method: 'POST', body: {type: 'workflow_run'}});
        if(tot) return;
        const workflowId=options.workflowId && options.workflowId();
        const laeufe = (data.items || []).filter(r=>!options.workflowId || (workflowId && r.workflow_id===workflowId));
        stand.textContent = laeufe.length ? laeufe.length + ' Lauf/Läufe.' : 'Noch kein Lauf. Starte einen Workflow im Startassistenten.';
        daten=laeufe.slice().reverse();
        liste.replaceChildren(...daten.map(r=>{
          const z = d().el('div', 'hs-ws-liste-zeile');
          const name = d().el('div', 'hs-ws-lauf-name');
          name.append(d().el('strong', '', r.title || r.id), d().el('small', 'hs-ws-hinweis', r.id));
          const status = String(r.state || '?');
          const badge = d().el('span', 'hs-ws-chip', root.sedraHarness.workflow_studio_debugger.statusText(status));
          badge.dataset.state = status.toUpperCase();
          z.append(name, badge);
          const b = d().el('button', 'hs-ws-knopf', 'Untersuchen'); b.type = 'button';b.setAttribute('aria-label','Lauf untersuchen: '+(r.title || r.id)+' · '+r.id);
          b.onclick = ()=>zeigeLauf(r.id);
          z.append(b); return z;
        }));
        filtern();
        if(options.shared && !gewaehlt && daten.length)gewaehlt=daten[0].id;
        if(gewaehlt) await zeigeLauf(gewaehlt, true);
      }catch(err){ if(!tot) stand.textContent = 'Läufe nicht geladen: ' + (err.message || err); }
      finally{laedt=false;}
    }
    async function zeigeLauf(id, leise){
      gewaehlt = id;
      const nr=++anfrage;
      try{
        const r = await api('/api/objects', {method: 'POST', body: {type: 'workflow_run', id}});
        if(tot || nr!==anfrage) return;
        const signatur=JSON.stringify(r);
        if(leise && debuggerAnsicht && letzterStand===signatur){await debuggerAnsicht.aktualisieren();return;}
        letzterStand=signatur;
        if(debuggerAnsicht) debuggerAnsicht.abbauen();
        detail.hidden = false; detail.replaceChildren();
        if(options.workflowId && r.workflow_id!==options.workflowId())throw new Error('Der Lauf gehört zu einem anderen Workflow.');
        debuggerAnsicht=root.sedraHarness.workflow_studio_debugger.baue(api,r,options);detail.append(debuggerAnsicht.box);
        const fort = d().el('button', 'hs-ws-knopf primary', 'Nach Freigabe fortsetzen'); fort.type = 'button';
        const abbr = d().el('button', 'hs-ws-knopf', 'Lauf beenden'); abbr.type = 'button';
        fort.hidden=!['CAPTAIN_REVIEW','READY','EXECUTE','VERIFY'].includes(r.state);
        abbr.hidden=!['READY','CAPTAIN_REVIEW','PAUSED','EXECUTE'].includes(r.state);
        const meldung = d().el('p', 'hs-ws-hinweis');
        const ausfuehren=async(verb)=>{fort.disabled=abbr.disabled=true;meldung.textContent='Bitte warten …';try{await aktion(verb,id);await laden();}catch(err){meldung.textContent='Aktion fehlgeschlagen: '+(err.message || err);}finally{fort.disabled=abbr.disabled=false;}};
        fort.onclick = ()=>ausfuehren('fortsetzen');
        abbr.onclick = ()=>ausfuehren('abbrechen');
        detail.append(d().el('div', 'hs-ws-knoepfe')); detail.lastChild.append(fort, abbr); detail.append(meldung);
        if(!leise) detail.scrollIntoView({block:'start',behavior:'instant'});
      }catch(err){ if(!tot && nr===anfrage && !leise){ detail.hidden = false; detail.textContent = 'Lauf nicht geladen: ' + (err.message || err); } }
    }
    aktualisieren.onclick = ()=>laden();
    laden();
    const timer=setInterval(laden,TAKT);
    return {box,oeffne:zeigeLauf,aktualisieren:laden,abbauen(){tot=true;anfrage++;clearInterval(timer);if(debuggerAnsicht)debuggerAnsicht.abbauen();box.replaceChildren();}};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.workflow_studio_live = {baueNotaus, baueLauf, baueLaeufe, berichtText};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.workflow_studio_live;
})();
