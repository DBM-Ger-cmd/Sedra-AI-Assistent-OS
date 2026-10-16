# Regelwerk Standardläufe

Stand 16.10.2026. Gilt für alle Läufe, die ein Cloud- oder lokales Modell in der Sandbox ausführt. Die sechs bisherigen Läufe
(shells, cockpit, spec, pipeline, drache, omni) sind die Vorlage und die Präzedenzfälle dieses Regelwerks.

## 1. Geltungsbereich und Grundsätze

1. **Sandbox statt Live-Code.** Ein Lauf schreibt nur in seinen eigenen Schreibbereich unter `workspace/GUPPI_OS/redesign/`.
   Der Live-Code (`runtime/src/guppi_runtime/uix/` ohne Sandbox) wird nie direkt verändert.
2. **Übernahme nur nach Prüfung und Freigabe.** Ergebnisse werden vom Vorarbeiter geprüft. Übernommen wird erst nach Freigabe des Captains.
3. **Keine erfundenen Daten.** Ein Modell hat keinen Internetzugang. Zahlen, Quellen und Objekte kommen nur aus den bereitgestellten Eingaben.
4. **Personenbezug** geht nicht in die Cloud. Im Testmodus werden persönliche Angaben durch eigene Begriffe ersetzt, produktiv gilt die strenge Regel (siehe KI Labor, Modus).
5. **Jeder Schritt wird protokolliert**, ohne Prompt- und Dateiinhalte. Ein Lauf ohne Abschluss gilt als „läuft“.

## 2. Pflichtangaben je Lauf

Jeder Lauf hat genau diese Angaben, bevor er startet:

| Angabe | Inhalt |
|---|---|
| Name | eindeutig, z. B. `drache`, `omni` |
| Modell | Anbieter und Modellkennung, festgelegt im Lauf |
| Eingaben | Dateien, die der Lauf lesen darf (Auszüge, Spezifikation) |
| Schreibbereich | Liste erlaubter Dateien oder Ordner (`allow`) |
| Ausgaben | die Dateien, die am Ende existieren müssen |
| Abbruchregeln | siehe Abschnitt 4 |
| Prüfregeln | siehe Abschnitt 5 |

## 3. Ablauf

1. **Vorbereitung:** Eingaben in den Laborordner legen. Nur das, was der Lauf braucht. Fremde Texte vor dem Versand prüfen
   (Abschnitt 6).
2. **Start:** Der Lauf wird aus der festen Liste der Vorarbeiter-Aktionen gestartet (`lauf_starten`). Eine Art Lauf läuft höchstens
   einmal in sechs Stunden.
3. **Ausführung:** Schritte nacheinander. Jeder Schritt ist ein Modellaufruf durch den Inhaltsschutz.
4. **Abschluss:** Der Lauf endet mit `finish` oder mit einem Abbruchgrund. Beides steht im Protokoll.
5. **Prüfung:** Der Vorarbeiter prüft die Ausgaben (Abschnitt 5) und meldet das Ergebnis im Gespräch.
6. **Entscheidung:** Der Captain entscheidet über Übernahme, Nacharbeit oder Verwerfen.

## 4. Abbruch- und Wiederholregeln

Diese Regeln stammen aus den Läufen des 16.10.2026:

- **Zeitüberschreitung und Überlastung (Zeitlimit, 429, 5xx):** bis zu zweimal wiederholen, mit 20 Sekunden Pause. Erst danach abbrechen.
  Ein Schritt bekommt bis zu 240 Sekunden.
- **Leere Antwort:** Das Modell hat das Token-Limit im Nachdenken verbraucht. Der Schritt wird wiederholt und nicht als Sperre gewertet.
  Das Token-Limit je Schritt ist 12.000.
- **Sperre durch den Inhaltsschutz:** Der Lauf endet mit dem Grund. Nicht umgehen, sondern die Eingabe bereinigen (Abschnitt 6) oder die Datei weglassen.
- **Ungültiges Werkzeug viermal in Folge:** Der Lauf stoppt. Das Ergebnis lautet „keine gültigen Schritte“.
- **Schrittlimit:** 40 Schritte je Lauf.
- **Keine Folgeläufe auf unfertige Grundlagen:** Die Pipeline startet einen Schritt nicht, wenn der vorige nicht „finished“ ist.

## 5. Prüfregeln für die Ergebnisse

Der Vorarbeiter prüft jede Ausgabe nach diesen Regeln:

1. **Schreibbereich:** Nur erlaubte Dateien wurden geschrieben. Das Protokoll zeigt die Liste der Schreibvorgänge.
2. **Syntax:** JavaScript prüfen (`node --check`). OpenSCAD-Dateien: Klammern und Semikola.
3. **Projektregeln:** keine Hex-Farben außerhalb der Tokens (für Oberflächen), höchstens 400 Zeilen je Datei, keine `fetch`- oder
   `localStorage`-Aufrufe in Werkzeugen.
4. **Belege:** Jede Aussage im Ranking, in der Bewertung oder in der Entscheidung verweist auf eine Zeile oder Quelle der Eingabe.
5. **Vollständigkeit:** Alle Ausgaben aus Abschnitt 2 existieren und sind nicht leer.
6. **Entscheidung:** Ergebnis als „bestanden“, „Nacharbeit“ oder „verworfen“ festhalten, mit Grund.

## 6. Eingaben und Datenschutz

- **Fremde Projekte** (z. B. OmniRoute): nur die Teile, die für den Auftrag nötig sind. Vor dem Versand wird geprüft.
  Gesperrte Stellen werden durch eigene Begriffe ersetzt (`redesign_prep.py`). Die Zuordnung bleibt lokal.
- **Bedarfsdaten** (z. B. Pipeline): nur Daten mit Quellenangabe und einer Verlässlichkeitsangabe. Unbekannte Werte bleiben „unbekannt“.
- **Persönliche Angaben:** im Testmodus ersetzt, produktiv blockiert.

## 7. Protokoll und Nachvollziehbarkeit

Jeder Lauf schreibt eine Protokolldatei `lauf_<name>.jsonl` neben seinem Schreibbereich. Sie enthält:

- Start und Ende mit Modell, Anbieter und Schreibbereich
- jeden Modellaufruf und jeden Inhaltsschutz-Entscheid (ohne Inhalt)
- jeden Schreibvorgang mit Pfad und Größe
- Abbruchgrund und Zahl der Schritte

Das Entwurfsfenster und die KI Labor (Tab „Läufe“) lesen diese Protokolle.

## 8. Präzedenzfälle

| Lauf | Modell | Schreibbereich | Zweck | Besonderheit |
|---|---|---|---|---|
| shells | je Shell ein eigenes, aus `module_models` | je Shell ein eigener Dateibereich | Umbau der sechs Oberflächen | Modellwahl je Shell, um Ergebnisse zu vergleichen |
| cockpit | aus `module_models` (Modul `redesign`) | Dateibereich der Shell B | Cockpit-Layout, Phase B | Läuft über `redesign_run B` |
| spec | drei Modelle | `shells/spec/` in eigenem Ordner | Neue Shell nur aus Spezifikation | Kein Zugriff auf bestehende Shells |
| pipeline | vier Modelle nacheinander | `paperclip_lab/out/` | Bedarf, Auswahl, Varianten, Prüfung, Vorlage | Schritte aufeinander aufgebaut |
| drache | nemotron-3.5-super-vl | `drache_lab/drache.js` | Seedrache als Entwurf | Ausgangsversion als Vorlage |
| omni | nemotron-3.5-super-vl | `omni_lab/out/` | Bewertung eines fremden Projekts | Fremde Auszüge vor dem Versand bereinigt |

## 10. Frei anlegbare Läufe

Neue Aufträge werden nicht mehr im Code festgelegt, sondern als Definition angelegt. Die sechs Präzedenzfälle bleiben fest;
ein neuer Auftrag wie „bewerte XY“ oder „baue XYZ“ ist eine Datei.

**Definition** (`workspace/GUPPI_OS/redesign/laeufe/<name>.json`, Felder aus `laufdefinition.py`):

| Feld | Pflicht | Regel |
|---|---|---|
| `name` | ja | Kleinbuchstaben, Ziffern, Bindestrich, 2–40 Zeichen; Name ist eindeutig |
| `art` | nein | `bewerten` (Ergebnis ist ein Bericht) oder `bauen` (Ergebnis sind Dateien); Standard `bewerten` |
| `beschreibung` | nein | eine Zeile, höchstens 300 Zeichen |
| `lab` | ja | Ordner unter `redesign/`, relativ, ohne `..` |
| `provider`, `model` | ja | Anbieter und Modellkennung; Modell für den Lauf festgelegt |
| `task` | ja | Auftrag, höchstens 4000 Zeichen; muss sagen, wann mit `finish` zu enden ist |
| `allow` | ja | erlaubte Dateien oder Ordner, relativ; höchstens 20 Einträge |
| `outputs` | nein | Dateien, die am Ende existieren müssen; jede Ausgabe liegt innerhalb eines `allow`-Eintrags |

**Ablauf:**

1. `lauf_anlegen` (Vorarbeiter) prüft die Definition und speichert sie. Bestehende Namen werden nicht überschrieben. Angelegt wird nicht gestartet.
2. `lauf_starten` mit dem Namen startet den Lauf. Die Sperre von sechs Stunden gilt je Name, wie bei den festen Läufen.
3. Endet der Lauf mit `finish`, fehlt aber eine Ausgabe, wird er als `unvollstaendig` gemeldet, nicht als fertig.

**Abgrenzung:** Die Prüfung schützt vor Pfaden außerhalb des Labors und vor fehlenden Angaben. Sie ersetzt nicht die Prüfung des
Ergebnisses durch den Vorarbeiter (Abschnitt 5) und nicht die Freigabe des Captains.

## 11. Offene Punkte

- Vision-Modell für die Bewertung von Screenshots ist noch nicht eingebunden.
- Ein Lauf-Test mit steigender Zahl gleichzeitiger Aufrufe steht aus.
- Die Standardliste der Läufe kann um weitere Aufträge aus den Gesprächen erweitert werden. Jeder neue Auftrag folgt diesem Regelwerk.
