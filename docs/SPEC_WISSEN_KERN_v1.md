# SPEC Wissen im Kern v1 – G1 Anforderungen (05.11.2026)

Stand: `main` `d51083a`. Gate **G1** (Anforderungen). Design (G2) und Bau-Aufgaben (G3) kommen erst nach der Freigabe durch den Captain.
Grundlage: `docs/ANALYSE_WISSEN_IM_KERN_2026-11-05.md`, `docs/INVENTUR_SHELLS_ONE_SEDRA_2026-11-05.md`, Spec 7 (`SPEC7_Wissen_und_RAG_Design_S7.2.md`,
`SPEC7_S7.6_RETRIEVAL_QUALITAET.md`), `SPEC_SHELL_WISSEN_v1`.

Auftrag des Captains vom 05.11.2026: Das Wissen soll in den Kern, „weil der Chat ja davon profitiert und darauf zugreifen soll“. Die Dokumentenverwaltung
„wird ein großer Teil“ und soll gleich ausgebaut und einfacher werden, „damit Sedra Dokumente in großen Mengen auswerten kann“. Die Wissensbasis ist
danach als App „nur noch dargestellt“.

## 1. Beschlüsse vom 05.11.2026

| Nr | Beschluss |
|---|---|
| E1 | Wissen ist **Kern** und **Grundfunktion** in jedem Profil. Der Chat von One Sedra greift darauf zu. |
| E2 | Das Gedächtnis der Harness wird eine Quelle im Wissensspeicher, mit **einer Freigabe je Projekt**. Andere Wege bleiben offen (siehe WK-41). |
| E3 | „Wissen zuerst“ ist ein **Schalter**. Er ist an, sobald das Wissen an ist. |
| E4 | Die App Wissen ist **nur Darstellung**. Die ganze Logik liegt im Kern. |
| E5 | Die Altspeicher `knowledge.py` (KnowledgeStore) und `arbeitsumfeld_wissen.py` **werden entfernt**, nachdem geprüft ist, dass niemand sie mehr braucht. |
| E6 | Die **Dokumentenverwaltung wird ausgebaut und vereinfacht** und soll große Mengen tragen. |

## 2. Befund

| Nr | Befund | Beleg |
|---|---|---|
| B1 | Der Wissensspeicher ist im Backend schon Kern: Quellen mit Freigabe, Zerlegen, CPU-Einbetten, hybride Suche, Rechtefilter, Zitatprüfung, Vorschläge, Nachmessung. | `wissen/*.py` (≈ 3 500 Zeilen) |
| B2 | One Sedra kommt nicht an das Wissen. Der Chat der Harness hat kein Werkzeug für den Speicher und keins für das GateWay. Den Wissensblock gibt es nur im alten Gesprächsweg. | `harness/werkzeuge.py`, `uix_server.py` ≈ 2196 |
| B3 | Neben dem Speicher gibt es drei eigene Suchen (Gedächtnis, KnowledgeStore, GateWay-Wissen). Den Rechtefilter hat nur der Speicher. | Analyse §2 |
| B4 | **Die Dokumentenverwaltung ist schmal.** Gelesen werden nur `.md` und `.txt`, höchstens 2 MB je Datei, Quellen nur unter `repo` oder `projekt`. Jede Quelle braucht einen eigenen Antrag. Wie weit eine Quelle ist (aufgenommen, eingebettet, Fehler je Datei), sieht man kaum. | `wissen/adapter.py` `DATEIARTEN`, `config/wissen.yaml` `datei_max_bytes` |
| B5 | Word (`.docx`) kann SEDRA schon lesen, ohne Zusatzpaket, aber nur im GateWay. | `gateway/dokumente.py` |
| B6 | Der Takt nimmt alle 600 s höchstens 120 s Einbetten auf der CPU. Bei tausenden Abschnitten dauert die Erstaufnahme Stunden. Gemessen ist das nicht. | `config/wissen.yaml` `takt` |
| B7 | Es gibt keinen Weg, **viele Dokumente auf einmal auszuwerten** (gleiche Frage an jedes Dokument, Ergebnis als Tabelle). Die Suche liefert nur die besten 5 Treffer. | `suche: k: 5`, `kontext: treffer: 5` |
| B8 | Der Schalter `wissen` steht in der Paket-Vorgabe auf `false`. | `config/wissen.yaml` |

## 3. Ziel

Ein Kerndienst **Wissen**. Alle fragen ihn auf demselben Weg und mit demselben Rechtefilter: Chat, Agenten, GateWay und Apps.
Dokumente kommen mit wenig Klicks hinein, auch hunderte bis tausende. Man sieht jederzeit, wie weit die Aufnahme ist.
SEDRA kann einen ganzen Bestand auswerten, nicht nur die fünf besten Treffer.

**Nicht Ziel:**
- Die geprüften reinen Teile neu bauen (Zerlegen, Fusion, Vektor, Schema, Einbett-Server).
- Ein fremdes Dokumentensystem anbinden (SharePoint, Paperless und Ähnliches; das ist später Sache von R7).
- OCR für gescannte Bilder in v1.

## 4. Anforderungen

### 4.1 Kerndienst (K1)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| WK-01 | Es gibt **eine** Schnittstelle des Kerns: `fragen(frage, leser, route, filter) → {treffer, fundstellen, art}`. `art` ist `hybrid`, `volltext` oder `aus`. Agentenlauf (`wissen/lauf.py`), alter Gesprächsweg (`desk_basis.kontext`) und der Chat von One Sedra gehen nur darüber. | Einheitstest; Suche im Code: keine zweite Aufrufstelle der Suche |
| WK-02 | Der Rechtefilter (Stufe, Projekt, Personenbezug → kein Cloud-Weg) gilt für jeden Aufrufer **vor** dem Ranking, wie heute (WIS-05, WIS-11). Die Route kommt vom Server, nie vom Modell. | Test je Aufrufer |
| WK-03 | **Wissen ist standardmäßig an.** Ohne Einbett-Modell läuft die Volltextsuche. Fehlt das Modell, steht das in der App und im Info-Hub, nie still. | Test frische Installation |
| WK-04 | Wissen ist **Grundfunktion**. Es lässt sich in keinem Profil ausblenden; Desktop Builder und Profilprüfung lehnen das ab. | Test wie bei den übrigen Grundfunktionen |
| WK-05 | Der Kerndienst bleibt ohne GPU nutzbar. Einbetten nur auf der CPU (WIS-04); die GPU-Stufe S7.4b bleibt außerhalb dieser Spec. | Test: keine Lease, kein Port 8089 |
| WK-06 | Audit wie heute: `component='wissen'`, nie Text aus Fragen oder Quellen. | Test |

### 4.2 Chat in One Sedra (K2)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| WK-10 | Werkzeug **`wissen_suchen`** (frei, nur lesen): Frage und wahlweise Filter (Quelle, Art, Projekt, Zeitraum). Antwort: Treffer mit Kennung `[W…]`, Stelle und Auszug. Projekt und Stufe kommen aus der Sitzung. | Einheitstest; `test_freigabe_vollstaendig` |
| WK-11 | Werkzeug **`wissen_beantragen`**: schlägt eine Quelle vor (Ordner oder Datei). Es entsteht ein Antrag im Posteingang, aufgenommen wird erst nach „Freigeben“. | Test: ohne Freigabe keine Aufnahme |
| WK-12 | Werkzeuge **`gateway_status`, `gateway_vorgang`, `gateway_regel`** auch in One Sedra (nur lesen, aus `chat_tools.py`). | Test |
| WK-13 | **Schalter „Wissen zuerst“** je Sitzung, Vorgabe aus dem Profil. Er ist an, sobald das Wissen an ist. Ist er an, geht vor dem ersten Modellaufruf eines Zugs der Wissensblock als markierte Daten (`trust: untrusted`) **hinten** an die Frage. Der Anfang des Systemprompts bleibt gleich (Cache). | Test: Systemprompt-Anfang je Zug gleich; Cache-Zahl im echten Sedra |
| WK-14 | **Zitatprüfung** wie bei den Agenten (WIS-07): Eine Kennung `[W…]`, die nicht unter den Treffern war, wird markiert. Unter der Antwort steht „Aus dem Wissen: n Fundstellen“; ein Klick öffnet die Fundstelle in der App Wissen. | Test |
| WK-15 | Ohne Modell beantwortet One Sedra eine Wissensfrage mit der Trefferliste (wie `desk_basis.ohne_modell`), statt „Kein Modell“ zu sagen. | Test |
| WK-16 | Neue Wege der Harness stehen in `desk/freigabeklasse.py` (`HARNESS_WEGE`, `HARNESS_UNTERWEGE`, `ROUTEN_HARNESS`) und im Regex `WEG`/`GESCHUETZT` in `harness/api.py`. | `test_freigabe_vollstaendig` |

### 4.3 Dokumentenverwaltung (Ausbau, E6)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| WK-20 | **Dateiarten:** `.md`, `.txt`, `.docx` (Leser aus `gateway/dokumente.py` in den Kern holen), `.csv` (Zeile als „Spalte: Wert“) und `.pdf`, sofern Text darin ist. PDF und weitere Arten (Excel, PowerPoint) gehen über die Hilfswerkzeuge: MarkItDown, sonst `pypdf` (F1). Ist keins installiert, steht die Datei als „übersprungen: Hilfswerkzeug fehlt“ mit dem Installationsbefehl in der Liste. Was sich nicht lesen lässt, steht je Datei mit Grund in der Liste, nie still. | Test je Art, Testdateien im Repo |
| WK-21 | **Ordner als Sammlung:** Ein Antrag deckt einen Ordner mit Unterordnern und Mustern ab, auch außerhalb von `repo`/`projekt`, aber nur unter freigegebenen Wurzeln (Liste in `local_config`, F2). Neue Dateien in einer freigegebenen Sammlung kommen ohne neuen Antrag hinein. Die Liste ist eine eigene kleine Datei, damit die Sandbox sie ebenfalls lesen kann (nur lesend einhängen). | Test |
| WK-22 | **Stand je Sammlung und Datei:** Anzahl Dateien, aufgenommen, eingebettet, übersprungen (mit Grund), zuletzt geprüft, geschätzte Restzeit. Sichtbar in der App und über `wissen_suchen(stand=…)`. | Test; Ansicht |
| WK-23 | **Große Mengen:** Ziel sind mindestens **5 000 Dateien bzw. 200 000 Abschnitte** je Speicher. Die Suche antwortet bei dieser Menge im Volltext in unter 1 s und hybrid in unter 3 s auf dem Rechner des Captains. | Messlauf mit Testbestand (CPU, nur mit Ja) |
| WK-24 | **Erstaufnahme schneller:** Für eine neue Sammlung kann der Captain einen Lauf „Jetzt aufnehmen“ starten. Er läuft länger als der Takt, nur auf der CPU, mit Fortschritt in der Taskleiste und abbrechbar. Der Takt bleibt für das laufende Nachführen. | Test; Lauf mit Fortschritt |
| WK-25 | **Grenze je Datei** (heute 2 MB) wird je Art einstellbar. Große Dateien werden in Teilen gelesen, statt abgelehnt zu werden. | Test |
| WK-26 | **Personenbezug je Sammlung** wird beim Antrag gesetzt (heute je Quelle) und gilt für alle Dateien darin. Der Inhaltsschutz meldet zusätzlich je Abschnitt (wie heute `hilfen`). | Test |
| WK-27 | **Entfernen:** Sammlung abschalten oder entfernen nimmt alle ihre Abschnitte aus der Suche, ohne Gate (nur enger, wie heute `abschalten`). | Test |

### 4.4 Bestand auswerten (Ausbau, E6)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| WK-30 | **Auswertung über eine Sammlung:** eine Frage oder eine Liste von Feldern (z. B. „Vertragspartner, Laufzeit, Kündigungsfrist“) an **jedes** Dokument einer Sammlung oder einer Trefferliste. Ergebnis ist eine Tabelle, je Zeile mit Fundstelle `[W…]`. | Test mit Modell-Attrappe |
| WK-31 | Eine Auswertung ist ein **Lauf** der Harness (`lauf_starten`) mit Fortschritt, Stopp und Wiederaufnahme nach Neustart. Sie braucht eine Freigabe, weil sie das Modell lange belegt. Die Freigabe nennt Anzahl Dokumente und geschätzte Dauer. | Test; Karte zeigt Anzahl und Dauer |
| WK-32 | Ergebnis als Datei im Projekt (`.csv` und `.md`) und auf Wunsch als Quelle zurück ins Wissen (Antrag). | Test |
| WK-33 | Ein Treffer mit Personenbezug geht nie auf einen Cloud-Weg, auch nicht in einer Auswertung (WK-02). | Test |
| WK-34 | Im Chat: Werkzeug **`wissen_auswerten`** legt die Auswertung als Antrag an (Sammlung, Felder, Modell). Gestartet wird erst nach der Freigabe. | `test_freigabe_vollstaendig` |

### 4.5 Gedächtnis als Quelle (E2)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| WK-40 | Die Notizen des Gedächtnisses je Projekt (`harness/gedaechtnis.py`) werden eine Quelle „Gedächtnis · <Projekt>“. Ein Gate je Projekt beim ersten Mal; danach kommen neue Notizen ohne Gate hinein. `erinnern` sucht über WK-01 mit dem Projekt der Sitzung. | Test |
| WK-41 | **Optionen offen halten:** Die Art der Freigabe ist eine Einstellung je Quelle-Art (`gate_je_projekt` als Vorgabe; `gate_je_notiz` und `aus` möglich). Die Änderung geht als Antrag. | Test der Einstellung |
| WK-42 | Bis WK-40 fertig ist, bleibt die heutige Suche von `erinnern` unverändert. | Bestandstest grün |

### 4.6 App Wissen, nur Darstellung (E4)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| WK-50 | **Eine** App „Wissen“ in One Sedra mit den Reitern Suche · Sammlungen · Vorschläge · Eigenes · Messung, rechts die Fundstelle. Index und Nachmessung stehen unter Messung. Im Start-Menü gibt es einen Eintrag statt acht; die Suchwörter bleiben. | Test Start-Menü |
| WK-51 | Die App enthält keine eigene Logik. Sie ruft nur Verben des Kerns (Desk) und zeigt an. | Code-Prüfung: kein `fetch` außer über die Brücke/Desk |
| WK-52 | Die Leistenzelle Wissen („hybrid · 85 % · 2 Vorschläge“) steht in der Taskleiste von One Sedra. | Test `taskleiste` |
| WK-53 | Die alte Shell Wissensbasis bleibt unverändert, bis One Sedra gleich viel kann; danach wird sie als „eingefroren“ gekennzeichnet. | – |

### 4.7 Aufräumen (E5)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| WK-60 | `knowledge.py`: Der Bestand wird einmal als Quelle übernommen, `modules/planning.py` fragt über WK-01, dann wird die Datei entfernt. | Test `planning`; Suche im Code |
| WK-61 | `arbeitsumfeld_wissen.py`: Vor dem Entfernen wird geprüft, ob es noch gebaut oder gelesen wird (Audit-Log, Dateidatum der SQLite, Adapter). Erst dann entfernen, Tests anpassen. | Befund in `docs/`, danach Test |
| WK-62 | GateWay- und Arbeitsplatz-Auskunft bleiben (Live-Zustand, kein Suchwissen). | – |

## 5. Abnahme

- `python benchmarks/run_tests.py harness uix desk` und `test_freigabe_vollstaendig` grün; dazu neue Tests je WK.
- Browser-Abnahme nur an einer eigenen Testinstanz: Frage im Chat → Antwort mit `[W…]` → Klick öffnet die Fundstelle.
- Messlauf WK-23 mit einem Testbestand (nur mit Ja; CPU).
- Am Ende prüft der Captain selbst im echten Sedra.

## 6. Reihenfolge (Vorschlag für G3)

1. **K1** WK-01 … 06: der Kerndienst. Danach ist alles Weitere einfach.
2. **K2** WK-10 … 16: Chat in One Sedra. Das ist der sichtbare Nutzen.
3. **K5** WK-20 … 27: Dokumentenverwaltung (docx/csv zuerst, PDF nach F1).
4. **K3** WK-50 … 53: App Wissen.
5. **K6** WK-30 … 34: Bestand auswerten.
6. **K4** WK-40 … 42, 60 … 62: Gedächtnis als Quelle, Aufräumen.

## 7. Gate G1: freigegeben vom Captain am 05.11.2026, 14:01

| Nr | Frage | Entscheidung |
|---|---|---|
| F1 | PDF lesen: welches Paket? | **Ja.** Nach Rückfrage gilt: Sedra nutzt die Hilfswerkzeuge aus `config/hilfswerkzeuge.yaml`, also MarkItDown (W4, schon in der Liste) und daneben `pypdf` als kleinen Rückfall (neu in die Liste). Sedra installiert nichts selbst, die Installation macht der Captain. Fehlt ein Werkzeug, nennt Sedra den Befehl. |
| F2 | Wo dürfen Sammlungen liegen? | **Liste freigegebener Ordner**, festgelegt vom Captain. Dieselbe Liste soll auch die Sandbox nutzen können. |
| F3 | Mengenziel 5 000 Dateien / 200 000 Abschnitte? | **Ja**, als erste Marke. |
| F4 | Wissen ganz abschalten? | **Ja, nur der Captain.** |
| F5 | Auswertung nur lokal? | **Ja**, in v1 nur auf dem lokalen Modell. |
