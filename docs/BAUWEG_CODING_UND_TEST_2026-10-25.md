# Bauweg für Coding- und Test-Sitzungen (Stand 25.10.2026)

Anlass: Bei S2.H4b und S1.H9 ging die Zeit nicht ins Bauen, sondern in Umwegen. Der Bauweg `spec_check --vm` → `devvm_build --profile standard` bleibt der einzige Weg für SEDRA-Module (Stempel, G3 je Spec, GPU nur mit Ja des Captains). Dieses Blatt ergänzt ihn um drei Bahnen drumherum.

## Bahnen

| Bahn | Wofür | Wer |
| --- | --- | --- |
| Modul-Bahn | abgeschlossene Module mit Referenz und versteckten Tests (`devvm_specs/<spec>.py`) | SEDRA über den Bauweg |
| Integrations-Bahn | Verdrahtung, Desk, Supervisor, Fixtures über mehrere Dateien | Claude, Review durch Subagent |
| Test-Bahn | Testdateien, die Lücken schließen | Claude; für SEDRA erst nach Entscheidung zu Punkt 4 unten |

## 1. Ein Befehl für Tests: `benchmarks/run_tests.py` (gebaut)

```
python benchmarks/run_tests.py orchestra           # Bereich: orchestra, desk, scheduler, wissen, uix, all
python benchmarks/run_tests.py --changed           # nur Tests zu geänderten Dateien (gegen HEAD; --base <Stand>)
python benchmarks/run_tests.py all --jobs 6        # parallel; schnelle Bahn, ohne Browser-Tests
python benchmarks/run_tests.py all --slow          # mit der Browser-Bahn
```

Pfad und Verzeichnis richtet der Befehl selbst ein. Bekannt rote Tests stehen in `tests/known_red.txt` (mit Grund); nur NEUE Fehlschläge machen den Lauf rot (Exit 1). Ein Test dort, der grün wird, wird gemeldet. Gemessen am 25.10.2026: schnelle Bahn 2891 Tests in 196 s (vorher seriell 928 s), Bereich `orchestra` 350 Tests in 35 s.

Regel für Sitzungen: vor dem ersten Schritt `run_tests.py <Bereich>` (Basis), nach jedem Schritt `--changed`, vor dem Commit der Bereich. Rot ist nur, was nicht in `known_red.txt` steht.

## 2. Abnahme beim Übernehmen (gebaut, Regel)

Beim Schritt „nach G4 übernehmen“ gehört die Abnahme der Bau-Spec ins Repo: Eintrag in `tests/test_orchestra_modules.py` (Orchestra), `tests/test_jobs_modules.py` (Scheduler) oder eine neue Datei nach demselben Muster mit `tests/bau_abnahme.py`. Dort laufen die versteckten Tests der letzten Stufe gegen `src`; relative Importe werden zu einfachen Namen, sonst bleibt alles gleich. Abweichungen von den versteckten Tests (spätere Spec, die der Bau-Spec nicht kannte) stehen in `KNOWN` mit Grund, nie als stillschweigend gelockerter Test. Erstes Ergebnis: alle elf `s1_*`-Specs und `s2_slotplan` bestehen gegen `src`; bekannte Abweichung `wissen_vorschlag` (Spec 7).

## 3. Testnamen beim Entwurf prüfen: `benchmarks/spec_testnames.py` (gebaut)

```
python benchmarks/spec_testnames.py docs/<spec>.md [--lines A-B] [--strict]
```

Meldet Testdateien in den Abnahmetabellen, die es nicht gibt, ohne `(neu)` in der Zeile und ohne Zuordnung in einer `Gebaut (`-Zeile. Beim G3 der Spec mit `--strict` laufen lassen. Stand heute (Spec 1 und 2): 34 Befunde, davon die D1.7-Namen von Spec 1 (die Zuordnung steht jetzt unter der Tabelle) und die noch nicht gebauten Dateien von S2.H5 bis S2.H7.

## 4. Test-Bahn für SEDRA (Entwurf, braucht Entscheidung)

Heute prüft `spec_check` ein Modul. Damit SEDRA auch Testdateien schreiben kann, braucht die Spec eine zweite Art von Aufgabe: „Schreibe `test_x.py`“ gegen eine gegebene Referenz. Bestanden ist sie, wenn

- die Tests an der Referenz grün sind und
- jede Variante aus einer Liste `MUTANTS` (kleine, gewollte Fehler der Referenz, je eine Datei oder ein Patch) mindestens einen Test rot macht.

Umfang: `spec_check` liest `MUTANTS` je Stufe, wendet jede auf eine Kopie der Referenz an und führt die vom Modell geschriebenen Tests aus (in der microVM wie die versteckten Tests). Dazu `devvm_build`: der Kandidat ist hier die Testdatei, die Prüfung sind die Mutanten. Grenzen: höchstens 8 Mutanten je Stufe, Tests müssen unter 30 s laufen. Offen: ob das Profil `standard` genügt, wer die Mutanten schreibt (Claude, mit Review) und ob das Verfahren G3 als neue Art von Spec braucht. Bis zur Entscheidung schreibt Claude Testdateien selbst.

## 5. Sitzungsvorlage

Je Schritt eine Sitzung (oder ein Abschnitt in einer Sitzung) mit festem Auftrag:

```
Schritt:     <ID und Name>
Dateien:     <Liste; keine anderen anfassen>
Fertig, wenn: <Prüfungen in Worten>
Basis:       run_tests.py <Bereich>   (rot nur, was nicht in known_red.txt steht)
Danach:      run_tests.py --changed, dann der Bereich; ein Commit je Schritt (Nachricht nennt Schritt-ID)
Review:      Subagent (Opus) liest den Diff gegen die Spec-Zeile, meldet Abweichungen; Ergebnis ins Logbuch
Nicht tun:   keine GPU-Läufe, keine Schalter, kein Push ohne Auftrag, keine eigene Sedra-Kopie (Abschnitt 6)
```

Bauort seit dem Umzug (26.10.2026): Projektordner für `devvm_build`, `spec_check --vm --project` und `vm_latency` ist immer `<a1>\workspace\GUPPI_OS` (`E:\Sedra Umgebung\A1 Sedra Main Branch Entwicklungs umgebung\workspace\GUPPI_OS`), Python ist `<a1>\runtime\.venv\Scripts\python.exe`, die eine Startdatei ist `<a1>\START_SEDRA.bat`. Nie der Ordner der alten Installation (`GUPPI_Runtime_v1.20`): ein falscher Projektordner legt einen neuen, leeren VM-Cache an.

Arbeitsverzeichnis: A1 oder der Worktree, den die App für die Sitzung anlegt; keine eigenen Auscheckungen (Abschnitt 6). Das Repo (`architecture/…/hardware_manager/…`) scheitert in sehr tiefen Pfaden an der Windows-Pfadlänge; für einen unvermeidbaren Auszug eines alten Stands gilt der eine Ordner `C:\sb` aus Abschnitt 6.

## 6. Regel: keine eigene Sedra-Kopie je Sitzung (26.10.2026)

Es gibt genau diese Arbeitsorte: den Entwicklungsstand A1 (`E:\Sedra Umgebung\A1 Sedra Main Branch Entwicklungs umgebung`), die Installation (`GUPPI_Runtime_v1.20`, nur der Captain und Betrieb) und die Worktrees, die die App für eine Sitzung selbst anlegt. Darüber hinaus gilt:

- Keine Kopie des Repos oder der Installation anlegen (kein `git archive`/`robocopy`/Zip-Auspacken in einen neuen Ordner, kein zweiter Auszug „zum Vergleichen“). Vergleiche gegen einen alten Stand laufen über `git show <stand>:<datei>` oder `git diff`; braucht ein Test wirklich einen alten Baum, dann in genau einem Ordner `C:\sb` (kurzer Pfad), der nach der Prüfung wieder geleert wird, und der Fund steht im Bericht der Sitzung.
- Keinen zweiten Sedra-Server, keine zweite Oberfläche und keinen zweiten Modellserver dauerhaft starten. Prüfläufe (`uix_check`, Tests) starten ihren Server auf einem temporären Projekt und beenden ihn; was danach noch läuft, beendet die Sitzung selbst.
- Temporäre Ordner nur über `tempfile` mit den Präfixen aus `benchmarks/hygiene.py` (`TEMP_PREFIXES`), damit sie sich aufräumen lassen.
- **Eine Version (Captain, 26.10.2026):** Es gibt nur noch SEDRA in A1. Alte Daten (Installation `GUPPI_Runtime_v1.20`, `E:\WEb Projekte`, Archive) überschreiben nie etwas in A1; Kopieren nur fehlender Dateien (`robocopy /XC /XN /XO`, nie `/MIR`, `/PURGE`, `/MOVE`), Konfiguration nur ergänzend und vorher gesichert. Der Platzhalter `<guppi>` zeigt auf A1.
- Worktrees: höchstens einer je laufender Sitzung; ist der Branch vollständig im Hauptbranch, wird die Sitzung archiviert und der Worktree aufgeräumt.

Prüfen: `python benchmarks/hygiene.py` (nur Anzeige): unbekannte Kopien unter `E:\Sedra Umgebung`, aufräumbare Worktrees, Sedra-Reste im Temp-Ordner, laufende Sedra-/llama-Prozesse. `--apply-temp` löscht nur Temp-Ordner mit Sedra-Präfix, älter als 24 Stunden. Vor jedem Sitzungsabschluss und beim Archivieren einmal laufen lassen.
