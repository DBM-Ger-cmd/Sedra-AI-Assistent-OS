# SPEC F0-05C – Owner-basierte UIX/Runtime/GPU-Shutdown-Reihenfolge

**Status:** ANTRAG für G1/G2 (Entwurf). Ohne Captain-Freigabe kein Code, keine G3.
**Basis:** lokaler `main` = `52f33f3` (enthält `aa5962e`, Vorfahr geprüft). Zeilennummern gelten für `52f33f3`; bei `aa5962e` identisch für die hier zitierten Stellen in `uix_server.py` (Zeile 3620, 3637) und `orchestra/service.py` (Zeile 242).
**Register:** SEDRA-F0-05C, Status `SPEC_APPROVED` (G1/G2 am 06.11.2026 freigegeben, dieser Entwurf ist die Spezifikation dazu).
**Erstellt:** 08.11.2026, Nachtlauf (Claude-Sitzung, kein Coder-Lauf mit lokalem Modell; siehe `ABGABE.md`).
**Vorbedingung:** F0-05B ist `MERGED` (`e83d0af`), F0-05A `MAIN_VERIFIED`.

---

## 1. Ist-Zustand (belegt)

### 1.1 Schließreihenfolge im UIX-Fenster

Datei: `runtime/src/sedra_runtime/uix_server.py`, Methode `UIXHub.close()` (Zeile 3620–3642).

| Schritt | Zeile | Was passiert | Problem |
|---|---|---|---|
| a | 3622 | `self.poller.stop()` | ok |
| b | 3624–3626 | `sched.stop_server(owner='werkstatt-close')` – Modellserver wird beendet | **GPU/Modell wird freigegeben, bevor Worker gedraint sind** |
| c | 3627–3629 | `self.unload_model({})` bzw. `_release_gpu()` – GPU-Lease geht zurück | **gleiches Problem: GPU-Freigabe vor Drain** |
| d | 3630–3633 | `_gw_wissen`, `_arbeitsplatz` werden geschlossen (`w.close()`) | **Wissensspeicher wird geschlossen, obwohl Orchestra-Worker ihn evtl. noch lesen** (vgl. `runtime.py:603–616`, dort ist genau dieser Schutz vorgesehen) |
| e | 3637 | `self.runtime.close()` – Orchestra-Drain und Wissen-Close | läuft erst jetzt; sein Ergebnis wird nur ins Audit geschrieben (3638–3643) |

Zusätzlich: `UIXHub.__init__` (Zeile 127) ruft bei Init-Fehler `runtime.close()` ohne Drain-Prüfung auf; die Fehlerausgabe wird geschluckt, nur der Init-Fehler wird weitergereicht.

Der Aufruf `hub.close()` im `finally` (Zeile 4247) ist der einzige Pfad beim Fensterende. Ein Timeout im Drain erzeugt dort nur einen Audit-Eintrag `RUNTIME_SHUTDOWN_ERROR`, sichtbar für den Captain nur im Audit, nicht in der Oberfläche.

### 1.2 Runtime-Schließen

Datei: `runtime/src/sedra_runtime/runtime.py`, Methode `close()` (Zeile 594–620).

- Schließt nacheinander `orchestra` und `wissen`, merkt erfolgreiche Dienste in `_closed_services`.
- Bei `orchestra_shutdown_pending` wird `wissen` **nicht** geschlossen (`break`, Zeile 613–616). Gut.
- Bei anderen Fehlern wird `wissen` trotzdem geschlossen, während der Orchestra-Fehler offen ist. Das ist ein Widerspruch zur Absicht „Wissen nicht vor dem Drain schließen“ (nur bei `orchestra_shutdown_pending` geschützt).
- Am Ende: `RuntimeError("runtime_close_failed:…")`.

### 1.3 Orchestra-Schließen

Datei: `runtime/src/sedra_runtime/orchestra/service.py`, Methode `close(wait_s=5)` (Zeile 238–243).

- `stop_tick(wait_s)` false → `RuntimeError("orchestra_shutdown_pending")`, SQLite-Verbindung bleibt offen. Richtig.
- Die Wartezeit (5 s) ist fest; kein Gesamtbudget über alle Stufen.

### 1.4 Was fehlt

- Es gibt keine Reihenfolge-Garantie „GPU/Modell erst nach bestätigtem Drain“. Schritt b und c laufen vor e.
- Ein Timeout wird im UIX nicht als `SHUTDOWN_PENDING` angezeigt; es gibt nur das Audit-Ereignis.
- Die Bestätigung „Drain fertig“ ist nicht als eigenes Ergebnis (z. B. `DRAINED`) modelliert.

---

## 2. Soll-Reihenfolge (Vorschlag)

Die Stufen laufen in dieser Reihenfolge. Jede Stufe liefert ein Ergebnis `DRAINED` oder `SHUTDOWN_PENDING`; die nächste Stufe startet nur bei `DRAINED`.

1. **Annahme sperren:** neue Claims und neue Modellanfragen aus dem UIX werden abgelehnt (Quiesce, siehe F0-05B). Poller stoppen (wie heute).
2. **Worker-Drain:** `runtime.close()` bzw. `orchestra.close()` – Worker beenden, Tick stoppen. Ergebnis `DRAINED` nur, wenn alle Handles beendet sind.
3. **Wissen schließen:** erst nach `DRAINED` aus Stufe 2.
4. **Datenbank schließen:** erst nach Stufe 3.
5. **Modellserver und GPU freigeben:** erst nach `DRAINED` aus Stufe 2 (und nur dann, wenn kein anderer Owner die GPU hält – Fencing aus F0-05D).

Konsequenz: Die Schritte b, c und d aus 1.1 wandern hinter den Drain. Die Fensterlogik bleibt sonst gleich.

### 2.1 Ergebnisform

- `DRAINED`: alle Stufen erfolgreich, keine Handles offen.
- `SHUTDOWN_PENDING`: mindestens ein Worker oder Tick läuft noch; Ressourcen, die er braucht (Wissen, DB, Modell, GPU), bleiben belegt. Das Fenster zeigt diesen Zustand sichtbar an.
- Teilfehler: sichtbar im Fenster (Oberfläche), zusätzlich im Audit. Kein stilles Verschlucken.

### 2.2 Timeout

- Gesamtbudget für den Shutdown (Vorschlag: 15 s, Captain-Entscheidung, siehe Abschnitt 6). Die Stufen teilen sich das Budget.
- Bei Ablauf: `SHUTDOWN_PENDING`, nie `DRAINED`.
- Die noch laufenden Handles bleiben in der Runtime. Ein späterer Aufruf von `close()` (Retry) setzt dort fort; das bestehende Muster in `runtime.py` (`_closed_services`) bleibt erhalten.

---

## 3. Fehlerpfade

| Fall | Verhalten |
|---|---|
| Drain erfolgreich | Stufen 3 bis 5 laufen in Reihenfolge, Ergebnis `DRAINED`, Audit `SHUTDOWN_OK` |
| Timeout beim Drain | `SHUTDOWN_PENDING`, Wissen, DB, Modell und GPU bleiben offen, Audit `SHUTDOWN_PENDING`, Anzeige im Fenster |
| Teilfehler (z. B. Wissen schließt nicht) | Die übrigen unabhängigen Stufen laufen weiter; Fehler wird angezeigt und auditiert, nicht verschluckt |
| Wiederholung (zweiter `close()`) | Nur die noch offenen Stufen laufen; bereits geschlossene werden übersprungen (wie `_closed_services`) |
| Modellserver antwortet nicht beim Stoppen | GPU-Lease bleibt bis zum Timeout; kein stilles Freigeben |
| Init-Fehler in `UIXHub.__init__` | Gleiche Reihenfolge; Init-Fehler bleibt die Hauptfehlermeldung |

**Keine vorzeitige Freigabe:** GPU und Modell werden nie vor `DRAINED` freigegeben, auch nicht bei Fehlern.

---

## 4. Abgrenzung

- **F0-05A** (Drain-Sicherheit, `MAIN_VERIFIED`): Stop-/Join-Status von WorkerPool und Orchestra. Diese Spec baut darauf auf und ändert die Stop-Logik nicht.
- **F0-05B** (Quiesce-Gate, `MERGED`): sperrt neue Claims. Diese Spec setzt es voraus (Stufe 1).
- **F0-05D** (Recovery, Fencing, Leases): Owner-Schlüssel und Lease-Regeln gehören dorthin. Diese Spec verlangt nur die Reihenfolge und nutzt den Owner-Schlüssel aus F0-05B, ohne ihn zu definieren.
- **Nicht Teil von F0-05C:** Crash-Recovery, `in_doubt`/`unknown`, Job-State-Migration, Browser-Bahn, Windows-Live-Tests (F0-05E).

---

## 5. Abnahme (Vorschlag für G3-Tests)

Die Tests sind Vorschlag; sie werden erst mit G3 geschrieben und nicht ausgeführt, bevor G3 erteilt ist.

1. Fake-Worker hängt beim Drain: `close()` liefert `SHUTDOWN_PENDING`; GPU-Stopp und Wissen-Close wurden nicht aufgerufen (Mock-Zählung 0).
2. Drain erfolgreich: Aufrufreihenfolge exakt Wissen → DB → Modell → GPU, nach Drain.
3. Zweiter `close()` nach Timeout: schließt nur die offenen Stufen; keine doppelte Schließung.
4. Teilfehler in Wissen: andere Stufen laufen, Fehler im Ergebnis und im Audit sichtbar.
5. Windows-Live (F0-05E): echter Worker, Fensterende, Prüfung der Prozesse und des GPU-Speichers – nicht Teil dieser Spec, sondern F0-05E.

---

## 6. Offene Fragen an den Captain

1. **Gesamtbudget Shutdown:** Vorschlag 15 s. Bestätigen oder anderen Wert nennen?
2. **Anzeige im Fenster:** Soll `SHUTDOWN_PENDING` im UIX als Hinweis erscheinen (Vorschlag: ja, kurzer Text, kein Blockieren)?
3. **Entscheidung Modell bei Timeout:** Soll das Modell bei `SHUTDOWN_PENDING` trotzdem nach Ablauf des Budgets beendet werden (mit Risiko für laufende Worker), oder bleibt es bis zum Retry an? Vorschlag: bleibt an, bis Retry oder Neustart; nicht stillschweigend beenden.
4. **Owner-Schlüssel:** Die Spec von F0-05B schlägt pro Runtime-Instanz vor. Für F0-05C reicht das; Bestätigung nötig, weil F0-05D darauf aufbaut.
5. **Wissen-Schutz in `runtime.close()`:** Der aktuelle Code schließt Wissen bei Fehlern außer `orchestra_shutdown_pending` trotzdem. Soll das auf „Wissen nie vor erfolgreichem Orchestra-Drain“ verschärft werden? Vorschlag: ja.
6. **Ein Test ist offen:** Ob der Windows-Prozess-Test (echte Worker-Threads) in F0-05C oder erst in F0-05E liegt. Vorschlag: F0-05E.

---

## 7. Belege (Zeilen)

- `runtime/src/sedra_runtime/uix_server.py:127` – Init-Fehler-Pfad mit `runtime.close()`
- `runtime/src/sedra_runtime/uix_server.py:3620–3643` – `UIXHub.close()`
- `runtime/src/sedra_runtime/uix_server.py:4245–4250` – `finally` mit `hub.close()` beim Fensterende
- `runtime/src/sedra_runtime/runtime.py:594–620` – `SedraRuntime.close()`
- `runtime/src/sedra_runtime/orchestra/service.py:238–243` – `Orchestra.close()`
- `runtime/src/sedra_runtime/wissen/schema.py:129` – `oeffne_db` (SQLite-Verbindung, Quelle der ResourceWarnings in F0-06A)

Diese Zeilen sind am lokalen `main` (`52f33f3`) gelesen; vor G3 gegen den dann aktuellen Stand neu prüfen.
