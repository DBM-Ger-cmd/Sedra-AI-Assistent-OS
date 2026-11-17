/* Sedra IDE: texts English. Same keys as texte_de.js. */
(function (root) {
  'use strict';
  const S = root.SIDE = root.SIDE || {};
  S.texte = S.texte || {};
  S.texte.en = {
    titel: 'Sedra IDE',
    sprung: 'Skip to editor',
    beispiel: 'Sample data',
    quelle_beispiel: 'Source: sample data for agents, terminal, chat and extensions. Files come from the project when there is one.',
    taste_strg: 'Ctrl', taste_umschalt: 'Shift',

    mn_leiste: 'Main menu', mn_datei: 'File', mn_bearbeiten: 'Edit', mn_auswahl: 'Selection', mn_ansicht: 'View',
    mn_gehe: 'Go', mn_ausfuehren: 'Run', mn_terminal: 'Terminal', mn_hilfe: 'Help',

    bf_palette: 'Show command palette', bf_dateiSuche: 'Open file …', bf_geheZeile: 'Go to line …',
    bf_seiteLinks: 'Toggle left side bar', bf_panel: 'Toggle bottom panel', bf_seiteRechts: 'Toggle right side bar',
    bf_reiterVor: 'Next tab', bf_reiterZurueck: 'Previous tab', bf_schliessen: 'Close tab',
    bf_speichern: 'Save', bf_alleSpeichern: 'Save all', bf_teilen: 'Split editor', bf_neueDatei: 'New file',
    bf_suchenDatei: 'Find', bf_suchen: 'Find in files', bf_allesWaehlen: 'Select all',
    bf_ansichtExplorer: 'Show explorer', bf_ansichtQuellcode: 'Show source control', bf_ansichtAusfuehren: 'Show run',
    bf_ansichtErweiterungen: 'Show extensions', bf_ansichtAgenten: 'Show agents', bf_terminal: 'Focus terminal',
    bf_lauf: 'Start sample run', bf_fokusEditor: 'Focus editor', bf_bereichVor: 'Next area', bf_bereichZurueck: 'Previous area',
    bf_zurueck: 'Back', bf_vor: 'Forward', bf_willkommen: 'Show welcome', bf_thema: 'Switch theme (dark/light)',
    bf_sprache: 'Switch language (Deutsch/English)', bf_beispieldaten: 'Toggle sample data', bf_layoutStandard: 'Reset layout',
    bf_ueber: 'About Sedra IDE',
    ueber_text: 'Sedra IDE, draft. Runs without network, all content is sample data.',
    bsp_an: 'Sample data shown.', bsp_aus: 'Sample data hidden (empty state).',

    an_leiste: 'Activity bar', an_explorer: 'Explorer', an_suche: 'Search', an_quellcode: 'Source control', an_ausfuehren: 'Run',
    an_erweiterungen: 'Extensions', an_agenten: 'Agents', an_konto: 'Account', an_einstellungen: 'Settings',
    an_konto_aus: 'No account: this stage works without sign-in.', an_aenderungen: '{0} changed files',

    ex_offen: 'Open editors', ex_ordner: 'Folder', ex_gliederung: 'Outline', ex_zeitachse: 'Timeline',
    ex_ungespeichert: 'unsaved', ex_gruppe: 'Group {0}',
    gl_klasse: 'Class', gl_funktion: 'Function', gl_wert: 'Value', gl_methode: 'Method', gl_schluessel: 'Key', gl_unter: 'Entry', gl_titel: 'Heading',
    git_neu: 'New, untracked', git_geaendert: 'Modified', git_enthaelt: 'Contains changes',

    leer_ordner: 'No folder opened.', leer_gliederung: 'No outline for this file.', leer_keine_datei: 'No file opened.',
    leer_zeitachse: 'No entries.', leer_zuletzt: 'No recent files.', leer_aenderungen: 'No changes.',
    leer_laeufe: 'No runs configured.', leer_erweiterungen: 'No extensions found.', leer_agenten: 'No agents connected.',
    leer_sitzungen: 'No sessions.', leer_chat: 'No messages yet.', leer_live: 'No events.', leer_detail: 'No agent selected.',
    leer_terminal: 'Terminal empty.', leer_probleme: 'No problems found.', leer_debug: 'No debug output.',
    leer_ausgabe: 'No output.', leer_logs: 'No log lines.',

    su_platz: 'Search', su_hinweis: 'Enter a search term. All sample files are searched.', su_nichts: 'No results for “{0}”.', su_anzahl: '{0} results',
    qc_nachricht: 'Message', qc_uebernehmen: 'Commit', qc_aenderungen: 'Changes', qc_attrappe: 'Mock-up: nothing is committed.',
    au_start: 'Start', au_laeufe: 'Runs', au_lauf_js: 'Start sample', au_lauf_test: 'Run tests',
    au_gestartet: 'Sample run for {0} (mock-up, nothing executed)',
    erw_platz: 'Search extensions', erw_installiert: 'Installed', erw_empfohlen: 'Recommended', erw_installieren: 'Install',
    erw_attrappe: 'Mock-up: nothing is installed without network.',
    erw_python: 'Syntax colours and outline for Python', erw_yaml: 'Syntax colours and checks for YAML', erw_agenten: 'Agent list and live coding',
    erw_markdown: 'Syntax colours and outline for Markdown', erw_pruefer: 'Rule check for line count and tokens', erw_zweige: 'Show branches and history',

    ag_frage: 'What can I do for you?', ag_liste: 'Agents', ag_letzte: 'Recent', ag_platz: 'Type your task …', ag_modus: 'Mode',
    ag_plan: 'Plan', ag_act: 'Act', ag_auto: 'Auto-approve:', ag_auto_an: 'Read, Edit', ag_auto_aus: 'off',
    ag_rolle_bau: 'Build', ag_rolle_doku: 'Documents', ag_rolle_leitung: 'Lead', ag_rolle_test: 'Tests',
    zs_aktiv: 'working', zs_wartet: 'waiting', zs_fehler: 'error',

    re_leiste: 'Chat bar', re_chat: 'Chat', re_sitzungen: 'Sessions', re_live: 'Live coding', re_detail: 'Agent detail',
    re_live_mehr: 'Add sample event', re_sitzung_attrappe: 'Session “{0}”: mock-up, no history loaded.',
    ch_platz: 'Write a message …', ch_senden: 'Send', ch_ich: 'You', ch_hinweis: 'Enter sends, Shift+Enter: new line',
    ch_antwort: 'Mock-up ({0}): message noted, nothing was sent.',
    ev_liest: 'reads', ev_schreibt: 'writes', ev_prueft: 'checks', ev_meldet: 'reports',
    dt_rolle: 'Role', dt_auftrag: 'Task', dt_datei: 'File', dt_keine: 'none', dt_schritte: 'Steps', dt_seit: 'Since', dt_oeffnen: 'Open file',

    pn_panel: 'Panel', pn_terminal: 'Terminal', pn_ausgabe: 'Output', pn_probleme: 'Problems', pn_debug: 'Debug console', pn_logs: 'Live logs',
    tm_gruss_echt: 'Sedra terminal (display only). "help" lists the commands. It shows what the Coder has loaded from the project and runs no commands on this computer.', tm_erst_oeffnen: 'Not opened yet: {0}. Load it with "open {0}", then cat shows the text.', tm_unbekannt_echt: 'Unknown command: {0}. This terminal runs no real commands (only help, ls, cat, open, status, echo, agenten, clear).', tm_ls_hinweis: 'Loaded folders only. Expand a folder in the Explorer to list its files.', df_titel: 'Changes: {0}', df_anzahl: '{0} lines changed', df_gleich: 'No change compared with the last commit.', df_links: 'Last commit', df_rechts: 'Editor', df_datei: 'Open file', df_zu: 'Close diff', df_fehler_kein_git: 'No Git folder in the project.', df_fehler_zu_gross: 'The file is too large to compare.', df_fehler_binaer: 'The file is not text.', df_fehler_git_zeit: 'Git did not answer in time.', df_fehler_sonst: 'The comparison is not possible.', su_laeuft: 'Searching …', su_fehler: 'The search is not possible.', su_gekuerzt: '(shortened: not everything shown)', su_ersetzen_platz: 'Replace with (editor only)', su_ersetzen: 'Replace', su_ersetzen_datei: 'Replace in {0} (editor only, not saved)', su_ersetzen_leer: 'Enter the replacement text first.', su_ersetzt: '{0} places replaced in {1} (unsaved; saving sends the request to Approvals).', su_ersetzt_nichts: 'Nothing to replace in {0}.', vw_ok: 'OK', vw_abbruch: 'Cancel', vw_hinweis_antrag: 'This is only a request to Approvals. Nothing changes until you agree.', vw_neuer_ordner: 'New folder', vw_umbenennen: 'Rename', vw_loeschen: 'Delete', vw_ordner_titel: 'New folder (path in the project)', vw_umbenennen_titel: 'Rename: {0}', vw_loeschen_titel: 'Delete {0}?', vw_loeschen_hinweis: 'Request to Approvals. Only files and empty folders are deleted; only after you agree.', vw_antrag_ordner: 'Request sent to Approvals: create folder {0}.', vw_antrag_umbenennen: 'Request sent to Approvals: rename {0} to {1}.', vw_antrag_loeschen: 'Request sent to Approvals: delete {0}.', vw_fertig_ordner: 'Folder {0} created (approved).', vw_fertig_umbenennen: '{0} renamed to {1} (approved).', vw_fertig_loeschen: '{0} deleted (approved).', sp_fehler_ziel_existiert: 'The target already exists.', sp_fehler_nicht_gefunden: 'File or folder not found.', sp_fehler_ordner_nicht_leer: 'The folder is not empty. Only empty folders are deleted.', sp_fehler_invalid_kind: 'Unknown action.', kf_suchen: 'Find in file', kf_ersetzen: 'Replace with', kf_anzahl: '{0} matches', kf_keine: 'No matches', kf_von: '{0} of {1}', kf_vorher: 'Previous match (Shift+Enter)', kf_weiter: 'Next match (Enter)', kf_eins: 'Replace', kf_alle: 'Replace all', kf_zu: 'Close find bar', kf_ersetzt: '{0} places replaced in the editor (unsaved).', pj_menue: 'Choose project', pj_ungespeichert: 'Save the unsaved files first (request) or close them, then switch project.', pj_fehler: 'The project could not be loaded.', bf_schriftGroesser: 'Larger font', bf_schriftKleiner: 'Smaller font', bf_schriftStandard: 'Reset font size', schrift_gr: 'Font size {0}', mk_wieder: 'Resumed open requests: {0}.', bf_umbruch: 'Toggle word wrap (Alt+Z)', bf_faltAlleZu: 'Fold all', bf_faltAlleAuf: 'Unfold all', ed_umbruch_an: 'Word wrap on.', ed_umbruch_aus: 'Word wrap off.', ed_cursor: '{0} cursors', tm_gruss: 'Sedra terminal (mock-up). "help" lists the commands. Nothing is executed on this machine.',
    tm_hilfe: 'Commands: help, ls, cat <file>, open <file>, echo <text>, status, agenten, clear',
    tm_keine_datei: 'File not found: {0}', tm_geoeffnet: 'Opened: {0}', tm_unbekannt: 'Unknown command: {0}', tm_eingabe: 'Terminal input',
    db_eingabe: 'Debug input', db_attrappe: 'Mock-up: expressions are not evaluated.',
    pb_todo: 'Open item (TODO)', pb_leerraum: 'Trailing whitespace', pb_tab_yaml: 'Tab character in YAML',

    echt_marke: 'Project, read only', echt_geladen: 'Project “{0}” loaded (read only).',
    echt_fehler_lesen: '“{0}” could not be read.', echt_fehler_binaer: '“{0}” is not a text file and is not shown.',
    echt_fehler_gross: '“{0}” is too large for the Coder (over 2 MB).', echt_fehler_gesperrt: '“{0}” is blocked (keys and local configuration are never shown).',
    sp_antrag: 'Request sent to Approvals: {0} (+{1} / −{2} lines). Nothing is written until you agree.', sp_antrag_neu: 'Request sent to Approvals: new file {0}. Nothing is written until you agree.', sp_wartet: '{0}: The request is still waiting for your approval.', sp_nichts: 'No unsaved files.', sp_neben: 'request open', sp_angewendet: '{0} saved (approved).', sp_abgelehnt: '{0}: request declined, nothing written.', sp_zeit: '{0}: No longer checking. The approval stays open; send the request again if needed.', sp_fehler_file_changed_repeat_request: 'The file changed on disk. The approval no longer applies: please save again.', sp_fehler_captain_approval: 'Nothing is written without the Captain\'s approval.', sp_fehler_already_applied: 'This request was already carried out.', sp_fehler_keine_aenderung: 'No change compared with the file in the project.', sp_fehler_access_blocked: 'This file is blocked (keys or local configuration).', sp_fehler_datei_zu_gross: 'The file is too large to save from the Coder.', sp_fehler_datei_nicht_lesbar: 'The file is not UTF-8 text.', sp_fehler_ziel_ist_ordner: 'The target is a folder.', sp_fehler_content_too_large: 'The text is too large to save from the Coder.', sp_fehler_invalid_path: 'Invalid file name.', sp_fehler_write_failed: 'Writing failed.', sp_fehler_sonst: 'Cannot save.', su_hinweis_echt: 'Enter a search term. The whole project is searched (blocked files excluded).', qc_git_fehlt: 'No Git folder in the project, or Git is not reachable.', qc_aktualisieren: 'Refresh', qc_echt_hinweis: 'No changes in the project (read only).',
    ed_reiter: 'Tabs of editor group {0}', ed_schliessen: 'Close {0}', ed_brotkrumen: 'Path', ed_eingabe: 'Editor {0}', ed_minimap: 'Minimap',
    ed_tab_frei: 'Tab now leaves the editor once.', ed_gruppe_zu: 'Close group', ed_teilen_voll: 'At most three editor groups.',
    ed_gespeichert: '{0} saved (in page memory only).', ed_alle_gespeichert: 'All files saved (in page memory only).',

    wk_reiter: 'Welcome', wk_titel: 'Sedra IDE', wk_unter: 'Developing with SEDRA', wk_start: 'Start', wk_zuletzt: 'Recent', wk_einfuehrungen: 'Walkthroughs',
    wk_neu: 'New file …', wk_oeffnen: 'Open file …', wk_ordner: 'Open folder …', wk_verbinden: 'Connect …',
    wk_verbinden_aus: 'Connect is not wired up in this stage.',
    wk_e1_titel: 'Command palette', wk_e1_text: 'Find every command with Ctrl+Shift+P or F1.',
    wk_e2_titel: 'Split editor', wk_e2_text: 'Edit two files side by side.',
    wk_e3_titel: 'Agents', wk_e3_text: 'See the agent list, live coding and chat.',
    wk_e4_titel: 'Dark and light', wk_e4_text: 'Switch the theme of the interface.',

    pl_feld: 'Command or file', pl_platz: 'File name, ">" for commands, ":" for line', pl_nichts: 'No results.',
    pl_keine_datei: 'No file opened.', pl_gehe_zeile: 'Go to line {0}', pl_zeile_hinweis: 'Enter a line number between 1 and {0}.',

    weg_lokal: 'Local model ({0})', weg_cloud: 'Cloud: {0} ({1})', weg_bereit: 'ready', weg_laedt: 'Looking for available models …',
    weg_keine: 'No model ready: start the local model or switch on a cloud provider in the settings.',
    ag_denkt: 'Thinking …', ag_hinweis: 'Note', ag_laeuft: 'A question is still running.', ag_kein_weg: 'No model chosen or ready. The agent can only answer, not save anything.',
    ag_kein_modell: 'No local model loaded.', ag_gesperrt_schutz: 'Stopped by content protection ({0}). Nothing was sent to the cloud.', ag_fehler: 'The model did not answer ({0}).',
    ag_kontext: '{0} file(s) as context', ag_ohne_kontext: 'no file context', ag_ausgelassen: 'Not sent: {0}.',
    ag_grund_gesperrt: 'blocked', ag_grund_binaer: 'not a text file', ag_grund_zu_gross: 'too large', ag_grund_nicht_lesbar: 'not readable', ag_grund_kein_platz: 'no room left',
    st_ordner: 'Workspace', st_zweig: 'Branch (sample)', st_probleme: '{0} errors, {1} warnings', st_zeile: 'Ln {0}, Col {1}',
    st_zeile_kurz: 'Ln {0}', st_auswahl: '({0} selected)', st_einrueckung: 'Spaces: 2', st_kodierung: 'Encoding', st_zeilenende: 'End of line',
    st_sprache: 'Language of the file', st_text: 'Text',
    tl_links: 'Width of the left side bar', tl_rechts: 'Width of the right side bar', tl_panel: 'Height of the panel'
  };
})(window);
