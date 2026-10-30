# SPEC Harness-Shell Stufe 6 – G1 Anforderungen: Verständlichkeit und geteilte Ansicht (30.10.2026)

Anlass: Abnahme am PC durch den Captain, 30.10.2026 12:10. Befund: „Das passt soweit, aber bei den Aufgaben weiß man nicht, was dort gemacht wird; es wird eine Beschreibung kurz und knapp benötigt. Bei Projekten weiß man auch nicht, was man machen soll. Hier fehlt die Bildschirmteilung des Master-Chat-Fensters.“
Stufen 4 und 5 sind in dieser Abnahme bis auf diese drei Punkte bestanden (Einstellungen, Benachrichtigungen, Grenzen der Schleife, Statusleiste mit GPU-Zelle). Nichts davon ist gebaut; diese Datei ist G1.

## 1. Befund

| Nr | Was der Captain sieht | Ursache im Code |
|---|---|---|
| B1 | Reiter „Aufgaben“: Karten mit Titel, ID, Sitzungen und Zeilen wie `lauf_starten · run_tests`. Was die Aufgabe **bewirkt**, steht nirgends in einem Satz. | Die Aufgabe hat nur `titel`, `erlaubt` (Werkzeug + Muster) und `ende`; es gibt kein Beschreibungsfeld (`harness/aufgabe.py`, `aufgabe.js`). |
| B2 | Seitenleiste „Projekte“: Ein Projekt mit vielen alten Sitzungen, keine Erklärung, was ein Projekt ist, was man dort tut, was der Vorarbeiter-Knopf macht. | `seite.js` zeigt nur die Liste; kein Leerzustand, keine Hilfe. |
| B3 | Es gibt nur **einen** Arbeitsbereich. Zwei Sitzungen (oder Sitzung und Aufgaben/Werkstatt) lassen sich nicht nebeneinander sehen. | HS-01: genau eine Arbeitsfläche; Reiter wechseln sie nur. |

## 2. Anforderungen

### 2.1 Aufgaben mit Beschreibung (zu B1)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-60 | Eine Aufgaben-Freigabe trägt ein Feld **`zweck`**: ein Satz, höchstens 160 Zeichen, in der Sprache des Captains („Testläufe der Gruppe harness starten und das Ergebnis lesen“). Beim Anlegen durch den Captain ist es Pflicht; ein Vorschlag des Vorarbeiters muss es ebenfalls enthalten. | Test: ohne Zweck `zweck_fehlt`; zu lang `zweck_zu_lang` |
| HS-61 | Die Karte der Aufgabe zeigt den Zweck als **erste Zeile** unter dem Titel, dann in Klartext, was erlaubt ist („Darf: Dateien schreiben in docs/spec_entwuerfe · Lauf run_tests starten“), danach Rest an Aufrufen und Zeit. Technische Muster stehen darunter, einklappbar. | uix_check: Karte hat Zweckzeile und Klartext-Erlaubnis |
| HS-62 | **Alte Aufgaben ohne Zweck** (angelegt vor Stufe 6) zeigen statt des Zwecks die erzeugte Klartext-Zeile aus HS-61; nichts wird nachträglich geschrieben oder geändert. | Test mit Datei ohne `zweck` |
| HS-63 | Dieselbe Klartext-Zeile erscheint auf der Freigabe-Karte und im Verlauf, wenn ein Werkzeugaufruf von einer Aufgabe gedeckt wird („gedeckt durch Aufgabe: <Zweck>“). | Test der Werkzeugzeile |
| HS-64 | Das Formular „Aufgabe freigeben“ hat das Feld Zweck an erster Stelle, mit Beispielsatz als Platzhalter, und erklärt in einem Satz, was Freigabe bedeutet. | uix_check |

### 2.2 Projekte erklärt (zu B2)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-65 | Die Gruppe **Projekte** hat eine Kopfzeile mit einem Satz („Ein Projekt ist ein Arbeitsordner mit eigenen Sitzungen, Freigaben und einem Vorarbeiter.“) und ein „?“, das eine kurze Hilfe öffnet (was ein Projekt ist, was die Fahne/der Vorarbeiter bedeutet, wie man eine Sitzung anlegt, wo die Aufgaben stehen). | uix_check |
| HS-66 | Ein Projekt ohne Sitzung zeigt einen Leerzustand mit dem nächsten Schritt („Neue Sitzung starten“). Das aktive Projekt ist hervorgehoben; ein Klick auf den Projektnamen klappt auf/zu und zeigt in der Tooltip-Zeile Anzahl Sitzungen, Vorarbeiter und offene Aufgaben. | Test der Shell |
| HS-67 | Sitzungen älter als 7 Tage stehen in einem eingeklappten Block „Ältere Sitzungen (n)“; **nichts wird gelöscht oder archiviert** (HS-18 bleibt: Löschen nur auf Nachfrage). | Test |

### 2.3 Geteilte Ansicht (zu B3)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-70 | Die Arbeitsfläche lässt sich in **zwei Flächen** teilen (nebeneinander; Voreinstellung 50/50, Trennbalken ziehbar, Mindestbreite je Fläche 420 px). Jede Fläche hat ihre eigene Reiterleiste; ein Reiter lässt sich per Ziehen oder Kontextmenü („Rechts daneben öffnen“) in die andere Fläche verschieben. | Test der Shell, uix_check bei 1400×860 |
| HS-71 | Eine Fläche ist die aktive (Rahmen in Akzentfarbe); das Eingabefeld und Tastaturkürzel gelten für die aktive Fläche. Strg+\ teilt/schließt die Teilung. | Test |
| HS-72 | Beide Flächen können **gleichzeitig** je eine Sitzung mit eigenem Strom zeigen; zwei Antworten laufen unabhängig (jede Sitzung hat schon ihren eigenen Strom, HS-10). Dieselbe Sitzung nie in beiden Flächen. | Test: zwei Sitzungen streamen parallel |
| HS-73 | Unter 1100 px Breite gibt es keine Teilung (Knopf ausgeblendet, vorhandene Teilung wird zu Reitern zusammengeführt); HS-05 gilt unverändert. | uix_check bei 1024×700 |
| HS-74 | Die Teilung merkt sich der Browser je Projekt (Anordnung der Reiter, Breite); die Sitzungen selbst bleiben unverändert. | Test |

## 3. Abgrenzung

- Keine neue Rolle, kein neues Recht: Zweck und Klartext sind **Anzeige**; über Deckung und Freigabe entscheiden weiter nur `erlaubt`, Katalog und Vorbehalte. Der Zweck deckt nichts (HS-27 unverändert).
- Kein Modell erzeugt den Zweck; er steht so im Antrag, wie der Captain oder der Vorarbeiter ihn schreibt. Die Klartext-Zeile erzeugt Code aus `erlaubt`, ohne Modell.
- Mehr als zwei Flächen, frei schwebende Fenster und Teilung über mehrere Bildschirme sind nicht Teil dieser Stufe.
- Keine Änderung an Läufen, Karten, Audit, Vorarbeiter-Freigabe.

## 4. Entscheidungen des Captains (offen)

| Nr | Frage | Vorschlag |
|---|---|---|
| HQ-1 | Zweck Pflicht oder freiwillig? | **Pflicht** (HS-60); alte Aufgaben zeigen die Klartext-Zeile (HS-62) |
| HQ-2 | Teilung: nur nebeneinander oder auch übereinander? | nur **nebeneinander** (zwei Flächen) |
| HQ-3 | Was ist mit „Master-Chat-Fenster“ gemeint: der Gesprächsreiter (zwei Sitzungen nebeneinander) oder ein fester Hauptchat mit Nebenfenster (Aufgaben, Werkstatt, Verlauf einer anderen Sitzung)? | beides durch dieselbe Teilung: jede Fläche zeigt einen beliebigen Reiter |
| HQ-4 | Ältere Sitzungen einklappen (HS-67)? | ja, nur einklappen, nie löschen |
| HQ-5 | Reihenfolge | zuerst HS-60 bis HS-67 (klein, nur Anzeige), danach HS-70 bis HS-74 (Teilung); eine Abnahme je Teil |

## 5. Berechtigungen vorab (ENTWICKLUNG.md)

Für den späteren Bau (nach G2/G3), hier schon benannt:

| Nr | Berechtigung | Begründung |
|---|---|---|
| P6-1 | Schreiben in `runtime/src/guppi_runtime/harness/aufgabe.py`, `api.py`, `vorarbeiter.py` (nur Feld `zweck`, Klartext-Zeile) | HS-60 bis HS-63 |
| P6-2 | Schreiben in `uix/shells/harness/*` (`aufgabe.js`, `seite.js`, `reiter.js`, `shell.js`, `shell.css`, neu `teilung.js`) | HS-61 bis HS-74 |
| P6-3 | Schreiben von Tests und `harness_abnahme_stufe6.py`; Browser-Prüfung ohne Modell (Playwright: das Paket fehlt in der `.venv`, **Installation nur nach Ja des Captains**) | Abnahme |
| P6-4 | Branch `harness/stufe-6`, Commits, kein Push | wie bisher |
| **nicht** | Modelle laden, Läufe mit Modell, Änderung von `local_config/`, Löschen, Push | außerhalb dieses Auftrags |

## 6. Nächste Gates

- **G1** (diese Datei): Captain beantwortet HQ-1 bis HQ-5 und gibt die Anforderungen frei.
- **G2** Design (Datenfeld `zweck`, Aufbau der zwei Flächen, Ereignisse), **G3** Bau-Aufgaben (Claude allein, wie Stufe 4 und 5), **G4** Abnahme am PC durch den Captain.
