# Spec 7, S7.6 – Retrieval-Qualität (Vorschlag, 23.10.2026)

**Ziel:** Treffer@5 der hybriden Suche von 77,5 % (S7.1, BGE-M3) auf das Abnahmeziel von 85 % bringen (D7.11).

**Rahmen:**
- ohne neue Python-Abhängigkeit (G1-S7-e)
- ohne Eingriff in `core/`, Guard und Rezepte
- alles lokal

Die Ideen stammen aus der GitHub-Recherche vom 23.10.2026 (`docs/PRUEFUNG_SPEC7_CODE_2026-10-23.md`, Abschnitt 3). Grundlage im Code ist `main` mit dem Patch der Prüfung (`fix/spec7-pruefung-2026-10-23`).

**Zeitpunkt.** S7.2-F ist noch nicht gemessen, und das Raster steht laut D7.5 vor der Messung fest. S7.6 erweitert dieses Raster, bevor gemessen wird. Nach dem Einfrieren wäre jede Ergänzung ein neues Gate mit Nachmessung.

**Regel gegen Überanpassung (gilt für alle Stufen):**
- Abgestimmt wird nur auf dem Entwicklungssatz (`wissen_goldsatz.json`, 40 Fragen).
- Der versiegelte Abnahmesatz (`wissen_goldsatz_v2.json`) wird für S7.6 weder gelesen noch als Quelle für Glossar oder Fragen benutzt; er wird nur in S7.5 gemessen.

## Stufen

| Stufe | Was | Woher (Muster) | Stand |
|---|---|---|---|
| **A1** | Eingabeformat `e2` fürs Einbetten: `Dokument > Stelle` + Text, Tabellenzeilen als „Spalte: Wert; …“. Volltext und Datenblock behalten den Originaltext. | Anthropic Contextual Retrieval (ohne LLM-Teil), RAGFlow Tabellen-Vorlage | **gebaut**, Vorgabe `e1` |
| **A2** | Glossar der Wortsuche: Gruppen gleichbedeutender Begriffe als ODER-Alternativen; der Gütefaktor zählt eine Alternative als Treffer des Fragewortes. | OpenThesaurus-Prinzip, selbst gepflegt | **gebaut**, Vorgabe aus |
| **A3** | Messung schärfen: Recall@20, nDCG@10, Treffer@5 je Quellgruppe; Raster Format × Glossar × 12. | BEIR, ranx | **gebaut** |
| **A4** | Datamarking: im untrusted-Block werden Leerzeichen zu `ˆ`, und ein Zusatz im Systemsatz erklärt das. Kopfzeilen und IDs bleiben unmarkiert. | Microsoft Spotlighting (Hines u. a. 2024) | **gebaut**, Vorgabe aus |
| B1 | Zerlegte deutsche Komposita als zweites FTS5-Feld: ein Wort wird geteilt, wenn beide Teile (ab 4 Zeichen) im eigenen Index stehen (`abschnitte_vocab`). Migration 2. | CharSplit, german-decompounder (nur Prinzip, keine Fremddaten) | offen |
| B2 | Lokaler Reranker `bge-reranker-v2-m3` (GGUF Q8_0, 636 MB, Apache-2.0) als eigener `llama-server --reranking` (Port 8095, eigene PID) auf den Top 20–30 der Fusion; bei Fehler oder Zeitüberschreitung bleibt die Fusion. | llama.cpp PR #9510, LightRAG-Empfehlung | offen; Risiko llama.cpp Issue #16407 |
| C1 | Je Abschnitt Kontextsatz und 2–3 deutsche Fragen vom lokalen LLM, eigener Index. | Contextual Retrieval, RAGFlow Auto-Questions | nach Spec 2 (GPU-Zeit unter dem Scheduler) |
| C2 | HyDE für Agentenläufe. | texttron/hyde | nur, wenn A–C1 nicht reichen |

Nicht übernommen:
- LightRAG und GraphRAG: großes LLM zum Indizieren nötig.
- sqlite-vec: native Abhängigkeit, erst ab rund 50 000 Abschnitten ein Thema.
- ragas und ARES: Cloud bzw. A100; übernommen werden nur die Kennzahlen.
- khoj: AGPL.
- kotaemon: Reranking über die Cloud.
- LLM Guard: archiviert.

## Stufe A im Code

| Datei | Änderung |
|---|---|
| `wissen/glossar.py` (neu, rein) | `pruefe`, `alternativen` (Beugung: Präfix ab 5 Zeichen, höchstens 3 Zeichen länger; Akzente wie der Index), `anfrage_woerter`; `wis_glossar_ungueltig`. In `test_wissen_grenze` als reines Modul eingetragen |
| `config/wissen_glossar.yaml` (neu) | 18 Gruppen aus der Fachsprache der Doku und den Fehlgriffen des Entwicklungssatzes (G03, G16, G36, G40); Ergänzungen dieses Rechners in `local_config/wissen_glossar.yaml` |
| `wissen/konfig.py`, `config/wissen.yaml` | `einbetten.eingabeformat` ∈ {e1, e2}; `suche.glossar` (bool, Vorgabe false); `kontext.datamarking` (bool, Vorgabe false); Glossar aus Paket und `local_config` |
| `wissen/zerlegen.py` | `dokumentname`, `tabellen_als_zeilen`, `eingabetext_e2` |
| `wissen/speicher.py` | `_offene` baut bei `e2` den Eingabetext aus Datei, Stelle und Text; `alternativen`; Wortliste und `_guete` mit Glossar; `suche` gibt `glossar` zurück |
| `wissen/ausgabe.py`, `wissen/lauf.py` | `markiere`, `MARKE`, `SYSTEM_WISSEN_MARKIERT`; `datensaetze(…, datamarking=)` |
| `benchmarks/wissen_fusion_messung.py` | `--eingabe e1|e2|beide`, `--glossar aus|an|beide`; Startkombination `e1 · glossar=aus · Startvariante`; Auswahlregel D7.5 über alle Kombinationen; Leave-one-out; Recall@20, nDCG@10, `je_gruppe` |
| `tests/test_wissen_s76.py` (neu) | 11 Prüfungen |

Der Wechsel auf `e2` ist ein Modellwechsel: Die Modell-ID endet auf `#e2`, und der Index wird automatisch neu eingebettet (WIS-04). Auf der CPU sind das bei rund 3100 Abschnitten etwa 7 Minuten.

**Erste Zahl ohne Modell.** Die Wortsuche allein wurde auf dem Entwicklungssatz gemessen: Zerleger z2, Repo-Doku ohne die drei Speicher, Weg `datei`.
- Treffer@5: 52,5 % ohne Glossar, 57,5 % mit Glossar.
- Recall@20: 65 % ohne Glossar, 80 % mit Glossar.

Diese Werte sind **zu optimistisch**: Das Glossar ist teils aus genau diesen Fehlgriffen gebaut. Aussagekräftig ist erst der Abnahmesatz.

## Messung auf dem PC (ersetzt den Befehl aus dem Baubericht, Schritt 5)

```
.venv\Scripts\python.exe benchmarks\wissen_fusion_messung.py --server-url http://127.0.0.1:8094 --projekt <guppi>\workspace\GUPPI_OS ^
    --zerleger z2 --eingabe beide --glossar beide --listen --json benchmarks\wissen_s72f.json
```

- Aufwand: zwei Einbett-Läufe auf der CPU (e1, e2), zusammen etwa 15 Minuten; alles andere läuft offline.
- Ergebnis: 48 Kombinationen. Die Startkombination bleibt, außer eine andere ist um mindestens 2 Fragen besser und in keiner Art um mehr als 1 schlechter (D7.5).
- Das Ergebnis wird eingefroren: `eingabeformat`, `glossar` und die Fusionswerte in `config/wissen.yaml`, dazu `meta.fusion_version`.

**Datamarking (A4)** bleibt aus, bis der Einschleus-Test aus D7.11 mit dem lokalen Modell in beiden Modi gelaufen ist: einmal mit, einmal ohne Marke. Die Antwortqualität darf nicht sichtbar leiden; Prüfstein ist Abschnitt (8).

## Gate-Liste G2-S7.6

Jede Zeile wird einzeln entschieden. Die Empfehlung steht in der letzten Spalte.

| Gate | Frage an den Captain | Empfehlung |
|---|---|---|
| G2-S7.6-a | Stufe A (A1–A4) übernehmen, alle Schalter mit Vorgabe aus/`e1`; Messskript erweitert | ja |
| G2-S7.6-b | Glossar: Paket-Datei mit 18 Gruppen; neue Gruppen nur aus Doku-Fachsprache und Entwicklungssatz, nie aus dem Abnahmesatz; lokale Ergänzungen in `local_config` | ja |
| G2-S7.6-c | Raster S7.2-F erweitert auf Format {e1, e2} × Glossar {aus, an} × 12 Fusionsvarianten; Startkombination e1/aus/Start; Auswahlregel D7.5 | ja, vor der Messung festschreiben |
| G2-S7.6-d | Datamarking erst nach dem Einschleus-Test (beide Modi, mit und ohne Marke) einschalten | ja |
| G2-S7.6-e | Stufe B1 (Komposita-Feld, Migration 2) als nächster Bau, falls S7.2-F unter 85 % bleibt | ja, nach S7.2-F |
| G2-S7.6-f | Stufe B2 (Reranker): Download 636 MB, dritter Prozess (Port 8095), nur CPU bis Spec 2, fail-open, Übernahme nur bei messbarem Gewinn am Entwicklungssatz und Recall@20 deutlich über Treffer@5 | entscheiden nach S7.2-F |
| G2-S7.6-g | Stufe C (LLM-Kontext, Auto-Fragen, HyDE) | später, nach Spec 2 |
