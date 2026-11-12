// Rollen-Sicht der Shell „KI Gateway für KMU“ (SPEC_APPS_v1_AM7 AM7-08, AM7-09). Rein: aus dem Zustand des Betriebs (GET /api/uix/betrieb) folgt, welche der sieben Grundfunktionen
// die Shell zeigt. Das ist eine ANZEIGE – gegen eine Person mit Administratorrechten am Rechner schützt sie nicht (AM7 §2, Betriebsart A); durchgesetzt wird anderswo (Richtlinie, Guard).
//   sachbearbeitung: Gespräch, Entscheidungen, Aufgaben/Vorgänge (AM7-08)
//   betreiber, pruefung: dazu der Zugang „Verwaltung“ mit Logbuch, Modus und Grenzen, Module und Berechtigungen, Einstellungen und Zustand (AM7-09) – dieselben Apps des Pakets
// Ohne aktive Richtlinie (Einzelplatz wie bisher) oder wenn der Zustand nicht zu lesen ist, zeigt die Shell alles. Eine bekannte Richtlinie mit unbekannter Rolle bekommt die kleinste Sicht.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const ALLE = ['entscheidungen', 'gespraech', 'aufgaben', 'logbuch', 'modus_grenzen', 'module_berechtigungen', 'einstellungen_zustand'];
  const VERWALTUNG = ['logbuch', 'modus_grenzen', 'module_berechtigungen', 'einstellungen_zustand'];
  const ROLLEN = {sachbearbeitung: ['entscheidungen', 'gespraech', 'aufgaben'], betreiber: ALLE, pruefung: ALLE};
  const ORT = {entscheidungen: 'decisions', aufgaben: 'tasks', logbuch: 'logbook', modus_grenzen: 'boundary', module_berechtigungen: 'modules', einstellungen_zustand: 'machine'};
  const TITEL = {entscheidungen: 'Entscheidungen', aufgaben: 'Aufgaben', logbuch: 'Logbuch', modus_grenzen: 'Modus und Grenzen', module_berechtigungen: 'Module und Berechtigungen', einstellungen_zustand: 'Einstellungen und Zustand'};

  // welche Grundfunktionen die Shell zeigt: Schnitt aus dem, was die Rolle sehen darf, und dem, was die Richtlinie für sie freigibt
  function sichtbar(betrieb){
    const rl = betrieb && betrieb.richtlinie;
    if(!rl || rl.aktiv !== true) return ALLE.slice();
    const rolle = ROLLEN[betrieb.rolle] || ROLLEN.sachbearbeitung;
    const frei = Array.isArray(betrieb.grundfunktionen) ? betrieb.grundfunktionen : ALLE;
    return ALLE.filter(n=>rolle.includes(n) && frei.includes(n));
  }

  // was die Leiste anbietet: die eigenen Knöpfe und – wenn mindestens eine Verwaltungsfunktion sichtbar ist – den Zugang „Verwaltung“
  function zugaenge(betrieb){
    const s = sichtbar(betrieb);
    return {gespraech: s.includes('gespraech'), entscheidungen: s.includes('entscheidungen'), aufgaben: s.includes('aufgaben'), verwaltung: VERWALTUNG.filter(n=>s.includes(n))};
  }

  const api = {ALLE, VERWALTUNG, ROLLEN, ORT, TITEL, sichtbar, zugaenge};
  if(typeof module !== 'undefined' && module.exports) module.exports = api; else root.sedraKmuRollen = api;
})();
