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
      this.tableList = el('div', 't-wf-tablelist');this.tableList.append(el('p', 't-wf-hint', 'Noch keine Tabellen.'));this.tableView = el('div', 't-wf-tableview');
      const load = button('Tabelle laden (ersetzt den Inhalt)', ()=>this.safe(async()=>{
        const f = this.tableFile.files[0];if(!f||!this.tableName.value.trim())throw new Error('Tabellenname und Datei wählen.');
        const out = await this.call('workflow', null, 'tabelle_importieren', {name: this.tableName.value.trim(), text: await f.text(), ersetzen: true});
        this.notice('Tabelle ' + out.name + ': ' + out.zeilen + ' Zeilen geladen.');await this.refresh();
      }));
      box.append(el('h3', '', 'Eingabedatei'), this.fileBox, this.fileState, el('h3', '', 'Lokale Tabellen'),
        el('p', 't-wf-hint', 'Ersatz für n8n-„Data tables“ (Aufträge, Positionen, Kostenübersicht …). CSV mit Semikolon oder Komma, oder JSON als Liste von Objekten.'), this.tableName, this.tableFile, load, this.tableList, this.tableView);
      run.append(box);
    },
    // Liste der Tabellen als Knöpfe; ein Klick zeigt die Zeilen zum Ansehen und Bearbeiten.
    listeTabellen(tabellen){
      if(!this.tableList)return;this.tableList.replaceChildren();
      if(!(tabellen || []).length){this.tableList.append(el('p', 't-wf-hint', 'Noch keine Tabellen.'));return;}
      tabellen.forEach(t=>this.tableList.append(button(t.name + ' (' + t.zeilen + ' Zeilen)', ()=>this.safe(()=>this.zeigeTabelle(t.name)))));
    },
    async zeigeTabelle(name){
      const t = await this.call('workflow', null, 'tabelle_lesen', {name});
      const view = this.tableView;view.replaceChildren(el('h3', '', t.name + ' · ' + t.anzahl + ' Zeilen' + (t.anzahl > t.zeilen.length ? ' (die ersten ' + t.zeilen.length + ')' : '')));
      const spalten = t.spalten.length ? t.spalten : ['wert'];
      const wert = text=>/^-?\d+(\.\d+)?$/.test(text) ? Number(text) : text === 'true' ? true : text === 'false' ? false : text === 'null' ? null : text;
      const tabelle = el('table', 't-wf-table'), kopf = el('tr');['id'].concat(spalten, ['']).forEach(c=>kopf.append(el('th', '', c)));tabelle.append(kopf);
      const zeile = (z)=>{
        const tr = el('tr'), felder = {};tr.append(el('td', '', z ? String(z.id) : 'neu'));
        spalten.forEach(c=>{const td = el('td'), i = el('input');i.value = z && z[c] !== null && z[c] !== undefined ? String(z[c]) : '';i.setAttribute('aria-label', c);felder[c] = i;td.append(i);tr.append(td);});
        const aktion = el('td');
        aktion.append(button('Speichern', ()=>this.safe(async()=>{
          const werte = {};spalten.forEach(c=>{if(felder[c].value !== '')werte[c] = wert(felder[c].value);});
          if(!Object.keys(werte).length)throw new Error('Mindestens ein Feld ausfüllen.');
          await this.call('workflow', null, 'tabelle_zeile_speichern', {name: t.name, id: z ? z.id : null, werte});await this.refresh();await this.zeigeTabelle(t.name);this.notice('Zeile gespeichert.');
        })));
        if(z)aktion.append(button('Löschen', ()=>this.safe(async()=>{
          if(!root.confirm('Zeile ' + z.id + ' aus „' + t.name + '“ löschen?'))return;
          await this.call('workflow', null, 'tabelle_zeile_loeschen', {name: t.name, id: z.id});await this.refresh();await this.zeigeTabelle(t.name);this.notice('Zeile gelöscht.');
        })));
        tr.append(aktion);return tr;
      };
      t.zeilen.forEach(z=>tabelle.append(zeile(z)));tabelle.append(zeile(null));
      const wrap = el('div', 't-wf-tablewrap');wrap.append(tabelle);view.append(wrap, button('Schließen', ()=>view.replaceChildren()));
    },
    // Ergebnis eines Eigenablauf-Laufs: je Knoten aufklappbar. Gibt false zurück, wenn es kein Eigenablauf-Ergebnis ist.
    lokalRender(run){
      const r = run.result;if(!r || r.profile !== 'sedra-lokal-v1')return false;
      const out = this.output;out.replaceChildren();out.style.whiteSpace = 'normal';
      out.append(el('p', r.status === 'completed' ? '' : 'bad', (r.status === 'completed' ? 'Lauf abgeschlossen' : 'Lauf fehlgeschlagen') + ' · SEDRA-Eigenablauf · ' + (r.dauer_ms || 0) + ' ms'));
      if(r.status !== 'completed')out.append(el('p', 'bad', 'Fehler' + (r.fehler_knoten ? ' in „' + r.fehler_knoten + '“' : '') + ': ' + (r.fehler_text || r.error)));
      (r.knoten || []).forEach(k=>{
        const d = el('details'), ok = k.status === 'ok';
        d.append(el('summary', '', (ok ? '✓ ' : '– ') + k.name + ' (' + k.art + ')' + (ok ? ' → ' + (k.ausgang || []).join(' / ') : ' · ohne Daten übersprungen')));
        d.append(el('pre', '', ok ? JSON.stringify(k.beispiel, null, 2) : 'Dieser Knoten bekam keine Einträge.'));out.append(d);
      });
      (r.hinweise || []).forEach(h=>out.append(el('p', 't-wf-hint', 'Hinweis: ' + h)));
      if((r.tabellen_geschrieben || []).length)out.append(el('p', '', 'Geschrieben in Tabelle: ' + r.tabellen_geschrieben.join(', ')));
      if(r.output){const d = el('details');d.open = true;d.append(el('summary', '', 'Ergebnis'), el('pre', '', JSON.stringify(r.output, null, 2)));out.append(d);}
      return true;
    },
    fileLabel(){
      const n = this.state.doc.nodes.find(x=>String(x.type).endsWith('.formTrigger'));if(!n)return null;
      const f = (((n.parameters || {}).formFields || {}).values || []).find(v=>v.fieldType === 'file');return f ? f.fieldLabel : null;
    }
  };};
})();
