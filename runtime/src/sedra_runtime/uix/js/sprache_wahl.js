// X5: Sprache DE/EN – UI-Strings aus zentraler Textdatei, Umschaltung ohne Neustart, Fallback auf DE.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

var SPRACHE = {code:'de', name:'Deutsch', aktiv:true};
var STRINGEINGELADEN = false;

var STRINGS_DE = {
  btn_speichern:'Speichern', btn_schliessen:'Schließen', btn_öffnen:'Öffnen', btn_abbrechen:'Abbrechen',
  btn_senden:'Senden', btn_anhangen:'Anhängen',
  lbl_kommando:'Kommando', lbl_sprache:'Sprache', lbl_deutsch:'Deutsch', lbl_englisch:'Englisch',
  lbl_deck:'Deck', lbl_sedra:'SEDRA', lbl_werkstatt:'Werkstatt', lbl_besatzung:'Besatzung',
  lbl_bibliothek:'Bibliothek', lbl_einstellungen:'Einstellungen', lbl_karten:'Karten', lbl_projekte:'Projekte',
  lbl_meter:'Guppy-Meter', lbl_logbuch:'Logbuch', lbl_hardware:'Hardware', lbl_maschinenraum:'Maschinenraum',
  lbl_entwicklung:'Entwicklungsumgebung',
  msg_fehler:'Fehler', msg_info:'Information', msg_warnung:'Warnung', msg_erfolg:'Erfolg',
  msg_lädt:'Wird geladen …', msg_nichts_gefunden:'Nicht gefunden', msg_keine_verbindung:'Keine Verbindung zur Runtime',
  msg_freigabe_erforderlich:'Captain-Freigabe erforderlich', msg_freigabe_erteilt:'Freigabe erteilt', msg_freigabe_abgelehnt:'Freigabe abgelehnt',
  lbl_palette_platzhalter:'Was willst du tun?', lbl_palette_fuss:'↑↓ wählen · Enter ausführen · Esc schließen · Strg+K öffnet das Kommando von überall',
  lbl_historie:'Zuletzt', lbl_vorschlag:'Vorschlag', lbl_vorlage_laden:'Vorlage laden',
  lbl_rueckgaengig:'Rückgängig', lbl_wiederholen:'Wiederholen',
  lbl_barrierefrei:'Barrierefreiheit', lbl_fokus:'Fokus', lbl_aria_label:'Beschriftung',
  msg_kontrast_ok:'Kontrast OK (WCAG AA)', msg_kontrast_zu_niedrig:'Kontrast zu niedrig',
  lbl_tab_reihenfolge:'Tab-Reihenfolge', lbl_eingabefeld:'Eingabefeld', lbl_schaltfläche:'Schaltfläche',
  lbl_menü:'Menü', lbl_dialog:'Dialog', lbl_schließen:'Schließen', lbl_minimieren:'Minimieren', lbl_maximieren:'Maximieren'
};

var STRINGS_EN = {
  btn_speichern:'Save', btn_schliessen:'Close', btn_öffnen:'Open', btn_abbrechen:'Cancel',
  btn_senden:'Send', btn_anhangen:'Attach',
  lbl_kommando:'Command', lbl_sprache:'Language', lbl_deutsch:'German', lbl_englisch:'English',
  lbl_deck:'Deck', lbl_sedra:'SEDRA', lbl_werkstatt:'Workshop', lbl_besatzung:'Crew',
  lbl_bibliothek:'Library', lbl_einstellungen:'Settings', lbl_karten:'Cards', lbl_projekte:'Projects',
  lbl_meter:'Guppy Meter', lbl_logbuch:'Logbook', lbl_hardware:'Hardware', lbl_maschinenraum:'Machine Room',
  lbl_entwicklung:'Development Environment',
  msg_fehler:'Error', msg_info:'Information', msg_warnung:'Warning', msg_erfolg:'Success',
  msg_lädt:'Loading …', msg_nichts_gefunden:'Not found', msg_keine_verbindung:'No connection to Runtime',
  msg_freigabe_erforderlich:'Captain approval required', msg_freigabe_erteilt:'Approval granted', msg_freigabe_abgelehnt:'Approval rejected',
  lbl_palette_platzhalter:'What do you want to do?', lbl_palette_fuss:'↑↓ select · Enter execute · Esc close · Strg+K opens command from anywhere',
  lbl_historie:'Recent', lbl_vorschlag:'Suggestion', lbl_vorlage_laden:'Load template',
  lbl_rueckgaengig:'Undo', lbl_wiederholen:'Redo',
  lbl_barrierefrei:'Accessibility', lbl_fokus:'Focus', lbl_aria_label:'Label',
  msg_kontrast_ok:'Contrast OK (WCAG AA)', msg_kontrast_zu_niedrig:'Contrast too low',
  lbl_tab_reihenfolge:'Tab order', lbl_eingabefeld:'Input field', lbl_schaltfläche:'Button',
  lbl_menü:'Menu', lbl_dialog:'Dialog', lbl_schließen:'Close', lbl_minimieren:'Minimize', lbl_maximieren:'Maximize'
};

function ladeSprache(code){
  var datei = code === 'en' ? 'strings_en.json' : 'strings_de.json';
  var pfad = '/uix/js/' + datei;
  try{
    if(typeof XMLHttpRequest !== 'undefined'){
      var xhr = new XMLHttpRequest();
      xhr.open('GET', pfad, false);
      xhr.send(null);
      if(xhr.status === 200 || xhr.status === 0){
        var daten = JSON.parse(xhr.responseText);
        if(code === 'en') STRINGS_EN = daten; else STRINGS_DE = daten;
      }
    }
  }catch(e){
    // Datei noch nicht vorhanden → Inline-Daten bleiben
  }
  STRINGEINGELADEN = true;
  SPRACHE.code = code;
  SPRACHE.name = code === 'en' ? 'English' : 'Deutsch';
  SPRACHE.aktiv = true;
  return {ok:true, code:code};
}

function t(schluessel){
  if(!STRINGEINGELADEN){ ladeSprache(SPRACHE.code || 'de'); }
  var tabelle = SPRACHE.code === 'en' ? STRINGS_EN : STRINGS_DE;
  var wert = tabelle[schluessel];
  if(wert === undefined){
    wert = STRINGS_DE[schluessel] || schluessel;
    if(SPRACHE.code === 'en') console.warn('Sprache: fehlende Übersetzung EN→DE für "'+schluessel+'"');
  }
  return wert;
}

function spracheUmschalten(code){
  return ladeSprache(code);
}

function spracheAktuell(){
  return {code:SPRACHE.code, name:SPRACHE.name, aktiv:SPRACHE.aktiv};
}

function alleStringsBereit(){
  var schlüssel = Object.keys(STRINGS_DE).concat(Object.keys(STRINGS_EN));
  var einzigartig = {};
  schlüssel.forEach(s=>{ einzigartig[s] = true; });
  var fehlend = [];
  Object.keys(einzigartig).forEach(s=>{
    if(STRINGS_DE[s] === undefined || STRINGS_EN[s] === undefined){
      fehlend.push(s);
    }
  });
  return {bereit: fehlend.length === 0, fehlend: fehlend};
}


if(typeof module !== 'undefined' && module.exports){ module.exports = {ladeSprache, t, spracheUmschalten, spracheAktuell, alleStringsBereit, SPRACHE, STRINGS_DE, STRINGS_EN}; }
