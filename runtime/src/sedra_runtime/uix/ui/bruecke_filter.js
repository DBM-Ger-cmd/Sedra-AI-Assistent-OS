// UI contract – AM3 (SPEC_APPS_v1_AM3_BERECHTIGUNG AM3-16 bis AM3-18, AM3-20, AM3-23): was eine fremde App (COMMUNITY) über die Brücke sehen und senden darf.
// Rein, ohne DOM, auch unter Node. `filterEreignis` schneidet Ereignisse mit Inhalt auf feste Schlüssel zu (öffentliche Ereignisse gehen unverändert durch, alles
// andere gar nicht), `bereinigeHinweis` macht aus einem Hinweis der App einen kurzen, gekennzeichneten Text, `drossel` begrenzt Hinweise und Zellenwerte je App,
// `pruefeZelle` prüft den Wert einer fremden Leistenzelle (noch nicht angeschlossen: die Brückennachricht `zelle` gibt es erst mit AM3).
// Gebaut als Kandidat von SEDRAs Factory-Bau (`bruecke_filter`, 11.11.2026), von Hand nachgearbeitet: `hasOwnProperty` wird über Object.prototype aufgerufen
// (ein Nutzlast-Objekt ohne Prototyp oder mit eigenem Schlüssel `hasOwnProperty` hätte den Filter gebrochen).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
var EREIGNIS_OEFFENTLICH = [
  "system.state",
  "model.changed",
  "desk.resync",
  "tools.refresh",
  "slot.changed"
];

var EREIGNIS_SCHLUESSEL = {
  "decision.pending": ["id", "kind", "way"],
  "decision.answered": ["id", "kind", "way"],
  "task.changed": ["id", "phase"],
  "object.open": ["type", "id"],
  "agent.changed": ["id"],
  "issue.changed": ["id"],
  "budget.warning": ["agent_id", "stufe"]
};

function filterEreignis(name, payload) {
  if (typeof name !== "string") {
    return null;
  }

  var i;
  for (i = 0; i < EREIGNIS_OEFFENTLICH.length; i++) {
    if (name === EREIGNIS_OEFFENTLICH[i]) {
      if (payload === undefined) {
        return {};
      }
      return payload;
    }
  }

  if (Object.prototype.hasOwnProperty.call(EREIGNIS_SCHLUESSEL, name)) {
    var keys = EREIGNIS_SCHLUESSEL[name];
    var result = {};
    if (payload !== null && typeof payload === "object") {
      var j;
      for (j = 0; j < keys.length; j++) {
        if (Object.prototype.hasOwnProperty.call(payload, keys[j])) {
          var val = payload[keys[j]];
          if (typeof val === "string" || typeof val === "number" || typeof val === "boolean") {
            result[keys[j]] = val;
          }
        }
      }
    }
    return result;
  }

  return null;
}

function bereinigeHinweis(appName, text, ton) {
  if (typeof appName !== "string" || typeof text !== "string") {
    return null;
  }

  // Remove control characters U+0000 to U+001F and U+007F
  var cleaned = text.replace(/[\u0000-\u001F\u007F]/g, "");

  // Trim spaces at both ends
  cleaned = cleaned.trim();

  // If nothing is left, return null
  if (cleaned === "") {
    return null;
  }

  // Build result: appName + ": " + cleaned, cut to at most 200 characters
  var result = appName + ": " + cleaned;
  if (result.length > 200) {
    result = result.substring(0, 200);
  }

  return { text: result, ton: "note" };
}

function drossel(intervallMs) {
  var last = Object.create(null);
  return function erlaubt(schluessel, jetztMs) {
    var key = String(schluessel);
    if (Object.prototype.hasOwnProperty.call(last, key) && (jetztMs - last[key]) < intervallMs) {
      return false;
    }
    last[key] = jetztMs;
    return true;
  };
}

function pruefeZelle(msg) {
  if (msg === null || msg === undefined || typeof msg !== "object") {
    return null;
  }
  if (typeof msg.wert !== "string" || msg.wert === "") {
    return null;
  }
  var wert = msg.wert.substring(0, 24);
  var hinweis = typeof msg.hinweis === "string" ? msg.hinweis.substring(0, 80) : "";
  var ton = msg.ton === "ok" || msg.ton === "warn" || msg.ton === "off" ? msg.ton : "off";
  return { wert: wert, hinweis: hinweis, ton: ton };
}

  const api = {EREIGNIS_OEFFENTLICH, EREIGNIS_SCHLUESSEL, filterEreignis, bereinigeHinweis, drossel, pruefeZelle};
  root.sedraBrueckeFilter = api;
  if(typeof module !== 'undefined' && module.exports) module.exports = api;
})();
