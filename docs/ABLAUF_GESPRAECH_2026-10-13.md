# Entwurf: Ein Gespräch von der Eingabe bis zur Ausgabe bei GUPPI

Stand 13.10.2026, Entwurf von Claude, noch nicht freigegeben. Ziel des Captains: Er führt **ein Gespräch im Fenster "GUPPI Chat"**, von der Bitte ("baue mir X") bis zum Ergebnis ("X ist gebaut, geprüft und übernommen"), ohne zwischendurch in eine Claude-Sitzung zu wechseln.

## Ausgangslage

Heute läuft ein Bau in zwei Welten:

| Schritt | Heute | Wer |
|---|---|---|
| Wunsch klären, Spec mit Stufen schreiben | Claude-Sitzung | Claude |
| Versteckte Tests und Referenzlösung schreiben, Spec prüfen | Claude-Sitzung (`spec_check.py`) | Claude |
| Bauen | `devvm_build.py` | GUPPI |
| Kandidaten lesen, Mängel notieren | Claude-Sitzung | Claude |
| Übernehmen, Tests, Logbuch, Commit | Claude-Sitzung (`logbook.py`) | Claude |
| Freigaben (Gates) | Fenster "Brücke" | Captain |

Das Fenster "GUPPI Chat" (andere Sitzung, im Bau) liefert die Oberfläche: Sitzungen, Streaming, "Als Auftrag planen", Slash-Befehle. Die Brücke liefert den Missionsablauf mit Freigaben. Neu wäre nur die Verbindung dazwischen.

## Der Ablauf als Gespräch

1. **Bitte.** Der Captain schreibt im Chat, was er braucht. Das Missionssystem legt daraus einen Auftrag an ("Als Auftrag planen").
2. **Klärung.** GUPPI stellt Rückfragen, bis Ziel, Dateinamen und **konkrete Beispiele** (Eingabe → erwartetes Ergebnis) feststehen. Die Beispiele sind später die versteckten Tests.
3. **Spec-Karte.** GUPPI zeigt im Chat eine Karte: Stufen (klein, mit je einem Satz Aufgabe), die Beispiele als Tests, die Regeln. Der Captain bestätigt oder ändert im Gespräch (Gate "Spec freigeben").
4. **Vorprüfung.** Ohne GPU: Ist die Spec in sich stimmig (Lint, Beispiele widersprechen sich nicht, Saat besteht die erste Stufe nicht)? Hat der Captain eine Referenzlösung oder ein vorhandenes Modul angegeben, besteht sie alle Tests (`spec_check`)?
5. **Bau.** Gate "Bau starten" (GPU-Lease), danach streamt der Chat den Fortschritt: Stufe bestanden, Nacharbeit, Aufrufe, Zeit.
6. **Abnahme-Bericht.** GUPPI liest den Kandidaten und schreibt im Chat: was gebaut wurde, Besonderheiten (Duplikate, tote Teile), Tests grün/rot. Scheitert eine Stufe, prüft GUPPI zuerst den Test gegen den Kandidaten (`spec_check --snapshots`) und fragt im Gespräch: "Der Test erwartet X, der Code liefert Y, welches ist richtig?"
7. **Übernahme.** Gate "Übernehmen" (Kandidat → Paket, nur neue Dateien auf E1, wie heute). Der Chat bestätigt mit Logbucheintrag und Fundstelle.

Der Captain tippt nur im Chat. Freigaben stehen **nicht im Gesprächsverlauf**, sondern in der Freigabe-Leiste (nächster Abschnitt), damit sie ihn nicht aus der Unterhaltung ziehen. Im Verlauf erscheint nur eine ruhige Textzeile ("Freigabe angefragt: Bau starten, siehe Leiste" und später "Freigegeben 18:02").

## Die Freigabe-Leiste (Entscheidung des Captains, 13.10.2026, bestätigt)

Eine schmale Leiste **unter dem Gespräch**, über dem Eingabefeld (oder als kleine Seitenansicht neben dem Gespräch, wenn der Platz es zulässt; die Einstellung wird in G7 festgelegt). Sie zeigt jede offene Freigabe als kompakten Eintrag:

| Zustand | Farbe | Beschriftung | Bedeutung |
|---|---|---|---|
| wartet | **rot** | `● offen` + Titel, z. B. "Bau starten · GPU" | das Missionssystem hat ein Gate angelegt, der Captain hat noch nicht entschieden |
| freigegeben | **grün** | `✓ freigegeben` + Uhrzeit | genau dieses Gate wurde freigegeben; der Eintrag bleibt kurz sichtbar und rückt dann in eine Verlaufszeile |
| abgelehnt | grau | `✕ abgelehnt` | das Gate wurde abgelehnt |

- **Nicht nur Farbe:** Symbol und Text tragen den Zustand mit (Rot/Grün allein sind für manche Augen nicht unterscheidbar).
- **Ein Klick auf den Eintrag** öffnet eine kleine Detailansicht mit genau dem, was das Gate verlangt (Aktion, Ziel, Risiken, Bindung, wie in der Brücke heute) und die Knöpfe "Freigeben" und "Ablehnen". Erst dort wird entschieden. Es gibt kein "alles freigeben": Regel 1, jedes Gate einzeln und per ID.
- **Keine Unterbrechung:** keine Dialogfenster, kein Springen des Gesprächs. Ein kleiner Zähler am Fenstertitel zeigt, wie viele Freigaben offen sind.
- **Datenquelle:** die Gates der Mission (`human_gates.pending`); Freigabe über `/api/mission/approve`, Ablehnung über `/api/mission/reject`, wie die Brücke es heute tut.

## Was dafür gebaut werden muss

Jeder Punkt ist ein kleiner, reiner Baustein, den GUPPI nach Spec selbst bauen kann (Anteil GUPPI ≥ 50 %). Claude liefert Spec, Tests, Referenz und Abnahme.

| Nr | Baustein | Inhalt | Abhängigkeit |
|---|---|---|---|
| G0 | `test_catalog` | Katalog wiederverwendbarer Testbausteine (K01 bis K15, siehe unten), jeder mit Erzeuger, Muster und Mutante als Beweis | keine |
| G1 | `build_request` | Gesprächsergebnis (Ziel, Beispiele, Dateien) → Spec-Datei mit Stufen; die Tests entstehen aus den Beispielen (Asserts) und aus gewählten Katalogbausteinen | G0 |
| G2 | `spec_lint` | Vorprüfung ohne GPU nach den Teststandards T1 bis T8 (siehe unten): Lint wie `spec_check`, Widerspruch-Erkennung zwischen Beispielen, Saat-Probe, Mutationsprobe | G0, G1 |
| G3 | `build_runner` | Mission-Aktion "devvm_build": startet den Bau unter Gate, liest `# run ended`, liefert Stufenzeilen als Ereignisse | Missionssystem |
| G4 | `review_report` | Kandidat + Testläufe → Bericht in Klartext (Zeilen, Mängel, Diagnose bei Fehlschlag) | G3 |
| G5 | `chat_bridge` | Verbindet Chat-Sitzung ↔ Mission: Nachricht → Auftrag, Ereignisse → Chat (Streaming), ruhige Textzeilen zu Freigaben (ohne Knöpfe), Slash-Befehle `/bauen`, `/stand`, `/uebernehmen` | **Chat-Fenster fertig** |
| G6 | `adopt` | Übernahme des Kandidaten ins Paket mit Weiche-Prüfung, betroffene Tests, `logbook.add` | G4 |
| G7 | `gate_bar` | Freigabe-Leiste unter dem Gespräch: rot/grün/grau mit Symbol und Text, Detailansicht pro Gate, Zähler am Fenstertitel; reiner Rechenteil (Zustände, Sortierung, Text) getrennt vom Zeichnen | G5 |

Bis das Chat-Fenster fertig ist, bauen wir G1 bis G4 und G6 (rein, ohne Oberfläche, mit Kommandozeile zum Testen) und vom G7 den reinen Rechenteil (Gates → Leistenzeilen, mit Tests). G5 und das Zeichnen von G7 kommen danach und verbinden nur.

## Entschieden (Captain, 13.10.2026)

1. **Die Tests entstehen aus den Beispielen im Gespräch**, GUPPI macht die Asserts, der Captain bestätigt die Spec-Karte. Dazu kommt ein **Testkatalog**, damit nicht jedes Mal neue Tests erfunden werden (nächster Abschnitt).
2. **Tests werden nach Standardvorgaben geprüft**, die vorher festgelegt sind (Teststandards, übernächster Abschnitt). Der Captain wird bei einem Fehlschlag im Gespräch gefragt, nicht zum Prüfen jedes Tests.
3. **Spec und Bau haben getrennte Freigaben**, damit man planen kann, ohne die GPU zu belegen. Wunsch dazu: gleichzeitig schreiben und bauen können (Abschnitt "Schreiben während des Baus").
4. **Freigaben in der Freigabe-Leiste**, nicht im Gespräch.

5. **Freigabe-Leiste wie beschrieben bestätigt:** Standard ist die Leiste unter dem Gespräch, über dem Eingabefeld; bei breitem Fenster darf sie als kleine Seitenansicht daneben stehen. Zustände rot (`● offen`), grün (`✓ freigegeben` mit Uhrzeit) und grau (`✕ abgelehnt`), Entscheidung nur in der Detailansicht, jedes Gate einzeln per ID, kein "Alles freigeben", im Gespräch nur eine ruhige Textzeile, Zähler am Fenstertitel.

## Der Testkatalog (zu Entscheidung 1)

Ein Baustein hat eine Kennung, Parameter, einen Erzeuger (macht daraus den `assert`-Code) und einen Beweis: ein kleines Muster, das besteht, und eine Mutante, die scheitern muss. Der Anfangsbestand stammt aus den Tests dieser Sitzung, die sich ständig wiederholt haben:

| Nr | Baustein | prüft | kam vor in |
|---|---|---|---|
| K01 | Beispieltabelle | Eingabe → erwartetes Ergebnis, mehrere Zeilen | bench_std, alle Specs |
| K02 | Argumente unverändert | Eingabe vor und nach dem Aufruf tief gleich | skill_unify, skill_rank, skill_digest |
| K03 | Leer, None, fehlend | `None`, `""`, `[]`, fehlende Schlüssel ohne Ausnahme | skill_rank, skill_digest |
| K04 | Grenzen | 0, 1, Maximum, Maximum + 1, Zahl als Text | skill_rank (`limit`) |
| K05 | Feste Reihenfolge bei Gleichstand | gleiche Wertung → Ordnung nach Kennung | skill_rank, skill_unify |
| K06 | Gleiche Eingabe, gleiches Ergebnis | zweimal aufrufen, gleiches Ergebnis | alle reinen Funktionen |
| K07 | Ausnahme mit Text | Typ und Meldung der Ausnahme | bench_std (`fix`) |
| K08 | Eingabereihenfolge bleibt | stabile Ausgabe | skill_unify (`merge_index`) |
| K09 | Zahlen mit Toleranz | `near(a, b)` statt `==` bei Gleitkomma | skill_rank2 |
| K10 | Datei-Ergebnis | Ort, genau eine Datei, Überschriften in fester Reihenfolge, Pflichtzeilen | skill_need (adr, spec, plan) |
| K11 | Textformat | erste Zeile nach Muster, Höchstlänge, Leerzeile, Begründung | skill_need (commit) |
| K12 | Reiner Baustein | importierbar im leeren Ordner, kein Datei-, Prozess-, Netzzugriff | alle NOTES |
| K13 | Ausgabe begrenzt | Zeilen- oder Zeichengrenze mit festem Marker | skill_digest, skill_library |
| K14 | Bauform | keine Kommentare und Docstrings, Importe oben, keine ungenutzten Namen (Quelltextprüfung mit `ast`) | bisher nur im Review |
| K15 | Vorstufen gelten weiter | der Test einer Stufe enthält den der Stufe davor | alle Specs mit Stufen |

**So benutzt G1 ihn:** Aus der Signatur und den Beispielen wählt GUPPI Bausteine (eine Funktion mit Liste → K02, K03, K05; eine Datei als Ergebnis → K10; jede Funktion → K06, K12, K14). Die Spec-Karte zeigt sie als Häkchenliste ("geprüft wird: 4 Beispiele · Argumente unverändert · leere Eingaben · …"); der Captain kann Bausteine ein- oder ausschalten. Neue Bausteine kommen dazu, wenn ein Test in zwei Specs vorkommt.

## Die Teststandards (zu Entscheidung 2)

Vorgaben, die jede Spec automatisch bestehen muss, bevor der Captain die Karte sieht (G2, erweitert `spec_check`):

| Nr | Standard | ohne Referenz prüfbar |
|---|---|---|
| T1 | Der Test ist gültiger Python-Text und läuft ohne Ausnahme außer den Asserts | ja |
| T2 | Jeder Katalogbaustein besteht auf seinem Muster und scheitert auf seiner Mutante | ja (Beweis liegt im Katalog) |
| T3 | Die Beispiele widersprechen sich nicht (gleiche Eingabe, verschiedene Ausgabe) | ja |
| T4 | Die erste Stufe scheitert auf der Saat oder dem leeren Ordner | ja |
| T5 | Keine `or`-Asserts ohne Kennzeichnung, keine verketteten `and` (eine Aussage je Assert) | ja |
| T6 | Keine Uhrzeiten, kein Zufall, kein Netz, keine absoluten Pfade | ja |
| T7 | Stufentests sind kumulativ und nutzen nur Regeln dieser und früherer Stufen | nur mit Muster |
| T8 | Mutationsprobe: einige Standard-Mutanten des Musters (Konstante ändern, Vergleich umdrehen, `None` zurückgeben) bringen jeweils mindestens einen Assert zum Scheitern | nur mit Muster |

Ohne Muster oder Referenz sind T7 und T8 nicht prüfbar. Das zeigt die Spec-Karte offen an ("Test nicht gegen ein Muster geprüft"), und nur dann trägt der Captain mit der Bestätigung die Verantwortung. Scheitert nach dem Bau eine Stufe, diagnostiziert `spec_check --snapshots`, ob der Test eine spätere Regel braucht; GUPPI fragt dann im Gespräch.

## Schreiben während des Baus (zu Entscheidung 3)

Spec, Klärung und Vorprüfung brauchen **keine GPU**, abgesehen vom Chat-Modell selbst. Der Haken: Chat-Modell und Bau-Modell teilen sich die eine 12-GB-Karte, und die Lease erlaubt nur einen Modellprozess. Drei Wege:

| Weg | Prinzip | Kosten / Risiko |
|---|---|---|
| A Warteschlange | Nachrichten werden angenommen und gespeichert; die Statuszeile antwortet sofort mit dem Stand des Baus, GUPPI antwortet inhaltlich nach dem Bau | einfach, sicher; man wartet |
| B zweiter Slot im Bau-Server | der Chat spricht mit demselben Modell (`np 2`, kleines Fenster) | VRAM-Spitze (Grenze 11,5 GB) und Tempo des Baus müssen gemessen werden |
| C kleines Modell auf CPU | der Chat antwortet unabhängig von der GPU | langsam, kleineres Modell |

Empfehlung: **A zuerst** (kein Risiko für Bau und Messungen), B messen. Die Agenten arbeiten im Hintergrund; der Chat zeigt Statuszeilen aus dem Bau und nimmt weiter Eingaben an.

## Reihenfolge

1. Fertig: Werkzeuge (`spec_check`, `ab_queue`, `logbook`), Bibliotheken aus einer Datei, Rezept in ENTWICKLUNG.md.
2. G0 (`test_catalog`) mit K01 bis K15 und Beweisen: zuerst, weil G1 und G2 darauf bauen. Spec und Referenz schreibt Claude, GUPPI baut.
3. G1, G2, G3, G4, G6 und der Rechenteil von G7 als Specs an GUPPI.
4. Messung Weg B (zweiter Slot) für das Schreiben während des Baus.
5. Wenn "GUPPI Chat" fertig ist: G5, Zeichnen von G7 und ein erster durchgehender Probelauf mit einer kleinen echten Aufgabe.
