// Werkzeug „Wissen“ – das Plus: Wissen hinzufügen durch Ziehen oder durch den Windows-Dialog. Ein Browser gibt beim Ziehen nie den Pfad weiter,
// nur den Inhalt; die Dateien gehen deshalb in Teilstücken (unter 1 MB je Anfrage) in den Eingang des Projekts (Verb eingang_ablegen). Der Dialog
// (Verb explorer_waehlen) öffnet sich auf dem Rechner von SEDRA und kopiert die Wahl in einen Eingang. Beides endet im geführten Antrag ab
// Schritt 3 (Wer darf es lesen?) – die Freigabe im Posteingang bleibt. `teileVon`, `endungOk`, `werteVon` und `pruefungVon` sind rein.
// Vor tool.js geladen; quellen.js zeichnet das Plus über sedraWissenPlus.zeichnen.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const TEIL = 512 * 1024;                       // Rohbytes je Anfrage; Base64 bleibt unter dem 1-MB-Limit des Servers
  const ARTEN = ['.md', '.txt', '.docx', '.csv', '.pdf', '.xlsx', '.pptx'];

  // [[offset, länge], …] – eine leere Datei ist ein Stück der Länge 0 (rein)
  function teileVon(groesse, teil){
    const n = teil || TEIL, out = [];
    for(let o = 0; o < groesse; o += n) out.push([o, Math.min(n, groesse - o)]);
    return out.length ? out : [[0, 0]];
  }
  function endungOk(name){
    const m = /\.[A-Za-z0-9]+$/.exec(String(name || ''));
    return !!m && ARTEN.indexOf(m[0].toLowerCase()) >= 0;
  }
  // die Werte des Antrags aus der Antwort des Eingangs (rein): ein Ordner im Projekt, Adapter dokumente, vorsichtig vorbelegt
  function werteVon(out){
    return {adapter: 'dokumente', wurzel: 'projekt', pfad: out.eingang, muster: out.muster, stufe: 3, projekt: null, personenbezug: true};
  }
  function pruefungVon(out){
    const z = out.uebersprungen ? Object.values(out.uebersprungen).reduce((a, b)=>a + b, 0) : 0;
    return {status: 'erledigt', dateien: out.dateien, schon_da: false, ueberschneidung: [],
            satz: out.dateien + (out.dateien === 1 ? ' Datei' : ' Dateien') + ' im Eingang' + (z ? ', ' + z + ' übersprungen (Dateiart, Größe oder Menge)' : '') + '.'};
  }

  function base64(puffer){
    const b = new Uint8Array(puffer); let s = '';
    for(let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
    return root.btoa(s);
  }
  const lies = f=>new Promise((ok, nein)=>{ const r = new root.FileReader(); r.onload = ()=>ok(r.result); r.onerror = ()=>nein(r.error); r.readAsArrayBuffer(f); });

  // alle Dateien eines Ziehens samt Ordnerstruktur: [{file, name}]
  async function sammle(items){
    const out = [];
    const lesen = e=>new Promise(ok=>{ const alle = []; const r = e.createReader(); (function runde(){ r.readEntries(l=>{ if(!l.length) ok(alle); else{ alle.push(...l); runde(); } }, ()=>ok(alle)); })(); });
    const geh = async(e, pfad)=>{
      if(e.isFile) await new Promise(ok=>e.file(f=>{ out.push({file: f, name: pfad + f.name}); ok(); }, ok));
      else if(e.isDirectory) for(const k of await lesen(e)) await geh(k, pfad + e.name + '/');
    };
    const eintraege = [];
    for(const it of items || []) eintraege.push(it.webkitGetAsEntry ? it.webkitGetAsEntry() : null);
    for(const e of eintraege) if(e) await geh(e, '');
    return out;
  }

  async function hochladen(t, liste){
    const p = t.s.plus;
    const gut = liste.filter(x=>endungOk(x.name));
    if(!gut.length){ p.text = 'Darunter ist nichts, was das Wissen lesen kann (Markdown, Text, Word, CSV, PDF, Excel, PowerPoint).'; p.bad = true; return t.draw(); }
    let sitzung = null, n = 0;
    p.bad = false; p.laeuft = true;
    for(const x of gut){
      n++; p.text = 'Lade ' + n + ' von ' + gut.length + ': ' + x.name; await t.draw();
      let puffer;
      try{ puffer = await lies(x.file); }catch(e){ p.text = 'Die Datei ' + x.name + ' ließ sich nicht lesen.'; p.bad = true; p.laeuft = false; return t.draw(); }
      for(const [offset, laenge] of teileVon(x.file.size)){
        const daten = base64(puffer.slice(offset, offset + laenge));
        const r = await t.verb('eingang_ablegen', {sitzung, name: x.name, offset, daten});
        if(!r || r.status !== 'erledigt'){
          if(sitzung) await t.verb('eingang_verwerfen', {sitzung});
          p.text = (r && r.satz) || 'Das Hochladen ist fehlgeschlagen.'; p.bad = true; p.laeuft = false; return t.draw();
        }
        sitzung = r.sitzung;
      }
    }
    const fertig = await t.verb('eingang_fertig', {sitzung});
    return weiter(t, fertig, gut.length < liste.length ? liste.length - gut.length : 0);
  }

  function weiter(t, out, fremd){
    const p = t.s.plus;
    p.laeuft = false;
    if(!out || out.status !== 'erledigt'){
      if(out && out.sitzung) t.verb('eingang_verwerfen', {sitzung: out.sitzung});
      p.text = (out && out.satz) || 'Daraus lässt sich nichts aufnehmen.'; p.bad = true; return t.draw();
    }
    if(fremd) out = Object.assign({}, out, {uebersprungen: Object.assign({art: 0}, out.uebersprungen, {art: ((out.uebersprungen || {}).art || 0) + fremd})});
    t.s.plus = null;
    t.s.antrag = {schritt: 3, vorlage: 'eingang', eingang: out.sitzung, werte: werteVon(out), pruefung: pruefungVon(out)};
    t.s.ansicht = 'quellen';
    return t.draw();
  }

  async function explorer(t, art){
    const p = t.s.plus; p.laeuft = true; p.bad = false; p.text = 'Der Auswahldialog ist offen – er kann hinter diesem Fenster liegen.'; await t.draw();
    const out = await t.verb('explorer_waehlen', {art});
    if(out && out.status === 'abgebrochen'){ p.laeuft = false; p.text = ''; return t.draw(); }
    return weiter(t, out, 0);
  }

  function ablage(t){
    const p = t.s.plus;
    const feld = d().el('div', 's-card s-col t-wissen-drop' + (p.ueber ? ' on' : ''));
    feld.setAttribute('role', 'group'); feld.setAttribute('aria-label', 'Dateien oder Ordner hierher ziehen');
    feld.append(d().el('b', null, 'Dateien oder Ordner hierher ziehen'),
                d().el('small', 's-muted', 'Markdown, Text, Word, CSV, PDF, Excel, PowerPoint. Sie werden ins Projekt kopiert; aufgenommen wird erst nach deiner Freigabe.'));
    feld.ondragover = e=>{ e.preventDefault(); if(!p.ueber){ p.ueber = true; feld.classList.add('on'); } };
    feld.ondragleave = ()=>{ p.ueber = false; feld.classList.remove('on'); };
    feld.ondrop = async e=>{
      e.preventDefault(); p.ueber = false;
      if(p.laeuft) return;
      const items = e.dataTransfer && e.dataTransfer.items ? Array.from(e.dataTransfer.items) : [];
      let liste = items.length ? await sammle(items) : [];
      if(!liste.length) liste = Array.from((e.dataTransfer && e.dataTransfer.files) || []).map(f=>({file: f, name: f.name}));
      return hochladen(t, liste);
    };
    return feld;
  }

  function zeichnen(t){
    const p = t.s.plus;
    const box = d().el('section', 's-card s-col t-wissen-plus'); box.setAttribute('aria-label', 'Wissen hinzufügen');
    const kopf = d().el('div', 's-row');
    kopf.append(d().el('b', null, 'Wissen hinzufügen'));
    const zu = d().button('Schließen', ()=>{ t.s.plus = null; return t.draw(); }); zu.style.marginLeft = 'auto'; kopf.append(zu);
    box.append(kopf, ablage(t));
    const row = d().el('div', 's-row t-wissen-teil');
    const ordner = d().button('Ordner im Explorer wählen …', ()=>explorer(t, 'ordner'), 'p');
    const dateien = d().button('Dateien im Explorer wählen …', ()=>explorer(t, 'dateien'));
    ordner.disabled = dateien.disabled = !!p.laeuft;
    row.append(ordner, dateien);
    box.append(row);
    if(p.text) box.append(d().el('div', 's-note' + (p.bad ? ' bad' : ''), p.text));
    box.onkeydown = e=>{ if(e.key === 'Escape' && !p.laeuft){ e.preventDefault(); t.s.plus = null; t.draw(); } };
    return box;
  }

  // der Knopf „+“ (Kopf der Quellen und leere Liste)
  function knopf(t){
    const b = d().button('+', ()=>{ t.s.plus = t.s.plus ? null : {text: '', bad: false, laeuft: false}; return t.draw(); }, 'p');
    b.classList.add('t-wissen-plus-knopf'); b.setAttribute('aria-label', 'Wissen hinzufügen'); b.title = 'Wissen hinzufügen – Dateien ziehen oder im Explorer wählen';
    return b;
  }

  root.sedraWissenPlus = {zeichnen, knopf, teileVon, endungOk, werteVon, pruefungVon, ARTEN};
  if(typeof module !== 'undefined' && module.exports) module.exports = {teileVon, endungOk, werteVon, pruefungVon, ARTEN};
})();
