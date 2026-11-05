// Harness-Shell (One Sedra) – der Baukasten (Captain 05.11.2026: die Teile der Oberfläche sollen sich anpassen und verschieben lassen). Ein Baustein ist ein Teil der Oberfläche, das eine
// Kennung trägt (`data-baustein`): die Teile der leeren Sitzung (Begrüßung, Schritte, Hilfetext), die Zeile unter dem Eingabefeld (Projekt, Vorlage, Ordner öffnen, Neues Projekt, Als
// Vorgabe merken) und die Leiste im Eingabefeld (+, Freigabe-Schild, Modell, Mikrofon, Senden). Die Wahl des Captains (S._desktop.layout, Teil eines Profils) legt fest, wo ein Baustein auf dem
// Raster steht (12 Spalten), in welcher Reihenfolge die Bausteine einer Leiste stehen und welche ausgeblendet sind. Grundfunktionen (Freigabe-Schild, Senden) bleiben immer sichtbar –
// dasselbe prüft der Server. Leer heißt: die Vorgabe der Shell, das Aussehen ändert sich dann in nichts. Der Editor dazu ist layouteditor.js im Desktop Builder.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const SPALTEN = 12, ZEILEN = 40, HOEHE = 20;
  const START = [['gruss', 'Begrüßung (Logo, Titel, Text)'], ['schritte', 'Die drei Schritte'], ['hilfe', 'Hilfetext']];
  const ZEILE = [['projekt', 'Projekt'], ['vorlage', 'Vorlage'], ['ordner', 'Ordner öffnen'], ['neues-projekt', 'Neues Projekt'], ['vorgabe', 'Als Vorgabe merken']];
  const WERKZEUGE = [['plus', 'Datei anhängen (+)'], ['schild', 'Wer freigibt (Schild)'], ['modell', 'Modell'], ['mikro', 'Mikrofon'], ['senden', 'Senden']];
  const GRUND_WERKZEUGE = ['schild', 'senden'];
  // das Start-Menü: seine Abschnitte und die Kacheln „Auf einen Blick“ (dieselbe Bauart: Reihenfolge und Sichtbarkeit; die App-Gruppen und der Weg in die Einstellungen bleiben)
  const MENUE = [['zuletzt', 'Zuletzt benutzt'], ['blick', 'Auf einen Blick'], ['gruppen', 'App-Gruppen'], ['oberflaechen', 'Oberflächen'], ['darstellung', 'Darstellung und Gedächtnis']];
  const BLICK = [['aufgaben', 'Aufgaben'], ['labor', 'KI-Labor'], ['token', 'Sedra Token'], ['hardware', 'Hardware'], ['modelle', 'Modelle'], ['einstellungen', 'Einstellungen']];
  const GRUND_MENUE = ['gruppen'], GRUND_BLICK = ['einstellungen'];
  // die Vorgabe der Shell: untereinander, volle Breite (so sieht die leere Sitzung ohne Wahl aus)
  const STANDARD = {gruss: {x: 1, y: 1, b: SPALTEN, h: 5, sichtbar: true}, schritte: {x: 1, y: 6, b: SPALTEN, h: 3, sichtbar: true}, hilfe: {x: 1, y: 9, b: SPALTEN, h: 2, sichtbar: true}};
  const LEER = ()=>({start: {}, zeile: {reihenfolge: [], ausblenden: []}, werkzeuge: {reihenfolge: [], ausblenden: []}, menue: {reihenfolge: [], ausblenden: []}, blick: {reihenfolge: [], ausblenden: []}});

  const layoutVon = S=>{ const l = S && S._desktop && S._desktop.layout; return l ? Object.assign(LEER(), l) : LEER(); };
  const ids = liste=>liste.map(x=>x[0]);

  // ---- reine Teile (node prüft sie)
  const ganz = (x, von, bis)=>Math.max(von, Math.min(bis, Math.round(Number(x) || von)));
  // Ein Baustein auf dem Raster, in die Grenzen geklemmt: x und b innerhalb von 12 Spalten, y und h innerhalb von 40 Zeilen (b höchstens 12, h höchstens 20)
  function klemmen(b){
    const br = ganz(b.b, 1, SPALTEN), x = ganz(b.x, 1, SPALTEN - br + 1), h = ganz(b.h, 1, HOEHE), y = ganz(b.y, 1, ZEILEN - h + 1);
    return {x, y, b: br, h, sichtbar: b.sichtbar !== false};
  }
  const bewegen = (b, dx, dy)=>klemmen(Object.assign({}, b, {x: b.x + dx, y: b.y + dy}));
  const groesse = (b, dw, dh)=>klemmen(Object.assign({}, b, {b: b.b + dw, h: b.h + dh}));
  // Das Raster mit der Wahl: jeder Baustein der leeren Sitzung, die Wahl über der Vorgabe
  function rasterVon(layout){
    const out = {};
    START.forEach(([id])=>{ out[id] = klemmen(Object.assign({}, STANDARD[id], (layout && layout.start && layout.start[id]) || {})); });
    return out;
  }
  const hatEigenesRaster = layout=>!!(layout && layout.start && Object.keys(layout.start).length);
  const rasterStil = b=>({gridColumn: b.x + ' / span ' + b.b, gridRow: b.y + ' / span ' + b.h});
  // Die Reihenfolge einer Leiste: genannte Bausteine zuerst in der genannten Reihenfolge, die übrigen dahinter in ihrer Vorgabe-Reihenfolge; {id: Platz in Zehnerschritten}
  function reihenfolge(alle, genannt){
    const platz = {};
    const rest = alle.filter(i=>!(genannt || []).includes(i));
    (genannt || []).filter(i=>alle.includes(i)).concat(rest).forEach((i, n)=>{ platz[i] = (n + 1) * 10; });
    return platz;
  }

  // ---- anwenden
  // Eine Leiste (Flexbox): `order` und Sichtbarkeit je Baustein; ohne Wahl wird nichts gesetzt. `zusatz`: Teile ohne Kennung, die an einem Baustein hängen – {el, nach|vor: Kennung}.
  function reiheAnwenden(behaelter, alle, wahl, zusatz){
    const aus = new Set((wahl && wahl.ausblenden) || []);
    const platz = reihenfolge(alle, wahl && wahl.reihenfolge);
    const eigen = !!(wahl && wahl.reihenfolge && wahl.reihenfolge.length);
    behaelter.querySelectorAll(':scope > [data-baustein]').forEach(k=>{
      const id = k.dataset.baustein;
      k.style.order = eigen && platz[id] !== undefined ? String(platz[id]) : '';
      k.classList.toggle('hs-baustein-aus', aus.has(id));
    });
    (zusatz || []).forEach(z=>{
      const bezug = z.nach || z.vor;
      z.el.style.order = eigen && platz[bezug] !== undefined ? String(platz[bezug] + (z.nach ? 1 : -1)) : '';
    });
  }

  // Die beiden Leisten des Eingabebereichs (eingabe.js trägt die Kennungen ein)
  function anwenden(S){
    const e = S && S._eingabe;
    if(!e) return false;
    const l = layoutVon(S);
    if(e.projektZeile) reiheAnwenden(e.projektZeile, ids(ZEILE), l.zeile);
    const leiste = e.box && e.box.querySelector && e.box.querySelector('.hs-eingabe-leiste');
    if(leiste){
      const q = s=>leiste.querySelector(s);
      const platz = reihenfolge(ids(WERKZEUGE), l.werkzeuge.reihenfolge);
      const ersteRechts = ['mikro', 'senden'].sort((x, y)=>platz[x] - platz[y])[0];          // die Lücke trennt links (+, Schild, Modell) von rechts (Mikrofon, Senden)
      const zusatz = [{el: q('.hs-kontext'), nach: 'modell'}, {el: q('.hs-luecke'), vor: ersteRechts}, {el: q('.hs-vormerk-knopf'), vor: 'senden'}].filter(z=>z.el);
      reiheAnwenden(leiste, ids(WERKZEUGE), l.werkzeuge, zusatz);
    }
    return true;
  }
  // Das Start-Menü (startmenue.js trägt die Kennungen ein): Abschnitte im Inhalt und im Fuß nach der Wahl ordnen, die Kacheln „Auf einen Blick“ ebenso
  function menueAnwenden(S, teile){
    const l = layoutVon(S);
    [teile && teile.inhalt, teile && teile.fuss].forEach(c=>{ if(c && c.querySelectorAll) reiheAnwenden(c, ids(MENUE), l.menue); });
    const blick = teile && teile.inhalt && teile.inhalt.querySelector ? teile.inhalt.querySelector(':scope > [data-baustein="blick"]') : null;
    if(blick) reiheAnwenden(blick, ids(BLICK), l.blick);
    return true;
  }

  // Die leere Sitzung: bloecke = {gruss, schritte, hilfe} (Elemente); ohne eigenes Raster bleibt die Vorgabe (untereinander), mit eigenem liegen die Bausteine auf dem Raster
  function startAnwenden(S, box, bloecke){
    const layout = layoutVon(S), raster = rasterVon(layout), eigen = hatEigenesRaster(layout);
    START.forEach(([id])=>{
      const el = bloecke[id]; if(!el) return;
      el.classList.add('hs-baustein'); el.dataset.baustein = id;
      const b = raster[id];
      if(eigen){ const stil = rasterStil(b); el.style.gridColumn = stil.gridColumn; el.style.gridRow = stil.gridRow; }
      el.classList.toggle('hs-baustein-aus', b.sichtbar === false);
      box.append(el);
    });
    box.classList.toggle('hs-raster', eigen);
    return eigen;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.bausteine = {SPALTEN, ZEILEN, HOEHE, START, ZEILE, WERKZEUGE, GRUND_WERKZEUGE, MENUE, BLICK, GRUND_MENUE, GRUND_BLICK, menueAnwenden, STANDARD, LEER, layoutVon, klemmen, bewegen, groesse, rasterVon, hatEigenesRaster, rasterStil, reihenfolge,
                                  reiheAnwenden, anwenden, startAnwenden};
})();
