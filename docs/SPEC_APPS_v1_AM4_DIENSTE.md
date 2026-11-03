# SPEC Apps v1 – AM4: Dienste außerhalb des Server-Prozesses, MCP-Zugang mit Berechtigung (03.11.2026)

Status: **G1** (Anforderungen mit Entwurf), nichts gebaut. Teil von `docs/KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` §11. Setzt AM3 voraus.
Ziel: (A) Der vorhandene MCP-Zugang zum Desk bekommt eine Berechtigung wie eine App. (B) Eine App kann ein **Dienst** sein: ein eigener Prozess, den der Kern startet und stoppt, der nur über Desk-Objekte und -Verben spricht. (C) Was es bräuchte, damit SEDRA fremde MCP-Server als Werkzeuge nutzt – mit der Empfehlung, das zurückzustellen.
Pfade relativ zu `runtime/src/guppi_runtime/`, Zeilen für c364081.

## 1. Befund

| Nr | Befund | Beleg |
|---|---|---|
| B1 | Externe Clients: `cli` und `mcp`. Beim Start schreibt die Oberfläche je Client einen Zufallstoken nach `runtime_data/uix/clients/<client>.json` (Windows DPAPI, sonst Datei 0600). Ein Client-Token öffnet nur `POST /api/objects` und `POST /api/actions`. | `uix_clients.py:1–9, 21–22` |
| B2 | Der Dateikopf sagt selbst: `client` ist eine Herkunftsangabe, **keine Berechtigung**; „alle Token-Halter sind dasselbe Konto auf Loopback“. | `uix_clients.py:7–9` |
| B3 | Der MCP-Server `desk_mcp.py` bietet die Werkzeuge `objects` und `act` (Vertrag, Nachtrag Spec 0, R5). Die Einstellungsseite der Harness sagt: „Zu konfigurieren gibt es nichts (K7).“ | `shells/harness/einstellungen.js:223–230` |
| B4 | Weitere MCP-Server im Paket: `devvm_mcp.py` (DevVM-Arbeitsordner, `docs/MCP_SERVER_DEVVM.md`), `state_mcp.py`. Nicht gelesen. | Dateiliste |
| B5 | Ein Verb über einen Client-Token durchläuft dasselbe Desk mit Gate; `client` steht im Audit (`UIX_ACTION`, R4). Welche Verben ein `mcp`-Client rufen darf, ist nicht eingeschränkt außer durch die Gates. | Vertrag Nachtrag Spec 0 R4/R5; `desk/kinds.py:154–161` |
| B6 | Die microVM für Tests hat standardmäßig **kein Netz**. | `runtime/config/sandbox.yaml:16` (`network: deny`) |
| B7 | Ob und wie ein Prozess in der microVM den Desk erreichen kann, ist nicht bekannt (`sandbox/broker.py`, `worker.py` nicht gelesen). | – |
| B8 | SEDRA nutzt heute **keine** fremden MCP-Server als Werkzeuge für das Modell (nicht gefunden; die Einstellungsseite nennt nur `desk_mcp`). | `einstellungen.js:223–230` |

**Wichtige ehrliche Grenze (aus B1/B2):** Auf dem Host läuft jeder Dienst unter demselben Benutzerkonto wie SEDRA. Ein Prozess dieses Kontos kann DPAPI-geschützte Dateien desselben Kontos entschlüsseln und Dateien mit 0600 desselben Kontos lesen. **Token-Bereiche (Scopes) sind auf dem Host deshalb Ordnung und Nachweis, aber keine Sicherheitsgrenze gegen einen bösartigen Dienst.** Eine echte Grenze gibt es nur, wenn der Dienst in einer Umgebung läuft, die die Token-Dateien nicht lesen kann (microVM, anderes Konto). Daraus folgt AM4-07.

## 2. Anforderungen

### 2.1 Teil A – MCP-Zugang des Desk mit Berechtigung

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM4-01 | Der Zugang `mcp` wird in der Berechtigung als **Zugang** geführt (kein Manifest, kein Start durch SEDRA – der MCP-Host startet `python -m guppi_runtime.desk_mcp` selbst): Eintrag `zugaenge: {mcp: {lesen, verben}}` in `local_config/apps/berechtigung.yaml` (AM3-05). Die Berechtigungsseite zeigt, welche Typen er lesen und welche Verben er rufen darf. | uix_check |
| AM4-02 | Vorgabe: lesen alle Typen, Verben **keine**. Verben auf Antrag (Gate `grant_app_rights`), je `typ.verb`. Der Server prüft bei Token-Klasse `mcp` den Körper wie AM3-11. | Test: Verb ohne Gewährung → 403 `verb_nicht_gewaehrt`, Audit |
| AM4-03 | Für `cli` gilt dasselbe als Zugang `cli`, Vorgabe: lesen alle, Verben alle (heutiges Verhalten, weil der Captain selbst tippt). | Test |
| AM4-04 | Die Seite „Integrationen → MCP“ zeigt statt „nichts zu konfigurieren“ die Berechtigung von `desk-mcp` und den Satz aus B2 in Klartext („jedes Programm unter deinem Windows-Konto kann diesen Zugang nutzen“). | uix_check |

### 2.2 Teil B – Dienst-Apps

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM4-05 | `kind: dienst` mit Block `dienst: {start: [<programm>, <arg>…], ort: host|microvm, neustart: nie|bei_fehler, protokoll_max: <KB>}`. `start[0]` muss eine Datei **im Ordner der App** sein; Pfade mit `..`, absolute Pfade und Shell-Zeichen → abgewiesen. Ein Dienst hat keine Fläche und keinen Ort (darf eine `zelle` haben, AM3-23 sinngemäß über den Desk). | Schema-Test |
| AM4-06 | `dienst` ist eine Fähigkeit der Schutzstufe B (Antrag mit Gate). Start nur, wenn gewährt **und** aktiv. Deaktivieren/Entzug stoppt den Prozess (erst Bitte, nach 5 s beenden) und macht seinen Token sofort ungültig. | Test mit Fake-Prozess |
| AM4-07 | `ort: host` nur für Vertrauen `CAPTAIN` und `GUPPI_BUILT`. `COMMUNITY` nur `ort: microvm` – und erst, wenn B7 geklärt ist; bis dahin ist ein `COMMUNITY`-Dienst nicht einbaubar (`dienst_fremd_nur_microvm`). | Test |
| AM4-08 | Jeder Dienst bekommt einen **eigenen** Client-Token (`dienst:<id>`), übergeben über eine Datei, deren Pfad in der Umgebungsvariable `SEDRA_DIENST_TOKEN_DATEI` steht; der Server ordnet ihn der App zu; `client` im Audit = `dienst:<id>` (vom Server gesetzt, R4). Der Token öffnet nur `objects`/`actions`, geprüft gegen die Gewährung (AM3-11). | Test |
| AM4-09 | Ausgaben (stdout/stderr) gehen nach `runtime_data/dienste/<id>/protokoll.txt`, begrenzt auf `protokoll_max` (Vorgabe 512 KB, rollierend). Kein Inhalt ins Audit. | Test |
| AM4-10 | Audit: `DIENST_GESTARTET`, `DIENST_GESTOPPT {grund}`, `DIENST_ABGESTUERZT {exitcode}`, `DIENST_TOKEN_ENTZOGEN`. `neustart: bei_fehler` höchstens 3 Mal je Stunde, dann aus mit Hinweis. | Test |
| AM4-11 | Text, den ein Dienst über Verben in den Kern bringt und der später an ein Modell geht, gilt als **Fremdinhalt** und läuft durch den Inhaltsschutz wie ein Dokument (R-08/R-09, `gateway/klassen.py:65–70`). | Test mit Anweisung im Text |
| AM4-12 | Ein Dienst kann keine Kern-Erweiterung sein: Er registriert keine Objekttypen und keine Verben (`desk/kinds.py` bleibt beim Start eingefroren, Vertrag R1). Er nutzt vorhandene Typen; eigene Typen nur als Daten in seiner Ablage. | Code-Prüfung |

### 2.3 Teil C – Fremde MCP-Server als Werkzeuge (zurückgestellt)

| ID | Anforderung (für später, nicht in diesem Baustein zu bauen) |
|---|---|
| AM4-13 | Ein fremder MCP-Server wäre ein Dienst, dessen **Werkzeuge dem Modell** angeboten werden. Jedes Werkzeug bräuchte eine Wirkungsklasse und eine Stufe im Freigabe-Katalog der Harness (`harness/katalog.py:18`), Vorgabe `captain`. |
| AM4-14 | Werkzeugbeschreibungen und Antworten fremder Server sind Fremdinhalt (Werkzeug-Beschreibungen können Anweisungen an das Modell enthalten). Sie müssten vor dem Modell durch den Inhaltsschutz. |
| AM4-15 | Ändert ein fremder Server seine Werkzeugliste, wäre das ein Update mit Rechte-Diff (AM3-14). |
| AM4-16 | **Empfehlung:** Teil C erst nach AM6 und nach einer eigenen Sicherheits-Spec. Begründung: Er bringt Fremdinhalt direkt in die Werkzeugwahl des Modells; das ist ein anderer Angriffsweg als alles in AM0–AM3. |

## 3. Entwurf

- `uix_clients.py`: `CLIENTS` bleibt für `cli`/`mcp`; Dienst-Tokens werden zur Laufzeit erzeugt und nur im Speicher des Servers zugeordnet (wie heute die Zuordnung Token → Client, `uix_clients.py:5–6`), die Datei liegt unter `runtime_data/dienste/<id>/token.json` (DPAPI/0600).
- Prozessverwaltung: eine neue Datei `desk/dienste.py` (≤ 400 Zeilen), gestartet und gestoppt vom Hub; kein Shell-Aufruf (`subprocess` mit Liste, `shell=False`), Arbeitsordner = App-Ordner, Umgebung minimal (`PATH`, `SYSTEMROOT` unter Windows, `SEDRA_DESK_PORT`, `SEDRA_DIENST_TOKEN_DATEI`).
- `ort: microvm`: offen bis G2 (B7). Wenn der Broker keinen Kanal zum Desk bietet, entfällt `microvm` für Dienste in v1, und fremde Dienste sind nicht möglich.

## 4. Tests und Abnahme

Fake-Dienst (Python-Skript im Testordner), der Objekte liest, ein erlaubtes und ein nicht gewährtes Verb ruft, abstürzt, zu viel schreibt. MCP: Test mit gesetztem Kopf der Token-Klasse `mcp`. Abnahme am PC: Seite Integrationen → MCP zeigt Berechtigung; ein Verb über MCP ohne Gewährung wird abgewiesen.

## 5. Rückfall

Schalter `dienste` (Standard aus). `desk-mcp` ohne Gewährungsdatei = heutiges Verhalten (lesen und Verben).

## 6. Abgrenzung

Kein fremder Python-Code im Server-Prozess. Keine Netzfreigabe für Dienste durch SEDRA (auf dem Host nicht durchsetzbar; in der microVM `deny`). Teil C nicht bauen.

## 7. Risiken

- Hoch: Prozessstart auf dem Host ist Ausführung von Code mit den Rechten des Captains. Darum nur eigene (`CAPTAIN`) oder von SEDRA gebaute (`GUPPI_BUILT`) Dienste auf dem Host.
- Die Einschränkung des MCP-Zugangs (AM4-02) kann bestehende Abläufe des Captains mit MCP-Hosts (z. B. Claude Desktop) brechen, wenn sie Verben nutzen. Gegenmittel: Übergang mit „Verben wie bisher“ und Hinweis.

## 8. Entscheidungen des Captains

| Nr | Frage | Vorschlag |
|---|---|---|
| AM4-E1 | MCP-Zugang: Verben standardmäßig aus? | ja, mit Übergangszeit und Hinweis |
| AM4-E2 | Fremde Dienste nur in der microVM – und wenn das nicht geht, gar nicht? | ja |
| AM4-E3 | Teil C (fremde MCP-Server als Werkzeuge) zurückstellen? | ja |

## 9. Berechtigungen vorab

Schreiben `uix_clients.py`, `desk/dienste.py` (neu), `desk_mcp.py` (nur Anzeige der Berechtigung, falls nötig), `uix_server.py`, Harness-Einstellungen (Seite MCP), Tests. Lesen `sandbox/*` für G2.

## 10. Nächste Gates

G1 → G2 (Kanal microVM ↔ Desk nach Lesen von `sandbox/`; Prozessverwaltung unter Windows) → G3 → G4.
