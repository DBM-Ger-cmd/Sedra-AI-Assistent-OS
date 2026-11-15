// UI-Strings der Delegations-Karte (delegation.js), DE und EN in einer Datei. Lädt vor i18n.js (shell.yaml); gleiche Schlüssel in beiden Sprachen.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  root.sedraI18nStrings = root.sedraI18nStrings || {};
  root.sedraI18nStrings.de = Object.assign(root.sedraI18nStrings.de || {}, {
    dg_karte:'Delegation',
    dg_titel:'Delegation an {n} Helfer',
    dg_aktiv:'{a} von {n} arbeiten',
    dg_abgeschlossen:'abgeschlossen',
    dg_alle_anhalten:'Alle anhalten',
    dg_anhalten:'Anhalten',
    dg_verlauf:'Verlauf',
    dg_freigabe:'Freigabe ansehen',
    dg_z_wartet:'wartet auf einen Platz',
    dg_z_laeuft:'arbeitet',
    dg_z_freigabe:'wartet auf deine Freigabe',
    dg_z_fertig:'fertig',
    dg_z_gescheitert:'gescheitert',
    dg_z_angehalten:'angehalten',
    dg_zug:'1 Zug',
    dg_zuege:'{n} Züge',
    dg_token:'{n} Token',
    dg_zelle:'Team {a}/{n}',
    dg_zelle_titel:'Helfer der laufenden Delegation: arbeiten / gesamt',
    dg_stopp_fehler:'Anhalten ging nicht: ',
    dg_helfer:'Helfer'
  });
  root.sedraI18nStrings.en = Object.assign(root.sedraI18nStrings.en || {}, {
    dg_karte:'Delegation',
    dg_titel:'Delegation to {n} helpers',
    dg_aktiv:'{a} of {n} working',
    dg_abgeschlossen:'finished',
    dg_alle_anhalten:'Stop all',
    dg_anhalten:'Stop',
    dg_verlauf:'History',
    dg_freigabe:'View approval',
    dg_z_wartet:'waiting for a slot',
    dg_z_laeuft:'working',
    dg_z_freigabe:'waiting for your approval',
    dg_z_fertig:'done',
    dg_z_gescheitert:'failed',
    dg_z_angehalten:'stopped',
    dg_zug:'1 turn',
    dg_zuege:'{n} turns',
    dg_token:'{n} tokens',
    dg_zelle:'Team {a}/{n}',
    dg_zelle_titel:'Helpers of the running delegation: working / total',
    dg_stopp_fehler:'Could not stop: ',
    dg_helfer:'Helper'
  });
})();
