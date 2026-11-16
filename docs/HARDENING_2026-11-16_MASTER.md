# Hardening-Runde 16.11.2026: Master-Modus, Gedächtnis, Sitzungspost, Gruppe 1

Basis: `main` `5db7e67`. Branch `hardening-master` (Commits `e7d532d`, `1367257`, `418dc20`), kein Merge, kein Push. Prüfer: unabhängige Sitzung (nicht der Bauende). Methode: je Angriff ein Test, der ROT wird, wenn der Schutz fehlt; die Funde wurden gegen den Stand vor der Änderung rot gesehen. Alle Testwerte sind erfunden. G4 für `harness/master.py`: vom Captain in dieser Sitzung erteilt (16.11.2026, Dateiliste: nur `master.py`; Diff vorgelegt).

## 1. Ergebnis in Kürze

| Schwere | Fund | Stand |
|---|---|---|
| **Hoch** | M-1 Geschützte Pfade über Befehlsargumente: unter dem Master schrieb `xcopy` (und jedes Programm mit Pfad-Argument) ohne Karte in `local_config`, Katalog, Harness-Code, `.git`, Ablage der Harness | behoben |
| **Hoch** | M-2 Die Sperrliste ist eine Verbotsliste: von 521 Probezeilen liefen 334 durch (u. a. `gh api`, `docker`, `wmic`, `setx`, `regedit /s`, `shutdown`, `conhost cmd`, `forfiles`, `perl -e`) | behoben (positive Programmliste): 63 von 521 laufen noch durch, alle gewollt (Tests, Skripte, einfaches Git) |
| **Hoch** | M-3 `python -Ic/-Sc/-Bc/-cX` und `-mpip install` umgingen die Sperre „Programmtext auf der Befehlszeile“ und „pip install“ (gebündelte Schalter) | behoben |
| Mittel | M-4 `pip -q install`, `pip --proxy x install`, `pipx`, `uv`, `poetry`, `conda`, `python setup.py install`, `npm --silent install`, `npm -g install` (Schalter vor dem Unterbefehl) | behoben |
| Mittel | M-5 Git: `git branch -Df/-fd/-C`, `git checkout .`/`restore .`/`stash drop`/`reflog expire`, `git ls-remote`, `git daemon`, `commit --amend` | behoben (Unterbefehle als positive Liste, gebündelte Kurzschalter gelesen) |
| Mittel | M-6 `node --eval=`, `-pe`, `-r`, `--import`, `--loader` | behoben |
| Mittel | G-1 Sitzungspost: Datenblock ließ sich schließen (`[Ende Sitzungspost]` im Text) und die Kopfzeile nachbauen; danach scheinbare Captain-Anweisung | behoben (jede Zeile der Nachricht zitiert) |
| Mittel | G-2 Gedächtnis: Filter „Anweisung“ und „Schlüssel“ scheiterten an doppeltem Leerzeichen, Umbruch, geschütztem Leerzeichen, unsichtbaren Zeichen, voller Breite | behoben (Filter auf normalisiertem Text) |
| Niedrig | G-3 Notiz mit `---` im Hinweis wurde geschrieben, aber unlesbar (verschwand aus Liste, Index-Zeile blieb) | behoben |
| Niedrig | G-4 Notizname `con`, `nul`, `aux`, `com1` … war erlaubt (unter Win 11 Build 26300 funktioniert es, auf älteren Windows ist es ein Gerät) | behoben (Namen abgelehnt) |
| Niedrig | D-1 Aufbewahrung: ein Zeitpunkt in der Zukunft oder `Infinity` in `local_config/aufbewahrung.json` sperrte den Lauf auf Dauer | behoben |

Offen / nur Befund: siehe §4.

## 2. Beleg und Gegenprobe je Fund

Tests: `runtime/tests/test_hardening_master_2026_11_16.py` (25), `test_hardening_gedaechtnis_post_2026_11_16.py` (29), `test_hardening_aufbewahrung_2026_11_16.py` (9). Vor der Änderung rot: im Master-Teil 13 von 31 (nach Bereinigung zweier eigener Fehlannahmen in den Tests, die Zustandsproben waren von Anfang an grün), im Rest 8 von 38; danach alle 69 grün.

- **M-1** `test_ganzer_weg_xcopy_in_local_config`: `Kiste.aufruf('befehl', 'xcopy docs\neu.txt local_config\harness_projekte.yaml /Y')` mit Master auf `**` lieferte `status ok, stufe master`, die Datei in `local_config` war überschrieben. Ursache: `vorbehalte.pruefen` prüft bei `befehl` nur die Zeile als Text (Präfix), die Pfade der Argumente prüfte weder er noch `master.sperre_befehl`. Folge wäre gewesen: das Modell schreibt eine Textdatei (nicht „Code“, kein G4-Treffer) und kopiert sie über `local_config/harness_projekte.yaml` (Feld `master` und `schreibbereich` weiten) oder den Katalog. Behebung: jedes Argument (auch `--opt=`, `/opt:`, `-oWert`) und der Arbeitsordner werden gegen `vorbehalte.PFADE` geprüft (`master._geschuetzt`), außer bei rein lesenden Programmen (`git status/diff/log/show …`, `findstr`, `where`, `tree`, `rg`, `grep`, `node --check`, `python -m py_compile`, `pip list`).
- **M-2** Probe `scratchpad/probe_a.py` (521 Zeilen) gegen `sperre_befehl`; Behebung: Programme außerhalb `PROGRAMME` bleiben Karte; Programm mit Pfad oder Endung außer `.exe` (`.\git.bat`, `docs\x.cmd`) ebenfalls.
- **M-3 bis M-6** Tests `test_python_*`, `test_installieren_andere_wege`, `test_node_*`, `test_git_zweige_und_verlust`, `test_netz_und_cloud_werkzeuge`, `test_systemwerkzeuge_und_lolbins`, `test_andere_interpreter_mit_programmtext`; Gegenprobe zur Gegenprobe `test_beabsichtigtes_bleibt_erlaubt` (Tests, `py_compile`, `git status/diff/log/add/commit`, `checkout feature`, `checkout -b neu`, `node --check`, `pytest` bleiben ohne Karte).
- **G-1** `test_block_laesst_sich_nicht_vorzeitig_schliessen`, `…_kopfzeile_…`: der Block enthielt zweimal `[Ende Sitzungspost]` bzw. zwei Kopfzeilen.
- **G-2/3/4** `test_anweisungsfilter_…`, `test_schluesselfilter_…`, `test_kopf_mit_trennlinie_bleibt_lesbar`, `test_name_windows_geraetenamen`.
- **D-1** `test_zeitpunkt_in_der_zukunft_…`, `test_unendlich_und_unsinn_im_zeitpunkt`.

## 3. Geprüft, nicht gefunden (was versucht wurde)

**A Master-Modus**
- Pfad-Quirks bei `datei_schreiben` unter dem Master `**`: `docs/../runtime/…/master.py`, Groß/Klein, Punkt oder Leerzeichen am Ende, `::$DATA`, `:strom`, `\\?\`-Präfix, absoluter Pfad, 8.3-Kurzname, Junction auf einen geschützten Ordner, Junction nach außen: alle ohne Schreiben (`resolve` im Werkzeug normalisiert vor dem Vorbehalt; Status `wartet`, `hinweis` oder `fehler`, geschützte Dateien unverändert).
- Zustand: Neustart (neues Objekt = aus, nichts in einer Datei), Ablauf nach 24 h (23:59 an, 24:00 aus), Löschen der Sitzung beendet ihn (`loeschen` ruft `master.aus`; `aufraeumen` geht über `loeschen`), anderes Projekt und andere Sitzung decken nicht, kaputter Eintrag oder Datum = nie frei, ungültiges Feld `master` schaltet nicht ein, Aus und Ablauf lösen die Rücknahme eines laufenden `befehl` aus, erneutes Ein vergisst das alte Aus.
- Das Modell hat kein Werkzeug, das den Master schaltet; `gedaechtnis_*`, `sitzung_nachricht` kennen ihn nicht (Test), `master_schalten` Klasse H über die Tür (vorhandene Prüfstelle grün).
- Wiederholungsdeckel unter dem Master: dritter gleicher Aufruf wird Karte. Audit je Aufruf (`HARNESS_MASTER_AN`, `_AUFRUF`, `_NICHT`, `_AUS`) vollständig und ohne Inhalt.
- Planted Programm im Arbeitsordner (`git.cmd`): `shutil.which` findet es mit Python 3.14 nicht (System-`git` gewinnt).
- Unicode-Ähnlichkeiten (`‥`, volle Breite `．．`, `／`, `∕`) sind unter Windows keine Pfadtrenner: keine Umgehung. UNC, `\\?\`, `\\.\`, `%VAR%`, `$env:`, `~`: werden gesperrt.
- Cloud-Modell: `Kiste(lokal=False)` → Karte (Test). Siehe aber O-3.

**B Gedächtnis**: Pfad-Traversal in Name und Projekt-ID (`..`, `/`, `\`, NUL, Großbuchstaben, 41 Zeichen), Projektgrenze, Verknüpfung des Projektordners nach außen (nichts geschrieben), Überschreiben (`neu` bei vorhandener Notiz abgelehnt), Größenkappen (4 000 Zeichen, 150 Hinweis, 100 Notizen, Kontextkappe auch bei 100 000-Zeichen-Zeile), kaputte Notiz/Index/Binärdatei, Rechte im Notiztext (kein Feld wirkt, Modul importiert weder Master noch Freigabe), Index-Zeile bleibt eine Zeile (`\n`, `\r\n`, U+2028, U+0085).

**C Sitzungspost**: Absender kommt fest vom Server (`von='captain'` im Weg; gefälschte Absender-ID `S-ZZZZZZZZ`, `../S-…` abgelehnt), zwei Fenster schreiben sich nicht endlos (Bremse nach `HOPS_MAX`), gefälschte `hops` (-1, 2, 99, `None`, Text) abgelehnt, Stunden- und Ungelesen-Deckel, Post an sich selbst und ins fremde Projekt, Nachricht ist nie Karte/Erlaubnis/Freigabe, Audit ohne Text, Titel des Absenders kann den Block nicht verlassen (Titel wird einzeilig).

**D** `rollen.js` sagt im Kopf ausdrücklich „ANZEIGE … schützt nicht gegen Administratorrechte“ (AM7 §2); nichts zu beanstanden. `_a01_an_pruefung` und der Aufruf in `gateway_approve` (a01_an_rolle_pruefung, Audit) gelesen, kein Fund. Aufbewahrung: Richtlinie prüft positive Ganzzahlen; der Lauf löscht nie selbst (nur `harness.loeschen` = Verschieben); Schreibfehler am Zeitpunkt = Vermerk, kein Absturz; Audit ohne Titel und Namen.

**E**
- `test_harness_oberflaeche_weg.py` Zeile 78: auf `5db7e67` **kein** Syntaxfehler; er war schon mit `d42d131` repariert; `compileall` über `tests` und `src` ohne Fehler. Neu gefunden und behoben: SyntaxWarning (`\s`) im Docstring von `test_harness_lernen.py`.
- Die fünf roten Tests (`SEDRA_BROWSER=1`) hatten Ursachen in den Tests, nicht im Produkt: `test_uix_shell_start` erwartete eine Shell-Liste in alter Reihenfolge (der Code sortiert alphabetisch; Erwartung angepasst), `test_process_browser` 3×: zwei versteckte Datei-Eingaben im n8n-Werkzeug (Selektor jetzt eindeutig). Danach 17/17 grün (`test_uix_shell_start`, `test_process_browser`).
- `test_uix_harness_wege`: im Lauf grün und einzeln grün; kein Fehler reproduziert (Aufräumen unter Last bleibt als Windows-Eigenheit möglich, nicht gesehen).
- Im Gruppenlauf zwei Rote (`test_harness_lauf.test_toter_prozess_ohne_ende_ist_verloren_nie_ok`, `test_uix_harness_lauf.LaufServerTests` mit WinError 32 beim Aufräumen): beide **einzeln grün** (27 Tests, `test_harness_lauf`, `test_uix_harness_lauf`, `test_uix_harness_wege`) = Last bei 12 parallelen Gruppen; keine Berührung mit den geänderten Dateien.

## 4. Offen und Empfehlungen (nicht behoben)

1. **O-1 (Mittel) Aufgaben und Sitzungs-Erlaubnis haben dieselbe Lücke wie M-1**: der feste Vorbehalt prüft bei `befehl` keine Pfad-Argumente. Eine Aufgabe oder „Für diese Sitzung erlauben“ mit einem Befehlsmuster (`xcopy*`) schreibt ebenso in geschützte Pfade. Empfehlung: die Prüfung `master._geschuetzt` in `vorbehalte.pruefen` für `befehl` übernehmen (G4: `vorbehalte.py`, hier nicht umgesetzt, weil es auch Aufgaben anders einstuft).
2. **O-2 (Niedrig) Wiederholungsdeckel (MM-15) ist umgehbar**: Schlüssel = Werkzeug + Ziel + Argumente; eine geänderte Leerstelle oder ein Zusatzargument zählt als anderer Aufruf. Gegen Schleifenfehler wirkt er, gegen ein absichtlich variierendes Modell nicht. Zähler zusätzlich je Zug nach normalisierter Zeile wäre eine Option (G4: `deckung.py`).
3. **O-3 (Niedrig, latent) `Kiste.lokal` wird in `api._kiste` nicht gesetzt** (Standard `True`; Spec §11 nennt es). Heute gibt es in der Harness nur lokale Modelle (`PROVIDER`), die Cloud-Sperre des Masters greift erst, wenn jemand `lokal` setzt. Empfehlung: `lokal=` explizit aus dem Anbieter der Sitzung übergeben, bevor ein Cloud-Modell in die Harness kommt (`api.py`, nicht geschützt).
4. **O-4 (Niedrig) Rest der Positivliste**: `python skript.py`, `pytest`, `npm run` (Skripte in `package.json`), `pytest -p`, `tsc` führen Code aus, den das Modell geschrieben haben kann. Das deckt nur G4 (ungesehener Code). Bekannte, in der Spec (§6) genannte Grenze; die Sperrliste ist ein Zeilenprüfer, kein Käfig. Wird G4 für den Master später gelockert, ist der Master Vollzugriff.
5. **O-5 (Niedrig) Aus-Knopf gegen `datei_schreiben`**: zwischen Deckungsentscheidung und Schreiben liegt ein winziges Fenster; ein laufender `befehl` endet dagegen sofort (Rücknahme). Kein Eingriff nötig.
6. **O-6 (Niedrig) Anweisungsfilter bleibt Heuristik**: Umschreibungen (`disregard prior guidance`) passieren; der eigentliche Schutz sind der Antrag mit Karte beim Captain und die Kennzeichnung „Daten von früher“.
7. **O-7** Neue Positivliste kann den Alltag zu Karten machen (`git reset`, `git rm`, `xcopy`, `findstr`-Ketten). Ob weitere Programme auf die Liste sollen, entscheidet der Captain am PC nach der Abnahme (nur enger frei, weiter mit G4).

## 5. Nicht geprüft

- Kein echter Modelllauf, kein Server-Neustart am PC, keine GPU; Einschalten über die Tür und Aus-Knopf in der Oberfläche nicht gesehen (nur die Logik und die vorhandenen Tests).
- `uix`-Oberflächenteile des Masters (Schild, Taskleiste) nicht im Browser geprüft.
- Windows-Eigenheiten nur auf diesem Rechner (Win 11 Build 26300, Python 3.14); 8.3-Kurznamen waren auf dem Temp-Datenträger vorhanden und wurden geprüft, auf anderen Datenträgern nicht.
- Mehrere gleichzeitige Sitzungen am selben Projekt (nur einzeln; jede Sitzung hat ihren eigenen Schalter).
- Fremde Harnesses (`master.entscheiden`, MM-13) nur gelesen, nicht gegen Angriffe getestet.

## 6. Testläufe (Exit-Codes)

| Lauf | Ergebnis |
|---|---|
| `run_tests.py harness desk` | 1331 Tests, 7 übersprungen, 2 rot (nur unter Last, einzeln grün), Exit 1; die Prüfstellen `test_freigabe_vollstaendig`, `test_harness_werkzeug_vollstaendig`, `test_harness_deckung_vergleich` grün |
| `unittest test_harness_lauf test_uix_harness_lauf test_uix_harness_wege` | 27 Tests, OK, Exit 0 |
| `SEDRA_BROWSER=1 unittest test_uix_shell_start test_process_browser` | 17 Tests, OK, Exit 0 (vorher 4 rot) |
| neue Tests (3 Dateien) | 69 Tests (31 + 29 + 9), OK, Exit 0 |

## 7. Skript

`runtime/tools/scan_pfade_schluessel.py` (liest nur): scannt die gegenüber `main` geänderten und neuen Dateien oder angegebene Dateien nach lokalen Pfaden und Schlüsselmustern, meldet Datei:Zeile und Art, nie den Wert, Exit 1 bei Treffern. Lauf über den Branch: 2 Treffer, beide Fantasiewerte in Filter-Testfällen (`test_hardening_gedaechtnis_post…:40`, `test_harness_gedaechtnis_notizen:50`); die neuen und geänderten Quelldateien und Docs sind sauber.
