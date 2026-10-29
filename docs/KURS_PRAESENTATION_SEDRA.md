# SEDRA / GUPPI – Material für die Kurspräsentation

Stand 28.10.2026. Alle Zahlen stammen aus dem Repository (`docs/LOGBUCH_AGENT_MANAGER.md`, `docs/ARCHITEKTUR.md`, `docs/MODELLE.md`, `docs/MESSBERICHT_SLOTS_2026-10-23.md`, `docs/CHANGELOG.md`, `git log`) oder aus den Projektnotizen. Wo etwas unklar oder nur vermutet ist, steht „(Vermutung)“ oder „(unklar)“. Der „Captain“ ist die menschliche Entscheidungsrolle im Projekt.

**Kennzahlen auf einen Blick**

| Größe | Wert | Quelle |
|---|---|---|
| Commits im Git-Verlauf | 402, zwischen 15.10. und 28.10.2026 | `git log` |
| Python-Quellcode `runtime/src` | rund 54.900 Zeilen | gezählt mit `wc` |
| Testdateien in `runtime/tests` | 257 | gezählt |
| Tests in den Gruppen scheduler/desk/orchestra/uix | 1049 grün (Stand 28.10.) | Auftrag; im Logbuch 1005 am 27.10. früh, 1047 nach dem UIX-Merge |
| Lokale Modelle (Beispiele) | Qwen3.6-35B-A3B, Qwen3.5-9B (mit MTP), Gemma-4-12B | `docs/MODELLE.md` |
| Grafikkarte | RTX 4070 Ti, 12 GB VRAM | `docs/MODELLE.md` |

Hinweis: Der Git-Verlauf beginnt am 15.10.2026. Das Logbuch reicht aber bis zum 4. bis 7.10. zurück (Arbeit vor dem Git-Verlauf, lokale Versionsverwaltung ab 7.10.).

---

# Teil 1 – Folienvorschlag (14 Folien)

## Folie 1 – Titel: SEDRA/GUPPI – ein lokaler KI-Assistent, der den Menschen entscheiden lässt
- Projekt im Selbstversuch: KI-Agenten bauen und betreiben ein KI-System auf einem einzelnen PC
- Zeitraum der Dokumentation: Oktober 2026 (gut drei Wochen)
- Leitfrage: Wie viel darf eine KI selbst tun, und wo muss der Mensch entscheiden?

*Sprechernotiz:* Kurz vorstellen, dass es ein Praxisprojekt ist und die Zahlen aus echten Messläufen stammen. Die Leitfrage zieht sich durch den ganzen Vortrag.

## Folie 2 – Zweck und Grundidee
- GUPPI ist die Laufzeit (Python-Paket `guppi_runtime`), SEDRA die Oberfläche und Produktlinie darum
- „Local First, Cloud Second“: Modelle laufen lokal; Cloud nur über Router, Inhaltsschutz und GateWay, sichtbar und mit Budget
- Ziel laut Entwicklungsdokument: GUPPI soll sich selbst erweitern, immer hinter der Freigabe des Captains
- Ziel der Agenten-Orchestrierung: mehrere KI-Agenten arbeiten wie ein kleines Team (Rollen, Aufgaben, Budgets)

*Sprechernotiz:* Der Name GUPPI ist die Laufzeit, SEDRA das Gesamtprodukt. „Captain“ ist die Rolle des menschlichen Entscheiders (Begriff im Projekt, nicht eine Person im Kurs).

## Folie 3 – Architektur im Überblick
- Kern (rund 1.200 Zeilen): Mission mit Zustandsautomat, Brain, Message-Bus, Guard, Audit, Step-Journal
- Jobs und Ressourcen: Job-Supervisor, Ressourcen-Scheduler (VRAM/RAM/KV-Cache), GPU-Lease
- Modelle: Rezepte je Rolle, eigener `llama-server`, GPU-Selbsttest (Canary), sicheres Entfernen
- Selbstentwicklung: Bau in einer microVM, Stufen E1 bis E3, Kandidaten mit Abnahme
- Oberfläche: Desk (Objekte + Verben), Shells, Server `uix_server`

*Sprechernotiz:* Das Architekturbild aus `docs/ARCHITEKTUR.md` (Captain → Oberfläche/CLI → Runtime → vier Blöcke) als eine Grafik zeigen. Wichtig: Der Kern importiert nichts aus den anderen Teilen; das prüft ein eigener Test.

## Folie 4 – Prinzip „Captain entscheidet“: Guard und Freigaben
- Jede Aktion geht durch den Guard: ALLOW, BLOCK oder CAPTAIN_REQUIRED; unbekannte Aktionen brauchen immer den Captain
- Lesen und neue Artefakte sind erlaubt; Überschreiben, Löschen, Shell, Modellsteuerung und externe Schreibaktionen brauchen eine Freigabe
- Freigaben sind Einmal-Token, gebunden an Mission, Aktion, Ziel und Auftrags-Digest, 24 Stunden gültig
- Rechtestufen 0 bis 6 liegen über dem Guard und können nur zusätzlich „Nein“ sagen
- Audit-Protokoll ist hash-verkettet (Manipulation fällt auf); Schlüsselwerte werden geschwärzt

*Sprechernotiz:* Das ist das Kernprinzip: Die KI darf vorschlagen und vorbereiten, ausführen mit Wirkung nur nach Freigabe. Belegbeispiel aus dem Logbuch: Ein Gate (Agent starten) wurde vorgelegt und blieb `pending`, bis der Captain im Chat „Freigeben“ sagte.

## Folie 5 – Desk, Cockpit und UIX-Shells
- Desk = Andockstelle zwischen Kern und Oberfläche: Objekte `{type, id, title, state, summary, actions, links}`, Verben über `POST /api/actions`, jedes Verb kennt sein Gate
- Shells (Oberflächen): `cockpit`, `paperclip` (Arbeitsplatz für Agenten), `minimal`, `gateway-kmu`, `gateway-studio`, Einstieg `start`, `wissensbasis`
- UIX-Paket Stufe 1 bis 6 (27.10.): Cockpit-Baum, Palette, Wissensbasis, ordnende Leiste, Mini-Hub zum Wechseln der Shells
- Prüfwerkzeuge der Oberfläche laufen nur im Prüfbetrieb (Schalter `entwicklung`, Standard aus)

*Sprechernotiz:* Ein Kern, viele Oberflächen. Die Shells sind austauschbar, weil sie nur das Objektmodell und die Verben des Desk benutzen. Das Changelog nennt UIX Stufe 5 und 6 ausdrücklich „nicht abgenommen“; das ehrlich so sagen.

## Folie 6 – Orchestra: Agenten als kleines Team
- Paket `orchestra/`: Organigramm, Aufgabenbrett mit atomarem Checkout, Herzschlag-Wecken, Budgets, Routinen (Vorbild: Paperclip)
- Rollen im Betrieb: Leitung (zerlegt Aufgaben), Recherche-Agent, weitere Agenten mit Vorgesetztem
- Jede Weckung eines Agenten ist ein Gate: Antrag im Posteingang, der Captain gibt frei
- Erster echter Leiter-Lauf (27.10.): Aufgabe zerlegt in zwei Recherche-Teilaufgaben, Antwort in rund 15 s

*Sprechernotiz:* Die Orchestrierung wurde zuerst als Spezifikation geschrieben (Anforderungen im EARS-Format, jede mit ID und Abnahmekriterium) und dann gebaut. Die Spec-Reihenfolge war: Spec 0 (Kern) zuerst, Spec 1 bis 4 danach, Spec 5 prüft alles zusammen.

## Folie 7 – Modell-Scheduler und lokale Modelle
- Eigener `llama-server` (llama.cpp), Rezepte legen fest: welches Modell, welche Rolle, wie viel Kontext, wie viel VRAM
- Von „ein Prozess lädt“ zu „ein Server, mehrere Slots, ein Scheduler verteilt“
- Ressourcen werden vor dem Laden reserviert (VRAM/RAM/KV-Cache mit Reserve); bei zu wenig freiem RAM wird abgelehnt
- GPU-Selbsttest (Canary) nach Windows-Start und nach jedem Server-Absturz; schlägt er fehl, werden keine Modelle geladen
- Cloud-Angebot als Option im Scheduler (SCH-07), Standard bleibt lokal

*Sprechernotiz:* Wichtig für Studierende: Auf einer 12-GB-Karte ist VRAM der Engpass. Der Scheduler macht dieses Limit explizit, statt das Programm einfach abstürzen zu lassen.

## Folie 8 – Messung: parallele Slots (22./23.10.2026)
- Hilfsmodell Qwen3.5-9B Q6_K mit MTP: 1 Slot 70,0 Token/s gesamt, 2 Slots 117,7, 3 Slots 147,9
- Ohne MTP: 56,5 / 100,2 / 135,5 Token/s; bei 4 Slots 11,21 GiB VRAM, über der nutzbaren Grenze (10,8 GB) – MTP ab 4 Slots aus
- Hauptmodell Qwen3.6-35B-A3B: 31,6 / 36,9 / 44,9 / 49,9 Token/s gesamt bei 1 bis 4 Slots (+17 % bis +58 % Durchsatz), aber weniger Tempo je Slot
- Ergebnis: Standardempfehlung 2 Slots; der Server teilt den Gesamtkontext `-c` auf die Slots auf
- Ein Messfehler wurde dabei selbst gefunden: Das Werkzeug nahm an, `/props` melde die Summe – es meldet das Fenster je Slot

*Sprechernotiz:* Diagramm: Balken Token/s gesamt über Slotzahl für beide Modelle. Betonen: mehr Parallelität erhöht den Gesamtdurchsatz, verlangsamt aber jeden einzelnen Agenten.

## Folie 9 – Qualitätssicherung: Tests, versteckte Tests, Gegenproben
- 257 Testdateien; Testgruppen scheduler/desk/orchestra/uix: 1049 Tests grün
- Bau-Specs mit versteckten Abnahmetests und einer grünen Referenzlösung; vor einem Bau muss ein Stempel (`spec_check`) die Spec bestätigen
- Der Modellcode läuft nur in einer microVM, nie ersatzweise auf dem Host
- Regel „wird eine Lücke gefunden, zuerst die Spec ändern“; Review Zeile für Zeile vor Übernahme
- Gefundener Fehler, den Tests mit Fake-Router verdeckten: echtes Schema `type: ["string","null"]` löste in jedem echten Lauf einen TypeError aus (`models/structured.py`) – behoben, Test ergänzt

*Sprechernotiz:* Lehre: Tests mit Attrappen (Fakes) können genau den Fehler verstecken, der erst im echten Betrieb auftritt. Deshalb gab es zusätzlich Betriebsstunden mit echten Aufgaben.

## Folie 10 – Betriebsstunde und Härtung (26./27.10.)
- Erste Betriebsstunde (23:06 bis 00:06, 338 Messungen): 11 von 12 Prüfpunkten bestanden; Temperatur höchstens 53 Grad; nie mehr als ein `llama-server`
- Fehler gefunden und behoben: zusammengelegte Weckrufe blieben ohne Lauf; ein zweiter Weckruf hängte sich an einen wartenden Antrag und blieb nach der Entscheidung „tot“
- Messung zum Arbeitsspeicher: Ohne `cache_ram` wuchs der Server-Speicher von 11,16 auf 17,05 GB (freier RAM 7 auf 1,2 GB); mit `cache_ram: 1024` blieb er bei rund 12,5 GB
- Freigabe-Härtung: ein Antrag je Weckruf, Altbestand der Datenbank bereinigt (mit Sicherung vorher)

*Sprechernotiz:* Typischer Ablauf: messen, Ursache belegen, ändern, wieder messen. Die Ursache der RAM-Knappheit in der Nacht blieb unklar (vermutlich außerhalb von SEDRA, nicht bewiesen).

## Folie 11 – 3D-Objekt-Lauf: Agenten und Modell arbeiten zusammen
- Skript `benchmarks/nachtlauf_3d.py`: Recherche-Agent liest 10 Quellen zu OpenSCAD; das lokale Modell schreibt OpenSCAD-Code für 8 Objekte (Würfel mit Kugelloch, Becher, Vase, Stufenpyramide, Schraubenmutter, Zahnscheibe, Bücherstütze, Schachturm)
- Bis zu 4 Versuche je Objekt, der Fehlertext von OpenSCAD geht zurück an das Modell; Ausgabe als STL
- Jede Weckung wird einzeln freigegeben; das Skript misst alle 30 s VRAM, Temperatur und RAM
- Verlauf: Nachtlauf 0 von 8 Objekten, nach Härtung 5 von 8, danach 8 von 8 im Kurzlauf

*Sprechernotiz:* Der Lauf ist eine Ende-zu-Ende-Probe: Recherche, Code erzeugen, Fehlermeldung zurückspielen, Ergebnis prüfen. Er zeigt auch die Grenze des 9B-Modells bei komplexen Formen.

## Folie 12 – Ergebnis des 6-Stunden-Dauerlaufs (27.10., 15:53 bis 21:53)
- GPU stabil mit NVIDIA-Debug-Modus; ohne ihn gab es Treiber-Zurücksetzungen (nvlddmkm, LiveKernelEvent 141, seit 24.10.), der `llama-server` brach dann ab
- VRAM konstant 9231 bis 9349 MiB (705 Messungen), GPU 39 bis 72 Grad, freier RAM mindestens 9,4 GB, kein Modellabbruch
- 1086 von 1229 Objekten gelungen = 88 Prozent (30-Minuten-Lauf vor dem Fix: 76 Prozent); 2036 Modellaufrufe, im Schnitt 10,6 s je Aufruf
- Erfolgsquote je Objekt: Würfel 100, Zahnscheibe 99, Stufenpyramide 97, Bücherstütze 97, Schachturm 94, Becher 92, Schraubenmutter 68, Vase 61 Prozent
- Restfehler sind Modellqualität bei komplexen Formen, keine Technik

*Sprechernotiz:* Wichtig: Ein früherer 12-von-51-Anteil der Parse-Fehler kam nicht vom Modell, sondern vom Skript – abgeschnittene Antworten ließen eine Markdown-Zaunzeile in der Datei. Nach dem Fix stieg die Quote von 76 auf 88 Prozent. Erst die Ursachenanalyse zeigte, was Modell und was Werkzeug war.

## Folie 13 – Mensch-KI-Arbeitsteilung im Projekt
- GUPPI (lokale Modelle) schreibt Produktionscode neuer Module; Claude schreibt Specs, versteckte Tests, Referenzen und den Harness (Guard, Bridge, Bauskripte); der Captain entscheidet jedes Gate
- Eingriffe von Claude werden im Logbuch eingetragen und gezählt; ein Code-Zähler misst Zeilen der Modelle gegen Zeilen von Claude
- Ziel „50 % des neuen Codes durch GUPPI“ wurde am 20.10. ersetzt durch eine gemessene Quote je Aufgabe
- Entscheidungsweg: Anforderungen → Design → Aufgaben → Umsetzung, jede Stufe endet mit einem Tor (G1 bis G4)

*Sprechernotiz:* Ehrlich benennen, dass die lokalen Modelle ohne externe Abnahme unzuverlässig waren (siehe Folie „Was wir gelernt haben“).

## Folie 14 – Offene Punkte und Ausblick
- Nemotron-Test steht aus (Modelldatei fehlt noch)
- Weitere Härtungslücken: Wiederholung nach Fehler braucht jedes Mal neue Freigabe (kein Deckel); VRAM-Spitze vom 26.10. 23:28 ungeklärt (vermutlich Treiber)
- UIX Stufe 5 und 6 nicht abgenommen; Hub ziehen und Position nach Neustart nicht geprüft
- Vase und Schraubenmutter ließen sich mit mehr Token oder besserem Prompt eventuell verbessern (Empfehlung im Logbuch)

*Sprechernotiz:* Offene Punkte sind kein Makel, sondern Teil der Methode: Jeder Befund wird als solcher gekennzeichnet und im Logbuch geführt.

---

# Teil 2 – Zeitachse (belegt durch Logbuch, Dokumente und Commit-Verlauf)

Commits je Tag (aus `git log`): 15.10.: 4 · 16.10.: 20 · 19.10.: 29 · 20.10.: 59 · 21.10.: 87 · 22.10.: 66 · 23.10.: 6 · 24.10.: 9 · 25.10.: 25 · 26.10.: 74 · 27.10.: 21 · 28.10.: 2.

| Datum | Meilenstein |
|---|---|
| 4.–7.10.2026 | Vorarbeiten: Loop-Guard-Pläne, DevVM (microVM-Entwicklungsumgebung, Phasen 0 bis 5), Agent-Manager-Integration (AM-001 bis AM-006). Bauaufträge mit versteckten Tests; z. B. AM-003 Lauf 3: 6 von 8 Stufen bestanden, Rest durch gezielte Nacharbeit |
| 7.10. | Fehleranalyse der Modellbauten; Auswertung „Wo musste Claude eingreifen“ (5 Arten von Eingriffen, 7 Lösungsansätze); Entscheidung: PyYAML nicht ins VM-Image, strenger Loader auf dem Host |
| 9.–12.10. | Modellvergleich (Bericht `MODELLVERGLEICH_2026-10-12`), Paketaufteilung des Codes in Unterpakete, Rezepte für lokale Modelle; fünf Modelle (71,4 GB) in Quarantäne entfernt |
| 13.–15.10. | Builds 7 bis 23: Desk, Werkbank, Grenzen, Shell-Creator, KI-GateWay, Inhaltsschutz; 15.10. erster Commit im heutigen Git-Verlauf |
| 16.10. | Build 24: API-Zugang für Cloud-Modelle, Einstellungen im Kern, Shell-Auswahl |
| 19.–20.10. | Gesamtreview, „einheitliche Linie“ L1 bis L6 (ein Bauweg, kein Bau ohne Stempel, Stufengröße höchstens 20 Prüfungen, Aufgabenteilung); Spec „Agenten-Orchestrierung“ v1 |
| 21.–22.10. | Specs 1 (Orchestra), 4 (Shell D), 7 (Wissensspeicher); Embedding-Messung BGE-M3 gegen Qwen3-Embedding-0.6B; Design Spec 2 (Scheduler) zur Freigabe vorgelegt |
| 22.–23.10. | Messung paralleler Slots (Folie 8) |
| 24.–26.10. | Spec 2 gebaut: testlab Schema 2, Fassade `model_scheduler`, Supervisor mit Slots, Cloud-Angebot SCH-07; Review-Auflagen; Umstieg auf die einzige Hauptumgebung A1 |
| 26./27.10. | Erste Betriebsstunde, Härtung, `cache_ram`-Messung, 3D-Lauf-Skript, UIX Stufe 2 bis 6 mit Mini-Hub (1047 Tests grün nach Merge) |
| 27.10. 13:00–21:53 | Voller Lauf mit Treiberereignissen, Debug-Modus der GPU, 30-Minuten-Lauf (76 %), 6-Stunden-Lauf (88 %) |
| 28.10. | Scheduler-Poll startet mit dem Server; veralteter Wecken-Antrag schließt seinen Weckruf; bekannte rote Tests wieder grün |

---

# Teil 3 – Messergebnisse zum Vorzeigen

| Messung | Ergebnis | Quelle |
|---|---|---|
| Slots, Hilfsmodell (MTP) | 70,0 → 117,7 → 147,9 Token/s bei 1/2/3 Slots | `MESSBERICHT_SLOTS_2026-10-23.md` |
| Slots, Hauptmodell | 31,6 → 49,9 Token/s bei 1 bis 4 Slots | dito |
| Erste Betriebsstunde | 11 von 12 Punkten, Temperatur ≤ 53 °C | Logbuch 27.10. |
| RAM-Wachstum | 17,05 GB ohne, 12,5 GB mit `cache_ram: 1024` | Logbuch 27.10. |
| 3D-Nachtlauf (vor Härtung) | 0 von 8 Objekten, Recherche 2 von 10 | Logbuch 27.10. |
| Voller Lauf nach Härtung, ohne Debug-Modus | Recherche 10/10, Objekte 5/8, drei Treiber-Zurücksetzungen in 8 Minuten | Logbuch 27.10. |
| Voller Lauf mit Debug-Modus (5,7 min) | Recherche 10/10, Objekte 8/8, VRAM konstant ~10.228 MiB | Logbuch 27.10. |
| 30-Minuten-Dauerlauf | 39 von 51 Objekten (76 %), 109 Modellaufrufe | Logbuch 27.10. |
| 6-Stunden-Dauerlauf | 1086 von 1229 Objekten (88 %), 2036 Aufrufe, GPU 39 bis 72 °C, VRAM 9231–9349 MiB | Logbuch 27.10. |
| Versuche bis zum Erfolg (6 h) | 788 im 1., 236 im 2., 43 im 3., 19 im 4. Versuch | dito |
| Fehlerarten (6 h) | 950 fehlgeschlagene Versuche: 479 OpenSCAD-Parse-Fehler, 471 Render-/Geometriefehler | dito |

---

# Teil 4 – Was wir gelernt haben

**Technik**
1. **Messen vor Vermuten.** Der RAM-Anstieg des Servers wurde erst durch eine Serie mit gleichen Prompts mit und ohne `cache_ram` eindeutig erklärt. Die Nacht-Ursache blieb ohne Messdaten offen und wurde als unklar geführt.
2. **Fehler liegen oft im Werkzeug, nicht im Modell.** Zwölf von 51 Parse-Fehlern im 30-Minuten-Lauf kamen von abgeschnittenen Antworten, die das Skript falsch auswertete. Nach dem Fix stieg die Erfolgsquote von 76 auf 88 Prozent.
3. **Hardware gehört in die Fehlersuche.** Die Abbrüche des Modellservers ließen sich nicht dem Code zuordnen, sondern dem Grafiktreiber (ohne NVIDIA-Debug-Modus Zurücksetzungen, mit Debug-Modus sechs Stunden stabil). Ein kurzer Lauf ohne Abbruch beweist keine Stabilität: Die Ereignisse traten erst nach 1 bis 8 Minuten Last auf.
4. **Tests mit Attrappen reichen nicht.** Der Schemafehler mit `["string","null"]` und die zusammengelegten Weckrufe zeigten sich erst in echten Läufen.
5. **Parallelität ist ein Tausch.** Mehr Slots bringen mehr Gesamtdurchsatz, aber weniger Tempo je Agent und mehr VRAM.

**Zusammenarbeit mit der KI**
6. **Kleine Aufgaben, klare Abnahme.** Stufen mit 3 bis 6 Verhalten gelangen meist im ersten Anlauf, Stufen mit 10 und mehr scheiterten (Auswertung vom 7.10.). Daraus folgte die Regel L3 (höchstens 20 Prüfungen je Stufe).
7. **Ein Befund in Worten hilft mehr als eine Fehlermeldung.** Mit Review-Text gelang die Nacharbeit jedes Mal in einem Anlauf; mit bloßer Fehlerausgabe nicht (Auswertung 7.10.).
8. **Die KI prüft sich nicht zuverlässig selbst.** Die Eigenprüfung der Modelle war in beiden Richtungen unzuverlässig (z. B. in AM-005 nur bei 1 von 6 Stufen richtig). Darum: unabhängige Abnahmetests und eine Referenzlösung als Gegenprobe. Ob ein Modell einer anderen Familie besser prüft, ist laut Dokument nicht gemessen und wurde deshalb nicht umgestellt.
9. **Der Mensch behält die Freigabe.** Starts von Agenten, Läufe, Downloads und Änderungen am Kern laufen über Gates. Das kostet Zeit, verhinderte aber unbeabsichtigte Wirkung. Im Projekt gilt außerdem: Lange Läufe nur nach ausdrücklichem Ja.
10. **Alles protokollieren.** Das Logbuch (Datum, Art, Befund, Beleg) machte spätere Auswertungen und Korrekturen möglich, etwa bei der Korrektur falsch notierter Uhrzeiten.
11. **Entscheidungen früh festhalten, Spec vor Code.** Wenn beim Bauen eine Lücke auffällt, wird zuerst die Spec geändert.
12. **Lange Chats werden ausgelagert.** Bei zu langem Kontext werden Aufgaben in eigene Sitzungen verschoben und der Stand in Notizen gesichert (Arbeitsweise im Projekt, Interpretation für den Vortrag).

**Offene Fragen für die Diskussion**
- Wie viel Eigenständigkeit verträgt ein Agentensystem, bevor jede Freigabe zur Routine wird und nicht mehr gelesen wird? (Hinweis im Projekt: „Wiederholung nach Fehler braucht jedes Mal neue Freigabe“ ist ein offener Punkt.)
- Wie misst man den Anteil, den die KI am Code wirklich selbst geschrieben hat? (Code-Zähler `code_meter` im Projekt; eine feste Zielquote wurde verworfen.)
- Wie viel der Leistung steckt im Modell, wie viel im Drumherum (Prompt, Rückmeldeschleife, Werkzeuge)? (Beispiel 76 → 88 Prozent durch Werkzeugfix.)

---

# Anhang – Quellen im Repository
`docs/ARCHITEKTUR.md` · `docs/ENTWICKLUNG.md` · `docs/MODELLE.md` · `docs/MESSBERICHT_SLOTS_2026-10-23.md` · `docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md` · `docs/EINGRIFFE_CLAUDE_AUSWERTUNG_2026-10-07.md` · `docs/CHANGELOG.md` · `docs/LOGBUCH_AGENT_MANAGER.md` (Einträge OP-S2-18 vom 26./27.10.2026) · `runtime/README_RUNTIME.md` · `git log` · Projektnotizen (Stand 27.10.2026).
