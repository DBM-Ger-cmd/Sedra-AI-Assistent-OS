# SPEC Harness-Shell Stufe 6 – G1 Anforderungen: Verständlichkeit und geteilte Ansicht (30.10.2026)

Anlass: Abnahme am PC durch den Captain, 30.10.2026 12:10. Befund: „Das passt soweit, aber bei den Aufgaben weiß man nicht, was dort gemacht wird; es wird eine Beschreibung kurz und knapp benötigt. Bei Projekten weiß man auch nicht, was man machen soll. Hier fehlt die Bildschirmteilung des Master-Chat-Fensters.“ Präzisiert (12:50): „rechts die Unterhaltung, links die entsprechende Vorschau, mit der Option zum Tauschen, und das Ganze läuft in einem Reiter-Fenster.“
Stufen 4 und 5 sind in dieser Abnahme bis auf diese drei Punkte bestanden (Einstellungen, Benachrichtigungen, Grenzen der Schleife, Statusleiste mit GPU-Zelle). Nichts davon ist gebaut; diese Datei ist G1.

## 1. Befund

| Nr | Was der Captain sieht | Ursache im Code |
|---|---|---|
| B1 | Reiter „Aufgaben“: Karten mit Titel, ID, Sitzungen und Zeilen wie `lauf_starten · run_tests`. Was die Aufgabe **bewirkt**, steht nirgends in einem Satz. | Die Aufgabe hat nur `titel`, `erlaubt` (Werkzeug + Muster) und `ende`; es gibt kein Beschreibungsfeld (`harness/aufgabe.py`, `aufgabe.js`). |
| B2 | Seitenleiste „Projekte“: Ein Projekt mit vielen alten Sitzungen, keine Erklärung, was ein Projekt ist, was man dort tut, was der Vorarbeiter-Knopf macht. | `seite.js` zeigt nur die Liste; kein Leerzustand, keine Hilfe. |
| B3 | Im Gespräch sieht man nur den Text. Woran der Agent arbeitet (Datei, Karte, Lauf, Seite), steht nicht daneben; man muss den Reiter wechseln. | HS-01: genau eine Arbeitsfläche je Reiter; die Vorschau gibt es nicht. |

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

### 2.3 Gespräch mit Vorschau in einem Reiter (zu B3; Auslegung des Captains 30.10.2026 12:50)

Gemeint ist **keine** Teilung der ganzen Arbeitsfläche, sondern ein Sitzungsreiter in zwei Hälften: **rechts läuft die Unterhaltung, links steht die dazu passende Vorschau**, mit einem Knopf zum **Tauschen** der Seiten. Alles bleibt in **einem** Reiter.

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-70 | Ein Sitzungsreiter hat zwei Flächen: **Gespräch** (rechts, Voreinstellung) und **Vorschau** (links). Ein Knopf in der Reiterzeile (Tooltip „Seiten tauschen“, Tastenkürzel Strg+Umschalt+X) vertauscht sie; die Wahl gilt je Reiter und bleibt im Browser erhalten. Ein weiterer Knopf klappt die Vorschau zu (dann füllt das Gespräch den Reiter, wie heute). | Test der Shell |
| HS-71 | Die Vorschau zeigt **das Objekt, um das es im Gespräch gerade geht**, und folgt ihm von selbst: die zuletzt geschriebene oder geänderte Datei (als Text oder Diff), eine offene Freigabe-Karte mit ihrer Vorschau, ein laufender oder beendeter Lauf (Fortschritt, Ausgabe), eine geöffnete App oder Seite. Eine Zeile über der Vorschau nennt, was sie zeigt und warum („Datei docs/x.md – eben geändert“). | Test: nach `datei_schreiben` zeigt die Vorschau die Datei; bei offener Karte die Karte |
| HS-72 | Der Captain kann die Vorschau **festhalten** (Pin): dann folgt sie nicht mehr; ein Klick auf eine Werkzeugzeile im Gespräch oder auf einen Dateinamen öffnet das Objekt in der Vorschau. Vorschau und Gespräch scrollen unabhängig. | Test |
| HS-73 | Die Vorschau **ändert nichts**: sie liest nur (Anzeige); Freigeben, Ablehnen, Stoppen laufen weiter über die vorhandenen Karten und Wege (Herkunft, Katalog, Vorbehalte unverändert). Inhalte kommen über dieselben Lesewege wie `datei_lesen` (Vorbehalte gelten: gesperrte Dateien werden nicht angezeigt). | Test: gesperrte Datei zeigt „nicht anzeigbar“ |
| HS-74 | Breite: Mindestbreite je Fläche 420 px, Trennbalken ziehbar (Voreinstellung 50/50). Unter 1100 px Gesamtbreite zeigt der Reiter nur eine Fläche mit einem Umschalter Gespräch/Vorschau (HS-05 gilt unverändert). Bei 1024×700 kein waagerechtes Rollen. | uix_check bei 1024×700 und 1400×860 |
| HS-75 | Eine leere Sitzung (Figur SEDRA, HS-04) hat keine Vorschau, bis es ein Objekt gibt; die Vorschau blendet sich dann mit einem Satz ein („Hier erscheint, woran ich arbeite“). Pro Reiter eine Vorschau, nie dieselbe Sitzung in zwei Reitern gedoppelt. | Test |

### 2.4 Handlung statt Verweis (Nachtrag des Captains 30.10.2026 15:30)

Anlass: Im Eingabebereich stand „Kein Modell geladen – Modell wählen (Start → Modelle → Werkstatt …)“. Regel: **Wo gehandelt werden kann, steht kein Verweis, sondern die Handlung selbst**, wie in der Taskleiste.

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-80 | Fehlt das Modell, zeigt der Eingabebereich statt des Verweises eine Steuerung: Rezept wählen (Vorgabe: zuletzt geladenes), „Laden“, Zustand („lädt … kann Minuten dauern“); Fehler des Servers (z. B. zu wenig Speicher) erscheinen als Satz an derselben Stelle. | Test der Shell |
| HS-81 | Das Feld „Modell“ im Eingabebereich ist ein Knopf: Klick öffnet dieselbe Steuerung mit „Wechseln“ und „Entladen“. Dieselben Wege wie die Werkstatt (`/api/model/load`, `/api/model/unload`); Gates und Prüfungen bleiben beim Server. Meldungen im Verlauf („Kein Modell geladen“) öffnen die Steuerung, statt auf Menüs zu verweisen. | Test der Shell |

### 2.5 Dateien anhängen (Captain 30.10.2026 15:55: „anhängen bauen“)

„+“ und „@“ im Eingabefeld versprachen „kommt mit Stufe 2“. Jetzt tun sie, was sie sagen.

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-82 | „+“ öffnet eine Auswahl der Projektdateien: Suchfeld, Ordneransicht mit Pfadleiste, Klick auf einen Ordner geht hinein, Klick auf eine Datei fügt `@pfad` an der Schreibmarke ein; mehrere Dateien nacheinander, „Fertig“ oder Esc schließt. | Test der Shell |
| HS-83 | Der Weg `GET /api/harness/dateien?projekt=&ordner=&q=` nennt **nur Namen** (kein Inhalt) und nur, was die Einstufung von `datei_lesen` zulässt (Katalog `verboten` und feste Vorbehalte erscheinen nicht); er bleibt im Projektordner, folgt keinen Verknüpfungen und überspringt `.git`, Umgebungen, `runtime_data`, `engines`; höchstens 40 Treffer je Suche. | Test: gesperrte Dateien fehlen, `..` wird abgelehnt |
| HS-84 | Tippt der Captain `@wort`, erscheinen unter dem Feld bis zu 8 passende Dateien; ein Klick ersetzt das Wort durch `@pfad`. | Test der Shell |
| HS-85 | Der Systemprompt sagt dem Modell, dass `@pfad` eine angehängte Datei ist, die es mit `datei_lesen` lesen soll; gelesen wird mit der üblichen Einstufung (Karten wie sonst). Es wird **nichts** vorab ins Gespräch kopiert. | Test des Prompts |

## 3. Abgrenzung

- Keine neue Rolle, kein neues Recht: Zweck und Klartext sind **Anzeige**; über Deckung und Freigabe entscheiden weiter nur `erlaubt`, Katalog und Vorbehalte. Der Zweck deckt nichts (HS-27 unverändert).
- Kein Modell erzeugt den Zweck; er steht so im Antrag, wie der Captain oder der Vorarbeiter ihn schreibt. Die Klartext-Zeile erzeugt Code aus `erlaubt`, ohne Modell.
- Keine Teilung der ganzen Arbeitsfläche in zwei Reiter, keine frei schwebenden Fenster, keine Vorschau über mehrere Bildschirme; die Vorschau bearbeitet nichts (HS-73).
- Keine Änderung an Läufen, Karten, Audit, Vorarbeiter-Freigabe.

## 4. Entscheidungen des Captains (offen)

| Nr | Frage | Vorschlag |
|---|---|---|
| HQ-1 | Zweck Pflicht oder freiwillig? | **Pflicht** (HS-60); alte Aufgaben zeigen die Klartext-Zeile (HS-62) |
| HQ-2 | Was zeigt die Vorschau von selbst? | Datei/Diff, offene Karte, Lauf, geöffnete App – das Objekt, das das Gespräch zuletzt berührt hat (HS-71), mit Festhalten (HS-72) |
| HQ-3 | Voreinstellung: Gespräch rechts, Vorschau links, Vorschau beim Start eingeklappt oder offen? | Gespräch **rechts**, Vorschau **links**, **offen** sobald es ein Objekt gibt (HS-75), jederzeit zuklappbar |
| HQ-4 | Ältere Sitzungen einklappen (HS-67)? | ja, nur einklappen, nie löschen |
| HQ-5 | Reihenfolge | zuerst HS-60 bis HS-67 (klein, nur Anzeige), danach HS-70 bis HS-75 (Vorschau); eine Abnahme je Teil |

## 5. Berechtigungen vorab (ENTWICKLUNG.md)

Für den späteren Bau (nach G2/G3), hier schon benannt:

| Nr | Berechtigung | Begründung |
|---|---|---|
| P6-1 | Schreiben in `runtime/src/guppi_runtime/harness/aufgabe.py`, `api.py`, `vorarbeiter.py` (nur Feld `zweck`, Klartext-Zeile) | HS-60 bis HS-63 |
| P6-2 | Schreiben in `uix/shells/harness/*` (`aufgabe.js`, `seite.js`, `reiter.js`, `shell.js`, `shell.css`, `verlauf.js`, neu `vorschau.js`) | HS-61 bis HS-75 |
| P6-3 | Schreiben von Tests und `harness_abnahme_stufe6.py`; Browser-Prüfung ohne Modell (Playwright: das Paket fehlt in der `.venv`, **Installation nur nach Ja des Captains**) | Abnahme |
| P6-4 | Branch `harness/stufe-6`, Commits, kein Push | wie bisher |
| **nicht** | Modelle laden, Läufe mit Modell, Änderung von `local_config/`, Löschen, Push | außerhalb dieses Auftrags |

## 6. Nächste Gates

- **G1** (diese Datei): **freigegeben vom Captain am 30.10.2026**, HQ-1 bis HQ-5 wie vorgeschlagen.
- **G2** Design (Datenfeld `zweck`, Aufbau der zwei Hälften im Reiter, Folgen des Objekts, Ereignisse), **G3** Bau-Aufgaben (Claude allein, wie Stufe 4 und 5), **G4** Abnahme am PC durch den Captain.
