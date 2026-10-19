// Werkzeug „KI GateWay“ (Build 19, SPEC_GATEWAY_VORGANG_v1) – der Vorgang nach dem Studio Flow v1.1 in vier Stationen.
// Alles Fachliche (Scan, Merkmale, Klasse, Matrix, Platzhalter, Rechecks) tut der Server; hier wird gezeigt und gefragt.
// Die Freigabe ist ein Gate: der Klick hier ist derselbe Weg wie in den Entscheidungen (ctx.shell.decide) – eine Tür.
// Kein eigenes fetch, kein Speicher, nur ctx.api; Stil nur unter .t-gateway, Farben nur Token.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const PH = /<(PERSON|COMPANY|EMAIL|PHONE|CUSTOMER_ID|ADDRESS|ROLE|TERM)_(\d{3})>/g;
  const TYP = {PERSON: 'Person', COMPANY: 'Organisation', EMAIL: 'E-Mail', PHONE: 'Telefon', CUSTOMER_ID: 'Kunden-ID', ADDRESS: 'Adresse', ROLE: 'Rolle', TERM: 'Begriff'};
  const WEG = {LOCAL_ONLY: 'Lokal freigeben', CLOUD_AFTER_PSEUDONYMIZATION: 'Cloud freigeben (mit Platzhaltern)', CLOUD_ALLOWED: 'Cloud freigeben'};

  // rein: Text mit Platzhaltern -> Teile [{text}|{token, typ}] (node prüft das)
  function tokenize(text){
    const out = []; let last = 0; let m;
    PH.lastIndex = 0;
    while((m = PH.exec(text || ''))){
      if(m.index > last) out.push({text: text.slice(last, m.index)});
      out.push({token: m[0], typ: m[1]}); last = m.index + m[0].length;
    }
    if(last < (text || '').length) out.push({text: text.slice(last)});
    return out;
  }
  // rein: Original mit Markierungen [[a,b,typ]] -> Teile
  function markup(text, spans){
    const out = []; let pos = 0;
    (spans || []).slice().sort((x, y)=>x[0] - y[0]).forEach(([a, b, t])=>{
      if(a < pos || b > (text || '').length) return;
      if(a > pos) out.push({text: text.slice(pos, a)});
      out.push({token: text.slice(a, b), typ: t, original: true}); pos = b;
    });
    if(pos < (text || '').length) out.push({text: text.slice(pos)});
    return out;
  }

  const tool = {
    id: 'gateway',

    async mount(el, ctx){
      this.ctx = ctx; this.el = el; this.state = null; this.offs = [];
      el.classList.add('t-gateway');
      this.offs.push(ctx.bus.on('tools.refresh', ()=>this.refresh()));
      this.offs.push(ctx.bus.on('decision.answered', ()=>this.refresh()));
      await this.refresh();
    },
    unmount(){ (this.offs || []).forEach(off=>off()); this.el.replaceChildren(); },

    actions(){
      const o = this.ctx.object || {};
      if(o.collection || o.id === 'alle') return [{label: 'Neuer Vorgang', run: ()=>this.neu()}];
      const v = this.state && this.state.vorgang;
      if(!v) return [];
      const out = [];
      if(v.zustand === 'ENTWURF') out.push({label: 'Geprüft', run: ()=>this.urteil('geprueft')}, {label: 'Verwerfen', run: ()=>this.urteil('verworfen')});
      if(['GEPRUEFT', 'GESPERRT', 'FEHLER', 'NEU'].includes(v.zustand)) out.push({label: 'Vorgang verwerfen', run: ()=>this.verwerfen()});
      return out;
    },

    async refresh(){
      const o = this.ctx.object || {type: 'gateway', id: 'alle', collection: true};
      try{
        const list = await this.ctx.api('/api/gateway/vorgaenge');
        if(o.collection || o.id === 'alle'){ this.state = {list}; this.renderList(list); return; }
        const vorgang = await this.ctx.api('/api/gateway/vorgang', {method: 'POST', body: {id: o.id}});
        this.state = {list, vorgang}; this.render(vorgang, list);
      }catch(err){
        this.el.replaceChildren(d().el('div', 's-note bad', 'Das KI GateWay antwortet nicht: ' + err.message));
      }
    },

    // ---------------------------------------------------------------- die Liste
    cloudWort(list){
      const c = (list || {}).cloud || {};
      if(c.modus !== 'anbieter') return 'Simulation';
      return c.bereit && c.bereit.length ? 'Anbieter ' + c.bereit.join(', ') : 'Anbieter ohne Schlüssel';
    },

    renderList(list){
      const box = d().el('div', 't-gateway-list');
      const head = d().el('div', 't-gateway-head');
      head.append(d().el('h3', null, 'KI GateWay'), d().el('small', 's-muted', 'Kundenanfrage → Datenschutz prüfen → Freigabe → Entwurf → deine Prüfung. Kein Versand.'));
      box.append(head, root.sedraGatewayArbeit.reiter(this, list));
      // Der Menüpunkt Regeln und die Dateien haben ihre eigene Ansicht; die Vorgänge bleiben wie sie sind
      if(this.ansicht === 'regeln'){ box.append(root.sedraGatewayRegeln.draw(list)); this.el.replaceChildren(box); root.sedraGatewayArbeit.vorgabenListe(this, box); return; }
      if(this.ansicht === 'dateien'){ box.append(root.sedraGatewayArbeit.dateien(this, list)); this.el.replaceChildren(box); return; }
      const form = d().el('div', 't-gateway-new');
      const titel = d().el('input'); titel.placeholder = 'Titel des Vorgangs, z. B. Projektabstimmung vorbereiten'; titel.setAttribute('aria-label', 'Titel');
      const wunsch = d().el('select'); wunsch.setAttribute('aria-label', 'Wunsch');
      [['local', 'Lokale KI' + (list.modell ? ' · ' + list.modell : ' · kein Modell geladen')], ['cloud', 'Cloud-KI · ' + this.cloudWort(list)]].forEach(([v, t])=>{ const op = d().el('option', null, t); op.value = v; wunsch.append(op); });
      form.append(titel, wunsch, d().button('Neuer Vorgang', async()=>{ await this.neu(titel.value, wunsch.value); titel.value = ''; }, 'p'));
      box.append(form);
      const rows = d().el('div', 't-gateway-rows');
      if(!list.vorgaenge.length) rows.append(d().empty('Noch kein Vorgang. Leg einen an – die Anfrage bleibt auf diesem Rechner.'));
      list.vorgaenge.forEach(v=>{
        const row = d().el('div', 't-gateway-row');
        row.append(d().el('b', null, v.titel), d().el('span', 't-gateway-pill ' + this.tone(v), v.zustand_wort || v.zustand),
                   d().el('small', 's-muted', [v.id, v.klasse, v.weg ? WEG[v.weg] : ''].filter(Boolean).join(' · ')));
        d().clickable(row, ()=>this.ctx.shell.open({type: 'gateway', id: v.id, title: v.titel}));
        rows.append(row);
      });
      box.append(rows, this.leitfaden(list, null), this.fragSedra(null), this.mvpNote(list));
      this.el.replaceChildren(box);
    },

    // B6-G-03: der Leitfaden – so arbeitet ein Mensch mit dem GateWay, vom Anlegen bis zum Ablegen. Teil des Moduls, aus der Wissensbasis.
    leitfaden(list, v){
      const det = d().el('details', 't-gateway-leitfaden'); if(v) det.open = false;
      const aktuell = v ? (list.schritt_von_zustand || {})[v.zustand] : null;
      det.append(d().el('summary', null, 'Leitfaden – so arbeitest du mit dem GateWay' + (aktuell ? ' · du bist bei Schritt ' + aktuell : '')));
      const ol = d().el('ol');
      (list.leitfaden || []).forEach(st=>{
        const li = d().el('li', st.nr === aktuell ? 'on' : '');
        li.append(d().el('b', null, 'Schritt ' + st.nr + ' (' + st.station + '): ' + st.titel), d().el('div', null, st.mensch));
        const more = d().el('details'); more.append(d().el('summary', null, 'Warten · Prüfen · Ablage · SEDRA'));
        [['Warten', st.warten], ['Prüfen', st.pruefen], ['Ablage', st.ablegen], ['SEDRA hilft', st.sedra]].forEach(([k, t])=>{ const r = d().el('div', 's-muted'); r.append(d().el('b', null, k + ': '), t); more.append(r); });
        li.append(more); ol.append(li);
      });
      det.append(ol);
      return det;
    },

    // B6-G-03: „Frag SEDRA“ – die Wissensbasis antwortet ohne Modell; Knöpfe öffnen, nichts läuft von allein.
    fragSedra(v){
      const box = d().el('div', 't-gateway-frag');
      const inp = d().el('input'); inp.placeholder = 'Frag SEDRA: Was muss ich als Nächstes machen? Wo ist der Fehler in diesem Text: …'; inp.setAttribute('aria-label', 'Frage an SEDRA');
      const out = d().el('div', 't-gateway-frag-out');
      const ask = async()=>{
        const frage = inp.value.trim(); if(!frage) return;
        try{
          const a = await this.ctx.api('/api/gateway/frage', {method: 'POST', body: {frage, vorgang: v ? v.id : ''}});
          out.replaceChildren();
          const note = d().el('div', 's-note'); note.textContent = a.reply; out.append(note);
          const row = d().el('div', 's-row');
          (a.ui_actions || []).forEach(x=>{ if(x.kind === 'open' && x.object) row.append(d().button(x.title || 'Öffnen', ()=>this.ctx.shell.open(x.object))); });
          row.append(d().button('Merken', async()=>{ await this.ctx.api('/api/gateway/wissen', {method: 'POST', body: {frage, antwort: a.reply}}); this.ctx.shell.notify('Gemerkt – steht beim nächsten Mal in der Wissensbasis.', 'note'); }));
          row.append(d().el('small', 's-muted', a.quelle || ''));
          out.append(row);
        }catch(err){ out.replaceChildren(d().el('div', 's-note bad', 'Keine Antwort: ' + err.message)); }
      };
      inp.addEventListener('keydown', e=>{ if(e.key === 'Enter') ask(); });
      box.append(d().el('div', 't-gateway-colhead', 'Frag SEDRA'), inp, d().button('Fragen', ask), out);
      return box;
    },

    tone(v){ return v.zustand === 'GESPERRT' || v.zustand === 'FEHLER' ? 'bad' : v.zustand === 'ENTWURF' || v.zustand === 'WARTET' ? 'warn' : v.zustand === 'ABGESCHLOSSEN' ? 'ok' : ''; },

    mvpNote(list){
      const n = d().el('details', 't-gateway-mvp');
      n.append(d().el('summary', null, 'Was dieses MVP nicht tut'));
      const ul = d().el('ul'); (list.nicht_im_mvp || []).forEach(t=>ul.append(d().el('li', null, t))); n.append(ul);
      return n;
    },

    async neu(titel, wunsch){
      const out = await this.ctx.api('/api/gateway/neu', {method: 'POST', body: {titel: titel || 'Vorgang', wunsch: wunsch || 'local'}});
      // Der neue Vorgang erscheint in derselben Ansicht, nicht in einem zweiten Reiter: ein Werkzeug hat nur einen Zustand
      // (this.ctx, this.el), zwei Reiter desselben Werkzeugs würden sich gegenseitig überschreiben.
      this.ctx.object = {type: 'gateway', id: out.id, title: out.titel};
      await this.refresh();
    },

    // ---------------------------------------------------------------- der Vorgang: vier Stationen
    render(v, list){
      const box = d().el('div', 't-gateway-flow');
      const head = d().el('div', 't-gateway-head');
      head.append(d().el('h3', null, v.titel), d().el('span', 't-gateway-pill ' + this.tone(v), v.zustand_wort),
                  d().el('small', 's-muted', v.id + ' · ' + (v.erstellt || '').replace('T', ' ').slice(0, 16)));
      box.append(head);
      this.list = list;
      box.append(this.station01(v, list), this.station02(v, list), this.station03(v), this.station04(v));
      box.append(this.leitfaden(list, v), this.fragSedra(v));
      if(v.verlauf && v.verlauf.length){
        const vl = d().el('details', 't-gateway-verlauf'); vl.append(d().el('summary', null, 'Verlauf'));
        v.verlauf.slice().reverse().forEach(x=>vl.append(d().el('div', 's-muted', (x.at || '').slice(11, 16) + ' · ' + x.text)));
        box.append(vl);
      }
      box.append(this.mvpNote(list));
      this.el.replaceChildren(box);
    },

    step(nr, title, badge, schritt){
      const h = d().el('div', 't-gateway-step');
      h.append(d().el('small', 's-head', nr), d().el('h4', null, title));
      if(badge) h.append(d().el('span', 't-gateway-pill ' + (badge[1] || ''), badge[0]));
      const st = schritt && ((this.list || {}).leitfaden || []).find(x=>x.nr === schritt);
      if(st) h.append(d().el('small', 't-gateway-lf', 'Leitfaden Schritt ' + st.nr + ': ' + st.titel));
      return h;
    },

    station01(v, list){
      const sec = d().el('section', 't-gateway-sec');
      sec.append(this.step('01 / KI & Modell', 'Wie möchtest du arbeiten?', ['Local First', 'ok'], 2));
      const grid = d().el('div', 't-gateway-models');
      const locked = v.zustand === 'WARTET' || v.zustand === 'ENTWURF';
      [['local', 'Lokale KI', list.modell ? 'Verarbeitung auf diesem Rechner · ' + list.modell : 'Kein Modell geladen – in der Werkstatt laden'],
       ['cloud', 'Cloud-KI', 'Nur über einen von der Policy erlaubten Weg · ' + this.cloudWort(list)]].forEach(([id, name, hint])=>{
        const card = d().el('div', 't-gateway-model' + (v.wunsch === id ? ' on' : ''));
        card.append(d().el('span', 't-gateway-radio'), d().el('b', null, name), d().el('small', 's-muted', hint));
        if(!locked) d().clickable(card, ()=>{ v.wunsch = id; this.render(v, list); });
        grid.append(card);
      });
      sec.append(grid, d().el('small', 's-muted', 'Deine Auswahl ist ein Wunsch. Die Policy bestimmt den erlaubten Weg – restriktiver geht immer, offener nie.'));
      return sec;
    },

    station02(v, list){
      const sec = d().el('section', 't-gateway-sec');
      sec.append(this.step('02 / Eingabe & Übergabe', 'Ein Prompt. Zwei Perspektiven.', null, 3));
      const pair = d().el('div', 't-gateway-pair');
      // links: Eingabe
      const left = d().el('div', 't-gateway-col');
      left.append(d().el('div', 't-gateway-colhead', 'Eingabeprompt'), d().el('small', 's-muted', 'Geschützter lokaler Bereich'));
      const locked = v.zustand === 'WARTET' || v.zustand === 'ENTWURF';
      if(v.zustand === 'GESPERRT'){
        left.append(d().el('div', 's-note bad', 'Gesperrt – der Text wurde nicht gespeichert. ' + ((v.einstufung || {}).gruende || []).join(' ')));
      }else if(v.uebergabe && v.anfrage && locked){
        left.append(this.pre(markup(v.anfrage, v.uebergabe.spans), 'original'));
      }else{
        const ta = d().el('textarea', 't-gateway-text'); ta.rows = 8; ta.value = v.anfrage || ''; ta.setAttribute('aria-label', 'Eingabeprompt');
        ta.placeholder = 'Die Kundenanfrage und was der Entwurf leisten soll – z. B. „Bereite eine kurze Übersicht für die nächste Projektabstimmung vor …“';
        this.ta = ta; left.append(ta);
        if(v.uebergabe && v.anfrage){ const det = d().el('details'); det.append(d().el('summary', null, 'Markierungen im Original'), this.pre(markup(v.anfrage, v.uebergabe.spans), 'original')); left.append(det); }
      }
      const attach = d().el('div', 't-gateway-attach');
      const sel = d().el('select'); sel.setAttribute('aria-label', 'Dokument');
      const none = d().el('option', null, 'Kein Dokument'); none.value = ''; sel.append(none);
      (list.dateien || []).forEach(f=>{ const op = d().el('option', null, f.pfad + ' (' + d().fmtBytes(f.bytes) + ')'); op.value = f.pfad; if((v.dokument || {}).name === f.pfad) op.selected = true; sel.append(op); });
      sel.disabled = locked; this.sel = sel;
      // Datei manuell einfügen: sie kommt in den Eingang des GateWay (ohne Projekt) und ist danach im Auswahlfeld
      const up = d().el('input'); up.type = 'file'; up.accept = '.md,.txt,.docx'; up.disabled = locked; up.setAttribute('aria-label', 'Datei hochladen');
      up.onchange = ()=>{ const f = up.files && up.files[0]; if(!f) return; const r = new FileReader();
        r.onload = async()=>{ try{ await this.ctx.api('/api/gateway/upload', {method: 'POST', body: {name: f.name, data: String(r.result).split(',')[1]}}); await this.refresh(); }
          catch(err){ alert('Hochladen fehlgeschlagen: ' + err.message); } }; r.readAsDataURL(f); };
      attach.append(sel, up, d().el('small', 's-muted', 'Nur .md, .txt und .docx · Datei hochladen oder aus dem Projekt'));
      left.append(attach);
      // G-05 (Ticket B6-G-01): Zweck und verantwortliche Person – beide gehen in die Bindung der Freigabe.
      const bind = d().el('div', 't-gateway-attach t-gateway-bind');
      const zweck = d().el('select'); zweck.setAttribute('aria-label', 'Zweck');
      (list.zwecke || []).forEach(z=>{ const op = d().el('option', null, 'Zweck: ' + z.name); op.value = z.id; if(v.zweck === z.id) op.selected = true; zweck.append(op); });
      zweck.disabled = locked; this.zweck = zweck;
      const wer = d().el('input'); wer.type = 'text'; wer.maxLength = 80; wer.value = v.verantwortlich || ''; wer.placeholder = 'Verantwortliche Person';
      wer.setAttribute('aria-label', 'Verantwortliche Person'); wer.disabled = locked; this.wer = wer;
      bind.append(zweck, wer, d().el('small', 's-muted', 'Zweck und Person sind Teil der Freigabe – ändert sich eines, gilt die Freigabe nicht mehr'));
      left.append(bind);
      const manuell = d().el('label', 't-gateway-check');
      const cb = d().el('input'); cb.type = 'checkbox'; cb.checked = (v.manuell || []).includes('R01'); cb.disabled = locked; this.r01 = cb;
      manuell.append(cb, d().el('span', null, 'R01 – Rechtsstreit / laufendes Verfahren (von Hand, kein Scanner erkennt das)'));
      left.append(manuell);
      const hoch = d().el('label', 't-gateway-check');
      const cbA = d().el('input'); cbA.type = 'checkbox'; cbA.checked = (v.manuell || []).includes('A01'); cbA.disabled = locked; this.a01 = cbA;
      hoch.append(cbA, d().el('span', null, 'A01 – Hochrisiko-Kontext nach EU AI Act (Personal, Kredit, Bildung, Strafverfolgung; von Hand) – R-13'));
      left.append(hoch);
      if(!locked && v.zustand !== 'GESPERRT' || v.zustand === 'GESPERRT'){
        const act = d().el('div', 's-row');
        if(v.zustand === 'GESPERRT'){
          act.append(d().button('Neu beginnen', ()=>{ v.zustand = 'NEU'; v.anfrage = ''; v.einstufung = null; v.uebergabe = null; this.render(v, list); }));
        }else{
          act.append(d().button('Datenschutz prüfen →', ()=>this.pruefen(v), 'p'), d().el('small', 's-muted', 'Prompt und Dokument gemeinsam prüfen – lokal'));
        }
        left.append(act);
      }
      pair.append(left);
      // rechts: Übergabe
      const right = d().el('div', 't-gateway-col t-gateway-right');
      right.append(d().el('div', 't-gateway-colhead', 'Übergabeprompt an die KI'), d().el('small', 's-muted', v.uebergabe ? (v.uebergabe.unpseudonymisiert ? 'Unverändert – siehe Hinweis' : 'Pseudonymisierte Fassung – das würde die KI erhalten') : 'Erscheint nach der Prüfung'));
      if(v.uebergabe){
        right.append(this.pre(tokenize(v.uebergabe.text)));
        if(v.uebergabe.dokument) { const det = d().el('details'); det.append(d().el('summary', null, 'Dokument (' + ((v.dokument || {}).name || '') + ')'), this.pre(tokenize(v.uebergabe.dokument))); right.append(det); }
        if(v.uebergabe.unpseudonymisiert) right.append(d().el('div', 's-note warn', v.uebergabe.grund));
        const legend = d().el('div', 't-gateway-legend');
        Object.entries(v.uebergabe.counts || {}).forEach(([t, n])=>legend.append(d().el('span', 't-gateway-tok tok-' + t.toLowerCase(), (TYP[t] || t) + ' · ' + n)));
        right.append(legend);
        right.append(d().el('div', 't-gateway-local', 'Die Zuordnung bleibt lokal – nur in diesem Prozess, gelöscht nach der Rückübersetzung. Pseudonymisierung ist keine Anonymisierung.'));
      }else{
        right.append(d().el('div', 't-gateway-placeholder', 'Hier steht nach „Datenschutz prüfen“ die Fassung mit Platzhaltern.'));
      }
      pair.append(right);
      sec.append(pair);
      return sec;
    },

    pre(parts, cls){
      const p = d().el('div', 't-gateway-pre' + (cls ? ' ' + cls : ''));
      parts.forEach(x=>{ if(x.token){ const s = d().el('span', 't-gateway-tok tok-' + x.typ.toLowerCase(), x.token); s.title = TYP[x.typ] || x.typ; p.append(s); } else p.append(document.createTextNode(x.text)); });
      return p;
    },

    station03(v){
      const sec = d().el('section', 't-gateway-sec');
      const e = v.einstufung;
      if(!e){ sec.append(this.step('03 / Empfehlung & Freigabe', 'Erst prüfen'), d().el('small', 's-muted', 'Die Empfehlung kommt aus der Prüfung – Schutzklasse, Merkmale, erlaubte Wege.')); return sec; }
      const tone = e.policy === 'BLOCKED' ? 'bad' : e.policy === 'HUMAN_REVIEW_REQUIRED' ? 'warn' : 'ok';
      sec.append(this.step('03 / Empfehlung & Freigabe', e.policy === 'BLOCKED' ? 'Verarbeitung gesperrt' : 'Empfehlung: ' + (e.wege[0] === 'LOCAL_ONLY' ? 'lokale Verarbeitung' : 'Cloud zulässig – ' + this.cloudWort(this.list)), [e.policy_wort, tone], v.zustand === 'WARTET' ? 5 : 4));
      const facts = d().el('div', 't-gateway-facts');
      const fact = (k, val)=>{ const f = d().el('div'); f.append(d().el('small', 's-muted', k), d().el('b', null, val)); facts.append(f); };
      fact('Schutzklasse', e.klasse + ' · ' + e.klasse_wort);
      fact('Merkmale', e.merkmale.length ? e.merkmale.map(m=>m.id).join(', ') : 'keine erkannt');
      fact('Erlaubte Wege', e.wege_wort.length ? e.wege_wort.join(' / ') : 'keiner');
      fact('Review (R1)', e.review === 'PENDING' ? 'deine Prüfung ist die Freigabe' : 'nicht nötig');
      fact('Zweck', v.zweck_wort || v.zweck || '–');
      fact('Verantwortlich', v.verantwortlich || '–');
      sec.append(facts);
      e.gruende.forEach(g=>sec.append(d().el('div', 's-note ' + tone, g)));
      const det = d().el('details'); det.append(d().el('summary', null, 'Mehr Infos – Merkmale und Zuordnung'));
      const tbl = d().el('table', 't-gateway-table');
      const tr = d().el('tr'); ['Merkmal', 'Bedeutung', 'gefunden in', 'Regel'].forEach(t=>tr.append(d().el('th', null, t))); tbl.append(tr);
      e.merkmale.forEach(m=>{ const r = d().el('tr'); [m.id, m.name, m.quelle, m.regel || '–'].forEach(t=>r.append(d().el('td', null, t))); tbl.append(r); });
      det.append(tbl, d().el('small', 's-muted', e.hinweis),
                 d().el('small', 's-muted', 'Policy ' + e.policy_version + ' · Regelwerk v0.1 – Normbezüge sind Annahmen des Teams, keine Rechtsprüfung · Schutzklassen sind keine EU-AI-Act-Risikoklassen.'));
      sec.append(det);
      // Freigabe
      const rel = d().el('div', 't-gateway-release');
      if(v.zustand === 'WARTET'){
        rel.append(d().el('div', 's-note warn', 'Die Freigabe liegt in den Entscheidungen. Dort oder hier beantworten.'),
                   d().button('Jetzt freigeben', ()=>this.freigeben(v, v.weg, v.freigabe_offen), 'p'),
                   d().button('Ablehnen', ()=>this.ctx.shell.decide('request:' + v.freigabe_offen, 'ablehnen').then(()=>this.refresh())));
      }else if(v.zustand === 'GEPRUEFT'){
        const wege = e.wege.filter(w=>v.wunsch === 'local' ? w === 'LOCAL_ONLY' : true);
        if(!wege.length) rel.append(d().el('div', 's-note bad', 'Für diesen Wunsch gibt es keinen erlaubten Weg.'));
        wege.forEach(w=>rel.append(d().button(WEG[w] + ' →', ()=>this.freigeben(v, w), w === 'LOCAL_ONLY' ? 'p' : '')));
        if(v.wunsch === 'cloud' && !wege.includes('CLOUD_AFTER_PSEUDONYMIZATION') && !wege.includes('CLOUD_ALLOWED')) rel.append(d().el('small', 's-muted', 'Cloud ist hier nicht erlaubt – nur lokal.'));
        rel.append(d().el('small', 's-muted', 'Die Freigabe ist eine Entscheidung mit Bindung: Anfrage, Dokument, Klasse, Merkmale, Weg, Übergabeprompt, Zweck und verantwortliche Person. Cloud: ' + this.cloudWort(this.list) + '.'));
      }else if(e.policy === 'BLOCKED'){
        rel.append(d().el('div', 's-note bad', 'Kein Modellaufruf, auch nicht lokal. Es gibt kein „trotzdem“ – entferne den Grund und prüfe neu.'));
      }
      sec.append(rel);
      return sec;
    },

    station04(v){
      const sec = d().el('section', 't-gateway-sec');
      const e = v.entwurf;
      sec.append(this.step('04 / Ergebnis & menschliche Prüfung', 'Ausgabe / Antwort', e ? [e.pruefung === 'geprueft' ? 'geprüft' : 'Entwurf · deine Prüfung', e.pruefung === 'geprueft' ? 'ok' : 'warn'] : ['Noch kein Ergebnis', ''], e ? (e.pruefung === 'geprueft' ? 7 : 6) : null));
      if(!e){
        sec.append(d().el('div', 't-gateway-placeholder', v.zustand === 'VERWORFEN' ? 'Verworfen – Entwurf und Zuordnung sind gelöscht.' : v.zustand === 'ABGESCHLOSSEN' ? 'Abgeschlossen – der Entwurf ist am Löschdatum gelöscht worden.' : 'Hier erscheint der Entwurf nach der Freigabe.'));
        return sec;
      }
      sec.append(d().el('div', 't-gateway-kennz', e.kennzeichnung || 'KI-Entwurf'));            // R-14: KI-Kennzeichnung (EU AI Act Art. 50)
      const ans = d().el('div', 't-gateway-answer'); ans.textContent = e.text; sec.append(ans);
      const foot = d().el('div', 't-gateway-foot');
      foot.append(d().el('small', 's-muted', (e.weg === 'LOCAL_ONLY' ? 'Lokal · ' : 'Cloud · ') + e.modell + ' · ' + (e.erstellt || '').replace('T', ' ').slice(0, 16)
                         + ' · wird gelöscht am ' + (e.loeschen_am || '').slice(0, 10)));
      const rc = d().el('small', 's-muted', (e.rechecks || []).join(' · ')); foot.append(rc);
      if(e.pruefung === 'offen'){
        const row = d().el('div', 's-row');
        row.append(d().button('Geprüft – Entwurf ist in Ordnung', ()=>this.urteil('geprueft'), 'p'), d().button('Verwerfen', ()=>this.urteil('verworfen')),
                   d().el('small', 's-muted', 'Kein Versand: was du damit tust, geschieht außerhalb von SEDRA.'));
        foot.append(row);
      }
      sec.append(foot);
      return sec;
    },

    // ---------------------------------------------------------------- Handlungen
    async pruefen(v){
      const out = await this.ctx.api('/api/gateway/pruefen', {method: 'POST', body: {id: v.id, anfrage: this.ta ? this.ta.value : v.anfrage, dokument: this.sel ? this.sel.value : '',
                                                                                     wunsch: v.wunsch, manuell: [this.r01 && this.r01.checked ? 'R01' : null, this.a01 && this.a01.checked ? 'A01' : null].filter(Boolean),
                                                                                     zweck: this.zweck ? this.zweck.value : v.zweck, verantwortlich: this.wer ? this.wer.value : v.verantwortlich}});
      this.state.vorgang = out; this.render(out, this.state.list);
      const e = out.einstufung || {};
      this.ctx.shell.notify('Geprüft: ' + (e.klasse || '?') + ' · ' + (e.policy_wort || ''), e.policy === 'BLOCKED' ? 'warn' : 'note');
    },

    async freigeben(v, weg, missionId){
      let mid = missionId;
      if(!mid){
        const out = await this.ctx.api('/api/gateway/freigabe', {method: 'POST', body: {id: v.id, weg}});
        mid = out.mission_id;
        const hinweis = weg === 'LOCAL_ONLY' ? 'Nichts verlässt den Rechner.' : this.cloudWort(this.list) === 'Simulation'
          ? 'Cloud ist simuliert; nichts verlässt den Rechner.' : 'Der Übergabeprompt geht an den Cloud-Anbieter, nach Inhaltsschutz und Regelwerk.';
        if(!confirm('Genau das einmal freigeben?\n\n' + ((out.binding || {}).describe || '') + '\n\n' + hinweis)){ await this.refresh(); return; }
      }
      await this.ctx.shell.decide('request:' + mid, 'freigeben_und_anwenden');
      await this.refresh();
    },

    async urteil(u){
      const v = this.state.vorgang;
      const out = await this.ctx.api('/api/gateway/pruefung', {method: 'POST', body: {id: v.id, urteil: u}});
      this.state.vorgang = out; this.render(out, this.state.list);
      this.ctx.shell.notify(u === 'geprueft' ? 'Entwurf geprüft. Kein Versand.' : 'Entwurf verworfen und gelöscht.', 'note');
    },

    async verwerfen(){
      const v = this.state.vorgang;
      if(!confirm('Vorgang verwerfen? Zuordnung und Entwurf werden gelöscht.')) return;
      const out = await this.ctx.api('/api/gateway/verwerfen', {method: 'POST', body: {id: v.id}});
      this.state.vorgang = out; this.render(out, this.state.list);
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraGatewayPure = {tokenize, markup};
  if(typeof module !== 'undefined' && module.exports) module.exports = {tokenize, markup};
})();
