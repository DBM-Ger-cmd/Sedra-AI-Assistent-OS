// Geführte Schritte für die Seite „Ausführungen“ des SEDRA-Eigenablaufs: immer genau ein Schritt ist „Jetzt“, mit einer klaren Aufforderung und den passenden Knöpfen.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const NS = 'http://www.w3.org/2000/svg';
  function el(tag, cls, text){const x = document.createElement(tag);if(cls)x.className = cls;if(text !== undefined)x.textContent = text;return x;}
  function button(text, fn, primary){const b = el('button', primary ? 't-wf-primary' : '', text);b.type = 'button';b.onclick = fn;return b;}
  const kurz = name=>String(name || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
  function ico(name){
    const svg = document.createElementNS(NS, 'svg');svg.setAttribute('viewBox', '0 0 24 24');svg.setAttribute('aria-hidden', 'true');
    if(root.sedraWorkflowIcons)root.sedraWorkflowIcons.append(svg, name, 12, 12, 24);
    return svg;
  }
  const LAUFEND = ['CAPTAIN_REVIEW', 'READY', 'EXECUTE', 'VERIFY', 'PAUSED'];
  root.sedraWorkflowSchritte = function(){return {
    buildSchritte(run){
      [...run.children].forEach((c, i)=>{if(i > 0 && !c.classList.contains('t-wf-lokal'))c.classList.add('t-wf-classic');});      // die alten Knöpfe, solange die Schritte führen
      this.stepsNext = el('p', 't-wf-next');this.stepsNext.setAttribute('role', 'status');
      this.steps = el('ol', 't-wf-steps');
      this.advanced = button('Erweitert: Eingaben als JSON und alle Knöpfe', ()=>{this.erweitert = !this.erweitert;this.updateSteps();});this.advanced.className = 't-wf-linkbtn';
      run.insertBefore(this.stepsNext, run.children[1]);run.insertBefore(this.steps, run.children[2]);run.insertBefore(this.advanced, run.children[3]);
    },
    updateSteps(){
      if(!this.steps || this.dead)return;
      const ex = this.exec || {}, own = ex.profile === 'sedra-lokal-v1';
      this.runSection.classList.toggle('t-wf-gefuehrt', own && !this.erweitert);
      this.steps.hidden = this.stepsNext.hidden = this.advanced.hidden = !own;
      if(!own)return;
      const brauch = ex.liest || [], haben = (this.tabellenListe || []).filter(t=>t.zeilen > 0).map(t=>kurz(t.name)), fehlt = brauch.filter(n=>!haben.includes(kurz(n)));
      const felder = ex.dateifelder || [];let ref = null;try{ref = JSON.parse(this.input.value);}catch(e){}
      const hatDatei = !felder.length || felder.every(l=>ref && ref[l] && ref[l].datei);
      const phase = this.runId && this.runWf === this.wid ? this.runState : null, laufend = LAUFEND.includes(phase), ende = phase === 'COMPLETE' || phase === 'FAILED';
      const bereit = !fehlt.length && hatDatei && !this.dirty();
      const S = [
        {icon: 'dataTable', titel: 'Daten bereit', fertig: !fehlt.length,
          sag: !fehlt.length ? (brauch.length ? 'Tabellen vorhanden: ' + brauch.join(', ') + '.' : 'Keine Tabellen nötig.') : 'Es fehlen Daten in: ' + fehlt.join(', ') + '. Unten unter „Tabellen“ eine CSV- oder JSON-Datei laden.',
          tun: ()=>[button('Tabellen öffnen', ()=>{this.lokalBox.open = true;this.lokalBox.scrollIntoView({block: 'center'});}, true)]},
        {icon: 'extractFromFile', titel: felder.length ? 'Rechnung als PDF wählen' : 'Eingabe', fertig: hatDatei,
          sag: hatDatei ? (felder.length ? 'Datei ist abgelegt.' : 'Keine Datei nötig.') : 'Wähle die PDF, die geprüft werden soll. Sie wird nur lokal abgelegt.',
          tun: ()=>felder.length ? [button('PDF auswählen …', ()=>this.fileBox.click(), !hatDatei), this.fileState, this.fileBox] : []},
        {icon: 'bolt', titel: 'Zur Freigabe vorlegen', fertig: !!phase,
          sag: this.dirty() ? 'Der Workflow hat ungespeicherte Änderungen. Erst speichern, dann vorlegen.' : 'SEDRA legt den Lauf dem Captain vor. Dabei läuft noch nichts.',
          tun: ()=>{const b = button('Lauf zur Freigabe vorlegen', ()=>this.submitRun(), true);b.disabled = !bereit;return [b];}},
        {icon: 'human', titel: 'Freigeben und fortsetzen', fertig: ende,
          sag: laufend ? 'Jetzt du: 1. Posteingang öffnen. 2. Den Eintrag „n8n: …“ mit „einmal“ freigeben. 3. Das Fenster von SEDRA bestätigen (oder FREIGABE.bat freigeben B-XXXX). 4. Hier „Fortsetzen“.' : 'Wartet auf den Lauf.',
          tun: ()=>laufend ? [button('Posteingang öffnen', ()=>this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Freigaben'}), phase === 'CAPTAIN_REVIEW'),
            button('Nach Freigabe fortsetzen', ()=>this.safe(async()=>{await this.call('workflow_run', this.runId, 'fortsetzen');await this.showRun(this.runId);}), phase !== 'CAPTAIN_REVIEW'),
            button('Lauf beenden', ()=>this.safe(async()=>{await this.call('workflow_run', this.runId, 'abbrechen');await this.showRun(this.runId);}))] : []},
        {icon: 'end', titel: 'Ergebnis', fertig: ende,
          sag: phase === 'FAILED' ? 'Der Lauf ist fehlgeschlagen. Der Grund steht unten beim betroffenen Knoten.' : ende ? 'Fertig. Das Ergebnis steht unten, jeder Knoten ist aufklappbar.' : 'Erscheint hier, sobald der Lauf fertig ist.',
          tun: ()=>ende ? [button('Neuer Lauf', ()=>{this.runId = null;this.runState = null;this.input.value = '{}';this.fileBox.value = '';this.fileState.textContent = '';this.output.replaceChildren();this.updateSteps();}, true)] : []}
      ];
      const jetzt = S.findIndex(s=>!s.fertig);
      this.stepsNext.textContent = jetzt < 0 ? 'Fertig. Der Lauf ist abgeschlossen.' : 'Jetzt: Schritt ' + (jetzt + 1) + ' von ' + S.length + ' · ' + S[jetzt].titel;
      this.stepsNext.classList.toggle('ok', jetzt < 0);
      this.steps.replaceChildren(...S.map((s, i)=>{
        const art = s.fertig ? 'fertig' : i === jetzt ? 'jetzt' : 'spaeter';
        const li = el('li', 't-wf-step ' + art), icon = el('span', 't-wf-step-ico');icon.append(ico(s.fertig ? 'end' : s.icon));
        const head = el('div', 't-wf-step-head');head.append(el('span', 't-wf-step-nr', 'Schritt ' + (i + 1)), el('strong', '', s.titel),
          el('span', 't-wf-chip ' + art, s.fertig ? 'Erledigt' : i === jetzt ? 'Jetzt' : 'Danach'));
        const body = el('div', 't-wf-step-body');body.append(head);
        if(art !== 'spaeter')body.append(el('p', 't-wf-hint', s.sag));
        if(art === 'jetzt' || (i === 1 && art === 'fertig' && !phase)){const row = el('div', 't-wf-step-actions');row.append(...s.tun());if(row.children.length)body.append(row);}
        li.append(icon, body);return li;
      }));
      if(this.lokalBox && jetzt === 0)this.lokalBox.open = true;
    }
  };};
})();
