// Harness-Shell (One Sedra) – X4 Befehlspalette (Strg+K) und Tastaturkürzel.
//
// Die Palette ist eine Overlay-Eingabe: Strg+K öffnet, Esc schließt, die Suche filtert,
// die Auswahl ruft den bestehenden Chat-/Harness-Weg auf. Schreibwerkzeuge werden nie
// direkt ausgeführt, sondern nur als Antrag (Gate/Karte) angemeldet (X4-05/X4-06). Werkzeug-
// zeilen füllen das Eingabefeld der Sitzung mit einem Befehlsanfang; der Mensch schickt ab.
// Reine Teile (Zeilenbau, Suche, Kürzel-Prüfung, Historie) laufen auch unter node
// (kein DOM) und werden von test_uix_harness_palette.py geprüft. Der Overlay-Teil benötigt
// document und läuft nur im Browser.
//
// UI-Regeln: DOM-Inhalte nur per textContent gesetzt, keine Hex-Farben (CSS separat),
// kein Polling-Timer, Datei unter 400 Zeilen.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const H = root.sedraHarness;

  const HOST_ID = 'hs-palette';
  const HISTORIE_MAX = 10;

  // ---- Shell-Aktionen (direkt ausführbar in der Harness-Shell) ----
  const SHELL_BEFEHLE = [
    {id:'sit_neu',        label:'Neue Sitzung',          hint:'Neues Gespräch öffnen',                                                  kuerzel:'Strg+N'},
    {id:'posteingang',    label:'Posteingang öffnen',    hint:'Offene Freigaben und Anträge (Karten)',                                  kuerzel:''},
    {id:'einstellungen',  label:'Einstellungen',         hint:'Sprache, Freigaben, Schalter, Katalog',                                  kuerzel:''},
    {id:'startmenue',     label:'Start-Menü öffnen',     hint:'Apps, Oberflächen, Darstellung · Schrift',                               kuerzel:'Alt+S'},
    {id:'seitenleiste',   label:'Seitenleiste',          hint:'Ein-/ausblenden',                                                        kuerzel:'Strg+B'},
    {id:'vorschau',       label:'Vorschau',              hint:'Datei neben dem Gespräch ein-/ausblenden',                               kuerzel:'Strg+Umschalt+X'},
    {id:'launcher',       label:'Befehlspalette',        hint:'Diese Überlagerung schließen',                                           kuerzel:'Strg+K'}
  ];

  // ---- Chat-/Harness-Werkzeuge (aus NAMEN, Einstufung wie werkzeuge.py/katalog.py) ----
  // Lesende Werkzeuge dürfen über den bestehenden Chat-/Harness-Weg aufgerufen werden;
  // Schreibwerkzeuge nur über einen Antrag (Captain-Freigabe), nie direkt aus der Palette.
  const LESENDO = ['datei_lesen','dateien_auflisten','suchen','lauf_status','sitzungen_auflisten'];
  const SCHREIBWERKZEUGE = ['datei_schreiben','datei_aendern','desktop_aendern'];
  const WERKZEUG_BEFEHLE = [
    {id:'datei_lesen',            label:'Datei lesen',               hint:'Inhalt einer Datei aus dem Projekt lesen',                  kategorie:'werkzeug'},
    {id:'dateien_auflisten',      label:'Dateien auflisten',         hint:'Projektordner und Dateien anzeigen',                        kategorie:'werkzeug'},
    {id:'suchen',                 label:'Suchen',                    hint:'Text in Dateien suchen',                                    kategorie:'werkzeug'},
    {id:'lauf_status',            label:'Lauf-Status',               hint:'Status eines KI-Laufs abfragen',                            kategorie:'werkzeug'},
    {id:'sitzungen_auflisten',    label:'Sitzungen auflisten',       hint:'Bestehende Gespräche zeigen',                              kategorie:'werkzeug'},
    {id:'datei_schreiben',        label:'Datei schreiben',           hint:'Neue Datei anlegen – benötigt Captain-Freigabe',            kategorie:'werkzeug', schreibwerkzeug:true},
    {id:'datei_aendern',          label:'Datei ändern',              hint:'Eine Stelle ersetzen – benötigt Captain-Freigabe',          kategorie:'werkzeug', schreibwerkzeug:true},
    {id:'desktop_aendern',        label:'Desktop ändern',            hint:'Oberflächen-Zuschnitt speichern – benötigt Captain-Freigabe', kategorie:'werkzeug', schreibwerkzeug:true}
  ];

  // ---- Befehls-Historie (max. 10 Einträge, pro Sitzung, nur im Speicher) ----
  var HISTORIE = [];
  function histHinzufuegen(id){
    if(!id) return;
    HISTORIE = HISTORIE.filter(function(h){ return h !== id; });
    HISTORIE.unshift(id);
    if(HISTORIE.length > HISTORIE_MAX) HISTORIE.length = HISTORIE_MAX;
  }
  function historie(){ return HISTORIE.slice(); }

  // ---- Kürzel-Tabelle (globale + Builder-Kürzel), keine Doppelbelegung ----
  function kuerzelString(k){
    return (k.ctrl ? 'Strg+' : '') + (k.meta ? 'Cmd+' : '') + (k.shift ? 'Umschalt+' : '') + k.key.toUpperCase();
  }

  var KUERZEL = [
    {kuerzel:'Strg+K',   key:'k',   ctrl:true,  aktion:'palette öffnen',  beschreibung:'Befehlspalette öffnen', builder:false},
    {kuerzel:'Esc',      key:'Escape',                 aktion:'palette schließen', beschreibung:'Befehlspalette schließen', builder:false},
    {kuerzel:'Strg+S',   key:'s',   ctrl:true,  aktion:'speichern',       beschreibung:'Aktuellen Kontext speichern', builder:false},
    {kuerzel:'Strg+B',   key:'b',   ctrl:true,  aktion:'seitenleiste',    beschreibung:'Seitenleiste ein-/ausblenden', builder:false},
    {kuerzel:'Alt+S',    key:'s',   alt:true,   aktion:'startmenue',      beschreibung:'Start-Menü öffnen', builder:false}
  ];

  // Prüft eine Kürzel-Liste auf Doppelbelegungen; gibt Konflikte zurück (leer = OK).
  function kuerzelPruefen(liste){
    var l = liste || KUERZEL, gesehen = {}, konflikte = [];
    l.forEach(function(k){
      var ks = kuerzelString(k);
      if(gesehen[ks]) konflikte.push({kuerzel:ks, erstes:gesehen[ks], zweites:k.aktion});
      else gesehen[ks] = k.aktion;
    });
    return konflikte;
  }

  function kuerzelListe(){ return KUERZEL.slice(); }

  function befehlIstSchreibwerkzeug(id){ return SCHREIBWERKZEUGE.indexOf(id) >= 0; }

  // ---- Eingabefeld der Sitzung befüllen (bestehender Chat-/Harness-Weg, kein direkter Aufruf) ----
  function eingabeFuellen(S, text, praefix){
    if(!S || !S._eingabe || !S._eingabe.feld) return false;
    S._eingabe.feld.value = (praefix ? praefix + ' ' : '') + text;
    S._eingabe.feld.focus();
    try{ S._eingabe.feld.dispatchEvent(new Event('input', {bubbles: true})); }catch(_e){}
    return true;
  }

  // Erzeugt einen Antrag (Karte) für ein Schreibwerkzeug, statt es direkt auszuführen.
  // Rückgabe: {gate_required: true, befehlId, text, hinweis}
  function schreibwerkzeugAntrag(befehlId, text){
    return {gate_required: true, befehlId: befehlId, text: text||'', hinweis: 'Captain-Freigabe erforderlich für Schreibwerkzeug aus der Befehlspalette.'};
  }

  // Führt ein Schreibwerkzeug erst nach Captain-Entscheidung aus (genehmigt=true -> über den Chat-/Harness-Weg).
  function schreibwerkzeugAusfuehren(befehlId, genehmigt){
    if(!genehmigt) return {ausgefuehrt: false, befehlId: befehlId, gate_required: true, hinweis: 'Freigabe verweigert oder nicht erteilt.'};
    return {ausgefuehrt: true, befehlId: befehlId, gate_required: false, hinweis: 'Nach Captain-Freigabe ausgeführt.'};
  }

  // Baut die Zeilen der Palette (rein): Historie oben, dann Shell-Aktionen und Werkzeuge,
  // gefiltert nach Titel/Hinweis/ID (nicht case-sensitiv).
  function befehlszeilen(text){
    var q = String(text||'').toLowerCase().trim();
    var zeilen = [];
    if(!q){
      historie().forEach(function(h){ zeilen.push({id:'hist:'+h, label:'Zuletzt: '+h, hint:'Letzte Befehle', kategorie:'historie'}); });
    }
    [].concat(SHELL_BEFEHLE, WERKZEUG_BEFEHLE).forEach(function(b){
      var hay = (b.label + ' ' + (b.hint||'') + ' ' + b.id).toLowerCase();
      if(!q || hay.indexOf(q) >= 0){
        zeilen.push({id:b.id, label:b.label, hint:b.hint||'', kategorie:b.kategorie||'shell', kuerzel_anzeige:b.kuerzel||'', schreibwerkzeug:!!b.schreibwerkzeug});
      }
    });
    return zeilen;
  }

  // ---- Overlay (nur Browser, braucht document) ----
  var host = null, input = null, list = null, index = 0, shell = null;

  function build(){
    host = d().el('div', HOST_ID);
    host.setAttribute('role', 'dialog');
    host.setAttribute('aria-modal', 'true');
    host.setAttribute('aria-label', 'Befehlspalette');
    host.hidden = true;
    var box = d().el('div', 'pal-box');
    input = d().el('input');
    input.type = 'text';
    input.setAttribute('aria-label', 'Befehl oder Werkzeug');
    input.placeholder = 'Befehl oder Werkzeug – Strg+K öffnet, Esc schließt';
    list = d().el('div', 'pal-list');
    list.setAttribute('role', 'listbox');
    input.oninput = function(){ index = 0; renderList(); };
    input.onkeydown = function(e){
      var rows = befehlszeilen(input.value);
      if(e.key === 'ArrowDown'){ e.preventDefault(); index = Math.min(rows.length - 1, index + 1); renderList(); }
      else if(e.key === 'ArrowUp'){ e.preventDefault(); index = Math.max(0, index - 1); renderList(); }
      else if(e.key === 'Enter'){ e.preventDefault(); wähle(rows[index]); }
      else if(e.key === 'Escape'){ e.preventDefault(); schliessen(); }
    };
    box.append(input, list);
    host.append(box);
    host.onmousedown = function(e){ if(e.target === host) schliessen(); };
    document.body.append(host);
    renderList();
  }

  function renderList(){
    var rows = befehlszeilen(input ? input.value : '');
    index = Math.max(0, Math.min(index, rows.length - 1));
    list.replaceChildren.apply(list, rows.map(function(r, i){
      var line = d().el('div', 'pal-row' + (i === index ? ' on' : '') + (r.kategorie === 'historie' ? ' zuletzt' : ''));
      line.setAttribute('role', 'option');
      line.setAttribute('aria-selected', i === index ? 'true' : 'false');
      line.append(d().el('b', null, r.label), d().el('small', null, r.hint || ''));
      if(r.kuerzel_anzeige) line.append(d().el('small', 'pal-kuerzel', r.kuerzel_anzeige));
      if(r.schreibwerkzeug) line.append(d().el('small', 'pal-warn', '· Freigabe'));
      line.onmousedown = function(e){ e.preventDefault(); wähle(r); };
      line.onmousemove = function(){ if(index !== i){ index = i; renderList(); } };
      return line;
    }));
  }

  // Auswahl: Shell-Aktionen rufen echte Shell-Funktionen auf.
  // Werkzeugzeilen füllen das Eingabefeld der Sitzung (bestaender Chat-/Harness-Weg, kein direkter Aufruf).
  // Schreibwerkzeuge bekommen die Kennzeichnung „braucht Freigabe“.
  function wähle(row){
    if(!row) return null;
    schliessen();
    var text = input ? input.value.trim() : '';
    histHinzufuegen(row.id);
    if(String(row.id).indexOf('hist:') === 0){
      return wähle({id: row.id.slice(5), label: row.label, hint: row.hint, kategorie: row.kategorie, schreibwerkzeug: row.schreibwerkzeug});
    }
    if(shell){
      if(row.id === 'sit_neu' && shell.reiter && shell.reiter.neu){ return shell.reiter.neu(shell); }
      if(row.id === 'posteingang' && shell.shellApi && shell.shellApi.decide){ return shell.shellApi.decide('alle'); }
      if(row.id === 'einstellungen' && H.einstellungen && H.einstellungen.oeffnen){ return H.einstellungen.oeffnen(shell); }
      if(row.id === 'startmenue' && H.startmenue && H.startmenue.oeffnen){ return H.startmenue.oeffnen(shell); }
      if(row.id === 'seitenleiste' && shell.seiteUmschalten){ shell.seiteUmschalten(); return null; }
      if(row.id === 'vorschau' && H.vorschau && H.vorschau.tauschen){ H.vorschau.tauschen(shell); return null; }
      if(row.id === 'launcher'){ return null; }
    }
    if(LESENDO.indexOf(row.id) >= 0 && shell){
      eingabeFuellen(shell, text);
      return {ausfuehrung: 'werkzeug:' + row.id, text: text};
    }
    if(row.schreibwerkzeug && shell){
      eingabeFuellen(shell, text, 'braucht Freigabe:');
      return schreibwerkzeugAntrag(row.id, text);
    }
    return {ausfuehrung: row.id, text: text};
  }

  function oeffnen(s){
    if(s) shell = s;
    if(!host) build();
    host.hidden = false;
    if(input){ input.value = ''; index = 0; renderList(); }
    try{ input.focus(); }catch(_e){}
  }
  function schliessen(){ if(host) host.hidden = true; }
  function umschalten(s){ if(host && !host.hidden) schliessen(); else oeffnen(s); }
  function istGeoeffnet(){ return !!host && !host.hidden; }

  // Tastatur: Strg+K öffnet/schließt, Esc schließt (global, einmal registriert, nur im Browser)
  if(typeof document !== 'undefined' && document.addEventListener){
    document.addEventListener('keydown', function(e){
      if((e.ctrlKey || e.metaKey) && e.key === 'k'){ e.preventDefault(); umschalten(); }
      else if(e.key === 'Escape'){ if(istGeoeffnet()){ e.preventDefault(); schliessen(); } }
    }, true);
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.palette = {
    verbinde: function(s){ shell = s; },
    oeffnen: oeffnen, schliessen: schliessen, umschalten: umschalten, istGeoeffnet: istGeoeffnet,
    zeilen: befehlszeilen, schreibwerkzeugAntrag: schreibwerkzeugAntrag,
    schreibwerkzeugAusfuehren: schreibwerkzeugAusfuehren,
    kuerzelListe: kuerzelListe, kuerzelPruefen: kuerzelPruefen,
    befehlIstSchreibwerkzeug: befehlIstSchreibwerkzeug, histHinzufuegen: histHinzufuegen, historie: historie,
    eingabeFuellen: eingabeFuellen
  };
})();
