// Import eines n8n-Workflows auf der Startseite (n8n Workflows und Szenario Studio): Datei wählen, hineinziehen oder Text einfügen,
// dann die Vorschau des Servers (Verb `import_vorschau`, nur lesen) mit Urteil, Funden, Knotenliste und Bild. Erst „Als Entwurf öffnen“
// übernimmt den Workflow in den Editor; gespeichert wird danach wie immer mit „Speichern“. Reines Anzeigemodul, keine eigenen Routen.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const MAX = 1000000;
  const STATUS = {unterstuetzt: 'läuft in SEDRA', erhalten: 'bleibt erhalten', notiz: 'Notiz'};
  function el(tag, cls, text){const x = document.createElement(tag);if(cls)x.className = cls;if(text !== undefined)x.textContent = text;return x;}
  function button(text, fn){const b = el('button', '', text);b.type = 'button';b.onclick = fn;return b;}
  const SVG = 'http://www.w3.org/2000/svg';
  function svg(tag, attrs){const x = document.createElementNS(SVG, tag);Object.keys(attrs || {}).forEach(k=>x.setAttribute(k, attrs[k]));return x;}

  // Bild: Knoten als Kästchen, Verbindungen als Kurven; Positionen aus dem Workflow, bei layout_noetig aus der automatischen Anordnung
  function bild(v){
    const L = root.sedraWorkflowLayout, doc = v.workflow, pos = {};
    const auto = v.layout_noetig && L ? L.anordnen(doc).pos : null;
    const sichtbar = v.knoten.filter(k=>k.status !== 'notiz');
    sichtbar.forEach(k=>{
      const n = doc.nodes.find(x=>x.id === k.id) || {};
      pos[k.name] = auto && auto[k.name] ? auto[k.name] : (n.position || [0, 0]);
    });
    const xs = sichtbar.map(k=>pos[k.name][0]), ys = sichtbar.map(k=>pos[k.name][1]);
    const x0 = Math.min(...xs, 0), y0 = Math.min(...ys, 0), B = 150, H = 40;
    const breite = Math.max(...xs, 0) - x0 + B + 40, hoehe = Math.max(...ys, 0) - y0 + H + 40;
    const s = svg('svg', {viewBox: '0 0 ' + breite + ' ' + hoehe, role: 'img', 'aria-label': 'Vorschau des Ablaufs'});s.classList.add('t-wf-imp-bild');
    s.style.minWidth = Math.min(breite, 900) + 'px';
    const p = k=>[pos[k][0] - x0 + 20, pos[k][1] - y0 + 20];
    v.verbindungen.forEach(c=>{
      if(!pos[c.von] || !pos[c.nach])return;
      const a = p(c.von), b = p(c.nach), ax = a[0] + B, ay = a[1] + H / 2, bx = b[0], by = b[1] + H / 2, m = Math.max(24, Math.abs(bx - ax) / 2);
      const w = svg('path', {d: 'M' + ax + ' ' + ay + ' C' + (ax + m) + ' ' + ay + ' ' + (bx - m) + ' ' + by + ' ' + bx + ' ' + by});
      w.setAttribute('class', 't-wf-imp-kante' + (c.art !== 'main' ? ' sub' : ''));
      const t = svg('title');t.textContent = c.von + ' → ' + c.nach + (c.zweig ? ' (' + c.zweig + ')' : '') + (c.art !== 'main' ? ' · ' + c.art : '');w.append(t);s.append(w);
    });
    sichtbar.forEach(k=>{
      const [x, y] = p(k.name), g = svg('g', {transform: 'translate(' + x + ' ' + y + ')'});
      g.setAttribute('class', 't-wf-imp-knoten ' + k.status + (k.deaktiviert ? ' aus' : '') + (k.ausloeser ? ' start' : ''));
      const r = svg('rect', {width: B, height: H, rx: 8}), t = svg('text', {x: 10, y: 25});
      t.textContent = k.name.length > 20 ? k.name.slice(0, 19) + '…' : k.name;
      const tt = svg('title');tt.textContent = k.name + ' · ' + k.typ;g.append(tt, r, t);s.append(g);
    });
    const box = el('div', 't-wf-imp-bildbox');box.append(s);return box;
  }

  function liste(v){
    const t = el('table', 't-wf-imp-tabelle');
    const kopf = el('tr');['Schritt', 'Art', 'SEDRA', 'Hinweis'].forEach(x=>kopf.append(el('th', '', x)));t.append(kopf);
    v.knoten.forEach(k=>{
      const r = el('tr', k.status);r.append(el('td', '', k.name + (k.deaktiviert ? ' (aus)' : '')), el('td', '', k.art || k.typ), el('td', '', STATUS[k.status] || k.status));
      r.append(el('td', '', (k.hinweise || []).concat(k.zugang ? ['braucht Zugangsdaten'] : []).join('; ')));t.append(r);
    });
    return t;
  }

  function attach(ed){
    const box = el('section', 't-wf-import');box.setAttribute('aria-label', 'n8n-Workflow importieren');
    const kopf = el('h3', '', 'n8n-Workflow importieren');
    const hinweis = el('p', 't-wf-hint', 'JSON-Datei aus n8n („Download“) hierher ziehen, wählen oder den Text einfügen. Du siehst zuerst eine Vorschau; nichts wird gespeichert oder gestartet.');
    const zone = el('div', 't-wf-imp-zone');zone.tabIndex = 0;zone.setAttribute('role', 'button');zone.setAttribute('aria-label', 'Datei hierher ziehen oder wählen');
    zone.append(el('strong', '', 'Datei hierher ziehen'), el('span', '', 'oder klicken zum Wählen (.json, bis 1 MB)'));
    const feld = el('textarea');feld.rows = 3;feld.maxLength = MAX;feld.placeholder = 'Oder den n8n-JSON-Text hier einfügen …';feld.setAttribute('aria-label', 'n8n-JSON einfügen');
    const pruef = button('Vorschau zeigen', ()=>zeigen(feld.value, null));pruef.className = 't-wf-primary';
    const ziel = el('div', 't-wf-imp-ziel');ziel.setAttribute('aria-live', 'polite');
    box.append(kopf, hinweis, zone, feld, pruef, ziel);

    async function lesen(f){
      if(!f)return;
      if(f.size > MAX){ziel.replaceChildren(el('p', 't-wf-imp-fehler', 'Die Datei ist größer als 1 MB und wird nicht gelesen.'));return;}
      const text = await f.text();feld.value = text.length > 20000 ? '' : text;await zeigen(text, f.name);
    }
    // Das Dateifeld entsteht erst beim Klick und steht nie im Dokument (die Seite hat schon das Feld des Editors).
    const waehlen = ()=>{const d = el('input');d.type = 'file';d.accept = '.json,application/json';d.onchange = ()=>ed.safe(()=>lesen(d.files[0]));d.click();};
    zone.onclick = waehlen;
    zone.onkeydown = e=>{if(e.key === 'Enter' || e.key === ' '){e.preventDefault();waehlen();}};
    ['dragenter', 'dragover'].forEach(n=>zone.addEventListener(n, e=>{e.preventDefault();zone.classList.add('an');}));
    ['dragleave', 'drop'].forEach(n=>zone.addEventListener(n, e=>{e.preventDefault();zone.classList.remove('an');}));
    zone.addEventListener('drop', e=>ed.safe(()=>lesen(e.dataTransfer && e.dataTransfer.files[0])));

    async function zeigen(text, name){
      if(!String(text || '').trim()){ziel.replaceChildren(el('p', 't-wf-imp-fehler', 'Es ist noch nichts da: Datei wählen oder Text einfügen.'));return;}
      const v = await ed.call('workflow', null, 'import_vorschau', {text, dateiname: name});
      ziel.replaceChildren(v.ok ? anzeigen(v) : fehler(v));
    }
    function fehler(v){
      const d = el('div', 't-wf-imp-karte bad');d.append(el('strong', '', 'Das kann SEDRA so nicht importieren'), el('p', '', v.fehler.satz));
      d.append(button('Verwerfen', ()=>ziel.replaceChildren()));return d;
    }
    function anzeigen(v){
      const d = el('div', 't-wf-imp-karte ' + v.urteil.stufe), z = v.zaehler;
      d.append(el('strong', '', v.name), el('p', 't-wf-imp-urteil', v.urteil.satz));
      const kennzahlen = el('p', 't-wf-hint', z.knoten + ' Schritte · ' + z.verbindungen + ' Verbindungen · ' + z.ausloeser + ' Auslöser · ' + z.notizen + ' Notizen · ' + z.unbekannt + ' ohne Ausführung in SEDRA' + (z.zugang ? ' · ' + z.zugang + ' mit Zugangsdaten' : ''));
      d.append(kennzahlen);
      if(v.aenderungen && v.aenderungen.length){const a = el('ul', 't-wf-imp-aend');v.aenderungen.forEach(x=>a.append(el('li', '', x)));d.append(el('p', 't-wf-hint', 'Beim Übernehmen ergänzt SEDRA fehlende Angaben:'), a);}
      // Zusammenfassung
      if(v.zusammenfassung){d.append(el('p', 't-wf-imp-saetze', 'Zusammenfassung: ' + v.zusammenfassung));}
      // Kategorien
      if(v.kategorien){
        const kate = el('details', 't-wf-imp-kategorien');
        const katz = Object.entries(v.kategorien).filter(([,n])=>n.length>0).sort((a,b)=>b[1].length-a[1].length);
        if(katz.length){
          const tl = el('p', 't-wf-hint');
          tl.textContent = 'Kategorien: ' + katz.map(([k,n])=>n.length+' '+((k==='ki'?'KI/Modell':k==='ausloeser'?'Auslöser':k==='daten'?'Daten':k==='code'?'Code':k==='netzwerk'?'Netzwerk':k==='ablauf'?'Ablauf':k)) + '('+n.join(', ')+')').join(' · ');
          kate.append(el('summary', '', 'Kategorien (' + katz.length + ')'));kate.append(tl);
        }else{kate.append(el('summary', '', 'Kategorien: keine'));}
        d.append(kate);
      }
      // Auslöser-Info
      if(v.ausloeser_info && v.ausloeser_info.length){
        const aInfo = el('details', 't-wf-imp-kategorien');
        aInfo.append(el('summary', '', 'Auslöser (' + v.ausloeser_info.length + ')'));
        v.ausloeser_info.forEach(a=>{
          const p = el('p', 't-wf-hint');
          p.textContent = a.name + ' (' + a.art + ')' + (a.zeitplan ? ' · Zeitplan: ' + a.zeitplan : '');
          aInfo.append(p);
        });
        d.append(aInfo);
      }
      // Cloud-Knoten
      if(v.cloud_knoten && v.cloud_knoten.length){
        const cl = el('details', 't-wf-imp-kategorien');
        cl.append(el('summary', '', 'Cloud-Knoten (' + v.cloud_knoten.length + ')'));
        v.cloud_knoten.forEach(c=>{
          const p = el('p', 't-wf-hint');
          p.textContent = c.name + ' · ' + c.anbieter + (c.modell ? ' · ' + c.modell : '') + ' · ' + c.ort;
          cl.append(p);
        });
        d.append(cl);
      }
      // Modell-Knoten (SPEZ-04a D)
      if(v.modellknoten && v.modellknoten.length){
        const mk = el('details', 't-wf-imp-kategorien');
        mk.append(el('summary', '', 'KI-Modellknoten (' + v.modellknoten.length + ')'));
        v.modellknoten.forEach(m=>{
          const p = el('p', 't-wf-hint');
          p.textContent = m.name + ' · ' + m.anbieter + (m.modell ? ' · ' + m.modell : '') + ' · ' + m.ort + (m.umstellbar ? ' · umstellbar' : ' · nicht umstellbar');
          mk.append(p);
        });
        d.append(mk);
      }
      // Code-Knoten
      if(v.code_knoten && v.code_knoten.length){
        const ck = el('details', 't-wf-imp-kategorien');
        ck.append(el('summary', '', 'Code-Knoten (' + v.code_knoten.length + ')'));
        v.code_knoten.forEach(c=>{
          const p = el('p', 't-wf-hint');
          let txt = c.name + ' · ' + c.sprache + ' · ' + c.zeilen + ' Zeilen';
          if(c.gefaehrliche_muster && c.gefaehrliche_muster.length){
            p.setAttribute('class', 't-wf-imp-fund warn');
            txt += ' ⚠ Gefahr: ' + c.gefaehrliche_muster.join(', ');
          }
          p.textContent = txt;ck.append(p);
        });
        d.append(ck);
      }
      // Externe Ziele
      if(v.externe_ziele && (v.externe_ziele.domains.length || v.externe_ziele.dienste.length)){
        const ez = el('details', 't-wf-imp-kategorien');
        ez.append(el('summary', '', 'Externe Ziele'));
        if(v.externe_ziele.domains.length){
          const dp = el('p', 't-wf-hint');
          dp.textContent = 'Domains: ' + v.externe_ziele.domains.join(', ');
          ez.append(dp);
        }
        if(v.externe_ziele.dienste.length){
          const sp = el('p', 't-wf-hint');
          sp.textContent = 'Dienste: ' + v.externe_ziele.dienste.join(', ');
          ez.append(sp);
        }
        d.append(ez);
      }
      // Geheimnisse (Security - SPEZ-04a B)
      if(v.pruefung && v.pruefung.geheimnisse && v.pruefung.geheimnisse.length){
        const sec = el('details', 't-wf-imp-kategorien');
        sec.append(el('summary', 't-wf-imp-fund warn', '⚠ Sicherheit (' + v.pruefung.geheimnisse.length + ' Funde)'));
        v.pruefung.geheimnisse.forEach(g=>{
          const p = el('p', 't-wf-imp-fund ' + g.stufe);
          p.textContent = g.knoten + ' (' + g.ort + '): ' + g.text;
          sec.append(p);
        });
        d.append(sec);
      }
      v.funde.forEach(f=>d.append(el('p', 't-wf-imp-fund ' + f.stufe, f.text)));
      d.append(bild(v));
      const det = el('details', 't-wf-imp-liste');det.append(el('summary', '', 'Alle Schritte (' + v.knoten.length + ')'), liste(v));d.append(det);
      const knoepfe = el('div', 't-wf-toolbar');
      const auf = button('Als Entwurf öffnen', ()=>ed.safe(async()=>{
        if(!ed.discard())return;
        const doc = JSON.parse(JSON.stringify(v.workflow));
        if(v.layout_noetig && root.sedraWorkflowLayout){const pos = root.sedraWorkflowLayout.anordnen(doc).pos;doc.nodes.forEach(n=>{if(pos[n.name])n.position = pos[n.name];});}
        ed.adopt(doc, null, null);ed.setTab('editor');ed.notice('Importiert: „' + v.name + '“. Unbekannte Felder und Schritte bleiben erhalten. Speichern erzeugt die erste Revision.');ziel.replaceChildren();feld.value = '';
      }));auf.className = 't-wf-primary';
      knoepfe.append(auf, button('Verwerfen', ()=>{ziel.replaceChildren();feld.value = '';}));d.append(knoepfe);
      return d;
    }
    return {el: box, zeigen};
  }

  root.sedraWorkflowImport = {attach};
})();
