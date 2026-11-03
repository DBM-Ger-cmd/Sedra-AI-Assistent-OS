# Übergabe an den lokalen Vorarbeiter (03.11.2026, aus der Cloud-Sitzung)

Für: die lokale Sitzung am PC des Captains. Stand: `main` nach dem Merge dieser Übergabe (PR #6).
Was hier steht, ist in der Cloud gebaut und **im Container (Linux, ohne GPU, ohne Browser) geprüft**, am PC aber noch nicht.

## 1. Was heute auf `main` gekommen ist

| Thema | Wo nachlesen | Stand |
|---|---|---|
| Release 1.22.0 (Tag `v1.22.0` auf `4e051f0`, Manifest für den Updater, `release_manifest.py`) | `BETRIEB.md` „Release“, `BESTANDSAUFNAHME_v1.22.0_2026-11-03.md` | Tag gesetzt, geprüft |
| G4: Läufe und Befehle nur nach Sicht auf geänderten Code (`CODE_STAND.bat`) | `SPEC_APPS_v1_G4_MODELLCODE_G2.md` | gebaut, **Abnahme am PC offen** |
| Tests starten keine Programme des PCs mehr über `gpu_preflight`; relative Ordner unter macOS/Linux | `CHANGELOG.md` „Nach 1.22.0“ | gebaut |
| G2 für O3+ und G9–G11, Entscheidungen E1–E14 | `SPEC_APPS_v1_O3PLUS_G9_G2.md` §9, §9a | entschieden |
| G11: Vollständigkeitstest der Freigabe-Wege | dort §13.1 | gebaut |
| E9 Variante C: Hardware-Server zeigt wieder Daten | dort §13.2 | gebaut, im Browser nicht geprüft |
| **G9/G10: Freigaben der Klasse H nur außerhalb des Browsers** | dort §13.3 | gebaut, **am PC nicht geprüft** |

Ganze Bahn im Container zuletzt: **3.810 Tests, 0 rot**, 121 übersprungen.

## 2. Was sich für den Captain im Alltag ändert (G9)

- Gibt er in der Oberfläche eine Freigabe der **Klasse H**, passiert nicht sofort etwas. Klasse H heißt: Rechte für später, Programme starten, Regeln oder Kern ändern, Code in den Betrieb bringen, Daten nach außen. Beispiele: Aufgabe anlegen, Karte zu `befehl`/`lauf_starten`, Schalter, Routing, Modul einbauen, Update, Cloud-Einstellungen, MasterChat-Sitzung mit Vorlage-Erlaubnissen.
  Stattdessen erscheint unter Windows ein **Fenster von SEDRA** mit Text aus dem Kern („Ja“/„Nein“). Die Seite zeigt: „wartet auf Bestätigung … `FREIGABE.bat freigeben B-…`“.
- Ohne Fenster oder wenn es nicht erscheint: im SEDRA-Ordner `FREIGABE.bat liste`, dann `FREIGABE.bat freigeben B-…`. SEDRA muss dabei laufen.
- Klasse N (Dateien im Projekt außerhalb von Kern und Oberfläche, Modelle laden, lokale GateWay-Vorgänge, Ablehnen) geht weiter direkt aus der Seite.
- Der Vorarbeiter beantwortet nur noch Klasse N. Karten der Klasse H gehen immer an den Captain.
- Notbremse: `local_config/switches.yaml` → `freigabe_ausserhalb: {enabled: false}`, dann Neustart. Danach geht Klasse H wieder aus der Seite, steht aber im Audit (`FREIGABE_KLASSE_H_AUS_DER_SEITE`).

## 3. Abnahme am PC – bitte in dieser Reihenfolge

1. **Testbahn am PC:** `runtime\run_tests.bat` (oder die Gruppen `harness`, `desk`, `uix`). Besonders: `test_tuning`, `test_freigabe_tuer`, `test_hardware_dashboard_server`. Erwartet: grün. Rot → Ausgabe an die Cloud-Sitzung.
2. **Fenster (G9):** SEDRA mit `START_SEDRA.bat` starten, in der Harness eine Aufgabe anlegen. Erwartet: Das Fenster „SEDRA – Freigabe bestätigen“ erscheint **im Vordergrund**, und die Seite zeigt den Wartesatz.
   - Ja → die Aufgabe ist angelegt.
   - Noch einmal mit Nein → nichts angelegt.
   - Erscheint das Fenster nicht im Vordergrund oder gar nicht, festhalten und zurückmelden.
3. **Konsole (G9):** Eine Freigabe der Klasse H auslösen (z. B. Schalter-Antrag im Posteingang) und das Fenster offen lassen. In einer Eingabeaufforderung im SEDRA-Ordner `FREIGABE.bat liste`, dann `FREIGABE.bat freigeben B-…`. Erwartet: ausgeführt. Danach im Fenster „Ja“ → Fehler „unbekannt“, kein zweites Mal.
4. **Harness-Karte (G9):** MasterChat lässt einen `befehl` außerhalb der freien Muster laufen → Karte → „Erlauben“ → Fenster → Ja. Erwartet: Der Befehl läuft und die Antwort des Modells geht weiter. **Dieser Weg hat noch keinen eigenen Test** (die Harness-Tests laufen mit abgeschalteter Tür).
5. **G4** (aus `SPEC_APPS_v1_G4_MODELLCODE_G2.md`): Test schreiben lassen, `run_tests` → Karte mit dem Code; freigeben → Lauf; zweiter Lauf ohne Karte; nach `git pull` Karte oder `CODE_STAND.bat sedra-entwicklung --uebernehmen`.
6. **Hardware-Server:** `guppi hardware-dashboard --open` (bzw. `runtime/run_hardware_manager.sh`) → Werte erscheinen.
7. **Update-Probe (B10):** Werkzeug „System“ → „Nach Updates suchen“. Erwartet: „kein Update“ (installiert 1.22.0).

Ergebnisse bitte ins Logbuch (`LOGBUCH_AGENT_MANAGER.md`), Abweichungen mit Text der Fehlermeldung.

## 4. Offen (nicht gebaut) – Reihenfolge laut Spec §11

1. G9-Rest: eigene Anzeige des Wartezustands an Karte und Posteingang (heute als Fehlermeldung); Test für die Harness-Karte hinter der Tür; G10-03 (`guppi approve` und die Konsole des Agent Manager schreiben `FREIGABE_ERTEILT` mit Kanal `konsole`); `FREIGABE.bat` und `desk/freigabe_konsole.py` in die Stick-Liste.
2. O3 und G1: harte und weiche Muster der Oberfläche, weich vor Katalog (E1), Feld `oberflaeche` in Aufgaben; `test_freigabe_*.py` hart (E14).
3. G2, G3, G7: Abnahme vor Wirkung (Sammelkarte, Vorschau), Hinweise im Diff, Rückweg.
4. G6: Startbericht.
5. Aus der Bestandsaufnahme: B9 (gemergte Branches löschen), B10 (Update-Probe), B11 (offene Dateien in Tests).

## 5. Was der Vorarbeiter **nicht** tun soll

- Keine Dateien unter `runtime/src/guppi_runtime/desk/{freigabeklasse,bestaetigung,systemdialog,freigabe_konsole,decisions}.py`, `harness/{vorbehalte,freigabe,…}.py`, `hardware_manager/dashboard.html` ändern: Das sind harte Vorbehalte, Änderungen nur über Claude mit Freigabe des Captains.
- Den Schalter `freigabe_ausserhalb` nicht abschalten, um Tests oder Arbeit zu beschleunigen.
- Tests nicht abschwächen, damit sie grün werden. Gilt besonders für `test_freigabe_*.py` und `host_isolation.py`.
