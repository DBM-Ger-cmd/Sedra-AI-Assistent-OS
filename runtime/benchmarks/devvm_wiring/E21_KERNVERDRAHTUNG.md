# E-21 Kernverdrahtung `coder_ext` (Spec, 2026-10-10)

Ziel: Die abgenommenen und aufgeräumten Module E-01 bis E-09 und `coder_ext.py` (E-20) werden über genau drei Hook-Punkte an GUPPIs Kern angeschlossen. Ohne `--coder-ext` verhält sich alles wie vorher, Byte für Byte.

Die Abnahme macht `test_coder_ext_wiring.py` in diesem Ordner. Die Datei kommt erst nach der Umsetzung nach `runtime/tests/`. Bis dahin wird sie dem Umsetzenden nicht gezeigt, wenn das GUPPI ist.

Hinweis zum Bauweg: Ein DevVM-Workspace kann die Kerndateien nicht aufnehmen. `devvm_agents.py` ist allein 60 KB groß, und die Kerndateien importieren das halbe Paket. Deshalb ist der Bauweg eine eigene Entscheidung des Captains, siehe Ende.

## 0. Paket

- `src/guppi_runtime/coder_ext/` mit den aufgeräumten Kandidaten `read_tracker.py`, `fuzzy_edit.py`, `replay_log.py`, `think_guard.py`, `no_call_monitor.py`, `syntax_note.py`, `result_pruner.py`, `tool_cards.py`, außerdem `coder_cards.py` von Claude und `coder_ext.py` als `__init__.py`.
- Die einzige Änderung am Modulcode: In `__init__.py` werden die Importe relativ (`from . import fuzzy_edit` ...). Die anderen Module importieren sich nicht gegenseitig.
- Die Herkunft jedes Moduls (Kandidaten-Ordner, Datum, Hermes/little-coder/dsh-Idee) wird in einer Zeile in `coder_ext/README.md` festgehalten. In den Modulen selbst stehen keine Kommentare.

## 1. `DevToolBox` (`devvm_tools.py`): Hooks vor und nach einem Tool-Aufruf

- Konstruktor: neuer Parameter `ext=None` (eine `CoderExtensions`-Instanz) und `self.ext_stats = {"refusals": 0, "fuzzy_edits": 0, "syntax_notes": 0, "cards": 0}`.
- In `call()` werden für die Hooks die bereinigten Argumente benutzt, also `path`, `source` und `destination` über `_clean`.
  - **Vor `_run`** (nur wenn `ext` gesetzt ist und der Name `edit_file`, `append_file` oder `write_file` lautet): `current` = Text der Datei oder None. Ist `ext.before_tool(...)["refuse"]` gesetzt, wird ein `ToolError` mit genau diesem Text ausgelöst, `refusals` steigt um 1, und `_run` läuft nicht. Ein `note` wird gemerkt.
  - **Nach `_run`**, bei Erfolg und bei Fehler: `after = ext.after_tool(name, args, ok, text, current_after)`. Dabei ist `current_after` der Dateitext nach dem Aufruf für `read_file`, `write_file`, `append_file` und `edit_file`, sonst None. Ist der Aufruf erfolgreich und gibt es ein gemerktes `note`, wird es an den Text angehängt, durch `"\n"` getrennt. Dasselbe gilt für ein nicht leeres `after`. Für die Zähler gilt: beginnt `after` mit `syntax error in`, `invalid JSON in` oder `invalid TOML in`, steigt `syntax_notes`, sonst steigt bei einem fehlgeschlagenen Aufruf `cards`.
  - **Der Loop-Guard** bekommt weiterhin `raw`, also den Text ohne `note`, `after` und Warnung.
- **`edit_file` mit genau einer Änderung:** Liefert `text.count(old) == 0` ein Ergebnis und ist `ext.edit_fallback(text, old, new)` nicht None, wird `r["text"]` geschrieben. Die Antwort ist `edited <path> (matched with <strategy>, <bytes> bytes)`, und `fuzzy_edits` steigt um 1. Sonst bleibt die bisherige Fehlermeldung mit `edit_hint`. Bei mehreren Änderungen (`edits`) ändert sich in diesem Schritt nichts.

## 2. `run_tool_loop` (`model_tools.py`): Hook nach jeder Modell-Antwort

- Neuer Parameter `ext=None`.
- **Vor jedem `post`:** `body.update(ext.request_patch())`.
- **Nach jeder Antwort, neben stub/compact:** `messages = ext.prune(messages, used)`.
- **Antwort mit Calls:** `d = ext.after_answer(data, True)`. Nach den Tool-Ergebnissen kommt jede Notiz in `d["notes"]` als User-Nachricht dazu.
- **Antwort ohne Calls** und `finish != "length"`: `d = ext.after_answer(data, False)`.
  - `"run"`: Die Calls aus `d["calls"]` werden wie normale Calls ausgeführt, mit den IDs `text_0`, `text_1` usw.
  - `"correct"`: Die Assistenten-Antwort kommt als `{"role": "assistant", "content": content}` in den Verlauf, danach jede Notiz als User-Nachricht, und die Schleife läuft weiter.
  - `"stop"` oder kein `ext`: wie bisher `break`.
- **`finish == "length"`:** unverändert, der bisherige Pfad mit CUT_NOTE.

## 3. `run_agent` (`devvm_agents.py`)

- Neuer Parameter `coder_ext=None`. Das ist ein Konfigurations-Dict wie `{"enabled": "all", "think_limit": 2000, "family": "qwen", "window": 32768, "record": False}`, keine Instanz.
- **Pro Agent-Lauf** eine neue Instanz: `CoderExtensions(enabled, think_limit, family, max_corrections, terminal=box.terminal, tool_names=box.names, prune_at, window)`. Tracker, Monitor und Recorder gehören also zu genau einem Lauf.
- Die Instanz geht an `DevToolBox(ext=...)` und `run_tool_loop(ext=...)`.
- **Bei `record: True`:** `post = ext.wrap_post(post, mode="record")` wird VOR `guarded` gelegt, aufgezeichnet wird also die echte Server-Antwort. Danach steht im Ergebnis `result["replay_records"] = ext.records()`.
- **Im Ergebnis** steht immer `result["coder_ext"] = {"enabled": sorted(...), **box.ext_stats, "think_less": bool, "corrections": n}`. Ohne Konfiguration ist das `{"enabled": []}` mit Zählern 0.
- **`stopped_by`:** keine neuen Werte. Ein Stopp durch E-03 bleibt `no_tool_call`.

## 4. `DevOrchestrator` und `devvm_build.py`

- `DevOrchestrator(..., coder_ext=None)` gibt die Konfiguration an jeden `run_agent`-Aufruf weiter.
- **`devvm_build.py`:**
  - neue Schalter `--coder-ext` (Standard: aus) und `--coder-ext-record`.
  - Familie aus dem Modell: Qwen → `qwen`, gpt-oss → `gptoss`, sonst `other`.
  - `window` = `--context`.
- **Aufzeichnungen** landen als JSONL unter `<project>/runtime_data/devvm_replays/<spec>/<attempt>/<n>_<role>.jsonl`, über `replay_log.dumps`.
- **Im Run-Log** erscheinen die `coder_ext`-Zähler pro Agent-Lauf.
- `devvm_mcp.py` (externe Agenten) wird in diesem Schritt nicht verdrahtet.

## 5. Abnahme und Messung

- Grün sein müssen `test_coder_ext_wiring.py` plus die Nachbartests: `test_devvm_tools.py`, `test_little_coder_guards.py`, `test_devvm_delegation.py`, `test_agent_devvm_*`.
- **Messung:** Solo-Standardtest und am009 jeweils ohne und mit `--coder-ext all`. Verglichen werden Zeit, Tokens, Bestehen des versteckten Tests, Verweigerungen, Fuzzy-Edits, fehlgeschlagene edit_file-Aufrufe und Korrekturen. Danach wird eine Erweiterung nach der anderen abgeschaltet, um ihren Einzelanteil zu sehen. Der Standard bleibt aus, bis die Messung zeigt, dass nichts schlechter wird.

## Offene Entscheidung Captain: wer setzt um?

1. **Claude setzt um**, etwa 60 bis 90 Zeilen in vier Dateien. Das ist der schnelle und sichere Weg. GUPPIs Anteil bleibt der Modul-Code, über 900 Zeilen.
2. **GUPPI setzt um**: Dafür bräuchte der DevVM-Workspace eine höhere Dateigrößen-Grenze und eine Kopie des ganzen Pakets, und die Abnahmetests müssten in der VM laufen. Das wäre ein eigenes Infrastruktur-Paket.
