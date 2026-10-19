# Vorlage: ein Werkzeug

Kopieren, Ordner und `id` umbenennen, ausfüllen. Der Ordner `_template` wird nie geladen.

## In vier Schritten
1. `cp -r uix/tools/_template uix/tools/<id>` (auf dem PC: Ordner kopieren und umbenennen).
2. In `tool.yaml`: `id` (= Ordnername), `name`, `description`, `handles`, `slot`, `api`, `events`, `trust`.
3. In `tool.js`: `id` anpassen, `mount`/`unmount`/`actions` ausfüllen. Reine Funktionen nach oben – die prüft node.
4. `python benchmarks/uix_check.py --tool <id>` muss `result ok` sagen.

## Was die Tests erzwingen
- Nur `ctx.api()` und `ctx.bus`; kein eigenes `fetch`, kein `localStorage`, kein `EventSource`.
- Gezeichnet wird nur in `el`; `unmount` hinterlässt ihn leer.
- Stil nur unter `.t-<id>`; keine Farbe ohne Token.
- ≤ 400 Zeilen je Datei; eine `README.md` je Modul.

## Für SEDRA (Vertrag §7)
Eine Spec in `benchmarks/devvm_specs/tool_<id>.py` beschreibt Zielobjekt, Handlungen, Routen und Ereignisse; die reinen Teile
werden als Node-Tests geprüft, der Browser-Teil über `uix_check`. Ein so gebautes Werkzeug trägt `trust: GUPPI_BUILT` und geht
durch denselben Install-Gate wie ein fremdes Modul.
