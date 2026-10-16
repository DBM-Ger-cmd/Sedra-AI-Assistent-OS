# little-coder und GUPPI im Vergleich (2026-10-10)

Quellen: lokale Kopie `<projekte>\little-coder-main` (nur gelesen), unsere Messungen in `docs/MODELL_VERGLEICH_ERGEBNISSE.md`, Logbuch. Wichtig vorab: **die Aufgaben sind nicht dieselben.** little-coder wurde auf Aider-Polyglot gemessen (kleine Aufgaben mit offenen Tests im Ordner), wir auf mehrstufigen Aufgaben mit versteckten Abnahmetests (am007 bis am010, bench_std). Zahlen sind nicht vergleichbar, Mechanismen schon.

| Bereich | little-coder | GUPPI (Stand heute) | Bewertung |
|---|---|---|---|
| Modell / Server | Qwen3.6-35B-A3B, llama.cpp, `-n-cpu-moe 999`, Flash Attention an, 32k, 38 Token/s auf 8 GB | Qwen3.6-35B-A3B, llama.cpp, `n_cpu_moe 28`, Flash Attention **aus** (Abstürze), 32k, 34 bis 45 Token/s auf 12 GB | gleiche Klasse; wir sind pro Zug nicht schneller |
| Ergebnis | 177 von 225 (78,7 %) Aider-Polyglot, Eigenmessung des Autors | bench_std 4/4; am009 3/3; am007 4/7 in beiden Läufen | nicht vergleichbar (siehe oben) |
| Wer urteilt | die offenen Tests der Aufgabe (der Agent darf sie selbst laufen lassen); zweiter Versuch mit der Testausgabe | versteckter Abnahmetest, der Entwickler sieht nur den Fehlerbericht | unser Rahmen ist strenger und schwerer |
| Schreiben in bestehende Dateien | **Write verweigert** (jede Größe), `edit` mit `edits[]` | bisher überschrieben; **jetzt** `write_file` verweigert ab 10 Zeilen, `edit_file` mit `edits` | übernommen (heute) |
| Schleifen / leere Antworten | Qualitätswächter **korrigiert** per Nachricht, Lauf geht weiter | Wächter **beendete** den Lauf; **jetzt** eine Korrektur, dann Ende | übernommen (heute) |
| Denken | Obergrenze 4096 Token, danach aus und weiter | aus (`reasoning off`) | offen: Messung M4 (Planer) |
| Kontext | Kaltstart etwa 7k, Kompaktierung bei 80 %, Lese-Schutz (30 Zeilen) | Kompaktierung bei 60 %, Schreibtexte gekürzt, `read_file` in 150-Zeilen-Teilen, `outline`, Karte des Arbeitsbereichs | ähnlich |
| Systemtext | wird nie pro Zug geändert (Cache) | pro Gespräch fest | gleich |
| Wissenskarten | kleine Karten (80 bis 150 Token) je Absicht und nach Fehlern | ein langer Systemtext je Rolle | offen |
| Planen | Plan-Modus als Erweiterung, `dispatch` für Unter-Coder | Planer teilt in Schritte mit wörtlichen Auszügen, Schnittstellen, Übergabenotizen (Option, noch ohne Wirkungsnachweis) | wir sind weiter, aber ungemessen |
| Selbstprüfung | keine eigenen Prüfskripte; Tests der Aufgabe | Entwickler schreibt `check_*.py`, bis 8 VM-Läufe, dazu `debug_*.py` | **mögliche Zeitfresser** (siehe unten) |
| Mehrere Agenten | wenige, nur lesende Unter-Coder | früher Planer, Prüfer, Coder, starker Coder, Schiedsrichter; heute **Solo** | wir haben das Team bewusst zurückgebaut |
| Werkzeuge | read, write, edit, bash, glob, grep, web | list, read, outline, write, append, edit, run_python (VM), Syntax, Git | ähnlich; **kein freies bash** bei uns (Sicherheit, VM) |
| Sicherheit | Rechte-Tor, Browser, Shell auf dem Rechner | alle Läufe in der microVM, Gates des Captains, Schutz vor Löschen | **unser Vorteil** |
| Messbarkeit | Benchmark-Skripte, Ergebnisdateien | Messdateien je Lauf, Vergleichstabelle, Sonden (Planer, Prüfer, Standardtest) | **unser Vorteil**, nur mit Zeitstempel-Fehlern im Logbuch |

## Zur Frage des Captains: sind unsere zusätzlichen Prüfschritte zu aufwendig und zu oft im Einsatz?
Die Daten sprechen dafür, aber sie beweisen es nicht:
- Im Team-Betrieb brachten Checker, Reviewer und Schiedsrichter nichts: eigene Prüfung stimmte nur in 31 von 60 Fällen mit dem versteckten Test überein; die Prüfer-Sonde ergab 0 von 4 brauchbaren Prüfungen (Qwen3.6 und Qwen3-Coder). Solo war gleich gut und 1,5- bis 3-mal schneller.
- Im Solo-Betrieb bleibt die Selbstprüfung: Im laufenden am007-Lauf (Stand 14:25) endeten **6 von 11** Entwicklerläufe am Rundenlimit (45 Runden), 3 mit Abgabe, 1 Zeitlimit, 1 `runaway`. Dabei legte der Entwickler 9 Hilfsdateien an, die das Aufräumen löschen musste (5 `check_*.py`, 4 `debug_*.py`). Er verbringt also viele Runden mit eigenen Prüf- und Fehlersuchskripten, die nicht abgegeben werden.
- little-coder kommt ohne eigene Prüfskripte aus; es verlässt sich auf offene Tests und einen zweiten Versuch mit der Fehlerausgabe. Wir können die Tests nicht offenlegen, aber wir können den Fehlerbericht lesbar machen (heute geschehen).
- **Neu messbar:** `--self-check full|light|none` (Standardtest-Modi `solo`, `solo-light`, `solo-none`): `full` = bisher (ein Prüfskript, bis 8 VM-Läufe), `light` = ein kleines Prüfskript, höchstens 2 VM-Läufe, Prüfungen nicht debuggen; `none` = kein Code ausführbar, nur die Aufgabe gegen den Code lesen. Zu messen: Standardtest mit je 2 Läufen je Modus, danach am009 und am007 `slots`.
