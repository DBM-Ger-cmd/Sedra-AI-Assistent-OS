# Prüfung Spec 7 – Code gegen Plan, Fehler, Lernquellen (23.10.2026)

Stand: `main` = `9a41b61` (Spec 7 ist über `090dc3f`, `e3045c9`, `fc2d218` gemergt). Geprüft wurde das Paket `runtime/src/guppi_runtime/wissen/` (13 Module, 2780 Zeilen) mit den Einschüben in `desk/orchestra_runner.py` und `runtime.py`. Grundlage waren Design D7.0–D7.13, der Baubericht und die G4-Auflagen vom 22.10. Python 3.13, ohne Modell und ohne VM.

**Testlauf:** 119 Tests (`test_wissen_*` und die drei alten Speicher) sind grün. Die Gegenprobe der Bau-Specs besteht 16 von 16 Stufen. Die Befunde unten sind mit eigenen Probeskripten auf der Test-Fixture nachgestellt. Bestehende Tests decken keinen davon ab.

## 1. Befunde im Code

| Nr | Schwere | Befund | Nachweis | Vorschlag |
|---|---|---|---|---|
| F1 | **hoch** | **Die Runtime startet nicht, wenn `wissen` an ist und der Ordner nicht anlegbar ist.** `WissenSpeicher.oeffnen` fängt nur `sqlite3.Error`, und `Runtime._optional` fängt nur `ValueError`. Ein `OSError` aus `mkdir` (Rechte, Datei statt Ordner, Laufwerk weg) beendet den ganzen Start. Das ist G4-Auflage (3), noch offen. | `local_config` als Datei angelegt → `NotADirectoryError` fliegt durch | In `oeffnen` auch `OSError` auf `wis_speicher_nicht_lesbar:` abbilden; das Gleiche für `TestLab(...)` in `_configure_wissen` |
| F2 | **hoch** | **Ein einziger Abschnitt, den der Server ablehnt, stoppt das Einbetten für immer.** `offene_vektoren` liefert immer dieselben ersten 16 Abschnitte nach `nr`. Scheitert der Stapel (z. B. Text über der Kontextlänge oder HTTP 500), scheitert jeder weitere Schritt am selben Stapel. Die Abdeckung bleibt dann bei 0 % und die Suche dauerhaft im Volltext. | Ein Abschnitt mit „GIFT“ lässt den Fake scheitern → 3 Schritte, je `fehler`, Abdeckung 0,0, Modus `volltext` | Bei Stapelfehler einzeln nachbetten; einen Abschnitt, der allein scheitert, in eine Liste `vektor_fehler` (nr, hash, grund) setzen und überspringen; Audit `WIS_ABSCHNITT_NICHT_EINBETTBAR` |
| F3 | **hoch** | **Die Suche wartet, solange eingebettet wird.** `einbetten_schritt` und `nachfuehren` halten `self.lock` über den ganzen Schritt (bis `schritt_s` = 120 s). `anfrage_vektor` kann unter derselben Sperre einen Kaltstart machen (bis 90 s) und die Prüfsumme über 635 MB rechnen. Captain und Agenten hängen in der Zeit. Das Design rechnet mit 5 s je Anfrage (D7.4). Das ist G4-Auflage (4), noch offen. | Mit verzögertem Fake wartete eine Suche 8,7 s auf den laufenden Schritt | Sperre nur um die DB-Zugriffe je Stapel nehmen (lesen, Server ohne Sperre, schreiben). In `suche` nie starten: läuft der Server nicht, sofort Volltext mit Hinweis und den Start im Takt anstoßen |
| F4 | **hoch (Qualität)** | **Das Logbuch steht doppelt im Index.** Die Erstbestückung gibt den Ordner `docs` mit `*.md` frei, und darin liegt `docs/LOGBUCH_AGENT_MANAGER.md`. Dazu kommt das Logbuch als eigene Quelle. Am heutigen Repo sind das **404 zusätzliche Tabellen-Abschnitte** (2854 Doku-Abschnitte, davon 404 Logbuch) neben den 447 Logbuch-Zeilen. Die Kopien besetzen Plätze unter den Top 5, zählen im Abnahmesatz aber nicht als Treffer, weil der Adapter `markdown` statt `logbuch` ist. Das Messskript S7.2-F nutzt dieselbe `ERSTBESTUECKUNG`. | Suche „Werkbank Bau“: Rang 1 ist der Markdown-Abschnitt des Logbuchs, Rang 2 und 3 die Logbuch-Zeilen | **Vor S7.2-F beheben:** `DateiAdapter` schließt Pfade aus, die eine andere aktive Quelle schon abdeckt; oder in `ERSTBESTUECKUNG` ein Ausschluss `!LOGBUCH_AGENT_MANAGER.md`. Sonst friert die Fusion auf einem verzerrten Korpus ein |
| F5 | mittel (WIS-11) | **Ein Vorschlag erbt den Personenbezug nur von den Belegen, die der Agent selbst angibt.** Lässt ein Agent `belege` leer, obwohl sein Block einen Treffer mit Personenbezug hatte, bekommt der Vorschlag `personenbezug = 0`. Nach der Freigabe wäre der Text damit für die Cloud-Route sichtbar. Die Entscheidungskarte zeigt nur `describe`, siehe Baubericht. | Agent Stufe 3, Block mit `gateway#eigene` → Vorschlag ohne Belege → `personenbezug = 0` | Personenbezug aus **allen** IDs des Blocks erben (`block_ids`), nicht nur aus `belege`; die Stufe ebenso mindestens als Maximum der Block-Quellen |
| F6 | mittel | **Dateien werden nicht atomar geschrieben (G4-Auflage 1, offen).** `vorschlaege.jsonl` bekommt die Zeile **vor** dem Statuswechsel in der DB. Stürzt danach etwas ab, ist der Text bei der nächsten Aufnahme Wissen, der Vorschlag steht aber noch auf „offen“. `vorschlag_zuruecknehmen` und `nachmessung_bewerten` schreiben die Datei per `write_text` neu. `nachmessung_bewerten` läuft außerdem **ohne** `self.lock`, während `_protokolliere` unter der Sperre anhängt; ein gleichzeitiger Eintrag kann dabei verloren gehen. Eine kaputte Zeile in `vorschlaege.jsonl` lässt `zuruecknehmen` mit `JSONDecodeError` scheitern. | Code-Lesung (`speicher.py` 554–564, 585–588, 620–627) | Temp-Datei + `os.replace`; Reihenfolge: DB-Status zuerst („freigegeben_ausstehend“) → Datei → Abgleich; Sperre um alle Datei-Schreiber; kaputte Zeilen überspringen |
| F7 | mittel | **Symlinks und Junctions werden nur bei der Freigabe geprüft (G4-Auflage 2, offen).** `_dateien` schließt nur Datei-Symlinks aus. Ordner-Junctions unter Windows sind für `is_symlink()` keine Symlinks; `rglob` folgt ihnen. Ein Pfad aus der Wurzel hinaus wird so beim Abgleich mit aufgenommen. | Code-Lesung (`adapter.py` 114–118); Test für Symlinks oder Junctions fehlt | Je Datei `p.resolve()` gegen die Wurzel prüfen, `is_junction()` (ab 3.12) ausschließen |
| F8 | niedrig | `_antrag_von` fällt still auf `"gated"` als Gate- und Missions-ID zurück (G4-Auflage 6, offen). Die Quelle trägt dann keine echte Freigabe-ID, und D7.2 verlangt diese. | Code-Lesung | Ohne gefundenen Antrag `ValueError('wis_antrag_unbekannt')`, damit der Applier nichts anlegt |
| F9 | niedrig | `speicher.py` hat weiter 646 Zeilen (G4-Auflage 5, offen). Die Docstring-Regel „jede öffentliche Methode nimmt `self.lock`“ stimmt nicht: `quelle`, `quellen`, `vorschlag`, `vorschlaege` und `nachmessung*` lesen bzw. schreiben ohne Sperre auf der geteilten Verbindung. | Code-Lesung | Beim Teilen (Quellen/Aufnahme, Suche, Vorschläge, Nachmessung) die Sperre einheitlich setzen |
| F10 | niedrig | Logbuch-Zeilen werden nie geteilt. Die längste Zeile hat heute 1834 Zeichen, also über `MAX_ZEICHEN` 1600. Mit 8192 Token Kontext ist das kein Fehler, verletzt aber die Regel aus D7.3. Zusammen mit F2 könnte eine sehr lange Zeile das Einbetten blockieren. | `awk` über das Logbuch | `zerlege_logbuch` über `_schneide` teilen |
| F11 | niedrig | `anfrage_vektor` und `lauf` fangen nur `ValueError`. Ein `OSError` aus `pruefsumme()` (GGUF gerade verschoben) oder `http.client.IncompleteRead` geht durch. In der Suche des Captains wird daraus HTTP 500; der Lauf ist durch `_wissensblock` geschützt. | Code-Lesung (`embed.py` 335–343) | `except (ValueError, OSError, http.client.HTTPException)` → Volltext |

**Unauffällig:**
- FTS5-Anfragen mit Sonderzeichen: `__init__`, `c++`, `NEAR(…)`, `ab*`, Umlaute, Hochzahlen. Alle zehn Proben liefen ohne Fehler.
- Rechtefilter vor dem Ranking (Stufe, Projekt, aktiv, Cloud).
- Migrationen und Modellwechsel.
- Säuberung der Kopfzeile.
- Zitatprüfung.
- `route_von` fällt sicher auf `cloud` zurück.

## 2. Plan gegen Code

- **Gebaut wie geplant (mit den 13 dokumentierten Abweichungen):** D7.1–D7.9 und WIS-01 bis WIS-13 auf Testebene.
- **Offen laut Plan:**
  - A-5 (CPU-Server ohne VRAM) auf dem PC
  - S7.2-F-Messung mit BGE-M3 auf der CPU
  - die 13 umgeschriebenen Fragen des Captains (G2-S7-n)
  - die KN-IDs im Abnahmesatz
  - S7.5 und S7.4b
- **Alle sechs G4-Auflagen sind unerledigt.** Seit `fc2d218` gibt es keinen Commit im Paket `wissen/`. Laut G4 müssen sie vor dem Einschalten von `wissen` erledigt sein; F1, F3, F6, F7, F8 und F9 oben sind genau diese Auflagen.
- **Neu gegenüber der G4-Prüfung:** F2 (Gift-Abschnitt), F4 (doppeltes Logbuch), F5 (Personenbezug über Vorschläge), F10, F11.

**Empfohlene Reihenfolge:**
1. F4, weil S7.2-F sonst auf falschem Korpus misst.
2. F1, F2, F3.
3. Die restlichen Auflagen F6–F9 und die Tests (Symlink/Junction, Abbruch zwischen Datei und DB, Sperre beim Start, OSError, Abschnitt über der Grenze, Gift-Abschnitt, Vorschlag ohne Belege).
4. A-5 und S7.2-F auf dem PC.

## 3. Was wir von GitHub lernen können (Recherche 23.10.2026)

Die Recherche hat 18 Projekte geprüft. Nicht geprüft wurden AnythingLLM, R2R, llmware, haystack, semantic-router und rebuff.

Die fünf größten Hebel für Treffer@5 (heute 77,5 %, Ziel 85 %), ohne neue Python-Abhängigkeit:

1. **Lokaler Reranker als dritter Schritt.**
   - Ein zweiter `llama-server --reranking` mit `bge-reranker-v2-m3` (GGUF Q8_0, 636 MB, Apache-2.0) über `/v1/rerank` auf den Top 20–30 der RRF.
   - Fail-open: Bei Fehler oder Zeitüberschreitung bleibt die RRF-Reihenfolge.
   - Eigener Prozess, weil `--embeddings` und `--reranking` nicht zusammen laufen.
   - Vorsicht: llama.cpp Issue #16407 meldet abweichende Reihenfolgen und wirkt offen; deshalb am Goldsatz messen und den KV-Cache nicht quantisieren.
   - Vorbild ist Anthropic Contextual Retrieval: Die Fehlerrate bei Top-20 sinkt mit Reranker um 67 % statt 49 %.
2. **Mehr Suchtext je Abschnitt („Contextual Retrieval“).**
   - Ein fester Vorspann aus Dokumenttitel, Überschriftenpfad und bei Tabellen „Spalte: Wert“, optional 50–100 Token Kontext vom lokalen Modell, vor dem Einbetten **und** im FTS-Text.
   - Dazu 2–3 erzeugte deutsche Fragen je Abschnitt (Muster aus RAGFlow „Auto-Questions“). Das hilft bei englischen Lektionen und umschriebenen Fachbegriffen.
3. **Zweites FTS5-Feld mit zerlegten deutschen Komposita und Stammformen.**
   - „Videospeicher“ wird dort zu „video speicher“: Kompositazerlegung nach CharSplit (MIT, nachbaubar), Stemmer aus Snowball (BSD).
   - Die Frage wird genauso vorverarbeitet, das Originalfeld bleibt für exakte Treffer.
4. **Glossar und Synonymtabelle** (VRAM ↔ Videospeicher, englisch ↔ deutsch).
   - Erweitert die FTS-Frage mit ODER, gefüllt aus den Fehlgriffen im Goldsatz.
   - Kleinster Aufwand, trifft genau die gemessenen Schwächen.
5. **Messung schärfen.**
   - Recall@20 zusätzlich messen: Er zeigt, ob ein Reranker überhaupt etwas findet, das er hochholen kann. Dazu nDCG@10.
   - Ein gepaarter Test bei der Rastersuche, Muster aus ranx.

**Für die Sicherheit (WIS-08):** „Spotlighting/Datamarking“ (Microsoft, 2024). Im untrusted-Block werden Leerzeichen durch ein Markierungszeichen ersetzt. Im Paper sank die Angriffsquote bei GPT-3.5 von rund 50 % auf 3,1 %; mit dem lokalen Modell nachmessen.

**Nicht passend für SEDRA:**
- LightRAG und nano-graphrag: brauchen ein großes LLM zum Indizieren.
- khoj: AGPL.
- kotaemon: Reranking nur über die Cloud.
- ARES: vLLM und A100.
- LLM Guard: archiviert.
- sqlite-vec: bestätigt das Design, wäre aber eine neue native Abhängigkeit.

## 4. Übertrag: Wissensdatenbank für ein Architekturbüro

Der Kern passt direkt: lokaler Speicher, Freigabe je Quelle, Rechte je Projekt, Zitate mit Fundstelle, Personenbezug bleibt lokal, Agenten dürfen nur vorschlagen. Für ein Büro fehlen vor allem diese Teile:

| Bedarf im Büro | Stand SEDRA | Was dazukäme |
|---|---|---|
| PDF (Baubeschreibungen, Gutachten, Protokolle), Scans | nur `*.md`/`*.txt` (G1-S7-c) | PDF-Adapter mit Text je Seite (Stelle = Datei > Seite), OCR für Scans |
| Pläne, CAD/BIM (DWG, IFC) | – | zuerst nur Metadaten und Planköpfe (Plannummer, Index, Maßstab, Geschoss); IFC-Attribute als Tabelle |
| Excel (Kostenschätzung, Raumbuch) | – | Tabellen-Adapter: Zeile = Abschnitt mit Spaltennamen (Muster wie unsere Tabellenregel) |
| E-Mails, Bauherrenkorrespondenz | – | Postfach-Adapter mit Personenbezug = ja, nie Cloud |
| Projektstruktur (Projektnummer, Leistungsphase, Gewerk) | `projekt` je Quelle | Metadaten-Filter je Abschnitt (Projekt, Leistungsphase, Bauteil, Datum) zusätzlich zur Volltextsuche |
| mehrere Mitarbeitende | ein Captain, Agenten mit Stufe | Benutzer und Rollen (Inhaber, Projektleitung, Mitarbeit, Praktikum) auf die Stufen abbilden |
| Normen und Richtlinien (DIN, LBO) | – | eigene Quelle; die Lizenzbedingungen gekaufter Normen vor dem Indizieren prüfen (kein Rechtsrat) |
| „Wie haben wir das beim Projekt X gelöst?“ | Lernschleife Vorschlag → Freigabe | Lessons Learned je Projektabschluss als Vorschlag, Freigabe durch die Projektleitung |

**Einschätzung:** Ein Büro-Pilot wäre ein guter Härtetest für Spec 7. Dafür müssten zuerst F1–F4 erledigt sein, dann kämen ein PDF- und ein Tabellen-Adapter dazu. Die Rechte-Logik (Stufe, Projekt, Personenbezug) trägt schon; neu ist die Mehrbenutzerfähigkeit.

## 5. Hinweis

Das Repo `DBM-Ger-cmd/Sedra-AI-Assistent-OS` ist **öffentlich**. Specs, Logbuch und die Commit-Autoren-Adresse sind für jeden lesbar. Falls das nicht gewollt ist: auf GitHub unter Settings → Danger Zone auf „Private“ stellen.

## 6. Umsetzung (Branch `fix/spec7-pruefung-2026-10-23`)

| Nr | Stand | Änderung |
|---|---|---|
| F1 | behoben | `WissenSpeicher.oeffnen` fängt `OSError`; `_configure_wissen` fängt Fehler beim Öffnen des Testlabors (`wis_testlab_nicht_lesbar`) – beides schaltet nur `wissen` aus |
| F2 | behoben | `EmbeddingDienst.lauf(…, markiere=)`: Stapelfehler → einzeln nachbetten; ein Abschnitt, der allein scheitert, wird im Prozess gemerkt und übersprungen (`WIS_ABSCHNITT_NICHT_EINBETTBAR`); antwortet der Server nicht mehr, bleibt es `fehler` |
| F3 | behoben | Sperre nur um DB-Zugriffe; `einbetten_schritt` ohne Sperre über Start und Stapel, zweiter gleichzeitiger Schritt → `beschaeftigt`; `suche` holt den Anfrage-Vektor ohne Sperre und ohne Start (`anfrage_vektor(starten=False)`), läuft kein Server: Volltext mit Grund `server_startet` und Start im Hintergrund; `starte` unter eigener Sperre |
| F4 | behoben | Ordner-Quellen (`markdown`/`text`) lassen Dateien aus, die eine andere aktive Datei-Quelle derselben Wurzel abdeckt; der Ausschluss geht in den Quell-Hash ein (Abschalten des Logbuchs holt es in den Ordner zurück) |
| F5 | behoben | Vorschlag erbt Personenbezug aus allen IDs des Blocks |
| F6 | behoben | `vorschlaege.jsonl`, Nachmessung und Ergebnisdatei atomar (Temp-Datei + `os.replace`); Status und Datei in einer Transaktion; Nachmessung unter `self.lock`; kaputte JSON-Zeilen werden übersprungen |
| F7 | behoben | Adapter prüfen je Datei und je Speicherdatei `resolve()` gegen die Wurzel und lassen Symlinks und Junctions (`is_junction`, ab 3.12) aus |
| F8 | behoben | `_antrag_von` ohne stillen Rückfall: `wis_antrag_unbekannt` |
| F9 | teilweise | Lesezugriffe (`quelle`, `quellen`, `vorschlag`, `vorschlaege`, `nachmessung`) unter `self.lock`; **das Teilen von `speicher.py` (G4-Auflage 5) ist nicht Teil dieses Patches** |
| F10 | behoben | `zerlege_logbuch` teilt Zeilen über `MAX_ZEICHEN` (Teile 1, 2, …) |
| F11 | behoben | `anfrage_vektor`, `lauf`, `einbette`, `starte` fangen auch `OSError`/`http.client.HTTPException` und kaputtes JSON |

Tests: neu `tests/test_wissen_pruefung.py` (16 Prüfungen, 12 davon scheitern auf `main`); in `test_wissen_speicher.py` und `test_wissen_einbetten.py` sinkt die Zahl der Abschnitte der Fixture von 13 auf 12, weil das Logbuch nicht mehr doppelt aufgenommen wird. Lauf hier (Python 3.13, ohne Modell): 43 Testmodule (`test_wissen_*`, `test_desk_*`, `test_orchestra*`, `test_uix_contract`, `test_uix_shell_d_pure`, `test_core_boundary*`, `test_arbeitsplatz`, `test_local_switches`, `test_runtime*`, die drei alten Speicher) **585 Tests OK**; Gegenprobe der Bau-Specs 16/16 ok; `wissen_fusion_messung.py --fake` result ok.

Auf dem PC nachzuholen: Windows-Junction praktisch prüfen (`mklink /J` in `docs`), `uix_check --tool wissen`, danach A-5 und S7.2-F. Wegen F4 ändert sich der Korpus: S7.2-F muss mit diesem Stand messen.
