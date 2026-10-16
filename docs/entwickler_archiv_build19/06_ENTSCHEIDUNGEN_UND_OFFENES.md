# 06 – Entscheidungen, Begründungen und Offenes

Dieses Dokument hält fest, was entschieden ist, warum, und was offen bleibt. Entschieden hat im Projekt der **Captain** (Klaus). Wo eine Entscheidung nur als Empfehlung vorliegt, steht das ausdrücklich dabei.

## 1. Entscheidungen seit dem 14.10.2026

| Datum | Entscheidung | Stand |
|---|---|---|
| 14.10. | Systemname SEDRA, technischer Name GUPPI, Maskottchen GUPPI | gilt |
| 15.10. | „Der sichere Weg zuerst“: Inhaltsschutz im Kern vor allen Funktionen | umgesetzt (Build 16) |
| 15.10. | Shell-Creator: drei Empfehlungen (Schema-Zwang am Router, Rahmen aus Vorgabe, Satz an GUPPI) | umgesetzt (Build 17) |
| 15.10. | Die alte GUPPI-XP-Oberfläche bleibt als wählbare Shell, der Einstieg ist START_SEDRA | umgesetzt (Build 18) |
| 15.10. | Das KI GateWay heißt in der Oberfläche KI GateWay; SEDRA erscheint nur im Hintergrund | gilt |
| 15.10. | Das KI GateWay wird als Vorgang nach dem Studio Flow v1.1 gebaut, mit Schutzklassen und Studio-Shell | umgesetzt (Build 19) |
| 15.10. | Die Lieferung der 0.3.0 wird nicht als Paket übernommen, nur ihre Werkzeuge; der Bestandsablauf bleibt MVP 2 | umgesetzt |
| 15.10. | Die Oberfläche des GateWay bekommt den Rand-Rahmen: Orte und Leiste erscheinen beim Anfahren | umgesetzt (Build 19) |

## 2. Der Weg: GateWay auf dem SEDRA-Kern oder eigener MVP

**Empfehlung (Stand 15.10.):** Das GateWay auf dem SEDRA-Kern bauen. Die Gegenüberstellung für die Partner steht im Dokument „KI GateWay auf dem SEDRA-Kern“ (https://claude.ai/artifact/S8UDS5Rjn5r7FxXrzCHywb). Die wichtigsten Punkte:

| Kriterium | Auf dem SEDRA-Kern | Eigener MVP (v0.7.7 Hauptbuild) |
|---|---|---|
| Schutz vor Modellaufrufen | vorhanden, zentral im Router | neu zu bauen |
| Nachweis und Audit | vorhanden (Hashes, nie Text) | neu zu bauen |
| Freigabe mit Bindung | vorhanden (Gate mit Einmal-Token) | neu zu bauen |
| Weitere Anwendungsfälle | ein neues Werkzeug im selben Kern | jeweils ein neuer Stapel |
| Abhängigkeit | an SEDRA gebunden | unabhängig, aber doppelte Pflege |
| Zeit bis MVP | kürzer, Grundlagen stehen | länger |
| Hauptrisiko | der Kern wird ein gemeinsamer Engpass | Sicherheitsfunktionen müssen neu bewiesen werden |

**Ehrliche Einschränkungen:**

- SEDRA ist jung (Builds 1 bis 19). Der Kern ist eine gemeinsame Abhängigkeit: Eine Änderung am Kern wirkt auf alle Anwendungen.
- Die Tests des Lieferpakets (88 Tests) und die Prüfungen aus der V4-Akte müssen in den Kern übernommen werden. Die Akte nennt für das Gateway-Team 363 Tests mit 90 bestanden und 3 fehlgeschlagen (mit Fake-Ollama). Dieser Stand ist nicht im SEDRA-Kern.
- Die Vertragsregeln von SEDRA brauchen Einarbeitung.

## 3. Offene fachliche Entscheidungen (beim Captain)

Diese Punkte sind **fachlich** und liegen nicht beim Entwickler.

| Nr. | Thema | Stand im Code | Was zu entscheiden ist |
|---|---|---|---|
| TC-011 | SK3 und G01: Review bleibt | umgesetzt als Empfehlung: G01, P02, P03, P04, V01 führen zu SK3 und verlangen die Prüfung, auch lokal | beschließen oder anders regeln |
| R01 | Rechtsstreit, laufendes Verfahren | nicht automatisch erkennbar, vom Captain von Hand gesetzt | Benennung und ob ein Scanner es später erkennen soll |
| F01 / F02 | Bankverbindung und Kartendaten als SK2 | Tabelle in `gateway/klassen.py` | Einordnung bestätigen |
| KLA-O1 / KLA-O2 | Rollen und Berechtigungen | keine Rollen; der Captain ist der Review | ob eine zweite Prüfstelle nötig ist |
| KLA-O6 | echter Cloudweg | nur simuliert; Adapter wäre Build S6 hinter der Netzgrenze | Beschluss, ob und wann |
| Löschfrist | Entwürfe spätestens 23.10.2026 | Testwert aus dem synthetischen MVP-Test, Uhrzeit Ende des Tages | Uhrzeit setzen; Produkt-Aufbewahrung festlegen |
| Mapping-Ende | Zuordnung Platzhalter → Original | nur im Prozess, gelöscht nach Abschluss | Bestätigung |

## 4. Technische Offenheiten

Aus `docs/START_HERE_UIX2.md` (Stand Build 19), sortiert nach Gewicht:

- **GateWay-Paket und Cloud-Adapter:** Das Paket `sedra_gateway` (0.3.0) ist nicht eingebaut; Build 19 nimmt die Werkzeuge und das Konzept. Der Cloud-Adapter bleibt Build S6. `sedra_gateway/guard.py` ist zu streichen, sobald der Kern alles übernimmt.
- **Scanner:** Nicht jedes Schlüsselformat ist erkannt (`sk-ant-…` nur als weiche Regel). Gehört in `b6core/privacy.py` mit neuer Herkunftsprüfung.
- **Fensterlage von Minimal:** liegt im Browser; neuer Port je Start verliert sie. Gehört in `uix.yaml` mit Schreibbremse.
- **Haus- und „SEDRA“-Menü** als Vertragsteil für alle Shells.
- **Auftrag-Feld** direkt als Verb.
- **Creator über das Gespräch**, Routinen-Werkzeug, Netz- und Löschen als Verb, Kostengrenze als Zahl.
- **Zwischenspeicher:** `live.py` und `_most_expensive_task()` lesen bei jedem Blick alles neu.
- **Kostenzählung** der Hilfsaufrufe des Inhaltsschutzes (Build 16 noch nicht).
- **GateWay-Korpus-Ablauf (MVP 2):** Der Bestandsablauf der 0.3.0 mit Dateien, Einheiten und Stichprobe; PDF und DOCX als Anhänge.

## 5. Was wir bewusst nicht gemacht haben

- Ein Ausbau des Projekts zu einer Mehrbenutzer-Plattform (keine Rollen, keine Konten).
- Eine Anbindung an einen Cloud-Anbieter. Das ist ein eigener Beschluss.
- Ein Agenten- oder MCP-Anschluss für das GateWay (Option A der Akte: nur dokumentiert).
- Ein Versand. Das GateWay endet beim geprüften Entwurf.

## 6. Wo man nachschlägt

| Frage | Dokument |
|---|---|
| Warum etwas so gebaut ist | `docs/SPEC_*.md` (Spezifikationen) |
| Was wann gebaut wurde | `docs/CHANGELOG.md`, `docs/BUILD_*.md` |
| Was zu tun bleibt | `docs/START_HERE_UIX2.md` |
| Welche Akte-Anforderung wo steckt | `03_KI_GATEWAY_EINBINDUNG.md`, Abschnitt 2 |
