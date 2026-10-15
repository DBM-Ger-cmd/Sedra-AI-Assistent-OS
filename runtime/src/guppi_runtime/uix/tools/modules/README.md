# Werkzeug: Module

Woraus die Oberfläche gerade besteht – und wie etwas dazukommt.

| Abschnitt | Was dort steht |
|---|---|
| **Shell** | welche läuft, welche es sonst gibt. Wechseln ist ein Klick + Neuladen. |
| **Werkzeuge** | Name, Herkunft (Paket oder eigener Ordner), Vertrauen, Zahl der Routen, an/aus |
| **Nicht geladen** | was abgelehnt wurde, mit dem Grund als Satz statt als Fehlercode |
| **Dazubauen** | aus der Vorlage (Audit) oder ein fremdes Modul vorlegen (Gate) |

## Die zwei Linien

- **Fremder Code → Gate.** `POST /api/uix/install` legt vor: Manifest, jede Datei mit SHA-256, jeder Fund der Durchsicht mit
  Datei und Zeile. Kopiert wird erst nach der Freigabe, und nur, wenn jede Datei noch denselben Hash hat.
- **Eigene Form → Audit.** Shell wechseln, Werkzeug an/aus, aus der Vorlage anlegen: unsere eigene, bekannte Form, nichts
  Fremdes, mit einem Klick zurück. Ein Gate dort würde die Freigabe zur Gewohnheit machen – und genau das soll sie nicht sein.
  *(Entscheidung des Captains, 14.10.2026.)*

**Nichts davon fasst den Projektordner an.** Geschrieben wird nur in `local_config` – deshalb berührt keine dieser Handlungen
eine Grenze aus Build 9.

## Ein eigenes Werkzeug in drei Schritten

1. Hier unten eine `id` eingeben → der Ordner `local_config/tools/<id>/` entsteht aus der Vorlage, schon umbenannt und geprüft.
2. `tool.js` schreiben (die Kommentare in der Vorlage erklären die vier Regeln, die die Tests erzwingen).
3. `python benchmarks/uix_check.py --tool <id>` muss `result ok` sagen.
