// Harness-Shell – die App „Desktop Builder“ (Captain 05.11.2026: Sedra XP und der Retro-Desktop werden nicht weiterentwickelt, die Harness wird der zentrale Punkt; hier sammelt sich,
// wie die Oberfläche aufgebaut ist, und hier legt der Captain fest, was angezeigt wird und wo). Drei Reiter: Module (die Landkarte der Oberfläche aus kontext.js, jedes Modul mit
// „Im Chat anpassen“), Start-Menü (welche Apps, in welcher Gruppe) und Taskleiste (welche Zellen, in welcher Reihenfolge). Gespeichert wird über desktop.js (POST /api/harness/desktop);
// leer heißt die Vorgabe der Shell, „Auf Vorgabe zurücksetzen“ nimmt die Wahl wieder zurück. Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const H = ()=>root.sedraHarness;
  const ID = 'builder:';
  const REITER = [['module', 'Module'], ['start', 'Start-Menü'], ['taskleiste', 'Taskleiste'], ['profile', 'Profile und Marke']];

  function oeffnen(S){ H().reiter.aktivieren(S, ID); return ID; }
  const istReiter = id=>String(id).startsWith(ID);

  const satz = text=>d().el('div', 'hs-app-satz', text);
  function meldung(box, text, schlecht){ box.textContent = text; box.classList.toggle('bad', !!schlecht); }

  // ---- Module: die Landkarte der Oberfläche
  function module(S, feld){
    const K = H().kontext;
    feld.append(satz('So ist die Oberfläche der Harness aufgebaut: jedes Modul meldet sich mit Namen, Selektor und Dateien an (kontext.js, kontextmodule.js). Ein Rechtsklick auf etwas in Sedra zeigt dasselbe an der Stelle; „Im Chat anpassen“ legt das Modul als Entwurf ins Eingabefeld.'));
    if(!K){ feld.append(d().el('small', 'hs-leise', 'Das Kontextmenü ist nicht geladen.')); return; }
    const liste = K.liste();
    feld.append(d().el('div', 'hs-hw-kopf', liste.length + ' Module'));
    liste.forEach(m=>{
      const z = d().el('div', 'hs-einst-zeile hs-builder-modul'); z.dataset.modul = m.id;
      z.append(d().el('b', 'hs-einst-label', m.titel), d().el('code', 'hs-einst-wert', m.dateien.join(', ') || '–'), d().el('small', 'hs-leise', m.selektor));
      const k = d().button('Im Chat anpassen', ()=>K.modulAnpassen(S, m.id));
      k.classList.add('hs-klein'); z.append(k);
      feld.append(z);
    });
  }

  // ---- Start-Menü: welche Apps, in welcher Gruppe
  function startApps(S){
    const st = S._start, L = root.sedraStartliste;
    if(!st || !st.konfig || !L) return null;
    return L.bauen(root.sedraPlaces.PLACES, (st.module && st.module.tools) || [], o=>S.ctx.tools.forObject(o), st.konfig, []).apps;
  }
  function start(S, feld){
    const D = H().desktop, L = root.sedraStartliste;
    feld.append(satz('Welche Apps das Start-Menü zeigt und in welcher Gruppe sie stehen. Ausblenden ist nur Zuschnitt: die App bleibt erreichbar (Suche, Befehle) und wird dadurch nicht gesperrt – das macht die Richtlinie eines Betreibers. Posteingang und Aufgaben bleiben immer. Leer heißt die Vorgabe der Shell.'));
    const apps = startApps(S);
    if(!apps){ feld.append(d().el('small', 'hs-leise', 'Das Start-Menü ist noch nicht geladen – öffne es einmal (Start).')); return; }
    const w = D.wahl(S).start;
    const aus = new Set(w.ausblenden), gruppe = Object.assign({}, w.zuordnung);
    apps.forEach(a=>{
      const z = d().el('div', 'hs-einst-zeile hs-builder-app'); z.dataset.app = a.id;
      const haken = d().el('input'); haken.type = 'checkbox'; haken.checked = !aus.has(a.id); haken.setAttribute('aria-label', a.label + ' im Menü zeigen');
      if(D.GRUND_START.includes(a.id)){ haken.checked = true; haken.disabled = true; haken.title = 'Grundfunktion: bleibt immer erreichbar'; }
      haken.onchange = ()=>{ if(haken.checked) aus.delete(a.id); else aus.add(a.id); };
      const wahl = d().el('select', 'hs-projektwahl'); wahl.setAttribute('aria-label', 'Gruppe von ' + a.label);
      L.GRUPPEN.forEach(g=>{ const o = document.createElement('option'); o.value = g; o.textContent = L.TITEL[g]; wahl.append(o); });
      wahl.value = gruppe[a.id] || a.gruppe;
      wahl.onchange = ()=>{ gruppe[a.id] = wahl.value; };
      z.append(haken, d().el('b', 'hs-einst-label', a.label), d().el('small', 'hs-leise', a.hint || ''), wahl);
      feld.append(z);
    });
    const meld = d().el('div', 'hs-leise');
    const sichern = d().button('Speichern', async ()=>{
      const basis = {}; apps.forEach(a=>{ basis[a.id] = a.gruppe; });
      const abweichend = {}; Object.keys(gruppe).forEach(id=>{ if(basis[id] !== undefined && gruppe[id] !== basis[id]) abweichend[id] = gruppe[id]; });
      try{ await D.speichern(S, {start: {ausblenden: [...aus], zuordnung: abweichend}}); meldung(meld, 'Gespeichert – das Start-Menü ist angepasst.'); }
      catch(err){ meldung(meld, 'Nicht gespeichert: ' + err.message, true); }
    });
    const zurueck = d().button('Auf Vorgabe zurücksetzen', async ()=>{
      try{ await D.speichern(S, {start: null}); meldung(meld, 'Die Vorgabe der Shell gilt wieder.'); zeigen(S, 'start'); }
      catch(err){ meldung(meld, 'Nicht zurückgesetzt: ' + err.message, true); }
    });
    feld.append(d().el('div', 'hs-builder-aktion'), meld);
    feld.lastChild.previousSibling.append(sichern, zurueck);
  }

  // ---- Taskleiste: welche Zellen, in welcher Reihenfolge
  function taskleiste(S, feld){
    const D = H().desktop;
    feld.append(satz('Welche Zellen die Taskleiste zeigt und in welcher Reihenfolge. Eine Zelle ohne Wert bleibt ohnehin leer ausgeblendet. Die Wahl gilt sofort nach „Speichern“.'));
    const w = D.wahl(S).zellen;
    const namen = {}; D.ZELLEN.forEach(([k, n])=>{ namen[k] = n; });
    const alle = D.ZELLEN.map(([k])=>k);
    let reihe = w.reihenfolge.filter(k=>alle.includes(k)).concat(alle.filter(k=>!w.reihenfolge.includes(k)));
    const aus = new Set(w.ausblenden);
    const liste = d().el('div', 'hs-liste');
    const meld = d().el('div', 'hs-leise');
    const zeichne = ()=>{
      liste.replaceChildren(...reihe.map((k, i)=>{
        const z = d().el('div', 'hs-einst-zeile hs-builder-zelle'); z.dataset.zelle = k;
        const haken = d().el('input'); haken.type = 'checkbox'; haken.checked = !aus.has(k); haken.setAttribute('aria-label', namen[k] + ' zeigen');
        if(D.GRUND_ZELLEN.includes(k)){ haken.checked = true; haken.disabled = true; haken.title = 'Grundfunktion: bleibt immer erreichbar'; }
        haken.onchange = ()=>{ if(haken.checked) aus.delete(k); else aus.add(k); };
        const hoch = d().button('↑', ()=>{ if(i > 0){ [reihe[i - 1], reihe[i]] = [reihe[i], reihe[i - 1]]; zeichne(); } }); hoch.disabled = i === 0; hoch.setAttribute('aria-label', namen[k] + ' nach vorn');
        const runter = d().button('↓', ()=>{ if(i < reihe.length - 1){ [reihe[i + 1], reihe[i]] = [reihe[i], reihe[i + 1]]; zeichne(); } }); runter.disabled = i === reihe.length - 1; runter.setAttribute('aria-label', namen[k] + ' nach hinten');
        z.append(haken, d().el('b', 'hs-einst-label', namen[k]), hoch, runter);
        return z;
      }));
    };
    zeichne();
    const sichern = d().button('Speichern', async ()=>{
      try{ await D.speichern(S, {zellen: {ausblenden: [...aus], reihenfolge: reihe}}); meldung(meld, 'Gespeichert – die Taskleiste ist angepasst.'); }
      catch(err){ meldung(meld, 'Nicht gespeichert: ' + err.message, true); }
    });
    const zurueck = d().button('Auf Vorgabe zurücksetzen', async ()=>{
      try{ await D.speichern(S, {zellen: null}); meldung(meld, 'Die Vorgabe der Shell gilt wieder.'); zeigen(S, 'taskleiste'); }
      catch(err){ meldung(meld, 'Nicht zurückgesetzt: ' + err.message, true); }
    });
    const aktion = d().el('div', 'hs-builder-aktion'); aktion.append(sichern, zurueck);
    feld.append(liste, aktion, meld);
  }

  // ---- Profile und Marke: ein Zuschnitt je Auftraggeber (wie die KMU-Shell, ohne eigene Shell)
  function profile(S, feld){
    const D = H().desktop, w = D.wahl(S);
    feld.append(satz('Ein Profil ist ein benannter Zuschnitt der Oberfläche für einen Auftraggeber: Start-Menü, Taskleiste und Marke. Profile lassen sich speichern, anwenden, exportieren und importieren. Das ist nur der Zuschnitt der Oberfläche; Rechte und erlaubte Apps eines Betreibers sind die Richtlinie und stehen nicht hier.'));
    const meld = d().el('div', 'hs-leise');
    const tun = (text, fn)=>async()=>{ try{ await fn(); meldung(meld, text); zeigen(S, 'profile'); }catch(err){ meldung(meld, 'Nicht möglich: ' + err.message, true); } };
    const eingabe = (label, wert, ph)=>{ const e = d().el('input', 'hs-einst-zahl'); e.type = 'text'; e.value = wert || ''; e.placeholder = ph || ''; e.setAttribute('aria-label', label); return e; };
    // Marke
    feld.append(d().el('h3', 'hs-ueber', 'Marke'));
    const name = eingabe('Name der Marke', w.marke.name, 'Name im Titel des Fensters');
    const farbe = d().el('input'); farbe.type = 'color'; farbe.value = w.marke.akzent || '#3b82f6'; farbe.setAttribute('aria-label', 'Akzentfarbe');
    const farbeAn = d().el('input'); farbeAn.type = 'checkbox'; farbeAn.checked = !!w.marke.akzent; farbeAn.setAttribute('aria-label', 'Akzentfarbe verwenden');
    const marke = d().el('div', 'hs-einst-zeile'); marke.append(name, farbeAn, d().el('small', 'hs-leise', 'Akzentfarbe'), farbe,
      d().button('Marke speichern', tun('Marke gespeichert.', ()=>D.speichern(S, {marke: {name: name.value, akzent: farbeAn.checked ? farbe.value : ''}}))));
    feld.append(marke);
    // Aktuelle Anordnung als Profil
    feld.append(d().el('h3', 'hs-ueber', 'Aktuelle Anordnung als Profil speichern'));
    const pid = eingabe('Kennung des Profils', '', 'kennung, z. B. muster-gmbh'), pn = eingabe('Name des Profils', w.marke.name, 'Name'), pa = eingabe('Auftraggeber', '', 'Auftraggeber'), pb = eingabe('Beschreibung', '', 'wofür');
    const neu = d().el('div', 'hs-einst-zeile'); neu.append(pid, pn, pa, pb, d().button('Als Profil speichern',
      tun('Profil gespeichert.', ()=>D.aktion(S, {aktion: 'profil_speichern', id: pid.value.trim(), name: pn.value, auftraggeber: pa.value, beschreibung: pb.value}))));
    feld.append(neu);
    // Vorhandene Profile
    feld.append(d().el('h3', 'hs-ueber', 'Profile (' + w.profile.length + ')' + (w.profil ? ' · gilt: ' + w.profil : '')));
    const text = d().el('textarea', 'hs-builder-json'); text.rows = 8; text.placeholder = 'Hier erscheint ein exportiertes Profil; zum Importieren ein Profil einfügen.'; text.setAttribute('aria-label', 'Profil als JSON');
    if(!w.profile.length) feld.append(d().el('small', 'hs-leise', 'Noch kein Profil gespeichert.'));
    w.profile.forEach(p=>{
      const z = d().el('div', 'hs-einst-zeile hs-builder-profil'); z.dataset.profil = p.id;
      z.append(d().el('b', 'hs-einst-label', p.name), d().el('small', 'hs-leise', [p.id, p.auftraggeber, p.beschreibung].filter(Boolean).join(' · ')),
        d().button('Anwenden', tun('Das Profil gilt jetzt.', ()=>D.aktion(S, {aktion: 'profil_anwenden', id: p.id}))),
        d().button('Exportieren', async ()=>{ try{ text.value = JSON.stringify(await S.api('/api/harness/desktop?profil=' + encodeURIComponent(p.id)), null, 1); meldung(meld, 'Exportiert – Text kopieren und weitergeben.'); }catch(err){ meldung(meld, 'Nicht exportiert: ' + err.message, true); } }),
        d().button('Löschen', tun('Profil gelöscht.', ()=>D.aktion(S, {aktion: 'profil_loeschen', id: p.id}))));
      feld.append(z);
    });
    feld.append(text, d().button('Profil aus dem Text importieren', tun('Profil importiert.', ()=>{
      let p; try{ p = JSON.parse(text.value); }catch(_e){ throw new Error('der Text ist kein gültiges Profil (JSON)'); }
      return D.aktion(S, {aktion: 'profil_importieren', profil: p});
    })), meld);
  }

  // ---- die Ansicht (verlauf.js → hier): Kopf, Reiter, Feld
  const FELDER = {module, start, taskleiste, profile};
  function zeigen(S, name){
    const st = S._builder; if(!st) return;
    st.name = name; S._builderReiter = name;
    st.knoepfe.forEach((k, n)=>{ k.classList.toggle('on', n === name); k.setAttribute('aria-selected', n === name ? 'true' : 'false'); });
    st.feld.replaceChildren();
    FELDER[name](S, st.feld);
  }

  function ansicht(S, id){
    const box = d().el('div', 'hs-verlauf hs-builder');
    const kopf = d().el('h2', 'hs-diff-titel', 'Desktop Builder');
    const leiste = d().el('div', 'hs-app-reiter'); leiste.setAttribute('role', 'tablist');
    const feld = d().el('div', 'hs-einst-seite hs-builder-feld');
    const knoepfe = new Map();
    REITER.forEach(([n, text])=>{
      const b = d().el('button', 'hs-app-reiter-knopf', text); b.type = 'button'; b.setAttribute('role', 'tab'); b.dataset.reiter = n; b.onclick = ()=>zeigen(S, n);
      knoepfe.set(n, b); leiste.append(b);
    });
    box.append(kopf, leiste, feld);
    S._builder = {feld, knoepfe, name: null};
    const a = H().reiter.stub(id, box, S, {abbauen(){ S._builder = null; }});
    zeigen(S, S._builderReiter || 'module');
    return a;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.builder = {oeffnen, ansicht, istReiter, ID};
})();
