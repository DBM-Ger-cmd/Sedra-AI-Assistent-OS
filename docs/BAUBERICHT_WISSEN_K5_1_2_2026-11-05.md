# Baubericht: Wissen K5-1 und K5-2 (05.11.2026)

Bau zu `docs/SPEC_WISSEN_KERN_v1_G2_K5.md` (G2 freigegeben 16:53). Auf dem Stand der Übergabe v2 und der neuen Vorbehalte. Kein Commit.

## Ergebnis

| Schritt | Inhalt | Dateien |
|---|---|---|
| K5-1 Freigegebene Ordner | `local_config/wissen_wurzeln.yaml` (Kennung, absoluter Pfad, Name, Untergrenzen Personenbezug und Stufe). Quellen mit `wurzel: w:<id>`, nur für Datei-Adapter. Die Stufe darf nicht unter der Vorgabe liegen (`wis_stufe_unter_wurzel`), der Personenbezug kommt von der Wurzel. Wird ein Ordner aus der Liste genommen, wird seine Quelle übersprungen, nicht geleert. Das Modell sieht nie den Pfad (`Wurzel.oeffentlich`). | `wissen/wurzeln.py` (neu), `adapter.py`, `speicher.py` |
| K5-1 Migration 2 | `quellen` wird neu aufgebaut (Wurzel `w:<id>`, Adapter `dokumente` erlaubt), neue Tabelle `dateien`. Läuft mit ausgeschalteten Fremdschlüsseln, damit `DROP` keine Abschnitte löscht; danach `foreign_key_check`. Vorher eine Sicherung `wissen.sqlite.bak-v1`. Saat `wis_ddl.py` gleich erweitert (nur angehängt). | `schema.py`, `benchmarks/wis_schema_seed/wis_ddl.py`, `speicher.py` |
| K5-2 Abgleich je Datei | Nur neue und geänderte Dateien werden gelesen, höchstens 200 je Durchgang (`aufnahme.dateien_je_schritt`). Entfernte Dateien verlieren ihre Abschnitte. Eine unlesbare Datei behält ihre alten Abschnitte und steht als `uebersprungen` mit Grund da. Der Quell-Hash wird erst gesetzt, wenn nichts mehr offen ist. `quell_hash = NULL` heißt weiter „alles neu zerlegen“, jetzt auch je Datei. Audit gebündelt (höchstens 20 Einzelmeldungen). | `wissen/dateien.py` (neu, Teil der Mischklasse), `schema.vergleiche_dateien`, `konfig.py` |
| K5-2 Stand je Datei | `dateien_stand(quelle, zustand, limit)` gibt die Summen (aufgenommen, übersprungen, offen, gesperrt, Abschnitte) und die Dateien mit Grund zurück. `restzeit_s` bleibt leer, bis sie gemessen ist. | `wissen/dateien.py` |

## Tests

- Neu: `test_wissen_k5_dateien.py` (9 Tests): Prüfung der Wurzeln, kaputte Datei, Untergrenzen, entfernte Wurzel, nur Geändertes gelesen (Zähler), stabile Kennungen, entfernte Datei, unlesbare Datei, Schritte, Migration von v1 mit Sicherung und Fremdschlüsseln.
- `run_tests.py harness uix desk orchestra`: 1548 Tests, 0 rot. Alle Wissenstests grün, `test_freigabe_vollstaendig` grün.

## Noch nicht in K5-1/2

- Desk-Verb `dateien` und die Anzeige: kommen mit K3 (App Wissen).
- `wissen_beantragen` mit `w:<id>` und `wissen_suchen(stand=…)`: kommen mit K5-8.
- Einstellungsseite mit den Wurzeln und dem Antrag „Ordner freigeben …“: kommt mit K3.
- Bis dahin trägt der Captain die Wurzeln von Hand in `local_config/wissen_wurzeln.yaml` ein (Beispiel im Kopf von `wissen/wurzeln.py`).

## Hinweis zum Einspielen

Beim ersten Start nach dem Update migriert der Wissensspeicher auf Version 2 und legt `local_config/wissen/wissen.sqlite.bak-v1` an.
Danach liest der erste Abgleich jede Datei einmal neu, weil die Tabelle `dateien` noch leer ist. Die Kennungen bleiben dabei gleich, neu eingebettet wird nichts.

## Nachtrag 06.11.2026: K5-3 und K5-5

| Schritt | Inhalt | Dateien |
|---|---|---|
| K5-3 Leser | Word (`.docx`) wird zu Markdown: Formatvorlagen „Heading n“/„Überschrift n“/„Title“ werden zu Köpfen, Tabellen zu Zeilen „Zelle \| Zelle“; nur `word/document.xml`, höchstens 20 MB entpackt. CSV wird zu „Spalte: Wert“ in Blöcken zu 25 Zeilen. Das Trennzeichen wird erkannt (`,` `;` Tab `\|`), Kodierung UTF-8 mit oder ohne BOM, sonst Windows-1252. Neuer Adapter `dokumente` für md, txt, docx und csv. Das GateWay liest Word jetzt über denselben Leser, mit unveränderter Ausgabe. | `wissen/leser/` (neu: `docx.py`, `tabelle.py`), `adapter.py` (`DokumenteAdapter`), `gateway/dokumente.py` |
| K5-5 Grenzen je Art | `aufnahme.je_art` (md und txt 20 MB, csv und docx 50 MB); `local_config/wissen.yaml` kann die Werte nur senken. Arten ohne eigene Grenze behalten `datei_max_bytes` (2 MB). | `konfig.py`, `config/wissen.yaml`, `adapter.py` |

**Abweichung vom G2:** Word und CSV laufen im Server-Prozess, nicht in einem eigenen Prozess. Sie brauchen nur die Standardbibliothek, und die Größe ist begrenzt (Archiv, entpacktes XML). Der eigene Prozess mit Zeitgrenze kommt mit K5-4 für MarkItDown, PDF, xlsx und pptx.
Große Text- und Markdown-Dateien werden bis zur Grenze am Stück gelesen (20 MB). Das Lesen in Teilen (§2.8) ist bis zu dieser Grenze nicht nötig.

Tests: `test_wissen_k5_leser.py` (9 Tests). `run_tests.py harness uix desk orchestra`: 1548 Tests, 0 rot. Alle Wissens- und GateWay-Tests sind grün.

## Nachtrag 06.11.2026: K5-8

| Inhalt | Dateien |
|---|---|
| `speicher.quelle_entfernen` löscht Quelle, Dateien, Abschnitte und Vektoren (Cascade), ohne Gate. Die Dateien auf der Platte bleiben. Audit `WIS_QUELLE_ENTFERNT`. Desk-Verben `dateien` (Stand je Datei, nur lesen) und `entfernen` (mit Rückfrage) an der Quelle. | `wissen/speicher.py`, `wissen/desk_wissen.py` |
| Chat: `wissen_beantragen` nimmt freigegebene Ordner `w:<id>` an. Für Ordner außerhalb und für Word und CSV gilt der Adapter `dokumente`; Stufe und Personenbezug kommen mindestens von der Wurzel. `wissen_suchen(stand=…)` liefert `wurzeln` (nur Kennung und Name, nie der Pfad), `quellen` oder den Stand je Datei einer Quelle mit den übersprungenen Dateien und ihrem Grund. | `harness/werkzeuge.py`, `harness/api.py` |

Tests: `test_harness_wissen.py` erweitert (`FreigegebeneOrdner`), `test_wissen_desk.py` (zwei neue Verben in der Liste). `harness desk` grün.

## Nachtrag 06.11.2026: K5-4

| Inhalt | Dateien |
|---|---|
| PDF, Excel (`.xlsx`) und PowerPoint (`.pptx`) im Adapter `dokumente`. Umgewandelt wird **in einem eigenen Prozess** (`python -I umwandeln.py`, leerer Arbeitsordner, Zeitgrenze `aufnahme.umwandeln_s` = 60 s, Ausgabe höchstens 20 MB). Zuerst MarkItDown, für PDF sonst `pypdf` (Seiten als `## Seite n`). Sedra installiert nichts. | `wissen/leser/umwandeln.py`, `wissen/leser/extern.py` (neu), `adapter.py`, `konfig.py`, `speicher.py` |
| Gründe im Stand je Datei: `wis_hilfswerkzeug_fehlt` (der Satz nennt `pip install "markitdown[pdf,xlsx,pptx]"`, für PDF reicht `pip install pypdf`), `wis_kein_text` (gescannte PDF, Texterkennung erst mit W5), `wis_umwandeln_zeitgrenze`, `wis_umwandeln_fehler`. | `speicher.py` (`SAETZE`) |
| Grenzen: PDF und PowerPoint 100 MB, Excel 50 MB. In der Liste der Hilfswerkzeuge steht MarkItDown jetzt mit den Extras für PDF, Excel und PowerPoint, dazu neu `pypdf`. | `config/wissen.yaml`, `config/hilfswerkzeuge.yaml` |

**Gefunden beim echten Lauf:** MarkItDown gibt bei einer kaputten PDF keinen Fehler zurück, sondern fällt auf seinen Textleser und liefert die Rohbytes (`%PDF-…`) als „Text“. Eine Ausgabe, die wie die Rohdatei beginnt (`%PDF`, ZIP-Kopf), gilt jetzt als Fehlschlag; dann wird `pypdf` versucht, sonst steht die Datei als `wis_umwandeln_fehler` im Stand.

Tests: `test_wissen_k5_umwandeln.py` (9 Tests). Hier gelaufen mit echtem MarkItDown 0.1, pypdf 6.17, openpyxl und python-pptx; fehlen die Pakete, werden diese Fälle übersprungen. Die Fälle „Werkzeug fehlt“, „Zeitgrenze“ und „Stand“ laufen immer.
`run_tests.py harness uix desk orchestra`: 1550 Tests, 0 rot. Alle Wissens-, GateWay- und Hilfswerkzeug-Tests sind grün.

**Für den PC des Captains:** Ob MarkItDown in `runtime/.venv` installiert ist, zeigt Einstellungen → Hilfswerkzeuge. Ohne MarkItDown und ohne pypdf werden PDF, Excel und PowerPoint übersprungen und stehen mit dem Befehl im Stand. Markdown, Text, Word und CSV gehen immer.

## Nachtrag 06.11.2026: K5-6

| Inhalt | Dateien |
|---|---|
| Die Vektorsuche nutzt **numpy**, wenn es da ist: alle Vektoren als eine Matrix, eine Multiplikation, Top-k mit `argpartition`. Ergebnis und Reihenfolge sind gleich wie in reinem Python (bei Gleichstand gewinnt die kleinere Nummer). Die Matrix wird neu geladen, sobald sich die Zahl der Vektoren ändert; das gilt auch für Vektoren, die ein anderer Prozess schreibt. Ohne numpy oder mit `suche.numpy: aus` läuft der bisherige Weg. Der Stand nennt die Art (`vektorsuche`). | `wissen/vektor_np.py` (neu), `suche.py`, `konfig.py`, `config/wissen.yaml`, `config/hilfswerkzeuge.yaml` |

**Messung (Mengenziel F3, `SEDRA_WISSEN_MENGE=1`):** 200 000 Abschnitte in 5 000 Dateien. Volltext ≈ 0,2 s. Vektorteil mit numpy 66 ms (Matrix 821 MB), reines Python 3,38 s. Die Zahl im G2 (54 s) war unter Last gemessen und falsch; das G2 ist korrigiert, Weg B (eigener Index) wird nicht gebaut.

Tests: `test_wissen_k5_vektor.py` (5 Tests), `test_wissen_menge.py` (nur mit `SEDRA_WISSEN_MENGE=1`). Die Importgrenze (`test_wissen_grenze`) erlaubt numpy jetzt nur in `vektor_np.py` und nur innerhalb einer Funktion; ein neuer Test prüft, dass numpy nicht beim Laden des Moduls importiert wird.

## Nachtrag 06.11.2026: K5-7

| Inhalt | Dateien |
|---|---|
| Neuer Lauftyp **`wissen_aufnahme`** (Name „Wissen – Erstaufnahme einer Quelle“, Parameter `quelle` nur `Q-` und 8 Hexzeichen, ohne GPU, Zeitlimit 600 min). Er wird wie jeder Lauf über `lauf_starten` gestartet; Stopp, Fortschritt in der Taskleiste und Ende kommen von der Lauf-Hülle. | `config/harness_laeufe.yaml`, `benchmarks/wissen_aufnahme.py` (neu) |
| Der Lauf gleicht in Schritten zu 200 Dateien ab, bis keine Datei mehr offen ist, und bettet danach auf der CPU ein. Läuft der Einbett-Server schon, nutzt er ihn mit; sonst startet er ihn und beendet ihn am Ende. Hält ein Bau die GPU-Lease, wartet er (höchstens eine Stunde). Fortschritt: `Stand p/100 · Dateien n/m · Abschnitte a · eingebettet e/v` (Abgleich bis 50, Einbetten bis 100). | `wissen/aufnahme_lauf.py` (neu) |
| **Sperre:** Der Takt des Servers hält `takt.lock` dauerhaft, deshalb gibt es eine zweite Sperre `local_config/wissen/aufnahme.lock`. Der Takt (und das Verb `nachfuehren`) nimmt sie je Durchgang ohne zu warten; hält der Lauf sie, entfällt der Durchgang. Der Lauf hält sie für seine ganze Dauer und wartet beim Start bis zu 10 Minuten, falls gerade ein Durchgang läuft. So schreiben nie zwei gleichzeitig. | `wissen/aufnahme.py` |
| Abbruch jederzeit: Jeder Schritt ist eine Transaktion. Ein neuer Lauf macht über die Tabelle `dateien` beim nächsten Schritt weiter, ohne doppelte Abschnitte. Audit: `WIS_AUFNAHME_LAUF` (start, ende). | – |

Rückgabe: 0 fertig, 2 Quelle unbekannt oder Wissen nicht lesbar, 3 Sperre belegt.
**Freigabe:** Im Beispiel-Katalog steht `wissen_aufnahme` nicht unter den freien Läufen. Jeder Start braucht also eine Freigabe des Captains. Soll er frei laufen, trägt ihn der Captain unter `lauf_starten` in seinen Katalog ein.

Tests: `test_wissen_k5_lauf.py` (8 Tests: Schritte und Fortschritt, Sperre zwischen Takt und Lauf, Sperre über die ganze Dauer, Abbruch und Wiederaufnahme, laufender Server bleibt an, unbekannte Quelle, `main`, Lauftyp). Das Startskript ist als eigener Prozess geprüft. `test_harness_lauf_typen` kennt den neuen Typ.

`run_tests.py harness uix desk orchestra wissen`: 1741 Tests, 0 rot (11 übersprungen). `test_freigabe_vollstaendig` und `test_harness_werkzeug_vollstaendig` sind grün.
