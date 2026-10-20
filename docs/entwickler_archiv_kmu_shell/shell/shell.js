// Shell „KI Gateway für KMU“ – das Design der Präsentation (B6, 19.10.2026). Sie besitzt den Bildschirm: Kopf mit dem Ablauf,
// das Werkstück in der Mitte, das Gespräch unten. Sie kennt kein Werkzeug beim Namen: die Registrierung sagt, wer ein Objekt zeichnet.
// Nachweis-Werkzeuge (slot: nachweis) gehören hier nicht daneben – das Gateway zeigt seinen Überblick selbst.
// Farben nur über die Tokens (--kmu-…, ui/tokens.css). Die Grafik ist ein Ausschnitt aus der Präsentation (Lizenz laut Klaus geklärt).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  // der Ablauf aus Folie 6: vier Schritte und der Schluss; der Mensch entscheidet am Ende
  const ABLAUF = ['Aufgabe eingeben', 'Schutz prüfen', 'Entwurf erzeugen', 'Ergebnis prüfen', 'selbst entscheiden.'];

  root.sedra.registerShell({
    id: 'gateway-kmu',

    async start(ctx){
      this.ctx = ctx;
      const host = document.getElementById('sedra-root');
      host.classList.add('sh-gateway-kmu');
      host.replaceChildren();

      // Kopf: Marke, Titel, der Ablauf als Leiste. Der Ablauf zeigt nur, er ist keine Schaltfläche.
      const kopf = d().el('header', 'sh-gateway-kmu-kopf');
      const marke = d().el('div', 'sh-gateway-kmu-marke');
      marke.append(d().el('h1', 'sh-gateway-kmu-titel', 'KI Gateway für KMU'),
                   d().el('p', 'sh-gateway-kmu-sub', 'KI-Power. Mit Kontrolle.'),
                   d().el('p', 'sh-gateway-kmu-satz', 'Eine Aufgabe. Eine Oberfläche. Nachvollziehbare Kontrollpunkte.'));
      const ablauf = d().el('ol', 'sh-gateway-kmu-ablauf'); ablauf.setAttribute('aria-label', 'Ablauf');
      ABLAUF.forEach((schritt, i)=>{
        const li = d().el('li', 'sh-gateway-kmu-schritt', schritt);
        if(i < ABLAUF.length - 1) li.dataset.pfeil = '→';
        ablauf.append(li);
      });
      const bild = d().el('img', 'sh-gateway-kmu-grafik');
      bild.src = '/uix/shells/gateway-kmu/kmu-grafik.png';
      bild.alt = '';                                     // dekorativ: der Titel sagt alles
      kopf.append(bild, marke, ablauf);

      // Das Werkstück: Verben oben, darunter das Werkzeug des Objekts
      this.body = d().el('section', 'sh-gateway-kmu-body');
      this.verbs = d().el('div', 'sh-gateway-kmu-verbs');
      this.verbs.dataset.verbs = '';
      this.body.append(this.verbs);
      this.werkstueck = d().el('div', 'sh-gateway-kmu-werkstueck');
      this.body.append(this.werkstueck);

      // Das Gespräch unten: ein Werkzeug, in einer Zone, die man hochscrollen kann (max. Höhe, eigener Rollbalken)
      const talk = ctx.tools.all().find(t=>t.id === 'talk');
      const gespraech = d().el('footer', 'sh-gateway-kmu-talk');
      host.append(kopf, this.body, gespraech);
      if(talk){
        root.sedraLifecycle.mountTool(ctx.tools.mod('talk'), gespraech, ctx.makeContext(talk, null, this.shellApi()), ctx.onProblem);
      }

      ctx.bus.on('object.open', o=>this.open(o));
      this.open({type: 'gateway', id: 'alle', title: 'KI Gateway', collection: true});
    },

    // Was ein Werkzeug von der Shell bekommt: einen Weg zum Öffnen, einen zum Melden, einen zum Entscheiden.
    shellApi(){
      return {open: o=>this.open(o), notify: text=>console.info('[shell]', text),
              decide: (id, way)=>this.ctx.api('/api/decisions/answer', {method: 'POST', body: {id, way}}),
              reload: ()=>location.reload()};
    },

    open(object){
      if(!object) return;
      this.werkstueck.replaceChildren();
      // Nachweise (slot nachweis) bleiben weg: diese Shell zeigt das Werkstück
      const tools = this.ctx.tools.for(object.type).filter(m=>m.slot !== 'nachweis');
      if(!tools.length){ this.werkstueck.append(d().empty('Kein Werkzeug für „' + object.type + '“.')); return; }
      (this.mounted || []).forEach(s=>root.sedraLifecycle.unmountTool(s, this.ctx.onProblem));
      this.mounted = tools.map(manifest=>{
        const slot = d().el('div', 'sh-gateway-kmu-tool');
        slot.dataset.tool = manifest.id;             // Vertragsmarke: so findet die Abnahme den Container jedes Werkzeugs
        this.werkstueck.append(slot);
        return root.sedraLifecycle.mountTool(this.ctx.tools.mod(manifest.id), slot,
                                             this.ctx.makeContext(manifest, object, this.shellApi()), this.ctx.onProblem);
      });
      // erst fragen, wenn gezeichnet ist – vorher weiß ein Werkzeug noch nicht, welche Handlungen sein Objekt hat
      Promise.all(this.mounted.map(s=>s.ready)).then(()=>this.drawVerbs()).catch(()=>this.drawVerbs());
    },

    drawVerbs(){
      this.verbs.replaceChildren();
      (this.mounted || []).forEach(state=>{
        root.sedraLifecycle.actionsOf(state).forEach(a=>this.verbs.append(d().button(a.label, async()=>{ await a.run(); this.drawVerbs(); })));
      });
    }
  });
})();
