// UI-Strings des Avatars (avatar.js), DE und EN in einer Datei. Lädt vor i18n.js (shell.yaml); gleiche Schlüssel in beiden Sprachen.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  root.sedraI18nStrings = root.sedraI18nStrings || {};
  root.sedraI18nStrings.de = Object.assign(root.sedraI18nStrings.de || {}, {
    av_freigabe_eine:'Eine Freigabe wartet auf dich.',
    av_freigabe_viele:'{n} Freigaben warten auf dich.',
    av_freigabe_knopf:'Ansehen',
    av_lauf_ok:'Der Lauf „{name}“ ist fertig.',
    av_lauf_fehler:'Der Lauf „{name}“ ist gescheitert. Das Ergebnis steht in der Taskleiste.',
    av_modell:'Es ist noch kein Modell geladen. Ohne Modell kann ich nicht antworten.',
    av_modell_knopf:'Modell wählen',
    av_erste:'Schreib unten, was du vorhast. Mit „/“ gibt es Befehle, mit „+“ hängst du eine Datei an.',
    av_erste_knopf:'Ins Feld',
    av_schliessen:'Hinweis schließen'
  });
  root.sedraI18nStrings.en = Object.assign(root.sedraI18nStrings.en || {}, {
    av_freigabe_eine:'One approval is waiting for you.',
    av_freigabe_viele:'{n} approvals are waiting for you.',
    av_freigabe_knopf:'View',
    av_lauf_ok:'The run “{name}” has finished.',
    av_lauf_fehler:'The run “{name}” failed. The result is in the taskbar.',
    av_modell:'No model is loaded yet. Without a model I cannot answer.',
    av_modell_knopf:'Choose model',
    av_erste:'Write below what you want to do. “/” gives commands, “+” attaches a file.',
    av_erste_knopf:'To the field',
    av_schliessen:'Close hint'
  });
})();
