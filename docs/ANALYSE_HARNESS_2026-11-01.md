# Analyse der Harness-Shell (1.11.2026) – Befunde und Verbesserungsplan (G1)

Captain 1.11. 20:21: „die aktuellen GitHub-Daten ziehen, die Shell Harness gezielt analysieren und dann verbessern“, dazu das
`ENTWICKLERPAKET_USB_STICK_2026-10-31.md` als Kontext (Harness ist die Standard-Shell des Sticks für einen Kollegen mit 16 GB RAM / 8 GB VRAM).
Stand: `origin/main` `bf20ff5` (Härtung übernommen, Stufe 6, Browser-Abnahme Stufe 4–6, Dynamische Rezepte R1–R6, LHM über Remote Web Server).
Branch `harness/analyse-2026-11-01`. Nichts geändert – dieses Dokument ist G1; der Bau folgt nach Entscheidung.

## 1. Ausgangslage: alles grün

| Prüfung (Cloud, ohne Modell) | Ergebnis |
|---|---|
| `uix_check.py --shell harness` | 43/43, 1 nicht geprüft |
| `harness_abnahme.py --stufe4 / --stufe5 / --stufe6` | S4-A..D, S5-A..D, S6-A..E alle ok, Konsole ohne Fehler |
| Letzter Gesamtlauf (30.10., gleicher Code) | 1 407 Tests 0 rot, Browser-Bahn 624 0 rot |

Die Shell erfüllt HS-10/11/13/14/15/18/19/21–29/30/31/33/40–43/50/51/53/80–85 (Durchsicht gegen die G1-Spec). Was folgt, sind die Lücken.

## 2. Befunde (30, nach Schwere)

Pfade: `H/` = `uix/shells/harness/`, `B/` = `harness/`.

| Nr | Bereich | Wo | Befund | Schwere |
|---|---|---|---|---|
| A1 | Schleife | `B/api.py:301-311` | `_antwort_anlegen` läuft **vor** `_kiste`/`_vorlage`; wirft eine davon (ungültige Vorlage, kaputte Kiste), bleibt die Antwort für immer „laufend“: Sitzung dauerhaft `antwort_laeuft` (auch Löschen geht nicht), zählt gegen `MAX_LAUFEND=8`, der Strom hängt mit Pings, Stopp greift ins Leere. | hoch |
| A2 | Herkunft S7 | `B/api.py:70`, `uix_server.py HERKUNFT_WEGE` | Nicht geschützt: `POST sitzungen/<id>/nachricht`, `PATCH/DELETE sitzungen`, `POST antworten/<id>/stopp`, `POST /api/model/load|unload`. Ein `befehl`-Kindprozess mit abgelesenem Token könnte eine „Captain“-Nachricht in die Vorarbeiter-Sitzung einspeisen oder Modelle laden. | hoch |
| A3 | HS-17 Mikrofon | `H/eingabe.js:35`, `ui/wechsel.js:75` | Der Mikrofon-Knopf sucht den Chip `.sx-hub-leiste .sx-chip`; mit `umschalter: menue` gibt es ihn nie → immer „Der Rekorder ist auf dieser Seite nicht da.“ | hoch |
| A4 | Taskleiste | `H/taskleiste.js:118` | Der Reiter `einstellungen:` heißt in der Taskleiste „Neue Sitzung“ mit 💬 (zweite Titel-Logik neben `reiter.name`). | mittel |
| A5 | Seitenleiste | `H/seite.js:114` | „Ja“ beim Löschen ohne `catch`: bei `antwort_laeuft` passiert nichts, die Rückfrage bleibt stehen. | mittel |
| A6 | Fehlertexte | `uix_server.py FRIENDLY_400` | Kein Harness-Code übersetzt: der Nutzer liest „Nicht gesendet: antwort_laeuft“, „zu_viele_antworten“, „titel_leer“, „zweck_fehlt“. | mittel |
| A7 | HS-32 Status | `H/taskleiste.js:143`, `H/shell.js:72` | Statuszellen (GPU-Temperatur, VRAM, RAM) frischen nur bei Modell-/Entscheidungs-Ereignissen auf – während einer langen Antwort oder eines Laufs stehen sie minutenlang fest. | mittel |
| A8 | Aufgaben-Reiter | `H/shell.js:83`, `H/aufgabe.js:171` | Bei `harness.aufgabe`/`harness.vorarbeiter`/`decision.pending` zeichnet sich der offene Aufgaben-Reiter nicht neu – neue Vorschläge erscheinen erst nach eigener Aktion. | mittel |
| A9 | Seitenleiste | `H/seite.js:94-182` | Jedes Ereignis baut die Leiste neu; ein offenes Umbenennen-Feld oder die Lösch-Rückfrage verschwindet mitten im Tippen. | mittel |
| A10 | Last | `B/sitzung.py:116`, `H/shell.js:71` | `liste()` liest jede Sitzungsdatei ganz; die Shell ruft sie bei jedem `harness.sitzung`/`harness.antwort` → Aufwand wächst mit allen Sitzungen je Ereignis. | mittel |
| A11 | HS-80 Modell | `H/modell.js:43-56` | Rezeptwahl zeigt technische IDs (`coder.local_primary`), keine Eignung (VRAM-Bedarf gegen freien Speicher), keine Sortierung; leere Liste → „Keine Rezepte vorhanden.“ ohne Weg. Für den Stick-Kollegen mit 8 GB VRAM der häufigste Stolperstein (Fehlversuch dauert Minuten, dann `hardware_pressure`). | mittel |
| A12 | Vorschau | `H/vorschau.js:117` | Toast „Hier erscheint, woran ich arbeite.“ bei jedem ersten Objekt je Teilung, auch nach Neuladen und für Hintergrund-Reiter; er liegt über dem Senden-Knopf (Bild 05 der Abnahme). | mittel |
| A13 | Lebenszyklus | `H/karte.js:54` | `S._karten` wächst unbegrenzt (jede gezeichnete Karte, auch aus geschlossenen Reitern). | mittel |
| A14 | Doku | `B/api.py:284`, `H/eingabe.js:2`, `H/README.md`, `H/arbeitsplatz.yaml` | Veraltete Sätze „ab Stufe 2“, README „Stufe 5, 1.5.0 … Noch nicht da: Dateien anhängen“; `arbeitsplatz.yaml` kennt Vorschau, Anhängen und Modell-Steuerung nicht. | mittel |
| A15 | Senden | `H/verlauf.js:188` | `senden` prüft `antwortId`, nicht `wartet`: zwei schnelle Sendungen während `POST sitzungen` legen eine zweite Sitzungsdatei an oder enden in `antwort_laeuft`. | mittel |
| A16 | HS-12 Denken | `B/schleife.py:259`, `H/verlauf.js:172` | Denktext wird nicht gespeichert – nach Neuladen nur „Dachte nach · n Zeichen (nicht gespeichert)“; die Spec will die eingeklappte Zeile mit Inhalt. | niedrig |
| A17 | HS-16 Ende | `B/schleife.py:63` | „erledigt“, sobald ein Werkzeug mit Wirkung `ok` lief – ohne den geforderten Prüfschritt. | niedrig |
| A18 | Kopplung | `H/shell.js:137`, `H/taskleiste.js:107,192`, `desk/decisions.py:130` | Sitzungs-ID an drei Stellen per Regex aus dem Prosa-Feld `note`. | niedrig |
| A19 | Doppelungen | `H/karte.js:91`, `lauf.js:22`, `aufgabe.js:175`, `app.js:122`, `einstellungen.js:58`; `startmenue.js:153`, `einstellungen.js:113` | Ansicht-Stub fünfmal, `seg()` zweimal, `^S-[0-9A-F]{8}$` viermal. | niedrig |
| A20 | Dateigrößen | `H/shell.css` 388, `H/verlauf.js` 369, `H/vorschau.css` | `vorschau.css` trägt fremde Regeln, weil `shell.css` an der Grenze ist; der Strom-Leser (komplexester Teil) steckt ungetestet in `verlauf.js`. | niedrig |
| A21 | Texte | `H/eingabe.js:9,22,26`, `H/karte.js:26` | Nutzertexte mit Spec-Nummern und Innenbegriffen („/einstellungen (HS-42)“, „Stufe captain · Regel keine“). | niedrig |
| A22 | Erster Start | `H/verlauf.js:35` | Startsatz erklärt einem neuen Nutzer nichts; `+`, `@`, `/` werden nicht genannt. | niedrig |
| A23 | Tasten | `H/anhang.js:73` | Esc bei offener Dateiauswahl schließt sie **und** stoppt die laufende Antwort. | niedrig |
| A24 | Dateien | `B/dateien.py:51` | Ordner ohne Einstufung gelistet → `local_config/` erscheint leer in der Anhang-Auswahl. | niedrig |
| A25 | localStorage | `H/vorschau.js:27`, `H/app.js:138` | `sedra.harness.vorschau` und `…app.nachweis` werden nie bereinigt. | niedrig |
| A26 | Rennen | `H/shell.js:127` | `freigabenLaden` ohne Dedupe: zwei parallele Dreifach-Abrufe, Blinken doppelt. | niedrig |
| A27 | Kommentare | `uix_server.py:3615`, `B/api.py:33` | „PATCH/DELETE nur für sitzungen/<id>“ stimmt nicht; Docstring nennt `harness.karte/katalog/vorlage` nicht. | niedrig |
| A28 | Verbindung | `H/shell.js`, `ui/bus.js system.state` | Server-Neustart bleibt unsichtbar, bis der Antwortstrom nach ~17 s „Verbindung verloren“ meldet. | niedrig |
| A29 | HS-03 Reiter | `H/reiter.js:16,117` | Nur `S-…`-Reiter werden gemerkt; `aufgaben:`/`einstellungen:` gehen beim Neuladen verloren. | niedrig |
| A30 | HS-13 Stopp | `B/schleife.py:113`, `H/verlauf.js:227` | Stopp wirkt erst beim nächsten Delta; während der Prompt-Verarbeitung (8 GB VRAM: Sekunden bis Minuten) passiert sichtbar nichts. | niedrig |

## 3. Verbesserungsvorschläge über die Befunde hinaus

| Nr | Vorschlag | Warum | Aufwand |
|---|---|---|---|
| V1 | **„Passt das Modell?“ in der Modell-Steuerung**: VRAM-Bedarf aus `/api/models` (Rezept, dynamische Aufteilung) gegen freien Speicher aus `/api/strip`; je Option „≈ 9,8 GB VRAM nötig · 8 GB frei“ mit Markierung; Modellname statt Rezept-ID; geprüfte/gemessene zuerst; Leerfall mit Knopf „Werkstatt öffnen“. | Der Stick-Kollege erkennt vor dem minutenlangen Fehlversuch, was läuft. Deckt A11. | klein |
| V2 | **Erststart-Schritte in der leeren Sitzung**: unter dem Drachen drei Zeilen mit Zustand ✓/○ – Modell laden → Projekt wählen → erste Nachricht; verschwinden mit der ersten Antwort. | Ersetzt verstreute Hinweise; A22. | mittel |
| V3 | **Antwort-Zeitlinie in der Taskleiste**: je laufender Antwort „denkt · 12 s“, „Werkzeug befehl · 40 s“, „wartet auf Freigabe“ aus dem Strom (`z` in verlauf.js). | Man sieht, ob SEDRA hängt oder arbeitet; mit A30 (Stopp angefordert). | klein |
| V4 | **Verlauf mit Werkzeugergebnissen** (`api.py:299`, `VERLAUF_MAX=20`): Kurzfassungen der letzten Werkzeugzeilen in den Modell-Kontext. | Das Modell „vergisst“ heute, was es gelesen hat, und liest erneut (Token, Zeit). | mittel |
| V5 | **Suche** über Titel und Captain-Texte (`GET sitzungen?q=`, Feld in der Seitenleiste; Strg+F im Reiter). | Ab ~30 Sitzungen findet man nichts mehr. | mittel |
| V6 | **Sitzung als Markdown exportieren** (Knopf im Reiter, nur lesend: Verlauf, Werkzeugzeilen, Entscheidungen). | Berichte und Übergaben; Daten liegen als JSONL vor. | klein |
| V7 | **Von der Karte in den Katalog**: „Welche Regel hätte das freigegeben?“ öffnet Einstellungen → Freigabe-Modus mit vorausgefüllter Regel. | Schließt den Kreis Karte ↔ Katalog (Stufe 5). | mittel |
| V8 | **Strom-Leser als Modul mit node-Tests** (`strom/lesen/ereignis` aus `verlauf.js` in `strom.js`). | Der komplexeste Teil der Shell ist heute ungetestet; entlastet A20. | mittel |
| V9 | **Fehlerzeile mit Weg**: endet der Antwort-Thread mit Ausnahme, zeigt die `fehler`-Zeile „Logbuch öffnen“ (App `logbook`, Filter harness). | Heute nur „fehler: TypeName“. | klein |

## 4. Vorschlag für den Bau – drei Pakete (Entscheidung des Captains)

| Paket | Inhalt | Umfang |
|---|---|---|
| **P1 Fehler und Lücken** (empfohlen: ja) | A1–A10, A12, A13, A15, A23–A27; Tests je Befund; Browser-Abnahme `--stufe4..6` und `uix_check` danach | ~1 Tag Cloud, kein Modell nötig |
| **P2 Stick-Sicht / erster Start** (empfohlen: ja) | V1 (passt das Modell), V2 (Erststart-Schritte), V3 + A30 (Zeitlinie, Stopp sichtbar), V9, A11, A21, A22, A14 (Doku Stufe 6) | ~½ Tag; Abnahme ohne Modell möglich, die Zahlen mit Modell prüft der Captain |
| **P3 Pflege und Vertrag** (empfohlen: ja, danach) | A16–A20, A28, A29, V8 (Strom-Leser mit Tests), V6 (Export), A18 (`sitzung_id` als Feld) | ~½ Tag |
| **später / eigene Spec** | V4 (Verlauf mit Werkzeugergebnissen – ändert, was das Modell sieht), V5 (Suche), V7 (Karte → Katalog) | je eigene kleine G2 |

Entscheidungen, die ich brauche:
- **E-A1** Pakete P1–P3 so bauen (Reihenfolge P1 → P2 → P3)? Oder nur P1 jetzt?
- **E-A2** A16 (Denktext speichern, gekürzt 4 000 Zeichen) – speichern oder Spec anpassen („nicht gespeichert“ bleibt)? Vorschlag: speichern.
- **E-A3** A17 (HS-16 „ausgeführt und geprüft“) – `erledigt` erst nach lesendem Nachweis, oder Wortlaut der Spec auf „ausgeführt“? Vorschlag: Spec anpassen (ein erzwungener Lesezugriff kostet Züge).
- **E-A4** V4/V5/V7 als eigene kleine Specs nach P3 – ja?
- **E-A5** Stick-Paket Abschnitt 6: die Worker-Aufgaben setzen den Push von `claude/usb-stick-minimal-3c1b19` voraus – der Branch ist auf GitHub nicht da. Pushst du ihn, oder sollen die Punkte 5–7 (Vorschläge zu `model_profiles.yaml`, `fenster/rekorder.html`, Ladezeit) ohne den Branch als Bericht entstehen?

Regeln wie immer: kein Push, nichts in `local_config/`, keine Modelle, Lieferung als Fork-ZIP; jeder Befund mit Test.

## 5. Nachtrag 20:33 – Maßnahmen aus dem Harness-Vergleich (31.10.)

Der Captain hat `ERGEBNIS_HARNESS_VERGLEICH_2026-10-31.md` nachgereicht (SEDRA gegen Hermes, Pi, Unsloth Studio; gleiche Aufgabe, Qwen3.5-9B).
Kern: SEDRA verliert nicht an Rechenzeit (79 s gegen 144/341/76 s), sondern an **Handlungen und Stolpersteinen** – 4 Klicks vor dem ersten Prompt,
3–8 Freigabekarten für harmlose Dinge im eigenen Testordner, Konfig-Datei + Neustart für einen neuen Arbeitsordner, und die Entlade-Panne
(`evict_idle_models`, Lauf 1: 395 s statt 79 s). Die drei dort genannten Maßnahmen werden hier als **Paket P0** eingearbeitet – vor P1, weil sie
den Stick-Kollegen am meisten kosten.

| Nr | Maßnahme (aus dem Vergleich) | Befund im Code | Vorschlag |
|---|---|---|---|
| M1 | **Weniger Karten im Schreibbereich**: `datei_schreiben`/`datei_aendern` im Schreibbereich des Projekts und Testbefehle (`python -m unittest*`, `python -m pytest*`, `pytest*`) ohne Karte; Knopf **„Erlauben für diese Sitzung“** auf der Karte. | Die Vorlage `config/freigabe_katalog.beispiel.yaml` stuft `python *` und alles Schreiben als `captain`; der Schreibbereich (`projekte.im_schreibbereich`) ist eine harte Grenze in `werkzeuge.py:132`, wird aber im Katalog nicht als Stufe genutzt. Eine Sitzungs-Erlaubnis gibt es nicht (`freigabe.py`: jede Karte einzeln). | (a) Vorlage: neue Regeln `schreiben-schreibbereich` (`frei`, Muster aus dem Schreibbereich des Projekts – zur Laufzeit eingesetzt, Platzhalter `${schreibbereich}`) und `befehl-unittests` (`frei`: `python -m unittest*`, `python -m pytest*`, `pytest*`); Feste Vorbehalte bleiben davor. (b) Karte: Knopf „Für diese Sitzung erlauben“ → `POST karten/<id>/entscheiden {weg: 'sitzung'}`; `freigabe.py` merkt `(sitzung_id, werkzeug, muster)` im Sitzungskopf (`sitzung.sitzung_erlaubt`), gilt bis zum Schließen der Sitzung, erscheint im Audit (`HARNESS_SITZUNG_ERLAUBT`) und in den Einstellungen als Liste mit „Zurücknehmen“. Nicht für `verboten` und nicht für Ziele außerhalb des Schreibbereichs. |
| M2 | **Nicht entladen, solange eine Sitzung arbeitet oder eine Karte wartet; Modell beim ersten Senden laden.** | `job_supervisor._models_in_use` (Z. 374) kennt nur Job-Versuche – Harness-Antworten zählen nicht, daher die Panne. `nachricht` antwortet `kein_modell` (`api.py:289-292`) statt zu laden. | (a) Supervisor bekommt einen Haken `in_use_extra()`; die Harness meldet das Modell jeder Sitzung mit `antwort_laeuft` oder offener Karte (plus 60 s Nachlauf). Test: Eviction mit laufender Antwort → Modell bleibt. (b) `nachricht` ohne Modell: wenn die Sitzung ein Rezept kennt (`s['modell']` oder Vorgabe aus M3) **und** die Katalogstufe für `modell_laden` `frei` ist, lädt der Server selbst und zeigt in der Zeitlinie „lädt Modell … 21 s“; sonst wie heute `kein_modell` mit Knopf „Laden“ direkt in der Fehlerzeile. Laden bleibt ein Gate-Weg, wenn der Katalog `captain` sagt (Regel des Captains: Modelle laden nur nach Ja – die Vorlage lässt `modell_laden` daher auf `captain`; der Stick setzt `frei`). |
| M3 | **„Ordner öffnen“ statt Konfig-Datei + Neustart; Rezept und Projekt als Vorgabe merken; Startbefehl mit den PC-Rezepten.** | Projekte nur aus `local_config/harness_projekte.yaml` (`projekte.py:60`), gelesen beim Start; kein Weg aus der Shell. Rezeptwahl in `modell.js` wird nicht gemerkt. | (a) `POST projekte` `{wurzel, name?, schreibbereich?}` als Gate-Antrag `harness_projekt` (wie `harness_katalog`): Vorschau „Ordner X, Schreibbereich `**`“, Freigabe schreibt **nicht** in `local_config/` des Captains, sondern in `<projekt>/.sedra/harness_projekte.yaml` (Laufzeitdatei, `.bak`), `projekte.laden` liest beide; Neustart entfällt (`harness.projekt`-Ereignis). Knopf „Ordner öffnen“ im Start-Menü und in der leeren Sitzung (V2). (b) Vorgaben `rezept_standard`, `projekt_standard` in der Laufzeitdatei; neue Sitzung übernimmt sie; „Als Vorgabe merken“ in der Modell-Steuerung und der Projektwahl. (c) Startbefehl: `--root` nur Dokumentation/Stick-Skript (`PLAN_USB_STICK` – Start-Skript setzt `--root` auf den Stick-Arbeitsbereich); keine Code-Änderung nötig, Hinweis ins README. |

Grenzen: n = 1 je Harness, 9B-Modell; die Entlade-Panne ist aber im Code nachvollziehbar (M2a), die Klickzahl in den Wegen (M3).

Paket **P0 Vergleichs-Maßnahmen** (M1–M3, Tests je Punkt, Abnahme `--stufe4..6` + neuer Fall „Sitzungs-Erlaubnis“) ≈ 1 Tag; Reihenfolge dann **P0 → P1 → P2 → P3**.

Zusätzliche Entscheidungen:
- **E-A6** M1 so (Vorlage mit Schreibbereich-Regel + Testbefehle `frei`, Sitzungs-Erlaubnis per Knopf)? Vorschlag: ja; `befehl-python` bleibt `captain` für alles andere.
- **E-A7** M2b Auto-Laden nur bei Katalogstufe `frei` für `modell_laden` (Vorlage: `captain` → kein Auto-Laden auf deinem PC, Stick-Katalog: `frei`)? Vorschlag: ja.
- **E-A8** M3a Laufzeitdatei `<projekt>/.sedra/harness_projekte.yaml` neben der Captain-Datei (die bleibt unangetastet)? Vorschlag: ja.
