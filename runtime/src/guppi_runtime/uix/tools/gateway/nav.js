// Werkzeug „KI GateWay“ – das linke Menü und die Übersicht (Skizze des Captains, 19.10.2026). Jeder Eintrag führt in eine Ansicht
// oder öffnet eine Funktion; die Farben zeigen den Status (grün: nichts wartet, gelb: wartet auf dich, rot: angehalten).
// Die Zahlen kommen aus der Vorgangsliste, die das Werkzeug schon hat – kein eigener Aufruf. Stil: .t-gateway-…, Farben nur Token.
// Wird vor tool.js geladen; stellt root.sedraGatewayNav bereit. Der Kern (`zaehle`, `passt`) ist rein und wird mit node geprüft.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // Menü: id, Name, Zeile darunter. Reihenfolge wie in der Skizze, Vorgänge und Dateien aus dem bisherigen Werkzeug dazwischen.
  const MENU = [
    ['uebersicht', 'Überblick', 'Was wartet und was läuft'],
    ['vorgaenge', 'Vorgänge', 'Anfragen anlegen und prüfen'],
    ['dateien', 'Dateien', 'Hochgeladene Originale und Fassungen'],
    ['regeln', 'Regeln', 'Regelbuch und gemerkte Vorgaben'],
    ['ausprobieren', 'Selbst ausprobieren', 'Übung und Frage an SEDRA'],
    ['verlauf', 'Verlauf', 'Alle Vorgänge, neueste zuerst']
  ];
  // Filter aus den Kacheln: welcher Zustand, und wie er heißt
  const FILTER = {neu: ['NEU', 'Ungeprüft'], freigabe: ['GEPRUEFT', 'Wartet auf deine Freigabe'], entwurf: ['ENTWURF', 'Entwurf zur Prüfung']};
  const WARTET = ['NEU', 'GEPRUEFT', 'ENTWURF', 'WARTET'];

  // rein: die Zahlen für den Überblick (node prüft das)
  function zaehle(liste, heute){
    const z = {heute: 0, heuteGeprueft: 0, neu: 0, geprueft: 0, gesperrt: 0, entwurf: 0, wartet: 0, lokal: 0, cloud: 0};
    (liste || []).forEach(v=>{
      if((v.erstellt || '').slice(0, 10) === heute){ z.heute += 1; if(v.klasse) z.heuteGeprueft += 1; }
      if(v.zustand === 'NEU') z.neu += 1;
      if(v.zustand === 'GEPRUEFT') z.geprueft += 1;
      if(v.zustand === 'GESPERRT') z.gesperrt += 1;
      if(v.zustand === 'ENTWURF') z.entwurf += 1;
      if(WARTET.indexOf(v.zustand) >= 0) z.wartet += 1;
      if(v.weg === 'LOCAL_ONLY') z.lokal += 1; else if(v.weg) z.cloud += 1;
    });
    return z;
  }

  // rein: passt ein Vorgang zum gewählten Filter? Ohne Filter passen alle.
  function passt(v, filter){
    if(!filter) return true;
    return !!FILTER[filter] && v.zustand === FILTER[filter][0];
  }

  function heute(){ return new Date().toLocaleDateString('sv-SE'); }      // YYYY-MM-DD in der Ortszeit des Rechners

  function kachel(tone, titel, gross, zeile, fn){
    const k = d().el('div', 't-gateway-tile ' + (tone || ''));
    k.append(d().el('small', 's-muted', titel), d().el('b', 't-gateway-tile-zahl', String(gross)), d().el('small', 's-muted', zeile));
    d().clickable(k, fn);
    return k;
  }

  // Ansicht „Überblick“: vier Kacheln wie in der Skizze, darunter, was auf dich wartet
  function uebersicht(tool, list, z){
    const box = d().el('div', 't-gateway-ueb');
    const regeln = (list.regeln || []).length;
    box.append(d().el('div', 't-gateway-banner ok', 'Schützt · ' + regeln + ' Regeln greifen · Regelwerk ' + (list.regelwerk || '') + ' · Policy ' + (list.policy_version || '')));
    const wechsel = (ansicht, filter)=>()=>{ tool.ansicht = ansicht; tool.filter = filter || null; tool.refresh(); };
    const kacheln = d().el('div', 't-gateway-tiles');
    kacheln.append(
      kachel(z.gesperrt ? 'bad' : z.neu ? 'warn' : z.heute ? 'ok' : '', 'Eingang prüfen', z.heuteGeprueft,
             z.heute + ' Anfragen heute · ' + z.gesperrt + ' gesperrt', wechsel('vorgaenge', z.neu ? 'neu' : null)),
      kachel(z.geprueft ? 'warn' : 'ok', 'Entscheidung', z.geprueft,
             z.geprueft ? 'wartet auf deine Freigabe' : 'nichts wartet', wechsel('vorgaenge', 'freigabe')),
      kachel(list.modell ? 'ok' : 'warn', 'KI', z.lokal + z.cloud,
             z.lokal + ' lokal · ' + z.cloud + ' Cloud' + (list.modell ? '' : ' · kein Modell geladen'), wechsel('vorgaenge', null)),
      kachel(z.entwurf ? 'warn' : 'ok', 'Antwort prüfen', z.entwurf,
             z.entwurf ? 'zur menschlichen Prüfung' : 'nichts zu prüfen', wechsel('vorgaenge', z.entwurf ? 'entwurf' : null)));
    box.append(kacheln);
    box.append(d().el('div', 't-gateway-colhead', 'Wartet auf dich'));
    const offen = (list.vorgaenge || []).filter(v=>WARTET.indexOf(v.zustand) >= 0);
    if(!offen.length) box.append(d().empty('Nichts wartet auf dich. Neue Anfragen legst du unter Vorgänge an.'));
    offen.forEach(v=>{
      const row = d().el('div', 't-gateway-row');
      row.append(d().el('b', null, v.titel), d().el('span', 't-gateway-pill ' + tool.tone(v), v.zustand_wort || v.zustand),
                 d().el('small', 's-muted', v.id));
      d().clickable(row, ()=>tool.ctx.shell.open({type: 'gateway', id: v.id, title: v.titel}));
      box.append(row);
    });
    return box;
  }

  // Ansicht „Selbst ausprobieren“: eine Übung (ein Vorgang mit „Übung:“ im Titel) und die Frage an SEDRA
  function ausprobieren(tool, list){
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
    box.append(form);
    box.append(d().el('div', 't-gateway-colhead', 'Frag SEDRA'), frageSedra(tool, null));
    return box;
  }

  // Ansicht „Verlauf“: alle Vorgänge, neueste zuerst; ein Klick öffnet den Vorgang mit seinem vollständigen Verlauf
  function verlauf(tool, list){
    const box = d().el('div', 't-gateway-verlauf-liste');
    box.append(d().el('div', 't-gateway-colhead', 'Verlauf'),
               d().el('small', 's-muted', 'Alle Vorgänge. Ein Klick öffnet den Vorgang mit seinen Stationen und seinem Verlauf.'));
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

  // Das Gerüst: links das Menü mit Zählern, rechts die gewählte Ansicht
  function gerust(tool, list){
    const ansicht = tool.ansicht || 'uebersicht';
    const z = zaehle(list.vorgaenge, heute());
    const zaehler = {uebersicht: z.wartet, vorgaenge: (list.vorgaenge || []).length, dateien: (list.dateien || []).length,
                     regeln: (list.regeln || []).length, verlauf: (list.vorgaenge || []).length};
    const wrap = d().el('div', 't-gateway-layout');
    const menu = d().el('nav', 't-gateway-nav'); menu.setAttribute('aria-label', 'KI GateWay Menü');
    MENU.forEach(([id, name, zeile])=>{
      const b = d().el('button', 't-gateway-navitem' + (id === ansicht ? ' on' : ''));
      b.type = 'button';
      b.append(d().el('b', null, name), d().el('small', 's-muted', zeile));
      const n = zaehler[id];
      if(n !== undefined){
        const warn = id === 'uebersicht' && n > 0;
        b.append(d().el('span', 't-gateway-navn' + (warn ? ' warn' : ''), String(n)));
      }
      b.addEventListener('click', ()=>{ tool.ansicht = id; tool.filter = null; tool.refresh(); });
      menu.append(b);
    });
    const inhalt = d().el('div', 't-gateway-inhalt');
    if(ansicht === 'uebersicht') inhalt.append(uebersicht(tool, list, z));
    else if(ansicht === 'vorgaenge') inhalt.append(tool.vorgaengeBox(list));
    else if(ansicht === 'dateien') inhalt.append(root.sedraGatewayArbeit.dateien(tool, list));
    else if(ansicht === 'regeln'){ inhalt.append(root.sedraGatewayRegeln.draw(list)); root.sedraGatewayArbeit.vorgabenListe(tool, inhalt); }
    else if(ansicht === 'ausprobieren') inhalt.append(ausprobieren(tool, list));
    else if(ansicht === 'verlauf') inhalt.append(verlauf(tool, list));
    wrap.append(menu, inhalt);
    return wrap;
  }

  function filterName(filter){ return FILTER[filter] ? FILTER[filter][1] : ''; }

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

  root.sedraGatewayNav = {gerust, zaehle, passt, filterName, frageSedra, MENU, FILTER};
  if(typeof module !== 'undefined' && module.exports) module.exports = {zaehle, passt, MENU, FILTER};
})();
