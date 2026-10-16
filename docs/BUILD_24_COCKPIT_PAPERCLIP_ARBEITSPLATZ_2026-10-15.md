# Build 24: Cockpit und Paperclip ohne Platzhalter; SEDRA kennt seinen Arbeitsplatz (15.10.2026, Ticket B6-G-06)

**Klaus, 18:44:** *„Werte Design und Funktion für die zwei weiteren Bereiche Cockpit und Paperclip auf und hinterlege in den Modulen die dafür
nötigen Funktionen – keine Dummys.“* **19:05:** Routinen-Einträge entfernen; voller Umfang. **19:22:** *„Die Shell bildet den Arbeitsplatz für
SEDRA; SEDRA muss – wie beim KI GateWay – seinen Arbeitsplatz kennen, um helfen und beraten zu können.“* **19:34:** KI-GateWay-Funktionen
bleiben in ihrer Shell (der GateWay-Block in Baum/Navigation/Dashboard wurde wieder entfernt). **19:36:** *„Arbeitsplatzwissen bleibt immer im Modul.“*

## 1. Befund (Build 23, selbst eingesehen)

| Nr | Platzhalter | Was dahinter war |
|---|---|---|
| D1 | Cockpit „＋ Neu → Projekt anlegen“ öffnete die Dateiliste mit dem Satz „sag unten ‚neues Projekt‘“ | `POST /api/project/create` existierte, kein Werkzeug rief es |
| D2 | „＋ Neu → Modell hinzufügen (GGUF wählen, Rezept prüfen, laden)“ öffnete die Werkstatt-Liste | `model/pick·browse·inspect·add/request` + Gate existierten – nur im alten GUPPI-XP-Fenster (`uix/js/model_add.js`) genutzt |
| D3 | Baum „Teststrecke“ öffnete dieselbe Liste | `standard-test` + `start` existierten (`uix/js/standard_test.js`), kein Werkzeug |
| D4 | „Routinen – noch nicht gebaut“ in beiden Shells | kein Backend, kein Werkzeug (Nachtkette, Konzept) |
| D5 | Paperclip-Hinweis „Board = Captain“ | – |
| D6 | Cockpit-CSS mit festen Pixelgrößen (10–13 px) | „Schrift Groß“ aus dem Umschalter griff dort nicht; Paperclip: Umschalter neben dem Gesprächsknopf, KPI-Kacheln schnitten Text ab |

## 2. Was gebaut wurde (ADAPT – kein neues Backend)

| Nr | Änderung | Dateien |
|---|---|---|
| F1 | **Werkstatt 1.1**: Abschnitte „Neues Modell“ (Dateidialog dieses PCs / Modellordner / Pfad → Prüfen → Rezept mit ID, Rollen, Kontext → „Rezept anlegen (Freigabe)“ → Entscheidung) und „Teststrecke: Standardtest“ (Dauer, Kriterien, Start, Fortschritt alle 5 s, Ergebnis, „Empfehlung als Freigabe anlegen“). Objekt `model:neu` / `model:teststrecke` öffnet den Abschnitt; Verb „Neues Modell“. Offene Modell-Freigaben werden angezeigt. Fehlerwörter des Servers in Sätzen (`explainAddError`). | `uix/tools/workshop/tool.js·css·yaml` |
| F2 | **Projekt 1.1**: „Neues Projekt“ (Name 1–80 → `POST /api/project/create` → Hinweis und Knopf „Modus und Grenzen“); Projektname aus `display_name`. | `uix/tools/files/tool.js·css·yaml` |
| F3 | Cockpit-Baum: „Modell hinzufügen“, „Teststrecke“ (mit Hinweis, ob ein Modell geladen ist); **Routinen weg**. ＋-Neu-Texte passen zu dem, was die Werkzeuge tun. | `shells/cockpit/tree.js·shell.js` |
| F4 | Paperclip: **Routinen weg**; Kartenhinweise sachlich. | `shells/paperclip/nav.js·pages.js` |
| F5 | **Arbeitsplatz-Wissen je Modul**: `arbeitsplatz.yaml` in `shells/cockpit`, `paperclip`, `minimal`, `gateway-studio`, `guppi-xp` (Satz, Zonen, eigene Wörter mit Objekt, Begriffe) und in `tools/workshop`, `files`, `decisions`, `boundaries`, `intent`, `logbook`, `gateway` (Anleitungen, Begriffe). | 12 neue YAML-Dateien |
| F6 | **`desk/arbeitsplatz.py`**: Lader (erlaubte Schlüssel, Objekttypen des Vertrags ohne `routine`; Fehler = Befund, Stück bleibt weg), Vertragsteil (Umschalter, Strg+K, Entscheidungen, GateWay = eigene Oberfläche), SQLite `local_config/sedra/arbeitsplatz.sqlite` (aus den Dateien, bei jedem Start neu), Suche (Wortgrenzen, kein Treffer ohne Wort der Frage, Doppeltes zusammengelegt), `naechstes(live)` in der Reihenfolge eines Menschen (Grenzen → Entscheidungen → GateWay → Aufgaben → Modell → Projekt), `antwort()` mit Knöpfen. | `desk/arbeitsplatz.py` |
| F7 | **Gespräch**: Reihenfolge GateWay-Wissen → Arbeitsplatz-Wissen → Modell. Zuständig bei „wo finde ich …“, „wie … ich …“, „was ist …“, „was muss ich als Nächstes machen“ (im Studio bleibt das beim GateWay). Audit `UIX_CHAT_ARBEITSPLATZ_WISSEN` ohne Text. Systemtext des Modells nennt die aktive Oberfläche (Zonen, Wörter, Wege); zwei lesende Werkzeuge `arbeitsplatz_wissen`, `arbeitsplatz_stand`; `CHAT_STATE_WORDS` erweitert. `arbeitsplatz` ist Kern (E3). | `uix_server.py`, `chat_tools.py`, `selfdev/evolution_targets.py` |
| F8 | **Design**: Cockpit nur Token-Stufen, Fokusring im Baum, ＋-Neu 280 px, Hinweiszelle zweizeilig; Paperclip Umschalter über dem Gesprächsknopf (`.pc ~ .sx-host`), KPI-Unterzeile zweizeilig, Fokusring in der Navigation, Platz unten auf der Seite. | `shells/cockpit/shell.css·strip.js`, `shells/paperclip/shell.css` |

Nicht gebaut (bewusst): Routinen als Modul (OPEN, Register); GateWay-Einträge in Cockpit/Paperclip (Klaus 19:34).

## 3. Sicherheitsprüfung
- Nichts läuft von allein: jede Antwort der Wissensbasis liefert Knöpfe (`kind: open`); Rezept und Kontext werden nur als Gate vorgelegt (`add/request`, `routing-config/request`); das Anwenden bleibt „freigeben und anwenden“ im Werkzeug Entscheidungen mit Einmal-Token und Bindung.
- Allowlist: alle neuen Routen stehen in `tool.yaml`; der Dateidialog (`model/pick`) und der Modellordner (`model/browse`) sind serverseitig auf den Modellordner begrenzt (unverändert seit Build 14).
- Wissensdateien sind Daten, kein Code: der Lader nimmt nur bekannte Schlüssel, nur Objekttypen des Vertrags, keine Funktionen; ein Fehler ist ein Audit-Befund (`UIX_ARBEITSPLATZ_BEFUND`), kein Absturz. Das Audit trägt nie den Fragetext.
- Live-Stand: nur Zahlen und Namen (kein Vorgangstext).

## 4. Abnahme (Linux)
| Was | Ergebnis |
|---|---|
| `test_arbeitsplatz` (19: reine Teile, Modul-Dateien, kaputte Datei, Wissensbasis, Gespräch, Modellwerkzeuge) | grün |
| `test_uix_flows.Build24` (Cockpit: Projekt anlegen, Modell-Abschnitt mit Fehlerpfad, Teststrecke ohne Modell gesperrt, Arbeitsplatz-Antwort → Knopf öffnet; Paperclip: Neues Projekt, „Wo finde ich den Posteingang?“ → Knopf öffnet „Posteingang“) | grün |
| `test_uix_contract` (+ Baum öffnet Werkstatt-Abschnitte, Werkstatt/Projekt rein), `test_uix_shell_paperclip`, `test_gateway`, `test_evolution_targets` | grün |
| `uix_check` cockpit, paperclip, minimal, gateway-studio 30/30; guppi-xp 3/3; start 6/6 | grün |
| Volle Suite | 2.156 Tests, 1 Fehler = bekannter Umgebungsfehler `library_not_built`, 49 übersprungen (441 s). Ein echter Fehler im Modellpfad (`ArbeitsplatzWissen.beschreibung` mit falschem Dekorator) wurde von vier Tests gefunden und behoben; diese vier Module danach erneut grün (104 Tests). |

Nicht gelaufen: Windows; der Dateidialog (`model/pick`) auf dem PC; Teststrecke mit geladenem Modell; echtes Modell mit den neuen Werkzeugen.

## 5. Für den Nutzer
- Cockpit: ＋ Neu → Projekt; Baum → Modell hinzufügen / Teststrecke. Paperclip: Dateien → „Neues Projekt“ (Verb oben), Werkstatt (Modelle).
- Im Gespräch: „Wo finde ich …?“, „Wie lege ich … an?“, „Was ist die Werkbank?“, „Was muss ich als Nächstes machen?“ – Antwort ohne Modell, Quelle `arbeitsplatz-wissen`.
- Wissen ergänzen: `arbeitsplatz.yaml` im Ordner der Shell oder des Werkzeugs (Schema im Kopf der Datei); beim nächsten Start ist es da.
