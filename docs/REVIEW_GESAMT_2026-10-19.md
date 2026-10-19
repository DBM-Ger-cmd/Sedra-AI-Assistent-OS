# Gesamtreview SEDRA – Stand 19.10.2026

**Art:** reine Prüfung. Es wurde kein Code, keine Konfiguration, keine Berechtigung und kein Commit geändert. Kein llama-server gestartet, keine GPU-Last erzeugt. Einzige Schreibaktion: dieser Bericht.
**Prüfstand:** Worktree `main` mit laufenden, nicht committeten Änderungen mehrerer Sitzungen. Die Befunde beziehen sich auf den Stand zum Prüfzeitpunkt (ca. 12:00–12:20 Uhr). Während der Prüfung kamen Änderungen dazu (siehe Abschnitt 2.3).
**Ausgangspunkt:** `docs/REVIEW_ARCHITEKTUR_2026-10-19.md`. Dessen Befunde wurden gegen den aktuellen Stand nachgeprüft (Abschnitt 2).

**Pfade:** relativ zum Repo-Wurzelordner. Python-Pfade mit Präfix `runtime/src/guppi_runtime/`, Oberfläche mit `runtime/src/guppi_runtime/uix/`.

**Kennzeichnung der Befunde:**
- **verifiziert (Lauf):** Test oder Aufruf tatsächlich ausgeführt.
- **verifiziert (Lesung):** Zeile gelesen und Ablauf nachvollzogen, nicht ausgeführt.
- **vermutet:** plausibel, nicht geprüft (Größenordnung, Laufzeitverhalten, Fremdbibliothek).

**Aufwand:** klein (unter einem Tag, lokal), mittel (einige Tage, mehrere Dateien), groß (Wochen oder Umbau mit Abstimmung).

**Vollständigkeit:** Alle vier Prüfbereiche (Python-Kern, Oberfläche, Skripte und Konfiguration, Tests) sind gelesen. Nicht gelesen bleiben: Teile von `desk/`, `agent_manager/`, `jobs/job_supervisor.py`, die Gesamtdatei `capability_router.yaml` (nur per Schlüsselsuche), die übrigen rund 150 Testdateien und die Browser-Ausführung der Oberfläche (Abschnitt 6).

---

## 1. Zusammenfassung: die fünf wichtigsten Risiken

1. **Cloud-Aufrufe ohne Logbuch (hoch, verifiziert Lesung).** Drei Stellen erzeugen `ContentGuard(cloud_enabled=True)` ohne `audit`: `labor.py:39`, `labor.py:98`, `redesign_prep.py:61`. Dann schreibt `core/content_guard.py:275-276` keinen Eintrag. Cloud-Verbindungstest, Cockpit-Chat und Textvorbereitung laufen damit ohne Protokoll, obwohl der Docstring „geht nichts raus, wenn das Logbuch nicht schreibt“ verspricht.
2. **Tool-Call-Argumente bei gemischter Antwort (Befund I1 aus dem Architekturbericht: im Arbeitsbaum behoben, nicht committet).** Der Fix steht in `models/router.py:98-131`: Text und Werkzeugaufrufe laufen zusammen durch den Guard. Der zugehörige Test `test_content_guard.py:182-195` ist aber tolerant (Befund T5): Er besteht auch dann, wenn der Guard gar nicht blockiert. Der Fix ist also noch nicht durch einen scharfen Test abgesichert.
3. **Modulschnittstelle und Freigaberoute (hoch, verifiziert Lesung).** `window.sedraApi` ist global und trägt Token und `call` mit frei wählbarer Modul-Kennung (`uix/ui/api.js:37`, `:19`). `POST /api/decisions/answer` gehört zu allen Vorgabe-Shells und zur Vorlage (Architekturbericht P3, P4, P5). Ein Modul kann sich damit als anderes Modul ausgeben und Freigaben erteilen.
4. **Fehler des Betriebs bleiben unsichtbar (mittel, verifiziert Lesung/Lauf).** Ein ungültiger Canary-Wert (z. B. `context: 65536`) schaltet den llama-server ab, auch wenn der Canary aus ist (`models/gpu_canary.py:60-61`, verifiziert im Architekturbericht per Lauf). Eine defekte Schalterdatei deaktiviert alle Schalter (`runtime.py:284-294`). Beides zeigt die Oberfläche nicht als Grund an. Dazu kommen Sicherheitsangaben in den YAML-Dateien ohne Wirkung, z. B. der Block `security` in `model_runtimes.yaml` (`auto_start_external_binaries: false`) und die gesamte `runtime.yaml` (`default_unknown_action: CAPTAIN_REQUIRED`). Sie erwecken den Eindruck eines Schutzes, den es nicht gibt (Abschnitt 3.4, B7a/B7b).
5. **Schlüsselablage und Cloud-Verbindung (mittel, verifiziert Lesung).** Eine defekte `cloud_keys.json` führt beim nächsten Schreiben zu Verlust aller Schlüssel (`cloud_settings.py:58-63`, `:83-93`). Die HTTP-Schicht `models/cloud_api.py:107-125` gibt Kopfzeilen mit Schlüssel bei Weiterleitungen an den Standardhandler weiter. Zusätzlich verbindet sich `redesign_prep.py:63-72` mit Symlinks im Quellordner und kopiert deren Inhalt in den Cloud-Ordner.

---

## 2. Stand der Vorbefunde und Änderungen während der Prüfung

### 2.1 Architekturbericht: Bestätigung

| Kennung | Stand | Stelle (aktuell) | Kennzeichnung |
|---|---|---|---|
| I1 Tool-Call bei Text | **im Arbeitsbaum behoben, nicht committet** | `models/router.py:98-131`, Test `tests/test_content_guard.py:182-195` (tolerant, siehe T5) | verifiziert (Lesung) |
| M1 Canary ungültig schaltet llama-server ab | bestätigt, Zeile verschoben | `models/gpu_canary.py:60-61` (Prüfung nicht in `if self.enabled`) | verifiziert (Lauf im Architekturbericht) |
| M2 Adapter überschrieben | bestätigt | `runtime.py:280` | verifiziert (Lesung) |
| W2 SQLite nicht geschlossen | bestätigt | `gateway/wissen.py:164`, `desk/arbeitsplatz.py:207`, `arbeitsumfeld_wissen.py:91`, `agent_manager/agent_registry.py:8`, `agent_manager/bridge.py:51` | verifiziert (Lauf: 14 Testfehler) |
| I2 zwei Policy-Versionen | bestätigt | `core/content_policy.py:114`, `gateway/klassen.py:17` | verifiziert (Lesung) |
| I3 Rechtsgrundlage nur Konstante | bestätigt | `gateway/klassen.py:19` (einziger Leser `:199`) | verifiziert (Lesung) |
| I4 Schärfe-Modus nur im Speicher | bestätigt | `runtime.py:121` (`mode='sandbox'`) | verifiziert (Lesung) |
| I6 Hash-Test Zeilenenden | bestätigt | Test `tests/test_content_guard.py:66-71` | verifiziert (Lauf: 1 Fehlschlag) |
| K2 Konstruktor-Reihenfolge | bestätigt | `runtime.py:62` ff. | verifiziert (Lesung) |
| K3 widersprüchliche Standards | bestätigt | `runtime.py:208` (True) gegen `runtime.py:352` (False) | verifiziert (Lesung) |
| K5 Audit ohne fsync | bestätigt | `core/audit.py:51` (`open('a')`) | verifiziert (Lesung) |
| V2 Shell-Name im Kern | bestätigt | `gateway/wissen.py:307` | verifiziert (Lesung) |
| P1 Trust-Stufen wirkungslos | teilweise behoben | `desk/gateway.py:31`, `uix_server.py:280-283` setzt bei Installation `COMMUNITY`; Herkunftsableitung für vorhandene Manifeste fehlt | verifiziert (Lesung) |
| P3 Freigabe-Route | bestätigt | `uix_server.py:194-232`, `desk/gateway.py:48` (`FRAME_API`) | verifiziert (Lesung, Architekturbericht) |
| P4 window.sedraApi | bestätigt | `uix/ui/api.js:37`, `:19` | verifiziert (Lesung) |
| P5 Gerüst mit CAPTAIN | bestätigt | `uix_server.py:512` | verifiziert (Lesung) |
| A4 Hub-Sperre über Modellaufrufen | bestätigt | `uix_server.py:1575` (`with self.lock:`) | verifiziert (Lesung) |
| A9 „lade …“ ohne Modell | bestätigt | `uix_server.py:1571-1573` (`no_model` vor Werkzeugen) | verifiziert (Lesung) |
| C1 Schalterdatei | bestätigt | `runtime.py:284-294` | verifiziert (Lesung) |

Nicht erneut geprüft: A1, A2, A3, A5–A8, C2, C3, K1, K4, K6, K7, P2, P6, P7, V1, V3, W1, W3, W4, X1–X3, M3–M5, I5, I7. Sie stammen aus dem Architekturbericht und sind dort mit ihrem eigenen Stand beschrieben.

**Shims (K1):** `runtime/src/guppi_runtime/*.py` enthält 117 Dateien, davon 75 Alias-Module (`sys.modules[__name__] = …`). Zählung nachgeprüft (verifiziert Lauf).

### 2.2 Gemeldete Behebungen, nicht geprüft (vom Partner)

- **`talk.mode` im Bus und im Gesprächs-Manifest:** Laut Partner-Sitzung behoben im Arbeitsbaum, Commit folgt. Nachgeprüft: `ui/bus.js:17` führt `'talk.mode'`, `tools/talk/tool.yaml:20` deklariert `emits: [object.open, talk.mode]`. Ein Lauf der UI-Verträge wurde in dieser Prüfung nicht ausgeführt.
- **`chat_kombi` bei Sperre des Cloud-Schritts:** Laut Partner-Sitzung behoben im Arbeitsbaum, Commit folgt (Sperre wird als Ergebnis `blocked` behandelt, lokaler Entwurf bleibt, 7 Tests grün). Die Stelle, die ich gelesen habe (`uix_server.py:2141-2170`), entsprach vor der Behebung dem Befund T1. Nach der Behebung habe ich den Code nicht erneut gelesen.

### 2.3 Änderungen während der Prüfung

Während der Prüfung änderten sich mehrere Dateien (u. a. `ui/bus.js`, `tools/talk/tool.yaml`, `chat_kombi`). Ein früher Testlauf zeigte zeitweise andere Ergebnisse. Die Befunde in diesem Bericht gelten für den jeweils genannten Stand; ein wiederholbarer Testlauf setzt einen festen Stand voraus (Befund T8).

---

## 3. Befunde je Bereich

### 3.1 Python-Kern (`runtime/src/guppi_runtime`)

Quelle: Lesprüfung durch einen Agenten, Stichprobe durch mich. Alle Befunde sind verifiziert (Lesung), sofern nicht anders angegeben. Keine Tests in diesem Bereich ausgeführt, außer den im Architekturbericht und in Abschnitt 3.5 genannten.

| ID | Datei:Zeile | Befund | Verbesserung | Aufwand | Priorität |
|---|---|---|---|---|---|
| F1 | `labor.py:39`, `labor.py:98`, `redesign_prep.py:61` | Drei `ContentGuard(cloud_enabled=True)` ohne `audit=`. `core/content_guard.py:275-276` schreibt dann keinen Eintrag, `SG_MODEL_CALL` und `SG_STOPPED` fehlen für Cloud-Aufrufe. | Audit aus der Runtime durchreichen; Konstruktor bzw. `_log` ohne Audit im Produktivbetrieb ablehnen. | klein | **hoch** |
| F2 | `models/cloud_api.py:107-125` (`_get`, `_post`) | `urlopen` mit Schlüsselkopfzeilen. Bei Weiterleitung (3xx) übernimmt der Standard-Redirect-Handler die Kopfzeilen, auch an anderen Host oder `http://`. `require_https_url` (`:44-48`) prüft nur die Basis-URL. Die Zusage „nie in einer Fehlermeldung“ (`:8`) deckt das nicht. | Eigenen Redirect-Handler setzen, 3xx ablehnen; Test mit Stub-Server. | klein | mittel |
| F3 | `redesign_prep.py:63-66`, `:71-72` | Kein Symlink-Schutz. `is_file()` und `read_text()` folgen Links; die Datei wird bei ALLOW nach `dst` kopiert. `core/request_binding.py:15, :22` verbietet Symlinks, `prepare` nicht. | `path.is_symlink()` ablehnen, `resolve().relative_to(src)` prüfen. | klein | mittel (hoch, wenn `dst` in die Cloud geht) |
| F4 | `cloud_settings.py:58-63`, `:83-93`, `:65-69` | `_load` gibt bei Lesefehler `{}` zurück; `set`/`delete` schreiben den leeren Stand zurück. Feste Temp-Datei `cloud_keys.tmp`, ohne `fsync` und Sperre. `core/util.py:55-65` (`atomic_write_json`) und `append_lock` existieren schon. | Defekte Datei als Fehler melden; `atomic_write_json`; Read-Modify-Write unter Sperre. | klein | mittel |
| F5 | `core/audit.py:95-97` (`verify_chain`), `core/util.py:67-83` (`read_last_jsonl`), `core/audit.py:38` | Abgeschnittene letzte Zeile lässt `read_last_jsonl` bei jedem `append` scheitern, bis `cli audit-repair` läuft. Der Guard schlägt dann mit `SG_AUDIT_FAILED` fehl (fail-closed, aber Ursache unsichtbar). `verify_chain` wirft statt `False`. | `verify_chain` mit `try` → `False`; Hinweis beim Start. | klein | mittel |
| F6 | `core/content_guard.py:122`, `:154`, `:156` | `_log` wird bei `SG_ONCE_USED`, `SG_ONCE_GRANTED`, `SG_DECISION_REJECTED` nicht auf Rückgabe geprüft. Einmal-Freigaben werden verbraucht oder gesetzt, obwohl kein Eintrag entsteht. Der Docstring (`:14`) sagt das Gegenteil. | Rückgabe prüfen, vor Verbrauch abbrechen. | klein | mittel |
| F7 | `models/router.py:75`, `:78-82` (`_once`) | Ist kein Guard gesetzt, läuft der Aufruf ungeprüft zum Adapter (`if guard is None: result=adapter.chat(...)`). Heute setzt `runtime.py:122` den Guard immer. Fail-open-Muster für künftige Router. | Ohne Guard `ModelAdapterError("guard_missing")`. | klein | mittel (latent) |
| F8 | `tools/git.py:40-47`, `:85` | `core.hooksPath` und Credential-Helper werden abgeschaltet, `core.fsmonitor` und Filtertreiber aus `.gitattributes` bleiben aktiv. Bei fremden Repos kann die Konfiguration Programme starten. Ausführung über fsmonitor/Filter: vermutet. | `-c core.fsmonitor=false`, Filter für Lesebefehle aus. | klein | mittel |
| F9 | `models/role_routing.py:249-262` | Defekte Health-Datei macht alle Anbieter `HEALTHY`; der nächste Schreibvorgang übernimmt das. Cooldowns wirken nicht mehr. | Defekt protokollieren, Anbieter `DEGRADED`. | klein | niedrig |
| F10 | `tools/git.py:40`, `tools/shell.py:50-56` | Ohne Guard lässt `git.py` Befehle ohne Entscheidung durch (`git init` mutiert). `shell.py:56` bricht mit `AttributeError` ab. Heute durch `runtime.py:92-93` nicht ausnutzbar. | Guard im Konstruktor Pflicht. | klein | niedrig |
| F11 | `uix_server.py:948-955` (`install_remove`) | Nur der Endordner wird auf Symlink geprüft; liegt `local_config/tools` als Junction, löscht `rmtree` außerhalb. | `resolve()` und `relative_to(local_config)`. | klein | niedrig |
| F12 | `core/permission_levels.py:110`, `jobs/job_supervisor.py:158`, `:433-434` | Fehlt `policy_hash`, wird die Änderungsprüfung übersprungen (fail-open). Heute setzt der Anlagepfad den Hash. | Fehlenden Hash als `DENIED("policy_hash_missing")`. | klein | niedrig |
| F13 | `models/llama_server_runtime.py:301-302`, `:343-346` | Ein fremder Server auf dem Port kann die Startschleife als „gestartet“ beenden. | `/props` gegen `identifier` prüfen, `self._proc.poll() is None`. | klein | niedrig |
| F14 | `devenv/mcp_shield.py:98-105`, `state_mcp.py:121-127`, `:138-139` | Ganzzahlfelder ohne Untergrenze (`limit: -1`); Protokoll ohne Größenbegrenzung. | `min` im Schema, Längenbegrenzung. | klein | niedrig |
| F15 | `models/gpu_preflight.py:76-78` | Nur die erste GPU wird gelesen; leere Ausgabe wirft `IndexError`. Mehr-GPU-Verhalten: vermutet. | Summe, `GpuNotClean` bei leerer Ausgabe. | klein | niedrig |
| F16 | `models/gpu_preflight.py:86-106` | Zwischen Auflistung und `taskkill` kann die PID an einen fremden Prozess gehen. Race: vermutet. | Vor dem Stopp erneut prüfen. | klein | niedrig |
| F17 | `gateway/dokumente.py:46` | `ET.fromstring` ohne Härtung gegen Entity-Expansion; Größenlimit `MAX_XML_BYTES` (`:15`, `:44`) deckt das nicht ab. Expat-Version: vermutet. | `defusedxml` oder Prüfung auf `<!DOCTYPE`/`<!ENTITY`. | klein | niedrig |
| F18 | `core/guard.py:66` | `KeyError` bei unbekannter Entscheidung aus `guard_rules.yaml`; Regeldatei wird nicht validiert. | Validierung beim Laden. | klein | niedrig |
| F19 | `sandbox/provider.py:62-64`, `:80-83` | Worker-stderr auf `DEVNULL`; `json.loads` ohne Abfang. Startfehler sind unsichtbar. | stderr in Job-Datei; Parsefehler abfangen. | klein | niedrig |
| F20 | `models/cloud_api.py:63-66` (`_error_detail`) | Schwärzung nur für Präfixe `(nvapi|sk)-` und Werte über 12 Zeichen. Ein Schlüssel mit anderem Präfix kann in Fehlertexten landen, falls der Anbieter ihn spiegelt. | Konkreten Schlüsselwert gezielt ersetzen. | klein | niedrig |
| F21 | `core/content_policy.py:199-217`, `core/content_guard.py:86-87`, `:107` | Im Modus „beobachten“ lassen lokale Funde in fremden Inhalten Schlüssel durch; lokal sind Karten und Personen nur Notiz. Vermutlich gewollt (Captain, 15.10.), sollte bestätigt und dokumentiert werden. | Bestätigung dokumentieren. | klein | niedrig (zur Kenntnis) |
| F22 | `core/content_policy.py:221-224`, `core/content_guard.py:115`, `:187-190` | `binding_hash` ohne `mission_id`: eine „einmal“-Freigabe gilt für jede Mission mit gleichem Inhalt, Modell und Weg, zehn Minuten lang. | `mission_id` in die Bindung, oder dokumentieren. | klein | niedrig (zur Kenntnis) |

**Gut geprüfte Bereiche ohne neue Befunde (Lesung):** `core/request_binding.py` (Symlinks, Budgets), `core/mission_lock.py` und `core/util.py` (Sperre, atomares Schreiben), `sandbox/broker.py` (Pfad, Symlink, Größen, Manifest), `tools/base.py` (`_resolve` prüft Symlinks je Pfadteil), `tools/shell.py` (Erlaubnisliste; Captain-Zweige in `:50-57` sind faktisch tot), `models/cloud_api.py` (Schlüssel nur aus Umgebung oder DPAPI, `health()` ohne Netz).

**Nicht vertieft:** `jobs/job_supervisor.py` (1.382 Zeilen), `desk/` und `agent_manager/` im Detail, `uix_server.py` außer den genannten Stellen, `runtime.py` außer den bekannten Stellen.

### 3.2 Oberfläche (`runtime/src/guppi_runtime/uix`, JavaScript)

Quelle: Lesprüfung durch einen Agenten, Stichprobe durch mich.

**Zeilenregel (max. 400 je Datei):** eingehalten. Geprüft über 87 `.js`-Dateien. Am Limit: `tools/talk/tool.js` mit genau 400 Zeilen (kein Puffer), `tools/labor/tool.js` 394, `tools/gateway/tool.js` 384, `tools/workshop/tool.js` 379.

| ID | Datei:Zeile | Befund | Verbesserung | Aufwand | Priorität |
|---|---|---|---|---|---|
| J1 | `ui/bus.js:8-21`, `tools/talk/tool.yaml:20` | `talk.mode` fehlte in `EVENTS` und im Manifest; Online-KI-Umschaltung (`tools/gauge-cloud/tool.js:20`, `talk/tool.js:103`) wurde vom Bus abgelehnt. **Laut Partner-Sitzung im Arbeitsbaum behoben, Commit folgt.** Nachgeprüft: Eintrag in `bus.js:17` und `talk/tool.yaml:20` vorhanden. | Test für Hin- und Zurückschalten. | klein | hoch (behoben, offen committen) |
| J2 | `ui/api.js:37`, `:19` | `window.sedraApi = {token, call, forModule, api}` global. `call` nimmt jede Modul-Kennung und setzt den Header aus ihr. Ein Skript kann sich als anderes Modul ausgeben. Die Serverprüfung habe ich nicht gelesen. | `call` und `forModule` nicht global; Token nicht als Eigenschaft. | mittel | hoch |
| J3 | `ui/api.js:7`, `ui/loader.js:62`, `js/status.js:96`, `js/core.js:4` | Token im URL-Fragment, im Query-String von `EventSource` (`loader.js:62`) und in der iframe-URL zu `/hardware` (`status.js:96`). Query-Strings landen in Server- und Proxy-Logs. | Kurzlebiges Stream-Ticket oder Cookie (`SameSite=Strict`) für `/api/events`; Fragment nach dem Lesen entfernen (`history.replaceState`). | mittel | mittel (Query-Variante höher) |
| J4 | `ui/api.js:23`, `tools/talk/tool.js:298-301`, `tools/talk/kombi.js:12-14`, `tools/talk/tool.js:227-228` | `fetch` ohne Zeitlimit. „Denkt nach …“ bleibt bei hängendem Server stehen. | `AbortController` mit Timeout, Meldung „antwortet nicht“. | klein | mittel |
| J5 | `tools/talk/tool.js:92` | Enter ruft `submit()` ohne Sperre auf; der Senden-Knopf sperrt über `ui/dom.js:27-34`. Doppelte Anfragen und unsauberer `this.history` (`:299`, `:307`). | `busy`-Flag in `submit()`; gilt auch für `kombi.js` und `sendCloud`. | klein | mittel |
| J6 | `js/desktop.js:131-137` | `imageType` aus Browser-MIME ungeescaped in `innerHTML`. Risiko gering. | `escapeHtml` oder DOM-API. | klein | niedrig |
| J7 | `js/core.js:4-15`, `ui/api.js` | Zwei getrennte HTTP-Clients mit getrennter Token-Ableitung; `core.js` setzt keine Modul-Kennung. | Ein Client. | mittel | mittel |
| J8 | `tools/schutz/tool.js:255` | Promise ohne `.catch`; unhandled rejection in der Konsole. | `.catch` oder `d().button`. | klein | niedrig |
| J9 | `tools/talk/kombi.js` / `tools/talk/tool.js:221`, `ui/loader.js:93, :97` | `kombi.js` ist eingebunden (`tool.yaml`, `entry`). Schlägt sein Laden fehl, bricht `loader.js:93` ab und das Werkzeug „Gespräch“ wird nicht registriert. `tool.js:221` ruft `root.sedraTalkKombi` ohne Prüfung. | `if(!root.sedraTalkKombi)`-Prüfung, Ladefehler pro Datei. | klein | niedrig bis mittel |
| J10 | `tools/talk/tool.yaml:23` | `tests: [test.spec.js]`, die Datei fehlt. | Datei anlegen oder Eintrag entfernen. | klein | niedrig |

**Positiv (Lesung):** `ui/dom.js:25-37` (`button()` sperrt und zeigt Fehler 8 s), `tools/gateway/tool.js:58-70` (`refresh()` mit sichtbarem Fehler), keine `eval`/`new Function` im Bereich, keine `innerHTML`-Nutzung in `tools/*/tool.js` (Grep).

**Nicht gelesen:** `tools/labor/tool.js`, `tools/entwurf/tool.js`, `ui/frame.js`, `js/models.js`, Teile von `shells/cockpit/dock.js` und `tools/workshop/tool.js`, `shells/minimal|paperclip|start/*`. Muster (innerHTML, fetch, Token, Ereignisse) wurden per Grep geprüft; weitere Befunde sind möglich.

### 3.3 Skripte und Starter

Quelle: Lesprüfung durch einen Agenten (vollständige Liste im Scratchpad, `agent_skripte.md`), Stichproben durch mich. Ausgeführt wurden nur: `sh -n start_sedra.sh` (Syntax), Byte- und Dateiprüfungen, Schlüsselsuche in den YAML-Dateien. Nichts gestartet, kein Build, keine GPU.

| ID | Datei:Zeile | Befund | Verbesserung | Aufwand | Priorität |
|---|---|---|---|---|---|
| A1 | `start_sedra.sh`, `runtime/*.sh` | Arbeitskopie CRLF, Index LF (`git ls-files --eol`). `sh -n` läuft in Git Bash durch. Auswirkung unter POSIX (Shebang `/bin/sh\r`) nicht getestet: vermutet. | `.gitattributes` mit `*.sh text eol=lf`. | klein | niedrig |
| A2 | `START_SEDRA.bat:15`, `start_sedra.sh:20` | Architekturversion `v1.20` hart verdrahtet. `architecture/` enthält v1.17, v1.20, `sandbox_research_v1.0`. Auswahl im Starter, nicht in der Runtime. | Pfad aus Konfiguration oder Umgebungsvariable; dieselbe Auflösung wie `runtime.py:57-67`. | klein | mittel |
| A3 | `runtime/validate_package.py:5`, `src/guppi_runtime/agent_manager/cli.py:214` | Architekturversionen lexikografisch sortiert (`v1.9` > `v1.20`). Heute richtig, bei einstelliger Nachfolgeversion falsch. `validate_package.py` wirft `IndexError` ohne Architekturordner. Die Runtime (`runtime.py:57-59`) sortiert numerisch. | Gemeinsame Funktion aus `runtime.py`; leere Liste abfangen. | klein | mittel |
| A4 | `runtime/ready_test.py:12, :16, :19` | Keine `architecture_root`-Übergabe; im Standardlayout `FileNotFoundError`. Standardpfad `.` schreibt nach `runtime/runtime_data/`. Berichtsname `PC_READY_TEST_v1.15.json` veraltet. Kein Starter ruft das Skript auf. | `--architecture` wie `READY_TEST_WINDOWS.bat` übernehmen. | klein | niedrig |
| A5 | `runtime/run_tests.bat:7`, `run_tests.sh:8`, `run_doctor.*`, `run_demo.*`, `benchmarks/mtp_tune_…_run.bat:7,9`, `benchmarks/sandbox_dns_capture.ps1:32` | Nutzen `runtime\.venv`, der im Worktree fehlt (Lauf). `START_SEDRA.bat` nutzt `portable\python\current` (vorhanden). Zwei Python-Umgebungen. | Auflösung angleichen oder Umgebungen dokumentieren. | klein | mittel |
| A6 | `runtime/run_hardware_manager.sh:4` | `--root .` (= `runtime/`) statt `workspace/GUPPI_OS`; kein venv, kein `PYTHONPATH`; `python3` statt venv-Python. | `--root ../workspace/GUPPI_OS`, venv-Python, `PYTHONPATH` wie `run_demo.sh`. | klein | mittel |
| A7 | `runtime/benchmarks/mtp_tune_qwen35_2026-10-12_run.bat:3, :7, :9` | Zielordner `workspace\GUPPI_OS\runtime_data\measurements` fehlt (Lauf); cmd bricht die Umleitung ab, bevor Python startet. Setzt `GUPPI_ENGINE_BUILD=b11160`, ohne SHA-Pins (siehe B7i). **Nicht gestartet**, weil GPU-Last. | `mkdir` vor der Umleitung; Build-Pin oder Sperre für Messläufe. | klein | mittel |
| A8 | `runtime/benchmarks/sandbox_dns_capture.ps1:25-35` | `pktmon filter add GUPPI-DNS` vor `pktmon start`; schlägt `start` fehl, bricht `throw` (`:28`) ab, bevor der `finally`-Block (`:29-35`) greift. Filter bleibt im System stehen; der Kommentar (`:9`, „removed at the end“) stimmt für diesen Pfad nicht. `Set-Location` ohne `Pop-Location`. | Filter-Setup in den `try`-Block; Entfernen vor `throw`; `Pop-Location`. | klein | mittel |
| A9 | `START_SEDRA.bat:108, :112` | `set /p` mit `%CHOICE%` in `echo … \|`: `&` oder `\|` in der Eingabe hängt ein Kommando an. Betrifft nur die Person am Gerät. | `!CHOICE!` mit verzögerter Expansion. | klein | niedrig |
| A10 | `Erststart_Konfig.ps1:33`, `runtime/config/llama_server.yaml:27, :42` | `engine_build` wird per Textmuster gelesen und trifft zuerst die eingerückte Canary-Zeile (`:27`). Heute beide `b11371`. Laufen sie auseinander, prüft der Erststart einen anderen Build als `engine_download.py` (liest YAML). Fehlt der Treffer, ist `$Build` leer. | YAML lesen (`llama_server.engine_build`). | klein | mittel |
| A11 | `Erststart_Konfig.ps1:18, :19, :25` | Modellpfad mit Apostroph (z. B. `O'Brien`) ergibt ungültiges YAML (`'` nicht verdoppelt). `Set-Content -Encoding UTF8` schreibt in PS 5.1 einen BOM (siehe C4). | `Replace("'", "''")`; Schreiben ohne BOM. | klein | niedrig |
| A12 | `runtime/Ersteinrichtung.ps1:18-21` | Bei falscher oder abgebrochener Datei wirft das Skript „Download-Pruefsumme stimmt nicht“, lädt aber nicht neu. Der Benutzer muss die Datei löschen. | Bei Hash-Fehler löschen und einmal neu laden. | klein | niedrig |
| A13 | `runtime/examples/self_dev/uix_window/tests/test_uix_window.py:5, :14, :17`, `runtime/tests/test_auftrag.py:116` | Feste Benutzerpfade (`C:\Users\D\…`, `C:\Users\David\…`) nur in Tests und Beispielen. Keine echten Schlüssel in den Skripten gefunden. | Temporäre Pfade. | klein | niedrig |
| A14 | `start_sedra.sh:23-33` | Nur Existenzprüfung von `python3` (README verlangt Python ≥ 3.11). Kein `Erststart_Konfig`, kein `engine_download.py`, kein `Test-PortableRuntime` auf POSIX; ob gewollt, ist nicht dokumentiert. `--system-site-packages` ohne Isolation (vgl. `-I` im Windows-Starter). | Versionsprüfung mit Meldung; Entscheidung dokumentieren. | klein bis mittel | mittel |
| A15 | `runtime/build_offline_runtime.py:39, :84, :85, :88`, `runtime/prepare_sandbox.py:14-15` | `read_text()` ohne Kodierung; `'.data' in PurePosixPath(...).parts[0]` ist eine Teilstring-Prüfung (`x.database/` wird verworfen); Wheel-Suche mit verschiedenen Mustern; Version `0.7.4` fest. | Kodierung angeben; Prüfung auf Gleichheit; eine Version-Quelle. | klein | niedrig |

**Positiv (Lesung):** Alle Server binden an Loopback (`uix_server.py:3014`, `hardware_manager/dashboard.py:49`, `llama_server_runtime.py:67-69`, `selfdev/kev.py:45-46`). `engine_download.py` prüft SHA256 vor dem Entpacken und fragt vor dem Download. `Ersteinrichtung.ps1` prüft SHA256 mit Größenlimit. `build_offline_runtime.py` verwirft Links, Verschlüsselung, `.pth`-Dateien und Pfadkollisionen. `START_SEDRA.bat` prüft `errorlevel` nach jedem Schritt. `.gitignore` schließt `local_paths.yaml`, `.venv/`, `portable/`, `runtime_data/`, `*.log` aus. Löschaktionen treffen nur feste oder selbst erzeugte Pfade; kein offenes `rm -rf` mit Platzhalter gefunden.

### 3.4 Konfiguration und Overlay

Quelle: Lesprüfung durch einen Agenten, Schlüsselgegenprüfung per Skript (nur Lesen) über alle `runtime/config/*.yaml` gegen `runtime/src` und `uix/js`, Stichproben durch mich.

**Lade-Logik (Lesung):** Eine zentrale Konfigurationsschicht gibt es nicht. Jede YAML wird im jeweiligen Modul einzeln gelesen (z. B. `llama_server_runtime.py:109`, `model_loader.py:65`, `job_supervisor.py:125`, `token_policy.py:95`, `resource_scheduler.py:61`, `tools/web.py:47`). Overlay nur für: Cloud (`cloud_settings.py:112-116`, `local_config/cloud_providers.yaml` vor `config/`), Routing (`models/role_routing.py:186-189`, `local_config/role_routing.yaml`), Schalter (`local_switches.py`, nur `ALLOWED`-Abschnitte) und Routing-Profile (`routing_profiles.py`). Schalter werden in `runtime.py:275-276, :205-206, :300, :334` angewandt.

**Bestätigte Vorbefunde (Architekturbericht):**
- **C1** Eine fehlerhafte Schalterdatei schaltet alle Schalter ab (`runtime.py:284-294`, `local_switches.py:48-61`). Nur `ValueError` wird gefangen (`runtime.py:289`); `OSError` nicht (`local_switches.py:45-47`), also bricht eine gesperrte Datei den Start ab. Verifiziert (Lesung).
- **C2** Startfehler erscheinen nur in `boot()` (`runtime.py:385`) und einzelnen Ansichten. Weitgehend bestätigt (Lesung).
- **C3** Drei Orte ohne gemeinsame Rangfolge. Bestätigt (Lesung).
- **C4** BOM in `runtime/config/local_paths.yaml` und `workspace/GUPPI_OS/local_config/switches.yaml` (Lauf: Byte-Analyse). Ursache `Erststart_Konfig.ps1:19, :25` (`Set-Content -Encoding UTF8` in PS 5.1). PyYAML überspringt den BOM, daher kein akuter Fehler.
- **K3** `runtime.py:208` (`True`) gegen `runtime.py:352` (`False`) für `lm-studio`. Ohne Wirkung, weil `enabled: false`.
- **K4** Architekturordner nicht in `workspace/`; siehe A2.
- **M4** Modellpfad `<modelle>` per Textersetzung (`local_paths.py:34-39`, nicht rekursiv). Pfad auf diesem PC stimmt (Lauf: Datei `…\unsloth\Qwen3.5-9B-MTP-GGUF\Qwen3.5-9B-Q6_K.gguf` vorhanden, 7,68 GB). Ordner-Existenz wird nicht geprüft; die Konvention „Ordner oberhalb von `unsloth`“ steht in keiner Datei.
- **M1, M2** bestätigt (siehe 2.1).

**Neue Befunde:**

| ID | Datei:Zeile | Befund | Verbesserung | Aufwand | Priorität |
|---|---|---|---|---|---|
| B7a | `runtime/config/model_runtimes.yaml:17-21` | Block `security:` (`local_endpoints_only`, `auto_download_models`, `auto_start_external_binaries: false`, `runtime_control_requires_captain`) wird nirgends gelesen (Lauf: Schlüsselsuche). `auto_start_external_binaries: false` ist irreführend: GUPPI startet den llama-server (`llama_server_runtime.py`). Dazu `:13-15` `providers_dir`, `catalog_dir` ungenutzt. | Block entfernen oder mit Code verdrahten und testen. | klein | mittel |
| B7b | `runtime/config/runtime.yaml` (16 Zeilen, Block `runtime_config`) | Datei wird nicht gelesen (Lauf: keine Referenz auf `runtime.yaml` oder `runtime_config` in `runtime/src`). `default_unknown_action: CAPTAIN_REQUIRED`, `strict_mode: true`, `health_checks_enabled: true` sehen nach Sicherheitsvorgabe aus und sind tot. Der tatsächliche Standard steht in `guard_rules.yaml`. | Datei entfernen oder anbinden, mit Test. | klein | mittel (Irreführung) |
| B7c | `runtime/config/sandbox.yaml:7` | `image_archive_sha256` nicht gelesen; der Plan verlangt die Prüfsumme (`sandbox/provision.py:30`). Angabe in der Datei ist tot. | Entfernen oder anbinden. | klein | niedrig |
| B7d | `sandbox.yaml` (`sdk_version: 0.7.4`), `sandbox/broker.py:32`, `sandbox/worker.py:235`, `build_offline_runtime.py:88`, `Test-PortableRuntime.ps1:6` | SDK-Version an fünf Stellen. Die YAML-Angabe wirkt nur gegen eine Konstante. | Eine Quelle. | klein | niedrig |
| B7e | `runtime/config/self_development.yaml:28 ff.` | Block `invariants` (`no_permission_escalation`, `e3_never_auto_activates` u. a.) nirgends im Code. Die Invarianten gelten nur über andere Mechanismen. | Als Dokumentation kennzeichnen oder im Test prüfen. | klein | niedrig |
| B7f | `runtime/config/capability_router.yaml:20 ff.` | `capability_aliases` ungenutzt (Lauf: Schlüsselsuche). Die 861 Zeilen wurden nicht vollständig gelesen; `execution_binders` (`:844`) wird gelesen (`capability_router.py:341`). | Entfernen oder anbinden. | klein | niedrig |
| B7g | `runtime/config/kev.yaml` (`local_only: true`) | Modus fest im Code (`selfdev/kev.py:49`); der YAML-Schalter hat keine Wirkung. | Entfernen oder prüfen. | klein | niedrig |
| B7h | `runtime/config/llama_server.yaml:34-37` (Kommentar, `engine_source: guppi`) und `models/llama_server_runtime.py:55` | Fehlt der Schlüssel, greift der Standard `"lmstudio"`. Der Kommentar verspricht „no fallback to LM Studio“. Fehlt der Schlüssel, startet GUPPI still die LM-Studio-Binärdatei. | Standard `"guppi"` oder Fehler bei fehlendem Schlüssel. | klein | mittel |
| B7i | `llama_server.yaml:23, :40` (b11160), `:27, :42` (b11371), `engine_assets` | Widersprüchliche Engine-Angaben: stabiler Build b11160 in Kommentaren, b11371 als Wert; nur b11371 gepinnt. `engine_provision.py:50` wirft `engine_assets_missing` für Builds ohne Pins. Messskript setzt b11160 per Umgebungsvariable (`llama_server_runtime.py:60-61`, siehe A7). | Kommentare und Pins angleichen; Umgebungsvariable im Status anzeigen. | klein | mittel |
| B7j | `llama_server.yaml:19` (`mtp: true`) und `model_loader.yaml` | Zwei MTP-Messungen auf unterschiedlichen Wegen ohne Erklärung des Geltungsbereichs. Kein Widerspruch im Code. | Ein Satz je Datei. | klein | niedrig (vermutet) |
| B7k | `runtime/src/guppi_runtime/jobs/resource_scheduler.py:38` vs. `runtime/config/resource_scheduler.yaml` | Code-Standard `vram_reserve_gb = 1.0`, YAML `0.7` (Captain-Entscheidung 13.10.2026). Fehlt der Schlüssel, gilt 1,0. | Code-Standard angleichen. | klein | niedrig |
| B7m | `runtime/config/model_runtimes.yaml:7-9` | Generischer `llama-cpp-server` mit Endpunkt `:8080` ist standardmäßig an. Drei Ziele: `:8080` (generisch), `:8089` (llama_server), `:8093` (Canary). Ist `llama_server` aus, zeigt der Router auf `:8080`, ohne dass dort ein Server läuft. | Standard prüfen; Status zeigt den aktiven Endpunkt. | klein | niedrig |
| B7n | `runtime/config/model_profiles.yaml` | `verification.provider: kev` und `base_model`, obwohl `kev.yaml` (`enabled: false`) und `role_routing.yaml` (`verifier.local_kev`) aus sind. `base_model` nicht gelesen (Lauf). | Kommentar oder Test. | klein | niedrig |
| B7o | `llama_server_runtime.py:54, :63, :66`; `model_removal.py:173-174`; `llama_server.yaml:39` | Pfade `backend_dir`, `engine_root`, `vendor_dir`, `models_root` nur auf Typ und Nicht-Leer geprüft, nicht auf Existenz. Fehler erst bei Nutzung. | Existenz beim Laden melden. | klein | niedrig |
| B7p | `runtime/config/job_supervisor.yaml` `context_manager.retention` | Schlüssel nicht im Code; der Kommentar sagt „not enforced yet“. Bekannt. | — | — | — |

**Schlüsselsuche (Lauf, Ergebnis):** Keine Treffer ohne Schlüsselnamen für `cloud_providers.yaml`, `kev.yaml`, `local_paths.yaml`, `model_loader.yaml`, `permission_levels.yaml`, `resource_scheduler.yaml`, `role_routing.yaml`, `token_policy.yaml`, `web_access.yaml`, `benchmark_policy.yaml`. Tote Schlüssel: siehe B7a, B7b, B7c, B7e, B7f, B7g, B7n, B7p. Falschtreffer (verschachtelte Schlüssel, dynamisch gelesene Namen) bei `llama_server.yaml`, `skill_library.yaml`, `capability_router.yaml`. Die Gegenrichtung (im Code gelesen, nicht in YAML) wurde nicht systematisch geprüft; die Standards für `kev.*` (`runtime.py:80-84`) und `llama_server.host`/`port` (`llama_server_runtime.py:67, :70`) stimmen mit dem YAML überein.

**Positiv (Lesung):** Cloud fail-closed (`cloud_providers.yaml:9` `enabled: false`; `cloud_api.py:44-47` erzwingt https). `permission_levels.yaml` `never_automatic` wird gelesen und auf Überschneidung geprüft (`core/permission_levels.py:34-39`). Schalter nur für freigegebene Abschnitte (`local_switches.py:24-31`). Ungültige Werte werden typgeprüft (`llama_server_runtime.py:47-93`, `resource_scheduler.py:38-45`, `job_supervisor.py:73-92`).

### 3.5 Tests

Quelle: Lesprüfung der Tests, Stichprobe und Automatik-Scan (Assertions, Skips, schluckende `except`, Pfadzugriffe) durch einen Agenten. Kurze Läufe ohne GPU und ohne Server.

**Testläufe (verifiziert Lauf):**

| Datei | Tests | Ergebnis | Hinweis |
|---|---|---|---|
| `test_content_guard` | 28 | 1 Fehler | bekannter Hash-Test (I6) |
| `test_gateway_wissen` | 14 | 14 Fehler | alle `PermissionError [WinError 32]` beim Aufräumen, Testkörper grün (W2) |
| `test_role_routing` | 79 | OK | keine Fehler |

Hinweis zur Anleitung: `PYTHONPATH=runtime/src:runtime/tests` funktioniert unter Windows nicht, weil Windows `;` als Trenner verlangt. Richtig: `PYTHONPATH="runtime/src;runtime/tests"`. Die `run_tests.bat/.sh` setzen eine `.venv` voraus, die in diesem Worktree nicht existiert.

**Befunde:**

| ID | Datei:Zeile | Befund | Verbesserung | Aufwand | Priorität |
|---|---|---|---|---|---|
| T1 | `tests/test_chat_kombi.py:68-75`, `:44-56` | **Falsch grüner Test.** Der Test mockt `chat_cloud` mit `ContentGuardStop`. Der echte Pfad wirft diese Ausnahme nicht; `labor.cloud_chat` gibt `{"status": "blocked"}` zurück. Vor der Behebung ergab `chat_kombi` dann `completed` mit `cloud: None`. **Laut Partner-Sitzung behoben im Arbeitsbaum, Commit folgt** (Sperre als Ergebnis; Tests: Sperre als Ergebnis, als Ausnahme, Fehler; 7 grün). Den Testlauf habe ich nicht selbst wiederholt. | Stubs am echten Pfad ausrichten (behoben, siehe 2.2). | klein | hoch |
| T2 | `tests/test_ki_aufteilung_beweis.py:78`, `:55-59`, `:62-66`, `:96-97`, `:45-46` | Kein Beweis. Lokaler Teil wird nur mit llama-server auf 127.0.0.1:8089 ausgeführt, sonst Skip; ruft `LlamaCppServerAdapter.chat` direkt auf, ohne `ModelRouter` und Guard. Cloud-Teil `test_cloud_sieht_nur_das_bereinigte` ist ein fester `SkipTest`. Prüfung per Teilstring (`'30'`, `'120'`, `'170'`) mit Fremdtreffern. Netzaufruf beim Einlesen (`:55-59`). | Umbenennen (`test_ki_aufteilung_lokal_modell`), Cloud-Teil entfernen oder `expectedFailure`; Wortgrenzen-Regex; Netzaufruf in Testlauf verlegen. | mittel | hoch |
| T3 | `tests/test_gateway_wissen.py:15-19` | 14 rote Tests durch SQLite-Verbindung, die nie geschlossen wird (`gateway/wissen.py:164`, `close()` bei `:387` nicht aufgerufen). Verdeckt echte Fehler. Kann auch im Produktivcode Dateisperren bedeuten. | `self.addCleanup(self.w.close)` nach dem Tempdir-Cleanup; prüfen, ob `GateWay` ebenfalls Verbindungen hält. | klein | mittel bis hoch |
| T4 | `tests/test_uix_server.py:50-51, 122-127, 233-236, 348-350, 384-390, 455-458, 568-571, 625-627` | Quelltext-Stringtests (`*_is_wired`): prüfen, ob Zeichenketten in JS/HTML stehen, nicht ob die Funktion etwas tut. Die Datei hat daneben echte HTTP-Tests (`:34`) und node-Tests (`:159`, `:354`). | Verhaltenstests ergänzen oder als „Verdrahtungs-Smoke“ kennzeichnen und getrennt laufen lassen. | mittel | mittel |
| T5 | `tests/test_content_guard.py:182-195` | **Tolerant; schützt den I1-Fix nicht.** `try/except ContentGuardStop: out = None`, dann `assertFalse(out and TOKEN in …)`. Der Test besteht, wenn der Guard nicht blockiert und das Token fehlt; er prüft nicht, dass die Sperre passiert. | `assertRaises(ContentGuardStop)` oder konkretes Ergebnis ohne Token. | klein | mittel |
| T6 | `tests/test_content_guard.py:73-77` | `test_b6core_does_not_reach_the_network` prüft per Textsuche (`urllib`, `socket`, `subprocess`), umgehbar und mit Fehlalarmen. `test_core_boundary_src.py` nutzt dagegen den AST. | AST-Prüfung. | klein | mittel |
| T7 | `tests/test_content_guard.py:347` | `r = g.call(...) if mode != 'sandbox' else None`: im Modus `sandbox` entfällt die Prüfung ohne Meldung. | Erwartung je Modus als Tabelle. | klein | niedrig |
| T8 | `tests/test_role_routing.py:766` | `@env_skip.needs_ram(16)` auf der Architekturgrenze „keine Anbieter- oder Modellnamen“. Auf Rechnern unter 16 GB RAM übersprungen, also dort ungeprüft. | Textprüfung ohne RAM-Bedingung. | klein | mittel |
| T9 | `tests/test_cuda_crash_hunt.py:28-34` | Nicht mit `needs_pc_files` markiert; schlägt ohne Modelldateien fehl. | Dekorator ergänzen. | klein | mittel |
| T10 | `tests/test_uix_server.py:11`, `tests/test_gateway.py:14`, `tests/test_role_routing.py:29` | Architekturpfade hart kodiert in unterschiedlichen Versionen (`v1.17_RUNTIME_SYNC`, `v1.20_SELF_DEVELOPMENT`). | Konstante in `tests/host_isolation.py` oder Helfer mit `glob`-Auswahl. | klein | niedrig bis mittel |
| T11 | `tests/test_uix_server.py:16-22, 24-27, 84-86` | Akzeptanzmengen statt fester Erwartung. | Erwartung aus Testkonfiguration ableiten. | klein | niedrig |
| T12 | `tests/test_gpu_canary.py:13`, `test_llama_server_runtime.py:12-13`, `test_token_policy.py:13`, `test_gateway.py:12`, u. a. | Testdateien importieren einander (`from test_content_guard import FakeAdapter`). Umbenennen einer Datei bricht andere. | Gemeinsame Helfer nach `tests/helpers.py`. | mittel | mittel |
| T13 | `tests/test_acceptance_suite.py`, `test_*_acceptance.py` (u. a. `test_agent_contracts_acceptance.py`, `test_code_meter_acceptance.py`), `suite_helper.py:13` | Null Assertions; delegieren an `workspace/GUPPI_OS/acceptance/suites`. Dieser Ordner existiert im Worktree nicht. Die Abnahmetests für Agenten, Matcher, Registry, Import und Code-Meter **laufen nie**. | Suiten bereitstellen oder die Lücke dokumentieren. | mittel | mittel |
| T14 | `tests/test_gateway_ende_zu_ende.py:120-126` | Implementierungsdetail (Platzhalter-`<>` im Systemprompt); bricht bei Prompt-Umbau, obwohl das Verhalten gleich bleibt. | Auf Verhaltenstest verlagern. | klein | niedrig |
| T15 | `tests/test_cuda_crash_hunt.py`, `test_arbiter_probe.py:10,51`, `test_devvm_style.py`, `test_acceptance_vm.py` | Lesen aus `workspace/GUPPI_OS`; durch `skipUnless` geschützt. Schreibzugriffe nicht gefunden (vermutet für den Rest). | — | — | — |

**Positiv:** `test_gateway_ende_zu_ende.py` (echte Hub-Aufrufe, echte Docx-Auswertung, Gate-Pfade, Cloud-Simulation ehrlich beschriftet), `test_role_routing.py:263` (drei klare Erwartungen). Keine Reihenfolgeabhängigkeit und kein Schreiben in den echten Workspace in den gelesenen Dateien.

**Ungetestet oder kaum getestet (Namensabgleich, vermutet, Stichprobe):**

| ID | Modul | Befund | Priorität |
|---|---|---|---|
| L1 | `core/b6core/privacy.py` (195 Zeilen) | keine Testdatei; Personenbezug nur indirekt | hoch |
| L2 | `core/content_policy.py` (288 Zeilen) | nur Import-Grenze geprüft, keine Verhaltenstests | hoch |
| L3 | `core/b6core/contracts.py` (153 Zeilen) | nur Hash-Test | mittel bis hoch |
| L4 | `gateway/dokumente.py` (60 Zeilen) | `MAX_XML_BYTES`-Zweig (`:44-45`) und kaputte Zip-Größen ungetestet | mittel |
| L5 | `gateway/probe.py` (89) | nur Namenstreffer | mittel |
| L6 | `core/audit.py` (Kettenprüfung) | kein eigener Manipulationstest | mittel |
| L7 | `coder_ext/think_guard.py`, `churn_guard.py`, `no_call_monitor.py`, `read_tracker.py`, `syntax_note.py`, `result_pruner.py`, `tool_cards.py`, `fuzzy_edit.py` | ohne Namenstreffer; `test_little_coder_guards.py` deckt vermutlich Teile ab | mittel |
| L8 | `redesign_agent.py`, `redesign_review.py`, `redesign_run.py` | ohne Namenstreffer; `test_redesign_prep.py` nur für Vorbereitung | mittel |
| L9 | `capabilities/self_diagnosis.py`, `devenv/external_agent.py`, `devenv/build_log.py` | ohne Namenstreffer | niedrig bis mittel |
| L10 | Architekturgrenze `core` | `test_core_boundary_src.py:17` (`FORBIDDEN`) prüft nur `devenv`, `devvm*`, `agent_manager`, `coder_ext`; Importe von `core` nach `gateway`, `desk`, `uix`, `jobs` werden nicht geprüft (verifiziert Lesung) | mittel |

**Fehlalarme des Scans (geprüft):** 21 Funktionen ohne direkte Assertion nutzen Hilfsmethoden mit Assertions (z. B. `test_verification_gate.py:121-165`). `except ... pass` in `test_devvm_solo_build.py:28` und `test_job_worker.py:86` liegt in begrenzten Schleifen; kein Befund.

**Netz und GPU in Tests:** In den gelesenen Dateien nur `127.0.0.1`-Testserver oder Stubs; `host_isolation.py` ersetzt `nvidia-smi`, `lms` und PowerShell. Einzige Verletzung der Regel „kein Netz“: T2 (Server beim Import).

**Die übrigen ~150 Testdateien** (u. a. `test_desk_*`, `test_job_*`, `test_agent_*`, `test_sandbox*`, `test_model_*`) wurden nicht gelesen. Aussagen dazu sind vermutet.

**Vollständiger Testlauf:** nicht ausgeführt. Der Architekturbericht meldete einen Abbruch nach über 10 Minuten; das bleibt unverifiziert (Befund T16 unten).

| ID | Befund | Verbesserung | Aufwand | Priorität |
|---|---|---|---|---|
| T16 | Ein Gesamtlauf aller Tests ist nicht reproduzierbar; Ergebnisse hängen am Zustand des Arbeitsbaums (C5 im Architekturbericht). | Testläufe auf festem Stand (Worktree oder Snapshot-Commit), Commit-Hash protokollieren; schnelle und langsame Tests trennen. | mittel | mittel |

---

## 4. Reihenfolge der Arbeiten mit Abhängigkeiten

Die Reihenfolge richtet sich nach Schwere und Abhängigkeiten. Schritte innerhalb einer Stufe sind unabhängig und können parallel laufen.

**Stufe 0: Bereits im Arbeitsbaum, Commit offen**
- J1 (`talk.mode`), T1 (`chat_kombi`), I1 (Tool-Call-Guard in `router.py`). Vor dem Commit: T5 (tolerant) schärfen, damit I1 abgesichert ist. Die Commits gehören der Partner-Sitzung; diese Prüfung committet nichts.

**Stufe 1: klein, unabhängig, hohe Wirkung**
- F1 (Audit bei Cloud-Aufrufen). Abhängigkeit: keine.
- F2 (Redirect-Handler), F3 (Symlinks), F4 (`cloud_keys.json`). Unabhängig voneinander.
- T3 (SQLite-Teardown in Tests). Unabhängig, aber vor T2, damit echte Fehler sichtbar werden.
- M1 (Canary nur bei aktivem Canary prüfen, Grund in Oberfläche). Unabhängig.
- C1 (Schalter pro Abschnitt, auch `OSError` fangen). Unabhängig.
- B7a, B7b (tote Sicherheitsschlüssel entfernen oder anbinden), B7h (`engine_source`-Standard). Unabhängig, klein; B7h vor dem nächsten Start mit fehlendem Schlüssel.
- A8 (pktmon-Filter bei Fehlstart), A7 (Messskript-Zielordner, vor der nächsten Messung). Unabhängig.

**Stufe 2: Modulschnittstelle (vor großen Umbauten)**
- J2 (`window.sedraApi` nicht global), J3 (Token aus URLs), P3 (Freigaberoute aus Vorlagen und Gateway-Manifest herauslösen), P2 (Allowlist für jeden Aufruf aus Modul). Abhängigkeit: J2 vor J3, P2 nach P3. Das bildet die Grundlage für N2 (iframe/Worker) im Architekturbericht.
- P5 (Gerüst nur `COMMUNITY`). Nach P3.

**Stufe 3: Betriebsfehler sichtbar machen**
- A9 (Befehle ohne Modell), A8 (Befehlsparser), C2 (zentrale Startprobleme). Abhängigkeit: C2 vor A9.
- F5 (Audit-Kette abgeschnitten), F6 (Einmal-Freigaben nach Log), F7 (Guard Pflicht), F12 (Policy-Hash). Unabhängig.

**Stufe 4: Test-Hygiene**
- T2 (Beweis-Test umbenennen, Cloud-Teil entfernen), T5 (I1-Test schärfen), T4 (Stringtests), T6 (AST-Prüfung), T8 und T9 (Hardware-Bedingungen), T13 (Suiten bereitstellen), T16 (fester Stand für Läufe). Abhängigkeit: T3 vor T2.

**Stufe 5: Hub und Laufzeit (mittel)**
- A4 (Hub-Sperre nicht über Modellaufrufen). Abhängigkeit: A9 und J4 (Timeouts) vorher sinnvoll.
- K5 (fsync für Gate- und Modellereignisse; inkrementelle Audit-Prüfung). Nach F5.
- C3 (eine Konfigurationsrangfolge, `doctor` mit Herkunft). Nach C2.

**Stufe 6: groß (Umbau mit Abstimmung)**
- A1/A2/A3 (`uix_server.py` aufteilen, Routen klassifizieren). Nach Stufe 2.
- K1 (Shims ausphasen), K2 (Konstruktor in Komponenten mit Abhängigkeiten).
- V1 (Modulrouten über Registrierung), N2 (Modul-Code in iframe/Worker).

---

## 5. Offene Fragen an den Captain

1. **Cloud-Protokoll (F1):** Soll ein Cloud-Aufruf ohne Logbuch grundsätzlich unmöglich sein (Fehler), oder darf es einen dokumentierten Ausnahmepfad für Verbindungstests geben?
2. **Freigabe-Route (P3):** Soll `POST /api/decisions/answer` aus allen Vorlagen und Gateway-Manifesten gestrichen und als eigene Berechtigung geführt werden? Darf ein Modul je Freigabe-Route einen eigenen Gate-Typ bekommen?
3. **Fremdmodule (J2, P4):** Sollen Fremdmodule nur über iframe oder Worker mit Nachrichtenkanal laufen, oder reicht eine Liste der erlaubten Routen je Modul?
4. **Canary (M1):** Soll der llama-server bei einem ungültigen Canary-Block weiter starten (nur ohne Canary), oder bewusst verweigern?
5. **Schalter (C1):** Sollen gültige Schalterabschnitte angewandt werden, auch wenn ein anderer Abschnitt ungültig ist?
6. **Tool-Call bei Text (I1):** Blockieren oder pseudonymisieren? Der Fix blockiert bei nicht eindeutiger Prüfung; das ist zu bestätigen.
7. **Cloud-Schlüssel (F4, F2):** Soll ein Schlüssel bei Weiterleitung grundsätzlich nicht mitgehen? Soll der Captain einen Pflicht-Test mit Stub-Server festlegen?
8. **Shell-Namen im Kern (V2):** Soll der Kern eine Eigenschaft aus dem Manifest abfragen dürfen?
9. **Architekturversion (K4):** v1.20 als feste Referenz oder die jeweils neueste?
10. **Laufzustand (K6):** Dürfen `modell_zustand.json` und `zuletzt_geladen.json` nach `runtime_data/` umziehen?
11. **Mehrere Sitzungen (C5/T16):** Soll der Captain festlegen, welche Dateien eine Sitzung ändern darf, oder sollen Tests nur auf festem Stand laufen?
12. **Abnahmesuiten (T13):** Wo liegt `workspace/GUPPI_OS/acceptance/suites` außerhalb dieses Worktrees, und soll die Suite ins Repo?

---

## 6. Was verifiziert ist und was nur vermutet

**Verifiziert durch Lauf (in dieser Prüfung):**
- `test_content_guard`: 28 Tests, 1 Fehler (I6, Zeilenenden).
- `test_gateway_wissen`: 14 Fehler, alle beim Aufräumen (W2).
- `test_role_routing`: 79 Tests OK.
- Zählung der Alias-Module: 75 von 117 (K1).
- Schlüsselsuche über alle `runtime/config/*.yaml` gegen Code und Oberfläche (B7a–B7p).
- `sh -n start_sedra.sh` (Syntax), BOM-Analyse per `od`, Dateiexistenz (`runtime/.venv`, `architecture/`, Messordner).
- `runtime.yaml` ohne Referenz im Code; `engine_source`-Standard `lmstudio` (`llama_server_runtime.py:55`).

**Verifiziert durch Lesung (in dieser Prüfung, teils Stichprobe durch mich):**
- I1-Fix in `models/router.py:98-131` und sein tolerantes Test-Gegenstück (T5).
- `talk.mode` in `ui/bus.js:17` und `tools/talk/tool.yaml:20`.
- `window.sedraApi` in `ui/api.js:37`.
- `labor.py:39, :98`, `redesign_prep.py:61` ohne Audit; `core/content_guard.py:275-276`.
- `models/cloud_api.py:107-125`, `redesign_prep.py:63-72`, `cloud_settings.py:58-93`.
- `chat_kombi`/`chat_cloud` in `uix_server.py` (vor Behebung): Ablauf T1.
- `models/gpu_canary.py:60-61` (Prüfung außerhalb von `if self.enabled`).
- `uix_server.py:1575` (Hub-Sperre), `:1571-1573` (`no_model` vor Werkzeugen).
- `gateway/klassen.py:19`, `gateway/wissen.py:307`.

**Vermutet (nicht ausgeführt):**
- F2: Standard-Redirect-Verhalten von `urllib` übernimmt Kopfzeilen (aus Bibliothekskenntnis).
- F8: Ausführung durch fsmonitor oder Filter (aus Git-Kenntnis).
- F13, F15, F16: Race- und Mehr-GPU-Verhalten.
- F17: Entity-Expansion je nach Expat-Version.
- J2: serverseitige Prüfung der Modul-Kennung (nicht gelesen).
- Alle Aussagen zu den nicht gelesenen Testdateien (Abschnitt 3.5).
- Laufzeit- und Größenangaben (Dauer der Hub-Sperre, Kosten der Audit-Prüfung).

**Nicht geprüft:**
- Teile von `desk/`, `agent_manager/`, `jobs/job_supervisor.py` (Abschnitt 3.1).
- `capability_router.yaml` nur per Schlüsselsuche; die Gegenrichtung Code→YAML nicht systematisch (Abschnitt 3.4).
- Startskripte nur gelesen, nie ausgeführt (Abschnitt 3.3); kein Start, kein Build.
- Browser-Ausführung der Oberfläche.
- Vollständiger Testlauf (T16).
- Der Ladevorgang in der Wirklichkeit (kein Modell gestartet).
