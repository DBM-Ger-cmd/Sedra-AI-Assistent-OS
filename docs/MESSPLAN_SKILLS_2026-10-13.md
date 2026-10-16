# Messplan: Skill-Bibliothek (`--skills`)

Stand 13.10.2026. Frage: Helfen `skill_search` und `skill_read` dem lokalen Coder, oder kosten sie nur Fenster und Zeit?

## Vorbereitung (einmal)
```
cd runtime
.venv\Scripts\python.exe -c "from guppi_runtime.skill_library import build_library; print(build_library(r'<quelle>', 'runtime_data/skill_library', source_name='claude-skills (A. Rezvani)', license_name='MIT'))"
```
`<quelle>` ist der entpackte Ordner `claude-skills-main` (nur Daten, nichts daraus wird ausgeführt). Stand heute: 368 nutzbare Skills.

## Aufbau
- Spec `bench_std` (Referenzaufgabe des Projekts), danach `am008_meter` als Gegenprobe (Referenz 4740 s, 22,6 tok/s).
- Rezept und Einstellungen wie im Standard: `--coder coder.local_primary --context 32768 --tidy --reasoning off --coder-ext all` plus die Server-Schalter aus `docs/ENTWICKLUNG.md`.
- A = ohne `--skills`, B = mit `--skills runtime_data/skill_library`. Je Spec 3 Läufe pro Arm, abwechselnd (A B A B A B), damit Drift der GPU nicht einen Arm trifft.

## Vorher (Captain-Regeln)
GPU-Lease holen, Canary laufen lassen (Overclock-Befund vom 11.10.), VRAM bis 11,5 GB nutzen und messen, nur eigene PIDs beenden.

## Gemessen
Aus `summary.json` und dem Journal der Agentenläufe: bestandene Stufen, Nacharbeiten, Gesamtzeit, Tokens, größter Prompt (Fensterfüllung), Anzahl `skill_search`/`skill_read` je Lauf, Folgefehler nach `skill_read`.

## Urteil
- Behalten, wenn B mindestens gleich viele Stufen besteht und die Zeit um höchstens 10 % wächst.
- Ändern (kürzere Seiten, nur Beschreibung statt Text), wenn der größte Prompt in B klar über A liegt.
- Ablehnen, wenn B mehr Nacharbeiten braucht oder Skill-Text in den Code kopiert wird.
Die Aufgaben der Specs sind in sich geschlossen; Skills helfen dort vermutlich selten. Bleibt B gleich, ist das ein Ergebnis (Schalter bleibt aus), kein Fehler.
