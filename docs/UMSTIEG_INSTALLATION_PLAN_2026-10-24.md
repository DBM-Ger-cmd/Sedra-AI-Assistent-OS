# Umstiegsplan: Installation `<guppi>` auf den Stand von A1

**Stand:** 24.10.2026. Dies ist nur ein Plan: Es wurde nichts geändert, nichts committet und kein Prozess gestartet. Jeder Schritt ab Abschnitt 2 braucht eine Freigabe des Captains (Gates U-1 bis U-6).
**Quelle:** `<a1>` = Arbeitsstand A1, Branch `spec/agenten-orchestrierung`, HEAD `d6d25ca` (Repo `Sedra-AI-Assistent-OS`). **Ziel:** `<guppi>` = laufende Installation, eigenes Git-Repo (`Guppi-Self-Improve-AI-Agent`), `main` auf `16a6e07` (14.10.), 64 Commits nicht gepusht.
**Sicherung schon vorhanden:** Bundle aller Refs der Installation, Diffs der offenen Änderungen und eine Liste der unversionierten Dateien (Ordner `_Aufraeumen_2026-10-24/sicherung/` neben `<guppi>`).

---

## 0. Kurzfassung

- Die Installation hat **keine Datei, die es in A1 nicht gibt**. Alle 1124 versionierten Dateien der Installation gibt es in A1 unter demselben Pfad: 792 sind gleich, 269 hatte A1 schon einmal in genau dieser Fassung und hat sie seitdem weiterentwickelt, und 63 haben einen Inhalt, den A1 nie hatte. Diese 63 sind fast alle **ältere Fassungen**: umgestellte Importe, der alte Desktop (`uix/js`, `uix/css`, `retro_desktop.html`) und GUPPI-Texte. Nur in der Installation stehen bloß **zwei offene Änderungen an Messskripten** und **sechs unversionierte Skripte für Nachtketten** (Abschnitt 1.1).
- `update_anwenden` deckt nur `runtime/src/guppi_runtime/` und `runtime/config/` ab, also **648 von 1907 Dateien**. Es fehlen `architecture/` (darin die Guard-Regeln GR-029 bis GR-038), `runtime/benchmarks/` (`devvm_build`, `spec_check`, `uix_check`, `make_build`), `runtime/tests/`, die Doku und der Starter `START_SEDRA.bat`. Außerdem würde der Weg in der Installation **`runtime/config/local_paths.yaml` und alle `.bak-*`-Dateien in den Prüfbereichen löschen**, weil sie nicht im Manifest stehen. Das Löschen lässt sich zurückholen, weil vorher gesichert wird, aber ohne `local_paths.yaml` bleibt der GPU-Canary aus und `<modelle>` wird nicht gefunden.
- **Empfehlung: Weg G.** Die Installation wechselt am selben Ort per Git auf `d6d25ca`: Remote `a1` als lokaler Pfad (kein GitHub), offene Änderungen vorher auf einen eigenen Branch. Git tauscht alle versionierten Dateien, lässt ignorierte Ordner (`workspace`, `engines`, `.venv`, `portable`, `runtime_data`, `local_paths.yaml`, `.bak-*`) in Ruhe, und der Rückweg ist ein `git checkout`. Eine Überschneidung zwischen Dateien, die A1 versioniert, und Dateien, die in der Installation unversioniert oder ignoriert sind, wurde geprüft: **keine** gefunden. Der Weg über Paket, Manifest und `plan()` bleibt als **Prüfung** davor, für Dateiliste und Rechteliste. Weg U (`update_anwenden`) ist die Alternative, braucht aber vorher zwei Code-Änderungen (Abschnitt 2.4).

## 1. Abgleich

### 1.1 Was nur die Installation hat

| Datei | Was es ist | Empfehlung |
|---|---|---|
| `runtime/src/guppi_runtime/models/gpu_preflight.py` (offen, Grenze 3,0 GiB) | `clear_leftovers(baseline_max_gb=3.0)` | **verwerfen**: A1 hat schon 3,0 (`models/gpu_preflight.py:93`). Die `.bak-2026-10-22-gpu-grenze` bleibt als ignorierte Datei liegen. |
| `runtime/benchmarks/context_ladder.py` (offen) | Leiter bis 192k/256k mit `--max` (Messung zu mmap vom 13.10.) | **prüfen, eher übernehmen**: A1 hat die Leiter bis 128k und zusätzlich `--parallel` (S2.H0). Das wären 2 Zeilen als kleiner Patch in A1, eigener Commit auf dem Branch der Sitzung. |
| `runtime/benchmarks/moe_sweep.py` (offen) | misst zusätzlich `load_s`, `free_ram_gib`, `ram_before_gib` | **prüfen, eher übernehmen**: 5 Zeilen, nur Messung, keine Wirkung auf den Betrieb. |
| `runtime/benchmarks/canary_retry.py` (unversioniert) | Canary gezielt erneut, mit GPU-Lease | **prüfen**: als Werkzeug nützlich. Wenn es übernommen wird, die Importe auf `guppi_runtime.jobs.testlab` bzw. `models.*` umstellen. |
| `runtime/benchmarks/chain_judge.py`, `gpu_recovery.py`, `night_queue_2026-10-13_b.py`, `start_night_chains_2026-10-13.ps1`, `runtime/tests/test_chain_judge.py` (unversioniert) | Richter und Wiederaufnahme für Nachtketten (13.10.) | **verwerfen** (für A1): Seit L1 sind Ketten nur noch Archiv. Sie bleiben auf dem Sicherungsbranch der Installation (Schritt 2.2) und im Bundle. |
| 63 Dateien mit Inhalt, den A1 nie hatte (u. a. `uix_server.py`, `runtime.py`, `uix_start.py`, `models/router.py`, `uix/css/desktop.css`, `retro_desktop.html`, ~30 Tests, `README.md`, `START_HERE.txt`, `docs/BETRIEB.md`, `docs/ENTWICKLUNG.md`) | Geprüft wurde Zeile für Zeile, welche Zeilen der Installation **nirgends** in A1 vorkommen: je Datei 1–55, bei `desktop.css` 137. Stichproben: alte Importpfade vor der Paketaufteilung, GUPPI-Texte (`CHAT_SYSTEM`, „GUPPI Entwicklungsumgebung“), CSS des alten Desktops, Teile des Commits `16a6e07` (Claude-Chat, unfertig). | **verwerfen**: A1 ist die neuere Fassung. Inhaltlich stehen sie im Bundle und auf dem Sicherungsbranch. |
| `START_GUPPI.bat`, `ERSTER_START.bat` | alte Starter | **verwerfen**: Ersatz ist `START_SEDRA.bat`. Unter Weg G löscht Git `START_GUPPI.bat`, weil A1 ihn nicht versioniert. Verknüpfungen auf dem Desktop des Captains danach anpassen. |
| `archiv/` (Wurzel, ignoriert), `runtime/runtime_data/` (ignoriert) | Altbestand | bleiben unberührt |

Die 64 nicht gepushten Commits der Installation (7.–14.10.) gingen inhaltlich in A1 ein: A1 beginnt am 15.10. mit „Build 20“, und alle Pfade sind vorhanden. Sie bleiben im Bundle und im Repo der Installation erhalten (Abschnitt 2.6). Nach A1 übernommen werden muss **vor** dem Umstieg nichts. Die Patches für `context_ladder`/`moe_sweep` gehen auch danach (Frage F3).

### 1.2 Konfiguration und Daten außerhalb der Prüfbereiche

Wichtig: Seit dem 20.10. (PIPE-09) laufen Bauten und Messungen aus A1 schon gegen `<guppi>/workspace/GUPPI_OS` und mit `<guppi>/runtime/.venv`. Daten und Rezepte haben den A1-Code also schon gesehen.

| Bereich | Befund | Folge |
|---|---|---|
| `workspace/GUPPI_OS/local_config/switches.yaml` | Abschnitte `job_supervisor`, `context_manager`, `resource_scheduler`, `model_loader` (+`evict_idle_models`), `llama_server` (+`mtp`), `token_policy`, alle in `ALLOWED` von A1 | passt. **`orchestra` und `wissen` fehlen, bleiben also aus** (Vorgabe `enabled: false` in `orchestra.yaml`/`wissen.yaml`). Einschalten nur per eigenem Gate. |
| `local_config/role_routing.yaml` (Live-Rezepte) | Mit dem A1-Lader probehalber gelesen (nur lesen): **geladen, 18 Rezepte, noch keins mit `slots`/`per_slots`** | Die Felder aus S2.H2 erst nach dem Umstieg eintragen, mit Sicherung `.bak-<datum>-s2h2` und Gate `change_routing` (Schritt 3.6). |
| `local_config/routing_profiles.yaml` | unverändert | prüft der Start (doctor) |
| `runtime/config/local_paths.yaml` | Installation: 6 Schlüssel (`modelle`, `modelle-test`, `hermes`, `projekte`, `guppi`, `skillsets`); in A1 nur `modelle` | ist ignoriert und bleibt unter Weg G liegen. **Unter Weg U würde sie gelöscht** (Abschnitt 2.4). |
| `runtime/config/` | A1 bringt neu `orchestra.yaml`, `wissen.yaml`, `wissen_glossar.yaml`, `cloud_providers.yaml` (alle Standard aus), dazu geänderte `permission_levels.yaml` (Stufen wie D4) | Rechteänderung (Gate U-3) |
| `architecture/…/core/guard/guard_rules.yaml` | A1 hat **GR-029 bis GR-038** (K0.23, 21.10.): 6× `CAPTAIN_REQUIRED`, 4× `ALLOW` (`assign_task`, `delegate_task`, `pause_agent`, `fire_routine`) | **Guard-Änderung in der Installation**: ausdrücklich nennen und freigeben (U-3), nicht stillschweigend. Weg U brächte sie gar nicht mit (Code neu, Guard alt). |
| `runtime_data/testlab/testlab.db` | A1 legt Tabellen mit `IF NOT EXISTS` an, dazu `ALTER TABLE runs ADD COLUMN pid` | ergänzt nur, kein Rückbau nötig. Wird seit dem 20.10. schon von A1-Bauten benutzt. |
| `runtime_data/agent_manager/registry.sqlite` | Schema gleich (`entries`, `receipts`, `outbox`) | keine Migration |
| neue Datenbanken: `orchestra/orchestra.db`, `slot_db`-Tabellen, `local_config/wissen/wissen.sqlite` | entstehen erst bei Benutzung bzw. beim Einschalten | aus, solange die Schalter aus sind |
| `local_config/wissen.yaml` (Engine/Modell bge-m3) | in der Installation nicht vorhanden | ohne die Datei gibt es nur die Volltextsuche, Einbetten „nicht bereit“. Gehört zu Spec 7 und nicht zu diesem Umstieg. |
| `uix.yaml` (gewählte Oberfläche) | gibt es in der Installation noch nicht | entsteht beim ersten `START_SEDRA.bat` |
| `<guppi>/local_config/update/` (Wurzel) | `update_anwenden`/`update_holen` legen Sicherung und Staging **an der Wurzel** an. Dieser Pfad steht nicht in der `.gitignore` von A1. | nur Weg U: erscheint danach als unversioniert. Pfad in `.gitignore` aufnehmen (Frage F5). |
| Python | `.venv`: 3.14.7, `requirements.txt` und `pyproject.toml` gleich wie in A1; `runtime/portable/sandbox` ist da, `portable/python` fehlt | `START_SEDRA.bat` nimmt den Entwicklerweg über `.venv`, keine Ersteinrichtung, keine Downloads |
| Engine | `llama_server.yaml` gleich wie in A1, `engines/llama.cpp/b11160` vorhanden (dazu b11371, b11530) | `test_bau_ort` prüft das |

## 2. Ablauf (Weg G, empfohlen)

**Vorbedingungen (Gate U-1):** Kein SEDRA aus `<guppi>` läuft, keine Sitzung hält die GPU-Lease (`TestLab(default_path(<guppi>/workspace/GUPPI_OS)).holder()` ist leer), kein Bau und keine Messung läuft. Die anderen Sitzungen werden vorher benachrichtigt, denn sie nutzen `<guppi>/workspace/GUPPI_OS` und `.venv`. Nichts beenden, sondern warten.

1. **Stand in A1 festlegen.** Auf welchem Commit wird umgestiegen? Vorschlag: `d6d25ca` oder ein Tag darauf (`v1.22.0-rc1`, nur lokal). In A1: `git status` ist sauber. Läuft das gezielte Testpaket grün (Abschnitt 3.2)?
2. **Installation sichern (zusätzlich zum Bundle).**
   - `git -C <guppi> switch -c installation/stand-2026-10-24`, dann die 3 offenen und die 6 unversionierten Dateien committen („Stand der Installation vor dem Umstieg“). `main` bleibt auf `16a6e07`.
   - Kopie von `workspace/GUPPI_OS/local_config/` (Rezepte, Schalter, Profile) und `runtime/config/local_paths.yaml` nach `<sicherung>/config_2026-10-24/`.
   - Kopie von `runtime_data/testlab/testlab.db` und `runtime_data/agent_manager/registry.sqlite`, wenn nichts läuft.
3. **Prüfpaket bauen (nur lesen, Staging außerhalb von `<guppi>`).**
   - `git -C <a1> archive d6d25ca` → in einen leeren Ordner `<staging>/d6d25ca/` entpacken. Wichtig: aus dem **Commit**, nicht aus dem Arbeitsbaum von A1, denn dort liegen eine eigene `local_paths.yaml` und `.bak`-Dateien in `runtime/config/`.
   - `manifest_erzeugen(<staging>/d6d25ca)` → `<staging>/d6d25ca/release/MANIFEST.sha256` (627 + 21 Einträge).
   - Zusätzlich `make_build.py --out <staging>/paket`, als Zip mit `PACKAGE_CHECKSUMS.sha256` für das Archiv. Nichts geht zu GitHub.
   - `update_anwenden.plan(<staging>/d6d25ca, <guppi>, manifest)` ausführen. Die Funktion schreibt nichts und liefert die Listen *geändert*, *entfallen* und *Rechte*. Erwartet: 52 Sätze „neues Modul“ (alle Tools und Shells, weil die Installation noch keine Modul-Manifeste hat) und unter *entfallen* `local_paths.yaml` sowie die `.bak`-Dateien (siehe 2.4).
   - Dazu ein `git diff --stat 16a6e07 d6d25ca -- architecture runtime/config` für die Guard- und Rechteliste.
4. **Rechte freigeben (Gate U-3).** Der Captain bestätigt namentlich: die 52 neuen Module samt Routen, GR-029 bis GR-038, die Stufen in `permission_levels.yaml` und die neuen Configs (alle aus).
5. **Wechsel (Gate U-4).**
   - `git -C <guppi> remote rename origin alt-origin` und `git -C <guppi> remote set-url --push alt-origin KEIN_PUSH`, damit die A1-Geschichte nicht versehentlich ins alte Repo geht.
   - `git -C <guppi> remote add a1 <a1>` (lokaler Pfad), dann `git -C <guppi> fetch a1 spec/agenten-orchestrierung`.
   - `git -C <guppi> switch -c betrieb/a1-d6d25ca d6d25ca`. Git bricht ab, wenn etwas Unversioniertes überschrieben würde. Dann stoppen und nicht mit `--force` weiter.
   - Prüfen: `git -C <guppi> status` sauber. `local_paths.yaml`, `switches.yaml`, `role_routing.yaml`, `engines/` und `.venv/` sind unverändert (gleiche Prüfsumme wie in der Sicherung aus Schritt 2).
6. **Neustart.** `START_SEDRA.bat --uebersicht` (Entwicklerweg über `.venv`). Desktop-Verknüpfungen auf `START_SEDRA.bat` umstellen.

### 2.4 Weg U (Alternative über `update_anwenden`)

Vorher nötig, jeweils als eigene A1-Änderung mit Test (Gate):
- (a) `_programmdateien` lässt `local_paths.yaml`, `*.bak-*` und `.model-original-*` aus, so wie `.gitignore` und `make_build`. Sonst werden sie gelöscht und müssen aus `local_config/update/sicherung/…` zurückgeholt werden.
- (b) Für alles außerhalb von src/config (`architecture/`, `benchmarks/`, `tests/`, `docs/`, Starter an der Wurzel) braucht es einen zweiten Kopierschritt aus dem Paket. Dieser Schritt hat **keine** Manifestprüfung und keinen `zurueck`. Oder man erweitert `PRUEFBEREICHE`, aber das ändert den Update-Weg und braucht ein eigenes Gate.
- Ablauf danach: Staging wie in 2.3, dann `anwenden(staging, <guppi>, manifest, rechte_schluessel, 'a1-d6d25ca')` (legt die Sicherung an), danach der Kopierschritt (b), danach der Neustart. Das Git-Repo der Installation zeigt anschließend ~1000 geänderte Dateien gegen `16a6e07`. Man müsste es danach ohnehin auf A1 umstellen, also landet man doch bei Weg G.

### 2.6 Was mit dem Git-Repo der Installation passiert

Das Repo **bleibt** und wird zum Betriebs-Checkout von A1:
- Branches `main` (`16a6e07`) und `installation/stand-2026-10-24` bleiben als Geschichte erhalten.
- `alt-origin` ist nur noch zum Lesen da.
- Neuer Remote `a1` (lokal). Spätere Updates: `fetch a1` und `switch` auf einen neuen Tag.
- Wenn der Captain es will, zeigt `origin` später auf GitHub `Sedra-AI-Assistent-OS` (nur Release-Tags, wie PLAN_ISOLATION 4.1), siehe Frage F2.
- Das alte GitHub-Repo bekommt **keinen** Push.

## 3. Prüfungen danach

1. `runtime/run_doctor.bat` (`guppi doctor`): **READY**, `LOCAL_SWITCHES_APPLIED` ohne `problems`, `orchestra`/`wissen` aus, kein `*_error`.
2. Betroffene Tests mit `.venv`, `PYTHONPATH=src;tests`: `test_bau_ort`, `test_local_switches`, `test_role_routing`, `test_core_boundary_src`, `test_uix_server`, `test_uix_start`, `test_gpu_canary`, `test_update_anwenden` (sofern vorhanden), `test_uix_contract` und Tests von Spec 2 (Slots/Scheduler). Ergebnis mit Zahlen ins Logbuch.
3. `py -3.13 benchmarks/uix_check.py` aus `<guppi>/runtime`: Zeile **`result ok`**.
4. Rezeptlader mit der Live-Datei: `RoutingConfig.load('config/role_routing.yaml', '<guppi>/workspace/GUPPI_OS/local_config/role_routing.yaml')` lädt alle 18 Rezepte (vor dem Umstieg schon so geprüft).
5. **Kurzer Modellstart (eigenes Gate U-5, GPU):** GPU-Lease holen, Canary, `coder.local_primary` laden, eine kurze Frage, entladen, Lease freigeben. Prüfen: VRAM ≤ 11,5 GB, kein Rest-Server auf Port 8089.
6. Erst danach, mit eigenem Gate U-6: `slots`/`per_slots` in die Live-Rezepte eintragen (Sicherung, Lader-Probe, Audit `ROUTING_RECIPE_ADDED`/Routing-Änderung), dann noch einmal ein Kurzstart mit 2 Slots.

## 4. Rückweg, Abbruch, Dauer

**Rückweg (Weg G):** SEDRA schließen, dann `git -C <guppi> switch installation/stand-2026-10-24`. Damit sind auch die offenen Änderungen wieder da. Die Dateien `local_config/*` aus Schritt 2 zurückkopieren, falls nach dem Wechsel etwas daran geändert wurde, zum Beispiel die Slots. Datenbanken: Die neuen Tabellen stören den alten Code nicht. Notfalls die Kopien aus Schritt 2 einspielen. Letzte Reserve: `git clone <bundle>`. **Weg U:** `update_anwenden.zurueck(<guppi>)` stellt nur src/config wieder her. Den Rest holt man über Git oder das Bundle.

**Abbruch, dann sofort zurück:**
- `git switch` verweigert den Wechsel (unversionierte Datei würde überschrieben).
- doctor zeigt SAFE_MODE oder einen `*_error`, und der Grund ist nicht in 15 Minuten behoben.
- Der Rezeptlader verwirft die Live-Datei.
- `uix_check` ist nicht `ok` (Oberfläche startet nicht).
- Canary scheitert (zuerst den NVIDIA-Debug-Modus prüfen, das ist kein Code-Fehler).
- Geschützte Dateien (`local_paths.yaml`, `local_config/*`) haben nach dem Wechsel eine andere Prüfsumme.

**Dauer (Schätzung):** Sicherung und Prüfpaket 20–30 min. Freigabe der Rechteliste hängt vom Captain ab. Der Wechsel selbst dauert 5 min. Tests und doctor 15–30 min, `uix_check` 5 min, Kurzstart mit GPU 5–10 min. Zusammen etwa 1–1,5 Stunden ohne Wartezeit auf Freigaben. Weg U plus Kopierschritt: etwa +30 min.

## 5. Risiken und Fragen an den Captain

**Risiken**
- *Andere Sitzungen* nutzen `<guppi>/workspace/GUPPI_OS` und `.venv` als Bau-Ort. Ein Bau während des Wechsels würde mit gemischtem Code laufen. Gegenmittel: Vorbedingung U-1 und ein Hinweis an die Gruppe.
- *Guard und Rechte werden erweitert* (4 ALLOW-Regeln, 52 Module, neue Stufen). Gegenmittel: namentliche Freigabe U-3. `orchestra`/`wissen` bleiben aus.
- *`START_GUPPI.bat` entfällt.* Der alte Weg über Verknüpfungen bricht. Gegenmittel: Verknüpfungen auf `START_SEDRA.bat` umstellen, Hinweis in `START_HERE.txt` (in A1 vorhanden).
- *Zeilenenden:* In der Installation gilt `core.autocrlf=true`. Beim Wechsel schreibt Git alle Dateien mit CRLF. Das ist harmlos, aber die Prüfsummen der Arbeitsdateien weichen dann vom Manifest ab, das aus LF erzeugt wurde. Darum ersetzt bei Weg G der Git-Stand das Manifest als Beleg.
- *Weg U* löscht `local_paths.yaml` ohne Fix (a) und bringt die Guard-Regeln nicht mit.
- *Lokale Pfade in alten Commits:* Die Geschichte der Installation enthält lokale Pfade. Darum nie nach GitHub pushen (Regel 11).

**Fragen an den Captain (Gates)**
- **F1 / U-2:** Weg G (Git am selben Ort, empfohlen) oder Weg U (`update_anwenden` mit Fix (a) und Kopierschritt)?
- **F2:** Remote der Installation: `a1` lokal und `alt-origin` nur lesend (Vorschlag). Soll später `origin` = GitHub `Sedra-AI-Assistent-OS` mit Release-Tags sein?
- **F3:** Die 2 offenen Mess-Patches (`context_ladder` 192k/256k, `moe_sweep` Ladezeit/RAM) und `canary_retry.py` nach A1 übernehmen, vor oder nach dem Umstieg? Die Nachtketten-Skripte verwerfen (bleiben im Bundle)?
- **F4 / U-3:** Freigabe der Rechteliste: 52 neue Module, GR-029 bis GR-038, `permission_levels.yaml` (D4), neue Configs `orchestra`/`wissen`/`cloud_providers` (aus).
- **F5:** Umsteigen auf `d6d25ca` oder erst nach dem Merge der laufenden Spec-Branches auf `main`, mit einem lokalen Tag? Außerdem: `local_config/` (Wurzel) in `.gitignore` von A1 aufnehmen?
- **U-1, U-4, U-5, U-6:** Ruhefenster ohne Bau oder Messung, Wechsel, Kurzstart mit GPU, Slots in die Live-Rezepte.
