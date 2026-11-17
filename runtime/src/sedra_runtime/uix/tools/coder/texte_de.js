/* Sedra IDE: Texte Deutsch. Gleiche Schluessel wie texte_en.js. */
(function (root) {
  'use strict';
  const S = root.SIDE = root.SIDE || {};
  S.texte = S.texte || {};
  S.texte.de = {
    titel: 'Sedra IDE',
    sprung: 'Zum Editor springen',
    beispiel: 'Beispieldaten',
    quelle_beispiel: 'Quelle: Beispieldaten für Agenten, Terminal, Chat und Erweiterungen. Dateien kommen aus dem Projekt, wenn eines da ist.',
    taste_strg: 'Strg', taste_umschalt: 'Umschalt',

    mn_leiste: 'Hauptmenü', mn_datei: 'Datei', mn_bearbeiten: 'Bearbeiten', mn_auswahl: 'Auswahl', mn_ansicht: 'Ansicht',
    mn_gehe: 'Gehe zu', mn_ausfuehren: 'Ausführen', mn_terminal: 'Terminal', mn_hilfe: 'Hilfe',

    bf_palette: 'Befehlspalette anzeigen', bf_dateiSuche: 'Datei öffnen …', bf_geheZeile: 'Gehe zu Zeile …',
    bf_seiteLinks: 'Seitenleiste links ein/aus', bf_panel: 'Panel unten ein/aus', bf_seiteRechts: 'Seitenleiste rechts ein/aus',
    bf_reiterVor: 'Nächster Reiter', bf_reiterZurueck: 'Vorheriger Reiter', bf_schliessen: 'Reiter schließen',
    bf_speichern: 'Speichern', bf_alleSpeichern: 'Alle speichern', bf_teilen: 'Editor teilen', bf_neueDatei: 'Neue Datei',
    bf_suchenDatei: 'Suchen', bf_suchen: 'In Dateien suchen', bf_allesWaehlen: 'Alles auswählen',
    bf_ansichtExplorer: 'Explorer anzeigen', bf_ansichtQuellcode: 'Quellcodeverwaltung anzeigen', bf_ansichtAusfuehren: 'Ausführen anzeigen',
    bf_ansichtErweiterungen: 'Erweiterungen anzeigen', bf_ansichtAgenten: 'Agenten anzeigen', bf_terminal: 'Terminal fokussieren',
    bf_lauf: 'Beispiellauf starten', bf_fokusEditor: 'Editor fokussieren', bf_bereichVor: 'Nächster Bereich', bf_bereichZurueck: 'Vorheriger Bereich',
    bf_zurueck: 'Zurück', bf_vor: 'Vor', bf_willkommen: 'Willkommen anzeigen', bf_thema: 'Thema wechseln (Dunkel/Hell)',
    bf_sprache: 'Sprache wechseln (Deutsch/English)', bf_beispieldaten: 'Beispieldaten ein/aus', bf_layoutStandard: 'Anordnung zurücksetzen',
    bf_ueber: 'Über Sedra IDE',
    ueber_text: 'Sedra IDE, Entwurf. Läuft ohne Netz, alle Inhalte sind Beispieldaten.',
    bsp_an: 'Beispieldaten eingeblendet.', bsp_aus: 'Beispieldaten ausgeblendet (Leerzustand).',

    an_leiste: 'Aktivitätsleiste', an_explorer: 'Explorer', an_suche: 'Suche', an_quellcode: 'Quellcodeverwaltung', an_ausfuehren: 'Ausführen',
    an_erweiterungen: 'Erweiterungen', an_agenten: 'Agenten', an_konto: 'Konto', an_einstellungen: 'Einstellungen',
    an_konto_aus: 'Kein Konto: Diese Stufe arbeitet ohne Anmeldung.', an_aenderungen: '{0} geänderte Dateien',

    ex_offen: 'Offene Editoren', ex_ordner: 'Ordner', ex_gliederung: 'Gliederung', ex_zeitachse: 'Zeitachse',
    ex_ungespeichert: 'ungespeichert', ex_gruppe: 'Gruppe {0}',
    gl_klasse: 'Klasse', gl_funktion: 'Funktion', gl_wert: 'Wert', gl_methode: 'Methode', gl_schluessel: 'Schlüssel', gl_unter: 'Eintrag', gl_titel: 'Überschrift',
    git_neu: 'Neu, noch nicht verfolgt', git_geaendert: 'Geändert', git_enthaelt: 'Enthält Änderungen',

    leer_ordner: 'Kein Ordner geöffnet.', leer_gliederung: 'Keine Gliederung für diese Datei.', leer_keine_datei: 'Keine Datei geöffnet.',
    leer_zeitachse: 'Keine Einträge.', leer_zuletzt: 'Keine zuletzt geöffneten Dateien.', leer_aenderungen: 'Keine Änderungen.',
    leer_laeufe: 'Keine Läufe eingerichtet.', leer_erweiterungen: 'Keine Erweiterungen gefunden.', leer_agenten: 'Keine Agenten verbunden.',
    leer_sitzungen: 'Keine Sitzungen.', leer_chat: 'Noch keine Nachrichten.', leer_live: 'Keine Ereignisse.', leer_detail: 'Kein Agent gewählt.',
    leer_terminal: 'Terminal leer.', leer_probleme: 'Keine Probleme gefunden.', leer_debug: 'Keine Debug-Ausgabe.',
    leer_ausgabe: 'Keine Ausgabe.', leer_logs: 'Keine Log-Zeilen.',

    su_platz: 'Suchen', su_hinweis: 'Suchbegriff eingeben. Gesucht wird in allen Beispieldateien.', su_nichts: 'Keine Treffer für „{0}“.', su_anzahl: '{0} Treffer',
    qc_nachricht: 'Nachricht', qc_uebernehmen: 'Übernehmen', qc_aenderungen: 'Änderungen', qc_attrappe: 'Attrappe: Es wird nichts übernommen.',
    au_start: 'Starten', au_laeufe: 'Läufe', au_lauf_js: 'Beispiel starten', au_lauf_test: 'Tests laufen lassen',
    au_gestartet: 'Beispiellauf für {0} (Attrappe, nichts ausgeführt)',
    erw_platz: 'Erweiterungen durchsuchen', erw_installiert: 'Installiert', erw_empfohlen: 'Empfohlen', erw_installieren: 'Installieren',
    erw_attrappe: 'Attrappe: Ohne Netz wird nichts installiert.',
    erw_python: 'Syntaxfarben und Gliederung für Python', erw_yaml: 'Syntaxfarben und Prüfung für YAML', erw_agenten: 'Agentenliste und Live-Coding',
    erw_markdown: 'Syntaxfarben und Gliederung für Markdown', erw_pruefer: 'Regelprüfung für Zeilenzahl und Tokens', erw_zweige: 'Zweige und Verlauf anzeigen',

    ag_frage: 'Was soll ich tun?', ag_liste: 'Agenten', ag_letzte: 'Letzte', ag_platz: 'Aufgabe eingeben …', ag_modus: 'Modus',
    ag_plan: 'Plan', ag_act: 'Act', ag_auto: 'Auto-Freigabe:', ag_auto_an: 'Lesen, Bearbeiten', ag_auto_aus: 'aus',
    ag_rolle_bau: 'Bau', ag_rolle_doku: 'Dokumente', ag_rolle_leitung: 'Leitung', ag_rolle_test: 'Tests',
    zs_aktiv: 'arbeitet', zs_wartet: 'wartet', zs_fehler: 'Fehler',

    re_leiste: 'Chat-Leiste', re_chat: 'Chat', re_sitzungen: 'Sitzungen', re_live: 'Live-Coding', re_detail: 'Agent-Detail',
    re_live_mehr: 'Beispielereignis hinzufügen', re_sitzung_attrappe: 'Sitzung „{0}“: Attrappe, kein Verlauf geladen.',
    ch_platz: 'Nachricht schreiben …', ch_senden: 'Senden', ch_ich: 'Du', ch_hinweis: 'Eingabe sendet, Umschalt+Eingabe: neue Zeile',
    ch_antwort: 'Attrappe ({0}): Nachricht notiert, es wurde nichts gesendet.',
    ev_liest: 'liest', ev_schreibt: 'schreibt', ev_prueft: 'prüft', ev_meldet: 'meldet',
    dt_rolle: 'Rolle', dt_auftrag: 'Auftrag', dt_datei: 'Datei', dt_keine: 'keine', dt_schritte: 'Schritte', dt_seit: 'Seit', dt_oeffnen: 'Datei öffnen',

    pn_panel: 'Panel', pn_terminal: 'Terminal', pn_ausgabe: 'Ausgabe', pn_probleme: 'Probleme', pn_debug: 'Debug-Konsole', pn_logs: 'Live-Logs',
    tm_gruss_echt: 'Sedra Terminal (nur Anzeige). "hilfe" zeigt die Befehle. Es zeigt, was der Coder aus dem Projekt geladen hat, und führt keine Befehle auf dem Rechner aus.', tm_erst_oeffnen: 'Noch nicht geöffnet: {0}. Mit "open {0}" laden, dann zeigt cat den Text.', tm_unbekannt_echt: 'Unbekannter Befehl: {0}. Dieses Terminal führt keine echten Befehle aus (nur hilfe, ls, cat, open, status, echo, agenten, clear).', tm_ls_hinweis: 'Nur geladene Ordner. Ordner im Explorer aufklappen, dann erscheinen ihre Dateien.', df_titel: 'Änderungen: {0}', df_anzahl: '{0} Zeilen geändert', df_gleich: 'Keine Änderung gegenüber dem letzten Commit.', df_links: 'Letzter Commit', df_rechts: 'Editor', df_datei: 'Datei öffnen', df_zu: 'Diff schließen', df_fehler_kein_git: 'Kein Git-Ordner im Projekt.', df_fehler_zu_gross: 'Die Datei ist zu groß für den Vergleich.', df_fehler_binaer: 'Die Datei ist kein Text.', df_fehler_git_zeit: 'Git antwortet nicht rechtzeitig.', df_fehler_sonst: 'Der Vergleich ist nicht möglich.', su_laeuft: 'Suche läuft …', su_fehler: 'Die Suche ist nicht möglich.', su_gekuerzt: '(gekürzt: nicht alles angezeigt)', su_ersetzen_platz: 'Ersetzen durch (nur im Editor)', su_ersetzen: 'Ersetzen', su_ersetzen_datei: 'In {0} ersetzen (nur im Editor, nicht gespeichert)', su_ersetzen_leer: 'Erst den Ersetzen-Text eingeben.', su_ersetzt: '{0} Stellen in {1} ersetzt (ungespeichert; Speichern stellt den Antrag an die Freigaben).', su_ersetzt_nichts: 'In {0} nichts zu ersetzen.', vw_ok: 'OK', vw_abbruch: 'Abbrechen', vw_hinweis_antrag: 'Das ist nur ein Antrag an die Freigaben. Geändert wird erst nach deiner Zustimmung.', vw_neuer_ordner: 'Neuer Ordner', vw_umbenennen: 'Umbenennen', vw_loeschen: 'Löschen', vw_ordner_titel: 'Neuer Ordner (Pfad im Projekt)', vw_umbenennen_titel: 'Umbenennen: {0}', vw_loeschen_titel: '{0} löschen?', vw_loeschen_hinweis: 'Antrag an die Freigaben. Gelöscht werden nur Dateien und leere Ordner; erst nach deiner Zustimmung.', vw_antrag_ordner: 'Antrag an die Freigaben gestellt: Ordner {0} anlegen.', vw_antrag_umbenennen: 'Antrag an die Freigaben gestellt: {0} umbenennen in {1}.', vw_antrag_loeschen: 'Antrag an die Freigaben gestellt: {0} löschen.', vw_fertig_ordner: 'Ordner {0} angelegt (freigegeben).', vw_fertig_umbenennen: '{0} umbenannt in {1} (freigegeben).', vw_fertig_loeschen: '{0} gelöscht (freigegeben).', sp_fehler_ziel_existiert: 'Das Ziel gibt es schon.', sp_fehler_nicht_gefunden: 'Datei oder Ordner nicht gefunden.', sp_fehler_ordner_nicht_leer: 'Der Ordner ist nicht leer. Gelöscht werden nur leere Ordner.', sp_fehler_invalid_kind: 'Unbekannte Aktion.', tm_gruss: 'Sedra Terminal (Attrappe). "hilfe" zeigt die Befehle. Es wird nichts auf dem Rechner ausgeführt.',
    tm_hilfe: 'Befehle: hilfe, ls, cat <datei>, open <datei>, echo <text>, status, agenten, clear',
    tm_keine_datei: 'Datei nicht gefunden: {0}', tm_geoeffnet: 'Geöffnet: {0}', tm_unbekannt: 'Unbekannter Befehl: {0}', tm_eingabe: 'Terminal-Eingabe',
    db_eingabe: 'Debug-Eingabe', db_attrappe: 'Attrappe: Ausdrücke werden nicht ausgewertet.',
    pb_todo: 'Offener Punkt (TODO)', pb_leerraum: 'Leerraum am Zeilenende', pb_tab_yaml: 'Tabulator in YAML',

    echt_marke: 'Projekt, nur lesen', echt_geladen: 'Projekt „{0}“ geladen (nur lesen).',
    echt_fehler_lesen: '„{0}“ konnte nicht gelesen werden.', echt_fehler_binaer: '„{0}“ ist keine Textdatei und wird nicht angezeigt.',
    echt_fehler_gross: '„{0}“ ist für die Vorschau zu groß (über 100 kB).', echt_fehler_gesperrt: '„{0}“ ist gesperrt (Schlüssel und lokale Konfiguration werden nie angezeigt).',
    sp_antrag: 'Antrag an die Freigaben gestellt: {0} (+{1} / −{2} Zeilen). Geschrieben wird erst nach deiner Zustimmung.', sp_antrag_neu: 'Antrag an die Freigaben gestellt: neue Datei {0}. Geschrieben wird erst nach deiner Zustimmung.', sp_wartet: '{0}: Der Antrag wartet noch auf deine Zustimmung in den Freigaben.', sp_nichts: 'Keine ungespeicherten Dateien.', sp_neben: 'Antrag offen', sp_angewendet: '{0} gespeichert (freigegeben).', sp_abgelehnt: '{0}: Antrag abgelehnt, nichts geschrieben.', sp_zeit: '{0}: Keine Antwort mehr abgefragt. Die Freigabe bleibt offen; Antrag bei Bedarf neu stellen.', sp_fehler_file_changed_repeat_request: 'Die Datei hat sich auf der Platte geändert. Die Freigabe gilt nicht mehr: bitte neu speichern.', sp_fehler_captain_approval: 'Ohne Zustimmung des Captains wird nichts geschrieben.', sp_fehler_already_applied: 'Dieser Antrag wurde schon ausgeführt.', sp_fehler_keine_aenderung: 'Keine Änderung gegenüber der Datei im Projekt.', sp_fehler_access_blocked: 'Diese Datei ist gesperrt (Schlüssel oder lokale Konfiguration).', sp_fehler_datei_zu_gross: 'Die Datei ist zu groß zum Speichern aus dem Coder.', sp_fehler_datei_nicht_lesbar: 'Die Datei ist kein UTF-8-Text.', sp_fehler_ziel_ist_ordner: 'Das Ziel ist ein Ordner.', sp_fehler_content_too_large: 'Der Text ist zu groß zum Speichern aus dem Coder.', sp_fehler_invalid_path: 'Ungültiger Dateiname.', sp_fehler_write_failed: 'Schreiben fehlgeschlagen.', sp_fehler_sonst: 'Speichern nicht möglich.', su_hinweis_echt: 'Suchbegriff eingeben. Gesucht wird nur in bereits geöffneten Dateien.', qc_git_fehlt: 'Kein Git-Ordner im Projekt oder Git nicht erreichbar.', qc_aktualisieren: 'Aktualisieren', qc_echt_hinweis: 'Keine Änderungen im Projekt (nur lesen).',
    ed_reiter: 'Reiter der Editorgruppe {0}', ed_schliessen: '{0} schließen', ed_brotkrumen: 'Pfad', ed_eingabe: 'Editor {0}', ed_minimap: 'Minimap',
    ed_tab_frei: 'Tabulator verlässt jetzt einmal den Editor.', ed_gruppe_zu: 'Gruppe schließen', ed_teilen_voll: 'Höchstens drei Editorgruppen.',
    ed_gespeichert: '{0} gespeichert (nur im Speicher der Seite).', ed_alle_gespeichert: 'Alle Dateien gespeichert (nur im Speicher der Seite).',

    wk_reiter: 'Willkommen', wk_titel: 'Sedra IDE', wk_unter: 'Entwickeln mit SEDRA', wk_start: 'Start', wk_zuletzt: 'Zuletzt', wk_einfuehrungen: 'Einführungen',
    wk_neu: 'Neue Datei …', wk_oeffnen: 'Datei öffnen …', wk_ordner: 'Ordner öffnen …', wk_verbinden: 'Verbinden …',
    wk_verbinden_aus: 'Verbinden ist in dieser Stufe nicht angebunden.',
    wk_e1_titel: 'Befehlspalette', wk_e1_text: 'Alle Befehle mit Strg+Umschalt+P oder F1 suchen.',
    wk_e2_titel: 'Geteilter Editor', wk_e2_text: 'Zwei Dateien nebeneinander bearbeiten.',
    wk_e3_titel: 'Agenten', wk_e3_text: 'Agentenliste, Live-Coding und Chat ansehen.',
    wk_e4_titel: 'Dunkel und Hell', wk_e4_text: 'Das Thema der Oberfläche wechseln.',

    pl_feld: 'Befehl oder Datei', pl_platz: 'Dateiname, ">" für Befehle, ":" für Zeile', pl_nichts: 'Keine Treffer.',
    pl_keine_datei: 'Keine Datei geöffnet.', pl_gehe_zeile: 'Gehe zu Zeile {0}', pl_zeile_hinweis: 'Zeilennummer zwischen 1 und {0} eingeben.',

    weg_lokal: 'Lokales Modell ({0})', weg_cloud: 'Cloud: {0} ({1})', weg_bereit: 'bereit', weg_laedt: 'Verfügbare Modelle werden gesucht …',
    weg_keine: 'Kein Modell bereit: lokales Modell starten oder in den Einstellungen einen Cloud-Anbieter einschalten.',
    ag_denkt: 'Denkt nach …', ag_hinweis: 'Hinweis', ag_laeuft: 'Es läuft noch eine Frage.', ag_kein_weg: 'Kein Modell gewählt oder bereit. Der Agent kann nur antworten, nichts speichern.',
    ag_kein_modell: 'Kein lokales Modell geladen.', ag_gesperrt_schutz: 'Vom Inhaltsschutz gestoppt ({0}). Es wurde nichts an die Cloud gesendet.', ag_fehler: 'Das Modell hat nicht geantwortet ({0}).',
    ag_kontext: '{0} Datei(en) als Kontext', ag_ohne_kontext: 'ohne Dateikontext', ag_ausgelassen: 'Nicht mitgesendet: {0}.',
    ag_grund_gesperrt: 'gesperrt', ag_grund_binaer: 'keine Textdatei', ag_grund_zu_gross: 'zu groß', ag_grund_nicht_lesbar: 'nicht lesbar', ag_grund_kein_platz: 'kein Platz mehr',
    st_ordner: 'Arbeitsbereich', st_zweig: 'Zweig (Beispiel)', st_probleme: '{0} Fehler, {1} Warnungen', st_zeile: 'Zeile {0}, Spalte {1}',
    st_zeile_kurz: 'Zeile {0}', st_auswahl: '({0} ausgewählt)', st_einrueckung: 'Leerzeichen: 2', st_kodierung: 'Kodierung', st_zeilenende: 'Zeilenende',
    st_sprache: 'Sprache der Datei', st_text: 'Text',
    tl_links: 'Breite der linken Seitenleiste', tl_rechts: 'Breite der rechten Seitenleiste', tl_panel: 'Höhe des Panels'
  };
})(window);
