var EREIGNIS_OEFFENTLICH = ['system.state', 'model.changed', 'desk.resync', 'tools.refresh', 'slot.changed'];

var EREIGNIS_SCHLUESSEL = {
  'decision.pending': ['id', 'kind', 'way'],
  'decision.answered': ['id', 'kind', 'way'],
  'task.changed': ['id', 'phase'],
  'object.open': ['type', 'id'],
  'agent.changed': ['id'],
  'issue.changed': ['id'],
  'budget.warning': ['agent_id', 'stufe']
};

function einfach(v) {
  return typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean';
}

function filterEreignis(name, payload) {
  if (typeof name !== 'string') return null;
  if (EREIGNIS_OEFFENTLICH.indexOf(name) >= 0) {
    return payload === undefined ? {} : payload;
  }
  if (!Object.prototype.hasOwnProperty.call(EREIGNIS_SCHLUESSEL, name)) return null;
  var erlaubt = EREIGNIS_SCHLUESSEL[name];
  var erg = {};
  if (payload === null || typeof payload !== 'object') return erg;
  for (var i = 0; i < erlaubt.length; i++) {
    var k = erlaubt[i];
    if (Object.prototype.hasOwnProperty.call(payload, k) && einfach(payload[k])) erg[k] = payload[k];
  }
  return erg;
}

function bereinigeHinweis(appName, text, ton) {
  if (typeof text !== 'string' || typeof appName !== 'string') return null;
  var sauber = text.replace(/[\u0000-\u001f\u007f]/g, '').trim();
  if (!sauber) return null;
  return {text: (appName + ': ' + sauber).slice(0, 200), ton: 'note'};
}

function drossel(intervallMs) {
  var letzte = new Map();
  return function (schluessel, jetztMs) {
    var key = String(schluessel);
    if (letzte.has(key) && jetztMs - letzte.get(key) < intervallMs) return false;
    letzte.set(key, jetztMs);
    return true;
  };
}

function pruefeZelle(msg) {
  if (msg === null || typeof msg !== 'object') return null;
  if (typeof msg.wert !== 'string' || !msg.wert) return null;
  var ton = msg.ton === 'ok' || msg.ton === 'warn' || msg.ton === 'off' ? msg.ton : 'off';
  return {wert: msg.wert.slice(0, 24), hinweis: typeof msg.hinweis === 'string' ? msg.hinweis.slice(0, 80) : '', ton: ton};
}
