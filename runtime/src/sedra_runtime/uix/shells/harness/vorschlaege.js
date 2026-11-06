// Harness-Shell (One Sedra) – Vorhersagen beim Tippen (Captain 05.11.2026: aus Lob und Korrektur lassen sich Vorschläge für die Eingabe ableiten). Während man tippt, fragt die Eingabe
// (kurz verzögert) GET /api/harness/vorschlaege und zeigt unter dem Feld: Aufträge, die der Captain schon einmal so gestellt hat und deren Antwort er gelobt hat (★ gute, ★★ besonders gute,
// mit den Dateien, in denen sie gelöst wurde – ein Klick auf die Datei hängt sie als @pfad an), und ein ⚑ Hinweis, wenn ein ähnlicher Auftrag zuletzt korrigiert wurde (mit seinen Worten).
// Ein Klick oder Tab übernimmt den ersten Vorschlag. Die Vorschläge kommen nur aus den eigenen gelobten und korrigierten Antworten dieses Projekts, lokal (harness/belohnung.py,
// config/belohnung.yaml `vorschlaege`). Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const MIN = 3, VERZOEGERUNG_MS = 250;

  // Soll für diese Eingabe gefragt werden? Nicht bei Befehlen (/), nicht beim Nennen einer Datei (@), nicht bei mehreren Zeilen, nicht bei zu wenig Text.
  const soll = t=>typeof t === 'string' && t.trim().length >= MIN && !t.startsWith('/') && !t.includes('\n') && !/(^|\s)@\S*$/.test(t);

  function uebernehmen(S, v){
    const e = S._eingabe; if(!e) return;
    e.feld.value = v.frage; e.feld.dispatchEvent(new Event('input')); e.feld.focus();
    e.feld.selectionStart = e.feld.selectionEnd = e.feld.value.length;
  }

  function zeigen(S, r){
    const e = S._eingabe; if(!e) return;
    const zeilen = [];
    (r.warnungen || []).forEach(w=>{
      const z = d().el('div', 'hs-vorschlag-zeile hs-vorschlag-warn');
      z.append(d().el('b', null, '⚑ Zuletzt korrigiert: '), d().el('span', null, w.korrektur));
      z.title = 'Ein ähnlicher Auftrag („' + w.frage + '“) wurde korrigiert.';
      zeilen.push(z);
    });
    (r.vorschlaege || []).forEach(v=>{
      const z = d().clickable(d().el('div', 'hs-vorschlag-zeile hs-vorschlag-gut'), ()=>uebernehmen(S, v));
      z.append(d().el('span', 'hs-vorschlag-stern', v.stufe === 2 ? '★★' : '★'), d().el('span', null, v.frage));
      (v.dateien || []).forEach(pfad=>{
        const k = d().el('button', 'hs-knopf hs-klein hs-vorschlag-datei', '@' + pfad.split('/').pop()); k.type = 'button'; k.title = pfad + ' anhängen';
        k.onclick = ev=>{ ev.stopPropagation(); const H = root.sedraHarness; if(H.anhang) H.anhang.einfuegen(S, pfad, false); };
        z.append(k);
      });
      z.title = 'Schon einmal so gefragt und die Antwort war gut' + (v.vorlage ? ' (Vorlage ' + v.vorlage + ')' : '') + '. Klick oder Tab übernimmt.';
      zeilen.push(z);
    });
    e._vsErste = (r.vorschlaege || [])[0] || null;
    e.vorschlag.replaceChildren(...zeilen);
    e.vorschlag.hidden = !zeilen.length;
  }

  async function holen(S){
    const e = S._eingabe; if(!e) return;
    const t = e.feld.value, n = e._vsN = (e._vsN || 0) + 1;
    let r;
    try{ r = await S.api('/api/harness/vorschlaege?q=' + encodeURIComponent(t) + '&vorlage=' + encodeURIComponent(e.vorlage && e.vorlage.value || '')); }catch(_err){ return; }
    if(n !== e._vsN || e.feld.value !== t || !soll(t)) return;                  // inzwischen weitergetippt: die Antwort ist veraltet
    if(r && r.an === false){ S._vorschlaegeAus = true; return; }                  // am Server abgeschaltet: nicht mehr fragen
    zeigen(S, r || {});
  }

  // eingabe.js ruft es bei jedem Tippen; fragt erst nach einer kurzen Pause und nur, wenn es sinnvoll ist
  function planen(S){
    const e = S._eingabe; if(!e) return false;
    clearTimeout(e._vsTimer); e._vsN = (e._vsN || 0) + 1; e._vsErste = null;
    if(S._vorschlaegeAus || !soll(e.feld.value)) return false;
    e._vsTimer = setTimeout(()=>holen(S), VERZOEGERUNG_MS);
    return true;
  }

  // Tab im Eingabefeld übernimmt den ersten Vorschlag (true, wenn es einen gab)
  function erstenUebernehmen(S){
    const e = S._eingabe;
    if(!e || !e._vsErste || e.vorschlag.hidden) return false;
    uebernehmen(S, e._vsErste); e._vsErste = null; e.vorschlag.replaceChildren(); e.vorschlag.hidden = true;
    return true;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.vorschlaege = {soll, planen, erstenUebernehmen, zeigen, MIN};
})();
