// Harness-Shell – die Seite „Hilfswerkzeuge“ (Einstellungen → Integrationen): welche Programme und Pakete auf der CPU Sedra helfen und auf diesem Rechner da sind
// (GET /api/harness/hilfswerkzeuge, Plan docs/PLAN_CPU_HILFSWERKZEUGE_2026-11-04.md). Nur Anzeige: Sedra installiert nichts; fehlt etwas, steht der Befehl da, den der
// Captain selbst ausführt (Kopieren-Knopf). Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  function zeile(w){
    const z = d().el('div', 'hs-hw-zeile ' + w.status); z.dataset.id = w.id;
    z.append(d().el('span', 'hs-hw-punkt', w.status === 'da' ? '●' : '○'), d().el('b', 'hs-hw-name', w.name), d().el('small', 'hs-leise hs-hw-zweck', w.zweck));
    if(w.status === 'da') z.append(d().el('small', 'hs-leise hs-hw-fund', 'da: ' + w.fundort));
    else{
      const cmd = d().el('code', 'hs-hw-befehl', w.install);
      const kopie = d().el('button', 'hs-knopf hs-klein', 'Kopieren'); kopie.type = 'button';
      kopie.onclick = ()=>{ try{ navigator.clipboard.writeText(w.install); kopie.textContent = 'Kopiert'; }catch(_e){ kopie.textContent = 'Nicht kopiert'; } };
      z.append(cmd, kopie);
    }
    if(w.plan && w.plan !== 'vorhanden') z.append(d().el('small', 'hs-leise hs-hw-plan', 'Plan ' + w.plan));
    return z;
  }

  function zeigen(S, box){
    box.append(d().el('div', 'hs-app-satz', 'Hilfswerkzeuge nehmen dem Sprachmodell Arbeit ab und laufen auf der CPU, die Grafikkarte bleibt frei. Sedra erkennt nur, was da ist – installiert wird nichts von selbst. Lizenz und Größe vor dem Einsatz prüfen.'));
    const kopf = d().el('div', 'hs-hw-kopf', 'liest …'); box.append(kopf);
    const liste = d().el('div', 'hs-hw-liste'); box.append(liste);
    S.api('/api/harness/hilfswerkzeuge').then(v=>{
      if(v.fehler){ kopf.textContent = 'Die Liste ließ sich nicht lesen: ' + v.fehler; return; }
      kopf.textContent = v.da + ' von ' + v.gesamt + ' sind auf diesem Rechner da.';
      const sortiert = (v.werkzeuge || []).slice().sort((a, b)=>(a.status === 'da' ? 0 : 1) - (b.status === 'da' ? 0 : 1));
      liste.replaceChildren(...sortiert.map(zeile));
    }).catch(err=>{ kopf.textContent = 'Nicht lesbar: ' + err.message; });
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.hilfswerkzeugseite = {zeigen};
})();
