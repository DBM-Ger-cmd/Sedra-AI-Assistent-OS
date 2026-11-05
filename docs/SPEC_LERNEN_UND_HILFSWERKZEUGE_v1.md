# SPEC Lernen und Hilfswerkzeuge v1 – G1 Anforderungen (05.11.2026)

Stand: `main` `d51083a`. Gate **G1** (Anforderungen); Design (G2) und Bau (G3) erst nach Freigabe durch den Captain.
Herkunft: `ROADMAP_ONE_SEDRA_RENEW_2026-11-05.md` (Phase R5, Unterchat U7), `ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05.md` (X4, W4, W5), `ENTWURF_BELOHNUNG_UND_LERNEN_2026-11-05.md` (L1–L4 gebaut), `PLAN_CPU_HILFSWERKZEUGE_2026-11-04.md` (P0/P1 gebaut, E1–E5 offen), `WISSEN_SEDRA_GESAMT.md` §10.

**Kurz:** Das Lernsystem ist gebaut, aber im Alltag noch nicht wirksam: Es gibt keinen Rückblick und keine `docs/AAR/LESSONS.md`, und die Zustimmung des Captains zu einer gelernten Regel ist nur eine Regel im Prompt. U7 bringt (1) den **Rückblick in den Alltag**, mit einem Knopf an jeder korrigierten Antwort, (2) das Werkzeug **`rueckblick_schreiben`** als Antrag, sodass Regeln nur mit dem Ja des Captains in den Systemprompt kommen, (3) **bessere Vorschläge beim Tippen** und das Werkzeug `vorschlaege_pflegen`, (4) **Dokumente lesen auf der CPU** (MarkItDown, neu `pypdf` als kleiner Rückfall) und die Prüfung vor der Freigabe. Sedra installiert nichts selbst.

## 1. Befund (im Code gelesen)

### 1.1 Lernen

| Nr | Befund | Beleg |
|---|---|---|
| L1 | **Den Rückblick gibt es nur als Vorlage, die man von Hand startet.** Kein Knopf an einer korrigierten Antwort, kein Hinweis „n Korrekturen seit dem letzten Rückblick“. Im echten Sedra nicht ausprobiert. | `config/harness_vorlagen/rueckblick.yaml`; `ROADMAP_ONE_SEDRA_RENEW…` §2 |
| L2 | **`docs/AAR/` gibt es im Repo nicht.** L4 („gelernte Regeln wirken“) liest also heute nichts; bisher ist kein Rückblick geschrieben. | `ls docs/AAR` → fehlt; `harness/belohnung.py:251–264` |
| L3 | **LESSONS.md wirkt im Systemprompt jeder Sitzung des Projekts** (letzte 25 Zeilen, höchstens 2 000 Zeichen), ist aber **kein Vorbehalt**. Die Vorlage hat `datei_schreiben`, `datei_aendern` und `befehl`; „Maßnahmen nur mit Ja“ steht nur im Prompt. Über eine Sitzungs-Erlaubnis für eine Karte in `docs/AAR/` (Muster `docs/AAR/**`) oder den Baustein „Dokumente in docs/ ändern“ (`docs/**`) kann das Modell Regeln ohne weitere Karte in den Systemprompt schreiben. Zum Vergleich: ein Skill (dauerhafter Text für das Modell) ist Klasse H. | `harness/api.py:544`; `config/harness_vorlagen/rueckblick.yaml:7`; `rueckblick.md:38–39`; `harness/erlaubnis.py:29–31`; `config/freigabe_bausteine.yaml:13–17`; `desk/freigabeklasse.py:27` |
| L4 | Der Standard-Schreibbereich eines Projekts ist `runtime/**`, `docs/**`, `redesign/**`; im Katalog gewinnt dort die Regel `schreiben-docs` (Stufe `captain`). Ohne Erlaubnis kommt also eine Karte; die Lücke aus L3 entsteht erst durch eine Erlaubnis. | `harness/projekte.py:21`; `config/freigabe_katalog.beispiel.yaml:30–44` |
| L5 | **Vorschläge lesen bei jeder Tipp-Pause den ganzen Index** (`_index.jsonl`) ohne Zwischenspeicher; 250 ms Verzögerung. Wie lange das bei vielen Einträgen dauert, ist nicht gemessen. | `harness/belohnung.py:187–199, 308`; `uix/shells/harness/vorschlaege.js:10, 57–62` |
| L6 | **Gelobt und später korrigiert:** Eine Frage, deren Antwort erst gelobt und später zum selben Auftrag korrigiert wurde, wird weiter als ★ vorgeschlagen; die Korrektur erscheint nur als Warnung daneben. | `harness/belohnung.py:316–327` |
| L7 | **Mindestlänge doppelt:** Der Browser fragt erst ab 3 Zeichen (fest), der Server liest `min_zeichen` aus der Konfiguration. Wer in `local_config` 2 einträgt, merkt im Browser nichts. | `vorschlaege.js:10, 13`; `config/belohnung.yaml:43` |
| L8 | **Nur eine Quelle:** Vorschläge kommen nur aus gelobten Fragen. Keine Vorlagen, keine Dateien, keine Messung, wie oft ein Vorschlag übernommen wurde. X4 verlangt „Vorschläge ausbauen (Dateien, Vorlagen)“. | `harness/belohnung.py:297–328`; `ROADMAP_…_UIX_WERKZEUGE` §2 X4 |
| L9 | **Lesen ist schon frei:** `belohnungen_lesen` läuft ohne Karte (Liste `OHNE_KARTE`). Ein Antrag-Werkzeug nach demselben Muster gibt es mit `vorlage_beantragen`. | `harness/katalog.py:20`; `harness/werkzeuge.py:101, 108` |
| L10 | **Wissen:** Die Tagesdateien der Belohnungen sind eine Markdown-Quelle, die per Antrag (Klasse H) in die Wissensdatenbank kommt. Seit heute ist Wissen ein Kerndienst mit `wissen_suchen` (frei) und `wissen_beantragen` (Antrag); die Arbeit liegt nicht in diesem Worktree (Stand nicht gelesen, Vermutung: gleiche Muster). | `ENTWURF_BELOHNUNG…` §1; `desk/freigabeklasse.py:31` |

### 1.2 Hilfswerkzeuge

| Nr | Befund | Beleg |
|---|---|---|
| H1 | **Register und Seite sind gebaut (P1):** 21 Einträge, nur Erkennung (`which`, `find_spec` ohne Import), Installationsbefehl als Text, keine Installation. | `config/hilfswerkzeuge.yaml` (21 × `id:`); `harness/hilfswerkzeuge.py:1–5, 39–52` |
| H2 | **MarkItDown und Docling stehen im Register (W4), `pypdf` fehlt.** | `config/hilfswerkzeuge.yaml:14–15` |
| H3 | **Dokumente lesen kann nur `.md`, `.txt`, `.docx`** (Standardbibliothek), ausdrücklich kein PDF; Fehler sind fail-closed (`dokument_nicht_lesbar`). | `gateway/dokumente.py:1–6, 14, 26–37` |
| H4 | **Sedra installiert nichts:** `pip install`, `winget`, `curl`, `wget` sind feste Vorbehalte für `befehl`. | `harness/vorbehalte.py:41–42` |
| H5 | **E1–E5 im Plan sind Entscheidungen, keine Bauschritte** (Python-Umgebung, NER, Lizenzen, Speicherort, Reihenfolge); alle offen. Nächster Bauschritt im Plan: P2 = W4/W5, F5, dann F8. | `PLAN_CPU_HILFSWERKZEUGE…:65–80` |

## 2. Ziel

**Lernen:** Nach einer Korrektur steht der Rückblick einen Klick entfernt. Er sammelt die Fakten, beantwortet die vier Fragen und stellt **einen Antrag**: Bericht `docs/AAR/<ID>.md` und vorgeschlagene Regeln für `docs/AAR/LESSONS.md`. Der Captain wählt im Posteingang, welche Regeln gelten. Erst dann stehen sie im Systemprompt. Vorschläge beim Tippen sind schnell, widersprechen keiner Korrektur und lassen sich pflegen.

**Hilfswerkzeuge:** Sedra liest PDF, Excel und PowerPoint auf der CPU mit MarkItDown, falls der Captain es installiert hat; für PDF gibt es `pypdf` als kleinen Rückfall. Fehlt beides, nennt Sedra den Befehl und liest nichts. Diff-Karten zeigen vor dem Ja, ob die Syntax stimmt.

**Nicht Ziel:** etwas herunterladen oder installieren; automatische Rückblicke ohne Klick; Regeln ohne Ja des Captains; GPU-Läufe; NER-Modelle (W7) und Klassifikatoren (F13) ohne E2 des Plans; Docling (schwer, Vermutung: zieht PyTorch nach) als Standard; das Wissen selbst umbauen (parallele Arbeit).

## 3. Anforderungen

### 3.1 Rückblick im Alltag

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| LR-01 | **Knopf „Rückblick“ an jeder Antwort mit ⚑.** Er legt eine neue Sitzung mit der Vorlage `rueckblick` an, vorbelegt mit Sitzung, Antwort und den Worten der Korrektur (erste Nachricht, nicht abgeschickt). Kein automatischer Start. | Node-Test; Playwright an der Testinstanz |
| LR-02 | **Hinweis im Alltag:** Info-Seite und Posteingang zeigen „n Korrekturen seit dem letzten Rückblick“ mit Knopf „Rückblick starten“ (Zeitraum seit dem letzten Bericht in `docs/AAR/`). | Test `uebersicht`; Node-Test |
| LR-03 | **Vorlage enger:** `rueckblick.yaml` verliert `datei_schreiben` und `datei_aendern` und bekommt `rueckblick_schreiben`; `befehl` bleibt nur für Lesen über den Katalog (`git log*`, `git show*` sind frei). Die Vorlagendatei ist Vorbehalt; Änderung durch Claude mit Gate. | Test: Vorlage laden, Werkzeugliste |
| LR-04 | **Fakten zuerst:** Der Rückblick nutzt `belohnungen_lesen`, `erinnern` und, sobald gebaut, `wissen_suchen`. Fehlt eine Quelle, steht das im Bericht. | Prompt-Test mit Attrappe |
| LR-05 | **Messung:** Info-Seite zeigt Rückblicke, vorgeschlagene, angenommene und abgelehnte Regeln (aus dem Audit). | Test |

### 3.2 Werkzeug `rueckblick_schreiben` (W4)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| LR-10 | **Schema:** `{id: "AAR-JJJJ-MM-TT-<stichwort>", titel, bericht (Markdown, höchstens 30 Zeilen), regeln: [höchstens 5 Sätze, je höchstens 200 Zeichen], quelle: korrektur\|lob\|auftrag, belege: [antwort_id …]}`. Ungültiges → Fehler mit Satz, kein Antrag. | Test je Feld |
| LR-11 | Das Werkzeug **schreibt nichts**, es stellt einen Antrag `request:harness_lessons` in den Posteingang (wie `vorlage_beantragen`). Läuft ohne Karte (`OHNE_KARTE`), eine Katalogregel kann es nur mit `verboten` abschalten. | Test: keine Datei vor der Freigabe |
| LR-12 | **Klasse H:** Text, der in den Systemprompt kommt, ist eine dauerhafte Anweisung (wie ein Skill). Eintrag in `freigabeklasse.ARTEN`; die Freigabe geht durch die Tür von G9. | `test_freigabe_klasse`, `test_freigabe_vollstaendig` |
| LR-13 | **Auswahl im Posteingang:** Bericht ganz, jede Regel mit Haken; der Captain kann Regeln abwählen oder umformulieren. Ablehnen = nichts wird geschrieben. | Node-Test; Test der Anwendung |
| LR-14 | **Anwenden:** schreibt `docs/AAR/<ID>.md` (neu, nie überschreiben) und hängt je gewählte Regel eine Zeile `- JJJJ-MM-TT: <Regel> (Quelle: <ID>)` an `docs/AAR/LESSONS.md` (legt die Datei mit Überschrift an). Atomar; Audit `HARNESS_LESSONS_ANGENOMMEN {id, anzahl}`. | Test |
| LR-15 | **Budget:** Hätte `LESSONS.md` danach mehr als 25 Regelzeilen, zeigt der Antrag den Hinweis und schlägt vor, ältere Zeilen nach `docs/ARCHIVE/lessons.md` zu legen (eigene Auswahl, gleicher Antrag). | Test |
| LR-16 | **Vorbehalt:** `docs/AAR/**` wird fester Vorbehalt für `datei_schreiben`/`datei_aendern` (weder Karte-Erlaubnis noch Baustein noch Katalog öffnen ihn); der einzige Schreibweg ist LR-14. Hängt an E3 von `SPEC_FREIGABEN_S4_v1.md` (Vorbehaltsliste). | `test_harness_vorbehalte`; Gegenprobe Baustein `docs-aendern` |
| LR-17 | **Werkzeug-Regel** aus der UIX-Roadmap §3: Schema in `SCHEMAS`, Zweig in `vorbereiten`/`ausfuehren`, Eintrag in `HARNESS_WEGE`/`HARNESS_UNTERWEGE`/`ROUTEN_HARNESS`, Regex `WEG`/`GESCHUETZT` in `harness/api.py`, `OHNE_KARTE`, Test. | `test_freigabe_vollstaendig` |
| LR-18 | **Wissen:** Angenommene Berichte unter `docs/AAR/` können als Quelle ins Wissen (über `wissen_beantragen`, ein Gate je Projekt). Kein eigener Weg. | Test, sobald `wissen_beantragen` auf `main` ist |

### 3.3 Bessere Vorschläge beim Tippen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| VS-01 | **Schnell:** Der Index wird nur neu gelesen, wenn sich Änderungszeit oder Größe geändert haben (wie `Aufgaben.alle`). Ziel: Antwort unter 50 ms bei 2 000 Einträgen auf dem PC des Captains. | Test mit 2 000 Einträgen (Zeit als Messwert im Bericht, keine harte Grenze im Test) |
| VS-02 | **Korrektur schlägt Lob:** Ist eine Frage (gleiche Wörter ohne Füllwörter) nach ihrem Lob korrigiert worden, wird sie nicht mehr als ★ vorgeschlagen; es bleibt die ⚑-Warnung. | Test |
| VS-03 | **Eine Mindestlänge:** Der Server nennt `min_zeichen` in seiner Antwort; der Browser nutzt den Wert, 3 nur als Rückfall. | Node-Test |
| VS-04 | **Übernahme zählen:** Wird ein Vorschlag übernommen, schickt die Eingabe `aus_vorschlag: true` mit der Nachricht (kein neuer Weg). Info-Seite zeigt gezeigt/übernommen je Woche. | Test; Node-Test |
| VS-05 | **Weitere Quellen (X4), nach E-L2:** Vorlagen (Name und Beschreibung) und zuletzt genannte Dateien (`@pfad`) als zweite Gruppe unter den gelobten Aufträgen, höchstens 5 Zeilen insgesamt. | Node-Test |
| VS-06 | **„Nicht mehr vorschlagen“:** ein kleines × an jedem Vorschlag; `POST /api/harness/vorschlaege/entfernen {frage}` (Unterweg `entfernen` gibt es schon) merkt die Frage in `runtime_data/harness/belohnungen/_ausgeblendet.jsonl`. Handlung Klasse N (verengt nur). | Test; `test_freigabe_vollstaendig` |

### 3.4 Werkzeug `vorschlaege_pflegen` (W4)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| VP-01 | **Schema:** `{aktion: liste\|ausblenden\|einblenden, frage?}`. `liste` zeigt die häufigsten Vorschläge mit Zahl der Lobe und Korrekturen; `ausblenden`/`einblenden` wirkt wie VS-06. | Test |
| VP-02 | **Nur verengen, ohne Karte:** Ausblenden und Einblenden fügen keinen Text hinzu und ändern nichts, was das Modell liest; deshalb `OHNE_KARTE` und Klasse N. Ein Werkzeug, das Vorschläge **umformuliert oder anheftet**, wird nicht gebaut (E-L3). | Test: keine Schreibaktion außer `_ausgeblendet.jsonl` |
| VP-03 | Werkzeug-Regel wie LR-17. | `test_freigabe_vollstaendig` |

### 3.5 CPU-Hilfswerkzeuge: Dokumente lesen (W4/W5 des Plans, P2)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HW-01 | **Neuer Eintrag im Register:** `{id: pypdf, name: pypdf, art: paket, name_im_system: pypdf, zweck: "PDF zu Text (kleiner Rückfall, wenn MarkItDown fehlt)", install: "pip install pypdf", plan: W4}`. Der Installationstext von MarkItDown wird vor dem Bau gegen die aktuelle Fassung geprüft (Vermutung: PDF, Excel und PowerPoint brauchen Extras, etwa `pip install "markitdown[pdf,xlsx,pptx]"`). | `test_harness_hilfswerkzeuge` (22 Einträge, `pypdf` erkannt per Attrappe) |
| HW-02 | **Eine Lesefunktion** in `gateway/dokumente.py`: `.pdf`, `.xlsx`, `.pptx` über MarkItDown, falls installiert; `.pdf` sonst über `pypdf` (nur Text, ohne Layout); sonst Fehler `dokument_nicht_lesbar` mit Satz und Installationsbefehl. `.md`, `.txt`, `.docx` bleiben bei der Standardbibliothek. | Test mit Attrappen für beide Leser und für „keiner da“ |
| HW-03 | **Fremde Dateien lesen im eigenen Prozess:** Umwandlung in einem Unterprozess mit Zeitlimit (Vorschlag 60 s), Grenzen für Datei (20 MB) und Text (2 MB), begrenzten CPU-Threads (`max(2, Kerne // 2)`, wie beim Einbetter). Überschreitung oder Absturz → Fehler, kein halber Text (fail-closed). | Test mit Attrappe, die hängt oder abstürzt |
| HW-04 | **Ein Weg für alle Nutzer:** Vorgänge (GateWay), Wissens-Aufnahme und das Harness-Werkzeug `datei_lesen` nutzen dieselbe Funktion; der Text läuft wie jedes Dokument durch den Inhaltsschutz. `datei_lesen` kennzeichnet umgewandelten Text („umgewandelt mit MarkItDown“). | Test je Nutzer |
| HW-05 | **Nichts installieren:** Kein Code ruft `pip`, `winget` oder einen Download; die Seite „Hilfswerkzeuge“ zeigt den Befehl zum Kopieren und „wird genutzt für: Dokumente lesen“. | Test: Suche nach `pip install` im Aufrufpfad; Node-Test der Seite |
| HW-06 | **Lizenzen vor dem Einsatz prüfen** (Plan E3): MarkItDown und `pypdf` gelten als frei nutzbar (MIT bzw. BSD, aus dem Wissen des Verfassers, nicht geprüft); PyMuPDF (AGPL) wird nicht genutzt. | Eintrag `lizenz` im Register nach Prüfung |

### 3.6 CPU-Hilfswerkzeuge: Prüfen vor der Freigabe (F8)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HW-10 | **Diff-Karten zeigen „Syntax ok“ oder den ersten Fehler** vor dem Ja: `.py` mit `compile()` (Standardbibliothek, ohne Ausführen), `.json`/`.yaml` mit dem Parser, `.js` mit `node --check`, falls Node da ist. `ruff` nur, wenn installiert. | Test je Dateiart |
| HW-11 | Die Prüfung entscheidet nichts: Sie ist ein Hinweis auf der Karte, kein Grund für Frei oder Verboten. Läuft im eigenen Prozess mit Zeitlimit wie HW-03. | Test: fehlerhafte Syntax → Karte wie sonst, mit Hinweis |

## 4. Abnahme

1. Neue Tests je Anforderung; `test_harness_belohnung` (31), `test_harness_hilfswerkzeuge` (7), `test_freigabe_*` und `test_harness_vorbehalte` grün; ganze Bahn ohne Rot.
2. Gegenproben: (a) `docs/AAR/**` aus den Vorbehalten nehmen → Test LR-16 rot; (b) neues Werkzeug ohne Eintrag in `freigabeklasse.py` → `test_freigabe_vollstaendig` rot; (c) MarkItDown-Attrappe hängt → Fehler, kein Text.
3. Browser-Abnahme an einer eigenen Testinstanz: Knopf „Rückblick“ an ⚑, Antrag im Posteingang mit Haken je Regel, × an Vorschlägen.
4. **Im echten Sedra (nach U0):** ein Rückblick mit einer echten Korrektur, eine Regel angenommen, sie steht im Systemprompt der nächsten Sitzung; eine echte PDF über MarkItDown, falls der Captain es installiert hat.

## 5. Reihenfolge

| Stufe | Inhalt | Hängt an |
|---|---|---|
| **L-a** | Vorschläge: VS-01–VS-03 (klein, ohne neue Wege) | – |
| **L-b** | `rueckblick_schreiben` mit Antrag, Vorbehalt `docs/AAR/**`, enge Vorlage (LR-03, LR-10–LR-17) | E3 der Spec Freigaben S4 (Vorbehaltsliste) |
| **L-c** | Rückblick im Alltag: Knopf, Hinweis, Messung (LR-01, LR-02, LR-05) | L-b |
| **L-d** | Pflege: VS-04, VS-06, `vorschlaege_pflegen` | L-a |
| **H-a** | Register `pypdf`, Lesefunktion, eigener Prozess (HW-01–HW-06) | E1, E3, E4 des Plans |
| **H-b** | Prüfen vor der Freigabe (HW-10, HW-11) | – (Standardbibliothek) |
| **L-e** | Weitere Quellen (VS-05), Wissen (LR-04, LR-18) | E-L2; Wissen auf `main` |

L-a und H-b sind ohne Installation und ohne Entscheidung baubar. U0 (Alltagsprobe) liefert vorher die echten Lob- und Korrekturdaten.

## 6. Offene Entscheidungen des Captains

**Lernen**
- **E-L1 – Rückblick nur auf Knopfdruck?** Vorschlag: **ja**, nie automatisch (ein Rückblick ist ein Modelllauf; „unbeaufsichtigte Läufe nur auf Ja“).
- **E-L2 – Vorschläge aus Vorlagen und Dateien (VS-05)?** Vorschlag: **ja, nach L-a und U0**, wenn die Übernahme-Zahl (VS-04) zeigt, dass die Vorschläge genutzt werden.
- **E-L3 – Darf `vorschlaege_pflegen` Text hinzufügen (umformulieren, anheften)?** Vorschlag: **nein**, nur aus- und einblenden. Neuer Text wäre ein Antrag wie W4 und bringt wenig.
- **E-L4 – Klasse von `request:harness_lessons`:** Vorschlag **H** (dauerhafte Anweisung an das Modell, wie Skill).

**Hilfswerkzeuge (E1–E5 des Plans, mit Vorschlag)**
- **E1 – Python-Umgebung:** Vorschlag: **eigene Umgebung** `runtime/.venv-hilfen`, aufgerufen nur im Unterprozess (HW-03). Die Kern-Runtime bleibt schlank, ein kaputtes Paket bricht den Server nicht.
- **E2 – NER-Modell (W7):** Vorschlag: **nicht in U7**. Später nur als zusätzliche Stufe, die mehr findet und nie freigibt.
- **E3 – Lizenzen:** Vorschlag: **nichts mit AGPL oder GPL im Kern**; MarkItDown und `pypdf` vor dem Einsatz prüfen und die Lizenz ins Register schreiben (HW-06).
- **E4 – Speicherort:** Vorschlag: Programme in der eigenen Umgebung (E1); Modelldaten (später OCR, Reranker) unter `I:\KI-Daten\` wie die Sprachmodelle. Für W4 und `pypdf` sind keine Modelldaten nötig.
- **E5 – Reihenfolge:** Vorschlag: **F8 (H-b) vor W4 (H-a)**, weil F8 ohne Installation auskommt und jede Diff-Karte verbessert. Danach W4 mit MarkItDown und `pypdf`, dann F5 (trafilatura), dann W5 (OCR) und W3 (Reranker).

## 7. Rückfall und nächste Gates

Rückfall: Vorschläge lassen sich mit `vorschlaege: {an: false}` in `local_config/belohnung.yaml` abschalten; ohne `LESSONS.md` ändert sich der Systemprompt nicht; ohne MarkItDown und `pypdf` liest Sedra wie heute nur `.md`, `.txt` und `.docx`. Nächste Gates: G1 (dieses Dokument, Entscheidungen E-L1–E-L4 und E1–E5) → G2 Design → G3 Bau in der Reihenfolge §5 → G4 Abnahme im echten Sedra.
