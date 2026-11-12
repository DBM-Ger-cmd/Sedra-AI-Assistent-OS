(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  function el(tag, cls, text){const x = document.createElement(tag);if(cls)x.className = cls;if(text !== undefined)x.textContent = text;return x;}
  function button(text, fn){const b = el('button', '', text);b.type = 'button';b.onclick = fn;return b;}
  // Methoden, die der Editor in seinen Regler übernimmt (this = Regler).
  root.sedraWorkflowLokal = function(){return {
    // SEDRA-Eigenablauf: Datei für den Formular-Start hochladen und lokale Tabellen füllen (ohne n8n).
    buildLokal(run){
      const box = el('details', 't-wf-lokal');box.append(el('summary', '', 'Eingabedatei und Tabellen (SEDRA-Eigenablauf)'));
      this.fileBox = el('input');this.fileBox.type = 'file';this.fileBox.accept = '.pdf,application/pdf';this.fileBox.setAttribute('aria-label', 'PDF für den Formular-Start');
      this.fileState = el('p', 't-wf-hint', 'Hat der Workflow ein Formular mit Dateifeld, hier die Datei wählen. Sie wird lokal abgelegt und beim Freigeben Byte für Byte festgeschrieben.');
      this.fileBox.onchange = ()=>this.safe(async()=>{
        const f = this.fileBox.files[0];if(!f)return;if(f.size > 700000)throw new Error('Die Datei ist größer als 700 KB.');
        const label = this.fileLabel();if(!label)throw new Error('Dieser Workflow hat kein Formular mit Dateifeld.');
        const bytes = new Uint8Array(await f.arrayBuffer());let bin = '';for(let i = 0; i < bytes.length; i += 8192)bin += String.fromCharCode(...bytes.subarray(i, i + 8192));
        const up = await this.call('workflow', null, 'eingabe_hochladen', {name: f.name, data: root.btoa(bin)});
        const inputs = {};inputs[label] = {datei: up.datei, name: up.name};this.input.value = JSON.stringify(inputs);
        this.fileState.textContent = f.name + ' · ' + up.groesse + ' Bytes abgelegt, Kennung ' + up.datei.slice(0, 12) + ' … Jetzt „Lauf zur Freigabe vorlegen“.';
      });
      this.tableName = el('input');this.tableName.placeholder = 'Tabellenname, z. B. Auftraege';this.tableName.setAttribute('aria-label', 'Tabellenname');
      this.tableFile = el('input');this.tableFile.type = 'file';this.tableFile.accept = '.csv,.json,text/csv,application/json';this.tableFile.setAttribute('aria-label', 'CSV- oder JSON-Datei für die Tabelle');
      this.tableList = el('p', 't-wf-hint', 'Noch keine Tabellen.');
      const load = button('Tabelle laden (ersetzt den Inhalt)', ()=>this.safe(async()=>{
        const f = this.tableFile.files[0];if(!f||!this.tableName.value.trim())throw new Error('Tabellenname und Datei wählen.');
        const out = await this.call('workflow', null, 'tabelle_importieren', {name: this.tableName.value.trim(), text: await f.text(), ersetzen: true});
        this.notice('Tabelle ' + out.name + ': ' + out.zeilen + ' Zeilen geladen.');await this.refresh();
      }));
      box.append(el('h3', '', 'Eingabedatei'), this.fileBox, this.fileState, el('h3', '', 'Lokale Tabellen'),
        el('p', 't-wf-hint', 'Ersatz für n8n-„Data tables“ (Aufträge, Positionen, Kostenübersicht …). CSV mit Semikolon oder Komma, oder JSON als Liste von Objekten.'), this.tableName, this.tableFile, load, this.tableList);
      run.append(box);
    },
    fileLabel(){
      const n = this.state.doc.nodes.find(x=>String(x.type).endsWith('.formTrigger'));if(!n)return null;
      const f = (((n.parameters || {}).formFields || {}).values || []).find(v=>v.fieldType === 'file');return f ? f.fieldLabel : null;
    },
    lokalText(run){
      const r = run.result;if(!r || r.profile !== 'sedra-lokal-v1')return null;
      const lines = [(r.status === 'completed' ? 'Lauf abgeschlossen' : 'Lauf fehlgeschlagen') + ' · SEDRA-Eigenablauf · ' + (r.dauer_ms || 0) + ' ms'];
      if(r.status !== 'completed')lines.push('Fehler' + (r.fehler_knoten ? ' in „' + r.fehler_knoten + '“' : '') + ': ' + (r.fehler_text || r.error));
      (r.knoten || []).forEach(k=>lines.push((k.status === 'ok' ? '✓ ' : '– ') + k.name + ' (' + k.art + ')' + (k.status === 'ok' ? ' → ' + (k.ausgang || []).join(' / ') : ' ohne Daten übersprungen')));
      (r.hinweise || []).forEach(h=>lines.push('Hinweis: ' + h));
      if((r.tabellen_geschrieben || []).length)lines.push('Geschrieben in Tabelle: ' + r.tabellen_geschrieben.join(', '));
      if(r.output)lines.push('', 'Ergebnis:', JSON.stringify(r.output, null, 2));
      return lines.join('\n');
    }
  };};
})();
