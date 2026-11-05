// Harness-Shell – die Module der Oberfläche für das Kontextmenü (kontext.js): je Zone und Baustein ein Name, der Selektor, an dem man ihn erkennt, und die Dateien, in denen er lebt.
// Das ist die Landkarte, nach der "Im Chat anpassen" dem Modell sagt, WO etwas geändert werden soll. Ein neues Modul trägt sich in seiner eigenen Datei mit
// `root.sedraHarness.kontext.registrieren({...})` ein; diese Tabelle gilt nur für das, was es schon gibt. Die Reihenfolge der Anmeldung ist egal: das innerste passende Modul steht zuerst.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const K = root.sedraHarness && root.sedraHarness.kontext;
  if(!K) return;
  const klick = text=>(S, el)=>[{text, tun: ()=>el.click()}];

  [
    {id: 'harness', titel: 'One Sedra', selektor: 'body', dateien: ['shell.js', 'shell.yaml']},
    {id: 'seitenleiste', titel: 'Seitenleiste', selektor: '.hs-seite', dateien: ['seite.js', 'seitenleiste.js']},
    {id: 'sitzung', titel: 'Sitzung', selektor: '.hs-sz', dateien: ['seite.js'], eintraege: klick('Sitzung öffnen')},
    {id: 'reiterleiste', titel: 'Reiterleiste', selektor: '.hs-reiter', dateien: ['reiter.js']},
    {id: 'reiter', titel: 'Reiter', selektor: '.hs-tab', dateien: ['reiter.js'],
     eintraege: (S, el)=>[{text: 'Reiter schließen', tun: ()=>{ if(el.dataset.reiter && root.sedraHarness.reiter) root.sedraHarness.reiter.schliessen(S, el.dataset.reiter); }}]},
    {id: 'flaeche', titel: 'Arbeitsfläche', selektor: '.hs-flaeche', dateien: ['verlauf.js', 'markdown.js']},
    {id: 'nachricht', titel: 'Deine Nachricht', selektor: '.hs-captain', dateien: ['verlauf.js']},
    {id: 'antwort', titel: 'Antwort', selektor: '.hs-antwort', dateien: ['verlauf.js', 'strom.js', 'markdown.js']},
    {id: 'werkzeugzeile', titel: 'Werkzeugaufruf', selektor: '.hs-wz', dateien: ['zeilen.js']},
    {id: 'karte', titel: 'Freigabe-Karte', selektor: '.hs-karte', dateien: ['karte.js']},
    {id: 'eingabe', titel: 'Eingabebereich', selektor: '.hs-eingabe', dateien: ['eingabe.js', 'anhang.js', 'modell.js']},
    {id: 'taskleiste', titel: 'Taskleiste', selektor: '.hs-taskleiste', dateien: ['taskleiste.js']},
    {id: 'statuszelle', titel: 'Statuszelle', selektor: '.hs-zelle', dateien: ['taskleiste.js'], eintraege: klick('Dazugehörige App öffnen')},
    {id: 'startmenue', titel: 'Start-Menü', selektor: '.hs-start-menue', dateien: ['startmenue.js', 'startliste.js', 'start_gruppen.json']},
    {id: 'app', titel: 'App', selektor: '.hs-app-box', dateien: ['app.js']},
    {id: 'freigaben', titel: 'Freigaben', selektor: '.hs-aufgaben', dateien: ['aufgabe.js', 'erlaubnisse.js', 'katalog_editor.js']},
    {id: 'token', titel: 'Sedra Token', selektor: '.hs-token-feld', dateien: ['tokenseite.js']},
    {id: 'builder', titel: 'Desktop Builder', selektor: '.hs-builder', dateien: ['builder.js', 'desktop.js']},
    {id: 'info', titel: 'Info', selektor: '.hs-info-modelle, .hs-info-leiste, .hs-info-liste, .hs-info-verlauf', dateien: ['infoseite.js']},
    {id: 'einstellungen', titel: 'Einstellungen', selektor: '[class*="hs-einst-"]', dateien: ['einstellungen.js', 'einstellungen_seiten.js', 'einstellungen.css']}
  ].forEach(m=>K.registrieren(m));
})();
