# Auswertung: Wo und warum Claude eingreifen musste (Entwurf 2026-10-07)

Auftrag des Captains: Nach Abschluss der Integration ansehen, **wie der Code von GUPPI geschrieben wurde**, **warum Claude so oft aushelfen musste**, und eine **Lösung** dafür entwickeln. Dies ist die Sammlung der Fakten und Hypothesen; die Auswertung steht noch aus (Hypothesen sind als solche markiert).

## 1. Eingriffe, nach Art
| Art | Anzahl | Beispiele | Beleg |
|---|---|---|---|
| A. Aufgabe und Abnahme von außen schreiben | 4 Bauaufträge, 774 Zeilen, dazu 4 Referenzimplementierungen zur Prüfung der Tests | `am002` bis `am005` | `benchmarks/devvm_specs/` |
| B. Gezielte Nacharbeit mit Befund | 4 | AM-002 `version` (Nicht-ASCII-Ziffern), AM-002 `seal` (Funktionen nie geschrieben), AM-003 `command_replay` (alte Revision bei delete, Anfragetext nicht normalisiert), AM-004 `permissions` (fehlende Schlüssel) | Logbuch, `am_review_*.txt` |
| C. Fehlerhafte Modelltests entfernen | 17 von 3 Dateien | 4 in AM-003, 13 in AM-004 (fehlende Importe, veraltete Erwartungen) | `archiv/.../*.model-original-2026-10-07` |
| D. Werkzeug und Betrieb reparieren | ca. 10 | Eigenprüfung zählte bei `unjudged` als bestanden; Kontext 16k zu klein (`error`); `ubatch` bei 32k; Fehlermeldung fehlte im Log; Läufe an die Sitzung gebunden; UTF-16-Logs; Absturz-Rettung | Logbuch, Fehleranalyse |
| E. Anbindung an Bestehendes | 487 Zeilen | Guard-Brücke, strenger YAML-Loader, Dienst, Fenster, Route, Templates der DevVM-Rollen | `agent_manager/` |

## 2. Beobachtungen zum Schreibstil der Modelle
- Die Dateien werden groß: `agent_registry.py` 454 Zeilen (eine Referenz braucht rund 100), viele Kommentare, dieselbe Prüfung in jeder Methode kopiert (AM-003 Lauf 1). Mit der Aufgabenzeile „keine Kopien, keine Kommentare" ging es besser (AM-004: 225 Zeilen, 0 Kommentare).
- Das Modell vergisst Randfälle (Phase 5) **und** schreibt falsche Prüfungen (AM-004 `permissions`: widersprüchlich, siehe `acceptance_step1.py`). Die Eigenprüfung ist in beiden Richtungen unzuverlässig.
- Es gibt oft `answer_cut`, `time` und `turns` bei großen Dateien; bei Nacharbeit liefern die Modelle manchmal nur Kommentare statt Code (AM-004, letzter Lauf vor dem Absturz).
- Stufen mit 3 bis 6 Verhalten gelingen meist im ersten Anlauf; Stufen mit 10 und mehr scheitern (AM-003 `commands`, `outbox`).

## 3. Vermutete Ursachen (zu prüfen)
1. **Kein eigener unabhängiger Maßstab:** GUPPI schreibt Aufgabe, Code und Prüfung mit demselben Modelltyp; ohne externe Abnahme gibt es keinen Beweis.
2. **Zu wenig Kontext über Bestehendes:** Anbindung an Guard, UIX und Registry braucht Kenntnis großer Dateien (`guard.py`, `uix_server.py` 64 KB); das übersteigt Fenster und Aufmerksamkeit des Coders.
3. **Zu große Aufgaben je Schritt** und **zu wenig Zerlegung durch den Planer** (der Planer lieferte oft nichts Brauchbares: „the planner handed in nothing usable").
4. **Rework ohne Befund:** Das Modell bekommt nur die Fehlerausgabe, nicht die Ursache in Worten; mit Befund (Review-Text) gelang es jedes Mal in einem Anlauf.
5. **Wenig Gedächtnis über Lektionen:** höchstens eine Lektion je Prompt, und die war in allen Läufen dieselbe (`unittest.TestCase`-Hinweis), also nicht passend zur Stufe.

## 4. Lösungsansätze zum Entwickeln und Messen
| Idee | Wirkung | Messung |
|---|---|---|
| a) GUPPI schreibt Bauaufträge und Abnahmetests **selbst** (Planer-Rolle mit Vorlage: Verhalten → Tabelle → Test), Claude oder ein zweites Modell prüft nur | nimmt Eingriff A weg | gleiche Stufen mit selbst geschriebenen Tests gegen meine Referenz laufen lassen |
| b) **Referenz-Gegenprobe** für jede Eigenprüfung: eine zweite, unabhängig geschriebene Implementierung muss die Prüfung bestehen, sonst gilt die Prüfung als verdächtig | erkennt falsche und widersprüchliche Prüfungen automatisch | Trefferquote bei den bekannten Fällen (AM-004 `permissions`) |
| c) **Befund-Schreiber:** ein Schritt, der aus Fehlerausgabe und Spezifikation einen Review-Text erzeugt (Ursache in Worten), vor jeder Nacharbeit | nimmt Eingriff B weg | Anteil Stufen, die nach einer Nacharbeit bestehen (Ziel: wie bei meinen Befunden) |
| d) **Dateigrößen- und Kommentarregel automatisch prüfen** und bei Verstoß zurückgeben | kleinerer, lesbarer Code | Zeilen je Funktion, Kommentaranteil |
| e) **Kontext-Auszüge:** für Anbindungsaufgaben nur die relevanten Funktionen (Signaturen, Beispiele) in den Prompt, nicht die ganze Datei | macht Eingriff E möglich | Anbindungsstufe (z. B. Route + Test) als Probeaufgabe |
| f) **Lektionen je Stufe** aus dem Wissensspeicher (Rang nach Stufe, nicht immer dieselbe) | gezieltere Hinweise | Wiederholung von Stufen mit/ohne passende Lektion |
| g) **Test-Aufräumer:** Modelltests, die gegen die Abnahme laufen und scheitern, gehen zurück an das Modell mit dem Befund, statt von Hand entfernt zu werden | nimmt Eingriff C weg | Anzahl entfernter Tests = 0 |

## 5. Plan
1. Nach Abschluss der Integration (AM-005 integriert, Abschlussbericht) die Messdaten sammeln: je Stufe Dauer, Eskalationen, Nacharbeiten, `answer_cut`, `time`, Eigenprüfung, versteckter Test (`measurements/logs/devvm_build_*.json`).
2. Die Eingriffe aus Abschnitt 1 vollständig und mit Zeitaufwand nachtragen.
3. Den erzeugten Code lesen und bewerten (Größe, Duplikate, Kommentare, Lesbarkeit, Fehler, die nur der versteckte Test fand).
4. Lösungen b), c) und g) zuerst bauen (kleinster Aufwand, größte Wirkung nach bisherigen Befunden), dann a).
5. Bericht und Messung mit denselben Stufen vor und nach der Änderung.

## 6. Umsetzung am 2026-10-07 (nach Captain-Auftrag "Empfehlungen umsetzen, aufteilen, bestes Modell je Arbeit")
Gebaut und getestet, Standardwerte unverändert (alles aus, bis ein Lauf es per Optionsdatei einschaltet):
| Maßnahme | Stand |
|---|---|
| `stop` im Manager (Prozessbaum nach PID, bekannter Ausgang) | fertig, 4 Tests |
| Prüfskript zuerst, nur aus der Aufgabe (`check_first`) | fertig, 2 Tests; Importe von Modulen aus den Backticks der Aufgabe erlaubt |
| Code und Prüfskript gleichzeitig (`parallel_check`) | fertig, 2 Tests; nur mit gleichem Modell und 2 Server-Plätzen, sonst nacheinander; **Beschleunigung nicht gemessen** |
| Eigenes Modell für Prüfskript (`checker`) und Schiedsrichter (`arbiter`) | fertig, 1 Test; jede Rezept-ID als Schlüssel möglich |
| Optionen für Läufe über den Manager (`seeds/<spec>.options.json`, feste Schalter) | fertig, 1 Test |

**Beleg für die Modellfrage (2026-10-07):** In AM-005 war die Eigenprüfung nur bei 1 von 6 Stufen richtig (versions); bei hard_filter, resource_fit, score, match und all wurde sie abgelehnt, obwohl der versteckte Test bestand. Prüfskript-Schreiber und Schiedsrichter waren dasselbe Modell wie der Coder (Qwen3-Coder). In AM-004 `permissions` widersprach sich das Skript selbst. Hypothese: ein Modell einer anderen Familie schreibt bessere, unabhängigere Prüfungen.
**Nicht gemessen und deshalb nicht umgestellt:** welches Modell die Prüfung am besten schreibt. Messplan: gleiche Aufgabe `am006_style` mit `check_first`, `checker` und `arbiter` = gpt-oss-20b (Rezept `coder.llama_gptoss`; 98 % Programmieren bei 32k laut Messung vom 3.10); Vergleich: Anteil der Stufen mit richtiger Eigenprüfung (Eigenprüfung stimmt mit dem versteckten Test überein), Dauer je Stufe inklusive Modellwechsel. Basis: AM-005 (1 von 6, 8112 s für 6 Stufen).
**Nicht aufteilbar:** die Stufen selbst (sie bauen auf derselben Datei auf), und zwei verschiedene Modelle gleichzeitig (VRAM: Qwen3-Coder 9 GB von 12 GB).

## 7. Belege für den Schiedsrichter (Idee des Captains, 2026-10-07)
Befund: Der Schiedsrichter sah nur die Aufgabe, bis zu 8000 Zeichen Diff und die letzten 800 Zeichen der Fehlerausgabe, nicht das Prüfskript, und ein Skript bricht beim ersten scheiternden `assert` ab. Neu (`devvm_evidence.py`): jedes `assert` einzeln und bis zum Ende ausgeführt, mit "bekommen / erwartet", dazu die Regel "zu jeder scheiternden Behauptung den Satz der Aufgabe zitieren oder NONE". Realtest am AM-004-Fehlfall zeigt den Widerspruch sofort (21 von 24 scheitern, überall derselbe Zusatzbefund).
Weitere Belege, noch nicht gebaut: (E5) eine zweite, unabhängig aus der Aufgabe geschriebene Implementierung; wenn sie dieselbe Behauptung ebenfalls verletzt, ist die Prüfung verdächtig; (E6) wörtliche Zitate gegen den Aufgabentext automatisch prüfen (existiert der Satz?) und nur dann überstimmen lassen, wenn alle scheiternden Behauptungen unbegründet sind (deterministische Entscheidung statt Modellmeinung); (E7) Verlauf: dieselbe Behauptung scheitert in jeder Runde trotz Änderung.
Messplan: Probe am bekannten Fehlfall (AM-004 `permissions`, Erwartung PASS) und am Gegenfall (Kandidat mit dem echten Fehler, Erwartung FAIL), je mehrere Läufe, Modell Qwen3-Coder; danach die Eigenprüfungsquote in einem Bauauftrag.
