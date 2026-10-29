# Baubericht Harness-Shell Stufe 3 – Teil ohne Modell (29.10.2026)

Spec: `SPEC_HARNESS_SHELL_v1_G2_STUFE3.md` (G2) und `SPEC_HARNESS_SHELL_v1_G3_STUFE3.md` (G3, N1 bis N12, P-1 bis P-15), Entscheidungen des Captains
29.10.2026 („Ja, so“; P-11 bis P-14 auf Ansage; P-16 für `uix/ui/bus.js` am selben Tag). Gebaut von Claude auf `harness/stufe-3` ab `spec/agenten-orchestrierung`
(`dcb3d43`), 13 Commits, **nichts gepusht, nichts nach `spec` gemerged, kein Modell geladen, nichts in `local_config/` geändert**.

**Stand: Stufe 3 ist ohne Modell gebaut und geprüft. Der SEDRA-Bau N2, der Pilot N8 und die Abnahme mit echtem Modell stehen aus (auf Ansage des Captains,
„Modelltest später“).** Die Übernahme (G4) ist damit noch nicht entscheidbar.

## Ergebnis

| Prüfung | Ergebnis |
|---|---|
| Gruppe `harness` | 223 Tests, 0 rot, 1 übersprungen (der Browser-Durchlauf, nur mit `SEDRA_BROWSER=1`); Stand vor Stufe 3: 122 |
| `scheduler desk orchestra uix harness` (nach N11) | 1297 Tests, **1 rot**: `test_uix_stufe6.ImBrowser.test_mini_hub_ziehen_klappen_merken_wechseln` (Cockpit-Browsertest, allein grün, unter Last rot – wie `test_k5`); Browser-Bahn (5 Dateien) ausgelassen |
| `uix_check --shell harness` (1024×700, 1400×860) | 18 von 18 ok, 0 Konsolenfehler, Überhang 0 px |
| Browser-Durchlauf mit Modell-Attrappe (`SEDRA_BROWSER=1 … test_uix_harness_browser`) | beide Größen grün, mehrfach wiederholt: A Karte an den Vorarbeiter, B Aufgabe mit Rücknahme, C Lauf mit Fortschritt, Ende, Markierung |
| Durchgang A und B von Hand im Browser-Fenster (Attrappe) | durchgeführt, sieben Befunde behoben (unten) |
| Abnahme-Skript Teil 3 (`harness_abnahme.py --stufe3`) gegen die Attrappe | S3-A bis S3-D grün (Skriptlogik geprüft, **nicht** das Modell) |
| Abnahme mit echtem Modell (P-14), Pilot (P-12), Bau N2 (P-11), Review mit Gemma (P-13) | **nicht gestartet** |

## Aufgaben

| Nr | Fertig | Belege (Tests) |
|---|---|---|
| N1 Vorlagen | `harness/vorlagen.py`, Vorlagen `vorarbeiter`, `bauagent`, `pruefer`, Sitzung mit Vorlage (Whitelist, Systemprompt, Hash im Kopf, `max_zuege`, `frist_min`, `bremse_pro_stunde`), `GET /vorlagen` | `test_harness_vorlagen` (10) |
| N2 Aufgaben-Deckung (SEDRA) | **offen** – als Referenz von Claude liegt `harness/aufgabe_deckung.py` (`deckt`, `zustand`) im Paket; Bau-Spec, versteckte Prüfungen, Stempel und `devvm_build` folgen auf Ansage (P-7/P-11) | – |
| N3 Aufgaben-Freigabe | `harness/aufgabe.py` (Pflichtgrenzen, weite Muster, S9, Zähler, Ablauf, Rücknahme), Einstufung mit Aufgabe in `freigabe.Kiste`, weicher Vorbehalt, neue harte Pfade (S8), `katalog.WERKZEUGE` erweitert (`einstufen` unberührt) | `test_harness_aufgabe` (19), `test_uix_harness_aufgabe` (5) |
| N4 Vorarbeiter-Freigabe | `harness/vorarbeiter.py`, Karten mit `an`/`art`/`vorschau_hash`, Werkzeuge `freigaben_offen`, `freigabe_entscheiden`, `aufgabe_vorschlagen`, `aufgabe_beenden`, Frist 15 min, Bremse 30/h, Rücknahme einer Entscheidung, Posteingang `harness_aufgabe`, Katalog-Vorlage um 4 Regeln (D-G6) | `test_harness_vorarbeiter` (7), `test_uix_harness_vorarbeiter` (12) |
| N5 Herkunft | `harness/herkunft.py` (Register der Harness-Prozesse, Gegenstelle → PID über `GetExtendedTcpTable`, Vorfahrenkette mit Startzeit), 403 `herkunft_abgelehnt` für Karten, Aufgaben, Ernennung, Läufe-Stopp, Posteingang | `test_harness_herkunft` (12, darunter echte Kind- und Enkelprozesse) |
| N6 Lauf-Typen | `config/harness_laeufe.yaml` (5 Typen), `harness/lauf.py` Teil 1 (`argv_bauen`) | `test_harness_lauf_typen` (15) |
| N7 Läufe | `harness/lauf.py` Teil 2, `lauf_huelle.py` (losgelöst, `stopp.txt`, Zeitlimit, `ende.json`), Werkzeuge `lauf_starten/stoppen/status`, `modell_laden/entladen`, „Modell belegt“, Rücknahme stoppt Läufe | `test_harness_lauf` (11), `test_uix_harness_lauf` (9) |
| N8 Lauf-Fortschritt (SEDRA-Pilot) | **offen**; bis dahin ein kleiner Ersatz `fortschritt_aus` in `lauf.py`, der das SEDRA-Modul automatisch bevorzugt, sobald es existiert | `FortschrittTests` |
| N9 Wege, Ereignisse, Audit | alle neuen Wege, `decision.answered` mit Kind `harness_aufgabe`, `HARNESS_KARTE_FRIST`, Tabellentest | `test_uix_harness_wege` (4) |
| N10 Oberfläche Freigaben | `aufgabe.js`, `karte.js`, Schild, Seitenleiste (⚑, Ernennen), Vorlagenwahl; Shell 1.2.0 | `uix_check`, Browser-Durchlauf A/B |
| N11 Läufe und Benachrichtigung | `lauf.js`, Taskleiste mit Laufknöpfen, einmaliges Blinken, Markierung bis zum Klick (IDs in `sedra.harness.gesehen`), „Freigaben n · beim Vorarbeiter m“, `bus.js` (P-16); Shell 1.3.0 | Browser-Durchlauf C |
| N12 Abnahme, Bericht | Teil ohne Modell erledigt (dieser Bericht, Gruppe, `harness_abnahme.py --stufe3` fertig und gegen die Attrappe geprüft); Abnahme mit Modell offen | – |

Szenarien S3-A bis S3-E aus G3: S3-A und S3-B in `test_uix_harness_vorarbeiter`, S3-C in `test_uix_harness_aufgabe` und `…_lauf`, S3-D in `test_uix_harness_lauf` und dem Browser-Durchlauf,
S3-E (Skript fragt die Karte selbst ab) in `test_harness_herkunft` mit echtem Unterprozess. S3-F ist der Pilot N8 und steht aus.

Umfang gegenüber `spec`: 56 Dateien, +5211/−264. Paket `harness/` +1937, Oberfläche (`uix/`) +586, `desk/decisions.py` und `uix_server.py` +19, Konfiguration +167, Tests +2049.

## Befunde aus dem Durchgang A und B (alle behoben, `950797b`)

1. Die Karte aus dem Verlauf kannte den Empfänger nicht (der Sitzungseintrag trug `an`, `art`, `vorschau_hash`, `warnung` nicht): nach dem Neuladen fehlte „Beim Vorarbeiter“. Jetzt im Eintrag, und die Karte holt den Stand vom Server.
2. Der Hinweis „Beim Vorarbeiter“ blieb nach der Entscheidung stehen.
3. Das Titelfeld des Aufgaben-Formulars war riesig (falsche Flex-Regel).
4. In den Reitern Aufgaben, Lauf und Diff war das Eingabefeld überflüssig: ausgeblendet.
5. Das Schild war unter 1200 px versteckt; es bleibt sichtbar und kürzt sich.
6. Der Rest der Aufgabe im Schild war veraltet (kein Ereignis beim Zählen): nach jeder fertigen Antwort neu geladen.
7. Rennen Laden gegen Senden: eine sofort gesendete Nachricht konnte von der späten Ladung des Verlaufs weggeräumt werden (leere Ansicht).
Dazu in N11: Die Ereignisse `harness.lauf`, `harness.aufgabe`, `harness.vorarbeiter`, `harness.karte` erreichten den Browser nicht, weil `uix/ui/bus.js` sie nicht kannte – **Berechtigung P-16 (Captain: „Ja, P-16“)**.

## Abweichungen und Entscheidungen beim Bau (bitte prüfen)

1. **`modell_laden`/`modell_entladen` sind Werkzeuge** (Ziel = Rezept-ID), keine Lauf-Typen wie in G2 §6.1 steht; so passen sie zum weichen Vorbehalt und zu `einstufen`. Die Vorlage `vorarbeiter` nennt sie (für den Modellwechsel zum Prüfer, WQ-2).
2. **Läufe mit Modell:** Der Lauf-Typ trägt `modell` (Rezept oder Rolle); eine Aufgabe muss es in `modelle` nennen. `devvm_build` nennt `coder.local_primary` (Rezept des Profils `standard`), die Pilot-Aufgabe in G3 nennt noch `coder.llama_qwen35` – **vor N8 anpassen**.
3. **`spec_check` und `devvm_build` mit `../workspace/GUPPI_OS` aus `runtime` heraus wurden nie echt gestartet**; der Pfad im argv ist nicht erprobt.
4. **Origin-Prüfung nicht verschärft** (ein Skript kann den Header setzen; die Prozess-Prüfung ist die Sperre). Sie schützt nicht gegen Prozesse außerhalb der Harness (Terminal des Captains); scheitert die Auflösung, gilt nur Token und Origin mit Audit-Warnung (D-G5).
5. **Die Herkunftsprüfung ist neu und nur unter Windows ausgebaut**; auf anderen Systemen ist die Auflösung der Gegenstelle leer (nur Token und Origin).
6. **„Weit“** heißt: führendes `*` oder weniger als 5 Zeichen (Dateien) bzw. 10 Zeichen (Befehle) ohne Platzhalter. Diese Schwellen sind meine Festlegung.
7. **Ein laufender `befehl` wird bei der Rücknahme einer Aufgabe nicht abgebrochen** (G2 §4.4); Läufe werden gestoppt, `befehl` bleibt bei seinem eigenen Abbruch-Signal.
8. **Abnahme S3-B angepasst:** Die Sitzung des Vorarbeiters nimmt, solange eine eigene Werkzeug-Karte offen ist, keine Nachricht an (Stufe-2-Verhalten `karte_offen`); „er entscheidet seine eigene Karte nicht“ lässt sich deshalb mit dem Modell nicht durch Zureden prüfen, nur in den Tests (`selbstfreigabe`). Das Skript prüft stattdessen, dass eine Karte der Stufe `captain` beim Captain bleibt.
9. **Der Browser-Durchlauf läuft nur mit `SEDRA_BROWSER=1`**, weil `run_tests.py` nicht Teil der Berechtigung war (P-6 nur „falls das Muster nicht reicht“); ein Eintrag in `SLOW_FILES` würde ihn in die Browser-Bahn holen.
10. **Ein unerklärter Einzelfehler** von `test_harness_lauf…test_abbruch_durch_aufgabe_hat_einen_eigenen_status` unter Last; danach mehrfach grün, Ursache nicht geklärt.
11. **Die Gruppe `harness` braucht jetzt rund 50 Sekunden** (vorher 3), wegen der Tests mit echten Prozessen (Läufe, Herkunft).

## Offen

- **Captain:** Start von N2 (P-11), danach Pilot N8 (P-12) und Review mit Gemma-4-12B (P-13), Abnahme mit Qwen3.6 (P-14, dafür in `local_config/freigabe_katalog.yaml` die Regel `abnahme-s3`, siehe Kopf von `harness_abnahme.py`), Entscheidung über die Übernahme (G4), Zusammenführen von `harness/stufe-3` nach `spec/agenten-orchestrierung`. Nichts davon geschieht ohne dich.
- **Claude, ohne Modell:** Bau-Spec, Referenz und versteckte Prüfungen für N2 (≤ 17) und N8 (≤ 10) samt `spec_check --vm`-Stempel (P-7), danach läuft der Bau auf Ansage.
- `test_uix_stufe6` (Cockpit, unter Last) und das Abbruch-Wegfallen von `befehl` bei Rücknahme.

## Quote (L4)

Bisher **0 Zeilen von SEDRA**: N2 und N8 sind die einzigen SEDRA-Bauten der Stufe (zusammen rund 160 Zeilen laut G3); alles andere ist Harness-Code, Integration und Oberfläche (Claude, ENTWICKLUNG.md L4).
Gezählt wird nach Bau und Übernahme von N2/N8.
