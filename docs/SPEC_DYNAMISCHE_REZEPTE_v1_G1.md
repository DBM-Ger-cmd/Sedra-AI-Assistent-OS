# SPEC Dynamische Rezepte v1 – G1 Anforderungen (30.10.2026)

Auftrag des Captains 29.10.2026 („die Rezepte sollten beim RAM dynamischer werden“). Nichts gebaut; diese Datei ist G1.

## 1. Befund (Messung am PC, 29./30.10.2026)

Ein Rezept legt feste Zahlen fest: `requirements.min_ram_gb`, `measured_vram_gb`, `n_cpu_moe`, Kontext. Ob es lädt, entscheidet ein Vergleich dieser festen Zahlen mit dem **jetzt** freien Speicher (`resource_scheduler._decide`: `ram_available − ram_reserve ≥ need`, `vram_available + resident − vram_reserve ≥ need`). Am 29.10. lud `coder.local_primary` (Qwen3.6-35B-A3B, 17,7 GB) so nicht:

| Wert | Rezept | tatsächlich | Folge |
|---|---|---|---|
| RAM | `min_ram_gb: 18` | etwa 7 bis 10 GB (Gewichte 17,7 − 9,3 in der GPU, dazu Kontext und Aufschlag); frei waren 14 bis 16 GB | `hardware_pressure` / `ram_measured`, obwohl es passt |
| VRAM | `measured_vram_gb: 10,4` bei festem `n_cpu_moe: 28` | frei 10,85 GB, nötig 10,4 + 0,7 Reserve | `vram_insufficient`, es fehlten 0,25 GB |
| Abhilfe | von Hand: `min_ram_gb` 12, `n_cpu_moe` 30, `measured_vram_gb` 9,8 in `local_config/role_routing.yaml` | Laden gelang mit 9,3 GB Grafikspeicher | Zahlen geschätzt, nicht gemessen |

Ursache: Das Rezept kennt **eine** Aufteilung zwischen Grafikkarte und Arbeitsspeicher. Bei MoE-Modellen ist diese Aufteilung aber einstellbar (`n_cpu_moe`: je mehr Expertenlagen im RAM, desto weniger VRAM und desto langsamer; Messung `moe_sweep`: 28 → 40 Lagen sparen 4,4 GiB VRAM, kosten rund 20 % Tempo). Der Rechner hat 12 GB VRAM und rund 31 GB RAM, aber nie beides vollständig frei.

## 2. Ziel

Ein Rezept nennt **Spannen und Messwerte**, nicht eine feste Aufteilung; beim Laden wählt SEDRA die Aufteilung, die zum jetzt freien Speicher passt, und nennt dem Captain Zahlen und Folgen. Wo es nicht passt, sagt es genau, was fehlt und was die nächstbeste Möglichkeit ist.

## 3. Anforderungen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| DR-01 | Der RAM-Bedarf eines Rezepts wird **berechnet**, nicht als feste Zahl gelesen: `ram = Gewichte außerhalb der Grafikkarte + Kontext (KV, wenn im RAM) + Aufschlag des Servers`. Eingaben: `model_size_gb`, die Aufteilung der Gewichte und die Kontextgröße. `min_ram_gb` bleibt als **Untergrenze** (nie weniger als das), nicht als Soll. | Test mit Zahlen des Befunds: Qwen3.6 braucht bei `n_cpu_moe` 28 unter 12 GB |
| DR-02 | Rezepte mit einstellbarer Aufteilung (MoE: `n_cpu_moe`) tragen eine **Spanne** (`n_cpu_moe: {min, max}`) und eine **Messtabelle** (`moe_sweep`: Lagen → VRAM, Tempo). Ohne Messtabelle bleibt der feste Wert (heutiges Verhalten). | Test: Rezept ohne Tabelle verhält sich wie bisher |
| DR-03 | Beim Laden wählt der Lader die **kleinste** Zahl Lagen im RAM (= schnellste Einstellung), bei der VRAM und RAM zum jetzt freien Speicher passen (jeweils mit den Reserven des Ressourcen-Schedulers). Passt keine Zahl der Spanne, wird nicht geladen. | Test mit Attrappe des Speicherstands |
| DR-04 | Abgelehnt wird mit **Zahlen**: „braucht X GB VRAM und Y GB RAM bei Einstellung Z; frei sind A und B; es fehlen …“ und dem Vorschlag der nächstbesten Möglichkeit (anderer Kontext, kleineres Rezept, Programme beenden). Kein bloßes `hardware_pressure`. | Test des Satzes |
| DR-05 | Der Kontext ist eine **zweite Stellschraube**: Stufen des Rezepts (`context.tiers`) werden von groß nach klein probiert, bis der Speicher passt; der Mindestkontext des Rezepts gilt als Untergrenze. | Test |
| DR-06 | Was tatsächlich geladen wurde (Lagen im RAM, Kontext, erwarteter und gemessener VRAM/RAM, Grund der Wahl) steht im Audit und in der Antwort von `POST /api/model/load`; die Oberfläche zeigt es im Modell-Hinweis („lädt mit 30 Lagen im RAM, 65 536 Kontext, ≈ 9,8 GB VRAM, 8 GB RAM“). | Test, Oberfläche |
| DR-07 | Das **gemessene** Ergebnis nach dem Laden (`nvidia-smi`, Prozess-RAM) wird je Rezept und Einstellung gemerkt (`runtime_data`), nicht ins Rezept geschrieben; spätere Entscheidungen bevorzugen Messwerte vor Schätzungen. Rezepte (`local_config`) ändert nur der Captain. | Test |
| DR-08 | Feste Vorbehalte bleiben: eine Aufteilung außerhalb der Spanne, mehr als die VRAM-Grenze des Captains (11,5 GB inkl. Reserve) oder weniger als die RAM-Reserve (1,5 GB) wird **nie** gewählt, auch wenn das Modell sonst nicht lädt. | Test der Grenzen |
| DR-09 | Nur ein Modell zurzeit auf der Grafikkarte (wie heute); der Wechsel entlädt vorher. Läufe mit `gpu: exklusiv` bleiben unverändert. | bestehende Tests |

## 4. Abgrenzung

- Kein automatisches Messen (`moe_sweep`) beim Laden; die Messtabelle kommt aus den vorhandenen Messläufen und vom Captain.
- Keine Änderung der Rollen-Auswahl (welches Modell für welche Rolle) und keine Cloud.
- Dichte (nicht-MoE) Modelle behalten eine feste Aufteilung (alles oder Teile der Schichten über `gpu_layers`); eine Spanne für `gpu_layers` ist möglich, aber erst in G2 entschieden.
- Die Oberfläche bekommt nur die Zeile aus DR-06; keine neue Seite.

## 5. Entscheidungen des Captains (offen)

| Nr | Frage | Vorschlag |
|---|---|---|
| DQ-1 | Reihenfolge der Stellschrauben bei Speichermangel: erst weniger VRAM durch mehr Lagen im RAM (langsamer), dann kleinerer Kontext | erst Lagen im RAM bis zur Obergrenze der Spanne, dann Kontext verkleinern |
| DQ-2 | Darf das Laden von selbst langsamer laden (mehr Lagen im RAM), oder fragt SEDRA vorher? | **von selbst**, wenn die Spanne im Rezept steht; die Zahl wird immer genannt (DR-06) |
| DQ-3 | Messwerte (DR-07) in `runtime_data` merken und bevorzugen | ja |
| DQ-4 | Gilt das auch für dichte Modelle (`gpu_layers`)? | später, erst MoE (Qwen3.6) |
| DQ-5 | Bau durch Claude allein oder als SEDRA-Bau (reine Rechenmodule: Bedarf berechnen, Aufteilung wählen) | Rechenmodule als **SEDRA-Bau** (versteckte Prüfungen), Einbau in Lader und Oberfläche durch Claude |

## 6. Berechtigungen vorab (für G2/G3)

| Nr | Berechtigung | Begründung |
|---|---|---|
| PD-1 | Schreiben in `models/role_routing.py`, `models/model_loader.py`, `jobs/resource_scheduler.py` (nur Schätzung und Auswahl), neues Modul `models/aufteilung.py`, Tests | DR-01 bis DR-05 |
| PD-2 | Schreiben in `uix_server.py` (Antwort von `/api/model/load`) und `uix/shells/harness/modell.js` | DR-06 |
| PD-3 | Lesen der Messläufe `moe_sweep_*` unter `runtime_data/measurements` | DR-02 |
| PD-4 | Modelle laden zur Prüfung (Qwen3.6, danach Gemma) | erst auf Ansage des Captains in der Bau-Sitzung |
| **nicht** | Ändern von `local_config/role_routing.yaml` (die Zahlen vom 30.10. stehen dort von Hand), Löschen, Push | außerhalb dieses Auftrags |

## 7. Nächste Gates

- **G1** (diese Datei): **freigegeben vom Captain am 30.10.2026**, DQ-1 bis DQ-5 wie vorgeschlagen. G2: `SPEC_DYNAMISCHE_REZEPTE_v1_G2.md`.
- **G2** Design (Formel, Spanne im Rezept-Schema, Aufbau von `aufteilung.py`, Messspeicher), **G3** Bau-Aufgaben, **G4** Abnahme mit Modell am PC.
