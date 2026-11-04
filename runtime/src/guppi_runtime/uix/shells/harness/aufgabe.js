// Harness-Shell – Aufgaben-Freigaben (SPEC_HARNESS_SHELL_v1 HS-27, HS-29; G3 Stufe 3 N10): ein Reiter „Aufgaben“ mit
//  1. den Vorschlägen des Vorarbeiters (Kartenart `aufgabe`): Einträge abhaken, Frist und Zähler setzen, freigeben oder ablehnen,
//  2. den aktiven Aufgaben mit Rest an Aufrufen und Minuten und dem Knopf „Zurücknehmen“ (Läufe der Aufgabe mit stoppen – Vorgabe an),
//  3. einem Formular „Aufgabe freigeben“ (nur der Captain legt Aufgaben an; weite Muster und Schreiben-dann-Ausführen warnen rot).
// Gesendet wird über /api/harness/aufgaben und /api/harness/karten/<id> – dieselben Türen wie überall; Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  function minuten(a){
    if(a.rest_min === null || a.rest_min === undefined) return '';
    return a.rest_min >= 60 ? Math.floor(a.rest_min / 60) + ' h ' + (a.rest_min % 60) + ' min' : a.rest_min + ' min';
  }

  function eintraege(liste){
    const ul = d().el('ul', 'hs-auf-liste');
    (liste || []).forEach(e=>ul.append(d().el('li', null, e.werkzeug + ' · ' + e.muster)));
    return ul;
  }

  // Stufe 6 (HS-61): erst der Zweck, dann in Klartext, was erlaubt ist; die technischen Muster stehen darunter, eingeklappt.
  function zweckZeilen(a){
    const z = d().el('div', 'hs-auf-zweck');
    const satz = a.zweck_anzeige || a.zweck || '';
    z.append(d().el('div', 'hs-auf-satz', satz));
    if(a.klartext && a.klartext !== satz) z.append(d().el('div', 'hs-leise hs-auf-darf', a.klartext));
    return z;
  }

  function technisch(liste){
    const det = d().el('details', 'hs-auf-technik');
    det.append(d().el('summary', 'hs-leise', 'Genaue Regeln (' + (liste || []).length + ')'), eintraege(liste));
    return det;
  }

  function sitzungsName(S, id){
    const s = S.sitzung && S.sitzung(id);
    return (s && s.titel ? s.titel + ' ' : '') + '(' + id + ')';
  }

  // ---- 1. ein Vorschlag des Vorarbeiters
  function vorschlagKarte(S, k, neuLaden){
    const doc = k.args || {};
    const box = d().el('div', 'hs-karte hs-auf-karte');
    box.dataset.karte = k.karte_id;
    box.append(d().el('div', 'hs-karte-kopf', ''));
    box.firstChild.append(d().el('span', 'hs-karte-icon', '⛨'), d().el('b', null, 'Vorschlag: ' + (doc.titel || k.ziel || '')), d().el('small', 'hs-leise', 'vom Vorarbeiter · Karte ' + k.karte_id));
    box.append(d().el('div', 'hs-auf-satz', doc.zweck || '(ohne Zweck)'));
    box.append(d().el('div', 'hs-leise', 'Sitzungen: ' + (doc.sitzungen || []).map(id=>sitzungsName(S, id)).join(', ')));
    const haken = (doc.erlaubt || []).map((e, i)=>{
      const zeile = d().el('label', 'hs-auf-zeile');
      const cb = d().el('input'); cb.type = 'checkbox'; cb.checked = true; cb.dataset.index = String(i);
      cb.setAttribute('aria-label', e.werkzeug + ' ' + e.muster);
      zeile.append(cb, d().el('span', null, e.werkzeug + ' · ' + e.muster));
      box.append(zeile);
      return cb;
    });
    const ende = doc.ende || {};
    const max = d().el('input', 'hs-auf-feld'); max.type = 'number'; max.min = '1'; max.max = '500'; max.value = ende.max_aufrufe || ''; max.setAttribute('aria-label', 'Höchstens so viele Aufrufe');
    const frist = d().el('input', 'hs-auf-feld'); frist.type = 'number'; frist.min = '1'; frist.max = '1440'; frist.placeholder = 'Minuten ab jetzt'; frist.setAttribute('aria-label', 'Frist in Minuten ab jetzt');
    const ersatz = d().el('div', 'hs-auf-grenzen');
    ersatz.append(d().el('label', 'hs-leise', 'Aufrufe höchstens '), max, d().el('label', 'hs-leise', ' Frist (statt ' + (ende.bis ? new Date(ende.bis).toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'}) + ' Uhr' : 'keine') + ') '), frist);
    box.append(ersatz);
    const notiz = d().el('input', 'hs-karte-notiz'); notiz.placeholder = 'Begründung (optional)'; notiz.setAttribute('aria-label', 'Begründung');
    const fuss = d().el('div', 'hs-karte-fuss');
    const antworten = async weg=>{
      fuss.querySelectorAll('button').forEach(b=>{ b.disabled = true; });
      try{
        const aenderungen = {};
        const auswahl = haken.filter(c=>c.checked).map(c=>Number(c.dataset.index));
        if(weg === 'erlauben'){
          if(!auswahl.length) throw new Error('Mindestens ein Eintrag muss bleiben.');
          if(auswahl.length !== haken.length) aenderungen.auswahl = auswahl;
          if(max.value && Number(max.value) !== ende.max_aufrufe) aenderungen.max_aufrufe = Number(max.value);
          if(frist.value) aenderungen.bis = new Date(Date.now() + Number(frist.value) * 60000).toISOString();
        }
        await S.api('/api/harness/karten/' + k.karte_id, {method: 'POST', body: {weg, notiz: notiz.value.trim() || null, aenderungen: Object.keys(aenderungen).length ? aenderungen : undefined}});
        S.hinweis(weg === 'erlauben' ? 'Aufgabe freigegeben.' : 'Vorschlag abgelehnt.');
        neuLaden();
      }catch(err){
        fuss.querySelectorAll('button').forEach(b=>{ b.disabled = false; });
        S.hinweis('Nicht gesendet: ' + err.message, 'bad');
      }
    };
    const ja = d().el('button', 'hs-senden', 'Freigeben'); ja.type = 'button'; ja.onclick = ()=>antworten('erlauben');
    const nein = d().el('button', 'hs-knopf', 'Ablehnen'); nein.type = 'button'; nein.onclick = ()=>antworten('ablehnen');
    fuss.append(ja, nein, notiz);
    box.append(fuss);
    return box;
  }

  // ---- 2. eine aktive Aufgabe
  function aufgabenZeile(S, a, neuLaden){
    const box = d().el('div', 'hs-karte ' + (a.status === 'aktiv' ? 'hs-auf-aktiv' : 'hs-auf-alt'));
    box.dataset.aufgabe = a.id;
    const kopf = d().el('div', 'hs-karte-kopf');
    kopf.append(d().el('b', null, a.titel), d().el('code', 'hs-karte-ziel', a.id));
    const rest = [a.rest_aufrufe !== null && a.rest_aufrufe !== undefined ? 'noch ' + a.rest_aufrufe + ' Aufrufe übrig' : null, a.rest_min !== null && a.rest_min !== undefined ? 'noch ' + minuten(a) : null].filter(Boolean).join(' · ');
    box.append(kopf, zweckZeilen(a), d().el('div', 'hs-leise', (a.status === 'aktiv' ? rest : a.status + (a.grund ? ' – ' + a.grund : '')) + ' · ' + a.aufrufe + ' benutzt' + (a.vorschlag_von ? ' · Vorschlag des Vorarbeiters' : '')),
               d().el('div', 'hs-leise', 'Sitzungen: ' + a.sitzungen.map(id=>sitzungsName(S, id)).join(', ')), technisch(a.erlaubt));
    if((a.modelle || []).length) box.append(d().el('div', 'hs-leise', 'Modelle: ' + a.modelle.join(', ')));
    (a.warnungen || []).forEach(w=>box.append(d().el('div', 'hs-karte-warnung', '⚠ ' + w)));
    if(a.status !== 'aktiv') return box;
    const laeufe = d().el('input'); laeufe.type = 'checkbox'; laeufe.checked = true; laeufe.setAttribute('aria-label', 'Läufe der Aufgabe mit stoppen');
    const lab = d().el('label', 'hs-auf-zeile'); lab.append(laeufe, d().el('span', 'hs-leise', 'Läufe der Aufgabe mit stoppen'));
    const zurueck = d().el('button', 'hs-knopf', 'Zurücknehmen'); zurueck.type = 'button';
    zurueck.onclick = async()=>{
      zurueck.disabled = true;
      try{
        const out = await S.api('/api/harness/aufgaben/' + a.id + '/zuruecknehmen', {method: 'POST', body: {laeufe_stoppen: laeufe.checked}});
        S.hinweis('Aufgabe zurückgenommen' + ((out.gestoppte_laeufe || []).length ? '; ' + out.gestoppte_laeufe.length + ' Lauf/Läufe gestoppt.' : '.'));
        neuLaden();
      }catch(err){ zurueck.disabled = false; S.hinweis('Rücknahme fehlgeschlagen: ' + err.message, 'bad'); }
    };
    const fuss = d().el('div', 'hs-karte-fuss'); fuss.append(zurueck, lab);
    box.append(fuss);
    return box;
  }

  // ---- 3. das Formular (Analyse Freigaben S1, 04.11.2026): Bausteine statt Muster-Zeilen, die neueste Sitzung vorgewählt, Frist und Aufrufe mit Vorgabe.
  // Titel, Zweck, eigene Zeilen und Modelle stehen unter „Erweitert“ (leer = aus den Bausteinen). Gesendet wird dasselbe wie vorher (POST /api/harness/aufgaben);
  // die Prüfung, was erlaubt sein darf, bleibt im Code (harness/aufgabe.py), das Formular zeigt nur vorher in einem Satz, was man erlaubt.
  const WAS = {datei_lesen: 'Dateien lesen', dateien_auflisten: 'Ordner auflisten', suchen: 'in Dateien suchen', datei_schreiben: 'Dateien neu schreiben',
               datei_aendern: 'Dateien ändern', befehl: 'Befehl ausführen', lauf_starten: 'Lauf starten', lauf_stoppen: 'Lauf stoppen',
               modell_laden: 'Modell laden', modell_entladen: 'Modell entladen'};
  const WEIT = /^(\*\*?|\*\*\/\*|\.?\/?\*\*?)$/;
  function klartextZeile(z){
    const i = z.indexOf(' '), w = i < 0 ? z : z.slice(0, i), m = i < 0 ? '' : z.slice(i + 1).trim();
    const was = WAS[w];
    if(!was) return {text: '„' + z + '“ – dieses Werkzeug kennt die Freigabe nicht', schlecht: true};
    if(!m) return {text: was + ' – es fehlt das Muster (wo oder was)', schlecht: true};
    const weit = WEIT.test(m);
    const wo = w === 'lauf_starten' || w === 'lauf_stoppen' ? 'Lauf „' + m + '“' : w === 'befehl' ? '„' + m + '“' : m.indexOf('**') >= 0 || m.indexOf('*') >= 0 ? 'überall in ' + m : m;
    return {text: was + ': ' + wo + (weit ? ' – ALLES, ohne Einschränkung' : ''), schlecht: weit};
  }

  // Rückfall, falls /api/harness/bausteine nicht antwortet: dieselben drei wie in der Vorgabe (runtime/config/freigabe_bausteine.yaml).
  const NOTFALL = [{id: 'tests-starten', name: 'Tests starten', zeilen: [{werkzeug: 'lauf_starten', muster: 'run_tests'}]},
                   {id: 'docs-aendern', name: 'Dokumente in docs/ ändern', zeilen: [{werkzeug: 'datei_aendern', muster: 'docs/**'}]},
                   {id: 'docs-anlegen', name: 'Neue Dateien in docs/ anlegen', zeilen: [{werkzeug: 'datei_schreiben', muster: 'docs/**'}]}];
  const FRISTEN = [[30, '30 Minuten'], [120, '2 Stunden'], [480, '8 Stunden'], [1440, '24 Stunden']];
  const FRIST_VORGABE = 120, AUFRUFE_VORGABE = 50;
  const SITZUNGEN_ZUERST = 6;

  function vor(iso){
    const m = Math.round((Date.now() - Date.parse(iso)) / 60000);
    if(!(m >= 0)) return '';
    return m < 1 ? 'gerade eben' : m < 60 ? 'vor ' + m + ' min' : m < 1440 ? 'vor ' + Math.floor(m / 60) + ' h' : 'vor ' + Math.floor(m / 1440) + ' Tagen';
  }

  function formular(S, neuLaden){
    const f = d().el('form', 'hs-karte hs-auf-form');
    f.setAttribute('aria-label', 'Aufgabe freigeben');
    f.onsubmit = e=>e.preventDefault();
    const schritt = (nr, text, hilfe)=>{ const k = d().el('div', 'hs-auf-schritt'); k.append(d().el('b', null, nr + ' · ' + text)); if(hilfe) k.append(d().el('small', 'hs-leise', hilfe)); return k; };
    // 1 · Was darf der Agent? – Bausteine zum Anklicken, darunter in Klartext, was daraus wird
    const gewaehlteBausteine = new Set();
    let bausteine = NOTFALL;
    const schnell = d().el('div', 'hs-auf-schnell'); schnell.setAttribute('role', 'group'); schnell.setAttribute('aria-label', 'Bausteine');
    const erlaubt = d().el('textarea', 'hs-auf-text'); erlaubt.rows = 3; erlaubt.setAttribute('aria-label', 'Erlaubte Aufrufe');
    erlaubt.placeholder = 'Eigene Zeilen, eine je Erlaubnis: Werkzeug Muster\ndatei_aendern docs/spec_entwuerfe/**\nlauf_starten run_tests';
    const summe = d().el('div', 'hs-auf-summe'); summe.setAttribute('aria-live', 'polite');
    const eigene = ()=>erlaubt.value.split('\n').map(z=>z.trim()).filter(Boolean);
    const zeilen = ()=>[...new Set(bausteine.filter(b=>gewaehlteBausteine.has(b.id)).flatMap(b=>b.zeilen.map(z=>z.werkzeug + ' ' + z.muster)).concat(eigene()))];
    const zeigeSumme = ()=>{
      const z = zeilen();
      if(!z.length){ summe.replaceChildren(d().el('small', 'hs-leise', 'Noch nichts gewählt – klick oben einen Baustein an.')); return; }
      summe.replaceChildren(d().el('b', null, 'Der Agent darf, ohne zu fragen:'), ...z.map(x=>{ const k = klartextZeile(x); return d().el('div', k.schlecht ? 'hs-karte-warnung' : 'hs-auf-darf-zeile', (k.schlecht ? '⚠ ' : '✓ ') + k.text); }));
    };
    const zeichneBausteine = ()=>{
      schnell.replaceChildren(...bausteine.map(b=>{
        const k = d().el('button', 'hs-knopf hs-klein', b.name); k.type = 'button'; k.dataset.baustein = b.id; k.title = b.hinweis || b.zeilen.map(z=>z.werkzeug + ' ' + z.muster).join(' · ');
        const an = ()=>{ k.setAttribute('aria-pressed', gewaehlteBausteine.has(b.id) ? 'true' : 'false'); k.classList.toggle('p', gewaehlteBausteine.has(b.id)); };
        k.onclick = ()=>{ gewaehlteBausteine.has(b.id) ? gewaehlteBausteine.delete(b.id) : gewaehlteBausteine.add(b.id); an(); zeigeSumme(); };
        an();
        return k;
      }));
    };
    zeichneBausteine(); zeigeSumme(); erlaubt.oninput = zeigeSumme;
    S.api('/api/harness/bausteine').then(out=>{ if((out.bausteine || []).length){ bausteine = out.bausteine; zeichneBausteine(); zeigeSumme(); } }).catch(()=>{});
    // 2 · In welchen Sitzungen? – die neueste ist vorgewählt
    const projekt = d().el('select', 'hs-projektwahl'); projekt.setAttribute('aria-label', 'Projekt'); projekt.hidden = (S.projekte || []).length < 2;
    (S.projekte || []).forEach(p=>{ const o = document.createElement('option'); o.value = p.id; o.textContent = p.name; projekt.append(o); });
    const sitzungen = d().el('div', 'hs-auf-sitzungen');
    let alleZeigen = false, vorgewaehlt = false;
    const gewaehlt = new Set();
    const zeichneSitzungen = ()=>{
      const meine = (S.sitzungen || []).filter(s=>s.projekt === projekt.value);
      if(!vorgewaehlt && meine.length){ gewaehlt.add(meine[0].id); vorgewaehlt = true; }
      const sichtbar = alleZeigen ? meine : meine.filter((s, i)=>i < SITZUNGEN_ZUERST || gewaehlt.has(s.id));
      sitzungen.replaceChildren(...sichtbar.map(s=>{
        const l = d().el('label', 'hs-auf-zeile'); const cb = d().el('input'); cb.type = 'checkbox'; cb.value = s.id; cb.checked = gewaehlt.has(s.id);
        cb.onchange = ()=>{ cb.checked ? gewaehlt.add(s.id) : gewaehlt.delete(s.id); };
        l.append(cb, d().el('span', null, (s.titel || 'Ohne Titel').slice(0, 70) + (s.vorlage ? ' · ' + s.vorlage : '')), d().el('small', 'hs-leise', vor(s.zuletzt) || s.id));
        return l;
      }));
      if(!meine.length) sitzungen.append(d().el('small', 'hs-leise', 'Noch keine Sitzung in diesem Projekt.'));
      else if(meine.length > sichtbar.length || alleZeigen && meine.length > SITZUNGEN_ZUERST){
        const mehr = d().el('button', 'hs-knopf hs-klein', alleZeigen ? 'Nur die neuesten zeigen' : (meine.length - sichtbar.length) + ' ältere zeigen'); mehr.type = 'button';
        mehr.onclick = ()=>{ alleZeigen = !alleZeigen; zeichneSitzungen(); };
        sitzungen.append(mehr);
      }
    };
    projekt.onchange = ()=>{ gewaehlt.clear(); vorgewaehlt = false; zeichneSitzungen(); }; zeichneSitzungen();
    // 3 · Wie lange und wie oft? – Vorgabe 2 Stunden und 50 Aufrufe; die Frist ist höchstens 24 Stunden
    const frist = d().el('select', 'hs-auf-feld'); frist.setAttribute('aria-label', 'Frist');
    FRISTEN.forEach(([min, text])=>{ const o = document.createElement('option'); o.value = String(min); o.textContent = text; frist.append(o); });
    const max = d().el('input', 'hs-auf-feld'); max.type = 'number'; max.min = '1'; max.max = '500'; max.placeholder = 'ohne Grenze'; max.setAttribute('aria-label', 'Höchstens so viele Aufrufe');
    const grenzen = d().el('div', 'hs-auf-grenzen'); grenzen.append(d().el('label', 'hs-leise', 'Frist '), frist, d().el('label', 'hs-leise', ' Aufrufe höchstens '), max);
    const werte = ()=>{ frist.value = String(FRIST_VORGABE); max.value = String(AUFRUFE_VORGABE); };
    werte();
    // Erweitert: Titel, Zweck, eigene Zeilen, Modelle
    const titel = d().el('input', 'hs-karte-notiz'); titel.placeholder = 'Titel (leer = aus den Bausteinen)'; titel.setAttribute('aria-label', 'Titel');
    const zweck = d().el('input', 'hs-karte-notiz'); zweck.maxLength = 160; zweck.setAttribute('aria-label', 'Zweck'); zweck.placeholder = 'Wofür? Ein Satz (leer = aus den Bausteinen)';
    const modelle = d().el('input', 'hs-karte-notiz'); modelle.placeholder = 'Modelle (Rezept-IDs, durch Komma) – nur für Läufe mit Modell'; modelle.setAttribute('aria-label', 'Modelle');
    const mehr = d().el('details', 'hs-auf-erweitert'); mehr.append(d().el('summary', 'hs-leise', 'Erweitert: Titel, Zweck, eigene Zeilen, Modelle'), titel, zweck, erlaubt, modelle);
    const meldung = d().el('div', 'hs-auf-meldung'); meldung.setAttribute('role', 'status');
    const ok = d().el('button', 'hs-senden', 'Freigeben'); ok.type = 'submit';
    ok.onclick = async()=>{
      meldung.replaceChildren();
      const z = zeilen();
      if(!z.length){ meldung.replaceChildren(d().el('div', 'hs-karte-warnung', 'Wähle zuerst mindestens einen Baustein.')); return; }
      if(!gewaehlt.size){ meldung.replaceChildren(d().el('div', 'hs-karte-warnung', 'Wähle mindestens eine Sitzung, in der es gelten soll.')); return; }
      const liste = z.map(x=>{ const i = x.indexOf(' '); return i < 0 ? {werkzeug: x, muster: ''} : {werkzeug: x.slice(0, i), muster: x.slice(i + 1).trim()}; });
      const namen = bausteine.filter(b=>gewaehlteBausteine.has(b.id)).map(b=>b.name);
      const ende = {bis: new Date(Date.now() + Number(frist.value) * 60000).toISOString()}; if(max.value) ende.max_aufrufe = Number(max.value);
      ok.disabled = true;
      try{
        const out = await S.api('/api/harness/aufgaben', {method: 'POST', body: {titel: titel.value.trim() || namen.join(', ').slice(0, 60) || 'Aufgabe',
          zweck: zweck.value.trim() || ('Erlaubt: ' + (namen.join(', ') || liste.map(x=>x.werkzeug).join(', '))).slice(0, 160), projekt: projekt.value,
          sitzungen: [...gewaehlt], erlaubt: liste, modelle: modelle.value.split(',').map(m=>m.trim()).filter(Boolean), ende}});
        S.hinweis('Aufgabe ' + out.id + ' freigegeben.' + ((out.warnungen || []).length ? ' Achtung: ' + out.warnungen.length + ' Warnung(en).' : ''), (out.warnungen || []).length ? 'warn' : 'note');
        ok.disabled = false; titel.value = zweck.value = modelle.value = erlaubt.value = ''; gewaehlteBausteine.clear(); zeichneBausteine(); werte();
        gewaehlt.clear(); vorgewaehlt = false; zeichneSitzungen(); zeigeSumme();
        neuLaden(true);
      }catch(err){
        ok.disabled = false;
        meldung.replaceChildren(d().el('div', 'hs-karte-warnung', 'Nicht freigegeben: ' + err.message));
      }
    };
    f.append(d().el('b', null, 'Neue Aufgabe freigeben'),
             d().el('small', 'hs-leise', 'Der Agent darf das Gewählte in den gewählten Sitzungen ohne Rückfrage tun, nur so lange und so oft wie eingestellt. Verbotenes, feste Vorbehalte und Warnkarten bleiben bei dir.'),
             schritt(1, 'Was darf der Agent?', 'Klick einen oder mehrere Bausteine an.'), schnell, summe,
             schritt(2, 'In welchen Sitzungen?', 'Die neueste ist vorgewählt. Nur die angehakten dürfen es nutzen.'), projekt, sitzungen,
             schritt(3, 'Wie lange und wie oft?', 'Vorgabe: 2 Stunden und 50 Aufrufe. Die Frist ist höchstens 24 Stunden.'), grenzen,
             mehr, meldung, ok);
    return f;
  }

  // ---- der Reiter
  // Der Reiter zeichnet nur neu, wenn sich etwas geändert hat, und behält die Stelle, an der man gerade liest. Das Formular entsteht einmal und
  // bleibt stehen (sonst gingen Eingaben verloren). `laden` ruft die Shell bei jeder Freigaben-Änderung; es ruft sie NICHT selbst wieder auf.
  function ansicht(S, id){
    const box = d().el('div', 'hs-verlauf hs-aufgaben');
    const liste = d().el('div', 'hs-liste');
    const kopf = d().el('h2', 'hs-diff-titel', 'Aufgaben-Freigaben');
    const vorschlaege = d().el('div', 'hs-auf-abschnitt'), aktivBox = d().el('div', 'hs-auf-abschnitt'), altBox = d().el('div', 'hs-auf-abschnitt');
    let formEl = null, letzte = '', laeuft = false, nochmal = false;
    liste.append(kopf, vorschlaege, aktivBox);
    box.append(liste);
    const a = root.sedraHarness.reiter.stub(id, box, S, {laden: force=>laden(force)});
    async function laden(force){
      if(laeuft){ nochmal = true; return; }
      laeuft = true;
      try{
        const [auf, entsch] = await Promise.all([S.api('/api/harness/aufgaben'), S.api('/api/decisions')]);
        const karten = await Promise.all((entsch.items || []).filter(x=>x.kind === 'harness_aufgabe').map(x=>S.api('/api/harness/karten/' + String(x.id).replace('harness:', ''))));
        const aktiv = (auf.aufgaben || []).filter(x=>x.status === 'aktiv');
        const alt = (auf.aufgaben || []).filter(x=>x.status !== 'aktiv').slice(-5).reverse();
        const stand = JSON.stringify([karten, aktiv, alt, (S.sitzungen || []).length]);
        if(stand === letzte && !force && formEl) return;
        letzte = stand;
        const oben = box.scrollTop;
        vorschlaege.replaceChildren(d().el('h3', 'hs-ueber', 'Vorschläge des Vorarbeiters (' + karten.length + ')'),
          ...(karten.length ? karten.map(k=>vorschlagKarte(S, k, laden)) : [d().el('small', 'hs-leise', 'Keine offenen Vorschläge.')]));
        aktivBox.replaceChildren(d().el('h3', 'hs-ueber', 'Gilt gerade (' + aktiv.length + ')'),
          ...(aktiv.length ? aktiv.map(x=>aufgabenZeile(S, x, laden)) : [d().el('small', 'hs-leise', 'Keine Aufgabe gilt gerade – unten kannst du eine freigeben.')]));
        if(!formEl){ formEl = formular(S, laden); liste.append(formEl, altBox); }
        altBox.replaceChildren(...(alt.length ? [d().el('h3', 'hs-ueber', 'Zuletzt beendet'), ...alt.map(x=>aufgabenZeile(S, x, laden))] : []));
        box.scrollTop = oben;
      }catch(err){ vorschlaege.replaceChildren(d().el('div', 's-note bad', 'Aufgaben nicht lesbar: ' + err.message)); }
      finally{ laeuft = false; if(nochmal){ nochmal = false; laden(); } }
    }
    laden();
    return a;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.aufgabe = {ansicht, vorschlagKarte, aufgabenZeile, formular, minuten, zweckZeilen, klartextZeile};
})();
