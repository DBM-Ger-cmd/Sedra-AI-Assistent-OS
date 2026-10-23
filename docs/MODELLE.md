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

## Parallele Slots (Messung 23.10.2026)

Engine b11160, FA an, KV q8_0, Rezepte unverändert; Einzelheiten und Einschränkungen: [MESSBERICHT_SLOTS_2026-10-23.md](MESSBERICHT_SLOTS_2026-10-23.md). „Mindestens“ heißt: Die Leiter wurde vom Werkzeug früher abgebrochen als nötig (alle Antworten waren richtig), nachgemessen wird noch.

| Modell | Slots | Fenster je Slot (sicher) | Gesamtkontext | VRAM-Spitze (GiB) | Token/s gesamt | Token/s je Slot | S0 | Hinweis |
|---|---|---|---|---|---|---|---|---|
| Qwen3.6-35B-A3B | 1 | 131072 | 131072 | 8,76 | 31,6 | 42,3 | ok | Vergleichswert 44–47 Token/s (Server) aus dem Modellvergleich |
| Qwen3.6-35B-A3B | 2 | mindestens 49152 | mindestens 98304 | 8,26 | 36,9 | 25,7 | ok | Empfehlung Standard: 2 Slots, Fenster 32768 |
| Qwen3.6-35B-A3B | 3 | mindestens 16384 | mindestens 49152 | 8,05 | 44,9 | 19,1 | ok | Fenster 32768 noch nicht belegt |
| Qwen3.6-35B-A3B | 4 | mindestens 8192 | mindestens 32768 | 7,93 | 49,9 | 15,4 | ok | Fenster 32768 noch nicht belegt |
| Qwen3.5-9B Q6_K MTP | 1 | 98304 | 98304 | 8,77 | 70,0 | 76,2 | ok | ohne MTP 56,5 |
| Qwen3.5-9B Q6_K MTP | 2 | mindestens 24576 | mindestens 49152 | 8,97 | 117,7 | 65,7 | ok | ohne MTP 100,2; Empfehlung Standard: 2 Slots |
| Qwen3.5-9B Q6_K MTP | 3 | mindestens 8192 | mindestens 24576 | 8,58 | 147,9 | 56,9 | ok | ohne MTP 135,5 |
| Qwen3.5-9B Q6_K MTP | 4 | nicht bestimmt | – | 11,21 | 155,7 | 47,6 | ok | über der nutzbaren Grenze 10,8 GB; ohne MTP 162,6 Token/s bei 9,98 GiB: MTP ab 4 Slots aus |
| Qwen3.5-9B (CPU) | 1 / 2 | 32768 / 8192 | – | 1,3 / 1,5 | 7,6 / 9,7 | 10,2 / 6,6 | – | `n_gpu_layers=0`, nicht für Agenten |

Die VRAM-Spitze ist der belegte Speicher der ganzen Karte (enthält rund 2,2 GiB Desktop). Der Server teilt `-c` auf die Slots auf; `/props` meldet das Fenster je Slot.
