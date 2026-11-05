# Bericht U9 – Testgesundheit (05.11.2026)

Basis `main` d51083a, Worktree ohne Commit. Maschine der Messung: Linux, **2 Kerne**, Python 3.13, Chromium aus Playwright.
Last: 4 CPU-Brenner (`python3 -c "while True: pass"`) neben dem Testlauf, also etwa dreifache Überbuchung; zusätzlich zwei Volläufe `harness uix desk --jobs 4`.

## Ergebnis zuerst

| Test | vorher unter Last | nachher unter Last | Ursache |
|---|---|---|---|
| `test_uix_stufe6.ImBrowser` | **3 von 3 Läufen rot** (4, 2, 1 rote Tests) + im Volllauf 2 rot | **4 von 4 Läufen grün** (je 10 Tests) | feste Wartezeiten; Startwarten schluckt Zeitüberschreitung; Shell-Wechsel nicht abgewartet |
| `test_harness_lauf` | hier **nicht reproduzierbar** (11 Läufe unter Last grün) | grün, + 1 neuer Test | ein echtes Rennen in `Laeufe.laden` gefunden und behoben (deterministisch belegt) |
| `test_uix_harness_lauf` | hier **nicht reproduzierbar** (11 Läufe unter Last grün) | grün | wie oben (gleicher Code `laden`); Zeitreserve gemessen |

## 1. `test_uix_stufe6.ImBrowser`

**Befund (vorher, 3 Läufe unter Last, alte Fassung als Kopie gemessen):**
- `test_r1_leiste_und_mini_hub_in_jeder_shell`: `wait_for_selector('.sx-hub .sx-hub-shell', timeout=5000)` überschritten (3/3 Läufe).
- `test_r8_kmu_arbeitsbereich`: `querySelector('.sh-gateway-kmu-body')` ist `null`.
- `test_r1_mehr_zeigt_die_uebrigen`: `mehr.is_visible()` ist `False`.
- `test_mini_hub_ziehen_klappen_merken_wechseln`: `window.sedraBoot.ctx` ist `undefined` nach dem Wechsel zu Paperclip.

**Ursache:**
1. `uix_check.wait_until_started` wartet höchstens 15 s und **schluckt die Zeitüberschreitung**. Unter Last war die Shell nach 15 s + 2,2 s noch nicht gestartet – belegt durch R8: der KMU-Körper wird in `shell.start()` synchron gebaut, `ctx` erst danach gesetzt; „null“ heißt also „Start nicht fertig“. Die Tests scheiterten dann mit Folgefehlern statt mit einem Befund.
2. Der Shell-Wechsel ist POST → bis zu 1,5 s Ablage schreiben → `location.reload()`. Nach festen 2,5 s stand unter Last noch die alte Seite; `wait_until_started` kehrte dort sofort zurück, dann riss das Neuladen den Kontext weg.
3. Feste Pausen (200 ms, 600 ms, 900 ms) nach Klicks und Größenänderung; die Leiste ordnet sich gebündelt (200 ms) erst, wenn die Instrumente Werte haben; die Fundstelle lädt ihren Text nach („Lese [W…] …“ stand nach 900 ms noch da – im ersten Nachher-Lauf 2× gesehen, dann behoben).

**Änderung (nur `runtime/tests/test_uix_stufe6.py`):**
- `gestartet(page, shell)`: wartet bis zu 60 s auf `sedraBoot.ctx.manifest` **der erwarteten Shell** und meldet einen ausbleibenden Start als Zeitüberschreitung (statt still weiterzumachen).
- Shell-Wechsel: `page.expect_navigation()` um den Klick, danach `gestartet`.
- Zustände statt Millisekunden: `.lst-mehr` sichtbar, Feld offen/zu, Fundstelle ≥ 280 px, `dataset.zeige`, Text „Vor dem Laden“ – jeweils bis 20 s. Danach bleiben **alle bisherigen Prüfungen unverändert** stehen; das Warten macht keine Prüfung weicher, es verschiebt nur den Zeitpunkt.
- R1 „Mehr“: Zahl auf dem Knopf und Zellen im Feld in **einem** `evaluate` gelesen (ein späteres Neuordnen schließt das Feld und ändert die Zahl).
- Abschwächung, begründet: der Selektor `.sx-hub-shell` hat 20 s statt 5 s (die Knöpfe kommen aus `/api/uix/modules` nach dem Start).

**Messung nachher:** 4 Läufe der Endfassung unter derselben Last: 10/10 grün je Lauf, 201–203 s (vorher 288–357 s, weil Zeitüberschreitungen Zeit kosteten). Ohne Last vorher 166 s.

## 2. `test_harness_lauf` und `test_uix_harness_lauf`

**Befund:** Unter Last hier nicht reproduzierbar: 5 Läufe mit 4 Brennern, 6 Läufe neben dem Browser-Test plus Brennern, 2 Volläufe `--jobs 4` – alle grün (22 bzw. 35 Tests). Die Wackler stammen vermutlich vom Windows-PC des Captains (anderes Prozessmodell, Virenscanner); das kann ich hier nicht prüfen.

**Gefundener echter Fehler (Code, `harness/lauf.py`, `Laeufe.laden`):** `laden` las zuerst `ende.json` (noch nicht da) und prüfte danach, ob die Hülle noch lebt. Schreibt die Hülle ihr Ende genau dazwischen und ist fort, meldet `laden` einen sauber beendeten Lauf als **`verloren`** statt `ok`. Unter Linux startet die Prozessprüfung `ps` (ein Unterprozess, der zugleich den Zombie der Hülle abräumt) – das Fenster ist also nicht leer und wächst unter Last. Beide Testdateien erwarten an mehreren Stellen `ok` nach dem Ende und wären genau so rot geworden.
- Belegt mit neuem Test `test_ende_zwischen_lesen_und_prozesspruefung_ist_nicht_verloren` (simuliert das Ende genau zwischen den beiden Schritten): **vorher rot** (`verloren`), nachher grün.
- Zufällig getroffen habe ich das Rennen nicht (Probe: 140 kurze Läufe unter Last, alle `ok`) – es ist selten; ob es die Wackler des Captains erklärt, ist **Vermutung**.
- Fix (kleinste Änderung): ist kein Ende da und der Prozess weg, wird `ende.json` ein zweites Mal gelesen; erst wenn es dann fehlt, heißt der Lauf `verloren`. Verhalten sonst gleich (`test_toter_prozess_ohne_ende_ist_verloren_nie_ok` bleibt grün).

**Weitere Prüfung `test_uix_harness_lauf`:** Der knappste Zeitpunkt ist `test_lauf_mit_modell…` (Lauf `modellprobe` dauert ~0,8 s, der Test erwartet währenddessen „Modell belegt“). Gemessen unter Last: die Prüfungen kommen nach 0,01–0,06 s, der Lauf endet nach 1,05–1,10 s (8/8). Reserve ~1 s – hier kein Problem; auf einem sehr langsamen PC denkbar, deshalb nicht geändert, aber notiert.

## 3. Abschlussprüfung

- `python3 benchmarks/run_tests.py harness uix desk --jobs 2` (ohne Zusatzlast): 110 Dateien, **1206 Tests, 9 übersprungen, 0 rot**, 276 s.
- `PYTHONPATH=src python3 -m unittest test_freigabe_vollstaendig` (im Ordner `tests`): 17 Tests, OK.

## 4. Nebenbefund (nicht in U9 behoben)

Im Volllauf `harness uix desk --jobs 4` auf 2 Kernen wurden weitere Browser-Tests mit demselben Muster rot (`uix_check.wait_until_started` + feste Pausen): `test_uix_dock_stufe2.ImBrowser` (2), `test_uix_dock_stufe2.UeberDenWechsel` (2), `test_uix_shell_fisch.InTheBrowser` (1), `test_uix_wissen_v2.WissenImCockpit` (2). Vorschlag: `wait_until_started` in `benchmarks/uix_check.py` die Zeitüberschreitung nicht mehr schlucken lassen (oder einen strengen Zwilling anbieten) und die Tests wie hier auf Zustände umstellen – eigener Auftrag, weil außerhalb von U9 und `runtime/tests`.

## Geänderte Dateien

- `runtime/src/guppi_runtime/harness/lauf.py` – Rennen in `Laeufe.laden` (9 Zeilen).
- `runtime/tests/test_harness_lauf.py` – neuer Test für das Rennen.
- `runtime/tests/test_uix_stufe6.py` – Warten auf Zustände statt fester Pausen, strenger Start.
