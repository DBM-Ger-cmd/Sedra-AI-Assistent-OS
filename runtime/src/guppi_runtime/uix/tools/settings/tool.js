// Werkzeug „Einstellungen“ – API-Einstellungen für Cloud-Modelle (Kern: jede Shell kann es öffnen).
// Gleiche Routen wie das Fenster der Desktop-Oberfläche. Ein Schlüssel wird nie angezeigt: nur der Zustand.
// Speichern wirkt nach dem nächsten Start.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const KEY_TEXT = {
    umgebung: 'Schlüssel: aus der Umgebungsvariable (wird nicht angezeigt)',
    gespeichert: 'Schlüssel: verschlüsselt gespeichert (Windows-Benutzer)',
    fehlt: 'Schlüssel: fehlt'
  };

  const tool = {
    id: 'settings',

    mount(el, ctx){
      this.el = el; this.ctx = ctx; this.msg = '';
      el.classList.add('t-set');
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-set'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let data;
      try{ data = await this.ctx.api('/api/cloud'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Einstellungen nicht lesbar: ' + err.message)); return; }
      this.draw(data);
    },

    draw(data){
      const box = d().el('div', 's-col');
      box.append(d().el('h5', 's-head', 'API-Einstellungen (Cloud-Modelle)'));
      box.append(d().el('div', 's-note', 'Standard: aus. Was den Rechner verlässt, prüft der Inhaltsschutz bei jedem Aufruf. Personenbezug wird vor dem Versand pseudonymisiert und anonymisiert. Änderungen wirken nach dem nächsten Start.'));
      if(data.error) box.append(d().el('div', 's-note bad', 'Fehler in der Konfiguration: ' + data.error));

      const master = d().el('label', 's-field');
      const masterBox = d().el('input'); masterBox.type = 'checkbox'; masterBox.id = 'settingsCloudMaster'; masterBox.checked = !!data.enabled;
      master.append(masterBox, ' Cloud-Modelle insgesamt einschalten');
      box.append(master);

      for(const p of data.providers){
        const card = d().el('div', 's-provider');
        card.dataset.provider = p.id;
        card.append(d().el('div', 's-head', p.id + ' (' + (p.kind === 'anthropic' ? 'Anthropic Messages API' : 'OpenAI-kompatibel') + ')'));

        const on = d().el('label', 's-field'); const onBox = d().el('input'); onBox.type = 'checkbox'; onBox.className = 'cp-enabled'; onBox.checked = !!p.enabled;
        on.append(onBox, ' Anbieter aktiv'); card.append(on);

        const model = d().el('input'); model.type = 'text'; model.className = 'cp-model'; model.value = p.default_model || ''; model.placeholder = 'Modellname des Anbieters'; model.maxLength = 120;
        card.append(d().el('label', 's-field', 'Modell'), model);

        const url = d().el('input'); url.type = 'text'; url.className = 'cp-url'; url.value = p.base_url; url.maxLength = 200;
        card.append(d().el('label', 's-field', 'Adresse (https)'), url);

        card.append(d().el('div', 's-small s-muted', KEY_TEXT[p.key] || ''));
        if(p.key_store_available){
          const pw = d().el('input'); pw.type = 'password'; pw.className = 'cp-key'; pw.autocomplete = 'off'; pw.placeholder = 'Neuer API-Schlüssel';
          const save = d().el('button', 'Schlüssel speichern'); save.type = 'button'; save.onclick = ()=>this.saveKey(p.id, pw.value);
          const del = d().el('button', 'Schlüssel löschen'); del.type = 'button'; del.onclick = ()=>this.clearKey(p.id);
          card.append(pw, save, del);
        } else {
          card.append(d().el('div', 's-small s-muted', 'Die verschlüsselte Ablage läuft nur unter Windows. Hier bleibt die Umgebungsvariable GUPPI_SECRET_' + p.id.toUpperCase().replace(/-/g, '_') + '_API_KEY.'));
        }
        box.append(card);
      }

      const saveAll = d().el('button', 'Einstellungen speichern'); saveAll.type = 'button'; saveAll.onclick = ()=>this.save();
      box.append(saveAll, d().el('div', 's-small s-muted', this.msg));
      this.el.replaceChildren(box);
    },

    collect(){
      const providers = {};
      this.el.querySelectorAll('.s-provider').forEach(card=>{
        providers[card.dataset.provider] = {
          enabled: card.querySelector('.cp-enabled').checked,
          default_model: card.querySelector('.cp-model').value.trim() || null,
          base_url: card.querySelector('.cp-url').value.trim()
        };
      });
      return {enabled: this.el.querySelector('#settingsCloudMaster').checked, providers};
    },

    async save(){
      try{
        await this.ctx.api('/api/cloud/save', {method: 'POST', body: JSON.stringify(this.collect())});
        this.msg = 'Gespeichert. Wirkt nach dem nächsten Start der Oberfläche.';
      }catch(err){ this.msg = 'Nicht gespeichert: ' + err.message; }
      await this.refresh();
    },

    async saveKey(provider, value){
      try{
        await this.ctx.api('/api/cloud/key', {method: 'POST', body: JSON.stringify({provider, value})});
        this.msg = 'Schlüssel für ' + provider + ' verschlüsselt gespeichert. Wirkt nach dem nächsten Start.';
      }catch(err){ this.msg = 'Schlüssel nicht gespeichert: ' + err.message; }
      await this.refresh();
    },

    async clearKey(provider){
      try{
        await this.ctx.api('/api/cloud/key', {method: 'POST', body: JSON.stringify({provider, clear: true})});
        this.msg = 'Schlüssel für ' + provider + ' gelöscht.';
      }catch(err){ this.msg = 'Nicht gelöscht: ' + err.message; }
      await this.refresh();
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
