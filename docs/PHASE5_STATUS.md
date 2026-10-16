# PHASE5_STATUS – Routing, Provider Health, unabhängiger Verifier

Stand: 2026-10-01 · Testumgebung: Windows 11, Python 3.14.7. **Keine Modelle, kein Zielgerät, kein echter Provider.**

**Ergebnis:** `python -m unittest discover -s tests` → **664 Tests, 0 Fehler, 5 übersprungen** (die 5 sind Symlink-Tests, siehe PHASE0_STATUS). `validate_package.py` und `compileall` OK.
Alles bleibt **hinter dem Flag** `role_routing.enabled` (AUS). Ausgeschaltet verhält sich die Modellwahl wie in v1.20: der `ModelRouter` bekommt den Provider-Zustand nicht angehängt, der Supervisor hat keinen Resolver (beides im Test geprüft).

## Umgesetzt

| Baustein | Datei |
|---|---|
| Deklarative Capability-Rezepte, Policy, Health-Parameter | `config/role_routing.yaml` |
| Rollenauflösung, Fallback, `independence_key`, `ProviderHealth` | `src/guppi_runtime/role_routing.py` |
| Rolle → Provider im Control Master | `modules/control.py` (`resolve_role`, `resolve_fallback`) |
| Provider-Zustand im Modell-Router (nur wenn angehängt) | `models/router.py` |
| Auflösung beim Start, Meldung des Ergebnisses, Unabhängigkeit | `job_supervisor.py` (`resolver`, `provider_report`, `requirements`, `independent_of`) |
| Unabhängigkeit auch im Entwicklungspfad | `self_development.py` (`independence_check`) |
| Verdrahtung, `/api/routing` (nur lesend), `boot()`-Status | `runtime.py`, `uix_server.py` |
| Fehlerklassen für Auflösungsfehler | `failure_classes.py` |
| F-9 (Budgetuntergrenze) | `context_budget.py` |

## Was belegt ist (67 neue Tests)

**Auflösung**
- Rolle → Rezept mit Begründung (`considered` nennt jede Ablehnung samt Grund). Gesunde Provider vor degradierten, dann lokal vor Cloud (bei `offline_preferred`), dann Reihenfolge.
- Nicht unterstützte oder fehlerhafte Anforderungen werden **nie ignoriert** (`requirements_unmet`).
- Statische Prüfung: RAM/VRAM-Limits des Jobs und des Hosts, Kontextbedarf gegen das **effektive** Fenster aus dem Hardware-Model-Pass (4096 auf `cpu_small`, obwohl das Rezept 32768 sagt), nicht passendes Modell (`hardware_incompatible`).
- `load_check`-Hook liefert `hardware_pressure` (Reservierungen sind weiter Phase 7).
- Fehlercodes: `no_capability`, `requirements_unmet`, `policy_denied` (nur wenn **jeder** Kandidat an der Policy scheitert), `hardware_pressure`, `provider_unavailable`.

**Policy**
- Berechtigungsstufe des Jobs über der des Rezepts → `policy_denied`. Netzwerkregeln. **Cloud nur mit Policy-Freigabe, Captain-Freigabe pro Auflösung und unkritischer Datenklasse.**
- `GUPPI_GENERATED` und `EXTERNAL_UNVERIFIED` können **nie** in die erlaubten Vertrauensstufen aufgenommen werden (Start wird verweigert).
- Ein Fallback lockert weder Netzwerk, Datenklasse noch Berechtigung (`fallback_loosens_requirements`). Ein Fallback nach `policy_denied` ist **immer** verboten.

**Unabhängiger Verifier (schließt F-4)**
- Schlüssel = Modellfamilie + exakte Gewichte. **Ohne Gewichts-ID gibt es keinen Schlüssel**, und unbekannt gilt nie als unabhängig.
- Derselbe Schlüssel unter anderer Rolle (`coder` und `verifier` auf demselben Modell) scheitert. Fehlender Schlüssel scheitert. Unbekannter Bauherr scheitert.
- Doppelt abgesichert: schon bei der Auflösung **und** nochmals in `mark_passed` (`verification_inconclusive`). Der Entwicklungspfad stuft ein PASS ohne nachweisbare Unabhängigkeit auf `INCONCLUSIVE` herab.

**Provider Health**
- HEALTHY → DEGRADED → COOLDOWN, `rate_limit` und `runtime_crash` sofort, `model_unavailable` → UNAVAILABLE bis zu einer erfolgreichen Probe. Cooldown wächst exponentiell bis zum Deckel. Nach Ablauf genau **ein Versuch** (DEGRADED): Erfolg heilt, Misserfolg verlängert.
- **Nur Provider-Fehler zählen** (Policy, Test-, Validierungs-, Kontext- und Hardwarefehler bestrafen den Provider nicht).
- Zustand überlebt einen Neustart, 6 Threads verlieren keinen Fehler, nur Zustandswechsel werden auditiert.
- **Eigener Fehler, vom Test gefunden und behoben:** Meine erste Fassung begrenzte die Cooldown-Dauer relativ zur aktuellen Uhr. Eine zurückgestellte Uhr hätte einen Provider **dauerhaft** eingefroren. Jetzt wird der Beginn mitgespeichert, und eine Uhr vor dem Beginn beendet den Cooldown früh (ein Probeversuch, nie ein Einfrieren).

**Zusammenspiel mit dem Supervisor**
- Der Start löst die Rolle auf und trägt `provider_ref`, `capability`, `independence_key` am Versuch ein. Die Berechtigungsstufe des Jobs geht an den Router.
- Scheitert die Auflösung, ist nichts gelaufen, der Ausgang ist bekannt: `policy_denied` → Captain, `no_capability`/`requirements_unmet` → GUPPI, `provider_unavailable`/`hardware_pressure` → neu einreihen mit Wartezeit. Kein Provider wird dafür verantwortlich gemacht.
- Ein abstürzender Resolver lässt den Job nicht hängen (der Claim verfällt).
- Ergebnisse gehen an die Health: Fehler (inkl. verlorener Worker als `timeout`) und Erfolg bei `mark_passed`.
- **Fallback Ende zu Ende:** Nach zwei Timeouts ist p1 DEGRADED, der Router wählt für den dritten Versuch das gesunde p2. Dessen Timeout fordert den Fallback an (`exclude: [p2]`), der nächste Versuch läuft wieder auf p1.

**Modell-Router:** ohne Hook unverändert. Mit Hook werden Provider im Cooldown übersprungen, ein ausdrücklich gewählter Provider im Cooldown gibt `provider_cooldown`, Fehler und Erfolge werden gemeldet.

**Grenzen (statisch geprüft):** `role_routing.py` und `job_supervisor.py` nennen keinen Provider und kein Modell.

## Neuer Befund und Korrektur (F-9)

`ContextBudgetManager` lehnt jetzt Fenster unter **3145** mit **einer** Meldung (`context_window_too_small`), wenn die Standardaufteilung gilt. Explizit übergebene Reserven und Teilbudgets bleiben möglich.
**Korrektur zu PHASE4_STATUS:** Dort stand „kleinste Fenstergröße 3133". Das war irreführend: Die Aufteilung ist knapp über der Grenze **nicht monoton** (3133 gelingt, 3134–3137, 3139 und 3144 scheitern). Die wirkliche Untergrenze, ab der **jede** größere Fenstergröße funktioniert, ist 3145. Der Test prüft den gesamten Bereich von 1024 bis 40000.

## Nicht umgesetzt / offene Grenzen (ehrlich)

1. **Keine echten Provider geprüft.** Alle Tests nutzen nachgebaute Adapter und Rezepte. Die mitgelieferte Konfiguration nennt zwei Provider-Kennungen, ohne dass hier ein Server lief.
2. **Das Verifier-Rezept ist abgeschaltet** (`enabled: false`), weil kein Kev-Server und keine Gewichte vorliegen. Ebenso hat das Standard-Rezept **keine Gewichts-ID**. Beides heißt: **Mit der ausgelieferten Konfiguration kann kein PASS mit nachgewiesener Unabhängigkeit entstehen**, bis der Captain eine Gewichts-ID einträgt und ein Verifier-Rezept aktiviert. Das ist beabsichtigt und sicher, aber kein Komfort.
3. **Zwei Welten:** Supervisor-Jobs (`runtime_data/jobs/`) und Entwicklungsjobs sind weiter getrennt (Phase 8). Die Unabhängigkeitsprüfung im Entwicklungspfad arbeitet mit **Rollennamen** (`coder`/`verifier`) und löst deren Schlüssel über den Router auf, nicht über die tatsächlich gelaufenen Versuche.
4. **Kein Treiber:** Nichts ruft den Fallback automatisch auf. `resolve_fallback` existiert und ist getestet. Der Supervisor nutzt stattdessen `retry.exclude` und löst beim nächsten Start neu auf. Der Aufruf von `resolve_fallback` durch einen Worker-Loop fehlt.
5. **`exclusive`, `test_required`, `filesystem_scope`** werden **nicht** erzwungen (Dateizugriff regelt der Guard, `exclusive` braucht Reservierungen aus Phase 7).
6. **Provider-Gesundheit gilt je Provider-Kennung**, nicht je Modell. Zwei Rezepte desselben Providers teilen ihren Zustand.
7. **Echte Health-Probes** (Provider lebt?) gibt es nicht. `probe()` ist da, aber niemand ruft es auf. Ein als `UNAVAILABLE` markierter Provider bleibt es bis zu einer Probe oder einem erfolgreichen Aufruf über einen anderen Weg.
8. **Fehlerklassifikation echter Provider-Fehler** ungeprüft (siehe Phase 0). Ein nicht erkannter Fehler zählt nicht als Provider-Fehler und bestraft den Provider daher nicht.
9. **Cloud-Anbindung** existiert nicht. Cloud-Rezepte sind nur als Richtlinienprüfung getestet.
10. **Uhr:** Die Gesundheit nutzt Wanduhrzeit. Eine zurückgestellte Uhr beendet einen Cooldown früh (gewollt), eine Rückkehr in das alte Zeitfenster lässt den Rest wieder gelten, höchstens bis zum ursprünglichen Ende.

## Abweichungen vom Vertrag

| Vertrag | Umsetzung |
|---|---|
| 8.1 `Resolution.runtime_profile_id` | `context_window`, `model`, `estimated_resources`; ein eigener Profil-Identifikator fehlt |
| 8.1 `estimated_resources.kv_cache_gb` | immer `null` (KV-Cache ist nicht modelliert, siehe Hardware-Pass) |
| 8.3 „Fallback entscheidet der Control Master innerhalb der Policy" | `resolve_fallback` im Router/Control Master. Der Supervisor erzeugt weiter nur `retry.exclude` |
| 5 Rollen-Konfiguration | zusätzlich `independent_of` je Rolle in `job_supervisor.yaml` (Verifier und Security-Reviewer unabhängig von `coder`) |
| E-8 `independence_key` | Familie + Gewichts-ID, **keine** Bildung durch Hashen der Gewichtsdatei. Die ID trägt der Captain ein |

## Entscheidungen für den Captain

1. **Gewichts-IDs und Verifier:** Welches Modell soll `coder` und welches `verifier` sein, und wo kommt die Gewichts-ID her (Dateihash, Katalogeintrag)? Ohne diese Angabe bleibt jede Verifikation `INCONCLUSIVE`.
2. **Provider-Kennungen in der Konfiguration** (`llama-cpp-server`, `kev`) sind Annahmen aus dem Bestand. Bitte bestätigen oder ändern.
3. **Probes:** Soll der Supervisor `ProviderHealth.probe` periodisch mit dem Adapter-`health()` füttern? Empfehlung: ja, zusammen mit dem Reaper-Thread in einem Worker-Loop.

## Nächster Schritt: Phase 6 (Berechtigungen)

Level 0–6 als **Abbildung auf Guard-Aktionen** (keine zweite Rechteschicht), Bindung an die Entwicklungsumgebung, Approval-Zustand (`request_approval`/`resolve_approval`) und die Prüfung, dass ein Job nur Aktionen bis zu seinem Level anfordern kann. Offen ist dort vorab, die 24 Guard-Aktionen anhand von `guard_rules.yaml` tatsächlich zu lesen (bisher nur nach Namen eingeordnet).
