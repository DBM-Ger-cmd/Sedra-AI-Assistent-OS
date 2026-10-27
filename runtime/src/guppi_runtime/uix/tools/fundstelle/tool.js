// Werkzeug „Fundstelle“ (SPEC_SHELL_WISSEN_v1 §4.2): der Nachweis neben dem Wissen. Ein Treffer im Werkzeug „Wissen“ sendet
// `wissen.auswahl {id, quelle}`; hier steht der Abschnitt im Zusammenhang – Datei bzw. Quelle, Stelle, Stand, Stufe, Personenbezug,
// der Abschnitt davor und danach, die Suchwörter der letzten Suche markiert. Kein Werkzeug kennt das andere: nur das Ereignis.
// Gelesen wird über POST /api/objects {type: 'wissen_abschnitt', id}; der Server prüft Stufe und Projekt wie bei der Suche.
// Gedächtnis (Vertrag 1.1): die Kennung des gezeigten Abschnitts in der Sitzung (kein Inhalt), der Text nie im Browser-Speicher.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const LEER = Object.freeze({get: (_n, v)=>v, set(){}, clear(){}});
  const MUSTER = /^W[0-9a-f]{10,16}$/;

  // was die Kopfzeile sagt (rein)
  function kopfText(a){
    if(!a) return '';
    return [a.datei, 'Stand ' + String(a.datum || '').slice(0, 10), 'Stufe ' + a.stufe, a.projekt ? 'Projekt ' + a.projekt : 'alle Projekte']
      .filter(Boolean).join(' · ');
  }
  // die Suchwörter markieren (rein, wie im Werkzeug Wissen): [{text, mark}]
  function teile(text, woerter){
    const Z = root.sedraWissenZitate;
    if(Z && Z.hervorheben) return Z.hervorheben(text, woerter || []);
    return [{text: String(text || ''), mark: false}];
  }

  const tool = {
    id: 'fundstelle',

    async mount(el, ctx){
      this.el = el; this.ctx = ctx; this.a = null; this.fehler = null; this.woerter = [];
      el.classList.add('t-fundstelle');
      this.sitzung = ctx.sitzung || LEER;
      ctx.bus.on('wissen.auswahl', e=>{ if(e && e.zweck !== 'gespraech') this.zeigen(e.id, e.woerter); });
      const o = ctx.object || {};
      const id = MUSTER.test(String(o.abschnitt || '')) ? o.abschnitt : this.sitzung.get('abschnitt', null);
      if(id) return this.zeigen(id);
      this.draw();
    },

    unmount(el){ (el || this.el).classList.remove('t-fundstelle'); (el || this.el).replaceChildren(); this.a = null; },

    async zeigen(id, woerter){
      if(!this.el || !MUSTER.test(String(id || ''))) return;
      if(Array.isArray(woerter)) this.woerter = woerter.slice(0, 12);
      this.sitzung.set('abschnitt', id);
      this.laedt = id; this.draw();
      try{
        const o = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'wissen_abschnitt', id}});
        this.a = o && o.abschnitt ? o.abschnitt : null; this.fehler = this.a ? null : 'Dieser Abschnitt ist nicht lesbar.';
      }catch(err){
        const m = String(err && err.message || err);
        this.a = null;
        this.fehler = m.indexOf('wis_abschnitt_unbekannt') >= 0 || m.indexOf('object_not_found') >= 0 ? 'Den Abschnitt [' + id + '] gibt es nicht mehr, oder er ist für dich nicht lesbar.'
                    : m.indexOf('unknown_object_type') >= 0 ? 'Der Wissensspeicher ist ausgeschaltet.' : 'Nicht lesbar: ' + m;
      }
      this.laedt = null;
      this.draw();
    },

    text(node, text){ teile(text, this.woerter).forEach(t=>node.append(t.mark ? d().el('mark', 't-fundstelle-mark', t.text) : t.text)); return node; },

    nachbar(n, wie){
      const box = d().el('div', 's-col t-fundstelle-nachbar');
      box.append(d().el('small', 's-muted', wie + ': ' + n.stelle));
      box.append(this.text(d().el('pre', 't-fundstelle-text klein'), n.text));
      const b = d().button('Zeigen', ()=>this.zeigen(n.id)); b.title = 'Diesen Abschnitt als Fundstelle zeigen'; box.append(b);
      return box;
    },

    draw(){
      if(!this.el) return;
      // Stufe 6 (S6-E5): ohne Abschnitt sagt die Fundstelle der Shell „leer“ – die Spalte klappt ein, solange alle Nachweise leer sind
      if(this.ctx.shell && this.ctx.shell.nachweisLeer) this.ctx.shell.nachweisLeer('fundstelle', !this.a && !this.laedt && !this.fehler);
      const box = d().el('div', 's-col');
      box.append(d().el('b', null, 'Fundstelle'));
      if(this.laedt){ box.append(d().el('div', 's-note', 'Lese [' + this.laedt + '] …')); return this.el.replaceChildren(box); }
      if(this.fehler){ box.append(d().el('div', 's-note warn', this.fehler)); return this.el.replaceChildren(box); }
      const a = this.a;
      if(!a){ box.append(d().empty('Wähle einen Treffer im Wissen – hier steht er dann im Zusammenhang, mit dem Abschnitt davor und danach.')); return this.el.replaceChildren(box); }
      box.append(d().el('div', 't-fundstelle-stelle', a.stelle));
      box.append(d().el('small', 's-muted', kopfText(a)));
      const marken = d().el('div', 's-row');
      marken.append(d().el('span', 't-fundstelle-marke', '[' + a.id + ']'));
      if(a.personenbezug) marken.append(d().el('span', 't-fundstelle-marke warn', 'Personenbezug – bleibt lokal'));
      if((a.befunde || []).length) marken.append(d().el('span', 't-fundstelle-marke bad', 'Befund: ' + a.befunde.join(', ')));
      box.append(marken);
      if(a.davor) box.append(this.nachbar(a.davor, 'davor'));
      box.append(this.text(d().el('pre', 't-fundstelle-text t-fundstelle-haupt'), a.text));
      if(a.danach) box.append(this.nachbar(a.danach, 'danach'));
      const row = d().el('div', 's-row t-fundstelle-knoepfe');
      row.append(d().button('Ins Gespräch übernehmen', ()=>{
        this.ctx.bus.emit('wissen.auswahl', {id: a.id, quelle: String(a.quelle), zweck: 'gespraech', stelle: String(a.stelle || '')});
      }, 'p'));
      row.append(d().button('Quelle zeigen', ()=>this.ctx.shell.open({type: 'wissen', id: 'speicher', title: 'Wissen', view: 'quellen', quelle: String(a.quelle)})));
      box.append(row);
      this.el.replaceChildren(box);
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  if(typeof module !== 'undefined' && module.exports) module.exports = {kopfText, teile, tool};
})();
