// Minimal-Shell – die Bildzeichen der Ablage (Build 19, Captain 15.10.: „die Icons sollten hier angepasst werden“).
//
// Eigene, schlichte Linienzeichen auf 24×24, gezeichnet mit `currentColor` – sie folgen damit dem Thema (Klar/Nacht) ohne eine
// eigene Farbe. Keine Bilddatei, keine fremde Bibliothek, kein HTML als Text: jedes Zeichen ist eine Liste von Pfaden, aus denen
// `iconEl` SVG-Knoten baut. `ICONS`, `typeIcon` und `iconIds` sind rein und werden mit node geprüft.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;

  // id -> [Beschriftung im Auswahlfeld, Pfade]
  const ICONS = {
    aufgaben:   ['Aufgaben',   ['M9 6h11', 'M9 12h11', 'M9 18h11', 'M4 5.5l1.2 1.2L7 5', 'M4 11.5l1.2 1.2L7 11', 'M4 17.5l1.2 1.2L7 17']],
    vorhaben:   ['Vorhaben',   ['M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18', 'M12 7a5 5 0 1 0 0 10a5 5 0 1 0 0-10', 'M12 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2']],
    projekt:    ['Projekt',    ['M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z']],
    werkstatt:  ['Werkstatt',  ['M14.5 5.5a4 4 0 0 0-5 5L4 16l4 4l5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5l-2.5-.5l-.5-2.5z']],
    besatzung:  ['Besatzung',  ['M9 5a3 3 0 1 0 0 6a3 3 0 1 0 0-6', 'M3 20a6 6 0 0 1 12 0', 'M16 5a3 3 0 0 1 0 6', 'M17 14a5 5 0 0 1 4 6']],
    bibliothek: ['Bibliothek', ['M4 4h4v16H4z', 'M10 4h4v16h-4z', 'M16 5l3.5-1l2.5 15.5l-3.5 1z']],
    logbuch:    ['Logbuch',    ['M6 3h10l3 3v15H6z', 'M9 9h7', 'M9 13h7', 'M9 17h4']],
    entscheidung: ['Entscheidung', ['M12 3l8 4v5c0 4.5-3.5 8-8 9c-4.5-1-8-4.5-8-9V7z', 'M8.5 12l2.5 2.5l4.5-5']],
    maschine:   ['Maschinenraum', ['M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6', 'M12 2v3', 'M12 19v3', 'M2 12h3', 'M19 12h3', 'M4.9 4.9l2.1 2.1', 'M17 17l2.1 2.1', 'M4.9 19.1L7 17', 'M17 7l2.1-2.1']],
    hardware:   ['Hardware',   ['M6 6h12v12H6z', 'M9.5 9.5h5v5h-5z', 'M9 2v4', 'M15 2v4', 'M9 18v4', 'M15 18v4', 'M2 9h4', 'M2 15h4', 'M18 9h4', 'M18 15h4']],
    meter:      ['Guppy-Meter', ['M4 20V10', 'M10 20V4', 'M16 20v-7', 'M22 20H2']],
    module:     ['Module',     ['M4 4h7v7H4z', 'M13 4h7v7h-7z', 'M4 13h7v7H4z', 'M16.5 13v7', 'M13 16.5h7']],
    grenzen:    ['Grenzen',    ['M5 11h14v10H5z', 'M8 11V7a4 4 0 0 1 8 0v4']],
    kandidat:   ['Kandidat',   ['M8 7l-5 5l5 5', 'M16 7l5 5l-5 5', 'M14 4l-4 16']],
    gespraech:  ['Gespräch',   ['M4 5h16v11H9l-5 4z']],
    auftrag:    ['Auftrag',    ['M4 12l16-8l-6 16l-3-6z', 'M11 14l9-10']],
    blitz:      ['Blitz',      ['M13 2L4 14h7l-1 8l9-12h-7z']],
    stern:      ['Stern',      ['M12 3l2.8 5.8l6.2.9l-4.5 4.4l1.1 6.2L12 17.4l-5.6 2.9l1.1-6.2L3 9.7l6.2-.9z']],
    fahne:      ['Fahne',      ['M5 21V4', 'M5 4h12l-2 4l2 4H5']],
    rakete:     ['Rakete',     ['M12 3c4 2 6 6 6 10l-3 3H9l-3-3c0-4 2-8 6-10', 'M12 9a1.5 1.5 0 1 0 0 3a1.5 1.5 0 1 0 0-3', 'M9 16l-2 5l3-2', 'M15 16l2 5l-3-2']],
    test:       ['Test',       ['M9 3h6', 'M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3', 'M7.5 15h9']],
    zahnrad:    ['Einstellung', ['M12 8.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7', 'M12 2l1.5 2.6l3-.6l.6 3l2.6 1.5l-1.2 2.5l1.2 2.5l-2.6 1.5l-.6 3l-3-.6L12 22l-1.5-2.6l-3 .6l-.6-3L4.3 15.5l1.2-2.5l-1.2-2.5L6.9 9l.6-3l3 .6z']],
    haus:       ['Übersicht',  ['M3 11l9-7l9 7', 'M5 10v10h5v-6h4v6h5V10']],
    gateway:    ['KI GateWay', ['M12 3l8 3v6c0 4.5-3.4 8.1-8 9c-4.6-.9-8-4.5-8-9V6z', 'M9 12h6', 'M12 9v6']],
    planung:    ['Planungstisch', ['M3 9h18', 'M5 9v10', 'M19 9v10', 'M8 5h8', 'M12 5v4', 'M9 14h6']],   // ein Tisch mit Lampe (19.10.)
    fisch:      ['Translator',      ['M3 12c3-4 7-6 11-6l5 4-5 4c-4 0-8-2-11-6z', 'M14 6l6 6-6 6', 'M8 11h.5']],   // Übersetzer: der Fisch (19.10.)
    transkript: ['Transkript', ['M5 4h14v16H5z', 'M8 9h8', 'M8 13h8', 'M8 17h5']],
    aufnahme:   ['Rekorder',   ['M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z', 'M6 11a6 6 0 0 0 12 0', 'M12 17v4', 'M9 21h6']],   // ein Mikrofon (19.10.)
    uhr:        ['Routine',    ['M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18', 'M12 7v5l3 2']],   // Spec 4: Routinen (Zeitplan)
    wissen:     ['Wissen',     ['M4 5.5C6.5 4 9.5 4 12 6c2.5-2 5.5-2 8-.5V19c-2.5-1.5-5.5-1.5-8 .5c-2.5-2-5.5-2-8-.5z', 'M12 6v13.5']],   // ein aufgeschlagenes Buch (Spec 7)
    plus:       ['Neu',        ['M12 5v14', 'M5 12h14']]
  };

  // Welches Zeichen ein Objekttyp oder ein Ort bekommt, wenn der Captain keines wählt (rein)
  const BY_TYPE = {task: 'aufgaben', intent: 'vorhaben', project: 'projekt', model: 'werkstatt', agent: 'besatzung', skill: 'bibliothek',
                   logbook: 'logbuch', decision: 'entscheidung', machine: 'maschine', hardware: 'hardware', meter: 'meter',
                   module: 'module', boundary: 'grenzen', candidate: 'kandidat', talk: 'gespraech', gateway: 'gateway', planung: 'planung', uebersetzung: 'fisch', transkript: 'transkript', aufnahme: 'aufnahme',
                   routine: 'uhr', labor: 'test', wissen: 'wissen'};      // Spec 4 (G2-S4-21): Orte Routinen und KI-Labor

  function typeIcon(type){ return BY_TYPE[type] || 'stern'; }

  // Was im Auswahlfeld steht – ohne die Zeichen, die die Shell selbst braucht (rein)
  function iconIds(){ return Object.keys(ICONS).filter(id=>id !== 'plus' && id !== 'haus'); }

  function iconEl(id, size){
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('width', String(size || 22)); svg.setAttribute('height', String(size || 22));
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('class', 'sh-min-icon');
    ((ICONS[id] || ICONS.stern)[1]).forEach(d=>{
      const p = document.createElementNS(NS, 'path');
      p.setAttribute('d', d);
      svg.append(p);
    });
    return svg;
  }

  root.sedraMinIcons = {ICONS, BY_TYPE, typeIcon, iconIds, iconEl};
  if(typeof module !== 'undefined' && module.exports) module.exports = {ICONS, BY_TYPE, typeIcon, iconIds};
})();
