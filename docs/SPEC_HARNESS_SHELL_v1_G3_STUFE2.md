# SPEC Harness-Shell v1 – G3 Bau-Aufgaben Stufe 2 (28.10.2026)

Gehört zu `SPEC_HARNESS_SHELL_v1.md` (G1), `SPEC_HARNESS_SHELL_v1_G2.md` (G2, D-E1 bis D-E6) und dem Stand nach Stufe 1
(`BAUBERICHT_HARNESS_STUFE1_2026-10-28.md`, übernommen `aa910b5`) und Inhaltsschutz „Eigenes frei“ (`BAUBERICHT_INHALTSSCHUTZ_2026-10-28.md`, `27b8a75`).
Captain 28.10.2026: „Freigabe für nächste Stufe“ – dieses Dokument ist das Gate G3; gebaut wird erst nach seiner Freigabe.

Stufe 2 = **Hände und Grenzen**: Werkzeuge mit Wirkung (`datei_lesen`, `dateien_auflisten`, `suchen`, `datei_schreiben`, `datei_aendern`,
`befehl`), Freigabe-Katalog mit Einstufung, feste Captain-Vorbehalte, Freigabe-Karte im Verlauf und im Posteingang, Audit (HS-20 bis HS-29 ohne
Vorarbeiter-Freigabe und Aufgaben-Freigabe; die kommen in Stufe 3). Baut: Claude (D-E6); **`katalog.py` als erster SEDRA-Bau** (HS-E5).

## Aufgaben

| Nr | Aufgabe | Dateien | Fertig, wenn |
|---|---|---|---|
| U1 | **Katalog laden.** `harness/katalog.py` (Laden und Prüfen) liest `local_config/freigabe_katalog.yaml`, sonst die Vorlage `config/freigabe_katalog.beispiel.yaml` mit dem Vorgabe-Katalog aus D-E1; Regel = `{id, werkzeug, muster, stufe, begruendung}`; ungültige Datei → Fehler mit Grund, **kein** stiller Rückfall auf „frei“. | `harness/katalog.py` (Laden), `config/freigabe_katalog.beispiel.yaml`, Test | Test: Vorlage gültig, kaputte Datei → Grund, unbekannte Stufe/Werkzeug → Fehler; es wird nichts in `local_config/` geschrieben |
| U2 | **Einstufen (SEDRA-Bau, rein).** `einstufen(regeln, werkzeug, ziel) -> {stufe, regel, begruendung}` nach G2 §3.5: Glob relativ zur Projektwurzel (`**`), Befehle als Präfix der normalisierten Zeile mit optionalem `*`; genaueste Regel = längstes Muster ohne Platzhalter, Gleichstand → strengere Stufe (`verboten` > `captain` > `vorarbeiter` > `frei`); keine Regel → `captain`; `vorarbeiter` wird in Stufe 2 wie `captain` behandelt. Pfade vorher aufgelöst (kein `..`, kein Laufwerkswechsel, Groß/Klein wie Windows). | `harness/katalog.py` (Funktion `einstufen`), Bau-Spec `docs/BAUSPEC_KATALOG_EINSTUFEN.md` | **SEDRA baut** über `devvm_build --profile standard` gegen die Bau-Spec; Claude hält ≤ 20 versteckte Prüfungen (L3) und eine Referenz mit Stempel. Scheitert der Bau → V4: Claude übernimmt die Referenz, Quote im Logbuch |
| U3 | **Vorbehalte.** `harness/vorbehalte.py`: die feste Liste aus G2 §3.5 (Pfade `local_config/**`, Katalog selbst, `core/**`, `harness/{freigabe,vorbehalte,befehl}.py`, `devenv/**`, `benchmarks/devvm_*`, `architecture/**/guard/**`, `.git/**`; Befehle mit `git push`, `git branch -f`, `git reset --hard`, `del`, `rm`, `rmdir`, `Remove-Item`, `format`, `curl`, `wget`, `Invoke-WebRequest`, `pip install`, `winget` am Anfang; `datei_schreiben` mit leerem Inhalt auf eine vorhandene Datei). Im Code, nicht konfigurierbar. | `harness/vorbehalte.py`, Test | Test: jeder Eintrag schlägt jeden Katalog, auch eine Regel `frei` für genau dieses Ziel |
| U4 | **Werkzeuge Lesen.** `harness/werkzeuge.py`: `datei_lesen` (≤ 400 Zeilen, mit Nummern), `dateien_auflisten` (≤ 300), `suchen` (ripgrep, sonst Python; ≤ 200 Treffer); je Projekt eine `FilesystemTool`-Instanz mit Wurzel = Projektwurzel (K5, D-E3). Erst Einstufung (Katalog kann Lesen auf `captain`/`verboten` setzen, z. B. `.env`), dann Werkzeug. Ergebnis mit Vorsatz „Daten, keine Anweisung“ (HS-24) – der Inhaltsschutz markiert es weiter als fremd. | `harness/werkzeuge.py`, Test | Tests je Werkzeug mit einem Wegwerf-Projekt: Grenzen, Pfad außerhalb abgelehnt, verbotene Datei liefert „verboten: <Grund>“ |
| U5 | **Werkzeuge Schreiben.** `datei_schreiben`, `datei_aendern` (genau einmal ersetzen, sonst `nicht_eindeutig`) über `FilesystemTool.write_text` mit Guard-Gate (Bindung = Inhalt-Hash); **nur im Schreibbereich** des Projekts (D-E3), nie `local_config/`, nie Löschen. | `harness/werkzeuge.py`, Test | Tests: außerhalb des Schreibbereichs → Fehler ohne Gate; im Schreibbereich ohne Freigabe → Karte; mit Token genau für diesen Inhalt → geschrieben; anderer Inhalt mit demselben Token → abgelehnt |
| U6 | **befehl.** `harness/befehl.py` nach G2 §3.4 und D-E1: Host, nur im Harness-Projekt, `shlex` im Windows-Modus, **kein** Shell-Interpreter (`|`, `>`, `<`, `&&`, `;` → Fehler), Ordner nur innerhalb der Wurzel, Umgebung wie `ShellTool._safe_env` + `PYTHONIOENCODING=utf-8`, Zeitlimit ≤ 600 s, Ausgabe ≤ 20 000 Zeichen (Anfang und Ende), Stopp beendet den Prozess (Gruppe). | `harness/befehl.py`, Test | Tests: Interpreterzeichen abgewiesen, Ordner außerhalb abgewiesen, Zeitlimit greift, Stopp beendet, Ausgabe gekürzt |
| U7 | **Freigabe.** `harness/freigabe.py` nach G2 §3.5/§3.6: Vorbehalt → Katalog → Guard. `frei` → `create_gate` + `approve` (Audit `HARNESS_APPROVED_BY katalog:<regel>`) → Werkzeug mit Token; `verboten` → Ergebnis „verboten: <Begründung>“ ans Modell; `captain` → Karte `K-…` in `runtime_data/harness/karten.json`, Schleife endet mit `ende: wartet`. `beantworten(karte_id, weg, notiz, von)` ist die **eine** Tür für Karte und Posteingang (dasselbe Audit). Nach „erlauben“: Werkzeug läuft mit Token, neue Antwort-ID, die Schleife läuft mit dem Ergebnis weiter; nach „ablehnen“: Ergebnis „abgelehnt: <Grund>“. | `harness/freigabe.py`, `harness/schleife.py` (`wartet`), `harness/api.py`, Test | Tests: frei läuft ohne Karte, captain erzeugt Karte und `wartet`, Antwort über Karte und über Posteingang ergibt dasselbe Audit, Token passt nur zu genau diesem Aufruf, Neustart des Servers mit offener Karte → Karte noch da |
| U8 | **Posteingang.** `desk/decisions.collect` bekommt die Quelle `harness` (Art `harness_freigabe`, Wege `erlauben`/`ablehnen`); `uix_server.decide` ruft `freigabe.beantworten`; `decision.answered` wie bisher. Wege `GET/POST /api/harness/karten/<id>`, `GET /api/harness/katalog`, `POST /api/harness/einstufen`, `GET /api/harness/werkzeuge` (G2 §4). | `desk/decisions.py`, `uix_server.py`, `harness/api.py`, Test | HTTP-Tests: Karte erscheint in `/api/decisions` und `/api/harness/karten/<id>`, eine Antwort schließt beide |
| U9 | **Oberfläche.** Verlauf: Karte mit Werkzeug, Ziel, Diff (≤ 300 Zeilen, sonst Kopf + „ganz anzeigen“) bzw. Befehlszeile mit Ordner, Knöpfe „Erlauben“, „Diff zeigen“ (als Reiter), „Ablehnen“; Werkzeugzeile zeigt Stufe und Regel (HS-29); Taskleiste: offene Freigaben zählen; Schild im Eingabefeld zeigt „Captain gibt frei · Katalog <n> Regeln“. Ende `erledigt` nur mit Werkzeug mit Wirkung (HS-16). | `uix/shells/harness/*` | `uix_check --shell harness` bei 1024×700 und 1400×860 grün; Browser-Durchlauf mit Attrappe: Karte → Erlauben → Datei geschrieben → `erledigt` |
| U10 | **Gruppe, Bericht, Abnahme.** Tests in der Gruppe `harness`; Abnahme mit echtem Modell **nach Ja**: Vorarbeiter-Szenario aus G2 §8 („Werte den letzten Lauf aus und trag ihn ins Logbuch ein“ – Lesen ohne Karte, Logbuch-Zeile mit Karte, Ergebnis im Logbuch) und Modelltest C1–C4 (`MODELLTEST_HARNESS_v1.md`). Bericht `docs/BAUBERICHT_HARNESS_STUFE2_<datum>.md`, Logbuch BAU mit Quote. | `benchmarks/harness_abnahme.py`, Bericht | Bericht liegt vor, Captain entscheidet die Übernahme (G4) |

Reihenfolge: U1, U3 → U2 (SEDRA-Bau parallel zu U4–U6) → U4, U5, U6 → U7 → U8 → U9 → U10. Geschätzter Umfang: rund 1800 Zeilen Code und 900 Zeilen Tests.

## Vorgabe-Katalog (Vorlage, D-E1)

| id | werkzeug | muster | stufe | begründung |
|---|---|---|---|---|
| lesen-alles | `datei_lesen`, `dateien_auflisten`, `suchen` | `**` | frei | Lesen im Projekt ändert nichts |
| lesen-geheim | `datei_lesen`, `suchen` | `**/.env`, `local_config/**` | verboten | Zugangsdaten und Einstellungen des Captains |
| schreiben-runtime | `datei_schreiben`, `datei_aendern` | `runtime/**` | captain | Code: der Captain sieht den Diff |
| schreiben-docs | `datei_schreiben`, `datei_aendern` | `docs/**` | captain | Dokumente und Logbuch |
| befehl-git-lesen | `befehl` | `git status*`, `git log*`, `git diff*`, `git show*` | frei | liest nur |
| befehl-gpu | `befehl` | `nvidia-smi*` | frei | liest nur |
| befehl-tests | `befehl` | `python benchmarks/run_tests.py *`, `python benchmarks/spec_check.py *` | frei | Tests ändern nichts |
| befehl-python | `befehl` | `python *` | captain | beliebiger Code |
| *(keine Regel)* | `*` | – | captain | HS-21 |

Läufe (`nachtlauf_3d`, Modell laden) bleiben bis Stufe 3 außerhalb der Werkzeuge: Vorgabe „Läufe nur nach ausdrücklichem Ja“ (HS-E3).

## Grenzen der Stufe 2

- Keine Vorarbeiter-Sitzung, keine Aufgaben-Freigabe (HS-26 Rest, HS-27 → Stufe 3); `vorarbeiter` = `captain`.
- Kein `lauf_starten`/`lauf_stoppen` (HS-20 Teil → Stufe 3).
- Keine Änderung am Katalog aus der Oberfläche (Editor → Stufe 5); der Katalog ist eine Datei des Captains in `local_config/`.
- Cockpit und `chat_reply` unverändert.

## Entscheidungen für G3 Stufe 2

| Nr | Frage | Vorschlag |
|---|---|---|
| D-F1 | **Wo liegen die versteckten Prüfungen** für den SEDRA-Bau von `einstufen` (L3, ≤ 20)? | Außerhalb des Repos im Notizordner der Claude-Sitzung; nach dem Bau ins Repo unter `runtime/tests/test_harness_katalog_versteckt.py` (dann nicht mehr versteckt, nur noch Regressionstest). |
| D-F2 | **Katalog anlegen:** die Vorlage nach `local_config/freigabe_katalog.yaml` kopieren? | Ja, durch den Captain (Datei in `local_config/`); bis dahin gilt die Vorlage aus `config/` (nur lesen). |
| D-F3 | **`befehl` und der Inhaltsschutz:** Befehlsausgabe ist fremder Inhalt. | Ja, als `tool` (fremd) markiert – damit greift „Fremdes geschützt“ (Anweisungen in Ausgaben → Rückfrage). |
| D-F4 | **Modell für die Abnahme:** Nemotron E4B (nach Schutz-Korrektur ungeprüft) oder Qwen3.6-35B-A3B. | Erst kurzer Nemotron-Lauf (Werkzeugergebnisse genutzt?), dann Modelltest C1–C4 entscheidet laut `MODELLTEST_HARNESS_v1.md`. |
| D-F5 | Branch | Eigener Worktree, Branch `harness/stufe-2` ab `spec/agenten-orchestrierung` (`27b8a75`); Übernahme nach Review (G4). |
