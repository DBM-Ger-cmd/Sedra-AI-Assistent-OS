// Werkzeug „Module“ (Vertrag §6/§7, Spec SHELL_E_UND_MODULE §2).
//
// Es zeigt, woraus die Oberfläche gerade besteht: welche Shell läuft, welche Werkzeuge geladen sind, was abgelehnt wurde und
// warum. Und es macht aus dem Einbau, der bisher nur eine Route war, etwas, das der Captain anfassen kann.
//
// Zwei Linien, die hier sichtbar bleiben:
//   fremder Code  → Gate. Vorlegen, Hashes, Durchsicht; eingebaut wird erst nach der Freigabe.
//   eigene Form   → Audit. Shell wechseln, Werkzeug an/aus, aus der Vorlage anlegen – alles mit einem Klick zurück.
// Nichts davon fasst den Projektordner an; geschrieben wird nur in `local_config`.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // Was ein Vertrauenswort bedeutet – in einem Satz, ohne Fachwort (rein)
  const TRUST = {
    CORE: 'gehört zum Paket',
    CAPTAIN: 'von dir angelegt',
    COMMUNITY: 'von außen – bekommt nur Leserouten'
  };

  // Aus einer abgelehnten Begründung einen Satz machen, damit niemand Code lesen muss (rein)
  const WHY = {
    id_must_match_folder: 'die id im Manifest ist nicht der Ordnername',
    needs_ui_not_met: 'das Modul will eine andere Fassung des Vertrags',
    local_module_cannot_be_core: 'ein eigenes Modul kann nie CORE sein',
    duplicate_id: 'diese id gibt es schon',
    handles_unknown_type: 'es will einen Objekttyp zeichnen, den es nicht gibt',
    kind_invalid: 'die Art ist weder object noch instrument noch panel',
    entry_js_required: 'im Manifest fehlt die js-Datei'
  };

  function reason(text){
    const key = String(text || '').split(':')[0];
    return WHY[key] || text;
  }

  const tool = {
    id: 'modules',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-modules');
      ctx.bus.on('tools.refresh', ()=>this.refresh());
      ctx.bus.on('decision.answered', ()=>this.refresh());
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-modules'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      try{ this.view = await this.ctx.api('/api/uix/modules'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Module nicht lesbar: ' + err.message)); return; }
      const box = d().el('div', 's-col');
      if(this.pendingReload){
        // Eine Änderung, die erst beim nächsten Laden wirkt, steht hier oben – mit dem Knopf, der es tut. Niemand soll raten.
        const note = d().el('div', 's-note warn t-modules-reload');
        note.append(d().el('span', null, this.pendingReload + ' '));
        note.append(d().button('Jetzt neu laden', ()=>{ if(this.ctx.shell.reload) this.ctx.shell.reload(); }, 'p'));
        box.append(note);
      }
      box.append(this.shells(), this.tools(), this.rejected(), this.add());
      box.append(d().el('small', 's-muted', this.view.note));
      this.el.replaceChildren(box);
    },

    // ---- Shells: welche läuft, welche es sonst gibt
    shells(){
      const box = d().el('div', 's-col');
      box.append(d().el('h5', 's-head', 'Shell'));
      if(!this.view.shell_available){
        box.append(d().el('div', 's-note warn', 'Die eingestellte Shell „' + this.view.shell + '“ ist nicht da – unten steht, warum.'));
      }
      this.view.shells.forEach(s=>{
        const row = d().el('div', 't-modules-row' + (s.enabled ? ' on' : ''));
        const head = d().el('div');
        head.append(d().el('b', null, s.name), d().el('small', 's-muted', ' · ' + s.description));
        row.append(head);
        const buttons = d().el('div', 's-row');
        if(s.enabled) buttons.append(d().el('span', 's-note ok', 'läuft gerade'));
        else buttons.append(d().button('Diese Shell nehmen', async()=>{
          await this.ctx.api('/api/uix/shell', {method: 'POST', body: {shell: s.id}});
          this.pendingReload = 'Die Shell „' + s.name + '“ ist eingestellt. Sie erscheint beim nächsten Laden der Seite.';
          await this.refresh();
        }));
        if(s.origin === 'local' && !s.enabled){
          buttons.append(d().button('Entfernen', async()=>{
            if(!confirm('Die Shell „' + s.name + '“ entfernen? Der Ordner wird gelöscht. Das ist kein Gate – was weg ist, kann nichts mehr tun.')) return;
            await this.ctx.api('/api/uix/remove', {method: 'POST', body: {kind: 'shell', id: s.id}});
            await this.refresh();
          }));
        }
        row.append(buttons);
        box.append(row);
      });
      return box;
    },

    // ---- Werkzeuge: Herkunft, Vertrauen, an/aus
    // Dreiundzwanzig in einer Liste liest niemand: nach Art gruppiert – was zeichnet, was misst, was spricht
    tools(){
      const box = d().el('div', 's-col');
      const groups = [['object', 'Werkzeuge'], ['instrument', 'Instrumente'], ['panel', 'Gespräch']];
      groups.forEach(([kind, label])=>{
        const list = this.view.tools.filter(t=>t.kind === kind).sort((a, b)=>a.name.localeCompare(b.name, 'de'));
        if(!list.length) return;
        box.append(d().el('h5', 's-head', label + ' · ' + list.length));
        list.forEach(t=>box.append(this.toolRow(t)));
      });
      return box;
    },

    toolRow(t){
        const row = d().el('div', 't-modules-row' + (t.enabled ? '' : ' off'));
        const head = d().el('div');
        head.append(d().el('b', null, t.name),
                    d().el('small', 's-muted', ' · ' + (TRUST[t.trust] || t.trust) + ' · ' + (t.routes.length || 'keine') + ' Route(n)'));
        if(t.description) head.append(d().el('div', 's-muted', t.description));
        if((t.own_types || []).length) head.append(d().el('div', 's-note warn', 'Bringt eigene Objekttypen mit: ' + t.own_types.join(', ') + ' – Baum und Palette kennen sie nicht; das Werkzeug öffnet sie selbst.'));
        if(t.trust === 'COMMUNITY') head.append(d().el('small', 's-muted', 'Von außen: nur Leserouten. Schreiben darf es erst nach einer Freigabe, die genau seine Routen nennt.'));
        row.append(head);
        const buttons = d().el('div', 's-row');
        if(t.required) buttons.append(d().el('small', 's-muted', t.id === 'talk' ? 'ohne Gespräch kein Eingabefeld' : 'der Weg zurück hierher'));
        else buttons.append(d().button(t.enabled ? 'Abschalten' : 'Anschalten', async()=>{
          await this.ctx.api('/api/uix/enabled', {method: 'POST', body: {id: t.id, enabled: !t.enabled}});
          this.pendingReload = '„' + t.name + '“ ist ' + (t.enabled ? 'abgeschaltet' : 'angeschaltet') + '. Es wirkt beim nächsten Laden der Seite.';
          await this.refresh();
        }));
        if(t.origin === 'local' && t.trust === 'COMMUNITY'){
          buttons.append(d().button('Schreibrouten freigeben …', async()=>{
            await this.ctx.api('/api/uix/trust', {method: 'POST', body: {kind: 'tool', id: t.id}});
            this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true});
          }));
        }
        if(t.origin === 'local'){
          buttons.append(d().button('Entfernen', async()=>{
            if(!confirm('„' + t.name + '“ entfernen? Der Ordner wird gelöscht. Das ist kein Gate – was weg ist, kann nichts mehr tun.')) return;
            await this.ctx.api('/api/uix/remove', {method: 'POST', body: {kind: 'tool', id: t.id}});
            await this.refresh();
          }));
        }
        row.append(buttons);
        return row;
    },

    // ---- Abgelehnt: der Grund im Klartext, damit niemand raten muss
    rejected(){
      const box = d().el('div', 's-col');
      if(!this.view.rejected.length) return box;
      box.append(d().el('h5', 's-head', 'Nicht geladen · ' + this.view.rejected.length));
      this.view.rejected.forEach(r=>{
        const row = d().el('div', 't-modules-row warn');
        row.append(d().el('b', null, r.kind + ' ' + r.id),
                   d().el('small', null, r.reasons.map(reason).join(' · ')));
        box.append(row);
      });
      return box;
    },

    // ---- Dazubauen: aus der Vorlage (Audit) oder von außen (Gate) – Werkzeug oder Shell, der Weg ist derselbe
    kindSwitch(){
      const box = d().el('div', 's-row');
      const state = {kind: 'tool'};
      const buttons = [['tool', 'Werkzeug'], ['shell', 'Shell']].map(([kind, label])=>{
        const b = d().el('button', 's-btn' + (kind === state.kind ? ' p' : ''), label);
        b.type = 'button';
        b.onclick = ()=>{ state.kind = kind; buttons.forEach(x=>x.classList.toggle('p', x.dataset.kind === kind)); };
        b.dataset.kind = kind;
        box.append(b);
        return b;
      });
      return {el: box, kind: ()=>state.kind};
    },

    add(){
      const box = d().el('div', 's-col t-modules-add');
      box.append(d().el('h5', 's-head', 'Dazubauen'));

      const mine = d().el('div', 't-modules-row');
      const mineKind = this.kindSwitch();
      const id = d().el('input');
      id.placeholder = 'id – kleine Buchstaben und Bindestrich, z. B. routinen oder meine-bruecke';
      id.setAttribute('aria-label', 'id des neuen Moduls');
      mine.append(d().el('b', null, 'Aus der Vorlage'),
                  d().el('small', 's-muted', 'Kopie mit Kommentaren, umbenannt und geprüft. Kein Gate: eigene Form, kein fremder Code. Eine Shell steht danach oben in der Liste.'),
                  mineKind.el, id,
                  d().button('Anlegen', async()=>{
                    const out = await this.ctx.api('/api/uix/scaffold', {method: 'POST', body: {kind: mineKind.kind(), id: id.value.trim()}});
                    id.value = '';
                    this.ctx.shell.notify(out.note, 'note');
                    await this.refresh();
                  }, 'p'));
      box.append(mine);

      // Build 17: eine Shell aus einer Vorgabe – Satz oder Vorlage, Skizze, anlegen; der Block ist Vertrag (ui/vorgabe.js)
      if(root.sedraVorgabe){
        const vg = d().el('div', 't-modules-row');
        vg.append(root.sedraVorgabe.block(this.ctx.api, (t, tone)=>this.ctx.shell.notify(t, tone), ()=>this.refresh()));
        box.append(vg);
      }

      const foreign = d().el('div', 't-modules-row');
      const foreignKind = this.kindSwitch();
      const folder = d().el('input');
      folder.placeholder = 'Ordner auf diesem Rechner – vollständiger Pfad';
      folder.setAttribute('aria-label', 'Ordner des fremden Moduls');
      foreign.append(d().el('b', null, 'Fremdes Modul vorlegen'),
                     d().el('small', 's-muted', 'Manifest, jede Datei mit Prüfsumme und die Durchsicht stehen danach in der Entscheidung. Eingebaut wird erst nach deiner Freigabe – und als COMMUNITY nur mit Leserouten.'),
                     foreignKind.el, folder,
                     d().button('Vorlegen', async()=>{
                       await this.ctx.api('/api/uix/install', {method: 'POST', body: {kind: foreignKind.kind(), source: folder.value.trim()}});
                       folder.value = '';
                       this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true});
                     }));
      box.append(foreign);

      const hint = d().el('small', 's-muted', 'Vorlagen liegen in: ' + (this.view.templates || []).join(' · '));
      box.append(hint);
      return box;
    },

    actions(){ return []; }      // die Handlungen stehen an den Zeilen, wo sie hingehören – nicht in der Verbenzeile
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraModulesPure = {TRUST, WHY, reason};
  if(typeof module !== 'undefined' && module.exports) module.exports = {TRUST, WHY, reason};
})();
