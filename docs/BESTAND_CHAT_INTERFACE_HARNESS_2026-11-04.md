# Bestand: Chat-Interface der Harness (MasterChat im weiten Sinn) – 04.11.2026

Stand: Branch `claude/masterchat-42fc7f` auf `758cce1`, dazu drei Commits dieser Sitzung (`49a35bc`, `09d5d90`, `50576c8`). Der Captain hat den Begriff „MasterChat“ am 04.11. auf das ganze Chat-Interface der Harness ausgeweitet.
Geprüft wurde durch Lesen und Zählen, nicht durch Browser-Läufe. „Test“ heißt unten: eine Testdatei nennt das Modul; ob sie dessen Verhalten prüft oder nur die Datei, ist je Zeile angegeben, wo ich es nachgesehen habe.

## Bestandteile (`runtime/src/guppi_runtime/uix/shells/harness/`)

| Teil | Dateien | Zeilen | Tests (Verhalten mit node) |
|---|---|---|---|
| Verlauf einer Sitzung, Senden, Strom | `verlauf.js`, `strom.js`, `zeilen.js`, `markdown.js` | 365 / 70 / 78 / 185 | `verlauf`: 3 Dateien mit node (u. a. neu `test_harness_masterchat_dialog.py`); `strom`: `test_harness_strom.py`; `markdown`: 1; `zeilen`: nur Namensbezug, kein node |
| Eingabefeld | `eingabe.js`, `gespraechsoptionen.js`, `anhang.js` | 242 / 61 / 104 | `eingabe`, `gespraechsoptionen`: node; `anhang`: eine Datei, kein node |
| Vorlagenwahl und Hinweis | `vorlagenhinweis.js` | 65 | `test_harness_hinweis_klappen.py` (3), neu der Dialog bis zum Server (3) |
| Freigabe-Karte, Sitzungs-Erlaubnisse | `karte.js`, `erlaubnisse.js` | 128 / 51 | `karte`: Namensbezug in vielen Dateien, kein node; `erlaubnisse`: 2 Dateien, kein node |
| Chat-Liste | `seitenleiste.js`, `startliste.js`, `reiter.js` | 143 / 121 / 147 | node in `test_harness_seitenleiste.py` (6), Startliste und Reiter je 1 |
| Taskleiste-Knopf Aufnahme | `schnell.js` | 81 | **kein Test** (Commit `a2e699e` vom 04.11.) |
| Modellwahl | `modell.js` | 228 | Namensbezug, kein node |

Server: `harness/vorlagen.py`, `harness/api.py` (`anlegen`, `OPTIONEN`), `harness/werkzeuge.py` (+ `katalog.py`, `vorbehalte.py`, `freigabe.py`).

## Befunde

1. **Auskunft fehlte im Systemtext** – behoben (`09d5d90`): Abschnitt „Auskunft und Lenkung“ in `masterchat.md`.
2. **Werkzeugnamen** der Vorlage und des Systemtexts gegen die Harness abgesichert – keine Abweichung (`49a35bc`). Die Ladeprüfung ließ „vorgesehene“, nicht vorhandene Namen zu; der Test schließt das für diese Vorlage.
3. **Dialog bis Server** hatte keinen Test – behoben (`50576c8`); Gegenprobe: Feld entfernt → Test rot.
4. **Ohne Verhaltenstest**: `schnell.js` (Aufnahme-Knopf, neu), `anhang.js`, `erlaubnisse.js`, `karte.js`, `zeilen.js`. Vorschlag: je ein node-Test im Stil von `test_harness_hinweis_klappen.py`, zuerst `karte.js` (Freigabe) und `erlaubnisse.js` (Zurücknehmen), weil beide Rechte berühren.
5. **Kein Lauf mit echtem Modell** belegt, dass der MasterChat die Auskunftsanweisung befolgt (Punkt 3 der Sitzung, siehe unten).
6. **Übergabe 03.11., Punkt 4**: Harness-Karte → Fenster → Ja hat keinen eigenen Test (die Harness-Tests laufen mit abgeschalteter Tür). Offen, gehört zum Freigabe-Code (fester Vorbehalt des MasterChats, nicht der Entwicklung).
7. **Dateigröße**: `verlauf.js` hat 365 Zeilen; Grenze der Oberfläche laut Vertrag 400. Neues im Verlauf besser in eigene Dateien.

## Aufgeräumt in `docs/wunsch_umsetzen/`

- Die drei Aufträge `A-2026-11-03-…export…` standen auf „Offen“, sind aber umgesetzt (Commits `26b2fa1`, `078694b`; Tests `test_harness_export_token.py`). Status nachgezogen: „umgesetzt, Abnahme durch den Captain offen“. Abgenommen setzt nur der Captain.
- `03_ergebnisse/` und `04_luecken/` enthalten nur die Beschreibung (README); es gibt zu keinem der Aufträge einen Bericht. Wunsch `W-2026-11-03-chatfenster-layout` und `…startmenue-ausbau` haben keinen Auftrag.
- `docs/ARBEITSWEG_WUNSCH_UMSETZEN.md` und die README dort verweisen aufeinander; Verweise stimmen.
- `docs/CHANGELOG.md` und `LOGBUCH_AGENT_MANAGER.md` nennen den MasterChat; der Eintrag zu den heutigen Änderungen (Auskunft, drei Tests) steht noch aus und folgt mit dem Commit.
