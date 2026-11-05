# Analyse: Wissen in den Kern – was es gibt, was sich vereinfachen lässt (05.11.2026)

Anlass: Der Captain will die Wissensbasis nicht blind als App übernehmen. Sie wird überall gebraucht und gehört vielleicht in den Kern.
Vor dem Bau soll geprüft werden, was sich überarbeiten oder vereinfachen lässt. Nur im Code gelesen (`main` `d51083a`), nicht im laufenden Sedra.
Das Audit-Log lag hier nicht vor.

## 1. Befund in einem Satz

Der **Wissensspeicher ist im Backend schon Kern** (`guppi_runtime/wissen/`, Spec 7, `runtime.wissen`, Desk-Erweiterung, Schalter `wissen`).
Nicht im Kern sind drei Dinge: der **Zugang aus One Sedra**, die **Oberfläche** und die **Ordnung**. Neben dem Wissensspeicher gibt es sechs
weitere Wissensorte. Jeder hat eine eigene Ablage und eine eigene Suche.

## 2. Bestand: neun Orte, an denen Wissen liegt

| # | Ort | Datei / Ablage | Größe | Was | Wer fragt | Einschätzung |
|---|---|---|---|---|---|---|
| 1 | **Wissensspeicher** (Spec 7) | `wissen/*.py` → `local_config/wissen/wissen.sqlite` | ≈ 3 500 Zeilen | Quellen mit Freigabe, Zerlegen, CPU-Einbetten (Port 8094), hybride Suche, Rechtefilter (Stufe, Projekt, Personenbezug → kein Cloud-Weg), Zitatprüfung `[W…]`, Vorschläge der Agenten, Nachmessung, Glossar, Captain-Notizen | Agentenläufe (`wissen/lauf.py`), Gespräch der alten Shells, falls `gespraech.wissen` (`uix_server.py` ≈ 2196), Werkzeuge `wissen`/`fundstelle` | **gut gebaut, behalten**, das ist der Kern |
| 2 | KnowledgeStore | `knowledge.py` → `runtime_data/knowledge/records.jsonl` | 44 | alte Notizsätze `KN-…` | nur `modules/planning.py` (`search`); Adapter liest mit | **Altlast**: als Quelle in 1 aufgehen lassen, dann stilllegen |
| 3 | Arbeitsumfeld-Wissen | `arbeitsumfeld_wissen.py` → `local_config/arbeitsumfeld/wissen.sqlite` | 303 | Ordner, Läufe, Regeln, Modelle | im Betrieb **kein Aufrufer gefunden** (nur Tests, Benchmark, Adapter liest die Datei) | **Vermutung: tot oder veraltet**, prüfen, dann entfernen oder als Quelle in 1 |
| 4 | GateWay-Wissen | `gateway/wissen.py` → `local_config/gateway/wissen.sqlite` | 444 | Regelbuch R-01…R-16, Merkmale, Fehlercodes, **Live-Zustand**, Antworten ohne Modell | Gespräch der alten Shells (`zustaendig`), Chat-Werkzeuge `gateway_*` (`chat_tools.py`) | **Auskunft, kein Suchwissen**: bleibt, in One Sedra fehlen die Werkzeuge |
| 5 | Arbeitsplatz-Wissen | `desk/arbeitsplatz.py` + `arbeitsplatz.yaml` je Shell | 314 | wo was ist, Begriffe, Live-Stand | Gespräch der alten Shells, Werkzeug `arbeitsplatz_stand` (auch in One Sedra) | bleibt; mit einer Hauptshell wird es eine Datei |
| 6 | Gedächtnis der Harness | `harness/gedaechtnis.py` → `<projekt>/runtime_data/harness/gedaechtnis/*.jsonl` | 238 | automatische Notiz je Antwort, eigene Wortsuche | Werkzeug `erinnern` | **zweite Suche neben 1**: vereinheitlichen (siehe V2) |
| 7 | Betriebslog | `harness/betriebslog.py` → Tagesdateien | 84 | Betrieb je Tag | als Quelle für 1 per Antrag | so lassen |
| 8 | Belohnungen | `harness/belohnung.py` → Tagesdateien | 329 | Lob ★ und Korrektur ⚑ | Werkzeug `belohnungen_lesen`, Quelle für 1 per Antrag | so lassen |
| 9 | Gelernte Regeln | `docs/AAR/LESSONS.md` | ≤ 25 Zeilen | Regeln im Systemprompt | jeder Zug der Harness | so lassen (klein, bewusst im Prompt) |

## 3. Wo es heute hakt

1. **One Sedra kommt nicht an das Wissen.** Der Chat der Harness (`harness/werkzeuge.py`, 20 Werkzeuge) hat kein Werkzeug für den Wissensspeicher
   und auch keins für `gateway_*`. Der automatische Wissensblock läuft nur im alten Gesprächsweg (`uix_server.chat`).
2. **Zwei Gesprächswege** mit verschiedenem Wissen: `uix_server.chat` (GateWay-Wissen, Arbeitsplatz, Wissensblock) und Harness (`erinnern`, `arbeitsplatz_stand`).
   Wird One Sedra die Zentrale, sollte das Wissen nur einmal angebunden werden.
3. **Drei eigene Suchen**: die hybride Suche (1), die Wortsuche des Gedächtnisses (6) und `KnowledgeStore.search` (2). Rechtefilter und Personenbezug gibt es nur in (1).
4. **Viele Begriffe für Ähnliches**: Notizen des Captains (1), Gedächtnis (6), Records (2), Lessons (9). Für den Captain ist schwer zu sehen, was wo landet.
5. **Oberfläche**: acht Wissens-Orte stehen einzeln im Start-Menü (Suche, Quellen, Vorschläge, Eigenes, Messung, Index, Nachmessung, Bibliothek).

## 4. Vorschläge zum Vereinfachen

| # | Vorschlag | Nutzen | Aufwand | Risiko |
|---|---|---|---|---|
| **V1** | **Wissen wird Kerndienst und Grundfunktion.** Eine Schnittstelle `wissen.fragen(frage, leser, route)` → Treffer mit Fundstellen, für alle Aufrufer: Harness-Chat, Agentenlauf, alte Gespräche. `lauf.py` und `desk_basis.kontext` gehen darüber. Ohne Einbett-Server gibt es Volltext (geht auch auf dem Stick). | Ein Weg, ein Rechtefilter | klein: die Teile gibt es, sie werden nur zusammengezogen | gering |
| **V2** | **Gedächtnis der Harness wird eine Quelle im Wissensspeicher** (Projektfilter gibt es schon). `erinnern` sucht dann über `wissen.fragen` mit Projekt der Sitzung. Die eigene Wortsuche fällt weg. | eine Suche weniger, Rechtefilter gilt | mittel | Quelle braucht heute ein Gate. Hier ist eine Entscheidung nötig: eine Daueraufnahme ohne Gate oder ein einmaliges Gate je Projekt (wie bei den Captain-Notizen) |
| **V3** | **KnowledgeStore stilllegen**: Bestand als Quelle übernehmen, `planning.py` fragt über V1 | eine Ablage weniger | klein | gering, Test für `planning` |
| **V4** | **Arbeitsumfeld-Wissen prüfen und entfernen**, falls es wirklich nicht mehr gebaut wird. Ordner, Läufe und Regeln liegen ohnehin als Dateien vor (Quelle `repo`) | ≈ 300 Zeilen weniger | klein | Vermutung prüfen (Audit, Dateidatum der SQLite) |
| **V5** | **GateWay- und Arbeitsplatz-Auskunft bleiben getrennt** (Live-Zustand, kein Suchwissen), aber in One Sedra als Werkzeuge `gateway_status/vorgang/regel` lesbar | GateWay-App bekommt den Chat | klein | gering |
| **V6** | **Chat-Werkzeuge in One Sedra**: `wissen_suchen` (frei, lesen) und `wissen_beantragen` (Quelle vorschlagen → Posteingang). Dazu ein Schalter je Sitzung/Profil **„Wissen zuerst“**: Der Block wird automatisch hinten an die Frage gehängt, wie bei den Agenten. Der Anfang des Prompts bleibt gleich, der Cache bleibt erhalten. | Chat antwortet mit Fundstellen | mittel, mit neuen Wegen in `freigabeklasse.py`/`api.py` | gering |
| **V7** | **Oberfläche: eine App „Wissen“** mit Reitern Suche · Quellen · Vorschläge · Eigenes · Messung, Fundstelle rechts. Die Einzelorte im Start-Menü werden zu einem Eintrag (Wörter für die Suche bleiben). Index und Nachmessung landen unter Messung. | Start-Menü schlanker; zugleich das Muster für den App-Rahmen (A2) | mittel | gering |
| **V8** | **Begriffe ordnen**: *Gedächtnis* (automatisch, je Projekt), *Notizen* (vom Captain), *Regeln* (gelernt, LESSONS), *Quellen* (Dokumente, Logs). Alles ist im Wissen auffindbar, jede Art mit eigenem Filter. | verständlich für Auftraggeber | klein (Texte) | – |

Nicht anfassen: Zerlegen, Fusion, Vektor, Schema mit Migrationen und Embed-Server. Sie sind rein, geprüft (Spec 7 Abnahme, S7.6) und gut getrennt.

## 5. Zielbild

```
           One Sedra (Chat, App „Wissen“)      Agentenlauf        GateWay-App
                         │                          │                  │
                         ▼                          ▼                  ▼
            ┌──────── Kern: wissen.fragen(frage, leser, route) ────────┐   gateway_* (Auskunft, Live)
            │  Rechtefilter → Suche (hybrid | Volltext) → Fundstellen   │   arbeitsplatz_stand
            └───────────────────────┬──────────────────────────────────┘
                                    │ Quellen (je mit Freigabe)
     Dokumente · Logbuch · Betriebslog · Belohnungen · Gedächtnis je Projekt · Notizen · (Altbestand KN-…)
```

## 6. Vorgeschlagene Schritte (je eigener kleiner Auftrag)

1. **K1 Kerndienst** (V1): `wissen.fragen` ziehen, `lauf.py`/`desk_basis` darüber, Tests. Kein neues Verhalten.
2. **K2 Chat** (V6, V5): `wissen_suchen`, `wissen_beantragen`, `gateway_*` in One Sedra, Schalter „Wissen zuerst“.
3. **K3 App Wissen** (V7, V8): eine App mit Reitern, Start-Menü zusammenfassen.
4. **K4 Aufräumen** (V2, V3, V4): Gedächtnis als Quelle, KnowledgeStore und Arbeitsumfeld-Wissen stilllegen. Erst nach K1 und erst nach dem Blick ins Audit-Log am echten Rechner.

K1 und K2 bringen den sichtbaren Nutzen. K4 ist reines Aufräumen und kann warten.

## 7. Entscheidungen des Captains

1. Wissen als **Grundfunktion** (nie ausblendbar, in jedem Profil), ja oder nein?
2. Gedächtnis der Harness als Quelle: **Daueraufnahme ohne Gate** oder **ein Gate je Projekt** (Vorschlag: ein Gate je Projekt, wie bei den Notizen)?
3. „Wissen zuerst“ im Chat: **automatisch an** oder **nur auf Schalter** (Vorschlag: Schalter, Vorgabe an, sobald der Schalter `wissen` an ist)?
4. Altspeicher 2 und 3 entfernen, nachdem geprüft ist, dass sie nicht mehr gebraucht werden?
