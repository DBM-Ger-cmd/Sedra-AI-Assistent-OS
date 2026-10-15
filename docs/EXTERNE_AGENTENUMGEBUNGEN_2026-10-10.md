# Vergleich mit öffentlichen Agentenumgebungen für lokale Modelle (Recherche 2026-10-10)

Auftrag des Captains: nachsehen, ob jemand auf GitHub eine funktionierende Agentenumgebung dieser Art hat. Kurzfassung: **little-coder** (Apache-2.0) zielt auf genau unser Modell und unseren Server (Qwen3.6-35B-A3B, llama.cpp) und löst mehrere Probleme, die wir heute gemessen haben.

## little-coder (github.com/itayinbarr/little-coder)
Agent für kleine lokale Modelle auf Basis von `pi`; Aider-Polyglot (225 Aufgaben) mit Qwen3.5-9B: **45,56 %** gegen **19,11 %** für Aider mit demselben Modell (Aussage des Autors, ein Blogbeitrag, nicht begutachtet). Die Mechanismen:

| Mechanismus (little-coder) | Bei uns | Bewertung |
|---|---|---|
| **Write verweigert das Überschreiben bestehender Dateien** ("Write für neue Dateien, Edit für bestehende"); greift bei etwa 57 % der Aufgaben. Auch Shell-Umleitungen (`>`, `tee`) werden abgefangen. | `write_file` überschreibt ohne Frage. Beim Schritt 2 von `slots` erzeugte das Modell 39.000 Token in 17 Aufrufen (ganze Dateien mehrfach neu). | **Hoher Nutzen, billig.** Gleiche Ursache wie unsere Token-Verschwendung. |
| **Read-Schutz:** ein Lesen, das das Fenster sprengt, wird auf die ersten 30 Zeilen gekürzt, mit der Anweisung zu suchen. | `read_file` liest höchstens 150 Zeilen mit Kopfzeile (seit heute). | Haben wir sinngemäß. |
| **Edit verweigert, bis die Datei gelesen wurde.** | `edit_file` braucht den genauen alten Text. | Kein Bedarf. |
| **Denk-Budget** (2048 Token); bei Überschreitung abbrechen, Teil als Kontext behalten, ohne Denken neu anfragen. | `reasoning off` überall. | Nur für den Planer denkbar (Messung M4). |
| **Ausgabe-Reparatur:** kaputte Werkzeugaufrufe (Fenced-Block, `<tool_call>`, bares JSON) werden gelesen; **Qualitätswächter** für leere, erfundene und sich wiederholende Ausgaben, schickt eine Korrektur. | Schleifenwächter und `runaway`-Wächter stoppen den Lauf (Stoppgrund `loop`, `runaway`). | **Stoppen statt korrigieren:** bei uns ist ein `runaway` oder `loop` das Ende des Laufs, dort wird nur korrigiert, wenn das Rework greift. |
| **Kleine Zusatzkarten** (80 bis 150 Token je Werkzeug, höchstens 500 Token je Zug) nur bei passender Absicht; Kaltstart-Kontext etwa 7k Token. | Statischer Systemtext. | Später. |
| **Zweiter Versuch mit den fehlgeschlagenen Testausgaben**, etwa 18 % der bestandenen Aufgaben; ohne ihn 37,6 % statt 45,56 %. | Unser Rework mit Fehlerbericht (seit heute lesbar). | Gleiche Idee, bestätigt den Weg. |
| **Kompaktierung bei 80 % des Fensters**, Fenster wird vom Server gelesen. | Kompaktierung bei 60 %, Fenster aus der Option `--context`. | Gleich. |
| Temperatur 0,3 (Aider 0). | Standard 0,1. | Passt zur Messung M1 (Sampling). |
| Beispielserver: `--jinja -c 16384 -ngl 99 --n-cpu-moe 999 --flash-attn on`. | `n_cpu_moe 28`, 32k, Flash Attention aus (Abstürze auf dieser Karte). | Zeigt: kleineres Fenster plus alle Experten im RAM ist ihr Weg; bei uns bremst das Erzeugen. |

## Weitere Fundstellen (nicht vertieft)
- **OpenHands** (docs.openhands.dev): empfiehlt für lokale Modelle Qwen3-Coder-30B-A3B; **Kondensierer** fasst den Verlauf zusammen (Standard etwa 120 Ereignisse, die ersten 4 bleiben). Braucht ein großes Fenster; für uns zu schwer.
- **mini-swe-agent:** reiner Bash-Agent, linearer Verlauf, **keine** Verdichtung; läuft über litellm gegen llama.cpp. Der Verlauf läuft bei langen Läufen über.
- **Aider:** Architekt/Editor-Modus (ein Modell plant, eines setzt um), Repo-Karte mit Token-Budget (Standard 1024). Der Aider-Autor schreibt, dass Modelle ab etwa 25 bis 30k Token im Kontext „verwirrt" werden (Aussage, keine Messung).
- **llmm** (zsh-Hülle, Claude Code gegen lokalen llama.cpp-Server), **Hecker-Lab** (llama.cpp-Spielwiese mit MCP-Servern), Berichte: Qwen3.6-35B lief im Frage-Modus gut, schlug im Agent-Modus in GitHub Copilot oft in Schleifen um (ein Nutzer, Reddit, Juni 2026).

## Was ich daraus vorschlage (nichts davon gebaut)
1. **Schreiben nicht überschreiben:** `write_file` auf eine bestehende Datei von mehr als etwa 40 Zeilen wird abgelehnt mit der Anweisung: kleine Änderung `edit_file`, Anhängen `append_file`, ganz neu erst `delete_file`. Erwartung: weniger erzeugte Token, weniger Zeitlimit-Abbrüche. Messen mit am007 `slots`.
2. **Korrigieren statt stoppen** bei `loop`/`runaway`: statt den Lauf zu beenden, einmal eine kurze Korrektur schicken („du wiederholst dich, mach etwas anderes / gib ab").
3. Messungen M1 (Sampling, auch 0,3) und M4 (Planer mit begrenztem Denken) wie geplant.
Quellen: github.com/itayinbarr/little-coder, itayinbarr.substack.com/p/honey-i-shrunk-the-coding-agent, docs.openhands.dev, github.com/lukoshkin/llmm.

## Nachtrag: Durchsicht der lokalen Kopie `<projekte>\little-coder-main` (nur gelesen, nichts ausgeführt)
Gelesen wurden `docs/benchmark-qwen3.6-35b-a3b.md`, `docs/extensions.md`, `models.json`, `.pi/settings.json`, die Erweiterungen `write-guard`, `quality-monitor`, `thinking-budget` und die Werkzeug-Karten unter `skills/tools`.

**Messwert für UNSER Modell:** Qwen3.6-35B-A3B (UD-Q4_K_M, 22,1 GB) schafft im vollen Aider-Polyglot-Lauf (225 Aufgaben) **177 von 225 = 78,67 %** (Qwen3.5-9B: 44,9 bis 46,2 %). Start: `-ngl 99 --n-cpu-moe 999 --flash-attn on --jinja -c 32768`, RTX 5070 Laptop mit 8 GB, 3,8 GB VRAM belegt, rund 38 Token/s beim Erzeugen. 158 Aufgaben beim ersten Versuch, 19 im zweiten (Testausgabe als Kontext); Java 0 von 11 gerettet (ausführliche Testausgabe frisst den Kontext). Persönliche Anmerkung zur Übertragbarkeit: Aider-Aufgaben sind klein (eine Datei, die Tests liegen sichtbar im Ordner, der Agent darf sie mit `bash` laufen lassen); unsere versteckten, mehrstufigen Abnahmetests (am007) sind deutlich schwerer. Die Zahl zeigt, was das Modell mit gutem Gerüst kann, nicht was es bei am007 schafft.

**Konkrete Einstellungen** (`.pi/settings.json`, Profil `llamacpp/qwen3.6-35b-a3b`): Temperatur 0,3 (Terminal-Bench 0,2, GAIA 0,4), `max_tokens` 4096 je Antwort, **Denk-Budget 4096** (Terminal-Bench 3000, GAIA 2000), Karten-Budget 300 Token, Wissens-Budget 200 Token, ein Wiederholungsversuch, höchstens 40 Runden bei Terminal-Bench. Das Modell denkt also **mit Obergrenze**, wir lassen es ganz ohne Denken.

**Einzelheiten der Erweiterungen**
- `write-guard`: Schreiben auf eine **bestehende** Datei wird abgelehnt (egal wie groß), die Antwort enthält ein fertiges `edit`-Beispiel mit `oldText`/`newText` und den Satz "Do NOT retry Write". Das gilt auch für Shell-Umleitungen (`>`, `tee`, `dd of=`); Anhängen (`>>`) bleibt erlaubt. Zusätzlich: reservierte Windows-Gerätenamen (`nul`, `con`, `com1` ...) und ein Pfad `/datei.md` wird auf das Arbeitsverzeichnis umgeschrieben.
- Werkzeug-Karte `write`: "Write is for creating new files only"; für einen vollständigen Austausch darf `edit` die ganze Datei als `oldText` nehmen (kostet dieselben Token, ist aber eine bewusste Entscheidung). Die Karte `edit` kennt **mehrere Änderungen in einem Aufruf** (`edits[]`) und eine Wiederherstellungsregel ("String not found → neu lesen, `oldText` korrigieren; NICHT auf `write` zurückfallen").
- `quality-monitor`: erkennt leere Antwort, leeren/erfundenen Werkzeugnamen, kaputte Argumente (`_raw`) und eine **wortgleich wiederholte** Werkzeugaufruf-Folge; wiederholt der Agent einen Aufruf, nachdem ein zustandsändernder Aufruf (Edit, Write, Bash) lief, zählt das **nicht** als Schleife (Issue #81). Die Korrektur geht als Nachricht an das Modell, der Lauf endet nicht.
- `thinking-budget`: zählt Denk-Token (Zeichen / 3,5); bei Überschreitung wird Denken **ausgeschaltet**, eine Nachricht "Please commit to an implementation now" angehängt und der Zug abgebrochen; das Denken bleibt für den Rest der Aufgabe aus.
- Kaltstart-Kontext etwa 7k Token; eine zentrale Regel: den **Systemtext nie pro Zug ändern**, weil das den gesamten zwischengespeicherten Anfang entwertet (Issue #73); Zusatztexte kommen als Nachricht.
- Wissenskarte `workspace_docs`: vor nicht trivialen Änderungen einmal `AGENTS.md`/`README.md`/`SPEC.md` lesen (140 Token).

**Was ich für uns daraus ableite (Reihenfolge nach Nutzen / Aufwand)**
1. `write_file` auf bestehende Dateien ablehnen, mit fertigem `edit_file`-Beispiel und Wiederherstellungsregel (klein, direkt gegen unsere 39.000-Token-Fälle).
2. `edit_file` mit mehreren Änderungen je Aufruf (`edits[]`): weniger Aufrufe, weniger Verlauf.
3. Wächter: bei `loop`/`runaway` zuerst eine Korrekturnachricht senden (einmal), erst dann beenden; Wiederholung nach einer Änderung nicht als Schleife zählen (wir haben das für Lesewerkzeuge über das Ergebnis, nicht für `run_python`).
4. Denk-Budget mit Abbruch und Wiederholung ohne Denken, zuerst nur für den Planer (Messung M4 erweitern).
5. Kleine Werkzeug-Karten nach einem Fehler statt langem Systemtext.
Nichts davon ist gebaut.
