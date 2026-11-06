---
name: sedra-ui-vertrag
description: Regeln und Muster für Oberflächen und Apps von One Sedra (Tools, Shells, ui/-Bausteine, Prozess-Apps n8n Workflows und Szenario Studio): Dateigrenzen, Farben, Routen, Browser-Tests. Nutzen, wenn Dateien unter runtime/src/guppi_runtime/uix angelegt oder geändert werden.
---

# UI-Vertrag One Sedra

## Harte Regeln (der Vertragstest `test_uix_contract` prüft sie)
- Keine Datei eines Tools oder einer Shell über **400 Zeilen**. Wächst eine Datei darüber, Methoden in eine Mixin-Datei auslagern (Beispiel `ui/workflow-extras.js`, in den Editor gemischt über `...root.sedraWorkflowExtras(options)`).
- **Farben nur als Token** in `ui/tokens.css`. In anderen CSS-Dateien keine Hex-Werte (`--x:#fff` fällt durch). Neue Themenfarben dort definieren, im Modul nur `var(--...)`.
- Ein Tool stylt nur `.t-<id>`. Gemeinsame Bausteine liegen in `ui/`, **kein Querimport** zwischen Tools.
- Skripte werden in `desk.html` einzeln eingebunden (Reihenfolge: Modell, Prozess, Symbole, Dialog, Auswahl, Canvas, Extras, Editor). Top-Level-Code nur in `tool.js`/`shell.js`.
- Jede Route, die ein Tool ruft, steht in seiner `tool.yaml` unter `api` (sonst 403). Ruft der Code sie nur über einen Helfer aus `ui/`, im Test `RoutenImManifest.HELFER` eintragen. Harness-Routen stehen als Muster in `harness/api.py`.

## Muster
- Zwei Apps, eine Basis: `ui/workflow-*.js` (Modell, Prozess, Canvas, Editor, NDV). Eine App unterscheidet sich nur über Optionen (`style`, `runBar`, `ndv`, `palette`, `inspector`).
- Unsichtbare Trefferflächen im SVG brauchen eine sichtbare Geometrie (Kreis in einer Gruppe), sonst findet Playwright sie nicht ("not visible").
- Menschliche Schritte erscheinen nie als technische Knoten. Ein Prozessmodell ist nie ausführbar (`disabled`), die Prozess-Apps erteilen keine Rechte.
- Texte auf Deutsch, `aria-label` für jedes Bedienelement, Tastatur (Escape schließt, Enter wählt).

## Browser-Tests
- `uix_check.start_server(..., shell='harness')`, Edge über `playwright` (`channel='msedge'`), Umgebungsvariable `SEDRA_BROWSER=1`.
- Namen von Knöpfen exakt abfragen (`exact=True`); neue Knöpfe dürfen vorhandene Namen nicht doppeln.
- Gesperrte Einträge (`aria-disabled`) mit `click(force=True)` prüfen.
- Nach Layout-Änderungen die Export- und Speichertests der Apps wieder laufen lassen: schmale Auswahlfelder in der oberen Leiste machten sie schon instabil.

## Vorlagen und Lizenz
n8n und Make nur als Referenz für Maße und Bedienlogik. Keinen Code, keine Symbole und keine Texte der Hersteller übernehmen.
