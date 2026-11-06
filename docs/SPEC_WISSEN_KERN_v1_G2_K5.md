# SPEC Wissen im Kern v1 – G2 Design für K5 Dokumentenverwaltung (05.11.2026)

Gate **G2** (Design) zu `docs/SPEC_WISSEN_KERN_v1.md` §4.3 (WK-20 … WK-27, G1 freigegeben am 05.11.2026, 14:01, mit F1–F5).
Baut auf K1/K2 auf (`docs/SPEC_WISSEN_KERN_v1_G2_K1K2.md`, gebaut, Übergabe v2). Nur im Code gelesen und auf diesem Rechner gemessen
(Linux, 2 Kerne, Python 3.13), nicht auf dem PC des Captains.

## 0. Entscheidungen aus G1, die hier gelten

| Nr | Entscheidung |
|---|---|
| F1 | PDF und weitere Arten über die Hilfswerkzeuge: MarkItDown (W4), `pypdf` als kleiner Rückfall (neu in `config/hilfswerkzeuge.yaml`). Sedra installiert nichts. |
| F2 | Sammlungen nur unter freigegebenen Ordnern, die der Captain festlegt; dieselbe Liste kann die Sandbox lesen. |
| F3 | Mengenziel 5 000 Dateien / 200 000 Abschnitte. |
| F4 | Wissen ganz abschalten nur der Captain. |
| F5 | Auswertung (K6) nur lokal – betrifft K5 nicht direkt. |

## 1. Befund im Code und Messung

| Nr | Befund | Beleg | Folge für K5 |
|---|---|---|---|
| B1 | **Der Abgleich liest bei jeder Änderung die ganze Quelle neu.** Der Quell-Hash ist die Summe aller Dateien. Ändert sich eine Datei, werden alle Dateien der Quelle gelesen und zerlegt. Erst danach vergleicht `schema.vergleiche` mit dem Bestand. | `speicher.py` `abgleich` (≈ 237–300), `adapter.py` `quell_hash` | Bei 5 000 Dateien, darunter PDFs mit Umwandlung, dauert jede Änderung Minuten. Es braucht einen **Stand je Datei**. |
| B2 | Für einzelne Dateien gibt es keine Tabelle. `stand()` kennt nur Summen. Eine übersprungene Datei steht nur im Audit (`WIS_DATEI_UEBERSPRUNGEN`). | `schema.py` (Tabellen meta, quellen, abschnitte, vektoren, vorschlaege, laeufe) | WK-22 (Stand je Datei) braucht eine neue Tabelle. |
| B3 | Erlaubt sind nur die Wurzeln `repo` und `projekt`, nur die Adapter der Liste und nur `*.md` und `*.txt`. Das steht als `CHECK` in der Tabelle `quellen` und als Liste im Adapter. | `schema.py` `quellen` CHECK; `adapter.py` `DATEIARTEN`, `NAMEN` | Neue Wurzeln und Dateiarten brauchen eine Migration. SQLite kann ein `CHECK` nicht ändern, also muss die Tabelle `quellen` neu aufgebaut werden. |
| B4 | **Die Vektorsuche ist zu langsam für das Mengenziel.** Gemessen: 10 000 Vektoren mit 1 024 Dimensionen brauchen **2,7 s** und 45 MB (reines Python, `vektor.top_k`). Hochgerechnet auf 200 000 Abschnitte sind das **≈ 54 s und ≈ 0,9 GB**. Ziel aus WK-23 sind unter 3 s. | `wissen/vektor.py` (ohne numpy, bewusst, D7.2), Messskript im Scratchpad | Es braucht eine andere Suche (§2.6). In der Volltextsuche (FTS5) liegt das Problem nicht. |
| B5 | Den Word-Leser gibt es ohne Zusatzpaket, aber nur im GateWay: nur `word/document.xml`, fail-closed, entpackt höchstens 20 MB. | `gateway/dokumente.py` `lies_docx` | Er wandert in den Kern, und das GateWay importiert ihn dann von dort. |
| B6 | Die Grenze je Datei ist fest auf 2 MB eingestellt; eine größere Datei wird ganz abgelehnt. | `config/wissen.yaml` `aufnahme.datei_max_bytes` | WK-25 |
| B7 | Der Takt nimmt alle 600 s höchstens 120 s fürs Einbetten. Bei 200 000 Abschnitten mit BGE-M3 auf der CPU dauert die Erstaufnahme damit vermutlich viele Stunden. Das ist ungemessen; die Zahl der Abschnitte je Sekunde fehlt. | `config/wissen.yaml` `takt` | WK-24 (Erstaufnahme als Lauf) |
| B8 | Personenbezug und Stufe gelten heute schon je Quelle. „Sammlung“ heißt in K5 einfach Quelle mit `art: ordner`. | `quellen.personenbezug`, `stufe` | WK-26 ist größtenteils schon da. |
| B9 | Abschalten gibt es (`quelle_aendern aktiv=0`, ohne Gate), Entfernen nicht. Die Fremdschlüssel löschen Abschnitte mit (`ON DELETE CASCADE`). | `speicher.quelle_aendern`, `schema.py` | WK-27: das Verb `entfernen` |

## 2. Design

### 2.1 Freigegebene Ordner (F2, WK-21)

- Neue Datei **`local_config/wissen_wurzeln.yaml`**. Sie liegt im Bereich `local_config`, der schon fester Vorbehalt ist; schreiben kann sie also nur der Captain:
  ```yaml
  wurzeln:
    - {id: kunden, pfad: '<projekte>/Kunden', name: Kundenakten, personenbezug: 1, stufe: 2}
    - {id: handbuch, pfad: '<modelle>/../handbuecher', name: Handbücher}
  ```
  `id`: `a-z 0-9 -`. Der Pfad ist absolut und muss existieren. `personenbezug` und `stufe` sind Vorgaben für Sammlungen darin; ein Antrag darf sie nur strenger setzen.
- Im Kern liest `wissen/wurzeln.py` (neu, rein, ≤ 120 Zeilen) die Datei und prüft sie. Ist sie kaputt, gibt es keine äußeren Wurzeln und einen Satz im Info-Hub, nie einen Absturz.
- In `quellen.wurzel` steht dann `repo`, `projekt` oder `w:<id>`. Der Adapter löst `w:<id>` über die Liste auf. Fehlt eine Wurzel später, wird die Quelle übersprungen (`wis_wurzel_unbekannt`), nicht geleert.
- **Sandbox:** Dieselbe Datei kann die Sandbox als Liste lesen (nur lesend eingehängt, ein Ordner je Wurzel). Das Einhängen selbst ist nicht Teil von K5, die Liste ist nur so gebaut, dass sie es trägt.
- **Einstellungen:** Unter Einstellungen → System → Wissen zeigt eine Seite die Wurzeln, nur lesend. „Ordner freigeben …“ stellt einen Antrag, der die Datei ändert (Klasse H, wie andere Änderungen an `local_config`). Die Seite bekommt keinen eigenen Schreibweg.

### 2.2 Migration des Schemas (v+1, nur anhängen)

- **`quellen` neu aufbauen:** `wurzel` ohne `CHECK`, geprüft in `pruefe_quelle`. Bei `adapter` kommt `dokumente` dazu. Der Bestand wird 1:1 übernommen.
- **Neue Tabelle `dateien`:** je Datei einer Quelle eine Zeile.
  ```sql
  CREATE TABLE dateien (quelle TEXT NOT NULL REFERENCES quellen(id) ON DELETE CASCADE, datei TEXT NOT NULL,
    hash TEXT NOT NULL, art TEXT NOT NULL, zustand TEXT NOT NULL CHECK (zustand IN ('aufgenommen','uebersprungen','gesperrt')),
    grund TEXT, abschnitte INTEGER NOT NULL DEFAULT 0, groesse INTEGER NOT NULL, geprueft TEXT NOT NULL, PRIMARY KEY (quelle, datei));
  ```
- Die Migration läuft beim Öffnen des Speichers, mit Sicherung vorher (`wissen.sqlite.bak-v<n>`). Ein Fehler lässt das Wissen aus und nennt den Grund; die Datei bleibt dann unverändert.

### 2.3 Adapter `dokumente` und Leser je Art (WK-20)

| Art | Leser | Paket | Zerlegen |
|---|---|---|---|
| `.md` | wie heute | – | `zerlege_markdown` |
| `.txt` | wie heute, große Dateien in Teilen (§2.8) | – | `zerlege_text` |
| `.docx` | `wissen/leser/docx.py` (aus `gateway/dokumente.py`; das GateWay importiert von dort) | – (Standardbibliothek) | Überschriften (`Heading n`) werden zu Markdown-Köpfen, dann `zerlege_markdown` |
| `.csv` | `wissen/leser/csv.py` (Standardbibliothek): Trennzeichen erkennen, Kopfzeile, je Zeile „Spalte: Wert“ | – | ein Abschnitt je Zeilenblock, die Kopfzeile in der Stelle |
| `.pdf` | MarkItDown, sonst `pypdf` (nur Text) | Hilfswerkzeug | Markdown von MarkItDown, Seiten als Köpfe bei `pypdf` |
| `.xlsx`, `.pptx` | MarkItDown | Hilfswerkzeug | Tabellen bzw. Folien als Köpfe |

- **Umwandlung in einem eigenen Prozess** (`python -I -m guppi_runtime.wissen.leser.umwandeln <datei>`), mit Zeitgrenze (60 s, einstellbar), ohne Netz und mit Größengrenze. Ein hängendes oder böswilliges Dokument hält so nicht den Server auf. Die Ausgabe ist UTF-8-Text über stdout, höchstens 20 MB.
- **Fehlt das Hilfswerkzeug:** Die Datei steht als `uebersprungen`, Grund `hilfswerkzeug_fehlt:markitdown`, dazu der Installationsbefehl aus `hilfswerkzeuge.yaml`. Sie wird nie still weggelassen.
- **Kein OCR in v1:** Eine PDF ohne Textschicht ergibt `uebersprungen`, Grund `kein_text` (Hinweis auf W5, Texterkennung).
- Der Inhaltsschutz (`befunde_von`) läuft je Abschnitt wie heute. Ein harter Fund sperrt den Abschnitt (`gesperrt`), nicht die ganze Datei.

### 2.4 Abgleich je Datei (B1)

- `quell_hash` bleibt als schneller Gesamtblick.
- Ist er anders, vergleicht der Abgleich je Datei `größe:mtime_ns` mit `dateien.hash`. **Gelesen und zerlegt werden nur neue und geänderte Dateien.** Fehlen Dateien, verschwinden ihre Abschnitte.
- `schema.vergleiche` bekommt eine Teilmenge der Dateien: Alte Abschnitte dieser Dateien gegen die neuen, alle anderen bleiben unberührt. Die Kennungen der Abschnitte bleiben stabil, wie heute über `quelle`, `datei`, `stelle` und `teil`; unveränderte Abschnitte werden nicht neu eingebettet.
- Je Durchgang höchstens `aufnahme.dateien_je_schritt` Dateien (Vorgabe 200), damit der Takt kurz bleibt. Der Rest folgt im nächsten Schritt oder im Lauf (§2.7).
- **Audit:** `WIS_ABGLEICH` mit Zahlen je Zustand. Je übersprungener Datei weiter `WIS_DATEI_UEBERSPRUNGEN`, aber gebündelt: höchstens 20 Einträge je Durchgang, dazu die Summe.

### 2.5 Stand je Sammlung und Datei (WK-22)

- `speicher.dateien_stand(quelle_id, zustand=None, limit=100)` → `{summen: {aufgenommen, uebersprungen, gesperrt, offen}, dateien: [...], restzeit_s}`.
  Die Restzeit wird aus den Abschnitten je Sekunde der letzten Läufe geschätzt; gibt es dazu nichts, bleibt sie leer statt geraten.
- Desk-Verb `dateien` an der Quelle (lesen, ohne Gate); die App Wissen (K3) zeigt es.
- Werkzeug `wissen_suchen` bekommt das Argument `stand: <quelle>`. Dann kommen die Summen und die übersprungenen Dateien mit Grund statt der Treffer, damit das Modell dem Captain sagen kann, was fehlt.

### 2.6 Große Mengen: Vektorsuche (WK-23, B4)

| Möglichkeit | 200 000 × 1 024 | Speicher | Abhängigkeit | Genauigkeit |
|---|---|---|---|---|
| heute (reines Python) | ≈ 54 s | ≈ 0,9 GB | keine | exakt |
| **A: numpy, wenn installiert** (Matrix float32, ein Matrixprodukt) | unter 0,2 s (Erfahrungswert, in G3 messen) | 0,8 GB | numpy als Hilfswerkzeug (fehlt heute in `runtime/.venv`, WISSEN §6) | exakt |
| **B: Grobindex in reinem Python** (k-means, 256 Zentren, die 8 nächsten Gruppen durchsuchen ≈ 6 000 Vektoren) | ≈ 1,6 s (aus der Messung hochgerechnet) | ≈ 0,9 GB | keine | fast exakt (Erfahrungswert 95–99 % der Treffer, in G3 messen) |
| C: int8-Quantisierung (zusätzlich zu A) | ≈ wie A | ≈ 0,2 GB | numpy | gering schlechter |

**Vorschlag: A, wenn numpy da ist, sonst B.** Den Index für B baut der Lauf (§2.7) oder der Takt, sobald mehr als 20 000 Vektoren da sind. Darunter bleibt die exakte Suche. Der Speicherbedarf (≈ 0,8–0,9 GB) wird im Info-Hub gezeigt, damit er nicht überrascht. Die Volltextsuche (FTS5) wird bei 200 000 Abschnitten in G3 gemessen; erwartet sind deutlich unter 1 s.

### 2.7 Erstaufnahme als Lauf (WK-24)

- Ein neuer Lauftyp `wissen_aufnahme` in `runtime/config/harness_laeufe.yaml` (fester Vorbehalt, also nur mit Captain-Gate). Er startet `python -m guppi_runtime.wissen.aufnahme_lauf --quelle <id>` als eigenen Prozess über die bestehende Lauf-Hülle: Fortschritt in der Taskleiste, Stopp, Ende melden, Wiederaufnahme nach einem Neustart über die Tabelle `dateien`.
- Der Lauf nimmt die **Takt-Sperre** (`takt.lock`). Der Takt des Servers setzt so lange aus (`wis_takt_busy`, das gibt es schon), und zwei Schreiber gleichzeitig kann es nicht geben.
- Ablauf: Abgleich in Schritten von 200 Dateien, danach Einbetten in Stapeln. Die Fortschrittszeile lautet `Dateien n/m · Abschnitte k/l · eingebettet e/l`, passend zur `fortschritt_regel` der Lauf-Typen.
- Gerät: nur die CPU (WK-05). Hält jemand die GPU-Lease für einen Bau, pausiert der Lauf wie der Takt (`TestLabZugang.lage`).
- **Offen für G3:** Der Einbett-Server (Port 8094, eigene PID-Datei) wird heute vom Server-Prozess gestartet. Der Lauf soll denselben Dienst nutzen: Läuft er schon, über HTTP, sonst startet der Lauf ihn mit derselben PID-Datei. In G3 ist zu prüfen, dass `EmbeddingDienst` dabei einen fremden, laufenden Server erkennt (Entscheidung D-K5-4).
- Start: In der App Wissen gibt es an einer Sammlung „Jetzt aufnehmen“. Im Chat entsteht der Lauf nur über `lauf_starten` mit Karte, wie jeder Lauf.

### 2.8 Grenzen je Art und große Dateien (WK-25)

- `config/wissen.yaml` `aufnahme.datei_max_bytes` wird je Art festgelegt: `{text: 20 MB, md: 20 MB, csv: 50 MB, docx: 50 MB, pdf: 100 MB, xlsx: 50 MB, pptx: 100 MB}`. Die lokale Datei kann die Werte nur senken.
- Text, Markdown und CSV über 2 MB werden in Stücken gelesen: zeilenweise, mit Überhang an einer Absatzgrenze, ohne die ganze Datei auf einmal in den Speicher zu laden. Das Zerlegen bleibt dasselbe.

### 2.9 Personenbezug und Stufe je Sammlung (WK-26)

- Gibt es schon je Quelle. Neu ist nur die Vorgabe aus der Wurzel (§2.1): Ein Antrag darf strenger sein (Personenbezug 1, höhere Stufe), nie lockerer.
- Der Inhaltsschutz meldet weiter je Abschnitt. Der Stand je Datei zählt gesperrte Abschnitte mit.

### 2.10 Entfernen (WK-27)

- Das Desk-Verb `entfernen` an der Quelle löscht Quelle, Dateien, Abschnitte und Vektoren (Cascade), ohne Gate, weil das Wissen dadurch nur enger wird. Vorher kommt eine Rückfrage in der App, und es gibt ein Audit `WIS_QUELLE_ENTFERNT`. Die Quell-Dateien auf der Platte bleiben unberührt.
- Ein neuer Antrag für denselben Ordner ist danach wieder möglich.

### 2.11 Chat (Folge von D4 aus K2)

- `wissen_beantragen` nimmt dann `wurzel: w:<id>` an. Die Liste der Wurzeln sieht das Modell über `wissen_suchen(stand: 'wurzeln')`: nur id und name, keine Pfade.
- Das Muster darf nur die erlaubten Arten enthalten (`*.md, *.txt, *.docx, *.csv, *.pdf, *.xlsx, *.pptx`).

## 3. Tests

| Test | prüft |
|---|---|
| `test_wissen_wurzeln.py` | Liste lesen und prüfen; kaputt → keine Wurzeln, mit Satz; `w:<id>` auflösen; fehlende Wurzel → Quelle übersprungen |
| `test_wissen_migration_k5.py` | Bestand bleibt erhalten; neue Spalten und Tabelle da; Sicherung angelegt; Fehler → Wissen aus, Datei unverändert |
| `test_wissen_leser.py` | docx (Überschriften, Tabellen), csv (Trennzeichen, Kopf, Umlaute), PDF über eine Attrappe des Umwandlers, fehlendes Hilfswerkzeug → `uebersprungen` mit Befehl, Zeitgrenze → `uebersprungen` |
| `test_wissen_abgleich_je_datei.py` | Nur geänderte Dateien gelesen (Zähler des Lesers), Kennungen unveränderter Abschnitte bleiben, entfernte Datei → Abschnitte weg, Schrittgrenze 200 |
| `test_wissen_menge.py` | Synthetischer Bestand mit 200 000 Abschnitten. Volltext unter 1 s, Grobindex unter 3 s und ≥ 95 % gleiche Treffer wie exakt. Mit `--slow`, nur auf der CPU. |
| `test_wissen_aufnahme_lauf.py` | Lauf nimmt die Takt-Sperre, Fortschrittszeilen, Stopp, Wiederaufnahme |
| `test_harness_wissen.py` (erweitert) | `wissen_beantragen` mit `w:<id>`, `stand` |
| `test_freigabe_vollstaendig` | neue Verben und Entscheidungsarten eingeordnet |

## 4. Bau-Aufteilung (Vorschlag für G3)

| Schritt | Inhalt | Dateien |
|---|---|---|
| K5-1 | Wurzeln und Migration | `wissen/wurzeln.py`, `schema.py`, `speicher.pruefe_quelle` |
| K5-2 | Abgleich je Datei und Stand je Datei | `speicher.py`, `schema.vergleiche`, `adapter.py` |
| K5-3 | Leser docx und csv, Umwandeln im eigenen Prozess | `wissen/leser/*`, `gateway/dokumente.py` (importiert neu) |
| K5-4 | PDF, xlsx, pptx über die Hilfswerkzeuge | `wissen/leser/umwandeln.py`, `config/hilfswerkzeuge.yaml` (+ `pypdf`) |
| K5-5 | Große Dateien und Grenzen je Art | `adapter.py`, `konfig.py`, `config/wissen.yaml` |
| K5-6 | Vektorsuche für große Mengen (numpy oder Grobindex) mit Messung | `wissen/vektor.py`, `suche.py`, neu `wissen/grobindex.py` |
| K5-7 | Erstaufnahme als Lauf | `wissen/aufnahme_lauf.py`, `config/harness_laeufe.yaml` |
| K5-8 | Entfernen, Chat (`w:<id>`, `stand`) | `desk_wissen.py`, `harness/api.py` |

Reihenfolge 1 → 2 → 3 → 5 → 4 → 8 → 6 → 7. K5-1 und K5-2 sind die Grundlage, K5-6 und K5-7 sind die größten Schritte.
Die Oberfläche (Sammlungen, Stand, „Jetzt aufnehmen“) kommt mit K3, der App Wissen.

## 5. Entscheidungen für das Gate G2

**Gate G2 freigegeben vom Captain am 05.11.2026, 16:53** („machen wir weiter“ auf die Frage „Gibst du G2 so frei?“): alle Vorschläge D-K5-1 bis D-K5-7 wie unten.

| Nr | Frage | Vorschlag |
|---|---|---|
| D-K5-1 | Wo stehen die freigegebenen Ordner? | eigene Datei `local_config/wissen_wurzeln.yaml` (fester Vorbehalt); ändern nur per Antrag oder von Hand durch den Captain |
| D-K5-2 | Vektorsuche bei großen Mengen | **A** (numpy, wenn installiert) mit Rückfall **B** (Grobindex in reinem Python); numpy kommt als Hilfswerkzeug in die Liste, die Installation macht der Captain |
| D-K5-3 | Umwandlung von PDF, xlsx und pptx | in einem eigenen Prozess mit 60 s Zeitgrenze; kein OCR in v1 |
| D-K5-4 | Einbetten im Lauf | derselbe Einbett-Server (Port 8094) wie der Takt; der Lauf startet ihn nur, wenn keiner läuft |
| D-K5-5 | Grenzen je Art | wie §2.8 (Text 20 MB, PDF 100 MB …); die lokale Datei kann nur senken |
| D-K5-6 | Schritt je Takt | höchstens 200 Dateien je Durchgang; der Rest folgt im nächsten Durchgang oder im Lauf |
| D-K5-7 | Messung auf deinem PC | Messlauf `test_wissen_menge --slow` nur auf der CPU, auf dein Ja (er dauert vermutlich einige Minuten) |
