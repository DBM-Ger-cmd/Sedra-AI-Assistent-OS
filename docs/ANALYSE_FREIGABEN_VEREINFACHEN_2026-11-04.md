# Analyse: Freigaben vereinfachen und vereinheitlichen (04.11.2026)

Auftrag des Captains (Bildschirmfoto „Aufgaben-Freigaben“): die Freigaben überarbeiten, vereinfachen, standardisieren. Dies ist eine **Bestandsaufnahme mit Vorschlag**, noch kein Umbau. Alles unter „Bestand“ ist im Code gelesen; die Ideen darunter sind Vorschläge.

## 1. Bestand: fünf Wege im Chat, dazu der Posteingang

| Nr | Weg | Wofür | Code | Wo in der Oberfläche |
|---|---|---|---|---|
| 1 | **Karte je Aufruf** | ein Werkzeugaufruf wartet auf Ja/Nein (Stufen frei, Karte, verboten; feste Vorbehalte; Warnkarten) | `harness/freigabe.py`, `uix/.../karte.js` | im Gespräch |
| 2 | **Katalog** | Regeln „Werkzeug + Muster → Stufe“ dauerhaft | `harness/katalog.py`, `katalog_editor*.js` | Einstellungen → Agent → Freigabe-Modus |
| 3 | **Sitzungs-Erlaubnis** | „Für diese Sitzung erlauben“ auf der Karte; auch die Erlaubnisse einer Vorlage beim Anlegen der Sitzung | `harness/erlaubnis.py`, `erlaubnisse.js` | Karte, Katalog-Seite unten |
| 4 | **Aufgaben-Freigabe** | Liste von Aufrufen (Werkzeug + Muster) für bestimmte Sitzungen, befristet und gezählt | `harness/aufgabe.py`, `aufgabe.js` | Reiter „Aufgaben“ (das Bild) |
| 5 | **Vorschlag des Vorarbeiters** | wie 4, vom Vorarbeiter vorgeschlagen, der Captain entscheidet | `aufgabe.py` (`vorschlag=True`) | dieselbe Seite oben |
| 6 | **Anträge (Posteingang)** | 17 Arten (`desk/decisions.py` `REQUEST_TITLE`): Katalog, Vorlage, Projekt, Code-Stand, Update, Cloud-Adresse, Wissen … | `desk/gated.py`, `decisions.py` | Posteingang |

Der Kern ist immer derselbe Satz: **Werkzeug + Muster darf laufen**. Er steht aber in drei Formen (Katalogregel, Sitzungs-Erlaubnis, Aufgabe) mit drei Oberflächen und drei Wortschätzen.

## 2. Was auf dem Bild stört

- **Fachsprache:** „Technische Muster (1)“, „Rest 3 Aufrufe · 0 Aufrufe bisher“, Zeilenformat `datei_aendern docs/spec_entwuerfe/**`.
- **Drei Nummernschritte** vor dem ersten nützlichen Klick; das Formular steht unter den aktiven Aufgaben und ist länger als der Bildschirm.
- **Sitzungsliste:** sechs fast gleiche Titel („Ich kann das Modell qwen 3,5 9b mtp nicht laden …“), ohne Zeit und ohne Vorauswahl der aktuellen Sitzung.
- **Dieselbe Sache heißt verschieden:** Erlaubnis, Aufgabe, Freigabe, Regel, Antrag, Vorbehalt.
- **Knöpfe im Posteingang** wechseln je Art („Einmal öffnen“, „Freigeben und anwenden“, „Grenze ändern …“, „Entsperren“).
- **Beobachtet (Test 04.11.):** „Sicher? Freigeben und anwenden“ fiel beim zweiten Klick zurück. Ursache gefunden: kein Neuzeichnen, sondern ein Zeitlimit von 5 Sekunden für den zweiten Klick – zu knapp, um die Rückfrage zu lesen. Jetzt 10 Sekunden.

## 3. Vorschlag: ein Begriff, ein Ort, feste Bausteine

**Ein Begriff „Erlaubnis“** mit vier Angaben, überall gleich:
1. **Was:** ein Baustein oder Werkzeug + Muster.
2. **Wo:** welche Sitzung(en) (Vorgabe: die aktuelle).
3. **Wie lange:** einmal · diese Sitzung · bis Uhrzeit/Anzahl · immer (= Katalogregel).
4. **Warum:** ein Satz (bleibt für das Audit).

Die Karte bietet dann dieselbe Leiter: **Einmal · Diese Sitzung · Immer so**. Aufgabe und Katalogregel sind nur andere Längen derselben Erlaubnis.

**Feste Bausteine** statt Zeilen mit Muster-Syntax, ein Klick je Baustein: *Tests starten · Dokumente in docs/ ändern · Neue Dateien in docs/ anlegen · Code in runtime/src ändern · Git lesen*. Die freie Zeile `werkzeug muster` bleibt unter „Erweitert“, zugeklappt.

**Ein Ort „Freigaben“** mit drei Reitern: **Wartet** (Karten und Anträge) · **Gilt gerade** (alle aktiven Erlaubnisse und Aufgaben in einer Liste, je ein Knopf „Zurücknehmen“) · **Regeln** (Katalog). Das ersetzt die verstreuten Seiten, die Inhalte bleiben.

**Eine Sprache:** Stufen *Frei · Fragen · Verboten*; Dauer *einmal · Sitzung · befristet · immer*; Knöpfe im Posteingang einheitlich *Freigeben · Ablehnen · Ansehen*, den Unterschied trägt der Text, nicht die Beschriftung.

**Unverändert, nicht verhandelbar:** `verboten`, feste Vorbehalte, Warnkarten, Schreibbereich des Projekts und alle Prüfungen im Code (`freigabe.py`, `vorbehalte.py`). Die Oberfläche wird einfacher, der Schutz nicht schwächer. Ein Formular vergibt nie mehr, als ein Klick des Captains vergeben würde.

## 4. Stufen (jede für sich lieferbar und testbar)

| Stufe | Inhalt | Aufwand | Berührt Schutzcode |
|---|---|---|---|
| **S1** | Seite „Aufgaben“ neu: Bausteine, aktuelle Sitzung vorgewählt, Liste mit Zeit, „Erweitert“ zugeklappt, Klartext statt „Rest 3 Aufrufe“ | klein | nein (nur `aufgabe.js`, `shell.css`) |
| **S2** | „Sicher?“-Fehler beheben, Posteingang: gleiche Knöpfe und Texte für alle Arten | klein bis mittel | nein |
| **S3** | Ein Ort „Freigaben“ mit den drei Reitern; die alten Einstiege verweisen dorthin | mittel | nein |
| **S4** | Gemeinsames Modell „Erlaubnis mit Dauer“ im Code (Sitzungs-Erlaubnis und Aufgabe als zwei Längen); Karte mit der Leiter Einmal · Sitzung · Immer | groß | **ja**, `aufgabe.py`, `erlaubnis.py`, `freigabe.py` |

Empfehlung: **S1 und S2 zuerst** (sofort spürbar, kein Risiko), dann S3. S4 erst nach einer Entscheidung, weil es Schutzcode umbaut und mehr Tests braucht.

## 5. Offene Entscheidungen

1. Umfang: nur S1/S2, oder bis S3, oder auch S4?
2. Sollen die **Bausteine** fest im Code stehen oder als Datei unter `local_config` editierbar sein (Vorschlag: Vorgabe im Repo, eigene Bausteine über die Datei des Captains, nie über das Modell)?
3. Soll die Dauer „immer“ auf der Karte direkt als Katalogregel angeboten werden (heute nur über den Editor)?

## 6. Stand (04.11.2026, abends)

**S1 und S2 sind gebaut und in einer Testinstanz geprüft** (Entscheidung des Captains: S1 + S2 jetzt, S3 danach; Bausteine als Vorgabe im Repo, eigene in `local_config`).

- **S1, Seite „Aufgaben“:** Bausteine zum Anklicken (`runtime/config/freigabe_bausteine.yaml`, eigene in `local_config/freigabe_bausteine.yaml`, Lesen über `GET /api/harness/bausteine`, `harness/bausteine.py`); darunter in Klartext, was erlaubt wird; die neueste Sitzung ist vorgewählt, mit Zeitangabe; Frist (Vorgabe 2 Stunden) und Aufrufe (Vorgabe 50) mit Vorgabe; Titel, Zweck, eigene Zeilen und Modelle unter „Erweitert“, leer = aus den Bausteinen; Meldungen in Klartext. „Aktiv“ heißt jetzt „Gilt gerade“, „Rest 3 Aufrufe“ heißt „noch 3 Aufrufe übrig“, „Technische Muster“ heißt „Genaue Regeln“.
- **S2:** Zeitlimit des zweiten Klicks 10 statt 5 Sekunden (Seitenleiste und Posteingang); die Seitenleiste gibt jetzt auch eine neue Vorlage und den Code-Stand direkt frei (wie ein Projekt), Regeln bleiben im Posteingang; „Genau ansehen“ und „Aufgabe öffnen“ heißen „Ansehen“ und „Vorgang ansehen“ („Aufgabe“ meint in der Harness etwas anderes).
- **Nicht geändert:** `verboten`, feste Vorbehalte, Warnkarten, Schreibbereich, alle Prüfungen im Code, und die Herkunftsprüfung der Freigabe (eine Freigabe der Klasse H bestätigt man im Sedra-Fenster, nicht in einem Browser-Pane).
- **Offen:** S3 (ein Ort „Freigaben“ mit drei Reitern), S4 (gemeinsames Modell „Erlaubnis mit Dauer“). Der Playwright-Test `test_uix_harness_browser.py` wurde an das neue Formular angepasst, aber in dieser Umgebung nicht ausgeführt (Browser-Bahn ausgelassen).
