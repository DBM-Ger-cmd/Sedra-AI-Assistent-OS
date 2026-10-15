# Lokale Modelle

Stand 12.10.2026. Ausführlicher Vergleich mit allen Messwerten: [MODELLVERGLEICH_2026-10-12.pdf](MODELLVERGLEICH_2026-10-12.pdf) (Quelle: `MODELLVERGLEICH_2026-10-12.html`).
Rohdaten aller Bauten: [MODELL_VERGLEICH_ERGEBNISSE.md](MODELL_VERGLEICH_ERGEBNISSE.md), erzeugt von `benchmarks/model_compare.py`.

Alle Werte stammen von der RTX 4070 Ti (12 GB), Engine b11160, mit Flash Attention, KV q8_0, ubatch 512 und 1 Slot.

## Einsatz

| Rolle | Modell | Rezept | Erzeugen (Server) | Kontext sicher bis | Belege |
|---|---|---|---|---|---|
| **Standard-Coder / Hauptagent** | Qwen3.6-35B-A3B UD-IQ4_XS (MoE) | `coder.local_primary` (an) | 44–47 Token/s | 131k | Standardtest in allen Solo-Läufen 4/4; mcp_shield 4/4, core_boundary 4/4, Coder-Erweiterungen |
| Zweiter Coder, lange Bauten | Qwen3-Coder-30B-A3B UD-Q4_K_XL (MoE) | `coder.llama_qwen3_coder` (an) | 33–41 Token/s | 131k | Standardtest 4/4; e11 3/3; am002–am005, am008 |
| Prüfer, lange Texte | Gemma-4-12B QAT Q4_0 | `verifier.llama_gemma` (an) | – | 131k | Standardtest 4/4, aber viele Aufrufe; als Agent ungeeignet |
| Schnelle Unteragenten | Qwen3.5-9B Q6_K **mit MTP** | `coder.llama_qwen35` (an seit 12.10., nur auf Anforderung oder als Ersatz) | ca. 109 Token/s | 131k | 80 % der MTP-Vorschläge angenommen; noch kein Bau-Test |
| GPU-Canary, kleiner Coder | Qwen3.5-9B Q6_K | `coder.llama_qwen35_q6` (aus) | 56 Token/s | 131k | Standardtest 4/4, layer_summary 3/3 |
| Kleinteam | Jan-code-4b + SWE-Review-8B | `coder.llama_jan`, `reviewer.llama_swe` (aus) | – | 16k | nur mit Test als Richter |

## Entfernt am 12.10.2026

In der Quarantäne `<modelle>\_guppi_entfernt\RM-20261012T055725\` liegen Qwen3.6 Q4_K_M, Qwen3.8-27B (+ MTP-Datei), gpt-oss-20b,
DeepSeek-Coder-V2-Lite und Hermes-4-14B (zusammen 71,4 GB). Zurückholen: `guppi model-restore RM-20261012T055725`. Die Begründungen stehen in der PDF.

## Bekannte Grenzen

- Die Verbindungsprüfung S0 vom 12.10. ist bei allen Modellen nicht bestanden, mit ähnlichen Fehlern. Das deutet auf die Prüfung selbst, sie wird untersucht.
- MoE-Modelle legen Experten-Schichten in den Arbeitsspeicher (`n_cpu_moe`); das Tempo hängt stark davon ab.
- Ältere Kontextgrenzen, etwa 16k bei Qwen3.5 wegen CUDA-Abstürzen, stammen von Engine b11371 ohne Flash Attention. Mit den heutigen Einstellungen sind sie neu gemessen.
