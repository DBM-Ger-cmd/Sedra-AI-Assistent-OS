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
    let angehalten = false, arbeitet = false;
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
    return {box, aktualisieren: lesenStand, abbauen(){ box.replaceChildren(); }};
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
    let gewaehlt = null;
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
    return {box, aktualisieren: laden, abbauen(){ box.replaceChildren(); }};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.workflow_studio_live = {baueNotaus, baueLauf, baueLaeufe, berichtText};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.workflow_studio_live;
})();
