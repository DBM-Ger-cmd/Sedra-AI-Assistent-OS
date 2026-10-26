// UI contract 1.0 – der Rahmen: eine Shell aus einer Vorgabe (SPEC_SHELL_AUS_VORGABE_v1, Build 17).
//
// Eine Vorgabe (shell.vorgabe.yaml, geprüft gegen ui/schema/vorgabe.schema.json) sagt, *was wo steht*; dieser Rahmen baut daraus
// den Bildschirm. Die Mechanik, die bis hierher in vier Shells viermal geschrieben war – Werkzeug mounten, `ready` abwarten,
// Verben zeigen, `unmount` beim Wechsel, Marken setzen, talk.context senden, nach einer Handlung auffrischen –, steht hier
// **einmal**. Eine Shell aus Vorgabe besteht nur aus shell.yaml, shell.vorgabe.yaml und optional shell.css.
//
// Sechs Zonen: leiste (Instrumente) · orte (Ortskunde) · werkstueck (Objekt mit Nachweisen) · gespraech · entscheidungen · leer.
// Der Rahmen kennt kein Werkzeug beim Namen (außer dem Gespräch, Regel 11) – er fragt die Registrierung. Kein eigenes fetch,
// kein eigener Global außer sedraFrame. Die reinen Teile (parseRaster, layoutOf) prüft node.
// Classic script: definiert window.sedraFrame; der Loader ruft register(manifest.shell), wenn die Shell eine Vorgabe ist.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const ZONES = ['leiste', 'orte', 'werkstueck', 'gespraech', 'entscheidungen', 'leer'];
  const MAX_HISTORY = 24;

  // ---- rein: aus dem Raster werden Zeilen aus Spalten
  function parseRaster(raster){
    return (raster || []).map(row=>String(row).split('|').map(z=>z.trim()).filter(z=>ZONES.includes(z)));
  }

  // rein: was die Vorgabe sagt, mit allen Standardwerten – ein Ort für jede Annahme
  function layoutOf(v){
    v = v || {};
    const rows = parseRaster(v.raster);
    const zones = rows.flat();
    return {
      rows, zones,
      orte: {breite: (v.orte || {}).breite || 220, liste: (v.orte || {}).liste || null, einblenden: (v.orte || {}).einblenden || 'fest'},
      leiste: {einblenden: (v.leiste || {}).einblenden || 'fest'},
      rand: z=>(z === 'orte' && ((v.orte || {}).einblenden === 'rand')) || (z === 'leiste' && ((v.leiste || {}).einblenden === 'rand')),
      nachweise: (v.werkstueck || {}).nachweise || 'seitenleiste',
      nachweisBreite: (v.werkstueck || {}).nachweis_breite || 360,
      gespraech: {art: (v.gespraech || {}).art || 'zone', hoehe: (v.gespraech || {}).hoehe || 112},
      entscheidungen: v.entscheidungen || 'karte',
      suche: v.suche || 'strg-k',
      start: v.start || {type: 'task', id: 'alle', title: 'Aufgaben', collection: true},
      hasZone: z=>zones.includes(z)
    };
  }

  function register(shellManifest){
    const L = layoutOf(shellManifest.vorgabe);
    const id = shellManifest.id;
    const key = 'sedra.frame.' + id;

    const shell = {
      id,

      async start(ctx){
        this.ctx = ctx; this.L = L;
        this.api = ctx.api; this.onProblem = ctx.onProblem;
        this.mounted = []; this.current = null; this.history = [];
        const host = document.getElementById('sedra-root');
        host.classList.add('fr'); host.replaceChildren();
        this.shellApi = {open: o=>this.open(o), notify: (t, tone)=>this.notify(t, tone), decide: (i, w)=>this.decide(i, w),
                         theme: n=>root.sedraBoot && root.sedraBoot.setTheme(n), reload: ()=>root.sedraWechsel && root.sedraWechsel.neuLaden ? root.sedraWechsel.neuLaden() : location.reload()};
        this.el = {};
        this.grid(host);
        if(L.hasZone('leiste')) this.buildLeiste();
        if(L.hasZone('orte')) this.buildOrte();
        this.buildWerkstueck();
        this.buildGespraech(host);
        if(L.entscheidungen === 'karte') this.buildKarte(host);
        if(L.suche === 'strg-k') this.buildPalette();

        ctx.bus.on('object.open', o=>this.open(o));
        // Vertrag 1.1 (§9.5): Ereignisse bündeln – höchstens ein Auffrischen je 500 ms
        const B = root.sedraLifecycle.buendeln;
        this.buendelAlle = B(()=>this.refreshAll(), 500);
        this.buendelLauf = B(()=>{ this.refreshLeiste(); this.drawVerbs(); }, 500);
        ctx.bus.on('decision.pending', ()=>this.buendelAlle());
        ctx.bus.on('decision.answered', ()=>this.buendelAlle());
        ctx.bus.on('task.changed', ()=>this.buendelLauf());
        ctx.bus.on('model.changed', ()=>this.buendelLauf());
        this.melder = root.sedraStand.makeMelder(ctx.api);
        ctx.bus.on('desk.error', e=>this.notify('Die Runtime meldet: ' + e.message, 'warn'));
        document.addEventListener('keydown', e=>{
          if(this.palette && (e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'k' || e.key === 'K')){ e.preventDefault(); this.palette.toggle(); }
          else if(e.key === 'Escape' && this.palette && this.palette.isOpen()) this.palette.close();
        });

        let saved = null;
        if(shellManifest.layout && shellManifest.layout.persist === 'browser'){
          try{ saved = JSON.parse(localStorage.getItem(key) || 'null'); }catch(_e){}
        }
        if(saved && Array.isArray(saved.history)) this.history = saved.history.slice(-MAX_HISTORY);
        // §10.4: lag in einer anderen Shell etwas vorn, das dieser Rahmen zeichnen kann, wird es das Werkstück
        const stand = await this.melder.holen();
        const vorn = ((stand && stand.offen) || []).find(o=>root.sedraStand.schluessel(o) === (stand && stand.vorn));
        const fremd = vorn && stand.shell && stand.shell !== id && this.ctx.tools.forObject(vorn).length ? vorn : null;
        this.open(fremd || (saved && saved.current) || L.start);
        if(fremd) this.notify('Aus der Oberfläche „' + stand.shell + '“ mitgenommen: ' + (fremd.title || fremd.type) + '.', 'note');
        await this.refreshAll();
        host.scrollLeft = 0; host.scrollTop = 0;           // ein Fokus darf den Rahmen nicht verschieben
        root.sedraBoot.onProblem = text=>this.notify(text, 'warn');
        (root.sedraBoot.problems || []).forEach(text=>this.notify(text, 'warn'));
      },

      // ---- das Raster: Zeilen, darin Spalten; jede Zone ein Element mit fr-zone-<name>
      grid(host){
        // Zonen mit `einblenden: rand` stehen nicht im Raster: sie liegen verborgen am Rand und fahren beim Anfahren heraus
        const rows = L.rows.map(row=>row.filter(z=>!L.rand(z))).filter(row=>row.length);
        const rowsCss = rows.map(row=>row.length === 1 && row[0] === 'leiste' ? 'auto'
                                    : row.includes('gespraech') && row.length === 1 ? L.gespraech.hoehe + 'px'
                                    : row.includes('werkstueck') ? 'minmax(0,1fr)' : 'auto').join(' ');
        host.style.gridTemplateRows = rowsCss;
        const make = z=>{
          const zone = d().el(z === 'orte' ? 'nav' : 'section', 'fr-zone fr-zone-' + z);
          zone.setAttribute('aria-label', {leiste: 'Instrumente', orte: 'Orte', werkstueck: 'Werkstück', gespraech: 'Gespräch', entscheidungen: 'Entscheidungen', leer: ''}[z]);
          this.el[z] = zone; return zone;
        };
        rows.forEach(row=>{
          const line = d().el('div', 'fr-row');
          line.style.gridTemplateColumns = row.map(z=>z === 'orte' ? L.orte.breite + 'px' : z === 'entscheidungen' ? '320px' : 'minmax(0,1fr)').join(' ');
          row.forEach(z=>line.append(make(z)));
          host.append(line);
        });
        L.zones.filter(z=>L.rand(z)).forEach(z=>{
          const zone = make(z); zone.classList.add('fr-rand', 'fr-rand-' + (z === 'orte' ? 'links' : 'oben'));
          if(z === 'orte') zone.style.width = L.orte.breite + 'px';
          const sensor = d().el('div', 'fr-sensor fr-sensor-' + (z === 'orte' ? 'links' : 'oben'));
          sensor.setAttribute('aria-hidden', 'true');
          let timer = null;
          const show = ()=>{ clearTimeout(timer); zone.classList.add('on'); };
          const hide = ()=>{ clearTimeout(timer); timer = setTimeout(()=>{ if(!zone.contains(document.activeElement)) zone.classList.remove('on'); }, 350); };
          sensor.addEventListener('mouseenter', show); zone.addEventListener('mouseenter', show);
          zone.addEventListener('mouseleave', hide); zone.addEventListener('focusin', show); zone.addEventListener('focusout', hide);
          host.append(sensor, zone);
        });
      },

      // ---- leiste: ein Feld je Instrument (kind: instrument), gespeist aus /api/strip; dazu Suche und Gesprächsknopf
      buildLeiste(){
        const zone = this.el.leiste; this.gauges = [];
        this.ctx.tools.byKind('instrument').forEach(manifest=>{
          const cell = d().el('div', 'fr-gauge'); cell.dataset.tool = manifest.id; zone.append(cell);
          const state = root.sedraLifecycle.mountTool(this.ctx.tools.mod(manifest.id), cell, this.ctx.makeContext(manifest, null, this.shellApi), this.onProblem);
          this.gauges.push({manifest, state, mod: this.ctx.tools.mod(manifest.id)});
        });
        const right = d().el('div', 'fr-leiste-right');
        if(L.suche === 'feld'){
          const input = d().el('input', 'fr-search'); input.placeholder = 'Ort oder Auftrag'; input.setAttribute('aria-label', 'Suche');
          input.onkeydown = e=>{ if(e.key === 'Enter'){ e.preventDefault(); const t = input.value.trim(); input.value = ''; if(t) this.route(t); } };
          right.append(input);
        }
        if(L.gespraech.art === 'schublade') right.append(d().button('Gespräch', ()=>this.toggleDrawer(), 'fr-drawer-btn'));
        right.append(d().el('small', 'fr-hint', L.suche === 'strg-k' ? 'Strg+K · Enter sendet · Esc schließt' : 'Enter im Gespräch sendet'));
        zone.append(right);
      },

      async refreshLeiste(){
        if(!this.gauges || !this.gauges.length) return;
        let reading = null, err = null;
        try{ reading = await this.api('/api/strip'); }catch(e){ err = e.message; }
        this.gauges.forEach(g=>{ if(g.mod.update) try{ g.mod.update(reading, err); }catch(e){ this.onProblem('Instrument ' + g.manifest.id, e); } });
      },

      // ---- orte: die Ortskunde als Liste; der aktuelle Ort ist markiert
      buildOrte(){
        const zone = this.el.orte; zone.replaceChildren();
        const P = root.sedraPlaces.PLACES;
        const list = L.orte.liste ? L.orte.liste.map(i=>P.find(p=>p.id === i)).filter(Boolean) : P;
        list.forEach(p=>{
          const row = d().el('div', 'fr-ort'); row.dataset.ort = p.id;
          row.append(d().el('b', null, p.label), d().el('small', null, p.hint));
          d().clickable(row, ()=>this.open(p.object));
          zone.append(row);
        });
      },

      markOrt(object){
        if(!this.el.orte || !object) return;
        const P = root.sedraPlaces.PLACES;
        const hit = P.find(p=>p.object.type === object.type && (p.object.id === object.id || !object.collection && p.object.id === 'alle'));
        this.el.orte.querySelectorAll('.fr-ort').forEach(r=>r.classList.toggle('on', !!hit && r.dataset.ort === hit.id));
      },

      // ---- werkstueck: Kopf mit Titel und Verben (data-verbs), Körper mit Inhalt und Nachweisen nach der Vorgabe
      buildWerkstueck(){
        const zone = this.el.werkstueck;
        this.head = d().el('div', 'fr-head'); this.title = d().el('b', 'fr-title');
        this.verbs = d().el('div', 'fr-verbs'); this.verbs.dataset.verbs = '';
        this.head.append(this.title, this.verbs);
        this.body = d().el('div', 'fr-body fr-mode-' + L.nachweise);
        if(L.nachweise === 'seitenleiste') this.body.style.gridTemplateColumns = 'minmax(0,1fr) ' + L.nachweisBreite + 'px';
        zone.append(this.head, this.body);
      },

      open(object){
        if(!object || !object.type || !object.id) return;
        const same = this.current && this.current.type === object.type && this.current.id === object.id;
        // Vertrag 1.1: dasselbe Objekt ohne verlangte Ansicht hängt nichts neu ein (der Zustand bleibt); eine verlangte Ansicht ist Navigation
        if(same && object.ansicht === undefined && object.view === undefined && this.mounted.length) return;
        this.current = {type: object.type, id: object.id, title: object.title || object.id, collection: !!object.collection};
        if(object.view !== undefined) this.current.view = String(object.view);
        if(object.ansicht !== undefined) this.current.ansicht = String(object.ansicht);
        if(this.melder) this.melder.offen([this.current].concat(this.history.slice().reverse()), root.sedraStand.schluessel(this.current));
        if(!same){ this.history = this.history.filter(h=>!(h.type === object.type && h.id === object.id)).concat([this.current]).slice(-MAX_HISTORY); this.save(); }
        this.mounted.forEach(s=>root.sedraLifecycle.unmountTool(s, this.onProblem));
        this.mounted = []; this.body.replaceChildren(); this.title.textContent = this.current.title;
        const tools = this.orderTools(this.ctx.tools.forObject(this.current), this.current);   // N1: zu genau diesem Objekt
        if(!tools.length){ this.body.append(d().empty('Kein Werkzeug für „' + object.type + '“ – im Werkzeug „Module“ nachsehen.')); this.drawVerbs(); return; }
        const inhalt = d().el('div', 'fr-col fr-inhalt'), nachweis = d().el('div', 'fr-col fr-nachweis');
        nachweis.dataset.slot = 'nachweis';
        const evidence = tools.filter(t=>t.slot === 'nachweis'), content = tools.filter(t=>t.slot !== 'nachweis');
        const mountIn = (manifest, where)=>{
          const slot = d().el('div', 'fr-tool'); slot.dataset.tool = manifest.id; where.append(slot);
          this.mounted.push(root.sedraLifecycle.mountTool(this.ctx.tools.mod(manifest.id), slot, this.ctx.makeContext(manifest, this.current, this.shellApi), this.onProblem));
        };
        content.forEach(m=>mountIn(m, inhalt));
        if(L.nachweise === 'keine' || !evidence.length){ this.body.append(inhalt); }
        else if(L.nachweise === 'umschalter'){
          const tabs = d().el('div', 'fr-seg'); const panes = [inhalt, nachweis];
          const names = ['Werkstück'].concat(evidence.map(m=>m.name));
          evidence.forEach(m=>mountIn(m, nachweis));
          names.forEach((n, i)=>{
            const b = d().el('button', 'fr-seg-item' + (i === 0 ? ' on' : ''), n); b.type = 'button';
            if(i > 0) b.dataset.seg = evidence[i - 1].id;      // data-seg, nicht data-tool: der Knopf ist kein Container
            b.onclick = ()=>{ tabs.querySelectorAll('button').forEach(x=>x.classList.remove('on')); b.classList.add('on');
                              inhalt.hidden = i !== 0; nachweis.hidden = i === 0;
                              nachweis.querySelectorAll('.fr-tool').forEach(s=>{ s.hidden = i > 0 && s.dataset.tool !== evidence[i - 1].id; }); };
            tabs.append(b);
          });
          nachweis.hidden = true;
          this.body.append(tabs, inhalt, nachweis);
        }else if(L.nachweise === 'spalten'){               // jeder Nachweis seine eigene Spalte, alles zugleich sichtbar
          this.body.append(inhalt);
          evidence.forEach(m=>{ const col = d().el('div', 'fr-col fr-nachweis'); col.dataset.slot = 'nachweis'; mountIn(m, col); this.body.append(col); });
          this.body.style.gridTemplateColumns = 'repeat(' + (1 + evidence.length) + ', minmax(0,1fr))';
        }else{                                            // seitenleiste: Werkstück links, die Nachweise rechts untereinander
          evidence.forEach(m=>mountIn(m, nachweis));
          this.body.append(inhalt, nachweis);
        }
        Promise.all(this.mounted.map(s=>s.ready)).then(()=>this.drawVerbs()).catch(()=>this.drawVerbs());
        this.markOrt(this.current);
        this.ctx.bus.emit('talk.context', {object: {type: this.current.type, id: this.current.id, title: this.current.title}});
      },

      // eine Sammlung bekommt keine Nachweise (Fund der Shell E: die Liste der Aufgaben hat keinen Diff)
      orderTools(manifests, object){
        return object.collection ? manifests.filter(m=>m.slot !== 'nachweis') : manifests;
      },

      drawVerbs(){
        this.verbs.replaceChildren();
        this.mounted.forEach(state=>{
          if(state.el.closest('[data-slot="nachweis"]')) return;
          root.sedraLifecycle.actionsOf(state).forEach(a=>this.verbs.append(d().button(a.label, async()=>{ await a.run(); this.drawVerbs(); })));
        });
      },

      save(){
        if(!(shellManifest.layout && shellManifest.layout.persist === 'browser')) return;
        try{ localStorage.setItem(key, JSON.stringify({current: this.current, history: this.history, v: 1})); }catch(_e){}
      },

      // ---- gespraech: das Werkzeug talk, in seiner Zone oder in einer Schublade
      buildGespraech(host){
        let zone = this.el.gespraech;
        if(L.gespraech.art === 'schublade'){
          zone = d().el('section', 'fr-drawer'); zone.setAttribute('aria-label', 'Gespräch'); host.append(zone); this.el.gespraech = zone;
          if(!this.el.leiste) this.head.append(d().button('Gespräch', ()=>this.toggleDrawer(), 'fr-drawer-btn'));
        }
        if(!zone) return;
        const manifest = this.ctx.tools.all().find(t=>t.kind === 'panel' && t.id === 'talk');
        if(!manifest){ zone.append(d().empty('Das Werkzeug „Gespräch“ fehlt – ohne es gibt es kein Eingabefeld. uix.yaml prüfen.')); return; }
        const slot = d().el('div', 'fr-tool'); slot.dataset.tool = 'talk'; zone.append(slot);
        this.talkState = root.sedraLifecycle.mountTool(this.ctx.tools.mod('talk'), slot, this.ctx.makeContext(manifest, null, this.shellApi), this.onProblem);
      },

      toggleDrawer(){ const z = this.el.gespraech; if(z && z.classList.contains('fr-drawer')){ z.classList.toggle('on'); if(z.classList.contains('on')){ const i = z.querySelector('input'); if(i) i.focus(); } } },

      notify(text, tone){ const mod = this.ctx.tools.mod('talk'); if(mod && mod.say) mod.say(text, tone || 'note'); else console.warn('[frame]', text); },
      talk(text){ const mod = this.ctx.tools.mod('talk'); if(mod && mod.send) return mod.send(text); this.notify('Das Gespräch ist nicht geladen; der Auftrag wurde nicht gesendet.', 'warn'); },
      route(text){ const r = root.sedraPlaces.routeText(text); if(r && r.kind === 'place') return this.open(r.object); return this.talk(text); },

      // ---- entscheidungen als Karte: erscheint, sobald eine wartet – in ihrer Raster-Zone oder rechts schwebend
      buildKarte(host){
        let zone = this.el.entscheidungen;
        this.karteFloats = !zone;
        if(!zone){ zone = d().el('section', 'fr-karte'); zone.setAttribute('aria-label', 'Entscheidungen'); host.append(zone); this.el.entscheidungen = zone; }
        zone.hidden = this.karteFloats;
        if(!this.karteFloats) zone.append(d().empty('Nichts wartet. Was deine Entscheidung braucht, erscheint hier.'));
      },

      async refreshKarte(){
        const zone = this.el.entscheidungen;
        if(!zone || L.entscheidungen !== 'karte') return;
        let open = null;
        try{ open = await this.api('/api/decisions'); }catch(_e){ return; }
        const count = (open && open.items || []).length;
        zone.hidden = this.karteFloats && count === 0;
        if(count === 0){
          if(this.karteState){ root.sedraLifecycle.unmountTool(this.karteState, this.onProblem); this.karteState = null; zone.replaceChildren(); }
          if(!this.karteFloats && !zone.childElementCount) zone.append(d().empty('Nichts wartet. Was deine Entscheidung braucht, erscheint hier.'));
          return;
        }
        if(this.karteState) return;
        const alle = {type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true};
        const manifest = this.ctx.tools.forObject(alle)[0];
        if(!manifest) return;
        const slot = d().el('div', 'fr-tool'); slot.dataset.tool = manifest.id; zone.replaceChildren(slot);
        this.karteState = root.sedraLifecycle.mountTool(this.ctx.tools.mod(manifest.id), slot,
          this.ctx.makeContext(manifest, alle, this.shellApi), this.onProblem);
      },

      async refreshAll(){ await Promise.all([this.refreshLeiste(), this.refreshKarte()]).catch(e=>this.onProblem('Auffrischen', e)); },

      async decide(id, way){
        const out = await this.api('/api/decisions/answer', {method: 'POST', body: {id, way}});
        await this.refreshAll();
        this.ctx.bus.emit('decision.answered', {id, kind: 'answered'});
        return out;
      },

      // ---- suche: die Palette (Strg+K) über der Ortskunde – Zeilen aus paletteRows, Enter öffnet oder sendet
      buildPalette(){
        const P = root.sedraPlaces; let index = 0;
        const host = d().el('div', 'fr-pal'); host.hidden = true;
        const box = d().el('div', 'fr-pal-box'); const input = d().el('input'); const list = d().el('div', 'fr-pal-list');
        input.placeholder = 'Wohin oder was? – ein Ort, oder ein Auftrag für SEDRA'; input.setAttribute('aria-label', 'Kommando');
        const render = ()=>{
          const rows = P.paletteRows(input.value); index = Math.max(0, Math.min(index, rows.length - 1));
          list.replaceChildren(...rows.map((r, i)=>{ const line = d().el('div', 'fr-pal-row' + (i === index ? ' on' : ''));
            line.append(d().el('b', null, r.label), d().el('small', null, r.hint || ''));
            line.onmousedown = e=>{ e.preventDefault(); pick(r); }; line.onmousemove = ()=>{ if(index !== i){ index = i; render(); } }; return line; }));
        };
        const close = ()=>{ host.hidden = true; const i = this.el.gespraech && this.el.gespraech.querySelector('input'); if(i) i.focus(); };
        const pick = r=>{ if(!r) return; const text = input.value.trim(); close(); if(r.id === '__talk') return this.talk(text); if(r.object) return this.open(r.object); };
        input.oninput = ()=>{ index = 0; render(); };
        input.onkeydown = e=>{ const rows = P.paletteRows(input.value);
          if(e.key === 'ArrowDown'){ e.preventDefault(); index = Math.min(rows.length - 1, index + 1); render(); }
          else if(e.key === 'ArrowUp'){ e.preventDefault(); index = Math.max(0, index - 1); render(); }
          else if(e.key === 'Enter'){ e.preventDefault(); pick(rows[index]); }
          else if(e.key === 'Escape'){ e.preventDefault(); close(); } };
        box.append(input, list); host.append(box); host.onmousedown = e=>{ if(e.target === host) close(); };
        document.body.append(host);
        this.palette = {toggle: ()=>{ if(host.hidden){ host.hidden = false; input.value = ''; index = 0; render(); input.focus(); } else close(); },
                        close, isOpen: ()=>!host.hidden};
      }
    };
    root.sedra.registerShell(shell);
    return shell;
  }

  root.sedraFrame = {register, parseRaster, layoutOf, ZONES};
  if(typeof module !== 'undefined' && module.exports) module.exports = {parseRaster, layoutOf, ZONES};
})();
