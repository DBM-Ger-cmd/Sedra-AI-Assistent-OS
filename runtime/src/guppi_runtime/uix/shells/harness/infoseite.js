// Harness-Shell – die Seite „Info“ (Einstellungen → System): der Info-Hub. Sagt in Klartext, welche Modelle laufen (Fenster, Slots, Grafikspeicher), was zuletzt abgelehnt wurde
// und warum, und zeigt die letzten Ereignisse des Audit-Logs, filterbar nach Art und Suchwort (GET /api/harness/info). Zusätzlich das Betriebslog: Tagesdateien, die als Quelle in die Wissensdatenbank können (Antrag, Freigabe im Posteingang).
// Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const ARTEN = [['alle', 'Alle'], ['modelle', 'Modelle'], ['fehler', 'Fehler und Ablehnungen'], ['freigaben', 'Freigaben']];

  function uhrzeit(iso){
    const t = new Date(iso);
    return isNaN(t) ? String(iso || '') : t.toLocaleString('de-DE', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit'});
  }

  // Die Ladeprobe: könnte jedes Rezept jetzt laden (ohne zu laden)? Sie läuft nach jedem Start und bei jedem Öffnen dieser Seite.
  function probeZeilen(p){
    if(!p) return [];
    if(p.fehler) return [d().el('h3', 'hs-ueber', 'Laden (Probe)'), d().el('small', 'hs-info-fehler', 'Die Probe ließ sich nicht rechnen: ' + p.fehler)];
    const kopf = !p.loader ? 'Der Modell-Lader ist aus – es lässt sich nichts laden.' : p.ok + ' von ' + p.gesamt + ' Rezepten könnten jetzt laden.';
    const zeilen = [d().el('h3', 'hs-ueber', 'Laden (Probe)'), d().el('div', 'hs-hw-kopf' + (p.loader && p.ok === p.gesamt ? '' : ' hs-info-fehler'), kopf)];
    (p.rezepte || []).forEach(x=>{
      const z = d().el('div', 'hs-info-zeile' + (x.ok ? '' : ' hs-info-fehler'));
      z.append(d().el('span', null, x.ok ? '✓' : '✗'), d().el('b', null, x.id), d().el('span', null, x.ok ? 'passt' + (x.fenster ? ' · Fenster ' + Number(x.fenster).toLocaleString('de-DE') : '') + (x.geladen ? ' · geladen' : '') : x.grund));
      zeilen.push(z);
    });
    return zeilen;
  }

  function modelleZeigen(box, m, probe){
    const laeuft = (m && m.laeuft) || [], abgelehnt = (m && m.abgelehnt) || [];
    const zeilen = probeZeilen(probe).concat([d().el('h3', 'hs-ueber', 'Läuft jetzt (laut Log)')]);
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

  // Verlauf: Sedra schreibt die wichtigen Ereignisse tageweise in das Betriebslog (Ordner im Projekt); dieser Ordner kann als Quelle in die Wissensdatenbank (Freigabe im Posteingang)
  function verlaufZeigen(S, box, v){
    const zeilen = [d().el('h3', 'hs-ueber', 'Verlauf (gespeichert)')];
    const tage = (v && v.tage) || [];
    const wiss = d().el('div', 'hs-info-zeile');
    if(v.wissen === 'aufgenommen') wiss.append(d().el('span', null, 'Der Verlauf läuft in die Wissensdatenbank ein.'));
    else if(v.wissen === 'aus') wiss.append(d().el('span', 'hs-leise', 'Die Wissensdatenbank ist abgeschaltet – der Verlauf wird trotzdem gespeichert.'));
    else{
      const knopf = d().el('button', 'hs-knopf', 'In die Wissensdatenbank aufnehmen'); knopf.type = 'button';
      const meld = d().el('small', 'hs-leise');
      knopf.onclick = async()=>{
        try{ const a = await S.api('/api/harness/info/wissen', {method: 'POST', body: {}}); knopf.disabled = true; meld.textContent = a && a.status === 'schon_aufgenommen' ? 'Schon aufgenommen.' : 'Antrag gestellt – im Posteingang freigeben.'; }
        catch(err){ meld.textContent = 'Nicht möglich: ' + err.message; }
      };
      wiss.append(knopf, meld, d().el('small', 'hs-leise', 'Ordner: ' + v.ordner));
    }
    zeilen.push(wiss);
    const text = d().el('pre', 'hs-info-tag'); text.hidden = true;
    if(!tage.length) zeilen.push(d().el('small', 'hs-leise', 'Noch kein Tag gespeichert.'));
    tage.forEach(t=>{
      const k = d().el('button', 'hs-knopf hs-klein', t.tag + ' (' + t.zeilen + ')'); k.type = 'button';
      k.onclick = ()=>S.api('/api/harness/info?limit=1&tag=' + encodeURIComponent(t.tag)).then(r=>{ text.textContent = r.tag ? r.tag.text : ''; text.hidden = false; }).catch(err=>{ text.textContent = 'Nicht lesbar: ' + err.message; text.hidden = false; });
      zeilen.push(k);
    });
    zeilen.push(text);
    box.replaceChildren(...zeilen);
  }

  function zeigen(S, box){
    box.append(d().el('div', 'hs-app-satz', 'Hier steht in Klartext, was Sedra laut seinem Audit-Log getan hat: welche Modelle laufen, was abgelehnt wurde und warum. Die wichtigen Ereignisse bleiben tageweise gespeichert (Verlauf unten) und können in die Wissensdatenbank einlaufen.'));
    const modelleBox = d().el('div', 'hs-info-modelle'); box.append(modelleBox);
    const leiste = d().el('div', 'hs-info-leiste');
    const art = d().el('select', 'hs-projektwahl'); art.setAttribute('aria-label', 'Art der Ereignisse');
    ARTEN.forEach(([wert, name])=>{ const o = document.createElement('option'); o.value = wert; o.textContent = name; art.append(o); });
    const such = d().el('input', 'hs-info-such'); such.type = 'search'; such.placeholder = 'Suchwort, z. B. qwen oder vram'; such.setAttribute('aria-label', 'Suchwort');
    const neu = d().el('button', 'hs-knopf hs-klein', 'Neu lesen'); neu.type = 'button';
    leiste.append(art, such, neu); box.append(leiste);
    const kopf = d().el('div', 'hs-hw-kopf', 'liest …'); box.append(kopf);
    const liste = d().el('div', 'hs-info-liste'); box.append(liste);
    const verlaufBox = d().el('div', 'hs-info-verlauf'); box.append(verlaufBox);
    const laden = ()=>{
      const q = '?art=' + encodeURIComponent(art.value) + '&such=' + encodeURIComponent(such.value) + '&limit=80';
      S.api('/api/harness/info' + q).then(v=>{
        if(v.fehler){ kopf.textContent = 'Das Log ließ sich nicht lesen: ' + v.fehler; return; }
        modelleZeigen(modelleBox, v.modelle, v.ladeprobe);
        if(v.verlauf) verlaufZeigen(S, verlaufBox, v.verlauf);
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
