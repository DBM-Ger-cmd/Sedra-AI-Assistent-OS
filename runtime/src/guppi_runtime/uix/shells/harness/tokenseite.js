// Harness-Shell – die Seite „Token und Gespräch“ (Einstellungen → Agent): oben der Verbrauch (Sitzung und Tag), darunter alles, was ihn bestimmt –
// Token sparen (Denken, Lese-Grenze, Verlauf, Zusammenfassen, Kontext-Sicherung), Spur und Gedanken, Gedächtnis (ansehen, exportieren, löschen) und das lange Gespräch.
// Ausgelagert aus einstellungen.js (der Vertrag erlaubt höchstens 400 Zeilen je Datei). Alles hier ist eine Vorgabe der Harness oder ein Lesen; geschrieben wird über
// /api/harness/vorgaben und /api/harness/gedaechtnis (nur der Captain, Herkunftsprüfung im Server). Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // Gedanken der Modelle: Sedra speichert sie je Antwort; hier steht, wie viel davon wieder an das Modell geht (mehr kostet Token)
  const GEDANKEN = [['aus', 'Aus – Gedanken nicht zurücksenden', 'Das Modell bekommt nur Text und Ergebnisse, keine Spur und keine Gedanken (spart am meisten). Die Gedanken bleiben bei Sedra und sind für dich aufklappbar.'],
                    ['spur', 'Spur (Standard)', 'Jede frühere Antwort trägt eine Zeile: was lief und wie viel Gedanken gespeichert sind. Das Modell holt sie bei Bedarf selbst mit „erinnern“.'],
                    ['kurz', 'Kurz', 'Spur, dazu das Ende der Gedanken der letzten 2 Antworten (je höchstens 800 Zeichen).'],
                    ['voll', 'Ausführlich', 'Spur, dazu die Gedanken der letzten 4 Antworten (je höchstens 6 000 Zeichen, insgesamt 12 000). Kostet deutlich mehr Token und füllt das Fenster schneller.']];
  function gedanken(S, box){
    box.append(d().el('div', 'hs-app-satz', 'Sedra speichert die Gedanken jedes Modells in der Sitzung (bis 20 000 Zeichen je Antwort, je Zug getrennt). Wähle, wie viel davon beim nächsten Mal wieder an das Modell geht.'));
    const liste = d().el('div', 'hs-einst-eigen'); box.append(liste);
    const meld = d().el('div', 'hs-leise'); box.append(meld);
    const zeichne = aktuell=>{
      liste.replaceChildren(...GEDANKEN.map(([wert, name, text])=>{
        const z = d().el('label', 'hs-einst-zeile'); const r = d().el('input'); r.type = 'radio'; r.name = 'hs-gedanken'; r.value = wert; r.checked = wert === aktuell;
        r.onchange = async()=>{
          try{ await S.api('/api/harness/vorgaben', {method: 'POST', body: {gedanken_zurueck: wert}}); meld.textContent = 'Gespeichert: ' + name + '. Gilt ab der nächsten Nachricht.'; }
          catch(err){ meld.textContent = 'Nicht gespeichert: ' + err.message; zeichne(aktuell); }
        };
        z.append(r, d().el('b', null, name), d().el('small', 'hs-leise', text));
        return z;
      }));
    };
    zeichne('spur');
    S.api('/api/harness/vorgaben').then(v=>zeichne(v.gedanken_zurueck || 'spur')).catch(()=>{});
    gedaechtnisBereich(S, box);
    langesGespraech(S, box);
  }

  // Token sparen: wählbare Grenzen. Jede Zeile ist eine Vorgabe der Harness (Laufzeitdatei, gilt ab der nächsten Nachricht); „Standard“ nimmt sie wieder zurück.
  const SPAREN = [
    ['denken', 'Denken eingrenzen', [['standard', 'Standard', 'das Modell denkt, so viel es will'], ['begrenzt', 'Begrenzt (1 000 Token)', 'das Denken wird je Aufruf gekappt'], ['aus', 'Aus', 'kein Denken (`reasoning_effort: none`)']],
     'Denken kostet die meiste Zeit beim Erzeugen (Gemma: rund 42 Token/s). Ohne Denken kann die Antwortqualität sinken, besonders bei Werkzeugwahl und Planung. Gemessen wurde die Wirkung von „Aus“ mit LM Studio (`jobs/token_policy.py`), mit dem Modell-Router noch nicht – vergleiche die Zahlen oben.'],
    ['antwort_budget', 'Antwortbudget je Aufruf', [['2048', '2 048 Token (Standard)', 'knapp, schnell'], ['4096', '4 096 Token', 'mehr Raum fürs Denken'], ['8192', '8 192 Token', 'für lange Überlegungen']],
     'So viele Token darf das Modell je Aufruf erzeugen – Denken und Antwort zusammen. Reicht es nicht, bleibt die Antwort leer („Token-Grenze beim Denken erreicht“); SEDRA versucht es dann einmal mit doppeltem Budget, ohne das Denken zu beschneiden. Ein großes Budget kostet nur Zeit, wenn es gebraucht wird.'],
    ['lese_grenze', 'Lese-Grenze je Aufruf', [['4000', '4 000 Zeichen', 'rund 1 200 Token'], ['6000', '6 000 Zeichen', 'rund 1 900 Token'], ['8000', '8 000 Zeichen (Standard)', 'rund 2 500 Token']],
     'So viel liefert datei_lesen höchstens je Aufruf. Weniger spart Token, braucht aber mehr Aufrufe (das Modell liest mit „weiter mit ab_zeile“ weiter).'],
    ['verlauf_laenge', 'Länge des Verlaufs', [['10', '10 Nachrichten', ''], ['20', '20 Nachrichten (Standard)', ''], ['30', '30 Nachrichten', '']],
     'So viele frühere Nachrichten gehen an das Modell. Was davor liegt, fasst Sedra zusammen (siehe „Langes Gespräch“) oder es fällt weg.'],
    ['zusammen_ab', 'Zusammenfassen ab', [['4', '4 Nachrichten', 'öfter, kürzere Aufrufe'], ['8', '8 Nachrichten (Standard)', ''], ['12', '12 Nachrichten', 'seltener']],
     'So viele Nachrichten müssen aus dem Verlauf gefallen sein, bevor Sedra sie zusammenfasst (ein kurzer Modellaufruf).'],
    ['kontext_sicherung', 'Kontext-Sicherung', [['frueh', 'Früh', 'kürzt ab 80 %, Abschluss ab 90 %'], ['normal', 'Normal (Standard)', 'kürzt ab 90 %, Abschluss ab 95 %'], ['spaet', 'Spät', 'kürzt ab 93 %, Abschluss ab 97 %']],
     'Wann Sedra bei vollem Fenster alte Ergebnisse kürzt und die Antwort ohne weitere Werkzeuge abschließt. Bei 100 % endet die Antwort mit Hinweis.']];
  function sparenBereich(S, box){
    box.append(d().el('h3', 'hs-ueber', 'Token sparen'));
    const meld = d().el('div', 'hs-leise');
    const zeilen = {};
    SPAREN.forEach(([schluessel, titel, wahl, hilfe])=>{
      const z = d().el('div', 'hs-spar-zeile');
      const sel = d().el('select', 'hs-projektwahl'); sel.setAttribute('aria-label', titel);
      wahl.forEach(([wert, name, text])=>{ const o = document.createElement('option'); o.value = wert; o.textContent = name + (text ? ' – ' + text : ''); sel.append(o); });
      sel.onchange = async()=>{
        try{ await S.api('/api/harness/vorgaben', {method: 'POST', body: {[schluessel]: sel.value}}); meld.textContent = titel + ': gespeichert, gilt ab der nächsten Nachricht.'; }
        catch(err){ meld.textContent = 'Nicht gespeichert: ' + err.message; laden(); }
      };
      zeilen[schluessel] = sel;
      z.append(d().el('b', 'hs-einst-label', titel), sel, d().el('small', 'hs-leise', hilfe));
      box.append(z);
    });
    const zurueck = d().el('button', 'hs-knopf hs-klein', 'Alles auf Standard'); zurueck.type = 'button';
    zurueck.onclick = async()=>{
      try{ for(const [schluessel] of SPAREN) await S.api('/api/harness/vorgaben', {method: 'POST', body: {[schluessel]: null}}); meld.textContent = 'Alle Grenzen stehen wieder auf Standard.'; }
      catch(err){ meld.textContent = 'Nicht zurückgesetzt: ' + err.message; }
      laden();
    };
    box.append(zurueck, meld);
    function laden(){ S.api('/api/harness/vorgaben').then(v=>SPAREN.forEach(([schluessel])=>{ if(v[schluessel] !== undefined) zeilen[schluessel].value = String(v[schluessel]); })).catch(()=>{}); }
    laden();
  }

  // Langes Gespräch: an das Modell gehen die letzten 20 Nachrichten; was davor liegt, fasst Sedra auf Wunsch zusammen (ein kurzer Modellaufruf vor der Antwort)
  function langesGespraech(S, box){
    const liste = d().el('div', 'hs-einst-eigen'), meld = d().el('div', 'hs-leise');
    box.append(d().el('h3', 'hs-ueber', 'Langes Gespräch'),
               d().el('div', 'hs-app-satz', 'An das Modell gehen die letzten 20 Nachrichten. Was davor liegt, fasst Sedra zusammen und legt es in den Systemprompt – sonst ginge es verloren.'), liste, meld);
    const WAHL = [['auto', 'Automatisch zusammenfassen (Standard)', 'Fallen 8 Nachrichten aus dem Verlauf, fasst das geladene Modell sie vor der nächsten Antwort kurz zusammen (ein kleiner Modellaufruf, einige Sekunden).'],
                  ['aus', 'Nicht zusammenfassen', 'Ältere Nachrichten fallen weg. Eine schon vorhandene Zusammenfassung bleibt im Systemprompt.']];
    const zeichne = aktuell=>liste.replaceChildren(...WAHL.map(([wert, name, text])=>{
      const z = d().el('label', 'hs-einst-zeile'); const r = d().el('input'); r.type = 'radio'; r.name = 'hs-zusammenfassen'; r.value = wert; r.checked = wert === aktuell;
      r.onchange = async()=>{
        try{ await S.api('/api/harness/vorgaben', {method: 'POST', body: {verlauf_zusammenfassen: wert}}); meld.textContent = 'Gespeichert: ' + name + '.'; }
        catch(err){ meld.textContent = 'Nicht gespeichert: ' + err.message; zeichne(aktuell); }
      };
      z.append(r, d().el('b', null, name), d().el('small', 'hs-leise', text));
      return z;
    }));
    zeichne('auto');
    S.api('/api/harness/vorgaben').then(v=>zeichne(v.verlauf_zusammenfassen || 'auto')).catch(()=>{});
  }

  // Das Gedächtnis: je Antwort eine wörtliche Notiz; hier stellt der Captain ein, wie weit das Modell suchen darf, und fasst alte Notizen zusammen (ein Modellaufruf)
  function gedaechtnisBereich(S, box){
    const kopf = d().el('div', 'hs-app-satz', 'Gedächtnis: Sedra merkt sich je Antwort eine kurze Notiz (Frage, Antwort, Werkzeuge, Kern der Gedanken). Das Modell sucht darin mit „erinnern“.');
    const reich = d().el('div', 'hs-einst-eigen'), liste = d().el('div', 'hs-einst-eigen'), meld = d().el('div', 'hs-leise');
    box.append(d().el('h3', 'hs-ueber', 'Gedächtnis'), kopf, reich, liste, meld);
    const REICH = [['projekt', 'Nur das Projekt der Sitzung (Standard)', 'Notizen eines Projekts sieht ein anderes nicht.'],
                   ['alle', 'Alle Projekte', 'Das Modell darf in den Notizen aller Projekte suchen – auch in denen, an denen es gerade nicht arbeitet.']];
    const zeichneReich = aktuell=>reich.replaceChildren(...REICH.map(([wert, name, text])=>{
      const z = d().el('label', 'hs-einst-zeile'); const r = d().el('input'); r.type = 'radio'; r.name = 'hs-reichweite'; r.value = wert; r.checked = wert === aktuell;
      r.onchange = async()=>{
        try{ await S.api('/api/harness/vorgaben', {method: 'POST', body: {gedaechtnis_reichweite: wert}}); meld.textContent = 'Gespeichert: ' + name + '.'; }
        catch(err){ meld.textContent = 'Nicht gespeichert: ' + err.message; zeichneReich(aktuell); }
      };
      z.append(r, d().el('b', null, name), d().el('small', 'hs-leise', text));
      return z;
    }));
    const zeichneListe = v=>liste.replaceChildren(...(v.projekte || []).map(p=>{
      const z = d().el('div', 'hs-einst-zeile');
      const k = d().el('button', 'hs-knopf hs-klein', 'Zusammenfassen'); k.type = 'button';
      k.disabled = p.unverdichtet < v.mindestens;
      k.title = k.disabled ? 'Ab ' + v.mindestens + ' neuen Notizen' : 'Fasst die ältesten neuen Notizen mit dem geladenen Modell zusammen (kostet Token, das Modell ist kurz belegt)';
      k.onclick = async()=>{
        k.disabled = true; meld.textContent = 'Fasse zusammen … das Modell ist kurz belegt.';
        try{ const out = await S.api('/api/harness/gedaechtnis', {method: 'POST', body: {projekt: p.id}}); meld.textContent = out.notizen + ' Notizen zusammengefasst (' + out.zusammenfassung + ').'; }
        catch(err){ meld.textContent = 'Nicht zusammengefasst: ' + err.message; }
        laden();
      };
      const ansehen = d().el('button', 'hs-knopf hs-klein', 'Ansehen'); ansehen.type = 'button';
      const export_ = d().el('button', 'hs-knopf hs-klein', 'Exportieren'); export_.type = 'button'; export_.title = 'Als Markdown-Datei speichern';
      const weg = d().el('button', 'hs-knopf hs-klein', 'Alles löschen'); weg.type = 'button'; weg.title = 'Löscht alle Notizen und Zusammenfassungen dieses Projekts (die Sitzungen bleiben)';
      const feld = d().el('div', 'hs-gedaechtnis-feld'); feld.hidden = true;
      const zeigeNotizen = async(suche)=>{
        let out;
        try{ out = await S.api('/api/harness/gedaechtnis/notizen?projekt=' + encodeURIComponent(p.id) + '&suche=' + encodeURIComponent(suche || '') + '&limit=50'); }
        catch(err){ feld.replaceChildren(d().el('div', 'hs-karte-warnung', 'Nicht lesbar: ' + err.message)); return; }
        const suchfeld = d().el('input', 'hs-karte-notiz'); suchfeld.placeholder = 'Suchen (jedes Wort muss vorkommen)'; suchfeld.value = suche || ''; suchfeld.setAttribute('aria-label', 'Notizen durchsuchen');
        suchfeld.onkeydown = e=>{ if(e.key === 'Enter'){ e.preventDefault(); zeigeNotizen(suchfeld.value); } };
        const kopf = d().el('small', 'hs-leise', out.treffer + (out.treffer === out.gesamt ? '' : ' von ' + out.gesamt) + ' Notizen' + (out.notizen.length < out.treffer ? ' · die neuesten ' + out.notizen.length : ''));
        const eintraege = out.notizen.map(n=>{
          const e = d().el('div', 'hs-gedaechtnis-notiz');
          const art = n.art === 'zusammenfassung' ? 'Zusammenfassung von ' + (n.deckt || []).length + ' Notizen' : 'Frage: ' + (n.frage || '');
          const x = d().el('button', 'hs-sz-knopf', '×'); x.type = 'button'; x.title = 'Diese Notiz löschen'; x.setAttribute('aria-label', 'Notiz ' + n.antwort_id + ' löschen');
          x.onclick = async()=>{
            try{ await S.api('/api/harness/gedaechtnis?projekt=' + encodeURIComponent(p.id) + '&id=' + encodeURIComponent(n.antwort_id), {method: 'DELETE'}); }catch(err){ meld.textContent = 'Nicht gelöscht: ' + err.message; }
            laden(); zeigeNotizen(suchfeld.value);
          };
          e.append(d().el('b', null, art), x, d().el('small', 'hs-leise', n.antwort_id + ' · ' + String(n.zeit || '').slice(0, 16) + (n.werkzeuge && n.werkzeuge.length ? ' · ' + n.werkzeuge.join(', ') : '')));
          if(n.antwort) e.append(d().el('div', 'hs-gedaechtnis-text', n.antwort));
          if(n.gedanken) e.append(d().el('div', 'hs-leise', 'Gedanken: ' + n.gedanken));
          return e;
        });
        feld.replaceChildren(suchfeld, kopf, ...(eintraege.length ? eintraege : [d().el('small', 'hs-leise', 'Nichts gefunden.')]));
      };
      ansehen.onclick = ()=>{ feld.hidden = !feld.hidden; ansehen.textContent = feld.hidden ? 'Ansehen' : 'Zuklappen'; if(!feld.hidden) zeigeNotizen(''); };
      export_.onclick = async()=>{
        try{
          const out = await S.api('/api/harness/gedaechtnis/export?projekt=' + encodeURIComponent(p.id));
          const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([out.text], {type: 'text/markdown;charset=utf-8'})); a.download = out.dateiname;
          document.body.append(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(a.href), 1000);
          meld.textContent = 'Exportiert: ' + out.dateiname;
        }catch(err){ meld.textContent = 'Nicht exportiert: ' + err.message; }
      };
      weg.disabled = !p.notizen && !p.zusammenfassungen;
      weg.onclick = async()=>{
        if(!weg.dataset.sicher){                                                // zweiter Klick statt confirm(): ein Browser-Dialog antwortet in eingebetteten Fenstern still mit Nein
          weg.dataset.sicher = '1'; weg.textContent = 'Sicher? Alles löschen';
          setTimeout(()=>{ if(weg.isConnected){ delete weg.dataset.sicher; weg.textContent = 'Alles löschen'; } }, 5000);
          return;
        }
        try{ const out = await S.api('/api/harness/gedaechtnis?projekt=' + encodeURIComponent(p.id) + '&alle=1', {method: 'DELETE'}); meld.textContent = out.geloescht + ' Einträge gelöscht.'; }
        catch(err){ meld.textContent = 'Nicht gelöscht: ' + err.message; }
        laden();
      };
      z.append(d().el('b', 'hs-einst-label', p.name), d().el('small', 'hs-leise', p.notizen + ' Notizen · ' + p.unverdichtet + ' noch nicht zusammengefasst · ' + p.zusammenfassungen + ' Zusammenfassungen'), k, ansehen, export_, weg);
      const block = d().el('div', 'hs-gedaechtnis-block'); block.append(z, feld);
      return block;
    }));
    function laden(){ S.api('/api/harness/gedaechtnis').then(v=>{ zeichneReich(v.reichweite || 'projekt'); zeichneListe(v); }).catch(err=>{ meld.textContent = 'Gedächtnis nicht lesbar: ' + err.message; }); }
    zeichneReich('projekt'); laden();
  }

  // Token und Gespräch: oben der Verbrauch (Sitzung und Tag), darunter alles, was ihn bestimmt – Spur, Gedanken, Gedächtnis, Zusammenfassung des langen Gesprächs
  // A3 (Captain 03.11.2026): die App „Sedra Token“ hat drei Reiter – Verbrauch (mit den Grenzen zum Sparen), Kosten und Zeilen (das Werkzeug Meter) und Gespräch (Gedanken, Gedächtnis, langes Gespräch)
  function verbrauch(S, box){
    const fmt = n=>Number(n || 0).toLocaleString('de-DE');
    const komma = x=>String(x).replace('.', ',');
    box.append(d().el('h3', 'hs-ueber', 'Verbrauch'));
    const v = d().el('div', 'hs-token-verbrauch'); box.append(v);
    const knopf = d().el('button', 'hs-knopf hs-klein', 'Aktualisieren'); knopf.type = 'button'; box.append(knopf);
    const zeile = (name, wert, hinweis)=>{ v.append(d().el('span', 'hs-token-name', name), d().el('b', 'hs-token-wert', wert), d().el('small', 'hs-leise', hinweis || '')); };
    const zeichne = ()=>{
      v.replaceChildren();
      const t = S.tokenStand;
      if(!t){ v.append(d().el('small', 'hs-leise', 'Noch keine Zahlen.')); return; }
      const s = t.sitzung, h = t.heute;
      if(s && s.antworten){
        v.append(d().el('div', 'hs-token-kopf', 'Diese Sitzung'));
        zeile('Antworten', fmt(s.antworten), fmt(s.zuege) + ' Züge insgesamt');
        zeile('Eingehend ↑', fmt(s.ein), 'was an das Modell ging – jeder Zug zählt den ganzen Verlauf neu');
        zeile('Erzeugt ↓', fmt(s.aus), 'was das Modell geschrieben hat, Denken eingeschlossen');
        zeile('Ø je Antwort', fmt(Math.round(s.ein / s.antworten)) + ' ↑ · ' + fmt(Math.round(s.aus / s.antworten)) + ' ↓', '');
        if(s.letzte) zeile('Letzte Antwort', fmt(s.letzte.ein) + ' ↑ · ' + fmt(s.letzte.aus) + ' ↓', s.letzte.zuege + ' Züge' + (s.letzte.tok_s ? ' · ' + komma(s.letzte.tok_s) + ' Token/s' : ''));
        if(s.cache_zuege) zeile('Aus dem Cache', s.cache_anteil + ' %', fmt(s.aus_cache) + ' von ' + fmt(s.aus_cache + s.neu_gerechnet) + ' Token der Eingabe wurden nicht neu gerechnet (Prompt-Cache des Modellservers)' + (s.cache_zuege >= 3 && s.cache_anteil < 10 ? ' – der Cache greift kaum: Systemprompt und Verlauf werden jedes Mal neu gerechnet' : ''));
        else if(s.antworten >= 3) zeile('Aus dem Cache', 'nicht gemessen', 'Der Modellserver meldet keine Cache-Zahlen (cache_n) – ältere Antworten oder ein Modell ohne Angabe');
        if(s.tok_s) zeile('Erzeugungstempo', komma(s.tok_s) + ' Token/s', 'Ø über die Zeit in Modellaufrufen (ohne Werkzeuge)');
        if(s.kontext && s.kontext.fenster) zeile('Kontextfenster', Math.round(100 * s.kontext.belegt / s.kontext.fenster) + ' %', fmt(s.kontext.belegt) + ' von ' + fmt(s.kontext.fenster) + ' Token belegt');
      }else if(t.fuer){
        v.append(d().el('small', 'hs-leise', 'Diese Sitzung hat noch keine Antwort – oder sie ist von vor dem Zählen der Token.'));
      }
      if(h && h.antworten){
        v.append(d().el('div', 'hs-token-kopf', 'Heute (' + h.tag + ')'));
        zeile('Antworten', fmt(h.antworten), 'in ' + h.sitzungen + (h.sitzungen === 1 ? ' Sitzung' : ' Sitzungen') + ' · ' + fmt(h.zuege) + ' Züge');
        zeile('Eingehend ↑', fmt(h.ein), '');
        zeile('Erzeugt ↓', fmt(h.aus), h.tok_s ? 'Ø ' + komma(h.tok_s) + ' Token/s' : '');
        if(h.cache_zuege) zeile('Aus dem Cache', h.cache_anteil + ' %', fmt(h.aus_cache) + ' von ' + fmt(h.aus_cache + h.neu_gerechnet) + ' Token der Eingabe');
      }
    };
    knopf.onclick = ()=>S.tokenLaden().then(zeichne);
    zeichne(); S.tokenLaden().then(zeichne);
    sparenBereich(S, box);
  }
  function gespraech(S, box){
    box.append(d().el('h3', 'hs-ueber', 'Gespräch und Gedanken'));
    gedanken(S, box);
  }
  function tokenSeite(S, box){ verbrauch(S, box); gespraech(S, box); }
  function oeffnen(S, reiter){
    const ort = root.sedraPlaces && root.sedraPlaces.PLACES.find(p=>p.id === 'meter');
    if(!ort) return;
    if(reiter) S._tokenReiter = reiter;
    root.sedraHarness.app.oeffnen(S, ort);
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.tokenseite = {zeigen: tokenSeite, verbrauch, gespraech, oeffnen, SPAREN, GEDANKEN};         // die Listen nutzt auch das Feld unter dem Schild (gespraechsoptionen.js)
})();
