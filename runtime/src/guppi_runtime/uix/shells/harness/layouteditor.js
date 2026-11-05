// Harness-Shell (One Sedra) – der Layout-Editor des Desktop Builders (Captain 05.11.2026: Baukasten und Raster, anpassen wie man will und verschieben; Entwurf mit Bühne, Rahmen und
// Hilfslinien; das Start-Menü hat dieselbe Bauart). Der Reiter „Layout“ zeigt eine **Bühne**: ein verkleinertes Abbild der leeren Sitzung, wie sie wirklich aussieht – Begrüßung, die drei Schritte, der Hilfetext auf dem
// Raster mit 12 Spalten, darunter das Eingabefeld mit seiner Leiste und die Zeile mit Projekt und Vorlage. Jeder Baustein hat einen Rahmen. Bausteine auf dem Raster zieht man mit der
// Maus (die Ecke unten rechts ändert die Größe, die Pfeiltasten verschieben, mit Umschalt ändern sie die Größe); beim Ziehen zeigen grüne Hilfslinien, wo andere Bausteine enden. Die Chips
// der beiden Leisten tauscht man per Ziehen (oder Alt+Pfeil) und blendet sie mit dem Kreuz aus; Freigabe-Schild und Senden bleiben immer sichtbar. Darunter stehen die genauen Zahlen.
// Gespeichert wird als Teil des Profils (desktop.js → POST /api/harness/desktop, `layout`). Die Teile heißen und liegen in bausteine.js. Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const H = ()=>root.sedraHarness;
  // logische Größe der Bühne (sie wird auf die Breite des Fensters verkleinert): Raster mit 12 Spalten, Zeilenhöhe 30
  const BREITE = 920, RAND = 40, ZEILE_H = 30, OBEN = 14, MIN_ZEILEN = 11;
  const RASTER_B = BREITE - 2 * RAND, SPALTE_B = RASTER_B / 12;

  const gleich = (a, b)=>JSON.stringify(a) === JSON.stringify(b);
  const meldung = (box, text, schlecht)=>{ box.textContent = text; box.classList.toggle('bad', !!schlecht); };

  // Was in einem Chip steht (so sieht der Baustein in der echten Oberfläche aus; die Klassen sind die echten)
  const CHIPS = {
    plus: ()=>d().el('span', 'hs-rund hs-lay-chipinhalt', '+'),
    schild: ()=>d().el('span', 'hs-schild hs-lay-chipinhalt', '⛨ Captain gibt frei'),
    modell: ()=>d().el('span', 'hs-modell hs-lay-chipinhalt', 'kein Modell'),
    mikro: ()=>d().el('span', 'hs-rund hs-lay-chipinhalt', '🎙'),
    senden: ()=>d().el('span', 'hs-senden p hs-lay-chipinhalt', 'Senden'),
    projekt: ()=>{ const s = d().el('span', 'hs-lay-chipinhalt'); s.append(d().el('span', 'hs-leise', 'Projekt '), d().el('span', 'hs-projektwahl', 'Sedra Entwicklung ▾')); return s; },
    vorlage: ()=>{ const s = d().el('span', 'hs-lay-chipinhalt'); s.append(d().el('span', 'hs-leise', 'Vorlage '), d().el('span', 'hs-projektwahl', 'ohne Vorlage ▾')); return s; },
    ordner: ()=>d().el('span', 'hs-knopf hs-lay-chipinhalt', 'Ordner öffnen …'),
    'neues-projekt': ()=>d().el('span', 'hs-knopf hs-lay-chipinhalt', 'Neues Projekt …'),
    vorgabe: ()=>d().el('span', 'hs-knopf hs-lay-chipinhalt', 'Als Vorgabe merken')};

  // Die Inhalte der drei Bausteine auf dem Raster, wie die leere Sitzung sie zeigt (die Begrüßung nimmt Logo und Titel des Profils)
  function startInhalt(S, id){
    const D = H().desktop, g = D ? D.begruessung(S) : {logo: '', titel: 'SEDRA', text: ''};
    if(id === 'gruss'){
      const b = d().el('div', 'hs-start-block');
      if(g.logo){ const i = d().el('img', 'hs-start-logo'); i.src = g.logo; i.alt = ''; b.append(i); } else if(H().verlauf && H().verlauf.drache) b.append(H().verlauf.drache());
      b.append(d().el('h1', 'hs-start-titel', g.titel)); if(g.text) b.append(d().el('p', 'hs-start-gruss', g.text));
      return b;
    }
    if(id === 'schritte'){
      const ol = d().el('ol', 'hs-start-schritte');
      [['○', 'Ein Modell laden'], ['✓', 'Projekt: Sedra Entwicklung'], ['○', 'Die erste Nachricht schreiben']].forEach(([h, t])=>{ const li = d().el('li', 'hs-start-schritt'); li.append(d().el('span', 'hs-start-haken', h), d().el('span', null, t)); ol.append(li); });
      return ol;
    }
    return d().el('p', 'hs-start-text', 'Im Feld: „+“ hängt eine Datei an, „@“ nennt eine Datei, „/“ gibt Befehle. Die Antwort streamt; jeder Werkzeugaufruf steht sichtbar im Verlauf.');
  }

  function leisteBauen(name, titel, alle, grund, state, chipFn, luecke){
  const reihe = d().el('div', 'hs-lay-chips'); reihe.dataset.leiste = name; reihe.setAttribute('aria-label', titel);
  let gezogen = null;
  const zeichneLeiste = ()=>{
    const rechts = luecke ? state.reihe.find(i=>['mikro', 'senden'].includes(i)) : null;      // die Lücke trennt links von rechts (nur in der Leiste im Eingabefeld)
    reihe.replaceChildren(...state.reihe.flatMap((id, i)=>{
      const c = d().el('div', 'hs-lay-chip' + (state.aus.has(id) ? ' aus' : '') + (grund.includes(id) ? ' grund' : '')); c.dataset.baustein = id; c.draggable = true; c.tabIndex = 0;
      c.title = (grund.includes(id) ? 'Grundfunktion: bleibt immer sichtbar. ' : '') + 'Ziehen oder Alt+Pfeil verschiebt.';
      c.append(chipFn(id));
      if(!grund.includes(id)){ const x = d().el('button', 'hs-lay-aus', state.aus.has(id) ? '↺' : '×'); x.type = 'button'; x.setAttribute('aria-label', (state.aus.has(id) ? 'Zeigen: ' : 'Ausblenden: ') + id);
        x.onclick = e=>{ e.stopPropagation(); if(state.aus.has(id)) state.aus.delete(id); else state.aus.add(id); zeichneLeiste(); }; c.append(x); }
      const tausch = (a, b)=>{ if(b < 0 || b >= state.reihe.length) return; [state.reihe[a], state.reihe[b]] = [state.reihe[b], state.reihe[a]]; zeichneLeiste(); const n = reihe.querySelector('[data-baustein="' + id + '"]'); if(n) n.focus(); };
      c.addEventListener('keydown', e=>{ if(e.altKey && e.key === 'ArrowLeft'){ e.preventDefault(); tausch(i, i - 1); } else if(e.altKey && e.key === 'ArrowRight'){ e.preventDefault(); tausch(i, i + 1); } });
      c.addEventListener('dragstart', e=>{ gezogen = id; try{ e.dataTransfer.setData('text/plain', id); e.dataTransfer.effectAllowed = 'move'; }catch(_e){} });
      c.addEventListener('dragover', e=>{ if(gezogen) e.preventDefault(); });
      c.addEventListener('drop', e=>{ e.preventDefault(); if(!gezogen || gezogen === id) return; const von = state.reihe.indexOf(gezogen), nach = state.reihe.indexOf(id); state.reihe.splice(von, 1); state.reihe.splice(nach, 0, gezogen); gezogen = null; zeichneLeiste(); });
      c.addEventListener('dragend', ()=>{ gezogen = null; });
      return id === rechts ? [d().el('span', 'hs-lay-luecke'), c] : [c];
    }));
  };
  zeichneLeiste();
  return reihe;
  }

  function bauen(S, feld, st){
    const B = H().bausteine;
    const namen = {}; B.START.forEach(([id, n])=>{ namen[id] = n; });
    const buehne = d().el('div', 'hs-lay-buehne'); buehne.setAttribute('role', 'group'); buehne.setAttribute('aria-label', 'Bühne: verkleinertes Abbild der leeren Sitzung');
    const bild = d().el('div', 'hs-lay-bild'); bild.style.width = BREITE + 'px'; buehne.append(bild);
    const raster = d().el('div', 'hs-lay-raster'); raster.style.margin = OBEN + 'px ' + RAND + 'px 0'; raster.style.backgroundSize = SPALTE_B + 'px ' + ZEILE_H + 'px';
    const linien = d().el('div', 'hs-lay-hilfslinien'); linien.setAttribute('aria-hidden', 'true');
    let k = 1;                                                        // Verkleinerung der Bühne
    const skalieren = ()=>{
      k = Math.max(0.3, Math.min(1, (buehne.clientWidth || BREITE) / BREITE));
      bild.style.transform = 'scale(' + k + ')'; buehne.style.height = Math.ceil(bild.offsetHeight * k) + 'px';
    };
    const bloecke = {}, felder = {};
    const zeilen = ()=>Math.max(MIN_ZEILEN, ...Object.values(st.start).map(b=>b.y + b.h - 1));
    const zeichne = id=>{
      const b = st.start[id], el = bloecke[id];
      el.style.gridColumn = b.x + ' / span ' + b.b; el.style.gridRow = b.y + ' / span ' + b.h; el.classList.toggle('aus', !b.sichtbar);
      el.querySelector('.hs-lay-name').textContent = namen[id] + (b.sichtbar ? '' : ' (aus)') + ' · ' + b.x + '/' + b.y + ' · ' + b.b + '×' + b.h;
      raster.style.gridTemplateRows = 'repeat(' + zeilen() + ', ' + ZEILE_H + 'px)'; raster.style.height = zeilen() * ZEILE_H + 'px';
      const f = felder[id]; if(f){ f.sichtbar.checked = b.sichtbar; ['x', 'y', 'b', 'h'].forEach(n=>{ f[n].value = b[n]; }); }
      skalieren();
    };
    // Hilfslinien beim Ziehen: wo andere Bausteine anfangen oder enden (Kanten auf dem Raster) und die Mitte
    const hilfslinien = id=>{
      linien.replaceChildren();
      const b = st.start[id], senkrecht = new Set(), waagrecht = new Set();
      Object.keys(st.start).filter(o=>o !== id && st.start[o].sichtbar).forEach(o=>{
        const a = st.start[o];
        [[b.x, a.x], [b.x, a.x + a.b], [b.x + b.b, a.x], [b.x + b.b, a.x + a.b]].forEach(([p, q])=>{ if(p === q) senkrecht.add(p); });
        [[b.y, a.y], [b.y, a.y + a.h], [b.y + b.h, a.y], [b.y + b.h, a.y + a.h]].forEach(([p, q])=>{ if(p === q) waagrecht.add(p); });
      });
      if(2 * b.x + b.b === 14) senkrecht.add(7);                    // die Mitte des Rasters (Spalte 7 beginnt in der Mitte)
      senkrecht.forEach(sp=>{ const l = d().el('div', 'hs-lay-linie senkrecht'); l.style.left = (RAND + (sp - 1) * SPALTE_B) + 'px'; linien.append(l); });
      waagrecht.forEach(z=>{ const l = d().el('div', 'hs-lay-linie waagrecht'); l.style.top = (OBEN + (z - 1) * ZEILE_H) + 'px'; linien.append(l); });
    };
    const ziehen = (el, id, art, ev)=>{
      ev.preventDefault(); ev.stopPropagation();
      try{ el.setPointerCapture(ev.pointerId); }catch(_e){ /* ohne Capture bewegt sich der Baustein nur im Element */ }
      const start = {x: ev.clientX, y: ev.clientY, b: Object.assign({}, st.start[id])};
      const bewegt = e=>{
        const dx = Math.round((e.clientX - start.x) / k / SPALTE_B), dy = Math.round((e.clientY - start.y) / k / ZEILE_H);
        st.start[id] = art === 'groesse' ? B.groesse(start.b, dx, dy) : B.bewegen(start.b, dx, dy);
        zeichne(id); hilfslinien(id);
      };
      const ende = ()=>{ el.removeEventListener('pointermove', bewegt); el.removeEventListener('pointerup', ende); el.removeEventListener('pointercancel', ende); linien.replaceChildren(); };
      el.addEventListener('pointermove', bewegt); el.addEventListener('pointerup', ende); el.addEventListener('pointercancel', ende);
    };
    const form = d().el('div', 'hs-liste');
    B.START.forEach(([id])=>{
      const el = d().el('div', 'hs-lay-block'); el.tabIndex = 0; el.dataset.baustein = id;
      el.setAttribute('aria-label', namen[id] + ': mit den Pfeiltasten verschieben, mit Umschalt und Pfeiltasten die Größe ändern');
      const inhalt = d().el('div', 'hs-lay-inhalt'); inhalt.append(startInhalt(S, id));
      const griff = d().el('span', 'hs-lay-griff'); griff.setAttribute('aria-hidden', 'true');
      el.append(d().el('span', 'hs-lay-name'), inhalt, griff);
      griff.addEventListener('pointerdown', ev=>ziehen(el, id, 'groesse', ev));
      el.addEventListener('pointerdown', ev=>{ if(ev.target !== griff) ziehen(el, id, 'bewegen', ev); });
      el.addEventListener('keydown', ev=>{
        const pfeil = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]}[ev.key];
        if(!pfeil) return;
        ev.preventDefault();
        st.start[id] = ev.shiftKey ? B.groesse(st.start[id], pfeil[0], pfeil[1]) : B.bewegen(st.start[id], pfeil[0], pfeil[1]);
        zeichne(id);
      });
      bloecke[id] = el; raster.append(el);
      // genaue Eingabe: gleiche Wirkung wie Ziehen, für Tastatur und Feinarbeit
      const z = d().el('div', 'hs-einst-zeile hs-lay-feld'); z.dataset.baustein = id;
      const sichtbar = d().el('input'); sichtbar.type = 'checkbox'; sichtbar.setAttribute('aria-label', namen[id] + ' zeigen');
      sichtbar.onchange = ()=>{ st.start[id] = Object.assign({}, st.start[id], {sichtbar: sichtbar.checked}); zeichne(id); };
      const f = {sichtbar}; z.append(sichtbar, d().el('b', 'hs-einst-label', namen[id]));
      [['x', 'Spalte'], ['y', 'Zeile'], ['b', 'Breite'], ['h', 'Höhe']].forEach(([n, name])=>{
        const e = d().el('input', 'hs-einst-zahl'); e.type = 'number'; e.setAttribute('aria-label', name + ' von ' + namen[id]);
        e.onchange = ()=>{ st.start[id] = B.klemmen(Object.assign({}, st.start[id], {[n]: Number(e.value)})); zeichne(id); };
        f[n] = e; z.append(d().el('small', 'hs-leise', name), e);
      });
      felder[id] = f; form.append(z);
    });
    // Eingabefeld und die beiden Leisten: Abbild mit Chips zum Tauschen
    const composer = d().el('div', 'hs-lay-composer hs-lay-fest');
    composer.append(d().el('div', 'hs-lay-feldabbild', 'Nachricht an SEDRA – Enter sendet, Umschalt+Enter neue Zeile, / für Befehle'));
    const chipLeiste = (name, titel, alle, grund, state)=>leisteBauen(name, titel, alle, grund, state, id=>CHIPS[id](), name === 'werkzeuge');
    composer.append(chipLeiste('werkzeuge', 'Leiste im Eingabefeld', B.WERKZEUGE.map(x=>x[0]), B.GRUND_WERKZEUGE, st.werkzeuge));
    const zeileBox = d().el('div', 'hs-lay-fest hs-lay-zeilebox'); zeileBox.append(chipLeiste('zeile', 'Zeile unter dem Eingabefeld', B.ZEILE.map(x=>x[0]), [], st.zeile));
    bild.append(raster, linien, composer, zeileBox);
    feld.append(d().el('h3', 'hs-ueber', 'Bühne: so sieht die leere Sitzung aus'),
                d().el('small', 'hs-leise', 'Baustein ziehen verschiebt, die Ecke unten rechts ändert die Größe, grüne Linien zeigen die Kanten anderer Bausteine. Chips in den beiden Leisten tauschst du per Ziehen (oder Alt+Pfeil), das Kreuz blendet aus.'),
                buehne);
    const genau = d().el('details', 'hs-lay-genau'); genau.append(d().el('summary', null, 'Genaue Eingabe (Zahlen für Spalte, Zeile, Breite und Höhe)'), form); feld.append(genau);
    B.START.forEach(([id])=>zeichne(id));
    if(typeof ResizeObserver !== 'undefined') new ResizeObserver(()=>skalieren()).observe(buehne); else root.addEventListener('resize', skalieren);
    setTimeout(skalieren, 0);
  }

  // ---- das Start-Menü: dieselbe Bauart (Bühne mit Rahmen, Chips zum Tauschen, Kreuz zum Ausblenden)
  // Die Abschnitte des Menüs stehen untereinander; ein Abschnitt wird am Griff ⠿ gezogen. „Auf einen Blick“ enthält die Kacheln als Chips.
  const MENUE_INHALT = {
    zuletzt: ()=>d().el('small', 'hs-leise', 'Aufgaben · Modelle · Posteingang'),
    gruppen: ()=>d().el('small', 'hs-leise', 'Arbeit 17 · Modelle 3 · Sedra Token · Wissen · System · Prüfung'),
    oberflaechen: ()=>d().el('small', 'hs-leise', 'Cockpit · Translator · KI Gateway für KMU · KI GateWay Studio · SEDRA XP · Minimal · Paperclip · Wissensbasis'),
    darstellung: ()=>d().el('small', 'hs-leise', 'Darstellung und Schrift … · Gedächtnis leeren')};
  // Das Menü hat zwei Zonen: den Inhalt (scrollt) und den Fuß (steht unten); Abschnitte wechseln nur innerhalb ihrer Zone
  const ZONE = {zuletzt: 'inhalt', blick: 'inhalt', gruppen: 'inhalt', oberflaechen: 'fuss', darstellung: 'fuss'};
  const BLICK_CHIP = {aufgaben: 'Aufgaben', labor: 'KI-Labor', token: 'Sedra Token', hardware: 'Hardware', modelle: 'Modelle', einstellungen: 'Einstellungen'};

  function menueBuehne(S, feld, st){
    const B = H().bausteine;
    const namen = {}; B.MENUE.forEach(([id, n])=>{ namen[id] = n; });
    const rahmen = d().el('div', 'hs-lay-menuebuehne'); rahmen.setAttribute('role', 'group'); rahmen.setAttribute('aria-label', 'Bühne: Abbild des Start-Menüs');
    rahmen.append(d().el('div', 'hs-lay-suche', 'App suchen … (Strg+K sucht einen Ort)'));
    const liste = d().el('div', 'hs-lay-abschnitte');
    rahmen.append(liste);
    let gezogen = null;
    const zeichne = ()=>{
      const reihe = ['inhalt', 'fuss'].flatMap(z=>st.menue.reihe.filter(i=>ZONE[i] === z));
      liste.replaceChildren(...reihe.flatMap((id, n)=>{
        const trenner = ZONE[id] === 'fuss' && (n === 0 || ZONE[reihe[n - 1]] !== 'fuss') ? [d().el('div', 'hs-lay-trenner', 'Fuß des Menüs (steht unten)')] : [];
        const a = d().el('section', 'hs-lay-abschnitt' + (st.menue.aus.has(id) ? ' aus' : '') + (B.GRUND_MENUE.includes(id) ? ' grund' : '')); a.dataset.baustein = id;
        const kopf = d().el('div', 'hs-lay-abschnittskopf');
        const griff = d().el('span', 'hs-lay-griff-liste', '⠿'); griff.draggable = true; griff.title = 'Ziehen verschiebt den Abschnitt';
        griff.addEventListener('dragstart', e=>{ gezogen = id; try{ e.dataTransfer.setData('text/plain', id); e.dataTransfer.effectAllowed = 'move'; }catch(_e){} });
        griff.addEventListener('dragend', ()=>{ gezogen = null; });
        kopf.append(griff, d().el('b', null, namen[id]));
        if(!B.GRUND_MENUE.includes(id)){
          const x = d().el('button', 'hs-lay-aus hs-lay-aus-innen', st.menue.aus.has(id) ? '↺' : '×'); x.type = 'button'; x.setAttribute('aria-label', (st.menue.aus.has(id) ? 'Zeigen: ' : 'Ausblenden: ') + namen[id]);
          x.onclick = ()=>{ if(st.menue.aus.has(id)) st.menue.aus.delete(id); else st.menue.aus.add(id); zeichne(); }; kopf.append(x);
        }
        a.append(kopf);
        if(id === 'blick') a.append(leisteBauen('blick', 'Kacheln Auf einen Blick', B.BLICK.map(x=>x[0]), B.GRUND_BLICK, st.blick, k=>d().el('span', 'hs-start-blick-kachel hs-lay-kachel hs-lay-chipinhalt', BLICK_CHIP[k]), false));
        else a.append(MENUE_INHALT[id]());
        a.addEventListener('dragover', e=>{ if(gezogen) e.preventDefault(); });
        a.addEventListener('drop', e=>{
          e.preventDefault();
          if(!gezogen || gezogen === id || ZONE[gezogen] !== ZONE[id]) return;                  // nur innerhalb der Zone
          const von = st.menue.reihe.indexOf(gezogen), nach = st.menue.reihe.indexOf(id);
          st.menue.reihe.splice(von, 1); st.menue.reihe.splice(nach, 0, gezogen); gezogen = null; zeichne();
        });
        return trenner.concat([a]);
      }));
    };
    zeichne();
    rahmen.append(d().el('div', 'hs-lay-suche hs-lay-fussabbild', 'Der Rest des Menüs (Suche, Treffer) bleibt wie er ist.'));
    feld.append(d().el('h3', 'hs-ueber', 'Start-Menü'),
                d().el('small', 'hs-leise', 'Abschnitte am Griff ⠿ ziehen, Kacheln „Auf einen Blick“ per Ziehen (oder Alt+Pfeil) tauschen, mit dem Kreuz ausblenden. Die App-Gruppen und die Kachel Einstellungen bleiben immer.'), rahmen);
  }

  // ---- der Seitenaufbau (Stufe 3): wo die großen Zonen stehen. Seitenleiste, Eingabefeld und Taskleiste ziehst du auf die andere Seite; Breiten gibt man in Zahlen an.
  // Keine Zone verschwindet: sie wechseln nur Platz oder Breite (der Server prüft es). In der leeren Sitzung bleibt das Eingabefeld, wo der Baukasten es hinstellt.
  function zonenBuehne(S, feld, st){
    const B = H().bausteine;
    const fenster = d().el('div', 'hs-lay-fenster'); fenster.setAttribute('role', 'group'); fenster.setAttribute('aria-label', 'Bühne: Seitenaufbau des Fensters');
    const zone = (id, text)=>{ const z = d().el('div', 'hs-lay-zone hs-lay-zone-' + id, text); z.dataset.zone = id; z.tabIndex = 0; return z; };
    const seite = zone('seite', 'Seitenleiste'), leiste = zone('leiste', 'Taskleiste (Start, Status)');
    const haupt = d().el('div', 'hs-lay-haupt');
    const reiter = d().el('div', 'hs-lay-reiter', 'Reiter'), flaeche = d().el('div', 'hs-lay-flaeche', 'Arbeitsfläche'), eingabe = zone('eingabe', 'Eingabefeld');
    haupt.append(reiter, flaeche, eingabe);
    fenster.append(seite, haupt, leiste);
    const zeichne = ()=>{
      const z = st.zonen, k = B.zonenKlassen(z);
      Object.keys(k).forEach(n=>fenster.classList.toggle(n, k[n]));
      fenster.style.setProperty('--lay-seite-b', (z.seite.breite || 260) / 13 + '%');
      eingabe.style.width = z.eingabe.breite ? Math.min(100, z.eingabe.breite / 14) + '%' : '';
      seite.textContent = 'Seitenleiste · ' + z.seite.platz + (z.seite.breite ? ' · ' + z.seite.breite + ' px' : '');
      leiste.textContent = 'Taskleiste · ' + z.taskleiste.platz;
      eingabe.textContent = 'Eingabefeld · ' + z.eingabe.platz + (z.eingabe.breite ? ' · ' + z.eingabe.breite + ' px' : '');
      Object.keys(felder).forEach(n=>felder[n]());
    };
    // Ziehen: die Seite, auf der die Maus beim Loslassen (und beim Ziehen) steht, ist der neue Platz
    const ziehen = (el, id)=>el.addEventListener('pointerdown', ev=>{
      ev.preventDefault();
      try{ el.setPointerCapture(ev.pointerId); }catch(_e){ /* ohne Capture folgt die Maus nur im Element */ }
      const r = fenster.getBoundingClientRect(), h = haupt.getBoundingClientRect();
      const bewegt = e=>{
        if(id === 'seite') st.zonen.seite.platz = e.clientX - r.left > r.width / 2 ? 'rechts' : 'links';
        else if(id === 'leiste') st.zonen.taskleiste.platz = e.clientY - r.top > r.height / 2 ? 'unten' : 'oben';
        else st.zonen.eingabe.platz = e.clientY - h.top > h.height / 2 ? 'unten' : 'oben';
        zeichne();
      };
      const ende = ()=>{ el.removeEventListener('pointermove', bewegt); el.removeEventListener('pointerup', ende); el.removeEventListener('pointercancel', ende); };
      el.addEventListener('pointermove', bewegt); el.addEventListener('pointerup', ende); el.addEventListener('pointercancel', ende);
    });
    ziehen(seite, 'seite'); ziehen(leiste, 'leiste'); ziehen(eingabe, 'eingabe');
    // genaue Eingabe: Platz und Breite (für Tastatur und Feinarbeit); jede Zeile spiegelt den Stand der Bühne
    const felder = {};
    const zeile = (name, titel, optionen, breitenTitel, von, bis)=>{
      const z = d().el('div', 'hs-einst-zeile hs-lay-zonenzeile'); z.dataset.zone = name;
      const sel = d().el('select', 'hs-projektwahl'); sel.setAttribute('aria-label', 'Platz: ' + titel);
      optionen.forEach(o=>{ const e = document.createElement('option'); e.value = o; e.textContent = o; sel.append(e); });
      sel.onchange = ()=>{ st.zonen[name].platz = sel.value; zeichne(); };
      z.append(d().el('b', 'hs-einst-label', titel), sel);
      let zahl = null;
      if(breitenTitel){
        zahl = d().el('input', 'hs-einst-zahl'); zahl.type = 'number'; zahl.step = '10'; zahl.setAttribute('aria-label', breitenTitel);
        zahl.onchange = ()=>{ const w = Math.round(Number(zahl.value) || 0); st.zonen[name].breite = w === 0 ? 0 : Math.max(von, Math.min(bis, w)); zeichne(); };
        z.append(d().el('small', 'hs-leise', 'Breite in px (0 = Vorgabe, ' + von + ' bis ' + bis + ')'), zahl);
      }
      felder[name] = ()=>{ sel.value = st.zonen[name].platz; if(zahl) zahl.value = st.zonen[name].breite; };
      return z;
    };
    const genau = d().el('div', 'hs-liste');
    genau.append(zeile('seite', 'Seitenleiste', ['links', 'rechts'], 'Breite der Seitenleiste', 180, 480), zeile('taskleiste', 'Taskleiste', ['unten', 'oben']),
                 zeile('eingabe', 'Eingabefeld', ['unten', 'oben'], 'Breite des Eingabefelds', 480, 1400));
    feld.append(d().el('h3', 'hs-ueber', 'Seitenaufbau: wo die großen Zonen stehen'),
                d().el('small', 'hs-leise', 'Seitenleiste nach links oder rechts, Taskleiste nach oben oder unten, Eingabefeld über oder unter die Arbeitsfläche – ziehen oder in der Liste wählen. Keine Zone verschwindet. In der leeren Sitzung bleibt das Eingabefeld, wo der Baukasten es hinstellt.'),
                fenster, genau);
    zeichne();
  }

  function zeigen(S, feld){
    const B = H().bausteine, D = H().desktop;
    if(!B || !D){ feld.append(d().el('small', 'hs-leise', 'Der Baukasten ist nicht geladen.')); return; }
    const l = B.layoutVon(S);
    feld.append(d().el('div', 'hs-app-satz', 'Baukasten und Raster: jedes Teil der Oberfläche ist ein Baustein mit Rahmen, den du verschieben, in der Größe ändern oder ausblenden kannst. Das Layout gehört zum Profil. Das Freigabe-Schild und „Senden“ bleiben immer sichtbar. Ausblenden ist Zuschnitt, keine Sperre.'));
    const meld = d().el('div', 'hs-leise');
    const liste = (alle, wahl)=>{ const platz = B.reihenfolge(alle, wahl.reihenfolge); return {reihe: alle.slice().sort((a, b)=>platz[a] - platz[b]), aus: new Set(wahl.ausblenden || [])}; };
    const st = {start: B.rasterVon(l), zeile: liste(B.ZEILE.map(x=>x[0]), l.zeile), werkzeuge: liste(B.WERKZEUGE.map(x=>x[0]), l.werkzeuge)};
    st.zonen = JSON.parse(JSON.stringify(B.zonenVon(l)));
    zonenBuehne(S, feld, st);
    st.menue = liste(B.MENUE.map(x=>x[0]), l.menue); st.blick = liste(B.BLICK.map(x=>x[0]), l.blick);
    bauen(S, feld, st);
    menueBuehne(S, feld, st);
    const holen = (state, alle)=>({reihenfolge: gleich(state.reihe, alle) ? [] : state.reihe.slice(), ausblenden: [...state.aus]});
    const sichern = d().button('Layout speichern', async ()=>{
      const start = {};
      B.START.forEach(([id])=>{ if(!gleich(st.start[id], B.klemmen(B.STANDARD[id]))) start[id] = st.start[id]; });
      try{
        await D.speichern(S, {layout: {start, zeile: holen(st.zeile, B.ZEILE.map(x=>x[0])), werkzeuge: holen(st.werkzeuge, B.WERKZEUGE.map(x=>x[0])),
                                       menue: holen(st.menue, B.MENUE.map(x=>x[0])), blick: holen(st.blick, B.BLICK.map(x=>x[0])), zonen: st.zonen}});
        meldung(meld, 'Gespeichert – das Layout gilt sofort.');
      }catch(err){ meldung(meld, 'Nicht gespeichert: ' + err.message, true); }
    });
    const zurueck = d().button('Auf Vorgabe zurücksetzen', async ()=>{
      try{ await D.speichern(S, {layout: null}); meldung(meld, 'Die Vorgabe der Shell gilt wieder.'); H().builder.zeigen(S, 'layout'); }
      catch(err){ meldung(meld, 'Nicht zurückgesetzt: ' + err.message, true); }
    });
    const aktion = d().el('div', 'hs-builder-aktion'); aktion.append(sichern, zurueck);
    feld.append(aktion, meld);
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.layouteditor = {zeigen};
})();
