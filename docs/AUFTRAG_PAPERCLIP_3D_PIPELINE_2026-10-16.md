# Auftrag: 3D-Pipeline im Paperclip-Dashboard (Testlauf)

Stand 16.10.2026. Dieser Auftrag ist ein Testlauf. Er soll zeigen, wie man eine Pipeline aus mehreren Modellen und Agenten
baut, die etwas Greifbares herstellt und das Ergebnis dem Captain zur Entscheidung vorlegt.

## 1. Ziel

Vier Agenten arbeiten nacheinander in einer Pipeline. Am Ende liegen drei 3D-Objekte als Quelltext und eine Entscheidungsvorlage
für den Captain bereit. Die Vorlage sagt, welche Objekte sich aufgrund der Bedarfsdaten lohnen, und wartet auf Freigabe.

Gemessen wird, wie gut die Pipeline funktioniert: Schritte, Fehler, Nachvollziehbarkeit und Qualität der Ergebnisse.

## 2. Rollen im Organigramm (Paperclip)

| Rolle | Aufgabe | Eingabe | Ausgabe |
|---|---|---|---|
| Bedarfsanalyst | Liest die Bedarfsdaten und rankt die Objekte | `in/bedarf.csv` | `out/bedarf_ranking.md` |
| Konstrukteur | Schreibt je Objekt ein Modell als OpenSCAD-Quelltext | Ranking, Vorgaben | `out/objekte/<name>.scad` (3 Dateien) |
| Prüfer | Prüft Quelltext, Maße und Druckbarkeit | `out/objekte/` | `out/pruefung.md` |
| Vorlage | Schreibt die Entscheidung für den Captain | alle Ausgaben | `out/entscheidung.md` |

Jede Rolle arbeitet nur in ihrem Ausgabeordner und liest die Ausgaben der vorigen Rolle.

## 3. Eingaben und Grenzen (wichtig)

- **Bedarfsdaten:** Die Datei `in/bedarf.csv` stellt der Captain bereit (Spalten: Objekt, Suchanfragen oder Verkäufe, Zeitraum,
  Quelle). Die Modelle haben **keinen Internetzugang** und dürfen keinen Bedarf erfinden. Fehlt die Datei, endet der Lauf sofort
  mit dem Hinweis „keine Datenbasis“.
- **Werkzeug:** OpenSCAD ist auf dem Rechner nicht installiert. Die Objekte entstehen zunächst als Text. Das Rendern als STL
  folgt, sobald OpenSCAD installiert ist.
- **Keine Veröffentlichung:** Die Entscheidungsvorlage wird nicht veröffentlicht, nicht gedruckt und nicht bestellt.

## 4. Regeln für alle Rollen

- Keine Zahl, kein Objekt und keine Quelle, die nicht in den Eingabedaten steht. Wo Daten fehlen, steht „unbekannt“.
- Jede Aussage im Ranking und in der Entscheidung verweist auf eine Zeile in `in/bedarf.csv`.
- OpenSCAD-Dateien: Parameter oben in Variablen, Maße in Millimetern, höchstens 200 Zeilen je Datei.
- Schreibbereich: nur der eigene Ausgabeordner. Lesen ist im ganzen Arbeitsordner erlaubt.
- Beende mit `finish` und einer Zusammenfassung, welche Entscheidungen du getroffen hast und warum.

## 5. Ablauf

1. **Bedarfsanalyst:** Prüft, ob `in/bedarf.csv` vorhanden und vollständig ist. Rankt die Objekte nach dem, was die Daten zeigen,
   und begründet jede Platzierung mit Zeilen.
2. **Konstrukteur:** Wählt die drei obersten Objekte. Schreibt je Objekt eine `.scad`-Datei mit Parametern für Maße, Wandstärke
   und Befestigung. Gibt bei fehlenden Maßen einen Standardwert an und markiert ihn als Annahme.
3. **Prüfer:** Liest jede Datei. Prüft: Syntax (Klammern, Semikola, Befehle), Maße plausibel, keine offenen Stellen,
   Druckbarkeit (Mindestwandstärke, keine Überhänge ohne Stütze). Notiert jeden Fund.
4. **Vorlage:** Schreibt `entscheidung.md`: Empfehlung, Begründung mit Zeilenbezug, offene Annahmen, Risiken. Endet mit dem Status
   „wartet auf Freigabe durch den Captain“.

## 6. Ergebnis-Dateien

- `out/bedarf_ranking.md`
- `out/objekte/<name>.scad` (drei Dateien)
- `out/pruefung.md`
- `out/entscheidung.md`

## 7. Messung (je Modell)

- Anzahl Schritte und Fehler, Zahl der Wiederholungen
- Anteil der Aussagen mit Zeilenbezug im Ranking und in der Entscheidung
- Anzahl der Funde des Prüfers und wie viele davon berechtigt waren
- Ob die Vorlage ohne Nacharbeit lesbar ist

## 8. Offen, vor dem Start zu klären

1. Bereitstellung von `in/bedarf.csv` durch den Captain: Welche Daten gibt es, und woher stammen sie?
2. Soll OpenSCAD installiert werden, damit die Objekte gerendert werden können?
3. Welche drei Objekttypen sind als Testfeld gewünscht, falls die Daten keine klare Reihenfolge ergeben?
