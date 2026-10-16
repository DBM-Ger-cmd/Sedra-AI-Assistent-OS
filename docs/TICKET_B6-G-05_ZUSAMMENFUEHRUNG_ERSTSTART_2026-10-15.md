# TICKET B6-G-05 – Zusammenführung Entwickler-Archiv Build 19 + Build 22; sauberer Erststart (IMPLEMENTED/TESTED, 15.10.2026)

**Status:** Anfrage Klaus (Chat 18:12, Q2) als Ticketfreigabe; umgesetzt, Linux getestet. **Nicht abgenommen** – der Windows-Erststart ist nicht ausgeführt (keine Windows-Maschine), nur gelesen und auf Logik geprüft. Gate: Klaus (Erststart auf dem PC).
**Ergebnis:** `SEDRA_Build_023_Zusammenfuehrung_2026-10-15.zip`, SHA-256 `11e933ef8722af19400b8e5b7de105555966f513376b4df20b1816c4dd539cb1` (ohne Git-Bundle; die Historie liegt getrennt als `sedra_history_build23.bundle`, SHA-256 `f9b306f2…cc81`, 29 Commits: Archiv bis Build 19 → Build 20 → G-01 → G-03 → G-04 → Build 23). Ersetzt Build 22.
**Doku im Paket:** `docs/BUILD_23_ZUSAMMENFUEHRUNG_ERSTSTART_2026-10-15.md`, `START_HERE.txt`, `docs/entwickler_archiv_build19/`.

## (a) Zusammenführung
Archiv = Build 19 (`2692c37`) + nicht committeter Start-Patch (16 Dateien). Arbeitsstand = Build 20 (identisch mit dem ZIP vom Vormittag, als Commit auf `2692c37` gesetzt) + Tickets G-01/G-03/G-04. Start-Patch dreiwege auf Build 22: 14 Dateien sauber, 2 Doku-Konflikte (README, BETRIEB) mit beiden Inhalten gelöst. Alte Starter entfernt; Oberflächenauswahl im Start.

## (b) Erststart-Befunde (alle geschlossen)
| Nr | Befund | Änderung |
|---|---|---|
| E1 | Sandbox-SDK (`runtime\portable\sandbox`) nicht im Paket → Windows-Erststart unmöglich | SDK optional (`sdk_version: none`), Pinning bleibt, wenn der Ordner da ist; Start gibt Hinweis |
| E2 | `.sh`/`.command` ohne Ausführungsrecht in allen ZIPs → macOS/Linux „Permission denied“ | Rechte im Git und im ZIP; `sh ./start_sedra.sh` als Weg |
| E3 | Fehlende Engine → Abbruch in `Erststart_Konfig.ps1` und `START_SEDRA.bat` | Hinweis statt Abbruch, Oberfläche startet |
| E4 | `START_HERE.txt` veraltet (Build 7) | neu |

## (c) Tests (Linux)
Volle Suite 2.132 Tests, nur der bekannte Umgebungsfehler; `test_offline_bundle` +2; `test_uix_start` grün; `uix_check --shell start` 6/6; frische Kopie mit `sh start_sedra.sh --uebersicht` gestartet (venv, Server, Übersicht). **Nicht:** Windows-Erststart, Ersteinrichtung.ps1 mit echtem Download, echtes Modell.

## (d) Offen
Windows-Erststart durch Klaus (Protokoll `runtime\einrichtung.log` zurück); Abnahmen B6-G-01/03/04/05; P6-Vorlagen; G-02.
