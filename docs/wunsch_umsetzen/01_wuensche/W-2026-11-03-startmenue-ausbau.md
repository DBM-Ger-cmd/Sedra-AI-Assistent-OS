# Wunsch: Start-Menü ausbauen – Sedra Token, Mini-Apps

- Datum: 2026-11-03
- Sitzung: Vorarbeiter (Claude Code), Screenshot des Start-Menüs
- Wunsch (Worte des Captains): „Das Start-Menü muss ausgebaut werden. Sedra-Meter kann umbenannt werden in Sedra Token; darunter werden wir alles, was Token geht, sammeln und auch aufwerten und ausbauen. KI-Labor kann auch als kleine App angezeigt werden mit den wichtigsten Daten. Das machen wir mit allen Punkten, die praktikabel sind und Aufwertung brauchen.“
- Was verstanden wurde:
  1. **Umbenennung (erledigt 03.11., ungeprüft im Browser, nicht committet):** „Guppy-Meter“ heißt in den Orten (`ui/places.js`), im Befehlsfeld, im Cockpit-Baum, in den Minimal-Symbolen und im Werkzeug `meter` jetzt „Sedra Token“. Die Kennung `meter` bleibt, damit Verknüpfungen und Reiter nicht brechen.
  2. **Gruppe „Token“:** unter „Sedra Token“ sammeln sich alle Token-Dinge: Zelle Token der Taskleiste, die Seite „Token und Gespräch“ (heute unter Einstellungen → Agent), der Tagesverbrauch und die Kosten (`costs`). Aufwertung offen (Verlauf je Sitzung, je Modell, tok/s).
  3. **Mini-Apps im Start-Menü:** Orte mit einem kleinen Datenfeld (Kachel) statt nur einer Zeile, zuerst KI-Labor (Anbieter, Schlüssel gesetzt ja/nein, Modelle, letzter Test), danach alle Orte, bei denen das praktikabel ist (Hardware, Modelle und Slots, Aufgaben, Entscheidungen, Wissen).
- Offene Rückfragen:
  - Welche Orte außer KI-Labor sollen eine Kachel bekommen, und welche drei bis vier Werte je Kachel?
  - Sollen die Kacheln live aktualisieren (Abfrage beim Öffnen des Menüs) oder nur beim Öffnen einmal laden?
  - Gehört „Token und Gespräch“ aus den Einstellungen in die Token-Gruppe verschoben oder nur dort verlinkt?
- Berührte Stellen (Vorschlag): `uix/shells/harness/startmenue.js`, `startliste.js`, `ui/places.js`, `tools/meter/`, `tools/labor/`, `tokenseite.js`; ein Manifest-Feld für die Kachel (siehe `docs/ENTWURF_APPS_MODELL_2026-11-03.md` auf dem Branch `docs/apps-modell`, Zellen und Gebiet je Werkzeug).
