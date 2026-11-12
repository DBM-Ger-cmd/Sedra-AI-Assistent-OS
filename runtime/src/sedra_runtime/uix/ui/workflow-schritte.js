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
  const LAUFEND = ['CAPTAIN_REVIEW', 'READY', 'EXECUTE', 'VERIFY'];      // PAUSED = abgelehnt oder angehalten: dafür gibt es kein „Fortsetzen“
  root.sedraWorkflowSchritte = function(){return {
    buildSchritte(run){
      [...run.children].forEach((c, i)=>{if(i > 0 && !c.classList.contains('t-wf-lokal'))c.classList.add('t-wf-classic');});      // die alten Knöpfe, solange die Schritte führen
      this.stepsNext = el('p', 't-wf-next');this.stepsNext.setAttribute('role', 'status');
      this.steps = el('ol', 't-wf-steps');
      this.advanced = button('Erweitert: Eingaben als JSON und alle Knöpfe', ()=>{this.erweitert = !this.erweitert;this.updateSteps();});this.advanced.className = 't-wf-linkbtn';
      run.insertBefore(this.stepsNext, run.children[1]);run.insertBefore(this.steps, run.children[2]);run.insertBefore(this.advanced, run.children[3]);
    },
    // Freigabe als Fenster: öffnet sich, sobald ein Lauf auf den Captain wartet. „Jetzt freigeben“ ist die einzige Bestätigung (Klasse N, freigabeklasse.KLASSE_N_GATES);
    // danach läuft der Lauf von selbst weiter. Wäre ein Gate Klasse H, wartet das Fenster auf die Bestätigung außerhalb des Browsers (Windows-Fenster, FREIGABE.bat).
    async pruefeFreigabe(run){
      if(!run || run.state !== 'CAPTAIN_REVIEW' || this.gefragt === run.id || this.freigabeFenster || !(this.exec && this.exec.profile === 'sedra-lokal-v1'))return;
      this.gefragt = run.id;
      const offen = async()=>{const d = await this.ctx.api('/api/decisions').catch(()=>null);return d ? (d.items || []).find(x=>x.mission_id === run.id && x.kind === 'gate') : null;};
      const item = await offen();if(!item || this.dead)return;
      const dlg = el('dialog', 't-wf-freigabe'), status = el('p', 't-wf-hint');status.setAttribute('role', 'status');this.freigabeFenster = dlg;
      const kopf = el('div', 't-wf-freigabe-kopf'), sym = el('span', 't-wf-step-ico');sym.append(ico('human'));kopf.append(sym, el('h3', '', 'Freigabe erforderlich'));
      const risiken = el('ul');(item.risks || []).forEach(r=>risiken.append(el('li', '', r)));
      const zu = ()=>{if(dlg.open)dlg.close();dlg.remove();this.freigabeFenster = null;};
      const weiter = async()=>{zu();await this.call('workflow_run', run.id, 'fortsetzen');await this.showRun(run.id);this.notice('Freigegeben, der Lauf wurde fortgesetzt.');};
      const warten = ()=>{
        const bis = Date.now() + 300000, tick = async()=>{
          if(this.dead || !this.freigabeFenster)return;
          if(!(await offen()))return this.safe(weiter);
          if(Date.now() < bis)setTimeout(tick, 2000);else status.textContent = 'Keine Bestätigung erhalten. „Später“ wählen und im Posteingang freigeben.';
        };
        setTimeout(tick, 2000);
      };
      const knoepfe = el('div', 't-wf-step-actions'), sperre = ein=>knoepfe.querySelectorAll('button').forEach(b=>{b.disabled = !ein;});
      const antwort = way=>this.safe(async()=>{
        sperre(false);status.textContent = way === 'einmal' ? 'Freigabe wird angefordert …' : 'Wird abgelehnt …';
        try{
          await this.ctx.shell.decide(item.id, way);
          if(way === 'einmal')return weiter();
          zu();await this.showRun(run.id);
        }catch(e){
          const text = String(e && e.message || e);
          if(/wartet_auf_bestaetigung/.test(text)){status.textContent = 'Bestätige jetzt im Fenster von SEDRA (Windows) oder mit FREIGABE.bat. Dieses Fenster wartet und setzt den Lauf danach fort.';warten();setTimeout(()=>{if(this.freigabeFenster === dlg){sperre(true);status.textContent = 'Noch keine Antwort. Ein neues Windows-Fenster kannst du mit „Jetzt freigeben“ anfordern.';}}, 60000);}
          else{status.textContent = text;sperre(true);}
        }
      });
      knoepfe.append(button('Jetzt freigeben', ()=>antwort('einmal'), true), button('Ablehnen', ()=>antwort('ablehnen')), button('Später', zu));
      dlg.append(kopf, el('p', '', item.title || 'Lauf freigeben'), risiken, el('p', 't-wf-hint', item.note || ''), status, knoepfe);
      dlg.addEventListener('cancel', ()=>{this.freigabeFenster = null;});
      this.el.append(dlg);dlg.showModal();
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
      const phase = this.runId && this.runWf === this.wid ? this.runState : null, laufend = LAUFEND.includes(phase), pausiert = phase === 'PAUSED', ende = phase === 'COMPLETE' || phase === 'FAILED';
      const neu = ()=>{this.runId = null;this.runState = null;this.input.value = '{}';this.fileBox.value = '';this.fileState.textContent = '';this.output.replaceChildren();this.updateSteps();};
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
          sag: laufend ? 'Die Freigabe erscheint als Fenster. Mit „Jetzt freigeben“ gibst du diesen Lauf einmal frei; er startet sofort. Die Freigabe steht auch im Posteingang.' : pausiert ? 'Die Freigabe wurde abgelehnt, der Lauf ist angehalten. Es ist nichts gelaufen und nichts geschrieben worden. Lege den Lauf neu vor.' : 'Wartet auf den Lauf.',
          tun: ()=>laufend ? [button('Jetzt freigeben …', ()=>{this.gefragt = null;this.pruefeFreigabe({id: this.runId, state: phase});}, phase === 'CAPTAIN_REVIEW'),
            button('Posteingang öffnen', ()=>this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Freigaben'})),
            button('Nach Freigabe fortsetzen', ()=>this.safe(async()=>{await this.call('workflow_run', this.runId, 'fortsetzen');await this.showRun(this.runId);}), phase !== 'CAPTAIN_REVIEW'),
            button('Lauf beenden', ()=>this.safe(async()=>{await this.call('workflow_run', this.runId, 'abbrechen');await this.showRun(this.runId);}))] : pausiert ? [button('Neu vorlegen', neu, true)] : []},
        {icon: 'end', titel: 'Ergebnis', fertig: ende,
          sag: phase === 'FAILED' ? 'Der Lauf ist fehlgeschlagen. Der Grund steht unten beim betroffenen Knoten.' : ende ? 'Fertig. Das Ergebnis steht unten, jeder Knoten ist aufklappbar.' : 'Erscheint hier, sobald der Lauf fertig ist.',
          tun: ()=>ende ? [button('Neuer Lauf', neu, true)] : []}
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
