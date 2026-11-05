// Harness-Shell – die Seite „Info“ (Einstellungen → System): der Info-Hub. Sagt in Klartext, welche Modelle laufen (Fenster, Slots, Grafikspeicher), was zuletzt abgelehnt wurde
// und warum, und zeigt die letzten Ereignisse des Audit-Logs, filterbar nach Art und Suchwort (GET /api/harness/info). Nur Anzeige: nichts wird geschrieben oder freigegeben.
// Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const ARTEN = [['alle', 'Alle'], ['modelle', 'Modelle'], ['fehler', 'Fehler und Ablehnungen'], ['freigaben', 'Freigaben']];

  function uhrzeit(iso){
    const t = new Date(iso);
    return isNaN(t) ? String(iso || '') : t.toLocaleString('de-DE', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit'});
  }

  function modelleZeigen(box, m){
    const laeuft = (m && m.laeuft) || [], abgelehnt = (m && m.abgelehnt) || [];
    const zeilen = [d().el('h3', 'hs-ueber', 'Läuft jetzt (laut Log)')];
    if(!laeuft.length) zeilen.push(d().el('small', 'hs-leise', 'Laut Log läuft seit dem letzten Start von Sedra kein Modellserver.'));
    laeuft.forEach(x=>{
      const z = d().el('div', 'hs-info-zeile');
      z.append(d().el('b', null, x.rezept), d().el('span', null, x.slots + ' Slots · je ' + x.fenster_je_slot + ' Token Fenster · ' + x.vram_gb + ' GB Grafikspeicher'), d().el('small', 'hs-leise', 'seit ' + uhrzeit(x.seit)));
      zeilen.push(z);
    });
    if(abgelehnt.length){
      zeilen.push(d().el('h3', 'hs-ueber', 'Zuletzt abgelehnt'));
      abgelehnt.forEach(x=>{
        const z = d().el('div', 'hs-info-zeile hs-info-fehler');
        z.append(d().el('b', null, x.rezept), d().el('span', null, x.grund), d().el('small', 'hs-leise', 'Rolle ' + x.rolle + ' · ' + uhrzeit(x.zeit)));
        zeilen.push(z);
      });
    }
    box.replaceChildren(...zeilen);
  }

  function zeigen(S, box){
    box.append(d().el('div', 'hs-app-satz', 'Hier steht in Klartext, was Sedra laut seinem Audit-Log getan hat: welche Modelle laufen, was abgelehnt wurde und warum. Nur Anzeige.'));
    const modelleBox = d().el('div', 'hs-info-modelle'); box.append(modelleBox);
    const leiste = d().el('div', 'hs-info-leiste');
    const art = d().el('select', 'hs-projektwahl'); art.setAttribute('aria-label', 'Art der Ereignisse');
    ARTEN.forEach(([wert, name])=>{ const o = document.createElement('option'); o.value = wert; o.textContent = name; art.append(o); });
    const such = d().el('input', 'hs-info-such'); such.type = 'search'; such.placeholder = 'Suchwort, z. B. qwen oder vram'; such.setAttribute('aria-label', 'Suchwort');
    const neu = d().el('button', 'hs-knopf hs-klein', 'Neu lesen'); neu.type = 'button';
    leiste.append(art, such, neu); box.append(leiste);
    const kopf = d().el('div', 'hs-hw-kopf', 'liest …'); box.append(kopf);
    const liste = d().el('div', 'hs-info-liste'); box.append(liste);
    const laden = ()=>{
      const q = '?art=' + encodeURIComponent(art.value) + '&such=' + encodeURIComponent(such.value) + '&limit=80';
      S.api('/api/harness/info' + q).then(v=>{
        if(v.fehler){ kopf.textContent = 'Das Log ließ sich nicht lesen: ' + v.fehler; return; }
        modelleZeigen(modelleBox, v.modelle);
        const e = v.ereignisse || [];
        kopf.textContent = e.length ? 'Die letzten ' + e.length + ' Ereignisse (neueste unten)' : 'Kein Ereignis passt zu dieser Auswahl.';
        liste.replaceChildren(...e.map(x=>{
          const z = d().el('div', 'hs-info-ereignis' + (x.art === 'fehler' ? ' hs-info-fehler' : ''));
          z.append(d().el('small', 'hs-leise hs-info-zeit', uhrzeit(x.zeit)), d().el('span', null, x.text));
          return z;
        }));
      }).catch(err=>{ kopf.textContent = 'Nicht lesbar: ' + err.message; });
    };
    art.onchange = laden; neu.onclick = laden;
    such.onkeydown = ev=>{ if(ev.key === 'Enter') laden(); };
    laden();
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.infoseite = {zeigen};
})();
