# Plan: Hilfswerkzeuge auf der CPU auslagern (04.11.2026)

Auftrag des Captains: Werkzeuge wie WhisperX finden, die auf der CPU laufen und Sedra helfen; faster-whisper als Provider vorbereiten, die übrigen einbinden; ein Plan, welche weiteren Funktionen sich so auslagern lassen. Dieser Plan ist ein **Entwurf**: Versionen, Kommandozeilen und Lizenzen stammen aus dem Wissen des Verfassers und sind vor dem Einsatz zu prüfen; Messungen auf diesem Rechner gibt es noch keine.

## 1. Warum

Der Rechner hat 12 GB Grafikspeicher; ein Modell wie Gemma braucht rund 9,4 GB samt Reserve (im Audit steht `vram_insufficient` für `verifier.llama_gemma`). Alles, was ein Hilfswerkzeug auf der CPU erledigt, nimmt dem Modell nichts weg und spart Token, weil Sedra ein festes Ergebnis statt einer Modell-Antwort bekommt.

## 2. Was es schon gibt (nicht doppelt bauen)

| Bereich | Stand im Repo |
|---|---|
| Sprache → Text | `sprache/stt.py`: Provider `whisperx` (nutzt schon faster-whisper, CPU mit int8 möglich), `whisper`; **neu:** `faster-whisper` (Kommandozeile `whisper-ctranslate2`, CPU int8, ohne PyTorch) |
| Wissen: Einbetten | `config/wissen.yaml`: eigener `llama-server --embeddings`, **nur CPU**, BGE-M3, dazu Wort-Suche und Fusion (`fusion.k`, `w_vektor`, `w_wort`) |
| Pseudonymisieren | `core/b6core/pseudo.py`: Regeln ohne KI, nur Standardbibliothek; bekannte Grenze `NAMEN_AUSSERHALB_DER_REGELN` |
| Dokumente lesen | `gateway/dokumente.py`: `.txt`, `.md`, `.docx` (Standardbibliothek); **kein PDF** |
| Token schätzen | `harness/kontext.py` `schaetzen()`: Schätzung, kein Zähler |

Ehrliche Korrektur zum ersten Vorschlag: „Embeddings über ONNX“ ist für das Wissen nicht nötig (läuft schon auf der CPU); neu wäre nur ein **Reranker**, und der könnte über denselben `llama-server` laufen (Option `--reranking`, vor dem Bau gegen die verwendete Server-Version prüfen).

## 3. Die angefragten Werkzeuge

| Nr | Werkzeug | Wofür | Ort im Code | Stand |
|---|---|---|---|---|
| W1 | faster-whisper (`whisper-ctranslate2`) | Rekorder und Transkripte auf der CPU | `sprache/stt.py` | **vorbereitet** mit Test `tests/test_sprache_stt.py`; nichts installiert |
| W2 | Silero VAD | Stille abschneiden vor dem Whisper-Lauf, weniger erfundene Sätze | `sprache/stt.py` oder `sprache/kern.py` | Plan |
| W3 | Reranker (bge-reranker-v2-m3) | Treffer des Wissensspeichers neu ordnen | `knowledge.py` / `wissen/` | Plan, siehe Abschnitt 2 |
| W4 | Docling oder MarkItDown | PDF, Excel, PowerPoint zu Markdown für Vorgänge und Wissen | `gateway/dokumente.py`, Wissens-Aufnahme | Plan |
| W5 | RapidOCR oder Tesseract | Scans und Bilder lesen | neben W4 | Plan |
| W6 | Piper | Sedra liest Antworten vor | neue Quelle „Ton aus“ im Kern Sprache | Plan |
| W7 | Presidio mit spaCy (de) | zusätzlicher Erkenner für Namen und Orte im GateWay | `core/b6core/pseudo.py` als **weitere Stufe** | Plan, Entscheidung E2 |
| W8 | Argos Translate oder OPUS-MT (CTranslate2) | Übersetzung Sprache → Sprache ohne Modellaufruf | `fisch/uebersetzer.py` | Plan |

## 4. Weitere Funktionen, die sich auslagern lassen (bisher nicht bedacht)

Jede Zeile ersetzt eine Modell-Antwort durch ein festes, prüfbares Ergebnis.

| Nr | Funktion | Werkzeug | Nutzen für Sedra |
|---|---|---|---|
| F1 | **Geheimnis-Scan** vor Commit, Antwort und Export | detect-secrets oder gitleaks | ergänzt die Schutzregeln (`.env`, `local_config`, Schlüssel); Fund = Freigabe nötig |
| F2 | **Sprache erkennen** | lingua-py oder fastText-LID | Rekorder und Übersetzer raten `de`/`en` selbst, statt nur auf Angabe zu laufen (LocalScribe-Regel: Angabe des Captains bleibt Vorrang) |
| F3 | **Zusammenfassen ohne Modell** (extraktiv: TextRank, YAKE) | sumy, yake | Rückfall, wenn die Zusammenfassung des früheren Gesprächs leer bleibt (Fehler `zusammenfassung_leer` vom 03.11.) |
| F4 | **Exakter Token-Zähler** | `POST /tokenize` des laufenden `llama-server` | `kontext.schaetzen()` bekommt echte Zahlen; kein neues Paket |
| F5 | **Web-Seite zu Text** | trafilatura | HTML-Rauschen nicht an das Modell schicken (`config/web_access.yaml`), spart viele Token |
| F6 | **Tabellen abfragen** (CSV, Excel) | DuckDB | Kundenanfragen und Wissen: SQL statt „Tabelle lesen lassen“; das Modell schreibt nur die Frage |
| F7 | **Rechnen, Einheiten, Daten** | sympy, pint, dateparser | Modelle rechnen schlecht; ein Werkzeug `rechnen` liefert das Ergebnis |
| F8 | **Prüfen vor Freigabe**: Syntax, Format, Lint | ruff, `node --check`, yamllint, JSON-Schema | Diff-Karten zeigen „Syntax ok“ vor dem Ja des Captains |
| F9 | **Ähnliche Einträge finden** (Duplikate) | rapidfuzz, MinHash | Chat-Liste aufräumen, doppelte Wissensvorschläge, Logbuch |
| F10 | **Repo-Karte und Codesuche** | tree-sitter, ctags, ripgrep | Agenten bekommen Überblick ohne ganze Dateien zu laden |
| F11 | **Rechtschreibung und Grammatik** | LanguageTool (offline, Java) | Prüfstufe für Übersetzer, Entwürfe und Kundenantworten |
| F12 | **Audio vorbereiten** | ffmpeg (Rauschen, Lautstärke), RNNoise | bessere Abschrift bei schlechtem Mikrofon |
| F13 | **Zusätzliche Schutzstufe** gegen Prompt-Injection | kleines ONNX-Klassifikationsmodell | weitere Stufe im Inhaltsschutz; nur additiv, nie als Ersatz der Regeln |
| F14 | **Zeitplan lesen** | croniter | Routinen: nächste Läufe berechnen und anzeigen |

## 5. Bauweise (ein Muster für alle)

Nach dem Vorbild von `sprache/stt.py`:
- **Erkennung statt Zwang:** ein Werkzeug ist da, wenn `which`/`import` es findet; sonst ein **Platzhalter** mit Grund und Installationsbefehl (nie ein Absturz).
- **Rein und testbar:** `which` und `run` sind Parameter; Tests geben Attrappen, brauchen keine Installation.
- **Fail-closed:** ein Fehler des Hilfswerkzeugs lässt den Vorgang nicht stillschweigend weiterlaufen.
- **Ein Verzeichnis, eine Konfiguration:** `config/hilfswerkzeuge.yaml` (id, Programm, Installationsbefehl, Lizenz, Größe, `cpu_threads`, an/aus) und in der Harness eine Seite „Hilfswerkzeuge“ (Einstellungen → Integrationen) mit Status je Werkzeug.
- **CPU-Last begrenzen:** Threads wie beim Einbetter (`max(2, Kerne // 2)`), Absprache mit `config/resource_scheduler.yaml`; ein Lauf hat Zeitlimit.
- **Installation ist eine Freigabe:** Herunterladen und Installieren nur nach ausdrücklichem Ja des Captains (Netz, Größe und Lizenz vorher nennen).

## 6. Reihenfolge

1. **P0 (erledigt):** W1 als Provider vorbereitet, getestet.
2. **P1:** Register und Seite „Hilfswerkzeuge“ (nur Erkennung und Status, keine Installation); F4 (Token-Zähler über `/tokenize`) und F3 als Rückfall der Gesprächs-Zusammenfassung, weil beide nichts Neues installieren.
3. **P2:** W4/W5 (Dokumente lesen) und F5 (Web-Text), dann F8 (Prüfen vor Freigabe).
4. **P3:** W3 (Reranker), W2 (VAD), F2 (Spracherkennung).
5. **P4:** W6, W8, F6, F7, F9 bis F14 nach Bedarf.
6. **P5:** W7 und F13 nur nach Entscheidung E2.

## 7. Entscheidungen des Captains

- **E1 Installation:** in welche Python-Umgebung (`runtime/.venv` oder eine eigene für Hilfswerkzeuge)? Vorschlag: eine eigene, damit die Kern-Runtime schlank bleibt.
- **E2 Namen-Erkennung mit Statistik-Modell (W7):** `pseudo.py` ist bewusst „ohne KI“ und deterministisch. Ein NER-Modell wäre eine **zusätzliche** Stufe, die nur mehr findet, nie etwas freigibt. Erlaubt?
- **E3 Lizenzen:** Vorschlag, nichts mit AGPL oder GPL im Kern einzubinden. Zu prüfen unter anderem: PyMuPDF (AGPL), Piper (neuere Fassungen GPL), NLLB-Gewichte (nicht kommerziell), jeweils vor dem Einsatz.
- **E4 Speicherort der Modelle und Daten:** unter `I:\KI-Daten\` wie die Sprachmodelle?
- **E5 Reihenfolge:** passt P1 bis P5, oder soll ein Punkt vor?

## 8. Offen / nicht belegt

- Kein Werkzeug ist installiert oder gemessen; Zeiten und Speicherbedarf fehlen.
- Die Flags von `whisper-ctranslate2` (`--device`, `--compute_type`, `--output_format`) sind aus dem Wissen übernommen und gegen die installierte Fassung zu prüfen, sobald es installiert wird.
- Ob die verwendete `llama-server`-Fassung `--reranking` und `/tokenize` bietet, ist zu prüfen.
