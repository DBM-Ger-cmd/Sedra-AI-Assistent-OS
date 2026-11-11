# SPEC Apps v1 – O3+ (Schutz des Oberflächen-Codes) und G9–G11 (Freigaben außerhalb des Browsers) – G2 Design (03.11.2026)

Grundlage: `docs/SPEC_APPS_v1_AM0_E1_OBERFLAECHENCODE.md`. Darin: §6 (O3 hart/weich/frei), §5a.5 (G1, G2, G3, G6, G7), §5b (Klassen H/N, G9, G10, G11), §8 (Entscheidungen). Entschieden vom Captain am 03.11.2026: **O3+** mit G1, G2, G3, G6, G7; danach **G9, G10, G11**. G4 ist gebaut (`SPEC_APPS_v1_G4_MODELLCODE_G2.md`), G5 und G8 gehören zu AM9 und sind nicht Teil dieses Dokuments.
Status: **G2 freigegeben** am 03.11.2026 (E1–E8, E10, E11 wie vorgeschlagen; E9 nach der Ausarbeitung in §9a offen). Bau (G3) beginnt mit G11 (§11 Schritt 1).
Pfade relativ zu `runtime/src/sedra_runtime/`, Zeilen für `00cef7c` (`main` nach PR #3).

## 0. Ziel in zwei Sätzen

Code, den ein Modell für die Oberfläche schreibt, wirkt im Betrieb erst, wenn der Captain ihn mit vollem Diff gesehen und übernommen hat (O3+). Freigaben, die Rechte für später erteilen, Programme starten, Regeln oder Kern ändern, Code in den Betrieb bringen oder Daten nach außen geben (Klasse H), lassen sich aus der Seite heraus nicht mehr erteilen, nur noch über ein Fenster des Betriebssystems oder die Konsole (G9). Jede Freigabe trägt ihren Kanal im Audit (G10), und ein Test stellt sicher, dass kein Freigabe-Weg an dieser Regel vorbeiführt (G11).

## 1. Befund (beim Lesen für G2 geprüft)

Die Vorlage AM0-E1 bleibt gültig. Beim Lesen des heutigen Codes kamen Präzisierungen und **fünf neue Befunde** (N1–N5) dazu.

| Nr | Befund | Beleg |
|---|---|---|
| B1 | Die Seite (`/`, `desk.html`) und das Archiv (`/retro`) liest der Server **einmal beim Start**. Alles unter `/uix/{ui,shells,tools}/…` (`Gateway.file`) und `/uix/{css,js}/…` (`STATIC_FILE`) liest er **bei jeder Anfrage**, ohne Zwischenspeicher. | `uix_server.py:3523–3526`, `3575–3586`, `3718–3724`; `desk/gateway.py:382–405`; `Cache-Control: no-store` `uix_server.py:3682` |
| B2 | Ausgeliefert werden Dateien mit den Endungen `js, css, json, svg, png, html`. Es geht also nicht nur um Programmcode: CSS kann Knöpfe umgestalten, eine `html`- oder `svg`-Datei kann Skripte derselben Herkunft laden. | `desk/gateway.py:55–56` |
| B3 | Im Standardprojekt `sedra-entwicklung` ist die Wurzel das Repo selbst. Was die Harness unter `runtime/src/sedra_runtime/uix/**` schreibt, sind **genau die Dateien, die der laufende Server ausliefert**. | `harness/projekte.py:19–21` |
| B4 | Das Muster `…/uix/**/tool.yaml` (Doppelstern in der Mitte) trifft jede Tiefe; `pfad_normal` vergleicht ohne Groß-/Kleinschreibung. Damit ist die offene Frage aus AM0-E1 §6 („zu prüfen in G3“) beantwortet. | `harness/katalog.py:46–84` |
| B5 | Der G4-Code-Stand kennt je Projekt den gesehenen Hash jeder Code-Datei, die Spur der Harness (Sitzung, Weg, Zeit) und legt die gesehene Fassung vor dem Schreiben ab (`vorher/<sha>`). „Code“ heißt dort aber nur `.py, .js, …`, also **nicht** CSS, JSON, HTML und SVG. | `harness/code_stand.py:28–30, 176–196, 198–203` |
| B6 | Über `POST /api/decisions/answer` erteilt der Server Freigaben für **sechs Arten** von Entscheidungen. Nur ein Teil davon läuft über `guard.approve`: Grenzüberschreitungen, Fragen des Scheduler und der Inhaltsschutz haben eigene Wege. | `uix_server.py:261–311`; `desk/decisions.py:46–136` |
| B7 | `guard.approve` rufen heute sechs Stellen: `cli.py:333`, `harness/freigabe.py:244, 369`, `uix_server.py:2213`, `desk/gated.py:145`, `agent_manager/cli.py:74`. Das Audit `CAPTAIN_GATE_APPROVED` trägt nur `gate_id`, keinen Kanal. | `core/guard.py:79–102` |
| B8 | Die Herkunftsprüfung S7 (keine Freigabe aus einem Prozess, den die Harness gestartet hat) gilt für die Entscheidungs-Routen des Servers (`HERKUNFT_WEGE`) und die geschützten Harness-Routen (`GESCHUETZT`). Gegen Code in der Seite hilft sie nicht, denn der Browser ist kein Harness-Prozess. | `uix_server.py:3608, 3830, 4061`; `harness/api.py:87–90` |
| **N1** | **Ein elfter Freigabe-Weg**, der in AM0-E1 §5b.2 fehlt: `POST /api/harness/sitzungen` mit einer Vorlage und `erlaubnisse_bestaetigt: true` vergibt beim Anlegen Sitzungs-Erlaubnisse. Bei MasterChat ist das Schreiben in `runtime/src/**`, `runtime/tests/**` und der Lauf `run_tests`. Das ist Klasse H („dauerhaft weiter freigeben“). | `harness/api.py:336–357`; `runtime/config/harness_vorlagen/masterchat.yaml` |
| **N2** | **Ein `frei` im Katalog überspringt heute den weichen Vorbehalt.** `pruefen_weich` wird nur gefragt, wenn die Stufe nicht `frei` ist (für die Deckung durch Aufgaben und den Ausschluss der Sitzungs-Erlaubnis). In der Vorlage greift das nicht, weil `runtime/**` dort `captain` ist. Ein eigener Katalog des Captains mit `frei` für `modell_laden` hebt den weichen Vorbehalt für Modelle aber schon heute auf. Für O3 („weich“ = nur eine Aufgabe mit Nennung deckt) muss das geschlossen werden. | `harness/freigabe.py:39–45, 230–238`; `runtime/config/freigabe_katalog.beispiel.yaml:30–39` |
| **N3** | **Der Token des Konsolen-Clients ist nicht lesegeschützt.** `runtime_data/uix/clients/cli.json` liegt im Projekt; der Lese-Vorbehalt `lesen-geheim` steht nur in der Katalog-Vorlage und nennt diesen Ordner nicht. Unter Windows ist der Token mit DPAPI verschlüsselt, unter macOS/Linux steht er im Klartext (Datei `0600`, für die Harness desselben Benutzers lesbar). Wenn G9 die Konsole als Kanal nutzt, darf kein Modell diesen Token lesen können. | `uix_clients.py:35–58`; `runtime/config/freigabe_katalog.beispiel.yaml:18–22` |
| **N4** | Externe Clients teilen sich eine Routenliste: `ROUTES = ('/api/objects', '/api/actions')` gilt für `cli` **und** `mcp`. Der MCP-Client ist der Zugang für Modelle. Eine neue Konsolen-Route darf nicht automatisch auch für MCP gelten. | `uix_clients.py:21–22, 93` |
| **N5** | Die Konsole `sedra approve` arbeitet in einem eigenen Prozess direkt auf dem Missionsspeicher. Eine Harness-Karte setzt sie nicht fort, denn deren Schleife, Grenzüberschreitungen, Inhaltsschutz und Scheduler-Fragen leben im Speicher des Servers. Eine Konsole für G9 muss deshalb **mit dem laufenden Server sprechen**. | `cli.py:327–335`; `uix_server.py:261–311` |

## 2. Anforderungen

### 2.1 O3: hart, weich, frei für die Oberfläche (AM0-E1 §6, mit Präzisierungen)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| O3-01 | **Hart** (neue Einträge in `harness/vorbehalte.py` `PFADE`, nur Karte an den Captain): `runtime/src/sedra_runtime/uix/ui/**`; `…/uix/**/tool.yaml`, `…/uix/**/shell.yaml`, `…/uix/**/shell.vorgabe.yaml`; `…/uix/**/arbeitsplatz.yaml`; `…/uix/desk.html`, `…/uix/retro_desktop.html`, `…/uix/js/**`. | Test je Muster |
| O3-02 | **Hart, Prüfstellen** (aus AM0-G2 Teil A übernommen): `desk/gateway.py`, `desk/install.py`, `desk/registry.py`, `uix_server.py`, `uix_clients.py`, `cloud_settings.py`, `models/cloud_api.py`, `runtime/config/cloud_providers.yaml`. Dazu die neuen Dateien dieses Dokuments: `desk/decisions.py`, `desk/freigabeklasse.py`, `desk/bestaetigung.py`, `desk/systemdialog.py`, `desk/freigabe_konsole.py`, `harness/oberflaeche.py`. (`desk/herkunft.py` aus AM0-G2 Teil B kommt mit dessen Bau.) | Test je Muster |
| O3-03 | **Weich** (neu: `vorbehalte.pruefen_weich` erkennt für `datei_schreiben`/`datei_aendern` die Muster `…/uix/shells/**`, `…/uix/tools/**`, `…/uix/css/**`, soweit nicht hart): Ergebnis `{grund: 'Captain-Vorbehalt: Code der Oberfläche (läuft in der Seite mit allen Rechten)', oberflaeche: <pfad>}`. | Test |
| O3-04 | **Weich heißt: nur eine Aufgabe mit Nennung deckt** – und zwar auch dann, wenn der Katalog `frei` sagt (schließt N2). In `freigabe.einstufung` wird ein weicher Vorbehalt zur Stufe `captain`, außer eine aktive Aufgabe deckt ihn. Das gilt für die Oberfläche **und** für Modelle (heute `modelle`). Sitzungs-Erlaubnis, Vorarbeiter und Katalog decken nie. | Test: Katalog `frei` + weicher Vorbehalt → Karte |
| O3-05 | **Frei**: `…/uix/**/README.md` bleibt im normalen Katalog. | Test |
| O3-06 | **Lese-Sperre im Code** (schließt N3): `**/runtime_data/uix/clients/**` ist für `datei_lesen`, `dateien_auflisten` und `suchen` **verboten**, unabhängig vom Katalog. Neu: `vorbehalte.pruefen_lesen`; Ergebnis `verboten` mit Grund, keine Karte. | Test |

### 2.2 G1: die Aufgabe für die Oberfläche ist eng

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G1-01 | Neues Feld `oberflaeche: [muster …]` in der Aufgabe, wie `modelle` (`harness/aufgabe.py:120–122`). Nur Muster in `oberflaeche` decken den weichen Oberflächen-Vorbehalt; die Muster müssen zusätzlich von einem `erlaubt`-Eintrag für `datei_schreiben`/`datei_aendern` getroffen werden. | Test |
| G1-02 | Alle Muster einer Aufgabe liegen in **genau einem** Ordner: `…/uix/shells/<id>/`, `…/uix/tools/<id>/` oder `…/uix/css/`. Ohne Platzhalter im `<id>`-Teil. Sonst `oberflaeche_zu_breit` bzw. `oberflaeche_mehrere_ordner`. | Test |
| G1-03 | Höchstens **eine** aktive Aufgabe mit `oberflaeche` je Projekt; sonst `oberflaeche_schon_aktiv` mit der Kennung der laufenden. | Test |
| G1-04 | Ein **Vorschlag** des Vorarbeiters darf kein `oberflaeche` enthalten (`oberflaeche_nur_captain`). | Test |
| G1-05 | Ende ist Pflicht; das gilt schon heute (`ende_fehlt`, `bis` ≤ 24 h, `max_aufrufe` ≤ 500). | `harness/aufgabe.py:25–26, 123–143` |
| G1-06 | Beim Feld `oberflaeche` zeigt das Formular den Satz aus AM0-E1 §6: „Code an diesen Stellen läuft in der Oberfläche mit allen Rechten der Seite – auch Freigaben. Er wirkt erst, wenn du ihn übernimmst (Sammelkarte). Gib nur Pfade frei, die zu diesem Zweck gehören.“ | uix_check |

### 2.3 G2: Abnahme vor Wirkung

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G2-01 | **Zurückhalten**: Schreibt die Harness unter einer **Aufgabe** in eine Datei unter dem `uix/`-Ordner des **laufenden** Programms (`Path(uix_server.__file__).parent / 'uix'`, aufgelöst), merkt `harness/oberflaeche.py` vor dem Schreiben die bestätigte Fassung (Inhalt in die Ablage, siehe G2-08). Weitere Schreibvorgänge an derselben Datei ändern die gemerkte Fassung nicht. | Test |
| G2-02 | Schreibt die Harness über eine **Karte** des Captains (er sah den Diff auf der Karte), wird **nicht** zurückgehalten; die Karte ist dann Klasse H (G9-03). Schreibvorgänge in Ordner eines anderen Projekts als des laufenden Programms werden nicht zurückgehalten (der Server liefert sie nicht aus); der weiche Vorbehalt gilt dort trotzdem. | Test |
| G2-03 | **Ausliefern**: Für eine zurückgehaltene Datei liefert der Betriebsserver die **bestätigte Fassung**: an `_module_file` (`/uix/{ui,shells,tools}/…`) und an `STATIC_FILE` (`/uix/css/…`). War die Datei neu, antwortet er `404`. Gilt für alle ausgelieferten Endungen (B2), nicht nur für Code. | Test über HTTP |
| G2-04 | Tests, `uix_check` und die Vorschau sehen die **neue** Fassung auf der Platte. Nur der Betriebsserver liest den Zurückhalte-Stand (er liegt unter dessen `runtime_data`; ein Prüfserver mit leerem Prüfprojekt hat keinen). | Test |
| G2-05 | **Sammelkarte** „Oberflächen-Änderungen übernehmen“: neue Entscheidungsart `harness_oberflaeche` mit den Wegen `uebernehmen`, `zuruecksetzen`, `ablehnen`. Sie entsteht, wenn die Aufgabe endet (erledigt, abgelaufen, erschöpft, zurückgenommen) und zurückgehaltene Dateien da sind, oder auf Wunsch (`POST /api/harness/oberflaeche/vorlegen {projekt}`). Höchstens eine offene je Projekt; eine neue ersetzt die alte. | Test |
| G2-06 | Inhalt der Sammelkarte: je Datei der vollständige Diff bestätigt → jetzt (wie die G4-Vorschau, `code_stand.vorschau`), mit Hinweisen (G3). Gebunden an die Liste `(pfad, sha_jetzt)`. Ändert sich danach eine Datei, ist die Karte hinfällig und wird neu vorgelegt. Grenzen wie bei G4 (30 Dateien, 2.000 Zeilen); darüber nur über die Konsole (G7-04). | Test |
| G2-07 | **`uebernehmen`** (Klasse H): Für jede gebundene Datei, deren Fassung noch stimmt, endet das Zurückhalten. Dateien unter Code-Endungen gelten zugleich als gesehen im G4-Code-Stand (`gesehen_setzen`). Es entsteht ein Übernahme-Satz `U-…` (G7). **`zuruecksetzen`** (Klasse N): stellt die bestätigten Fassungen auf der Platte wieder her; neue Dateien wandern nach `runtime_data/harness/oberflaeche/verworfen/<zeit>/`, gelöscht wird nichts. **`ablehnen`** (Klasse N): Karte zu, Dateien bleiben zurückgehalten. | Test |
| G2-08 | **Ablage**: `<SEDRA-Projekt>/runtime_data/harness/oberflaeche/` (dort schon harter Vorbehalt `**/runtime_data/harness/**`): `stand.json` `{schema, dateien: {rel: {bestaetigt_sha, sitzung, aufgabe, zeit}}, uebernahmen: [...]}`, Inhalte unter `inhalt/<sha>` (≤ 1 MB je Datei, wie `VORHER_MAX`). Größere Dateien werden nicht zurückgehalten, sondern die Schreibaktion wird zur Karte. | Test |
| G2-09 | **Vorschau**: `POST /api/harness/oberflaeche/vorschau {shell?}` startet einen **Prüfserver als eigenen Prozess** (`python -m sedra_runtime.uix_server --root <leeres Prüfprojekt> --architecture <wie Betrieb> --port 0 [--shell …]`) und nennt seine Adresse. Code dort erreicht keine echten Entscheidungen (eigener Token, eigener Port, leeres Projekt). Ende nach 30 min, beim Beantworten der Sammelkarte oder beim Ende des Servers. | Test (Prozess startet, Adresse, Ende) |
| G2-10 | Schalter `oberflaeche_abnahme` in `local_config/switches.yaml` (Standard an, nur in der Datei, wie `code_sicht`). Aus: Es wird nicht mehr zurückgehalten; schon zurückgehaltene Dateien bleiben es, bis zur Sammelkarte oder Konsole. | Test |

### 2.4 G3: Hinweise im Diff

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G3-01 | Zeilen, die hinzukommen, werden mit `⚠ <Hinweis>` markiert, wenn sie Muster aus `desk/install.py` `FLAGS` treffen (`eval`, `new Function`, `fetch`, `location.hash/href/search`, `innerHTML`, `window.parent/top`, …, `install.py:26–46`). Dazu kommen Muster für Freigabe-Wege: `decisions/answer`, `/api/mission/approve`, `/api/harness/karten`, `/api/harness/aufgaben`, `/api/harness/vorarbeiter`, `erlaubnisse_bestaetigt`, `/api/uix/install`, `/api/uix/trust`, `trust:`. Die Liste steht einmal in `desk/install.py` und wird dort gelesen. | Test |
| G3-02 | Gilt für die Sammelkarte (G2) **und** für die G4-Karte (gebaut, `code_stand.vorschau`). | Test |
| G3-03 | Die Karte sagt ausdrücklich: „Hinweise sind eine Lesehilfe. Sie finden nicht alles, und ein Treffer ist kein Beweis.“ | Test des Texts |

### 2.5 G6: Startbericht

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G6-01 | Beim Start des Servers fragt SEDRA den G4-Code-Stand des Projekts, dessen Wurzel das laufende Programm enthält (B3), nach ungesehenen Dateien unter `runtime/src/**`. Steht für eine davon eine Spur der Harness, entsteht ein Eintrag im Posteingang. | Test |
| G6-02 | Neue Entscheidungsart `startbericht`, einziger Weg `zur_kenntnis` (Klasse N). Text: „Seit dem letzten Start hat die Harness n Programmdateien geändert, die du in dieser Fassung nicht gesehen hast. Sie laufen ab jetzt.“ Dazu die Liste (≤ 30 Pfade mit Sitzung und Weg) und der Konsolenweg zum Ansehen (`CODE_STAND.bat <projekt> --zeigen`). Weitere ungesehene Dateien ohne Spur (Claude, `git pull`) stehen als Zahl daneben. | Test |
| G6-03 | `zur_kenntnis` macht nichts gesehen; Läufe brauchen weiter die G4-Karte. Audit `STARTBERICHT {anzahl_harness, anzahl_sonst}` beim Start, `STARTBERICHT_GELESEN` bei der Antwort. | Test |

### 2.6 G7: Rückweg

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G7-01 | Jede Übernahme (G2-07) speichert `U-…`: `{zeit, dateien: [{rel, alt_sha, neu_sha}], kanal}`. Die alten Inhalte bleiben in `inhalt/<sha>`. | Test |
| G7-02 | „Übernahme zurücknehmen“ stellt je Datei die alte Fassung wieder her, **wenn** die Datei noch die übernommene Fassung hat; sonst bleibt sie und wird genannt (`seit_der_uebernahme_geaendert`). War die Datei neu, wandert sie nach `verworfen/`. Danach gelten die alten Fassungen als bestätigt; im G4-Code-Stand gelten sie als gesehen. | Test |
| G7-03 | Zurücknehmen geht **ohne Oberfläche**: `CODE_STAND.bat <projekt> --oberflaeche` (zurückgehaltene Dateien und die letzten Übernahmen), `--zuruecknehmen U-…`, `--zuruecksetzen` (wie G2-07). Der Server muss dafür nicht laufen; Dateien und Ablage werden atomar geschrieben. Audit `HARNESS_OBERFLAECHE_ZURUECK {u, dateien, kanal: konsole}`. | Test (Unterprozess wie bei G4) |
| G7-04 | Über die Konsole lässt sich auch übernehmen: `--uebernehmen-oberflaeche`. Das ist der Weg, wenn die Sammelkarte zu groß ist (G2-06). Audit mit `kanal: konsole`. | Test |
| G7-05 | In der Oberfläche: „Übernahme zurücknehmen“ an der letzten Übernahme (Harness, Einstellungen → Freigaben). Klasse N, denn es stellt nur einen schon einmal bestätigten Stand her. | uix_check |

### 2.7 G9: Bestätigung außerhalb des Browsers für Klasse H

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G9-01 | **Eine Tabelle** `desk/freigabeklasse.py` (rein, ohne Netz): `klasse(art, weg, binding) → 'H' \| 'N'`. `ablehnen` und Zurücknehmen sind immer N. Unbekannte Art oder unbekannter Weg ist **H**. Inhalt der Tabelle: §3.3. | Test |
| G9-02 | **Eine Tür**: Kommt eine Antwort der Klasse H über die Seite (Kanal `seite`), führt der Server sie **nicht** aus. Er legt eine Bestätigung `B-…` an (`desk/bestaetigung.py`, im Speicher des Servers), antwortet `{status: 'wartet_auf_bestaetigung', bestaetigung, kanaele}` und zeigt den Dialog (G9-05). Erst ein Ja über `systemdialog` oder `konsole` führt die ursprüngliche Antwort aus, mit demselben Code wie bisher. | Test mit Fake-Dialog: kein `approve` ohne Ja |
| G9-03 | Die Tür sitzt an jeder Stelle, an der heute eine Freigabe aus der Seite kommt (§3.4): `UIXHub.decide`, die Route `/api/mission/approve`, `harness/api.beantworten` (Karte und Posteingang), `POST /api/harness/aufgaben`, `POST /api/harness/vorarbeiter` (ernennen) und `POST /api/harness/sitzungen` mit `erlaubnisse_bestaetigt` (N1). Bei N1 wird die Sitzung sofort angelegt, die Erlaubnisse erst nach dem Ja. | Test je Weg |
| G9-04 | Die Bestätigung bindet Art, Kennung, Weg und den Hash der Bindung der Entscheidung. Ändert sich die Entscheidung in der Zwischenzeit oder ist sie schon beantwortet, wird nichts ausgeführt (`bestaetigung_hinfaellig`). Frist 10 min, danach bleibt die Entscheidung offen und kann neu beantwortet werden. Nach einem Neustart des Servers gibt es keine offenen Bestätigungen mehr; die Entscheidungen bleiben offen. | Test |
| G9-05 | **Systemdialog** (Windows): `desk/systemdialog.py` zeigt `MessageBoxW` mit `MB_YESNO \| MB_ICONWARNING \| MB_TOPMOST \| MB_SETFOREGROUND \| MB_SYSTEMMODAL` in einem eigenen Thread des Servers (`ctypes`, ohne neue Abhängigkeit; Vorbild `harness/herkunft.py:51–60`). Der Text kommt **nur aus dem Kern**: Art, Titel und Beschreibung der Entscheidung, Ziel, Kennung `B-…`, Klasse-H-Grund, Uhrzeit. Ein Ja ruft die Tür mit `kanal: systemdialog`, ein Nein lehnt die Bestätigung ab (die Entscheidung bleibt offen). | Test mit Fake; Abnahme am PC |
| G9-06 | Ohne Windows oder wenn der Dialog nicht angezeigt werden kann: kein Dialog, nur die Konsole. Die Seite nennt dann den Befehl. | Test |
| G9-07 | **Konsole**: `FREIGABE.bat liste` · `FREIGABE.bat freigeben B-…` · `FREIGABE.bat ablehnen B-…` (Windows, Pfade und Python wie `CODE_STAND.bat`; sonst `python -m sedra_runtime.desk.freigabe_konsole --root workspace/SEDRA_OS …`). Der Befehl spricht mit dem laufenden Server über `POST /api/freigabe/offen` und `POST /api/freigabe/bestaetigen` mit dem **CLI-Token** (N5). `liste` zeigt denselben Kern-Text wie der Dialog. | Test (Unterprozess gegen einen Prüfserver) |
| G9-08 | Die neuen Routen nimmt der Server **nur** mit dem CLI-Token an: nicht mit dem Browser-Token, nicht mit dem MCP-Token (schließt N4: Routen je Client statt einer gemeinsamen Liste). Sie stehen in `HERKUNFT_WEGE` (S7). | Test |
| G9-09 | Die Seite zeigt den Wartezustand: an der Karte bzw. im Posteingang „Wartet auf deine Bestätigung außerhalb des Browsers (Fenster von SEDRA oder `FREIGABE.bat freigeben B-…`)“. Aus der Seite heraus gibt es keinen Knopf, der die Bestätigung erteilt. | uix_check |
| G9-10 | Karten der Klasse H gehen immer an den Captain (`an: captain`), auch wenn der Katalog `vorarbeiter` sagt. Der Vorarbeiter beantwortet nur Klasse N. | Test |
| G9-11 | Schalter `freigabe_ausserhalb` in `local_config/switches.yaml` (Standard an, nur in der Datei). Aus: Klasse H geht wieder aus der Seite; jede solche Freigabe wird mit `kanal: seite`, `klasse: H` im Audit vermerkt. | Test |

### 2.8 G10: Kanal im Audit

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G10-01 | Jede erteilte Freigabe erzeugt `FREIGABE_ERTEILT {art, id, weg, klasse, kanal, gate_id?}` mit `kanal` aus `seite` · `systemdialog` · `konsole` · `aufgabe` · `sitzung` · `vorarbeiter` · `katalog` (künftig `freigabefenster` mit G5). Das Ereignis entsteht in der Tür (G9-02), nicht verstreut. | Test |
| G10-02 | `HARNESS_APPROVED_BY` (automatische Freigaben über Aufgabe, Sitzung, Katalog) bekommt `kanal` dazu. `CAPTAIN_GATE_APPROVED` im Guard bleibt unverändert (`core/**` bleibt unberührt); die Zuordnung läuft über `gate_id`. | Test |
| G10-03 | Die Konsole `sedra approve` (`cli.py:327–335`) und `agent_manager/cli.py:74` schreiben `FREIGABE_ERTEILT` mit `kanal: konsole`. | Test |

### 2.9 G11: Vollständigkeitstest

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G11-01 | Ein Test findet über den AST jede Stelle im Paket, die `.approve(` an einem Guard ruft (heute sechs, B7), und verlangt für jede einen Eintrag in einer Liste im Test: Datei, Funktion, Kanal, „hinter der Tür“ ja/nein mit Begründung. Eine neue Stelle ohne Eintrag lässt den Test fehlschlagen. | der Test selbst |
| G11-02 | Derselbe Test liest die POST-, PATCH- und DELETE-Routen des Servers (Routentabelle in `uix_server.py`, `HERKUNFT_WEGE`, `harness/api.py` `WEG`/`GESCHUETZT`) und verlangt für jede eine Einordnung: `liest` · `antrag` (legt nur eine Entscheidung an) · `freigabe` (mit Klasse) · `anwenden` (braucht ein schon freigegebenes Gate) · `sonst` mit Begründung. | der Test |
| G11-03 | Jede Entscheidungsart, die `desk/decisions.py` erzeugen kann (`gate`, `request:<art>` für alle Schlüssel in `REQUEST_TITLE`, `boundary`, `content`, `cloud_offload`, `slot_server`, `harness_freigabe`, `harness_aufgabe`, neu `harness_oberflaeche`, `startbericht`), und jeder Weg in `WAYS` hat eine Klasse in `freigabeklasse`. | der Test |
| G11-04 | Die Wege ohne `guard.approve` (`_answer_crossing`, `_answer_scheduler`, `content_guard.answer`) werden nur aus `decide` gerufen (Aufrufstellen im AST). | der Test |
| G11-05 | Verhaltensprüfung: Für jede Art der Klasse H führt eine Antwort mit Browser-Token über die Seite nie zu `approve` bzw. zur Wirkung, solange keine Bestätigung kam (Fake-Guard zählt). | der Test |

## 3. Entwurf

### 3.1 Neue und geänderte Dateien

| Datei | Neu/geändert | Inhalt |
|---|---|---|
| `harness/vorbehalte.py` | geändert | `PFADE` + O3-01, O3-02; `pruefen_weich` erkennt `oberflaeche`; neu `pruefen_lesen` (O3-06) |
| `harness/freigabe.py` | geändert | `einstufung`: weicher Vorbehalt → `captain`, außer eine Aufgabe deckt (O3-04); Karten der Klasse H immer an den Captain (G9-10); Zurückhalten beim Schreiben über eine Aufgabe (G2-01, über `harness/oberflaeche.py`); `kanal` in `HARNESS_APPROVED_BY` |
| `harness/aufgabe.py` | geändert | Feld `oberflaeche` (G1-01 bis G1-04); `deckt(..., weich=...)` filtert nach `oberflaeche` wie heute nach `modelle` (`:302–308`) |
| `harness/oberflaeche.py` | **neu** (≤ 400 Zeilen) | Zurückhalten, Ausliefern, Sammelkarte, Übernahme, Zurücksetzen, Zurücknehmen, Konsole (G2, G7) |
| `harness/code_stand.py` | geändert | Hinweise in `vorschau` (G3-02); Konsole: `--oberflaeche`, `--zuruecknehmen`, `--zuruecksetzen`, `--uebernehmen-oberflaeche` (G7-03, G7-04), ruft `oberflaeche.py` |
| `harness/api.py` | geändert | Tür in `beantworten`, `aufgabe_anlegen`, `vorarbeiter_weg` (ernennen), `anlegen` (N1); Routen `oberflaeche/vorlegen`, `oberflaeche/vorschau`; Sammelkarte als Entscheidung |
| `desk/freigabeklasse.py` | **neu** (rein) | Tabelle §3.3 |
| `desk/bestaetigung.py` | **neu** | Bestätigungen `B-…` im Speicher: anlegen, offen, bestätigen, ablehnen, Frist, Bindung |
| `desk/systemdialog.py` | **neu** | Windows-Dialog in eigenem Thread; im Test austauschbar |
| `desk/freigabe_konsole.py` | **neu** | `liste`, `freigeben`, `ablehnen` über `uix_clients.call` mit CLI-Token |
| `desk/decisions.py` | geändert | Arten `harness_oberflaeche`, `startbericht`; Weg `zur_kenntnis`; Wartezustand im Eintrag |
| `desk/install.py` | geändert | `FLAGS` um die Freigabe-Wege ergänzt (G3-01); eine Funktion `hinweise(zeilen)` für alle Karten |
| `uix_server.py` | geändert | Tür in `decide` und in der Route `/api/mission/approve`; Auslieferung über `oberflaeche` (G2-03); Routen `/api/freigabe/offen`, `/api/freigabe/bestaetigen`; Startbericht (G6) |
| `uix_clients.py` | geändert | Routen je Client: `cli` bekommt `/api/freigabe/*`, `mcp` nicht (G9-08) |
| `cli.py`, `agent_manager/cli.py` | geändert | `FREIGABE_ERTEILT` mit `kanal: konsole` (G10-03) |
| `local_switches.py` | geändert | `oberflaeche_abnahme`, `freigabe_ausserhalb` (nur Datei) |
| `uix/shells/harness/*.js`, `uix/tools/decisions/*` | geändert | Wartezustand, Sammelkarte mit Vorschau-Knopf, Feld `oberflaeche` im Aufgaben-Formular, „Übernahme zurücknehmen“ |
| `FREIGABE.bat` | **neu** | Konsolenweg G9 unter Windows |
| `runtime/config/harness_vorlagen/masterchat.md` | geändert | Hinweis: Oberfläche nur über eine Aufgabe mit genannten Pfaden; Wirkung erst nach der Sammelkarte |

### 3.2 Ablauf der Tür (G9-02)

```
antwort(art, id, weg, kanal, ausfuehren)          # ausfuehren = der heutige Code dieser Stelle
  klasse = freigabeklasse.klasse(art, weg, binding)
  wenn kanal == 'seite' und klasse == 'H' und Schalter freigabe_ausserhalb an:
      b = bestaetigung.anlegen(art, id, weg, hash(binding), text_aus_dem_kern, ausfuehren)
      systemdialog.zeigen(b)  (Windows; sonst nichts)
      return {status: 'wartet_auf_bestaetigung', bestaetigung: b.id, kanaele: [...]}
  ergebnis = ausfuehren()
  audit FREIGABE_ERTEILT {art, id, weg, klasse, kanal}   (nur wenn erteilt, nicht bei ablehnen)
  return ergebnis

bestaetigen(b_id, kanal in {systemdialog, konsole})
  b = bestaetigung.nehmen(b_id)  → prüft Frist und Bindung gegen den aktuellen Stand der Entscheidung
  return antwort(b.art, b.id, b.weg, kanal, b.ausfuehren)
```

Der Ausführungsteil bleibt an jeder Stelle der heutige Code. Die Tür entscheidet nur, **wann** er läuft. Bei Harness-Karten setzt `ausfuehren` die Antwort des Modells fort wie heute (`harness/api.py:1222ff`). Ob die Fortsetzung aus dem Dialog-Thread genauso läuft wie aus einem HTTP-Thread, prüft G3 (§7).

### 3.3 Klassen (G9-01) – Vorschlag, je Zeile entscheidbar (E2)

Grundlage AM0-E1 §5b.3. `ablehnen` und Zurücknehmen sind überall N.

| Art (Weg) | Klasse | Grund |
|---|---|---|
| `gate` (`einmal`) – Missions-Gate allgemein | **H** | unbekannte Wirkung; Vorgabe für Unbekanntes |
| `request:switch`, `routing`, `boundaries`, `harness_katalog`, `harness_vorlage` | **H** | Regeln ändern |
| `request:install`, `trust`, `update`, `model_add`, `skill` | **H** | Code oder Anweisungen in den Betrieb (ein Skill ist Text für das Modell, wie `arbeitsplatz.yaml`) |
| `request:cloud_url` | **H** | Daten nach außen |
| `request:gateway` | **H**, wenn die Bindung den Weg Cloud nennt; sonst **N** | 5b.3 |
| `request:orchestra`, `standing`, `harness_projekt` | **H** | Rechte für später (Agenten, Dauerfreigabe, neuer Ordner für das Modell) |
| `request:wissen_quelle`, `wissen_vorschlag` | **H** (Vorschlag, E2b) | Text wird Wissen für Agenten (Anweisungen über Inhalte, AM0-E1 §5a.2) |
| `boundary` (`einmal`, `aendern`) | **H** | Grenze überschreiten oder ändern |
| `content` (`einmal`) | **H**, wenn der Weg des Aufrufs Cloud ist; sonst **N** | 5b.3 |
| `cloud_offload` (`cloud_diesen_lauf`) | **H** | Daten nach außen |
| `slot_server` (`bestaetigen` = „Entsperren“) | **N** | gibt keine neuen Rechte (Vorschlag, E2c) |
| `harness_freigabe` mit `befehl`, `lauf_starten` | **H** | Programme ausführen |
| `harness_freigabe` mit `datei_schreiben`/`datei_aendern` auf einen **harten oder weichen** Pfad (§2.1) | **H** | Kern, Regeln oder Code der Oberfläche |
| `harness_freigabe` mit `datei_schreiben`/`datei_aendern` sonst; `modell_laden`/`entladen`; `sitzungen_aufraeumen` | **N** | einzelne Handlung im Projekt |
| `harness_freigabe` mit Weg `sitzung` | **H** | Sitzungs-Erlaubnis = Rechte für später |
| `harness_aufgabe` (Vorschlag einer Aufgabe) | **H** | Freigabe im Voraus |
| `harness_oberflaeche` (`uebernehmen`) | **H** | Code in den Betrieb |
| `harness_oberflaeche` (`zuruecksetzen`), `startbericht` (`zur_kenntnis`) | **N** | stellt Bestätigtes her bzw. liest |
| Route `POST /api/harness/aufgaben` | **H** | Freigabe im Voraus |
| Route `POST /api/harness/vorarbeiter` (ernennen) | **H** | übergibt Entscheidungen an ein Modell |
| Route `POST /api/harness/sitzungen` mit `erlaubnisse_bestaetigt` (N1) | **H** | Sitzungs-Erlaubnisse |

### 3.4 Wege nach dem Bau

| Weg (AM0-E1 §5b.2) | danach |
|---|---|
| F1 Posteingang (`decide`) | hinter der Tür |
| F2 `/api/mission/approve` | hinter der Tür (die Route; `decide` ruft `approve_gate` intern, schon nach der Tür) |
| F3 Harness-Karte | hinter der Tür (`harness/api.beantworten`, dieselbe Tür für Karte und Posteingang) |
| F4 Aufgabe anlegen | hinter der Tür |
| F5 Vorarbeiter ernennen | hinter der Tür |
| F6 Katalog | Antrag N; die Freigabe läuft als `request:harness_katalog` über F1 |
| F7 Desk-Verben mit Gate | legen einen Antrag an; die Freigabe läuft über F1 |
| F8 Update | Freigabe über F1 (`request:update`); die Route `update/uebernehmen` braucht die erteilte Freigabe |
| F9 Shell wechseln, Werkzeug an/aus | unverändert ohne Gate (Form, keine Rechte) |
| F10 `sedra approve` | Kanal `konsole` (außerhalb des Browsers) |
| **F11** (N1) Sitzung mit Vorlage-Erlaubnissen | hinter der Tür |

## 4. Abläufe

**MasterChat ändert die Harness-Oberfläche.**
1. Der Captain legt eine Aufgabe an: Zweck, `erlaubt: datei_aendern …/uix/shells/harness/**`, `oberflaeche: […/uix/shells/harness/**]`, Ende. Klasse H: Die Seite zeigt „wartet“, das Fenster von SEDRA fragt, der Captain sagt Ja.
2. Das Modell ändert drei Dateien. Der Betriebsserver liefert weiter die alten Fassungen; Tests und `uix_check` sehen die neuen.
3. Der Captain klickt „Vorschau“ und sieht die neue Oberfläche in einem eigenen Fenster (Prüfserver, leeres Projekt).
4. Die Aufgabe endet, die Sammelkarte kommt mit drei Diffs und Hinweisen. „Übernehmen“ ist Klasse H, also wieder das Fenster. Danach liefert der Server die neuen Fassungen; beim nächsten Neuladen wirken sie.
5. Ist die Oberfläche danach kaputt: `CODE_STAND.bat sedra-entwicklung --zuruecknehmen U-…` und die Seite neu laden.

**Bestätigter Code in der Seite versucht eine Freigabe.** Er ruft `POST /api/decisions/answer` für eine Aufgabe oder einen `befehl`. Der Server antwortet `wartet_auf_bestaetigung` und zeigt das Fenster mit dem Text des Kerns. Ohne das Ja des Captains passiert nichts. Klasse N (eine Datei im Projekt schreiben, ein Modell laden) bleibt möglich (§7).

**Neustart nach Python-Änderungen der Harness.** Der Posteingang zeigt den Startbericht mit der Liste. Läufe brauchen weiter die G4-Karte.

## 5. Tests (für G3)

| Datei | Prüft |
|---|---|
| `tests/test_harness_vorbehalte.py` | O3-01 bis O3-06 je Muster; Katalog `frei` + weich → Karte (N2), auch für Modelle |
| `tests/test_harness_aufgabe.py` | G1-01 bis G1-04 |
| `tests/test_harness_oberflaeche.py` (neu) | G2-01 bis G2-10 über HTTP mit einem echten Hub auf einem Prüfprojekt; G7-01 bis G7-04, Konsole als Unterprozess |
| `tests/test_freigabe_klasse.py` (neu) | G9-01; G11-03 |
| `tests/test_freigabe_tuer.py` (neu) | G9-02 bis G9-11 mit Fake-Dialog: jede Art aus §3.3 über die Seite; Ja über `systemdialog` und `konsole`; Frist; Bindung geändert; Neustart; Schalter aus |
| `tests/test_freigabe_vollstaendig.py` (neu) | G11-01, G11-02, G11-04, G11-05 |
| `tests/test_desk_client.py` | Routen je Client (N4): CLI darf `/api/freigabe/*`, MCP nicht |
| `tests/test_harness_code_stand.py` | Hinweise in der G4-Vorschau (G3-02); neue Konsolen-Optionen |
| `tests/test_startbericht.py` (neu) | G6-01 bis G6-03 |
| Browser (`SEDRA_BROWSER=1`) | Wartezustand, Sammelkarte, Vorschau-Knopf, Feld `oberflaeche` (nicht im Container: Python-Playwright fehlt) |

## 6. Folgen für die Praxis

- **Häufigkeit des Fensters:** Es kommt bei Klasse H. Im Alltag des MasterChat sind das: Sitzung mit Vorlage-Erlaubnissen anlegen, Aufgaben anlegen, Karten zu `befehl` außerhalb der freien Muster, Läufe nach G4, die Sammelkarte, Anträge zu Regeln und Modulen, Updates. Dateien schreiben (außer Kern und Oberfläche), Modelle laden und lokale Vorgänge bleiben im Browser. Eine Messung, wie oft das am Tag ist, gibt es nicht. Das Audit (`HARNESS_EINGESTUFT`, `FREIGABE_ERTEILT`) erlaubt sie nachträglich.
- **Oberfläche anpassen** geht mit einer Aufgabe je Shell- oder Werkzeugordner. Die Wirkung kommt nach der Sammelkarte, nicht nach dem Neuladen.
- **Claude** ändert weiter direkt im Repo. Das läuft an der Harness vorbei; der G4-Code-Stand zeigt es als ungesehen ohne Spur.
- **Stick:** `FREIGABE.bat` und `desk/freigabe_konsole.py` gehören in die Stick-Liste, sobald gebaut. Ob die Import-Hülle von `freigabe_konsole` klein bleibt, prüft G3 mit `stick_paket.closure` (wie bei G4).

## 7. Grenzen (ehrlich)

- **Klasse N bleibt aus der Seite möglich:** Bestätigter schädlicher Code kann Dateien im Projekt schreiben (außer Kern und Oberfläche), Modelle laden, lokale Vorgänge freigeben, ablehnen und stören. Python, das so entsteht, wirkt beim nächsten Start; G6 zeigt es, G4 blockiert Läufe damit. Ganz weg ist das erst mit AM9 (G5, G8).
- **Gewohnheit:** Der Captain kann das Fenster bestätigen, ohne zu lesen. Der Text kommt vom Kern und nennt Ziel und Kennung; verhindern lässt sich blindes Bestätigen nicht.
- **Täuschung über den Zeitpunkt:** Code in der Seite kann eine echte, aber andere Freigabe auslösen, während der Captain eine erwartet. Das Fenster nennt Art, Ziel und Kennung; G10 macht den Kanal sichtbar.
- **Andere Programme desselben Benutzers** können das Fenster bedienen oder den CLI-Token unter Windows entschlüsseln (DPAPI schützt gegen andere Konten, nicht gegen eigene Prozesse). Das liegt außerhalb dieses Konzepts; G4 sorgt dafür, dass vom Modell geschriebener Code nicht ungesehen auf dem Rechner läuft.
- **Vorarbeiter:** Er beantwortet nach G9-10 nur noch Klasse N. Wie oft das Karten zum Captain verschiebt, ist nicht gemessen.
- **Seiten, die der Server beim Start liest** (`desk.html`, `/retro`, `hardware_manager/dashboard.html`), wirken erst nach dem Neustart. `desk.html` und `/retro` sind hart (O3-01). `dashboard.html` liegt außerhalb von `uix/` und fällt unter die Python-Regel (wirkt beim Neustart, G6 zeigt es nur, wenn es Code ist). Ob es hart werden soll, entscheidet E9.
- **Nicht geprüft beim Lesen für G2**, deshalb in G3 zu prüfen:
  - ob `MessageBoxW` aus dem Server-Prozess unter `START_SEDRA.bat` (Fenster-Modus) im Vordergrund erscheint;
  - ob die Fortsetzung einer Harness-Antwort aus dem Dialog-Thread genauso läuft wie aus einem HTTP-Thread;
  - ob der Prüfserver für die Vorschau beim Start Modelle, GPU oder Scheduler anfasst (`uix_server.serve` startet `hub.poller`);
  - welche Felder `content` für den Weg „Cloud“ trägt (`route`) und welche `request:gateway` (`weg`).

## 8. Rückfall

Beide Teile lassen sich über Schalter in der Datei abschalten (`oberflaeche_abnahme`, `freigabe_ausserhalb`). Zurückgehaltene Dateien bleiben dann zurückgehalten, bis Sammelkarte oder Konsole. Ohne den Bau bleibt alles wie heute. Die Änderung am weichen Vorbehalt (O3-04) hat keinen Schalter; sie stellt den beschriebenen Zustand her (E1).

## 9. Entscheidungen des Captains

| Nr | Frage | Vorschlag |
|---|---|---|
| E1 | Weicher Vorbehalt vor Katalog (N2): Ein `frei` im Katalog deckt keinen weichen Vorbehalt mehr, auch nicht bei Modellen. | ja |
| E2 | Klassen nach §3.3; Vorgabe für Unbekanntes H. Einzeln: E2a Missions-Gates allgemein H; E2b Wissen-Anträge H; E2c „Entsperren“ des Modellservers N. | ja, ja, ja |
| E3 | Karten zu harten und weichen Pfaden sind Klasse H; was über eine solche Karte geschrieben wird, wirkt sofort (keine Sammelkarte). | ja |
| E4 | Vorschau als eigener Prozess statt im Server-Prozess. | ja |
| E5 | Konsole: `FREIGABE.bat` für G9; Rückweg G7 in `CODE_STAND.bat`. | ja |
| E6 | Ohne Windows nur Konsole, keine Dialog-Programme anderer Systeme (`osascript`, `zenity`). | ja |
| E7 | Klasse-H-Karten nie an den Vorarbeiter (G9-10). | ja |
| E8 | Lese-Sperre für `runtime_data/uix/clients/**` im Code (O3-06) und Routen je externem Client (G9-08). | ja |
| E9 | `hardware_manager/dashboard.html` hart? | **entschieden: Variante C** (§9a) – hart, und der Hardware-Server liefert sein Skript selbst mit CSP ohne `unsafe-inline`; gebaut (§13.2) |
| E10 | Frist der Bestätigung 10 min; nach Neustart keine offenen Bestätigungen. | ja |
| E11 | Sitzung mit Vorlage-Erlaubnissen: Sitzung sofort, Erlaubnisse nach dem Ja. | ja |
| E12 | (neu aus G11, §13.1) Die vier Handlungen ohne Gate mit Klasse H (`/api/cloud/save`, `/api/cloud/key`, `/api/cloud/module-model`, `/api/candidate`) bekommen in G9 dieselbe Tür. | ja |
| E13 | (neu aus G11) Gedächtnis der Harness bleibt N. | ja |
| E14 | (neu aus G11) `tests/test_freigabe_*.py` werden mit O3 harter Vorbehalt. | ja |

**Entschieden vom Captain am 03.11.2026:** E1–E8, E10 und E11 wie vorgeschlagen. E12–E14 (aus G11) ebenfalls wie vorgeschlagen. E9 nach der Ausarbeitung: Variante C. E9 sollte genauer ausgeführt werden (§9a); die Entscheidung darüber ist offen.

### 9a. E9 genauer: Soll `hardware_manager/dashboard.html` ein harter Vorbehalt werden?

**Was die Datei ist.** 16 Zeilen HTML mit eingebettetem Stil. Sie lädt genau ein Skript, `/uix/js/hardware_dashboard.js` (13 Zeilen). Das Skript liest den Token aus der Adresse und ruft nur Leserouten (`/api/state`, `/api/inventory`, `/api/profiles`, `/api/capabilities`). Zuletzt geändert am 30.10. in der Härtungsrunde E3 (Inline-Skript ausgelagert, `958a7a0`).

**Wer sie ausliefert.**

| Server | Adresse | Gelesen | CSP für Skripte | Wer die Seite öffnet |
|---|---|---|---|---|
| Server der Oberfläche | `/hardware` | einmal beim Start (`uix_server.py:3526`) | `script-src 'self'`, kein Inline (`:3686–3687`) | nur das Archiv `/retro` (Build 6), als Rahmen **ohne** `sandbox` und mit dem Browser-Token in der Adresse (`uix/retro_desktop.html:182`, `uix/js/status.js:93–97`). Keine heutige Shell nutzt `/hardware`. |
| Hardware-Server (`sedra hardware-dashboard`, `runtime/run_hardware_manager.sh`) | `/` | einmal beim Start (`hardware_manager/dashboard.py:14`) | `script-src 'unsafe-inline'`, **ohne** `'self'` (`dashboard.py:46`) | der Browser des Captains; eigener Port, eigener Token, nur Leserouten (`dashboard.py:1, 32–34`) |

**Was eine geänderte Datei bewirken könnte.**
- *Im Server der Oberfläche* bringt sie **keinen neuen Code** in den Betrieb. Inline-Skripte sperrt die CSP. Skripte kommen nur von derselben Herkunft und nur mit JS-Typ (`nosniff`), und alle ausgelieferten `.js` liegen nach O3 unter harten (`uix/ui`, `uix/js`) oder zurückgehaltenen (Shells, Werkzeuge) Pfaden. Möglich bleibt:
  - (a) schon bestätigte Skripte in den Rahmen `/hardware` laden. Der Rahmen hat den Browser-Token und ist nicht abgeschottet, reicht also bis in die Seite `/retro`. Es läuft dabei nur bestätigter Code, aber in einem anderen Zusammenhang.
  - (b) eine täuschende Anzeige im Hardware-Fenster des Archivs.
  - (c) das Fenster unbrauchbar machen.

  Eine Freigabe auslösen kann die Seite so nicht: Formulare setzen keinen Token-Kopf. Bilder, Rahmen und Schriften fremder Adressen sperrt die CSP. Eine Weiterleitung auf eine fremde Seite trägt den Token nicht mit, denn der Teil nach `#` wird nicht gesendet (`Referrer-Policy: no-referrer`).
- *Im Hardware-Server* **läuft ein Inline-Skript**, denn die CSP erlaubt es. Es hätte den Token dieses Servers und könnte Hardware-Daten lesen (Inventar, Profile, Zustand). Freigaben erreicht es nicht: anderer Port, anderer Token, keine schreibende Route. Nach außen: `connect-src 'self'` sperrt `fetch`, eine Navigation des Fensters mit Daten in der Adresse sperrt die CSP aber nicht.
- Wirksam wird eine Änderung jeweils erst beim nächsten Start des Servers.

**Nebenbefund (geprüft).** Der Hardware-Server zeigt seit der Härtungsrunde vom 30.10. **keine Daten**. Seine Seite lädt `/uix/js/hardware_dashboard.js`, und er antwortet darauf mit 403: Er liefert nur `/` und Datenrouten mit Token-Kopf. Seine CSP würde ein Skript derselben Herkunft außerdem nicht zulassen (`script-src` ohne `'self'`). Nachgeprüft im Container mit einem Fake-Manager: `/` → 200, `/uix/js/hardware_dashboard.js` → 403. Ob der Hardware-Server am PC noch genutzt wird, ist nicht bekannt. `BETRIEB.md:145` nennt den Befehl.

**Optionen.**

| Option | Was | Kosten | Nutzen |
|---|---|---|---|
| A – nicht hart (bisheriger Vorschlag) | bleibt wie jede Datei unter `runtime/src/**` | keine | – |
| B – hart | Eintrag in `PFADE`; jede Änderung wird eine Karte (Klasse H, E3) | gering: geändert seit Build 6 nur einmal (30.10.) | gleich behandelt wie `desk.html`; ein Modell kann kein Inline-Skript für den Hardware-Server mehr ohne Karte hineinschreiben |
| C – hart und Hardware-Server richtig | B, dazu: Der Hardware-Server liefert `hardware_dashboard.js` selbst aus, die CSP wird `script-src 'self'` ohne `unsafe-inline` (wie im Server der Oberfläche), dazu ein Test | klein (`hardware_manager/dashboard.py`, wenige Zeilen, ein Test) | B, und der Nebenbefund ist behoben; Inline-Skript ist dann auch für Änderungen von Claude oder aus `git` gesperrt |

**Neue Empfehlung: C.** Der Grund für „nein“ („wirkt nur beim Neustart, außerhalb der Oberflächen-Ordner“) trifft auf `desk.html` genauso zu, und die ist hart. Die Kosten sind gering, weil die Datei fast nie geändert wird. Die Reparatur des Hardware-Servers gehört streng genommen nicht zu O3, ist aber klein und behebt einen Fehler. Sie käme in §11 zu Schritt 4. Alternative zur Reparatur: den Hardware-Server stilllegen, weil die Oberfläche die Hardware selbst zeigt (Leiste, Werkzeug `system`). Das wäre eine eigene Entscheidung.

## 10. Berechtigungen vorab (für G3)

Schreiben: die Dateien aus §3.1, neue Tests aus §5, `FREIGABE.bat`, `runtime/benchmarks/stick_liste.txt` (Zeilen für `FREIGABE.bat` und das Modul), Doku (`BETRIEB.md`, `CHANGELOG.md`, Konzept §13, diese Spec §13). `core/**` wird nicht geändert. Lesen: alles unter `runtime/src/**`, `runtime/config/**`, `runtime/tests/**`.

## 11. Reihenfolge für G3

1. **G11 zuerst**: `desk/freigabeklasse.py` mit der Tabelle und `tests/test_freigabe_vollstaendig.py`. Der Test zeigt jede Stelle und jede Route, bevor etwas umgebaut wird.
2. **G10**: `FREIGABE_ERTEILT` und `kanal` an allen Stellen aus Schritt 1.
3. **G9**: Bestätigungen, Tür an F1–F5 und F11, Dialog, Konsole, Routen je Client, Lese-Sperre (O3-06), Vorarbeiter nur N.
4. **O3 und G1**: harte und weiche Muster, weich vor Katalog, Feld `oberflaeche`; je nach E9 auch `dashboard.html` und der Hardware-Server (§9a).
5. **G2, G3, G7**: Zurückhalten, Ausliefern, Sammelkarte mit Hinweisen, Übernahme, Rückweg, Konsole, Vorschau.
6. **G6**: Startbericht.
7. Oberfläche (Harness, Posteingang), Vorlage MasterChat, Doku, Stick-Liste.

Nach jedem Schritt: die betroffenen Testgruppen, nach Schritt 7 die ganze Bahn (Container) und die Browser-Bahn am PC.

## 12. Nächste Gates

G2 (dieses Dokument) → Freigabe durch den Captain mit E1–E11 → G3 (Bau in der Reihenfolge §11) → G4 (Abnahme am PC: Fenster erscheint im Vordergrund, Konsole, Sammelkarte, Rückweg ohne Oberfläche).

## 13. Stand des Baus (G3)

### 13.1 Schritt 1: G11 gebaut (03.11.2026)

| Datei | Inhalt |
|---|---|
| `desk/freigabeklasse.py` (neu) | `klasse(art, weg, binding)` nach §3.3 (Ablehnen/Zurücknehmen immer N, Unbekanntes H; GateWay nach `weg`, Inhaltsschutz nach `route`, Harness-Karte nach Werkzeug, Ziel und Weg über `vorbehalte`). Dazu die Bestandslisten: `ROUTEN_SERVER` (alle 121 POST-Routen), `ROUTEN_HARNESS` (24 schreibende Wege), `HARNESS_WEGE`/`HARNESS_UNTERWEGE` (alle Wege aus `WEG`), `APPROVE_STELLEN` (8 Stellen mit `.approve(`, je Kanal und Tür), `ANTWORT_OHNE_GUARD`, `BEFUNDE_OHNE_GATE`. |
| `harness/vorbehalte.py` | `desk/freigabeklasse.py` ist harter Vorbehalt (O3-02 vorgezogen: die Tabelle soll nicht ohne Karte änderbar sein, solange O3 nicht gebaut ist). |
| `tests/test_freigabe_vollstaendig.py` (neu, 16 Tests) | G11-01 bis G11-04 über den AST und die Muster: jede `approve`-Stelle, jede POST-Route, jeder Harness-Weg, jede Antragsart (aus `REQUEST_TITLE`, `APPLY`, `_remember('…')`, `register_applier`), jede weitere Art und jeder Weg; Freigabe- und Anwende-Routen in `HERKUNFT_WEGE` (S7); externe Clients erreichen keine Freigabe; Grenzüberschreitung, Scheduler und Inhaltsschutz nur aus `decide`. |
| `tests/test_freigabe_klasse.py` (neu, 9 Tests) | §3.3 Zeile für Zeile. |

**Gegenproben:** Für jede Prüfung wurde ein Eintrag entfernt oder eine falsche Einordnung gesetzt (approve-Stelle, Server-Route, Client-Route als Freigabe, Freigabe-Route ohne S7, Harness-Weg, geschützter Harness-Weg, Antragsart, Harness-Art, Weg). Jedes Mal war der Test rot. Ein Aufruf von `_answer_crossing` außerhalb von `decide` (vorübergehende Datei im Paket) wurde erkannt.

**Was die Bestandsliste zeigt:**
- Drei Stellen erteilen heute aus der Seite, ohne Tür: `harness/freigabe.beantworten` (F3), `uix_server.approve_gate` (F1, F2), `desk/gated.decide` (F1, F7). Sie stehen als „OFFEN bis G9“ in `APPROVE_STELLEN`.
- Außerhalb des Browsers: `sedra approve`, die Konsole des Agent Manager und `sedra lessons approve` (Lernkarten des Coders, kein Guard).
- `/api/mission/run` setzt eine Freigabe um, steht aber nicht in `HERKUNFT_WEGE`. Das ist kein Loch: Ein Harness-Prozess hat den Browser-Token nicht, und die externen Clients dürfen nur `/api/objects` und `/api/actions`.

**Neuer Befund N6 – Handlungen ohne Gate mit Wirkungen der Klasse H.** G9 deckt sie nicht, denn die Tür kennt nur Entscheidungen. Code in der Seite kann sie heute direkt aufrufen:

| Route | Wirkung |
|---|---|
| `/api/cloud/save` | schreibt die Cloud-Einstellungen (an/aus, Anbieter, Modelle) ohne Gate; nur eine geänderte `base_url` wird seit E2 zum Antrag (`uix_server.py:2670–2686`) |
| `/api/cloud/key` | setzt den API-Schlüssel ohne Gate; ein fremder Schlüssel heißt ein fremdes Konto beim Anbieter |
| `/api/cloud/module-model` | stellt ein Modul ohne Gate auf ein Cloud-Modell um, wirkt sofort für neue Aufrufe (`:2888`) |
| `/api/candidate` | `test`/`test-verify` führen Tests eines Kandidaten aus (wo sie laufen, ist nicht geprüft); `accept`/`rollback` nur mit Gate (`selfdev/candidate_acceptance.py:109–111`) |

Vorschlag für die Entscheidung des Captains (E12): Diese vier Routen bekommen in G9 dieselbe Tür. Die drei Cloud-Routen würden dann zu Anträgen wie `request:cloud_url`; bei `/api/candidate` wird zuerst geprüft, wo die Tests laufen.

**Offene Einordnung:** Das Gedächtnis der Harness (`POST /api/harness/gedaechtnis`) ist als Handlung N eingeordnet: dauerhafter Text für das Modell, der keine Rechte vergibt. Skills und `arbeitsplatz.yaml` sind aus demselben Grund H („dauerhafte Anweisung an das Modell“). Ob das Gedächtnis gleich behandelt werden soll, entscheidet der Captain (E13). Vorschlag: N lassen, denn es ist eine häufige Alltagsfunktion, und jede Wirkung braucht weiter Karten.

**Grenze:** Die Tests unter `runtime/tests/**` kann ein Modell in einer MasterChat-Sitzung ändern, also auch diesen Vollständigkeitstest abschwächen. Eine solche Änderung zeigt der G4-Code-Stand als ungesehen; verhindern wird sie erst O3 (falls die Tests der Prüfstellen hart werden sollen: E14, Vorschlag ja für `test_freigabe_*.py`).

**Nicht gebaut:** G11-05 (Verhaltensprüfung) kommt mit der Tür aus G9.

**Tests:** `test_freigabe_vollstaendig` 16 und `test_freigabe_klasse` 9 grün; Harness-, Freigabe-, Client-, Arbeitsplatz- und Vertragstests 452, 0 rot (Container). Ganze Bahn im Container: 3.789 Tests, 0 rot, 121 übersprungen.

### 13.2 E9 Variante C gebaut (03.11.2026)

- `harness/vorbehalte.py`: `runtime/src/sedra_runtime/hardware_manager/dashboard.html` ist harter Vorbehalt.
- `hardware_manager/dashboard.py`: liefert `/uix/js/hardware_dashboard.js` (nur diese Datei, ohne Token wie im Server der Oberfläche) und sendet `script-src 'self'` statt `'unsafe-inline'`. Damit zeigt `sedra hardware-dashboard` wieder Daten (Nebenbefund aus §9a behoben), und ein Inline-Skript in der Seite läuft in keinem der beiden Server.
- Test `tests/test_hardware_dashboard_server.py` (5): die Seite lädt genau das ausgelieferte Skript, kein Inline-Skript; das Skript kommt mit JS-Typ; CSP ohne `unsafe-inline`; andere Dateien und Daten ohne Token bleiben zu; Daten mit Token. Ohne die Änderung schlägt der Test fehl. Am PC nicht geprüft: das Fenster im Browser.

### 13.3 G9 und G10 gebaut (03.11.2026)

| Teil | Datei | Stand |
|---|---|---|
| Tür (G9-02) | `uix_server.py` `UIXHub.freigabe_tuer`, `freigabe_bestaetigen` | Klasse H aus der Seite → Bestätigung `B-…`, Antwort 400 `wartet_auf_bestaetigung: …` mit dem Satz für den Captain; N, Ablehnen und Kanäle außerhalb gehen sofort |
| Wege (G9-03, E12) | `decide` (alle Arten außer Harness), `/api/mission/approve` (`approve_gate_seite`), `/api/cloud/save`, `/api/cloud/key`, `/api/cloud/module-model`, `/api/candidate` (nur `test`/`test-verify`); `harness/api.py`: `beantworten` (Karte und Posteingang), Aufgabe anlegen, Vorarbeiter ernennen, Sitzung mit Vorlage-Erlaubnissen (Sitzung sofort, Erlaubnisse nach dem Ja, E11) | gebaut |
| Bestätigungen (G9-04) | `desk/bestaetigung.py` | im Speicher, Frist 10 min, Bindung geprüft, neue Antwort ersetzt die alte |
| Systemdialog (G9-05/06) | `desk/systemdialog.py` | Windows `MessageBoxW` in eigenem Thread; sonst kein Dialog |
| Konsole (G9-07/08) | `desk/freigabe_konsole.py`, `FREIGABE.bat`; Routen `/api/freigabe/offen`, `/api/freigabe/bestaetigen` nur mit CLI-Token (`uix_clients.ROUTEN_JE_CLIENT`, Befund N4), in `HERKUNFT_WEGE` | gebaut |
| Vorarbeiter nur N (G9-10, E7) | `harness/freigabe.py` | gebaut |
| Schalter (G9-11) | `freigabe_ausserhalb` in `local_switches.py` | Standard an |
| Lese-Sperre (O3-06, E8) | `vorbehalte.pruefen_lesen` für `**/runtime_data/uix/clients/**`; in `einstufung` und beim Durchsuchen | gebaut (vorgezogen aus O3) |
| Kanal (G10-01/02) | `FREIGABE_ERTEILT {art, id, weg, klasse, kanal}`; `HARNESS_APPROVED_BY` mit `kanal` | gebaut |
| Inhaltsschutz | `desk/decisions.content_decision`: Bindung trägt `route` (lokal = N) | gebaut |
| Harte Vorbehalte | `desk/bestaetigung.py`, `systemdialog.py`, `freigabe_konsole.py`, `decisions.py`, `freigabeklasse.py`, `hardware_manager/dashboard.html` | gebaut |

**Tests:** `test_freigabe_tuer` (14, Tür an, Fake-Dialog): Klasse H aus der Seite wartet und führt nichts aus (G11-05), N und Ablehnen sofort, Konsole bestätigt genau einmal, Nein lässt offen, Seite und MCP erreichen die Bestätigung nicht (403), Bindung weg oder geändert → hinfällig, Systemdialog Ja/Nein, `/api/mission/approve` und `/api/cloud/key` warten (der Schlüssel steht nie in Text oder Audit), Schalter aus, Frist, Konsolen-Modul. Gegenprobe: Tür durchlassend → rot. `test_freigabe_vollstaendig` angepasst: alle Seiten-Stellen hinter der Tür, Befund N6 leer, MCP ohne Freigabe-Routen. **In allen übrigen Tests ist die Tür aus** (`tests/host_isolation.py`, nur dort, kein Schalter im Code), damit sie die Logik ihrer Stellen weiter prüfen. Ganze Bahn im Container: 3.810 Tests, 0 rot.

**Nicht gebaut oder nicht geprüft (offen):**
- G9-09 nur teilweise: Die Seite zeigt den Wartezustand als Fehlermeldung mit dem Satz und der Kennung (jede Oberfläche zeigt `message` schon an). Eigene Anzeige an Karte und Posteingang fehlt.
- Die Harness-Karte hinter der Tür hat keinen eigenen Test; die Harness-Tests laufen mit Tür aus.
- G10-03: `sedra approve` und die Konsole des Agent Manager schreiben noch kein `FREIGABE_ERTEILT` (Kanal `konsole`).
- Am PC nicht geprüft: ob das Fenster unter `START_SEDRA.bat` im Vordergrund erscheint; `FREIGABE.bat` unter Windows.
- Stick-Liste: `FREIGABE.bat` und `desk/freigabe_konsole.py` noch nicht eingetragen.
- O3 (hart/weich, weich vor Katalog), G1, G2, G3, G6, G7: nicht gebaut (§11 Schritte 4–6).

### 13.4 O3 weicher Teil und G1 gebaut (11.11.2026)

| Teil | Datei | Stand |
|---|---|---|
| O3-03 weich | `harness/vorbehalte.py` `pruefen_weich`: `uix/shells/**`, `uix/tools/**`, `uix/css/**` (ohne `README.md`, ohne was schon hart ist) → `{grund, oberflaeche: <Pfad>}` | gebaut |
| O3-04 weich vor Katalog | `harness/freigabe.py` `einstufung`: ein `frei` oder `vorarbeiter` im Katalog wird für die Oberfläche zur Karte an den Captain (Regel `vorbehalt-weich`); nur eine aktive Aufgabe deckt; Sitzungs-Erlaubnis und Vorarbeiter nie (schließt N2 **für die Oberfläche**) | gebaut |
| O3-05 frei | `README.md` unter `uix/**` bleibt im normalen Katalog | gebaut |
| G1-01 bis G1-04 | `harness/aufgabe.py`: Feld `oberflaeche`, ein Ordner (`oberflaeche_zu_breit`, `oberflaeche_mehrere_ordner`), jedes Muster von einem `erlaubt`-Eintrag für Schreiben getroffen (`oberflaeche_nicht_erlaubt`), nur der Captain (`oberflaeche_nur_captain`), höchstens eine aktive je Projekt (`oberflaeche_schon_aktiv: T-…`); die Deckung vergleicht den Pfad mit `oberflaeche` | gebaut |
| G1-06 Hinweis | `oeffentlich(aufgabe)['oberflaeche_hinweis']` mit dem Satz (ohne den Satz zur Sammelkarte, die es noch nicht gibt) | Satz da, **Formular der Oberfläche nicht angepasst** |

**Absichtlich nicht gebaut:** O3-04 für **Modelle**. Dort steht im Katalog des Captains (`local_config/freigabe_katalog.yaml`) ein ausdrückliches `frei` für `modell_laden` der Rezepte `coder.local_primary_team` und `coder.local_primary_power` (Captain-Ja 10.11.2026). „Weich vor Katalog“ für Modelle würde das aufheben und jedes Laden zur Karte oder zur Aufgabe mit `modelle` machen; das braucht eine Entscheidung des Captains (Rest von N2).

**Offen (Schritt 5 aus §11):** Zurückhalten und Ausliefern der bestätigten Fassung (G2), Sammelkarte, Hinweise im Diff (G3), Rückweg (G7), Startbericht (G6), Formular für `oberflaeche`. Bis dahin wirkt eine gedeckte oder per Karte freigegebene Änderung an `uix/shells/**` sofort, weil der Server die Dateien bei jeder Anfrage liest.

**Tests:** `tests/test_harness_oberflaeche_weich.py` (25): weich/hart/frei je Pfad, `einstufung` mit Katalog `frei` und `vorarbeiter`, das Feld mit allen Fehlern, höchstens eine aktive Aufgabe, Deckung nur für den genannten Pfad (und die der Modelle unverändert), ganzer Weg mit echtem Guard und Kiste (Karte statt Schreiben, Aufgabe deckt nur den Pfad, Sitzungs-Erlaubnis deckt nie).


## 14. Stand des Baus (11.11.2026): O3 G2, G3, G6, G7 und das Formular G1-06

| ID | Stand | Beleg |
|---|---|---|
| G2-01, G2-02, G2-04 | gebaut: unter einer Aufgabe geschriebener Code unter `uix/` des laufenden Programms wird zurückgehalten (`harness/oberflaeche.py`, Haken in `harness/freigabe.py`); über eine Karte, ohne Aufgabe und in anderen Projekten nicht; die Platte hat die neue Fassung | `test_harness_oberflaeche_weg` |
| G2-03 | gebaut: der Betriebsserver liefert die bestätigte Fassung (`_module_file`, `STATIC_FILE`), neue Dateien als 404 | `test_harness_oberflaeche_weg` (HTTP) |
| G2-05, G2-06, G2-07 | gebaut als Antrag `harness_oberflaeche` im Posteingang (Klasse H, Bestätigung außerhalb des Browsers): Weg **Freigeben = übernehmen**, **Ablehnen** = Karte zu. **Abweichung:** das Zurücksetzen (Klasse N) ist kein dritter Weg der Karte, sondern eine eigene Route `POST oberflaeche/zuruecksetzen` mit Knopf in den Einstellungen. Die Karte entsteht am Ende einer Aufgabe oder auf Wunsch (`POST oberflaeche/vorlegen`); mehr als 30 Dateien nur über die Konsole | `test_harness_oberflaeche_karte`, `test_uix_oberflaeche_ui` |
| G2-08 | gebaut: `runtime_data/harness/oberflaeche/` (`stand.json`, `inhalt/<sha>`, `verworfen/`); die Grenze von 1 MB ist gleich `DATEI_MAX` des Werkzeugs, größere Dateien lehnt schon das Werkzeug ab | Test |
| G2-09 | **nicht gebaut:** die Vorschau mit eigenem Prüfserver-Prozess (`POST oberflaeche/vorschau`) | – |
| G2-10 | gebaut: Schalter `oberflaeche_abnahme` (Standard an, nur in der Datei) | Test |
| G3-01 bis 03 | gebaut: Hinweise `⚠` auf hinzukommenden Zeilen (`desk/install.py` `hinweise_im_diff`, `FREIGABE_WEGE`), auf der Sammelkarte und auf der G4-Karte, mit dem Satz „Hinweise sind eine Lesehilfe …“ | `test_harness_oberflaeche_hinweise` |
| G6-01 bis 03 | gebaut: Start-Bericht (`startbericht`, einziger Weg `zur_kenntnis`, Klasse N), Audit `STARTBERICHT` und `STARTBERICHT_GELESEN`; scannt beim Start nur, wenn es schon einen Code-Stand im Projekt gibt | `test_harness_startbericht` |
| G7-01, G7-02 | gebaut: Übernahme-Sätze `U-…`, Zurücknehmen mit Prüfung `seit_der_uebernahme_geaendert`, neue Dateien nach `verworfen/` | `test_harness_oberflaeche` |
| G7-03, G7-04 | gebaut: `CODE_STAND.bat <projekt> --oberflaeche`, `--uebernehmen-oberflaeche`, `--zuruecksetzen`, `--zuruecknehmen U-…`, Audit `kanal: konsole` | `test_harness_oberflaeche_konsole` |
| G7-05 | gebaut: Einstellungen → Freigabe-Modus: Liste, „Sammelkarte vorlegen“, „Alles zurücksetzen“, „Übernahme zurücknehmen“ | `test_uix_oberflaeche_ui` |
| G1-06 | gebaut: Feld „Oberfläche“ im Aufgabenformular mit dem Satz aus AM0-E1 §6 | `test_uix_oberflaeche_ui` |

Offen: G2-09 (Vorschau mit Prüfserver), die Abnahme am PC (eine echte Aufgabe mit `oberflaeche` durchspielen, die Sammelkarte über den Systemdialog bestätigen), und die Entscheidung „weich vor Katalog für Modelle“.
