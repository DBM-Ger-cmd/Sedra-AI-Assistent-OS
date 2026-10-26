# Erste Betriebsstunde des Modell-Schedulers mit echten Aufgaben (OP-S2-18)

Stand 27.10.2026, Vorbereitung. Ausgeführt wird sie vom Captain am Rechner, mit dem Cockpit offen und einem GPU-Zeitfenster von rund 90 Minuten.
Ziel: Der Scheduler (Overlay `model_scheduler.yaml`, `enabled: true`, `workers: 3`) trägt eine Stunde echte Arbeit von Agenten ohne Fehler,
ohne Hänger und ohne GPU-Überlast. Die Probeläufe (Schritte 3 bis 7, Agentenlauf-Test) sind bestanden; hier kommt der Dauerbetrieb dazu.

## 1. Vorher (10 Minuten)

1. `python benchmarks/scheduler_probelauf.py vor` zeigt „alles bereit“ (Lease frei, kein Server, RAM mindestens 13 GB frei, Overlay an).
2. `python benchmarks/run_tests.py scheduler desk orchestra uix` ohne roten Test (zuletzt 1001 Tests, 0 rot).
3. Keine Nachtkette, keine Benchmarks, kein zweites Cockpit. Anwendungen schließen, die viel RAM brauchen.
4. Oberfläche neu starten (`START_SEDRA.bat --replace`), damit `workers: 3` gilt. Cockpit offen lassen: Der Takt des Schedulers (`poll()`) läuft nur, solange
   eine Oberfläche die Ereignisse abonniert hat.

## 2. Start der Messung

In einem zweiten Fenster, im Ordner `runtime`:

```bash
python benchmarks/scheduler_probelauf.py stunde --minuten 60
```

Das Werkzeug ändert nichts. Es misst alle 10 Sekunden VRAM, Temperatur, freien RAM, llama-server (Zahl, `-np`), Lease, Übergabe-Schlange und Aufgabenzustände,
zählt die Ereignisse `SLOT_*`, `JOB_*`, `RESOURCE_*` im Audit und schreibt jede Messung sofort nach
`workspace/GUPPI_OS/runtime_data/measurements/beobachtung_<datum>_<zeit>.jsonl`. Strg+C beendet früher und druckt den Bericht trotzdem.

## 3. Agenten und echte Aufgaben

Vorlagen im Paket: `foreman` und `researcher` (`runtime/agent_templates/orchestra/`). Einstellen läuft über die Oberfläche (Agent einstellen, Antrag im Posteingang
freigeben, `set_org`). Beim Einstellen prüfen: Stufe 2 für die Arbeiter, die Leitung darf delegieren (`can_delegate`), Budget gesetzt (kein unbegrenztes Budget in der ersten Stunde).
Ob die Teilrollen Planer, Coder und Prüfer als Vorlagen vorhanden sind, steht erst beim Einstellen fest; wenn nicht, dienen die Aufgaben unten dem Leiter und dem Recherchierer.

Aufgaben, die ohne Dateizugriff lösbar sind (die Beschreibung enthält den nötigen Text) und echten Nutzen haben. Jede einzeln anlegen und einem Agenten zuweisen;
die ersten drei zusammen, damit zwei Slots belegt sind und die dritte wartet:

| Nr | Aufgabe (Titel) | Beschreibung zum Einfügen | Wer |
| --- | --- | --- | --- |
| 1 | Offene Punkte nach Abhängigkeit ordnen | „Ordne diese offenen Punkte nach Abhängigkeit und nenne je Punkt die erste Handlung: Spec 3 Cloud (Design C3.3, Bau-Spec cld_rules, Test mit Anbieter); Spec 4 Tools (U4.3 Bauschritte schneiden, U4.4 Bau); Spec 6 Social (Entwickler-Apps bei LinkedIn und Meta, Freigabeart SOC-07); Spec 7 Wissen (S7.2-F Messung, S7.4 Harness, S7.5 Abnahme); Spec 1 Orchestrierung (O1.2 bis O1.5); K0.6 Doku Local First, Cloud Second.“ | Leitung |
| 2 | Betrieb des Modell-Schedulers in zehn Zeilen | „Schreibe einen Abschnitt ‚Modell-Scheduler im Betrieb‘ in höchstens zehn Zeilen für den Captain: Ein Server, bis zu zwei Slots, ein dritter Lauf wartet; Benchmarks fordern die Lease exklusiv an und der Scheduler übergibt nach dem Drain; ‚Entladen erzwingen‘ in der Werkstatt unterbricht aktive Läufe; ohne geöffnetes Cockpit läuft kein Takt.“ | Arbeiter |
| 3 | Regel 2 auf Widersprüche prüfen | „Prüfe diese Regel auf Widersprüche und Lücken und nenne höchstens fünf Befunde: [Regel 2 GPU aus docs/ENTWICKLUNG.md hier einfügen].“ | Arbeiter oder Prüfer |
| 4 | Testplan für die Mammouth-Bedingungen | „Entwirf einen Testplan in höchstens zwölf Zeilen, mit dem sich prüfen lässt, ob die Cloud-Nutzung Spec 3 (Budget, Inhaltsschutz, Freigabe vor dem Senden) die Bedingungen einhält. Nenne je Punkt Eingabe und erwartetes Ergebnis.“ | Leitung |
| 5 | Wartungsliste der Konfiguration | „Erstelle eine Wartungsliste der lokalen Konfigurationsdateien eines SEDRA-Arbeitsplatzes (role_routing, routing_profiles, switches, model_scheduler, local_paths) mit je einem Satz: Zweck, wer ändert, vorher sichern.“ | Arbeiter |

Danach, wenn die ersten fünf sauber laufen: weitere Aufgaben nach Ihrem Bedarf nachlegen, solange die Stunde läuft (Zufluss gleichmäßig, mindestens drei Läufe in der Schlange).
Ergebnisse der Agenten sind Entwürfe: Der Captain liest sie, übernommen wird nichts automatisch.

## 4. Was beobachtet wird (Bestanden)

Der Bericht am Ende prüft diese Punkte (jeder einzeln):

| Punkt | Grenze |
| --- | --- |
| SLOT_POLL_FAILED | 0 |
| Server gesperrt (SLOT_SERVER_GESPERRT), Müllausgabe (SLOT_SERVER_GARBAGE), verlorene Lease (SLOT_GPU_LEASE_LOST), Absturz (SLOT_SERVER_EXITED) | je 0 |
| gleichzeitige llama-server | höchstens 1 |
| VRAM-Spitze | unter 11,5 GiB (11776 MiB) |
| GPU-Temperatur | unter 85 Grad |
| freier RAM | nie unter 2 GB |
| abgelehnte Reservierungen (RESOURCE_DENIED), fehlgeschlagene Jobs (JOB_FAILED) | 0 |
| Aufgaben der Agenten | mindestens ein Job entstanden |

Zusätzlich von Hand: Die Leiste zeigt zwei belegte Slots und einen Wartenden (`2/2`, `1 wartet`). Ein Chat des Captains während der Läufe antwortet und läuft mit Priorität 7 vor den Agenten.
Die Läufe enden mit `erledigt` oder einer begründeten Rückfrage, nicht mit `BLOCKED`. Danach: Server entladen (Werkstatt), `testlab_cli.py status` zeigt die GPU frei.

## 5. Nachher

1. Bericht und Messreihe ins Logbuch (Typ MESSUNG), Auffälliges als eigener Eintrag.
2. Audit der Stunde auswerten, bevor etwas gelöscht wird (Regel des Captains 26.10.): `runtime_data/audit/events.jsonl` ist die Quelle; Auszüge nach `measurements/` kopieren.
3. Bei Fehlern: Rückweg ist `model_scheduler.yaml` im Overlay löschen oder `enabled: false`, Oberfläche neu starten. Verhalten wie vor Spec 2 (ein Worker, Werkstatt mit eigener Lease).
4. Danach Entscheidung des Captains: Scheduler bleibt an (Overlay stehen lassen), Spec 2 zur Abnahme G4.
