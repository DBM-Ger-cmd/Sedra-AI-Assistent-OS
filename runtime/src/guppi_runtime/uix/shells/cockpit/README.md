# Shell `cockpit` – Cockpit

Die erste Shell: ein Werkstück vorn, die Nachweise daneben, das Gespräch unten (COCKPIT_MODUL_v1 §1, Skizze `uix2_C`).
Sie besitzt den Bildschirm und gibt den Werkzeugen Container – sie kennt kein Werkzeug beim Namen, sondern fragt die
Registrierung, wer einen Objekttyp zeichnet.

**Zonen:** Instrumentenleiste · Baum (Projekt, Vorhaben, Aufgaben, Werkstatt, Besatzung, Bibliothek, System) · Werkbank (Dock) · Gespräch · Palette (Strg+K)

Build 24 (B6-G-06): „Modell hinzufügen“ und „Teststrecke“ öffnen die Abschnitte der Werkstatt; keine Zeile ohne Werkzeug dahinter (Routinen entfernt). Schrift nur in Token-Stufen. **`arbeitsplatz.yaml`** – das Wissen über diese Oberfläche (Satz, Zonen, wo was ist, Begriffe), aus dem SEDRA im Gespräch antwortet; es gehört zur Shell (Klaus 15.10.).
**Slots:** strip, tree, dock, talk, palette · **Layout:** je Browser gemerkt · **Vertrauen:** CORE

## Dateien
- `dock.js` – das eigene kleine Dock (Reiter, Teilen, Ziehen, Layout als JSON). Gehört in die Shell, nicht in den Kern (§3a).
- `tree.js` – Navigation; eine Zeile sendet `object.open`, mehr tut sie nicht.
- `strip.js` – gibt jedem Instrument eine Zelle und reicht `/api/strip` durch.
- `palette.js` – Strg+K und der reine Router: kurze Navigationsphrase → Ort, sonst → Gespräch.
- `shell.js` – setzt die Zonen zusammen, verteilt die Ereignisse, beantwortet Entscheidungen an einer Stelle.

## Regeln, die hier durchgesetzt werden
1. Ein Eingabefeld (das Gespräch), Strg+K als Palette darüber.
2. Entscheidungen haben einen Ort; eine Antwort im Gespräch erzeugt dasselbe Audit.
3. Die Werkbank-Zeile zeigt die Handlungen des Objekts im aktuellen Zustand – nie Navigation.
4. Reiter tragen Namen, Zeilen tragen Zustand.

## Abnahme
`python benchmarks/uix_check.py` – lädt die Shell, öffnet jedes Werkzeug, misst die Zonen und die Konsole.

## Bildschirmfoto
`docs/shots/cockpit/shell.png`
