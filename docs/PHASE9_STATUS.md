# Phase 9 – Arbeitsset-Bauer und Langkontext-Messungen (2026-10-01/02)

Auslöser: Der Captain wollte nicht mehr bei jedem Schritt die ganze Historie an das Modell senden, sondern nur die gerade
benötigten Teile; der Rest wird außerhalb des Fensters gespeichert. Gleichzeitig stürzte Qwen3.5 bei langen Prompts ab.

## Was gebaut ist (hinter dem Schalter `context_manager`)

| Teil | Datei | Inhalt |
|---|---|---|
| Arbeitsset | `working_set.py` | stabiler Kopf, Archiv-Index, aktive Turns, aktueller Schritt mit zurückgerufenen Auszügen; Block-Verdichtung; deterministisch (kein Modell fasst zusammen) |
| Handler-Haken | `job_worker.py` | `model_text_handler(..., on_result=)` meldet die fertige Antwort, damit das Arbeitsset sie als Turn speichert |
| Fabrik | `runtime.py` | `GuppiRuntime.working_set(...)` |
| Tests | `tests/test_working_set.py` | 27 Tests |

Grenzen (bewusst): Die Relevanz ist lexikalisch (gemeinsame Wörter, Fehler, Dateinamen), nicht semantisch. Ein Block, dessen Wörter
nicht zum Schritt passen, wird nicht zurückgerufen, bleibt aber über seine Id erreichbar. Pins bleiben wörtlich erhalten.

**Noch nicht gemessen:** der Nutzen in einem echten Lauf (Prompt-Einsparung, Prefix-Wiederverwendung). Bisher nur durch Unit-Tests belegt.

## Messungen zu langen Prompts (RTX 4070 Ti, llama-server 2.49.0, je 5 verschiedene Prompts pro Größe)

| Modell | KV | ~7k | ~15k | ~23k | ~31k |
|---|---|---|---|---|---|
| Qwen3.5-9B (hybrid) | q8_0 | stabil | stabil | Absturz bei Anfrage 4 | Absturz bei Anfrage 3 |
| DeepSeek-R1-0528-Qwen3-8B | q8_0, Kontext 32768 | – | stabil (14–16k) | stabil (24–28k) | – |
| Gemma 4 12B QAT | f16 | – | – | – | stabil bis 92k (frühere Messung) |

- **Qwen3.5-Absturz** (`CUDA illegal memory access`, bekannt als llama.cpp #21383, hybride Gated-DeltaNet-Schichten): kein getestetes
  Flag, keine Version, keine Cache-Option und kein MTP-Wechsel hat geholfen. **Der KV-Typ ist nicht die Ursache:** f16 mit und ohne MTP
  sowie q8_0 stürzten bei ~31k alle ab (`long_ctx4.log`, je 3 Läufe). Nicht getestet: eine höhere Gewichts-Quantisierung (Q8/bf16).
- **Folge:** Qwen3.5 ist im Rezept auf 16384 begrenzt (Stufen 8192/16384). Das Arbeitsset soll die Prompts darunter halten.
- **Korrektur einer früheren Aussage:** „Ein stabiler Prefix wird von Qwen vertragen“ war falsch; ein entsprechender Test stürzte
  schon bei der ersten Anfrage ab.
- **DeepSeek mit Kontext 102400:** nur 30–40 Tokens/s Prompt-Verarbeitung, VRAM voll (vermutlich Überlauf in den Arbeitsspeicher).
  Mit 32768 sind es rund 4400 Tokens/s. Das Rezept ist deshalb auf 32768 begrenzt. Die VRAM-Zahlen im Rezept stammen aus dem
  Messwerkzeug (9b, unten), pro Stufe gemessen.

## Offen

Qualitätsvergleich über den llama-server (24 Aufgaben × 4 Varianten), Arbeitsset im echten Lauf messen, Stabilität von Qwen3-14B bei langen Prompts (Download fertig, Prüfsumme gegen Hugging Face geprüft, Speicher gemessen), Kev erst nach Erlaubnis für Download und Installation.

## Messwerkzeug für Rezepte (9b)

`recipe_measure.py` + `benchmarks/measure_recipe.py`: startet das Modell wie das Rezept es sagt, je Kontext-Stufe (kleinste zuerst), liest
den wirklich angewandten Kontext und den GPU-Speicher, schickt eine kurze Anfrage (Rechenpuffer wachsen beim Erzeugen) und entlädt.
Liefert `measured_context`, `measured_vram_gb` (Spitze + Rand, mindestens 0,3 GiB, sonst das 1,5-fache des Wachstums bei der Anfrage)
und `kv_cache_gb_per_1k_tokens` (Steigung zwischen kleinster und größter Stufe). Die GPU muss leer sein (sonst Abbruch). Ohne `--apply`
wird nur `runtime_data/measurements/<id>_<datum>.json` geschrieben; mit `--apply` werden genau diese drei Zeilen des Rezepts in
`local_config/role_routing.yaml` ersetzt (Sicherungskopie daneben). `maximum` und `tiers` ändert das Werkzeug nie: es misst Speicher, nicht
Stabilität bei langen Prompts. 14 Tests in `tests/test_recipe_measure.py`.

Gegenprobe an Gemma (Handwerte 7,41/7,54/7,80 GiB, Rate 0,016): Werkzeug 7,39/7,52/7,79, Rate 0,016, Vorschlag 7,7 = bisheriger Wert.
Gemessen und eingetragen: DeepSeek (5,54 GiB bei 8192, Rate 0,076; bis 32768 7,1 GiB), Qwen3-14B (siehe Rezept; bis 24576 10,3 GiB).

## Arbeitsset im echten Lauf (Gemma, 24 Module + 4 Rückfragen, `benchmarks/workingset_real_run.py`)

Saubere Läufe (leichter Test, Rückfragen fragen denselben Wert wie der frühere Schritt): **naive 28/28, 1,43 Mio. Prompt-Tokens**;
**Arbeitsset 28/28, 0,14 Mio. Tokens** (etwa ein Zehntel). Grenzen: Das Arbeitsset hat in diesem Test nie archiviert oder zurückgerufen
(`blocks 0, recalled 0`), die Einsparung kommt daher, dass große Tool-Ergebnisse ausgelagert werden und die Historie klein bleibt. Der
Abruf aus dem Archiv ist **nicht** belegt: der härtere Test (Rückfrage nach einer zweiten Konstante, die nur in der ausgelagerten Datei steht)
ist im Skript, hat aber noch keinen sauberen Lauf, weil Gemma zweimal Müll lieferte (siehe unten). Wichtig für die Nutzung: Die Datei, um die es
im Schritt geht, gehört in den aktuellen Schritt (`compose(step_task)`), nicht zuerst in die Historie.

## Befund: Gemma liefert zeitweise Müll (offen)

In 4 von 12 Läufen antwortete Gemma ab einem Schritt nur noch `<unused49>…` (finish=length) und blieb im selben Serverprozess kaputt (auch bei
kleinen Prompts), ohne Fehler im Log, bei wechselnden Prompt-Größen (10k, 21k, 32k, 50k). Die anderen 8 Läufe waren 28/28 richtig. Ausgeschlossen: Prompt-Größe,
LM-Studio-Modell-Ladevorgänge, CUDA-Graphen (abgeschaltet: 1 von 5 trotzdem Müll). Offen: f16-Überlauf, Fremdlast auf der GPU, Hardware. Folge: die
Aussage „Gemma stabil bei 100k" gilt für Einzel-Abfragen, nicht belegt für wiederholte Mehrschritt-Läufe. Pipelines müssen Müll erkennen und den Server neu starten.

## Befund 2: GPU-Ausnahmen des Treibers, nicht (nur) ein Modell-Fehler (2026-10-02)

Der Prüflauf `benchmarks/garbage_hunt.py` (frischer Server pro Durchgang, direkte HTTP-Anfragen ohne GUPPI-Aufrufpfad) lief im Basisfall 3 Durchgänge sauber
und stürzte im 4. ab: `CUDA error: an illegal memory access was encountered` in `ggml_cuda_kernel_launch` (Gemma, f16, Kontext 102400, bei ~29k Tokens).
Zur selben Sekunde (11:08:29) schrieb der NVIDIA-Treiber in das Windows-Systemprotokoll `nvlddmkm` Ereignis 13 („Graphics Exception: ESR …") und 153
(„Error occurred on GPUID").

Solche Ereignisse gibt es auf diesem PC schon lange: **1405 in den letzten 60 Tagen** (Ereignis 13 und 153), verteilt auf Tage mit GPU-Last, z. B. 20.08. (139),
04.09. (304), 18.–22.09. (75/66/19/130/113), 01.10. (446, davon 354 in der Stunde der Qwen3.5-Absturzmatrix), 02.10. (8). Das sind Zeiten vor jeder GUPPI-Messung.
Der Treiber (32.0.16.1692, Datum 04.09.2026) trägt dasselbe Datum wie der erste große Ausschlag; ob er an dem Tag installiert wurde, ist nicht geprüft.

Folgerung: Die beiden Fehlerbilder (Qwen3.5: Absturz ab ~23k Tokens; Gemma: zeitweise Müll-Ausgabe und gelegentlich Absturz) haben mindestens eine gemeinsame
Ursache auf GPU-/Treiber-Ebene nicht ausgeschlossen. Die Einordnung von Qwen3.5 als reiner Modell-/llama.cpp-Fehler (#21383) ist damit nicht mehr sicher;
der Absturz bei fester Prompt-Größe sprach für einen Software-Fehler, das Gemma-Bild (zufällig, Müll, Ereignis 13) eher für Instabilität. Beides kann zutreffen.
Nicht geprüft (Systemeinstellungen, nur der Captain): Takt/Speichertakt/Leistung zurücksetzen oder senken (MSI Center, NVIDIA-App-Tuning, `nvidia-smi -lgc`),
anderer Treiber. Danach `garbage_hunt.py --variants baseline --runs 8` wiederholen. Die Varianten (cache_ram0, cache_prompt_off, kv_q8, flash_off) sind im Werkzeug
vorbereitet, aber nicht gelaufen: sie sind erst sinnvoll, wenn die Hardware-Seite geklärt ist.

## gpt-oss-20b als Modell im Projekt, Arbeitsset-Abruf aus ausgelagerten Ausgaben (2026-10-02)

**Rezept** `coder.llama_gptoss20b` in `local_config/role_routing.yaml` (MXFP4, 12,1 GB, SHA-256 eingetragen). Neue geprüfte Server-Option
`n_cpu_moe` (`llama_server_runtime.build_command`, `role_routing.py`, Tests): die Experten-Gewichte der ersten N Schichten bleiben im RAM, der Rest
liegt auf der GPU. Gemessen (NVIDIA-Studio-Treiber 616.92, GPU-Debug-Modus = Referenztakt, KV q8_0, Kontext 65536, Werkzeug `moe_modelltest.py` in <hermes>/Hermes Arbeits ordner/tools):
`n_cpu_moe` 4 = 11,0 GB, 837 Token/s Prompt, 85 Token/s Antwort; 3 = 11,4 GB, 1047 / 94; 2 = 11,5 GB, läuft aus dem VRAM (Antwort 41). Das Rezept nimmt 4 (0,4 GB Luft).
Qwen3-30B-A3B-Instruct-2507 (`n_cpu_moe` 30-32): 43 Token/s, 266 Token/s Prompt; Original Qwen3-30B-A3B hat nur 40960 Kontext und erfüllt Hermes' 64K nicht.
Grenze des Verfahrens: ab etwa 11,5 GB belegtem VRAM läuft der Treiber in den Hauptspeicher über, das Tempo bricht auf ein Drittel ein.

**Qualität** (`token_quality.py`, 24 Aufgaben, `TQ_VARIANTS=default,low,medium,high`): default 24/24 (2,3 s, 133 Token), low 24/24 (1,4 s, 59 Token),
medium 24/24, high 23/24 (6,3 s; eine Aufgabe lief bis 3000 Token ohne Antwort). gpt-oss kennt kein `reasoning_effort: none`, nur low/medium/high.
Der Test ist für dieses Modell an der Decke (nichts trennt mehr); ein härterer Aufgabensatz fehlt noch.

**Arbeitsset, harter Test** (zweite Konstante steht nur in der ausgelagerten Datei): vor der Änderung 24/28, die vier Rückfragen waren geraten
(`blocks 0, recalled 0`). Ursache war GUPPI, nicht das Modell: große Tool-Ergebnisse gehen als Kurzfassung in den Verlauf, `compose` rief aber nur
Auszüge aus verdichteten Blöcken ab, nie aus ausgelagerten Ausgaben. Neu: `WorkingSet._recall_offloaded` liest die passenden Zeilen aus dem
hash-geprüften Artefakt (Wörter der Frage, nach Seltenheit über alle Ausgaben gewichtet, höchstens 2 Ausgaben und 40 Zeilen, innerhalb des Budgets,
deterministisch, am Ende des Prompts wegen der Präfix-Wiederverwendung). Bei langen Schritten zählt nur der letzte Absatz als Frage (`_ask_of`), damit
eingefügter Quelltext keine Abrufe auslöst. Ergebnis mit gpt-oss (effort low, 256 Token): **28/28**, 116,6k statt 113,1k Prompt-Tokens (+3 %).
Das Arbeitsset-Skript hat dafür `--effort` und `--max-tokens` (vorher fest `none` und 60: ein Modell, das denkt, lief bei 60 Token in `length`) und stürzt bei
leerer Antwort nicht mehr ab. 8 neue Tests in `tests/test_working_set.py` (35 insgesamt), gesamte Suite 1002 Tests OK.

**GPU-Vorprüfung** `gpu_preflight.clear_leftovers` (Hook `lab.lease(..., preflight=...)`, in allen Messskripten, Kommando `testlab_cli.py clean`): nur
unter gehaltener Sperre; beendet einen verwaisten GUPPI-llama-server (Port 8089 oder Startsignatur `--no-webui --spec-type` im LM-Studio-Backend-Ordner),
sonst nichts. Ist der Port von etwas anderem belegt oder die GPU über 2,5 GiB voll, wird der Lauf mit Namen der Verursacher abgelehnt, nichts fremdes beendet.
Anlass: ein Rest von 8 GB machte die erste Messung des Tages wertlos.

