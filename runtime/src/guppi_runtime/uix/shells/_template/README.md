# Vorlage: eine Shell

Eine Shell besitzt den Bildschirm und gibt den Werkzeugen Container. Sie kennt kein Werkzeug beim Namen.

## In vier Schritten
1. `cp -r uix/shells/_template uix/shells/<id>`.
2. `shell.yaml` ausfüllen (`id` = Ordnername, `provides` = welche Slots es wirklich gibt).
3. `shell.js`: `start(ctx)` baut die Zonen, `ctx.tools.for(type)` sagt, wer ein Objekt zeichnet, `ctx.makeContext(...)` gibt
   dem Werkzeug seinen Kontext. Das Gespräch (`talk`) ist ein Werkzeug – ohne es gibt es kein Eingabefeld.
4. In `local_config/uix.yaml` die Shell aktiv setzen (`uix: {shell: <id>}`) und `python benchmarks/uix_check.py` laufen lassen.

## Woran sich eine Shell halten muss
- Sie greift nie in ein Werkzeug hinein; sie gibt ihm `el` und `ctx`, und ruft `unmount`, wenn es weg soll.
- Entscheidungen haben einen Ort: eine Antwort im Gespräch und eine am Knopf müssen denselben Weg nehmen.
- Layout gehört der Shell (localStorage); Daten gehören der Runtime.
