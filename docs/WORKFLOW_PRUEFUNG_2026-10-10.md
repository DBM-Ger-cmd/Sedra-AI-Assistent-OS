# Prüfung des Workflows, des Schritt-Plans und der Anpassung an unsere Modelle (2026-10-10)

Auftrag des Captains: bevor weitere Aufgaben in die Warteschlange kommen, den Schritt-Plan und die weiteren Möglichkeiten prüfen, auf die vorhandenen Modelle anpassen, und den Workflow mit den Agenten allgemein ansehen. Stand: kein neuer GPU-Lauf gestartet, Gate HG-4F2EF52F (am007 mit verbesserten Schritt-Plänen) liegt vor und ist **nicht** freigegeben.

## 1. Was die Zahlen über den Workflow sagen

| Befund | Beleg | Folge |
|---|---|---|
| Die Zeit besteht fast nur aus **Erzeugen**, nicht aus Einlesen. | am009 solo: 24.050 erzeugte Token bei 34 Token/s = 707 s = die gesamte Laufzeit, obwohl 428.000 Prompt-Token zusammenkamen. Der Prompt-Cache trägt also. | Der wachsende Verlauf kostet **kaum Zeit**, aber **Fenster** (32k) und damit Fehler (HTTP 400). Zeit sparen heißt: weniger erzeugen (weniger Nacharbeit, kein doppeltes Schreiben) oder schneller erzeugen. |
| Modell-Prüfer sind unzuverlässig. | Prüfer-Test: 0 von 4 brauchbare Prüfungen bei Qwen3.6 und Qwen3-Coder; frühere Läufe: eigene Prüfung stimmte nur in 31 von 60 Fällen mit dem versteckten Test überein. | Checker, Schiedsrichter und Reviewer **aus dem selben Modell** bringen Zeit, keine Qualität. Solo ist richtig. Der unabhängige Richter ist der versteckte Test. |
| Solo ist schneller und gleich gut (mittelschwer). | Standardtest 197/274 s gegen 370/353 s; am009 707 s gegen 2206 s, beide 3/3. | Standard bleibt solo. |
| Bei der schweren Aufgabe zählen die Fehler der **Infrastruktur**. | am007: von 12 Agentenläufen in den Stufen 5 bis 7 endeten 8 ohne Abgabe (HTTP 400, `answer_cut`, Rundenlimit); dazu startete jeder 400er das Modell neu. | Behoben: 4xx ist kein Absturz mehr und der Servertext wird mitgeschrieben, Verlauf wird gekürzt, `read_file` in Teilen, `outline`. Wirkung offen (Messung steht aus). |
| Ein Lauf kann Code **halb umgebaut** hinterlassen. | am007 Stufe `all`: `NameError: _match` (Rundenlimit mitten im Umbau); die Nacharbeit startet auf dem kaputten Stand. | Option `--step-syntax-check` (fängt nur Syntax); Idee: Rundenlimit nur nach einem grünen Zwischenstand, sonst Rückgriff auf die letzte Fassung (Commit je Schritt gibt es schon). |

## 2. Der Schritt-Plan

**Gut:** frische kurze Unterhaltung je Schritt; wörtliche Auszüge (nichts geht verloren, was der Planer auslässt, geht an jeden Schritt); Schnittstellen und Übergabenotizen; Karte des Arbeitsbereichs; Zwang zum Teilen bei langen Aufgaben.

**Schwächen / offene Punkte:**
1. **Kein Beleg, dass er besser ist.** Bisher nur gebaut und mit Fake-Modellen getestet. Der erste echte Lauf (am007) steht aus. Ehrlich: es kann auch langsamer werden (Planer-Lauf und mehr kalte Prompts).
2. **Nacharbeit an einem Schritt:** nur der letzte Schritt wird fortgesetzt, ein Fehler aus Schritt 1 wird dort gesucht. Idee: Nachplanen (der Planer sieht den Bericht und weist ihn einem Schritt zu).
3. **Kalter Cache:** jeder Schritt beginnt neu (`cache_ram: 0`, ein Slot). Der Cache trägt nur innerhalb eines Gesprächs. Der Planer-Lauf und die Schritte teilen nur die Systemnachricht nicht (andere Rolle). Wenig Verlust, aber ein gemeinsamer Anfang (gleiche Systemnachricht und Karte zuerst) würde Einlesen sparen.
4. **Schrittgröße ist nicht an das Fenster gebunden.** Aktuell feste Zahlen (Kürzen ab 20.000, Schreibaufrufe ab 6.000 Prompt-Token) für ein 32k-Fenster. Bei einem anderen Fenster oder Modell stimmen sie nicht.
5. **Der Planer kann Einheiten falsch zuordnen** (z. B. eine Regel nur dem falschen Schritt). Schutz: nicht beanspruchte Einheiten gehen überall hin, aber falsch zugeordnete nicht. Prüfbar durch ein Planer-Probe (siehe 4).

## 3. Anpassung an die vorhandenen Modelle

Was wir haben (aus `role_routing.yaml` und den Messungen):

| Modell | Stärke / Eignung | Grenze |
|---|---|---|
| **Qwen3.6-35B-A3B** (`coder.local_primary`) | bester Entwickler und Planer, 45 Token/s, 32k Fenster, 10,4 GB | nur ein Modell dieser Klasse; Laden 10 s; schreibt gern lange Dateien in einem Zug |
| Qwen3-Coder-30B | 4/4 im Standardtest, aber 2,8-mal langsamer; am007 früher 0/7 | zweite Meinung / Rückfall |
| Jan-code-4b | klein, schnell (250 s, 1/4); passt ganz auf die GPU | zu schwach als Entwickler; mögliche Rolle: enge Hilfsjobs |
| SWE-Review-8b | Reviewer-Rolle | kein Messwert für den Nutzen |
| gpt-oss-20b, Gemma 4 12B | gpt-oss früher Haupt-Coder; Gemma Verifier | Gemma gibt zeitweise Müll aus (`<unused49>`); beide nie im Standardtest gemessen |
| Hermes-4-14B, DeepSeek-V2-Lite | im Standardtest 1/4 und 0/4 | nicht geeignet |

**Konsequenz für den Workflow:** ein starkes Modell für alle Rollen, kein Wechsel (jeder Wechsel kostet Laden und kalten Cache). Weitere Modelle nur dort, wo sie etwas **Unabhängiges** liefern — das ist **nicht gemessen** (siehe Messplan, Review-Probe).

**Hebel für Qwen3.6 (jeweils noch zu messen):**
- **Sampling:** unser Standard ist Temperatur 0,1. Die Hersteller empfehlen für die Qwen-Reihe im Nicht-Denk-Betrieb etwa Temperatur 0,7, top_p 0,8, top_k 20 (und bei Qwen3-Coder repeat_penalty 1,05). Zu niedrige Temperatur fördert Wiederholungsschleifen, passt zu unseren `answer_cut`. Billig zu messen mit dem Standardtest (`--sampling` gibt es).
- **Spekulatives Dekodieren ohne zweites Modell:** der installierte Server (b11371) kennt `--spec-type ngram-mod` / `ngram-simple` (Entwürfe aus dem eigenen Verlauf). Beim Code-Bearbeiten wird viel aus dem Kontext wiederholt; mögliche Beschleunigung des Erzeugens, das 100 % der Zeit ausmacht. Vorsicht: bei MoE mit Experten im RAM kann die Prüfung mehrerer Entwurfs-Token den Gewinn auffressen. Nur Messung entscheidet. (MTP bräuchte einen anderen Download.)
- **Größeres Fenster:** Qwen3.6 hat wenige Aufmerksamkeitsschichten; der Rechenpuffer ohne Flash Attention wächst aber mit dem Fenster. 49k bis 64k sind mit `moe_sweep.py` schnell zu messen (freier VRAM, Tempo).
- **Denken nur beim Planer:** das Modell läuft mit `reasoning off`. Für den Plan (kurze Antwort, viel Wirkung) könnte ein begrenztes Denken (Budget 1–2k Token) helfen; kostet einen Serverneustart.

## 4. Messplan (jeder Punkt ein eigenes Gate; GPU nacheinander)

| Nr. | Messung | Dauer | Frage |
|---|---|---|---|
| M1 | Standardtest Qwen3.6 mit 3 Sampling-Einstellungen, je 2 Versuche | ca. 40 min | senkt eine höhere Temperatur die Fehler/`answer_cut` ohne Zeitverlust? |
| M2 | Erzeugungstempo mit `ngram-mod`, `ngram-simple` gegen aus (Prompt: Code ändern) | ca. 15 min | gibt es Gewinn trotz Experten im RAM? |
| M3 | Fenster 49k und 64k bei `n_cpu_moe` 28 | ca. 10 min | passt es in 11,5 GB, was kostet es? |
| M4 | **Planer-Probe:** Abdeckung der Aufgabeneinheiten, Schrittzahl, Schnittstellen; alle Stufen von am007/am009, Modelle Qwen3.6 (aus/mit Denken), Qwen3-Coder | ca. 30 min | wer schneidet am besten, mit und ohne Denken? Ohne Entwickler, nur Plan |
| M5 | **Review-Probe mit Mutanten:** `suite_mutants` liefert Fehlerfassungen; ein Reviewer sieht Referenz oder Mutante und urteilt | ca. 40 min | welches Modell erkennt Fehler, ohne falschen Alarm? Nur dann lohnt eine zweite Instanz |
| M6 | am007 mit Schritt-Plan (HG-4F2EF52F, ist vorgelegt) | 1–2 h | der eigentliche Wirkungsnachweis |

Ohne GPU kann ich vorab bauen: Schwellen aus der Fenstergröße ableiten (statt fester Zahlen), Laufkennzahlen je Lauf (höchster Prompt, Aufrufe je Werkzeug, Lese-/Schreibanteil, Cache-Treffer aus dem Serverlog), einen Rückgriff auf den letzten grünen Stand bei Rundenlimit, und die Probes M4/M5.

## 5. Empfehlung

1. Keine weitere Aufgabe in die Warteschlange, bis M3, M4 und M1 gemessen sind (zusammen ca. 80 min): sie entscheiden, womit der Schritt-Plan überhaupt läuft.
2. Den wartenden Lauf `run-c097eb9e2bb6` (alter Planer-Stand) stoppen und das Gate HG-4F2EF52F erst nach M4 freigeben.
3. Ohne GPU: Schwellen aus dem Fenster, Laufkennzahlen, Probes M4/M5 bauen.
