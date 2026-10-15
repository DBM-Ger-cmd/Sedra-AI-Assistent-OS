# Modellvergleich: Ergebnisse der Tests

Erzeugt von `benchmarks/model_compare.py` aus den Messdateien (nicht von Hand ändern).

## Geschwindigkeit (moe_sweep: ein Prompt, höchstens 256 Token Antwort)

| Rezept | Fenster | n_cpu_moe | ubatch | Prompt-Token | Einlesen Token/s | Erzeugen Token/s | frei GiB | Quelle |
|---|---|---|---|---|---|---|---|---|
| coder.llama_deepseek_v2_lite | 8192 | 8 | 512 | 5449 | 560.8 | 73.2 | 1.27 | moe_sweep_coder.llama_deepseek_v2_lite_2026-10-09_181935.json |
| coder.llama_deepseek_v2_lite | 8192 | 6 | 512 | 5449 | 728.7 | 81.1 | 0.64 | moe_sweep_coder.llama_deepseek_v2_lite_2026-10-09_181935.json |
| coder.llama_deepseek_v2_lite | 32768 | 10 | 1024 | 10822 | 17.3 | 0.3 | 0.55 | moe_sweep_coder.llama_deepseek_v2_lite_2026-10-09_180046.json |
| coder.llama_qwen36 | 32768 | 40 | 1024 | 9565 | 227.2 | 35.5 | 5.91 | moe_sweep_coder.llama_qwen36_2026-10-09_102702.json |
| coder.llama_qwen36 | 32768 | 36 | 1024 | 9565 | 251.3 | 38.5 | 4.37 | moe_sweep_coder.llama_qwen36_2026-10-09_102702.json |
| coder.llama_qwen36 | 32768 | 32 | 1024 | 9565 | 281.6 | 41.7 | 2.91 | moe_sweep_coder.llama_qwen36_2026-10-09_102702.json |
| coder.llama_qwen36 | 32768 | 28 | 1024 | 9565 | 317.0 | 45.0 | 1.52 | moe_sweep_coder.llama_qwen36_2026-10-09_102702.json |
| coder.llama_qwen3_coder | 49152 | 48 | 512 | 11590 | 116.6 | 33.1 | 5.39 | moe_sweep_coder.llama_qwen3_coder_2026-10-03.json |
| coder.llama_qwen3_coder | 49152 | 40 | 512 | 11590 | 138.8 | 38.4 | 2.71 | moe_sweep_coder.llama_qwen3_coder_2026-10-03.json |
| coder.llama_qwen3_coder | 49152 | 36 | 512 | 11590 | 154.8 | 40.7 | 1.42 | moe_sweep_coder.llama_qwen3_coder_2026-10-03.json |
| coder.llama_qwen3_coder | 49152 | 48 | 2048 | 11590 | 380.0 | 32.3 | 5.17 | moe_sweep_coder.llama_qwen3_coder_2026-10-03.json |
| coder.llama_qwen3_coder | 49152 | 40 | 2048 | 11590 | 449.4 | 38.3 | 2.5 | moe_sweep_coder.llama_qwen3_coder_2026-10-03.json |
| coder.llama_qwen3_coder | 49152 | 36 | 2048 | 11590 | 498.2 | 41.4 | 1.21 | moe_sweep_coder.llama_qwen3_coder_2026-10-03.json |
| coder.local_primary | 32768 | 44 | 512 | 8988 | 117.5 | 34.1 | 3.0 | manual |
| coder.local_primary | 32768 | 40 | 512 | 8988 | 129.6 | 36.7 | 1.65 | manual |
| coder.local_primary | 32768 | 36 | 512 | 8988 | 143.5 | 39.4 | 0.4 | manual |
| coder.local_primary | 32768 | 48 | 1024 | 8988 | 192.8 | 31.3 | 2.1 | moe_sweep_coder.local_primary_2026-10-09.json |
| coder.local_primary | 32768 | 46 | 1024 | 8988 | 196.4 | 32.3 | 1.38 | moe_sweep_coder.local_primary_2026-10-09.json |
| coder.local_primary | 32768 | 44 | 1024 | 8988 | 207.7 | 33.2 | 0.71 | moe_sweep_coder.local_primary_2026-10-09_095126.json |
| coder.local_primary | 32768 | 44 | 1024 | 8988 | 207.7 | 33.7 | 0.71 | manual |
| coder.local_primary | 32768 | 40 | 1024 | 8988 | 32.5 | 35.1 | 0.41 | moe_sweep_coder.local_primary_2026-10-09_095126.json |
| coder.local_primary | 32768 | 36 | 1024 | 8988 | 72.4 | 38.7 | 0.41 | moe_sweep_coder.local_primary_2026-10-09_095126.json |
| coder.local_primary | 32768 | 32 | 1024 | 8988 | 27.2 | 1.4 | 0.47 | moe_sweep_coder.local_primary_2026-10-09_095126.json |
| coder.local_primary | 32768 | 28 | 1024 | 9567 | 315.8 | 44.0 | 1.5 | moe_sweep_coder.local_primary_2026-10-09_205608.json |
| coder.local_primary | 32768 | 26 | 1024 | 9567 | 338.9 | 47.2 | 0.85 | moe_sweep_coder.local_primary_2026-10-09_205608.json |
| coder.local_primary | 32768 | 28 | 1536 | 9567 | 315.6 | 43.4 | 0.47 | moe_sweep_coder.local_primary_2026-10-09_205738.json |
| coder.local_q4km | 32768 | 44 | 1024 | 12313 | 185.6 | 41.3 | 5.07 | moe_sweep_coder.local_q4km_2026-10-10_201015.json |
| coder.local_q4km | 32768 | 40 | 1024 | 12313 | 186.0 | 42.4 | 5.19 | moe_sweep_coder.local_q4km_2026-10-10_201015.json |
| coder.local_q4km | 32768 | 36 | 1024 | 12313 | 205.0 | 44.4 | 3.3 | moe_sweep_coder.local_q4km_2026-10-10_201015.json |
| coder.local_q4km | 32768 | 32 | 1024 | 12313 | 229.3 | 48.1 | 1.46 | moe_sweep_coder.local_q4km_2026-10-10_201015.json |
| coder.local_q4km | 32768 | 28 | 1024 | 12313 | 191.3 | 43.1 | 0.43 | moe_sweep_coder.local_q4km_2026-10-10_201015.json |

## Aufwand je Spec und Modell (alle Versuche, gescheiterte eingerechnet)

Benötigte Token = Summe aller Versuche. Gebauter Code = Codezeilen (ohne Tests, ohne Saat-Dateien) in allen Versuchen. Genutzter Code = Zeilen des Versuchs, der die versteckten Tests bestanden hat (0 ohne Erfolg).

| Spec | Modelle | Versuche (bestanden) | Benötigte Token | Gebauter Code (Zeilen) | Genutzter Code (Zeilen) | Token je genutzter Zeile |
|---|---|---|---|---|---|---|
| am002_contracts | qwen3coder | 3 (2) | 133752 | 670 | 308 | 434 |
| am003_registry | qwen3coder | 4 (2) | 250098 | 2379 | 617 | 405 |
| am004_import | qwen3coder | 1 (1) | 31650 | 373 | 373 | 85 |
| am005_matcher | qwen3coder | 1 (1) | 159490 | 588 | 588 | 271 |
| am006_style | qwen3coder | 1 (0) | 196570 | 364 | 0 | None |
| am007_crews | coder.local_primary, swe | 3 (0) | 733619 | 1708 | 0 | None |
| am007_crews | qwen3coder | 1 (0) | 310942 | 555 | 0 | None |
| am008_meter | coder.llama_qwen36 | 1 (1) | 133781 | 168 | 168 | 796 |
| am008_meter | qwen3coder | 1 (1) | 108713 | 129 | 129 | 843 |
| am009_collector | coder.local_primary, swe | 4 (4) | 141568 | 532 | 141 | 1004 |
| am009_collector | qwen3coder | 1 (0) | 187074 | 152 | 0 | None |
| bench_std | coder.llama_deepseek_v2_lite | 1 (0) | 4675 | 14 | 0 | None |
| bench_std | coder.llama_gptoss | 1 (0) | 0 | 14 | 0 | None |
| bench_std | coder.llama_hermes4_14b | 1 (0) | 60073 | 52 | 0 | None |
| bench_std | coder.llama_qwen35_q6 | 2 (2) | 20831 | 133 | 69 | 302 |
| bench_std | coder.llama_qwen36 | 1 (1) | 11610 | 65 | 65 | 179 |
| bench_std | coder.llama_qwen3_30b_2507 | 1 (0) | 14482 | 57 | 0 | None |
| bench_std | coder.llama_qwen3_coder | 2 (2) | 9760 | 131 | 68 | 144 |
| bench_std | coder.local_primary | 17 (17) | 94545 | 1065 | 72 | 1313 |
| bench_std | coder.local_primary, swe | 2 (2) | 18407 | 144 | 73 | 252 |
| bench_std | coder.local_q38 | 2 (2) | 2664 | 107 | 54 | 49 |
| bench_std | coder.local_q4km | 3 (3) | 18728 | 192 | 68 | 275 |
| bench_std | jan | 1 (0) | 22198 | 55 | 0 | None |
| bench_std | qwen3.6-35b-a3b | 10 (10) | 146563 | 686 | 77 | 1903 |
| bench_std | qwen3coder | 1 (1) | 27783 | 106 | 106 | 262 |
| bench_std | verifier.llama_gemma | 2 (2) | 29582 | 108 | 62 | 477 |
| e01_read_tracker | coder.local_primary, swe | 5 (5) | 62475 | 500 | 111 | 563 |
| e02_think_guard | coder.local_primary, swe | 4 (2) | 28403 | 245 | 64 | 444 |
| e03_no_call_monitor | coder.local_primary, swe | 3 (3) | 19015 | 360 | 130 | 146 |
| e04_replay_log | coder.local_primary, swe | 4 (4) | 16127 | 271 | 72 | 224 |
| e05_result_pruner | coder.local_primary, swe | 2 (2) | 25167 | 129 | 72 | 350 |
| e06_bg_jobs | coder.local_primary | 1 (0) | 92198 | 210 | 0 | None |
| e07_tool_cards | coder.local_primary, swe | 2 (2) | 7810 | 108 | 54 | 145 |
| e08_fuzzy_edit | coder.local_primary, swe | 3 (3) | 51266 | 403 | 143 | 359 |
| e09_syntax_note | coder.local_primary, swe | 2 (2) | 7675 | 90 | 46 | 167 |
| e10_self_repo_guard | verifier.llama_gemma | 1 (0) | 114930 | 0 | 0 | None |
| e11_lesson_cards | coder.llama_qwen3_coder | 1 (1) | 24961 | 222 | 222 | 112 |
| e20_coder_ext | coder.local_primary, swe | 6 (2) | 475487 | 5163 | 809 | 588 |
| layer_summary | coder.llama_qwen35_q6 | 1 (1) | 44744 | 179 | 179 | 250 |
| mcp_shield | coder.local_primary | 1 (1) | 18434 | 101 | 101 | 183 |
| phase5_view |  | 2 (0) | 22160 | 286 | 0 | None |
| phase5_view | jan | 7 (0) | 103151 | 1141 | 0 | None |
| phase5_view | qwen3coder | 1 (0) | 13144 | 167 | 0 | None |
| phase5_view_staged | jan | 3 (1) | 132137 | 558 | 200 | 661 |
| phase5_window | qwen3coder | 5 (3) | 94629 | 0 | 0 | None |
| s0_conn_check | coder.local_q38 | 1 (1) | 13053 | 198 | 198 | 66 |

## Bauläufe je Versuch (DevVM, versteckte Tests)

Die Token jedes Versuchs stammen aus dem Log bis zu dessen Abschlusszeile; auch gescheiterte Versuche zählen. Prompt-Token = alle an das Modell gesendeten Token einschließlich der aus dem Zwischenspeicher des Servers (usage.prompt_tokens): sie sind NICHT mit den neu verarbeiteten Token der Editor-Sitzungen (Serverlog) vergleichbar.

| Lauf | Versuch | Spec | Modelle | Modus | Dauer s | Stufen bestanden | Aufrufe | Tokens erzeugt | Prompt-Token | Token/s | Gebauter Code | Genutzter Code | Stufen mit gescheiterten eigenen Tests | bestanden |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| devvm_build_am002_contracts_2026-10-06_173913 | 1 | am002_contracts | qwen3coder | escalating | 4095.8 | 2/4 | 266 | 108138 | None | 26.4 | 223 | 0 | 0 | nein |
| devvm_build_am002_contracts_2026-10-06_191012 | 1 | am002_contracts | qwen3coder | escalating | 274.3 | 1/1 | 17 | 5988 | None | 21.8 | 139 | 139 | 0 | ja |
| devvm_build_am002_contracts_2026-10-06_191448 | 1 | am002_contracts | qwen3coder | escalating | 841.5 | 1/1 | 38 | 19626 | None | 23.3 | 308 | 308 | 0 | ja |
| devvm_build_am003_registry_2026-10-06_192851 | 1 | am003_registry | qwen3coder | escalating | 2910.8 | 1/4 | 210 | 69156 | None | 23.8 | 577 | 0 | 0 | nein |
| devvm_build_am003_registry_2026-10-07_075805 | 1 | am003_registry | qwen3coder | escalating | 8239.7 | 7/9 | 509 | 144444 | None | 17.5 | 593 | 0 | 0 | nein |
| devvm_build_am003_registry_2026-10-07_101641 | 1 | am003_registry | qwen3coder | escalating | 1708.1 | 1/1 | 46 | 21802 | None | 12.8 | 592 | 592 | 0 | ja |
| devvm_build_am003_registry_2026-10-07_104510 | 1 | am003_registry | qwen3coder | escalating | 1031.9 | 1/1 | 62 | 14696 | None | 14.2 | 617 | 617 | 0 | ja |
| devvm_build_am004_import_2026-10-07_141218 | 1 | am004_import | qwen3coder | escalating | 1743.9 | 1/1 | 41 | 31650 | None | 18.1 | 373 | 373 | 0 | ja |
| devvm_build_am005_matcher_2026-10-07_144124 | 1 | am005_matcher | qwen3coder | escalating | 8112.3 | 6/6 | 362 | 159490 | None | 19.7 | 588 | 588 | 0 | ja |
| devvm_build_am006_style_2026-10-07_172307 | 1 | am006_style | qwen3coder | escalating | 8576.0 | 2/5 | 410 | 196570 | None | 22.9 | 364 | 0 | 0 | nein |
| devvm_build_am007_crews_2026-10-08_113130 | 1 | am007_crews | qwen3coder | escalating | 14437.0 | 2/7 | 633 | 310942 | None | 21.5 | 555 | 0 | 0 | nein |
| devvm_build_am007_crews_2026-10-10_090054 | 1 | am007_crews | coder.local_primary, swe | solo | 6181.4 | 4/7 | 506 | 198524 | 10012936 | 32.1 | 588 | 0 | 0 | nein |
| devvm_build_am007_crews_2026-10-10_103142 | 1 | am007_crews | coder.local_primary, swe | solo | 8587.2 | 4/7 | 449 | 254195 | 6558400 | 29.6 | 515 | 0 | 0 | nein |
| devvm_build_am007_crews_2026-10-10_131036 | 1 | am007_crews | coder.local_primary, swe | solo | 9538.1 | 4/7 | 638 | 280900 | 8111698 | 29.5 | 605 | 0 | 0 | nein |
| devvm_build_am008_meter_2026-10-08_100606 | 1 | am008_meter | qwen3coder | escalating | 4740.0 | 4/4 | 252 | 108713 | None | 22.9 | 129 | 129 | 0 | ja |
| devvm_build_am008_meter_2026-10-09_134322 | 1 | am008_meter | coder.llama_qwen36 | escalating | 3709.5 | 4/4 | 259 | 133781 | None | 36.1 | 168 | 168 | 0 | ja |
| devvm_build_am009_collector_2026-10-08_153226 | 1 | am009_collector | qwen3coder | escalating | 7361.7 | 0/3 | 348 | 187074 | None | 25.4 | 152 | 0 | 0 | nein |
| devvm_build_am009_collector_2026-10-09_223107 | 1 | am009_collector | coder.local_primary, swe | solo | 707.3 | 3/3 | 69 | 24050 | 428317 | 34.0 | 141 | 141 | 0 | ja |
| devvm_build_am009_collector_2026-10-09_224441 | 1 | am009_collector | coder.local_primary, swe | escalating | 2206.1 | 3/3 | 218 | 74321 | 2239307 | 33.7 | 130 | 130 | 1 | ja |
| devvm_build_am009_collector_2026-10-11_105442 | 1 | am009_collector | coder.local_primary, swe | solo | 622.9 | 3/3 | 62 | 19061 | 354214 | 30.6 | 127 | 127 | 0 | ja |
| devvm_build_am009_collector_2026-10-11_110506 | 1 | am009_collector | coder.local_primary, swe | solo | 834.4 | 3/3 | 77 | 24136 | 507797 | 28.9 | 134 | 134 | 0 | ja |
| devvm_build_bench_std_2026-10-09_165930 | 1 | bench_std | coder.llama_qwen36 | escalating | 374.0 | 4/4 | 85 | 11610 | 359139 | 31.0 | 65 | 65 | 0 | ja |
| devvm_build_bench_std_2026-10-09_171231 | 1 | bench_std | qwen3coder | escalating | 1062.3 | 4/4 | 77 | 27783 | 417601 | 26.2 | 106 | 106 | 0 | ja |
| devvm_build_bench_std_2026-10-09_182149 | 1 | bench_std | coder.llama_deepseek_v2_lite | escalating | 77.6 | 0/4 | 0 | 4675 | 2979 | 60.2 | 14 | 0 | 0 | nein |
| devvm_build_bench_std_2026-10-09_182924 | 1 | bench_std | coder.llama_hermes4_14b | escalating | 1437.0 | 1/4 | 14 | 60073 | 44277 | 41.8 | 52 | 0 | 0 | nein |
| devvm_build_bench_std_2026-10-09_185323 | 1 | bench_std | coder.llama_qwen3_30b_2507 | escalating | 663.3 | 2/4 | 76 | 14482 | 215747 | 21.8 | 57 | 0 | 0 | nein |
| devvm_build_bench_std_2026-10-09_190427 | 1 | bench_std | jan | escalating | 250.3 | 1/4 | 82 | 22198 | 194613 | 88.7 | 55 | 0 | 4 | nein |
| devvm_build_bench_std_2026-10-09_210854 | 1 | bench_std | coder.local_primary | escalating | 370.1 | 4/4 | 88 | 11712 | 368240 | 31.6 | 65 | 65 | 2 | ja |
| devvm_build_bench_std_2026-10-09_211505 | 1 | bench_std | coder.local_primary | escalating | 352.9 | 4/4 | 99 | 11408 | 386310 | 32.3 | 66 | 66 | 4 | ja |
| devvm_build_bench_std_2026-10-09_212100 | 1 | bench_std | coder.local_primary | solo | 196.9 | 4/4 | 44 | 5437 | 118616 | 27.6 | 72 | 72 | 0 | ja |
| devvm_build_bench_std_2026-10-09_212418 | 1 | bench_std | coder.local_primary | solo | 274.0 | 4/4 | 56 | 8063 | 210873 | 29.4 | 70 | 70 | 0 | ja |
| devvm_build_bench_std_2026-10-10_143905 | 1 | bench_std | coder.local_primary | solo | 242.7 | 4/4 | 59 | 6233 | 214436 | 25.7 | 59 | 59 | 0 | ja |
| devvm_build_bench_std_2026-10-10_155344 | 1 | bench_std | coder.local_primary | solo | 247.2 | 4/4 | 35 | 7600 | 107809 | 30.7 | 66 | 66 | 0 | ja |
| devvm_build_bench_std_2026-10-10_155753 | 1 | bench_std | coder.local_primary | solo | 174.0 | 4/4 | 69 | 4405 | 242350 | 25.3 | 60 | 60 | 0 | ja |
| devvm_build_bench_std_2026-10-10_160048 | 1 | bench_std | coder.local_primary | solo | 325.0 | 4/4 | 33 | 11527 | 97371 | 35.5 | 59 | 59 | 0 | ja |
| devvm_build_bench_std_2026-10-10_160614 | 1 | bench_std | coder.local_primary | solo | 124.1 | 4/4 | 25 | 3354 | 44240 | 27.0 | 67 | 67 | 0 | ja |
| devvm_build_bench_std_2026-10-10_160820 | 1 | bench_std | coder.local_primary | solo | 119.1 | 4/4 | 26 | 3052 | 50630 | 25.6 | 58 | 58 | 0 | ja |
| devvm_build_bench_std_2026-10-10_164139 | 1 | bench_std | qwen3.6-35b-a3b | Qwen Code (asis) + none | 334.3 | 4/4 | 63 | 15301 | 994983 | 45.8 | 65 | 65 | 0 | ja |
| devvm_build_bench_std_2026-10-10_164732 | 1 | bench_std | qwen3.6-35b-a3b | Qwen Code (asis) + none | 602.6 | 4/4 | 141 | 31110 | 2468230 | 51.6 | 77 | 77 | 0 | ja |
| devvm_build_bench_std_2026-10-10_170451 | 1 | bench_std | qwen3.6-35b-a3b | Qwen Code (asis) + none | 442.4 | 4/4 | 49 | 12826 | 789130 | 29.0 | 73 | 73 | 0 | ja |
| devvm_build_bench_std_2026-10-10_171233 | 1 | bench_std | qwen3.6-35b-a3b | Qwen Code (asis) + none | 494.1 | 4/4 | 68 | 15766 | 1121294 | 31.9 | 69 | 69 | 0 | ja |
| devvm_build_bench_std_2026-10-10_172104 | 1 | bench_std | qwen3.6-35b-a3b | Qwen Code (lean) + none | 530.7 | 4/4 | 55 | 19953 | 670888 | 37.6 | 76 | 76 | 0 | ja |
| devvm_build_bench_std_2026-10-10_173013 | 1 | bench_std | qwen3.6-35b-a3b | Qwen Code (lean) + none | 489.6 | 4/4 | 52 | 16665 | 708041 | 34.0 | 70 | 70 | 0 | ja |
| devvm_build_bench_std_2026-10-10_193211 | 1 | bench_std | qwen3.6-35b-a3b | Qwen Code (asis) + none | 361.8 | 4/4 | 29 | 4820 | 266134 | 13.3 | 67 | 67 | 0 | ja |
| devvm_build_bench_std_2026-10-10_193830 | 1 | bench_std | qwen3.6-35b-a3b | Qwen Code (asis) + none | 292.5 | 4/4 | 24 | 3736 | 161947 | 12.8 | 58 | 58 | 0 | ja |
| devvm_build_bench_std_2026-10-10_194339 | 1 | bench_std | qwen3.6-35b-a3b | Qwen Code (lean) + none | 283.9 | 4/4 | 28 | 4369 | 144257 | 15.4 | 69 | 69 | 0 | ja |
| devvm_build_bench_std_2026-10-10_194840 | 1 | bench_std | qwen3.6-35b-a3b | Qwen Code (lean) + none | 677.2 | 4/4 | 39 | 22017 | 475229 | 32.5 | 62 | 62 | 0 | ja |
| devvm_build_bench_std_2026-10-10_202050 | 1 | bench_std | coder.local_q4km | solo | 158.5 | 4/4 | 27 | 4186 | 63809 | 26.4 | 66 | 66 | 0 | ja |
| devvm_build_bench_std_2026-10-10_202330 | 1 | bench_std | coder.local_q4km | solo | 144.2 | 4/4 | 25 | 3780 | 54876 | 26.2 | 68 | 68 | 0 | ja |
| devvm_build_bench_std_2026-10-10_202555 | 1 | bench_std | coder.local_q4km | solo | 284.2 | 4/4 | 24 | 10762 | 53928 | 37.9 | 58 | 58 | 0 | ja |
| devvm_build_bench_std_2026-10-10_203041 | 1 | bench_std | coder.local_primary | solo | 137.7 | 4/4 | 25 | 3954 | 55270 | 28.7 | 70 | 70 | 0 | ja |
| devvm_build_bench_std_2026-10-10_203300 | 1 | bench_std | coder.local_primary | solo | 120.9 | 4/4 | 25 | 3176 | 55603 | 26.3 | 60 | 60 | 0 | ja |
| devvm_build_bench_std_2026-10-10_203503 | 1 | bench_std | coder.local_primary | solo | 113.6 | 4/4 | 24 | 2838 | 50865 | 25.0 | 58 | 58 | 0 | ja |
| devvm_build_bench_std_2026-10-11_104202 | 1 | bench_std | coder.local_primary, swe | solo | 367.6 | 4/4 | 100 | 9186 | 374901 | 25.0 | 71 | 71 | 0 | ja |
| devvm_build_bench_std_2026-10-11_104811 | 1 | bench_std | coder.local_primary, swe | solo | 389.1 | 4/4 | 96 | 9221 | 393193 | 23.7 | 73 | 73 | 0 | ja |
| devvm_build_bench_std_2026-10-11_205554 | 1 | bench_std | coder.local_primary | solo | 160.8 | 4/4 | 23 | 2903 | 47335 | 18.1 | 58 | 58 | 0 | ja |
| devvm_build_bench_std_2026-10-11_205837 | 1 | bench_std | coder.local_primary | solo | 126.3 | 4/4 | 24 | 2794 | 50102 | 22.1 | 58 | 58 | 0 | ja |
| devvm_build_bench_std_2026-10-11_232025 | 1 | bench_std | coder.llama_qwen3_coder | solo | 270.2 | 4/4 | 34 | 5137 | 98934 | 19.0 | 68 | 68 | 0 | ja |
| devvm_build_bench_std_2026-10-11_232457 | 1 | bench_std | coder.llama_qwen3_coder | solo | 261.5 | 4/4 | 38 | 4623 | 115549 | 17.7 | 63 | 63 | 0 | ja |
| devvm_build_bench_std_2026-10-12_005808 | 1 | bench_std | verifier.llama_gemma | solo | 205.8 | 4/4 | 60 | 8642 | 238827 | 42.0 | 62 | 62 | 0 | ja |
| devvm_build_bench_std_2026-10-12_010136 | 1 | bench_std | verifier.llama_gemma | solo | 474.7 | 4/4 | 97 | 20940 | 403794 | 44.1 | 46 | 46 | 0 | ja |
| devvm_build_bench_std_2026-10-12_020736 | 1 | bench_std | coder.llama_qwen35_q6 | solo | 102.3 | 4/4 | 30 | 5018 | 61460 | 49.1 | 64 | 64 | 0 | ja |
| devvm_build_bench_std_2026-10-12_020919 | 1 | bench_std | coder.llama_qwen35_q6 | solo | 286.0 | 4/4 | 28 | 15813 | 68758 | 55.3 | 69 | 69 | 0 | ja |
| devvm_build_bench_std_2026-10-12_023232 | 1 | bench_std | coder.llama_gptoss | solo | 100.4 | 0/4 | 0 | 0 | None | None | 14 | 0 | 0 | nein |
| devvm_build_bench_std_2026-10-12_024201 | 1 | bench_std | coder.local_q38 | solo | 315.2 | 4/4 | 19 | 1338 | 34514 | 4.2 | 54 | 54 | 0 | ja |
| devvm_build_bench_std_2026-10-12_024718 | 1 | bench_std | coder.local_q38 | solo | 312.1 | 4/4 | 19 | 1326 | 34494 | 4.2 | 53 | 53 | 0 | ja |
| devvm_build_bench_std_2026-10-12_041305 | 1 | bench_std | coder.local_primary | solo | 127.2 | 4/4 | 24 | 2869 | 50252 | 22.6 | 58 | 58 | 0 | ja |
| devvm_build_bench_std_2026-10-12_041513 | 1 | bench_std | coder.local_primary | solo | 135.1 | 4/4 | 23 | 3220 | 50239 | 23.8 | 61 | 61 | 0 | ja |
| devvm_build_e01_read_tracker_2026-10-10_203758 | 1 | e01_read_tracker | coder.local_primary, swe | solo | 971.2 | 3/3 | 83 | 30999 | 625435 | 31.9 | 111 | 111 | 0 | ja |
| devvm_build_e01_read_tracker_2026-10-10_215227 | 1 | e01_read_tracker | coder.local_primary, swe | solo | 525.7 | 1/1 | 19 | 20227 | 130865 | 38.5 | 103 | 103 | 0 | ja |
| devvm_build_e01_read_tracker_2026-10-10_223248 | 1 | e01_read_tracker | coder.local_primary, swe | solo | 159.6 | 1/1 | 16 | 4045 | 98845 | 25.3 | 98 | 98 | 0 | ja |
| devvm_build_e01_read_tracker_2026-10-10_224430 | 1 | e01_read_tracker | coder.local_primary, swe | solo | 263.3 | 1/1 | 27 | 5869 | 180714 | 22.3 | 93 | 93 | 0 | ja |
| devvm_build_e01_read_tracker_2026-10-11_004644 | 1 | e01_read_tracker | coder.local_primary, swe | solo | 73.5 | 1/1 | 10 | 1335 | 47614 | 18.2 | 95 | 95 | 0 | ja |
| devvm_build_e02_think_guard_2026-10-10_212206 | 1 | e02_think_guard | coder.local_primary, swe | solo | 330.3 | 3/3 | 47 | 10015 | 213675 | 30.3 | 64 | 64 | 0 | ja |
| devvm_build_e02_think_guard_2026-10-10_220859 | 1 | e02_think_guard | coder.local_primary, swe | solo | 413.4 | 0/1 | 148 | 8320 | 1397508 | 20.1 | 60 | 0 | 0 | nein |
| devvm_build_e02_think_guard_2026-10-10_220859 | 2 | e02_think_guard | coder.local_primary, swe | solo | 394.7 | 0/1 | 75 | 9112 | 607216 | 23.1 | 60 | 0 | 0 | nein |
| devvm_build_e02_think_guard_2026-10-10_223944 | 1 | e02_think_guard | coder.local_primary, swe | solo | 57.3 | 1/1 | 10 | 956 | 37352 | 16.7 | 61 | 61 | 0 | ja |
| devvm_build_e03_no_call_monitor_2026-10-10_212738 | 1 | e03_no_call_monitor | coder.local_primary, swe | solo | 470.9 | 3/3 | 80 | 12761 | 507183 | 27.1 | 116 | 116 | 0 | ja |
| devvm_build_e03_no_call_monitor_2026-10-10_222229 | 1 | e03_no_call_monitor | coder.local_primary, swe | solo | 176.1 | 1/1 | 19 | 3919 | 101758 | 22.3 | 130 | 130 | 0 | ja |
| devvm_build_e03_no_call_monitor_2026-10-10_224111 | 1 | e03_no_call_monitor | coder.local_primary, swe | solo | 114.8 | 1/1 | 15 | 2335 | 80944 | 20.3 | 114 | 114 | 0 | ja |
| devvm_build_e04_replay_log_2026-10-10_211641 | 1 | e04_replay_log | coder.local_primary, swe | solo | 323.3 | 3/3 | 40 | 9931 | 174955 | 30.7 | 72 | 72 | 0 | ja |
| devvm_build_e04_replay_log_2026-10-10_220706 | 1 | e04_replay_log | coder.local_primary, swe | solo | 112.1 | 1/1 | 17 | 2464 | 82115 | 22.0 | 68 | 68 | 0 | ja |
| devvm_build_e04_replay_log_2026-10-10_224314 | 1 | e04_replay_log | coder.local_primary, swe | solo | 75.0 | 1/1 | 11 | 1506 | 46591 | 20.1 | 59 | 59 | 0 | ja |
| devvm_build_e04_replay_log_2026-10-11_112453 | 1 | e04_replay_log | coder.local_primary, swe | solo | 93.3 | 1/1 | 13 | 2226 | 63729 | 23.9 | 72 | 72 | 0 | ja |
| devvm_build_e05_result_pruner_2026-10-10_213850 | 1 | e05_result_pruner | coder.local_primary, swe | solo | 673.4 | 3/3 | 64 | 21464 | 351204 | 31.9 | 72 | 72 | 0 | ja |
| devvm_build_e05_result_pruner_2026-10-10_222727 | 1 | e05_result_pruner | coder.local_primary, swe | solo | 139.4 | 1/1 | 14 | 3703 | 71005 | 26.6 | 57 | 57 | 0 | ja |
| devvm_build_e06_bg_jobs_2026-10-11_210045 | 1 | e06_bg_jobs | coder.local_primary | solo | 5130.3 | 1/3 | 378 | 92198 | 5244857 | 18.0 | 210 | 0 | 0 | nein |
| devvm_build_e07_tool_cards_2026-10-10_215005 | 1 | e07_tool_cards | coder.local_primary, swe | solo | 130.8 | 2/2 | 18 | 3946 | 66188 | 30.2 | 54 | 54 | 0 | ja |
| devvm_build_e07_tool_cards_2026-10-10_222948 | 1 | e07_tool_cards | coder.local_primary, swe | solo | 174.5 | 1/1 | 32 | 3864 | 182103 | 22.1 | 54 | 54 | 0 | ja |
| devvm_build_e08_fuzzy_edit_2026-10-10_205425 | 1 | e08_fuzzy_edit | coder.local_primary, swe | solo | 1319.4 | 3/3 | 171 | 37650 | 1745519 | 28.5 | 143 | 143 | 0 | ja |
| devvm_build_e08_fuzzy_edit_2026-10-10_220123 | 1 | e08_fuzzy_edit | coder.local_primary, swe | solo | 311.8 | 1/1 | 48 | 7794 | 351187 | 25.0 | 134 | 134 | 0 | ja |
| devvm_build_e08_fuzzy_edit_2026-10-10_223533 | 1 | e08_fuzzy_edit | coder.local_primary, swe | solo | 226.0 | 1/1 | 37 | 5822 | 272391 | 25.8 | 126 | 126 | 0 | ja |
| devvm_build_e09_syntax_note_2026-10-10_213530 | 1 | e09_syntax_note | coder.local_primary, swe | solo | 198.5 | 2/2 | 50 | 4861 | 214271 | 24.5 | 46 | 46 | 0 | ja |
| devvm_build_e09_syntax_note_2026-10-10_222527 | 1 | e09_syntax_note | coder.local_primary, swe | solo | 118.5 | 1/1 | 17 | 2814 | 85007 | 23.7 | 44 | 44 | 0 | ja |
| devvm_build_e10_self_repo_guard_2026-10-12_010932 | 1 | e10_self_repo_guard | verifier.llama_gemma | solo | 3095.8 | 0/3 | 415 | 114930 | 5177047 | 37.1 | 0 | 0 | 0 | nein |
| devvm_build_e11_lesson_cards_2026-10-11_232920 | 1 | e11_lesson_cards | coder.llama_qwen3_coder | solo | 1543.4 | 3/3 | 115 | 24961 | 850618 | 16.2 | 222 | 222 | 0 | ja |
| devvm_build_e20_coder_ext_2026-10-10_225110 | 1 | e20_coder_ext | coder.local_primary, swe | solo | 2918.8 | 1/3 | 396 | 62513 | 6242960 | 21.4 | 919 | 0 | 0 | nein |
| devvm_build_e20_coder_ext_2026-10-10_225110 | 2 | e20_coder_ext | coder.local_primary, swe | solo | 4011.2 | 1/3 | 349 | 102682 | 5812754 | 25.6 | 946 | 0 | 0 | nein |
| devvm_build_e20_coder_ext_2026-10-11_075037 | 1 | e20_coder_ext | coder.local_primary, swe | solo | 3667.9 | 3/5 | 203 | 125895 | 2141528 | 34.3 | 822 | 0 | 0 | nein |
| devvm_build_e20_coder_ext_2026-10-11_075037 | 2 | e20_coder_ext | coder.local_primary, swe | solo | 5425.0 | 3/5 | 339 | 177651 | 4785923 | 32.7 | 864 | 0 | 0 | nein |
| devvm_build_e20_coder_ext_2026-10-11_102236 | 1 | e20_coder_ext | coder.local_primary, swe | solo | 166.2 | 1/1 | 22 | 3105 | 176409 | 18.7 | 809 | 809 | 0 | ja |
| devvm_build_e20_coder_ext_2026-10-11_102603 | 1 | e20_coder_ext | coder.local_primary, swe | solo | 160.3 | 1/1 | 19 | 3641 | 153863 | 22.7 | 803 | 803 | 0 | ja |
| devvm_build_layer_summary_2026-10-12_021407 | 1 | layer_summary | coder.llama_qwen35_q6 | solo | 884.1 | 3/3 | 132 | 44744 | 1190416 | 50.6 | 179 | 179 | 0 | ja |
| devvm_build_mcp_shield_2026-10-12_035903 | 1 | mcp_shield | coder.local_primary | solo | 839.7 | 4/4 | 102 | 18434 | 585352 | 22.0 | 101 | 101 | 0 | ja |
| devvm_build_phase5_view_2026-10-06_140242 | 1 | phase5_view |  | escalating | 265.7 | 0/0 | 28 | 10699 | None | 40.3 | 154 | 0 | 0 | nein |
| devvm_build_phase5_view_2026-10-06_140242 | 2 | phase5_view |  | escalating | 287.4 | 0/0 | 28 | 11461 | None | 39.9 | 132 | 0 | 0 | nein |
| devvm_build_phase5_view_2026-10-06_141241 | 1 | phase5_view | qwen3coder | escalating | 503.4 | 0/0 | 31 | 13144 | None | 26.1 | 167 | 0 | 0 | nein |
| devvm_build_phase5_view_2026-10-06_142146 | 1 | phase5_view | jan | escalating | 336.2 | 0/0 | 30 | 13288 | None | 39.5 | 132 | 0 | 0 | nein |
| devvm_build_phase5_view_2026-10-06_142817 | 1 | phase5_view | jan | escalating | 1038.1 | 0/0 | 69 | 28716 | None | 27.7 | 165 | 0 | 0 | nein |
| devvm_build_phase5_view_2026-10-06_142817 | 2 | phase5_view | jan | escalating | 225.2 | 0/0 | 25 | 9722 | None | 43.2 | 144 | 0 | 0 | nein |
| devvm_build_phase5_view_2026-10-06_145209 | 1 | phase5_view | jan | escalating | 380.8 | 0/0 | 35 | 10197 | None | 26.8 | 174 | 0 | 0 | nein |
| devvm_build_phase5_view_2026-10-06_145209 | 2 | phase5_view | jan | escalating | 472.1 | 0/0 | 21 | 15580 | None | 33.0 | 163 | 0 | 0 | nein |
| devvm_build_phase5_view_2026-10-06_150656 | 1 | phase5_view | jan | pipeline | 459.6 | 0/0 | 54 | 13138 | None | 28.6 | 229 | 0 | 0 | nein |
| devvm_build_phase5_view_2026-10-06_150656 | 2 | phase5_view | jan | pipeline | 422.5 | 0/0 | 44 | 12510 | None | 29.6 | 134 | 0 | 0 | nein |
| devvm_build_phase5_view_staged_2026-10-06_152339 | 1 | phase5_view_staged | jan | escalating | 1889.2 | 2/4 | 178 | 51129 | None | 27.1 | 177 | 0 | 0 | nein |
| devvm_build_phase5_view_staged_2026-10-06_152339 | 2 | phase5_view_staged | jan | escalating | 930.7 | 1/4 | 79 | 35817 | None | 38.5 | 181 | 0 | 0 | nein |
| devvm_build_phase5_view_staged_2026-10-06_161158 | 1 | phase5_view_staged | jan | escalating | 1412.4 | 4/4 | 124 | 45191 | None | 32.0 | 200 | 200 | 0 | ja |
| devvm_build_phase5_window_2026-10-06_163551 | 1 | phase5_window | qwen3coder | escalating | 338.1 | 2/2 | 26 | 7601 | None | 22.5 | 0 | 0 | 0 | ja |
| devvm_build_phase5_window_2026-10-06_164258 | 1 | phase5_window | qwen3coder | escalating | 251.3 | 1/1 | 7 | 6172 | None | 24.6 | 0 | 0 | 0 | ja |
| devvm_build_phase5_window_2026-10-06_164804 | 1 | phase5_window | qwen3coder | escalating | 162.3 | 1/1 | 3 | 4094 | None | 25.2 | 0 | 0 | 0 | ja |
| devvm_build_phase5_window_2026-10-06_165556 | 1 | phase5_window | qwen3coder | escalating | 1329.1 | 0/1 | 33 | 36848 | None | 27.7 | 0 | 0 | 0 | nein |
| devvm_build_phase5_window_2026-10-07_101728 | 1 | phase5_window | qwen3coder | escalating | 1655.3 | 0/1 | 47 | 39914 | None | 24.1 | 0 | 0 | 0 | nein |
| devvm_build_s0_conn_check_2026-10-12_025231 | 1 | s0_conn_check | coder.local_q38 | solo | 3200.4 | 3/3 | 88 | 13053 | 513508 | 4.1 | 198 | 198 | 0 | ja |

## Sitzungen im Editor (VS Code, GUPPIs Modell über den lokalen Server)

| Werkzeug | Modell | Aufgabe | Dauer min | Anfragen | Prompt-Token | Erzeugte Token | Werkzeugaufrufe (Fehler) | versteckte Suite | Code / Tests (Zeilen) | Ordner |
|---|---|---|---|---|---|---|---|---|---|---|
| Cline 4.1.23 (VS Code) | qwen3.6-35b-a3b (n_cpu_moe 28, 32k, reasoning off) | am008_meter (3 Teile in einem Auftrag) | 61 | 128 | 453562 | 76147 | 109 (34) | 2 von 4 (daily, cards bestanden; heatmap, all nicht) | 162 / 351 | runtime_data/vscode_serve/ergebnis_cline_20261009_1633 |
