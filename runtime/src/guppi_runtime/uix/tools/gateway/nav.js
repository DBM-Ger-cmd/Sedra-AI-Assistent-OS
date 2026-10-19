// Werkzeug „KI GateWay“ – die Ansichten. Das Menü steht im Baum links (cockpit/tree.js). Wo es keinen Baum gibt (andere
// Oberflächen), zeigt das Werkzeug sein Menü selbst. Die Überblick-, Regel-, Prüf- und Verlauf-Ansichten des Schutzes zeigt das
// Werkzeug „schutz“ (KI GateWay · Schutz), eingebettet ohne eigene Reiter – so gibt es jede Funktion nur einmal.
// Stil: .t-gateway-…; Farben nur Token. Wird vor tool.js geladen; stellt root.sedraGatewayNav bereit.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // Menü: id, Name, Zeile darunter. Die Reihenfolge wie in der Skizze.
  const MENU = [
    ['uebersicht', 'Überblick', 'Stationen und was wartet'],
    ['vorgaenge', 'Vorgänge', 'Anfragen anlegen und prüfen'],
    ['dateien', 'Dateien', 'Originale und Fassungen'],
    ['regeln', 'Regeln', 'Regelbuch und Schärfe'],
    ['ausprobieren', 'Selbst ausprobieren', 'Text prüfen, Übung, Frage'],
    ['verlauf', 'Verlauf', 'Vorgänge und Schutz heute']
  ];
  // Diese Ansichten zeigt das Werkzeug „schutz“
  const SCHUTZ = ['uebersicht', 'regeln', 'ausprobieren', 'verlauf'];

  // Das Werkzeug „schutz“ in den Bereich einbetten; ein früherer Aufbau wird vorher abgebaut.
  function schutzEinbetten(tool, host, ansicht){
    const schutz = root.sedra && root.sedra.tools && root.sedra.tools.get('schutz');
    if(!schutz){ host.append(d().empty('Das Werkzeug „Schutz“ fehlt – diese Ansicht kann nichts zeigen.')); return; }
    if(tool.schutzAktiv && tool.schutzAktiv.host) tool.schutzAktiv.unmount();
    const ctx = Object.assign({}, tool.ctx, {object: {type: 'gateway', id: 'alle', ansicht, eingebettet: true}});
    tool.schutzAktiv = schutz;
    schutz.mount(host, ctx);
  }

  // Beim Verlassen des Werkzeugs: den eingebetteten Schutz abbauen, damit keine Ereignisse mehr hängen bleiben.
  function aufraeumen(tool){
    if(tool.schutzAktiv && tool.schutzAktiv.host) tool.schutzAktiv.unmount();
    tool.schutzAktiv = null;
  }

  // das Menü im Werkzeug – nur ohne Baum
  function menu(tool, ansicht, list){
    const nav = d().el('nav', 't-gateway-nav'); nav.setAttribute('aria-label', 'KI GateWay Menü');
    const zaehler = {vorgaenge: (list.vorgaenge || []).length, dateien: (list.dateien || []).length, regeln: (list.regeln || []).length, verlauf: (list.vorgaenge || []).length};
    MENU.forEach(([id, name, zeile])=>{
      const b = d().el('button', 't-gateway-navitem' + (id === ansicht ? ' on' : ''));
      b.type = 'button';
      b.append(d().el('b', null, name), d().el('small', 's-muted', zeile));
      if(zaehler[id] !== undefined) b.append(d().el('span', 't-gateway-navn', String(zaehler[id])));
      b.addEventListener('click', ()=>{ tool.ansicht = id; tool.refresh(); });
      nav.append(b);
    });
    return nav;
  }

  // Die Ansicht „Selbst ausprobieren“ des GateWay selbst: eine Übung und die Frage an SEDRA. Die Prüfung von Texten
  // kommt aus dem Schutz darüber.
  function uebung(tool, list){
    const box = d().el('div', 't-gateway-try');
    box.append(d().el('div', 't-gateway-colhead', 'Übung'),
               d().el('small', 's-muted', 'Eine Übung legt einen Vorgang an, den du Schritt für Schritt durchgehst. Nichts wird versendet. Füge dort einen Beispieltext ein, zum Beispiel: „Bereite eine kurze Übersicht für die nächste Projektabstimmung vor.“'));
    const titel = d().el('input'); titel.value = 'Projektabstimmung'; titel.setAttribute('aria-label', 'Titel der Übung');
    const wunsch = d().el('select'); wunsch.setAttribute('aria-label', 'Wunsch der Übung');
    [['local', 'Lokale KI' + (list.modell ? ' · ' + list.modell : ' · kein Modell geladen')], ['cloud', 'Cloud-KI']].forEach(([v, t])=>{
      const op = d().el('option', null, t); op.value = v; wunsch.append(op);
    });
    const form = d().el('div', 't-gateway-new');
    form.append(titel, wunsch, d().button('Übung anlegen und öffnen', ()=>tool.neu('Übung: ' + (titel.value.trim() || 'Projektabstimmung'), wunsch.value), 'p'));
    box.append(form, d().el('div', 't-gateway-colhead', 'Frag SEDRA'), frageSedra(tool, null));
    return box;
  }

  // Die Vorgänge in der Reihenfolge, neueste zuerst; ein Klick öffnet den Vorgang mit seinen Stationen und seinem Verlauf.
  function vorgangsVerlauf(tool, list){
    const box = d().el('div', 't-gateway-verlauf-liste');
    box.append(d().el('div', 't-gateway-colhead', 'Vorgänge'));
    const liste = list.vorgaenge || [];
    if(!liste.length) box.append(d().empty('Noch kein Vorgang.'));
    liste.forEach(v=>{
      const row = d().el('div', 't-gateway-row');
      row.append(d().el('small', 's-muted', (v.erstellt || '').replace('T', ' ').slice(0, 16)), d().el('b', null, v.titel),
                 d().el('span', 't-gateway-pill ' + tool.tone(v), v.zustand_wort || v.zustand));
      d().clickable(row, ()=>tool.ctx.shell.open({type: 'gateway', id: v.id, title: v.titel}));
      box.append(row);
    });
    return box;
  }

  // Das Gerüst: ohne Baum ein Menü links, daneben die gewählte Ansicht
  function gerust(tool, list){
    const ansicht = tool.ansicht || 'uebersicht';
    const wrap = d().el('div', 't-gateway-layout');
    if(!(tool.ctx.object && tool.ctx.object.imBaum)) wrap.append(menu(tool, ansicht, list));
    const inhalt = d().el('div', 't-gateway-inhalt');
    if(ansicht === 'vorgaenge') inhalt.append(tool.vorgaengeBox(list));
    else if(ansicht === 'dateien') inhalt.append(root.sedraGatewayArbeit.dateien(tool, list));
    else{
      const schutzHost = d().el('div', 't-gateway-schutz');
      inhalt.append(schutzHost);
      schutzEinbetten(tool, schutzHost, ansicht);
      if(ansicht === 'regeln'){ inhalt.append(root.sedraGatewayRegeln.draw(list)); root.sedraGatewayArbeit.vorgabenListe(tool, inhalt); }
      if(ansicht === 'ausprobieren') inhalt.append(uebung(tool, list));
      if(ansicht === 'verlauf') inhalt.append(vorgangsVerlauf(tool, list));
    }
    wrap.append(inhalt);
    return wrap;
  }

  // B6-G-03: „Frag SEDRA“ – die Wissensbasis antwortet ohne Modell; Knöpfe öffnen, nichts läuft von allein.
  function frageSedra(tool, v){
    const box = d().el('div', 't-gateway-frag');
    const inp = d().el('input'); inp.placeholder = 'Frag SEDRA: Was muss ich als Nächstes machen? Wo ist der Fehler in diesem Text: …'; inp.setAttribute('aria-label', 'Frage an SEDRA');
    const out = d().el('div', 't-gateway-frag-out');
    const ask = async()=>{
      const frage = inp.value.trim(); if(!frage) return;
      try{
        const a = await tool.ctx.api('/api/gateway/frage', {method: 'POST', body: {frage, vorgang: v ? v.id : ''}});
        out.replaceChildren();
        const note = d().el('div', 's-note'); note.textContent = a.reply; out.append(note);
        const row = d().el('div', 's-row');
        (a.ui_actions || []).forEach(x=>{ if(x.kind === 'open' && x.object) row.append(d().button(x.title || 'Öffnen', ()=>tool.ctx.shell.open(x.object))); });
        row.append(d().button('Merken', async()=>{ await tool.ctx.api('/api/gateway/wissen', {method: 'POST', body: {frage, antwort: a.reply}}); tool.ctx.shell.notify('Gemerkt – steht beim nächsten Mal in der Wissensbasis.', 'note'); }));
        row.append(d().el('small', 's-muted', a.quelle || ''));
        out.append(row);
      }catch(err){ out.replaceChildren(d().el('div', 's-note bad', 'Keine Antwort: ' + err.message)); }
    };
    inp.addEventListener('keydown', e=>{ if(e.key === 'Enter') ask(); });
    box.append(d().el('div', 't-gateway-colhead', 'Frag SEDRA'), inp, d().button('Fragen', ask), out);
    return box;
  }

  root.sedraGatewayNav = {gerust, frageSedra, aufraeumen, MENU, SCHUTZ};
  if(typeof module !== 'undefined' && module.exports) module.exports = {MENU, SCHUTZ};
})();
