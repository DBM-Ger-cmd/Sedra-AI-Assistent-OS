// Harness-Shell – Dateien anhängen (Stufe 6, HS-82 bis HS-85): „+“ im Eingabefeld öffnet eine Auswahl der Projektdateien (Ordner, Suche), „@“ im Text schlägt Dateien vor. Gewählt wird
// ein Pfad; er steht danach als `@pfad` in der Nachricht, und SEDRA liest die Datei mit `datei_lesen` (Einstufung und Karten wie sonst). Die Liste nennt nur Namen und nur, was der Katalog
// zum Lesen zulässt (GET /api/harness/dateien). Namen sind Daten: nur textContent.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const MAX_VORSCHLAG = 8;

  function projektId(S){
    const a = S.aktive(), s = a && S.sitzung(a.id);
    return (s && s.projekt) || (S._eingabe && S._eingabe.projekt.value) || (S.projekte[0] && S.projekte[0].id) || '';
  }

  async function holen(S, ordner, q){
    return S.api('/api/harness/dateien?projekt=' + encodeURIComponent(projektId(S)) + '&ordner=' + encodeURIComponent(ordner || '') + '&q=' + encodeURIComponent(q || ''));
  }

  function groesse(n){ return n == null ? '' : (n < 1024 ? n + ' B' : Math.round(n / 1024) + ' KB'); }

  // `@pfad` an der Schreibmarke einfügen; ersetzt ein begonnenes „@wort“ vor der Marke.
  function einfuegen(S, pfad, ersetzeToken){
    const e = S._eingabe, f = e.feld;
    const pos = f.selectionStart == null ? f.value.length : f.selectionStart;
    let vor = f.value.slice(0, pos);
    const nach = f.value.slice(pos);
    if(ersetzeToken) vor = vor.replace(/(^|\s)@\S*$/, '$1');
    else if(vor && !/\s$/.test(vor)) vor += ' ';
    const text = '@' + pfad + ' ';
    f.value = vor + text + nach;
    f.selectionStart = f.selectionEnd = (vor + text).length;
    f.dispatchEvent(new Event('input'));
    f.focus();
  }

  // ---- die Auswahl hinter „+“
  function oeffnen(S){
    const e = S._eingabe; if(!e) return;
    if(e.auswahl){ schliessen(S); return; }
    const box = d().el('div', 'hs-anhang'); box.setAttribute('role', 'dialog'); box.setAttribute('aria-label', 'Datei anhängen');
    const suche = d().el('input', 'hs-karte-notiz'); suche.placeholder = 'Dateien im Projekt suchen …'; suche.setAttribute('aria-label', 'Dateien suchen');
    const fertig = d().el('button', 'hs-knopf', 'Fertig'); fertig.type = 'button'; fertig.onclick = ()=>schliessen(S);
    const kopf = d().el('div', 'hs-anhang-kopf'); kopf.append(suche, fertig);
    const pfad = d().el('div', 'hs-leise hs-anhang-pfad');
    const liste = d().el('div', 'hs-anhang-liste');
    box.append(kopf, pfad, liste);
    e.auswahl = box;
    e.box.insertBefore(box, e.box.firstChild);
    let n = 0, ordner = '';
    async function laden(){
      const mein = ++n;
      liste.replaceChildren(d().el('small', 'hs-leise', 'lädt …'));
      let out;
      try{ out = await holen(S, ordner, suche.value); }catch(err){ if(mein === n) liste.replaceChildren(d().el('small', 'hs-leise bad', 'Nicht lesbar: ' + err.message)); return; }
      if(mein !== n) return;
      pfad.replaceChildren();
      if(!suche.value.trim()){
        const teile = ordner ? ordner.split('/') : [];
        const wurzel = d().button('Projekt', ()=>{ ordner = ''; laden(); }); pfad.append(wurzel);
        teile.forEach((t, i)=>{ pfad.append(' › '); pfad.append(d().button(t, ()=>{ ordner = teile.slice(0, i + 1).join('/'); laden(); })); });
      } else pfad.append(d().el('span', null, out.eintraege.length + ' Treffer' + (out.gekuerzt ? ' (gekürzt – Suche enger fassen)' : '')));
      liste.replaceChildren(...(out.eintraege.length ? out.eintraege.map(x=>{
        const name = suche.value.trim() ? x.pfad : x.pfad.split('/').pop();
        const z = d().clickable(d().el('div', 'hs-anhang-zeile ' + x.art), ()=>{ if(x.art === 'ordner'){ ordner = x.pfad; suche.value = ''; laden(); } else einfuegen(S, x.pfad, false); });
        z.append(d().el('span', 'hs-anhang-icon', x.art === 'ordner' ? '📁' : '📄'), d().el('span', 'hs-anhang-name', name + (x.art === 'ordner' ? '/' : '')), d().el('small', 'hs-leise', groesse(x.groesse)));
        z.title = x.pfad;
        return z;
      }) : [d().el('small', 'hs-leise', 'Nichts gefunden.')]));
    }
    let warte = null;
    suche.oninput = ()=>{ clearTimeout(warte); warte = setTimeout(laden, 200); };
    box.onkeydown = ev=>{ if(ev.key === 'Escape'){ ev.stopPropagation(); schliessen(S); } };
    e.escAus = ev=>{ if(ev.key === 'Escape'){ schliessen(S); } };          // auch aus dem Eingabefeld, wohin der Fokus nach dem Einfügen zurückgeht
    e.feld.addEventListener('keydown', e.escAus);
    laden();
    setTimeout(()=>suche.focus(), 0);
  }

  function schliessen(S){
    const e = S._eingabe; if(!e || !e.auswahl) return;
    e.auswahl.remove(); e.auswahl = null;
    if(e.escAus){ e.feld.removeEventListener('keydown', e.escAus); e.escAus = null; }
    e.feld.focus();
  }

  // ---- „@“ im Text: Vorschläge unter dem Feld (HS-84)
  async function vorschlaege(S, token){
    const e = S._eingabe; if(!e) return;
    const mein = e._vorschlagN = (e._vorschlagN || 0) + 1;
    let out;
    try{ out = await holen(S, '', token); }catch(_err){ return; }
    if(mein !== e._vorschlagN || !/(^|\s)@\S*$/.test(e.feld.value)) return;
    e.vorschlag.replaceChildren(...(out.eintraege.filter(x=>x.art === 'datei').slice(0, MAX_VORSCHLAG).map(x=>{
      const z = d().clickable(d().el('div', 'hs-vorschlag-zeile'), ()=>{ einfuegen(S, x.pfad, true); e.vorschlag.replaceChildren(); e.vorschlag.hidden = true; });
      z.append(d().el('b', null, '@' + x.pfad), d().el('small', 'hs-leise', groesse(x.groesse)));
      return z;
    })));
    if(!e.vorschlag.childNodes.length) e.vorschlag.append(d().el('div', 'hs-vorschlag-zeile', token ? 'Keine Datei passt zu „' + token + '“.' : 'Tippe einen Teil des Dateinamens.'));
    e.vorschlag.hidden = false;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.anhang = {oeffnen, schliessen, vorschlaege, einfuegen};
})();
