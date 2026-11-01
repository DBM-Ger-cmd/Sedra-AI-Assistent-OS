# Baubericht Harness-Shell – Analyse-Pakete P0–P3 (1.11.2026)

Grundlage: `ANALYSE_HARNESS_2026-11-01.md` (G1; 30 Befunde A1–A30, 9 Vorschläge V1–V9, §5 Maßnahmen M1–M3 aus dem Harness-Vergleich 31.10.).
Freigabe des Captains 1.11. 20:44: E-A1 P0→P1→P2→P3 ja; E-A2 Denktext speichern; E-A3 HS-16 Spec anpassen; E-A4 V4/V5/V7 eigene Specs;
E-A5 kein Push → Stick-Punkte 5–7 als Bericht; E-A6/E-A7/E-A8 ja; „A1 – das darf nicht sein“ zuerst.
Branch `harness/bau-2026-11-01` auf `origin/main` `bf20ff5` (11 Commits); Shell-Version 1.8.0 → **1.9.0**. Lieferung als Fork-ZIP + Patch, kein Push.

## 1. Was gebaut wurde

### P0 – Maßnahmen aus dem Harness-Vergleich (Commits a9babfc, c53ff9e, 3e50afc)

| Nr | Gebaut | Dateien |
|---|---|---|
| **M1** Sitzungs-Erlaubnis | Knopf **„Für diese Sitzung erlauben“** auf der Karte → `POST karten/<id> {weg: sitzung}`: der Aufruf läuft wie `erlauben`, die Sitzung merkt sich `(werkzeug, muster)` (Dateien: Ordner der Datei `ordner/**`, Wurzel `*`; Befehl: Anfang der Zeile `python -m unittest*`, `git commit*`; Läufe: genau das Ziel). Gleichartige Aufrufe laufen bis zum Schließen ohne Karte, Audit `HARNESS_APPROVED_BY sitzung:<karte>`, `HARNESS_SITZUNG_ERLAUBT`. **Nie** bei festem Vorbehalt, Warnkarte (W-2), Aufgabenkarte, `verboten`, `modell_laden/entladen` (weicher Vorbehalt). Liste mit „Zurücknehmen“ (`PATCH sitzungen/<id> {erlaubnis_zuruecknehmen}`) unter Einstellungen → Agent → Freigabe-Modus. Ablage: Eintrag `erlaubnis` im Sitzungs-JSONL (Rücknahme `aktiv: false`). | `harness/erlaubnis.py` (neu, rein), `freigabe.py`, `sitzung.py`, `api.py`, `schleife.py` (Karten-Ereignis trägt `vorbehalt`/`warnung`), `uix/shells/harness/karte.js`, `erlaubnisse.js` (neu), `einstellungen.js`, `einstellungen.css` (neu, aus shell.css) |
| **M1** Katalog-Vorlage | Regel `schreiben-schreibbereich` (`${schreibbereich}` → je Projekt dessen Muster, `frei`; die genaueren Regeln `runtime/**`, `docs/**` gewinnen weiter – für das Repo-Projekt ändert sich nichts) und `befehl-unittests` (`python -m unittest*`, `python -m pytest*`, `python3 …`, `pytest*` → `frei`); `befehl-python` bleibt `captain`. `POST einstufen` nimmt `projekt` an. | `config/freigabe_katalog.beispiel.yaml`, `harness/katalog.py` (`mit_projekt`, `SCHREIBBEREICH`), `api.py` |
| **M2** Modell halten | Ursache der Entlade-Panne: `job_supervisor._models_in_use` kannte nur Job-Versuche. Jetzt Haken `in_use_extra` → `harness.modelle_in_gebrauch()`: Modelle laufender Antworten, der zuletzt beendeten (60 s Nachlauf), und bei offener Werkzeug-Karte alle geladenen des llama-server. | `jobs/job_supervisor.py`, `harness/api.py` (`_aktiv`, `_zuletzt`, `NACHLAUF_S`), `uix_server.py` (Verdrahtung) |
| **M2** Auto-Laden | `GET vorgaben` → `{rezept_standard, projekt_standard, auto_laden: {rezept, regel} | null, auto_laden_grund}`; `nachricht` ohne Modell liefert dasselbe. Die Shell lädt beim Senden selbst (Zeile „Lade Modell … n s“) **nur**, wenn der Katalog `modell_laden` für das Standard-Rezept `frei` stellt (E-A7); die Vorlage tut das nicht → auf dem PC des Captains kein Auto-Laden, der Stick-Katalog setzt es. | `api.py` (`vorgaben`, `_rezept_standard`), `modell.js` (`autoLaden`), `verlauf.js` |
| **M3** Ordner öffnen | `POST projekte {wurzel, name?, schreibbereich?}` → Antrag `harness_projekt` (`HARNESS_PROJEKT_ADD`, Bindung mit Stand-Hash) im Posteingang „Ordner als Projekt öffnen“; Freigabe schreibt die **Laufzeitdatei** `runtime_data/harness/projekte.yaml` (atomar, `.bak-<zeit>`; im Vorbehalt `**/runtime_data/harness/**`, das Modell kommt nicht heran) – **nie** `local_config/` (E-A8; die Analyse nannte `<projekt>/.sedra/`, die Ablage der Harness ist der passendere Ort). Gesperrt: `local_config/`, `runtime_data/`, relative Pfade, `..` im Schreibbereich, schon vorhandene Ordner. `projekte.laden` = Datei des Captains + Laufzeitprojekte (`quelle: laufzeit`), Ereignis `harness.projekt`, kein Neustart. Formular unter der Projektzeile („Ordner öffnen …“: Pfad, Name, Schreibbereich). | `harness/projekte.py` (`laufzeit_*`, `neues_projekt`, `id_aus`), `antraege.py` (`projekt_antrag`, `_projekt_anwenden`), `desk/decisions.py` (Titel/Hinweis), `api.py`, `projekt.js` (neu), `eingabe.js`, `shell.js` |
| **M3** Vorgaben | `POST vorgaben {rezept_standard?, projekt_standard?}` (ohne Gate – eine Wahl, keine Erlaubnis; Herkunft S7); „Als Vorgabe merken“ neben Projektwahl und in der Modell-Steuerung; neue Sitzungen und die Rezeptwahl nehmen die Vorgabe, sonst „zuletzt geladen“. | `projekte.py`, `api.py`, `projekt.js`, `modell.js`, `eingabe.js` |

### P1 – Fehler und Lücken (Commits 3e50afc, c12e0b3)

| Nr | Gebaut |
|---|---|
| **A1** | `nachricht` und die Fortsetzung nach einer Karte bereiten erst Vorlage und Kiste vor (beides kann werfen) und legen die Antwort danach an; scheitert der Start trotzdem, endet die Antwort sofort mit `fehler`/`ende` (`_antwort_verwerfen`, Audit `HARNESS_ANTWORT_VERWORFEN`). Test: kaputte Vorlage → 400, `laufend` leer, Sitzung verschiebbar. |
| **A2** | Herkunft S7 jetzt auch auf `POST sitzungen/<id>/nachricht`, `PATCH/DELETE sitzungen/<id>`, `POST antworten/<id>/stopp`, `POST projekte`, `POST vorgaben` (`GESCHUETZT`, `herkunft_verlangt` auch für PATCH) und `/api/model/load|unload` (`HERKUNFT_WEGE`). |
| **A3** | Mikrofon-Knopf öffnet Einstellungen → Sprache → Rekorder (eingehängtes Werkzeug) statt nach einem Chip zu suchen, den es mit `umschalter: menue` nicht gibt. |
| **A4** | Taskleiste nutzt `reiter.titel` für alle Reiterarten (Einstellungen heißt „Einstellungen“ ⚙, Diff ±). |
| **A5/A9** | Seitenleiste: „Ja“ beim Löschen mit `catch` (Satz bei `antwort_laeuft`); ein offenes Umbenennen-Feld oder eine Rückfrage schiebt den Neuaufbau auf (`data-fertig`), bis es fertig ist. |
| **A6** | `FRIENDLY_400` kennt die Harness-Codes (`antwort_laeuft`, `zu_viele_antworten`, `karte_offen`, `titel_leer`, `zweck_fehlt`, `projekt_unbekannt`, `erlaubnis_unbekannt`, …) als Sätze. |
| **A7** | Statuszellen frischen im 15-s-Takt auf (sichtbarer Tab), HS-52 (≤ alle 2 s) bleibt. |
| **A8** | Der offene Aufgaben-Reiter zeichnet sich bei `harness.aufgabe`/`vorarbeiter`/`decision.*` neu (über `freigabenLaden`). |
| **A10** | `Sitzungen.liste()` mit Zwischenspeicher je Datei (`mtime_ns`, Größe): nur geänderte Dateien werden gelesen; Zeile trägt `erlaubnisse`. |
| **A12** | Vorschau-Hinweis einmal je Browser, nur im sichtbaren Reiter, im Kopf der Vorschau statt als Toast über dem Senden-Knopf. |
| **A13** | `S._karten` wird beim Schließen eines Reiters bereinigt. |
| **A15** | `senden` prüft auch `wartet` (kein zweites `POST sitzungen`). |
| **A23** | Esc schließt erst Dateiauswahl bzw. Start-Menü, stoppt dann erst die Antwort. |
| **A24** | Ordner, in denen nichts lesbar ist (`local_config/`), erscheinen nicht in der Dateiauswahl. |
| **A25** | `sedra.harness.vorschau` und `…app.nachweis` werden bereinigt (nur vorhandene Sitzungen / offene Apps). |
| **A26** | `freigabenLaden` dedupliziert parallele Aufrufe. |
| **A27** | Kommentare (`_harness_write`, Ereignisliste in `api.py`) berichtigt. |

### P2 – Stick-Sicht / erster Start (Commit dbffbb5)

| Nr | Gebaut |
|---|---|
| **V1/A11** „Passt das Modell?“ | `GET modelle`: je llama-server-Rezept die Prüfung des Routers (`_evaluate`, dieselbe wie beim Laden, ohne zu laden): `passt`, Bedarf VRAM/RAM, dynamische Auswahl, Grund (`host_vram_below_minimum`, Zahlen bei dynamischen Rezepten …), gemessen, geladen; freier Speicher aus `speicher_stand`. Sortierung: geladen → passend (gemessene, kleiner Bedarf zuerst) → Rest. Die Rezeptwahl zeigt Modellname statt ID, „✓ passt · ≈ 9,8 GB VRAM“ / „✗ zu wenig Grafikspeicher …“, darunter „frei: … GB VRAM, … GB RAM“; leere Liste → Knopf „Werkstatt öffnen“. |
| **V2/A22** Erststart | Leere Sitzung: drei Schritte mit ✓/○ (Modell laden · Projekt · erste Nachricht) und Knöpfe („Modell wählen“, „Ins Feld“); Satz zu `+`, `@`, `/`. Frischt bei Modell-/Projektwechsel auf. |
| **V3/A30** Zeitlinie | Taskleisten-Knopf einer laufenden Antwort zeigt Phase und Dauer: „denkt · 12 s“, „schreibt“, „Werkzeug befehl · 40 s“, „wartet auf Freigabe“, „Stopp angefordert – endet mit dem nächsten Schritt“; dazu eine Notiz im Verlauf beim Stopp. |
| **V9** Fehlerzeile | `fehler` im Strom zeigt „Logbuch öffnen“ (App `logbook`, sonst Einstellungen → Audit). |
| **A14** Doku | README (Stufe 6 + Bau 1.11., Version 1.9.0, Zonen/Wege/„Noch nicht da“ aktuell), `arbeitsplatz.yaml` (Anhängen, Vorschau, Modell laden, Sitzungs-Erlaubnis, Ordner öffnen, Vorgabe, Zeitlinie), `anhaenge_ab_stufe_2` → erklärender Code, Kopfkommentar `eingabe.js`. |
| **A21** Texte | Karte: „Entscheidet der Captain · Regel „schreiben-docs“ · …“ statt „Stufe captain · Regel keine“; Schild ohne Stufen-Namen; `/einstellungen` ohne „(HS-42)“. |

### P3 – Pflege und Vertrag (Commit dbffbb5)

| Nr | Gebaut |
|---|---|
| **A16** (E-A2) | `schleife.py` speichert die ersten 4 000 Zeichen des Denkens (`DENKEN_MAX`, nur im Live-Modus; scharf: nichts) als `denken_text`; die Zeile nach dem Neuladen zeigt ihn („Anfang gespeichert“, wenn gekürzt). |
| **A17** (E-A3) | `SPEC_HARNESS_SHELL_v1.md` HS-16: „erledigt“ = ausgeführt (Werkzeug mit Wirkung, `ok`); Nachtrag und Entscheidung HS-E7 eingetragen. Code unverändert. |
| **A18** | Entscheidungen der Harness tragen `sitzung_id` als Feld; `shell.js`/`taskleiste.js` lesen es zuerst (Regex auf `note` nur noch als Rückfall). |
| **A19** | Eine Ansichts-Vorlage `reiter.stub(id, box, S, extra)` statt fünf Kopien (karte, aufgabe, lauf, app, einstellungen); `ID` der Sitzung nur noch in `reiter.js` (`reiter.ID`). `seg()` in startmenue/einstellungen bleibt doppelt (verschiedenes Verhalten – Merkposten). |
| **A20/V8** | `verlauf.js` 369 → 310 Zeilen: **`zeilen.js`** (Werkzeugzeile, Denkzeile, Fuß) und **`strom.js`** (SSE-Zerlegung, Phasen, Dauer-/Denktexte, `lesen` mit fetch) ausgelagert; `strom.js` ist rein und mit `node` geprüft (Teilstücke, Kommentare, kaputte Daten, Ende). `shell.css` 388 → 378 (Einstellungen in `einstellungen.css`). |
| **A28** | `system.state` getrennt/verbunden → Hinweis „Verbindung zum Server getrennt – ich versuche es weiter“ / „Wieder verbunden“ und Neuladen von Sitzungen, Freigaben, Modell, Projekten. |
| **A29** | Reiter `aufgaben:`/`einstellungen:` überleben das Neuladen (localStorage wie Sitzungs-Reiter). |
| **V6** Export | `GET sitzungen/<id>/export` → `{markdown, dateiname}` (`harness/export.py`, rein: Verlauf, Werkzeugzeilen gekürzt, Karten mit Entscheidung, Erlaubnisse, Denkzeile); Knopf ↓ in der Sitzungszeile und `/export` speichern die Datei im Browser (Blob). |

Nicht gebaut (eigene Specs, E-A4): V4 Verlauf mit Werkzeugergebnissen, V5 Suche, V7 Karte → Katalog. Stick-Paket Punkte 5–7: `STICK_VORSCHLAEGE_PUNKTE_5_7_2026-11-01.md` (Bericht, kein Code).

## 2. Prüfung

| Bahn | Ergebnis |
|---|---|
| Neue Tests `tests/test_harness_bau_2026_11_01.py` | 29 Tests (ErlaubnisRein, KatalogSchreibbereich, StromLeserRein (node), P1Befunde, ModellHalten, SitzungsErlaubnisServer, OrdnerOeffnen) – alle grün |
| Gruppen `run_tests.py scheduler desk orchestra uix harness` | 1 437 Tests, 10 übersprungen, **1 rot → behoben**: `test_uix_harness_shell.test_reiter_merken_nur_ids` prüfte den alten Wortlaut von HS-03 (nur Sitzungs-IDs merken) – A29 merkt bewusst auch `aufgaben:`/`einstellungen:`; Test an das neue Verhalten angepasst, Datei danach 7/7 grün. (617 s) |
| Browser-Bahn `--slow uix harness` | 654 Tests, 10 übersprungen, **0 rot** (885 s) |
| `uix_check.py --shell harness / cockpit / minimal / paperclip` | 43/43 · 41/41 · 42/42 · 45/45 (Konsole ohne Fehler) |
| `harness_abnahme.py --stufe4 / --stufe5 / --stufe6` | S4-A..D ok · S5-A..D ok · S6-A..E ok; Bilder `lieferung/bau/stufe{4,5,6}/` (Bild 03: Erststart-Schritte, „✗ zu wenig Arbeitsspeicher“ in der Rezeptwahl, Knöpfe „Ordner öffnen …“/„Als Vorgabe merken“) |
| `tests/known_red.txt` | leer – jeder rote Test wäre neu |

Ein Fund der Browser-Bahn während des Baus: in `taskleiste.js` verdeckte die Statuszelle `status` die Funktion `status()` im 15-s-Takt
(„status is not a function“) – behoben (`root.sedraHarness.taskleiste.status`), uix_check danach 43/43. Grenzen: ohne Modell (Cloud) sind
Auto-Laden, „passt es?“-Zahlen und die Zeitlinie mit echtem Modell nur über die Attrappe geprüft; die Zahlen prüft der Captain auf seinem PC.

## 3. Für den Captain (G4)

1. Auf dem PC: eine Sitzung mit `datei_schreiben` außerhalb von `runtime/`/`docs/` → **keine** Karte mehr, wenn der Ordner im Schreibbereich liegt
   (Vorlage; eigene `freigabe_katalog.yaml` bleibt wie sie ist). Eine Karte mit „Für diese Sitzung erlauben“ beantworten → die nächste gleichartige läuft ohne Karte;
   Einstellungen → Freigabe zeigt die Erlaubnis; „Zurücknehmen“ → wieder Karte.
2. `evict_idle_models: true` + Scheduler an: eine laufende Harness-Antwort darf das Modell nicht mehr verlieren (Audit: kein `MODEL_IDLE_EVICTED` während `HARNESS_ANTWORT`).
3. Stick-Katalog: `modell_laden: frei` für die Basis-Rezepte → „Senden“ ohne Modell lädt und sendet danach selbst.
4. Entscheidung zu `STICK_VORSCHLAEGE_PUNKTE_5_7_2026-11-01.md` (Modellzuordnung, Rekorder-Fenster weglassen, Kopie auf lokale Platte) und ob der Branch `claude/usb-stick-minimal-3c1b19` gepusht wird (Punkte 1–4).

## 4. Regeln eingehalten

Kein Push, keine Modelle geladen, nichts in `local_config/`/`config/` des Captains (Tests nur in temporären Prüfprojekten), nichts gelöscht
(`.bak-<zeit>` bei der Laufzeitdatei, Sitzungen nach `geloescht/`), alle Shell-Dateien ≤ 400 Zeilen (`verlauf.js` 310, `shell.css` 378), CSS nur Token,
kein `innerHTML`/`eval`; Herkunft S7 auf jedem Schreibweg; Logbuch-Zeilen.
