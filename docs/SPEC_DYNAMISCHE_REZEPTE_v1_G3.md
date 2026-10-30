# SPEC Dynamische Rezepte v1 – G3 Bau-Aufgaben (30.10.2026)

G2 (D-R1 bis D-R5) gilt als freigegeben durch die Ansage des Captains „lass SEDRA G3 bauen, wenn möglich“ (30.10.2026). Baut: **SEDRA** die Rechenmodule (R2), **Claude** alles andere. Kein Push ohne Ja.

| Nr | Aufgabe | Wer | Dateien | Fertig wenn |
|---|---|---|---|---|
| R1 | Referenz, Spec und versteckte Prüfungen der Rechenmodule; Bau-Spec | Claude | `devvm_specs/modelle_aufteilung.py`, `devvm_refs/modelle_aufteilung/`, `docs/BAUSPEC_AUFTEILUNG.md` | `spec_check` lint, Größe, Referenz ok (**erledigt 30.10.**; Stempel mit `--vm` vor dem Bau) |
| R2 | **SEDRA-Bau** `aufteilung.py` (`bedarf`, `waehlen`) unter einem Vorarbeiter | SEDRA, Qwen3.6 | Kandidat in `runtime_data/devvm_candidates/modelle_aufteilung/` | versteckt bestanden; Review (Claude, Gemma); Übernahme nach `models/aufteilung.py` auf Ja des Captains |
| R3 | Rezeptblock `profile.dynamisch` prüfen und ins Rezept übernehmen; `_candidate` und `_resource_load_check` nutzen die Auswahl; Lader wählt vor dem Start neu | Claude | `models/role_routing.py`, `runtime.py`, `models/model_loader.py`, `models/llama_server_runtime.py` | Tests mit Attrappen (kein Modell) |
| R4 | Messspeicher `runtime_data/model_messwerte.json` | Claude | `models/messwerte.py` | Test |
| R5 | Antwort von `POST /api/model/load` mit `auswahl`, Audit `MODEL_LOAD_CHOICE`, Zeile in `modell.js` | Claude | `uix_server.py`, `uix/shells/harness/modell.js` | Tests, Browser-Abnahme |
| R6 | Abnahme: Suite, Playwright, danach mit Modell (nur auf Ansage) | Claude, Captain | `harness_abnahme_stufe6.py` (Modellzeile), Bericht | Bericht mit Belegen |

**Reihenfolge:** R1 → R2 (SEDRA, parallel zu R3 bis R5, sobald R2 den Kandidaten liefert, tauscht Claude die Referenz gegen den Kandidaten) → R6. R3 bis R5 arbeiten gegen die Referenz, damit der Einbau nicht auf den Bau wartet.

**Berechtigungen:** P-D1 bis P-D3 ja; P-D4 (Modell laden, SEDRA-Bau) mit der Ansage des Captains heute; `local_config/` ändert nur er. Aufgaben-Freigabe für den Bau: `datei_schreiben docs/spec_entwuerfe/**`, `lauf_starten spec_check`, `lauf_starten devvm_build`, Modell `coder.local_primary`, 60 Aufrufe, 180 Minuten.
