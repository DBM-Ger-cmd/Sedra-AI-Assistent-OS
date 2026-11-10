---
name: sedra-bau-starten
description: Einen Bau durch SEDRAs lokale Modelle vorbereiten, starten, überwachen und auswerten (devvm_build.py, bau_schleife.py, Factory-Bau, Stufen S1 bis S4, Kandidaten, versteckte Tests). Nutzen, sobald ein Bau gestartet, fortgesetzt oder wiederholt werden soll, wenn ein Bau gescheitert ist ("hidden FAILED", "BAU_ENDE", "SERVER CRASH") oder der Captain fragt, ob ein Bau bestanden hat - auch dann, wenn nur von "Factory", "Kandidat" oder "nochmal bauen" die Rede ist.
---

# Bau starten und auswerten

Ein Bau belegt die GPU für Minuten bis Stunden. Die teuersten Fehler waren bisher keine Modellfehler: fehlende Vorgaben im Arbeitsbereich, ein ungültiger Stempel, ein abgestürzter Modellserver und vier Wiederholungen ohne Ursachenanalyse. Deshalb steht die Prüfung vor dem Start und das Lesen vor der Wiederholung.

Alle Befehle laufen im Ordner `runtime` mit `.venv\Scripts\python.exe`. Die ausführliche Fassung steht in `docs/SO_WIRD_GEBAUT.md` und `docs/ENTWICKLUNG.md`.

## Vor dem Start

1. **Lohnt sich der Bau?** Sind Spec, Tests und Referenz zusammen größer als der Code, schreibt Claude das Teil direkt (Regel V4).
2. **Projektordner.** Immer `<sedra>/workspace/SEDRA_OS`. Nicht `<sedra>` selbst, und kein Testprojekt an anderer Stelle: dort fehlt der Sandbox-Unterbau, die microVM scheitert mit `VM run failed`.
3. **Eingaben.** Alles, was das Modell braucht, liegt im Arbeitsbereich: Schemata, Regelblätter, Referenzdateien, Saat (`SEED` in der Spec). Fehlt etwas, erfindet das Modell Strukturen. So ist der Factory-Bau v4 und v5 gescheitert.
4. **Stempel.** `benchmarks/spec_check.py <name> --vm --project <projekt>`. Nach jeder Änderung an Spec, Referenz oder Saat und oft auch nach einem Commit ist der Stempel ungültig (`spec_changed_since_check`). Dann neu prüfen.
5. **GPU und Prozesse.** Skill `sedra-schnellpruefung`. Der Bau verlangt eine ruhige GPU (höchstens 3 GiB belegt) und beendet beim Start alle llama-server von SEDRA, auch den Router. Die Karte hat 12 GB, ein zweiter Modellslot passt nicht neben einen Bau.
6. **Freigabe.** Das Ja des Captains für den Lauf und für das Beenden des Routers, im Chat dieser Sitzung.

## Starten

Einzelner Bau:

```
.venv\Scripts\python.exe benchmarks/devvm_build.py <projekt> --spec <name> --profile standard --pidfile <datei>
```

Bau-Schleife (Stufe für Stufe, mehrere Versuche, setzt nach Abbruch fort):

```
.venv\Scripts\python.exe benchmarks/bau_schleife.py --projekt <projekt> start "<Auftrag>" [--spec <name>] [--rezept <id>] [--kontext <n>] [--neu]
```

- Im Hintergrund starten und auf das Ende warten, nicht abfragen. `devvm_build.py` endet mit der Zeile `# run ended`.
- Eine Überwachung mit dem Monitor-Werkzeug endet nach 30 Minuten von selbst. Läuft der Bau noch, neu ansetzen.
- Die Schleife erlaubt nur einen Lauf gleichzeitig (Sperrdatei `runtime_data/bau_schleife.lock`). `--neu` verwirft den gespeicherten Stand, sonst wird eine bestandene Stufe nicht noch einmal gebaut.
- `devvm_build.py` und die Schleife starten ihren eigenen Modellserver und nehmen `n_cpu_moe` fest aus dem Server-Block des Rezepts. Die dynamische Auswahl greift hier nicht.
- Optionen wie `--plan-steps`, `--fresh-rework`, `--checker` gehen nur mit `--experimental`.
- Stoppen nur über die eigene PID aus der PID-Datei, nie über ein Namensmuster.

## Wo das Ergebnis steht

Alles unter `<projekt>/runtime_data/`:

| Datei oder Ordner | Inhalt |
|---|---|
| `bau_schleife_status.log` | Verlauf der Schleife, Eskalationen |
| `bau_schleife_stand.json` | Welche Stufen bestanden sind |
| `bau_schleife_<Stufe>_<Modell>_<Zeit>.log` | Log eines Versuchs |
| `devvm_candidates/<spec>/attempt_…/` | Der Kandidat mit der Testausgabe |
| `spec_stamps/<spec>.json` | Der Stempel |

Bestanden heißt: Zeile `stage <Stufe>: hidden PASSED` für jede Stufe. Bei der Standard-Spec der Factory kommt der Produktbericht dazu. Ein Bau gilt erst dann als bestanden, nicht nach einzelnen Stufen.

## Wenn eine Stufe scheitert

Die Baulogs nennen den gescheiterten Test nicht. In dieser Reihenfolge vorgehen:

1. **Infrastruktur oder Kandidat?** Steht `SERVER CRASH`, `ConnectionResetError`, `llama_server_not_found` oder `VM run failed` im Log, war es keine Modellprüfung. Erst den Server stabilisieren.
2. **Testausgabe lesen.** Im Kandidatenordner, oder `benchmarks/bau_schleife.py --projekt <projekt> bericht <kandidatenordner> [<stufe>]`.
3. **Liegt der Fehler in der Spec?** `benchmarks/spec_check.py <name> --tree <kandidat> --host-ok` zeigt die erste falsche Aussage je Stufe. Ein Stufentest, der eine Regel einer späteren Stufe braucht, ist falsch, nicht das Modell.
4. **Dem Captain melden:** Ursache mit Beleg, dazu ein Vorschlag (Eingabe ergänzen, Spec ändern, anderes Rezept, kleineres Fenster). Erst nach seinem Ja wiederholen.

Nach einer gescheiterten Stufe nicht weiterbauen. Das kostet nur GPU-Zeit.

## Nach dem Bau

- Die BAU-Zeile im Logbuch schreibt der Bau selbst. Nicht von Hand doppelt eintragen.
- Den Kandidaten Zeile für Zeile lesen und `benchmarks/REVIEW_VORLAGE.md` ausfüllen. Mängel mit Datei, Zeile und genauer Ersetzung.
- Übernommen wird nichts ohne Gate G4 des Captains. Danach gelten `sedra-git-uebernahme` und `sedra-register-dashboard`.
- Am Ende mit `nvidia-smi` prüfen, ob ein llama-server übrig geblieben ist. Beenden nur mit Ja.
