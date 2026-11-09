# Live-Meldungen laufender Prozesse (Stand 09.11.2026)

Der Reiter **Live** in „n8n Workflows“ und im „Szenario Studio“ zeigt, was gerade läuft: eine Karte je Prozess mit Zustand, aktuellem Schritt, Text, Verlauf und dem Diagramm, in dem der Schritt leuchtet. Die Anzeige rät nichts. Sie liest nur, was der laufende Prozess selbst meldet.

## Wie ein Prozess meldet

Der Prozess ruft bei jedem Schrittwechsel `workflows/live.py` auf. Die Meldung ist eine kleine Datei `runtime_data/live/<prozess>.json` im Projekt und nur Anzeige, sie gibt kein Recht und startet nichts.

```python
from sedra_runtime.workflows import live
live.melde(projekt_root, 'vollautomatischer-bau', 'bauen', 'laeuft', text='Stufe S2, Versuch 3 von 6')
live.melde(projekt_root, 'vollautomatischer-bau', 'pruefung', 'wartet', text='Das Produkt wartet auf deine Prüfung')
live.melde(projekt_root, 'vollautomatischer-bau', None, 'fertig')          # Ende des Laufs
```

Aus jeder anderen Sprache oder einem Skript per Befehlszeile:

    python -m sedra_runtime.workflows.live melde --projekt <Projektordner> --prozess vollautomatischer-bau --schritt bauen --zustand laeuft --text "Stufe S2, Versuch 3 von 6"

- **`prozess`** ist die Kennung des Ablaufs in `runtime/config/selbstabbild.yaml`, **`schritt`** die Kennung des Schritts darin. Beispiele für `vollautomatischer-bau`: `auftrag`, `spec`, `bauen`, `stufe-ok`, `fehlerbericht`, `versuche`, `eskalation`, `naechste`, `letzte`, `produktpruefung`, `pruefung`.
- **Zustände:** `laeuft`, `wartet` (ein Mensch ist dran, der Schritt leuchtet gelb), `fehler` (rot), `fertig` (Ende des Laufs, `schritt` darf dann leer sein).
- **Text** höchstens 240 Zeichen, der Verlauf behält die letzten 200 Meldungen. Nach `fertig` beginnt die nächste Meldung einen neuen Lauf, sonst mit `--neu`.
- **Eingaben:** Kennungen nur `a-z`, `0-9`, `-`. Falsche Eingaben werfen `ValueError` (Befehlszeile: Code 2); es entsteht nie eine halbe Datei (atomar geschrieben).

## Was die Anzeige tut

- Besuchte Schritte sind **grün**, der aktuelle trägt den gemeldeten Zustand, ein Schritt, dessen letzte Meldung `fehler` war, bleibt **rot**.
- Eine Meldung im Zustand `laeuft` oder `wartet`, die seit **drei Minuten** nicht mehr kam, steht als **„keine Meldung“** (die Karte wird blasser, der Chip nennt die Zeit). So sieht man einen abgestürzten Prozess, statt einen laufenden vorzutäuschen.
- Ein Schritt, den das Diagramm nicht kennt, wird als „im Diagramm nicht bekannt“ gezeigt, nicht verschwiegen.
- Die Anzeige fragt alle 2 Sekunden (`POST /api/actions`, Verb `live` am Typ `workflow`), aber nur, solange der Reiter offen ist.

## Wer meldet heute

Noch niemand. Der Bau (`runtime/benchmarks/bau_schleife.py`) soll vor und nach jedem Schritt melden (`auftrag`, `spec`, `bauen` je Versuch, `stufe-ok`, `fehlerbericht`, `versuche`, `naechste`, `letzte`, `produktpruefung`, `pruefung`, `eskalation`). Das ist Sache der Sitzung, die den Bau entwickelt. Weitere Prozesse melden sich mit ihrer Ablauf-Kennung, sobald sie im Selbstabbild stehen.

## Prüfung

`runtime/tests/test_workflow_live.py` (Datei, Zustände, Veralten, Eingaben, Befehlszeile, Verb) und `runtime/tests/test_uix_workflow_live.py` (Browser: Leerzustand, Schritt leuchtet und folgt der Meldung, wartet, Fehler, „keine Meldung“, beide Apps, Abfrage nur bei offenem Reiter).

## Die Fabrikhalle (E1)

Über den Prozesskarten zeigt der Reiter Live, was die Harness tut und was auf den Captain wartet. Das Verb `fabrik` (workflows/fabrik.py, nur lesen) fasst zusammen:

- **Drei Kacheln:** Läufe, Aufgaben, Freigaben. Die Kachel mit wartenden Freigaben ist gelb und führt per Klick in den Posteingang. Gezählt wird alles, was im Posteingang auf den Captain wartet (Missionen, Anträge, Harness-Karten).
- **Läufe:** die laufenden mit Dauer, Fortschrittsbalken und letzter Zeile, darunter die letzten sechs beendeten (fertig, Fehler, gestoppt, verloren). Wer das Modell gerade hält, steht darüber.
- **Aktive Aufgaben** mit Zweck und Restzeit, und die drei neuesten wartenden Freigaben.
- Befehl, Pfade und Parameter der Läufe gehen nie an die Oberfläche. Es wird nichts gestartet, gestoppt oder freigegeben.
- Läufe und Aufgaben stehen in der Fabrikhalle auch ohne Meldungen. Die Karten mit dem leuchtenden Schritt erscheinen nur für Prozesse, die selbst melden.

## Der rote Knopf: Fabrik anhalten (Notaus)

Unter den Reitern der Workflow-Apps sitzt in jedem Reiter ein roter Knopf **■ STOPP**. Ein Klick hält die Fabrik sofort an, ohne Rückfrage und ohne Gate (Anhalten ist immer erlaubt). Reihenfolge:

1. **Haltemarke setzen** (`runtime_data/fabrik/angehalten.json`: `seit`, `grund`, `von`). Ab jetzt startet nichts Neues.
2. **Läufe der Harness stoppen**, alle gleichzeitig (Prozessbaum), **aktive Aufgaben zurücknehmen**, **laufende Antworten abbrechen**.
3. **Den Bau beenden** (`bau_schleife.py` läuft als eigener Prozess des Managers): die PID aus `runtime_data/bau_schleife.lock` zählt nur, wenn der Prozess dahinter wirklich `bau_schleife` in der Befehlszeile trägt. Eine tote oder weitergegebene PID trifft nie einen fremden Prozess.
4. **Prozesse im Live-Reiter**, die noch „läuft“ melden, stehen danach als „Fehler: Fabrik angehalten“ da.
5. Ein Eintrag `FABRIK_NOTAUS` im Audit-Log, ein Bericht im Fenster. Ein Fehler bei einem Teil hält die anderen nicht auf und steht im Bericht.

Solange die Marke steht, lehnt `Laeufe.starten` jeden Lauf mit `fabrik_angehalten` ab, und `manager.werkzeuge.bau_starten` startet keinen Bau. **Freigeben** ist die Entscheidung des Captains und fragt noch einmal nach („Wirklich freigeben?“).

### Wer sonst startet oder läuft, prüft selbst

Prozesse außerhalb der Harness (der Bau, Skripte) fragen vor jedem Schritt:

```python
from sedra_runtime.workflows import fabrik
if fabrik.angehalten(projekt_root):
    raise SystemExit('Die Fabrik ist angehalten.')
```

oder prüfen, ob `<projekt>/runtime_data/fabrik/angehalten.json` existiert. `bau_schleife.py` sollte das zwischen den Stufen und Versuchen tun (Sache der Bau-Sitzung); der Notaus beendet den Bau-Prozess ohnehin hart.

Prüfung: `runtime/tests/test_fabrik_notaus.py` (Marke, Sperre beim Start, Reihenfolge, Gleichzeitigkeit, Fehler, Bau-Prozess, Manager) und im Browser `test_uix_workflow_live.py` (echter Prozess wird beendet, Rückfrage beim Freigeben, Knopf in jedem Reiter und im Szenario Studio, schon angehaltener Zustand).
