# Architektur-Review SEDRA – Stand 19.10.2026

**Art:** reine Analyse. Es wurde kein Code, keine Konfiguration und kein Commit geändert; kein llama-server gestartet, keine GPU-Last erzeugt.
**Prüfstand:** Arbeitsbaum `main` mit laufenden, nicht committeten Änderungen mehrerer Sitzungen (u. a. `uix_server.py`, `runtime.py`, `gateway/vorgang.py`, `gateway/klassen.py`, `gateway/wissen.py`, `models/role_routing.py`, `uix/tools/*`, untracked `tests/test_gateway_ende_zu_ende.py`). Zeilenangaben gelten für den Stand zwischen ca. 11:40 und 11:55 Uhr. Während der Prüfung haben sich Dateien verschoben; ein Testlauf zeigte deshalb zeitweise 20 Fehler, die beim Wiederholen verschwunden waren (siehe Abschnitt 8).

Pfade sind relativ zu `runtime/src/guppi_runtime/` (Kürzel `GR/`), soweit nicht anders angegeben.

---

## 1. Zusammenfassung

SEDRA ist im Kern gut durchdacht: Prüfkette mit Audit-Hash-Kette, Gate-Tokens mit Sperre, Host- und Origin-Prüfung, DPAPI für Schlüssel, fail-closed bei Cloud und ein Inhaltsschutz, der jeden Modellaufruf umschließt. Die Probleme liegen weniger in der Idee als in der Umsetzung. Die fünf wichtigsten Befunde:

1. **Sicherheitslücke im Inhaltsschutz (hoch):** Tool-Call-Argumente werden nicht geprüft, wenn die Modellantwort zusätzlich Text enthält (`GR/models/router.py:106`). Ich habe das mit einem Testaufruf nachgestellt: Ein Schlüssel im Argument kommt unverändert beim Aufrufer an.
2. **Stille Fehler im Modellbetrieb (hoch für den Betrieb):** Ein einziger ungültiger Wert `canary.context` (z. B. 65536) schaltet den ganzen llama-server ab, auch wenn der Canary aus ist (`GR/models/gpu_canary.py:57-58`). Die Oberfläche zeigt dann nur „kein Server“ bzw. „Modellladen nicht verfügbar“, nicht den Grund. Nachgestellt, bestätigt.
3. **Ein Schalter-Fehler macht alle Schalter wirkungslos:** Eine einzige fehlerhafte Zeile in `local_config/switches.yaml` deaktiviert alle Schalter (`GR/runtime.py:284-294`, `GR/local_switches.py`).
4. **Parallelität:** Der Hub-Sperre (`self.lock`) wird während Modellaufrufen gehalten (`GR/uix_server.py:1575` u. a.). Eine laufende Chat-Antwort blockiert dann alle schreibenden Oberflächen-Aktionen.
5. **Strukturschulden:** 75 von 117 Dateien auf der obersten Paketebene sind reine Alias-Shims, `uix_server.py` hat 3.105 Zeilen mit einer Klasse von rund 2.580 Zeilen und etwa 120 Routen, `runtime.py` injiziert ~60 Attribute in einem Konstruktor.

Dazu kommen zwei Wiederholungsfehler, die man sofort beheben kann: der Hash-Test des `b6core` scheitert unter Windows an Zeilenenden, und 14 Tests der Wissensbasis scheitern beim Aufräumen an SQLite-Sperren.

---

## 2. Prüfmethode und Stand der Verifikation

| Kennzeichen | Bedeutung |
|---|---|
| **verifiziert (Lauf)** | Test ausgeführt oder Python-Aufruf mit Ergebnis nachgestellt |
| **verifiziert (Code)** | Stelle im Code gelesen, Ablauf nachvollzogen, aber nicht ausgeführt |
| **vermutet** | Plausibel, aber nicht geprüft (Last, Größenordnung, Vollständigkeit) |

Ausgeführt wurden: der Hash-Test `test_b6core_is_the_delivered_code_hash_for_hash`, die Wissensbasis-Tests `test_gateway_wissen`, die Gateway- und Inhaltsschutz-Tests (86 Tests, 1 Fehlschlag), Python-Aufrufe für `LlamaServerConfig` (canary), `ModelRouter` mit Tool-Calls und `LocalSwitches.load` für die echte Datei. Der volle Testlauf (166 Testdateien) brach nach über 10 Minuten ab; er ist **nicht vollständig verifiziert**.

Zu den Beispielen aus dem Auftrag:

| Beispiel | Ergebnis |
|---|---|
| Canary `context: 65536` schaltet llama-server ab | **verifiziert (Lauf)** – Befund M1 |
| Wissensbasis-Tests scheitern unter Windows an SQLite-Sperren | **verifiziert (Lauf)** – Befund W2 (14 Teardown-Fehler, Testkörper laufen durch) |
| Hash-Test `core/b6core` hängt an Zeilenenden | **verifiziert (Lauf)** – Befund I6 |
| Chat: „lade …“ braucht ein Modell | **verifiziert (Code)** – Befund A9 |

---

## 3. Befunde je Bereich

Aufwand: **klein** (unter einem Tag, lokal), **mittel** (einige Tage, mehrere Dateien), **groß** (Wochen oder Umbau mit Abstimmung).

### 3.1 Kern-Architektur (Start, Abhängigkeiten, Zustand, Audit, Guard)

**K1 – Alias-Shims verdecken die echte Paketstruktur** – *verifiziert (Lauf: Zählung)*
- `GR/*.py`: 117 Dateien auf oberster Ebene, davon **75 Shims** (`sys.modules[__name__] = _module`), z. B. `guard.py`, `audit.py`, `brain.py`, `model_loader.py`, `gpu_canary.py`, `verification_gate.py`.
- Gleichnamige Module existieren doppelt: `registry.py` in `core/` und in `desk/`; `model_runtime.py` in `models/` und `tools/`.
- *Warum problematisch:* Man sieht nicht, welches Modul gemeint ist. `mock.patch`-Ziele sind mehrdeutig, weil ein Shim dieselbe Objektidentität hat, aber ein Patch an anderer Stelle bleibt. Neue Entwickler (und Agenten) importieren den falschen Namen.
- *Verbesserung:* Importe auf die Paketpfade umstellen (die Shims sind als Kompatibilität gedacht und wären mechanisch zu ersetzen), dann die Shims mit Ablaufdatum entfernen. Eine Testregel „keine Shim-Importe in neuem Code“ verhindert den Rückfall.
- *Aufwand:* mittel.

**K2 – `runtime.py` als Abhängigkeitsgraph durch Zeilenreihenfolge** – *verifiziert (Code)*
- `GR/runtime.py:62-160` (`__init__`) erzeugt ~60 Attribute. Abhängigkeiten gelten nur, weil eine Zeile vor der anderen steht: `_configure_job_supervisor` (Z. 135) liest `self.llama_server` (Z. 134) und `self.role_router`; `_configure_llama_server` überschreibt einen bereits registrierten Adapter direkt (`GR/runtime.py:280`, `self.model_router.adapters["llama-cpp-server"] = ...`), statt über `register()` zu gehen (dessen Dublettenprüfung dann umgangen wird).
- Der Konstruktor enthält Import-Anweisungen mitten im Ablauf (z. B. `from .tools.web import ...`, `from .core.content_guard import ContentGuard`).
- *Warum:* Die Reihenfolge ist fragil; eine Änderung an einer Komponente kann die Startreihenfolge einer anderen brechen, ohne dass ein Test das bemerkt. Die Shims (K1) machen die Abhängigkeiten zusätzlich unsichtbar.
- *Verbesserung:* Komponenten in Fabrikfunktionen mit ausdrücklichen Abhängigkeiten (`deps=`) aufteilen, dann topologisch starten; ein Test, der den Startgraphen prüft (keine zyklischen Abhängigkeiten, jede Komponente hat ihren Status). Das Muster `_optional(...)` (`GR/runtime.py:162`) ist ein guter Anfang und sollte überall gelten.
- *Aufwand:* groß.

**K3 – Uneinheitliche Fehlerbehandlung und widersprüchliche Standardwerte** – *verifiziert (Code)*
- Zwei Standardwerte für denselben Schalter: `GR/runtime.py:208` liest `lm_cfg.get("enabled", True)` für den Lader, `GR/runtime.py:352` liest `lm.get("enabled", False)` für LM Studio. Derselbe Eintrag `lm-studio` hat also je nach Aufrufer einen anderen Standard, wenn er in der Datei fehlt.
- Drei Muster nebeneinander: `_optional()` (Z. 162), manuelles `try/except` mit frühem `return` (`_configure_job_supervisor`, Z. 173-185), und einfaches `if … .get(...)`.
- `_configure_context_manager` (Z. 333) liest die Konfiguration aus `job_supervisor.yaml`, nicht aus einer eigenen Datei. Das mag Absicht sein, ist aber nicht dokumentiert.
- *Verbesserung:* Eine Konfigurations-Schnittstelle mit festen Standardwerten je Schlüssel und einem Muster für „aus, mit Grund“. Die Standardwerte stehen dann an einer Stelle.
- *Aufwand:* klein (Standardwerte angleichen), mittel (Muster vereinheitlichen).

**K4 – Architekturordner wird implizit gesucht** – *verifiziert (Code und Lauf-Umgebung)*
- `GR/runtime.py:65-68`: Ohne explizites `architecture_root` sucht die Runtime `project_root.parent / "architecture"` und nimmt die höchste Version. Im Standardlayout (`workspace/GUPPI_OS`) gibt es `workspace/architecture` nicht; die Suche würde mit `FileNotFoundError` scheitern.
- Das Startskript setzt dagegen hart `GUPPI_Architecture_v1.20_SELF_DEVELOPMENT` (`START_SEDRA.bat:15`), während in `architecture/` auch v1.17 liegt. Welche Version gilt, entscheidet also der Aufrufer, nicht die Runtime.
- *Verbesserung:* Architekturpfad nur über Konfiguration oder Umgebungsvariable setzen, Fehler laut melden, und im Startskript dieselbe Auflösung nutzen (oder die Version aus einer Datei lesen). Dann ist klar, welche Regeln gelten.
- *Aufwand:* klein.

**K5 – Audit: keine Dauerhaftigkeit der einzelnen Zeile, Vollprüfung bei jedem Start** – *verifiziert (Code), Größenordnung vermutet*
- `GR/core/audit.py` `_append_locked` schreibt mit `open('a')` ohne `flush`/`fsync`, obwohl `GR/core/util.py` Hilfsfunktionen mit `os.fsync` hat (Z. 38, 49, 61), die hier nicht benutzt werden. Bei einem Stromausfall kann die letzte Zeile fehlen. Die Kette bleibt wegen des `.head`-Files erkennbar, aber das Ereignis ist weg.
- `verify_chain` liest die ganze Datei bei jedem Start (`GR/core/audit.py:92`), und es gibt keine Rotation. Derzeit sind es 112 Zeilen (56 KB); bei langen Läufen wächst das.
- *Verbesserung:* Für kritische Ereignisse (Gate, Freigabe, Modellaufruf) die vorhandene `fsync`-Hilfsfunktion nutzen; `verify_chain` in Intervallen oder inkrementell (ab letztem `.head`) machen; Rotation mit Verweis auf den letzten Abschluss.
- *Aufwand:* klein (fsync), mittel (inkrementelle Prüfung, Rotation).

**K6 – Machine-lokale Zustände liegen im Konfigurationsordner** – *verifiziert (Lauf: Dateiliste)*
- `workspace/GUPPI_OS/local_config/` enthält neben Einstellungen auch Laufzustand: `modell_zustand.json` (9,5 KB) und `zuletzt_geladen.json`. Gleichzeitig enthält der Ordner Schlüssel (`cloud_keys.json`, DPAPI-verschlüsselt).
- *Warum:* Einstellungen und Laufzustand lassen sich nicht sauber sichern, zurücksetzen oder in Berichte übernehmen. Sie sollten getrennt liegen (z. B. `runtime_data/state/`).
- *Aufwand:* klein bis mittel (Pfade umstellen, Migration).

**K7 – Guard-Regeln: starke Vorteile, ein Punkt zur Härtung** – *verifiziert (Code)*
- Positiv: Token werden über eine Sperre (`GR/core/guard.py:38-55`) geschrieben, sind zeitlich begrenzt und werden nach dem Verbrauch nur als Spur gehalten (`TOKEN_KEEP_S`). Das ist solide.
- Die Regeldatei liegt im Architekturordner (`core/guard/guard_rules.yaml`), also außerhalb der Versionierung des Pakets. Wer die Runtime ohne den Architekturordner startet, bekommt einen Fehler, aber keine Warnung über eine veraltete Regelversion.

### 3.2 API und Oberfläche (`uix_server.py`)

**A1 – Datei und Klasse zu groß** – *verifiziert (Lauf: Zeilenzahl)*
- `GR/uix_server.py`: **3.105 Zeilen**. `class UIXHub` (Z. 97) umfasst rund 2.580 Zeilen. `make_server` (Z. 2722-3010) enthält die gesamte HTTP-Logik und die Routentabellen.
- *Warum:* Jede Änderung ist eine Änderung an einer riesigen Datei, Tests sind schwer zu schreiben, und bei parallelen Sitzungen entstehen Konflikte (wie im aktuellen Arbeitsbaum zu sehen).
- *Verbesserung:* Aufteilen in Handler-Module je Fachbereich (Modelle, Gateway, Chat, Cloud, Oberfläche), `make_server` nur für Transport und Authentifizierung. Die Routen-Tabelle als Datenstruktur (Pfad, Methode, Art, Handler).
- *Aufwand:* groß (schrittweise, je Bereich).

**A2 – Routentabellen werden bei jeder Anfrage neu gebaut** – *verifiziert (Code)*
- `GR/uix_server.py:2860` (GET) und `:2919` (POST) bauen das Dict innerhalb der Anfrage neu. Das kostet wenig, zeigt aber, dass es keine klare Routendefinition gibt.
- *Verbesserung:* einmal beim Start aufbauen (Teil von A1).
- *Aufwand:* klein.

**A3 – Die Art einer Route („nur lesen“, „schreibt“, „Gate“) steht nur im Kommentar** – *verifiziert (Code)*
- Die POST-Tabelle (ab `GR/uix_server.py:2919`) mischt Routen mit Kommentaren wie „read-only“ (z. B. `/api/objects`, `/api/project/file`, `/api/diagnose/explain`) und solche, die schreiben. Bei `/api/diagnose/command` steht: „reads; only `/rebind ja` changes the hardware bind“. Das schützt nur, solange niemand die Kommentare ernst nimmt.
- *Warum:* Nichts prüft die Einordnung. Eine Route, die als „read-only“ gilt, aber schreibt, bleibt unbemerkt.
- *Verbesserung:* Jede Route mit einer Klasse (`read`, `write`, `gate`) kennzeichnen; ein Test, der prüft, dass `read`-Routen keine Audit- oder Dateischreibvorgänge auslösen (oder dass sie nur `GET` nutzen).
- *Aufwand:* mittel.

**A4 – Hub-Sperre wird über Modellaufrufe gehalten** – *verifiziert (Code)*
- `GR/uix_server.py:1575`: `chat_reply` hält `with self.lock:` während der gesamten Werkzeugschleife (`run_tool_loop`, Z. 1607). `run_mission` (Z. 1624), `model_test`, `standard_test_start`, `generate_candidate` und mehrere Gate-Routen nehmen dieselbe Sperre.
- *Warum:* Eine Modellantwort dauert Sekunden bis Minuten. Während dieser Zeit warten alle anderen Hub-Operationen mit `self.lock` (Freigaben, Gateway-Prüfung, Einstellungen). Das ist ein Hauptgrund für „Oberfläche hängt“.
- *Verbesserung:* Sperre nur für die Zustandsänderung nehmen, nicht für den Modellaufruf. Für die Chat-Sitzung eine eigene Sperre je Sitzung. Lange Aufrufe über Hintergrund-Jobs mit Status.
- *Aufwand:* mittel. Dauer der Blockade in Sekunden: *vermutet*, nicht gemessen.

**A5 – Authentifizierung und Origin: solide, mit zwei Hinweisen** – *verifiziert (Code)*
- Positiv: Der Token wird pro Start erzeugt (`GR/uix_server.py:2723`) und nur im URL-Fragment übergeben; Host- und Origin-Prüfung (`_same_origin_ok`, Z. 2736) verhindert DNS-Rebinding; Vergleich über `hmac.compare_digest`; Antworten mit `no-store`, `no-referrer`, CSP.
- Hinweis 1: Der Token für `/api/events` darf in der Abfrage stehen (Z. 2748-2750). Begründung steht im Kommentar, und die Verbindung läuft über Loopback. Vertretbar, aber ein kurzlebiges Einmal-Ticket wäre sauberer.
- Hinweis 2: Ohne den Header `X-SEDRA-Tool`/`X-SEDRA-Shell` gilt für einen Aufruf nur der Token (`_module_allowed`). Die Modul-Freigabe greift also nur, wenn der Aufrufer sich ausweist. Das ist die gewollte Trennung, sollte aber im Modul-Handbuch klar stehen.
- *Aufwand:* klein.

**A6 – Fehlerantworten geben interne Ausnahmetexte an den Client** – *verifiziert (Code)*
- `GR/uix_server.py:2908` und `:3010`: Bei jedem unbehandelten Fehler kommen `type(exc).__name__` und `str(exc)` als 503 zurück. Dabei können Pfade und interne Details erscheinen.
- *Verbesserung:* stabile Fehlercodes; Details ins Audit. Auf localhost ist das Risiko klein, aber die Oberfläche soll sich auch unter Fehlern berechenbar verhalten.
- *Aufwand:* klein.

**A7 – Dateianhänge: Geheimnisdatei-Liste ist unvollständig** – *verifiziert (Code)*
- `GR/uix_server.py:1475` (`SECRET_NAMES`) erfasst `.env`, `tokens.json`, `*.pem`, `*.key` usw., aber nicht `cloud_keys.json` (liegt in `workspace/GUPPI_OS/local_config/`). Der Inhalt ist DPAPI-verschlüsselt (`GR/cloud_settings.py:58-69`), das Risiko ist daher gering; die Liste sollte trotzdem den ganzen Ordner `local_config` ausschließen.
- *Aufwand:* klein.

**A8 – Chat-Erkennung über Wortlisten (Teilstring)** – *verifiziert (Code)*
- `GR/uix_server.py:1448` (`CHAT_STATE_WORDS`) und `:1453` (`CHAT_MOVE_WORDS`) werden als Teilstring geprüft (`k in low`, Z. 1592). Jeder Satz, der „lade“, „fenster“, „zeig“, „modell“ oder „gpu“ enthält, zwingt das Modell beim ersten Zug zu `tool_choice: required` (Z. 1597). Beispiel: „geladen“, „Fensterbank“, „zeigen“.
- *Warum:* Das ist unscharf. Der Zwang zu einem Werkzeug kann auch dort greifen, wo keines gebraucht wird, und zugleich kann eine echte Befehlsabsicht ohne Wort aus der Liste durchrutschen.
- *Verbesserung:* Befehle (Verb plus Gegenstand) über einen kleinen deterministischen Parser erkennen, der direkt `list_actions`/`propose_action` aufruft. Die Wortlisten nur für den Zwang zur Werkzeugnutzung bei Fragen nach dem Zustand (Modell, Kontext, Schalter) verwenden, nicht für Befehle.
- *Aufwand:* mittel.

**A9 – „lade …“ ohne Modell: Befehl scheitert, obwohl kein Modell nötig ist** – *verifiziert (Code)*
- `GR/uix_server.py:1573`: `chat_reply` prüft nach den deterministischen Wissenspfaden (GateWay, Arbeitsplatz) als Erstes, ob ein Modell geladen ist. Ist keines geladen, kommt `{'status': 'no_model'}` zurück, **bevor** die Werkzeuge (`open_place`, `list_actions`, `propose_action`) überhaupt angeboten werden. Ein Befehl wie „lade Qwen …“ ist aber ein Auftrag an die Oberfläche, kein Gespräch mit dem Modell.
- *Verbesserung:* Vor dem Modellcheck einen Befehlspfad einschieben, der `list_actions` und `propose_action` ohne Modell auswertet und den Vorschlag als Knopf zeigt. Das Modell nur für freie Sprache verwenden.
- *Aufwand:* klein bis mittel. Ist der Befehlsparser aus A8 vorhanden, ist es klein.

### 3.3 Modelle und Router

**M1 – Ungültiger Canary-Wert schaltet den ganzen llama-server ab, ohne Grund in der Oberfläche** – *verifiziert (Lauf)*
- `GR/models/gpu_canary.py:57-58`: Die Prüfung `if self.context not in (16384, 32768): raise ValueError(...)` steht **außerhalb** von `if self.enabled`. Sie gilt also auch, wenn der Canary aus ist.
- Die `ValueError` läuft durch `LlamaServerConfig` (`GR/models/llama_server_runtime.py:74`) bis `GR/runtime.py:269-282`, wo sie als `llama_server_error` gespeichert wird; `self.llama_server` bleibt `None`.
- Nachstellung (Lauf): `LlamaServerConfig({'enabled': True, 'canary': {'enabled': False, 'context': 65536}})` → `ValueError: llama_server_config_invalid:canary.context`. Mit `32768` läuft es.
- Die Fehlermeldung erscheint nur im Status von `boot()` (`GR/runtime.py:420`, `cli doctor`). `models_view` (`GR/uix_server.py:2320-2341`) zeigt `server: None` ohne Grund. `load_model` (`GR/uix_server.py:2469`) meldet nur `model_loader_unavailable`, obwohl `model_loader_error` gesetzt ist.
- *Warum:* Genau das Muster „Der Lader erscheint als ausgeschaltet“: die Ursache steht an einer Stelle, die die Oberfläche nicht liest.
- *Verbesserung:* (a) Die Canary-Prüfung nur bei aktivem Canary; (b) ungültige Werte im Canary-Block nur für den Canary melden, nicht für den Server; (c) `models_view` und `load_model` geben den Grund aus (`llama_server_error`, `model_loader_error`) als Satz; (d) `cli doctor` als Pflichtcheck vor dem Start.
- *Aufwand:* klein.

**M2 – Adapter wird stillschweigend überschrieben** – *verifiziert (Code)*
- `GR/runtime.py:280`: `self.model_router.adapters["llama-cpp-server"] = LlamaCppServerAdapter(...)` umgeht `register()` (`GR/models/router.py:15-17`), das eine Dublette ablehnt. Die Absicht („statt des generischen 8080“, Kommentar Z. 279) ist klar, aber der Mechanismus versteckt die Änderung.
- *Verbesserung:* Explizit ersetzen (`replace_adapter` mit Audit-Eintrag).
- *Aufwand:* klein.

**M3 – Ohne Provider wird die erste gesunde lokale Option genommen, Reihenfolge ist die Dict-Reihenfolge** – *verifiziert (Code)*
- `GR/models/router.py:29-40` (`choose`): Ohne Angabe eines Providers wird der erste gesunde lokale Adapter in Registrierungsreihenfolge genommen. Diese Reihenfolge ist implizit (LM Studio zuerst, weil `_configure_model_runtimes` vor `_configure_llama_server` läuft). Das Rollen-Routing (`role_routing`) ist standardmäßig aus, daher gilt hier das v1.20-Verhalten.
- *Verbesserung:* Priorität als Zahl in der Konfiguration; ein Test, der die gewählte Option bei gegebenem Zustand festlegt.
- *Aufwand:* mittel.

**M4 – Konfigurierte Modellpfade: zwei Quellen, Pfad aus Textersetzung** – *berichtet, hier nicht nachgestellt*
- `config/llama_server.yaml` setzt `canary.gguf` als `<modelle>\unsloth\Qwen3.5-9B-MTP-GGUF\...` und ersetzt `<modelle>` aus `config/local_paths.yaml` (nicht in git). Eine Schwester-Notiz (`side-session-notes/local_28669cc8-…/ladefehler_canary_2026-10-16.md`) beschreibt einen Fall, in dem `modelle` schon auf `…\lokale-modelle\unsloth` zeigte und der Pfad sich zu `unsloth\unsloth` verdoppelte. In diesem Arbeitsbaum ist `local_paths.yaml` auf `E:\HermesAgentOrdner\lokale-modelle` gesetzt; dort stimmt der Pfad. Ich habe den Fall nicht nachgestellt.
- *Warum:* Die Pfadbildung per Textersetzung ist fragil, und die Pfadprüfung (Pfad vorhanden?) kommt erst beim Start. Der Fehler taucht dann im Ladevorgang auf, nicht bei der Konfiguration.
- *Verbesserung:* Modellordner nur an einer Stelle angeben und den Canary-Pfad relativ zu dieser Stelle schreiben, oder den Pfad beim Speichern der Konfiguration prüfen (existiert die Datei?).
- *Aufwand:* klein.

**M5 – Positiv: Cloud fail-closed, ohne Netzaufruf bei Gesundheitsprüfung** – *verifiziert (Code)*
- `GR/models/cloud_api.py:90-96`: `health()` macht keinen Netzaufruf; Cloud-Adapter starten nur mit Schlüssel und Modell. Netzaufrufe haben einen Timeout (`timeout=60`). `GR/runtime.py:352-360`: Ohne Schalter wird nichts gebaut. Das ist vorbildlich.

### 3.4 Inhaltsschutz und Regelwerk

**I1 – Tool-Call-Argumente werden nicht geprüft, wenn Text mitkommt** – *verifiziert (Lauf)*
- `GR/models/router.py:106`: `complete()` gibt bei vorhandenem Text sofort `content` zurück und prüft die Tool-Calls nicht. Der Guard sieht also nur den Text. Danach setzt `_guarded` `result["content"] = verdict.text` (Z. 116); `result["tool_calls"]` bleibt das Original vom Anbieter (nur bei leerem Text wird es über den Guard zurückübersetzt, Z. 114).
- Nachstellung (Lauf): Ein Anbieter-Stub antwortet mit Text und einem Tool-Call, dessen Argument ein Schlüssel im Format des Tests (`-----BEGIN RSA PRIVATE KEY-----…`) enthält. Ergebnis: Der Aufrufer bekommt den Tool-Call **unverändert**, der Guard meldet `observed: []`, `flags: []`.
- *Warum schwer:* Die Zusage in `_guarded` („auch deren Argumente geprüft“) stimmt nicht. Ein Modell, das in einem Tool-Call einen Schlüssel an ein Werkzeug schickt, wird nicht gestoppt, solange im selben Zug Text steht.
- *Verbesserung:* Den Guard immer über den gesamten Antwortinhalt laufen lassen (Text und `json.dumps(tool_calls)` zusammen), und die Tool-Call-Argumente nach der Prüfung zurückübersetzen. Testfall: Text plus Tool-Call mit Schlüssel → BLOCK oder Pseudonymisierung. Dazu einen Test in `tests/test_content_guard.py`.
- *Aufwand:* klein. Schwere: **hoch** (Zusage gebrochen; praktische Ausnutzung setzt voraus, dass das Modell den Schlüssel selbst in die Antwort schreibt).

**I2 – Zwei Richtlinienversionen für ein System** – *verifiziert (Code)*
- `GR/core/content_policy.py:114`: `POLICY_VERSION = 'sedra-gw-0.1.0-PROPOSED'` (steht im Audit bei jedem `SG_MODEL_CALL`).
- `GR/gateway/klassen.py:17`: `POLICY_VERSION = 'b6-datenregeln-0.1'` (steht in Vorgängen und im Wissensbestand, `gateway/wissen.py:195`), dazu `REGELWERK = 'REGELWERK_DATENKATEGORIEN_CLOUDSPERRE_v0.1_2026-10-15'`.
- *Warum:* Ein Audit-Auszug lässt sich nicht eindeutig einer Regelversion zuordnen. Die Oberfläche zeigt die Versionen aus `klassen`, die Prüfkette schreibt die aus `content_policy`.
- *Verbesserung:* Eine Quelle mit abgeleiteten Namen; im Audit beide Versionen aus derselben Konstante.
- *Aufwand:* klein.

**I3 – Cloud-Sperre bei Personenbezug: zwei Schalter, einer davon nur als Konstante** – *verifiziert (Code)*
- `GR/gateway/klassen.py:19`: `RECHTSGRUNDLAGE_CLOUD = False`. Der Docstring (`klassen.py:8-10`) sagt, sie werde „nur per Registereintrag, nie per Oberfläche“ gesetzt. Im Code liest nichts ein Register; die Änderung ist eine Quelltextänderung.
- Die Prüfkette (`content_policy.py`, `judge`) blockt Personenbezug in der Cloud ohne Bezug auf diese Konstante (`SG_PERSONAL_CLOUD`). Heute ergeben beide dasselbe Ergebnis, aber über zwei Mechanismen.
- *Warum:* Wer die Konstante ändert, ändert die Freigabe im GateWay, nicht die Prüfkette. Die Dokumentation verspricht einen Prozess, den es nicht gibt.
- *Verbesserung:* Die Rechtsgrundlage als Konfiguration mit Nachweisfeld (Stand, Verantwortliche, Datum) und Audit-Eintrag; die Prüfkette liest denselben Wert. Dokumentation anpassen.
- *Aufwand:* mittel. Fachliche Entscheidung beim Captain (siehe Abschnitt 6).

**I4 – Schärfe-Modus fest im Code, Änderung nur über die Oberfläche** – *verifiziert (Code)*
- `GR/runtime.py:121`: `ContentGuard(..., mode='sandbox')`. `set_mode` wird nur aus der Oberfläche aufgerufen (`GR/uix_server.py:178`). Der Modus wird nicht gespeichert: Nach jedem Neustart ist er wieder „sandbox“ (scharf). Das ist sicher, aber die Entscheidung des Captains geht verloren.
- Die Einmal-Erlaubnisse (`once`, `core/content_guard.py:76`) liegen nur im Speicher. Nach einem Neustart sind sie weg; auch das ist sicher.
- *Verbesserung:* Modus in `local_config` (oder Audit) festhalten und beim Start lesen; Einmal-Erlaubnisse nach Ablauf verwerfen, aber sichtbar protokollieren.
- *Aufwand:* klein.

**I5 – Regelwerk als Python-Konstanten** – *verifiziert (Code)*
- `GR/gateway/klassen.py:46` (`REGELN` als Dict mit Rechtsbezug) und die Muster in `content_policy.py` sind Quelltext. Der Docstring sagt: „neue Regeln sind neue Zeilen in REGELN … mit neuer Versionsnummer“. Das ist ehrlich, aber für Fachleute, die die Regeln prüfen, unhandlich.
- *Verbesserung:* Regeln als versionierte Datendatei (YAML oder JSON) mit Schema und Hash, geladen beim Start; Tests gegen die Datei. Die Regeln bleiben damit prüfbar, ohne Quelltext zu lesen.
- *Aufwand:* mittel.

**I6 – Hash-Test des `b6core` scheitert unter Windows an Zeilenenden** – *verifiziert (Lauf)*
- `tests/test_content_guard.py:65-70` vergleicht die SHA-256 über die **rohen Bytes** der Dateien mit `core/b6core/HERKUNFT.sha256`. Die Datei ist im Index als LF gespeichert (`git ls-files --eol`: `i/lf`), die Arbeitskopie ist CRLF (`w/crlf`), weil `core.autocrlf=true` gesetzt ist.
- Nachgerechnet: Die SHA-256 mit LF-Normalisierung stimmt mit `HERKUNFT.sha256` überein (z. B. `names.py`: `27f86b08…`), die rohe Datei hat `90e03acd…`. Der Test schlägt bei `__init__.py` fehl.
- *Verbesserung:* Im Test vor dem Hashen CRLF nach LF normalisieren (`read_bytes().replace(b'\r\n', b'\n')`), oder `.gitattributes` mit `core/b6core/** text eol=lf`. Der Test ist dann unabhängig vom Checkout.
- *Aufwand:* klein. Dies ist ein Schnellgewinn.

**I7 – Das Herkunfts-Hash-Verfahren schützt nur die Dateien, nicht den Einsatzort** – *vermutet*
- Der Hash-Test prüft die sieben Dateien, aber nicht, dass der Einbau in der Laufzeit der gleiche Code ist (Ersetzung zur Laufzeit wäre nicht erkannt). Das ist für einen Herkunftsnachweis in Ordnung, sollte aber im Testnamen klar sein.

### 3.5 MCP und Werkzeuge

**X1 – Zwei MCP-Server, nur einer mit Schutzschicht** – *verifiziert (Code)*
- `GR/state_mcp.py:132-147` prüft Anfrage (`check_request`), Ratenlimit (`rate_ok`), Hinweise (`flags`) und umhüllt den Text (`untrusted`).
- `GR/devvm_mcp.py:79-99` (`_call`) ruft direkt `self.box.call(...)` auf. Keine Ratenbegrenzung außer `max_calls=120` (Z. 38), keine Umhüllung der Rückgabe, keine Hinweis-Erkennung. Die Rückgabe läuft ungeschützt zum Modell.
- Die Dokumentation von `devvm_mcp` (Z. 9) verlangt, dass der Agent seine eigenen Datei- und Shell-Werkzeuge entfernt; das ist eine Vertragspflicht des Clients, nicht erzwungen.
- *Verbesserung:* Die Schutzschicht als gemeinsame Hülle für alle MCP-Server; die Pflicht zur Entfernung der Client-Werkzeuge mit einem Prüfschritt beim Start (der Server erkennt, welche Werkzeuge der Client anbietet, siehe `tools/list`).
- *Aufwand:* klein bis mittel.

**X2 – Hinweise sind nur Hinweise** – *verifiziert (Code)*
- `GR/devenv/mcp_shield.py:25-50` (`flags`) ist eine Liste von Regulären Ausdrücken. Bei Treffern wird nur ein Hinweis vorangestellt (`state_mcp.py:145`), der Text geht trotzdem durch. `untrusted()` markiert den Text mit einer Hülle, die ein Modell ignorieren kann.
- Das ist eine bewusste Entscheidung, sollte aber so dokumentiert sein: Der Schutz beruht auf dem Gehorsam des Modells, nicht auf einer harten Grenze.
- *Verbesserung:* Dokumentation und Tests, die genau das festhalten; Hinweise zusätzlich im Audit zählen, damit man sieht, wie oft sie anschlagen.
- *Aufwand:* klein.

**X3 – Werkzeuge in zwei Schichten mit unterschiedlicher Strenge** – *vermutet*
- `GR/chat_tools.py` (Oberfläche) und `GR/devenv/devvm_tools.py` (Entwicklungs-VM) haben je eine eigene Werkzeugschicht. Pfadprüfungen, Größenlimits und Protokollierung sind dort nicht gleich. Ich habe die Unterschiede nicht vollständig verglichen.
- *Verbesserung:* gemeinsame Basisklasse für Pfad- und Größenprüfung und für Protokoll.
- *Aufwand:* mittel.

### 3.6 Workflows, Module und Agenten

**W1 – Modul-Freigabe: gute Idee, Lücke ohne Kennzeichen** – *verifiziert (Code)*
- Positiv: Die Freigabe nach Modul (`X-SEDRA-Tool`/`X-SEDRA-Shell`, `GR/uix_server.py:2751-2762`) begrenzt Routen je Manifest (`hub.gateway.allowed`). Abgelehnte Aufrufe werden auditiert (`UIX_TOOL_DENIED`).
- Lücke: Der Header ist eine Behauptung des Aufrufers. Ein Modul, das ihn weglässt, hat dieselben Rechte wie die Hauptseite. Das ist wohl gewollt („die Seite selbst“), aber nirgends als Regel festgehalten.
- *Verbesserung:* Die Regel in die Modul-Dokumentation; Oberflächenaufrufe ohne Header nur über eine Liste zulassen, die im Manifest steht.
- *Aufwand:* klein bis mittel.

**W2 – SQLite-Verbindungen werden nie geschlossen; Windows sperrt die Datei** – *verifiziert (Lauf)*
- `GR/gateway/wissen.py:164`, `GR/arbeitsumfeld_wissen.py:91`, `GR/desk/arbeitsplatz.py:207`: `sqlite3.connect(..., check_same_thread=False)` ohne `close()` und ohne Kontext. Ebenso `GR/agent_manager/agent_registry.py:8` und `GR/agent_manager/bridge.py:51`.
- Lauf: `python -m unittest test_gateway_wissen` → **14 Fehler**, alle `PermissionError: [WinError 32]` beim Aufräumen des Temp-Ordners. Die Testkörper laufen durch (keine Fehlschläge), nur das Löschen scheitert.
- *Warum:* Unter Windows kann eine geöffnete Datei nicht gelöscht werden. Das betrifft auch Betrieb (Datei-Ersetzung, Sicherung).
- *Verbesserung:* Verbindungen in den Lebenszyklus der Komponente legen (`close()` in `shutdown`), Tests mit `tearDown` → `db.close()`. Mittelfristig eine gemeinsame Hilfsklasse für SQLite-Speicher.
- *Aufwand:* klein (Test-Teardown), mittel (Lebenszyklus).

**W3 – Große Module** – *verifiziert (Lauf: Zeilenzahl)*
- `GR/jobs/job_supervisor.py` 1.382 Zeilen; `GR/jobs/context_manager.py` 828; `GR/devenv/devvm_agents.py` 713; `GR/models/role_routing.py` 602; `GR/devenv/devvm_tools.py` 574; `GR/gateway/vorgang.py` 526.
- Die Größe allein ist kein Fehler. Gefährlich ist sie, wenn Zustand, Richtlinie und Ausführung in einer Datei stehen. Das trifft `job_supervisor.py` (Zustand, Gates, Ressourcen und Modellwahl zugleich).
- *Verbesserung:* Bei den nächsten Änderungen entlang der Verantwortung schneiden.
- *Aufwand:* mittel, je Datei.

**W4 – Registrierung: mehrere Ebenen, nicht vollständig geprüft** – *vermutet*
- Module werden über `tool.yaml`/`shell.yaml` (37 Dateien unter `uix/`) und über `core/registry.py` (liest den Architekturordner) und `desk/registry.py` gefunden. Ob jede Manifestdatei in genau einer Ebene erfasst wird und ob Abweichungen auffallen, habe ich nicht vollständig geprüft.
- *Verbesserung:* Ein Prüfbefehl (`doctor`), der Manifeste, Routen und Registrierung gegeneinander abgleicht.
- *Aufwand:* mittel.

### 3.7 Konfiguration und Betrieb

**C1 – Eine fehlerhafte Schalterdatei schaltet alle Schalter ab** – *verifiziert (Code)*
- `GR/local_switches.py`: Jeder Fehler (unbekannter Abschnitt, Nicht-Bool-Wert) wirft `ValueError`. `GR/runtime.py:284-294` (`_load_switches`) setzt dann `LocalSwitches()` (leer), und **kein** Schalter wird angewandt. Es gibt einen Audit-Eintrag `LOCAL_SWITCHES_REFUSED` und einen Fehlertext im `boot()`-Status.
- Die echte Datei `workspace/GUPPI_OS/local_config/switches.yaml` lädt gültig (Lauf: `{'model_loader': {'enabled': True}, 'llama_server': {'enabled': True, 'mtp': False}}`). Ein einziger Tippfehler darin hätte beides abgeschaltet.
- *Warum:* Das Prinzip „nicht halb anwenden“ ist richtig, aber es trifft den Captain als Ganzes und macht den Fehler unsichtbar (nur Audit und `boot`).
- *Verbesserung:* Jeden Abschnitt einzeln prüfen; gültige anwenden, ungültige einzeln melden; Ergebnis auch in der Oberfläche anzeigen.
- *Aufwand:* klein bis mittel.

**C2 – Fehler erscheinen nur im JSON des Starts** – *verifiziert (Code)*
- Viele `*_error`-Felder (`llama_server_error`, `model_loader_error`, `routing_error`, `cloud_providers_error`, `switches_error`, `token_policy_error`) werden nur in `boot()` ausgegeben (`GR/runtime.py:385-420`) und in einzelnen Ansichten. Die Oberfläche hat keine zentrale Stelle „Startprobleme“.
- *Verbesserung:* Eine Liste aller Startprobleme mit Schweregrad, sichtbar im Desk (beim Start und in der Werkstatt). `cli doctor` benutzt dieselbe Liste.
- *Aufwand:* mittel.

**C3 – Lokale Einstellungen an drei Orten** – *verifiziert (Lauf: Dateiliste)*
- `runtime/config/*.yaml` (Standards, Teil des Pakets), `runtime/config/local_paths.yaml` (machine-lokal, in `.gitignore`), `workspace/GUPPI_OS/local_config/*` (Schalter, Cloud, Routing, Oberfläche, Laufzustand) und `workspace/GUPPI_OS/runtime_data/` (Daten).
- Die Rangfolge ist im Code verteilt (z. B. Cloud: `local_config` vor `config/`, `GR/runtime.py:363`).
- *Warum:* Niemand kann auf einen Blick sagen, welcher Wert gilt. Ein Fehler wie M4 bleibt deshalb lange unbemerkt.
- *Verbesserung:* Eine Rangfolge (Standard → Paket-Konfiguration → Maschine → Sitzung), und ein `doctor`-Befehl, der die **wirksame** Konfiguration mit Herkunft je Wert ausgibt.
- *Aufwand:* mittel.

**C4 – Byte-Order-Mark und Editoren** – *verifiziert (Lauf)*
- `config/local_paths.yaml`, `workspace/GUPPI_OS/local_config/switches.yaml` beginnen mit UTF-8-BOM. PyYAML verarbeitet das (Lauf ok). Bei anderen Lesern (z. B. `json`-Lesern oder Skripten mit `encoding='utf-8'`) kann es dagegen zu Fehlern kommen. Kein akuter Fehler, aber eine Stolperstelle.
- *Verbesserung:* Schreibende Stellen ohne BOM; einheitlich UTF-8 ohne BOM.
- *Aufwand:* klein.

**C5 – Testlauf nicht reproduzierbar während laufender Änderungen** – *verifiziert (Lauf)*
- Während der Prüfung änderten sich `gateway/vorgang.py` (SEP-Konstante wurde verschoben) und `uix_server.py`. Ein Lauf meldete 20 Fehler (`NameError: name 'SEP' is not defined`, Gateway-Tests); beim Wiederholen wenige Minuten später bestanden sie alle (86 Tests, nur der Hash-Test scheitert).
- *Warum:* Die Ergebnisse sind nur gültig für den Moment, in dem sie laufen. Mehrere Sitzungen im selben Ordner machen das Verhältnis Test-Ergebnis zu Code unscharf.
- *Verbesserung:* Testläufe auf einem festen Stand (ein `git worktree` oder ein Snapshot-Commit) und Ergebnis mit Commit-Hash protokollieren.
- *Aufwand:* klein (Prozess), mittel (Automatisierung).
- *Zusatz:* Die Standard-Testskripte (`run_tests.sh`, `run_tests.bat`) setzen eine `.venv` voraus, die in diesem Arbeitsbaum nicht existiert. Ich habe mit dem System-Python 3.13 und `PYTHONPATH=src:tests` getestet.

**C6 – Vollständiger Testlauf nicht abgeschlossen** – *verifiziert (Lauf)*
- 166 Testdateien; der Lauf brach nach über 10 Minuten ab, ohne Zusammenfassung. Ein Teil lief durch (u. a. Agenten-Tests mit `ResourceWarning` für nicht geschlossene Dateien in `test_agent_devvm_runtime.py:47-48`, Socket-Warnung in `unittest/case.py`).
- *Verbesserung:* Tests nach Laufzeit aufteilen (schnelle Unit-Tests, langsame Server-Tests getrennt), und Ressourcen in Tests schließen (`with open(...)`).
- *Aufwand:* mittel.

---

## 4. Was gut ist (und bleiben soll)

- **Audit-Kette mit Kopfdatei** (`GR/core/audit.py`): Ketten-Hash, Kopfdatei gegen abgeschnittene Logs, Redaktion sensibler Schlüssel, Reparatur einer abgebrochenen letzten Zeile ohne Verlust der übrigen Kette.
- **Gate-Tokens** (`GR/core/guard.py:38-55`): Sperre über alle Schreibvorgänge, Ablaufzeit, Verbrauch einmal, Ablage als Spur.
- **Inhaltsschutz als Pflichtstrecke** für jeden Modellaufruf (`GR/models/router.py:75`), mit Bindung (`binding_hash`) und getrennter Prüfung von Text und Tool-Argumenten bei leerem Text (Ausnahme: I1).
- **Cloud fail-closed**: kein Cloud-Adapter ohne Schalter, Schlüssel nur per DPAPI, kein Umschalten auf Cloud ohne ausdrücklichen Aufruf (`GR/models/router.py:37-38`).
- **Host- und Origin-Prüfung** gegen DNS-Rebinding und CSRF (`GR/uix_server.py:2736`).
- **Lokale Schalter nie halb angewandt** (Prinzip richtig, Umsetzung zu grob, siehe C1).
- **Zeitbegrenzte Dateizugriffe** im Chat (`chat_attach`, 12 KB, Tiefe 4, 150 Einträge) und Ablehnung von Geheimnisdateien.

---

## 5. Priorisierte Reihenfolge

Die Reihenfolge richtet sich nach Schwere mal Aufwand. Schritte 1–4 sind sofort machbar und klein.

| # | Befund | Warum jetzt | Aufwand |
|---|---|---|---|
| 1 | **I1** Tool-Call-Guard bei Text + Tool-Call | Gebrochene Sicherheitszusage; Testfall liegt vor | klein |
| 2 | **M1 / M2** Canary-Validierung, Grund in Oberfläche, Adapter-Überschreiben | Betriebsfehler mit falscher Anzeige; Nachstellung liegt vor | klein |
| 3 | **I6** Hash-Test Zeilenenden | Schnellgewinn, verhindert Fehlalarm | klein |
| 4 | **W2** SQLite-Teardown im Test | Schnellgewinn; verdeckt echte Fehler in der Suite | klein |
| 5 | **C1** Schalter pro Abschnitt | Ein Tippfehler schaltet alles ab | klein–mittel |
| 6 | **A9 / A8** „lade …“ ohne Modell, Befehlsparser | Direkt sichtbar für den Captain | klein–mittel |
| 7 | **A4** Hub-Sperre über Modellaufrufen lösen | Oberfläche hängt bei Chat-Antworten | mittel |
| 8 | **C2** zentrale Startprobleme | Fehler werden erst im JSON sichtbar | mittel |
| 9 | **X1** Schutzschicht für `devvm_mcp` | Asymmetrie zwischen den beiden MCP-Servern | klein–mittel |
| 10 | **I2 / I3** eine Richtlinienversion, Rechtsgrundlage als Konfiguration | Nachweisbarkeit; Entscheidung beim Captain | klein / mittel |
| 11 | **K5** fsync für Gate- und Modellereignisse, Prüfung inkrementell | Verlust einzelner Ereignisse bei Absturz | klein–mittel |
| 12 | **K1** Shims ausphasen | Import- und Patch-Verwirrung | mittel |
| 13 | **A1 / A2 / A3** `uix_server.py` aufteilen, Routen klassifizieren | Wartbarkeit, Routenprüfung | groß |
| 14 | **K2** Konstruktor in Komponenten mit Abhängigkeiten | Startfehler durch Reihenfolge | groß |
| 15 | **C3** eine Konfigurationsrangfolge, `doctor` mit Herkunft | Konfigurationsfehler bleiben unsichtbar | mittel |

---

## 6. Offene Fragen an den Captain

1. **Rechtsgrundlage Cloud (I3):** Bleibt die Entscheidung „Personenbezug nur lokal“ bis zur Rechtsprüfung so? Wer setzt `RECHTSGRUNDLAGE_CLOUD` später, und soll das ein Eintrag mit Datum und Verantwortlichen sein?
2. **Tool-Call bei Text (I1):** Soll eine Antwort mit Schlüssel im Tool-Argument blockiert werden (BLOCK) oder pseudonymisiert und zurückübersetzt? Das Verhalten bei leerem Text ist bereits pseudonymisierend.
3. **Befehle ohne Modell (A9):** Soll „lade …“ (und ähnliche Befehle) immer ohne Modell als Vorschlag laufen, auch wenn ein Modell geladen ist? Oder nur, wenn kein Modell geladen ist?
4. **Hub-Sperre (A4):** Ist es akzeptabel, dass Freigaben während einer laufenden Chat-Antwort warten müssen, bis die Sperre neu vergeben wird? Oder soll die Chat-Antwort ihre eigene Sitzung haben?
5. **Canary-Verhalten (M1):** Soll der llama-server bei einem ungültigen Canary-Block weiter starten (nur ohne Canary) oder bewusst verweigern? Die Antwort bestimmt, ob Fehler „laut“ oder „nur sichtbar“ sein sollen.
6. **Architekturversion (K4):** Ist v1.20 die feste Referenz (Startskript) oder die jeweils neueste Version (Runtime)?
7. **Laufzustand (K6):** Dürfen `modell_zustand.json` und `zuletzt_geladen.json` aus `local_config/` nach `runtime_data/` umziehen?
8. **Mehrere Sitzungen im selben Ordner (C5):** Soll der Captain festlegen, welche Dateien eine Sitzung ändern darf, oder sollen Tests nur auf einem festen Stand laufen?

---

## 7. Was ich nicht geprüft habe

- Frontend-Logik im Browser (`uix/js`, `uix/tools/*/tool.js`) außer den Routen, die sie aufrufen. Der Chat-Pfad im Browser könnte das Verhalten in A8/A9 noch verändern.
- Der Ladevorgang in der Wirklichkeit (kein Modell gestartet, keine GPU-Last, kein llama-server). M1 ist über Konfigurationsobjekte nachgestellt, nicht über einen echten Start.
- Die vollständige Testsuite (siehe C6).
- Die Schwester-Fehlerbeschreibung zum Ladefehler (M4) wurde nicht nachgestellt; ich habe sie nur als Hinweis übernommen.
- Die Einzelheiten von `jobs/job_supervisor.py`, `agent_manager/` und `devenv/` außer den genannten Stellen.
- Leistungswerte (Dauer der Sperre in A4, Größenordnung der Audit-Prüfung in K5): *vermutet*.

---

## 8. Anhang: Ausgeführte Prüfungen

| Prüfung | Ergebnis |
|---|---|
| `python -m unittest test_content_guard.S1_Kern.test_b6core_is_the_delivered_code_hash_for_hash` | FAIL (I6) |
| `python -m unittest test_gateway_wissen` | FAILED (errors=14), alle WinError 32 beim Aufräumen (W2) |
| `python -m unittest test_content_guard test_gateway test_core_boundary_src test_gateway_ende_zu_ende` | 86 Tests, 1 Fehlschlag (I6). Ein früherer Lauf mit 20 `NameError` war durch laufende Änderungen bedingt (C5) |
| `LlamaServerConfig` mit `canary.context: 65536` und `enabled: false` | ValueError (M1). Mit 32768 OK |
| `ModelRouter` mit Stub-Anbieter (Text + Tool-Call mit Schlüssel) | Tool-Call unverändert durchgereicht, `observed: []` (I1) |
| `LocalSwitches.load` auf `workspace/GUPPI_OS/local_config/switches.yaml` | OK |
| Zählung der Alias-Module auf oberster Ebene | 75 von 117 (K1) |
| `git ls-files --eol` für `core/b6core/names.py` | `i/lf w/crlf` (I6) |
| Gesamtlauf aller Tests | nicht abgeschlossen (C6) |

---

## 9. Nachtrag: Verbindung Kern – Shells – Module (Vertrag, Trust, Allowlist)

Auftrag aus einer Schwester-Sitzung (Ergänzung des Nutzers): Wo berühren Shells den Kern, welche Grenzen greifen wirklich, welche stehen nur auf dem Papier. Geprüft: `desk/gateway.py`, `desk/install.py`, `desk/registry.py`, `uix_server.py` (Modul-Routen, Gate-Routen, Vorlagen), `uix/ui/api.js`, `uix/ui/loader.js`, `uix/js/core.js`, alle `tool.yaml`/`shell.yaml` unter `uix/` (35 Manifeste mit `api`-Liste). Ein Skript hat die Routenliste der Manifeste mit der Routentabelle des Servers verglichen (Lauf).

Die Trust-Stufen `CORE`, `CAPTAIN`, `GUPPI_BUILT`, `COMMUNITY` sind im Code nur **zwei** Stufen: `COMMUNITY` (Leserouten, Installation über Gate) und alle anderen. Die Grenze „Allowlist je Modul“ greift nur, wenn der Aufrufer den Modul-Header schickt, und ein Modul kann diesen Header fälschen. Das ist für Fremdcode nicht durch eine Grenze gesichert, sondern durch Konvention und Prüfhinweise.

### 9.1 Was greift wirklich

**S1 – Installation fremder Module über Gate, Hash-Bindung: greift** – *verifiziert (Code)*
- `uix_server.py:270-300` (`install_request`): Manifest, Dateien mit SHA-256, Gate. `install_apply` (Z. 306-355) prüft jede Datei vor und nach dem Kopieren gegen den Hash und schreibt das Manifest auf `COMMUNITY` (Z. 348), bevor es an seinen Platz rückt. Eine Hochstufung über die Manifest-Angabe wird also abgefangen.
- Lokale Module können nie `CORE` sein: `desk/gateway.py:94`.
- Positiv auch: lokale Module verdrängen nie Paketmodule gleicher Kennung (`desk/registry.py:186-187`, `duplicate_id`).

**S2 – Vorlagen-Shells („Vorgabe“) sind Daten, kein Code: greift** – *verifiziert (Code)*
- `desk/gateway.py:192-240` (`read_vorgabe`, `_check_frame_shell`): Schema-Prüfung, kein `entry`, keine eigenen Routen, Slots und API-Liste kommen vom Rahmen (`FRAME_API`, Z. 48), der Rahmen liegt in `ui/`. Das ist die stärkste Grenze im System.

**S3 – Schreibrechte fremder Module nur mit Captain-Gate, Hash-Bindung: greift** – *verifiziert (Code)*
- `uix_server.py:872-935` (`trust_request`/`trust_apply`): Nur `COMMUNITY` mit `origin == local` darf die Hochstufung beantragen (Z. 880-884); die Freigabe prüft den Manifest-Hash (Z. 920-925).

**S4 – Kern importiert nichts aus Shells: greift** – *verifiziert (Code)*
- Keine Importe von `desk/` oder `uix` in `core/`, `jobs/`, `models/`, `runtime.py`, `tools/`, `modules/`. Die Richtung „Kern kennt Oberfläche nicht“ stimmt.

### 9.2 Wo die Grenze nur auf dem Papier steht

**P1 – Trust-Stufen haben außer COMMUNITY keine Wirkung** – *verifiziert (Code, Lauf)*
- `desk/gateway.py:31` definiert `TRUST`. Gelesen wird der Wert nur an zwei Stellen: `desk/gateway.py:116` (COMMUNITY: nur GET-Routen) und `uix_server.py:882` (Hochstufung nur aus COMMUNITY). `CORE`, `CAPTAIN` und `GUPPI_BUILT` ändern weder Routen, Laden, Gate noch Anzeige in der Runtime.
- Alle 35 ausgelieferten Manifeste tragen `trust: CORE` (35) oder `CAPTAIN` (2); `GUPPI_BUILT` steht in keinem Manifest, nur in einem Kommentar.
- Der Trust-Wert ist eine Zeichenkette in der Datei. Beim Laden wird er nicht gegen Herkunft oder Hash geprüft (`desk/gateway.py:91-94`). Wer eine lokale `tool.yaml` von Hand auf `CAPTAIN` setzt, bekommt Schreibrouten ohne Gate. Die Sperre liegt nur bei der Installation und bei der Hochstufung über die Oberfläche.
- *Schwere:* mittel. *Verbesserung:* Trust aus der Herkunft ableiten (Paket → `CORE`, lokal → `COMMUNITY` bis Gate), nicht aus der Datei; `GUPPI_BUILT` entweder definieren oder streichen; beim Laden den Hash gegen den Gate-Stand prüfen. *Aufwand:* mittel.

**P2 – Modul-Allowlist greift nur bei Header** – *verifiziert (Code, Lauf)*
- `uix_server.py:2751-2762` (`_module_allowed`) prüft nur, wenn `X-SEDRA-Tool` oder `X-SEDRA-Shell` gesetzt ist. Ohne Header gilt nur der Token. Die Seite selbst schickt keinen Header (gewollt, siehe Kommentar Z. 2752).
- Lauf: 73 Pfade stehen in Manifesten; **42 von 119** Server-Routen stehen in keinem Manifest. Darunter sind die schreibenden Kernrouten `/api/mission/run`, `/api/mission/approve`, `/api/mission/reject`, `/api/switch/apply`, `/api/process/stop`, `/api/routing-config/apply`, `/api/model/add/apply`, `/api/job/cancel`. Gegen ein Modul mit Header sind sie gesperrt; mit einem Aufruf nur mit Token nicht.
- *Schwere:* hoch, sobald P3 oder P4 eintritt. *Verbesserung:* Die Allowlist nicht nur am Header festmachen, sondern jeden Aufruf aus einem Modul ablehnen, der nicht gelistet ist (Scope im Token oder eigener Schlüssel je Modul); die Seite selbst über eine eigene Liste.

**P3 – `POST /api/decisions/answer` ist eine Tür für Freigabe und Anwendung** – *verifiziert (Code)*
- `uix_server.py:194-232` (`decide`): Eine Antwort auf eine Entscheidung ruft `approve_gate` auf und bei `freigeben_und_anwenden` die Anwendung der Gate-Art (Schalter, Routing, Modell hinzufügen, Bibliothek, Grenzen, Installation, Hochstufung, Gateway). Die Route ist damit kein Lesezugriff und kein einzelnes Verb, sondern Freigabe plus Ausführung über eine Route.
- Erlaubt wird sie in: `uix/tools/gateway/tool.yaml:22`, `uix/tools/decisions/tool.yaml:12`, `uix/tools/schutz/tool.yaml:14`, `uix/shells/cockpit/shell.yaml:14`, `minimal/shell.yaml:15`, `paperclip/shell.yaml:15`, `start/shell.yaml:18`, `_template/shell.yaml:13` und **allen Vorgabe-Shells** über `FRAME_API` (`desk/gateway.py:48`).
- Die Kette: Eine Hochstufung (S3) kann ein Modul mit dieser Route beantragen. Der Captain sieht im Gate „darf schreiben: POST /api/decisions/answer“ (`uix_server.py:883-889`, nur die Routenliste), aber nicht, dass damit jede wartende Freigabe und jede Installation erreichbar wird.
- *Schwere:* hoch. *Verbesserung:* Freigabe und Anwendung als eigene Berechtigungen mit eigenem Gate-Typ; `decisions/answer` aus `FRAME_API` und `_template` streichen; der Hochstufungstext nennt die Wirkung im Klartext („kann Freigaben erteilen“). *Aufwand:* mittel.

**P4 – Die Modul-Schnittstelle lässt sich vom Modul selbst umgehen** – *verifiziert (Code, nicht im Browser ausgeführt)*
- `uix/ui/api.js:37`: `window.sedraApi = {token: TOKEN, call, forModule, api}`. `call(path, options, module)` (Z. 17) nimmt **jede** Modul-Kennung. Ein Werkzeug kann sich also als Shell `cockpit` ausgeben und deren Allowlist nutzen, oder mit `sedraApi.token` ohne Header direkt schreiben.
- Der Token steht zusätzlich im URL-Fragment (`location.hash`), das jedes Skript der Seite lesen kann. Im Retro-Desktop (`/retro`, `uix/js/core.js:4,7`) ist `API_TOKEN` eine globale Konstante, dort ohne Modul-Header.
- Die Prüfung beim Einbau (`desk/install.py:26-37`) meldet `fetch`, `XMLHttpRequest`, `eval`, `import()`, `localStorage`, `innerHTML` und fremde Adressen. Nicht gemeldet werden `sedraApi`, `location.hash`, `X-GUPPI-Token` und Zugriffe über `window[...]`. Der Kopf von `desk/gateway.py:1-12` („Honest limit“) sagt das selbst; in der Oberfläche steht es nicht.
- *Schwere:* hoch für Fremdmodule, mittel für eigene. *Verbesserung:* Modul-Code in einen eigenen Ausführungsbereich (iframe mit eigenem Origin oder Worker) mit Nachrichtenkanal statt geteiltem Fenster; Token nicht im Fragment lassen und nicht global exponieren; `sedraApi.call` nur mit dem Modul der Ladeumgebung.

**P5 – Gerüst-Vorlage gibt ohne Gate `CAPTAIN` und die Freigaberoute** – *verifiziert (Code)*
- `uix_server.py:474-512` (`module_scaffold`): „Kein Gate: der Inhalt ist unsere eigene Vorlage“. Die Kopie erhält `trust: CAPTAIN` (Z. 512). Die Vorlage `uix/shells/_template/shell.yaml:8-15` enthält `POST /api/decisions/answer` und ist selbst `CAPTAIN`. Eine neu erzeugte Shell hat damit P3 ohne Gate.
- *Schwere:* mittel. *Verbesserung:* Gerüste mit `COMMUNITY` anlegen; Freigaberouten aus der Vorlage entfernen.

**P6 – Der Einbau-Prüfer ist nur ein Hinweis** – *verifiziert (Code)*
- `desk/install.py:1-22` („Ein Fund ist kein Urteil“): Findungen gehen in den Gate-Text (`uix_server.py:291`), blockieren aber nichts. Die Erkennung ist eine Reihe Regulärer Ausdrücke (`desk/install.py:26-37`) und lässt sich mit Umformung umgehen (z. B. Funktionsaufrufe über zusammengesetzte Namen). Das ist als Hinweis für den Captain gedacht, nicht als Grenze; die Oberfläche sollte es so sagen.
- *Verbesserung:* Fremde Module mit Findungen gar nicht einbauen, oder die Findungen als Pflichtbestätigung in Klartext zeigen.

**P7 – Routenprüfung bei jedem Aufruf neu** – *verifiziert (Code), Kosten vermutet*
- `desk/gateway.py:256` (`_load`) liest und prüft alle Manifeste; `allowed()` (Z. 337) und `file()` (Z. 311) rufen `_load` bei jeder Anfrage auf. Das ist korrekt (keine veraltete Liste), aber teuer, und Dateien können sich zwischen Prüfung und Auslieferung ändern.
- *Verbesserung:* Manifeste beim Start oder bei Änderung (Hash) laden und die Liste cachen.

### 9.3 Kern und Shell: wo die Grenze fehlt

**V1 – Die Hub-Klasse kennt die Shells und ihre Werkzeuge** – *verifiziert (Code)*
- `uix_server.py` enthält die Handler für das GateWay (`gateway_*`, Z. 630–870, rund 250 Zeilen), Labor, Vorarbeiter, Bibliothek und Modell-Werkstatt; die Routen heißen nach Werkzeugen (`/api/gateway/*` mit 14 Routen, `/api/labor/*`, `/api/entwurf/*`, `/api/library/*`). Ein neues Modul mit eigener Route braucht eine Änderung an `uix_server.py`.
- Das GateWay selbst liegt als Kernpaket (`gateway/`), seine Oberfläche als Werkzeug (`uix/tools/gateway`). Die Logik sitzt also im Kern, die Anzeige im Modul, und die Verbindung ist fest verdrahtet (`uix_server.py:1551-1556` ruft `GatewayWissen` direkt aus dem Chat auf).
- *Schwere:* mittel (Erweiterbarkeit und Prüfbarkeit). *Verbesserung:* Modul-Routen über eine Registrierung des Moduls (Handler im Modulpaket, Kern nur als Vertrag); GateWay-Logik als Dienst mit eigener Schnittstelle, die der Hub nur über den Vertrag aufruft. *Aufwand:* groß.

**V2 – Der Kern kennt einen Shell-Namen** – *verifiziert (Code)*
- `gateway/wissen.py:307`: `if aktive_shell == 'gateway-studio' and …` ändert das Verhalten der Wissensbasis je nach Shell. Ein Shell-Name im Kern verletzt die Trennung. *Verbesserung:* Die Shell meldet ihre Eigenschaft im Manifest (z. B. `provides`), der Kern fragt die Eigenschaft ab. *Aufwand:* klein.

**V3 – Schreibschutz der lokalen Module nur über das Dateisystem** – *vermutet*
- Lokale Module liegen unter `local_config/`, das auch Schalter, Schlüssel (DPAPI) und Laufzustand enthält (siehe K6). Wer dort schreiben kann, kann ein Modul auf `CAPTAIN` setzen (P1). Ob das eine Grenze sein soll, ist eine Frage der Betriebsumgebung; der Bericht sieht hier keinen technischen Schutz.

### 9.4 Nachtrag zur Prioritätenliste

| # | Befund | Aufwand |
|---|---|---|
| N1 | **P3** `decisions/answer` aus `FRAME_API`, `_template` und Gateway-Manifest herauslösen; Freigabe als eigene Berechtigung | mittel |
| N2 | **P4** `window.sedraApi` nicht global und nicht frei adressierbar; Token nicht im Fragment; Modul-Code isolieren (iframe/Worker) | groß |
| N3 | **P2** Allowlist für jeden Aufruf aus einem Modul (nicht nur bei Header); 42 ungelistete Routen bewerten | mittel |
| N4 | **P1** Trust aus der Herkunft ableiten, `GUPPI_BUILT` klären, Hash beim Laden prüfen | mittel |
| N5 | **P5** Gerüst ohne Gate nur als `COMMUNITY` und ohne Freigaberouten | klein |
| N6 | **P6** Einbau-Findungen als Pflichtbestätigung in Klartext | klein |
| N7 | **V2** Shell-Name aus `gateway/wissen.py:307` entfernen | klein |
| N8 | **V1** Modul-Routen über Modulregistrierung, GateWay als Dienst | groß |

Diese Befunde ergänzen die Reihenfolge in Abschnitt 5; N1–N3 gehören vor die großen Umbauten.

**Offene Fragen an den Captain (zusätzlich zu Abschnitt 6):** Soll eine Hochstufung zu `CAPTAIN` (Schreibrechte fremder Module) künftig ausdrücklich nennen, welche Freigaben das Modul dann selbst erteilen kann? Und darf ein Modul je Freigabe-Route einen eigenen Gate-Typ bekommen?

**Nicht geprüft:** Die Browser-Ausführung von P4 (nur Lesen des Codes, kein Test im Browser). Die Ausführung der Shell-Oberfläche selbst. Die Kosten aus P7.
