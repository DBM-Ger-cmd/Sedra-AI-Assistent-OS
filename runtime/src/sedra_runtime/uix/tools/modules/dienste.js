// Werkzeug „Module“ – die Dienst-Apps (SPEC_APPS_v1_AM4_DIENSTE, AM4-05/06): kind: dienst, ein eigener Prozess ohne Fläche. Start nur mit Schalter `dienste` und einer Freigabe im Posteingang (Gate),
// Stopp jederzeit; der Token des Dienstes ist danach sofort ungültig. Auf dem Host läuft nur Code des Captains oder von SEDRA Gebautes. Text nur mit textContent.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const GRUND = {zu_oft_abgestuerzt: 'zu oft abgestürzt – aus', captain: 'von dir gestoppt', ende: 'mit dem Server beendet'};
  // rein: ein Satz zum Zustand eines Dienstes
  function zustandSatz(x){
    if(x.laeuft) return 'läuft · PID ' + x.pid;
    if(!x.grund) return 'läuft nicht';
    return 'läuft nicht · ' + (GRUND[x.grund] || (String(x.grund).startsWith('abgestuerzt:') ? 'abgestürzt (Exitcode ' + String(x.grund).split(':')[1] + ')' : x.grund));
  }
  const WARN = {dienst_fremd_nur_microvm: 'ein fremder Dienst läuft nur in der microVM – die ist noch nicht angebunden, also gibt es fremde Dienste nicht',
                dienst_microvm_nicht_verfuegbar: 'die microVM ist noch nicht angebunden'};
  function abgewiesenSatz(gruende){ return (gruende || []).map(g=>WARN[g] || g).join(' · '); }

  function zeichnen(ctx, box, v, neu){
    if(!v) return;
    box.append(d().el('h5', 's-head', 'Dienste'));
    if(!v.schalter) box.append(d().el('div', 's-note warn', 'Dienste sind ausgeschaltet (Schalter dienste in switches.yaml). Ein Start wird dann abgelehnt.'));
    if(!(v.dienste || []).length && !(v.abgewiesen || []).length){ box.append(d().el('small', 's-muted', 'Kein Dienst eingebaut.')); return; }
    (v.dienste || []).forEach(x=>{
      const row = d().el('div', 't-modules-row' + (x.laeuft ? ' on' : ''));
      const head = d().el('div');
      head.append(d().el('b', null, x.name), d().el('small', 's-muted', ' · ' + x.id + ' · ' + x.vertrauen + ' · ' + x.ort + ' · ' + zustandSatz(x)));
      row.append(head);
      const knoepfe = d().el('div', 's-row');
      if(x.laeuft) knoepfe.append(d().button('Stoppen', async()=>{ await ctx.api('/api/uix/dienste/stopp', {method: 'POST', body: {id: x.id}}); neu(); }));
      else knoepfe.append(d().button('Starten …', async()=>{
        await ctx.api('/api/uix/dienste/start', {method: 'POST', body: {id: x.id}});
        ctx.shell.open({type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true});
      }));
      row.append(knoepfe); box.append(row);
    });
    (v.abgewiesen || []).forEach(x=>{
      const row = d().el('div', 't-modules-row warn');
      row.append(d().el('b', null, 'Dienst ' + x.id), d().el('small', null, ' nicht eingebaut: ' + abgewiesenSatz(x.gruende)));
      box.append(row);
    });
  }

  root.sedraModulesDienste = {zeichnen, zustandSatz, abgewiesenSatz};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraModulesDienste;
})();
