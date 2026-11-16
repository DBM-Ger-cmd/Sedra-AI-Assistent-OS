/* Sedra IDE: Beispieldaten fuer Agenten, Sitzungen, Ereignisse, Erweiterungen. Keine echte Verbindung. */
(function (root) {
  'use strict';
  const S = root.SIDE;

  S.AGENTEN = [
    { id: 'hermes', name: 'Hermes', rolle_key: 'ag_rolle_bau', zustand: 'aktiv', auftrag: 'Runde 1: Editor ohne Netz', datei: 'src/start.js', schritte: 14, seit: '14:02' },
    { id: 'pi', name: 'Pi', rolle_key: 'ag_rolle_doku', zustand: 'wartet', auftrag: 'Plan ergaenzen', datei: 'docs/plan.md', schritte: 6, seit: '13:40' },
    { id: 'manager', name: 'Manager', rolle_key: 'ag_rolle_leitung', zustand: 'aktiv', auftrag: 'Auftraege verteilen', datei: '', schritte: 3, seit: '13:15' },
    { id: 'testbot', name: 'Testbot', rolle_key: 'ag_rolle_test', zustand: 'fehler', auftrag: 'tests/test_start.py', datei: 'tests/test_start.py', schritte: 2, seit: '14:20' }
  ];

  S.SITZUNGEN = [
    { id: 's1', titel: 'Editor ohne Netz', agent: 'Hermes', zeit: '14:02', text: 'Monaco ersetzt durch eigenen Editor' },
    { id: 's2', titel: 'Plan Runde 2', agent: 'Pi', zeit: '13:40', text: 'Aufteilen in Dateien bis 400 Zeilen' },
    { id: 's3', titel: 'Testlauf', agent: 'Testbot', zeit: '13:05', text: '2 Tests, 1 rot' }
  ];

  S.EREIGNISSE = [
    { zeit: '14:02:10', wer: 'Hermes', art: 'liest', text: 'src/start.js', datei: 'src/start.js', zeile: 1 },
    { zeit: '14:02:31', wer: 'Hermes', art: 'schreibt', text: 'src/start.js Zeile 19', datei: 'src/start.js', zeile: 19 },
    { zeit: '14:03:02', wer: 'Pi', art: 'schreibt', text: 'docs/plan.md Zeile 8', datei: 'docs/plan.md', zeile: 8 },
    { zeit: '14:03:40', wer: 'Testbot', art: 'prueft', text: 'tests/test_start.py', datei: 'tests/test_start.py', zeile: 6 },
    { zeit: '14:04:05', wer: 'Manager', art: 'meldet', text: 'Auftrag an Hermes vergeben', datei: '', zeile: 0 }
  ];
  S.EREIGNIS_VORRAT = [
    { wer: 'Hermes', art: 'schreibt', text: 'src/agenten.py Zeile 11', datei: 'src/agenten.py', zeile: 11 },
    { wer: 'Testbot', art: 'prueft', text: 'src/werkzeuge.py', datei: 'src/werkzeuge.py', zeile: 4 },
    { wer: 'Pi', art: 'liest', text: 'README.md', datei: 'README.md', zeile: 1 }
  ];

  S.AUSGABE = [
    { art: 'leise', text: '[09:12:00] Arbeitsbereich geladen: sedra-arbeitsbereich' },
    { art: 'ok', text: '[09:12:00] 9 Beispieldateien, kein Netzabruf' },
    { art: 'warnung', text: '[10:40:12] docs/plan.md: offener Punkt (TODO)' },
    { art: 'fehler', text: '[14:20:44] Testbot: 1 Test rot (Beispiel)' }
  ];
  S.DEBUG = [
    { art: 'leise', text: 'Debug-Sitzung nicht gestartet (Beispieldaten).' },
    { art: '', text: '> bereich.offen.length' },
    { art: 'ok', text: '1' }
  ];
  S.LOGS = [
    { art: 'leise', text: '14:02:10 INFO  hermes   Datei gelesen src/start.js' },
    { art: '', text: '14:02:31 INFO  hermes   Aenderung vorgeschlagen (1 Datei)' },
    { art: 'warnung', text: '14:03:40 WARN  testbot  Test laeuft laenger als erwartet' },
    { art: 'fehler', text: '14:20:44 ERROR testbot  test_kuerze fehlgeschlagen (Beispiel)' }
  ];

  S.ERWEITERUNGEN = [
    { name: 'Sedra Python', text_key: 'erw_python', installiert: true },
    { name: 'Sedra YAML', text_key: 'erw_yaml', installiert: true },
    { name: 'Sedra Agenten', text_key: 'erw_agenten', installiert: true },
    { name: 'Sedra Markdown', text_key: 'erw_markdown', installiert: true },
    { name: 'Sedra Pruefer', text_key: 'erw_pruefer', installiert: false },
    { name: 'Sedra Zweige', text_key: 'erw_zweige', installiert: false }
  ];

  S.CHAT = [
    { von: 'Hermes', ich: false, text: 'Bereit. Dies ist eine Attrappe mit Beispieldaten, es besteht keine Verbindung.' }
  ];
})(window);
