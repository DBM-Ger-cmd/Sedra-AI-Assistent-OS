// Werkzeug „Module“ – Betrieb im Unternehmen (SPEC_APPS_v1_AM7_UNTERNEHMEN, Betriebsart A): Zustand der Richtlinie des Betreibers, Nachweis für die Prüfung (AM7-13) und die Seite
// „Was SEDRA mit deinen Eingaben tut“ (AM7-14). Nur lesen – es gibt keinen Weg, die Richtlinie über SEDRA zu ändern (AM7-06). Text nur mit textContent.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const ROLLE = {betreiber: 'Betreiber', pruefung: 'Prüfung', sachbearbeitung: 'Sachbearbeitung'};
  // rein: eine Zeile zum Zustand der Richtlinie
  function richtlinieSatz(v){
    if(!v || !v.schalter) return 'Der Betrieb im Unternehmen ist ausgeschaltet (Schalter betrieb_unternehmen in switches.yaml): Einzelplatzbetrieb wie bisher.';
    const r = v.richtlinie || {};
    if(r.aktiv) return 'Richtlinie aktiv · ' + (ROLLE[r.rolle] || r.rolle) + ' · ' + r.person + ' · Prüfsumme ' + String(r.hash || '').slice(0, 12);
    if(r.vorhanden) return 'Die Richtlinie ist nicht gültig und gilt deshalb nicht: ' + (r.fehler || []).join(', ');
    return 'Keine Richtlinie vorhanden (local_config/richtlinie.yaml): Einzelplatzbetrieb.';
  }

  async function zeichnen(ctx, box){
    box.append(d().el('h5', 's-head', 'Betrieb im Unternehmen'));
    let v;
    try{ v = await ctx.api('/api/uix/betrieb'); }catch(err){ box.append(d().el('div', 's-note bad', 'Nicht lesbar: ' + err.message)); return; }
    box.append(d().el('div', 's-note' + (v.richtlinie && v.richtlinie.aktiv ? ' ok' : ' warn'), richtlinieSatz(v)));
    box.append(d().el('small', 's-muted', 'Die Richtlinie ändert nur der Betreiber, als neue Datei. SEDRA erkennt die Änderung an der Prüfsumme und protokolliert sie. Gegen jemanden mit Administratorrechten an diesem Rechner schützt das Betriebssystem, nicht SEDRA.'));
    const aus = d().el('div', 's-col');
    const knoepfe = d().el('div', 's-row');
    knoepfe.append(d().button('Nachweis für die Prüfung', async()=>{ const x = await ctx.api('/api/uix/betrieb/export'); aus.replaceChildren(d().el('pre', 's-muted', x.text)); }),
                   d().button('Was SEDRA mit deinen Eingaben tut', async()=>{
                     const t = await ctx.api('/api/uix/betrieb/eingaben');
                     aus.replaceChildren(d().el('h5', 's-head', t.titel), ...t.absaetze.map(a=>d().el('p', null, a)));
                   }));
    box.append(knoepfe, aus);
  }

  root.sedraModulesBetrieb = {zeichnen, richtlinieSatz};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraModulesBetrieb;
})();
