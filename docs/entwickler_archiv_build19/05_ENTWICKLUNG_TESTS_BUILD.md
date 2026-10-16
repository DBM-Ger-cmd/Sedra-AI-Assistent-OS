# 05 – Entwicklung, Tests und Build

Dieses Dokument beschreibt den Weg vom Quellcode zu einem geprüften Paket. Die Regeln für Menschen und KI-Sitzungen stehen im Quellcode in `docs/ENTWICKLUNG.md`; hier die praktischen Schritte.

## 1. Voraussetzungen

- **Python 3.11 oder neuer** (`requires-python >= 3.11` in `runtime/pyproject.toml`). Die Entwicklung lief zuletzt auf Python 3.13.
- **Abhängigkeiten** (`runtime/requirements.txt`): PyYAML, dulwich (Git in reinem Python, für die DevVM), urllib3.
- **Betriebssystem:** Die Entwicklung lief auf Windows (Ziel) und Linux (Container). Tests, die nur auf einem bestimmten PC laufen können (Windows, Modelle, Engines, dulwich), überspringen sich mit einem Grund über `tests/env_skip.py`. **Rot heißt kaputt**, übersprungen heißt nur „hier nicht möglich“.
- **Modelle und Engine** sind für die Tests nicht nötig. Modellaufrufe in Tests laufen über ein Fake-Modell.

## 2. Einrichten

```
cd runtime
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt     # Linux/macOS
.venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
```

Den Ordner `runtime/.venv` legen die Startdateien selbst an (`START_SEDRA.bat` bzw. `start_sedra.sh`).

**Windows-Ersteinrichtung:** `START_SEDRA.bat` ruft beim ersten Mal `runtime/Ersteinrichtung.ps1` auf. Die Datei verlangt `runtime/portable/sandbox/RELEASE_LOCK.json` und das gepinnte SDK-Wheel (microsandbox 0.7.4, Windows x64) sowie Python 3.14.8 (embed) und PyYAML 6.0.3 unter `runtime/portable/downloads/` oder aus dem Netz (nach Rückfrage). Der Ordner `runtime/portable/` gehört nicht zum Repository und ist im Archiv nicht enthalten. Fehlt er, bricht die Einrichtung mit „Offline-Paketierung fehlgeschlagen“ ab. Siehe Hinweis in `00_LIES_MICH.md`.

## 3. Starten zum Ausprobieren

| System | Befehl |
|---|---|
| Windows | `START_SEDRA.bat` (fragt nach der Oberfläche), `START_SEDRA.bat cockpit` (direkt), `START_SEDRA.bat --uebersicht` (Übersicht) |
| macOS / Linux | `./start_sedra.sh`, `./start_sedra.sh cockpit` |

Die Übersicht öffnet die Start-Shell. Schließt man das Fenster, wird der Server beendet.

## 4. Tests

Die Testsuite nutzt `unittest` (keine externe Testbibliothek):

```
runtime/run_tests.sh                 # Linux/macOS
runtime/run_tests.bat                # Windows
```

Beide Skripte setzen `PYTHONPATH` auf `src` und `tests` und rufen `python -m unittest discover -s tests -t tests -v` auf.

**Einzelne Tests:**

```
cd runtime
PYTHONPATH=src:tests .venv/bin/python -m unittest tests.test_gateway -v
PYTHONPATH=src:tests .venv/bin/python -m unittest tests.test_content_guard tests.test_model_structured -v
PYTHONPATH=src:tests .venv/bin/python -m unittest tests.test_uix_frame tests.test_uix_start tests.test_uix_shell_start -v
```

**Erwartung:** Die volle Suite umfasst **2072 Tests** (Stand Build 19, rund sechseinhalb Minuten). Bekannt ist ein Umgebungsfehler: `test_uix_kommandodeck…test_search_and_read…` schlägt mit `library_not_built` fehl, wenn die Bibliothek nicht gebaut ist. Das ist kein Fehler im Code.

**Die wichtigsten Testdateien für die Arbeit seit Build 16:**

| Datei | Anzahl | Thema |
|---|---|---|
| `test_content_guard.py` | 27 | Inhaltsschutz, je eine Zusage |
| `test_model_structured.py` | 10 | Schema-Zwang beim Modell |
| `test_uix_frame.py` | 16 | Rahmen, Vorgabe, Zonen |
| `test_gateway.py` | 21 | KI GateWay: Matrix, Vorgang, Bindung |
| `test_desk_gateway.py` | – | Objekttyp `gateway`, Fremdwerkzeuge |
| `test_uix_start.py` | 8 | Startweg, `--shell`, `--uebersicht` |
| `test_uix_shell_start.py` | 7 | Einstieg, Creator, Klick-Wege |
| `test_core_boundary_src.py` | – | Grenzen des Kerns, benannte Kernmodule |

**Regel:** Ein Test je Zusage. Wer eine Regel ändert, ändert den Test dazu und nennt den Grund im Changelog.

## 5. Prüfen der Oberfläche: `uix_check`

`uix_check` ist das Werkzeug, das Shells und Werkzeuge gegen den Vertrag im Browser-Modus prüft (siehe `04_SHELLS_WERKZEUGE_VORGABEN.md`, Abschnitt 6). Die Abnahme aus Build 19: Studio 29/29, Cockpit, Minimal und Paperclip je 29/29, GUPPI XP 3/3.

## 6. Ein Build entsteht

Ein Paket entsteht mit `runtime/benchmarks/make_build.py`. Die Build-Nummer steht in der Datei `BUILD.txt` im Wurzelordner.

```
cd runtime
.venv/bin/python benchmarks/make_build.py --bump --out /pfad/outNN --previous /pfad/verifyNN-1/GUPPI_Runtime_v1.20
```

Das Skript liest `BUILD.txt` aus dem Wurzelordner des Repositorys (eine Ebene über `runtime/`).

- `--bump` erhöht die Build-Nummer und setzt das heutige Datum.
- `--out` ist der Ausgabeordner. Dort entstehen das Zip, die Prüfsummen und, mit `--previous`, ein **Patch** gegen den Vorgänger.
- `--previous` zeigt auf den entpackten Vorgänger-Build.

**Prüfen aus dem Zip:** Nach dem Bau das Zip in einen **neuen, leeren** Ordner entpacken und die Tests dort laufen lassen. Dabei **nicht** den Interpreter mit `-I` starten, denn `-I` wirft `PYTHONPATH` weg und die Tests finden das Paket nicht.

## 7. Das Logbuch

Jeder Schritt mit Wirkung wird im Logbuch festgehalten:

```
TZ=Europe/Berlin .venv/bin/python -I benchmarks/logbook.py add BAU "Text" --ref "Datei"
```

Die Uhrzeit setzt das Werkzeug. Pfade mit Laufwerksbuchstaben lehnt es ab. Das Logbuch liegt in `docs/LOGBUCH_AGENT_MANAGER.md`.

## 8. Der Changelog

Jeder Build hat einen Eintrag in `docs/CHANGELOG.md` mit: was gebaut wurde, welche Spec gilt, welche Tests dazu gehören, welche Abnahme, was noch nicht geht. Die Chronik der Builds 14 bis 19 steht in `07_BUILD_CHRONIK_14_BIS_19.md`.

## 9. Dateien, Zeilenenden und Git

- **Zeilenenden:** Jede Datei behält ihre Zeilenenden. Manche Dateien sind CRLF (Windows), andere LF. Eine Änderung, die alle Zeilenenden einer Datei umstellt, macht Diffs unlesbar.
- **Parallele Arbeit:** Jede Sitzung arbeitet auf einem eigenen Branch oder liefert einen Patch gegen eine benannte Commit-ID. Zusammenführen heißt `git merge`, nicht Dateivergleich.
- **Commits:** Der Verlauf ist im Bundle (`git/sedra_gupti_history.bundle`) enthalten. Commit `2692c37` ist Build 19. Im Commit steht `BUILD.txt` noch auf 18; die Arbeitskopie trägt 19.
- **Nicht ins Repository:** Modelle (`*.gguf`), Engines, `runtime/.venv`, `runtime/portable/`, Laufzeitdaten, `local_config/` mit Pfaden und Schlüsseln. Siehe `.gitignore`.

## 10. Die Regeln, die beim Bauen zählen

Aus `docs/ENTWICKLUNG.md` und der Arbeit an Build 14 bis 19:

- **Sicherheit vor Bequemlichkeit:** Keine Umgehung des Guards, der Freigaben oder der Bindungen, auch nicht zum Testen. Ein Test, der eine Sperre umgeht, ist ein Fehler.
- **Keine Cloud ohne Beschluss:** Die Cloud bleibt simuliert, bis der Captain den echten Weg freigibt.
- **Kein Text im Audit:** Ereignisse haben Hashes, Regeln, Zählungen, nie Inhalte.
- **Grenzen prüfen lassen:** Neue Kernmodule kommen in `test_core_boundary_src.py` mit Begründung.
- **Erst prüfen, dann behaupten:** Ein Build gilt erst als fertig, wenn die Tests grün sind (bis auf den bekannten Umgebungsfehler), das Zip aus einem leeren Ordner läuft und der Changelog steht.
