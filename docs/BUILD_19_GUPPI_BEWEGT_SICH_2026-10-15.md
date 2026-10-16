# Build 19b: GUPPI bewegt sich in der Oberfläche, und die Minimal-Shell gehört dem Captain (15.10.2026)

> Parallel zu Build 19 (KI GateWay) in einer eigenen Sitzung entstanden; beide sind in **Build 20** zusammengeführt (CHANGELOG).

**Captain, 10:09 (nach dem PC-Test mit Build 18):** *„GUPPI sollte sich in seiner Modulumgebung frei bewegen können, das heißt
Fenster öffnen nach Freigabe und auch Befehle ausführen können.“* – *„Die Minimal-Shell muss überarbeitet werden: ich sehe nicht,
wie ich wieder auf die Haupt-Shell zurückkomme, die Icons sollten angepasst werden, und man sollte selber unten weitere Aufgaben
und Icons dazu anlegen können.“*

## 1. Der Befund aus dem Gespräch

| Gesagt | Was passierte | Warum |
|---|---|---|
| „ja“ (auf „Eine Entscheidung wartet: … Kontext 32768 → 65536“) | GUPPI: „Verstehe. Wie kann ich dir helfen?“ | Das Gespräch merkte sich die Ankündigung in einer Variablen; war sie weg (ein `decision.answered` aus dem Strom), ging „ja“ ans Modell. |
| „kannst du mir ein Fenster für Maschinenraum öffnen“ | „Ich kann keine neuen Fenster öffnen.“ | Die Ortskunde nahm nur Sätze bis vier Wörter ohne Fragewort; das Modell hatte kein Werkzeug dafür, und der Systemsatz sagte ihm: *„Du kannst in diesem Chat nichts ausführen.“* |
| Minimal: zurück zur Übersicht? | kein Weg | Nur das Werkzeug „Module“ wechselte die Shell. |
| Minimal: Ablage | nur Text, feste sieben Felder | – |

## 2. GUPPI bewegt sich – und tut nichts ohne den Captain

Die Linie bleibt die von Build 8 (*„dieselbe Handlung läuft aus Gespräch, Werkzeug und Palette denselben Weg“*): **das Modell
schlägt vor, der Captain klickt, und der Klick geht über `POST /api/actions` mit denselben Gates wie jeder Werkzeugknopf.**

| | Was | Wo |
|---|---|---|
| Neue Modellwerkzeuge | `list_places`, `open_place`, `open_object`, `list_actions`, `propose_action`, `propose_intent`, `list_decisions` | `chat_tools.py` |
| Keines tut etwas | Jedes legt eine Oberflächen-Handlung in `ui_actions` der Antwort (`{kind: open \| verb \| intent, …}`), höchstens vier. Ein Verb wird nur angeboten, wenn das Objekt es **jetzt** anbietet (Zustand frisch gelesen). | `ChatTools._offer` |
| Knöpfe unter der Antwort | „Öffnen: Werkstatt“, „Laden: coder.llama_qwen35“, „Ausführen: … (mit Freigabe)“, „Als Vorhaben anlegen: …“. Warnsatz (`confirm`) wie im Werkzeug. Nach dem Klick sagt GUPPI, was geschah – „liegt zur Freigabe bei den Entscheidungen“, wenn ein Gate folgt. | `tools/talk` 1.1.0 |
| „Nach Freigabe“ | Ein Fenster öffnet sich **sofort**, wenn der Captain im selben Satz selbst ums Öffnen bat („öffne …“, „… öffnen“) – das ist die Freigabe. Sonst ein Knopf. | `places.wantsOpen` |
| Ortskunde | „kannst du mir ein Fenster für Maschinenraum öffnen“, „geh zum Logbuch“ → Navigation **ohne Modell**; „zeig mir die Modelle von gestern“ bleibt eine Frage. | `ui/places.js` |
| Systemsatz | Nennt die Werkzeuge; „Sag nie ‚das kann ich nicht‘, wenn eines passt“. Wörter des Öffnens/Tuns erzwingen im ersten Zug einen Werkzeugaufruf (wie schon die Zustandswörter). | `uix_server.CHAT_SYSTEM`, `CHAT_MOVE_WORDS` |
| „ja“ / „nein“ | liest `GET /api/decisions` **frisch**: die angekündigte, sonst die einzige; warten mehrere, fragt GUPPI nach. Änderungsanträge werden „freigegeben und angewendet“. **„ok“, „los“, „mach“ sind keine Freigabe mehr** – das ist oft nur ein Nicken. | `talk.pickDecision`, `wayFor` |
| Audit | `UIX_CHAT_TOOLS` zählt `offered` (Arten, kein Text); der Klick selbst ist `UIX_ACTION` / `INTENT_CREATED` wie bisher. | |

„Befehle ausführen“ heißt damit: die **Verben** der Objekte (Modell laden/entladen/testen, Aufgabe ausführen, Kandidat testen/
übernehmen, Vorhaben → Aufgabe, Grenzen bestätigen) und Vorhaben anlegen. Ein Shell-Befehl auf dem Rechner ist bewusst **kein**
Verb – das bleibt der Weg über Aufgabe, Sandbox und Gate.

## 3. Minimal: Rückweg, Bildzeichen, eigene Ablage

| | Was |
|---|---|
| **Haus-Knopf** ganz links | zur Übersicht der Oberflächen – **nur für diesen Lauf** (`POST /api/uix/shell {shell: start, nur_jetzt: true}` setzt den Override aus Build 18, schreibt nichts, Audit `UIX_SHELL_VISIT`). Die Wahl in `uix.yaml` bleibt; wer in der Übersicht eine Oberfläche nimmt, wählt ausdrücklich. |
| Menü **„SEDRA“** | „Übersicht der Oberflächen“ und „Wechseln zu Cockpit / GUPPI XP / Paperclip / …“ (aus `/api/uix/modules`). |
| **Bildzeichen** | 24 eigene Linienzeichen (`icons.js`), `currentColor`, folgen Klar/Nacht; jeder Ort und jeder Objekttyp hat eins. Kein Bild, keine Bibliothek, kein HTML als Text. |
| **„＋ Neu“** in der Ablage | drei Arten: **Ort** (Maschinenraum, Werkstatt, …), **Fenster vorn** (eine bestimmte Aufgabe, ein Modell), **Auftrag an GUPPI** (ein Satz, der beim Klick ins Gespräch geht – „Lade das Coder-Modell“, „öffne die Hardware“). Name und Bildzeichen wählbar. |
| Rechtsklick auf ein Feld | Nach links · Nach rechts · Ändern … · Entfernen · Ablage zurücksetzen |
| Menü „Fenster“ | „An die Ablage heften“ (das Fenster vorn), „Feld in der Ablage anlegen …“ |
| Gemerkt | in `local_config/uix.yaml` unter `uix.shelf.minimal` über `GET/POST /api/uix/shelf` – **nicht im Browser**: SEDRA startet jedes Mal auf einem neuen Port, und der Browser-Speicher gehört dem Port. Geprüft im Server (Art, Name ≤ 24, Zeichen-id, Ort-id, Objekttyp, Satz ≤ 400, höchstens 24 Felder). Audit `UIX_SHELF_SAVED`, kein Gate (eigene Form, Captain 14.10.). |
| Vorgabe | die sieben Felder von vorher plus „Maschine“. |

Ein Auftrag-Feld führt nichts aus: der Satz geht ins Gespräch und dort den gewohnten Weg (Ortskunde, „ja“, Modell → Knöpfe).

## 4. Nebenbei gefunden und behoben

- **`save_config` schrieb den Override fest** (seit Build 18): wer unter `START_SEDRA cockpit` ein Werkzeug abschaltete, hatte
  danach Cockpit als Wahl in `uix.yaml`. Jetzt wird die Wahl aus der Datei genommen. Test.
- `save_config` hätte die neue Ablage beim nächsten Shell-Wechsel gelöscht – sie wird mitgeschrieben. Test.
- Die Ankündigung im Gespräch sagte „an der Werkbank“ – Minimal und Paperclip haben keine. Jetzt: „auf der Karte, oder hier
  mit ‚ja‘ oder ‚nein‘“.

## 5. Abnahme

`tests/test_uix_guppi_moves.py` (15): Orte in Python und JS gleich, Öffnen ist ein Knopf, Verb nur wenn jetzt angeboten, Vorhaben
nur vorgeschlagen, höchstens vier Knöpfe, `chat_reply` trägt `ui_actions` und das Audit zählt sie, Ortskunde, „ja“/„ok“, Manifest
des Gesprächs, Ablage gespeichert/geprüft/überlebt Shell-Wechsel, Override nicht festgeschrieben, Übersicht als Besuch, reine Teile
von Editor und Zeichen. `tests/test_uix_flows.py` neuer Bedienweg in Minimal (Satz öffnet den Maschinenraum, Knopf unter GUPPIs
Antwort öffnet das Logbuch, „＋ Neu“ → Auftrag mit Zeichen → steht in `uix.yaml` → Klick öffnet die Hardware → nach Neuladen noch
da → Haus → Übersicht, `uix.yaml` unverändert). Bildschirmfotos: `docs/shots/build19/`.

## 6. Offen

- Die **Fensterlage** von Minimal liegt weiter im Browser (`sedra.minimal.windows`) und ist damit nach jedem `START_SEDRA` weg
  (neuer Port). Gehört wie die Ablage nach `uix.yaml` – mit Schreibbremse, weil Ziehen viele Änderungen macht.
- Haus-Knopf und Menü „SEDRA“ gibt es nur in Minimal; Cockpit und Paperclip kommen nur über „Module“ zurück. Am besten als
  Vertragsteil (`ui/`), damit auch eine Shell aus Vorgabe ihn hat.
- Ein Auftrag-Feld könnte statt eines Satzes direkt ein Verb tragen (ein Klick = „Laden: coder…“); heute geht es den Umweg über
  das Gespräch, was ohne geladenes Modell nur für Ortssätze trägt.
