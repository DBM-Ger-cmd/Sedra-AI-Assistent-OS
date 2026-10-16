# Phase 8f – GUPPI startet und überwacht seinen eigenen llama-server (2026-10-01)

Auslöser: Bei langen Erzeugungen stürzte die qwen-Engine in LM Studio ab (`CUDA error: an illegal memory access`, danach
HTTP 400 für alle Anfragen, und LM Studio lud still mit eigenen Standardwerten neu: 2 Slots, 100k Kontext). Vorschlag des Captains:
das Modell direkt anzapfen und die Lade-Funktion selbst übernehmen. Umgesetzt mit dem `llama-server.exe`, das LM Studio
mitbringt (nichts heruntergeladen oder installiert; LM Studios Ordner werden nur gelesen).

## Was gebaut ist (alles hinter Schaltern)

| Teil | Datei | Inhalt |
|---|---|---|
| Prozess-Verwaltung | `llama_server_runtime.py` | startet/stoppt/überwacht genau einen `llama-server`; gleiche Schnittstelle wie der LM-Studio-Controller (`loaded_models`/`load_model`/`unload_model`) |
| Einstellungen | `config/llama_server.yaml` | Version (festgenagelt auf 2.49.0), Port 8089, nur Loopback, Zeitlimits, `mtp`, `flash_attn` |
| Lader | `model_loader.py` | mehrere Provider: wählt den Controller nach `resolution["provider_ref"]`; Verdrängen untätiger Modelle über alle Provider |
| Rezepte | `profile.server` im Rezept | `gguf`, `kv_cache_type`, `mmproj`, `reasoning`, `reasoning_budget`, `mtp` (strukturiert, keine freien Argumente) |
| Schalter | `local_config/switches.yaml` | `llama_server: {enabled, mtp}` |

Ablauf eines Starts: Befehl wird aus dem Rezept gebaut (`-m`, `-c`, `-ngl`, `-np 1`, `-ctk/-ctv`, `-fa`, `--alias`, `--spec-type`,
`--reasoning`, optional `--reasoning-budget`, `--no-mmproj`), Prozess startet ohne Shell mit den CUDA-Bibliotheken im Suchpfad,
GUPPI wartet auf `/health`, liest danach über `/props` den **wirklich angewandten** Kontext und gibt ihn an den Lader zurück
(stimmt er nicht, wird gestoppt und der Start schlägt fehl). Beendet sich der Prozess von selbst, ist das ein Absturz: er wird
mit Exit-Code vermerkt, und der nächste Job startet neu. Ein fremder Server auf dem Port wird nie übernommen oder beendet.

## MTP (spekulatives Entwurfs-Decoding): an und aus

- Direkter Pfad: global `llama_server.mtp` (Standard `true`; in `local_config/switches.yaml` auf `false` setzbar) **und** im Rezept
  `profile.server.mtp: true`. Beides muss stimmen; nur Modelle mit MTP-Kopf sollen es anfordern (qwen: ja, gemma: nein).
- LM-Studio-Pfad: MTP bleibt aus (`model_loader.yaml: mtp: false`), weil dort die Abstürze auftraten.
- Gemessen am direkten Pfad: 0 Abstürze in 4 von 4 langen Läufen mit MTP, rund doppelte Geschwindigkeit (qwen 140 statt 69 Tokens/s).

## Messungen

Stabilität (4 lange Denk-Aufgaben je Lauf, einziger Prozess auf der GPU): qwen ohne MTP 0/4, qwen mit MTP 0/4, gemma 0/4.

VRAM (GUPPIs eigener Start, `--no-mmproj`, ein Slot, idle nach dem Start, Basis 0,53 GiB abgezogen; Start dauert 5–6 s):

| Kontext | qwen ohne MTP | qwen mit MTP | gemma |
|---|---|---|---|
| 8192 | 5,50 | 5,92 | 7,41 |
| 16384 | 5,67 | 6,14 | 7,54 |
| 32768 | 6,02 | 6,53 | 7,80 |
| 65536 | 6,71 | 7,35 | 8,33 |

In allen 12 Starts wurde der angeforderte Kontext von `/props` bestätigt. Die Rezepte tragen diese Werte plus 0,3 GiB für Puffer.
Gegenüber LM Studio spart der direkte Pfad bei qwen rund 2 GiB (kein mmproj).

Request-Felder direkt am `llama-server` (qwen und gemma gleich): `reasoning_effort: none` und `chat_template_kwargs.enable_thinking=false`
schalten das Denken ab; `thinking_budget_tokens` und `reasoning_budget_tokens` begrenzen es; unbekannte Felder werden ignoriert
(kein Absturz). Der Adapter sendet trotzdem nur fest erlaubte Felder.

**Einschränkung der LM-Studio-Zahlen:** Der Absturz-Test mit den Zählungen 5/5, 0/5 und 1/5 lief gleichzeitig mit einem vergessenen
Hintergrundlauf meines ersten Qualitätsvergleichs, der LM Studio ständig neu laden ließ. Diese Zahlen sind nur ein Hinweis. Die CUDA-
Abstürze standen aber schon im Log, als nur dieser eine Lauf aktiv war.

## Echt geprüft

Golden Path (Dokumentations-Job → Prüfung → Prüf-Job → Gate) mit qwen (MTP an) und gemma über den eigenen `llama-server`, alle
Schalter nur aus den lokalen Dateien: Kontext 8192 bestätigt, qwen verdrängt, gemma geladen, Prüfung PASS, `READY_FOR_ACCEPTANCE`,
Nachweis- und Audit-Kette gültig, am Ende kein Prozess und GPU wieder bei 0,53 GiB.

## Rezepte auf diesem PC (`local_config/role_routing.yaml`)

Reihenfolge: 1. `coder.local_primary` und `verifier.llama_gemma` (eigener llama-server), 2. `coder.lmstudio_qwen` und
`verifier.lmstudio_gemma` (LM Studio, Rückfall bei Ausfall des ersten Anbieters).

## Grenzen und Offen

- **Ein Server, ein Modell:** Modellwechsel heißt Stoppen und Neustarten (5–6 s). Kein gleichzeitiges Laden beider Modelle.
- **Reste früherer Läufe:** Läuft nach einem Absturz von GUPPI noch ein eigener Server, wird das gemeldet (`leftover()`), aber nicht
  automatisch beendet. Das Aufräumen verwaister Server beim Start ist nicht gebaut.
- **Denk-Tokens:** `llama-server` meldet sie nicht in `usage`. Der Bericht enthält deshalb `reasoning_chars` (Größe des Denk-Textes).
- **MTP bei gemma** ist nicht getestet (im Rezept aus). **`reasoning_budget`** ist hier ein Startwert pro Modell; pro Anfrage
  überschreiben es die Felder der Token-Richtlinie.
- **Abhängigkeit:** Die Engine liegt in LM Studios Ordner. Wird sie entfernt oder aktualisiert, meldet der Provider „nicht gefunden“
  und der Router fällt auf LM Studio zurück. Eine eigene Engine lässt sich über `backend_dir`/`vendor_dir` eintragen.
- **Qualitätsvergleich** (Denken an/aus, Budgets) ist noch nicht über diesen Pfad wiederholt. Der erste Versuch scheiterte an den
  LM-Studio-Abstürzen.
- **Kev** wurde nicht angebunden (siehe PHASE8_STATUS: Kev ist nicht installiert, nicht im Prüfgate).
