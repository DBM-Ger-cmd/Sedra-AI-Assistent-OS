# Baubericht Dynamische Rezepte (30.10.2026): R1 Bau-Spec, R2 SEDRA-Bau der Rechenmodule

Spec: `SPEC_DYNAMISCHE_REZEPTE_v1_G1.md`, `…_G2.md`, `…_G3.md`, `BAUSPEC_AUFTEILUNG.md`. Captain 30.10.2026: „lass SEDRA G3 bauen, wenn möglich“ (Ansage für den Modelllauf), danach „Du darfst ihn beenden“ (übrig gebliebener Modellserver, PID 34024).

## R1 (Claude): gebaut

`devvm_specs/modelle_aufteilung.py` (Aufgabe, 16 versteckte Prüfungen, L3 ≤ 20), Referenz `devvm_refs/modelle_aufteilung/aufteilung.py` (92 Zeilen), Bau-Spec. `spec_check` lint, Größe, Referenz ok, Stempel `--vm` (microVM, Python 3.12.15).

## R2 (SEDRA): zwei Bauversuche über die Harness, **nicht bestanden**

Weg: Vorarbeiter-Sitzung `S-2C1BABE6` (Qwen3.6-35B-A3B, `coder.local_primary`), Aufgaben-Freigabe `T-B68BE1EC` (nur `spec_check` und `devvm_build`, Modell `coder.local_primary`, 20 Aufrufe): Der Vorarbeiter startete beide Läufe, ohne Karte.

| Versuch | Prüfungen | Ergebnis |
|---|---|---|
| 1 (`L-C554A758`) | 14 | **bestanden** (536 s, 14 Aufrufe, 1 Agentenlauf, 0 Nacharbeiten, 0 Eskalationen), Kandidat 256 Zeilen |
| Review des Kandidaten | gegen die Referenz (3000 Fälle `waehlen`, 2000 Fälle `bedarf`) | Rechnung **identisch** (`bedarf` 2000/2000, Erfolgsfälle 432/432, beste Kombination im Fehlschlag gleich); **aber** `fehlt` enthielt in allen 2568 Fehlschlägen den ganzen Bedarf statt des Fehlbetrags, `vorschlag` war nur „Waehlen Sie Lagen=…“, und kaputte Eingaben lösten `KeyError`/`TypeError` statt `ValueError` aus (`gemessen` mit falschem Wert, `frei_vram=None`, Kontext „x“, `slots=0` ohne Fehler); Berechnung doppelt (in `bedarf` und `waehlen`), Interpolation dreifach, ein unerreichbares `return` |
| Befund zur Prüfung | – | **Meine versteckten Prüfungen waren zu schwach** (`fehlt > 0` statt der Zahl; keine Eingabefehler). Geschärft auf 16 Prüfungen (Fehlbetrag als Zahl, sieben Eingabefehler, Satz mit GB); der erste Kandidat fällt nun durch |
| 2 (`L-C2D41245`) | 16 | **nicht bestanden** (3831 s, 4 Agentenläufe, 67 Aufrufe, 3 Nacharbeiten, 0 Eskalationen), Kandidat 389 Zeilen: `fehlt` jetzt richtig (4,8 und 5,13 GB im Probefall), aber die Eingabeprüfung (Zeile 38) besteht er nicht |

**Ergebnis (V4):** Die Referenz von Claude bleibt und steht als `models/aufteilung.py` im Paket (Kopfkommentar nennt den Bau); `tests/test_models_aufteilung.py` lässt sie dieselben versteckten Prüfungen bestehen und prüft die Zahlen des Befunds (Qwen3.6, 10,65 GB VRAM und 14,3 GB RAM frei → 30 Lagen). Quote Claude/SEDRA: Referenz 92 Zeilen, Spec und Prüfungen etwa 100; SEDRA-Kandidat 256 bzw. 389 Zeilen – kein Gewinn an Aufwand.

**Was der Versuch lehrt:** (1) SEDRA trifft die Rechenlogik zuverlässig (Zahlen identisch), scheitert aber an Randverhalten (Eingabeprüfung, Fehlertyp) und liefert viel Wiederholung; (2) schwache versteckte Prüfungen lassen einen falsch gebauten Kandidaten bestehen – Prüfungen müssen die Rückgabewerte prüfen, nicht nur ihre Form; (3) der Vorarbeiter (Qwen3.6) erfand zweimal eine Lauf-ID, ohne das Werkzeug aufzurufen (HS-16 zählt das richtig nicht als erledigt) und tippte `modell_aufteilung` statt `modelle_aufteilung`; erst die ausdrückliche Aufforderung „Ruf das Werkzeug wirklich auf“ führte zum Aufruf; (4) nach `devvm_build` ist das Gespräch ohne Modell (exklusive GPU), es muss neu geladen werden.

## R3 bis R5 (Claude, 30.10.2026 abends): gebaut

| Nr | Ergebnis |
|---|---|
| R3 | `models/role_routing.py`: Rezeptblock `profile.dynamisch` wird beim Laden geprüft (`aufteilung.pruefen`, sonst Rezept ungültig mit Grund `profile.dynamisch`). `_evaluate` wählt für ein dynamisches Rezept mit dem freien Speicher von jetzt (`speicher_stand`) die kleinste Lagenzahl im RAM, die passt; reicht der Speicher nicht, erst ein kleinerer Kontext (nie über dem gewünschten und nie unter dem verlangten Mindestkontext), sonst `hardware_pressure` mit einem Satz mit Zahlen; die gewählten Zahlen ersetzen die festen Schätzwerte in `estimated_resources` (`auswahl`), die Auflösung trägt `dynamisch_plan`. `jobs/resource_scheduler.py`: neue Methode `stand()` (frei = das kleinere von Ledger und Messung, Reserven getrennt). `models/model_loader.py`: `ensure` wählt unmittelbar vor dem Start **noch einmal** mit frischen Zahlen, überschreibt `n_cpu_moe` und den Kontext des Starts, lehnt mit Zahlen ab, wenn jetzt nichts passt (nichts wird gestartet), fehlt die Messung gilt die Wahl des Routings; die Antwort enthält `auswahl` nur bei dynamischen Rezepten; Audit `MODEL_LOAD_CHOICE`. `runtime.py` verdrahtet beides, nur wenn der Ressourcen-Scheduler an ist. Ohne Block oder ohne Speicherstand bleibt alles wie vorher. |
| R4 | `models/messwerte.py`: nach dem Laden merkt `uix_server` den gemessenen Unterschied des freien VRAM und RAM je Rezept, Lagen und Kontext in `runtime_data/model_messwerte.json` (atomar, höchstens 200 Einträge, unsinnige Werte nicht, kaputte Datei zählt als leer, nie ins Rezept); Audit `MODEL_LOAD_MEASURED`; die Auswahl bevorzugt Messwerte (`quelle: gemessen`). |
| R5 | `POST /api/model/load` meldet `auswahl` (Lagen, Kontext, VRAM, RAM, Token/s, Quelle, Grund); eine Ablehnung trägt den Grund mit den Zahlen (`recipe_not_usable:hardware_pressure:Es fehlen …`). `modell.js`: nach dem Laden ein Hinweis „Modell geladen mit 30 Lagen im RAM, 32.768 Kontext, ≈ 9,8 GB VRAM, 10,9 GB RAM, ≈ 43 Token/s“; bei Ablehnung steht der Satz mit den Zahlen im Modell-Hinweis. |

**Tests:** `test_dynamische_rezepte.py` (14: Rezeptblock, Auswahl beim Auflösen mit den Zahlen vom 29.10. → 30 Lagen, mehr Lagen vor kleinerem Kontext, RAM zu knapp für viele Lagen, Ablehnung mit Zahlen, Messwerte bevorzugt, ohne Block wie vorher, Lader wählt neu und startet mit den Lagen, ohne Messung gilt das Routing, kein dynamisches Rezept gleiche Antwort, Messspeicher, Ablehnungstext und Merken des Messwerts im Server), `test_resource_scheduler` (+1 `stand`), Browser-Abnahme `--stufe6` (+ S6-D Auswahl und Ablehnung). Gruppen `scheduler desk orchestra uix harness wissen`: **1520 Tests, 0 rot**; `test_role_routing`, `test_model_loader`, `test_llama_server_runtime`, `test_resource_scheduler` einzeln grün.

## Rezept des Captains (D-R2)

Wirksam wird alles erst mit dem Block in `local_config/role_routing.yaml` (nicht in Git; ändert nur der Captain oder Claude mit ausdrücklicher Freigabe), für `coder.local_primary` unter `profile`:

```yaml
dynamisch:
  n_cpu_moe: {min: 24, max: 40}
  tabelle:
    bei_kontext: 32768
    punkte:
      - {lagen: 28, vram_gb: 10.5, tokens_s: 45.0}
      - {lagen: 32, vram_gb: 9.1,  tokens_s: 41.7}
      - {lagen: 36, vram_gb: 7.6,  tokens_s: 38.5}
      - {lagen: 40, vram_gb: 6.1,  tokens_s: 35.5}
  vram_fix_gb: 1.5
  ram_aufschlag_gb: 1.5
  ram_untergrenze_gb: 8
```

Die Messpunkte stammen aus `moe_sweep` vom 9.10. (32k, ubatch 1024); `vram_fix_gb` und `ram_aufschlag_gb` sind Anfangswerte. Das Rezept braucht außerdem `kv_cache_gb_per_1k_tokens` und `model_size_gb` (17,73 stehen schon). Die von Hand geänderten Werte vom 29.10. (`min_ram_gb` 12, `n_cpu_moe` 30, `measured_vram_gb` 9,8) können danach zurück (`min_ram_gb` 18, `n_cpu_moe` 28).

## Offen

R6: Abnahme **mit Modell** (Qwen3.6 bei verschiedenem freien Speicher laden, gemessener VRAM/RAM gegen die Rechnung, Tempo je Lagenzahl), nur auf Ansage des Captains; das Rezept des Captains mit dem Block (oben); die Messtabelle gegen eine frische `moe_sweep`-Messung prüfen (die Werte vom 9.10. gelten für ubatch 1024, das Rezept läuft mit ubatch 512).
