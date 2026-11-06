// Werkzeug „Agentenfenster“ – die reine Logik des Verlaufs (Spec 4, D4.2.5): Nachrichten zusammenführen, der Satz zum Status
// einer Nachricht und die Tagestrenner. Daten rein, Daten raus; node prüft es ohne Browser (verlauf.test.js).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;

  // Nach ID ordnen: Zahlen als Zahlen, sonst als Text – die neueste steht zuletzt
  function vergleich(a, b){
    const x = Number(a.id), y = Number(b.id);
    if(!isNaN(x) && !isNaN(y)) return x - y;
    return String(a.id).localeCompare(String(b.id));
  }

  // Alte und neue Nachrichten zu einer Liste (rein): je ID eine, die neuere Fassung gewinnt (ihr Status kann sich geändert haben)
  function mergeMessages(alt, neu){
    const byId = new Map();
    (alt || []).concat(neu || []).forEach(m=>{ if(m && m.id !== undefined && m.id !== null) byId.set(String(m.id), m); });
    return Array.from(byId.values()).sort(vergleich);
  }

  // Der Satz unter einer Nachricht (rein). Der Agent antwortet nicht sofort: sein Lauf braucht eine Freigabe (OP-4).
  function statusText(n){
    const m = n || {};
    const s = m.status || m.state;
    if(s === 'angenommen') return 'angekommen' + (m.issue_id ? ' – Issue ' + m.issue_id + ' angelegt' : '');
    if(s === 'wartet_freigabe') return 'wartet auf Freigabe im Posteingang';
    if(s === 'laeuft') return m.mission_id ? 'Lauf ' + m.mission_id + ' läuft' : 'Lauf läuft';
    if(s === 'beantwortet') return '';
    if(s === 'fehler') return 'Fehler' + (m.grund ? ': ' + m.grund : '');
    return s ? String(s) : '';
  }

  // Der Tag einer Nachricht in UTC (rein), damit derselbe Verlauf überall gleich getrennt wird
  function tagVon(ts){
    if(!ts) return '';
    const t = new Date(ts);
    return isNaN(t.getTime()) ? '' : t.toISOString().slice(0, 10);
  }

  // Tagestrenner (rein): [{tag, label, items}] in der Reihenfolge der Nachrichten; ohne Zeit unter „ohne Datum“
  function byDay(nachrichten){
    const out = [];
    (nachrichten || []).forEach(m=>{
      const tag = tagVon(m.ts);
      let last = out[out.length - 1];
      if(!last || last.tag !== tag){
        last = {tag, label: tag ? tag.slice(8, 10) + '.' + tag.slice(5, 7) + '.' + tag.slice(0, 4) : 'ohne Datum', items: []};
        out.push(last);
      }
      last.items.push(m);
    });
    return out;
  }

  // Das Kennzeichen einer Antwort aus der Cloud (rein, CLD-06); lokale Antworten bleiben ohne
  function cloudText(m){
    if(!m || m.route !== 'cloud') return null;
    return 'Cloud · ' + (m.provider_id || 'Anbieter') + ' / ' + (m.model || 'Modell');
  }

  const pure = {mergeMessages, statusText, byDay, cloudText};
  root.sedraAgentfensterVerlauf = pure;
  if(typeof module !== 'undefined' && module.exports) module.exports = pure;
})();
