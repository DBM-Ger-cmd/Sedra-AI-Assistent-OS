# SPEC Dynamische Rezepte v1 – G2 Design (30.10.2026)

Grundlage: `SPEC_DYNAMISCHE_REZEPTE_v1_G1.md`. **G1 freigegeben vom Captain am 30.10.2026**, DQ-1 bis DQ-5 wie vorgeschlagen (erst mehr Lagen im RAM, dann kleinerer Kontext; von selbst langsamer laden, die Zahl wird immer genannt; Messwerte merken und bevorzugen; erst MoE-Modelle; die Rechenmodule als SEDRA-Bau, Einbau durch Claude). Nichts gebaut; diese Datei ist G2.

## 1. Ablauf heute und danach

Heute: `role_routing._candidate` schätzt aus festen Rezeptwerten (`min_ram_gb`, `measured_vram_gb`, `model_size_gb`, KV-Rate) → `runtime._resource_load_check` fragt `resource_scheduler.explain` → bei „passt nicht“ `hardware_pressure` ohne Zahlen. Geladen wird mit dem **festen** `profile.server.n_cpu_moe` und dem Kontext der Stufe (`model_loader.ensure` → `llama_server_runtime`).

Danach: Zwischen Schätzung und Laden steht **eine Auswahl** (`models/aufteilung.py`), die aus Rezept und jetzt freiem Speicher die Einstellung wählt. Dieselbe Auswahl beantwortet die Vorprüfung (passt es überhaupt?) und bestimmt, womit der Lader startet. Ohne Dynamik-Block im Rezept läuft alles wie bisher (DR-02).

## 2. Das Rezept (Schema, nur Erweiterung)

Neuer optionaler Block in `profile`:

```yaml
profile:
  server: {n_cpu_moe: 28, …}               # bleibt: Vorgabe, wenn nichts anderes gewählt wird
  dynamisch:
    n_cpu_moe: {min: 24, max: 40}           # Spanne der Lagen im RAM (je mehr, desto weniger VRAM, desto langsamer)
    tabelle:                                # Messwerte aus moe_sweep (VRAM der Gewichte plus Rechenpuffer bei Kontext `bei_kontext`)
      bei_kontext: 32768
      punkte:
        - {lagen: 28, vram_gb: 10.5, tokens_s: 45.0}
        - {lagen: 32, vram_gb: 9.1,  tokens_s: 41.7}
        - {lagen: 36, vram_gb: 7.6,  tokens_s: 38.5}
        - {lagen: 40, vram_gb: 6.1,  tokens_s: 35.5}
    vram_fix_gb: 1.5                        # KV-Cache und Rechenpuffer bei `bei_kontext` (nicht von den Lagen abhängig)
    ram_aufschlag_gb: 1.5                   # Prozess, Puffer, Seitenabbild des Servers
    ram_untergrenze_gb: 8                   # nie weniger als das ansetzen (das alte min_ram_gb als Boden)
```

Prüfung beim Laden der Datei (`role_routing`): Spanne ganze Zahlen mit `min ≤ max`, mindestens zwei Messpunkte innerhalb der Spanne, `vram_gb` fallend mit steigenden Lagen, alle Zahlen endlich und ≥ 0; sonst gilt das Rezept als ungültig mit Grund (kein stilles Zurückfallen). Rezepte in `local_config` ändert nur der Captain (DR-08); die Zahlen des Befunds (`n_cpu_moe` 30, 9,8 GB) setzt er oder genehmigt sie ausdrücklich.

## 3. Die Rechenmodule (SEDRA-Bau, rein, ohne Dateizugriff)

`models/aufteilung.py`, zwei Funktionen (je höchstens 12 versteckte Prüfungen, L3):

**`bedarf(dyn, lagen, kontext, kv_rate_gb_je_1k, groesse_gb, slots=1) -> {vram_gb, ram_gb}`**

- `vram_tabelle(lagen)`: lineare Zwischenwerte zwischen den Messpunkten; außerhalb der Messpunkte (aber in der Spanne) Fortschreibung mit der Steigung der nächsten zwei Punkte; außerhalb der Spanne `ValueError`.
- `vram_gb = vram_tabelle(lagen) + kv_rate · (kontext·slots − bei_kontext) / 1000` (KV-Unterschied zur Messung, nie negativ gerechnet, wenn der Kontext kleiner ist: dann wird gutgeschrieben, aber höchstens `vram_fix_gb`).
- `gewichte_im_vram = vram_tabelle(lagen) − vram_fix_gb`; `ram_gb = max(ram_untergrenze_gb, groesse_gb − gewichte_im_vram + ram_aufschlag_gb)`.

**`waehlen(dyn, kontexte, frei_vram_gb, frei_ram_gb, reserve_vram_gb, reserve_ram_gb, kv_rate_gb_je_1k, groesse_gb, slots=1, gemessen=None) -> Auswahl`**

- `kontexte`: die Stufen des Rezepts, größte zuerst, nicht unter dem Mindestkontext.
- Reihenfolge (DQ-1): für jeden Kontext von groß nach klein: die **kleinste** Lagenzahl der Spanne (= schnellste), für die `vram_gb ≤ frei_vram_gb − reserve_vram_gb` **und** `ram_gb ≤ frei_ram_gb − reserve_ram_gb`; gibt es keine, nächster (kleinerer) Kontext.
- `gemessen` (DR-07): Wörterbuch `{(lagen, kontext): {vram_gb, ram_gb}}` aus früheren Ladevorgängen; ein vorhandener Messwert ersetzt die Rechnung für genau diese Kombination.
- Rückgabe bei Erfolg: `{ok: True, lagen, kontext, vram_gb, ram_gb, tokens_s (aus der Tabelle, falls bekannt), grund: „kleinste Lagenzahl, die in den freien Speicher passt“, verglichen: [(kontext, lagen, vram, ram)…]}`; bei Misserfolg: `{ok: False, fehlt: {vram_gb, ram_gb} (größter Mangel der besten Kombination), beste: {kontext, lagen, vram, ram}, vorschlag: Satz}` – der Vorschlag nennt die nächstbeste Möglichkeit (kleinerer Kontext, Programme beenden, kleineres Rezept) mit Zahlen (DR-04).
- Grenzen sind harte Obergrenzen (DR-08): `frei_vram_gb − reserve_vram_gb` ist nie größer als die VRAM-Grenze des Captains (11,5 GB inkl. Reserve); die Reserven kommen aus `resource_scheduler.yaml`, nicht aus dem Rezept.

## 4. Einbau (Claude)

| Stelle | Änderung |
|---|---|
| `models/role_routing.py` | Dynamik-Block prüfen und ins Rezept übernehmen (`profile.dynamisch`); `_candidate` ruft für ein dynamisches Rezept `aufteilung.waehlen` mit dem Speicherstand und meldet bei Misserfolg `no("pressure", Satz mit Zahlen)` statt eines festen Codes; bei Erfolg trägt die `estimated` die gewählten Zahlen und die Auswahl (`estimated["auswahl"]`). |
| `runtime._resource_load_check` | reicht den Speicherstand (`resource_scheduler._host`) an die Auswahl; bei dynamischen Rezepten ersetzt deren Antwort die feste Prüfung. |
| `models/model_loader.ensure` | wählt **unmittelbar vor dem Start** noch einmal mit frischen Zahlen (der Stand kann sich seit der Vorprüfung geändert haben); die Auswahl überschreibt `n_cpu_moe` und den Kontext des Starts (Wert wird über `llama_server_runtime` weitergereicht); der Start bleibt ein einzelner Server. |
| `uix_server.load_model` | Antwort von `POST /api/model/load` enthält `auswahl` (`lagen`, `kontext`, `vram_gb`, `ram_gb`, `tokens_s`, `grund`); das Audit bekommt `MODEL_LOAD_CHOICE` mit denselben Zahlen. |
| `models/messwerte.py` (neu, klein) | nach dem Laden Messwert (`nvidia-smi`, Prozess-RAM) je `(Rezept, lagen, kontext)` nach `runtime_data/model_messwerte.json` (atomar, höchstens 200 Einträge, nie ins Rezept). |
| `uix/shells/harness/modell.js` | zeigt nach dem Laden eine Zeile „lädt mit 30 Lagen im RAM, 65 536 Kontext, ≈ 9,8 GB VRAM, 8 GB RAM (kleinste Lagenzahl, die passt)“; bei Ablehnung den Satz mit den Zahlen aus `auswahl.vorschlag`. |

## 5. Ablehnung mit Zahlen (DR-04)

Beispiel (Stand 29.10., 10,85 GB VRAM und 14,3 GB RAM frei, Reserven 0,7 und 1,5 GB, Qwen3.6): „Brauche bei 28 Lagen im RAM 10,5 GB VRAM und 9,7 GB RAM; frei sind 10,15 GB und 12,8 GB (nach Reserve). Mit 30 Lagen: 9,8 GB und 10,5 GB – passt. Gewählt: 30 Lagen, rund 7 % langsamer.“ Passt nichts: „Es fehlen 0,6 GB VRAM bei 40 Lagen im RAM und 8 192 Kontext. Nächstbeste Möglichkeit: Programme mit Grafikspeicher beenden (Chrome belegt 0,6 GB) oder das Rezept coder.local_qwen3_5_9b_q6_k laden.“

## 6. Tests und Abnahme

- **Rein** (versteckt, SEDRA-Bau): Interpolation, Fortschreibung, Spanne, KV-Unterschied, kleinste passende Lagenzahl, Kontextstufen von groß nach klein, Messwert ersetzt Rechnung, Ablehnung mit Zahlen und Vorschlag, Reserven und Obergrenzen, Eingaben mit `NaN`/negativ/fehlend.
- **Referenz** von Claude (`benchmarks/devvm_refs/…`) und ein Vergleichstest wie bei `aufgabe_deckung`; Prüfungen im `HIDDEN`; Abnahme der Zahlen des Befunds als Testfall (Qwen3.6, 10,85/14,3 GB frei → 30 Lagen).
- **Einbau**: Tests für Rezeptprüfung, `_candidate` mit Attrappe des Speicherstands, Lader mit Attrappe des Servers (übergibt `n_cpu_moe` und Kontext), Messspeicher, Antwort und Audit.
- **Mit Modell (P-Aufträge, nur auf Ansage des Captains in der Bau-Sitzung):** Qwen3.6 mit dynamischem Rezept bei verschiedenen freien Speichern laden (Chrome offen/zu); gemessener VRAM/RAM gegen die Rechnung; Tempo je Lagenzahl gegen die Tabelle.
- Browser-Abnahme der Modell-Zeile mit Playwright (wie Stufe 6).

## 7. Entscheidungen des Captains (offen)

| Nr | Frage | Vorschlag |
|---|---|---|
| D-R1 | Rezept-Schema wie §2 (`profile.dynamisch` mit Spanne, Tabelle, Aufschlägen) | ja |
| D-R2 | Messpunkte für Qwen3.6 aus `moe_sweep` vom 9.10. (28/32/36/40 Lagen), `vram_fix_gb` 1,5 und `ram_aufschlag_gb` 1,5 als Anfangswerte, danach von Messungen am PC korrigiert | ja; die Werte trägt der Captain in `local_config/role_routing.yaml` ein oder gibt ihre Anlage durch Claude ausdrücklich frei |
| D-R3 | Lader wählt unmittelbar vor dem Start noch einmal mit frischen Zahlen | ja |
| D-R4 | Messwerte nur in `runtime_data` merken, nie ins Rezept schreiben | ja |
| D-R5 | SEDRA-Bau der zwei Rechenmodule (`bedarf`, `waehlen`) mit Referenz von Claude; Einbau, Oberfläche und Tests der Anbindung durch Claude | ja |

## 8. Berechtigungen vorab

| Nr | Berechtigung | Zeitpunkt |
|---|---|---|
| P-D1 | Schreiben in `models/aufteilung.py`, `models/messwerte.py`, `models/role_routing.py`, `models/model_loader.py`, `models/llama_server_runtime.py` (nur Durchreichen), `runtime.py` (`_resource_load_check`), `uix_server.py` (Antwort, Audit), Tests | nach G2/G3 |
| P-D2 | Bau-Specs `devvm_specs/aufteilung.py`, Referenz `devvm_refs/aufteilung.py`, Prüfungen im `HIDDEN`, Bau-Spec `docs/BAUSPEC_AUFTEILUNG.md` | nach G2/G3 |
| P-D3 | `modell.js` und `shell.yaml` (Anzeige der Auswahl), Playwright-Abnahme | nach G2/G3 |
| P-D4 | Modell laden und SEDRA-Bau (Qwen3.6, danach Gemma als Prüfer) | **auf Ansage des Captains** in der Bau-Sitzung |
| **nicht** | `local_config/` ändern, Löschen, Push ohne Ja, Cloud-Modelle | außerhalb |

## 9. Nächste Gates

- **G2** (diese Datei): Captain beantwortet D-R1 bis D-R5.
- **G3** Bau-Aufgaben (R1 Rezeptprüfung und Referenz, R2 SEDRA-Bau `aufteilung`, R3 Einbau Routing und Lader, R4 Messspeicher, R5 Antwort, Audit, Oberfläche, R6 Abnahme), danach **G4** Abnahme mit Modell am PC.
