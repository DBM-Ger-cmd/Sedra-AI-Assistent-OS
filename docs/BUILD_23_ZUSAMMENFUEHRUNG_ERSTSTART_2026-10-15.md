# Build 23: Zusammenführung mit dem Entwickler-Archiv Build 19, sauberer Erststart (15.10.2026, Ticket B6-G-05)

**Klaus, 18:12:** *„Kannst du die beiden Versionen einmal zusammenführen – achte unterwegs auf Fehler; ganz wichtig der SEDRA-Start für
einen sauberen Erststart.“* Geliefert: `SEDRA_Entwickler_Archiv_Build19_2026-10-15.zip` (Quellcode Build 19, Git-Bundle bis `2692c37`,
sieben Entwicklerdokumente, ein nicht committeter Patch „ein einziger Start, Oberflächenauswahl, `uix_start --liste`“).

## 1. Was zusammengeführt wurde

| Seite | Stand | Beleg |
|---|---|---|
| A: Entwickler-Archiv | Build 19 (`2692c37`) + nicht committeter Patch `aenderungen_START_SEDRA_und_Auswahl.patch` (16 Dateien) | Archiv `git/` |
| B: Arbeitsstand dieser Sitzung | Build 20 (= 19 + 19b) + Tickets B6-G-01, B6-G-03, B6-G-04 (Build 22) | Git dieser Kopie |
| Gemeinsame Basis | Build 19 `2692c37`; Build 20 ist als Commit `1411eab` darauf gesetzt (Dateistand identisch mit dem ZIP `1e918b97…`) | `git diff --quiet` |
| Ergebnis | **eine lineare Historie**: Archiv bis Build 19 → Build 20 → G-01 → G-03 → G-04 → **Build 23** (dieser Build) | `git log` |

Der Start-Patch wurde dreiwege auf Build 22 angewendet: 14 Dateien sauber, zwei Textkonflikte (`README.md`, `docs/BETRIEB.md` –
beide Seiten hatten den Start-Absatz geändert) von Hand mit beiden Inhalten aufgelöst. Entfernt wie im Patch: `ERSTER_START.bat`,
`START_GUPPI.bat`, `GUPPI_EINRICHTEN_UND_STARTEN.bat`. Neu: Oberflächenauswahl beim Start (Menü in `START_SEDRA.bat` aus
`uix_start --liste`), `README`, `BETRIEB`, `READY_TEST_WINDOWS.bat`, `Erststart_Konfig.ps1`, `uix/js/core.js`, `uix/ui/api.js`,
`uix_start.py`, `test_uix_start.py`, `start_sedra.sh`. Die sieben Entwicklerdokumente liegen unter `docs/entwickler_archiv_build19/`
(Stand Build 19, unverändert; was sie beschreiben, ist seitdem durch Build 20–23 ergänzt).

## 2. Fehler, die beim Erststart aufgefallen sind – und was geändert wurde

| Nr | Befund | Wirkung | Änderung |
|---|---|---|---|
| E1 | `runtime\portable\sandbox` (microsandbox-Wheel + `RELEASE_LOCK.json`) ist nicht im Paket; `build_offline_runtime.py` verlangte es, `Test-PortableRuntime.ps1` verlangte `sdk_version 0.7.4`, `START_SEDRA.bat` brach vorher ab | **Windows-Erststart aus dem ZIP unmöglich** (im Archiv-LIES_MICH als bekannt beschrieben) | Das SDK ist **optional**: fehlt der Ordner ganz, wird ohne SDK paketiert (`sdk_version: none`, Hinweis); ist er da, muss er genau stimmen (Pinning bleibt). `Test-PortableRuntime.ps1` akzeptiert `none`. `START_SEDRA.bat` gibt einen Hinweis und richtet ein. Nur die DevVM braucht das SDK (`sandbox/worker.py` meldet `pinned_sdk_required`). Tests: zwei neue in `test_offline_bundle` |
| E2 | `start_sedra.sh`, `START_SEDRA.command`, `runtime/*.sh` ohne Ausführungsrecht in **allen** gelieferten ZIPs (aus Windows gepackt) | macOS/Linux: „Permission denied“ beim ersten Start | Rechte im Git gesetzt (`100755`), ZIP trägt sie; `START_SEDRA.command` ruft `sh ./start_sedra.sh`; README/START_HERE nennen `sh start_sedra.sh` |
| E3 | `Erststart_Konfig.ps1` warf bei fehlender Engine → `START_SEDRA.bat` brach ab, obwohl Modellordner und Schalter schon geschrieben waren; ebenso `engine_download.py` mit Fehlercode | Erststart ohne Netz oder ohne Engine endete im Fehler statt in der Oberfläche | Beide Stellen sind **Hinweise**: die Oberfläche startet, ohne Engine antwortet kein Modell; Protokollzeile in `einrichtung.log` |
| E4 | `START_HERE.txt` nannte noch Build 7 und die alten Starter | Verwirrung beim Einstieg | neu geschrieben (Windows, macOS/Linux, Umschalter, GateWay, Archiv) |
| – | geprüft und in Ordnung: Menü in `START_SEDRA.bat` (`for /f` mit `--liste`, `call set` für die Auswahl, Rücksprung bei falscher Eingabe), `-I`-Pfad des portablen Pythons (`._pth` enthält `../../../src`), Entwicklerpfad mit `.venv`, `--replace`, `start_sedra.sh` (venv, PyYAML aus System-Site-Packages, dulwich als Hinweis) | | |

**Erststart Linux, frische Kopie ohne `.venv` (selbst ausgeführt, 15.10. 18:40):** venv angelegt, PyYAML vorhanden, dulwich hier ohne Netz
→ Hinweis, Server auf 127.0.0.1 mit Übersicht der Oberflächen, kein Fehler. **Windows nicht ausgeführt** (keine Windows-Maschine hier):
`START_SEDRA.bat` wurde gelesen und auf Logik geprüft, nicht gestartet.

## 3. Abnahme (Linux)
| Was | Ergebnis |
|---|---|
| `test_uix_start` (inkl. Start-Patch: keine alten Starter, Übersicht/Direkt/--gewaehlt, `--liste`) | grün |
| `test_offline_bundle` (+2: ohne Sandbox-Ordner paketiert; vorhandener, aber falscher Ordner wird abgewiesen) | grün |
| Volle Suite | 2.132 Tests, 1 Fehler = bekannter Umgebungsfehler `library_not_built`, 49 übersprungen (386 s) |
| `uix_check`, `test_uix_flows` | unverändert zu Build 22 (keine Änderung an Shells/Werkzeugen in diesem Build) |

## 4. Für den Captain
- Windows: `START_SEDRA.bat` aus dem ZIP an einem beschreibbaren Ort starten; erwartet: Einrichtung (Download-Frage), Hinweis „ohne Sandbox-SDK“, Modellordner-Frage, Engine-Prüfung (Download-Frage), Oberflächen-Menü. Bitte `runtime\einrichtung.log` zurückgeben.
- Wer die DevVM braucht: `runtime\portable\sandbox` aus einer funktionierenden Installation kopieren, `runtime\portable\python` löschen, neu starten.
- Git: `git clone sedra_history_build23.bundle` (liegt getrennt neben dem ZIP) liefert die ganze Historie bis Build 23.
