# Nachtrag: offene Punkte aus Stufe 3 und 4 (30.10.2026)

Captain 30.10. 07:53: „halt, mach bitte erst die offenen Punkte, dann Stufe 5“. Branch `harness/stufe-5` (auf `harness/stufe-4`); Stufe 5 ruht
(G3 nur Entwurf). Ohne Modell, ohne lokale Daten des Captains.

## Erledigt

| Punkt (Quelle) | Was war | Was ist |
|---|---|---|
| **Befund 7, Stufe 3:** ein laufender `befehl` wird bei der Rücknahme einer Aufgabe nicht abgebrochen (G2 §4.4) | nur Läufe wurden gestoppt; `befehl` lief bis zum eigenen Abbruch oder Zeitlimit | `harness/befehl.py`: `RUECKNAHME` (ein Ereignis je Aufgabe); `ausfuehren(…, aufgabe_id=…)` beendet den Prozess mit Status `zurueckgenommen` („AUFGABE ZURÜCKGENOMMEN“ in der Werkzeugzeile, nach außen `abgebrochen`); `werkzeuge.py` gibt die `aufgabe_id` aus dem Kontext mit; `api.py` löst es bei `POST aufgaben/<id>/zuruecknehmen` aus. Tests: `test_harness_werkzeuge` (+2), `test_uix_harness_aufgabe` (Ereignis gesetzt) |
| **`test_k5`/`test_k8` unter Last** (Stufe 3, Befund K5) | Backlog 5 des UIX-Servers; Fix `request_queue_size = 64` lag auf `main`, die Nachprüfung unter Last stand aus | hier wiederholt: **8 parallele Prozesse** von `test_uix_cockpit_baum -k "k5 or k8"` → 8 × 2 bestanden (16/16, je 128–135 s) – unter Linux mit Chromium; unter Windows nicht erneut gemessen |
| **Bekannt rot `test_uix_flows.Build24.test_paperclip_new_project_and_the_workplace_answers`** (`known_red.txt` seit 25.10.) | der Test erwartete „kein Routinen in der Paperclip-Navigation“ (Regel Build 24); seit Spec 4 (G2-S4-01) steht „Routinen“ bewusst dort und das Werkzeug `routines` gibt es | Erwartung im Test berichtigt (Routinen da, KI GateWay nicht); Test grün; `known_red.txt` leer |
| Nebenbefund K5: `test_uix_shell_start` erwartet alte Shell-Liste | | war schon auf `main` behoben (`dcb3d43`) – nichts zu tun |

## Nicht hier möglich (brauchen den PC des Captains oder ein Modell)

- **G4 Stufe 4:** Prüfung mit RTX und LibreHardwareMonitor (Start-Menü, App, GPU-Zelle mit Temperatur und Quelle, Wechsel Cockpit und zurück).
- **S3-C mit Modell** (Stufe 3): im Skriptlauf nur einzeln bestanden – Wiederholung mit Qwen3.6 nach Ja.
- **Vergleich des zweiten N8-Kandidaten** (`runtime_data/devvm_candidates/harness_lauf_fortschritt/attempt_01_20261029_153441/`): die Datei liegt nur auf dem PC.
- **`test_k5` unter Last unter Windows** – hier nur Linux geprüft.

## Offene Entscheidungen (Captain), aus den Plänen

- `PLAN_USB_STICK_v1`: **16** Hintergrundbetrieb auf dem Stick (Vorschlag aus), **17** Einmal-Aufruf nur gegen laufendes SEDRA (Vorschlag ja),
  **18** Wissen in der Harness als Werkzeug + automatischer Block (Vorschlag beides), **19** Grundwissen auf dem Stick, **20** erwartete Größe des Wissens.
- `PLAN_PI_HERDR_ABGLEICH_v1`: **PQ-1** eigene Spec oder Nachträge, **PQ-2** `SEDRA.md`/`AGENTS.md`, **PQ-3** Hintergrundbetrieb, **PQ-4** wer baut Stufe A,
  **PQ-5** welcher fremde Agent zuerst, **PQ-6** was in `switches.yaml` an ist.
- Übergabe §4: Web-Browser G2 (eigene Linie), Wunsch-Anbindung G2, alte Spec-Punkte (Spec 1/2/3/7) – jeweils eigene Linien, nicht Teil der Harness-Stufen.
