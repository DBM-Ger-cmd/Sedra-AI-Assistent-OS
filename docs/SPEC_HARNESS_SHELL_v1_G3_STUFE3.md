# SPEC Harness-Shell v1 – G3 Bau-Aufgaben Stufe 3 (29.10.2026)

Gehört zu `SPEC_HARNESS_SHELL_v1.md` (G1), `SPEC_HARNESS_SHELL_v1_G2_STUFE3.md` (G2, Entwurf; Fragen D-G1 bis D-G8) und dem Stand `d9b8f97`
(`BAUBERICHT_HARNESS_STUFE2_2026-10-28.md`, `BAUBERICHT_WARNUNG_*`). **Entwurf: gebaut wird erst nach Freigabe von G2 (D-G1 bis D-G8), den Berechtigungen
unten und diesem Gate G3.** Es entsteht nichts außer diesen Spec-Dokumenten.

Stufe 3 = **Verantwortung teilen**: Vorlage Vorarbeiter (HS-19), Vorarbeiter-Freigabe (HS-26 Rest), Freigabe nach Aufgabe (HS-27), Läufe in der Taskleiste mit
Benachrichtigung (HS-31 bis HS-33). Baut: **Claude** den Harness-Code, die Integration und die Oberfläche (L4, ENTWICKLUNG.md); **SEDRA** zwei reine Module (N2, N8),
das zweite als **Pilot über die Harness** (HS-E5: erster Bau eines SEDRA-Agenten unter einem Vorarbeiter). Branch `harness/stufe-3` in eigenem Worktree ab
`spec/agenten-orchestrierung`; Übernahme nach Review durch den Captain (G4).

## Aufgaben

Nummern `N1` bis `N12`. „SEDRA“ = Bau über `devvm_build --profile standard` gegen eine Bau-Spec mit Referenz, Stempel (`spec_check --vm`) und **höchstens 20** versteckten Prüfungen (L3);
alles andere baut Claude. Neue Dateien stehen im Paket `runtime/src/guppi_runtime/harness/` (kurz `harness/`), Tests in `runtime/tests/`.

| Nr | Aufgabe | Wer | Dateien | Fertig, wenn |
|---|---|---|---|---|
| N1 | **Vorlagen (HS-19).** `harness/vorlagen.py`: laden und prüfen (`runtime/config/harness_vorlagen/<id>.yaml` + `.md`, `local_config/harness_vorlagen/` mit Vorrang), ungültig → Fehler mit Grund, kein stiller Rückfall. `HarnessApi.anlegen` nimmt `vorlage` an (Sperre `vorlage_ab_stufe_3` entfällt), Kopf speichert `vorlage` + Hash; `schleife.system_prompt` nimmt den Vorlagentext; die Kiste bietet nur die Whitelist `werkzeuge`. Mitgeliefert: `vorarbeiter` (aus `START_PROMPT_VORARBEITER_BIONIC.md` ohne Bionic-Hinweise, mit Harness-Werkzeugen und Regeln aus G2 §5), `bauagent`, `pruefer`. `GET /api/harness/vorlagen`. | Claude | `harness/vorlagen.py`, `api.py`, `sitzung.py`, `schleife.py`, `config/harness_vorlagen/*`, `tests/test_harness_vorlagen.py` | Tests: Vorlage gültig/ungültig (je Fehlergrund), unbekanntes Werkzeug → Fehler, Whitelist wirkt, Kopf trägt Hash, Cockpit/`chat_reply` unverändert |
| N2 | **Aufgaben-Deckung (SEDRA-Bau B1, rein).** `deckt(aufgaben, sitzung_id, werkzeug, ziel, jetzt)` und `zustand(aufgabe, jetzt)` nach G2 §4.2; benutzt `katalog.passt` (wird mitgegeben, nicht neu geschrieben). Bau-Spec `docs/BAUSPEC_AUFGABE_DECKUNG.md`, `devvm_specs/harness_aufgabe_deckung.py`, Referenz in `devvm_refs/`. Siehe „Versteckte Prüfungen N2“. Scheitert der Bau → V4: Claude übernimmt die Referenz, Quote im Logbuch. | **SEDRA** (Claude: Spec, Referenz, Prüfungen, Review) | `harness/aufgabe_deckung.py` (Kandidat), `benchmarks/devvm_specs/harness_aufgabe_deckung.py`, `benchmarks/devvm_refs/harness_aufgabe_deckung/` | `spec_check … --vm`: Lint ok, Referenz ok, Stempel; Bau besteht 15 von 15; Vergleich Kandidat gegen Referenz ≥ 500 Fälle ohne Abweichung; Übernahme durch den Captain |
| N3 | **Aufgaben-Freigabe: Speicher, Prüfung, Einstufung (HS-27).** `harness/aufgabe.py`: anlegen (Pflichtgrenzen D-G4, Muster-Prüfung S4/S9, nur lokale Modelle), laden, `zustand` anwenden (Ablauf/Erschöpfung mit Audit), Zähler unter Sperre, beenden, zurücknehmen. `freigabe.Kiste.aufruf` nach G2 §4.3: harter Vorbehalt → Katalog → Warnung → weicher Vorbehalt → `aufgabe_deckung.deckt` → Karte; Audit `aufgabe:<id>`. `vorbehalte.py`: `pruefen_weich`, neue harte Pfade (S8). `katalog.WERKZEUGE` um `lauf_starten`, `lauf_stoppen`, `modell_laden`, `modell_entladen` (**`einstufen` bleibt unberührt**). Vorübergehend dient die Referenz von N2 als `deckt`, bis der Bau übernommen ist. | Claude | `harness/aufgabe.py`, `freigabe.py`, `vorbehalte.py`, `katalog.py` (nur Tupel), `tests/test_harness_aufgabe.py`, `test_uix_harness_aufgabe.py` | Tests: Aufruf in der Aufgabe läuft ohne Karte (Audit `aufgabe:<id>`, Zähler +1); außerhalb → Karte; `verboten`, harter Vorbehalt und Warnkarte (W-2) werden nie gedeckt; Frist/Zähler erschöpft → Karte; andere Sitzung → Karte; Cloud-Modell → keine Deckung; Vorschlag mit weitem Muster, mit Vorarbeiter als Nutzer, mit S9-Kombination → abgelehnt; Neustart des Servers lässt Aufgaben bestehen |
| N4 | **Vorarbeiter-Freigabe (HS-26 Rest).** `harness/vorarbeiter.py`: Ernennung (`vorarbeiter.json`), Entscheidung nach G2 §5.3 (Bedingungen 1–6), Frist 15 Minuten (Karte fällt an `captain`), Bremse 30/Stunde. `freigabe.py`: Karte mit `an`, `art`, `vorschau_hash`, `vorgelegt`; `einstufung` löst `vorarbeiter` auf (S2); `beantworten(… von, ueber)` mit `von` nur vom Server. `werkzeuge.py`: `freigaben_offen`, `freigabe_entscheiden`, `aufgabe_vorschlagen` (Karte `art: aufgabe` an den Captain), `aufgabe_beenden`. `api.py`: Wege `vorarbeiter`, `aufgaben`, `…/zuruecknehmen`; `desk/decisions.py`: Kartenart `aufgabe`; Fortsetzung der Agenten-Sitzung im eigenen Thread (K8). | Claude | `harness/vorarbeiter.py`, `freigabe.py`, `werkzeuge.py`, `api.py`, `desk/decisions.py`, `tests/test_harness_vorarbeiter.py`, `test_uix_harness_vorarbeiter.py` | Tests (Attrappe, kein Modell): Karte `vorarbeiter` → Vorarbeiter erlaubt mit Begründung → Datei geschrieben, Audit `von=vorarbeiter:S-…`; Karte der Stufe `captain`, mit Vorbehalt, mit Warnung → `nur_captain`; eigene Karte → `selbstfreigabe`; alter Hash → `hash_veraltet`; kurze Begründung → Fehler; 31. Entscheidung in der Stunde → Captain; nach 15 Minuten fällt die Karte an den Captain (mit Uhr-Attrappe); `von` in der HTTP-Nutzlast wird ignoriert; Captain kann jede Karte beantworten und eine Vorarbeiter-Entscheidung zurücknehmen |
| N5 | **Herkunft der Antwort (S7, K14).** `harness/herkunft.py`: Prüfung `Origin`/`Host`, Auflösung der Gegenstelle zur PID (Windows, ohne neue Abhängigkeit), Register der Harness-Prozesse (`befehl`, Läufe) und ihrer Nachkommen. `uix_server.py` ruft sie für die Antwort-Wege der Karten, Aufgaben, Ernennung und Rücknahme. Scheitert die Auflösung → nur Origin-Prüfung + Audit `HARNESS_HERKUNFT_ABGELEHNT`/Warnung. | Claude | `harness/herkunft.py`, `befehl.py` (nur Registrierung der PID), `uix_server.py`, `tests/test_harness_herkunft.py` | Tests: fremder Origin → 403; Anfrage aus einem Unterprozess von `befehl` (echter Kindprozess der Testprozesses) → abgelehnt; Anfrage des Browsers/Tests → angenommen; Auflösung nicht möglich → angenommen mit Warnung. **`befehl.py` ist Vorbehalt-Datei: die Änderung ist nur dank P-2 erlaubt.** |
| N6 | **Lauf-Typen.** `runtime/config/harness_laeufe.yaml` (G2 §6.1) und `harness/lauf.py` Teil 1: laden, prüfen, `argv_bauen(typ, parameter)` (Parameter gegen Muster, kein Shell-Interpreter, Ordner in der Wurzel). Claude baut es selbst (V4: klein, und es ist eine Sicherheitsgrenze, kein Bau für SEDRA). | Claude | `config/harness_laeufe.yaml`, `harness/lauf.py`, `tests/test_harness_lauf_typen.py` | Tests: gültige Datei; unbekannter Parameter, Muster verletzt, `;`/`|` im Wert, Ordner außerhalb → Fehler; Typ ohne `argv` → Fehler |
| N7 | **Läufe: Starter, Hülle, Register, Werkzeuge.** `harness/lauf.py` Teil 2 und `harness/lauf_huelle.py`: entkoppelter Prozess, `ausgabe.log`, `ende.json`, PID + Startzeit, Wiederanbinden beim Serverstart (`verloren`), Stopp des Prozessbaums, Grenzen (3 je Projekt, exklusiv höchstens 1), Zeitlimit. Werkzeuge `lauf_starten`, `lauf_stoppen`, `lauf_status` über Vorbehalt → Katalog → Aufgabe → Karte; Gate-Bindung = Lauf-ID + Parameter. Lauf-Typen `modell_laden`/`modell_entladen` rufen `hub.load_model`/`unload_model`. Rücknahme einer Aufgabe stoppt ihre Läufe (D-G3). Wege `laeufe`, `laeufe/<id>`, `…/stopp`; Ereignis `harness.lauf`. | Claude | `harness/lauf.py`, `harness/lauf_huelle.py`, `werkzeuge.py`, `freigabe.py`, `api.py`, `tests/test_harness_lauf.py`, `test_uix_harness_lauf.py` | Tests mit einem Wegwerf-Skript als Lauf-Typ: Start, Fortschritt, `ok`/`fehler`/`gestoppt`; Prozess überlebt `HarnessApi`-Neuanlage (Wiederanbinden), toter Prozess ohne `ende.json` → `verloren`; Parameter außerhalb des Musters → Fehler vor dem Start; ohne Freigabe kein Prozess; exklusiv-Grenze; Stopp beendet auch Kindprozesse; `modell_laden` ohne Aufgabe → Karte, mit Aufgabe, die das Modell nennt → läuft (mit Attrappe von `hub.load_model`) |
| N8 | **Lauf-Fortschritt (SEDRA-Pilot B3, rein) – erster Bau über die Harness.** `fortschritt_aus(zeilen, regel) -> {prozent, text} | None` nach G2 §6.3: Regel `zeilen` (zwei Zahlen → Prozent), `prozent` (eine Zahl mit `%`), `text` (letzte nicht leere Zeile, gekürzt auf 80 Zeichen); keine Ausnahme bei Müll, Prozent 0–100. Bau-Spec `docs/BAUSPEC_LAUF_FORTSCHRITT.md`, Referenz, Stempel, höchstens 12 versteckte Prüfungen („Versteckte Prüfungen N8“). **Gebaut wird er von SEDRA über die Vorarbeiter-Sitzung** (Aufgaben-Freigabe „Pilot“ unten, Lauf `devvm_build`); Claude prüft Diff und Tests und übernimmt nach Captain-Ja. | **SEDRA** unter Vorarbeiter (Claude: Spec, Referenz, Prüfungen, Review) | `harness/lauf_fortschritt.py` (Kandidat), `benchmarks/devvm_specs/harness_lauf_fortschritt.py`, `benchmarks/devvm_refs/harness_lauf_fortschritt/` | Stempel; die Kette Wunsch-Aufgabe → Aufgaben-Freigabe → `lauf_starten devvm_build` → Fortschritt in der Taskleiste → Kandidat → Review (Gemma) → Übernahme ist im Bericht belegt; Bau besteht 12 von 12 ODER scheitert ehrlich (dann V4 und Befund im Bericht) |
| N9 | **Endpunkte, Ereignisse, Audit.** Alle Wege und Ereignisse aus G2 §7 in `HarnessApi.handle` und `shell.yaml`; Posteingang zeigt Karten beider Arten mit Empfänger; `decision.pending/answered` für `art: aufgabe`; `harness.aufgabe`, `harness.vorarbeiter`; Audit-Namen aus G2 §7. | Claude | `harness/api.py`, `uix_server.py`, `desk/decisions.py`, `uix/shells/harness/shell.yaml`, `tests/test_uix_harness_api.py` (neue Fälle) | HTTP-Tests je Weg (404/400/403/200), Posteingang zeigt Karte + Aufgabenkarte, eine Antwort schließt beide Ansichten, Ereignisse kommen auf `/api/events` |
| N10 | **Oberfläche Freigaben.** `karte.js`: Empfänger („beim Vorarbeiter“), Begründung des Vorarbeiters, „Übersteuern“ durch den Captain; Aufgabenkarte mit Häkchen je Eintrag, Frist, rote Warnung bei weiten Mustern oder S9; neu `aufgabe.js` (Dialog „Aufgabe freigeben“ und Liste mit Rest, Rücknahme-Knopf, Schalter „Läufe stoppen“); `verlauf.js`: Werkzeugzeile mit Regel `aufgabe:T-…`; `eingabe.js` Schild „Vorarbeiter gibt frei · Aufgabe T-… Rest n, bis hh:mm“; `seite.js`: Marke am Vorarbeiter, Ernennen-Knopf. Zeilenvertrag ≤ 400 je Datei. | Claude | `uix/shells/harness/{karte,aufgabe,verlauf,eingabe,seite}.js`, `shell.css`, `tests/test_uix_harness_shell.py` | `uix_check --shell harness` 1024×700 und 1400×860 grün; Browser-Durchlauf mit Attrappe: Karte an Vorarbeiter → Entscheidung → Verlauf; Aufgabe anlegen → Aufruf ohne Karte → Rücknahme → nächster Aufruf mit Karte |
| N11 | **Oberfläche Läufe und Benachrichtigung (HS-31 bis HS-33).** `taskleiste.js`: Läufe als Knöpfe mit Fortschritt, Statusbereich „Freigaben n · beim Vorarbeiter m“, Markierung und einmaliges Blinken (`prefers-reduced-motion`), `sedra.harness.gesehen`; neu `lauf.js` (Reiter Lauf: Zustand, Log, Stopp); `reiter.js`: Reiterart `lauf`. | Claude | `uix/shells/harness/{taskleiste,lauf,reiter}.js`, `shell.css`, Tests | Browser-Durchlauf mit Attrappe: Lauf startet → Knopf „Tests 42 %“ → endet → Knopf markiert und blinkt einmal → Klick öffnet Reiter → Markierung weg; neue Karte markiert „Freigaben“; Neuladen behält ungesehene Marken; 0 Konsolenfehler |
| N12 | **Gruppe, Abnahme, Pilot, Bericht.** Gruppe `harness` enthält alle neuen Dateien; `benchmarks/harness_abnahme.py` bekommt Teil Stufe 3 (Szenarien unten). Abnahme erst ohne Modell (Attrappe), dann mit Qwen3.6 **nach Ja**; Pilot N8 als Teil der Abnahme. Bericht `docs/BAUBERICHT_HARNESS_STUFE3_<datum>.md`, Logbuch BAU mit Quote (Zeilen SEDRA gegen Zeilen Claude, L4). | Claude | `benchmarks/harness_abnahme.py`, Bericht, Logbuch | Bericht liegt vor mit Belegen, offenen Punkten und Quote; Captain entscheidet die Übernahme (G4) |

**Reihenfolge:** N1 → N2 (SEDRA-Bau parallel, braucht P-11) → N3 → N4 → N5 → N6 → N7 → N9 → N10 → N11 → N8 (Pilot, braucht N3, N4, N7) → N12.
Geschätzter Umfang: rund 1600 Zeilen Python im Paket, 350 Zeilen Oberfläche, 900 Zeilen Tests, 5 Konfigurationsdateien; davon SEDRA rund 160 Zeilen (zwei Module).

## Versteckte Prüfungen (L3, höchstens 20 je Bau; Inhalt hält Claude außerhalb der Sicht der Agenten in der Bau-Spec, D-F1)

**N2 – `deckt` und `zustand` (Entwurf 17 Punkte, gebaut 15 Prüfungen, Stand 29.10.2026):** (1) leere Liste → `None`; (2) passender Eintrag → Treffer mit `aufgabe_id`; (3) falsches Werkzeug → `None`; (4) Sitzung nicht in `sitzungen` → `None`; (5) Status `zurueckgenommen`/`erledigt` → `None`;
(6) `bis` in der Vergangenheit → `None`, genau auf der Grenze → `None`; (7) `aufrufe == max_aufrufe` → `None`, eins darunter → Treffer; (8) Datei-Glob mit `**`, groß/klein wie `katalog.passt`; (9) `befehl`-Präfix mit `*`;
(10) Lauf-ID-Glob; (11) mehrere Treffer → frühestes Ende gewinnt; (12) Gleichstand beim Ende → kleinere ID; (13) ohne Ende gewinnt zuletzt; (14) `zustand` setzt `abgelaufen` und `erschoepft`, `aktiv` bleibt `aktiv`;
(15) `zustand` ändert das Eingabeobjekt nicht; (16) fehlende Felder/Müll → kein Treffer, keine Ausnahme; (17) `ziel` mit `..` oder Laufwerk wird wie in `katalog.pfad_normal` behandelt (kein Treffer außerhalb).

**N8 – `fortschritt_aus` (Entwurf 10 Punkte, gebaut 12 Prüfungen, Stand 29.10.2026):** (1) `12/40` → 30 %; (2) `12 / 40` mit Leerzeichen; (3) `42 %` und `42.5%`; (4) Zähler größer als Nenner → 100, nie darüber; (5) Nenner 0 → `None`; (6) mehrere Zeilen → die letzte passende zählt;
(7) keine passende Zeile → `None` bei `zeilen`/`prozent`; (8) Regel `text` → letzte nicht leere Zeile, höchstens 80 Zeichen, mit `…`; (9) Müll, `None`, Nicht-Texte → `None`, keine Ausnahme; (10) Ergebnis hat immer die Schlüssel `prozent`, `text`.

## Abnahme (N12)

Zuerst alles **ohne Modell** (Attrappe von `control.execute`, Browser-Attrappe, `uix_check`); die Szenarien mit echtem Modell erst nach Ja (P-14).

| Nr | Szenario | Erwartung |
|---|---|---|
| S3-A | Zwei Sitzungen: `vorarbeiter` und `bauagent`. Der Agent will `docs/spec_entwuerfe/x.md` ändern (Katalog `vorarbeiter`). | Karte `an: vorarbeiter`; der Vorarbeiter liest die Vorschau, erlaubt mit Begründung; Datei geschrieben; Audit `von=vorarbeiter:S-…`; der Captain sieht Karte, Begründung und Entscheidung |
| S3-B | Der Agent will `runtime/…` ändern (Katalog `captain`); der Vorarbeiter versucht, die Karte zu entscheiden. Danach versucht der Vorarbeiter, eine Karte seiner eigenen Sitzung zu erlauben. | `nur_captain` bzw. `selbstfreigabe`, Karte bleibt offen und wartet auf den Captain; kein Weg über HTTP-Nutzlast `von` |
| S3-C | Der Captain gibt eine Aufgabe frei (Schreiben in einer Datei, `run_tests`, 10 Aufrufe, 30 Minuten). Der Agent arbeitet ohne Karte; ein Aufruf außerhalb → Karte; der Captain nimmt zurück. | Aufrufe in der Aufgabe ohne Karte, Zähler stimmt, nach Rücknahme der nächste Aufruf mit Karte, laufender Lauf gestoppt, Audit lückenlos |
| S3-D | `lauf_starten run_tests` (Gruppe `harness`) mit Karte an den Vorarbeiter; Lauf in der Taskleiste mit Fortschritt; Lauf endet. | Knopf „Tests n %“, nach dem Ende markiert und einmal geblinkt, Klick öffnet den Reiter; Neustart des Servers mitten im Lauf → Lauf wird wieder angezeigt |
| S3-E | Herkunft: Ein Agent schreibt unter einer Aufgabe ein Skript, das `POST /api/harness/karten/<id>` mit `erlauben` sendet, und startet es. | Antwort abgelehnt (S7), Audit `HARNESS_HERKUNFT_ABGELEHNT`; ohne die Aufgabe hätte schon der Aufruf eine Karte erzeugt |
| S3-F | **Pilot N8:** Der Captain nennt dem Vorarbeiter den Wunsch „Fortschritt aus Log-Zeilen lesen“; der Vorarbeiter schlägt die Aufgabe vor, der Captain gibt sie frei, der Vorarbeiter startet `spec_check` und `devvm_build`; der Kandidat entsteht; Gemma-4-12B (Vorlage `pruefer`) prüft; der Captain übernimmt oder verwirft. | Kette belegt im Bericht (Audit-Zeilen, Taskleiste, Kandidat, Prüfung); Misserfolg wird ehrlich als Befund und V4-Entscheidung festgehalten |

Bekannt-rote Tests unverändert (`test_k5` der Cockpit-Baum-Tastatur, nicht Teil dieser Stufe). Gruppen `scheduler desk orchestra uix harness` laufen vollständig.

## Aufgaben-Freigabe für den Pilot (Vorschlag; legt der Captain zum Zeitpunkt an, P-12)

| Feld | Inhalt |
|---|---|
| Sitzungen | die Vorarbeiter-Sitzung |
| Erlaubt | `datei_lesen`, `dateien_auflisten`, `suchen` auf `**`; `datei_schreiben` auf `docs/spec_entwuerfe/**`; `befehl` `python benchmarks/spec_check.py harness_lauf_fortschritt *`; `lauf_starten` `devvm_build` (Parameter `spec=harness_lauf_fortschritt`, `profile=standard`) |
| Modelle | `coder.local_primary` (die Rolle des Bau-Profils `standard`; so steht es in `harness_laeufe.yaml`, Stand 29.10.2026) |
| Ende | höchstens 3 Stunden, 60 Aufrufe, `bei_erledigt` |
| Nicht enthalten | Schreiben in `runtime/**` (der Kandidat liegt in `runtime_data/devvm_candidates/`, die Übernahme macht Claude nach Captain-Ja), Push, Katalog, `local_config/` |

## Berechtigungen vorab (ENTWICKLUNG.md: „Berechtigungen werden vorher eingeholt“)

Dieselbe Liste und Nummerierung wie in G2 §9 (dort mit Begründung und Vorschlag); hier **je Aufgabe zugeordnet**. Was nicht aufgeführt ist, läuft nicht und wird nicht mitten in der Arbeit nachgefragt.

| Nr | Berechtigung (Kurz) | Aufgaben | Zeitpunkt |
|---|---|---|---|
| P-1 | Worktree/Branch `harness/stufe-3`, Commits, kein Push/Merge | alle | sofort nach G3 |
| P-2 | Schreiben in `harness/` (neu: `vorlagen`, `aufgabe`, `vorarbeiter`, `lauf`, `lauf_huelle`, `herkunft`; ändern: `freigabe`, `vorbehalte`, `katalog` nur Tupel, `werkzeuge`, `schleife`, `api`, `sitzung`, `befehl` nur PID-Registrierung) | N1, N3, N4, N5, N6, N7, N9 | sofort |
| P-3 | Schreiben `uix_server.py`, `desk/decisions.py` | N4, N5, N9 | sofort |
| P-4 | Schreiben `uix/shells/harness/*` (inkl. neu `aufgabe.js`, `lauf.js`) | N10, N11 | sofort |
| P-5 | Schreiben `config/harness_vorlagen/*`, `config/harness_laeufe.yaml`, `config/freigabe_katalog.beispiel.yaml`; **nicht** `local_config/` | N1, N3, N6 | sofort |
| P-6 | Schreiben Tests und `benchmarks/harness_abnahme.py` | alle | sofort |
| P-7 | Schreiben Bau-Specs `devvm_specs/`, `devvm_refs/`, `docs/BAUSPEC_*` | N2, N8 | vor P-11/P-12 |
| P-8 | Schreiben `docs/BAUBERICHT_HARNESS_STUFE3_*`, Logbuch-Zeilen, Statuszeilen der Specs | alle | laufend |
| P-9 | Befehle ohne Modell: `run_tests`, `uix_check`, `spec_check --vm`, `git` auf dem Branch | alle | laufend |
| P-10 | Browser-Attrappe (Playwright, ohne Modell) | N10, N11 | N10, N11 |
| P-11 | Modell laden + Lauf: SEDRA-Bau B1 (`devvm_build`, Qwen3.6-35B-A3B, exklusive GPU, ~6 min) | N2 | **auf Ansage** |
| P-12 | Modell laden + Lauf: Pilot B3 über die Harness (Vorarbeiter Qwen3.6, Aufgabe oben, `spec_check --vm`, `devvm_build`) | N8, S3-F | **auf Ansage** |
| P-13 | Modell laden: Review mit Gemma-4-12B (Vergleichslauf zweites Modell, Wechsel, nie gleichzeitig) | N2, N8, S3-F | **auf Ansage** |
| P-14 | Modell laden: Abnahme S3-A bis S3-F mit Qwen3.6-35B-A3B | N12 | **auf Ansage** |
| P-15 | Lesen nach Modellläufen: `nvidia-smi`, Ereignisprotokoll auf Treiberfehler | N2, N8, N12 | nach jedem Modelllauf |
| nicht beantragt | `local_config/`, Push, Merge, `main`, Löschen, Downloads, Engine-Wechsel, `core/**`/Guard, Dauerläufe (`nachtlauf_3d`), Nemotron-/9B-Läufe, Cloud | – | – |

Bei jedem Modelllauf gilt weiter: Lade-Lease holen, Rezepte und Engine nicht ändern, Modell danach entladen, GPU vorher/nachher messen (ENTWICKLUNG.md Regel 2, Bericht Stufe 2).

## Grenzen der Stufe 3

- Keine Änderung am Katalog des Captains (`local_config/`) und an `einstufen`; keine Änderung an Guard, Inhaltsschutz, `core/**`.
- Keine Wunsch-Anbindung (Eingabe, Spec-Schreiber, Wunsch-Ordner, Review-Urteil): das ist das Wunsch-G2 nach Abnahme dieser Stufe. `wunsch_id` ist nur ein Feld.
- Kein Start-Menü, kein Statusbereich über die Zellen hinaus, keine Einstellungen (Stufen 4 und 5); keine Läufe aus dem Terminal in der Taskleiste (D-G7).
- Keine Cloud-Modelle in Aufgaben und Läufen; kein automatisches Wecken von Sitzungen; kein automatisches Zurückdrehen von Änderungen.
- Cockpit und `chat_reply` bleiben unverändert.

## Fragen an den Captain (Vorschlag jeweils fett; die Designfragen D-G1 bis D-G8 stehen in G2 §10)

| Nr | Frage | Vorschlag |
|---|---|---|
| D-H1 | **Wer baut was?** SEDRA nur die zwei reinen Module (N2 `deckt`, N8 `fortschritt_aus`, zusammen rund 160 Zeilen); alles andere ist Harness-Code, Integration oder Oberfläche und bleibt bei Claude (L4). Die Quote Claude/SEDRA liegt dadurch deutlich über 1 (V4). | **Ja, so.** HS-E5 („ab Stufe 3 bauen SEDRA-Agenten“) wird damit nur durch den Pilot N8 erfüllt; mehr SEDRA-Anteil gibt es erst, wenn SEDRA Oberfläche oder Integration bauen kann (Stufe 4/5, eigene Frage dort). |
| D-H2 | **Zwei Abnahmen?** 3a = N1 bis N5, N9 bis N10 (Vorlage, Aufgabe, Vorarbeiter, Herkunft, Oberfläche Freigaben); 3b = N6, N7, N8, N11 (Läufe, Taskleiste, Pilot). | **Ja, zwei Abnahmen und zwei Berichte.** 3a ist ohne GPU-Fragen (K13) prüfbar; 3b hängt am Modell- und Lauf-Verhalten. |
| D-H3 | **Pilot vor der Übernahme?** Der Pilot N8 ist Teil der Abnahme von 3b. | **Ja.** Eine Stufe, die das Selbst-Bauen ermöglichen soll, wird erst mit einem echten Bau abgenommen. |
| D-H4 | **Versteckte Prüfungen** liegen wie in Stufe 2 im `HIDDEN` der Bau-Spec (Abweichung von D-F1 vom Captain bestätigt?). | **Ja**, sonst kann `spec_check` die Referenz nicht prüfen. |
| D-H5 | **Übernahme von N2** unmittelbar nach Review und Captain-Ja (wie `einstufen`), Referenz im Paket bis dahin. | **Ja.** |
| D-H6 | **Abnahmemodell:** nur Qwen3.6-35B-A3B (Nemotron E4B hat C2/C4 nicht bestanden, kein neuer Lauf). | **Ja, nur Qwen**; Gemma nur als Prüfer in S3-F. |
| D-H7 | **Berechtigungen:** P-1 bis P-10 und P-15 jetzt ja; P-11 bis P-14 „auf Ansage“ (erlaubt, Start erst auf dein Wort in der Bau-Sitzung). | **So.** Jede andere Zeile streichst du, dann läuft sie nicht. |
| D-H8 | **Worktree:** eigener Worktree `harness/stufe-3`; war ein zweiter Worktree wieder gesperrt (Stufe 2), arbeitet die Bau-Sitzung im bestehenden Worktree auf dem neuen Branch weiter. | **So.** |

Nach deinen Antworten tragen wir die Entscheidungen in beide Specs ein; erst dann beginnt der Bau (N1).

## Entscheidungen des Captains (29.10.2026 08:52)

Captain: „Ja, so“ – D-H1 bis D-H8 gelten wie vorgeschlagen (SEDRA baut nur N2 und N8; zwei Abnahmen 3a/3b; Pilot Teil von 3b; Prüfungen im `HIDDEN`; N2 sofort nach Review übernehmen; nur Qwen; Worktree-Regel wie D-H8).
Berechtigungen: P-1 bis P-10 und P-15 **ja**, P-11 bis P-14 **auf Ansage** (Start erst auf ausdrückliches Wort des Captains in der Bau-Sitzung).
G3 Stufe 3 ist damit freigegeben; der Bau beginnt mit N1.
