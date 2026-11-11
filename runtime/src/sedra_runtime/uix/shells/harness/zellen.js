// Harness-Shell – die Zellen der Taskleiste aus den Manifesten der Instrumente (SPEC_APPS_v1_AM1, Vertrag 1.1): rein, ohne DOM, auch unter Node.
// zellenAusManifest(instrumente, auswahl) macht aus den CORE-Instrumenten und der Auswahl (leiste.json) die Zellen; pruefeAuswahl prüft die Datei;
// ZELLEN_RUECKFALL ist die eingebaute Liste, wenn die Datei fehlt oder nichts ergibt; aktionZiel sagt, was ein Klick auf eine Zelle öffnet.
// Gebaut als Kandidat von SEDRAs Factory-Bau (`zellen`, 10.11.2026), von Hand nachgearbeitet: die Kennungen werden in einer Liste statt in einem
// Objekt gemerkt (ein Instrument namens „constructor“ wäre sonst als doppelt gemeldet worden), und alles steht in einer Funktion statt im globalen Namensraum.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
const ZELLEN_RUECKFALL = [
  { id: "gauge-decisions", feld: "decisions", label: "Freigaben", ort: null, aktion: "freigaben", quelle: null },
  { id: "gauge-model", feld: "model", label: "Modell", ort: "models", aktion: "modellmenue", quelle: null },
  { id: "gauge-temp", feld: "temp", label: "Temp", ort: "hardware", aktion: null, quelle: "gpu" },
  { id: "gauge-vram", feld: "vram", label: "VRAM belegt", ort: "hardware", aktion: null, quelle: "gpu" },
  { id: "gauge-ram", feld: "ram", label: "RAM frei", ort: "hardware", aktion: null, quelle: null },
  { id: "gauge-server", feld: "server", label: "Modellserver", ort: "models", aktion: "modellmenue", quelle: null },
  { id: "gauge-scheduler", feld: "scheduler", label: "Scheduler", ort: "slots", aktion: null, quelle: null },
  { id: "gauge-state", feld: "state", label: "Zustand", ort: "machine", aktion: "einstellungen:system", quelle: null }
];

function pruefeAuswahl(roh) {
  var data;
  if (typeof roh === "string") {
    try {
      data = JSON.parse(roh);
    } catch (e) {
      throw new Error("Leiste: Datei ist kein gueltiges JSON");
    }
  } else {
    data = roh;
  }
  if (data === null || Array.isArray(data) || typeof data !== "object") {
    throw new Error("Leiste: Inhalt ist kein Objekt");
  }
  if (!Array.isArray(data.zellen)) {
    throw new Error("Leiste: zellen fehlt oder ist keine Liste");
  }
  if (data.zellen.length === 0) {
    throw new Error("Leiste: zellen ist leer");
  }
  if (data.zellen.length > 30) {
    throw new Error("Leiste: hoechstens 30 Zellen");
  }
  var seen = [];
  var ids = [];
  var re = /^[a-z0-9-]{2,40}$/;
  for (var i = 0; i < data.zellen.length; i++) {
    var entry = data.zellen[i];
    var str = String(entry);
    if (typeof entry !== "string" || !re.test(entry)) {
      throw new Error("Leiste: ungueltige Kennung " + str);
    }
    if (seen.indexOf(str) >= 0) {
      throw new Error("Leiste: Kennung doppelt: " + str);
    }
    seen.push(str);
    ids.push(str);
  }
  return { zellen: ids };
}

function zellenAusManifest(instrumente, auswahl) {
  var zellen = [];
  var fehlend = [];
  var ohneZelle = [];
  var ids = [];
  if (auswahl !== null && typeof auswahl === "object" && Array.isArray(auswahl.zellen)) {
    ids = auswahl.zellen;
  }
  var inst = Array.isArray(instrumente) ? instrumente : [];
  var seen = [];
  for (var i = 0; i < ids.length; i++) {
    var entry = ids[i];
    if (typeof entry !== "string") {
      continue;
    }
    if (seen.indexOf(entry) >= 0) {
      continue;
    }
    seen.push(entry);
    var id = entry;
    var found = null;
    for (var j = 0; j < inst.length; j++) {
      var m = inst[j];
      if (m === null || typeof m !== "object") {
        continue;
      }
      if (m.id === id && m.kind === "instrument" && m.trust === "CORE") {
        found = m;
        break;
      }
    }
    if (!found) {
      fehlend.push(id);
      continue;
    }
    var z = found.zelle;
    if (z === null || z === undefined || Array.isArray(z) || typeof z !== "object") {
      ohneZelle.push(id);
      continue;
    }
    var feld = z.feld;
    var label = z.label;
    if (typeof feld !== "string" || feld.length === 0) {
      ohneZelle.push(id);
      continue;
    }
    if (typeof label !== "string" || label.length === 0) {
      ohneZelle.push(id);
      continue;
    }
    var ort = (typeof z.ort === "string" && z.ort.length > 0) ? z.ort : null;
    var aktion = (typeof z.aktion === "string" && z.aktion.length > 0) ? z.aktion : null;
    var quelle = (typeof z.quelle === "string" && z.quelle.length > 0) ? z.quelle : null;
    zellen.push({ id: id, feld: feld, label: label, ort: ort, aktion: aktion, quelle: quelle });
  }
  return { zellen: zellen, fehlend: fehlend, ohneZelle: ohneZelle };
}

function aktionZiel(zelle) {
  if (zelle === null || typeof zelle !== "object") {
    return { art: "keine" };
  }
  var aktion = zelle.aktion;
  if (aktion === "freigaben" || aktion === "modellmenue" || aktion === "routermenue") {
    return { art: aktion };
  }
  if (typeof aktion === "string") {
    var m = aktion.match(/^einstellungen:([a-z]+)(\/([a-z]+))?$/);
    if (m) {
      return { art: "einstellungen", gruppe: m[1], punkt: m[3] || null };
    }
  }
  var ort = zelle.ort;
  if (typeof ort === "string" && ort.length > 0) {
    return { art: "ort", ort: ort };
  }
  return { art: "keine" };
}

  const api = {ZELLEN_RUECKFALL, pruefeAuswahl, zellenAusManifest, aktionZiel};
  root.sedraZellen = api;
  if(typeof module !== 'undefined' && module.exports) module.exports = api;
})();
