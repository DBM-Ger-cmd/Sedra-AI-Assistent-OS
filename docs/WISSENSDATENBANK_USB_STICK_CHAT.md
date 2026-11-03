# Wissensdatenbank: USB-Stick-Minimalversion (dieser Chat)

Stand: 3.11.2026. Umfang: alles aus dem Chat zur SEDRA-Minimalversion auf dem USB-Stick K:\ (Einrichtung, Modelle, Tests, Messungen, Entscheidungen, offene Punkte). Quellen sind genannt. Was nicht belegt ist, steht als offen.

Weitere Wissensdateien: `docs/WISSEN_SEDRA_GESAMT.md` (alle Chats), `docs/ENTWICKLERPAKET_USB_STICK_2026-10-31.md` (Übergabepaket für einen Cloud-Worker), `docs/ENTSCHEIDUNGEN_USB_STICK.md` (Entscheidungen des Captains).

## 1. Ziel und Umfang

- Eine portable SEDRA-Minimalversion auf dem USB-Stick GIGASTONE (exFAT, entfernbar, Laufwerk K:\). Zielrechner für die Basis: 16 GB RAM, 8 GB VRAM. Ein Kollege soll damit arbeiten können.
- Enthalten: Kern, Harness-Shell (Standard), Cockpit, Paperclip, Translator-Shell (Ordner `uix/shells/fisch`, intern noch „fisch“).
- Nicht enthalten: Start-, Minimal-, Gateway-, Guppi-XP-Shell, Wissensbasis, Vorlagen, das Projekt als Ganzes.
- Die „Transkript-Shell“ gibt es nicht. Gemeint ist die Translator-Shell.
- Die Arbeit findet in der Umgebung `E:\Sedra Umgebung\Sedra Test umgebung für Minimale USB Stick Version` statt. A1 (`E:\Sedra Umgebung\A1 Sedra Main Branch Entwicklungs umgebung`) bleibt die Hauptumgebung der PC-Version.

## 2. Entscheidungen

Quelle: `docs/ENTSCHEIDUNGEN_USB_STICK.md`.

| Thema | Entscheidung | Datum |
|---|---|---|
| Pfade | Option B: keine Junctions oder Symlinks (exFAT kann sie nicht). Modellordner über `local_paths.yaml`; relative Ordner zählen ab `runtime\`, `modelle: '..\modelle'`. | 30.10. |
| Modelle | Vier Modelle, Kopien von `I:\KI-Daten\modelle`. Bonsai-27B später auf Wunsch des Captains ergänzt. | 30.10. / 31.10. |
| Zwei Stufen | Basis (Pflicht): Bonsai-27B Q1_0 mit mmproj und Nemotron 3.5 Bolt E4B. Erweiterung (optional): Qwen3.6-35B-A3B, Qwen3.5-9B-MTP, Gemma 4 12B QAT mit mmproj. | 31.10. |
| Zielrechner | Basis für 16 GB RAM / 8 GB VRAM, Erweiterung für stärkere Systeme. | 31.10. |
| Translator-Shell | Braucht die Werkzeuge `uebersetzer`, `nachrichten`, `transkript`, `rekorder`, die Kern-Module `fisch/` und `sprache/`, `ui/sprache.js`, `ui/wechsel.js` und `fenster/rekorder.html`. | 30.10. |
| Fenster schließen | Beendet SEDRA (Server und Modell). Bleibt so. | 30.10. |
| Erststart | Stick-Start immer über `K:\SEDRA\START_SEDRA.bat --gewaehlt` (Harness). | 31.10. |
| Kopien | Keine Kopien mehr parallel auf K: anlegen, solange die Ersatzkopien laufen. | 31.10. |

Offen: Ob der Start ohne `--shell` für ein Minimalpaket mit vier Oberflächen scheitert. Laut Memory-Notiz vom 2.11. scheitert er, Harness und Translator tragen. Die Entscheidung ist offen (Commit `fd38a81`, „Prüfung des Minimalpakets mit vier Oberflächen“). Hier nicht nachgeprüft.

## 3. Repository-Stand

- Branch `claude/usb-stick-minimal-3c1b19` (Worktree `.claude\worktrees\usb-stick-minimal-3c1b19`). Commits `07f49fa`, `03bd44e`, `c1a9d29`, `33fccca`, `8a5a427`. Nur lokal, nicht gepusht, nicht in `main`.
- Inhalt dieser Commits: Plan `docs/PLAN_USB_STICK_MINIMAL.md`, relative Modellordner in `runtime/src/guppi_runtime/local_paths.py`, Paketbau `runtime/benchmarks/stick_paket.py` mit Stick-Liste `stick_liste.txt` (Importhülle per AST), Tests `test_local_paths.py` und `test_stick_paket.py`.
- Die Stick-Liste ergänzt `desk.html`, `retro_desktop.html`, `dashboard.html`. Ohne sie brach der Start mit FileNotFoundError ab.
- Auf `main` liegt inzwischen `b147788` mit den drei Dokumenten (Entscheidungen, Entwicklerpaket, Wissensdatei gesamt) sowie weitere Harness-Commits.
- Ein Cloud-Worker kann die Commits nur sehen, wenn der Branch gepusht ist. Push nur auf ausdrückliches Ja.

## 4. Modelle auf dem Stick

Quelle für alle: `I:\KI-Daten\modelle`. Ziel: `K:\SEDRA\modelle\`.

| Modell | Stufe | Größe (Byte) | Prüfstand |
|---|---|---|---|
| Bonsai-27B Q1_0 (`lmstudio-community\Bonsai-27B-GGUF`) | Basis | 3 803 452 576 | SHA-256 gleich (Ersatzkopie 11:44, 31.10.) |
| Bonsai mmproj | Basis | 931 145 888 | Größe gleich |
| Nemotron 3.5 Bolt E4B Q4_K_M | Basis | 6 180 446 208 | SHA-256 gleich (Ersatzkopie 10:55, 31.10.) |
| Qwen3.6-35B-A3B IQ4_XS (`unsloth`) | Erweiterung | 17 730 509 792 | Nur Stichprobe |
| Qwen3.5-9B-MTP Q6_K (`unsloth`) | Erweiterung | 7 684 551 008 | SHA-256 gleich (Ersatzkopie 11:18, 31.10.) |
| Gemma 4 12B QAT Q4_0 | Erweiterung | 6 975 879 008 | Nur Stichprobe |
| Gemma mmproj | Erweiterung | 175 115 328 | Nur Stichprobe |

Die Stichprobe liest 64-MB-Blöcke bei 0, 1/4, 1/2, 3/4 und am Ende. Eine vollständige SHA-256-Prüfung von Gemma und Qwen3.6 fehlt.

Die Kopien waren zuerst beschädigt, obwohl die Größe stimmte: Nemotron, Qwen3.5-9B und Bonsai. Ursache: Mitte und Ende der Datei unterschieden sich vom Original. Die Kopien wurden aus I: neu geschrieben. Die Größe allein ist kein Beweis.

## 5. Stick-Stand K:\SEDRA (31.10.)

- `START_SEDRA.bat`, `STICK_MANIFEST.json` (734 Dateien, 781 499 521 Byte, Stand `c1a9d29`), `LICENSE`, `runtime\`, `workspace\`, `architecture\`, `engines\`, `modelle\`.
- Engine `engines\llama.cpp\b11160\`: 31 Dateien, 715 MB. `verify_engine(full=True)` ergibt `(True, 'ok')`. Pfad über `DEFAULT_ROOT = parents[4] / "engines"` in `engine_provision.py`.
- Portables Python `runtime\portable\python\current\` (Python 3.14.8, PyYAML 6.0.3). Kopie aus `runtime\portable\python.aus\current\` des Bau-PCs. `Test-PortableRuntime.ps1` grün.
- `runtime\config\local_paths.yaml`: `modelle: '..\modelle'`.
- `workspace\GUPPI_OS\local_config\uix.yaml`: Harness als Standard.
- `runtime\config\model_profiles.yaml` auf dem Stick geändert, Original als `.orig`. Die Zuordnung (Bonsai für kleine GPU-Klassen, Gemma für größere) passt nicht zur Zwei-Stufen-Entscheidung. Nicht geändert.
- Im Manifest nicht erfasst: `model_profiles.yaml`.

## 6. Tests und Befunde

- **Start:** `START_SEDRA.bat --gewaehlt` startet den Server auf `http://127.0.0.1:57306/`. `/` und `/retro` liefern 200, `/api/state` ohne Token 403 (erwartet).
- **Engine-Check hing:** `engine_download.py` fragte „JA“, weil die Prüfung während laufender Kopien fehlschlug. Nach dem Ende der Kopien war die Prüfung ok. Ohne „JA“ wird nichts von GitHub geladen.
- **Nemotron auf dem Stick:** nur `<unused32>`-Tokens. Ursache: beschädigte Kopie. Vergleich: Der Start aus dem E:-Checkout mit der I:-Datei antwortete korrekt („Paris“) in 15 s. Die Warnungen zu Steuerzeichen-Tokens treten in beiden Fällen auf und sind nicht die Ursache. **Nach der Reparatur noch nicht vom Stick neu gestartet.**
- **Bonsai und Nemotron gleichzeitig:** nicht geprüft. Bonsai kam im Testlauf nicht hoch, Nemotron wurde nicht gestartet, die Kopie war zu dem Zeitpunkt unvollständig.
- **Abnahme Nemotron im Harness (28.10., E:-Checkout):** Modell geladen in 7 s, 5,2 GB VRAM. Aufgaben C1 bis C4 teilweise nicht bestanden (Kontextgrenze bei `datei_lesen`, Auswahl bei pytest). Bericht: `docs/BAUBERICHT_ABNAHME_NEMOTRON_2026-10-28.md`.
- **Unit-Tests:** `test_ki_aufteilung_beweis` ist ungeklärt; nicht gegen den Basisstand geprüft.
- **Harness-Gedächtnis-Pfad:** Vorlagen und Zusammenfassungen sind auf main, aber für den Stick nicht getestet.

## 7. Geschwindigkeit

| Gerät | Lesen (ungecacht) | Schreiben |
|---|---|---|
| I: | ca. 501 MB/s | — |
| K: (GIGASTONE) | ca. 32 MB/s | ca. 18 MB/s |
| J: | ca. 43 MB/s | ca. 42 MB/s |

- Laden eines 6-GB-Modells: rund 3 Minuten vom Stick (ca. 33 MB/s), 15 s von I:.
- Ein Vergleich mit dem Hilfsprogramm „MOVESPEED“ war geplant, konnte im Testlauf nicht ausgeführt werden. Nicht belegt.
- Die Ursache des langsamen Ladens ist nicht gelöst. Mögliche Wege: Modell einmal auf eine lokale Platte kopieren und von dort starten; schnellerer Stick. Entscheidung beim Captain.

## 8. Prozesse und Reste

- Der Stick-Server (Port 57306) und der Nemotron-`llama-server` von K: laufen weiter (Stand 31.10., PID 21324). Beenden nur mit Ja.
- `llama-server` PID 19380 aus dem E:-Checkout mit Qwen3.5-9B von I: auf Port 8089, rund 8,2 GB VRAM. Nicht gestartet von dieser Sitzung; nicht beendet.
- Auf dem Stick liegen zwei Testdateien: `K:\start_probe.txt` und `K:\_speedtest_tmp.bin`. Nur der Captain löscht sie.
- Ein Prozess kann nach dem Test als `HasExited = True` in der Liste bleiben; er belegt kein VRAM.
- `taskkill` und `Stop-Process` wurden vom Berechtigungsprüfer abgelehnt, auch mit Freigabe. Beenden ist deshalb mit Vorsicht zu behandeln.

## 9. Widersprüche und veraltete Aussagen

- `docs/WISSEN_SEDRA_GESAMT.md` (Abschnitte 4 und 8) sagt, die Nemotron-Datei fehle. Veraltet: sie liegt auf I: und K:.
- Dieselbe Datei nennt Nemotron „nicht bestanden“. Der Abnahmebericht vom 28.10. sagt: läuft im Harness, mit Fehlern bei C1 bis C4. Beides gilt nebeneinander.
- Im Testlauf hieß es zuerst, Nemotron sei in `role_routing.yaml` nicht vorhanden. Falsch: das Rezept `harness.nemotron_e4b` existiert (2 Slots; Kontext 45 056 laut Konfiguration, 16 384 je Slot im Abnahmebericht). Werte prüfen.

## 10. Offene Punkte

1. Nemotron vom Stick neu starten, mit Antwortprüfung. Ohne das gilt die Basis nicht als lauffähig.
2. Bonsai und Nemotron gleichzeitig auf K: testen (VRAM, RAM, Antworten).
3. Vollständige SHA-256-Prüfung für Gemma (Modell und mmproj) und Qwen3.6.
4. Ladezeit vom Stick verbessern oder Kopie auf lokale Platte festlegen.
5. `model_profiles.yaml` auf K: an die Zwei-Stufen-Entscheidung anpassen (Vorschlag: Nemotron für kleine Klassen).
6. `fenster/rekorder.html` fehlt im Repository. Entscheidung: nachbauen oder weglassen.
7. Modellrezepte für Gemma, Nemotron, Qwen3.6 und Bonsai fehlen im Repository. `local_config/role_routing.yaml` ändert nur der Captain.
8. Start ohne `--shell` mit vier Oberflächen (siehe Abschnitt 2).
9. Zweiter PC ohne Netz und ohne Python: nicht geprüft.
10. Abnahme auf einem PC mit 8 GB VRAM steht aus. Testrechner: RTX 4070 Ti (12 GB), Treiber 617.42.
11. `test_ki_aufteilung_beweis` gegen den Basisstand prüfen.
12. Cloud-Worker: Paket liegt in `docs/ENTWICKLERPAKET_USB_STICK_2026-10-31.md`, gestartet ist er nicht. Vorher Push-Freigabe nötig.

## 11. Fallen

- Junctions und Symlinks gehen auf exFAT nicht; Paketprüfung bricht bei Verknüpfungen ab.
- Der Worktree-Bau braucht `runtime/config/local_paths.yaml` und `engines`. Verknüpfungen in Worktrees nur mit `rmdir` entfernen, nie rekursiv löschen.
- `engine_download.py` fragt bei fehlgeschlagener Prüfung nach „JA“. Nicht bestätigen, wenn kein Download gewollt ist.
- Heredocs im Bash-Tool verfälschen Backslashes. Dateien mit Write oder Edit schreiben.
- Auto-Modus sperrt zusammengesetzte Befehle mit `branch -D` oder Remote-Löschen. Einzeln ausführen.
- Modelldateien: Größe gleich heißt nicht gleicher Inhalt. Hash oder vollständige Prüfung nötig.

## 12. Befehle

Stick starten (Harness):

```bash
K:\SEDRA\START_SEDRA.bat --gewaehlt
```

Paketprüfung im Repository (im Ordner `runtime`):

```bash
PYTHONIOENCODING=utf-8 python benchmarks/run_tests.py scheduler desk orchestra uix
```

## 13. Sitzungen dieses Chats

- „SEDRA: minimale USB-Version auf K:\ einrichten“ (`local_ea4e34a2-6ba2-4817-98aa-fdc0b18e2bfd`, Branch `claude/usb-stick-minimal-3c1b19`).
- „Test: Bonsai und Nemotron gleichzeitig“ (`local_236a8da5-3fdf-4690-bb77-f3439a61725e`, Branch `claude/test-bonsai-nemotron-ac86cc`).
- Dieser Chat: Auswertung, Entwicklerpaket, Wissensdatenbank.
