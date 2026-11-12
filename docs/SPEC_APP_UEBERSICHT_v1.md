# SPEC App „Übersicht“ (A3, Cockpit als App) – 12.11.2026

Teil der Inventur `docs/INVENTUR_SHELLS_ONE_SEDRA_2026-11-05.md` (Cockpit, Zeile „Baum“). Gebaut nach dem Muster der App Team (`docs/SPEC_APP_TEAM_v1.md`). Die alte Shell `cockpit` bleibt unverändert.

## Was gebaut ist

| ID | Anforderung | Stand |
|---|---|---|
| UE-01 | Ein Objekttyp `uebersicht` (Ort `uebersicht`, Wörter „übersicht“, „uebersicht“, „baum“, „gesamtlage“), ein Platzhalter-Werkzeug; die Shell zeichnet die App über `app.flaeche` | gebaut |
| UE-10 | Der Baum zeigt alle Apps nach den Gruppen des Start-Menüs (dieselbe Liste `S._start.liste`, dieselben Namen); eine Zeile öffnet die App über `app.oeffnen` | gebaut |
| UE-11 | Zustand je Zeile aus vorhandenen Routen: Aufgaben (`/api/missions`: offen, wartet), Modelle (`/api/models`: geladen oder keins) | gebaut |
| UE-12 | Eine zugeklappte Gruppe sagt „⚠ n wartet“; was wartet, verschwindet nicht | gebaut |
| UE-20 | Gruppen klappen; gemerkt werden nur Gruppennamen (`sedra.harness.uebersicht.baum`), nie ein Inhalt | gebaut |
| UE-21 | Tastatur wie ein Baum: Pfeile, Pos1/Ende, → öffnet, ← schließt oder springt zum Kopf, Enter/Leertaste | gebaut |
| UE-30 | Start-Menü: „Übersicht“ in der Gruppe Arbeit | gebaut |
| UE-50 | Die alte Shell `cockpit` ist unberührt | Test |

## Nicht gebaut

- Zustand für alle anderen Orte (nur Aufgaben und Modelle haben einen).
- Strg+K-Befehlspalette (X4) und der Hinweistext dazu, Dock (zwei Werkzeuge nebeneinander), Ziehen.
- Nicht im Browser mit echten Daten geprüft; der Test nutzt die leere Entwicklungsumgebung.
