# Verlauf des Vorarbeiters, 20. bis 25.10.2026

Nachschlagedatei für spätere Rückfragen: was entschieden, gebaut, gemessen und übernommen wurde, mit Commit und Fundstelle. Maßgeblich bleiben die Spec (`SPEC_AGENTEN_ORCHESTRIERUNG_v1.md`, Abschnitt „Entscheidungen des Captains“) und das Logbuch (`LOGBUCH_AGENT_MANAGER.md`); diese Datei fasst nur zusammen und sagt, wo man sucht. Branch `spec/agenten-orchestrierung` (GitHub `DBM-Ger-cmd/Sedra-AI-Assistent-OS`), Stand bei Abschluss `8cafc18`.

Suchtipp: `git log --oneline --first-parent` zeigt jeden Schritt; Gate-IDs (z. B. `G3-S2`, `HALT 3`, `PIPE-14`, `U-4`) stehen wörtlich in Spec, Logbuch und Commit-Texten.

## 1. Arbeitsweise

- Spec-getrieben: G1 Anforderungen → G2 Design → G3 Aufgaben/Bau-Specs → G4 Übernahme; jedes Gate entscheidet der Captain einzeln.
- Produktionscode neuer reiner Module baut SEDRA lokal aus Bau-Specs mit versteckten Tests (`docs/SO_WIRD_GEBAUT.md`); KI-Sitzungen schreiben Specs, Tests, Referenzen und den Harness. Ausnahme Spec 7: Cloud-Bau übernommen (Entscheidung des Captains).
- Review jedes Kandidaten (meist eigener Opus-Agent), Übernahme per Handkopie mit Logbuch.
- Sitzungen in der Sidebar-Gruppe „Sedra Vorarbeiter“, je eigener Worktree. Regeln zur Aufteilung siehe Abschnitt 9.

## 2. Spec 1 – Orchestrierung

| Schritt | Ergebnis | Commit |
| --- | --- | --- |
| SEDRA-Bauten s1_* Runde 1/2, PIPE-12 (Tests geschärft) | graphs, decompose, board, messages, routines, runner, org, budget übernommen; Korrekturen bei der Handkopie (decompose blocker, runner URL, board delegate) | `c41074d` |
| PIPE-13 | Saat auf SEDRA-Fassungen | `8d4e82b` |
| PIPE-14 | cron: zwei Neubauten gescheitert, Referenz-Fassung bleibt (V4) | `eb5feb7` |
| S1.H6 | Fassade, tick.py, Takt-Thread | `c4a7568` |
| S1.H7 | Desk-Verben, Felder, gespraech; HALT 1 (Dauerfreigabe über gated.py nur für `standing`), HALT 2 (Nutzung bleibt bei gescheitertem Start verbraucht, ein Wiederholungsversuch), HALT 3 (einstellen in zwei Anträgen, Weg B), Zulassung vor dem ersten Lauf | `1fd121c`, `bd11a8d`, `29fb89f`, `0ae5f1d`, `516ca41` |
| S1.H8 | Agentenlauf `orchestra_runner.py`, Rollen foreman/researcher, Vorlagen mit Abnahme-Suite; Punkte 2–7 angenommen | `90e1a59`, `4561867` |
| Offen | S1.H9 Abnahme; Läufe werden erst mit dem Worker-Pool (S2.H4b) abgearbeitet | – |

## 3. Spec 2 – Modell-Scheduler

| Schritt | Ergebnis | Commit |
| --- | --- | --- |
| G2 (D2.1–D2.13), G3 | freigegeben; VRAM 11,5 GB inkl. Reserve 0,7 (nutzbar 10,8) | `7149f41`, `94cec85` |
| S2.H0, S2.C1 | Messwerkzeuge, `jobs/vramplan.py` | `044bcf8` |
| SEDRA-Bauten | `jobs/slotplan.py` (+ Konstanten), `jobs/slot_store.py` nach zwei Nacharbeiten (264 statt 506 Zeilen), `jobs/slot_db.py` | `90fc6f6`, `851c7ca` |
| Messung S2.1 (Nacht 22./23.10.) | Hauptmodell 1 Slot 31,6 tok/s → 4 Slots 49,9; Hilfsmodell 70 → 155,7; Engine meldet Fenster je Slot | `35b0c96`, `docs/MESSBERICHT_SLOTS_2026-10-23.md` |
| Standard-Slotzahl | 2 Slots je Modell, MTP ab 4 Slots aus | `9a41b61` |
| S2.H2 | Rezeptfelder `slots`/`per_slots` (aus Cloud-Branch einzeln übernommen) | `d6d25ca` |
| Nachmessung 24.10. | teilweise (Windows um 15:34 heruntergefahren): Hauptmodell 2 Slots bis 65536, 3 Slots bis 32768 sicher; Werkzeug schreibt jetzt Zwischenstände | `7b6f6b9` |
| S2.H1, S2.H3, S2.H4a | testlab Schema 2, `jobs/model_scheduler.py` (Schalter aus, `enabled: true` bis S2.H5 gesperrt), Supervisor workers 1..8 | `821e271` |
| Offen | Rest-Nachmessung (Hauptmodell 4 Slots, Hilfsmodell 2–4 Slots, 2–3 h GPU); S2.H4b Worker-Pool, S2.H5–H7 | – |

## 4. Spec 3 – Cloud-Coder und Coder-Verbund (Nachtrag)

- Richtung (b): Cloud nur als Ausweichstufe für Coder-Agenten, nur mit Entscheidung des Captains je Lauf, nur Anbieter ohne Training; SEDRA-Bauten bleiben lokal (`4c07415`).
- G1-S3C-01..17 mit Guard-Aktionen `cloud_call`, `start_verbund`; Antworten 1–5: Slots desselben Modells genügen, Tests immer von anderem Modell, Startphase nur Mammouth, Plan-Freigabe ersetzt Einzelfreigaben nicht, Ausschlussliste für Cloud-Pakete inkl. versteckter Tests (`c97eccf`, `94cec85`).
- Offen: Mammouth-Bedingungen lesen (Captain, nach Anmeldung), danach Design.

## 5. Spec 4 – Shell D

Dialog „Einstellen“ auf `instance_id` umgestellt (HALT 3 B), `cb8a17e`.

## 6. Spec 7 – Wissen und RAG

| Schritt | Ergebnis | Commit |
| --- | --- | --- |
| G1 (WIS-01..13) | freigegeben | `0155a83` |
| S7.1 Messung | BGE-M3 hybrid Treffer@5 77,5 % (Wortsuche 57,5 %), 15 s/1000 Abschnitte GPU, +1 GB VRAM; Qwen3-Embedding verworfen | `4c37d55` |
| Übergabe an zweiten Account | Zip mit Anleitung und Kern-Auszug; Branch gepusht | `f45047f` ff. |
| G2-S7 (mit zweitem Account), G3-S7 | bestätigt: BGE-M3, Ziel 85 %, Mindest 80 %, Einbetten bis Spec 2 nur CPU; Abnahmesatz 120 Fragen | `da5af0a` |
| Cloud-Bau übernommen | Paket `wissen/`, Werkzeug `wissen`, S1-F-RECHERCHE-TRUST; SEDRA-Vergleichsbauten wis_* je an Stufe 3 gescheitert | `090dc3f`, `fc2d218` |
| Patches 23.10. | Befunde F1–F11, S7.6 Stufe A | `e87da76` |
| Auflagen zusammengeführt | zwei parallele Cloud-Fassungen vereint, `speicher.py` aufgeteilt (331 Z.), Review-Befund B1/B2 behoben | `6eb23a3` |
| Abnahmesatz | Knowledge-Fragen auf die 8 vorhandenen Lektionen umgeschrieben, versiegelt SHA-256 `bae43a02…` | `03c5830` |
| Offen | Schalter `wissen` bleibt aus; Erstbestückung, S7.2-F, Abnahme S7.5 | – |

## 7. Installation, Rezepte, GPU

- `gpu_preflight`-Grenze 2,5 → 3,0 GiB (`d55c431`).
- Live-Rezepte (`<guppi>/workspace/GUPPI_OS/local_config/role_routing.yaml`, nicht in git, Sicherungen `.bak-2026-10-24-s21`, `.bak-2026-10-25-slots`, `.bak-2026-10-25-stufe65536`): Hilfsmodell maximum 98304; Hauptmodell measured_maximum 131072, neue Stufe 65536, `slots: 2`, `per_slots {2: 65536}`; Hilfsmodell `slots: 2`, `per_slots {2: 16384}`.
- Umstieg der Installation (Plan `docs/UMSTIEG_INSTALLATION_PLAN_2026-10-24.md`, U-1..U-6): Weg G, Installation auf Branch `betrieb/a1-74de39e` (verfolgt `a1/spec/agenten-orchestrierung`), Push gesperrt; Rückweg `installation/stand-2026-10-24`. doctor READY, Tests und uix_check grün, Kurzstart 2 Slots × 65536 bestanden (`6311ba1`).
- VRAM-Grundlast der NVIDIA-Karte rund 1 GB, größter Posten `dwm` (Monitor an der NVIDIA-Karte).

## 8. Aufräumen `E:\Sedra Umgebung`

Index und Plan in `_Aufraeumen_2026-10-24/` (außerhalb des Repos). Sicherungen: Bundle der alten Installation mit allen Refs, Bundle `build25-basis`, Diffs. Archiv `SEDRA_Archiv_bis_2026-10-24.zip` (589 Dateien, dedupliziert, Manifest, verifiziert). Löschen macht der Captain nach `ZUM_LOESCHEN_DURCH_CAPTAIN.md` (Claude darf nicht löschen, auch nicht in den Papierkorb).

## 9. Arbeitsregeln für Sitzungen und Agenten (Captain, 25.10.2026)

1. Eigene Sitzung für lange Linien mit Folgeaufträgen (Harness-Schritte, Spec-Phasen, Messung + Auswertung).
2. Subagent für einmalige Prüfungen (Reviews, Abgleiche).
3. Höchstens 2–3 schreibende Sitzungen gleichzeitig, jede im eigenen Worktree; Logbuch-Konflikte löst der Vorarbeiter beim Merge.
4. Sonnet für Mechanisches, Opus für Design, Reviews, Zusammenführungen.
5. Vorarbeiter-Kontext rechtzeitig verdichten; Neustart mit dieser Datei als Einstieg.

## 10. Offene Punkte bei Abschluss (25.10.2026)

- Captain: Löschen nach Liste; Ordner `E:\e` (versehentlich angelegt) löschen; Rest-Nachmessung terminieren.
- Spec 2: S2.H4b Worker-Pool, S2.H5–H7, Rest-Nachmessung, danach `per_slots` Hilfsmodell.
- Spec 1: S1.H9 nach dem Worker-Pool.
- Spec 3: Mammouth-Bedingungen, Design.
- Spec 7: Einschalten erst nach Erstbestückung und Abnahme S7.5.
- Pipeline-Lehre: Bau-Specs aus der Cloud (wis_*) waren für das lokale Modell deutlich schwerer (alle an Stufe 3 gescheitert) – Ursache (Aufgabentexte oder Schwierigkeit) prüfen.
