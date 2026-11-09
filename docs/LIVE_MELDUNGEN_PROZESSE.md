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
