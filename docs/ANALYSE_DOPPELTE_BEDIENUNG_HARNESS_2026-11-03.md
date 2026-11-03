# Analyse: doppelte Knöpfe und Wege in der Harness-Shell (03.11.2026)

Stand: `main` bei `5ff07b7`. Geprüft in einer Probe-Instanz (alle sichtbaren Knöpfe in Sitzung, Start-Menü und Einstellungen aufgelistet) und im Code (`einstellungen.oeffnen(`, `app.oeffnen(`, `modell.menue(`, Orte in `ui/places.js`, Punkte in `einstellungen.js`). Nur Befund und Vorschlag – nichts wurde geändert.

## Stand der Umsetzung (03.11.2026, abends)

**Erledigt (Gruppe D1, nicht committet):** A5 (GPU und RAM sind eine Zelle „GPU · RAM“), A7 (Start-Menü: ein Knopf „Darstellung und Schrift …“ statt der vier Schalter), A8 (Eintrag „Einstellungen“ aus der Gruppe System im Start-Menü entfernt; Kachel und Suche bleiben), B1 (Gruppe „Sprache und Ton“), B2 („Züge je Vorlage“), B3 („KI-Labor“ statt „Cloud“), B4 („Logbuch“ statt „Audit“). Hilfetexte (`arbeitsplatz.yaml`, `README.md`) nachgezogen.

**Bewusst nicht geändert:** Die Zelle „Zustand“ öffnet weiter Einstellungen → System (Entscheidung D-U6 aus Stufe 5); „Hardware“ und „Maschinenraum“ bleiben zwei Orte, bis A2 entschieden ist.

**Offen:** A1, A2, A3, A4, A6.

## A. Dieselbe Sache zweimal angezeigt oder bedient (zusammenlegen)

| Nr | Was doppelt ist | Wo | Vorschlag | Aufwand |
|---|---|---|---|---|
| A1 | **Offene Sitzungen und Apps**: Reiterleiste oben **und** Taskleiste (Mitte) listen dieselben Reiter. Die Taskleiste trägt zusätzlich die Zeitlinie (denkt, schreibt, Werkzeug, wartet auf Freigabe, Dauer). | `reiter.js`, `taskleiste.js` | Taskleisten-Mitte entfällt als Liste; die Zeitlinie wandert als kleiner Zustand in den Reiter (Punkt und Kurztext) und die Läufe bleiben in der Taskleiste. | mittel |
| A2 | **Zehn Werkzeuge in zwei Menübäumen**: Rekorder, KI GateWay (sogar zweimal: „KI GateWay“ und „Guard / Inhaltsschutz“ zeigen dasselbe Werkzeug), KI-Labor (Start) = „Cloud“ (Einstellungen), Bibliothek, Werkstatt, Slots, Modus und Grenzen, Module, Logbuch = „Audit“. | `places.js` + `start_gruppen.json` gegen `einstellungen.js` | Start-Menü = Apps (Arbeit, Wissen, Modelle-Werkstatt); Einstellungen = Konfiguration. In Start nur *einen* Eintrag je Werkzeug, in Einstellungen die anderen als Verweis. „Guard / Inhaltsschutz“ und „KI GateWay“ zu einem Punkt. | mittel |
| A3 | **Token**: „Sedra Token“ (Werkzeug `meter`: Token, Zeilen, Kosten) und „Token und Gespräch“ (Einstellungen: Verbrauch heute und Sitzung, Denken, Antwortbudget, Verlauf) zeigen beide den Verbrauch; dazu die Token-Zelle der Taskleiste und die Optionen im Schild des Eingabefelds. | `tools/meter`, `tokenseite.js`, `gespraechsoptionen.js`, `taskleiste.js` | Eine App „Sedra Token“ mit Reitern *Verbrauch* (heute, Sitzung), *Kosten und Zeilen* (Meter), *Gespräch* (Optionen). Taskleiste und Schild verweisen darauf. | mittel bis groß |
| A4 | **Modell**: Modell-Knopf im Eingabefeld, Modell-Zelle in der Taskleiste (öffnet **dasselbe** Menü), Karte „Modelle“ im Start-Menü, „Werkstatt: Modelle“ und Einstellungen → Werkstatt (dasselbe Werkzeug), „Modell wählen“ im Startbild. Dazu die zweite Zelle „Server“ mit eigenem Router-Menü. | `eingabe.js:35`, `taskleiste.js:193`, `modell.js` | Modell-Zelle der Taskleiste und Modell-Knopf im Eingabefeld behalten *eine* Rolle: Zelle = Anzeige und Klick auf Werkstatt, Knopf = Laden und Wechseln. „Server“ ins selbe Menü legen (zwei Abschnitte). | klein |
| A5 | **Hardware**: Zellen GPU und RAM in der Taskleiste öffnen **dieselbe** App; im Start-Menü sind „Hardware“ und „Maschinenraum“ **dasselbe Werkzeug** (`system` hat `handles: [machine, hardware]`). | `taskleiste.js` (ZELLEN), `places.js:25–26`, `tools/system` | GPU und RAM zu einer Zelle („GPU 40 °C · RAM 15/31 GB“). Hardware und Maschinenraum zu einem Ort mit zwei Reitern. | klein |
| A6 | **Freigaben**: Seitenleiste „Posteingang“ (Anträge), Seitenleiste „Aufgaben“ (Aufgaben-Freigaben, Vorschläge des Vorarbeiters), Taskleisten-Zelle „Freigaben“ (springt je nach Art in Aufgaben, Sitzung oder die App Entscheidungen), Start „Entscheidungen“ und Kachel „Aufgaben“. Vier Eingänge für „was wartet auf mich“. | `seite.js`, `taskleiste.js:226`, `places.js` (`decisions`, `tasks`) | Ein Eingang „Posteingang“ (alle wartenden Dinge, Filter: Karten, Anträge, Aufgaben). Zelle, Seitenleiste und Kachel führen dorthin. „Aufgaben“ bleibt als eigene App für das, was *läuft*. | mittel |
| A7 | **Darstellung und Schrift**: Klar/Nacht und Normal/Groß stehen im Fuß des Start-Menüs und in Einstellungen → Darstellung (die Seite sagt selbst „dieselben Schalter“). | `startmenue.js` (fuss), `einstellungen.js` | Im Start-Menü nur ein Knopf „Darstellung …“ (öffnet die Einstellung) oder nur Klar/Nacht als Schnellschalter. | klein |
| A8 | **Einstellungen öffnen** auf sieben Wegen: Seitenleiste, Start → System → Einstellungen, Start-Kachel „Einstellungen“ samt sechs Gruppenknöpfen, Zelle „Zustand“ (öffnet *System*), Befehl `/einstellungen`, Zelle Token, Schild „mehr“. | `seite.js`, `startmenue.js`, `taskleiste.js` | Im Start-Menü den Eintrag in der Gruppe System streichen (die Kachel genügt; die Suche findet ihn weiter). Zelle „Zustand“ besser nach *Maschinenraum* als nach Einstellungen/System. | klein |

## B. Gleiche Wörter, verschiedene Dinge (umbenennen oder klären)

| Nr | Befund | Vorschlag |
|---|---|---|
| B1 | „**Sprache**“ ist zweimal Gruppe/Punkt: *Allgemein → Sprache* (Sprache der Oberfläche: „Deutsch, es gibt keine zweite“) und die *Gruppe* Sprache (Rekorder, Quelle). | Punkt in Allgemein streichen oder „Oberfläche: Sprache“ nennen; Gruppe → „Sprache und Ton“. |
| B2 | „**Grenzen**“: *Agent → Grenzen der Schleife* (max_zuege) und *System → Modus und Grenzen* (Projekt, Netz, Löschen, Kosten). | „Grenzen der Schleife“ → „Züge je Vorlage“. |
| B3 | „**Cloud**“ (Einstellungen) = „KI-Labor“ (Start, Kachel) = Werkzeug `labor`; „KI GateWay“ ist ein anderes. | Überall „KI-Labor“. |
| B4 | „**Audit**“ (Einstellungen) = „Logbuch“ (Start, Fehlerzeile). | Überall „Logbuch“. |

## C. Bewusst doppelt, so lassen

- Rekorder: Mikrofonknopf im Eingabefeld (schnell) und App (voll); Schild „Katalog gibt frei“ (schnell) und Freigabe-Modus (Editor): Schnellzugriff plus Seite ist ein Muster, solange der Schnellzugriff auf die Seite verweist.
- „Neue Sitzung“: Knopf in der Seitenleiste und „+“ in der Reiterleiste – zwei Orte, ein Zweck, beide üblich.
- „Logbuch öffnen“ in der Fehlerzeile: Kontextknopf.
- ☑ (mehrere auswählen) und ⋯ (Sortierung) in der Seitenleiste tun Verschiedenes.

## D. Reihenfolge, wenn umgesetzt wird

1. **Klein und sicher:** A8, A7, A5 (nur Zellen), B1 bis B4.
2. **Mittel:** A2, A4, A6.
3. **Größer, mit Entwurf:** A1 (Zeitlinie in den Reiter), A3 (Token-App).

Die Punkte A2, A3 und A6 hängen am Apps-Modell (`docs/KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md`: Ort, Gebiet, Zelle je Werkzeug); sie sollten darauf aufsetzen statt eine neue Aufteilung zu erfinden.
