# Baubericht Spec 7 – Wissen und RAG (S7.4, S7.2-F-Harness), 22.10.2026

Branch `spec7/bau` auf `spec7/design-s7.2` (`e1f8395`). Gebaut von Claude in der Cloud nach der Entscheidung des Captains vom
22.10.2026, 15:28 (alle Module, auch die drei der Bau-Specs) und 15:31 (vollständige Fassung, Feinschliff auf dem PC). Grundlage:
`docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md`, „Design Stufe 2“ D7.0 bis D7.13, „Bauschritte S7“, die Bau-Specs `wis_store`, `wis_chunk`,
`wis_fuse`. Python 3.13 hier, Syntax auf 3.12 geprüft (`test_wissen_grenze`); keine neue Abhängigkeit; kein Netz; `core/`,
Guard, `gpu_preflight`, Rezepte und Engine unverändert.

## 1. Was gebaut ist

### Paket `runtime/src/guppi_runtime/wissen/` (Zeilen)

| Datei | Z. | Inhalt | Design |
| --- | --- | --- | --- |
| `__init__.py` | 0 | leer | D7.1 |
| `schema.py` | 247 | DDL als `MIGRATIONEN` (= Saat `wis_schema_seed`), `oeffne_db`, `migriere`, Meta, `abschnitt_id`, `vergleiche`, `wende_an`, `offene_vektoren`, `schreibe_vektoren`, `modellwechsel` | D7.2, Bau-Spec `wis_store` |
| `zerlegen.py` | 235 | `bloecke`, `teile_block`, `zerlege_markdown/text/eintrag/logbuch`, `saeubere_stelle`, `abschnitt_hash`, `eingabetext`; `z2` | D7.3, Bau-Spec `wis_chunk` |
| `fusion.py` | 149 | `woerter`, `fts_anfrage`, `idf`, `guete`, `fusioniere` (gewichtete RRF, Spitzenschutz), `nur_volltext`, `darf_lesen`, `sql_filter`; `f1` | D7.5, D7.7, Bau-Spec `wis_fuse` |
| `vektor.py` | 55 | `normiere`, `packe`, `lese`, `skalarprodukt`, `top_k` (heapq, Gleichstand nach nr) | D7.2, D7.5 |
| `ausgabe.py` | 70 | `datensatz`, `datensaetze` (5 Treffer, 1600/8000 Zeichen), `zitate`, `pruefe_zitate`, `schlusstext`, `KEINE_TREFFER`, `HINWEIS_*`, `SYSTEM_WISSEN`, `ZITAT_MUSTER` | D7.6 |
| `konfig.py` | 149 | `config/wissen.yaml` (Vorgaben) + `local_config/wissen.yaml` (Engine, Modell, Prüfsumme); `wissen_config_invalid:<grund>` | D7.4 |
| `adapter.py` | 353 | `markdown`, `text`, `logbuch`, `knowledge`, `arbeitsumfeld`, `gateway` (`#wissen`, `#eigene`), `vorschlag`; `pruefe_pfad`, `quell_hash`, `stuecke`; `ERSTBESTUECKUNG` | D7.3 |
| `embed.py` | 352 | `GpuLage`, `TestLabZugang` (nur `holder`, `reservations`, `queue`), `EmbedEinstellung`, `EmbeddingDienst` (Start mit `-ngl 0 --device none`, PID-Datei, Alias, Prüfsumme, `/health`, Prüfsatz, `lauf` mit Pause, `anfrage_vektor`, `stoppe` nur eigene PID), Modell-ID | D7.4 |
| `speicher.py` | 646 | Fassade `WissenSpeicher`: Quellen freigeben/ändern, `abgleich`, `einbetten_schritt`, `nachfuehren`, `suche` (Filter vor dem Ranking, Wortliste, Vektorliste, Güte, Fusion, Rückfall), `stand`, Vorschläge (`vorschlagen`, `vorschlag_aufnehmen`, `ablehnen`, `zuruecknehmen`), Nachmessung, `SAETZE`, alle Audit-Ereignisse | D7.3–D7.8, D7.10, D7.11 |
| `aufnahme.py` | 53 | Takt-Thread unter `local_config/wissen/takt.lock` (`mission_lock.exclusive`), `wis_takt_busy` | D7.3 |
| `lauf.py` | 114 | `frage_aus_aufgabe`, `route_von`, `leser_aus_scope`, `kontext_nachrichten`, `nachrichten_mit`, `nachbereite`, `vorschlag_aus_antwort` | D7.6, D7.8 |
| `desk_wissen.py` | 357 | Erweiterung: Typen `wissen`, `wissen_quelle`, `wissen_vorschlag`; Typ-Verben `suche`, `nachfuehren`, `quelle_beantragen`, `erstbestueckung`, `nachmessung*`; Verben `abschalten`, `stufe_heraufsetzen`, `neu_beantragen`, `zuruecknehmen`; Applier `wissen_quelle`, `wissen_vorschlag`; `start` (Takt), `snapshot` | D7.7–D7.9 |

### Außerhalb des Pakets

| Datei | Änderung |
| --- | --- |
| `desk/extensions.py` | `MODULES` + `guppi_runtime.wissen.desk_wissen` (G2-S7-u) |
| `desk/orchestra_runner.py` | `scope` + `level`, `project_id`; `_wissensblock` vor dem ersten `_ask` für `arbeit`/`bericht`; Zitatprüfung; `wissen_vorschlag` (G2-S7-f) |
| `orchestra/runner.py` | `ARBEIT_SCHEMA` optionales Feld `wissen_vorschlag`; `outcome` reicht es durch |
| `runtime.py` | `_configure_wissen` (Schalter, Konfiguration, `WissenSpeicher.oeffnen`, `TestLabZugang`), `wissen_error`, Audit `WISSEN_OFF`, `boot()["wissen"]` |
| `local_switches.py` | Schalter `wissen: {enabled}` (Standard aus) |
| `uix_server.py` | `close()` schließt den Speicher (Takt, eigener Server); **keine neue Route** (D7.9 nennt nur `POST /api/objects`, `POST /api/actions`) |
| `desk/gateway.py` | `OBJECT_TYPES` + `wissen` (ein CORE-Werkzeug darf keinen Privattyp tragen) |
| `desk/decisions.py` | Titel und Hinweis der Antragsarten `wissen_quelle`, `wissen_vorschlag` im Posteingang |
| `uix/tools/wissen/` | `tool.yaml`, `tool.js` (246), `tool.css`, `README.md`, `test.spec.js` (9 Prüfungen), `arbeitsplatz.yaml` |
| `uix/shells/paperclip/nav.js`, `arbeitsplatz.yaml` | Zeile „Wissen“ unter Werkzeuge; Wort `wissen` |
| `config/wissen.yaml` | Paket-Vorgabe (27 Z.) |
| `benchmarks/wissen_spec_gegenprobe.py` | 48 Z.: versteckte Tests der drei Bau-Specs gegen das Paket |
| `benchmarks/wissen_fusion_messung.py` | 242 Z.: Harness S7.2-F |
| `benchmarks/uix_check.py` | Objekt des Werkzeugs `wissen` |
| `tests/test_wissen_*.py`, `tests/wissen_fixture.py` | 8 Testdateien (1224 Z.) + Fixture (244 Z.); `test_uix_contract.py`, `test_uix_shell_d_pure.py` nennen das Werkzeug |

Commits auf `spec7/bau`: `6178b6e` (schema, zerlegen, fusion, Gegenprobe), `3d53055` (vektor, ausgabe, konfig, Tests), `527b1ff` (adapter, embed, speicher, aufnahme, Fixture, test_wissen_speicher), `966903d` (Tests Adapter, Einbetten), `a3d2ae1` (desk_wissen, lauf, Einschübe Spec 1, Schalter/boot, Tests Desk und Lauf), `6330c05` (Werkzeug, nav, arbeitsplatz), danach Messskript und dieser Bericht.

## 2. Abweichungen vom Design (mit Grund)

| Nr | Abweichung | Grund |
| --- | --- | --- |
| Abw-1 | Modul heißt `embed.py`, nicht `einbetten.py` (D7.1) | Auftrag vom 22.10. nennt `embed.py`; Inhalt wie D7.4 |
| Abw-2 | Datensätze sind dicts, keine dataclasses (`Treffer`, `SuchErgebnis`, `Leser` = `speicher.leser(...)`) | Schnittstellen der Bau-Specs (G3-S7-05); `suche` gibt ein dict mit `modus, hinweis, treffer, modell_id, abdeckung, ms, woerter` |
| Abw-3 | `ausgabe` importiert `zerlegen.saeubere_stelle` (D7.1 sagt „ausgabe → nichts“) | keine Doppelung der Säuberung; beide rein, Richtung in `test_wissen_grenze` festgeschrieben |
| Abw-4 | Werkzeug `handles: [wissen]` statt `[wissen, wissen_quelle, wissen_vorschlag]`; Quellen und Vorschläge sind Ansichten (`view`) desselben Objekts; `desk/gateway.OBJECT_TYPES` + `wissen` | das Muster für `handles` (`[a-z0-9-]`) erlaubt keinen Unterstrich, Kind-Namen keinen Bindestrich; ein CORE-Werkzeug darf keinen Privattyp tragen. Der Klick auf einen Treffer öffnet `wissen:speicher` mit `view: quellen` (N5) |
| Abw-5 | Der Anfrage-Weg des Captains über `POST /api/actions {type: wissen, verb: suche}` liefert das Ergebnis im Feld `result` (so antwortet `desk/actions.run_type`) | bestehender Weg der Verben |
| Abw-6 | Freigegebene Vorschläge gehen **über** `vorschlaege.jsonl` in den Speicher (Applier hängt die Zeile an und ruft `abgleich` der Quelle `Q-VS-…`), statt zusätzlich direkt in `abschnitte` zu schreiben | ein Weg für Erstaufnahme und Neuaufbau (G2-S7-q), keine Doppelung |
| Abw-7 | `n_t` (Dokumentzahl je Wort) kommt aus `count(*) … MATCH '"w"'`, nicht aus `abschnitte_vocab` | gleicher Tokenizer wie der Index (`remove_diacritics 2`: „ärger“ ≠ Vokabel „arger“); Tabelle bleibt in der DDL |
| Abw-8 | `quell_hash` der Dateiadapter: Größe und Änderungszeit je Datei, kein Inhalts-Hash | billig (D7.3: „keine Datei wird zerlegt“); eine unlesbare Datei behält ihre alten Abschnitte, eine fehlende Datei-Quelle wird übersprungen, nicht geleert |
| Abw-9 | Bei Schalter aus stehen die drei Typen als Platzhalter (Objekt `speicher` im Zustand `aus`, Listen leer) statt `unknown_object_type` | sonst 400 im Browser und `uix_check console FAIL`; die Seite sagt, warum sie leer ist (UIX-02) |
| Abw-10 | Der Applier bekommt von `gated` nur die Bindung; Gate- und Missions-ID der Freigabe sucht `_antrag_von` in den Missionen | `quellen.freigabe_gate` muss die echte Gate-ID tragen (D7.2) |
| Abw-11 | Nachmessung: Ergebnisdatei `local_config/wissen/nachmessung_<datum>.json` (nicht `runtime/benchmarks/…`) | die Laufzeit schreibt nicht ins Repo; der Captain kopiert |
| Abw-12 | `WIS_MODELL_WECHSEL` nur bei echtem Wechsel (nicht beim ersten Modell); `WIS_TAKT_FEHLER`, `WIS_VORSCHLAG_ZURUECKGENOMMEN`, `WISSEN_OFF` als zusätzliche Ereignisse; Fehlercodes `wis_quelle_neuer_antrag`, `wis_nachmessung_urteil`, `wissen_aus`, `wissen_config_invalid:*`, `wis_abschnitt_doppelt/ungueltig/unbekannt`, `wis_id_kollision`, `wis_limit_ungueltig`, `wis_zerlegen_eingabe` (Bau-Specs) | D7.10 nachgezogen |
| Abw-13 | Messskript `wissen_fusion_messung.py` arbeitet gegen einen **laufenden** Embedding-Server (`--server-url`), den der Captain startet (`-ngl 0 --device none`); `--fake` prüft den Harness ohne Modell | ohne lokale Engine kein Start aus der Cloud |

## 3. Testergebnisse (hier, Python 3.13, ohne Modell, ohne VM)

```
cd runtime && PYTHONPATH=src:tests python3 -m unittest <module>
```

| Lauf | Ran / OK |
| --- | --- |
| `test_wissen_vektor test_wissen_ausgabe test_wissen_grenze test_wissen_adapter test_wissen_speicher test_wissen_einbetten test_wissen_desk test_wissen_lauf` | Ran 84 tests – OK |
| `test_core_boundary_src test_uix_contract test_uix_shell_d_pure` | Ran 49 tests – OK |
| `test_knowledge_lessons test_arbeitsumfeld_wissen test_gateway_wissen` (WIS-01: die drei Speicher unverändert) | Ran 35 tests – OK |
| alle `test_desk_*` (13 Module), alle `test_orchestra*` (12), `test_arbeitsplatz`, `test_local_switches` + die obigen zusammen | **Ran 506 tests in 93.6 s – OK** |
| `python3 benchmarks/uix_check.py --tool wissen --shell paperclip` | `result ok  12 of 12 checks ok` (tool:wissen ok, console ok, allowlist ok) |
| `node -r ../../../../../tests/uix_spec_dom.js test.spec.js` (Werkzeug) | 9 Prüfungen, 0 Fehler |
| `python3 benchmarks/wissen_fusion_messung.py --fake --json …` | läuft durch (`result ok`, 3426 Abschnitte, 12 Varianten, Leave-one-out); Werte ohne Aussage (Fake-Vektoren) |

Tests je WIS (Tabelle „Bauschritte S7“): 01 `test_wissen_adapter` (Hashes der drei Speicher vor/nach gleich, nur `mode=ro`) + `test_wissen_speicher` (Treffer aus allen drei); 02 `test_wissen_desk` (Quelle nur über Antrag, abgelehnt → 0 Abschnitte); 03 `test_wissen_speicher` (zweiter Abgleich 0 eingebettet, eine geändert, eine gelöscht); 04 `test_wissen_einbetten` (`socket.create_connection` nur `127.0.0.1`, PID-Datei, Prüfsumme, Modellwechsel löscht alle alten Vektoren); 05 `test_wissen_vektor` + Harness; 06 `test_wissen_speicher` (Server kaputt/Engine fehlt/Abdeckung → volltext mit Hinweis, `WIS_RUECKFALL_VOLLTEXT` einmal); 07 `test_wissen_ausgabe` + `test_wissen_lauf` (fremde ID markiert, fehlende Zitate → Fundstellen); 08 `test_wissen_ausgabe` (Kopfzeile gesäubert, genau eine Endmarke) + `test_wissen_lauf` (Block `trust: untrusted`, Abschnitt 8 ohne Regelfund im Block, Abschnitt mit Regelfund nicht an Agenten); 09 `test_wissen_speicher` + `test_wissen_lauf` (Stufe 1 gegen Quelle Stufe 3, Projekt A gegen B); 10 `test_wissen_desk` (Vorschlag → Antrag → Freigabe genau ein Abschnitt, Ablehnung keiner, `binding_stale`) + `test_wissen_lauf` (aus der Antwort); 11 `test_wissen_speicher`/`test_wissen_lauf` (Route cloud, `WIS_CLOUD_GEFILTERT` als zweite Sperre, kein Cloud-Embedding-Weg: `test_wissen_grenze`); 12 `test_wissen_einbetten` (Fake-TestLab: Halter → Pause, `WIS_EINBETTEN_PAUSE` einmal, Dienst-Eigner hält nicht an, Anfrage auch im Bau, nie eine Lease im Quelltext); 13 `uix_check`, `test_uix_contract`.

## 4. Gegenprobe je Bau-Spec

`python3 benchmarks/wissen_spec_gegenprobe.py` (die versteckten Stufen-Tests der Spec gegen `guppi_runtime.wissen.<modul>` im Arbeitsbaum wie beim Bau):

```
  wis_store  migriere ok | vergleiche ok | wende_an ok | vektoren ok | modellwechsel ok
  wis_chunk  bloecke ok | teile_block ok | markdown ok | text ok | stelle ok
  wis_fuse   woerter ok | guete ok | fusioniere ok | spitzenschutz ok | darf_lesen ok | sql_filter ok
result ok
```

Alle 16 Stufen bestehen. Die Module sind von den Referenzen ausgegangen (gleiche Seite), tragen Docstrings und Kommentare; `test_wissen_grenze` hält `schema.MIGRATIONEN == wis_ddl.MIGRATIONEN` fest.

## 5. Was hier nicht geprüft werden konnte – Befehle für den Captain (Ordner `runtime`)

1. **A-5, erste Prüfung von S7.4 (Pflicht vor allem anderen):** CPU-Server ohne VRAM.
   `nvidia-smi --query-gpu=memory.used --format=csv` vorher; dann
   `<engine>\llama-server.exe -m <modelle>\bge-m3\bge-m3-q8_0.gguf --embeddings --host 127.0.0.1 --port 8094 -ngl 0 --device none -t 6 -c 8192 -b 8192 -ub 8192 -np 1 --alias wissen-embed`
   eine Minute laufen lassen, `nvidia-smi` währenddessen (gleicher Wert), `curl http://127.0.0.1:8094/v1/embeddings -d "{\"input\":[\"Prüfsatz\"]}"` → Dimension 1024. Kennt die Engine `--device none` nicht: anhalten, Captain entscheidet (D7.4).
2. **local_config/wissen.yaml** anlegen (`wissen: {engine: '<guppi>/engines/llama.cpp/b11160/llama-server.exe', modell: '<modelle>/bge-m3/bge-m3-q8_0.gguf', modell_sha256: '<sha256>', modell_name: bge-m3-q8_0}`) und `switches: {wissen: {enabled: true}}` in `local_config/switches.yaml`; Oberfläche starten, `boot()["wissen"]` muss `enabled: true, error: null` zeigen.
3. **Erstbestückung:** Werkzeug „Wissen“ → „Erstbestückung beantragen“ → Posteingang → „Freigeben und anwenden“; dann „Nachführen“ (Abgleich rund 2000 Abschnitte, Einbetten in Schritten zu 120 s; Takt alle 600 s). Audit: `WIS_ABGLEICH`, `WIS_EMBED_SERVER`, `WIS_EINBETTEN`.
4. **WIS-12 lokal:** `.venv\Scripts\python.exe benchmarks\testlab_cli.py hold …` in einem zweiten Fenster, dann „Nachführen“ → `WIS_EINBETTEN_PAUSE {grund: lease:…}`; Halter freigeben → nächster Schritt läuft auf der CPU, `nvidia-smi` unverändert.
5. **S7.2-F:** Server aus Schritt 1 laufen lassen, dann
   `.venv\Scripts\python.exe benchmarks\wissen_fusion_messung.py --server-url http://127.0.0.1:8094 --projekt <guppi>\workspace\GUPPI_OS --zerleger beide --listen --json benchmarks\wissen_s72f.json`
   (rund 5 bis 10 Minuten CPU für zwei Korpora); Goldsatz Version 2 mit `erwartet_ueber` über `--goldsatz`, sobald die 13 Fragen freigegeben sind (G2-S7-n). Ergebnis einfrieren (`meta.fusion_version`, Werte in `config/wissen.yaml`).
6. **Windows:** `os.kill(pid, SIGTERM)` in `embed.stoppe` für einen Server aus einer früheren PID-Datei (TerminateProcess), `mission_lock` mit `msvcrt` für `takt.lock`, Pfade mit `\` in `pruefe_pfad` (hier nur Posix geprüft), `uix_check` mit Edge/Chrome.
7. **Python 3.12 / VM:** nur Syntax geprüft (`ast.parse(feature_version=(3, 12))`); FTS5 in der `.venv` laut S7.1 vorhanden (A-11).
8. **S7.5** (Abnahmesatz, Durchlauf „Agent zitiert“ mit echtem Modell, Einschleus-Test in sandbox und beobachten, Nachmessung über vier Wochen) bleibt offen.

### Bewusst dem PC überlassen (Entscheidung 15:31)

- Bildschirmfoto `docs/shots/paperclip/wissen.png` (README verweist darauf).
- Eintrag in `docs/CHANGELOG.md` und Logbuchzeilen (Vorschlag unten); Nachtrag in `docs/SHELL_WERKZEUG_VERTRAG_v1.md` zur Zeile `wissen` in `OBJECT_TYPES`.
- Feinschliff des Werkzeugs: `prompt()` für „Stufe heraufsetzen“/„Neu beantragen“ durch ein Formular ersetzen; Ansicht „Quellen“ nach Klick auf einen Treffer die Quelle hervorheben (`quelle` kommt am Objekt an, wird noch nicht markiert).
- `desk/decisions.py` zeigt für Wissensanträge nur `describe`; die Felder der Bindung (Pfad, Stufe, Belege) stehen in der Mission, nicht in der Entscheidungskarte.
- Speicher über 50 000 Abschnitten (G1-S7-e), Chat-Anbindung (G2-S7-s), GPU-Einbetten (S7.4b).

## 6. Vorschlag Logbuch-Zeilen (`benchmarks/logbook.py add …`)

- `INTEGRATION "Spec 7 S7.4: Paket wissen/ (13 Module, 2730 Z.), Werkzeug wissen, Anschluss an den Lauf (G2-S7-f), Schalter wissen; 84 Tests test_wissen_*, Gesamtlauf 506 OK, uix_check --tool wissen result ok; Branch spec7/bau" --ref "docs/BAUBERICHT_SPEC7_2026-10-22.md"`
- `ENTSCHEIDUNG "Spec 7: Claude baut schema.py, zerlegen.py, fusion.py in der Cloud (15:28, ändert G2-S7-o, G3-S7-04); Gegenprobe gegen die versteckten Tests 16/16 ok" --ref "runtime/benchmarks/wissen_spec_gegenprobe.py"`
- `INTEGRATION "Spec 7 S7.2-F: Messskript wissen_fusion_messung.py als Harness (12 Varianten, z1/z2, Leave-one-out); Messung mit BGE-M3 auf der CPU steht aus" --ref "runtime/benchmarks/wissen_fusion_messung.py"`

## 7. Code-Zähler

Claude-Code dieses Baus (ohne Doku): Paket `wissen/` 2730 Z.; Werkzeug 440 Z. (js 246, spec 134, yaml/css/README 60); Benchmarks 290 Z.; Konfiguration 27 Z.; Änderungen außerhalb 85 Z. (+) / 9 (−); Tests 1468 Z. (8 Dateien + Fixture). Zusammen rund **5040 Zeilen Claude**, davon Produktionscode rund 3570; SEDRA 0 (Entscheidung 15:28). Die Bau-Specs und Referenzen (670 + 484 Z.) bleiben als Abnahme stehen.
