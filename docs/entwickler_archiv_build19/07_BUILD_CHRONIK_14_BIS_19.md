# 07 – Build-Chronik 14 bis 19 (14. bis 15. Oktober 2026)

Kurzfassung der Builds, die den Weg von der Oberfläche zum KI GateWay gegangen sind. Die vollständigen Einträge stehen in `docs/CHANGELOG.md`; die Bau-Berichte je Build in `docs/BUILD_*.md`.

| Build | Thema | Kern-Ergebnis | Abnahme (laut Changelog) |
|---|---|---|---|
| 14 | Start-Shell und allgemeine Abnahme | Einstieg mit Karten je Oberfläche; Werkzeug Module mit Umschalter; eigene Shells entfernbar | Start-Shell und Module geprüft |
| 15 | Erste Lieferung von außen | Zwei Werkzeuge eines anderen Chats durch das Gate. V1 (eigene Objekttypen) und V2 (Vertrauen aus fremder Datei) geschlossen. Das Backend der Lieferung bleibt draußen. | `test_desk_gateway` 17, `test_desk_install` 26 |
| 16 | Der sichere Weg: Inhaltsschutz im Kern | Jeder Modellaufruf durch den Guard; Entscheidungen einmal oder ablehnen; Audit ohne Text; Schärfe aus dem Projektmodus | `test_content_guard` 27/27; Suite 2022 |
| 17 | Der Shell-Creator | Schema-Zwang beim Modell (`models/structured.py`); Shell aus Vorgabe; Rahmen `frame.js`; Satz an GUPPI | `test_model_structured` 10, `test_uix_frame` 16; drei Vorlagen 27/27, 27/27, 26/26 |
| 18 | START_SEDRA | Sauberer Einstieg; GUPPI XP als wählbare Shell; Meldung mit PID bei laufendem Altprozess | `test_uix_start` 8, `test_uix_shell_start` 7; Suite 2050 |
| 19 | Das KI GateWay in SEDRA | Vorgang nach dem Studio Flow; Schutzklassen SK0–SK3 und 13 Merkmale; Matrix; Gate mit Bindung; Entwurf lokal und simuliert in der Cloud; Werkzeuge `gateway` und `schutz`; Shell KI GateWay Studio; Rand-Rahmen | `test_gateway` 21; Studio 29/29; Suite 2072 |

## Die Stationen im Einzelnen

**Build 14 (14.10.).** Die Start-Shell wird der Einstieg, solange `uix.yaml` keine Shell nennt. Sie öffnet keine Objekte und sagt das. Das Werkzeug Module bekommt den Umschalter Werkzeug/Shell beim Anlegen und Vorlegen.

**Build 15 (15.10., Vormittag).** Ein anderer Chat hatte aus einem früheren Projekt ein Modul für SEDRA gebaut, als Test des Einbauwegs. Das Gate hat es nicht sofort akzeptiert. Die Manifestprüfung wies es mit `handles_unknown_type` ab. Daraus wurden zwei Vertragsbefunde:
- **V1:** Ein fremdes Werkzeug konnte keinen eigenen Objekttyp mitbringen. Jetzt erlaubt, wenn es nicht `CORE` ist und nicht aus dem Paket kommt (`own_types`).
- **V2:** Das Vertrauen kam aus der Datei des Fremden. Jetzt gilt: Was durch das Gate kommt, ist COMMUNITY. Schreibrouten braucht ein eigenes Gate (`/api/uix/trust`).

**Build 16 (15.10.).** Der Inhaltsschutz sitzt im Modell-Router. Die Schärfe folgt dem Modus des Projekts; Cloud und Grundschutz sind immer scharf. Ein Guard-Stopp ist kein Anbieterfehler.

**Build 17 (15.10.).** Drei Empfehlungen aus der Recherche zum Shell-Creator wurden in dieser Reihenfolge umgesetzt: Schema-Zwang am Router, Rahmen aus Vorgabe, Satz an GUPPI. Die Abnahme am Rahmen fand mehrere Fehler (u. a. Palette sichtbar, Schublade fokussierbar, falsche Knöpfe, Spalten), die behoben wurden.

**Build 18 (15.10.).** Der Start „in die alte Oberfläche“ war kein Fehler im Paket, sondern ein noch laufender Prozess eines alten Pakets; ein zweiter Start wurde verweigert. Seitdem nennt die Meldung PID und Paketordner. `START_SEDRA` startet die Übersicht; `START_SEDRA cockpit` direkt in eine Shell.

**Build 19 (15.10.).** Das KI GateWay. Der Vorgang folgt dem Studio Flow v1.1 und der Akte V4: Prüfen, Empfehlung, Freigabe mit Bindung, Entwurf, menschliche Prüfung. Kein Versand. Die Studio-Shell hat das GateWay im Mittelpunkt; Orte und Leiste erscheinen nur am Rand.

## Zahlen am Ende von Build 19

- Dateien im Quellcode (ohne `.git`): 1137 (Archiv-Ordner `quellcode/`).
- Tests: 2072 in der Suite, bekannter Umgebungsfehler `library_not_built`.
- Build-19-Commit `2692c37`: 40 Dateien, 2302 Zeilen ergänzt, 33 entfernt (`git show --stat 2692c37`).
- Commit `2692c37` ist der Stand von Build 19; die Arbeitskopie trägt die Build-Nummer 19 in `BUILD.txt`.
