# Wunsch: Chatfenster – Fenster bis unten, Werkzeug-Details in geteilter Vorschau

- Datum: 2026-11-03
- Sitzung: Vorarbeiter (Claude Code), Screenshot des Captains
- Wunsch (Worte des Captains): „Das Fenster darf bis unten durchlaufen.“ / „Hier ist frei, das kann hier angezeigt werden mit einer horizontal geteilten Ansicht.“ / „Der gelbe Kasten lässt sich nicht einfahren.“
- Was verstanden wurde:
  1. Die Vorschau (links) und das Gespräch (rechts) enden heute über der Eingabezeile (`.hs-haupt` hat die Reihen Reiter | Fläche | Eingabe). Die Eingabe soll nur unter dem Gespräch stehen; die Vorschau läuft bis zur Taskleiste durch.
  2. Der freie Platz unter der Dateiansicht in der Vorschau soll horizontal geteilt werden: oben die Datei, unten die Details des gewählten Werkzeugaufrufs (Eingabe und Ausgabe, heute in der aufgeklappten Zeile im Gespräch, die dort die Spalte sprengt).
  3. Der gelbe Hinweis der Vorlage ist seit 71bfd23 einklappbar; das Fenster des Captains lief mit dem alten Stand (kein Kopf „▾ … – Hinweis“ sichtbar). Neu laden (Strg+F5) genügt; bleibt es, ist es ein Fehler.
- Offene Rückfragen:
  - Soll die Teilung (oben Datei, unten Werkzeug) ein fester Balken sein oder ziehbar, wie die Breite der Vorschau?
  - Ein Klick auf eine Werkzeugzeile: nur unten in der Vorschau zeigen, oder die Zeile im Gespräch zusätzlich aufklappbar lassen?
- Berührte Stellen (Vorschlag): `uix/shells/harness/shell.js` (Raster `hs-haupt`), `shell.css`, `vorschau.js` und `vorschau.css`, `zeilen.js` (Werkzeugzeile), `eingabe.js` (Eingabe in die Gesprächshälfte). Test: `tests/test_uix_harness_browser.py`.
