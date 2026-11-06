// Lokal + KI im Gespräch: das lokale Modell entwirft, die Cloud prüft – in einem Fenster (zweite Datei des Werkzeugs „Gespräch“,
// wegen der 400-Zeilen-Regel des Vertrags). Beide Schritte gehen durch den Inhaltsschutz; `tool` ist das Gespräch selbst.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;

  async function sendKombi(tool, text){
    const cloud = [...tool.picker.options].find(o=>o.value.startsWith('cloud:'));
    if(!cloud){ tool.line('SEDRA', 'Für Lokal + KI braucht es ein Cloud-Modell. Der Anbieter ist noch nicht bereit (Schlüssel prüfen).', 'warn'); return; }
    const [pid, model] = cloud.value.slice('cloud:'.length).split('|');
    tool.line('Du', text, 'me');
    const row = tool.line('SEDRA', 'Lokal entwirft, dann prüft die Cloud …', 'note');
    try{
      const out = await tool.ctx.api('/api/chat/kombi', {method: 'POST', body: {provider: pid, model, text, history: root.sedraTalkVerlauf.fuerCloud(tool.history).slice(-8), vorgang: tool.vorgang || ''}});
      row.remove();
      if(out.status === 'completed'){
        tool.line('SEDRA lokal', out.local || '(leer)', '');
        tool.line('Cloud · ' + pid + ' / ' + model, out.cloud || '(leere Antwort)', '');
        // Verlauf: die Frage und die Antwort beider Modelle, damit die nächste Runde beide Seiten kennt
      tool.history.push({role: 'user', content: text}, {role: 'assistant', content: 'Lokaler Entwurf:\n' + (out.local || '') + '\n\nPrüfung (Cloud):\n' + (out.cloud || '')});
      }else if(out.status === 'no_local'){
        tool.line('SEDRA', 'Kein lokales Modell geladen: ' + (out.reason || 'Lokal + KI braucht das lokale Modell.'), 'warn');
      }else{
        if(out.local) tool.line('SEDRA lokal', out.local, '');
        tool.line('SEDRA', out.reason || 'Der Cloud-Schritt ist nicht gelaufen.', 'warn');
      }
    }catch(err){
      row.remove(); tool.line('SEDRA', 'Lokal + KI fehlgeschlagen: ' + err.message, 'warn');
    }
  }

  root.sedraTalkKombi = {sendKombi};
  if(typeof module !== 'undefined' && module.exports) module.exports = {sendKombi};
})();
