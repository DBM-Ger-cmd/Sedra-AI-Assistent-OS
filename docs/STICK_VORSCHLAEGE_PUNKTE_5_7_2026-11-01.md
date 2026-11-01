# USB-Stick: Vorschläge zu den Punkten 5–7 des Entwicklerpakets (1.11.2026, ohne Branch)

Grundlage: `ENTWICKLERPAKET_USB_STICK_2026-10-31.md` §6 (Aufgaben 5–7). Der Branch `claude/usb-stick-minimal-3c1b19` ist nicht auf GitHub
(E-A5: kein Push → Punkte 5–7 als Bericht). Geprüft wurde nur, was in `origin/main` (`bf20ff5`) liegt; Aussagen über K:\, I:\ oder Modelltests
stammen aus dem Paket und sind so gekennzeichnet. Nichts davon ist im Code umgesetzt – alles sind Vorschläge für die Entscheidung des Captains.
Die Punkte 1–4 (Plan-Abgleich, `stick_liste.txt`/`stick_paket.py`, Tests, `test_ki_aufteilung_beweis`) brauchen den Branch und bleiben offen.

## 5. Modellzuordnung `model_profiles.yaml` (Vorschlag, nicht im Code)

**Stand in `main`:** `runtime/config/model_profiles.yaml` (Schema 2, Strategie `qwen3.5_plus_kev_local_first`) kennt nur Qwen3.5 (0.8B/4B/9B) je
Hardware-Klasse (`cpu_small`, `cpu_16plus…`, `nvidia_small`, `nvidia_6_8`, `nvidia_10_12`, `nvidia_16plus`, `nvidia_24plus`, `apple_unified_*`) mit Kev
als Prüfmodell. Bonsai, Nemotron und Gemma stehen dort nicht; die Stick-Fassung (laut Paket geändert, Original `.orig`) ordnet Bonsai den kleinen und
Gemma den größeren Klassen zu – das widerspricht der Zwei-Stufen-Entscheidung (Basis: Bonsai + Nemotron; Erweiterung: Qwen3.6-35B, Qwen3.5-9B-MTP, Gemma 4 12B).

**Vorschlag (Stick-Fassung der Datei, `runtime/config/model_profiles.yaml` auf K:, nie `local_config/`):**

| Klasse | Preset | Modell (Rezept) | Begründung |
|---|---|---|---|
| `nvidia_6_8` (der Kollege: 8 GB VRAM, 16 GB RAM) | `stick-basis-nemotron` | **Nemotron 3.5 Bolt E4B Q4_K_M** (6,2 GB) | Basis-Pflicht, passt mit KV q8_0 und 8–16k Kontext in 8 GB; dichtes Modell, keine MoE-Aufteilung nötig. Ausweich bei `hardware_pressure`: Bonsai. |
| `nvidia_small`, `cpu_16plus` | `stick-basis-bonsai` | **Bonsai-27B Q1_0** (3,8 GB + mmproj 0,9 GB) | kleinster Speicherbedarf der Basis; mmproj nur laden, wenn Bilder gebraucht werden (sonst 0,9 GB gespart). |
| `nvidia_10_12` | `stick-erw-qwen9b` | Qwen3.5-9B-MTP Q6_K (7,7 GB), sonst Nemotron | Erweiterung, nur wenn vorhanden (`stick_liste`: optional); MTP-Rezept wie im Harness-Vergleich (b11160, Kontext 65536). |
| `nvidia_16plus`, `nvidia_24plus` | `stick-erw-qwen35b` | Qwen3.6-35B-A3B IQ4_XS (17,7 GB, dynamische Aufteilung) · Gemma 4 12B QAT als zweite Wahl | Erweiterung: ≥ 18 GB RAM laut Rezept; Gemma für Bild-Eingaben (mmproj). |
| `cpu_small`, `apple_unified_small` | `stick-basis-bonsai` mit `gpu_layers: 0` | Bonsai | läuft, aber langsam – im Start-Skript als Warnung nennen. |

Regeln dazu: (a) Die Basis-Presets dürfen nie auf ein Erweiterungs-Modell zeigen, das auf dem Stick fehlen kann – `stick_paket.py` prüft die
Dateien der Basis als Pflicht, die der Erweiterung als optional (Aufgabe 2). (b) Kev als Prüfmodell entfällt auf dem Stick (nicht im Paket);
`verification` auf `none` oder weglassen, sonst sucht der Scheduler ein Modell, das es nicht gibt. (c) Die Rezepte (Aufgabe 7 im Paket: fehlen im
Repo) gehören in eine `role_routing.yaml`-Vorlage für den Stick (`runtime/config/role_routing.stick.yaml`), die `START_SEDRA.bat` nur kopiert,
wenn `local_config/role_routing.yaml` fehlt – die Datei des Captains bleibt unberührt. (d) Für den Harness-Katalog des Sticks: `modell_laden`
für die Basis-Rezepte `frei` (Auto-Laden beim Senden, Bau 1.11. M2/E-A7) – sonst sieht der Kollege „Kein Modell geladen“.

Kosten: eine YAML-Vorlage + Tests (`test_stick_paket` erweitern), ≈ 2 h; keine Code-Änderung am Kern.

## 6. `fenster/rekorder.html` – Entscheidungsvorlage

**Befund in `main`:** Die Datei gibt es nicht (`find` leer). Sie wird nur in zwei Berichten genannt (`SHELL_TRANSLATOR_TECHNIK_2026-10-20.md`:
„eigenes Aufnahmefenster, 107 Zeilen, überlebt den Shell-Wechsel“; `SEDRA_KERN_UND_KMU_SHELL_AUSFUEHRLICH_2026-10-20.md`). Kein Code in
`uix/shells/fisch`, `ui/sprache.js` oder `ui/wechsel.js` öffnet sie (`grep rekorder.html` ohne Treffer außerhalb von `docs/`). Der Rekorder der
Translator-Shell läuft als Werkzeug `rekorder` im Mini-Hub (`.sx-hub-leiste .sx-chip`, Stufe 6 R1) – also **ohne** eigenes Fenster.

| Weg | Was | Kosten | Risiko |
|---|---|---|---|
| **A Weglassen (Vorschlag)** | Translator-Shell auf dem Stick mit dem Hub-Rekorder; Paket-Text und `stick_liste.txt` ohne `fenster/rekorder.html` | 0 h Code, 10 min Doku | Die Aufnahme bricht beim Shell-Wechsel ab (der Hub lädt neu). Für den Kollegen (Harness als Standard) ohne Belang. |
| B Nachbauen | Ein eigenes Fenster (`window.open`, eigene Seite unter `/fenster/rekorder.html` mit CSP `script-src 'self'`, Token-Übergabe, Strom zurück über `BroadcastChannel`) | ≈ 1 Tag inkl. Tests (Browser-Bahn, Herkunft, Token) | neue Angriffsfläche (zweites Fenster mit Token), CSP-Ausnahme, Fenster-Blocker im Browser; ohne Captain-PC nicht abnehmbar. |
| C Später | Weglassen jetzt, B als eigene kleine Spec nach dem Stick | wie A | – |

Empfehlung: **A**, mit C als Merkposten im `PLAN_USB_STICK_v1.md`. Die Berichte vom 20.10. beschreiben einen Stand, der nicht in `main` ist
(Widerspruch im Sinne von Paket §4) – im Plan vermerken, nicht übernehmen.

## 7. Ladezeit vom Stick (33 MB/s → 3 min für 6 GB) – Vorschläge ohne Kernumbau

Zahlen aus dem Paket (nicht selbst gemessen): K: liest ≈ 32 MB/s, J: ≈ 43 MB/s, I: ≈ 501 MB/s; Nemotron (6,2 GB) lädt von I: in 15 s.
Bei 32 MB/s sind 6,2 GB rechnerisch 194 s – die 3 Minuten sind der Stick, nicht SEDRA. Drei Wege, von billig nach aufwendig:

1. **Kopie auf die lokale Platte beim ersten Start (Vorschlag):** `START_SEDRA.bat` fragt einmal „Modelle nach `%LOCALAPPDATA%\SEDRA\modelle`
   kopieren? (6 GB, ≈ 3 min, danach 15 s je Start)“ – mit Ja kopiert es die Basis-Modelle (Robocopy, Hash-Prüfung gegen `STICK_MANIFEST.json`)
   und schreibt `local_paths.yaml` mit `modelle: '%LOCALAPPDATA%\SEDRA\modelle'` (Option B des Captains: Pfade über `local_paths.yaml`, keine
   Junctions). Ohne Ja bleibt der Stick die Quelle. Kosten: Skript + Prüfung ≈ 3 h. Vorteil: löst die Ladezeit vollständig, und die beschädigten
   Kopien (Paket §3.4) fallen bei der Hash-Prüfung auf.
2. **`mmap` aus für Stick-Starts:** `llama_server_runtime` kennt `mmap: false` → `--load-mode none` (liest die Datei einmal sequenziell statt sie
   zu mappen). Vom Stick ist sequenzielles Lesen schneller als die Seitenfehler des Mappings (USB-Sticks brechen bei wahlfreiem Zugriff ein);
   dazu `--mlock`? nein – 16 GB RAM. Kosten: ein Feld im Stick-Rezept (`server: {mmap: false}`), 0 Code. Gewinn geschätzt 10–30 %, nicht gemessen.
3. **Vorladen im Hintergrund:** `START_SEDRA.bat` liest die Basis-Modelldatei nach dem Serverstart einmal in den Datei-Cache (`type datei > nul`
   bzw. PowerShell `Get-Content -ReadCount`), während der Kollege die Oberfläche öffnet; der spätere Modellstart kommt aus dem Cache (bei 16 GB
   RAM reichen 6 GB Cache nur, solange nichts anderes läuft). Kosten ≈ 1 h; Gewinn nur beim ersten Laden je Sitzung, verpufft bei RAM-Druck.

Nicht empfohlen: Pufferung im Kern (eigener Lade-Thread) – Umbau am Modell-Lader, den das Paket ausschließt; schnellerer Stick (J: 43 MB/s)
ändert wenig. Reihenfolge: 1 jetzt, 2 als Rezeptfeld dazu, 3 nur wenn 1 abgelehnt wird.

## Was im Repo dafür geändert würde (nur nach Ja)

| Datei | Änderung |
|---|---|
| `runtime/config/role_routing.stick.yaml` (neu) | Rezepte Basis/Erweiterung mit `mmap: false`, Kontext und KV-Typ |
| `runtime/config/model_profiles.stick.yaml` (neu) oder Stick-Fassung | Presets aus §5 |
| `START_SEDRA.bat`, `runtime/benchmarks/stick_paket.py`, `stick_liste.txt` | Kopier-Frage, Hash-Prüfung, Basis/Erweiterung |
| `docs/PLAN_USB_STICK_v1.md` | Merkposten Rekorder-Fenster (C), Ladezeit-Weg 1 |
| `local_config/**`, K:\, I:\ | **nichts** |
