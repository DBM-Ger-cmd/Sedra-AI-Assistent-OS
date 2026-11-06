// Harness-Shell – „Neue Vorlage …“ (Einstellungen → Vorlagen, Captain 04.11.2026, wie „Neues Projekt …“): Name, Beschreibung, Basis, Werkzeuge und Anweisung → Antrag
// (POST /api/harness/vorlagen/neu); die zwei Dateien entstehen erst nach der Freigabe im Posteingang, in local_config/harness_vorlagen. Eine neue Vorlage hat keine Rechte und keine
// Sitzungs-Erlaubnisse. Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const NUR_VORARBEITER = ['freigaben_offen', 'freigabe_entscheiden', 'aufgabe_vorschlagen', 'aufgabe_beenden'];

  function feld(box, text, el){ const l = d().el('label', 'hs-vn-feld'); l.append(d().el('span', 'hs-leise', text), el); box.append(l); return el; }

  function formular(S, nach){
    const box = d().el('form', 'hs-ordner hs-vn'); box.hidden = true; box.setAttribute('aria-label', 'Neue Vorlage anlegen');
    const name = d().el('input', 'hs-ordner-feld'); name.placeholder = 'z. B. Übersetzer-Helfer'; name.setAttribute('aria-label', 'Name');
    const beschr = d().el('input', 'hs-ordner-feld'); beschr.placeholder = 'wofür die Vorlage ist (ein Satz)'; beschr.setAttribute('aria-label', 'Beschreibung');
    const basis = d().el('select', 'hs-ordner-feld'); basis.setAttribute('aria-label', 'Basis');
    basis.append(d().el('option', null, 'ohne Basis (Werkzeuge und Anweisung selbst)')); basis.firstChild.value = '';
    (S.vorlagen || []).filter(v=>!v.fehler).forEach(v=>{ const o = d().el('option', null, (v.name || v.id) + ' · ' + v.id); o.value = v.id; basis.append(o); });
    const anweisung = d().el('textarea', 'hs-ordner-feld'); anweisung.rows = 5; anweisung.setAttribute('aria-label', 'Anweisung');
    anweisung.placeholder = 'Anweisung für das Modell. Leer = die der Basis-Vorlage.';
    const liste = d().el('div', 'hs-vn-werkzeuge'); liste.setAttribute('role', 'group'); liste.setAttribute('aria-label', 'Werkzeuge');
    const haken = {};
    const senden = d().el('button', 'hs-senden p', 'Antrag stellen'); senden.type = 'submit';
    const zu = d().el('button', 'hs-knopf', 'Abbrechen'); zu.type = 'button';
    const stand = d().el('div', 'hs-leise hs-ordner-stand'); stand.setAttribute('role', 'status');
    const satz = d().el('div', 'hs-leise', 'Die Dateien entstehen erst nach deiner Freigabe im Posteingang, in local_config/harness_vorlagen. Keine Rechte, keine Sitzungs-Erlaubnisse; die Werkzeuge des Vorarbeiters gibt es hier nicht. Ohne Haken gelten die Werkzeuge der Basis.');
    feld(box, 'Name', name); feld(box, 'Beschreibung', beschr); feld(box, 'Basis (Vorgabe für Werkzeuge, Modell, Grenzen und Anweisung)', basis); feld(box, 'Anweisung', anweisung);
    box.append(d().el('span', 'hs-leise', 'Werkzeuge (kein Haken = wie die Basis)'), liste);
    const z = d().el('div', 'hs-ordner-zeile'); z.append(senden, zu); box.append(z, satz, stand);
    let geladen = false;
    async function werkzeugeLaden(){
      if(geladen) return; geladen = true;
      try{
        const out = await S.api('/api/harness/werkzeuge');
        (out.werkzeuge || []).filter(w=>NUR_VORARBEITER.indexOf(w.name) < 0).forEach(w=>{
          const l = d().el('label', 'hs-vn-haken'); const c = d().el('input'); c.type = 'checkbox'; haken[w.name] = c; c.title = String(w.beschreibung || '').slice(0, 300);
          l.append(c, d().el('span', null, w.name)); liste.append(l);
        });
      }catch(err){ geladen = false; stand.textContent = 'Werkzeuge nicht geladen: ' + err.message; }
    }
    const schliessen = ()=>{ box.hidden = true; stand.textContent = ''; };
    zu.onclick = schliessen;
    box.onsubmit = async e=>{
      e.preventDefault();
      if(!name.value.trim()){ stand.textContent = 'Ein Name fehlt.'; name.focus(); return; }
      const gewaehlt = Object.keys(haken).filter(k=>haken[k].checked);
      if(!basis.value && (!gewaehlt.length || !anweisung.value.trim())){ stand.textContent = 'Ohne Basis braucht es mindestens ein Werkzeug und eine Anweisung.'; return; }
      senden.disabled = true; stand.textContent = 'Antrag wird gestellt …';
      try{
        const body = {name: name.value.trim(), beschreibung: beschr.value.trim() || undefined, basis: basis.value || undefined,
                      werkzeuge: gewaehlt.length ? gewaehlt : undefined, system: anweisung.value.trim() || undefined};
        const out = await S.api('/api/harness/vorlagen/neu', {method: 'POST', body});
        stand.textContent = 'Antrag gestellt: „' + out.name + '“ (' + out.vorlage + ') mit ' + (out.werkzeuge || []).length + ' Werkzeugen – Entscheidung im Posteingang (Freigaben). Danach steht sie bei den Vorlagen.';
        S.hinweis('Neue Vorlage: Antrag im Posteingang.', 'note');
        if(S.freigabenLaden) S.freigabenLaden();
        if(nach) nach();
      }catch(err){ stand.textContent = 'Nicht gestellt: ' + err.message; }
      finally{ senden.disabled = false; }
    };
    return {box, oeffnen(){ box.hidden = false; werkzeugeLaden(); name.focus(); }, schliessen};
  }

  function knopf(S, box, nach){
    const f = formular(S, nach);
    const k = d().el('button', 'hs-knopf hs-ordner-knopf', 'Neue Vorlage …'); k.type = 'button';
    k.title = 'Name, Basis, Werkzeuge und Anweisung → Antrag im Posteingang';
    k.onclick = ()=>f.box.hidden ? f.oeffnen() : f.schliessen();
    box.append(k, f.box);
    return f;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.vorlagenneu = {formular, knopf};
})();
