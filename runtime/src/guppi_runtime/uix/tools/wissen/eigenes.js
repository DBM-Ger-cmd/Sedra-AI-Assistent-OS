// Werkzeug „Wissen“ – die Ansicht Eigenes (SPEC_SHELL_WISSEN_v1 §4.4, W-E3): der Captain schreibt sein eigenes Wissen als Notiz.
// Eine Notiz wird eine Markdown-Datei unter local_config/wissen/notizen/ (mit oder ohne Personenbezug); die Quelle „Notizen des
// Captains“ wird einmal freigegeben, danach ist jede Notiz ohne Gate sofort per Volltext findbar. Ändern und Löschen hier.
// Der Entwurf (Titel, Text) liegt in der Ablage des Servers – ein Shell-Wechsel mittendrin verliert nichts, im Browser liegt nichts.
// Vor tool.js geladen; registriert sich unter sedraWissenAnsichten.eigenes.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const leer = ()=>({titel: '', text: '', personenbezug: true, datei: null});

  async function speichern(t, f){
    const e = t.s.entwurf;
    e.titel = f.titel.value; e.text = f.text.value; e.personenbezug = !!f.pb.checked;
    if(!e.titel.trim() || !e.text.trim()){ t.hinweis = {text: 'Titel und Text der Notiz fehlen.', bad: true}; return t.draw(); }
    const out = e.datei ? await t.verb('notiz_aendern', {datei: e.datei, titel: e.titel, text: e.text})
                        : await t.verb('notiz_anlegen', {titel: e.titel, text: e.text, personenbezug: e.personenbezug});
    t.sage(out);
    if(out && out.status !== 'fehler'){ t.s.entwurf = leer(); t.d.notizen = null; await t.refresh(false); }
    else t.draw();
  }

  function formular(t){
    const e = t.s.entwurf || (t.s.entwurf = leer());
    const form = d().el('form', 's-card s-col t-wissen-form t-wissen-notiz-form');
    form.append(d().el('b', null, e.datei ? 'Notiz ändern' : 'Neue Notiz'));
    const titel = d().el('input', e.titel ? '' : 't-wissen-fokus'); titel.value = e.titel; titel.placeholder = 'Titel – wie man es wiederfindet'; titel.setAttribute('aria-label', 'Titel der Notiz');
    const text = d().el('textarea', 't-wissen-notiz-text'); text.value = e.text; text.rows = 6; text.placeholder = 'Was SEDRA wissen soll – Markdown ist erlaubt'; text.setAttribute('aria-label', 'Text der Notiz');
    const pb = d().el('input'); pb.type = 'checkbox'; pb.checked = e.personenbezug !== false; pb.disabled = !!e.datei;
    const pbRow = d().el('label', 's-row s-small');
    pbRow.append(pb, d().el('span', null, 'Personenbezug (Namen, Kunden, Adressen) – bleibt lokal, geht nie in eine Cloud' + (e.datei ? ' · beim Ändern fest' : '')));
    // der Entwurf geht bei jeder Eingabe in den Zustand: merken() schreibt ihn in die Ablage (nie in die Sitzung)
    const halten = ()=>{ e.titel = titel.value; e.text = text.value; e.personenbezug = !!pb.checked; t.merken(); };
    titel.oninput = halten; text.oninput = halten; pb.onchange = halten;
    const f = {titel, text, pb};
    form.onsubmit = ev=>{ ev.preventDefault(); return speichern(t, f); };
    text.onkeydown = ev=>{ if(ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)){ ev.preventDefault(); speichern(t, f); } };
    const row = d().el('div', 's-row');
    if(e.datei || e.titel || e.text) row.append(d().button('Verwerfen', ()=>{ t.s.entwurf = leer(); return t.draw(); }));
    row.append(d().button(e.datei ? 'Änderung speichern' : 'Speichern', ()=>speichern(t, f), 'p', {absenden: true}));
    row.append(d().el('small', 's-muted', 'Strg+Enter speichert'));
    form.append(titel, text, pbRow, row);
    return form;
  }

  function liste(t){
    const box = d().el('div', 's-col t-wissen-notizen');
    const alle = (t.d.notizen || {}).notizen || [];
    if(!alle.length){ box.append(d().empty('Noch keine Notizen. Was du hier schreibst, findet die Suche – und das Gespräch nennt es mit Fundstelle.')); return box; }
    alle.forEach(n=>{
      const card = d().el('div', 's-card s-col t-wissen-notiz'); card.dataset.datei = n.datei;
      const kopf = d().el('div', 's-row t-wissen-quelle-kopf');
      const links = d().el('div', 's-col t-wissen-quelle-name');
      links.append(d().el('b', null, n.titel || n.datei));
      const marken = d().el('div', 's-row');
      marken.append(d().el('span', 't-wissen-marke', 'Stand ' + d().fmtTime(n.stand)));
      if(n.personenbezug) marken.append(d().el('span', 't-wissen-marke warn', 'Personenbezug'));
      links.append(marken);
      kopf.append(links);
      card.append(kopf, d().el('pre', 't-wissen-text t-wissen-kurz', n.text));
      const row = d().el('div', 's-row');
      row.append(d().button('Ändern', ()=>{ t.s.entwurf = {titel: n.titel, text: n.text, personenbezug: n.personenbezug, datei: n.datei}; return t.draw(); }));
      // Löschen in zwei Schritten: erst fragen, dann tun (kein confirm())
      if(t.s.loeschen === n.datei){
        row.append(d().el('small', 's-note warn', 'Wirklich löschen?'), d().button('Ja, löschen', async()=>{
          t.s.loeschen = null; t.sage(await t.verb('notiz_loeschen', {datei: n.datei})); t.d.notizen = null; await t.refresh(false);
        }, 'p'), d().button('Nein', ()=>{ t.s.loeschen = null; return t.draw(); }));
      }else row.append(d().button('Löschen', ()=>{ t.s.loeschen = n.datei; return t.draw(); }));
      card.append(row);
      box.append(card);
    });
    return box;
  }

  const ansicht = {
    async laden(t){
      if(t.d.notizen) return;
      const out = await t.verb('notizen');
      t.d.notizen = out && out.status !== 'fehler' ? out : {notizen: [], freigegeben: false, antrag: null};
      if(out && out.status === 'fehler') t.hinweis = {text: 'Notizen nicht lesbar: ' + root.sedraWissenPure.ergebnisSatz(out), bad: true};
    },
    zeichnen(t){
      const box = d().el('div', 's-col');
      const n = t.d.notizen || {};
      if(!n.freigegeben){
        const hin = d().el('div', 's-note' + (n.antrag ? ' warn' : ''), n.antrag
          ? '„Notizen des Captains“ wartet auf deine Freigabe im Posteingang – einmal, danach ist jede Notiz sofort findbar.'
          : 'Beim ersten Speichern wird „Notizen des Captains“ einmal als Quelle beantragt (Stufe 3); danach schreibst du ohne Freigabe.');
        if(n.antrag) hin.append(' ', d().button('Im Posteingang entscheiden', ()=>t.ctx.shell.open({type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true})));
        box.append(hin);
      }
      box.append(formular(t), liste(t));
      box.append(d().el('small', 's-muted', 'Eigene Einträge im KI GateWay bleiben dort (Regelbuch, eigene Einträge) und sind als Quelle „GateWay“ beantragbar.'));
      return box;
    },
    aktionen(t){
      return [{label: 'Neue Notiz', run: ()=>{ t.s.entwurf = {titel: '', text: '', personenbezug: true, datei: null}; t.s.ansicht = 'eigenes'; return t.draw(); }}];
    }
  };

  root.sedraWissenAnsichten = Object.assign(root.sedraWissenAnsichten || {}, {eigenes: ansicht});
})();
