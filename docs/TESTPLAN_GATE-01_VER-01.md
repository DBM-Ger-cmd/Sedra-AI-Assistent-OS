# Testplan GATE-01 und VER-01 (vorbereitet, NICHT ausgeführt)

**Status:** Plan-Vorschlag. Nichts davon wurde gestartet. VER-01 braucht ein Live-System (Windows-Start, Prozesse), GATE-01 braucht Lesen und gezielte Testläufe auf einem Branch.
**Erstellt:** 08.11.2026, Nachtlauf. Freigabe für jeden Lauf durch den Captain nötig; GPU-Läufe ausgeschlossen.
**Register:** SEDRA-GATE-01 (`INTEGRATION_REVIEW`), SEDRA-VER-01 (`INTEGRATION_REVIEW`).

---

## A. SEDRA-GATE-01 – Freigabe-Lücken (Sicherheitsprüfung)

**Gegenstand:** `request:harness_prozess` soll Klasse H haben; `APPROVE_STELLEN` soll `cli.py:_execute_runtime_command` statt `cli.py:main` nennen. Commit `9328f07` (lokal auf main oberhalb `eaeb4d3`; laut Register noch nicht gemerged).

**Nachweise laut Register:** GATE-01-1 bis GATE-01-3 in `01_STATUS/NACHWEISANFORDERUNGEN_2026-11-06.md` (liegt im Coder-Paket, Pfad im Register angegeben). Diese Datei wurde im Nachtlauf nicht neu geöffnet; die Punkte sind hier nur als Plan geführt, bis sie gelesen sind.

### A1. Lesen (kein Lauf)

1. `runtime/src/sedra_runtime/desk/freigabeklasse.py` – Klasse von `request:harness_prozess` und Eintrag `APPROVE_STELLEN`.
2. `runtime/src/sedra_runtime/desk/cli.py` (Funktionen `_execute_runtime_command` und `main`) – prüfen, ob jede Freigabe-Stelle wirklich nur über den dort genannten Pfad erreicht wird.
3. Suche nach allen Aufrufern von `approve`, die nicht über `_execute_runtime_command` laufen (Grep über `runtime/src`).

### A2. Gezielter Test (Branch, keine Integration)

- `python benchmarks/selbsttest.py` mit Gruppe für `test_freigabe_vollstaendig` (17 Fälle, laut Register 17/17 grün auf `2b13daa`).
- Zusätzlich: ein Test, der die Klassenzuordnung `request:harness_prozess = H` als Fehlerfall prüft, falls er fehlt (nur Plan, nicht schreiben ohne G3).

### A3. Abnahme

- Alle drei Nachweispunkte GATE-01-1 bis GATE-01-3 belegt, jeweils mit Datei und Zeile.
- `test_freigabe_vollstaendig` grün auf dem Merge-Kandidaten.
- Eintrag Updater-Logbuch (M1) und Captain-Gate (G4). Ohne diese Freigabe bleibt der Status `INTEGRATION_REVIEW`.

### A4. Risiken

- Die Freigabe-Logik betrifft alle Harness-Läufe. Ein falscher Fix sperrt legitime Läufe. Deshalb nur mit Captain-Freigabe integrieren.

---

## B. SEDRA-VER-01 – Windows-Live-Lauf F0-Start und `--replace`

**Gegenstand:** Harness-Shell unter Windows aus dem F0-Worktree (`5822faf`). Erststart, Zweitstart ohne `--replace` (muss verweigern), Zweitstart mit `--replace` (muss beenden und neu starten).

**Stand laut Register:** Konsolenausgaben vom 06.11.2026 ohne Belegfile. Erststart mit `--open` lief; Zweitstart ohne `--replace` mit Code 3 und PIDs; mit `--replace` beide Prozesse beendet und neu gestartet. Grenzen: Stand vor F0-05; kein Worker- und Modelllauf; SQLite-Warnungen nicht untersucht.

### B1. Vorbedingungen (vor dem Lauf prüfen, kein Start)

1. Kein laufender `llama-server` und kein Build auf der GPU (Prozessliste prüfen; der GPU-Bau `devvm_build_factory_sdk_grundlage` läuft seit 21:24 am 08.11.2026).
2. Worktree `5822faf` existiert und ist sauber (`git -C <worktree> status --short`).
3. Vorab-Beleg: Konsolenausgaben in eine Datei sichern (der Stand vom 06.11. ist nicht gesichert).

### B2. Ablauf (erst nach Captain-Freigabe)

| Schritt | Befehl (Platzhalter) | Erwartung |
|---|---|---|
| 1 | Erststart mit `--open` | Harness startet, PID notiert |
| 2 | Zweitstart ohne `--replace` | Verweigerung, Code 3, PIDs der laufenden Instanz im Text |
| 3 | Zweitstart mit `--replace` | Laufende Instanz beendet, neuer Start, neue PID |
| 4 | Prozessliste nach Schritt 3 | Genau eine Harness-Instanz |
| 5 | Ohne `--open` starten | Endet mit eigenem Fenster nach ca. 3 s (bekannt, notieren) |

Befehle exakt aus der Harness-Dokumentation übernehmen (nicht hier erfinden). Jede Ausgabe in eine Datei `VER-01_<Datum>_<Schritt>.txt` schreiben.

### B3. Abnahme

- Schritte 2 und 3 wie erwartet, mit gespeicherter Ausgabe als Beleg.
- Dann erst Status `MERGED`/`MAIN_VERIFIED` durch den Captain (nicht durch diesen Plan).

### B4. Nicht Teil von VER-01

- Worker- und Modelllauf, GPU, Browser-Bahn: gehören zu F0-05E.
- SQLite-Warnungen: F0-06A.

---

## C. Gemeinsame Regeln

- Kein Lauf ohne Captain-Freigabe im Chat.
- Keine GPU-Läufe, solange der Bau läuft.
- Kein Commit, kein Push, kein Merge durch diesen Plan.
