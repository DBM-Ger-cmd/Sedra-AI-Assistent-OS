# Bau-Pakete aus den offenen Roadmap-Teilen (12.11.2026)

Auftrag: aus den offenen Teilen der Roadmaps Bau-Specs schneiden, die SEDRAs lokale Modelle selbst bauen können. Basis `main` Commit `74bf792`. Es wurde **nichts gebaut**: kein `devvm_build.py`, kein Modelllauf, keine GPU. Geprüft wurden nur Specs, Tests und Referenzen (`spec_check.py`, auch `--vm`).

## 1. Ergebnis in Kürze

- 7 Pakete, 28 Stufen, je ein Modul mit versteckten Tests, Referenz und Stempel. Jedes Paket ist in sich geschlossen (Python-Standardbibliothek, ein Paket reines JavaScript) und hängt von keinem anderen ab.
- Der **Einbau** in den Code (Routen, Werkzeuge, Oberfläche, Guard) ist nirgends Teil des Baus; er steht je Paket unter „Einbau“ und bleibt Handarbeit von Claude nach dem Ja des Captains.
- Gegen den Code geprüft: Einiges, was in den Roadmaps als offen steht, ist gebaut (Tabelle 2, Zeilen „gebaut“).

## 2. Bestandsaufnahme: offen, geeignet, nicht geeignet

Quellen: Wissensdatei Abschnitte 18 und 19, Specs `SPEC_APPS_v1_*`, `SPEC_LERNEN_UND_HILFSWERKZEUGE_v1`, `SPEC_APP_TEAM_v1`, `SPEC_APP_UEBERSICHT_v1`, die drei Roadmaps vom 05.11., Code in `runtime/src/sedra_runtime`.

| Teil | Stand im Code | Eignung | Grund / fehlende Voraussetzung |
|---|---|---|---|
| AM6-03/04/07/09 (Agentenliste, Wirkungsklasse, Kennzeichnung, Audit) | `langdock_agent` kommt im Code nicht vor | **geeignet** → Paket 1 | unabhängig vom Format der Agents-API |
| AM6-01/02/05/06/08/10 (Adapter, Verb, Inhaltsschutz, Ausfall) | nicht gebaut | nicht geeignet | Format der Agents-API unbekannt (AM6-01); Adapter braucht Netz und Guard-Anbindung |
| G2-09 Vorschau mit Prüfserver | nicht gebaut | **teilweise geeignet** → Paket 5 (Befehl, Adresse, Ende) | Prozessstart, PID, Route und leeres Prüfprojekt sind Eingriff in die Harness |
| AM7-10 Fach-Apps der KMU-Shell | nicht gebaut | **teilweise geeignet** → Paket 6 (rechnender Kern) | Auswahl der Kandidaten ist offen (Captain); die Apps selbst sind Oberfläche |
| AM7-07 signierte Richtlinie | nicht gebaut | nicht geeignet | AM7-E3: nicht in v1; Schlüsselverwaltung ist eine Captain-Entscheidung |
| AM7-04 `richtlinie.schema.json` | Prüfung steht im Code, Datei fehlt | nicht eigenes Paket | zu klein (Spec größer als Code, Regel V4): Claude schreibt es direkt |
| AM7-E4 Gesprächs-Vorgabe in der KMU-Shell auswerten | Feld wird gespeichert, nicht ausgewertet | nicht geeignet | Oberfläche der Shell |
| AM4 Teil C (microVM, fremde MCP-Server) | nicht gebaut | nicht geeignet | Sicherheits-Spec fehlt (AM4-16), Entscheidung B7, Eingriff in Kern |
| AM5-12 Schlüsselablage Langdock | nicht gebaut | nicht geeignet | Geheimnisse, Zugang des Betreibers; es gibt keine Langdock-Zugangsdaten |
| G9-09, G10-03 (Anzeige Wartezustand, `FREIGABE_ERTEILT` Konsole) | teilweise | nicht geeignet | Kern/Guard, Freigabe-Tür |
| Freigaben S4 (`SPEC_FREIGABEN_S4_v1`) | nicht gebaut | nicht geeignet | Entscheidungen E1–E6 des Captains offen |
| W4 `rueckblick_schreiben` (LR-10, 14, 15) | nicht gebaut (`rueckblick_schreiben` fehlt im Code) | **teilweise geeignet** → Paket 2 | Werkzeug, Klasse H, Vorbehalt `docs/AAR/**` hängen an E3 von S4 (Einbau) |
| VS-02, VS-06, VP-01 Vorschläge | `_ausgeblendet` und „Korrektur schlägt Lob“ fehlen | **geeignet** → Paket 4 | Einbau in `harness/belohnung.py` danach |
| HW-10/11 Syntax vor der Freigabe | `syntax` kommt in `harness/`, `desk/` nicht vor | **geeignet** → Paket 3 | Prozess mit Zeitlimit und Karte sind Einbau |
| HW-02/03 PDF, Excel, PowerPoint lesen | **gebaut** (`wissen/leser/umwandeln.py`, `extern.py`, K5-4) | – | steht in der Spec noch als offen |
| W2 `wissen_suchen`, `wissen_beantragen` | **gebaut** (`harness/werkzeuge.py`, `katalog.py`) | – | |
| A3 Übersicht, Minimal-Profil | **gebaut** (`a063a48`, `a35fda0`) | – | im Auftrag noch als „A3-Reste“ genannt |
| App Team: Agentenfenster-Stapel, Firmenwörter, Ereignishinweise | nicht gebaut | nicht geeignet | große Oberfläche, nicht im Browser geprüft |
| X4 Befehlspalette Strg+K | nicht gebaut (App Übersicht nennt sie offen) | **teilweise geeignet** → Paket 7 (Rang der Treffer) | Fenster, Tasten, Einträge aus Manifesten sind Oberfläche |
| X4 Layout-Rückgängig im Builder, X5 Texte Deutsch/Englisch | nicht gebaut | nicht eigenes Paket | Reserve: reine JS-Hilfen wären baubar (Undo-Stapel, Textschlüssel), Zuschnitt erst nach Entscheidung zur Oberfläche |
| W3 `desktop_aendern`, `profil_wechseln` | nicht gebaut | nicht geeignet | Vorschau und Freigabe, Eingriff in Harness |
| Konsens Punkt 4/5, `bau_coder_b`-Messung, Differenzfälle `n8n_modell_umstellen` | offen | nicht geeignet | Messläufe auf der GPU, Eingriff in Manager |
| `gesetze.en.md` freigeben, weitere englische Fassungen | offen | nicht geeignet | Freigabe des Captains |
| Abnahme am PC (Schalter `app_berechtigung`, `dienste`, `zugang_berechtigung`, `betrieb_unternehmen`) | offen | nicht geeignet | nur am PC |

## 3. Die Pakete

Alle Specs: `runtime/benchmarks/devvm_specs/<name>.py`, Referenz `runtime/benchmarks/devvm_refs/<name>/`. Ziel jeweils ein neues Modul; Zielort ist ein Vorschlag.

| # | Paket (Spec) | Datei des Baus → Zielort | Stufen | Prüfungen je Stufe (hidden) | Aufwand Bau (Schätzung) | Abdeckung |
|---|---|---|---|---|---|---|
| 1 | `langdock_agenten` | `langdock_agenten.py` → `desk/langdock_agenten.py` | 6 | 20 / 19 / 19 / 16 / 10 / 16 | 6 Stufen, je 1,5–3 min bei den bisherigen Bauten ähnlicher Größe, gesamt etwa 15–20 min | AM6-03, 04, 07, 09 |
| 2 | `rueckblick_antrag` | `rueckblick_antrag.py` → `harness/rueckblick_antrag.py` | 4 | 20 / 18 / 19 / 14 | etwa 10–15 min | LR-10, LR-14, LR-15 |
| 3 | `syntax_hinweis` | `syntax_hinweis.py` → `harness/syntax_hinweis.py` | 3 | 20 / 16 / 15 | etwa 8–12 min | HW-10, HW-11 |
| 4 | `vorschlag_filter` | `vorschlag_filter.py` → `harness/vorschlag_filter.py` | 4 | 20 / 18 / 20 / 18 | etwa 10–15 min | VS-02, VS-06, VP-01 |
| 5 | `vorschau_prozess` | `vorschau_prozess.py` → `harness/vorschau_prozess.py` | 5 | 16 / 20 / 10 / 18 / 18 | etwa 12–18 min | G2-09 (reine Teile) |
| 6 | `betrieb_uebersichten` | `betrieb_uebersichten.py` → `desk/betrieb_uebersichten.py` | 4 | 18 / 19 / 14 / 15 | etwa 10–15 min | AM7-10 (zwei Kandidaten, Kern) |
| 7 | `palette_rang` | `palette_rang.js` → `uix/ui/palette_rang.js` | 2 | 19 / 19 (Node, Host) | etwa 5–8 min | X4 Befehlspalette (Kern) |

Die Zeitschätzung stützt sich auf die Logbuchzeilen vom 10./11.11. (Bauten von `am0_*`, `am3_*`, `zellen`: 60–160 s je Spec mit 1–3 Stufen, mit Ausreißern bis 460 s). Sie ist eine Schätzung, kein Messwert dieser Specs; gemessen wurde nichts.

### Einbau und Abhängigkeiten je Paket (nicht Teil des Baus)

1. **langdock_agenten**: Abhängigkeit nur Standardbibliothek. Einbau: `desk/langdock_kinds.py` (Objekttyp `langdock_agent`, Verb `fragen`, Gate), Aufruf des Inhaltsschutzes, `LANGDOCK_AGENT_GEFRAGT` aus `audit_payload`; erst nach AM6-01 (Format der Agents-API). Die Agentenliste liest ein YAML-Leser, `agenten_pruefen` bekommt dessen Ergebnis.
2. **rueckblick_antrag**: Einbau: Werkzeug `rueckblick_schreiben` (Schema in `SCHEMAS`, Zweig, `HARNESS_WEGE`, `OHNE_KARTE`, Klasse H in `freigabeklasse.ARTEN`), Anwenden schreibt `docs/AAR/<ID>.md` und ruft `lessons_anhaengen`, Vorbehalt `docs/AAR/**`. Voraussetzung: Entscheidung E3 der Spec Freigaben S4.
3. **syntax_hinweis**: Einbau: Diff-Karte ruft `syntax_hinweis`; `node_pruefer` startet `node --check` im Unterprozess mit Zeitlimit 60 s (HW-03/HW-11). Entscheidet nichts, nur Hinweis.
4. **vorschlag_filter**: Einbau: `harness/belohnung.vorschlaege` ruft `vorschlaege_filtern`; `_ausgeblendet.jsonl` lesen und anhängen; Route `…/vorschlaege/entfernen`; später `vorschlaege_pflegen`.
5. **vorschau_prozess**: Einbau: Route `POST /api/harness/oberflaeche/vorschau`, `subprocess` mit `vorschau_befehl`, Ausgabe lesen bis `adresse_lesen` etwas liefert, `vorschau_ende` in der Prüfschleife, leeres Prüfprojekt anlegen. Berührt `harness/api.py` und die Sammelkarte (G2-05): nicht gleichzeitig mit anderen Harness-Arbeiten.
6. **betrieb_uebersichten**: Einbau: Fach-Apps in `uix/shells/gateway-kmu/apps/` (Manifest, Oberfläche), Route auf `desk/betrieb.py`. Vorher legt der Captain die Kandidaten aus AM7-10 fest.
7. **palette_rang**: Einbau: Palette-Fenster in der Harness-Shell, Einträge aus den Manifesten; Regeln `setInterval`, 400 Zeilen, keine Hex-Farben.

## 4. Reihenfolge und Abhängigkeiten

Die Pakete brauchen einander nicht; jedes ist einzeln baubar, jedes Modul steht allein. Vorschlag nach Nutzen und Risiko:

1. **`vorschlag_filter`** und **`syntax_hinweis`**: kleiner Einbau, kein Entscheidungsbedarf, sofort nützlich im Alltag.
2. **`rueckblick_antrag`**: Bau jetzt möglich, Einbau wartet auf E3 (S4).
3. **`vorschau_prozess`**: nützlich für die Oberflächen-Abnahme (G2), Einbau aufwendiger.
4. **`betrieb_uebersichten`**, **`palette_rang`**: Bau jederzeit; Einbau braucht Oberflächenarbeit.
5. **`langdock_agenten`**: Bau jetzt möglich, aber der Einbau steht, bis AM6-01 geklärt ist (kein Zugang zu Langdock).

Konflikte der Einbauten (nicht der Bauten): 2 und 4 berühren beide `harness/belohnung.py`/`api.py`; 4 und 5 `harness/api.py`. Einbauten nacheinander, nicht gleichzeitig.

## 5. Freigaben, die der Captain für den Bau geben muss

- **Ja zum Bau** (GPU-Lauf, Modellserver): je Paket oder für alle. Ohne Ja startet nichts; `spec_not_checked` verhindert Bauten ohne Stempel.
- **Reihenfolge und Menge** (ein Paket nach dem anderen; die GPU ist belegt, wenn der Router läuft).
- Vor dem Einbau, nicht vor dem Bau: E3 der Spec Freigaben S4 (Paket 2), AM6-01 (Paket 1), Kandidaten AM7-10 (Paket 6).
- Hinweis: Die Stempel liegen unter `workspace/SEDRA_OS/runtime_data/spec_stamps/` (nicht im Repo). Jede Änderung an Spec, Referenz oder Saat macht sie ungültig; dann `spec_check.py <name> --vm --project <Projekt>` neu.

## 6. Bau starten (nur Hinweis)

Mit dem Skill `sedra-bau-starten`: Vorprüfung GPU und RAM (mindestens 12 GB frei), `devvm_build.py` oder `bau_schleife.py --projekt <Ordner> --spec <name> start "<Auftrag>"`. Die Regressionsprobe (`REGRESSION`) prüft nach jeder Stufe die früheren Tests. Die Arbeitsanweisung `bau_coder` bleibt aus (Messung 11.11.: bei größeren Aufgaben schlechter). Nach dem Bau: Kandidat prüfen, dann von Hand einbauen; der Differenztest `ab_bau.py` braucht Differenzfälle, die hier nicht mitgeliefert sind.

## 7. Was geprüft wurde und was nicht

## 8. Prüfergebnisse (12.11.2026)

`spec_check.py <name>` (Host, Python 3.14) und `--vm` (microVM, Python 3.12.15) für alle sieben Specs: lint ok, Referenz besteht jede Stufe, Stempel Stufe `vm` geschrieben nach `workspace/SEDRA_OS/runtime_data/spec_stamps/`. Prüfungen je Stufe gezählt mit `count_checks` (höchstens 20; `palette_rang` meldet 21 und 22 nur, weil der Zähler drei `assert`-Wörter im Node-Kopf mitzählt).

**Gegenprobe** (bewusst fehlerhafte Referenzen, Test muss rot werden): 71 Änderungen, 5 überlebten. Davon waren 3 gleichwertig oder schwach: `rueckblick_antrag` `\d` statt `[0-9]` (gleichwertig, die Zeichenklasse trägt schon), `vorschau_prozess` Präfix mitten in der Zeile (gleichwertig, die Adresse wird dann ungültig), `syntax_hinweis` Text vor dem Übersetzen mit strip() (schwach: eingerückter Code würde nicht mehr auffallen; nicht nachgeschärft). Zwei echte Lücken (Sortierung ohne Beachtung der Großschreibung in `betrieb_uebersichten`, Fremdurteil nach einer Korrektur in `vorschlag_filter`) wurden geschärft; die beiden Specs danach neu geprüft und gestempelt (Host und VM ok), die Gegenprobe selbst wurde für diese zwei Änderungen nicht wiederholt.

**Nicht geprüft:** kein Bau durch ein Modell (also unbekannt, ob und in wie vielen Läufen SEDRA die Stufen besteht; Aufwandsschätzungen sind Schätzungen); `--seed` entfällt (keine Saat, die Aufgaben bauen neue Module); `--snapshots` nicht möglich ohne Bau; der Node-Test von `palette_rang` läuft nur auf dem Host (die microVM führt kein JavaScript aus, `vm ref` ist dort leer); keine Einbauten, keine Tests des Gesamtprojekts.

## 9. Bauergebnis (12.11.2026, nach dem Ja des Captains)

Alle sieben Pakete gebaut mit `devvm_build.py --profile standard`, nacheinander, ein Lauf je Spec: 28 von 28 Stufen `hidden PASSED`, Dauer 110 bis 502 s je Spec, Nacharbeiten 0 bis 3, keine Eskalation, kein Serverabsturz (Zeilen im Logbuch). Kandidaten unter `workspace/SEDRA_OS/runtime_data/devvm_candidates/<spec>/`.

**Nicht geprüft:** die Kandidaten sind nicht Zeile für Zeile gelesen (Checkliste `CODER_PROFIL_UND_WORKFLOW` §3) und nicht mit dem Differenztest gegen die Referenz verglichen; nichts ist eingebaut. Vor jeder Übernahme Gate G4 des Captains.
