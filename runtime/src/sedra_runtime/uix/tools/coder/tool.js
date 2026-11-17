// Werkzeug „Coder“: die Sedra IDE (VSC-ähnliche Entwicklungsoberfläche, Entwurf mit Beispieldaten).
// Läuft im abgeschotteten Rahmen (trust CAPTAIN, Stufe C): kein Token, keine Route, kein Netz. Alle Inhalte sind Beispieldaten im Speicher der Seite.
// tool.js steht zuletzt in der Ladereihenfolge: es baut das Gerüst und startet die IDE (start.js setzt SIDE.starte).

(function(){
  const root = window;

  function geruest(el){
    const mk = (tag, id, attr)=>{ const e = document.createElement(tag); if(id) e.id = id; Object.keys(attr || {}).forEach(k=>e.setAttribute(k, attr[k])); return e; };
    const teiler = (id, richtung)=>mk('div', id, {'class': 'teiler ' + (richtung === 'v' ? 'teiler-v' : 'teiler-h'), role: 'separator', 'aria-orientation': richtung === 'v' ? 'vertical' : 'horizontal', tabindex: '0'});
    const sprung = mk('a', 'sprung', {'class': 'sprung', href: '#editorbereich'}); sprung.textContent = 'Zum Editor springen';
    const mitte = mk('main', 'mitte');
    mitte.append(mk('div', 'editorbereich', {tabindex: '-1'}), teiler('teiler-panel', 'h'), mk('section', 'panel'));
    const haupt = mk('div', 'haupt');
    haupt.append(mk('nav', 'aktivleiste'), mk('aside', 'seite-links'), teiler('teiler-links', 'v'), mitte, teiler('teiler-rechts', 'v'), mk('aside', 'seite-rechts'));
    const palette = mk('div', 'palette'); palette.hidden = true;
    const meldung = mk('div', 'meldung', {role: 'status', 'aria-live': 'polite'});
    el.replaceChildren(sprung, mk('header', 'kopf'), haupt, mk('footer', 'status'), palette, meldung);
  }

  const tool = {
    id: 'coder',
    mount(el){
      this.el = el;
      el.classList.add('t-coder');            // die Rahmen-Seite ist ein eigenes Dokument: die Wurzel der IDE ist dieser Container
      document.body.style.margin = '0';
      root.SIDE.wurzel = el;
      geruest(el);
      root.SIDE.starte();
    },
    unmount(){ if(this.el) this.el.replaceChildren(); },
    actions(){ return []; }
  };

  root.sedra.registerTool(tool);
})();
