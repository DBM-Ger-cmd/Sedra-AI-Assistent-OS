# Konzept: Experten-Schleifen-Bau (Entwurf, 12.11.2026)

Stand: Entwurf zur Durchsicht, nichts gebaut, nichts eingeschaltet. Idee des Captains vom 12.11.2026 nach dem Unsloth-Vergleich. Verwandt mit `docs/KONZEPT_KONSENS_BAU_2026-11-11.md` (dieselbe Aufgabe N-mal lösen) und dem Modus `pipeline` von `devvm_build.py` (Planer, Schritte, Prüfer).

## 1. Idee in einem Satz

Ein umfangreiches Produkt wächst in vier Runden. Jede Runde holt vier Vorschläge mit verschiedenen Blickwinkeln ein, nimmt die besten Punkte in den Bau auf, lässt den Code **ausführen**, von einem Prüfer mit anderem Schwerpunkt prüfen und sichert ihren Teil. Ein zweites Modell prüft mit, weil es andere blinde Flecken hat.

## 2. Anlass: was der Bau `dashboard_index` gezeigt hat (12.11.2026)

Eine Spec in drei Stufen (`scan`, `index`, `dashboard`), Profil `standard`, 1 Versuch, Qwen3.6-35B. Belege in `runtime_data/devvm_replays/dashboard_index/attempt_01_20261112_165014/`:

| Befund | Beleg |
|---|---|
| Das Modell **kann den Code nicht ausführen** ("You cannot run code"), nur lesen, bearbeiten, `check_syntax` | Werkzeugliste der Mitschnitte |
| Stufe 3 begann mit **Neuschreiben der Datei** (Datei gelöscht, nur Anfang geschrieben) | Nacharbeit 1, Mitschnitt 07 |
| Die Nacharbeit schrieb den fertigen INDEX-Teil neu und baute einen Absturz ein (`KeyError: 'files_direct'`) | Nacharbeit 2, Endstand Zeile 220 |
| Der Test meldete nur "Rückgabecode 1", die Ursache blieb unbekannt, Nacharbeit 3 riet falsch | Mitschnitt 09, kein `KeyError` im Text |
| Die Regressionsprobe schlug nicht an (kein `REGRESSION` im Log) | Bau-Log, Ursache ungeklärt |
| Windows-Pfade mit `\` (`os.path.join`), in der Linux-VM unsichtbar | Zwischenstand `after_index` auf dem Host |
| Zwei Stufen bestanden, der Endstand verlor sie wieder | Test des Endstands auf dem Host |

Folgerungen für den Ablauf: Ausführen statt raten, kleine Änderungen statt Neuschreiben, Fehlermeldung mit Ort an den Coder, Regression gegen alle früheren Runden, Prüfung auch auf dem Host.

## 3. Rollen

| Rolle | Wer | Schwerpunkt | Ausgabe |
|---|---|---|---|
| **Architekt** | Hauptmodell (35B) | Gerüst und **Vertrag**: Dateien, Schnittstellen, Datenformat, ausführbare Beispiele (Ein- und Ausgabe) | `VERTRAG.md` und Beispieldateien, die ein Lauf prüfen kann |
| **Vier Experten** | Hauptmodell, je ein Blickwinkel | 1 Struktur und Schnittstellen, 2 Randfälle und Fehler (Katalog `docs/CODER_PROFIL_UND_WORKFLOW_2026-11-11.md` §4), 3 Einfachheit und Umfang, 4 Prüfbarkeit und Plattform (Windows, Unicode, Pfade) | je höchstens 300 Wörter: Vorschlag mit nummerierten Punkten |
| **Auswahl** | Prüfer-Rolle (anderer Prompt als der Coder) | wählt Punkte nach festen Kriterien, nicht nach Gefühl: deckt der Punkt eine Zeile des Vertrags? Ist er prüfbar? Widerspricht er einem anderen? | Liste gewählter Punkte mit Begründung je Punkt |
| **Coder** | Hauptmodell | baut nur das Gewählte, **ergänzt statt neu zu schreiben** (Regel: Datei nie löschen, kleine Änderungen) | Code der Runde |
| **Läufer** | Werkzeug, kein Modell | führt Vertragsbeispiele und alle früheren aus, liefert Ausgabe und Fehlerzeile | Ergebnis je Beispiel, Fehler mit Datei und Zeile |
| **Prüfer A** | Hauptmodell, andere Rolle | Befunde nach Fehlerliste (§3 des Coder-Profils): neu berechnet statt gelesen, `isdigit` mit Unicode, unhashbare Werte, unbegrenzter Speicher und so weiter | Befunde mit Datei, Zeile, genauer Ersetzung |
| **Prüfer B** | zweites Modell (siehe §5) | mechanische Checkliste (Formate, Namen, verbotene Muster); andere blinde Flecken | Befunde im gleichen Format |

### 3a. Expertenkatalog (Erweiterung auf Vorschlag des Captains, 12.11.2026)

Statt immer derselben vier Blickwinkel gibt es einen Katalog. Je Runde werden vier bis höchstens sechs Experten **nach Aufgabe gewählt**, nicht alle auf einmal. Jeder Experte bekommt nur seine eigene kurze Checkliste (höchstens eine Wissenskarte, mehr verschlechtert kleine Modelle) und liefert in einem festen Format: bis zu 5 nummerierte Punkte, je mit "prüfbar durch: <Beispiel oder Befehl>".

| Experte | Blick | Wann gewählt |
|---|---|---|
| Architektur | Dateien, Schichten, Abhängigkeiten, was darf was aufrufen | immer in Runde 0, bei neuen Modulen |
| Schnittstellen und Daten | Felder, Typen, Fehlerrückgaben, Formatversionen | immer in Runde 0, bei jeder Datenstruktur |
| Randfälle und Fehler | Katalog `CODER_PROFIL_UND_WORKFLOW` §4 (leer, None, Unicode, Namen wie `constructor`) | immer |
| Prüfbarkeit und Plattform | Windows und Linux, Pfade, Zeichensatz, Zeit, ausführbare Beispiele | immer |
| Oberfläche und Design | Aufbau der Seite, Bedienung, Beschriftung, Lesbarkeit, Hell und Dunkel | wenn die Aufgabe HTML, CSS oder Texte für Menschen hat |
| Leistung und Umfang | große Ordner, Speicher, Schleifen, Nachladen | wenn Daten mit mehr als etwa 1000 Einträgen vorkommen |
| Sicherheit und Datenschutz | Eingaben, Pfade außerhalb, Geheimnisse, Netzzugriff | wenn Eingaben von außen, Dateien oder Netz vorkommen |
| Einfachheit | was lässt sich streichen, kleinere Lösung | immer, als Gegengewicht, damit der Umfang nicht wächst |

**Wer wählt:** zuerst eine feste Tabelle (Stichworte in der Aufgabe oder Spec, Endungen der Dateien). Ob LFM3-1.7B diese Auswahl besser trifft als die Tabelle, ist ein Messpunkt, kein Vorausgesetztes (Modellkarte nennt Tool-Aufrufe als Stärke).

**Warum nicht alle acht immer:** Je mehr Vorschläge die Auswahl liest, desto schlechter wird sie; Vorschläge desselben Modells überlappen stark (im Nachtlauf teilten 8 von 10 Kandidaten denselben Fehler). Die Kosten sind gering gegen eine Nacharbeit (ein Vorschlag etwa 500 Token, rund 10 s bei 57 t/s; eine Nacharbeit im Bau `dashboard_index` dauerte bis 1.222 s), die Wirkung ist aber nicht belegt.

**Erste Messung der Vorschläge (12.11.2026, Runde 1 von 10, Power-Modus, vier Blickwinkel ohne Checkliste):** brauchbare Einzelpunkte (atomares Schreiben der JSON, gesperrte Ordner, Emoji-Namen, Abgleich der Zählung mit `find` oder `Get-ChildItem`), aber starke Überlappung (Pfadtrenner, Git-Fallback und gültiges JSON in drei bis vier Vorschlägen). Keiner nannte die Fallen des Coders (Dateiknoten ohne Zählfelder, Neuschreiben statt Ergänzen). Das "prüfbar durch" war oft nicht ausführbar ("visuelle Prüfung", `sudo chmod` auf Windows). Daraus drei Regeln:

1. **Jeder Experte bekommt zusätzlich seine Fallenliste** aus dem Fehlerkatalog des Coder-Profils (neu berechnet statt gelesen, Unicode-Ziffern, Namen wie `constructor`, Dateiknoten gegen Ordnerknoten, Ergänzen statt Neuschreiben), nicht nur die Rolle.
2. **"prüfbar durch" muss ein einzelner Befehl oder Python-Einzeiler sein**, den der Läufer auf Windows und Linux ausführen kann. Alles andere (visuelle Prüfung, `sudo`) wird bei der Auswahl verworfen.
3. **Überlappung wird gemessen** (Anteil gleicher Wörter zwischen den Vorschlägen einer Runde) und gegen den Stand ohne Fallenliste verglichen.

**Messpunkt:** Arm D mit allen passenden Experten (bis 6) gegen Arm B mit festen vier. Gezählt wird, welche Punkte der Experten am Ende in den Code kamen und welche Fehler der Durchsicht ein Experte vorher genannt hatte.

Rollen unterscheiden sich in **prüfbarer Ausgabe**, nicht nur im Prompttext. Grund: Die Arbeitsanweisung `bau_coder` brachte im A/B-Test keinen messbaren Nutzen bei 21 % mehr Prompt-Token.

### 3b. Profile je Projektart (Entscheidung des Captains, 12.11.2026)

Der Captain legt fest: **erst für ein Softwareprojekt planen, so wie es heute gebaut wird, und den Prozess danach je Projekt umstellen.** Darum wird der Ablauf in einen festen **Kern** und ein austauschbares **Profil** getrennt.

| Teil | Fest (Kern, gilt für jede Projektart) | Austauschbar (Profil) |
|---|---|---|
| Ablauf | Runde 0 bis 3, vier Vorschläge, Auswahl, Bau, Lauf, Befunde, höchstens 2 Nacharbeiten, Sicherung je Runde, Regression | Zahl der Runden, Zeitlimit je Runde |
| Experten | Format der Vorschläge (bis 5 Punkte, je "prüfbar durch") | **Expertenkatalog** und Auswahltabelle |
| Läufer | Vertrag mit prüfbaren Beispielen, Ergebnis je Beispiel mit Ort des Fehlers | **was ausgeführt wird** (Befehl, Umgebung, Zielplattform) |
| Prüfer | Befundformat mit Ort und genauer Ersetzung | **Checklisten** der Prüfer A und B |
| Sicherung | Stand je Runde festhalten, zurückfallen können | Form (Snapshot, Commit, Export) |
| Abnahme | Gate des Captains, kein Übernehmen von selbst | Bewertungsprüfung (versteckte Tests, Sichtprüfung, Messwerte) |

**Profil `software` (das erste, so wie heute):** Python und JavaScript/HTML, Bau im Arbeitsbereich der DevVM, Läufer führt `python`/`node` aus (VM Linux **und** Host Windows), Katalog nach 3a, Prüfer-Checkliste aus `docs/CODER_PROFIL_UND_WORKFLOW_2026-11-11.md`, Sicherung als Snapshot wie `devvm_snapshots`, Bewertung mit den versteckten Tests der Spec (`spec_check.py`) und Durchsicht nach `REVIEW_VORLAGE.md`.

**Später je Projekt (noch nicht geplant, nur Beispiele, was sich ändert):** ein Profil bringt eigene Experten (zum Beispiel Barrierefreiheit, Texte auf Deutsch, Statik oder Maße bei Konstruktion), einen eigenen Läufer (zum Beispiel Rendern oder Export statt `python`) und eigene Checklisten. Der Kern bleibt gleich. Neue Profile entstehen erst, wenn ein Projekt sie braucht.

## 4. Ablauf

```
Runde 0 (Gerüst)
  4 Experten -> Auswahl -> Architekt schreibt Gerüst + VERTRAG + Beispiele
  Läufer prüft, dass das Gerüst startet; Sicherung "r0"
Runde 1..3 (je ein Teil des Produkts)
  4 Experten zum Teil -> Auswahl (Kriterien gegen den Vertrag)
  Coder baut den Teil (ergänzen, nicht neu schreiben)
  Läufer: Beispiele dieses Teils + alle früheren Runden (Regression)
  Prüfer A und B: Befunde
  bis 2 gezielte Nacharbeiten (Befund + Fehlerzeile des Läufers)
  Sicherung "r<n>" (Snapshot, Stand der Beispiele, Befundliste)
Ende: Gesamtlauf aller Beispiele auf dem Host (Windows), Durchsicht mit REVIEW_VORLAGE.md
```

Abbruchregeln: Besteht eine Runde nach 2 Nacharbeiten nicht, nicht weiterbauen (Regel des Skills `sedra-bau-starten`), zurück zum letzten gesicherten Stand und dem Captain melden. Jede Runde hat ein Zeitlimit.

## 5. Zweites Modell: LFM3-1.7B (vom Captain bestätigt 12.11.2026)

- Datei: `I:\KI-Daten\modelle\liquid\LFM3-1.7B-GGUF\LFM3-1.7B-Q8_0.gguf` (1,85 GB, geladen 12.11.).
- Läuft nur mit llama.cpp ab b11960 (Modellkarte). SEDRAs Engines sind b11160/b11371, zu alt. Unsloths Build `<benutzer>\.unsloth\llama.cpp` (12284) kann es. **Für den Test ein eigener Server mit diesem Build**, `engines/` bleibt unberührt.
- 12 GB VRAM reichen nicht für den 35B (Power-Modus belegt 11,8 GiB) **und** LFM3 auf der GPU. Zwei Wege: (a) LFM3 auf der **CPU** (`-ngl 0`); Nachteil: die Experten des 35B liegen schon auf der CPU, beide konkurrieren um die Kerne; (b) **nacheinander** mit Modellwechsel (Ladezeit). Der Test misst beides.
- Rolle: laut Modellkarte stark bei Tool-Aufrufen und Anweisungsbefolgung (BFCL V4 71,39, IFEval 96,66, Herstellerangaben), **nicht** für Coding-Agenten. Darum nur Prüfer B (mechanische Checkliste, Befundformat) und gegebenenfalls Auswahl-Protokoll, **nicht** Coder.
- Alternative Kandidaten: MiMo-V2.6-Distill-Qwen-9B (ein Qwen3.5-9B-Ableger, also teils gleiche blinde Flecken), Gemma (im Profil `team-35b` schon Prüfer).

## 6. Messplan

Dieselbe Spec `dashboard_index` (Stempel gültig) und danach eine größere Spec mit mehreren Modulen.

| Arm | Beschreibung |
|---|---|
| A | Referenz: `devvm_build.py --profile standard`, 1 Versuch (gelaufen 12.11.: Stufen 2/3, Endstand kaputt, 3.828 s) |
| B | Experten-Schleifen nur mit 35B (Rollen über Prompts, Läufer als Werkzeug) |
| C | wie B, plus zweites Modell als Prüfer B |

Kennzahlen je Arm: versteckte Tests der Stufen (Host **und** VM), Endstand gegen alle Stufen, Befunde der Durchsicht mit `REVIEW_VORLAGE.md`, Zeit, Token, Zahl der Nacharbeiten, Windows-Lauf. Die versteckten Tests dienen nur der Bewertung, nicht der Auswahl.

## 7. Offene Fragen (Captain entscheidet)

1. ~~Welches Modell ist das zweite?~~ Entschieden: LFM3-1.7B. Offen: Soll MiMo-9B später ein dritter Arm werden?
2. CPU-Betrieb des zweiten Modells neben dem 35B oder Modellwechsel nacheinander?
3. Vier Vorschläge parallel im Team-Pool (3 bis 4 Slots mit gemeinsamem Speicher, Profil `team-35b`) oder nacheinander im Power-Modus?
4. Der Läufer braucht ein Werkzeug, das Code und Beispiele **ausführt**. Heute hat der Coder keines (Stufe `standard`). Soll das als Option des Prototyps kommen, ohne `devvm_build.py` zu ändern?
5. Wohin mit dem Prototyp: eigenes Skript `benchmarks/experten_bau.py` (wie `konsens.py`), nichts in den Kern, bis gemessen ist.

## 8. Nicht Teil dieses Entwurfs

- Kein Eingriff in `devvm_build.py`, `bau_schleife.py` oder die Harness.
- Keine Übernahme von Kandidaten ohne Gate G4.
- Keine Einschaltung als Standard vor der Messung (gleiche Regel wie beim Konsens-Bau).
