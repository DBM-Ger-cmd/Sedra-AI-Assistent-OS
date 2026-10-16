# Shell E – Minimal

Ein Schreibtisch: Menüleiste oben, freie Fenster, Ablage unten, die wartende Entscheidung rechts oben.
Sie lädt **dieselben Werkzeuge wie das Cockpit**, in einer anderen Form – das ist ihr eigentlicher Zweck
(`docs/SPEC_SHELL_E_UND_MODULE_v1.md`): Wenn für diese Shell ein Werkzeug geändert werden müsste, wäre das ein Mangel des
Vertrags, nicht der Shell.

## Umschalten

In `local_config/uix.yaml`:

```yaml
uix:
  shell: minimal      # oder cockpit
```

Danach die Seite neu laden – der Loader lädt genau eine Shell beim Start.

## Zurück, Bildzeichen, eigene Ablage (Build 19)

- **Haus-Knopf** ganz links in der Menüleiste: zur Übersicht der Oberflächen – nur für diesen Lauf, die Wahl in `uix.yaml` bleibt.
  Das Menü **„SEDRA“** wechselt direkt in eine andere Oberfläche.
- **Ablage mit Bildzeichen** (`icons.js`, eigene Linienzeichen, folgen dem Thema).
- **„＋ Neu“**: ein eigenes Feld – *Ort*, *Fenster vorn* (eine bestimmte Aufgabe, ein Modell) oder *Auftrag an GUPPI* (ein Satz,
  der beim Klick ins Gespräch geht). Name und Zeichen wählbar. **Rechtsklick** auf ein Feld: verschieben, ändern, entfernen,
  Ablage zurücksetzen. Menü „Fenster“: „An die Ablage heften“.
- Gemerkt in `local_config/uix.yaml` (`uix.shelf.minimal`) über `GET/POST /api/uix/shelf` – nicht im Browser, weil SEDRA bei
  jedem Start einen neuen Port nimmt. Audit `UIX_SHELF_SAVED`, kein Gate.

## Wie sie die Teile des Vertrags abbildet

| Vertrag | Cockpit | Minimal |
|---|---|---|
| Instrumente (`kind: instrument`, `update(reading)`) | Leiste oben | rechts in der Menüleiste – dieselben Werkzeuge, derselbe `/api/strip` |
| Werkstück und Nachweise (`slot: inhalt \| nachweis`) | zwei Spalten nebeneinander | ein Umschalter im Fenster; beim Wechseln wird wirklich `unmount`-et |
| Gespräch (`kind: panel`, `talk`) | Zone unten | ein Fenster **ohne Schließknopf** – ohne Gespräch gäbe es kein Eingabefeld (Regel 1) |
| Entscheidungen | Werkzeug `decisions` | Karte rechts oben, Antwort über dieselbe Route (Regel 2) |
| Navigation | Baum links | Ablage unten (eigene Felder, Bildzeichen), Menü „Werkzeuge“, Strg+K, Haus → Übersicht |
| Layout | Reiter, im Browser gemerkt | Fensterlage, im Browser gemerkt (`sedra.minimal.windows`) |

## Was sie bewusst nicht kann

- **Keine zwei Werkzeuge nebeneinander.** Ein Fenster zeigt eines; die Nachweise liegen dahinter. Für den Vergleich von
  Werkstück und Nachweis ist das Cockpit die bessere Form – diese Shell ist für wenige Fenster und viel Ruhe.
- **Kein Baum.** Wer die ganze Lage auf einmal sehen will, nimmt das Cockpit.
- **Keine Palette.** Strg+K öffnet das Menü „Werkzeuge“ mit Suchfeld; die Palette des Cockpits ist Cockpit-Code und wird hier
  nicht geerbt.

## Dateien

| Datei | Inhalt |
|---|---|
| `icons.js` | die Bildzeichen (Pfade auf 24×24); `typeIcon`, `iconIds` rein. |
| `shelfedit.js` | Feld anlegen/ändern; `entryFrom` rein. |
| `windows.js` | Fenster: öffnen, fokussieren, ziehen, Größe, Umschalter, Handlungen, Layout. `placeBox`/`clampBox`/`orderTools` sind rein und werden mit node geprüft. |
| `menubar.js` | Haus, Menüs (SEDRA · Ablage · Aufgabe · Werkzeuge · Fenster · Hilfe) und die Instrumente. |
| `shelf.js` | Ablage unten (Vorgabe, eigene Felder, Rechtsklick) und die Entscheidungskarte. |
| `shell.js` | `registerShell`, Start, Verdrahtung, `decide()`, `notify()`. |

## Abnahme

```
python benchmarks/uix_check.py --shell minimal
```

Prüft dieselben Werkzeuge wie beim Cockpit, dazu die Zonen dieser Shell und dass ein Fenster nach dem Neuladen wieder da ist.
