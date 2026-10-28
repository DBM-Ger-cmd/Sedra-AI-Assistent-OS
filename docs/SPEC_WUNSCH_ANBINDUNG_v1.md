# SPEC Wunsch-Anbindung v1 – G1 Anforderungen (28.10.2026)

Auftrag des Captains 28.10.2026: Wünsche werden in SEDRA eingegeben; daraus entsteht eine Spec; nach Freigabe baut ein SEDRA-Agent
(Stufe 3 der Harness-Shell, `SPEC_HARNESS_SHELL_v1.md` §6); danach prüft ein zweiter Lauf den Ertrag.
Entscheidungen des Captains (Abfrage 28.10.2026): Bau über **SEDRA-Agenten**; Freigabe **erst Spec, dann Bau**; Ablauf **Wunsch, Spec, Gate, Bau, Review**.

Abhängigkeit: Diese Spec braucht Stufe 2 (Freigabe-Katalog, Karten) und Stufe 3 (Vorarbeiter-Vorlage, Freigabe nach Aufgabe) der Harness-Shell.
Vor Stufe 3 gibt es nichts zu bauen. Bis dahin ist diese Spec nur der Plan.

## 1. Ablauf in fünf Schritten

| Schritt | Was passiert | Wer entscheidet |
|---|---|---|
| W1 Wunsch | Der Captain schreibt den Wunsch in der Harness-Shell (Sitzung „Wünsche“, Vorlage Vorarbeiter). Freitext, ein Wunsch je Sitzung. | Captain |
| W2 Spec-Entwurf | Der Vorarbeiter schreibt aus dem Wunsch eine Spec nach dem Muster `SPEC_*_v1.md`: Ziel, Anforderungen mit Prüfbarkeit, Grenzen, Stufen, offene Fragen. Er liest dafür nur, schreibt nur in `docs/spec_entwuerfe/`. | Vorarbeiter (Katalog-Stufe frei für Lesen, Schreiben nur dort) |
| W3 Gate | Die Spec wird als Karte vorgelegt (Diff, Umfang in Zeilen und Stufen, offene Fragen). Der Captain gibt frei, ändert oder verwirft. Ohne Freigabe kein Bau. | **Captain** (fest, HS-28) |
| W4 Bau | Ein SEDRA-Agent baut die freigegebene Spec in Stufen. Schreiben nur im Schreibbereich der Aufgabe (Aufgaben-Freigabe, HS-27), Läufe nur die in der Aufgabe genannten. Jede Stufe mit versteckten Tests. | SEDRA-Agent unter Vorarbeiter-Freigabe; Stufen mit Gate nach Spec 1 |
| W5 Review | Ein zweiter Agent (anderes Modell, nicht der Coder) prüft Diff und Tests gegen die Spec. Ergebnis: übernehmen, nacharbeiten oder verwerfen. Übernahme nur durch den Captain. | Review-Agent; Übernahme **Captain** |

Jeder Schritt schreibt ins Logbuch. Jeder Wunsch hat eine ID (`W-<8 Hex>`) und einen Ordner `runtime_data/wuensche/<ID>/` mit Wunsch, Spec, Bau-Protokoll und Review.

## 2. Anforderungen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| WA-01 | Ein Wunsch wird nur als Text angenommen (höchstens 4000 Zeichen); Anhänge sind nicht Teil von v1. | Test |
| WA-02 | Aus jedem Wunsch entsteht genau eine Spec-Datei; kein Bau ohne Karte mit Freigabe des Captains (W3). | Test: Bau ohne Freigabe wird abgelehnt |
| WA-03 | Die Freigabe-Karte zeigt Umfang (Zeilen, Stufen), die offenen Fragen aus der Spec und den Schreibbereich. | Test |
| WA-04 | Ein Bau läuft nur im freigegebenen Schreibbereich der Aufgabe und mit den freigegebenen Befehlen; Änderungen an Harness-Code, `local_config/` und Guard sind ausgeschlossen (HS-28). | Guard-Tests |
| WA-05 | Jede Stufe des Baus hat versteckte Tests. Eine Stufe gilt erst als fertig, wenn sie besteht; höchstens 20 neue Prüfungen je Stufe (L3). | Stempel nach `spec_check` |
| WA-06 | Das Review läuft mit einem anderen Modell als der Coder. Sein Urteil ist ein Vorschlag; übernommen wird nur durch den Captain. | Test: Modellname von Coder und Review verschieden |
| WA-07 | Nichts wird automatisch in den Kern übernommen oder auf `main` gebracht (Regel 6a, L5). | Test |
| WA-08 | Ein Wunsch kann jederzeit angehalten werden; der Stand bleibt im Ordner, laufende Befehle werden beendet. | Test |
| WA-09 | Jeder Schritt (W1 bis W5) ist im Audit sichtbar und in der Taskleiste als Lauf mit Fortschritt angezeigt (HS-31). | Test |

## 3. Abgrenzung

- Kein Wunsch-Bau ohne die Harness-Shell; kein zweiter Weg daneben.
- Kein Cloud-Modell im Bau. Cloud bleibt Spec 3 (Entscheidung je Lauf). Für das Review ist es in v1 ausgeschlossen.
- Keine Änderung am Freigabe-Katalog durch den Vorarbeiter oder einen Agenten (HS-28).
- Der Wunsch ersetzt nicht die Spec. Die Spec ist das, was freigegeben wird.

## 4. Entscheidungen des Captains (28.10.2026)

| Nr | Frage | Entscheidung |
|---|---|---|
| WQ-1 | Modell für die Spec (W2) | Qwen3.6-35B-A3B |
| WQ-2 | Prüfer im Review (W5) | Gemma-4-12B (anderes Modell als der Coder) |
| WQ-3 | Stufen je Durchgang | höchstens 5, danach neue Karte |
| WQ-4 | Parallelität | ein Wunsch je Sitzung, Slots des einen Modells |

Die Fragen unten sind beantwortet und bleiben zur Nachvollziehbarkeit stehen.

## 4a. Offene Fragen (beantwortet, siehe oben)

| Nr | Frage | Vorschlag |
|---|---|---|
| WQ-1 | Welches Modell schreibt die Spec (W2)? | Qwen3.6-35B-A3B, weil es für Coding der Standard ist (`docs/MODELLE.md`). Nemotron erst, wenn der Modelltest es besteht. |
| WQ-2 | Welches Modell prüft (W5), wenn Qwen der Coder ist? | Gemma-4-12B QAT (`verifier.llama_gemma`). Es ist als Prüfer gedacht, aber als Agent laut `MODELLE.md` ungeeignet; alternativ Nemotron nach dem Test. |
| WQ-3 | Wie groß darf ein Wunsch-Bau in einem Durchgang sein? | Höchstens 5 Stufen je Durchgang, danach neue Karte. |
| WQ-4 | Ist „ein Wunsch je Sitzung“ genug, oder sollen mehrere Wünsche parallel laufen? | Ein Wunsch je Sitzung, mehrere Sitzungen gleichzeitig nur nach dem Slot-Modell (ein Modell, mehrere Slots). |

## 5. Nächste Gates

- **G1** (diese Datei): Captain beantwortet WQ-1 bis WQ-4 und gibt die Anforderungen frei.
- **G2** Design: Datenformat des Wunsches, Ablage, Karte für W3, Anbindung an den Vorarbeiter (Stufe 3).
- **G3** Bau-Aufgaben, sobald Stufe 3 übernommen ist.
