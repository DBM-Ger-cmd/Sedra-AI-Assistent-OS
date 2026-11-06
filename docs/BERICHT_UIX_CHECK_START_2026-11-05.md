# Bericht UIX-Check – ausbleibender Start (05.11.2026)

Basis `main` d51083a + U9-Patch (vorgemerkt, nicht committet). Maschine: Linux, **2 Kerne**, Chromium aus Playwright.
Last: `run_tests.py test_uix_dock_stufe2 test_uix_shell_fisch test_uix_wissen_v2 --slow --jobs 4`, daneben als zweite Last 4 bzw. 6 CPU-Brenner (`python3 -c "while True: pass"`).
„Vorher“ wurde auf einer Kopie des U9-Stands gemessen (`git checkout-index`), „nachher“ im Worktree, mit derselben Last.

## Ergebnis zuerst

| Lauf | vorher | nachher |
|---|---|---|
| unter Last, 4 Brenner | **1 von 3 Läufen rot** (3 rote Tests), 237–243 s | **4 von 4 grün**, 213–217 s |
| unter Last, 6 Brenner | **2 von 2 Läufen rot** (1 bzw. 2 rote Tests), 284 s | **2 von 2 grün**, 275–278 s |
| ohne Last, je Datei einzeln | grün; dock 120 s, fisch 18 s, wissen 44 s | grün; dock 101 s, fisch 12 s, wissen 37 s |

Je Test, vorher (rot gesehen) → nachher:

| Test | vorher unter Last | nachher |
|---|---|---|
| `test_uix_dock_stufe2.ImBrowser.test_ein_einzelstueck…` | 2× `TypeError: Cannot read properties of undefined (reading 'api')` – `sedraBoot.ctx` fehlte, der Start war nicht fertig | 6/6 grün |
| `test_uix_wissen_v2.WissenImCockpit.test_frage_bleibt…` | 2× `… (reading 'dock')` – `sedra.shells.get('cockpit')` fehlte, Start nicht fertig | 6/6 grün |
| `test_uix_shell_fisch.InTheBrowser` | 1× „der Modus bleibt gemerkt“ (nach dem Neuladen 1200 ms zu kurz), 1× `.fi-glas` fehlt (Start nicht fertig) | 6/6 grün |
| übrige Tests der drei Dateien | in diesen Läufen grün; U9 sah im Volllauf auch `UeberDenWechsel` rot | 6/6 grün |

**Ursache (gemessen):** Ein Shell-Start dauert hier **ohne Last schon 4,4–5,1 s** (18 Messungen in `test_uix_dock_stufe2`). Davon gehen etwa 4,2 s auf rund 130 Modul- und Stildateien, die nacheinander geladen werden (jede ~30 ms, keine einzelne Lücke über 0,3 s); erst danach kommen die API-Aufrufe. Bei 3- bis 4-facher Überbuchung sind das mehr als 15 s – und `wait_until_started` gab nach 15 s **still** auf. Die Tests liefen dann in eine halb gestartete Seite und scheiterten mit Folgefehlern („undefined“, „null“).

## 1. `benchmarks/uix_check.py`

- `wait_until_started(page, ms=None, shell=None, strict=True)`:
  - Wartegrenze `START_MS` = **60 s**, einstellbar über die Umgebungsvariable `SEDRA_UIX_START_MS` (Millisekunden, mindestens 1000). Begründung: 15 s waren unter Last zu knapp (siehe oben); bei 60 s ist „startet nicht“ ein Befund und nicht nur „langsam“. Auf einem schnellen Rechner kostet die Grenze nichts, denn das Warten endet, sobald der Zustand erreicht ist.
  - „Gestartet“ heißt jetzt `sedraBoot.ctx.manifest` (vorher reichte `ctx`); mit `shell=` muss es **die erwartete Shell** sein. Ohne diese Prüfung kehrte das Warten nach einem Wechsel auf der alten Seite sofort zurück.
  - Bleibt der Start aus, gibt es `StartAusgeblieben` (eine Unterklasse von `AssertionError`, im Test also ein FAIL und kein ERROR), mit Grund und dem, was die Seite zeigt: `url`, `titel`, `readyState`, ob `sedraBoot`/`ctx` da sind, welche Shell, `problems` und die ersten 240 Zeichen Text. Beispiel aus der Probe: `Start der Shell ausgeblieben: nach 0.8 s kein window.sedraBoot.ctx.manifest der Shell 'paperclip'; die Seite zeigt: {"url": …, "sedraBoot": true, "ctx": true, "shell": "cockpit", …}`.
  - Wird die Seite mitten im Warten neu geladen („Execution context was destroyed“), wartet die Funktion bis zur Grenze weiter. Wird die Seite geschlossen, bricht sie ab und meldet das als Grund.
  - Mit `strict=False` kommt `True`/`False` zurück, und es wird nichts ausgelöst.
- `run_checks` (das CLI-Prüfwerkzeug) meldet Befunde als Zeilen und soll nicht abbrechen. Dafür gibt es intern `started(page)`: ein ausbleibender Start nach einem Neuladen wird zur Zeile `start FAIL <Meldung>`. Diese Funktion bekommt auch `uix_check_team.run`.
- Das erste Warten in `run_checks` (Cockpit oder `/retro`) nutzt `START_MS` statt fester 15 s.

## 2. Die drei Tests: Zustände statt fester Pausen

Gemeinsames Muster: Den Start meldet `wait_until_started(page, shell=…)`, danach wird jeweils **auf den Zustand gewartet, den die folgende Prüfung liest** (bis `WARTE_MS` = 20 s). Die Prüfungen selbst sind **unverändert**. Wo ein Zustand ausbleibt, kehrt das Warten zurück und die alte Prüfung meldet den Fehler mit ihrer eigenen Meldung.

**Nebenbefund, der die Testlogik betrifft (behoben):** `page.wait_for_function` wartet ein Promise **nicht** ab. Ein `async`-Prädikat ist sofort „wahr“, weil ein Promise-Objekt als wahr gilt. Das Warten auf den Arbeitsstand in `test_neuladen_bringt_die_reiter…` war darum schon vorher wirkungslos; nur die festen 700-ms-Pausen davor hielten den Test grün. Ohne diese Pausen wurde er sofort rot (`'logbook:audit' not found in []`). Neu ist `bis_wahr(page, js)` in `test_uix_dock_stufe2.py`: Es fragt per `page.evaluate` alle 250 ms ab, und `evaluate` wartet ein Promise ab. Alle `async`-Wartestellen nutzen jetzt `bis_wahr`.

`test_uix_dock_stufe2.py`
- `seite()`: statt 1200 ms wird gewartet, bis die Shell `cockpit` gestartet ist und ≥ 1 Reiter steht.
- `oeffnen()`: statt 700 ms wird gewartet, bis der Reiter des Objekts vorn ist.
- Teilen: statt 400 ms wird gewartet, bis ≥ 2 Gruppen da sind.
- `test_reiterwechsel…`: Erst wird gewartet, bis der angeklickte Reiter vorn ist. **Die 600 ms danach bleiben** als Beobachtungszeit. Diese Prüfung stellt fest, dass rechts *nichts* eingehängt wird, und dass etwas ausbleibt, lässt sich nicht abwarten.
- `test_kaputtes_layout…`: Gewartet wird auf Start und Reiter. **Die 1500 ms bleiben** als Beobachtungszeit für späte Fehler auf der Seite (`fehler == []`).
- `test_schliessen…`: Erst muss der Arbeitsstand das Logbuch kennen (das ist neu und macht den Test strenger, sonst prüfte „vergisst“ nichts). Statt 900 ms wird gewartet, bis `object.close` gemeldet ist und das Logbuch nicht mehr im Arbeitsstand steht.
- `UeberDenWechsel.wechseln`: statt 1800 ms wird auf den Start **der Zielshell** gewartet. Statt 900 ms wird gewartet, bis das neue Objekt im Arbeitsstand steht. Im Cockpit wird gewartet, bis Reiter, aktiver Reiter und die Zeile „mitgenommen“ stehen.
- `test_gespraech…`: Statt 1500 ms wird gewartet, bis der Verlauf im Log steht. Statt 300 ms wird gewartet, bis „Wirklich leeren?“ sichtbar ist; erst danach sagt die Prüfung „ein Klick leert nicht“ etwas aus. Statt 700 ms wird gewartet, bis der Text aus dem Log verschwunden ist. Das Werkzeug leert zuerst auf dem Server und dann auf der Seite (`verlauf.js`), deshalb gilt die Prüfung auf dem Server danach sicher.

`test_uix_shell_fisch.py`
- Statt 1200 ms nach dem Start wird je Selektor gewartet, bis er da ist.
- Pseudonymisieren/Prüfen/Freigeben: Statt 1200/1000/1200 ms wird gewartet, bis „Musterfrau“ fort ist, bis der Knopf „Freigeben“ erscheint (den gibt es nur im Status „geprüft“) und bis „Golden Record“ im Kopf steht.
- Neuladen: Statt 1200 ms wird auf `fisch` gewartet und darauf, dass `.fi-modus-btn.on[data-modus="transkript"]` gesetzt ist. Schublade: statt 400 ms wird gewartet, bis sie offen ist und `talk` darin steht.

`test_uix_wissen_v2.py`
- Statt 700 ms nach dem Reiterwechsel wird gewartet, bis die Werkbank-Zeile gewechselt hat. Statt 1500 ms nach Enter wird auf das Suchergebnis gewartet, statt 400 ms auf die Kennung `[W…]` im Feld.
- Statt 800 ms („Ablage bündelt“) wird gewartet, bis die Frage **auf dem Server** in der Ablage liegt (`/api/ablage/lesen` mit `X-SEDRA-Tool: wissen`; gemessen 0,9 s). `lifecycle.js` schreibt höchstens einmal je Sekunde, und der alte Kommentar „500 ms“ stimmte nicht.
- Wissensbasis: Statt 1500/1200/900/1500 ms wird gewartet auf den Start von `wissensbasis` mit Orten, auf die Treffer, auf die Fundstelle mit Text und `mark` und auf die Antwort mit `.t-wissen-zitat`.
- `ruhig(page, '.t-wissen')` vor dem Tippen wartet, bis das Werkzeug 600 ms lang nicht neu gezeichnet hat (MutationObserver). Siehe Abschnitt 4.

**Lockerungen, begründet:**
- Wartegrenzen 15 s → 20 s (`dock_stufe2`, `fisch`) und 5 s → 20 s (`wissen_v2`: `.t-wissen`, Suchfeld nach dem Neuladen). Das sind Grenzen fürs **Warten** und keine Prüfwerte. Unter Last kommt das Werkzeug nach dem 5 bis 20 s dauernden Start oft erst danach. Auf einem schnellen Rechner ändern sie nichts.
- Start 15 s → 60 s (siehe 1). Ein ausbleibender Start bleibt rot, jetzt mit einer klaren Meldung.
- Keine Prüfung entfernt oder weicher gemacht. Eine Prüfung ist strenger geworden (`test_schliessen`: das Logbuch muss vorher im Arbeitsstand stehen).

## 3. Weitere Aufrufer von `wait_until_started`

Geprüft mit `run_tests.py … --slow --jobs 2` (ohne Zusatzlast): `test_menue_seite`, `test_uix_shell_start`, `test_uix_flows`, `test_stufe_c_rahmen`, `test_uix_cockpit_baum`, `test_uix_rekorder`, `test_gateway_menu_browser`, `test_rekorder_fenster`, `test_uix_planung`, `test_gateway_kmu_shell`, `test_uix_harness_browser`, `test_uix_browser` (`run_checks`), `test_uix_stufe6`. Ergebnis: **13 Dateien, 48 Tests, 1 übersprungen, 0 rot**, 321 s. Alle rufen `wait_until_started(page)` mit einem Argument auf. Die Signatur ist damit verträglich, und das neue Auslösen trifft nur Fälle, in denen ohnehin nichts gestartet ist.

- `uix_check.py --shell cockpit` (CLI): `result ok 41 of 41 checks ok`.
- `harness_abnahme_stufe6.py`: ok. `harness_abnahme_stufe5.py`: „nicht bestanden“ (S5-A, Weg `befehl_punkt` ist `null`), **auf dem Vorher-Stand genauso**, also nicht durch diese Änderung. `harness_abnahme.py` braucht `--url` und wurde nicht gestartet.
- In den Abnahmeskripten (`harness_abnahme*.py`) bricht ein ausbleibender Start jetzt mit `StartAusgeblieben` ab (der `finally` räumt den Server ab, der Exit-Code ist ≠ 0). Vorher lief das Skript weiter und scheiterte dann mit einem Folgefehler. `harness_abnahme.py` Z. 326/328 hat nach dem Shell-Wechsel noch feste 2,5 s vor dem Warten. Mit `shell='cockpit'` bzw. `shell='harness'` wäre das sicher. Nicht geändert, weil das außerhalb des Auftrags liegt (Vorschlag).

## 4. Befund im Produkt (nicht behoben, `runtime/src` außerhalb des Auftrags)

In der Wissensbasis zeichnet das Werkzeug „Wissen“ kurz nach dem ersten Zeichnen gelegentlich noch einmal und ersetzt dabei das Suchfeld. Ein schon getippter Text ist dann fort, und Enter sucht mit leerer Frage („Die Frage enthält kein Suchwort.“). Ohne Last trat das in **1 von 4 Läufen** der ganzen Datei auf (ohne die alte 1500-ms-Pause). In diesen Fällen kam kein Bus-Ereignis, und nach dem ersten Zeichnen ging kein weiterer `/api/objects`-Aufruf ab. Welcher Weg das zweite Zeichnen auslöst, ist **offen (Vermutung: ein zweites Einhängen durch den Rahmen der Vorgabe-Shell)**. Für den Captain heißt das: Tippt er sofort nach dem Laden, kann seine Eingabe verloren gehen. Der Test wartet jetzt mit `ruhig` und nicht mit einer festen Pause. Danach waren es 5 von 5 Läufen der Datei grün, dazu alle Lastläufe.

Restrisiko (notiert): „Leeren“ fällt nach 4 s von selbst zurück (`verlauf.js`). Kommt der zweite Klick unter sehr hoher Last später, bleibt der Test rot. Gesehen habe ich das nicht.

## 5. Abschlussprüfung

- Lastläufe siehe oben: nachher 6/6 grün (4 mit 4 Brennern, 2 mit 6 Brennern).
- `python3 benchmarks/run_tests.py harness uix desk` (ohne Zusatzlast): 110 Dateien (Browser-Bahn ausgelassen: 5), **1206 Tests, 9 übersprungen, 0 rot**, 404 s.

## Geänderte Dateien

- `runtime/benchmarks/uix_check.py`: `START_MS`, `StartAusgeblieben`, `seite_zeigt`, `wait_until_started` neu, `run_checks` meldet einen ausbleibenden Start als Zeile.
- `runtime/tests/test_uix_dock_stufe2.py`: `WARTE_MS`, `bis_wahr`, Zustände statt Pausen.
- `runtime/tests/test_uix_shell_fisch.py`: Zustände statt Pausen.
- `runtime/tests/test_uix_wissen_v2.py`: Zustände statt Pausen, `ruhig`, Ablage auf dem Server abwarten.
