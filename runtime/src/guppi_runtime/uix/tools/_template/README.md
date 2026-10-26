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

## Gedächtnis (Vertrag 1.1, SPEC_DOCK_OHNE_NEUAUFBAU_v1 §3, §10)
Eine Shell baut ein Werkzeug ab, wenn es nicht mehr vorn ist, und bei einem Shell-Wechsel lädt die Seite neu. Was danach wieder
da sein soll, legt das Werkzeug in eines der drei Gedächtnisse – je Werkzeug und Objekt, ohne eigenen Speicher:

| | übersteht | darf enthalten | im Manifest |
|---|---|---|---|
| `ctx.memo.get(name, vorgabe)` / `.set(name, wert)` | Abbau und Einhängen | alles | – |
| `ctx.sitzung.get/.set` | Neuladen, Shell-Wechsel | **nur** Zustand der Ansicht (Ansicht, Filter, IDs, Sortierung) | `gedaechtnis: sitzung` |
| `await ctx.ablage.get(name, vorgabe)` / `.set` | Neuladen, Shell-Wechsel, zweiter Reiter | auch Inhalt (Fragen, Treffer) – bleibt im Prozess der Runtime | `gedaechtnis: ablage` |

- Ohne Angabe im Manifest sind `ctx.sitzung` und `ctx.ablage` Attrappen: sie nehmen alles an und behalten nichts.
- In `ctx.sitzung` nie Fragetexte, Dokumenttexte, Gesprächsinhalte, Personenbezug oder Geheimnisse – das gehört in `ctx.ablage`.
- Die Scrollposition des Containers merkt sich der Vertrag selbst.
- `instanzen: viele` (nur mit `unmount(el)` und `actions(el)` nach N2): die Shell darf das Werkzeug versteckt eingehängt lassen.
  Dann helfen die freiwilligen Haken `hidden(el)` (bei Ereignissen nur merken „es kam etwas“) und `shown(el)` (jetzt neu lesen).
- Ein Knopf aus `sedraDom.button()` sendet kein Formular ab; der Absende-Knopf sagt es: `d().button(label, fn, 'p', {absenden: true})`.

## Für SEDRA (Vertrag §7)
Eine Spec in `benchmarks/devvm_specs/tool_<id>.py` beschreibt Zielobjekt, Handlungen, Routen und Ereignisse; die reinen Teile
werden als Node-Tests geprüft, der Browser-Teil über `uix_check`. Ein so gebautes Werkzeug trägt `trust: GUPPI_BUILT` und geht
durch denselben Install-Gate wie ein fremdes Modul.
