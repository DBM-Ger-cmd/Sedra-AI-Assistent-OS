// Harness-Shell – Oberflächen-Änderungen (O3 G2/G7, SPEC_APPS_v1_O3PLUS_G9_G2): was die Harness unter einer Aufgabe im Code der Oberfläche geschrieben hat, wirkt erst nach deiner Übernahme.
// Hier steht die Liste der zurückgehaltenen Dateien (der Server liefert bis dahin die bestätigte Fassung), die Sammelkarte „Vorlegen“ (landet im Posteingang, Klasse H, Bestätigung außerhalb des
// Browsers), „Zurücksetzen“ (Klasse N) und „Übernahme zurücknehmen“ an den letzten Übernahmen (G7-05, Klasse N). Steht in den Einstellungen unter Agent → Freigabe-Modus. Text nur mit textContent.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const SATZ = 'Code der Oberfläche läuft in deiner Seite mit allen Rechten – auch Freigaben. Was die Harness dort schreibt, gilt erst nach „Vorlegen“ und deiner Bestätigung; bis dahin liefert der Server die bestätigte Fassung. Ohne Browser: CODE_STAND.bat <projekt> --oberflaeche.';

  // rein: eine Zeile je zurückgehaltener Datei
  function dateiText(e){
    return (e.neu ? 'neu ' : (e.geloescht ? 'gelöscht ' : 'geändert ')) + e.rel + (e.sitzung ? ' · Sitzung ' + e.sitzung : '');
  }
  function uebernahmeText(u){
    return u.id + ' · ' + String(u.zeit || '').slice(0, 16).replace('T', ' ') + ' · ' + (u.dateien || []).length + ' Datei(en) · ' + (u.kanal || '');
  }
  // rein: was die Antwort eines Zurücknehmens dem Captain sagt
  function zuruecknehmenSatz(r){
    const teile = [];
    if((r.hergestellt || []).length) teile.push((r.hergestellt.length) + ' Datei(en) auf die alte Fassung gebracht');
    if((r.verworfen || []).length) teile.push((r.verworfen.length) + ' neue Datei(en) nach verworfen/ verschoben');
    if((r.geaendert || []).length) teile.push('seit der Übernahme geändert und deshalb gelassen: ' + r.geaendert.join(', '));
    if((r.fehlt || []).length) teile.push('alte Fassung nicht mehr gespeichert: ' + r.fehlt.join(', '));
    return teile.join(' · ') || 'Nichts zu tun.';
  }

  function flaeche(S, box){
    const sec = d().el('section', 'hs-einst-gruppe hs-oberflaeche'); sec.append(d().el('div', 'hs-ueber', 'Oberflächen-Änderungen'));
    const satz = d().el('div', 'hs-app-satz', SATZ);
    const liste = d().el('div', 'hs-liste'); liste.setAttribute('aria-live', 'polite');
    const aktionen = d().el('div', 'hs-einst-zeile');
    const uebernahmen = d().el('div', 'hs-liste');
    sec.append(satz, liste, aktionen, uebernahmen); box.append(sec);
    let tot = false;
    const melde = (text, ton)=>{ if(S.hinweis) S.hinweis(text, ton || 'note'); };
    async function laden(){
      if(tot) return;
      let v;
      try{ v = await S.api('/api/harness/oberflaeche'); }catch(err){ liste.replaceChildren(d().el('div', 'hs-leise', 'Nicht lesbar: ' + err.message)); return; }
      if(tot) return;
      const offen = (v.dateien || []).filter(e=>e.geaendert);
      liste.replaceChildren(...(offen.length ? offen.map(e=>{ const z = d().el('div', 'hs-einst-zeile'); z.dataset.datei = e.rel; z.append(d().el('code', 'hs-einst-wert', dateiText(e))); return z; })
                                          : [d().el('div', 'hs-leise', 'Nichts wartet auf deine Übernahme.' + (v.aktiv ? '' : ' (Die Abnahme ist in switches.yaml abgeschaltet.)'))]));
      const vorlegen = d().el('button', 'hs-knopf', 'Sammelkarte vorlegen'); vorlegen.type = 'button'; vorlegen.disabled = !offen.length;
      vorlegen.onclick = async()=>{
        vorlegen.disabled = true;
        try{ const r = await S.api('/api/harness/oberflaeche/vorlegen', {method: 'POST', body: {}}); melde((r.schon_offen ? 'Die Karte liegt schon im Posteingang.' : 'Die Karte liegt im Posteingang.') + ' (' + r.anzahl + ' Dateien)'); }
        catch(err){ melde('Nicht vorgelegt: ' + err.message, 'bad'); }
        laden();
      };
      const zurueck = d().el('button', 'hs-knopf', 'Alles zurücksetzen'); zurueck.type = 'button'; zurueck.disabled = !offen.length;
      zurueck.onclick = async()=>{
        if(typeof confirm === 'function' && !confirm('Alle zurückgehaltenen Dateien auf die bestätigte Fassung zurücksetzen? Neue Dateien wandern nach verworfen/, gelöscht wird nichts.')) return;
        try{ melde(zuruecknehmenSatz(await S.api('/api/harness/oberflaeche/zuruecksetzen', {method: 'POST', body: {}}))); }catch(err){ melde('Nicht zurückgesetzt: ' + err.message, 'bad'); }
        laden();
      };
      aktionen.replaceChildren(vorlegen, zurueck);
      const letzte = (v.uebernahmen || []).slice(0, 5);
      uebernahmen.replaceChildren(...(letzte.length ? [d().el('div', 'hs-ueber', 'Letzte Übernahmen'), ...letzte.map(u=>{
        const z = d().el('div', 'hs-einst-zeile'); z.dataset.uebernahme = u.id;
        const weg = d().el('button', 'hs-knopf', 'Übernahme zurücknehmen'); weg.type = 'button';
        weg.onclick = async()=>{
          weg.disabled = true;
          try{ melde(zuruecknehmenSatz(await S.api('/api/harness/oberflaeche/zuruecknehmen', {method: 'POST', body: {u: u.id}}))); }catch(err){ weg.disabled = false; melde('Nicht zurückgenommen: ' + err.message, 'bad'); }
          laden();
        };
        z.append(d().el('code', 'hs-einst-wert', uebernahmeText(u)), weg);
        return z;
      })] : []));
    }
    laden();
    return {abbauen(){ tot = true; }, laden};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.oberflaeche = {flaeche, dateiText, uebernahmeText, zuruecknehmenSatz, SATZ};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.oberflaeche;
})();
