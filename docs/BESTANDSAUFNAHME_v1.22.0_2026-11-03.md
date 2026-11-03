# Bestandsaufnahme nach Release 1.22.0 (03.11.2026, 18:15)

Auftrag des Captains: „PR mergen, dann Tag v1.22.0 setzen wenn alles läuft, Bestandsaufnahme und zur Überarbeitung an Cloud-Sitzung zurück.“
Grundlage: GitHub-Stand `main` = `4e051f0`, Testlauf im Container (Linux, ohne GPU, ohne Browser), Dokumente im Repository. Was nur auf dem PC des Captains liegt, ist hier nicht enthalten.

## 1. Was heute passiert ist

| Zeit (MEZ) | Was | Beleg |
|---|---|---|
| 17:35 | Der PC merged `claude/intelligent-goldberg-7arr50` (Stand `1684036`) nach `main`. GitHub markiert PR #1 dabei automatisch als gemergt. | `abf4cbd` |
| 17:38–17:59 | Auf dem PC: UTF-8-Fix der Code-Stand-Konsole (unter Windows Absturz an der cp1252-Pipe), Markdown-Ausbau, Merge von `plan/usb-stick-minimal` und `fix/harness-list-projects` | `a0587b2`, `fc7ec97`, `5f31d87`, `078694b`, `e68e1f6`, `08361cd` |
| danach | Cloud-Sitzung: `--zeigen` für die Konsole; UTF-8 auch für `guppi code-stand`; Werkzeug `release_manifest.py`; `release/MANIFEST.sha256` | `a68a240`, `1573465`, `9ae5136` |
| 18:12 | PR #2 gemergt. `main` = `4e051f0`, Baum identisch mit dem getesteten Stand. | PR #2 |
| 18:13 | Tag `v1.22.0` auf `4e051f0` **nur lokal** in der Cloud-Sitzung angelegt. Der Push wurde vom Proxy der Sitzung abgelehnt (HTTP 403; Pushes sind dort nur auf den zugewiesenen Branch erlaubt). | §3 |

## 2. Stand des Repositorys

- **Version** 1.22.0 (`version.py`, `BUILD.txt`). Gegenüber `v1.21.0` (19.10.) sind 1.320 Dateien geändert (+115.102 / −4.227 Zeilen). Eine Zahl der Commits „seit v1.21.0“ gibt es nicht: Die Historie von `main` auf GitHub beginnt am 30.10. mit `ca5c123` (103 Commits bis `4e051f0`) und hat keinen gemeinsamen Vorfahren mit `v1.21.0` (32 Commits ab 15.10.). Für den Updater spielt das keine Rolle, er vergleicht Dateien. *(Korrigiert am 03.11.; zuerst stand hier „103 Commits seit v1.21.0“.)*
- **Release-Manifest** `release/MANIFEST.sha256`: 769 Dateien (`runtime/src/guppi_runtime/`, `runtime/config/`). `release_manifest.py --pruefen origin/main` meldet es als stimmig.
- **Branches auf GitHub:** `main`, `claude/intelligent-goldberg-7arr50` (= `main`), `docs/apps-modell`, `fix/harness-list-projects`, `plan/usb-stick-minimal`. Alle sind vollständig in `main` enthalten und können gelöscht werden (Entscheidung des Captains, siehe B9).
- **Tags:** `archiv/build25-basis`, `v1.21.0`. `v1.22.0` fehlt auf GitHub (B1).

## 3. Tests

**Container (Linux), ganze Bahn auf `main` + `a68a240`; die Programmdateien unterscheiden sich von `4e051f0` nur im UTF-8-Helfer in `code_stand.py` und `cli.py`:** 3.758 Tests, 121 übersprungen, 10 rot. Keiner davon stammt aus der Arbeit dieses Tages:

| Test | Ursache | Auf `main` ohne die heutige Arbeit |
|---|---|---|
| `test_tuning` (8) | kein `nvidia-smi` im Container (`FileNotFoundError`) | ebenso rot |
| `test_night_chain.DryRun` | `ctypes.windll` (nur Windows) in `benchmarks/kurzstart.py:39` | ebenso rot |
| `test_local_paths.test_a_relative_folder_counts_from_the_runtime_folder` | `..\modelle` ist unter Linux/macOS ein einziger Ordnername (B4) | ebenso rot |

Nach den letzten Commits sind die Gruppen Harness, CLI, Update, Stick, Release, Arbeitsplatz und Vertrag gelaufen: 443 Tests, 0 rot.
Nicht gelaufen: Browser-Bahn (Python-Playwright fehlt im Container), Tests auf dem PC mit 1.22.0 (ob der PC die ganze Bahn gefahren hat, ist hier nicht bekannt). `runtime/tests/known_red.txt` hat den Stand vom 30.10. und ist leer.
Beim Lauf gibt es 88 `ResourceWarning` (offene Dateien in Tests, z. B. `test_slot_measurement.py:228`, `test_meter_service.py:77`; ein noch laufender Unterprozess). Rot wird davon nichts.

## 4. Befunde zur Überarbeitung

| Nr | Befund | Beleg | Vorschlag | Wer |
|---|---|---|---|---|
| **B1** | Tag `v1.22.0` ist nicht auf GitHub. Bis dahin sieht der Updater nur `v1.21.0`, und das hat kein Manifest. | Push 403 | Tag am PC setzen und pushen (Befehle §6) | Captain |
| **B2** | Seit 1.22.0 ist der Updater zum ersten Mal benutzbar, die Releases sind aber nicht signiert. Der Plan empfiehlt eine Signatur „vor dem ersten Update für andere Nutzer“. Der Stick für einen Kollegen wäre so ein Fall. | `PLAN_ISOLATION_UND_UPDATE_2026-10-19.md` Frage 3; `BETRIEB.md` „Release“ | Entscheiden: (a) vorerst nur für den eigenen PC, Signatur vor der ersten Weitergabe, oder (b) jetzt signieren (signierte Tags oder ein Schlüssel im Programm). Empfehlung: (a), als Grenze in `BETRIEB.md` festhalten. | Captain |
| **B3** | `BUILD.txt` ist veraltet: Build 25, Datum 19.10., Nachtrag-Text von Build 20. `make_build.py --bump` ist nicht gelaufen, ein Paket für 1.22.0 gibt es nicht. | `BUILD.txt` | Am PC `make_build.py --bump` für 1.22.0 laufen lassen, falls ein Paket gebraucht wird, sonst den Nachtrag-Text auf 1.22.0 setzen | Cloud (Text) / PC (Paket) |
| **B4** | `local_paths.folder()` nimmt `..\modelle` unter Linux/macOS als einen Ordnernamen. SEDRA startet laut `BETRIEB.md` auch auf macOS/Linux. Der Test ist dort rot. | `local_paths.py:37–41`; Test §3 | `folder()` nimmt beide Trennzeichen an (unter Windows ändert sich nichts), die `expand`-Prüfung im Test wird plattformneutral | Cloud |
| **B5** | `test_tuning` und `test_night_chain.DryRun` sind auf Rechnern ohne `nvidia-smi` bzw. ohne Windows rot. Die Container-Bahn ist dadurch nie grün, und neue Fehler fallen weniger auf. | §3 | Mit `skipUnless` auf `nvidia-smi` bzw. Windows; der Grund steht im Test. Auf dem PC ändert sich nichts. | Cloud |
| **B6** | Das Logbuch endet am 02.11. um 12:20. Was danach kam (Harness-Commits 02./03.11., Apps v1, G4, Merges, Release), steht nicht drin. | `LOGBUCH_AGENT_MANAGER.md` | Einträge aus `git log` nachtragen, ohne etwas zu erfinden. Für 03.11. gibt es nur Commit-Texte als Beleg, für Tests auf dem PC keine. | Cloud |
| **B7** | Der `CHANGELOG` beschreibt die Harness-Stufen 28.10.–03.11., den Modell-Router und die Dynamischen Rezepte nur im Überblick. | `CHANGELOG.md` 1.22.0 | Mit den Bauberichten (`BAUBERICHT_HARNESS_*`, Messbericht R6) ausführlicher nachtragen | Cloud |
| **B8** | Der Index `docs/README.md` hat den Stand vom 20.10. 93 der 206 Dokumente fehlen darin, u. a. `SPEC_HARNESS_SHELL_v1.md`, `ANALYSE_HARNESS_2026-11-01.md`, `PLAN_USB_STICK_MINIMAL.md`, `SPEC_DYNAMISCHE_REZEPTE_v1.md`, `ARBEITSWEG_WUNSCH_UMSETZEN.md`. | Zählung | Die fehlenden eintragen, „Was gilt“ auf 1.22.0 bringen | Cloud |
| **B9** | Vier Branches auf GitHub sind vollständig gemergt. | §2 | Löschen. Aus der Cloud-Sitzung geht das nicht (nur der zugewiesene Branch). | Captain |
| **B10** | Das Update über die Oberfläche ist nie mit einem echten Tag-Zip von GitHub gelaufen. Geprüft ist derselbe Inhalt über `git archive`, `test_update_holen` arbeitet mit einem nachgebauten Zip. | – | Nach B1 am PC: Werkzeug „System“ → „Nach Updates suchen“ → Vorschau. Erwartet wird „kein Update“, weil installiert = 1.22.0. Die echte Probe kommt mit 1.22.1 oder auf einem Rechner mit 1.21.x. | Captain |
| **B11** | 88 `ResourceWarning` in der Bahn | §3 | Dateien in Tests mit `with` öffnen, Unterprozesse beenden. Niedrige Dringlichkeit. | Cloud |

## 5. Offene Arbeit aus früheren Plänen (nicht heute entstanden)

**Apps-Modell v1** (`KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` §11–§13):
- Die Abnahme von G4 am PC steht aus (drei Schritte in `SPEC_APPS_v1_G4_MODELLCODE_G2.md`). Gefunden und behoben wurde am PC der Absturz an der cp1252-Pipe.
- G2 fehlt für O3+ (Schutz des Oberflächen-Codes) und für G9–G11. AM9 (Werkstatt und Betrieb trennen, mit G5) gibt es nur als Skizze, ohne G1.
- Für die G2-Entwürfe AM0 und AM1 fehlen noch die Freigaben, u. a. AM0-G2-E1 (CSS fremder Vorgabe-Shells) und AM1-G2-E1 (Beschriftungen).
- AM2–AM8 stehen auf G1. AM5-01: Die Langdock-Unterlagen liegen nur als Suchauszüge vor. AM7 soll auf Betriebsart A (Stick als Pilot) zugeschnitten werden.

**USB-Stick** (`WISSENSDATENBANK_USB_STICK_CHAT.md` §10, 12 Punkte): u. a. Nemotron vom Stick mit Antwortprüfung, Bonsai und Nemotron gleichzeitig, SHA-256 für Gemma und Qwen3.6, Ladezeit, `fenster/rekorder.html` fehlt, Rezepte für die Stick-Modelle fehlen, Abnahme auf 8 GB VRAM, zweiter PC ohne Netz.

**Harness-Analyse 01.11.** (`ANALYSE_HARNESS_2026-11-01.md`, E-A4): V4 (Werkzeugergebnisse im Verlauf) und V7 (von der Karte in den Katalog) sollten eigene Specs bekommen. Ob sie inzwischen gebaut sind, ist hier nicht geprüft. V5 (Suche) ist dem Commit-Text nach mit `97269d8` gebaut.

## 6. Befehle für den PC (B1, B9)

Tag auf genau den Merge-Commit setzen und pushen:

```bash
git fetch origin
```

```bash
git tag -a v1.22.0 4e051f0 -m "SEDRA v1.22.0: Apps-Modell v1, G4, Harness-Stufen 28.10.-03.11., Modell-Router, Dynamische Rezepte R1-R6; erster Release mit Manifest fuer den Updater"
```

```bash
git push origin v1.22.0
```

```bash
runtime\.venv\Scripts\python.exe -I -B runtime\benchmarks\release_manifest.py --pruefen v1.22.0
```

(Braucht PyYAML. Gibt es keine `.venv`, nimm `runtime\portable\python\current\python.exe`.)

Gemergte Branches auf GitHub löschen (optional):

```bash
git push origin --delete docs/apps-modell fix/harness-list-projects plan/usb-stick-minimal
```

## 7. Vorschlag für die Überarbeitung in der Cloud-Sitzung

Reihenfolge nach Nutzen und Risiko. Alles läuft auf `claude/intelligent-goldberg-7arr50` und kommt per PR:
1. **B4, B5**: Die Container-Bahn wird grün, ohne dass sich am Verhalten unter Windows etwas ändert (Code in `local_paths.py`, sonst nur Tests).
2. **B3 (Text), B6, B7, B8**: Dokumentation auf 1.22.0 bringen, nur aus Belegen (`git log`, Bauberichte).
3. **B11**: Testhygiene.
4. Danach nach Wahl des Captains: G2 für O3+ und G9–G11, oder AM9 G1, oder Stick-Punkte, die ohne PC gehen (z. B. `fenster/rekorder.html` neu bauen oder weglassen).

Nicht in der Cloud machbar: B1, B9 (Push-Grenze), B10, die G4-Abnahme und alle Stick-Punkte mit Hardware.
