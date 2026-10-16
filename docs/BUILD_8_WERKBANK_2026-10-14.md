# Build 8 – Objektmodell, Verben, Live und die Werkbank-Werkzeuge (14.10.2026)

Gebaut nach `SHELL_WERKZEUG_VERTRAG_v1.md` §9 Punkt 2 und §10.1/§10.2, auf Build 7. **Am Kern ändert sich nichts**, alle alten
Routen bleiben, die Oberfläche von Build 6 bleibt unter `/retro`.

## 1. Was neu ist

### Desk: ein Objektmodell, Verben, Live-Zeilen

| Datei | Zweck |
|---|---|
| `desk/objects.py` | **Eine Form für alles**: `{type, id, title, state, summary, actions, links}`. Ein Werkzeug fragt nicht mehr zehn Spezialrouten, sondern `POST /api/objects {type, id}` – ohne `id` die Liste des Typs. |
| `desk/actions.py` | **Verben statt Routen**: `POST /api/actions {type, id, verb}`. Jedes Verb kennt sein Gate (`needs_gate`), seinen Zustand (`when`) und seinen Warnsatz (`confirm`). Ausgeführt wird nur, was im *jetzigen* Zustand angeboten wird – der Zustand wird dafür frisch gelesen. |
| `desk/live.py` | **Die Zeilen einer Aufgabe** aus Schritt-Journal, Übernahme und Audit, fortlaufend nummeriert und nach Zeit sortiert. |

Neue Routen daneben, alle nur lesend außer `/api/actions`: `/api/objects`, `/api/live`, `/api/candidate/diff`,
`/api/candidate/report`, `/api/cost`.

**Was `live.py` ehrlich ist:** die Runtime schreibt kein laufendes Protokoll je Aufgabe. Was sie schreibt, ist belastbarer – das
Schritt-Journal mit Beginn, Ende und Versuchen, die Artefakte, die Übernahme und die Audit-Kette. Daraus entstehen die Zeilen.
Aus dem Audit wird nur, was beim Zusehen zählt (Freigaben, Blockaden, Fehlschläge); „message sent“ und jeder Zustandswechsel
stehen vollständig im Logbuch und wären hier Rauschen. **Es steht keine Zeile da, deren Inhalt nicht in der Mission oder im
Audit steht.**

### Vier Werkzeuge an der Werkbank

- **`candidate`** – das Werkstück: der Diff Zeile für Zeile. Gerechnet wird er im Browser mit einer LCS-Tabelle über die Zeilen,
  lange unveränderte Strecken werden gefaltet. `diff2html` stand im Konzept als Vorschlag; eine Abhängigkeit dafür ist nicht nötig.
- **`tests`** – was nachgewiesen ist: Teststand, statische Prüfungen, geplante Läufe, Blocker der isolierten Ausführung. Quelle ist
  `candidate-report.json`. **Ein nicht gelaufener Test wird nie als grün dargestellt.**
- **`live`** – die Zeilen, einmal geholt und danach vom Strom nachgeschickt (`live.line` mit `since`). Kein Polling.
- **`costs`** – das Münzloch: Token und Aufrufe dieser Aufgabe. Die Zahlen kommen vom Kontext-Manager, der jeden Modellaufruf
  unter der Missions-ID verbucht; **gemeldet und geschätzt werden nie vermischt** (`quellen`).

### Werkbank in zwei Spalten

Das Manifest kennt jetzt `slot: inhalt | nachweis`. Das Cockpit stellt das Werkstück nach links und die Nachweise nach rechts
(COCKPIT_MODUL_v1 §1); eine Shell ohne zwei Spalten darf den Hinweis ignorieren – deshalb ist er ein Wort im Manifest und keine
Vorschrift im Vertrag. Unter 1100 px stehen die Spalten untereinander.

## 2. Drei Dinge, die die Abnahme selbst gefunden hat

1. **Die Werkbank-Zeile fragte zu früh.** Ein Werkzeug weiß erst nach dem ersten Zeichnen, welche Handlungen sein Objekt anbietet;
   die Zeile wurde davor gebaut und blieb leer. `mountTool` liefert jetzt ein `ready`-Versprechen, das Dock zeichnet die Verben
   danach (und erneut bei `task.changed`).
2. **Nachweise standen auch an einer Liste.** „Alle Aufgaben“ ist kein Werkstück; Live und Kosten zeigten dort „Diese Aufgabe gibt
   es nicht mehr“. Ein Objekt trägt jetzt `collection: true`, wenn es eine Sammlung ist, und bekommt keine Nachweise.
3. **Viele Reiter machten die Seite breiter als den Bildschirm.** Mit einem Dutzend offener Reiter wuchs die Werkbank über das
   Fenster hinaus, die Instrumentenleiste war rechts abgeschnitten. Jetzt scrollt die Reiterleiste in sich (`minmax(0,1fr)` in
   beiden Rastern), „＋ Neu“ und „Teilen“ bleiben stehen; `uix_check` misst den Überhang seither als eigene Prüfung `breite`.

Dazu aufgeräumt: das „Neu lesen“ jedes Werkzeugs ist aus der Werkbank-Zeile verschwunden. Nachlesen ist keine Handlung am Objekt,
und der Strom meldet jede Änderung von selbst (Cockpit-Regel 3). Ebenso bekam jede Phase, die die Runtime kennt, ein deutsches
Wort – vorher stand „candidate_review“ im Satz des Captains; ein Test hält das jetzt fest.

## 3. Was die Runtime strenger macht als gedacht

**Übernehmen geht nicht ohne Tests.** Die Vorschau lehnt einen Kandidaten ohne gebundene Testläufe ab
(`bound_test_commands_required`). Statt den Captain in diese Fehlermeldung laufen zu lassen, liest das Objektmodell den Bericht und
setzt `qualified`; das Verb *Übernehmen* wird erst dann angeboten, und der Satz unter dem Diff sagt vorher, woran es liegt.
Der Weg selbst ist unverändert: Vorschau → Gate → Ausführung gegen genau diese Vorschau, mit den Hashes jeder Datei.

## 4. Abnahme auf diesem Stand

| Prüfung | Ergebnis |
|---|---|
| `benchmarks/uix_check.py` | **`result ok`, 24 von 24** – jetzt mit einem echten Kandidaten im Prüfprojekt; je Werkzeug: eigener Container gefüllt, richtige Spalte, Handlungen, `unmount`, jeder Aufruf nennt seinen Absender |
| `tests/test_desk_objects.py` | 19 Tests – eine Form für alle, Verben nur im passenden Zustand, kein Verb ohne Angebot, echter Kandidat mit Diff und Bericht |
| `tests/test_desk_live.py` | 10 Tests – Reihenfolge, Nummerierung, Audit-Filter, Gate-Zeile, Fehlschlag, Übernahme und Rücknahme, `since` |
| `tests/test_uix_contract.py` | 29 Tests (4 neu: Diff-Rechnung, Testurteil, Münzen, Slots im Manifest) |
| `tests/test_desk_gateway/events/decisions.py` | unverändert grün |

## 5. Was bewusst offen bleibt

- **Modus und vier Grenzen**: ~~Build 9~~ – gebaut, siehe `BUILD_9_GRENZEN_2026-10-14.md`. Das Instrument sagt jetzt, was gilt.
- **Vorhaben** (`intent`): ~~offen~~ – mit Build 9 ein eigenes Objekt mit eigenem Werkzeug.
- **Routinen** sind im Baum angekündigt, nicht gebaut.
- Eine **Kostengrenze** gibt es erst, wenn sie gemessen ist – zwei Wochen Guppy-Meter auf dem PC (Captain-Entscheidung).
- `live.py` liest die Mission bei jedem Blick neu. Bei vielen gleichzeitigen Aufgaben ist das messbar; dann bekommt der Poller
  einen Zwischenspeicher. Heute ist es ein Lesevorgang alle drei Sekunden je laufender Aufgabe.
