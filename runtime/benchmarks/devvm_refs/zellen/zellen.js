var ZELLEN_RUECKFALL = [
  {id: 'gauge-decisions', feld: 'decisions', label: 'Freigaben', ort: null, aktion: 'freigaben', quelle: null},
  {id: 'gauge-model', feld: 'model', label: 'Modell', ort: 'models', aktion: 'modellmenue', quelle: null},
  {id: 'gauge-temp', feld: 'temp', label: 'Temp', ort: 'hardware', aktion: null, quelle: 'gpu'},
  {id: 'gauge-vram', feld: 'vram', label: 'VRAM belegt', ort: 'hardware', aktion: null, quelle: 'gpu'},
  {id: 'gauge-ram', feld: 'ram', label: 'RAM frei', ort: 'hardware', aktion: null, quelle: null},
  {id: 'gauge-server', feld: 'server', label: 'Modellserver', ort: 'models', aktion: 'modellmenue', quelle: null},
  {id: 'gauge-scheduler', feld: 'scheduler', label: 'Scheduler', ort: 'slots', aktion: null, quelle: null},
  {id: 'gauge-state', feld: 'state', label: 'Zustand', ort: 'machine', aktion: 'einstellungen:system', quelle: null}
];

var LEISTE_ID = /^[a-z0-9-]{2,40}$/;
var LEISTE_MAX = 30;

function pruefeAuswahl(roh) {
  var o = roh;
  if (typeof roh === 'string') {
    try {
      o = JSON.parse(roh);
    } catch (e) {
      throw new Error('Leiste: Datei ist kein gueltiges JSON');
    }
  }
  if (o === null || typeof o !== 'object' || Array.isArray(o)) throw new Error('Leiste: Inhalt ist kein Objekt');
  var z = o.zellen;
  if (!Array.isArray(z)) throw new Error('Leiste: zellen fehlt oder ist keine Liste');
  if (z.length === 0) throw new Error('Leiste: zellen ist leer');
  if (z.length > LEISTE_MAX) throw new Error('Leiste: hoechstens 30 Zellen');
  var gesehen = [];
  for (var i = 0; i < z.length; i++) {
    var x = z[i];
    if (typeof x !== 'string' || !LEISTE_ID.test(x)) throw new Error('Leiste: ungueltige Kennung ' + String(x));
    if (gesehen.indexOf(x) >= 0) throw new Error('Leiste: Kennung doppelt: ' + x);
    gesehen.push(x);
  }
  return {zellen: z.slice()};
}

function text(v) {
  return typeof v === 'string' && v ? v : null;
}

function zellenAusManifest(instrumente, auswahl) {
  var erg = {zellen: [], fehlend: [], ohneZelle: []};
  var liste = Array.isArray(instrumente) ? instrumente : [];
  var ids = auswahl && Array.isArray(auswahl.zellen) ? auswahl.zellen : [];
  var gesehen = [];
  for (var i = 0; i < ids.length; i++) {
    var id = ids[i];
    if (typeof id !== 'string' || gesehen.indexOf(id) >= 0) continue;
    gesehen.push(id);
    var m = null;
    for (var j = 0; j < liste.length; j++) {
      var t = liste[j];
      if (t && typeof t === 'object' && t.id === id && t.kind === 'instrument' && t.trust === 'CORE') {
        m = t;
        break;
      }
    }
    if (!m) {
      erg.fehlend.push(id);
      continue;
    }
    var z = m.zelle;
    if (!z || typeof z !== 'object' || Array.isArray(z) || !text(z.feld) || !text(z.label)) {
      erg.ohneZelle.push(id);
      continue;
    }
    erg.zellen.push({id: id, feld: z.feld, label: z.label, ort: text(z.ort), aktion: text(z.aktion), quelle: text(z.quelle)});
  }
  return erg;
}

function aktionZiel(zelle) {
  if (!zelle || typeof zelle !== 'object') return {art: 'keine'};
  var a = zelle.aktion;
  if (a === 'freigaben' || a === 'modellmenue' || a === 'routermenue') return {art: a};
  if (typeof a === 'string') {
    var m = /^einstellungen:([a-z]+)(?:\/([a-z]+))?$/.exec(a);
    if (m) return {art: 'einstellungen', gruppe: m[1], punkt: m[2] || null};
  }
  if (typeof zelle.ort === 'string' && zelle.ort) return {art: 'ort', ort: zelle.ort};
  return {art: 'keine'};
}
