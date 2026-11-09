// Der rote Knopf der Workflow-Darstellungen: die Fabrik sofort anhalten, wenn etwas aus dem Ruder läuft. Er sitzt unter den Reitern und ist
// in jedem Reiter da. Ein Klick hält alles an: die Haltemarke wird gesetzt (die Harness startet nichts Neues), laufende Läufe werden gestoppt, aktive
// Aufgaben zurückgenommen, laufende Antworten abgebrochen (workflows/fabrik.py, Verb fabrik_stopp). Anhalten braucht keine Rückfrage und kein Gate;
// nur das Freigeben ist eine Entscheidung und fragt noch einmal nach. Der Stand wird alle 4 Sekunden gelesen (Verb fabrik_status).
// `statusText` und `berichtText` sind rein.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const TAKT = 4000;

  const uhr = iso=>{ const m = /T(\d\d:\d\d)/.exec(String(iso || '')); return m ? m[1] : ''; };
  // Zwei Zeilen für den angehaltenen Zustand (rein)
  function statusText(marke){
    if(!marke) return null;
    return {titel: 'FABRIK ANGEHALTEN', zeile: 'Seit ' + (uhr(marke.seit) || 'eben') + ' Uhr – es startet nichts Neues.' + (marke.grund ? ' ' + marke.grund : '')};
  }
  // Was der Notaus getan hat, in einem Satz plus Fehlern (rein)
  function berichtText(b){
    const n = x=>(x || []).length, t = [];
    t.push(n(b && b.laeufe) + (n(b && b.laeufe) === 1 ? ' Lauf gestoppt' : ' Läufe gestoppt'));
    t.push(n(b && b.aufgaben) + (n(b && b.aufgaben) === 1 ? ' Aufgabe zurückgenommen' : ' Aufgaben zurückgenommen'));
    if(b && b.bau) t.push('Bau-Lauf beendet');
    if(n(b && b.antworten)) t.push(n(b.antworten) + (n(b.antworten) === 1 ? ' Antwort abgebrochen' : ' Antworten abgebrochen'));
    const f = (b && b.fehler) || [];
    return 'Fabrik angehalten: ' + t.join(', ') + '.' + (f.length ? ' Nicht alles ließ sich stoppen (' + f.length + '): ' + f.slice(0, 2).join('; ') : '');
  }

  const el = (tag, cls, text)=>{ const x = document.createElement(tag); if(cls) x.className = cls; if(text !== undefined) x.textContent = text; return x; };
  const knopf = (text, fn, cls)=>{ const b = el('button', cls || '', text); b.type = 'button'; b.onclick = fn; return b; };

  function attach(c){
    const box = el('section', 't-wf-notaus'); box.setAttribute('aria-label', 'Notaus der Fabrik');
    const stopp = knopf('■ STOPP', ()=>anhalten(), 't-wf-notaus-stopp');
    stopp.setAttribute('aria-label', 'Fabrik anhalten (Notaus)'); stopp.title = 'Hält die Fabrik sofort an: Läufe stoppen, Aufgaben zurücknehmen, nichts startet neu';
    const gestoppt = el('div', 't-wf-notaus-aus'); gestoppt.hidden = true; gestoppt.setAttribute('role', 'alert');
    const titel = el('b', 't-wf-notaus-titel'), zeile = el('small', 't-wf-notaus-zeile');
    const frei = knopf('Fabrik freigeben …', ()=>{ rueckfrage.hidden = false; frei.hidden = true; ja.focus(); }, 't-wf-notaus-frei');
    const rueckfrage = el('div', 't-wf-notaus-rueckfrage'); rueckfrage.hidden = true;
    const ja = knopf('Ja, freigeben', ()=>freigeben(), 't-wf-notaus-ja'), nein = knopf('Abbrechen', ()=>{ rueckfrage.hidden = true; frei.hidden = false; });
    rueckfrage.append(el('span', '', 'Wirklich freigeben? Danach darf die Fabrik wieder starten.'), ja, nein);
    gestoppt.append(titel, zeile, frei, rueckfrage);
    const meldung = el('p', 't-wf-notaus-meldung'); meldung.setAttribute('aria-live', 'polite'); meldung.hidden = true;
    box.append(stopp, gestoppt, meldung);
    const rail = c.tabButtons && c.tabButtons.live && c.tabButtons.live.parentElement && c.tabButtons.live.parentElement.parentElement;
    (rail || c.el).append(box);
    let timer = null, tot = false, arbeitet = false;

    function zeigen(marke){
      const s = statusText(marke);
      stopp.hidden = !!s; gestoppt.hidden = !s;
      box.classList.toggle('aus', !!s);
      if(s){ titel.textContent = s.titel; zeile.textContent = s.zeile; }
      else { rueckfrage.hidden = true; frei.hidden = false; }
      api.marke = marke || null;
      if(c.live && c.live.angehalten) c.live.angehalten(marke || null);
    }
    async function lesen(){
      if(tot || arbeitet) return;
      try{ const out = await c.call('workflow', null, 'fabrik_status'); if(!tot && out) zeigen(out.angehalten); }catch(e){ /* der Knopf bleibt, wie er ist */ }
    }
    function nachricht(text, schlecht){ meldung.textContent = text; meldung.hidden = !text; meldung.classList.toggle('schlecht', !!schlecht); }
    async function anhalten(){
      if(arbeitet) return;
      arbeitet = true; stopp.disabled = true; stopp.textContent = 'Halte an …'; nachricht('');
      try{
        const out = await c.call('workflow', null, 'fabrik_stopp');
        nachricht(berichtText(out), out && out.fehler && out.fehler.length);
        zeigen(out && out.marke);
      }catch(e){ nachricht('Das Anhalten ist fehlgeschlagen: ' + String(e && e.message || e).slice(0, 120) + ' – noch einmal drücken.', true); }
      finally{ arbeitet = false; stopp.disabled = false; stopp.textContent = '■ STOPP'; lesen(); }
    }
    async function freigeben(){
      if(arbeitet) return;
      arbeitet = true; ja.disabled = true;
      try{ await c.call('workflow', null, 'fabrik_freigeben'); nachricht('Die Fabrik ist wieder freigegeben.'); zeigen(null); }
      catch(e){ nachricht('Das Freigeben ist fehlgeschlagen: ' + String(e && e.message || e).slice(0, 120), true); }
      finally{ arbeitet = false; ja.disabled = false; }
    }
    const api = {
      marke: null, lesen, anhalten, freigeben,
      destroy(){ tot = true; if(timer) clearInterval(timer); timer = null; box.remove(); }
    };
    lesen(); timer = setInterval(lesen, TAKT);
    return api;
  }

  root.sedraWorkflowNotaus = {attach, statusText, berichtText};
  if(typeof module !== 'undefined' && module.exports) module.exports = {statusText, berichtText};
})();
