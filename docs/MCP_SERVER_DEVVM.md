# MCP-Server für einen DevVM-Arbeitsordner (`guppi_runtime.devvm_mcp`)

Gebaut am 2026-10-10 auf Wunsch des Captains: fertige Agenten (Qwen Code, little-coder, OpenCode, Goose) sollen ihre eigene Schleife und ihre Wächter mitbringen, das Modell soll aber **nur GUPPIs Werkzeuge sehen** (Arbeitsordner und microVM), nie den Rechner.

## Start
```
.venv\Scripts\python.exe -m guppi_runtime.devvm_mcp --project ..\workspace\GUPPI_OS [--seed <Ordner>] [--workspace-root <Ordner>] [--journal <Datei>] [--result-file <Datei>] [--max-vm-runs 8] [--self-check full|light|none] [--no-vm]
```
(`PYTHONPATH=src`, Arbeitsordner `runtime`.) Der Server spricht MCP über Standard-Ein/Ausgabe (JSON-RPC 2.0, eine Nachricht je Zeile: `initialize`, `tools/list`, `tools/call`, `ping`), nutzt nur die Python-Standardbibliothek und bedient **einen** Arbeitsordner.

## Was er anbietet
`list_dir`, `read_file` (in Teilen, `start`/`end`), `outline`, `write_file` (lehnt das Ersetzen einer Datei über 10 Zeilen ab), `append_file`, `edit_file` (auch `edits`), `make_dir`, `move_file`, `delete_file`, `search_text`, `diff_files`, `check_syntax`, `git_status`, `git_log`, `run_python` (nur in der **microVM**, auf einer Kopie des Arbeitsordners), `submit_result`. Nicht angeboten: `git_commit`, `run_tests`, jede Shell, jedes Netz. Die Regeln des Arbeitsordners gelten für jeden Agenten: Pfade nur darin (keine Symlinks, Tiefe, Größe, Dateitypen des Brokers), `run_python` höchstens N-mal (`--max-vm-runs`, bei `--self-check none` gar nicht), Aufrufgrenze und Zeitgrenze.

## Was er schreibt
- **Journal** (`--journal`): eine JSON-Zeile je Aufruf (`tool`, Argumente ohne lange Texte, `ok`, `ms`, `error`). Das ist die Datengrundlage für den Schichtenbericht über Aufrufe je Werkzeug.
- **Ergebnis** (`--result-file`): die Abgabe (`submit_result`) als JSON.
- Der Arbeitsordner liegt unter `--workspace-root` (sonst ein neuer Temp-Ordner); der Aufrufer committet und lässt den **versteckten Abnahmetest** laufen (der Server zeigt ihn nie).

## Geprüft
- 9 Tests (`tests/test_devvm_mcp.py`): Handshake, Werkzeugliste, Regeln des Arbeitsordners (kein Pfad nach außen, kein Ersetzen langer Dateien, mehrere Änderungen), `run_python` mit Begrenzung, Fehler und Benachrichtigungen, Journal, Abgabe, Stdio-Schleife mit kaputten Zeilen und ein echter Prozess über Stdio.
- Echter Rundlauf gegen die microVM am 2026-10-10: Datei schreiben, `run_python` -> "hello from Linux" (Zustand `completed`), fehlschlagender Test -> Traceback (Zustand `failed`).

## Anbinden: Qwen Code 0.25.0 (geprüft am 2026-10-10 ohne Modell und ohne GPU)
Installiert aus der Registry (`npm install --ignore-scripts --omit=optional @qwen-code/qwen-code@0.25.0`) in `<projekte>\qwen-code-main\qwen-code-installed` (ein Paket, 114 MB, keine Installationsskripte). Die Konfiguration steht im Code als `qwen_settings()` in `benchmarks/agent_tool_probe.py` (eigener Home-Ordner des Agenten, `~/.qwen/settings.json`):
- `permissions.deny`: Bash, Shell, Read, Edit, Glob, Grep, ListFiles, WebFetch, WebSearch, Agent, Skill, NotebookEdit (entfernt die eingebauten Werkzeuge vor dem Modell und lehnt Aufrufe ab);
- `permissions.allow`: nur unsere 15 Werkzeuge `mcp__devvm__*` (im nicht interaktiven Betrieb kann der Agent nicht nachfragen, ohne diese Erlaubnis lehnt er auch sie ab);
- `tools.disabled`: alle übrigen eingebauten und gebündelten Werkzeuge (Zeitplaner, Worktrees, Nachrichten, Ziele, Unter-Agenten, Pläne, Fragen, Web, Skill **und die Brücke `tool_search` / `tool_call`**);
- `tools.visible`: unsere Werkzeuge werden gleich im ersten Aufruf deklariert (ohne die Brücke wären sie nicht erreichbar); `tools.toolSearch.enabled: false`;
- `mcpServers.devvm`: `python -m guppi_runtime.devvm_mcp --project ... --workspace-root ...` mit `PYTHONPATH`.

**Befund der Werkzeug-Probe** (`python benchmarks/agent_tool_probe.py qwen-code --variant both|attack`; ein Fake-Modell auf 127.0.0.1 zeichnet die Anfrage auf):
- Ohne unsere Konfiguration bietet Qwen Code dem Modell `agent, get_goal, glob, grep_search, list_agents, read_file, skill, tool_call, tool_search, update_goal` an; **weitere Werkzeuge (Schreiben, Bearbeiten, Shell, Zeitplaner, Worktrees, Artefakte, Nachrichten) liegen hinter der Brücke `tool_search` / `tool_call`** und sind darüber erreichbar. Nur `deny` allein reicht daher nicht: mit `deny` blieben `get_goal, list_agents, tool_call, tool_search, update_goal` übrig und unsere eigenen Werkzeuge waren nur über die Brücke erreichbar.
- Mit der oben beschriebenen Konfiguration zeigt der Agent dem Modell **genau unsere 15 Werkzeuge** (`mcp__devvm__append_file` ... `mcp__devvm__write_file`) und nichts sonst.
- **Angriffsprobe** (das Fake-Modell ruft nacheinander auf): unser `write_file` -> angelegt im Arbeitsordner des Servers; die Shell (`run_shell_command`), das eingebaute Schreiben und das eingebaute Lesen -> vom Agenten **abgelehnt** („Matching deny rule"), die Marker-Dateien entstehen nicht; unser `read_file` mit `../../../../../../Windows/win.ini` -> vom Server als Fehler abgewiesen.
- Nicht geprüft: Verhalten mit einem echten Modell, andere Qwen-Code-Versionen (nach einem Update ist die Probe erneut zu fahren), Erweiterungen/Hooks/Skills aus dem Home-Ordner (der Home-Ordner des Agenten ist leer und liegt unter dem Temp-Ordner des Laufs), Netzzugriffe des Agenten selbst (Updates, Telemetrie).

## Grenzen
- Der Agentenprozess selbst (Node) läuft auf dem Rechner. Sicherheit entsteht dadurch, dass das Modell keine eingebauten Werkzeuge mehr hat; sie ist nur so gut wie diese Konfiguration und deren Prüfung.
- Ein Server je Arbeitsordner und Lauf; der Aufrufer legt den Ordner an und löscht ihn.
- Kein Flackerschutz für abgebrochene VM-Läufe über das hinaus, was `acceptance_vm.vm_runner` schon tut (drei Versuche).
