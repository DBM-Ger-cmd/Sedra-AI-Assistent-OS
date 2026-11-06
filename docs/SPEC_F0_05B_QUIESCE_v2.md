# SEDRA-F0-05B | Quiesce-Gate – Spezifikation v2 (G1/G2)

**Auftrag:** SEDRA-F0-05B · **Owner:** Coder 1 / Foundation
**Basis:** Git-Bundle `sedra_main_2b13daa.bundle`, Commit `2b13daa` (06.11.2026)
**Stand:** `CODER_HANDOFF` – technische Entwurfsabgabe, **kein G3** / kein Produktivcode
**Quelle des Auftrags:** `ANWEISUNG_CODER_1_V2_2026-11-06.md` und `ENTSCHEIDUNG_F0-05B_CLAIM_VERTRAG_2026-11-06.md`

## 1. Status, Ziele und Nicht-Ziele

Captain hat **Variante B** entschieden: nach der Quiesce-Grenze kein neuer Claim-Commit; davor reservierte, aber nicht begonnene Claims sollen über `_unclaim` ohne verbrauchten Attempt zur Queue zurückkehren. Neutrale Nichtannahme (auch bei `append_lock_timeout`) ist eine **Koordinator-Empfehlung mit noch ausstehender Captain-Bestätigung**. F0-05A ist weiterhin `INTEGRATION_REVIEW`; unabhängig verifiziertes Main und G3-Bauauftrag fehlen. Diese Datei stellt keinen Bauauftrag dar.

**Nicht in diesem Auftrag:** UIX/GPU-Reihenfolge (F0-05C), Recovery/Fencing-Änderungen (F0-05D), Schema-Migration, SOUL/Freigaben, Harness-Lauftypen, Wissen-K5, globale Scheduler-Sperre, Job-Abbruch, neue Orchestrierung.

## 2. Ist-Code mit reproduzierbaren Belegstellen (`2b13daa`)

| Thema | Befund / Source |
|---|---|
| Supervisor-Konstruktion | `runtime/src/guppi_runtime/jobs/job_supervisor.py:243-265`: `JobSupervisor` nimmt `store`, `config` etc., bisher **keine** runtimegebundene Quiesce-Owner-ID; `runtime/src/guppi_runtime/runtime.py:357-360` erzeugt den Supervisor. |
| Worker-ID | `job_supervisor.py:294-298`: `worker_id` ist ein Format-validierter String, **keine** Instanzidentität. `job_supervisor.py:628-630`: persistierter Claim nennt nur `worker_id`/Zeit/State. |
| Claim-Commit | `job_supervisor.py:597-635`: `store._lock()` ab 603, Scan ab 604, optionale Slot-Vergabe 625-626, persistierende `store.mutate` 628-634. **Kein Quiesce-Gate**. |
| Slot-Speicher | `job_supervisor.py:637-649`: `wait_for_job` / `take_for_job` laufen in einem **separaten** Slot-Backend; `_slot_requeue` bei Fehler 328-336/632-634. |
| `_unclaim` | `job_supervisor.py:651-663`: setzt nur bei passendem `worker_id` und `worker.state=='claimed'` den Worker auf `None`; requeued Slot; kein Attempt wird erzeugt. Vor Wiederverwendung Ownership-Rennen prüfen. |
| Start-Commit | `job_supervisor.py:665-715`, `717-774`: Resolver/Loader/Scheduler außerhalb Store-Lock; `_start_attempt` nutzt `store.mutate` ab 737 und erhöht `attempts` bei 760-764; **kein Gate vor Start-Commit**. |
| Lock-Mechanik | `runtime/src/guppi_runtime/selfdev/self_development.py:126-151`: Store-Lock via `append_lock`, `mutate` verwendet ihn reentrant und schreibt vor dem Exit. `core/util.py:93-120`: OS-/Thread-Lock; Timeout `RuntimeError('append_lock_timeout')` an Zeile 115. |
| Worker-Fehler | `runtime/src/guppi_runtime/jobs/job_worker.py:95-108`: `run_once()` behandelt beim Claim nur `JobError`, nicht `RuntimeError`; `run_forever` 154-163 hat keinen äußeren Catch. |
| Direkter Helfer | `job_supervisor.py:1490-1509`: `run_next()` behandelt nur `JobError` (`no_job`, `no_slot`); `RuntimeError` propagiert. |
| Orchestra-Pool | `runtime/src/guppi_runtime/desk/orchestra_runner.py:355-364`: `_loop()` fängt ausnahmsweise `Exception`, setzt auf `idle` zurück; **nicht** ausreichend als allgemeiner API-Vertrag; `365-380` Drain-Schutz durch F0-05A. |
| Runtime-Shutdown | `runtime/src/guppi_runtime/runtime.py:594-620`: `close()` schützt Wissen bei `orchestra_shutdown_pending`; Quiesce-Gate fehlt bisher. `orchestra/service.py:108-128,223-228`: bei fehlendem Drain SQLite nicht schließen. |

### Ergebnis des Fehlerpfad-Checks (v2 Auftrag Nr. 3)

**Bestätigt:** `append_lock_timeout` kann aus `claim()` als `RuntimeError` austreten; `run_once()` und `run_next()` fangen diesen Typ nicht. In `Worker.run_forever()` propagiert die Exception und beendet den Aufruf. **Nur** die äußere Orchestra-`WorkerPool._loop()`-Schleife fängt `Exception` und läuft weiter; dabei wird die spezifische Ursache zu `idle` verschluckt. Deshalb die Normalisierung **einmal zentral an der Claim-Grenze**, vor jeder der beiden Consumer-APIs, vorsehen; `run_once`/`run_next` müssen das definierte neutrale Ergebnis ausdrücklich korrekt abbilden.

## 3. Owner-Schlüssel – konkret

**Vorschlag für G3:** Jede `JobSupervisor`-Instanz erzeugt beim Erstellen eine **einmalige, zufällige** `instance_owner_id` (z. B. `uuid.uuid4().hex`), sofern ihr keine eindeutige Runtime-Boot-ID explizit übergeben wurde. `GuppiRuntime` kann bei Boot eine eigene Laufzeit-ID erzeugen und an genau ihren Supervisor übergeben (`runtime.py:357-360`). Eine direkt für Tests/CLI erzeugte `JobSupervisor`-Instanz braucht ihren eigenen Fallback. ID bleibt **prozesslokal/ephemer** und dient Gate-, In-flight- und Audit-Korrelation, **nicht** als Sicherheits-Token oder persistenter Lease-Owner.

- Gate, `STOP_REQUESTED`, Claim-In-flight-Liste und Zustandsautomat sind **an genau diese Supervisor-Instanz** gebunden. Zwei Supervisoren, die dieselben Jobs-Dateien verwenden, besitzen getrennte Gates; der bestehende Store-Lock serialisiert gemeinsame Schreibvorgänge.
- `worker_id` scheidet als Gate-Schlüssel aus: an `job_supervisor.py:294-298` wird nur Form geprüft, und Orchestra verwendet potenziell wiederkehrende Namen. Gleicher String in zwei Instanzen beweist **keine** gemeinsame Ownership. Ein Claim gehört nicht einfach deshalb uns, weil seine `worker_id` zufällig passt.
- **Prozessneustart:** Neue Owner-ID und neues Gate. Alte Claims/Leases dürfen nicht aufgrund einer nicht mehr existierenden In-Memory-ID freigegeben werden; bestehende Startup-Recovery- und Fencing-Regeln bleiben zuständig.
- **Offener G3-Sicherheitsnachweis:** Für ein `_unclaim` bei Quiesce muss zusätzlich zur `worker_id` eine lokale Claim-Erfassung mit Job-ID und eindeutigem Claim-Snapshot/Generation bestätigt werden. Die aktuelle Persistenz enthält keinen expliziten `instance_owner_id`; bei Unklarheit **nicht fremd unclaimen**, sondern `SHUTDOWN_PENDING`/Audit. Keine neue persistente Schemaänderung unter diesem G2-Auftrag.

## 4. Claim-Commit-Cut (Captain-Variante B) und Sperrfolge

**Begriffe:** `STOP_REQUESTED` bezeichnet die monotone, sofort sichtbare Stop-Anforderung. **Linearization Point** von `QUIESCING` ist der unter dem Gate-Mutex wirksame Zustandssprung. Ein vor diesem Punkt vollständig geschriebener Claim zählt als vor Quiesce committed; nach diesem Punkt darf kein neuer Claim geschrieben werden. Eine bereits begonnene Claim-Operation, die erst danach an den Guard gelangt, muss neutral abgelehnt werden.

### Lock-Reihenfolge – verbindlicher Vorschlag

`JobStore._lock` (OS-/Thread-Sperre) **vor** `QuiesceGate.lock`; für `claim` wird Gate-Lock bis **nach** der vollständigen `store.mutate`-Persistierung gehalten. `request_quiesce()` darf den Store-Lock **nicht** nehmen; es setzt zuerst das monotone Stop-Signal, dann synchronisiert es den Zustandswechsel **nur** über das Gate-Lock. Kein Warten auf Worker, GPU, Resolver, Slot-API oder Shutdown-Callback bei gehaltenem Gate-Lock.

### Nummerierter Ablauf `JobSupervisor.claim()`

1. Rollen, Worker-ID und Konfiguration prüfen. `gate.stop_requested`/`gate.state` **vor** Store-Lock lesen: geschlossen → definierte neutrale Ablehnung (`quiesced`; Entscheidung ausstehend). Nur ein schneller Vorfilter; **kein** alleiniger Schutz.
2. `store._lock()` mit definierter Obergrenze erwerben. Timeout (`RuntimeError('append_lock_timeout')` aus `core/util.py:115`) nur für **diesen erwarteten** Fehler in definiertes Nichtannahme-Ergebnis und Audit normalisieren; andere `RuntimeError` **nicht** verschlucken. Kein Job-State-Wechsel.
3. Unter Store-Lock `scan`, Busy-/Rollen-/Queue-Prüfung und Sortierung ausführen (`job_supervisor.py:604-624`). Falls Slots aktiviert, `_take_slot` in separatem Slot-Speicher (`625-626`, `637-649`) ausführen. Diese Phase kann Quiesce **überlappen**, weil der Gate-Lock hier noch nicht gehalten wird.
4. **Unmittelbar vor dem Persistieren** Gate-Lock mit einer Obergrenze erwerben (`store -> gate`). `stop_requested` **und** Gate-State erneut prüfen. Ist geschlossen: gegebenenfalls bereits erhaltenen Slot sicher requeueen (`_slot_requeue`), Job bleibt `QUEUED`/`worker=None`, **kein `store.mutate`-Claim**, neutrale Ablehnung. Fehler der Slot-Kompensation dürfen nicht als erfolgreicher Drain gemeldet werden.
5. Ist Gate offen: `store.mutate(chosen['job_id'])` unter **beiden Locks** vollständig bis inklusive Dateipersistenz abschließen. Erst nach erfolgreichem Store-Commit Gate-Lock freigeben. `mutate`/`save` verwenden den Store-Lock reentrant (`self_development.py:141-151`). Einen lokalen In-flight-Datensatz **vor** diesem Commit registrieren und nach erfolgreichem Exit als `claimed_not_started` führen.
6. Store-Lock freigeben; Rückgabe `{'status':'claimed','job':...}` nur bei wirklichem Commit. Audit nach Lock-Freigabe bzw. audit-sichere Reihenfolge nachweisen; der bestehende `_audit`-Aufruf in der Mutations-Transaktion muss in G3 auf Lock-Zyklen und Ausfallverhalten geprüft werden.
7. Bei jeder Exception: In-flight-Aufzeichnung korrekt und idempotent abschließen; bei Slot-Grant ohne Claim-Commit Slot nur für nachweislich eigene Reservierung kompensieren. Slot-Kompensationsfehler/Auditfehler sichtbar melden; nie den Quiesce-Zustand wieder öffnen.

### Quiesce während `_take_slot`

Quiesce benötigt **keine** Store-Sperre und kann während der Slot-Vergabe das Gate schließen. Die nachgelagerte Gate-Prüfung in Schritt 4 erkennt das zuverlässig. Ein bereits erhaltener Slot muss zurück in Wartestatus, **ohne** einen Job zu claimen. `wait_for_job()` kann zuvor für mehrere Jobs Queue-Einträge angelegt haben: diese im separaten Slot-Backend nicht ungezielt löschen. Eine unerwartete Slot-Backend-Störung führt zu `SHUTDOWN_PENDING`/Audit, nicht zu `DRAINED`.

### Start-Commit/`_unclaim` – zweite notwendige Schranke

`claim`-Schutz **allein reicht nicht**: `confirm_start` führt nach teils externen Resolver-/Loader-/Scheduler-Schritten `_start_attempt` aus (`job_supervisor.py:665-774`), schreibt `RUNNING` und erhöht `attempts` (`760-764`). G3 muss **vor dem Start-Commit** nochmals dasselbe lokale Gate prüfen und den Schreib-/Startübergang gegen den Quiesce-Cut serialisieren. Ein vor dem Cut vollständig gestarteter Attempt darf weiterlaufen und wird gedraint. Ein `claimed_not_started`-Job wird bei geschlossenem Gate mit der existierenden `_unclaim`-Semantik (`651-663`) zurück nach `QUEUED` gegeben, **ohne** Attempt-Erhöhung. Die zuvor gestarteten Resolver-/Slot-/Loader-Operationen müssen nachweislich eigene Reservierungen kompensieren oder als pending ausgewiesen werden.

**Noch zu verifizieren vor G3:** `_unclaim` identifiziert derzeit nur `worker_id` und `worker.state == 'claimed'`; beim Einsatz im Shutdown muss Ownership inkl. Claim-Generation ausreichend nachgewiesen sein. Quiesce darf **keine** fremden Claims/Leases lösen. Resolver, GPU-Model-Load und externe Callbacks werden **nie** unter Gate-Lock gehalten; der finale Start-Commit benötigt eigenen kurzen Guard. Reentrante Locks/Callback-Ketten unter Store-Lock sind vor Implementierung separat auf Deadlocks zu prüfen.

### Zeitachsen-Races

- Claim hält Store-Lock, Slot-Zuteilung läuft; Quiesce erhält Gate-Lock → Gate geschlossen → späteres Claim requeued Slot, **kein Commit**.
- Claim hält Store- und Gate-Lock, Store schreibt den Claim → Quiesce wartet auf Gate. Claim-Commit liegt *vor* dem Linearization Point. Danach Quiesce, ungestarteter Claim per `_unclaim` (nur bewiesene Ownership).
- Claim hat erfolgreich committed und `confirm_start()` löst gerade externes Modell-Loading aus → Quiesce schließt Gate; vor Start-Commit erneute Gate-Prüfung, danach `_unclaim`, nur eigene Reservierungen bereinigen.
- Claim kann Gate-Lock nicht in Deadline erwerben → keine Annahme; Shutdown zeigt `SHUTDOWN_PENDING`, falls Cut/Ownership nicht sicher bestätigt werden kann, **nicht** `DRAINED`.

## 5. Neutrale Nichtannahme / Timeout-Vertrag (Captain-Bestätigung ausstehend)

**Empfohlenes Ergebnis:** intern ein typisiertes, klares Resultat oder ein `JobError('quiesced')`, der an den Verbrauchergrenzen kontrolliert zu `{'status':'waiting','reason':'quiesced'}` übersetzt wird; `run_next` bekommt eine ebenfalls neutrale `waiting`-Antwort. Kein falsches `idle` bei unerwarteter Blockade und **kein** `fail(job)` / JobError-Report, der einen Attempt verbraucht. Das endgültige öffentliche Rückgabeformat bedarf des Vertragsabgleichs vor G3.

- Unterscheiden: `quiesced` (geplant), `append_lock_timeout` (Lock-Fehler), `slot_cleanup_pending` (Kompensation offen). Für außen neutrale Nichtannahme, für Readiness/Audit **ursprünglichen Grund bewahren**.
- Nur `RuntimeError` mit **exaktem** `append_lock_timeout` soll gezielt abgefangen werden; übrige Exceptions bleiben Fehler. Abbildung am zentralen `claim`-Schutzpunkt verhindert den aktuellen unbehandelten Timeout in `run_once` und `run_next`, ersetzt aber nicht deren explizite Consumer-Vertragstests.
- Das bestehende `Worker.run_forever` bricht bei unbehandeltem Timeout ab; die Orchestra-`WorkerPool._loop()` überdeckt solche Fehler heute als `idle` (`orchestra_runner.py:355-364`). Beide Wege müssen das neue neutrale Ergebnis identisch und unterscheidbar behandeln.
- Eine offene Sperr- oder Cleanup-Operation wird nach Deadline nicht zu `DRAINED` hochgestuft. Warten für Store-Lock, Gate-Lock, Claim/Start-Commit, Worker-Drain und Callbacks ist **begrenzt**; derzeitiger `append_lock` besitzt laut `core/util.py:93-120` 10s OS-Lock-Wartebudget, jedoch kann der vorgelagerte Thread-RLock-Erwerb (`with thread_lock`) ohne explizite Timeoutgrenze warten. **G3 muss diesen Lückenfall prüfen**, nicht bloß ein höheres äußeres Timeout versprechen.

## 6. Lokaler Shutdown-Zustandsautomat / Sichtbarkeit

```text
RUNNING --request_quiesce()--> STOP_REQUESTED --gate cut--> QUIESCING
                                                        | (alle eigenen in-flights + Worker nachweislich still)
                                                        v
                                                     DRAINED
                                                        ^
                                                        |
                                      SHUTDOWN_PENDING --+ (späterer Retry/Drain nachgewiesen)
                                         ^
                                         |
                 Zeitlimit/Gate-Kollision/unklare Ressourcen oder Ownership
```

`STOP_REQUESTED` ist ein **vorgelagertes monotones** Signal, kein persistierter Job-State. Wenn Gate-Cut selbst scheitert oder eine Wartestelle die Deadline erreicht, ist das Ergebnis `SHUTDOWN_PENDING`; `stop_requested` bleibt true, neue lokale Admission fail-closed. Idempotentes `close()`/Retry kann Zustand von `SHUTDOWN_PENDING` zu `DRAINED` bringen, aber **niemals** wieder `RUNNING` in derselben Instanz.

- Sichtbar über **bestehende** Readiness-/Observability-Ausgabe, soweit anschließbar, plus auditierbare Zustandsereignisse: `QUIESCE_REQUESTED`, `QUIESCE_GATE_CLOSED`, `QUIESCE_DRAIN_PENDING` (mit Grund und betroffenen In-flights), `QUIESCE_DRAINED`. Namen sind G2-Vorschläge, keine behauptete vorhandene API.
- Eine Audit-Ausnahme darf nicht zum Reopen führen. Hat das Audit/Monitoring selbst einen Fehler, bleibt Gate geschlossen und ein Diagnosefehler wird gesondert gemeldet; **nicht** den fehlenden Nachweis als `DRAINED` deklarieren.
- F0-05A hält `orchestra`/Wissen-Verbindung bei aktiven Workern sicher offen (`runtime.py:594-620`, `service.py:223-228`). F0-05B verlangt, dass der Quiesce-Cut **vor** Worker-Drain im Runtime-Close erfolgt. F0-05C behält Ownership über UIX/GPU-Shutdown-Reihenfolge.

## 7. Sicherheitsinvarianten und Abnahme

1. Kein neuer **lokaler** Claim-Commit nach geschlossenem Gate; keine neuen Attempt-/Start-Commits nach Cut.
2. Ein ungestarteter, nachweisbar **eigener** Claim wird über `_unclaim` ohne Attempt-/Retry-Verbrauch zurückgeführt; fremde Claims/Leases bleiben unverändert.
3. `unknown`/`in_doubt` und mutierende Attempts werden niemals automatisch wiederholt oder als Erfolg markiert.
4. Gate ist pro Instanz, monoton, idempotent, fail-closed; lokaler Shutdown blockiert **nicht** andere Supervisoren am selben Store.
5. Geenfalls den Verlust von Worker-Handles, SQLite- oder GPU-Ownership durch falsches `DRAINED` kaschieren.
6. Lock-Reihenfolge `store -> gate`, Quiesce nimmt **keinen** Store-Lock; keine unbeschränkten Callbacks/externen Modelle unter beiden Locks.
7. Kein Schema- oder Rollen-/Freigabe-Upgrade in F0-05B; Control Core, Audit, Human Gate und bestehenden Lease-/Fencing-Vertrag erhalten.

**G3-Gates:** F0-05A `MAIN_VERIFIED` mit unabhängigem Tester-Bericht; Captain-G3-Auftrag; Dateireservierung/Updater-Abstimmung; Captain-Bestätigung der neutralen Ablehnung; Owner-Claim-Korrelation ohne Fremd-Unclaim; Deadlock-/Timeout-Review; daraus abgeleitete ausführbare Race-Tests.

## 8. Testkonzept

Datei `tests/test_f0_05b_quiesce.py.draft` enthält nicht ausführbare G2-Szenarien: Commit-Cut mit und ohne Slot, Gate pro Instanz, `_unclaim` ohne Attempt, Race mit `confirm_start`, wiederholter Shutdown, Timeout/PENDING, Audit, fehlerhaftes Slot-Requeue, direkte `run_next`-/`run_forever`-Fehlerpfade, Foreign Lease und sichere Recovery-Abgrenzung. Erst nach G3 Umsetzung und unabhängiger Prüfung können daraus echte Tests entstehen.

## 9. SQLite-Testhygiene – nur Befund, keine Korrektur

Gezielt auf dem isolierten Bundle-Snapshot ausgeführter `runtime/tests/test_job_supervisor.py`-Lauf meldete **zwei** `ResourceWarning: unclosed database` bei der Garbage Collection. Der Trace verweist auf `runtime/src/guppi_runtime/wissen/schema.py:129` (`sqlite3.connect`). **Drei** Tests erzeugen `GuppiRuntime`, ohne `rt.close()` aufzurufen: `runtime/tests/test_job_supervisor.py:126-134`, `743-745` und `771-773`. Aus zwei Warnungen kann **nicht** ohne Attribution auf genau zwei Tests geschlossen werden; die drei Stellen sind konkrete Review-Kandidaten. `GuppiRuntime.close` schließt den Wissen-Dienst normalerweise (`runtime.py:594-620`); das ist ein **Testhygiene-Hinweis**, kein Beleg für einen produktiven Leak. Keine Warnung unterdrücken; Testfix nur separat genehmigt.

## 10. Offene Fragen an Captain/Koordinator

1. Neutrale Ablehnung inkl. `append_lock_timeout` verbindlich freigeben? Format `waiting/quiesced` vs. typisierte Nichtannahme festlegen.
2. Wie werden `instance_owner_id` und konkrete Claim-Generation ohne persistierte Schemaänderung sicher korreliert? Falls nicht beweisbar, ist ein eigener G3-Vertragsentscheid nötig; bis dahin kein fremdes `_unclaim`.
3. Umgang mit bereits im Resolver/Loader gestarteten, aber noch nicht committed Startvorgängen beim Quiesce: bounded cancellation/cleanup vs. PENDING und nachträgliche Freigabe.
4. Audit/Readiness-Feld für `SHUTDOWN_PENDING` ohne UIX-/K5-Scope ändern: genauer API-Eigentümer abstimmen.
5. Ist der G3-Codebau erst nach `F0-05A MAIN_VERIFIED` explizit freigegeben? Laut v2: **nein**.

---
**Abgabe:** `CODER_HANDOFF` zur Spezifikationsprüfung. Keine produktive Implementierung; kein Main-Merge und keine neue Git-Commit-Historie.
