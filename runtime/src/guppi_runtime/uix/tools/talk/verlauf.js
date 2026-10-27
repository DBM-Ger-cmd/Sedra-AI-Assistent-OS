// Werkzeug „Gespräch“ – der Verlauf vom Server (Vertrag 1.1, SPEC_DOCK_OHNE_NEUAUFBAU_v1 §9.2; Captain 26.10.2026 E4).
// Der Server hält fest, was über die Routen des Gesprächs ging (Frage, und die Antwort, die der Captain gesehen hat). Nach einem
// Neuladen oder Shell-Wechsel holt das Gespräch ihn hier ab und zeigt ihn wieder; im Browser liegt nichts davon.
// `verlaufZeilen` und `alsHistory` sind rein (node prüft sie); `laden` und `leeren` brauchen das Werkzeug. Vor tool.js geladen.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const MAX_HISTORY = 8;                 // so viel schickt das Gespräch dem Modell mit (wie chat_reply es annimmt)

  // Zeilen für das Protokoll aus den Einträgen des Servers (rein): wer, Text, Ton
  function verlaufZeilen(eintraege){
    return (eintraege || []).filter(e=>e && (e.rolle === 'user' || e.rolle === 'assistant') && typeof e.text === 'string')
      .map(e=>({wer: e.rolle === 'user' ? 'Du' : 'SEDRA', text: e.text, ton: e.rolle === 'user' ? 'me' : '', modell: e.modell || ''}));
  }

  // die History, die das Gespräch dem Modell mitschickt (rein): die letzten Einträge, Rolle und Inhalt
  function alsHistory(eintraege){
    return (eintraege || []).filter(e=>e && (e.rolle === 'user' || e.rolle === 'assistant') && typeof e.text === 'string')
      .slice(-MAX_HISTORY).map(e=>Object.assign({role: e.rolle, content: e.text.slice(0, 4000)}, e.nur_lokal ? {nurLokal: true} : {}));
  }

  // SPEC_SHELL_WISSEN_v1 §4.6 (rein): was in einen Cloud-Weg darf – nie eine Antwort mit Personenbezug aus dem Wissen, und nur Rolle und Inhalt
  function fuerCloud(history){
    return (history || []).filter(h=>h && !h.nurLokal).map(h=>({role: h.role, content: h.content}));
  }
  // der Körper für /api/chat/reply; `wissen` schaltet die Shell ein (Vorgabe gespraech.wissen), sonst ist es aus
  function antwortKoerper(tool, text){
    const body = {mission_id: tool.mission || '', text, history: (tool.history || []).slice(0, -1).map(h=>({role: h.role, content: h.content})), attachments: [], vorgang: tool.vorgang || ''};
    if(tool.ctx && tool.ctx.shell && tool.ctx.shell.wissen) body.wissen = true;
    return body;
  }
  // die Antwort in die History; mit Personenbezug aus dem Wissen nur lokal, und der Captain liest es einmal
  function antwortMerken(tool, out){
    const w = out && out.wissen;
    tool.history.push(Object.assign({role: 'assistant', content: out.reply}, w && w.personenbezug ? {nurLokal: true} : {}));
    if(w && w.ids && w.ids.length) zitateVerlinken(tool);
    if(w && w.personenbezug) tool.say('In den Fundstellen steckt Personenbezug: diese Antwort geht in keinen Cloud-Weg.', 'note');
  }
  // die Kennungen [W…] der letzten Antwort werden Verweise: ein Klick zeigt die Fundstelle (Wissen öffnen, wissen.auswahl senden)
  function zitateVerlinken(tool){
    const Z = root.sedraWissenZitate, zeilen = tool.log ? tool.log.querySelectorAll('.t-talk-line') : [];
    const zeile = zeilen[zeilen.length - 1], span = zeile && zeile.querySelector('span');
    if(!Z || !Z.zitatKnoten || !span) return;
    const text = span.textContent; span.textContent = '';
    Z.zitatKnoten(span, text, id=>{
      tool.ctx.shell.open({type: 'wissen', id: 'speicher', title: 'Wissen'});
      tool.ctx.bus.emit('wissen.auswahl', {id});
    });
  }

  // beim Einhängen: den Verlauf holen, zeigen und als History übernehmen. Ohne Verbindung bleibt das Gespräch leer, wie bisher.
  async function laden(tool){
    tool.ctx.bus.on('wissen.auswahl', e=>fundstelleAnhaengen(tool, e));
    let out = null;
    try{ out = await tool.ctx.api('/api/chat/verlauf'); }catch(_e){ return 0; }
    const e = (out && out.eintraege) || [];
    if(!e.length || !tool.log) return 0;
    const trenn = root.sedraDom.el('p', 't-talk-line note t-talk-alt', 'Bisher im Gespräch (' + e.length + (e.length === 1 ? ' Eintrag' : ' Einträge') + '):');
    tool.log.prepend(trenn);
    let nach = trenn;
    verlaufZeilen(e).forEach(z=>{
      const row = root.sedraDom.el('p', 't-talk-line t-talk-alt' + (z.ton ? ' ' + z.ton : ''));
      row.append(root.sedraDom.el('b', null, z.wer), root.sedraDom.el('span', null, ' ' + z.text));
      nach.after(row); nach = row;
    });
    tool.history = alsHistory(e).concat(tool.history || []);
    tool.log.scrollTop = tool.log.scrollHeight;
    return e.length;
  }

  // „Gespräch leeren“: auf dem Server (Audit ohne Inhalt) und im Protokoll; die History ist danach leer
  async function leeren(tool){
    await tool.ctx.api('/api/chat/verlauf/leeren', {method: 'POST', body: {}});
    tool.history = [];
    if(tool.log) tool.log.replaceChildren();
    tool.say('Gespräch geleert.', 'note');
  }

  // „Ins Gespräch“ aus dem Wissen (SPEC_WERKZEUG_WISSEN_v2 §3.2): die Kennung und die Stelle stehen danach im Eingabefeld
  function fundstelleAnhaengen(tool, e){
    if(!e || e.zweck !== 'gespraech' || !tool.input) return;
    const teil = '[' + e.id + ']' + (e.stelle ? ' (' + e.stelle + ')' : '') + ' ';
    tool.input.value = (tool.input.value ? tool.input.value.replace(/\s*$/, ' ') : '') + teil;
    try{ tool.input.focus(); }catch(_e){}
  }

  root.sedraTalkVerlauf = {fundstelleAnhaengen, verlaufZeilen, alsHistory, fuerCloud, antwortKoerper, antwortMerken, laden, leeren, MAX_HISTORY};
  if(typeof module !== 'undefined' && module.exports) module.exports = {verlaufZeilen, alsHistory, fuerCloud, antwortKoerper, MAX_HISTORY};
})();
