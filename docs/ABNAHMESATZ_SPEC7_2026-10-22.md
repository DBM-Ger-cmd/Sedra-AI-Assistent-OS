# Abnahmesatz Spec 7 (Wissensspeicher/RAG) – 22.10.2026

Geschrieben von einer anderen Sitzung als der, die Zerlegen und Fusion festlegt (D7.11, G2-S7-n, G3-S7-09). Diese Sitzung hat weder das Paket `wissen/`, noch `benchmarks/wissen_*`, noch den Baubericht Spec 7, noch die Design-Kapitel D7.3 (außer der Adapter-Tabelle) und D7.5 gelesen. Grundlage war allein der gelesene Text der Quellen. Branch `spec7/abnahmesatz`, Stand `b945a8d`.

Datei: `runtime/benchmarks/wissen_goldsatz_v2.json` · Prüfskript: `runtime/benchmarks/wissen_goldsatz_v2_check.py`

## Regel

- 120 Fragen: 110 beantwortbar (30 wortgleich, 50 umschrieben, 30 Fachbegriff) und 10 Negativfragen (`art: "negativ"`, Antwort steht nirgends in den Quellen, keine Quelle; getroffen heißt: der Speicher sagt offen, dass nichts gefunden wurde).
- Jede Erwartung ist ein Tripel `{adapter, datei, abschnitt}` mit `erwartet_ueber: "adapter"` und zeigt auf einen Inhalt, den ein Adapter aus D7.3 liefert: Doku-Abschnitt (Überschriftenpfad), Logbuchzeile (`Zeile <Zeit> <Art>`), Lektion (`Lektion <Titel>`), Zeile des Arbeitsumfelds (Titel), Regel/Fehler/Begriff/Zustand/Schritt des Gateways (Titel). Python-Quelltext ist keine Erwartung.
- Trefferregel wie Version 1: ein Abschnitt aus den Top 5 passt zu einer erwarteten Quelle, wenn Adapter gleich, `datei` Präfix der Datei-Kennung und `abschnitt` im Abschnittspfad vorkommt (Groß-/Kleinschreibung egal).
- Bei „umschrieben“ und „Fachbegriff“ benutzt die Frage keines der kennzeichnenden Wörter der Stelle; das Prüfskript erzwingt das (Wörter ab vier Zeichen aus dem Titel der Stelle, ohne Allerweltswörter).
- Der Satz wird nie zum Abstimmen benutzt; nach D7.11 darf er bei Durchfall nicht geändert werden.

## Verteilung

| | wortgleich | umschrieben | fachbegriff | negativ | Summe |
|---|---|---|---|---|---|
| doku | 10 | 16 | 10 | 3 | 39 |
| logbuch | 7 | 10 | 5 | 2 | 24 |
| knowledge | 3 | 4 | 3 | 1 | 11 |
| arbeitsumfeld | 5 | 9 | 4 | 2 | 20 |
| gateway | 5 | 11 | 8 | 2 | 26 |
| Summe | 30 | 50 | 30 | 10 | 120 |

Beantwortbar je Gruppe: doku 36, logbuch 22, knowledge 10, arbeitsumfeld 18, gateway 24 (jede ≥ 10). Fragen mit Antwort in einer langen Liste oder Tabellenzeile (`liste_oder_tabelle: true`): 40 (≥ 10).

Quellen der Doku-Gruppe: `BETRIEB.md`, `ENTWICKLUNG.md`, `SO_WIRD_GEBAUT.md`, `MODELLE.md`, `ARCHITEKTUR.md`, `SPEC_GATEWAY_VORGANG_v1.md`, `REGELWERK_DATENKATEGORIEN_CLOUDSPERRE_v0.1_…`, `REGELWERK_STANDARDLAEUFE.md`, `AUFTRAG_EINHEITLICHER_IMPORT_2026-10-16.md` und die Kapitel Spec 2, 3 und 6 der `SPEC_AGENTEN_ORCHESTRIERUNG_v1.md`.

## Platzhalter und Hinweise

- **knowledge (10 Fragen):** Die ursprünglichen Fragen A059–A068 verwiesen auf vier Sandbox-Lektionen (reserved_name, placeholder_write, syntax_error, missing_module), die im lokalen Speicher nie angelegt wurden. Entscheidung des Captains am 24.10.2026 (Weg a): die zehn Fragen sind auf die acht vorhandenen `coding_lesson` umgeschrieben (keine Lektionen angelegt, keine Daten erfunden); `art`, Gruppe und Verteilung blieben. Erwartung je Frage: `knowledge:<KN-ID>` und `Lektion <Titel>` aus dem lokalen Speicher. Zuordnung: A059 → KN-85E0AAF4 (Whole-string regex validation in Python), A060 und A067 → KN-82CAC22F (urllib.parse: the port attribute raises by itself), A061 und A068 → KN-E338EC2C (Validators: translate every library error into the documented one), A062 → KN-786685E0 (Regex: escape the dots of a literal host or version), A063 → KN-60536EEE (Regex: \d matches non-ASCII digits), A064 → KN-53AC38CC (Lists of records from outside contain junk), A065 → KN-2CD118AF (A polling window must not wipe or stop itself), A066 → KN-9309C5D3 (Own tests must be discoverable). Die Fragen sind deutsch, die Lektionstexte englisch; bei „umschrieben“ und „fachbegriff“ steht kein Wort des Lektionstitels in der Frage.
- **arbeitsumfeld:** Der Adapter liest die Tabelle `wissen`, die `arbeitsumfeld_wissen.py` füllt – nicht die `arbeitsplatz.yaml` der Shells und Werkzeuge (die liest `desk/arbeitsplatz.py`). Die Fragen zielen deshalb auf diese Zeilen: Vorarbeiter-Aktionen (`V-…`, aus `vorarbeiter.py`), Sperre (`V-sperre`), Präzedenzfall-Läufe (`L-…`, Abschnitt 8 des Regelwerks), Regel-Abschnitte (`R-01…R-10`, `## `-Überschriften von `REGELWERK_STANDARDLAEUFE.md` in Reihenfolge), Auftrags-Abschnitte (`A-01…A-07`) und drei Ordner (`O-local_config`, `O-redesign/vorarbeiter`, `O-redesign/omni_mapping`). Ordner-Zeilen entstehen nur, wenn der Ordner im Arbeitsbereich vorhanden ist (Feld `hinweis`).
- **gateway:** Kennungen nach den Zeilen von `gateway/wissen.py`: `R-xx` (Regel), `P04` (Merkmal), `F-<code>` (Fehler), `B-<begriff>` (Begriff, Titel mit großem Anfangsbuchstaben), `Z-<ZUSTAND>`, `L-<nr>` (Leitfaden-Schritt), `A-ABLAUF`.
- **logbuch:** Jede Stelle `Zeile <Datum> <Uhrzeit> <Art>` trifft genau eine Zeile des Logbuchs (geprüft); Zeilen mit „(ca.)“ wurden nicht gewählt.

## Prüfergebnis

`python runtime/benchmarks/wissen_goldsatz_v2_check.py` (Standardbibliothek):

```
Fragen: 120  je Art: {'fachbegriff': 30, 'negativ': 10, 'umschrieben': 50, 'wortgleich': 30}
je Gruppe (beantwortbar): {'arbeitsumfeld': 18, 'doku': 36, 'gateway': 24, 'knowledge': 10, 'logbuch': 22}  Liste/Tabelle: 40
result ok (0 Befunde)
```

Geprüft: Zählungen, IDs A001–A120, keine doppelte Frage, jede `datei` existiert im Repo (außer Kennungen mit Präfix `knowledge:`/`arbeitsumfeld:`/`gateway:`; Gateway-Kennungen gegen `klassen.py`/`wissen.py` geprüft), jedes Glied jedes Doku-`abschnitt` kommt als Überschrift in der Datei vor, jede Logbuch-Stelle trifft genau eine Zeile, keine lokalen Pfade, bei anderen Worten keine kennzeichnenden Wörter der Stelle.

## SHA-256 (Versiegelung)

```
bae43a026214ad15f0837cad8c7896bd68fdee80e5c93ada50f6e03eaecc9c56  runtime/benchmarks/wissen_goldsatz_v2.json
```

Frühere Summe vor dem Umschreiben der Knowledge-Fragen (Platzhalter-Stand): `d1b6a5927aa9cade62f5f8c7f9fd05ad7df73aea0f16eaa3e86091a4dcc65992`. Ändert sich die Datei erneut, wird die Summe neu berechnet und im Logbuch nachgetragen.

## Vorschlag Logbuch-Zeile (Art SPEC)

```
.venv\Scripts\python.exe benchmarks/logbook.py add SPEC "Spec 7 Abnahmesatz (S7.5, D7.11, G2-S7-n) von anderer Sitzung geschrieben, vor dem Einfrieren der Fusion: 120 Fragen (30 wortgleich, 50 umschrieben, 30 fachbegriff, 10 negativ; doku 36, logbuch 22, knowledge 10, arbeitsumfeld 18, gateway 24; 40 Liste/Tabelle), alle Erwartungen auf Adapter-Inhalt; Prüfskript result ok; knowledge-KN-IDs aus dem lokalen Speicher. SHA-256 d1b6a5927aa9cade62f5f8c7f9fd05ad7df73aea0f16eaa3e86091a4dcc65992" --ref "runtime/benchmarks/wissen_goldsatz_v2.json, docs/ABNAHMESATZ_SPEC7_2026-10-22.md"
```
