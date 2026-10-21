// Werkzeug „Issues“ – ein Issue im Einzelnen (Spec 4, D4.2.2): Kopf mit Zustand und Bearbeiter, Zielkette, Blocker,
// Unteraufgaben, Kommentare als Verlauf und der Weg zum Lauf. Zeichnet nur; gelesen und gehandelt wird in tool.js.
// Die Kosten und das Budget des Bearbeiters stehen daneben im Nachweis `costs` (D4.2.8).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const S = ()=>root.sedraBoardSpalten;

  function abschnitt(titel){
    const box = d().el('section', 's-col t-board-part');
    box.append(d().el('h5', 's-head', titel));
    return box;
  }

  // Ein Kommentar als Zeile des Verlaufs; aus der Cloud trägt er das Kennzeichen (CLD-06), lokal nichts
  function kommentar(k){
    const row = d().el('div', 't-board-comment');
    const head = d().el('div', 's-row s-small');
    head.append(d().el('b', null, String(k.autor || k.author || 'unbekannt')), d().el('span', 's-muted', String(k.autor_art || k.rolle || '')),
                d().el('span', 's-muted', d().fmtTime(k.ts)));
    if(k.route === 'cloud') head.append(d().el('span', 't-board-cloud', 'Cloud · ' + (k.provider_id || 'Anbieter') + ' / ' + (k.model || 'Modell')));
    row.append(head, d().el('div', null, String(k.text || '')));
    return row;
  }

  function draw(t){
    const issue = t.issue;
    const box = d().el('div', 's-col t-board-detail');
    if(!issue || issue.missing || issue.state === 'nicht gefunden'){
      box.append(d().empty('Dieses Issue gibt es nicht (mehr).'));
      box.append(d().button('Zur Liste', ()=>t.open({type: 'issue', id: 'alle', title: 'Issues', collection: true})));
      return box;
    }
    const f = S().feld(issue);
    const alle = (t.liste && t.liste.items) || [];
    const verbs = new Map((issue.actions || []).map(v=>[v.verb, v]));

    const head = d().el('div', 's-col');
    const titel = d().el('div', 's-row');
    titel.append(d().el('b', 't-board-title', f.title), d().el('span', 't-board-state ' + f.zustand, t.zustandWort(f.zustand)),
                 d().el('small', 's-muted', f.id));
    head.append(titel);
    const wer = d().el('div', 's-row s-small');
    wer.append(d().el('span', 's-muted', 'Bearbeiter:'), d().el('span', null, t.name(f.bearbeiter)));
    if(verbs.has('zuweisen')) wer.append(d().button(verbs.get('zuweisen').label || 'Zuweisen', ()=>t.verb(issue, verbs.get('zuweisen'))));
    head.append(wer);
    if(issue.summary) head.append(d().el('div', 's-muted', String(issue.summary)));
    box.append(head);
    if(t.form && t.form.issue && t.form.verb.verb !== 'kommentieren') box.append(t.drawForm(t.form));

    const kette = abschnitt('Zielkette');
    const glieder = d().el('div', 's-row t-board-chain');
    S().chain(issue, alle).forEach((g, n)=>{
      if(n) glieder.append(d().el('span', 's-muted', '›'));
      if(g.fehlt){ glieder.append(d().el('span', 't-board-missing', g.title + ' (nicht gefunden)')); return; }
      const link = d().el('span', 't-board-link', g.title);
      if(g.id !== f.id) d().clickable(link, ()=>t.open({type: g.type, id: g.id, title: g.title}));
      glieder.append(link);
    });
    kette.append(glieder);
    box.append(kette);

    const blocker = abschnitt('Blocker');
    if(!f.blocker.length) blocker.append(d().el('small', 's-muted', 'Nichts blockiert dieses Issue.'));
    f.blocker.forEach(id=>{
      const other = alle.find(i=>String(i.id) === id);
      const row = d().el('div', 't-board-link', '⛔ ' + (other ? other.title + ' (' + id + ')' : id + ' (nicht gefunden)'));
      if(other) d().clickable(row, ()=>t.open({type: 'issue', id, title: other.title}));
      blocker.append(row);
    });
    if(verbs.has('blocker_setzen')) blocker.append(d().button(verbs.get('blocker_setzen').label || 'Blocker setzen', ()=>t.verb(issue, verbs.get('blocker_setzen'))));
    box.append(blocker);

    const kinder = alle.map(i=>S().feld(i)).filter(i=>i.eltern_id === f.id);
    if(kinder.length){
      const sub = abschnitt('Unteraufgaben');
      kinder.forEach(i=>{
        const row = d().el('div', 's-row t-board-link');
        row.append(d().el('span', null, i.title), d().el('small', 't-board-state ' + i.zustand, t.zustandWort(i.zustand)), d().el('small', 's-muted', t.name(i.bearbeiter)));
        d().clickable(row, ()=>t.open({type: 'issue', id: i.id, title: i.title}));
        sub.append(row);
      });
      box.append(sub);
    }

    const verlauf = abschnitt('Kommentare');
    if(Array.isArray(issue.kommentare)){
      if(!issue.kommentare.length) verlauf.append(d().el('small', 's-muted', 'Noch keine Kommentare.'));
      issue.kommentare.forEach(k=>verlauf.append(kommentar(k)));
    }else verlauf.append(d().el('small', 's-muted', f.kommentare ? f.kommentare + ' Kommentar' + (f.kommentare === 1 ? '' : 'e') + ' – den Wortlaut liefert der Desk noch nicht.' : 'Noch keine Kommentare.'));
    if(verbs.has('kommentieren')){
      if(!t.kform || t.kform.issue.id !== issue.id) t.kform = {verb: verbs.get('kommentieren'), issue};
      t.kform.verb = verbs.get('kommentieren'); t.kform.issue = issue;
      verlauf.append(t.drawForm(t.kform));
    }
    box.append(verlauf);

    if(f.mission_id){
      const lauf = d().el('div', 's-row');
      lauf.append(d().button('Lauf ansehen', ()=>t.open({type: 'task', id: f.mission_id, title: 'Lauf ' + f.mission_id})),
                  d().el('small', 's-muted', 'Zeilen und Kosten des Laufs zeigt die Mission.'));
      box.append(lauf);
    }
    return box;
  }

  root.sedraBoardDetail = {draw, kommentar};
})();
