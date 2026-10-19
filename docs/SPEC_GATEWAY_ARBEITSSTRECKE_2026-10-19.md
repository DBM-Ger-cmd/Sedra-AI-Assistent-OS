# Spezifikation: KI GateWay – einheitliche Arbeitsstrecke, Regelbuch und Regel-Vorgaben

**Stand:** 19.10.2026
**Art:** nur Spezifikation. Kein Code. Jeder Punkt braucht die Freigabe des Captains, bevor er umgesetzt wird.
**Bezug:** `docs/SPEC_GATEWAY_VORGANG_v1.md`, `docs/PLAN_ISOLATION_UND_UPDATE_2026-10-19.md` (Stufe B und C der Modul-Isolation), `runtime/src/guppi_runtime/gateway/klassen.py` (Regelbuch R-01 bis R-16), `runtime/src/guppi_runtime/core/b6core/pseudo.py` (Platzhalter).

---

## 1. Ziel

Ein Dokument oder eine Anfrage geht durch **eine** Strecke, vom Hochladen bis zur gespeicherten, geprüften Fassung. Jeder Schritt ist sichtbar, jede Änderung an Text oder Regeln ist nachvollziehbar, und das Regelbuch ist dort erreichbar, wo man es braucht.

## 2. Ausgangslage (aus dem Screenshot und dem Code)

- Das Regelbuch steht heute als **rechte Spalte** im Gateway (Titel „Regelbuch“, Policy `b6-datenregeln-0.1`, Regelwerk v0.1, 16 Regeln, Suchfeld, Regelkarten R-01 bis R-16). Es ist nur lesbar und hängt an keinem Schritt.
- Dokumente hochladen geht seit `v1.21.0` über „Datei hochladen“ neben der Dokumentauswahl. Eine Vorschau gibt es nicht.
- Die Pseudonymisierung ersetzt Personen, Firmen, E-Mails, Telefonnummern, Kundennummern, Adressen, Rollen und Begriffe (`PERSON`, `COMPANY`, `EMAIL`, `PHONE`, `CUSTOMER_ID`, `ADDRESS`, `ROLE`, `TERM`). **Ortsnamen gibt es als eigenen Typ nicht.** Der Prüfbefund im Screenshot-Beispiel („Beierswerder“ als Firma) zeigt: Eine Firma wird ersetzt, ein Ort wie „Beierswerder“ nur, wenn die Erkennung ihn als Firma oder Adresse sieht.
- Die Platzhalter werden in `core/b6core/pseudo.py` vergeben. Eine neue Art (z. B. `LOCATION`) bräuchte dort eine Änderung.

## 3. Die Arbeitsstrecke (ein Ablauf für Dokument und Anfrage)

Die Strecke hat vier Stufen und eine Menüführung. Die bestehende Nummerierung der Stationen (01 bis 04) bleibt, wird aber um die Vorschau und den Bearbeitungsmodus ergänzt.

| Stufe | Name | Was der Nutzer sieht | Was passiert |
|---|---|---|---|
| 1 | **Hochladen** | Dateiauswahl, Liste der Eingänge | Datei kommt in den Eingang (`local_config/gateway/eingang`), wird nicht verändert. |
| 2 | **Vorschau** | Der Text der Datei, unverändert, mit farbigen Markierungen für jede erkannte Stelle und ihre Regel (R-xx) | Nur Anzeige. Keine Änderung, kein Modellaufruf. |
| 3 | **Bearbeiten** | Der Text, eine Liste der Fundstellen, Regel-Vorgaben (siehe Abschnitt 5) | Der Nutzer legt Ersetzungen fest. Jede Änderung wird als Vorschlag gespeichert, nicht sofort angewendet. |
| 4 | **Speichern unter** | Vorschlag „Name_anonymisiert.txt“ (bzw. .md/.docx), Ziel im Eingang | Die Fassung wird neu geschrieben, das Original bleibt unverändert. Erst danach ist sie für einen Vorgang wählbar. |

Danach läuft der Vorgang wie bisher: Prüfen, Freigabe, Entwurf, Prüfung. Die gespeicherte Fassung ist die Grundlage der Prüfung, nicht das Original.

**Regel:** Das Original wird nie überschrieben. Die anonymisierte Fassung hat einen eigenen Namen und einen Verweis auf das Original (Prüfsumme).

## 4. Das Regelbuch als Menüpunkt

- **Platz:** Die rechte Spalte („Regelbuch“) wird entfernt. Das Regelbuch wird ein Menüpunkt im Gateway, zum Beispiel „Regelbuch“ neben „Vorgänge“ und „Eingang“, mit Such- und Filterfeld wie heute.
- **Verwendung in der Strecke:** In Stufe 2 (Vorschau) und Stufe 3 (Bearbeiten) ist ein Link „Regel ansehen“ bei jeder Markierung. Er öffnet die Regelkarte im Menü, ohne die Strecke zu verlassen.
- **Anzeige:** Wie heute: Kategorie, Cloud-Status, Merkmal, Prüfpflicht, „Was tun“, Rechtsbezug (als Annahme gekennzeichnet).
- **Ändern:** Das Regelbuch selbst ändern ist keine Aufgabe dieser Strecke. Es bleibt bei der Versionierung des Regelwerks (neue Zeilen, neue Version, Freigabe durch den Captain).

## 5. Regel-Vorgaben im Bearbeitungsmodus

Der Nutzer legt fest, **wie eine Fundstelle behandelt wird**. Die Vorgaben gelten für alle Vorkommen der Fundstelle im Dokument und werden gemerkt, wenn der Nutzer sie als Standard speichert.

### 5.1 Arten einer Vorgabe

| Vorgabe | Bedeutung | Beispiel |
|---|---|---|
| **Ersetzen durch Platzhalter** | Die Fundstelle wird durch einen festen Platzhalter ersetzt, der immer gleich bleibt. | „Bürostuhl AG“ → `<COMPANY_001>` |
| **Immer anonymisieren** | Wie oben, aber als Standard für diese Art von Fundstelle (z. B. alle Ortsnamen). | Ortsnamen → `<ORT_001>` (siehe Abschnitt 6, offene Frage) |
| **Behalten** | Die Fundstelle bleibt, mit Begründung. Nur wenn die Regel das zulässt; R-01 (Personenbezug) bleibt lokal. | Ein Produktname, der keine Person ist |
| **Entfernen** | Die Stelle wird gelöscht und im Protokoll vermerkt. | Eine Kontonummer (nur wenn die Regel das verlangt) |

Keine Vorgabe kann eine Sperre der Regeln aufheben. Eine Fundstelle, die das Regelbuch sperrt (R-07 Zugangsdaten, R-08 Anweisungen im Dokument), wird nicht „behalten“, sondern bleibt gesperrt, bis sie aus dem Text entfernt ist.

### 5.2 Bedienung

1. Der Nutzer klickt eine Markierung an oder wählt sie aus der Fundstellenliste.
2. Auswahl der Vorgabe (Dropdown), bei „Ersetzen“ ist der Platzhalter-Typ vorgeschlagen (z. B. `COMPANY` bei Firmen).
3. Häkchen: „Für alle gleichen Stellen im Dokument“ (Standard: ja) und „Als Regel merken“ (Standard: nein).
4. Die Vorschau aktualisiert sich sofort, das Original bleibt sichtbar daneben.

### 5.3 Speicherung der Vorgaben

- Gemerkte Vorgaben liegen in `local_config/gateway/vorgaben_text.yaml`, nicht in git (machine-lokal, wie die Schalter).
- Jede gemerkte Vorgabe hat: Suchmuster (genauer Text oder Muster), Vorgabeart, Platzhalter-Typ, Datum, wer sie angelegt hat.
- Eine gemerkte Vorgabe wirkt auf neue Dokumente nur als **Vorschlag**, die Stelle wird markiert, nicht still ersetzt. Der Nutzer bestätigt.

## 6. Entscheidungen des Captains (2026-10-19)

1. **Ortsnamen:** Ja, es gibt einen eigenen Platzhalter `ORT` mit Regel R-17 (Regelwerk Version 0.2). Die Erkennung und `core/b6core/pseudo.py` werden dafür erweitert. Umsetzung nach Freigabe dieser Spezifikation.
2. **Gemerkte Vorgaben:** global, mit Anzeige, in welchen Dokumenten und Vorgängen sie wirken.
3. **Originale und Ordner:** Das Original bleibt im Eingang, mit Vermerk „Original, nicht gesendet“. Zum Arbeiten wird eine Kopie angelegt. Bearbeitete Fassungen wandern in den Ordner **Ausgang**. Dort liegen nur Dokumente, die anonymisiert und geprüft sind, als „bereit zur Verarbeitung mit externen Quellen“.

**Ablage (aus Entscheidung 3):**

| Ordner | Inhalt | Regel |
|---|---|---|
| `Eingang` | Originale, unverändert, mit Vermerk | nie bearbeitet, nie gelöscht |
| `Eingang/Arbeitskopien` | Kopie eines Originals zum Bearbeiten | wird nach dem Speichern als Ausgabe übernommen |
| `Ausgang` | anonymisierte, geprüfte Fassungen | nur mit Prüfvermerk und Prüfsumme des Originals |

Der Vermerk im Ausgang nennt das Original (Dateiname, Prüfsumme), die angewendeten Vorgaben und den Zeitpunkt. So ist immer nachvollziehbar, woher eine Fassung stammt, egal wo das Original liegt.

## 6b. Ortsnamen: Regeln statt Rückfragen (Stand 19.10.2026)

Ziel: Die Regeln entscheiden anhand der Formulierung. Niemand wird bei jedem Ortsnamen gefragt. Die Regeln blockieren nie; sie ersetzen oder lassen stehen, und die Vorschau zeigt, was passiert ist.

**Regel O-1: Anschrift ersetzen.** Ein Ortsname wird ersetzt, wenn er Teil einer Anschrift ist oder den Wohnort einer Person angibt. Erkennungsmerkmale: Straßenwort (Straße, Str., Weg, Platz, Gasse, Allee), Hausnummer, PLZ, sowie Wohnbezug („ich wohne in“, „wohnhaft in“, „lebt in“, „Adresse“, „Lieferadresse“, „aus“ bei einer genannten Person). Beispiel: „Ich wohne in der Hauptstraße 1 in DEF“ → Straße und Ort werden ersetzt.

**Regel O-2: Ereignis oder Thema behalten.** Ein Ortsname bleibt, wenn der Satz ein Ereignis, eine Auskunft oder ein Thema beschreibt und keine Person an den Ort gebunden ist. Erkennungsmerkmale: „in DEF passiert“, „es hat geknallt in DEF“, „Wetter in DEF“, „Verkehr in DEF“, „Öffnungszeiten in DEF“, „ob etwas passiert ist“. Beispiel: „Gestern Abend hat es in DEF geknallt, ich wollte wissen, ob etwas passiert ist“ → DEF bleibt, die Frage ist beantwortbar.

**Regel O-3: Unklar, keine Blockade.** Trifft keine der beiden Regeln zu, bleibt der Ortsname stehen und wird in der Vorschau als „Ort unbewertet“ markiert. Es gibt keine Rückfrage vor dem Speichern. Die Vorschau zeigt die Markierung; eine Vorgabe (ersetzen oder behalten) kann sie jederzeit ändern.

**Vorgaben wirken vor den Regeln:** Eine gemerkte Vorgabe für einen Ortsnamen (z. B. „DEF immer behalten“) gilt vor O-1 bis O-3 und wird in der Vorschau als Vorgabe ausgewiesen.

**Grenze, die im Vermerk steht:** Ein stehen gelassener Ortsname ist keine Anonymisierung. Zusammen mit anderen Angaben kann er jemanden erkennbar machen. Deshalb zeigt die Vorschau die Zahl der stehen gelassenen Ortsnamen, und der Vermerk nennt die angewendete Regel (O-1, O-2 oder Vorgabe).

**Offen (für den Captain):** Soll O-3 beim Speichern eine einmalige Bestätigung verlangen, wenn ein unbewerteter Ortsname im Text vorkommt? *Empfehlung:* nein, nur als Hinweis in der Vorschau; Blockaden bleiben den Sperren des Regelwerks vorbehalten.


**Entschieden (2026-10-19):** O-3 markiert nur, es wird nicht gefragt. Später nachschärfbar.

**Behalten als Vorgabe:** Jede Fundstelle kann im Bearbeiten-Modus als „Behalten“ markiert werden. Die Vorgabe „Behalten“ wirkt nur für Ortsnamen, nie für Sperren (R-07, R-08).

**Rückübersetzung:** Eine Antwort mit `<ORT_001>` wird wie bei anderen Platzhaltern zurückübersetzt. Ortsfragen ohne Personenbezug bekommen den Ort im Original und brauchen deshalb keine Rückübersetzung.

**Offen (für den Captain):** Reicht die Erkennung über Anschrift-Merkmale (Straße, PLZ, Hausnummer), oder soll jede Ortsnennung in einem Satz mit einer Person als „unklar“ (Stufe 3) gelten?

## 6a. Offene Fragen an den Captain (nach Entscheidung)

4. **Speichern unter:** Welche Endungen sind erlaubt? *Empfehlung:* .md und .txt sofort; .docx nur, wenn der Text unverändert übernommen wird.
5. **Vorschau von .docx:** Nur der Text, ohne Formatierung (MVP).

## 7. Sicherheit und Datenschutz

- Die Vorschau und die Bearbeitung erreichen **kein Modell**. Die Strecke ist rein lokal, bis der Vorgang freigegeben wird.
- Die Platzhalter-Zuordnung (Platzhalter → Original) bleibt im Prozess und wird nicht gespeichert (wie bisher). Die gespeicherte Fassung enthält nur die Platzhalter.
- Jede Vorgabe und jedes Speichern steht im Audit (Ereignis, Dateiname, Prüfsumme, Vorgabeart; **nie** der Text).
- Eine Fundstelle, die eine Sperre auslöst, kann nicht über die Bearbeitung freigegeben werden.
- Die Stufen B und C der Modul-Isolation (siehe Plan) betreffen das Gateway: Die Strecke läuft im Kern-Rahmen, nicht in einem Modul mit Freigaberechten.

## 8. Abnahme (wann die Strecke fertig ist)

1. Eine Datei hochladen, eine Vorschau sehen, eine Fundstelle durch `<COMPANY_001>` ersetzen, „Für alle gleichen Stellen“ anwenden, speichern unter einem neuen Namen. Das Original ist unverändert (Prüfsumme gleich).
2. Eine Vorgabe „Immer anonymisieren“ merken; bei einem zweiten Dokument erscheint die Stelle als Vorschlag, nicht als stille Ersetzung.
3. Das Regelbuch ist im Menü erreichbar, nicht mehr rechts im Gateway. Aus der Strecke heraus öffnet „Regel ansehen“ die passende Karte.
4. Eine gesperrte Fundstelle (R-07) lässt sich nicht als „behalten“ markieren.
5. Das Audit enthält die Ereignisse ohne Text.
6. Ende-zu-Ende-Test: Hochladen, Vorschau, Bearbeiten, Speichern, Vorgang bis zur Prüfung.

## 9. Reihenfolge

1. Regelbuch in den Menüpunkt verschieben (klein, ohne Logik-Änderung).
2. Vorschau mit Markierungen (klein).
3. Bearbeitung und Vorgaben für eine Fundstelle (mittel).
4. Gemerkte Vorgaben als Vorschläge (mittel).
5. Platzhalter „ORT“ und Regel R-17, nach Freigabe der offenen Frage 1 (mittel).
6. Speichern unter mit Prüfsumme und Audit (klein bis mittel).

Stufe B und C der Modul-Isolation laufen getrennt (siehe `docs/PLAN_ISOLATION_UND_UPDATE_2026-10-19.md`, Abschnitt 5).
