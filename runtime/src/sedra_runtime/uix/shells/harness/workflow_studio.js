// Harness-Shell: die App „Workflow Studio“ – aufgebaut wie die Vorlage SEDRA Workflow Studio v1.7: links die Navigation mit den Gruppen,
// rechts die Fläche, Startseite ist der Leitstand.
//
// Die Werkzeuge (workflow, scenario, live, decision, project, gateway, slots, hardware) bleiben, was sie sind; jede Zelle bekommt ihre
// Fläche über denselben Weg wie jeder App-Reiter (`app.flaeche(S, objekt)`). Die Factory-Läufe sind die Lese-Ansicht der App Factory Studio (`eigene`).
// Der Workflow-Katalog und der Leitstand zählen echte gespeicherte Workflows und ihre offenen Angaben; sie erfinden keine Zahlen.
// Der Startassistent füllt die offenen Angaben jedes gespeicherten Workflows aus und speichert sie als neue Revision. „Starten“ wechselt in „Live & Debugger“.
// Der Notaus (STOPP) sitzt oben im „Live & Debugger“ und ruft dieselben Verben wie der Editor (`fabrik_stopp`, `fabrik_status`, `fabrik_freigeben`).
// Das Design wählt dieselben Erscheinungsbilder und denselben Speicherplatz (`sedra.theme`) wie der Rest von SEDRA.
// Ein Modus wird beim ersten Öffnen eingehängt und beim Wechsel nur versteckt. Der zuletzt aktive Modus wird je Browser gemerkt.
// Text nur mit textContent, Farben nur über Tokens, keine Takte außer dem Notaus-Stand (alle 4 Sekunden, wie im Editor). Eigene Texte einsprachig deutsch.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const KEY = 'sedra.harness.workflow_studio.modus';
  const OBJEKT = {type: 'workflow-studio', id: 'app', title: 'Workflow Studio'};
  const THEME_KEY = 'sedra.theme';
  const TAKT = 4000;

  const N8N = {type: 'workflow', id: 'alle', title: 'n8n Workflows', collection: true};
  const SZENARIO = {type: 'scenario', id: 'alle', title: 'Szenario Studio', collection: true};
  const PROJEKT = {type: 'project', id: 'projekt', title: 'Projekte'};
  const FREIGABEN = {type: 'decision', id: 'alle', title: 'Freigaben', collection: true};
  const LIVE = {type: 'task', id: 'alle', title: 'Live', collection: true};
  const LAEUFE = {type: 'factory-laeufe', id: 'laeufe', title: 'Factory-Läufe', eigene: 'factory_laeufe'};
  const VERBINDUNGEN = {type: 'gateway', id: 'alle', title: 'KI GateWay', collection: true};
  const MODELLE = {type: 'model', id: 'alle', title: 'Modelle und Slots', collection: true};
  const HARDWARE = {type: 'hardware', id: 'hardware', title: 'Hardware'};

  // Die Modi, in der Reihenfolge der Navigation. `gruppe` ordnet sie ein, so wie die Vorlage ihre Gruppen zeigt.
  // `katalog`, `assistent`, `design`, `notaus` sind Flächen, die die App selbst baut; `zellen` sind die Werkzeuge, die sie einhängt.
  const MODI = [
    {id: 'leitstand', label: 'Startseite / Leitstand', gruppe: 'Leitstand', zellen: [FREIGABEN, LIVE], kpi: true},
    {id: 'katalog', label: 'Workflow-Katalog', gruppe: 'Direkt arbeiten', zellen: [], katalog: true},
    {id: 'n8n', label: 'n8n Workflows', gruppe: 'Direkt arbeiten', zellen: [N8N]},
    {id: 'startassistent', label: 'Startassistent', gruppe: 'Direkt arbeiten', zellen: [], assistent: true},
    {id: 'live', label: 'Live & Debugger', gruppe: 'Direkt arbeiten', zellen: [LIVE], notaus: true},
    {id: 'szenario', label: 'Szenario Studio', gruppe: 'Direkt arbeiten', zellen: [SZENARIO]},
    {id: 'factory', label: 'Factory', gruppe: 'Vorbereitung', zellen: [PROJEKT, LAEUFE]},
    {id: 'freigaben', label: 'Freigaben', gruppe: 'Prüfen und verbessern', zellen: [FREIGABEN]},
    {id: 'verbindungen', label: 'Verbindungen', gruppe: 'Plattform & Design', zellen: [VERBINDUNGEN]},
    {id: 'modelle', label: 'Modelle und Slots', gruppe: 'Plattform & Design', zellen: [MODELLE]},
    {id: 'hardware', label: 'Hardware', gruppe: 'Plattform & Design', zellen: [HARDWARE]},
    {id: 'design', label: 'Design', gruppe: 'Plattform & Design', zellen: [], design: true}
  ];
  const GRUPPEN = ['Leitstand', 'Direkt arbeiten', 'Vorbereitung', 'Prüfen und verbessern', 'Plattform & Design'];

  // Die Erscheinungsbilder, wie sie in js/theme.js stehen (gleicher Schlüssel im Browser).
  const THEMES = [['retro', 'Retro', 'Das SEDRA-Deck, wie du es kennst'], ['klar', 'Klar', 'Hell und ruhig, flache Flächen'], ['nacht', 'Nacht', 'Dunkel; passt zum Hardware-Fenster']];

  // Die Prozessangaben, die je Schritt fehlen dürfen (wie ui/workflow-process.js). Start braucht keine Eingabe, Ende kein Ergebnis.
  const ANGABEN = [['role', 'Rolle'], ['input', 'Eingabe'], ['output', 'Ergebnis'], ['evidence', 'Nachweis'], ['completion', 'Abschlusskriterium']];

  // rein
  function modusWahl(gemerkt){ return MODI.some(m=>m.id === gemerkt) ? gemerkt : MODI[0].id; }
  function lesen(){ try{ return modusWahl(localStorage.getItem(KEY)); }catch(_e){ return MODI[0].id; } }
  function merken(id){ try{ localStorage.setItem(KEY, id); }catch(_e){} }
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

  // Die Angaben eines Knotens: die gespeicherten, oder für einen Knoten ohne Angaben eine leere Vorlage (P.blank). So gilt der Assistent für jeden Workflow.
  function angabenVon(node){
    const P = root.sedraWorkflowProcess;
    return P.get(node) || P.blank(node);
  }
  // Ein Knoten zählt als Schritt, wenn er kein Notiz-Zettel ist (der bleibt ohne Angaben).
  function istSchritt(node){ return !String(node.type || '').endsWith('.stickyNote'); }
  // Offene Angaben je Schritt aus einem Workflow-Dokument. Rein: liest nur.
  function luecken(doc){
    const P = root.sedraWorkflowProcess;
    if(!P || !doc) return [];
    return (doc.nodes || []).filter(istSchritt).map(node=>{
      const meta = angabenVon(node);
      if(meta.kind === 'annotation') return null;
      const fehlt = ANGABEN.filter(([k])=>!(meta[k] || '').trim() && !(k === 'input' && meta.kind === 'start') && !(k === 'output' && meta.kind === 'end'));
      return {node, name: node.name, fehlt};
    }).filter(x=>x && x.fehlt.length);
  }

  // Alle gespeicherten Workflows mit ihrer Zahl offener Angaben. Liest nur; ein Workflow, der nicht lädt, zählt als „nicht geprüft“.
  async function workflowsZaehlen(api){
    const liste = await api('/api/objects', {method: 'POST', body: {type: 'workflow', id: 'alle'}});
    const eintraege = [];
    for(const r of (liste.items || [])){
      try{
        const rec = await api('/api/objects', {method: 'POST', body: {type: 'workflow', id: r.id}});
        const laufbar = !!(rec.execution && rec.execution.executable);
        eintraege.push({id: r.id, title: r.title, revision: r.revision, laufbar, offen: laufbar ? 0 : luecken(rec.workflow).length, geprueft: true});
      }catch(_e){ eintraege.push({id: r.id, title: r.title, revision: r.revision, offen: 0, geprueft: false}); }
    }
    return eintraege;
  }

  // Der Workflow-Katalog: alle gespeicherten Workflows, je mit offenen Angaben und einem Sprung in den Startassistenten.
  function baueKatalog(api, zumAssistent){
    const box = d().el('div', 'hs-ws-katalog');
    const stand = d().el('p', 'hs-ws-hinweis', 'Lade die gespeicherten Workflows …');
    const karten = d().el('div', 'hs-ws-luecken');
    box.append(stand, karten);
    workflowsZaehlen(api).then(liste=>{
      stand.textContent = liste.length ? liste.length + ' gespeicherte Workflow(s).' : 'Noch kein Workflow gespeichert. Lege einen im n8n-Editor an oder importiere ihn.';
      liste.forEach(w=>{
        const karte = d().el('div', 'hs-ws-karte');
        karte.append(d().el('h4', 'hs-ws-karten-titel', w.title));
        karte.append(d().el('p', 'hs-ws-hinweis', 'Revision ' + w.revision + (w.geprueft ? ' · ' + (w.offen ? w.offen + ' offene Angabe(n)' : 'vollständig') : ' · nicht geprüft')));
        const knopf = d().el('button', 'hs-ws-knopf', 'Im Startassistenten öffnen'); knopf.type = 'button';
        knopf.onclick = ()=>zumAssistent(w.id);
        karte.append(knopf); karten.append(karte);
      });
    }).catch(err=>{ stand.textContent = 'Workflows nicht geladen: ' + (err.message || err); });
    return {box, abbauen(){ box.replaceChildren(); }};
  }

  // Der Leitstand nach der Vorlage: Kontext, Arbeitslage, „Was liegt an?“, Kennzahlen und „Jetzt wichtig“. Alle Zahlen stammen aus den
  // gespeicherten Workflows und dem Fabrik-Stand; was nicht lädt, steht ehrlich als nicht geladen da.
  function baueLeitstand(api, zumModus, zumAssistent){
    const box = d().el('div', 'hs-ws-leitstand');
    const aktion = (text, fn)=>{ const b = d().el('button', 'hs-ws-knopf', text); b.type = 'button'; b.onclick = fn; return b; };
    const chips = d().el('div', 'hs-ws-chips');
    const bannerText = d().el('span', '', 'Lade die gespeicherten Workflows …');
    const banner = d().el('div', 'hs-ws-banner'); banner.append(d().el('b', '', 'SEDRA – Arbeitslage'), bannerText);
    const kpiWerte = ['Gespeicherte Workflows', 'Ausführbar', 'Mit offenen Angaben', 'Fabrik'].map(titel=>{
      const k = d().el('div', 'hs-ws-kennzahl'); const w = d().el('b', 'hs-ws-kennzahl-wert', '…');
      k.append(d().el('span', 'hs-ws-kennzahl-titel', titel), w); return {k, w};
    });
    const kennzahlen = d().el('div', 'hs-ws-kennzahlen'); kpiWerte.forEach(x=>kennzahlen.append(x.k));
    const wichtigListe = d().el('div', 'hs-ws-liste');
    const wichtig = d().el('div', 'hs-ws-karte'); wichtig.append(d().el('h4', 'hs-ws-karten-titel', 'Jetzt wichtig'), wichtigListe,
      d().el('p', 'hs-ws-hinweis', 'Echte Zahlen aus den gespeicherten Workflows. Keine Simulation.'));
    const was = d().el('div', 'hs-ws-was');
    was.append(d().el('h4', 'hs-ws-sektion', 'Was liegt an?'));
    was.append(d().el('p', 'hs-ws-hinweis', 'Erst Entscheidungen und Störungen, dann laufende Arbeit.'));
    was.append(d().el('div', 'hs-ws-knoepfe'));
    was.lastChild.append(aktion('Workflow-Katalog', ()=>zumModus('katalog')), aktion('Startassistent', ()=>zumModus('startassistent')), aktion('Live & Debugger', ()=>zumModus('live')), aktion('Freigaben', ()=>zumModus('freigaben')));
    box.append(d().el('p', 'hs-ws-kicker', 'SEDRA / WORKFLOW STUDIO'), d().el('h3', 'hs-ws-leit-titel', 'Startseite / Leitstand'), chips, banner, was, kennzahlen, d().el('div', 'hs-ws-spalten', ''));
    box.querySelector('.hs-ws-spalten').append(wichtig);
    workflowsZaehlen(api).then(liste=>{
      const laufbar = liste.filter(w=>w.laufbar).length, offen = liste.filter(w=>w.offen > 0).length;
      kpiWerte[0].w.textContent = String(liste.length); kpiWerte[1].w.textContent = String(laufbar); kpiWerte[2].w.textContent = String(offen);
      chips.replaceChildren(...['Workflows: ' + liste.length, 'Ausführbar: ' + laufbar, 'Offene Angaben: ' + offen].map(t=>d().el('span', 'hs-ws-chip', t)));
      bannerText.textContent = !liste.length ? 'Noch kein Workflow gespeichert.'
        : (offen ? offen + ' Workflow(s) mit offenen Angaben. ' : 'Alle gespeicherten Workflows sind vollständig beschrieben. ') + laufbar + ' ausführbar.';
      wichtigListe.replaceChildren(...liste.filter(w=>w.offen > 0).map(w=>{
        const z = d().el('div', 'hs-ws-liste-zeile'); z.append(d().el('span', '', w.title + ' · ' + w.offen + ' offen'), aktion('Öffnen', ()=>zumAssistent(w.id))); return z;
      }));
      if(!wichtigListe.childNodes.length) wichtigListe.append(d().el('p', 'hs-ws-hinweis', 'Nichts Dringendes.'));
    }).catch(err=>{ bannerText.textContent = 'Workflows nicht geladen: ' + (err.message || err); kpiWerte.forEach(x=>{ x.w.textContent = '–'; }); });
    api('/api/actions', {method: 'POST', body: {type: 'workflow', id: null, verb: 'fabrik_status', args: {}}})
      .then(out=>{ const r = out.result || out; kpiWerte[3].w.textContent = r.angehalten ? 'angehalten' : 'läuft'; })
      .catch(()=>{ kpiWerte[3].w.textContent = '–'; });
    return {box, abbauen(){ box.replaceChildren(); }};
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
    let angehalten = false, arbeitet = false, timer = null;
    const verb = (name, args)=>api('/api/actions', {method: 'POST', body: {type: 'workflow', id: null, verb: name, args: args || {}}}).then(out=>out.result || out);
    function zeichnen(){
      stand.textContent = angehalten ? 'FABRIK ANGEHALTEN – es startet nichts Neues.' : 'Die Fabrik läuft. Der Notaus hält alles sofort an.';
      frei.hidden = !angehalten; stopp.disabled = arbeitet;
    }
    async function lesenStand(){
      if(!box.isConnected || box.offsetParent === null) return;   // in einem versteckten Modus nicht abfragen
      try{ const r = await verb('fabrik_status'); angehalten = !!r.angehalten; zeichnen(); }
      catch(err){ stand.textContent = 'Stand nicht lesbar: ' + (err.message || err); }
    }
    stopp.onclick = async()=>{
      if(arbeitet) return; arbeitet = true; zeichnen(); meldung.textContent = '';
      try{ const r = await verb('fabrik_stopp'); meldung.textContent = berichtText(r); angehalten = true; }
      catch(err){ meldung.textContent = 'Das Anhalten ist fehlgeschlagen: ' + String(err.message || err).slice(0, 120) + ' – noch einmal drücken.'; }
      finally{ arbeitet = false; zeichnen(); }
    };
    frei.onclick = ()=>{ rueckfrage.hidden = false; frei.hidden = true; ja.focus(); };
    nein.onclick = ()=>{ rueckfrage.hidden = true; frei.hidden = false; };
    ja.onclick = async()=>{
      if(arbeitet) return; arbeitet = true; ja.disabled = true;
      try{ await verb('fabrik_freigeben'); angehalten = false; meldung.textContent = 'Die Fabrik ist wieder freigegeben.'; rueckfrage.hidden = true; }
      catch(err){ meldung.textContent = 'Das Freigeben ist fehlgeschlagen: ' + String(err.message || err).slice(0, 120); }
      finally{ arbeitet = false; ja.disabled = false; zeichnen(); }
    };
    lesenStand();
    timer = setInterval(lesenStand, TAKT);
    return {box, abbauen(){ if(timer) clearInterval(timer); timer = null; box.replaceChildren(); }};
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
  function baueLaeufe(api){
    const box = d().el('section', 'hs-ws-laeufe'); box.setAttribute('aria-label', 'Läufe');
    const kopf = d().el('div', 'hs-ws-knoepfe');
    const aktualisieren = d().el('button', 'hs-ws-knopf', 'Aktualisieren'); aktualisieren.type = 'button';
    kopf.append(d().el('h4', 'hs-ws-karten-titel', 'Läufe'), aktualisieren);
    const stand = d().el('p', 'hs-ws-hinweis', 'Lade die Läufe …');
    const liste = d().el('div', 'hs-ws-liste');
    const detail = d().el('div', 'hs-ws-karte'); detail.hidden = true;
    box.append(kopf, stand, liste, detail);
    let gewaehlt = null, timer = null;
    const sichtbar = ()=>box.isConnected && box.offsetParent !== null;
    const aktion = (verb, id)=>api('/api/actions', {method: 'POST', body: {type: 'workflow_run', id, verb, args: {}}}).then(out=>out.result || out);
    async function laden(){
      if(!sichtbar()) return;
      try{
        const data = await api('/api/objects', {method: 'POST', body: {type: 'workflow_run'}});
        const laeufe = data.items || [];
        stand.textContent = laeufe.length ? laeufe.length + ' Lauf/Läufe.' : 'Noch kein Lauf. Starte einen Workflow im Startassistenten.';
        liste.replaceChildren(...laeufe.slice().reverse().map(r=>{
          const z = d().el('div', 'hs-ws-liste-zeile');
          z.append(d().el('span', '', (r.title || r.id) + ' · ' + (r.state || '?')));
          const b = d().el('button', 'hs-ws-knopf', 'Anzeigen'); b.type = 'button';
          b.onclick = ()=>zeigeLauf(r.id);
          z.append(b); return z;
        }));
        if(gewaehlt) zeigeLauf(gewaehlt, true);
      }catch(err){ stand.textContent = 'Läufe nicht geladen: ' + (err.message || err); }
    }
    async function zeigeLauf(id, leise){
      gewaehlt = id;
      try{
        const r = await api('/api/objects', {method: 'POST', body: {type: 'workflow_run', id}});
        detail.hidden = false; detail.replaceChildren();
        detail.append(d().el('h4', 'hs-ws-karten-titel', 'Lauf ' + id + ' · ' + (r.state || '?')));
        detail.append(d().el('p', 'hs-ws-hinweis', 'Workflow ' + (r.workflow_id || '–') + (r.revision ? ' · Revision ' + r.revision : '')));
        if(r.wait) detail.append(d().el('p', 'hs-ws-hinweis', 'Wartet auf: ' + (typeof r.wait === 'string' ? r.wait : JSON.stringify(r.wait))));
        const schritte = (r.steps || []);
        if(schritte.length){
          const tabelle = d().el('div', 'hs-ws-liste');
          schritte.forEach(s=>tabelle.append(d().el('div', 'hs-ws-liste-zeile', (s.id || s.step_id || s.name || '?') + ' · ' + (s.status || '?') + (s.attempts ? ' · Versuch ' + s.attempts : ''))));
          detail.append(tabelle);
        }else detail.append(d().el('p', 'hs-ws-hinweis', 'Noch keine Schritte.'));
        if(r.result) detail.append(d().el('pre', 'hs-ws-ergebnis', JSON.stringify(r.result, null, 2)));
        const fort = d().el('button', 'hs-ws-knopf primary', 'Nach Freigabe fortsetzen'); fort.type = 'button';
        const abbr = d().el('button', 'hs-ws-knopf', 'Lauf beenden'); abbr.type = 'button';
        const meldung = d().el('p', 'hs-ws-hinweis');
        fort.onclick = async()=>{ meldung.textContent = 'Setze fort …'; try{ await aktion('fortsetzen', id); meldung.textContent = 'Fortgesetzt.'; laden(); }catch(err){ meldung.textContent = 'Nicht fortgesetzt: ' + (err.message || err); } };
        abbr.onclick = async()=>{ meldung.textContent = 'Beende den Lauf …'; try{ await aktion('abbrechen', id); meldung.textContent = 'Beendet.'; laden(); }catch(err){ meldung.textContent = 'Nicht beendet: ' + (err.message || err); } };
        detail.append(d().el('div', 'hs-ws-knoepfe')); detail.lastChild.append(fort, abbr); detail.append(meldung);
      }catch(err){ if(!leise){ detail.hidden = false; detail.textContent = 'Lauf nicht geladen: ' + (err.message || err); } }
    }
    aktualisieren.onclick = ()=>laden();
    laden();
    timer = setInterval(laden, TAKT);
    return {box, abbauen(){ if(timer) clearInterval(timer); timer = null; box.replaceChildren(); }};
  }

  // Die Darstellung: dieselben Erscheinungsbilder und derselbe Speicherplatz wie in js/theme.js.
  function baueDesign(){
    const box = d().el('div', 'hs-ws-katalog');
    box.append(d().el('p', 'hs-ws-hinweis', 'Erscheinungsbild der Oberfläche. Die Wahl gilt für den Browser und bleibt beim Neuladen erhalten.'));
    const reihe = d().el('div', 'hs-ws-knoepfe');
    const aktuell = ()=>{ try{ return document.documentElement.dataset.theme || 'retro'; }catch(_e){ return 'retro'; } };
    const knoepfe = THEMES.map(([id, label, hinweis])=>{
      const b = d().el('button', 'hs-ws-knopf', label); b.type = 'button'; b.title = hinweis; b.dataset.theme = id;
      b.onclick = ()=>{
        if(id === 'retro') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = id;
        try{ if(id === 'retro') localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, id); }catch(_e){ /* privates Fenster: die Wahl hält bis zum Neuladen */ }
        markieren();
      };
      reihe.append(b); return b;
    });
    function markieren(){ knoepfe.forEach(b=>{ const on = b.dataset.theme === aktuell(); b.classList.toggle('primary', on); b.setAttribute('aria-pressed', on ? 'true' : 'false'); }); }
    markieren();
    box.append(reihe);
    return {box, abbauen(){ box.replaceChildren(); }};
  }

  // Der Startassistent: wählt einen gespeicherten Workflow, zeigt seine offenen Angaben, nimmt Eingaben an und speichert sie als neue Revision.
  function baueAssistent(api, zumLive){
    const box = d().el('div', 'hs-ws-assist');
    const kopf = d().el('p', 'hs-ws-hinweis', 'Startassistent: füllt die offenen Angaben jedes Schritts aus und speichert sie als neue Revision. Danach geht es in Live & Debugger.');
    const wahl = d().el('select', 'hs-ws-wahl'); wahl.setAttribute('aria-label', 'Workflow wählen');
    const stand = d().el('p', 'hs-ws-hinweis');
    const liste = d().el('div', 'hs-ws-luecken');
    const knoepfe = d().el('div', 'hs-ws-knoepfe');
    let rec = null, eingaben = [];

    async function alleLaden(){
      const data = await api('/api/objects', {method: 'POST', body: {type: 'workflow', id: 'alle'}});
      wahl.replaceChildren(new Option('Workflow wählen', ''));
      (data.items || []).forEach(r=>wahl.append(new Option(r.title + ' · r' + r.revision, r.id)));
      if(rec) wahl.value = rec.id;                                // ein Sprung aus dem Katalog hat schon einen Workflow geöffnet: die Auswahl bleibt
    }
    async function oeffnen(id){
      rec = await api('/api/objects', {method: 'POST', body: {type: 'workflow', id}});
      wahl.value = id;
      zeichnen();
    }
    function zeichnen(){
      liste.replaceChildren(); knoepfe.replaceChildren(); eingaben = [];
      // Ein ausführbarer Workflow bekommt keine Prozessangaben: sobald sie an den Knoten stehen, gilt er als Prozessmodell und ist nicht mehr ausführbar.
      const laufbar = !!(rec && rec.execution && rec.execution.executable);
      const offen = rec && !laufbar ? luecken(rec.workflow) : [];
      if(!rec){ stand.textContent = 'Wähle einen gespeicherten Workflow. Der Startassistent arbeitet an jedem Workflow.'; }
      else if(laufbar){
        stand.textContent = '„' + rec.workflow.name + '“ ist ausführbar. Keine Angaben nötig: Prozessangaben würden den Workflow zum Prozessmodell machen, das nicht läuft. Starte ihn direkt.';
      }
      else if(!offen.length){
        stand.textContent = 'Keine offenen Angaben in „' + rec.workflow.name + '“. Der Workflow ist vollständig beschrieben.';
      }else{
        stand.textContent = rec.workflow.name + ' · Revision ' + rec.revision + ' · ' + offen.length + ' Schritt(e) mit offenen Angaben.';
      }
      offen.forEach(x=>{
        const karte = d().el('div', 'hs-ws-karte'); karte.append(d().el('h4', 'hs-ws-karten-titel', x.name));
        x.fehlt.forEach(([k, label])=>{
          const zeile = d().el('label', 'hs-ws-feld', label);
          const feld = d().el('textarea', 'hs-ws-eingabe'); feld.rows = 2; feld.setAttribute('aria-label', x.name + ': ' + label);
          zeile.append(feld); karte.append(zeile);
          eingaben.push({node: x.node, key: k, feld});
        });
        liste.append(karte);
      });
      const speichern = d().el('button', 'hs-ws-knopf', 'Angaben speichern'); speichern.type = 'button';
      speichern.disabled = !rec || !offen.length;
      speichern.onclick = ()=>sichern().catch(err=>{ stand.textContent = 'Nicht gespeichert: ' + (err.message || err); });
      const start = d().el('button', 'hs-ws-knopf primary', 'Starten: zu Live & Debugger'); start.type = 'button';
      start.onclick = ()=>zumLive(rec);
      knoepfe.append(speichern, start);
    }
    async function sichern(){
      const doc = JSON.parse(JSON.stringify(rec.workflow));
      const P = root.sedraWorkflowProcess;
      const geaendert = eingaben.filter(e=>e.feld.value.trim());
      if(!geaendert.length){ stand.textContent = 'Keine Eingabe. Trage mindestens eine Angabe ein.'; return; }
      // Knoten im Dokument suchen (gleicher Name), Angabe setzen, Rest bleibt unverändert.
      const gruppen = new Map();
      geaendert.forEach(e=>{ if(!gruppen.has(e.node.name)) gruppen.set(e.node.name, {}); gruppen.get(e.node.name)[e.key] = e.feld.value.trim(); });
      (doc.nodes || []).forEach(node=>{
        const werte = gruppen.get(node.name); if(!werte) return;
        P.set(node, Object.assign({}, angabenVon(node), werte));
      });
      const out = await api('/api/actions', {method: 'POST', body: {type: 'workflow', id: rec.id, verb: 'speichern',
        args: {workflow: doc, base_revision: rec.revision, change_note: 'Startassistent: offene Angaben ergänzt'}}});
      const gespeichert = out.result || {};
      await oeffnen(rec.id);
      stand.textContent = 'Revision ' + (gespeichert.revision || '') + ' gespeichert. ' + (luecken(rec.workflow).length ? luecken(rec.workflow).length + ' Schritt(e) noch offen.' : 'Keine offenen Angaben mehr.');
    }
    wahl.onchange = ()=>{ if(wahl.value) oeffnen(wahl.value).catch(err=>{ stand.textContent = 'Nicht geladen: ' + (err.message || err); }); };
    box.append(kopf, wahl, stand, liste, knoepfe);
    zeichnen();                                                  // Starten ist sofort da, auch ohne gewählten Workflow
    alleLaden().catch(err=>{ stand.textContent = 'Workflows nicht geladen: ' + (err.message || err); });
    return {box, oeffne: id=>oeffnen(id).catch(err=>{ stand.textContent = 'Nicht geladen: ' + (err.message || err); }), abbauen(){ box.replaceChildren(); }};
  }

  // Die Ansicht: Navigation links, je Modus ein Fensterchen rechts. Rückgabe {abbauen, zeichnen, zeigen, modus}.
  function ansicht(S, box, kopfFlaeche){
    const A = root.sedraHarness.app;
    // Die API des Werkzeugs „Workflow Studio“ (sein Manifest nennt die Routen /api/objects und /api/actions), nicht die der Shell.
    const manifest = (S.ctx.tools.forObject(OBJEKT) || [])[0];
    const api = (pfad, optionen)=>(manifest ? S.ctx.makeContext(manifest, OBJEKT, S.shellApi).api : S.ctx.api)(pfad, optionen);
    kopfFlaeche.koerper.hidden = true; kopfFlaeche.verben.hidden = true;           // die Fläche des Platzhalter-Werkzeugs bleibt leer
    const layout = d().el('div', 'hs-ws-layout');
    const nav = d().el('nav', 'hs-ws-nav'); nav.setAttribute('aria-label', 'Workflow Studio');
    nav.append(d().el('div', 'hs-ws-marke', 'SEDRA · WORKFLOW STUDIO'));
    const buehne = d().el('section', 'hs-ws-buehne');
    layout.append(nav, buehne);
    box.append(layout);
    const zustand = {modus: lesen(), felder: {}, knoepfe: {}, kontext: null, lauf: null};

    const aktiv = ()=>zustand.felder[zustand.modus];
    const zeichnen = ()=>{ const f = aktiv(); if(f) f.flaechen.forEach(x=>x.zeichnen()); };
    function einhaengen(modus){
      if(modus.assistent || modus.katalog || modus.design){
        const teil = modus.assistent
          ? baueAssistent(api, rec=>{ zustand.kontext = rec; if(zustand.lauf) zustand.lauf.setze(rec); zeigen('live'); })
          : modus.design ? baueDesign()
          : baueKatalog(api, id=>{ zeigen('startassistent'); const s = zustand.felder.startassistent; if(s && s.teil) s.teil.oeffne(id); });
        const pane = d().el('div', 'hs-ws-pane'); pane.dataset.modus = modus.id; pane.append(teil.box);
        buehne.append(pane);
        zustand.felder[modus.id] = {pane, teil, flaechen: [{zeichnen(){}, abbauen(){ teil.abbauen(); }}]};
        return;
      }
      const pane = d().el('div', 'hs-ws-pane' + (modus.zellen.length > 1 ? ' raster' : '')); pane.dataset.modus = modus.id;
      const extra = [];
      if(modus.kpi){
        const lt = baueLeitstand(api, id=>zeigen(id), id=>{ zeigen('startassistent'); const s = zustand.felder.startassistent; if(s && s.teil) s.teil.oeffne(id); });
        pane.append(lt.box); extra.push({zeichnen(){}, abbauen(){ lt.abbauen(); }});
      }
      if(modus.notaus){
        const n = baueNotaus(api); pane.append(n.box); extra.push({zeichnen(){}, abbauen(){ n.abbauen(); }});
        const l = baueLauf(api); pane.append(l.box); extra.push({zeichnen(){}, abbauen(){ l.abbauen(); }});
        zustand.lauf = l; l.setze(zustand.kontext);                 // zeigt den zuletzt gestarteten Workflow, falls vorhanden
        const la = baueLaeufe(api); pane.append(la.box); extra.push({zeichnen(){}, abbauen(){ la.abbauen(); }});
      }
      const flaechen = modus.zellen.map(objekt=>{
        const eigene = objekt.eigene && root.sedraHarness[objekt.eigene];
        const flaeche = eigene ? eigene.flaeche(S) : A.flaeche(S, objekt);
        const zelle = d().el('section', 'hs-ws-zelle'); zelle.dataset.zelle = objekt.type;
        if(modus.zellen.length > 1) zelle.append(d().el('h3', 'hs-ws-zellenkopf', objekt.title));
        zelle.append(flaeche.verben, flaeche.koerper);
        pane.append(zelle);
        return flaeche;
      });
      buehne.append(pane);
      zustand.felder[modus.id] = {pane, flaechen: extra.concat(flaechen)};
    }
    function zeigen(id){
      const modus = MODI.find(m=>m.id === id) || MODI[0];
      zustand.modus = modus.id; merken(modus.id);
      if(!zustand.felder[modus.id]) einhaengen(modus);
      MODI.forEach(m=>{
        const f = zustand.felder[m.id]; if(f) f.pane.hidden = m.id !== modus.id;           // verstecken, nicht aushängen
        const on = m.id === modus.id; const k = zustand.knoepfe[m.id];
        if(!k) return;
        k.classList.toggle('on', on); k.setAttribute('aria-current', on ? 'page' : 'false');
      });
      zeichnen();
    }
    GRUPPEN.forEach(g=>{
      const eintraege = MODI.filter(m=>m.gruppe === g); if(!eintraege.length) return;
      const abschnitt = d().el('div', 'hs-ws-gruppe');
      abschnitt.append(d().el('h4', 'hs-ws-gruppen-titel', g));
      eintraege.forEach(m=>{
        const b = d().el('button', 'hs-ws-nav-knopf', m.label); b.type = 'button'; b.dataset.modus = m.id;
        b.onclick = ()=>zeigen(m.id);
        zustand.knoepfe[m.id] = b; abschnitt.append(b);
      });
      nav.append(abschnitt);
    });
    zeigen(zustand.modus);
    return {
      zeichnen,
      zeigen,
      modus: ()=>zustand.modus,
      abbauen(){
        Object.values(zustand.felder).forEach(f=>f.flaechen.forEach(x=>{ try{ x.abbauen(); }catch(_e){} }));
        zustand.felder = {};
      }
    };
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.workflow_studio = {MODI, GRUPPEN, KEY, OBJEKT, modusWahl, luecken, berichtText, ansicht};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.workflow_studio;
})();
