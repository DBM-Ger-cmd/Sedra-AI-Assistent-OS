# Flash Attention auf der RTX 4070 Ti: Untersuchung vom 2026-10-09

Auftrag des Captains: herausfinden, wie Flash Attention arbeitet, sie wieder anbekommen oder eine ähnliche Lösung finden. Stand am Ende des Tages: **Flash Attention bleibt aus.** Alle Zahlen stehen auch im Logbuch (`docs/LOGBUCH_AGENT_MANAGER.md`).

## Was Flash Attention für GUPPI bedeutet

Flash Attention rechnet die Aufmerksamkeit in Kacheln, ohne die große Zwischentabelle im Speicher aufzubauen. Ohne sie:

1. **Der Rechenpuffer wächst mit dem Fenster.** Bei 32k passt `ubatch` 2048 nicht in den VRAM; wir laden mit 1024. Das halbiert fast die Einlesegeschwindigkeit (Qwen3-Coder 196 statt 380 Token/s).
2. **Der V-Cache lässt sich nicht quantisieren** (Startfehler „quantized V cache requires flash_attn to be enabled“, so bei DeepSeek und Hermes). Der K-Cache schon.
3. **DeepSeek-Coder-V2-Lite (MLA-Aufmerksamkeit) ist bei 32k unbrauchbar:** Einlesen 17 und Erzeugen 0,3 Token/s, VRAM voll. Bei 8k mit 8 Expertenschichten im RAM dagegen 561 und 73 Token/s.
4. Messung vom 2026-10-05: Bei Qwen3-Coder kostet „aus“ nur etwa 2 % Erzeugungsgeschwindigkeit, bei kleinen Modellen etwa ein Fünftel beim Einlesen langer Prompts. Mein Schätzwert für den Gewinn im Bau: grob 5 bis 15 %.

## Was wir über den Absturz wissen

Mit Flash Attention an stürzt der Server mit `CUDA error: illegal memory access` ab (jedes Mal 6 bis 7 Treiberereignisse `nvlddmkm` im Windows-Log).

| Test (Jan-code-4b, 2 bis 6 frische Starts) | Ergebnis |
|---|---|
| 2026-10-05, b11371, Treiber 616.92 | 0 von 2 sauber (Absturz nach 10 und 21 Anfragen) |
| 2026-10-05, Qwen3-Coder, SWE-Review | 1 von 2 und 0 von 2 |
| 2026-10-05, Flash Attention aus | 6 von 6 sauber (alle drei Modelle) |
| 2026-10-09, b11371, **neuer Treiber 617.42** | 0 von 2 (29, 9) |
| 2026-10-09, **b11530** (neuester Build) | **1 von 6 sauber** (5, 24, 38, 41, 66; einmal 82 Anfragen sauber) |
| 2026-10-09, b11371, Flash Attention + `q8_0`-Cache | 0 von 2 (9, 2) |
| 2026-10-09, `CUDA_LAUNCH_BLOCKING=1`, b11371 | Absturz nach genau 5 und 5 Anfragen (deterministisch) |
| 2026-10-09, `CUDA_LAUNCH_BLOCKING=1`, b11530 | 11 (CUDA) und 28 (anderer Fehler, siehe unten) |

Der Treiber allein behebt es nicht, der neue Build verbessert wenig. Der Fehlerort bleibt unscharf: gemeldet wird `ggml_cuda_kernel_launch` (allgemeiner Startpunkt jedes Kerns), der Kernel wird nicht genannt.

**Zusatzbefund b11530:** Ein Lauf endete mit HTTP 500 und „Unexpected empty grammar stack after accepting piece“. Das ist ein Fehler der Werkzeugaufruf-Grammatik des neuen Builds, kein CUDA-Fehler. Bei einem Wechsel des Standard-Builds muss das Werkzeugaufruf-Verhalten gegengeprüft werden.

## Hypothese (nicht bewiesen)

Zwischen b11371 und b11530 liegen 159 Änderungen. Relevant sind „CUDA: fix MMQ out-of-bounds reads“ (#29953), „CUDA: fix MMQ memory fault if n_expert >> n_ubatch“ (#29941), „ggml-cuda: per-thread stream for buffer-init padding memset“ (#28782). Nicht der Flash-Attention-Kern selbst, sondern ein Lesezugriff außerhalb des Speichers im Matrixkern MMQ, dessen Folgen von der Lage der Rechenpuffer abhängen. Das würde erklären, warum „Flash Attention aus“ funktioniert und b11530 teilweise hilft.

## Werkzeug zur Klärung: Compute Sanitizer

`engines/tools/compute-sanitizer-12.4.127` (Version 2024.1.1.0, 14 MB, Prüfsumme bestätigt) ist installiert und in den Absturztest eingebaut (`LlamaServerRuntime.launcher`, Varianten `sanitizer_*`). Es meldet jedoch: „Failed to initialize WDDM debugger interface. Please run EnableDebuggerInterface.bat as an administrator“ und „Device not supported“. Dafür muss eine Systemeinstellung geändert werden (`HKLM\SOFTWARE\NVIDIA Corporation\GPUDebugger`, `EnableInterface` auf 1). Das ist Sache des Captains. Zurücknehmen: Wert 0.

## Andere Wege, ohne Flash Attention schneller zu werden (gemessen)

- K-Cache `q8_0` (geht ohne FA): kein Gewinn bei Qwen3.6 (nur wenige Schichten haben einen Cache).
- `ubatch` 1536: kein Gewinn, weniger freier VRAM.
- 26 statt 28 Expertenschichten im RAM: 339 und 47,2 Token/s statt 316 und 45, aber nur 0,85 GiB frei (über dem Limit von 11,5 GB).
- Volle GPU (alle Experten auf der Karte): langsamer, weil Windows in den gemeinsamen Speicher auslagert.
- Größere Hebel: schnelleres Modell (Qwen3.6 ist 2,8-mal schneller als Qwen3-Coder im Standardtest), MTP-Variante, kleineres Quant (je mit Download), mehr VRAM.

## Entscheidungen, die offen sind

1. Compute Sanitizer freischalten (Registry-Wert, Admin)?
2. Neuer Build b11530 als Standard? Nein, solange die Absturzrate 5 von 6 und die Grammatikfehler offen sind.
3. Neue llama.cpp-Builds in einigen Tagen erneut mit dem Absturztest prüfen (Aufruf: `cuda_crash_hunt.py … --variants engine_<build>`).
