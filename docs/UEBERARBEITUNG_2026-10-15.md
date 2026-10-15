# Überarbeitung 15.10.2026 – das Werkzeug „Module“ und die drei Shells

Auftrag des Captains: *„überarbeite die Arbeit nochmal mit an Modul und den 3 Shells, werte den visuellen Stil auf und prüfe
die Bedienung und Logik dahinter.“* Drei Durchgänge: erst die Logik, dann die Bedienung mit echten Klicks, dann der Stil.
Jeder Fund steht hier mit dem, was daraus geworden ist.

## 1. Logik – was beim Lesen und Nachstellen auffiel

| Nr. | Fund | Ernst | Geschlossen durch |
|---|---|---|---|
| **L1** | **Im Cockpit war `ctx.shell` an der Werkbank tot – seit Build 7.** `dock.js` gab jedem Werkzeug im Reiter `shell.api` (die api-*Funktion*) statt `shell.shellApi` mit. `ctx.shell.open()`, `notify()`, `decide()` waren `undefined`: ein neues Vorhaben öffnete keinen Reiter, „Grenzen bestätigen“ sprang nicht zur Entscheidung, Fehler verschwanden im `catch` des Knopfs. Kein Test sah es, weil nur das Gespräch (richtig gemountet) navigierte. | hoch | `dock.js` repariert; **der Loader prüft jetzt, was eine Shell hergibt** (`checkShellApi`: open, notify, decide) und meldet es als Problem, das `uix_check` beim Laden sieht. Test im Vertrag und ein Klick-Test, der ein Vorhaben anlegt und den Reiter erwartet. |
| **L2** | **Das Gespräch ließ sich abschalten.** Im Werkzeug Module hatte jedes Werkzeug einen Schalter – auch `talk`. Ein Klick, ein Neuladen, und die Shell hätte kein Eingabefeld mehr. Dasselbe für `modules` selbst: der Weg zurück zur Liste wäre nur noch die Datei gewesen. | hoch | `tool_enabled` weist beide ab (`tool_is_required`); die Liste trägt `required`, das Werkzeug zeigt dort einen Satz statt eines Schalters. Test. |
| **L3** | **Nach dem Shell-Wechsel wusste der Captain nicht weiter.** „Beim nächsten Öffnen der Seite“ – aber welcher Knopf? | mittel | `shellApi.reload()` in allen drei Shells und der Vorlage (Neuladen gehört der Shell, nicht dem Werkzeug); das Werkzeug zeigt oben einen Hinweis mit „Jetzt neu laden“, auch nach an/aus. |
| **L4** | **Die eigene Handlung zählte erst mit dem nächsten Ereignis.** In D stand der Badge am Posteingang nach „Bestätigen“ noch auf 0, bis der Strom kam; in E die Karte rechts oben ebenso. | niedrig | Beide Shells frischen beim Öffnen eines Objekts sofort auf. |
| **L5** | Das Instrument `gauge-state` schreibt seinen Zustand als Klasse an den Container der Shell (`ok/warn/bad`) – gewollt (so färbt jede Shell den Wert), aber in D stand dafür keine Regel. | niedrig | `.pc-kpi.ok/.warn/.bad` ergänzt. |

## 2. Bedienung – mit echten Klicks durchgespielt (`tests/test_uix_flows.py`)

`uix_check` öffnet Objekte über den Bus; das prüft die Werkzeuge, nicht die Bedienung. Jetzt gibt es dazu vier Wege, die
geklickt, getippt und gedrückt werden, wie der Captain es tut:

- **Minimal**: Ablage → Fenster; Menü „Fenster → Alle schließen“ lässt nur das Gespräch stehen (neu); Strg+K, „logbuch“, Enter → Fenster.
- **Paperclip**: Navigation → Seite; „Zurück“ → Dashboard; ein Auftrag im Suchfeld öffnet die Schublade und wird **im Gespräch**
  gesendet; Esc schließt sie. Dann der ganze Entscheidungsweg: „Modus und Grenzen → Bestätigen“ → Badge „1“ sofort → Dashboard →
  Posteingang-Karte → „Freigeben und anwenden“ → Badge weg, Kachel sagt „Sandbox“.
- **Cockpit**: Baum → Module → „Diese Shell nehmen“ → Hinweis mit Knopf → „Jetzt neu laden“ → die andere Shell steht.
- **Cockpit, der Fehler L1 als Test**: ein Werkzeug im Reiter hat eine echte Shell-API; ein neues Vorhaben öffnet als Reiter;
  der Loader meldet nichts.

Dazu der Bedienfund in E: das Menü „Fenster“ hatte keinen Weg, aufzuräumen – ein Schreibtisch braucht einen.

## 3. Stil – was aufgewertet wurde

Die Richtung bleibt die des Manifests: hell, dicht, ehrlich, deutsch, der Guppy als einziges Maskottchen. Aufgewertet wurde,
was die drei Shells **gemeinsam** haben sollen, nicht ihre Eigenart:

| Was | Vorher | Jetzt |
|---|---|---|
| **Schriftstufen** | jede Shell eigene Pixel (9.5, 11, 11.5, 12, 12.5, 13, 14, 15, 20 px) | vier Stufen als Token (`--size-xs/-small/–/-l`, dazu `-head`, `-xl`); E und D benutzen nur noch Stufen. Eine Shell wählt eine Stufe, sie erfindet keine 11,5 px. |
| **Fokus** | sichtbar nur auf `.s-btn` und Eingaben; Zeilen der Shells (`role=button`) ohne Ring | ein Ring für alles, was wie ein Knopf wirkt – `button`, `[role=button]`, Eingaben – in allen Shells gleich |
| **Schleier** | `rgba(…)` von Hand in Cockpit und D | drei Token `--veil-*`; keine Shell schreibt mehr eine eigene Transparenz |
| **Nacht-Thema in D** | Navigationstext und aktive Zeile fast unsichtbar (`--panel` als „weiß“ missbraucht) | aus den `--live-*`-Token, die in beiden Themen gleich bleiben |
| **Werkzeug Module** | 23 Werkzeuge in einer Liste | nach Art gruppiert (Werkzeuge · Instrumente · Gespräch), alphabetisch; Pflicht-Werkzeuge ohne Schalter; der Hinweis zum Neuladen oben mit Knopf |
| **D, Kopfzeile** | zwei Knöpfe „Mit GUPPI sprechen“ | einer, rechts unten, wie im Entwurf |

Bewusst **nicht** verändert: die Eigenart der drei Formen (Reiter und Spalten · freie Fenster und Ablage · Firma und
Schublade), die Farbwelt, der Guppy. Die Ablage in E bleibt still – Kacheln mit Wort, ohne Dekor; ein buntes Dock hätte
die Gleichheit der Werkzeuge über die drei Formen hinweg verdeckt.

Auf dem PC wird außerdem die Grundschrift greifen, die `--font` schon nennt („Segoe UI“); in diesem Container fällt sie auf
DejaVu zurück – die Bilder hier zeigen also die Form, nicht die Schrift.

## 4. Abnahme

| Prüfung | Ergebnis |
|---|---|
| `uix_check --shell cockpit / minimal / paperclip` | 27/27 · 27/27 · 27/27 |
| `test_uix_flows` (4 Klick-Wege) | grün |
| `test_desk_modules` (10), `test_uix_contract` (30), `test_uix_shell_minimal` (7), `test_uix_shell_paperclip` (8) | grün |
| volle Suite | siehe Changelog Build 13 |

## 5. Was offen bleibt

- `test_uix_flows` braucht Chromium und dauert eine halbe Minute; auf dem PC läuft er mit, im Container ohne Browser wird er
  übersprungen.
- Die Schriftstufen gelten für E und D vollständig; das Cockpit hat seine Pixelwerte noch – es war vor den Token da und läuft
  27/27. Nachziehen, wenn es ohnehin angefasst wird.
- Ob die Ablage in E Zeichen bekommt, entscheidet der Captain am Bildschirm, nicht ich am Bild.
