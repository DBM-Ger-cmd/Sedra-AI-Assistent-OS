// Werkzeug „Issues“ – die reine Logik (Spec 4, D4.2.2): die Spalten des Boards, der Filter und die Zielkette eines Issues.
// Daten rein, Daten raus; node prüft es ohne Browser (spalten.test.js). Die Zustände sind die aus D3.3, in dieser Reihenfolge.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const ZUSTAENDE = [['offen', 'Offen'], ['zugewiesen', 'Zugewiesen'], ['in_arbeit', 'In Arbeit'], ['wartet', 'Wartet'],
                     ['erledigt', 'Erledigt'], ['abgebrochen', 'Abgebrochen']];
  const EINGEKLAPPT = ['erledigt', 'abgebrochen'];
  const SONSTIGE = 'sonstige';
  const leer = v=>v === null || v === undefined || v === '';
  const link = (i, type)=>((i.links || []).find(l=>l && l.type === type) || {}).id;

  // Ein Issue in einer Form, egal ob vom Leser `issue` (Spec 1) oder aus der Fixture (rein)
  function feld(i){
    const kom = i.kommentare;
    return {id: String(i.id), title: String(i.title || i.id), zustand: String(i.zustand || i.state || ''),
            bearbeiter: leer(i.bearbeiter) ? (leer(i.assignee) ? (link(i, 'agent') || null) : String(i.assignee)) : String(i.bearbeiter),
            prioritaet: Number(i.prioritaet) || 0, blocker: Array.isArray(i.blocker) ? i.blocker.map(String) : [],
            kommentare: Array.isArray(kom) ? kom.length : (Number(kom) || 0),
            eltern_id: leer(i.eltern_id) ? (leer(i.parent_id) ? null : String(i.parent_id)) : String(i.eltern_id),
            mission_id: leer(i.mission_id) ? (link(i, 'task') || null) : String(i.mission_id),
            vorhaben_id: leer(i.vorhaben_id) ? (leer(i.goal_ref) ? (link(i, 'intent') || null) : String(i.goal_ref)) : String(i.vorhaben_id),
            projekt_id: leer(i.projekt_id) ? (leer(i.project_id) ? (link(i, 'project') || null) : String(i.project_id)) : String(i.projekt_id),
            geaendert: String(i.geaendert || i.updated_at || '')};
  }

  // Der Filter (rein): Bearbeiter (`''` = alle, `'-'` = niemand), Text in Titel oder ID, „nur offene“ ohne erledigt/abgebrochen
  function passt(i, filter){
    const f = filter || {};
    if(f.bearbeiter === '-' && i.bearbeiter) return false;
    if(f.bearbeiter && f.bearbeiter !== '-' && i.bearbeiter !== f.bearbeiter) return false;
    if(f.nurOffen && EINGEKLAPPT.indexOf(i.zustand) >= 0) return false;
    const t = String(f.text || '').trim().toLowerCase();
    return !t || (i.title + ' ' + i.id).toLowerCase().indexOf(t) >= 0;
  }

  // Priorität absteigend, dann jüngste Änderung zuerst, dann ID – eine feste Reihenfolge für dieselbe Eingabe
  function ordnung(a, b){
    return (b.prioritaet - a.prioritaet) || (b.geaendert < a.geaendert ? -1 : b.geaendert > a.geaendert ? 1 : 0) || a.id.localeCompare(b.id);
  }

  // Die Spalten (rein): alle sechs in fester Reihenfolge, auch leere; ein unbekannter Zustand landet in „Sonstige“ statt zu verschwinden
  function boardColumns(items, options){
    const filter = (options || {}).filter;
    const liste = (items || []).map(feld).filter(i=>passt(i, filter));
    const spalten = ZUSTAENDE.map(([state, label])=>({state, label, count: 0, items: [], eingeklappt: EINGEKLAPPT.indexOf(state) >= 0}));
    const rest = {state: SONSTIGE, label: 'Sonstige', count: 0, items: [], eingeklappt: false};
    liste.forEach(i=>{ (spalten.find(s=>s.state === i.zustand) || rest).items.push(i); });
    if(rest.items.length) spalten.push(rest);
    spalten.forEach(s=>{ s.items.sort(ordnung); s.count = s.items.length; });
    return spalten;
  }

  // Die Liste in derselben Ordnung wie das Board: nach Zustand, dann Priorität und Änderung (rein)
  function listRows(items, options){
    return boardColumns(items, options).reduce((all, s)=>all.concat(s.items), []);
  }

  // Die Zielkette (rein): Vorhaben › Projekt › Elternaufgaben › Issue. `alle` sind die bekannten Issues (für die Eltern); ein
  // Glied, dessen Ziel nicht bekannt ist, trägt `fehlt` (ORC-13). Liefert der Server selbst eine `kette`, gilt seine.
  function chain(issue, alle){
    if(!issue) return [];
    if(Array.isArray(issue.kette)) return issue.kette.map(g=>({type: g.type, id: String(g.id), title: String(g.title || g.id), fehlt: !!g.fehlt}));
    const byId = new Map((alle || []).map(i=>[String(i.id), i]));
    const self = feld(issue);
    const out = [];
    if(self.vorhaben_id) out.push({type: 'intent', id: self.vorhaben_id, title: 'Vorhaben ' + self.vorhaben_id, fehlt: false});
    if(self.projekt_id) out.push({type: 'project', id: self.projekt_id, title: 'Projekt ' + self.projekt_id, fehlt: false});
    const eltern = [], seen = new Set([self.id]);
    let p = self.eltern_id;
    while(p && !seen.has(p)){
      seen.add(p);
      const e = byId.get(p);
      eltern.unshift(e ? {type: 'issue', id: p, title: String(e.title || p), fehlt: false} : {type: 'issue', id: p, title: p, fehlt: true});
      p = e ? feld(e).eltern_id : null;
    }
    return out.concat(eltern, [{type: 'issue', id: self.id, title: self.title, fehlt: false}]);
  }

  const pure = {feld, passt, boardColumns, listRows, chain, ZUSTAENDE, EINGEKLAPPT};
  root.sedraBoardSpalten = pure;
  if(typeof module !== 'undefined' && module.exports) module.exports = pure;
})();
