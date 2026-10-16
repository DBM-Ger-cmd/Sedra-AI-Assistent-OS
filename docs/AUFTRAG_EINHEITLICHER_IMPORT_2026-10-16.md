# Auftrag: einheitlicher Import für Shells und Werkzeuge

Stand 16.10.2026. Auftraggeber: Captain. Umsetzung durch GUPPI (Solo-Modus), Prüfung durch den Captain.

## 1. Anlass

Der Captain konnte mit dem bisherigen Weg nichts richtig importieren. Den Weg gibt es heute an zwei Stellen mit je
eigenem Ablauf:

- **Module** (Werkzeug `modules`): Knopf „Vorlegen“ unter „Fremdes Modul vorlegen“.
- **Start-Shell** (`uix/shells/start/shell.js`): Knopf „Vorlegen“ für eine fremde Shell.

Beide senden den eingegebenen Ordnerpfad an `POST /api/uix/install` (`uix_server.py`, `install_request`). Dort entsteht
eine Entscheidung unter „Entscheidungen“, die erst nach Freigabe über `POST /api/uix/install/apply` eingebaut wird.

Die Ursache des Fehlschlags ist nicht bekannt. Sie wird im ersten Schritt nachgestellt, nicht geraten.

## 2. Ziel

Ein einziger Weg, mit dem jede fremde Shell und jedes fremde Werkzeug importiert wird, Schritt für Schritt nachvollziehbar
und mit klaren Fehlermeldungen.

## 3. Ablauf (verbindlich)

1. **Quelle wählen.** Ein Feld für den vollständigen Ordnerpfad oder eine Auswahl über den Ordnerdialog. Art wählen: Shell
   oder Werkzeug. Art und Quelle sind Pflichtangaben.
2. **Prüfen.** Ohne Einbau. Geprüft werden: Manifest (`shell.yaml` bzw. `tool.yaml`), alle genannten Dateien vorhanden, Größe je
   Datei, Routen im erlaubten Schema, Objekttypen gegen `desk/gateway.py`, keine Hex-Farben außerhalb der Tokens, höchstens
   400 Zeilen je Datei, keine `fetch`- oder `localStorage`-Aufrufe in Werkzeugen. Ergebnis: Liste mit bestanden/Fehler je Punkt.
3. **Bericht.** Manifest, Prüfsumme je Datei und die Befunde aus Schritt 2 werden als ein Bericht gezeigt.
4. **Entscheidung.** Der Bericht landet als Entscheidung. Einbau nur nach Freigabe des Captains. Eine COMMUNITY-Quelle
   bekommt nur Leserouten (wie bisher).
5. **Einbau.** Vorher wird der betroffene Ordner gesichert. Der Einbau schreibt nur in `local_config`, nie in den Projektordner.
   Danach steht ein Rückweg bereit („zurück zur Sicherung“).
6. **Protokoll.** Jeder Schritt (Quelle, Prüfung, Entscheidung, Einbau, Rückweg) steht im Logbuch, ohne Dateiinhalte.

## 4. Fehlermeldungen

Jeder Fehler sagt in einem Satz, was fehlt und was zu tun ist. Keine Fehlercodes ohne Erklärung. Die bestehenden Codes
(`decision_cannot_be_applied`, `path` usw.) werden übersetzt, nicht umbenannt.

## 5. Akzeptanzkriterien

- **A1:** Der Captain importiert die Shell `minimal` aus einem Ordner über den neuen Weg. Ergebnis: Bericht, Entscheidung,
  Freigabe, eingebaut, Rückweg funktioniert.
- **A2:** Ein Ordner ohne `shell.yaml` wird mit einer Meldung abgelehnt, die die fehlende Datei nennt.
- **A3:** Ein Pfad, den es nicht gibt, wird vor der Entscheidung abgelehnt.
- **A4:** Eine COMMUNITY-Quelle mit Schreibroute wird nicht eingebaut.
- **A5:** Ein fremder Ordner ändert nichts im Projektordner (Prüfung per Dateivergleich vorher/nachher).
- **A6:** Die bestehenden Tests `test_uix_contract`, `test_ui_tokens`, `test_uix_flows` laufen grün.

## 6. Reihenfolge

1. Fehler nachstellen: den bisherigen Weg mit `minimal` durchspielen und den Punkt festhalten, an dem er scheitert.
2. Den einen Weg bauen (Abschnitte 3 und 4).
3. Akzeptanzkriterien A1–A6 prüfen, Ergebnisse im Auftrag festhalten.
4. Dem Captain übergeben. Eingebaut wird erst nach seiner Freigabe.

## 7. Nicht Teil dieses Auftrags

- Der Import von Shells aus dem Redesign-Bereich (`redesign/uix`). Das ist ein eigener Schritt nach der Prüfung der Läufe.
- Änderungen an der Freigabelogik selbst. Die bleibt wie sie ist.
