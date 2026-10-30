// Harness-Shell – Modell laden, wechseln und entladen direkt im Eingabebereich (Stufe 6, HS-80/HS-81): statt eines Verweises („Start → Modelle → Werkstatt“) steht dort, wo es fehlt,
// die Handlung selbst: Rezept wählen, „Laden“. Dieselben Wege wie die Werkstatt (GET /api/models, POST /api/model/load, POST /api/model/unload); Gates, Speicherprüfung und Fehlertexte
// kommen vom Server und werden unverändert angezeigt. Ein Ladevorgang kann Minuten dauern: der Knopf zeigt „lädt …“, nichts anderes wird blockiert.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const GRUND = {
    hardware_pressure: 'Zu wenig freier Arbeits- oder Grafikspeicher für dieses Rezept. Andere Programme beenden oder ein kleineres Rezept wählen.',
    gpu_lease_busy: 'Die Grafikkarte ist gerade belegt (Lauf oder anderer Dienst).',
    model_loader_unavailable: 'Das Laden von Modellen ist in dieser Installation ausgeschaltet.'
  };
  function fehlertext(err){
    const m = String((err && err.message) || err || '');
    const treffer = Object.keys(GRUND).find(k=>m.includes(k));
    return treffer ? GRUND[treffer] + ' (' + m + ')' : m;
  }

  // Die Steuerung: Rezeptwahl, Laden/Wechseln, Entladen, Zustand. `nachher` läuft nach Erfolg (Anzeige auffrischen).
  function steuerung(S, nachher){
    const box = d().el('div', 'hs-modell-steuer');
    const wahl = d().el('select', 'hs-projektwahl'); wahl.setAttribute('aria-label', 'Modell-Rezept');
    const laden = d().el('button', 'hs-senden p', 'Laden'); laden.type = 'button';
    const weg = d().el('button', 'hs-knopf', 'Entladen'); weg.type = 'button';
    const stand = d().el('span', 'hs-leise hs-modell-stand', ''); stand.setAttribute('role', 'status');
    let geladen = null;
    box.append(wahl, laden, weg, stand);

    async function auffrischen(){
      try{
        const v = await S.api('/api/models');
        const rezepte = (v.recipes || []).filter(r=>r.enabled && r.provider === 'llama-cpp-server');
        geladen = rezepte.find(r=>r.loaded) || null;
        const vorher = wahl.value;
        wahl.replaceChildren(...rezepte.map(r=>{
          const o = document.createElement('option'); o.value = r.id;
          o.textContent = r.model + (r.size_gb ? ' · ' + r.size_gb + ' GB' : '') + (r.loaded ? ' (geladen)' : '');
          o.title = (r.roles || []).join(', ');
          return o;
        }));
        wahl.value = rezepte.some(r=>r.id === vorher) ? vorher : (geladen ? geladen.id : (rezepte.some(r=>r.id === v.zuletzt) ? v.zuletzt : (rezepte[0] ? rezepte[0].id : '')));
        laden.disabled = !wahl.value;
        laden.textContent = geladen ? 'Wechseln' : 'Laden';
        weg.hidden = !geladen;
        if(!rezepte.length) stand.textContent = 'Keine Rezepte vorhanden.';
      }catch(err){ stand.textContent = 'Rezepte nicht lesbar: ' + err.message; laden.disabled = true; }
    }

    async function tun(pfad, body, text){
      laden.disabled = weg.disabled = wahl.disabled = true;
      stand.textContent = text;
      try{
        const out = await S.api(pfad, {method: 'POST', body});
        stand.textContent = '';
        await S.modellLaden();
        if(nachher) nachher(out);
      }catch(err){ stand.textContent = fehlertext(err); stand.classList.add('bad'); }
      finally{ wahl.disabled = false; laden.disabled = !wahl.value; weg.disabled = false; await auffrischen(); }
    }
    laden.onclick = ()=>{ stand.classList.remove('bad'); tun('/api/model/load', {recipe_id: wahl.value}, 'lädt … das kann einige Minuten dauern'); };
    weg.onclick = ()=>{ stand.classList.remove('bad'); tun('/api/model/unload', {}, 'entlädt …'); };
    auffrischen();
    return Object.assign(box, {auffrischen});
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.modell = {steuerung, fehlertext};
})();
