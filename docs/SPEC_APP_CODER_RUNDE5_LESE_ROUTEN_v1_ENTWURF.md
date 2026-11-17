# App Coder, Runde 5: Anbindung an SEDRA (Entwurf der Lese-Routen)

Stand: 2026-11-17. Bezug: `SPEC_SEDRA_IDE_2026-11-16.md` Runde 5, Werkzeug `runtime/src/sedra_runtime/uix/tools/coder/`.
**Nur Entwurf. Nichts gebaut, am Server nichts geändert, `tool.yaml` und `shell.yaml` unverändert.** Der Coder bleibt bis zu einer Freigabe des Captains eine Attrappe mit Beispieldaten.

## 1. Ausgangslage

- Der Coder läuft im abgeschotteten Rahmen (`trust: CAPTAIN`, `/uix/frame/coder`, `sandbox="allow-scripts"`): kein Token, kein eigenes Netz. Jede Route geht über die Brücke des Kerns (`ui/bruecke.js`). Sie lässt nur Routen durch, die im Feld `api` der `tool.yaml` stehen (`routeErlaubt`, Muster `GET /api/x` oder `GET /api/x/*`), und prüft die Methode.
- Heute steht dort `api: []`. Die IDE ruft nichts.
- Muster für eine reine Lese-Sicht: `factory_lesen.py` (nur lesen, fehlt eine Quelle, sagt die Antwort `quelle: fehlt` und legt nichts an, alle Funktionen bekommen den Projekt-Wurzelordner, Grenze `LIMIT_STANDARD 50` / `LIMIT_MAX 200`). Die Routen dazu stehen in `uix_server.py` (Methoden `factory_*`) und unter `/api/uix/factory/*` im Feld `api` der Shell.

## 2. Gewünschte Lese-Routen

Namensraum `/api/uix/coder/*`, alle `GET`, alle ohne Nebenwirkung. Antworten sind JSON-Objekte mit `quelle` (`ok`, `fehlt`, `fehler`) und `grund` bei Nicht-ok, wie bei `factory_lesen`.

| Nr | Route | Zweck | Quelle im Kern | Grenzen |
|----|-------|-------|----------------|---------|
| R1 | `GET /api/uix/coder/projekt` | Name und Ordnername des aktiven Projekts für Kopfzeile und Explorer | `hub.projects` (aktives Projekt) | kein absoluter Pfad in der Antwort |
| R2 | `GET /api/uix/coder/dateien?pfad=` | Ordnerinhalt für den Explorer | `hub.project_files` (`list_dir`, `bounded`, Limit 300, `HIDDEN_NAMES`) | Pfad nach `_project_path`: relativ, höchstens 300 Zeichen, kein `..`, kein Laufwerk |
| R3 | `GET /api/uix/coder/datei?pfad=` | Text einer Datei für den Editor | `hub.project_file` (`read_text`, `FILE_PREVIEW_BYTES` 100 000) | `binary` und `too_large` als eigene Antworten, nie Inhalt |
| R4 | `GET /api/uix/coder/aenderungen` | Zähler und Liste für Quellcodeverwaltung und Statusleiste | neu: schreibgeschützter Aufruf `git status --porcelain` im Projektordner | nur diese eine Form, kein Schreibweg (siehe Entscheidung E2) |
| R5 | `GET /api/uix/coder/agenten` | Agentenliste mit Zustand | vorhanden: `GET /api/agents` | nur Anzeige, keine Aktion |
| R6 | `GET /api/uix/coder/ereignisse?seit=&limit=` | Live-Coding: wer hat wann welche Datei gelesen oder vorgeschlagen | vorhanden: `GET /api/audit`, gefiltert auf Datei-Ereignisse | Limit 50, höchstens 200; keine Texte, nur Art, Agent, Pfad, Zeit |
| R7 | `GET /api/uix/coder/sitzungen` | Liste für die Chat-Leiste, "Letzte" | vorhanden: `GET /api/harness/sitzungen` | nur Titel, Zeit, Zustand |
| R8 | `GET /api/uix/coder/sitzungen/<id>` | Verlauf einer Sitzung zum Lesen | vorhanden: `GET /api/harness/sitzungen/<id>` | höchstens die letzten 200 Einträge; Text nur mit `textContent` |

Bewusst **nicht** in Runde 5: Speichern von Dateien, Terminal-Eingabe, Chat senden, Agenten starten oder stoppen, Git schreiben, Erweiterungen installieren. Das sind Schreibwege und brauchen je ein Gate (siehe Abschnitt 5).

## 3. Wo die Routen eingetragen werden müssten

Der Coder ist ein Rahmen-Werkzeug. Anders als bei Factory Studio (läuft in der Seite der Shell, Routen im Feld `api` der Shell) prüft hier die Brücke das Feld `api` **der `tool.yaml` des Werkzeugs**. Nötig wären drei Stellen:

1. `uix/tools/coder/tool.yaml`, Feld `api`: acht Zeilen `GET /api/uix/coder/...` (R8 als Präfix `GET /api/uix/coder/sitzungen/*`).
2. `uix_server.py`: Methoden `coder_projekt`, `coder_dateien`, `coder_datei`, … in der Tabelle der GET-Routen, Muster wie `factory_typen`; Kern in einer neuen Datei `coder_lesen.py` (höchstens 400 Zeilen, nur lesen, bekommt den Projekt-Wurzelordner).
3. `shells/harness/shell.yaml`, Feld `api`: nur nötig, wenn die Shell die Routen selbst ruft. Für den Rahmen **nicht** nötig; die Zeile entfällt, solange der Coder allein im Rahmen läuft (Vorschlag).

## 4. Sicherheitsregeln für den Bau

- Rahmen ohne Token: kein `fetch`, kein Netz, nur `ctx.api` der Brücke. Der Test `test_uix_coder_app` hält das fest (kein `fetch`, kein `localStorage`, nur `.t-coder`-Selektoren).
- Pfade: ausschließlich über `_project_path`; zusätzlich eine Sperrliste für `local_config`, `.env`, `*.key`, `*.pem`, `secrets*` (diese Namen erscheinen weder in Listen noch als Inhalt). **Heute fehlt die Sperrliste**; ohne sie darf R2/R3 nicht gebaut werden.
- Antworten nie mit absolutem Benutzerpfad, nie mit Schlüsseln. Dateiinhalt ist Fremdtext: im Editor als Wert einer `textarea`, nie als HTML.
- Jede Route zählt Aufrufe im Audit nur als Zahl, nicht mit Inhalt (Muster `HARNESS_*`-Ereignisse).
- Alle Routen laufen ohne Freigabe, weil sie nichts ändern. Jede spätere Schreibroute (Abschnitt 5) geht über `gated.request`, wie `prozess_beantragen`.

## 5. Schreibwege (für später, nicht Teil von Runde 5)

| Wunsch | Weg | Gate |
|--------|-----|------|
| Datei speichern | Antrag `coder_speichern` mit Bindung an den Stand der Datei (`binding_stale`), Anwendung erst nach "Freigeben und anwenden" | Captain, Klasse wie `rueckblick_schreiben` |
| Terminal ausführen | nur als Antrag mit Befehl und Arbeitsordner, nie direkt | Captain, höchste Klasse |
| Nachricht an Sitzung | vorhandener Weg `POST /api/harness/sitzungen/<id>/post` | wie heute |

## 6. Bauabschnitte nach Freigabe (Vorschlag)

1. `coder_lesen.py` mit R1 bis R3 und Sperrliste, Tests mit Wegwerf-Projekt (Ordner, Datei, binär, zu groß, `..`, Sperrliste, Projekt fehlt).
2. Explorer und Editor lesen echte Dateien; Beispieldaten bleiben als Ausweichfall ("Quelle: Beispieldaten" nur, wenn die Route `fehlt` meldet).
3. R5 bis R8 (nur vorhandene Quellen anschließen).
4. R4 (Git-Status), erst nach Entscheidung E2.
5. Schreibwege einzeln, je mit Gate und Test.

Prüfpunkte je Abschnitt: Sichtprüfung im Wegwerf-Projekt (Skill `sedra-ui-sichtpruefung`), Test mit Exit-Code, Konsole ohne Fehler.

## 7. Offene Entscheidungen für den Captain

- **E1 Projektbindung.** Soll der Explorer immer das aktive Projekt der Shell zeigen? Vorschlag: ja, nur dieses, kein freier Ordnerwechsel.
- **E2 Git-Status.** Darf ein schreibgeschützter `git status` im Projektordner laufen? Vorschlag: ja, feste Form, 2 Sekunden Zeitlimit; sonst bleibt die Quellcodeverwaltung eine Attrappe.
- **E3 Sperrliste.** Welche Dateinamen sollen nie erscheinen? Vorschlag: die Liste aus Abschnitt 4.
- **E4 Speichern.** Soll Speichern jemals möglich sein, und dann nur als Antrag mit Gate? Vorschlag: ja, als eigener Abschnitt nach R1 bis R3.
- **E5 Terminal.** Soll die Terminal-Leiste echte Befehle ausführen? Vorschlag: nein in dieser Stufe; sie zeigt nur Ausgabe und Logs (R6, R8).

## 8. Nicht geprüft

- Keine der Routen existiert; alle Quellen (`project_files`, `project_file`, `/api/agents`, `/api/audit`, `/api/harness/sitzungen`) sind im Code gelesen, aber hier nicht als Aufruf aus dem Rahmen heraus getestet.
- Ob `GET /api/audit` Datei-Ereignisse mit Pfad enthält, ist nicht belegt (Form der Ereignisse nicht gelesen); R6 kann deshalb eine neue Quelle brauchen.
- Antwortzeiten bei großen Ordnern, Zeichensätze außer UTF-8, Windows-Pfadbesonderheiten und die Wirkung der Sperrliste auf Verknüpfungen sind nicht untersucht.
