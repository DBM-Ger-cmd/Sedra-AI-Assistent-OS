// Werkzeug „System“ – Maschinenraum und Hardware in einem Werkzeug: Zustand der Teile, Entwicklungsumgebung, GPU und Speicher.
// Lesen, dazu die Updates (Suche, Vorschau, Übernahme nur mit Bestätigung, Rückweg). Schalter und Bindungen liegen am Schreibtisch.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'system',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      this.view = (ctx.object && ctx.object.type === 'hardware') ? 'hardware' : 'machine';
      el.classList.add('t-sys');
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-sys'); this.el.replaceChildren(); },

    // Updates: suchen auf Klick. Vorschau lädt nur in den Staging-Ordner; übernommen wird erst nach Bestätigung, Rechte einzeln.
    updateAbschnitt(){
      const box = d().el('div', 's-col t-sys-update');
      box.append(d().el('h5', 's-head', 'Updates'), d().el('small', 's-muted', 'Installiert: ' + (this.updateStand ? this.updateStand.installiert : '…')));
      const ergebnis = d().el('div');
      const vorschau = d().el('div');
      const knopf = d().button('Nach Updates suchen', async()=>{
        ergebnis.replaceChildren(d().el('small', 's-muted', 'Suche …'));
        vorschau.replaceChildren();
        try{
          const r = await this.ctx.api('/api/update/suche', {method: 'POST', body: {}});
          this.updateStand = r;
          if(r.status === 'neu'){
            ergebnis.replaceChildren(d().el('div', 's-note warn', 'Neue Version ' + r.neueste + ' ist verfügbar. Übernommen wird erst nach deiner Bestätigung.'));
            vorschau.replaceChildren(d().button('Vorschau laden (ändert noch nichts im Programm)', ()=>this.updateVorschau(vorschau, r.neueste), 'p'));
          }
          else if(r.status === 'aktuell') ergebnis.replaceChildren(d().el('div', 's-note ok', 'Die neueste Version ist installiert (' + r.installiert + ').'));
          else if(r.status === 'keine_releases') ergebnis.replaceChildren(d().el('small', 's-muted', 'Auf GitHub gibt es noch keine Version.'));
          else ergebnis.replaceChildren(d().el('div', 's-note bad', 'GitHub ist nicht erreichbar. Die Suche ändert nichts.'));
        }catch(err){ ergebnis.replaceChildren(d().el('div', 's-note bad', 'Suche fehlgeschlagen: ' + err.message)); }
      }, 'p');
      box.append(knopf, ergebnis, vorschau, this.updateRueckweg());
      return box;
    },

    // Vorschau: Prüfung gegen das Manifest, geänderte Dateien, Rechteänderungen einzeln. Übernehmen nur mit Häkchen bei Rechten.
    async updateVorschau(box, tag){
      box.replaceChildren(d().el('small', 's-muted', 'Lade ' + tag + ' und prüfe die Dateien …'));
      let p;
      try{ p = await this.ctx.api('/api/update/vorschau', {method: 'POST', body: {tag}}); }
      catch(err){ box.replaceChildren(d().el('div', 's-note bad', 'Vorschau fehlgeschlagen: ' + err.message)); return; }
      const zeilen = [d().el('div', 's-note ok', 'Geprüft: ' + p.anzahl + ' Dateien stimmen mit dem Manifest überein.'),
        d().el('small', 's-muted', 'Geändert: ' + p.geaendert.length + ' · entfällt: ' + p.entfallen.length + ' · ' + p.wirkt + '.')];
      if(p.geaendert.length) zeilen.push(this.updateListe('Dateien', p.geaendert));
      const ok = d().button('Übernehmen', async()=>{
        try{
          const r = await this.ctx.api('/api/update/uebernehmen', {method: 'POST', body: {tag, rechte_schluessel: p.rechte_schluessel}});
          box.replaceChildren(d().el('div', 's-note ok', 'Übernommen. Wirkung nach dem Neustart von SEDRA. Sicherung: ' + r.sicherung));
        }catch(err){ box.replaceChildren(d().el('div', 's-note bad', 'Übernahme abgebrochen: ' + err.message)); }
      }, 'p');
      if(p.rechte.length){
        const haken = d().el('input'); haken.type = 'checkbox';
        ok.disabled = true;
        haken.addEventListener('change', ()=>{ ok.disabled = !haken.checked; });
        zeilen.push(d().el('div', 's-note warn', 'Dieses Update ändert Modulrechte. Jede Änderung einzeln:'), this.updateListe('Rechte', p.rechte));
        const label = d().el('label'); label.append(haken, ' Ich bestätige genau diese Rechteänderungen');
        zeilen.push(label);
      }
      zeilen.push(ok);
      box.replaceChildren(...zeilen);
    },

    updateListe(titel, eintraege){
      const wrap = d().el('div');
      const ul = d().el('ul', 's-small');
      eintraege.slice(0, 40).forEach(e=>ul.append(d().el('li', null, e)));
      if(eintraege.length > 40) ul.append(d().el('li', 's-muted', '… und ' + (eintraege.length - 40) + ' weitere'));
      wrap.append(d().el('small', 's-muted', titel + ':'), ul);
      return wrap;
    },

    // Rückweg: die letzte Sicherung wiederherstellen. Zwei Klicks, weil es eine Freigabe ist.
    updateRueckweg(){
      const meldung = d().el('div');
      const knopf = d().button('Auf vorherige Version zurücksetzen', ()=>{
        const ja = d().button('Ja, zurücksetzen', async()=>{
          try{
            const r = await this.ctx.api('/api/update/zurueck', {method: 'POST', body: {}});
            meldung.replaceChildren(d().el('div', 's-note ok', 'Zurückgesetzt auf ' + r.version + '. Wirkung nach dem Neustart.'));
          }catch(err){ meldung.replaceChildren(d().el('div', 's-note bad', 'Zurücksetzen fehlgeschlagen: ' + err.message)); }
        }, 'p');
        meldung.replaceChildren(d().el('small', 's-muted', 'Die letzte Sicherung wird wiederhergestellt. Wirkung nach dem Neustart.'), ja);
      }, 'p');
      const box = d().el('div', 's-col');
      box.append(knopf, meldung);
      return box;
    },

    async refresh(){
      if(!this.el) return;
      let st;
      try{ st = await this.ctx.api('/api/status'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Zustand nicht lesbar: ' + err.message)); return; }
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note ' + (st.system_state === 'READY' ? 'ok' : 'warn'),
        st.system_state === 'READY' ? 'Alle Teile gesund.' : 'Sicherer Modus: mindestens ein Teil meldet ein Problem.'));
      box.append(this.updateAbschnitt());

      if(this.view === 'hardware'){
        const hw = st.hardware || {};
        const t = d().el('table', 's-table');
        [['Rechner', (hw.os || '') + ' · ' + (hw.architecture || '')], ['Prozessor', (hw.cpu || '') + ' · ' + (hw.cpu_threads || '?') + ' Fäden'],
         ['Arbeitsspeicher', (hw.ram_gb || '?') + ' GB'], ['Grafikkarte', hw.gpu_name || 'keine erkannt'], ['Grafikspeicher', (hw.vram_gb || '?') + ' GB'],
         ['Klasse', hw.hardware_class || '–']].forEach(([k, v])=>{
          const tr = d().el('tr'); tr.append(d().el('td', 's-muted', k), d().el('td', null, String(v))); t.append(tr);
        });
        box.append(d().el('h5', 's-head', 'Hardware'), t);
        const prof = (st.hardware_manager || {}).profile_state || {};
        if(prof.profile_id) box.append(d().el('small', 's-muted', 'Profil: ' + prof.profile_id + ' · ' + (prof.status || '')));
      }else{
        const t = d().el('table', 's-table');
        (st.health || []).forEach(h=>{
          const tr = d().el('tr');
          tr.append(d().el('td', null, h.component_id), d().el('td', h.state === 'HEALTHY' ? '' : 's-note warn', h.state === 'HEALTHY' ? 'gesund' : h.state));
          if((h.blocking_findings || []).length) tr.title = h.blocking_findings.join('; ');
          t.append(tr);
        });
        box.append(d().el('h5', 's-head', 'Teile'), t);

        const dev = st.development_environment || {};
        box.append(d().el('h5', 's-head', 'Entwicklungsumgebung'));
        box.append(d().el('div', 's-note ' + (dev.execution_ready ? 'ok' : 'warn'),
          dev.execution_ready ? 'Bereit: Kandidaten werden isoliert getestet.' : 'Blockiert: ' + ((dev.blockers || []).join(', ') || 'unbekannt') + ' – gebaut wird trotzdem, getestet wird nicht isoliert.'));
        const tools = st.tools || {};
        box.append(d().el('h5', 's-head', 'Werkzeuge der Runtime'));
        box.append(d().el('div', 's-small s-muted', Object.keys(tools).map(k=>k + (tools[k].healthy ? '' : ' (krank)')).join(' · ')));
      }
      this.el.replaceChildren(box);
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
