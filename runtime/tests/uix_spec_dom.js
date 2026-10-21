// Ein kleines Schein-DOM für die Werkzeug-Specs von Shell D (test.spec.js, Spec 4 D4.4): `node -r <diese Datei> test.spec.js`.
// Kein Browser, keine Bibliothek – genug, damit ein Werkzeug in einen leeren Container zeichnet und die Spec den Text prüft.
// Liegt unter tests/, nicht im Paket: der Browser lädt es nie. tests/test_uix_shell_d_pure.py lädt es vor jeder test.spec.js.
'use strict';

class ClassList {
  constructor(node){ this.node = node; }
  list(){ return String(this.node.className || '').split(/\s+/).filter(Boolean); }
  add(...names){ const l = this.list(); names.forEach(n=>{ if(!l.includes(n)) l.push(n); }); this.node.className = l.join(' '); }
  remove(...names){ this.node.className = this.list().filter(n=>!names.includes(n)).join(' '); }
  contains(name){ return this.list().includes(name); }
  toggle(name, force){ const on = force === undefined ? !this.contains(name) : !!force; on ? this.add(name) : this.remove(name); return on; }
}

class Node {
  constructor(tag){
    this.tagName = String(tag).toUpperCase(); this.children = []; this.parent = null; this.className = ''; this._text = '';
    this.dataset = {}; this.style = {}; this.attributes = {}; this.hidden = false; this.listeners = {}; this.value = '';
    this.classList = new ClassList(this);
  }
  get textContent(){ return this._text + this.children.map(c=>c.textContent).join(''); }
  set textContent(v){ this.children.forEach(c=>{ c.parent = null; }); this.children = []; this._text = String(v); }
  get innerText(){ return this.hidden ? '' : this._text + this.children.map(c=>c.innerText).join(' '); }
  get childElementCount(){ return this.children.length; }
  get firstChild(){ return this.children[0] || null; }
  _take(n){ if(typeof n === 'string'){ const t = new Node('#text'); t._text = n; n = t; } if(n.parent) n.remove(); n.parent = this; return n; }
  append(...nodes){ nodes.forEach(n=>this.children.push(this._take(n))); }
  appendChild(n){ this.append(n); return n; }
  prepend(...nodes){ this.children.unshift(...nodes.map(n=>this._take(n))); }
  replaceChildren(...nodes){ this.children.forEach(c=>{ c.parent = null; }); this.children = []; this._text = ''; this.append(...nodes); }
  remove(){ if(this.parent){ this.parent.children = this.parent.children.filter(c=>c !== this); this.parent = null; } }
  after(n){ if(!this.parent) return; const p = this.parent, i = p.children.indexOf(this); p.children.splice(i + 1, 0, p._take(n)); }
  setAttribute(k, v){ this.attributes[k] = String(v); }
  getAttribute(k){ return k in this.attributes ? this.attributes[k] : null; }
  removeAttribute(k){ delete this.attributes[k]; }
  addEventListener(name, fn){ (this.listeners[name] = this.listeners[name] || []).push(fn); }
  focus(){}
  scrollIntoView(){}
  closest(sel){ let n = this; while(n){ if(n.matches(sel)) return n; n = n.parent; } return null; }
  // Nur, was die Specs brauchen: `.klasse`, `tag`, `[data-x="y"]` und `tag.klasse`
  matches(sel){
    if(this.tagName === '#TEXT') return false;
    const m = /^([a-z0-9]*)((?:\.[A-Za-z0-9_-]+)*)(?:\[data-([a-z-]+)="([^"]*)"\])?$/.exec(sel.trim());
    if(!m) throw new Error('Schein-DOM kennt den Selektor nicht: ' + sel);
    if(m[1] && this.tagName !== m[1].toUpperCase()) return false;
    if(m[2] && !m[2].split('.').filter(Boolean).every(c=>this.classList.contains(c))) return false;
    if(m[3] && this.dataset[m[3].replace(/-([a-z])/g, (_x, c)=>c.toUpperCase())] !== m[4]) return false;
    return true;
  }
  querySelectorAll(sel){
    const out = [];
    const walk = n=>n.children.forEach(c=>{ if(c.matches(sel)) out.push(c); walk(c); });
    walk(this);
    return out;
  }
  querySelector(sel){ return this.querySelectorAll(sel)[0] || null; }
  // ein Klick wie im Browser: onclick des Knotens (dom.button fängt Fehler selbst ab)
  click(){ if(this.disabled) return undefined; if(this.onclick) return this.onclick({stopPropagation(){}, preventDefault(){}, target: this}); return undefined; }
}

globalThis.document = {createElement: tag=>new Node(tag), createTextNode: t=>{ const n = new Node('#text'); n._text = String(t); return n; }};
globalThis.confirm = ()=>true;

// Die Hilfen jeder Spec: ein Kontext mit Schein-API und Schein-Bus, und ein Warten, bis alle Versprechen durch sind
globalThis.specKit = {
  container(){ return new Node('div'); },
  context(object, answers){
    const calls = [], handlers = {}, opened = [];
    const api = async(path, options)=>{
      const body = (options || {}).body || null;
      calls.push({path, body});
      const answer = answers(path, body, calls.length);
      if(answer instanceof Error) throw answer;
      return JSON.parse(JSON.stringify(answer));
    };
    const bus = {on(name, fn){ (handlers[name] = handlers[name] || []).push(fn); return ()=>{}; }, emit(name, payload){ (handlers[name] || []).forEach(fn=>fn(payload || {})); }};
    const shell = {open(o){ opened.push(o); }, notify(){}};
    return {object, api, bus, shell, calls, opened, tokens: {}, manifest: {}};
  },
  settle: async()=>{ for(let i = 0; i < 20; i++) await new Promise(resolve=>setImmediate(resolve)); }
};
