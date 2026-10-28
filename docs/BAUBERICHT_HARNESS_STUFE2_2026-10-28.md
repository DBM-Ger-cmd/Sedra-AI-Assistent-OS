# Baubericht Harness-Shell Stufe 2 (28.10.2026)

Spec: `SPEC_HARNESS_SHELL_v1.md` (G1), `SPEC_HARNESS_SHELL_v1_G2.md` (G2), `SPEC_HARNESS_SHELL_v1_G3_STUFE2.md` (G3, U1–U10, D-F1–D-F5).
Auftrag des Captains 28.10.2026 (über die Vorarbeiter-Sitzung): Stufe 2 bauen; `local_config/freigabe_katalog.yaml` nicht anlegen (D-F2);
Abnahme mit echtem Modell erst nach Ja; nichts in `spec/agenten-orchestrierung` bewegen, kein Push. Gebaut von Claude (D-E6) auf
`harness/stufe-2` ab `a2f9717`. D-F1–D-F5 wie in G3 vorgeschlagen; Abweichung D-F1 siehe unten.

## Ergebnis

| Prüfung | Ergebnis |
|---|---|
| `run_tests all` (ohne Browser-Bahn) | **3225 Tests, 0 rot**, 81 übersprungen (257 Dateien; 16 DevVM-Dateien ohne `dulwich` übersprungen) |
| DevVM-Dateien mit dem `.venv` (ohne `dulwich` im System-Python übersprungen) | 239 Tests, 0 rot |
| Gruppe `harness` | 12 Testdateien, 106 Tests, 0 rot (Stufe 2 neu: 5 Dateien, 32 Tests) |
| `uix_check --shell harness --groesse 1024x700,1400x860` | 18 von 18 ok, 0 Konsolenfehler, Überhang 0 px |
| Browser-Durchlauf mit Modell-Attrappe, beide Größen | Lesen frei (`frei · lesen-alles`) → `datei_aendern docs/log.md` → Karte mit Diff, „Freigaben 1“ in der Taskleiste → „Diff zeigen“ öffnet Reiter → „Erlauben“ → Datei geschrieben → Ende **Erledigt**; nach Neuladen gleich; 0 Konsolenfehler |
| SEDRA-Bau von `einstufen` (U2, Captain-Ja) | **bestanden**: 19 von 19 versteckten Prüfungen in der microVM, 315 s, 23 Modellaufrufe, 0 Nacharbeiten; Kandidat gleich der Referenz in 698 Vergleichen (siehe unten) |
| Abnahme mit echtem Modell (U10) | **nicht gestartet** (Ja des Captains) |
| `local_config/` | nichts angelegt oder geändert |

## Aufgaben

| Nr | Fertig | Belege |
|---|---|---|
| U1 | `harness/katalog.py` lädt `local_config/freigabe_katalog.yaml`, sonst die Vorlage `config/freigabe_katalog.beispiel.yaml` (Vorgabe-Katalog D-E1, 8 Regeln); ungültig → `KatalogFehler` mit Grund, kein Rückfall; ohne gültigen Katalog bekommt das Modell nur die lesenden Zustandswerkzeuge | `test_harness_katalog` (4) |
| U2 | `einstufen` (rein): Glob mit `**`/`*`, Befehle als Präfix, genaueste Regel, Gleichstand → strenger, ohne Regel → `captain`. Referenz im Paket + `benchmarks/devvm_refs/harness_katalog/` + Bau-Spec `benchmarks/devvm_specs/harness_katalog.py` mit **19 versteckten Prüfungen** (`spec_check`: lint ok, ref ok) | `test_harness_katalog_einstufen` (2, führt die versteckten Prüfungen gegen das Paket aus) |
| U3 | `harness/vorbehalte.py`: feste Pfade (local_config, Katalog, core, harness/freigabe·vorbehalte·befehl, devenv, devvm_*, guard, .git) und Befehle (git push, branch -f, reset --hard, del, rm, rmdir, Remove-Item, format, curl, wget, Invoke-WebRequest, pip install, winget), leer überschreiben → immer `captain` | `test_harness_vorbehalte` (5); HTTP: `git push` → Karte mit Regel `vorbehalt` |
| U4 | `datei_lesen` (≤ 400 Zeilen, Nummern), `dateien_auflisten` (≤ 300), `suchen` (ripgrep `--files`, sonst `os.walk`; ≤ 200 Treffer; was der Katalog nicht lesen lässt, wird nicht durchsucht) | `test_harness_werkzeuge` (Lesen 5) |
| U5 | `datei_schreiben`, `datei_aendern` (genau einmal) über `FilesystemTool.write_text`, nur im Schreibbereich; Gate gebunden an Inhalt und Dateizustand – ändert sich die Datei nach der Karte, passt das Token nicht mehr | `test_harness_werkzeuge` (Schreiben 5) |
| U6 | `harness/befehl.py`: ohne Shell (`|`, `>`, `<`, `&`, `;`, Backtick, `$(` außerhalb von Anführungszeichen → Fehler), Ordner in der Wurzel, sichere Umgebung + UTF-8, Zeitlimit ≤ 600 s, Ausgabe ≤ 20 000 Zeichen, Stopp/Zeitlimit beenden den Prozessbaum; **Guard-Token je Zeile und Ordner** (Aktion `harness_befehl`) | `test_harness_werkzeuge` (befehl 6) |
| U7 | `harness/freigabe.py`: Vorbehalt → Katalog → Guard; `frei` → Gate + `approve` (Audit `HARNESS_APPROVED_BY katalog:<regel>`), `verboten` → Grund ans Modell, `captain` → Karte (`runtime_data/harness/karten/K-….json`, mit Zustand der Schleife) und `ende: wartet`; `beantworten` = eine Tür; Antwort setzt die Schleife mit dem Ergebnis fort (neue Antwort-ID); `erledigt` nur mit Wirkung | `test_uix_harness_freigabe` (5): frei/verboten, Karte → erlauben → erledigt, ablehnen über den Posteingang, Vorbehalt + Karte übersteht Neustart, Katalog/Einstufen/Werkzeuge |
| U8 | `desk/decisions.collect` Quelle `harness` (Art `harness_freigabe`, Wege `erlauben`/`ablehnen`); `uix_server.decide` ruft dieselbe Tür; Wege `karten/<id>`, `katalog`, `einstufen`, `werkzeuge` | dieselben HTTP-Tests: gleiches Audit (`HARNESS_FREIGABE` mit `ueber: karte|posteingang`), eine Karte wird genau einmal beantwortet |
| U9 | Karte im Verlauf (Werkzeug, Ziel, Stufe, Regel, Begründung, farbiger Diff; Erlauben · Diff zeigen als Reiter · Ablehnen, Begründung), Stufe und Regel an der Werkzeugzeile (HS-29), Schild „Captain gibt frei · Katalog n Regeln“, Ende „Wartet auf Freigabe“, Fortsetzung aus dem Posteingang hängt sich an | `uix_check`, Browser-Durchlauf (oben) |
| U10 | Gruppe `harness` erweitert (Muster `test_harness_*`, `test_uix_harness_*`); dieser Bericht; Logbuch | – |

Umfang: rund 800 Zeilen neues Python im Paket `harness/`, rund 230 Zeilen Oberfläche, 460 Zeilen neue Tests; insgesamt 26 Dateien, +1815/−48.

## Abweichungen und Entscheidungen beim Bau (bitte prüfen)

1. **D-F1 (versteckte Prüfungen):** nicht im Notizordner, sondern wie eingeführt im `HIDDEN` der Bau-Spec (`benchmarks/devvm_specs/harness_katalog.py`) – die bauenden Agenten sehen es nie; `spec_check` kann nur so die Referenz prüfen. Im Paket führt `test_harness_katalog_einstufen` dieselben Prüfungen als Regressionstest aus.
2. **Worktree:** Ein zweiter Worktree war für diese Sitzung gesperrt (Schreibschutz auf fremde Worktrees). Der bisherige Worktree `stufe-1-64f713` steht deshalb auf `harness/stufe-2` (sein alter Branch war vollständig in `spec` übernommen).
3. **Lesen mit Karte:** Der Guard kennt Lesen als ALLOW; für Lese-Aufrufe, die der Katalog auf `captain` setzt, legt die Harness ein Gate mit der Aktion `harness_lesen` an und verbraucht das Token selbst. Dasselbe für neue Dateien (`create_new_artifact` ist beim Guard ALLOW).
4. **`befehl` und Anführungszeichen:** `python -c "a; b"` ist erlaubt – ohne Shell ist `;` in Anführungszeichen ein Argument. `python` startet den Python dieser Runtime.
5. **Neue Nachricht bei offener Karte:** abgelehnt mit `karte_offen` (erst entscheiden) – sonst setzte eine spätere Freigabe einen veralteten Verlauf fort.
6. **Aufrufe nach einem wartenden Aufruf im selben Zug** laufen nicht; bei der Fortsetzung bekommt das Modell „nicht ausgeführt … ruf ihn bei Bedarf noch einmal auf“.
7. **Werkzeugzeile „wartet auf Freigabe“** bleibt im Verlauf stehen; das Ergebnis nach der Entscheidung steht als eigene Werkzeugzeile der Fortsetzung (Sitzungsdatei: `karte` offen → `karte` beantwortet → `werkzeug`).
8. **Vertrag „Shell-Datei ≤ 400 Zeilen“:** die Karte steht in `karte.js`; Shell-Version 1.1.0.

## Offen

- **SEDRA-Bau von `einstufen`** (erster SEDRA-Bau, HS-E5): `spec_check.py harness_katalog --vm --project <projekt>` (Stempel), dann `devvm_build.py <projekt> --spec harness_katalog --profile standard` – lädt ein Modell, nur nach Ja. Besteht der Bau, ersetzt er `einstufen` im Paket (Übernahme durch den Captain); scheitert er, gilt V4.
- **Abnahme mit echtem Modell** (G2 §8): Vorarbeiter-Szenario („Werte den letzten Lauf aus und trag ihn ins Logbuch ein“) und Modelltest C1–C4 (`MODELLTEST_HARNESS_v1.md`) – nur nach Ja.
- **Katalog des Captains:** `local_config/freigabe_katalog.yaml` (Kopie der Vorlage) legt der Captain an (D-F2); bis dahin gilt die Vorlage.
- Nicht im Browser geprüft: „Ablehnen“ auf der Karte (über HTTP und Posteingang geprüft), Antwort im Cockpit-Posteingang selbst (dieselbe Route `/api/decisions/answer` ist geprüft).

## Erster SEDRA-Bau: `einstufen` (28.10.2026, Captain-Ja)

- Stempel: `spec_check.py harness_katalog --vm --project workspace/GUPPI_OS` → lint ok, Referenz ok (Python 3.12.15 der microVM).
- Bau: `devvm_build.py workspace/GUPPI_OS --spec harness_katalog --profile standard` (Qwen3.6-35B-A3B, 32 768 Token, 1 Slot), 15:19:55–15:25:11:
  1 Versuch, Solo-Entwickler, 23 Modellaufrufe, 298 s Agent, **versteckter Test bestanden**, Nacharbeiten 0, Eskalationen 0.
  Kandidat: `workspace/GUPPI_OS/runtime_data/devvm_candidates/harness_katalog/attempt_01_20261028_152511/katalog_einstufen.py` (92 Zeilen).
- GPU vorher 1,5 GB / 40 °C, nachher 1,5 GB / 43 °C; keine Treiberereignisse (`nvlddmkm`, LiveKernelEvent) seit 15:19:50; Modell danach entladen.
- Vergleich SEDRA gegen Referenz (Vorgabe-Katalog, eigene Kataloge mit Gleichstand und `*`, 20 Pfade, 14 Befehlszeilen, 242 Muster/Ziel-Paare für
  `passt`): **698 Vergleiche, 0 Abweichungen**. Unterschiede nur im Stil (Sortierung der Kandidaten statt Maximum; ungenutzte Namen).
- Übernahme in `harness/katalog.py` (Kandidat ersetzt `einstufen` und Hilfen): **Entscheidung des Captains** – noch nicht gemacht.

## Quote (L4)

Stufe 2: Claude bis auf `einstufen`; SEDRA hat `einstufen` gebaut (92 Zeilen Kandidat gegen 129 Zeilen Spec und Referenz von Claude, Quote Claude/SEDRA 1,4 laut devvm_build). Der Kandidat ist noch nicht übernommen.
