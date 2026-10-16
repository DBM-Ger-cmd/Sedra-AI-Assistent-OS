# UIX-Roadmap (Stand 2026-10-04)

Grundlage: Lesen von `uix/retro_desktop.html` (959 Zeilen), `uix_server.py`, `START_GUPPI_FENSTER.bat`, `hardware_manager/dashboard.html` (nur dessen Existenz geprüft) und des Vergleichsordners `GUPPI_Vergleich_2026-10-03`. Die UIX wurde nicht gestartet, die Befunde stammen aus dem Code.

## Befunde

**Fehler**
- Chat-Fenster „GUPPI Interface" ist beim Start unsichtbar (`.window{display:none}`); der Benutzer sieht kein Eingabefeld.
- `openGuppi()` leert bei jedem Aufruf den Chatverlauf.
- `openBridge` ist doppelt definiert (erste Version tot), `openMachineRoom` wird nie aufgerufen.
- `activeProject` (Name) und `activeProjectId` laufen getrennt; ohne Projekt steht trotzdem „GUPPI OS" in der Begrüßung.
- Feste Werte im Projektfenster: „VM Workspace: nicht qualifiziert" (stimmt seit 2026-10-02 nicht mehr), „Kontext: geladen", Dateien README/ROADMAP.

**Attrappen**
- Ein Skript deaktiviert am Ende alle Knöpfe ohne `onclick` (Companion, Brücke betreten, Maschinenraum, Logbuch, Zurück, Dateien, VM-Konsole, Projekt prüfen).
- „—" und „□" tun nichts, Fenster sind nicht verschiebbar, die meisten Startmenü-Einträge ohne Funktion.

**Verbindung zur Runtime**
- Chat legt nur eine Mission an, keine Antwort von GUPPI, kein Verlauf.
- Vorhandene Endpunkte ohne UI: `/api/supervisor`, `/api/context`, `/api/routing`, `/api/permissions`, `/api/resources`, `/api/self-development`; Hardware-Manager-Dashboard ist nicht im Desktop verlinkt.
- Freigaben (Gates) nur über Brücke → Mission → Processor-Fenster erreichbar.

**Technik**
- Alles in einer Datei (HTML, CSS, ca. 400 Zeilen JS); JS nur über `pruefen.py` (Headless-Browser) testbar.
- Bedienelemente sind `div`s, keine Tastaturbedienung; Fensterpositionen fest.

## Plan

### Phase 1: Stolpersteine beheben
Vergleichsaufgabe läuft in `GUPPI_Vergleich_2026-10-03` (Unsloth vs. GUPPI). Phase 1 wird erst nach dem Vergleich ins Original übernommen.
1. Chat beim Start offen, Eingabefeld fokussiert.
2. Ehrlicher Zustand ohne Projekt (kein `undefined`/`null`, deutscher Hinweistext).
3. Chatverlauf bleibt erhalten; `newChat()` setzt bewusst zurück.
4. Name und ID des aktiven Projekts in einem Zustandsobjekt.
5. Tote/doppelte Funktionen entfernen.
6. Feste Texte im Projektfenster aus `/api/status` füllen.

### Phase 2: Alles Sichtbare ist echt
1. Jede Attrappe an die Runtime anbinden oder ausblenden (nicht nur ausgrauen).
2. Fenster verschiebbar, Minimieren/Maximieren, Taskleistenknopf je Fenster.
3. Maschinenraum aus `/api/status`, `/api/resources`, `/api/routing`: GPU-Lease, geladenes Modell, Kontextbudget, KV-Cache-Schätzung, Reservierungen.
4. Hardware-Manager-Dashboard (Telemetrie, Profile, nicht verfügbare Sensoren kennzeichnen) in den Desktop einbinden.
5. Logbuch aus Missionen, Schrittjournal und TESTLAB-Läufen (`runs`, `summary`, `events`).

### Phase 3: Chat wird zur Arbeitsfläche
1. Missionsstatus live im Chat (Plan, Phase, Ergebnis), „Ausführen" im Chat.
2. Freigaben als Karte im Chat (Anfrage sichtbar, einmal freigeben / ablehnen).
3. Kandidaten-Ablauf (testen, prüfen, übernehmen, zurückrollen) als Schrittleiste statt JSON-Dump.
4. Offline-/Fehlerzustand mit erneutem Verbinden.
5. Audit-Kette und Guard-Aktionen lesend anzeigen.

### Phase 4: Selbstausbau
1. HTML in Dateien aufteilen (CSS, JS-Module, Fensterbausteine) → kleinere, prüfbarere GUPPI-Änderungen.
2. `pruefen.py` als feste Abnahme für UIX-Änderungen.
3. GUPPI baut Phase 2/3 schrittweise selbst, jeweils als Kandidat mit Gate.

### Phase 5: Feinschliff
Tastaturbedienung, echte Buttons, responsive Fenster, Statuszeile im Tray mit echten Werten.

### Leitplanken (aus dem Unsloth-Plan übernommen)
- Runtime-Fakten (Supervisor-, Job-, Guard-Zustand) bleiben in der Runtime; die UIX liest nur (`/api/...` read-only) und speichert keinen eigenen Runtime-Zustand.
- Die UIX nennt Dinge so, wie die Runtime sie nennt, und erfindet keine eigenen Statusbegriffe.
- Server-Neustart oder Fensterschließen darf keinen stillen Datenverlust verursachen.

## Vergleich mit dem Unsloth-Plan
Der Unsloth-Plan setzt bei Hardware Manager, Ressourcen-UI und Audit/Logging an und hat damit die vorhandenen, nicht angezeigten Endpunkte gut erkannt (in Phase 2/3 oben übernommen). Er benennt die konkreten Fehler in `retro_desktop.html` nicht (verstecktes Chat-Fenster, Attrappen, doppelte Funktionen) und enthält Zeitschätzungen sowie Häkchen ohne Prüfung. Reihenfolge hier deshalb: erst die Bedienbarkeit (Phase 1), dann Anzeige der Runtime-Daten.

## Stand 2026-10-04 (Umsetzung)
- Phase 1: fertig (Chat offen mit Fokus, ehrlicher Zustand ohne Projekt, Verlauf bleibt, ein Projektzustand, tote Funktion entfernt, Projektfenster aus `/api/status`).
- Phase 2 (teilweise): Fenster verschiebbar/minimierbar/maximierbar, Taskleistenknöpfe, Attrappen angebunden oder entfernt, Maschinenraum und Logbuch (mit Audit-Kette). Offen: Hardware-Manager-Dashboard einbinden, Maschinenraum als Karten, feste Dateikarten im Projektfenster.
- Phase 3: Missions-Karte im Chat mit Ausführen, Freigeben und Ablehnen (`/api/mission/reject`), Kandidaten-Schrittleiste, Verbindungsabbruch mit Wiederverbinden, `/api/audit`.
- Neu (Modelle): Fenster „Modelle" (`/api/models`, Laden/Entladen unter TESTLAB-GPU-Sperre, Wechsel der Modellkombination), `RoleRouter.resolve_recipe`.
- Neu (Chat mit Modell): `/api/chat/reply`; Smalltalk ohne Plan-Karte, Plan nur auf Wunsch („Als Auftrag planen", `/plan ...`); eine Sitzungs-Mission pro Chat.
- Neu (Prozesse): Abschnitt „Läuft gerade" im Modelle-Fenster: GUPPI-llama-server (auch fremde), GUPPI-Läufe und Supervisor-Jobs sehen und abbrechen (`/api/processes`, `/api/process/stop`, `/api/job/cancel`); Warnung, wenn das laufende Modell nicht zum aktiven Profil passt. Es werden nur GUPPI-eigene Server und Läufe angeboten, nie fremde Programme.
- Offen: Schalter ändern (mit Freigabe), Modellauswahl direkt im Chat, Dateien im Projektfenster, `role_routing.yaml` bearbeiten.
- Neu (Hardware): Fenster Hardware zeigt das Hardware-Manager-Dashboard (/hardware im Rahmen, lesende Routen /api/state, /api/inventory, /api/profiles, /api/capabilities; keine Schreibroute). Profile ändern bleibt im CLI.
- Neu: Maschinenraum als Karten (System, Hardware, GPU/RAM, Modelle/Routing, Entwicklungsumgebung, Kontext, Tools); Hardware-Dashboard im UIX-Look (Farben, Schrift, Kartenform; Struktur unverändert).
- Neu: Dateikarten im Projektfenster (/api/project/files, /api/project/file, lesend über das Filesystem-Tool; Ordner zuerst, Pfadleiste, Textvorschau bis 100 KB im Verarbeitungsfenster; blendet __pycache__, .git, 
ode_modules, .venv aus). Damit ist Phase 2 bis auf Schalter/Modellauswahl im Chat abgeschlossen.
- Neu: Schalter mit Freigabe im Fenster Modelle (/api/switches, /api/switch/request, /api/switch/apply): Anfrage erzeugt eine Mission mit Gate change_switch, nach Freigabe wird nur der eine Wert in local_config/switches.yaml geändert (Kommentare bleiben, Sicherung switches.yaml.bak-<Datum>-uix), gültig ab dem nächsten Start.

## Phase 4 umgesetzt (2026-10-04): Aufbau der Oberfläche
Die UIX besteht nicht mehr aus einer Datei. Unter `runtime/src/guppi_runtime/uix/`:
- `retro_desktop.html`: nur Markup (ca. 260 Zeilen), lädt `css/desktop.css` und die Skripte aus `js/` in dieser Reihenfolge.
- `js/core.js` (Token, `api()`, Hilfsfunktionen), `desktop.js` (Fenster, Taskleiste, Startmenü, Zwischenablage), `status.js` (Laufzeitstatus, Maschinenraum, Logbuch, Hardware), `missions.js` (Plan-Karte, Freigaben, Brücke), `projects.js` (Projekte und Dateikarten), `chat.js` (Chat, Modellantworten), `models.js` (Modelle, Prozesse, Schalter, Modellauswahl), `main.js` (Start, läuft zuletzt).
- Klassische Skripte im gemeinsamen globalen Namensraum: Code auf oberster Ebene, der beim Laden läuft, gehört nur nach `main.js`.
- Der Server liefert `/uix/css/*.css` und `/uix/js/*.js` aus einer Whitelist (kleine Buchstaben und Unterstrich, Endung = Ordner) und liest sie bei jeder Anfrage, Änderungen sind nach einem Neuladen sichtbar. CSP: `script-src 'self' 'unsafe-inline'`.
- Tests: `test_uix_server.py` liest die Seite über `page_source()` (Markup + Styles + alle Skripte); `node --check` prüft jede JS-Datei; ein Test verlangt, dass jede Datei unter 400 Zeilen bleibt.
- Für GUPPI-Änderungen an der Oberfläche: die betroffene `js/`-Datei plus `tests/test_uix_server.py` als ausgewählte Dateien übergeben (kleiner als die frühere Einzeldatei).

## Modellauswahl im Chat (2026-10-04)
Unter dem Chat: Auswahlfeld mit den aktivierten Modellen, kurzer Hinweis „Gut für: …" je Modell (`MODEL_HINTS` in `js/models.js`), Laden beim Auswählen nach Rückfrage, „Kein Modell (nur planen)" entlädt. Beim Wechsel wird das von der UIX geladene Modell entladen, wenn der VRAM sonst nicht reicht; fremde Server werden nie angefasst. Fehler (zu wenig VRAM, GPU belegt) werden auf Deutsch erklärt.
- Neu: Modell-Einstellungen im Fenster Modelle (`/api/routing-config`, `.../request`, `.../apply`): je Rezept der Overlay-Datei `local_config/role_routing.yaml` Aktiv, Kontext (nur Stufen), Experten im Arbeitsspeicher (`n_cpu_moe` 0-48) und KV-Genauigkeit (f16/q8_0). Gate `change_routing`, nur die eine Zeile wird geändert (Kommentare, Zeilenenden bleiben), Sicherung `role_routing.yaml.bak-<Datum>-uix`, danach Prüfung mit dem echten Lader (bei Fehler zurückgesetzt), gültig ab dem nächsten Start.

## Stand 2026-10-13: Durchsicht im Browser
Erste Prüfung der UIX mit laufendem Server und Headless-Chromium (statt nur Lesen). Befunde und Behebungen in [UIX_ANALYSE_2026-10-13.md](UIX_ANALYSE_2026-10-13.md):
Fensterinhalt überlief den Rahmen (Chat-Fenster ohne Titelleiste), Taskleiste lief über, „null" als Modellname, zentrierte Listen in Brücke/Logbuch, grünes BLOCKED, Rohdaten ohne Kopf im Mission-Fenster.
Behoben, 5 Tests dazu (78 grün). Erste Tastaturbedienung (Phase 5) für Fenstersteuerung, Menüs, Taskleiste, Projektordner.
Offen und dort begründet: mehrere Verarbeitungsfenster, Verlauf nach Neuladen, Entscheidung zu den zwei Chat-Fenstern, Freigabe-Leiste G7, Live-Karte, Browser-Abnahme `uix_check.py` als feste Prüfung vor GUPPI-Kandidaten.
Nachtrag 22:35: Browser-Abnahme `benchmarks/uix_check.py` (+ `test_uix_browser.py`) und Live-Missionskarte umgesetzt; Specs `chat_store`, `window_state`, `mission_filter` für GUPPI vorbereitet; `spec_check.py` prüft jetzt auch node-Tests.
