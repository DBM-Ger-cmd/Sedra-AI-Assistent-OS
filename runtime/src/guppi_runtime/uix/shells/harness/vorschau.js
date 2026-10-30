// Harness-Shell – die Vorschau neben dem Gespräch (SPEC_HARNESS_SHELL_v1 Stufe 6, HS-70 bis HS-75; G2 §3). Ein Sitzungsreiter hat zwei Hälften: das Gespräch (rechts) und die
// Vorschau (links) mit dem Objekt, um das es gerade geht – Datei, Freigabe-Karte oder Lauf. „Tauschen“ vertauscht die Seiten, „Festhalten“ hält das Objekt fest, „Zuklappen“ gibt dem
// Gespräch die ganze Breite. Die Vorschau liest nur (GET /api/harness/vorschau und die vorhandenen Lesewege) und ändert nichts. Inhalte sind fremder Text: nur textContent, nie HTML.
// Zustand je Sitzung nur im Browser (localStorage `sedra.harness.vorschau`: Seite, zu, Breite, Pin – nie Inhalt).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const H = ()=>root.sedraHarness;
  const KEY = 'sedra.harness.vorschau';
  const ID = /^S-[0-9A-F]{8}$/;
  const SCHMAL = 1100;                 // darunter nur eine Fläche (HS-74)
  const MIN_PX = 420;
  const DATEIEN = ['datei_schreiben', 'datei_aendern', 'datei_lesen'];

  function alle(){ try{ return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; }catch(_e){ return {}; } }
  function klemmen(p, breite){
    const grenze = breite > 0 ? Math.min(45, MIN_PX / breite * 100) : 25;
    return Math.max(grenze, Math.min(100 - grenze, Number(p) || 50));
  }
  function zustand(id){
    const z = ID.test(id) ? (alle()[id] || {}) : {};
    return {seite: z.seite === 'rechts' ? 'rechts' : 'links', zu: !!z.zu, breite: Number(z.breite) || 50, pin: z.pin && typeof z.pin.ref === 'string' ? z.pin : null};
  }
  function merken(t){
    if(!ID.test(t.a.id)) return;
    try{ const a = alle(); a[t.a.id] = {seite: t.z.seite, zu: t.z.zu, breite: Math.round(t.z.breite), pin: t.z.pin}; localStorage.setItem(KEY, JSON.stringify(a)); }catch(_e){}
  }

  const zeile = (text, cls)=>d().el('div', cls || 'hs-leise', text);

  // ---- Fläche je Ansicht (a._teilung); die Ansicht des Gesprächs bleibt unverändert darin
  function fuer(S, a){
    if(a._teilung) return a._teilung;
    const t = {S, a, obj: null, n: 0, z: zustand(a.id), zeige: 'gespraech', hinweisGezeigt: false};
    t.el = d().el('div', 'hs-teilung hs-fl-ohne');
    t.leiste = d().el('div', 'hs-fl-leiste');
    t.gesp = d().el('div', 'hs-fl-gespraech'); t.gesp.append(a.box);
    t.balken = d().el('div', 'hs-fl-balken'); t.balken.setAttribute('role', 'separator'); t.balken.setAttribute('aria-orientation', 'vertical');
    t.balken.setAttribute('aria-label', 'Breite der Vorschau'); t.balken.tabIndex = 0;
    t.vor = d().el('div', 'hs-fl-vorschau'); t.vor.setAttribute('aria-label', 'Vorschau');
    t.kopf = d().el('div', 'hs-fl-kopf'); t.titel = d().el('span', 'hs-fl-titel', ''); t.inhalt = d().el('div', 'hs-fl-inhalt');
    t.pinKnopf = knopf('📌', 'Festhalten', ()=>festhalten(t), 'hs-fl-pin');
    t.vor.append(t.kopf, t.inhalt);
    t.kopf.append(t.titel, t.pinKnopf, knopf('⇄', 'Seiten tauschen (Strg+Umschalt+X)', ()=>tauschen(S, t)), knopf('✕', 'Vorschau zuklappen', ()=>zuklappen(t, true)));
    t.auf = knopf('Vorschau', 'Vorschau wieder öffnen', ()=>zuklappen(t, false), 'hs-fl-auf');
    t.gesp.append(t.auf);
    t.umschalter = [knopf('Gespräch', 'Gespräch zeigen', ()=>klein(t, 'gespraech')), knopf('Vorschau', 'Vorschau zeigen', ()=>klein(t, 'vorschau'))];
    t.leiste.append(...t.umschalter);
    t.el.append(t.leiste, t.gesp, t.balken, t.vor);
    balkenBedienen(t);
    t.pruefeBreite = ()=>anwenden(t);
    a._teilung = t;
    anwenden(t);
    if(t.z.pin){ t.hinweisGezeigt = true; setzen(t, {typ: t.z.pin.typ, ref: t.z.pin.ref, grund: t.z.pin.grund || 'festgehalten'}, true); }          // ein festgehaltenes Objekt bleibt nach dem Neuladen
    return t;
  }

  function knopf(text, titel, tat, cls){
    const b = d().el('button', 'hs-fl-knopf' + (cls ? ' ' + cls : ''), text); b.type = 'button'; b.title = titel; b.setAttribute('aria-label', titel);
    b.onclick = e=>{ e.stopPropagation(); tat(); };
    return b;
  }

  // ---- Aufbau und Maße
  function anwenden(t){
    const schmal = root.innerWidth < SCHMAL;
    const sichtbar = !!t.obj && !t.z.zu;
    t.el.classList.toggle('hs-fl-ohne', !sichtbar);
    t.el.classList.toggle('hs-fl-klein', schmal && sichtbar);
    t.el.classList.toggle('hs-fl-zeige-vorschau', schmal && t.zeige === 'vorschau');
    t.el.dataset.seite = t.z.seite;
    t.auf.hidden = !t.obj || !t.z.zu;
    t.umschalter.forEach((b, i)=>b.classList.toggle('on', (i === 0) === (t.zeige === 'gespraech')));
    const b = klemmen(t.z.breite, t.el.clientWidth || root.innerWidth);
    t.z.breite = b;
    t.el.style.gridTemplateColumns = t.z.seite === 'links' ? `${b}% 6px minmax(0, 1fr)` : `minmax(0, 1fr) 6px ${b}%`;
    t.vor.style.order = t.z.seite === 'links' ? 0 : 2; t.balken.style.order = 1; t.gesp.style.order = t.z.seite === 'links' ? 2 : 0;
    t.balken.setAttribute('aria-valuenow', String(Math.round(b)));
    const fest = t.z.pin && t.obj && t.z.pin.ref === t.obj.ref;
    t.pinKnopf.classList.toggle('on', !!fest); t.pinKnopf.title = fest ? 'Festhalten lösen' : 'Festhalten';
  }

  function balkenBedienen(t){
    const setzen = prozent=>{ t.z.breite = klemmen(prozent, t.el.clientWidth); anwenden(t); merken(t); };
    t.balken.addEventListener('pointerdown', e=>{
      e.preventDefault();
      const rect = t.el.getBoundingClientRect();
      const bewegen = ev=>{ const x = (ev.clientX - rect.left) / rect.width * 100; setzen(t.z.seite === 'links' ? x : 100 - x); };
      const ende = ()=>{ root.removeEventListener('pointermove', bewegen); root.removeEventListener('pointerup', ende); };
      root.addEventListener('pointermove', bewegen); root.addEventListener('pointerup', ende);
    });
    t.balken.addEventListener('keydown', e=>{
      const pfeil = {ArrowLeft: -5, ArrowRight: 5}[e.key];
      if(pfeil === undefined) return;
      e.preventDefault(); setzen(t.z.breite + (t.z.seite === 'links' ? pfeil : -pfeil));
    });
  }

  function tauschen(S, t){
    t = t || (S.aktive() && S.aktive()._teilung); if(!t) return;
    t.z.seite = t.z.seite === 'links' ? 'rechts' : 'links'; anwenden(t); merken(t);
  }
  function zuklappen(t, zu){ t.z.zu = zu; anwenden(t); merken(t); }
  function klein(t, was){ t.zeige = was; anwenden(t); }
  function festhalten(t){
    if(!t.obj) return;
    t.z.pin = t.z.pin && t.z.pin.ref === t.obj.ref ? null : {typ: t.obj.typ, ref: t.obj.ref, grund: t.obj.grund};
    anwenden(t); merken(t);
  }

  // ---- das Objekt
  function setzen(t, obj, erzwingen){
    if(!erzwingen && t.z.pin && !(obj.typ === t.z.pin.typ && obj.ref === t.z.pin.ref)) return;       // festgehalten: es folgt nicht mehr
    const neu = !t.obj;
    t.obj = obj;
    if(neu && !t.hinweisGezeigt && !t.z.zu){ t.hinweisGezeigt = true; t.S.hinweis('Hier erscheint, woran ich arbeite.'); }
    anwenden(t);
    zeichnen(t);
  }

  async function zeichnen(t){
    const n = ++t.n, o = t.obj;
    t.titel.textContent = (TYP[o.typ] || '') + (o.ref ? ' ' + o.ref : '') + (o.grund ? ' – ' + o.grund : '');
    t.inhalt.replaceChildren(zeile('lädt …'));
    let knoten;
    try{ knoten = await INHALT[o.typ](t.S, t.a, o); }
    catch(err){ knoten = [zeile('Nicht lesbar: ' + err.message, 'hs-leise bad')]; }
    if(n === t.n) t.inhalt.replaceChildren(...knoten);
  }

  const TYP = {datei: 'Datei', karte: 'Karte', lauf: 'Lauf'};
  const INHALT = {
    async datei(S, a, o){
      const out = await S.api('/api/harness/vorschau?sitzung=' + encodeURIComponent(a.id) + '&pfad=' + encodeURIComponent(o.ref));
      if(out.status === 'gesperrt') return [zeile('Nicht anzeigbar: ' + (out.grund || 'der Katalog lässt das Lesen nicht zu.'))];
      if(out.status === 'binaer') return [zeile('Binärdatei, ' + out.groesse + ' Bytes.')];
      if(out.status === 'fehlt') return [zeile('Die Datei gibt es (noch) nicht.')];
      const kopf = zeile(out.zeilen + ' Zeilen' + (out.gekuerzt ? ' (gekürzt, ' + out.groesse + ' Bytes gesamt)' : ''));
      let inhalt;
      if(/\.(md|markdown)$/i.test(o.ref) && H().markdown){ try{ inhalt = H().markdown.render(out.text); }catch(_e){ inhalt = null; } }
      return [kopf, inhalt || d().el('pre', 'hs-pre', out.text)];
    },
    async karte(S, a, o){
      const k = await S.api('/api/harness/karten/' + encodeURIComponent(o.ref));
      return [zeile((k.werkzeug || '') + ' · ' + (k.ziel || '') + ' · ' + (k.zustand || k.status || '')), zeile(k.begruendung || ''), d().el('pre', 'hs-pre', String(k.vorschau || ''))];
    },
    async lauf(S, a, o){
      const l = await S.api('/api/harness/laeufe/' + encodeURIComponent(o.ref));
      const log = Array.isArray(l.log) ? l.log.join('\n') : String(l.log || '');
      return [zeile((l.name || l.lauf || '') + ' · ' + (l.status || '') + (l.fortschritt && l.fortschritt.text ? ' · ' + l.fortschritt.text : '')), d().el('pre', 'hs-pre', log)];
    }
  };

  // ---- Auslöser (aus den vorhandenen Ereignissen der Sitzung; kein Polling)
  function beruehrt(S, a, name, args, status){
    if(!a || !DATEIEN.includes(name) || !args || typeof args.pfad !== 'string' || !args.pfad) return;
    if(name !== 'datei_lesen' && (status === 'abgelehnt' || status === 'fehler')) return;
    setzen(fuer(S, a), {typ: 'datei', ref: args.pfad, grund: name === 'datei_lesen' ? 'eben gelesen' : 'eben geändert'});
  }
  function karte(S, a, k){
    if(a && k && k.karte_id) setzen(fuer(S, a), {typ: 'karte', ref: k.karte_id, grund: 'wartet auf Freigabe'});
  }
  function lauf(S, e){
    const a = e && e.sitzung_id ? S.ansichten.get(e.sitzung_id) : null;
    if(!a) return;
    const t = fuer(S, a);
    if(t.obj && t.obj.typ === 'lauf' && t.obj.ref === e.id){ zeichnen(t); return; }
    setzen(t, {typ: 'lauf', ref: e.id, grund: e.zustand === 'gestartet' ? 'gestartet' : (e.status || '')});
  }
  // Ein Klick auf eine Werkzeugzeile mit Datei oder auf einen Dateinamen öffnet das Objekt in der Vorschau und hält es fest (HS-72).
  function oeffnen(S, a, pfad){
    const t = fuer(S, a);
    t.z.zu = false; t.z.pin = {typ: 'datei', ref: pfad, grund: 'festgehalten'}; merken(t);
    setzen(t, {typ: 'datei', ref: pfad, grund: 'festgehalten'}, true);
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.vorschau = {fuer, beruehrt, karte, lauf, oeffnen, tauschen, anwenden, zustand, klemmen};
})();
