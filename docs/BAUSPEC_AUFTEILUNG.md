# Bau-Spec R2: Aufteilung eines MoE-Modells (zweiter SEDRA-Bau unter einem Vorarbeiter, 30.10.2026)

Gehört zu `SPEC_DYNAMISCHE_REZEPTE_v1_G2.md` (§3) und `SPEC_DYNAMISCHE_REZEPTE_v1_G3.md` (R2). Aufgabe und versteckte Prüfungen (14, L3 ≤ 20) stehen in `runtime/benchmarks/devvm_specs/modelle_aufteilung.py`.

| | |
|---|---|
| Was SEDRA baut | `aufteilung.py` mit `bedarf(dyn, lagen, kontext, kv_rate_gb_je_1k, groesse_gb, slots=1)` und `waehlen(dyn, kontexte, frei_vram_gb, frei_ram_gb, reserve_vram_gb, reserve_ram_gb, kv_rate_gb_je_1k, groesse_gb, slots=1, gemessen=None)` – rein, nur Standardbibliothek |
| Ziel im Paket | `runtime/src/guppi_runtime/models/aufteilung.py` (Einbau durch Claude, G3 R3) |
| Referenz (Claude) | `runtime/benchmarks/devvm_refs/modelle_aufteilung/aufteilung.py`; `spec_check.py modelle_aufteilung` (Host): lint ok, Referenz ok |
| Stempel | `spec_check.py modelle_aufteilung --vm --project <A1>/workspace/GUPPI_OS` vor dem Bau |
| Bau | über die Vorarbeiter-Sitzung (Qwen3.6) unter einer Aufgaben-Freigabe: `spec_check`, `devvm_build` (Rezept `coder.local_primary`) – nicht von Hand |
| Prüfer | Gemma-4-12B (`pruefer`, nur lesend), nach dem Bau mit Modellwechsel |
| Zahlen der Prüfungen | Qwen3.6-35B-A3B nach `moe_sweep` (28/32/36/40 Lagen), 10,65 GB VRAM und 14,3 GB RAM frei (Stand 29.10.) → 30 Lagen bei 32 768 Kontext, 34 Lagen bei 65 536 |
