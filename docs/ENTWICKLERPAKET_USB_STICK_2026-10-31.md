# Entwicklerpaket: SEDRA-Minimalversion auf USB-Stick (Stand 31.10.2026)

Dieses Paket fasst alle Erkenntnisse aus den Sitzungen vom 20. bis 31.10.2026 zusammen, soweit sie den USB-Stick (K:\) betreffen. Es ist für einen Cloud-Worker gedacht, der nur das Repository sieht. Der Cloud-Worker hat keinen Zugriff auf K:\, I:\ oder die lokalen Modelle.

## 1. Ziel

Eine portable Minimalversion von SEDRA auf einem USB-Stick (GIGASTONE, exFAT, entfernbar), die ein Arbeitskollege auf einem Windows-PC mit 16 GB RAM und 8 GB VRAM startet. Eine Erweiterung für starke Systeme ist optional vorgesehen.

Umfang: Kern, Harness-Shell (Standard), Cockpit, Paperclip, Translator-Shell (Ordner `uix/shells/fisch`, intern noch „fisch“). Nicht enthalten: Start-, Minimal-, Gateway-, Guppi-XP-Shell, Wissensbasis, Vorlagen, das Projekt als Ganzes.

## 2. Festgelegte Entscheidungen (Captain)

Quelle: `docs/ENTSCHEIDUNGEN_USB_STICK.md`. Diese Entscheidungen sind nicht neu zu verhandeln.

- **Pfade, Option B:** Keine Junctions oder Symlinks (exFAT unterstützt sie nicht). Das Programm bekommt Modellordner über `local_paths.yaml`. Relative Ordner zählen ab `runtime\`; `modelle: '..\modelle'` zeigt auf `K:\SEDRA\modelle`.
- **Zwei Modellstufen (31.10.2026):**
  - Basis, Pflicht auf jedem Stick: Bonsai-27B Q1_0 mit mmproj (für 16 GB RAM / 8 GB VRAM) und Nemotron 3.5 Bolt E4B.
  - Erweiterung, optional, für starke Systeme: Qwen3.6-35B-A3B (laut Rezept mindestens 18 GB RAM), Qwen3.5-9B-MTP, Gemma 4 12B QAT mit mmproj.
- **Modelle bleiben auf I:\KI-Daten\modelle**; der Stick bekommt Kopien.
- **Translator-Shell** braucht zusätzlich die Werkzeuge `uebersetzer`, `nachrichten`, `transkript`, `rekorder`, die Kern-Module `fisch/` und `sprache/`, `ui/sprache.js`, `ui/wechsel.js` und `fenster/rekorder.html`. Eine „Transkript-Shell“ gibt es nicht; gemeint ist die Translator-Shell.

## 3. Stand je Bereich

### 3.1 Repository (Branch `claude/usb-stick-minimal-3c1b19`, Worktree `.claude\worktrees\usb-stick-minimal-3c1b19`)

Commits, **nur lokal, nicht auf GitHub, nicht in `main`**:

| Commit | Inhalt |
|---|---|
| `07f49fa` | Erster Plan (liegt auch als `origin/plan/usb-stick-minimal`, überholt) |
| `03bd44e` | Plan, relative Modellordner (Option B), Paketbau `stick_paket.py` mit Importhülle, Tests |
| `c1a9d29` | Stick-Liste um `desk.html`, `retro_desktop.html`, `dashboard.html` ergänzt (Start brach ohne sie mit FileNotFoundError ab) |
| `33fccca` | Stand 31.10.; Bonsai in der Modellliste |
| `8a5a427` | Zwei-Stufen-Modelle im Plan und in den Entscheidungen |

Dateien: `docs/PLAN_USB_STICK_MINIMAL.md`, `docs/ENTSCHEIDUNGEN_USB_STICK.md`, `runtime/benchmarks/stick_paket.py`, `runtime/benchmarks/stick_liste.txt`, `runtime/src/guppi_runtime/local_paths.py` (relative Ordner), `runtime/tests/test_local_paths.py`, `runtime/tests/test_stick_paket.py`.

`main` und `spec/agenten-orchestrierung` stehen auf `bf20ff5`. Nichts davon ist gepusht oder gemergt.

Die Dateien `docs/ENTSCHEIDUNGEN_USB_STICK.md` und `docs/WISSEN_SEDRA_GESAMT.md` liegen im Hauptcheckout als untracked (nicht committet).

### 3.2 Stick K:\SEDRA (Stand 31.10., aus den Sitzungen; nicht vom Cloud-Worker prüfbar)

- Programm: `K:\SEDRA\` mit `START_SEDRA.bat`, `STICK_MANIFEST.json`, `runtime\`, `workspace\`, `architecture\`, `LICENSE`. Manifest-Stand `c1a9d29`: 734 Dateien, 781 499 521 Byte.
- Engine `engines\llama.cpp\b11160\`: 31 Dateien, 715 MB. `verify_engine(full=True)` ergibt `(True, 'ok')`.
- Portables Python `runtime\portable\python\current\` (Python 3.14.8, PyYAML 6.0.3). Kopie aus `runtime\portable\python.aus\current\` des Bau-PCs. `Test-PortableRuntime.ps1` grün.
- Konfiguration: `runtime\config\local_paths.yaml` (`modelle: '..\modelle'`); `workspace\GUPPI_OS\local_config\uix.yaml` mit Harness als Standard.
- `runtime\config\model_profiles.yaml` auf dem Stick geändert; Original als `model_profiles.yaml.orig`. Die Zuordnung dort (Bonsai für kleine GPU-Klassen, Gemma für größere) passt **nicht** zur Zwei-Stufen-Entscheidung (Nemotron ist Basis, Gemma Erweiterung). Offen.
- Modelle unter `K:\SEDRA\modelle\` (Größen gegen I: verglichen, alle gleich; Hashes siehe 3.3):

| Modell | Datei | Größe (Byte) | Stufe |
|---|---|---|---|
| Bonsai-27B Q1_0 | `lmstudio-community\Bonsai-27B-GGUF\Bonsai-27B-Q1_0.gguf` | 3 803 452 576 | Basis |
| Bonsai mmproj | `...\mmproj-Bonsai-27B-BF16.gguf` | 931 145 888 | Basis |
| Nemotron 3.5 Bolt E4B Q4_K_M | `lmstudio-community\NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF\NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf` | 6 180 446 208 | Basis |
| Qwen3.6-35B-A3B IQ4_XS | `unsloth\Qwen3.6-35B-A3B-GGUF\Qwen3.6-35B-A3B-UD-IQ4_XS.gguf` | 17 730 509 792 | Erweiterung |
| Qwen3.5-9B-MTP Q6_K | `unsloth\Qwen3.5-9B-MTP-GGUF\Qwen3.5-9B-Q6_K.gguf` | 7 684 551 008 | Erweiterung |
| Gemma 4 12B QAT Q4_0 | `lmstudio-community\gemma-4-12B-it-QAT-GGUF\gemma-4-12B-it-QAT-Q4_0.gguf` | 6 975 879 008 | Erweiterung |
| Gemma mmproj | `...\mmproj-gemma-4-12B-it-QAT-BF16.gguf` | 175 115 328 | Erweiterung |

Summe rund 40 GiB.

### 3.3 Integritätsprüfung der Kopien

- Per SHA-256 gegen I: geprüft und identisch: **Nemotron, Qwen3.5-9B, Bonsai-27B** (Ersatzkopien am 31.10.: 10:55, 11:18, 11:44).
- Nur Stichprobe (Blöcke à 64 MB bei 0, 1/4, 1/2, 3/4, Ende): **Gemma und Qwen3.6**. Vollständige SHA-256-Prüfung fehlt.
- Bonsai-mmproj war zeitweise auf K: nicht vorhanden; später kopiert, Größe passt.

### 3.4 Start-Versuche und Befunde

- `START_SEDRA.bat --gewaehlt` auf K:: Server startet, meldet `http://127.0.0.1:57306/`. `/` und `/retro` liefern HTTP 200; `/api/state` ohne Token 403 (erwartet).
- Hängen beim Engine-Check: `engine_download.py` fragte „JA“, weil die Prüfung während laufender Kopien fehlschlug. Nach Abschluss der Kopien: Prüfung ok. Die Frage nach „JA“ ist bewusst; ohne „JA“ wird nichts aus GitHub geladen.
- **Nemotron auf K: gab nur `<unused32>`-Tokens.** Ursache: beschädigte Stick-Kopie (Mitte und Ende unterschiedlich, Größe gleich). Der gleiche Start von der E:-Checkout mit der I:-Datei lieferte korrekt „Paris“ (Laden 15 s). Die Warnungen zu Steuerzeichen-ähnlichen Tokens erscheinen in beiden Fällen und sind nicht die Ursache. Kopie ersetzt, Hash gleich. **Neustart vom Stick mit Antwortprüfung noch nicht gemacht.**
- Qwen3.5-9B und Bonsai-Kopie waren ebenfalls beschädigt (Stichprobe) und sind ersetzt (Hash gleich).
- **Ladezeit vom Stick:** rund 3 Minuten für 6 GB (etwa 33 MB/s), von I: 15 s. Ungelöst.
- **Bonsai + Nemotron gleichzeitig** (die Ausgangsfrage): nicht gelungen. Bonsai kam im Testlauf nicht hoch (Engine-Start hing, Kopie unvollständig). Nicht getestet.

### 3.5 Geschwindigkeitsmessung (USB)

| Gerät | Lesen (ungecacht) | Schreiben |
|---|---|---|
| I: (interne Quelle) | ca. 501 MB/s | — |
| K: (GIGASTONE-Stick) | ca. 32 MB/s | ca. 18 MB/s |
| J: (zweiter USB-Stick) | ca. 43 MB/s | ca. 42 MB/s |

Vergleich mit einem Start aus dem E:-Checkout (Modell von I:): 15 s Laden. Ein Vergleich mit dem Hilfsprogramm „MOVESPEED“ war geplant, konnte im Testlauf aber nicht ausgeführt werden (Werkzeug nicht gefunden). Nicht belegt.

Vorschlag für Laden vom Stick (Cloud-Worker prüft nur Vorschläge, nicht die Hardware): Modell einmal auf eine lokale Platte kopieren und von dort starten; oder Stick mit höherer Lesegeschwindigkeit. Entscheidung beim Captain.

### 3.6 Laufende Prozesse und Reste (31.10., 11:xx)

- `llama-server` PID 19380 aus dem **E:-Checkout**, Modell Qwen3.5-9B von I:, Port 8089, belegt rund 8,2 GB VRAM. Gehört nicht zum Stick. Nicht beendet.
- Harness-Server auf `127.0.0.1:57306` und `llama-server` PID 21324 aus K:\SEDRA (Nemotron, Port nach Test). Laufen weiter; Beenden wartet auf Freigabe des Captains.
- Nach einem Test-Lauf können Einträge `HasExited = True` in der Prozessliste bleiben; sie belegen kein VRAM.
- `K:\start_probe.txt` (Probe-Datei des ersten Starts, Stick-Wurzel) und `K:\_speedtest_tmp.bin` (Messdatei) liegen noch auf dem Stick. Löschen nur durch den Captain.
- Ordner `E:\Sedra Umgebung\Sedra Test umgebung für Minimale USB Stick Version` existiert mit einer SEDRA-Kopie; Inhalt nicht geprüft.

## 4. Widersprüche im Wissensstand (bitte nicht übernehmen)

- `docs/WISSEN_SEDRA_GESAMT.md` (Abschnitt 4 und 8) sagt, die Nemotron-Modelldatei fehle und der Nemotron-Test stehe aus. **Veraltet:** Die Datei ist auf I: und K: vorhanden.
- Dieselbe Datei sagt, Nemotron Q4_K_M sei abgenommen „nicht bestanden“. Der Abnahmebericht `docs/BAUBERICHT_ABNAHME_NEMOTRON_2026-10-28.md` sagt, Nemotron lief im Harness (geladen in 7 s, 5,2 GB VRAM), mit Fehlern bei C1–C4 (Kontextgrenze bei `datei_lesen`, Pytest-Auswahl). Beides gilt nebeneinander: Start ja, Aufgabentreue teilweise nein.
- Der Testlauf-Chat meldete zuerst „Nemotron nicht vorhanden“ in `role_routing.yaml`; das war falsch. Das Rezept `harness.nemotron_e4b` existiert (2 Slots, Kontext 45 056 laut Konfiguration; Abnahme nennt 16 384 je Slot). Die Werte sind zu prüfen.

## 5. Offene Punkte (priorisiert)

1. **Nemotron vom Stick neu starten** mit Antwortprüfung (Erwartung: korrekte Antwort, z. B. „Paris“). Ohne das gilt die Basis nicht als lauffähig. (Nur mit Freigabe des Captains; braucht den Stick.)
2. **Bonsai + Nemotron gleichzeitig** auf K: testen (VRAM, RAM, Antworten). Ergebnis ist die Grundlage für die Basisstufe.
3. **Vollständige SHA-256-Prüfung** für Gemma (Modell und mmproj) und Qwen3.6 auf K:.
4. **Ladezeit vom Stick** verbessern oder Kopie auf lokale Platte als Empfehlung festschreiben.
5. **Modellzuordnung** `model_profiles.yaml` auf K: an die Zwei-Stufen-Entscheidung anpassen (Vorschlag: Nemotron für kleine Klassen, Bonsai als Ausweich). Nur mit Captain-Ja.
6. **`fenster/rekorder.html`** fehlt im Repository (Translator-Shell). Entscheidung: nachbauen oder die Translator-Shell auf dem Stick ohne Rekorder-Fenster ausliefern. Vorschlag des Plans: nicht nachbauen, dem Captain melden.
7. **Modellrezepte** für Gemma, Nemotron und Qwen3.6 im Repository fehlen; das Rezept für Bonsai fehlt ebenfalls. `local_config/role_routing.yaml` wird nur vom Captain geändert.
8. **Zweiter PC ohne Netz und ohne Python** nicht geprüft.
9. **Laufdaten** `workspace\` und `runtime_data\` entstehen auf dem Stick; Verhalten bei Schreibfehlern auf exFAT nicht getestet.
10. **Fenster schließen beendet SEDRA** (Entscheidung, bleibt so).
11. **Gerät und Treiber:** Testrechner RTX 4070 Ti (12 GB), Treiber 617.42. Abnahme auf einem PC mit 8 GB VRAM steht aus.
12. **Unit-Tests:** `test_ki_aufteilung_beweis` ist ungeklärt (nicht gegen Basisstand geprüft). Die Test-Attrappe `_kern_fake` braucht seit 30.10. kein numpy mehr.

## 6. Aufgaben für den Cloud-Worker

Der Cloud-Worker arbeitet nur am Repository. Er greift nicht auf K:\, I:\ oder lokale Modelle zu, lädt nichts herunter und pusht nichts.

**Voraussetzung:** Die Commits `03bd44e` bis `8a5a427` sind nicht auf GitHub. Vor dem Start muss der Captain den Branch `claude/usb-stick-minimal-3c1b19` freigeben (Push). Ohne Push: Der Worker stoppt und meldet das.

**Auftrag:**
1. `docs/PLAN_USB_STICK_MINIMAL.md` und `docs/ENTSCHEIDUNGEN_USB_STICK.md` gegen dieses Paket abgleichen. Abweichungen melden, nicht stillschweigend ändern.
2. Die Zwei-Stufen-Entscheidung in `runtime/benchmarks/stick_liste.txt` und in `stick_paket.py` abbilden: Basis (Bonsai, Nemotron) als Pflicht, Erweiterung optional. Nur Kennzeichnung und Tests, keine Modelldateien.
3. Die Tests für `stick_paket.py` und `local_paths.py` ausführen (Aufruf: im Ordner `runtime`, `PYTHONIOENCODING=utf-8 python benchmarks/run_tests.py scheduler desk orchestra uix`, sowie `test_local_paths` und `test_stick_paket`). Ergebnis mit Ausgabe berichten.
4. `test_ki_aufteilung_beweis` gegen den Basisstand prüfen und benennen, ob der Fehler vorher bestand.
5. Vorschlag für die Modellzuordnung in `model_profiles.yaml` (nur Vorschlag im Bericht, nicht im Code).
6. Entscheidungsvorlage zu `fenster/rekorder.html` (Nachbauen, Weglassen, Kosten).
7. Vorschlag für Ladezeit-Verbesserung vom Stick (Kopie auf lokale Platte, Vorladen, Pufferung), ohne Umbau am Kern.

**Nicht tun:** `local_config/` ändern, Dateien auf K:\ schreiben, Modelle laden, Downloads, Push, Merge in `main`, Löschen von Worktrees oder Branches, Prozesse beenden.

## 7. Abnahmekriterien (für die Rückmeldung des Workers)

- Tests grün oder mit benanntem Fehler und Ausgabe.
- Liste der Dateien, die sich ändern würden, mit Begründung.
- Antworten auf die Punkte 2 bis 7 in Abschnitt 6.
- Keine Angaben über K:\ oder Modelltests, die der Worker nicht selbst ausgeführt hat.

## 8. Quellen

- Entscheidungen: `docs/ENTSCHEIDUNGEN_USB_STICK.md` (Zwei-Stufen-Eintrag vom 31.10.)
- Plan: `docs/PLAN_USB_STICK_MINIMAL.md` (Branch `claude/usb-stick-minimal-3c1b19`)
- Abnahme Nemotron: `docs/BAUBERICHT_ABNAHME_NEMOTRON_2026-10-28.md`
- Wissensdatei: `docs/WISSEN_SEDRA_GESAMT.md` (enthält veraltete Punkte, siehe Abschnitt 4)
- Sitzungen: „SEDRA: minimale USB-Version auf K:\ einrichten“ (`local_ea4e34a2-6ba2-4817-98aa-fdc0b18e2bfd`), „Test: Bonsai und Nemotron gleichzeitig“ (`local_236a8da5-3fdf-4690-bb77-f3439a61725e`)
