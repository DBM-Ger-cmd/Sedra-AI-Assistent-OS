# DevVM Phase 1: Arbeitsbereich auf dem Host, Git in Python, Ordnerexport (2026-10-06)

Auftrag und Entscheidungen: `docs/DEVVM_AUFTRAG_2026-10-05.md`, Befunde der Messung: `docs/DEVVM_PHASE0_BERICHT_2026-10-05.md`.

## 1. Was gebaut ist

| Teil | Datei | Stand |
|---|---|---|
| **Arbeitsbereich auf dem Host** (pro Mission) | `src/guppi_runtime/devvm.py` (`DevWorkspace`) | fertig, 11 Tests |
| **Git in Python** (dulwich 1.2.17, kein Git-Programm, keine Hooks) | dasselbe, `portable/devvm/wheels/` (mit `LOCK.json`, SHA-256 gegen PyPI geprüft), in `.venv` installiert | fertig |
| **Ordnerexport** (Erweiterung von Worker und Broker) | `sandbox/worker.py` (`expand_export_dirs`), `sandbox/broker.py` (`export_dirs`) | fertig, 7 neue Tests, **standardmäßig aus** (Gate, siehe 3) |
| **Abnahme in der echten VM** | `benchmarks/devvm_phase1_check.py` | alle 6 Schritte bestanden |

Sicherungen der geänderten Sicherheitsdateien: `archiv/bak_dateien/runtime/src/guppi_runtime/sandbox/{worker,broker}.py.bak-2026-10-06-export-dirs` und `archiv/bak_dateien/runtime/config/sandbox.yaml.bak-2026-10-06-export-dirs`.

### Aufbau des Arbeitsbereichs
`runtime_data/tool_workspace/devvm/<Mission>/repo/work/` ist der Ordner, den eine VM-Sitzung als Kopie bekommt. `.git` liegt daneben in `repo/.git` und wird **nie** in die VM kopiert (der Broker verbietet versteckte Einträge im Eingabeordner). Alle Regeln sind die des Brokers, damit alles im Arbeitsbereich auch in der VM laufen kann: relative Pfade unterhalb `work`, keine Punktnamen, keine Symlinks, nur `.py .md .txt .json .yaml .yml .toml .csv`, höchstens `max_files` (200) Dateien, 1 MiB je Datei, 4 MiB gesamt, Tiefe höchstens 8. Neue Ordner entstehen beim Schreiben (Entscheidung 3 des Captains), jede Änderung steht im Audit mit der Mission.
Operationen: `write`, `read`, `mkdir`, `move`, `delete` (nur Datei oder leerer Ordner), `list`, `tree`, `search`, `usage`; Git: `commit`, `status`, `diff`, `log`, `restore`; VM: `vm_preview` (nur der Plan des Brokers).

### Git-Sicherheit
- dulwich-Shell-Hooks (`pre-commit`, `commit-msg`, `post-commit`) werden nach dem Öffnen des Repositorys entfernt; ein Test beweist, dass bei vorhandenen Hook-Dateien keiner ausgeführt wird.
- Das Modell hat keinen Weg in `.git` (Pfadregeln, keine Punktnamen).
- Kein Modellcode läuft auf dem Host: dulwich liest und schreibt nur Daten.

## 2. Abnahme in der echten VM (`logs/devvm_phase1_check_2026-10-06_073438.*`)

| Schritt | Ergebnis |
|---|---|
| 1 Arbeitsbereich, Code, Test, Commit auf dem Host | 3 Dateien, Commit `fb854becce` |
| 2 VM-Lauf der Tests mit Ordnerexport | abgeschlossen in 1,2 s, `unittest` `OK`, Kandidat enthält genau `out/report.txt` und `out/sub/data.json`, Freigabe-Stufe `CAPTAIN_REVIEW_REQUIRED`, unabhängige Prüfung `verify` **PASS** |
| 6 Host-Arbeitsbereich unverändert | ja: die exportierten Dateien warten im Kandidaten, nicht im Arbeitsbereich |
| 3 Kaputte Änderung | VM-Lauf scheitert (1,1 s), Diff 6 Zeilen; `restore` auf den ersten Commit, VM-Lauf wieder grün |
| 4 Gast legt einen Symlink in den Exportordner | Lauf scheitert mit `guest_export_symlink`, nichts exportiert |
| 5 Gast schreibt `out/prog.exe` | vom Broker abgelehnt (`unsupported_workspace_file_type`), kein neuer Kandidat |

Tests der berührten Module: `test_sandbox` 46 (7 neu), `test_devvm` 11 (1 übersprungen, weil dieser Windows-Rechner kein Symlink-Recht hat), `test_run_log`; alle grün.

## 3. Gates und Entscheidungen für den Captain

1. **Ordnerexport einschalten:** in `config/sandbox.yaml` `allow_export_dirs: true` setzen (der Schalter ist als Kommentar dokumentiert, der Schlüssel fehlt, also aus). Ohne Schalter lehnt der Broker `export_dirs` ab, und der Plan (samt Digest) ist unverändert wie vorher. Mit Schalter gelten: Verzeichnisse statt Einzeldateien im Plan, höchstens 8, nicht ineinander, jede zurückkommende Datei wird gegen die Verzeichnisse und die Dateityp-Regeln geprüft, Symlinks und Sonderdateien verwerfen den ganzen Export, das Ergebnis bleibt ein Kandidat mit Captain-Prüfung.
2. **Wichtig für Phase 2 und 3 (nicht gelöst):** Jeder VM-Lauf läuft heute über `broker.execute('run')` mit Guard-Aktion `sandbox_execute` (Rechtestufe **3**, Standard-Obergrenze für Jobs ist 2) und braucht pro Plan eine Captain-Freigabe. Ein Agent mit 40 Werkzeugaufrufen hätte so viele Freigaben, wie er VM-Läufe startet. Die Wunschfunktion „Sitzungsfreigabe" ist als Ticket CW-001 vermerkt (am 2026-10-02 hatte die automatische Prüfung meinen Entwurf abgelehnt, er wurde zurückgenommen); ich baue sie nicht und umgehe die Freigabe nicht. Vorschlag: Agenten arbeiten fast ganz auf dem Host (schreiben, lesen, diffen, committen, Syntax prüfen) und lösen **einen** VM-Lauf je Überarbeitungsrunde aus (bis zu 5 Befehle in einem Plan). Ob das reicht oder ob CW-001 gebraucht wird, entscheidest du.
3. **Längere VM-Sitzung:** Die Grenzen bleiben wie sie sind (Job 120 s, Befehl 30 s, höchstens 5 Befehle je Plan). Mehrere Befehle laufen schon jetzt in **einer** VM, die Dateien bleiben dabei bestehen (Phase 0). Anheben ließe sich `job_timeout_seconds` bis 600 s in `config/sandbox.yaml`; ich habe es nicht geändert, sag mir, wenn du es willst.

## 4. Grenzen und offene Punkte
- Git-Funktionen: Commit, Status, Diff, Log, Zurücksetzen auf einen Commit. Keine Zweige, kein Zusammenführen, kein Remote (bewusst, kein Netz).
- `restore` setzt die Dateien auf den Stand eines Commits; HEAD bleibt, das Zurücksetzen ist eine Änderung, die man einchecken kann (wie `git checkout <commit> -- .`).
- Leere Ordner werden von Git nicht erfasst.
- Dateiliste der VM: Die VM bekommt `work` komplett (bis 200 Dateien). Ein Arbeitsbereich mit mehr Dateien ist nicht ausführbar, `usage()` zeigt das vorher.
- Phase 2 (Werkzeugsatz für Untermodelle) baut auf `DevWorkspace` auf; die Modell-Werkzeuge (`list_dir`, `make_dir`, `move_file`, `search_text`, `diff_files`, `run_tests`, `run_python`) hängen an dieser Klasse und an der Entscheidung zu Punkt 2.
