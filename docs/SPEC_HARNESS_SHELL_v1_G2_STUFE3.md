# SPEC Harness-Shell v1 – G2 Design für Stufe 3 (29.10.2026)

Gehört zu `SPEC_HARNESS_SHELL_v1.md` (G1: HS-19, HS-26 Rest, HS-27, HS-29, HS-31 bis HS-33), `SPEC_HARNESS_SHELL_v1_G2.md` (Stufe 1 und 2),
`SPEC_HARNESS_SHELL_v1_G3_STUFE2.md` samt Nachtrag und `SPEC_WUNSCH_ANBINDUNG_v1.md` (WQ-1 bis WQ-4).
Stand des Codes: Zweig `spec/agenten-orchestrierung`, `d9b8f97` (Paket `harness/` 1886 Zeilen, Gruppe `harness` 122 Tests grün).
**Dies ist nur ein Entwurf (Gate G2). Es wird nichts gebaut, bis der Captain die Fragen in §10 und die Berechtigungen in §9 entschieden hat.**
Bau-Aufgaben: `SPEC_HARNESS_SHELL_v1_G3_STUFE3.md`.

Stufe 3 = **Verantwortung teilen**: Der Captain muss nicht jede Karte selbst beantworten, ohne dass die Grenzen weichen.
Drei Bausteine: **Vorlage** (HS-19, der Vorarbeiter als Sitzungsart), **Vorarbeiter-Freigabe** (HS-26: er entscheidet Karten der Stufe
`vorarbeiter`), **Aufgaben-Freigabe** (HS-27: der Captain öffnet für eine Aufgabe eine Liste von Aufrufen, befristet und gezählt).
Dazu **Läufe** (`lauf_starten`/`lauf_stoppen`, HS-20 Rest) mit Anzeige und Benachrichtigung in der Taskleiste (HS-31 bis HS-33).

## 1. Was vorhanden ist und genutzt wird

| Baustein | Fundstelle | Nutzung in Stufe 3 |
|---|---|---|
| Einstufung | `katalog.einstufen(regeln, werkzeug, ziel)` (SEDRA-Bau, übernommen), `katalog.passt` | unverändert; die Stufe `vorarbeiter` gibt es schon, sie wirkt bisher wie `captain` |
| Vorbehalte | `vorbehalte.pruefen(werkzeug, ziel, args, vorhanden)` → Grund oder `None` | bleibt der harte Teil; dazu ein weicher Teil (K10) |
| Freigabe | `freigabe.Kiste.aufruf`, `einstufung`, `beantworten` (eine Tür), `Karten` (eine Datei je Karte, `uebernehmen` gegen Doppelantwort) | wird erweitert: Aufgabe vor Karte, Empfänger `an`, Entscheidung durch den Vorarbeiter |
| Warnung beim Überschreiben | `werkzeuge.ersetzung_warnung`, Karte mit `warnung` | bleibt Captain-Sache (§4.4) |
| Schleife | `schleife.laufen`, `system_prompt`, `ENDEN`, Zähler `letzter` (HS-14) | Systemprompt aus der Vorlage; Aufgabe wird je Aufruf geprüft |
| Sitzungskopf | `sitzung.anlegen(..., vorlage=None)`, Kopf `vorlage` | Feld ist da, wird ab jetzt gefüllt |
| Karten und Posteingang | `desk/decisions.collect` Quelle `harness`, `HarnessApi.beantworten`, Ereignisse `decision.pending/answered` | zweite Kartenart `aufgabe`, Karten mit Empfänger |
| Ströme und Ereignisse | `strom.Antwort`, `/api/events`, `harness.antwort`, `harness.sitzung` | neu `harness.lauf`, `harness.aufgabe`, `harness.vorarbeiter` |
| Taskleiste | `taskleiste.js`: Mitte = offene Reiter mit laufender Antwort, rechts `/api/strip` | Mitte um Läufe erweitert, Markierung (HS-33) |
| Modell laden | `/api/model/load`, `/api/model/unload` (`hub.load_model`, `unload_model`) | nur als Lauf-Typ `modell_laden`/`modell_entladen` (§6), nie als freies Werkzeug |
| Läufe heute | Skripte in `runtime/benchmarks/` (`run_tests.py`, `spec_check.py`, `devvm_build.py`, `nachtlauf_3d.py`, `harness_abnahme.py`); `labor_runs.list_runs` liest nur `redesign/lauf_*.jsonl` | siehe K11 |

## 2. Konflikte mit dem vorhandenen Code

| Nr | Konflikt | Folge für das Design |
|---|---|---|
| K6 | `HarnessApi.anlegen` lehnt jede Vorlage ab (`vorlage_ab_stufe_3`); `schleife.SYSTEM` ist ein fester Text; die Kiste kennt keine Werkzeugauswahl je Sitzung. | Vorlagen (§3) ersetzen die Sperre; `system_prompt` bekommt den Vorlagentext, `Kiste` eine Whitelist. |
| K7 | `freigabe.einstufung` setzt `wirkt_als = captain`, wenn die Stufe `vorarbeiter` heißt; `freigabe.py` ist Harness-Code mit Vorbehalt (SEDRA ändert ihn nie). | Die Auflösung `vorarbeiter → Vorarbeiter-Sitzung oder captain` kommt in `freigabe.py` – gebaut von Claude (§5, §7). |
| K8 | `HarnessApi.beantworten` schreibt `von='captain'` fest, wirft `antwort_laeuft`, wenn die **Sitzung der Karte** antwortet, und setzt deren Schleife aus dem Anfrage-Thread fort. Eine Vorarbeiter-Entscheidung kommt dagegen **aus der Schleife einer anderen Sitzung** (ein Werkzeugaufruf). | `beantworten` bekommt `von` als Parameter, den **nur der Server** setzt; die Fortsetzung der Agenten-Sitzung läuft in eigenem Thread, der Aufruf des Vorarbeiters wartet nicht darauf (§5.3). Höchstens 8 laufende Antworten (`strom.MAX_LAUFEND`) gelten weiter. |
| K9 | `katalog.WERKZEUGE` kennt weder `lauf_starten` noch `lauf_stoppen` noch `modell_laden`. `einstufen` darf nicht angefasst werden (SEDRA-Bau, übernommen). | Nur das Tupel `WERKZEUGE` wächst. Das Ziel eines Laufs ist seine **Lauf-ID** (`run_tests`); `passt` behandelt sie wie einen Pfad-Glob (§6.2) – kein Eingriff in `einstufen`. |
| K10 | `vorbehalte.py` sagt im Kopf „keine Aufgaben-Freigabe macht einen dieser Aufrufe frei“, HS-28 erlaubt aber **Modelle laden/entladen innerhalb einer freigegebenen Aufgabe**. Beides gleichzeitig ginge nicht. | Zwei Klassen: **hart** (`pruefen`, wie heute – auch Aufgaben helfen nicht) und **aufgabe_offen** (neue Funktion `pruefen_weich`: Modelle laden/entladen, Lauf-Typen mit `modell_weg`). Die weichen Fälle sind `captain`, außer eine Aufgabe nennt das Modell ausdrücklich (§4.2). |
| K11 | Es gibt **kein Lauf-Register**. Läufe sind Skripte, die der Captain im Terminal startet; `labor_runs` liest nur Umbau-Protokolle. HS-31 verlangt „jeder laufende Lauf“. | Stufe 3 führt ein Register nur für Läufe, die die Harness startet (§6). Läufe aus dem Terminal bleiben unsichtbar (Frage D-G7). |
| K12 | `befehl.py` ist synchron, ≤ 600 s, der Prozess stirbt mit der Antwort (Stopp beendet den Baum). Läufe dauern Minuten bis Stunden und müssen einen Neustart des Servers überleben. | Eigener Starter `lauf.py` mit entkoppeltem Prozess, Hülle, Log-Datei und PID-Datei (§6.3); `befehl.py` bleibt unverändert. |
| K13 | **Exklusive Läufe nehmen dem Vorarbeiter das Modell.** `devvm_build` und Messläufe fordern nach ENTWICKLUNG.md Regel 2 den Modus *exklusiv*; der Scheduler stoppt dann den Modellserver, auf dem die Vorarbeiter-Sitzung läuft. | Der Vorarbeiter startet den Bau, kann ihn aber nicht währenddessen betreuen: die Sitzung antwortet `kein_modell`, bis der Lauf endet (§6.4, Frage D-G1). Kein stiller Modellwechsel. |
| K14 | `HarnessApi` ist unauthentisch: `POST /api/harness/karten/<id>` beantwortet jede Anfrage von `127.0.0.1`. Ein Agent mit `befehl python …` und einem Skript, das er selbst geschrieben hat, könnte die eigene Karte (oder seine Aufgabe) bestätigen. In Stufe 2 war das durch „jeder Befehl braucht eine Karte“ gedeckt; mit Aufgaben-Freigaben (HS-27) wird es zur echten Lücke. | Schutz S6/S7 (§5.4): Herkunftsprüfung der Anfrage und Verbot, Schreiben und Ausführen derselben Dateien in einer Aufgabe zu öffnen. |

## 3. Vorlagen (HS-19)

**Ablage:** `runtime/config/harness_vorlagen/<id>.yaml` (Daten) und `<id>.md` (Systemprompt). Eine gleichnamige Datei in
`local_config/harness_vorlagen/` (Captain) hat Vorrang. Beides ist **Vorbehalt** (§5.4/S8): kein Agent schreibt seine eigene Vorlage.

```yaml
harness_vorlage:
  version: 1
  id: vorarbeiter
  name: Vorarbeiter
  beschreibung: Leitet und prüft; entscheidet Karten der Stufe „vorarbeiter“ anderer Sitzungen.
  system: vorarbeiter.md              # Datei neben der YAML, höchstens 12 000 Zeichen
  werkzeuge: [datei_lesen, dateien_auflisten, suchen, datei_schreiben, datei_aendern, befehl,
              lauf_starten, lauf_stoppen, lauf_status, freigaben_offen, freigabe_entscheiden, aufgabe_vorschlagen, aufgabe_beenden]
  rechte: {vorarbeiter_freigabe: true, aufgaben_vorschlagen: true}
  modell: coder.llama_qwen35          # Vorschlag für die Modellwahl; geladen wird nie von selbst
  max_zuege: 24
```

- Mitgeliefert: **`vorarbeiter`** (Inhalt aus `START_PROMPT_VORARBEITER_BIONIC.md`, ohne die Bionic- und Port-1234-Hinweise, mit den Harness-Werkzeugen
  und den Regeln aus §5), **`bauagent`** (Coder: Lesen, Schreiben, `befehl`, kein `freigabe_*`; seine Karten der Stufe `vorarbeiter` gehen an den Vorarbeiter),
  **`pruefer`** (Review: nur Lesen und `befehl` für Tests; Modell Gemma-4-12B laut WQ-2, Vorschlag). `spec-schreiber` (WQ-1) kommt mit dem Wunsch-G2.
- Beim Anlegen einer Sitzung mit `vorlage` prüft die Harness: Vorlage gültig, jedes Werkzeug bekannt, Rechte bekannt. Der Kopf der Sitzung speichert `vorlage` und
  den Hash des Vorlagentexts (Nachvollziehbarkeit HS-29: welche Fassung war gültig).
- `werkzeuge` ist eine **Whitelist**: die Kiste einer Antwort bietet dem Modell nur diese (Schnitt mit den vorhandenen). Die Rechte prüft der **Server** bei jedem Aufruf
  (nicht die Kiste allein): `freigabe_entscheiden` ohne `rechte.vorarbeiter_freigabe` und ohne Ernennung (§5.1) ist ein Fehler.
- Die Modellwahl bleibt beim Captain (Eingabefeld). Passt das geladene Modell nicht zur Vorlage, zeigt das Eingabefeld einen Hinweis („Vorlage empfiehlt …“), mehr nicht.

## 4. Aufgaben-Freigabe (HS-27)

### 4.1 Datenformat

Ablage `<projekt>/runtime_data/harness/aufgaben/T-<8 Hex>.json`, atomar geschrieben (wie die Karten); Änderungen nur über `aufgabe.py`, jede mit Audit.

```json
{"version": 1, "id": "T-1A2B3C4D", "titel": "Bau lauf_fortschritt (Pilot)", "projekt": "sedra-entwicklung",
 "sitzungen": ["S-11111111", "S-22222222"],
 "erlaubt": [
   {"werkzeug": "datei_lesen",   "muster": "**"},
   {"werkzeug": "datei_schreiben", "muster": "docs/spec_entwuerfe/**"},
   {"werkzeug": "befehl",        "muster": "python benchmarks/spec_check.py harness_lauf_fortschritt *"},
   {"werkzeug": "lauf_starten",  "muster": "devvm_build"}],
 "modelle": ["coder.llama_qwen35"],
 "ende": {"bis": "2026-10-29T18:00:00+02:00", "max_aufrufe": 60, "bei_erledigt": true},
 "von": "captain", "vorschlag_von": "S-11111111", "wunsch_id": null,
 "status": "aktiv", "aufrufe": 0, "angelegt": "…", "zuletzt": null, "beendet": null, "grund": null}
```

- `status` ∈ `aktiv` · `erledigt` · `abgelaufen` · `erschoepft` · `zurueckgenommen`. Nur `aktiv` deckt Aufrufe.
- `sitzungen`: wer die Freigabe nutzen darf (mindestens eine). Eine andere Sitzung profitiert nicht davon.
- `erlaubt`: Werkzeug + Muster in **derselben Schreibweise wie der Katalog** (Datei-Glob relativ zur Projektwurzel; bei `befehl` Präfix mit `*`; bei `lauf_starten` Lauf-ID-Glob).
- `modelle`: Rezept-IDs, die ein Lauf `modell_laden` oder ein Lauf-Typ mit `braucht_modell` verwenden darf (HS-28). Ohne Eintrag bleibt jedes Laden eine Captain-Karte.
- `ende`: **mindestens eins** von `bis` (höchstens 24 h ab Anlegen) und `max_aufrufe` (höchstens 500) ist Pflicht (D-G4); `bei_erledigt` erlaubt dem Captain und dem Vorarbeiter,
  die Aufgabe mit `aufgabe_beenden` zu schließen. Beenden verengt nur und ist deshalb dem Vorarbeiter erlaubt, Verlängern und Erweitern nicht.
- `wunsch_id` ist ein reiner Verweis für die Wunsch-Anbindung (§8); Stufe 3 wertet ihn nicht aus.
- Gilt nur für **lokale** Modelle (G1 HS-27, Spec 3): Ist das Modell der Sitzung ein Cloud-Modell, deckt die Aufgabe nicht.

### 4.2 Deckung und Zähler (reines Modul `aufgabe_deckung`)

`deckt(aufgaben, sitzung_id, werkzeug, ziel, jetzt) -> {aufgabe_id, eintrag} | None`:
1. Nur Aufgaben mit `status == aktiv`, `sitzung_id ∈ sitzungen`, `jetzt < ende.bis` (falls gesetzt), `aufrufe < ende.max_aufrufe` (falls gesetzt).
2. Ein Eintrag passt, wenn `werkzeug` gleich ist und `katalog.passt(muster, werkzeug, ziel)` gilt (dieselbe Regel wie im Katalog; kein zweites Muster-Verfahren).
3. Mehrere Treffer: die Aufgabe mit dem frühesten Ende (ohne Ende zuletzt), dann die älteste ID – deterministisch.
4. `zustand(aufgabe, jetzt)` liefert den Status nach Ablauf (`abgelaufen`, `erschoepft`) – rein, ohne Dateizugriff.
Das Hochzählen (`aufrufe += 1`) geschieht erst bei Ausführung, unter einer Sperre je Aufgabe; ein Aufruf, der bei der Ausführung am Zähler scheitert, wird zur Karte (Stufe wie ohne Aufgabe).

### 4.3 Einstufung mit Aufgabe (ersetzt die Skizze in G2 §3.5)

```
Aufruf ─► harter Vorbehalt (vorbehalte.pruefen)?  ── ja ──► captain, fest (Aufgabe hilft nicht)
            │ nein
          Katalog: Stufe ── verboten ──► verboten (Aufgabe hilft nicht)
            │ frei                                  │ captain | vorarbeiter | (keine Regel)
            ▼                                       ▼
          läuft (Audit katalog:<regel>)      Warnung W-2 gesetzt?  ── ja ──► Karte an captain (Aufgabe hilft nicht)
                                                    │ nein
                                             weicher Vorbehalt (pruefen_weich)? ── ja ──► nur eine Aufgabe, die das Modell nennt, deckt
                                                    │
                                             aufgabe.deckt(…)?  ── ja ──► läuft (Audit aufgabe:<id>), Zähler +1
                                                    │ nein
                                             Stufe vorarbeiter und Empfänger vorhanden? ── ja ──► Karte an vorarbeiter
                                                    │ nein
                                                    └──► Karte an captain
```

- Die Aufgabe hebt `captain` und `vorarbeiter` auf „läuft“. Sie hebt **nie** `verboten`, **nie** einen harten Vorbehalt, **nie** eine Warnkarte (W-2) – Kasten und Captain-Entscheidung bleiben.
- Ein Aufruf, der der Aufgabe entspricht, aber `frei` ist, wird nicht gezählt (er braucht keine Aufgabe).
- Karte `an vorarbeiter` nur, wenn für das Projekt ein Vorarbeiter ernannt ist (§5.1), die Sitzung des Aufrufs **nicht** diese Vorarbeiter-Sitzung ist (S2) und kein Vorbehalt vorliegt.
- Werkzeugzeile und Schild zeigen die Aufgabe: Stufe `aufgabe`, Regel `aufgabe:T-…`, „Rest n Aufrufe, bis hh:mm“.

### 4.4 Rücknahme und Ende (HS-29)

- `POST /api/harness/aufgaben/<id>/zuruecknehmen` (nur Captain, §5.4/S7): Status `zurueckgenommen`, Audit, Ereignis `harness.aufgabe`. Wirkung:
  der **nächste** Aufruf wird wieder normal eingestuft; Schleifen prüfen die Deckung bei jedem Aufruf. Ein laufender `befehl`, der unter dieser Aufgabe lief, bekommt das Abbruch-Signal.
  Läufe der Aufgabe werden gestoppt, wenn der Captain den Schalter „Läufe stoppen“ lässt (Vorgabe: an, D-G3). Was schon geschrieben ist, bleibt – die Oberfläche zeigt den Diff-Weg (`git diff`) und die Liste der Aufrufe der Aufgabe.
- Ablauf und Erschöpfung geschehen von selbst beim nächsten Zugriff (`zustand`), mit Audit und Ereignis; eine Aufgabe wird nie stillschweigend verlängert.

## 5. Vorarbeiter-Freigabe (HS-26)

### 5.1 Ernennung und Karten mit Empfänger

- **Ernannt** wird eine Sitzung mit Vorlage `vorarbeiter` (Recht `vorarbeiter_freigabe`) durch den Captain: `POST /api/harness/vorarbeiter {projekt, sitzung_id}`; Ablage
  `runtime_data/harness/vorarbeiter.json` (`{projekt: {sitzung_id, ernannt, von}}`), genau einer je Projekt, `DELETE` entzieht. Audit `HARNESS_VORARBEITER_ERNANNT`. Die Seitenleiste markiert ihn.
- Eine Karte bekommt **`an`** ∈ `captain` · `vorarbeiter`, **`art`** ∈ `werkzeug` · `aufgabe`, **`vorschau_hash`** (SHA-256 über Ziel, Argumente und Vorschau) und bei Bedarf
  **`vorgelegt`** `{von, notiz, zeit}`. Alte Karten ohne diese Felder gelten als `an: captain`, `art: werkzeug`.
- Der **Captain sieht jede Karte** (Posteingang, Verlauf) und kann auch eine Karte `an: vorarbeiter` selbst beantworten; der Vorarbeiter sieht nur seine.

### 5.2 Werkzeuge des Vorarbeiters

| Werkzeug | Zweck | Prüfung |
|---|---|---|
| `freigaben_offen` | Karten `an: vorarbeiter` mit voller Vorschau, `vorschau_hash`, Sitzung, Regel | liest nur (frei) |
| `freigabe_entscheiden {karte_id, weg, begruendung, vorschau_hash}` | `erlauben` · `ablehnen` · `vorlegen` (bleibt offen, geht an den Captain, mit Notiz) | §5.3 |
| `aufgabe_vorschlagen {…Format 4.1 ohne von/status}` | legt eine **Karte `art: aufgabe` an den Captain** an | §5.4/S4 |
| `aufgabe_beenden {id, grund}` | schließt eine aktive Aufgabe (nur verengen) | Recht der Vorlage |

`lauf_*` stehen in §6. Dateien lesen, schreiben und `befehl` stuft der Katalog wie bei jeder Sitzung ein; der Vorarbeiter hat dafür keine Sonderrechte.

### 5.3 Wann eine Vorarbeiter-Entscheidung gilt

`freigabe_entscheiden` ruft `freigabe.beantworten(…, von='vorarbeiter:<sitzung_id>', ueber='werkzeug')` – dieselbe Tür wie Captain-Karte und Posteingang (HS-22), dasselbe Audit,
`von` und `ueber` kommen aus dem Server, nie aus den Argumenten des Modells. Der Server lehnt ab (`nur_captain`, `nicht_ernannt`, `selbstfreigabe`, `hash_veraltet`, `begruendung_fehlt`,
`zu_viele`), wenn eine der Bedingungen fehlt:

1. Die aufrufende Sitzung ist die ernannte Vorarbeiter-Sitzung des Projekts und läuft mit der Vorlage (**S1**).
2. Die Karte hat `an: vorarbeiter`, `art: werkzeug`, **keinen Vorbehalt** und **keine `warnung`** (**S3**); Stufe `captain` kann er nur mit `vorlegen` weiterreichen.
3. Die Karte gehört **nicht** zur Sitzung des Vorarbeiters selbst (**S2**) und nicht zu einer Antwort, die er gerade fortsetzt.
4. `vorschau_hash` ist der aktuelle der Karte – er hat die Vorschau also in dieser Fassung gelesen (**S5**).
5. `begruendung` hat mindestens 15 Zeichen und steht in Audit, Karte und am Werkzeugaufruf des Agenten (HS-29).
6. Höchstens 30 Vorarbeiter-Entscheidungen je Stunde und Projekt, danach gehen neue Karten an den Captain (**S6**, Bremse; einstellbar nur in der Vorlage).

Danach wie jede Antwort: Guard-`approve` bzw. `reject`, Werkzeug mit Token, die Agenten-Sitzung wird fortgesetzt (eigener Thread, K8). **Frist (D-G2):** Eine Karte `an: vorarbeiter`, die
15 Minuten offen bleibt, fällt an den Captain (`an` wird `captain`, Ereignis, Audit) – es hängt nie etwas an einer Sitzung, die niemand weckt.

### 5.4 Schutz gegen Selbstfreigabe (Zusammenfassung)

| Nr | Schutz | Wo |
|---|---|---|
| S1 | Identität kommt vom Server (Sitzung der laufenden Schleife, Ernennung in `vorarbeiter.json`), nie aus Modelleingabe oder HTTP-Nutzlast (`von` in der Nutzlast wird ignoriert). | `freigabe.py`, `api.py` |
| S2 | Der Vorarbeiter entscheidet keine Karte, die seine eigene Sitzung ausgelöst hat; in seiner Sitzung wirkt Stufe `vorarbeiter` wie `captain`. | `freigabe.einstufung` |
| S3 | Kein Entscheiden bei Stufe `captain`, Vorbehalt, Warnkarte (W-2) oder Aufgabenkarte. | `freigabe.beantworten` |
| S4 | Der Vorarbeiter **legt keine Aufgaben-Freigabe an**, er schlägt sie vor (Karte an den Captain). Ein Vorschlag darf die Vorarbeiter-Sitzung nicht als Nutzer enthalten, keine **weiten** Muster (§4.1: Dateimuster mit weniger als 5, `befehl`-Muster mit weniger als 10 Zeichen ohne Platzhalter, jedes führende `*`) und nie Muster, die einen harten Vorbehalt treffen. Der Captain kann bei sich selbst weitere Muster eintragen. | `aufgabe.py` |
| S5 | Entscheidung nur mit dem aktuellen `vorschau_hash`; ändert sich die Karte, muss er neu lesen. | `freigabe.beantworten` |
| S6 | Bremse (30/Stunde) und Frist (15 Minuten) – nichts bleibt hängen, nichts läuft unbegrenzt durch. | `freigabe.py` |
| S7 | **Herkunft der Antwort** (K14): Antworten über HTTP auf Karten, Aufgaben, Ernennung und Rücknahme verlangen `Origin`/`Host` des eigenen Servers und werden abgelehnt, wenn der anfragende Prozess ein Nachkomme eines Harness-Prozesses ist (`befehl`, Lauf – die Harness führt die PIDs). Auflösung der Gegenstelle ohne neue Abhängigkeit (kein `psutil` im Projekt): `GetExtendedTcpTable` über `ctypes` oder `netstat -ano`. Grenze: schützt nicht gegen Prozesse außerhalb der Harness (das Terminal des Captains); ohne Auflösung gilt nur die Origin-Prüfung, mit Warnung im Audit (D-G5). | `herkunft.py`, `uix_server.py` |
| S8 | Zusätzliche **harte Vorbehalte** (Pfade, Schreiben): `harness/{aufgabe,vorarbeiter,lauf,lauf_huelle,herkunft}.py`, `runtime/config/harness_vorlagen/**`, `runtime/config/harness_laeufe.yaml`, `**/runtime_data/harness/**` (Karten, Aufgaben, Ernennung, Läufe). Der Katalog-Vorbehalt `**/freigabe_katalog*.yaml` besteht weiter. | `vorbehalte.py` |
| S9 | In einer Aufgabe darf nicht zugleich ein Dateimuster P zum Schreiben **und** ein `befehl`-Muster stehen, das beliebige Dateien ausführt (`python *`, `powershell *`, `cmd *` …): Schreiben-dann-Ausführen öffnet S7 nicht, aber den Katalog. Prüfung beim Anlegen; für Vorschläge ein Fehler, für den Captain eine rote Warnung auf der Karte. | `aufgabe.py` |

## 6. Läufe (HS-20 Rest, HS-31 bis HS-33)

### 6.1 Lauf-Typen

Ablage `runtime/config/harness_laeufe.yaml` (Repo, harter Vorbehalt). Ein Lauf ist **kein freier Befehl**: nur Typen aus dieser Liste, nur Parameter, die ihr Muster erfüllen.

```yaml
harness_laeufe:
  version: 1
  laeufe:
    - id: run_tests
      name: Tests
      argv: [python, benchmarks/run_tests.py, "{gruppen}"]
      ordner: runtime
      parameter: {gruppen: {muster: '^[a-z_ ]{1,80}$', vorgabe: harness}}
      gpu: keine                # keine · slot · exklusiv
      modell_weg: false         # nimmt dem Gespräch das Modell
      braucht_modell: false
      fortschritt: {art: zeilen, regex: '^\s*(\d+)\s*/\s*(\d+)\b'}   # 12/40 → 30 %
      zeitlimit_min: 90
```

Vorgesehene Typen: `run_tests`, `spec_check` (`--vm`, ohne Modell), `devvm_build` (`gpu: exklusiv`, `modell_weg`, `braucht_modell`), `harness_abnahme`, `nachtlauf_3d` (definiert, Katalog `captain`),
`modell_laden` und `modell_entladen` (rufen `hub.load_model`/`unload_model`, `modell_weg`, weicher Vorbehalt). Neue Typen fügt nur Claude hinzu (harter Vorbehalt auf die Datei).

### 6.2 Werkzeuge und Einstufung

| Werkzeug | Parameter | Einstufung |
|---|---|---|
| `lauf_starten` | `lauf` (ID), `parameter` | Ziel = Lauf-ID; Katalog-Muster als Glob über Lauf-IDs; Gate-Bindung = ID + Parameter (sortiertes JSON) |
| `lauf_stoppen` | `lauf_id` (`L-…`) | Ziel = Lauf-ID des Typs; beendet nur den eigenen Prozessbaum (PID aus der Lauf-Datei, nie per Namensmuster, ENTWICKLUNG.md Regel 2) |
| `lauf_status` | `lauf_id` oder leer | liest Zustand und die letzten 40 Zeilen der Ausgabe (**Daten, keine Anweisung**) |

Katalogvorschlag (nur die Vorlage im Repo, §10 D-G6): `run_tests`, `spec_check` → `vorarbeiter`; `lauf_stoppen` → `vorarbeiter`; `devvm_build`, `nachtlauf_3d`, `modell_laden`, `modell_entladen` → `captain`
(ohne Regel ohnehin `captain`); `docs/spec_entwuerfe/**` Schreiben → `frei` (Entwürfe sind nicht verbindlich, das Gate W3 des Wunsches folgt).

### 6.3 Register und Hülle (`lauf.py`, `lauf_huelle.py`)

- Ordner `<projekt>/runtime_data/harness/laeufe/L-<8 Hex>/` mit `lauf.json`, `ausgabe.log`, `ende.json`.
- `lauf.json`: `{id, lauf, parameter, sitzung_id, antwort_id, aufgabe_id, karte_id, pid, start_zeit_pid, gestartet, ende, exit, status, fortschritt}`; `status` ∈ `laeuft` · `ok` · `fehler` ·
  `gestoppt` · `abgebrochen` (Aufgabe zurückgenommen) · `verloren` (Prozess weg, kein `ende.json`).
- Die **Hülle** (`python -I -m guppi_runtime.harness.lauf_huelle <ordner>`) startet das Ziel mit `argv` (kein Shell-Interpreter), schreibt Ausgabe in `ausgabe.log`, am Ende `ende.json` (Exit-Code, Zeit).
  So überlebt ein Lauf den Neustart des Servers; beim Start prüft die Harness jede `laeuft`-Datei (PID und Startzeit stimmen?) und setzt sonst `verloren` – ein Lauf wird nie als ok gemeldet, den niemand beendet gesehen hat.
- Fortschritt: reine Funktion `fortschritt_aus(zeilen, regel) -> {prozent, text} | None` über die letzten Zeilen; ohne Regel zeigt die Taskleiste nur die Zeit.
- Höchstens 3 laufende Läufe je Projekt; `gpu: exklusiv` höchstens einer und nur, wenn keine andere Antwort läuft.

### 6.4 Taskleiste, Reiter, Benachrichtigung

- Mitte der Taskleiste: je laufendem Lauf ein Knopf „Tests 42 %“ (oder „devvm_build 12 min“); ein Klick öffnet den Reiter **Lauf** (Zustand, Fortschritt, Log mit Auto-Scroll, Stopp-Knopf, Aufgabe, Sitzung). Beendete Läufe bleiben als Knopf, bis sie angeklickt wurden.
- Daten: `GET /api/harness/laeufe` und Ereignis `harness.lauf` auf `/api/events` (`gestartet`, `fortschritt` höchstens alle 2 s, `ende`). Kein neues Messen im Browser.
- **Benachrichtigung (HS-33):** Auslöser sind `harness.lauf` mit `ende`, eine neue Karte (`decision.pending`, `an: captain`), eine Aufgabe, die abläuft oder erschöpft ist, und `ende: wartet`. Der Knopf blinkt **einmal** (CSS-Animation ohne Dauerlauf, `prefers-reduced-motion` respektiert) und
  bleibt markiert, bis er angeklickt wird; gemerkt wird nur die ID in `localStorage` `sedra.harness.gesehen`. Der Statusbereich zeigt „Freigaben n · beim Vorarbeiter m“.
- Wenn ein Lauf `modell_weg` hat, steht neben seinem Knopf „Modell belegt“; die Sitzungen antworten bis dahin `kein_modell` mit dem Grund „Modell belegt durch Lauf L-…“ (K13, HS-53).

## 7. Endpunkte und Ereignisse (neu)

| Weg | Methode | Zweck |
|---|---|---|
| `vorlagen` | GET | Vorlagen (Name, Beschreibung, Rechte, empfohlenes Modell, Hash) |
| `sitzungen` | POST | wie bisher, `vorlage` jetzt erlaubt |
| `vorarbeiter` | GET / POST / DELETE | Ernennung je Projekt (nur Captain, S7) |
| `aufgaben` | GET / POST | Liste (mit Rest und Zustand) / Aufgabe anlegen `{…Format 4.1}` – nur Captain |
| `aufgaben/<id>` | GET | Aufgabe mit Aufrufen (Audit-Auszug) |
| `aufgaben/<id>/zuruecknehmen` | POST | Rücknahme `{laeufe_stoppen}` – nur Captain |
| `karten/<id>` | GET / POST | wie bisher; Karte zeigt `an`, `art`, `vorgelegt`; bei `art: aufgabe` kann `erlauben` eine gekürzte Liste/Frist mitgeben (`auswahl`, `bis`, `max_aufrufe`) |
| `karten/<id>/zuruecknehmen` | POST | eine Vorarbeiter-Entscheidung zurücknehmen (Marker, Audit, Hinweis an beide Sitzungen) – nur Captain |
| `laeufe` | GET | Register; `laeufe/<id>` Zustand + Log-Ende; `laeufe/<id>/stopp` POST |

Antwort-Strom neu: `lauf {lauf_id, lauf, zustand}` und an `karte` die Felder `an`, `art`; `werkzeug.ende` trägt bei Aufgabe `stufe: aufgabe`, `regel: aufgabe:T-…`.
Gemeinsamer Strom neu: `harness.lauf`, `harness.aufgabe {id, zustand}`, `harness.vorarbeiter {projekt, sitzung_id}`; `decision.pending/answered` auch für `art: aufgabe`.
Audit neu: `HARNESS_AUFGABE_VORGESCHLAGEN/ANGELEGT/BEENDET/ZURUECKGENOMMEN`, `HARNESS_APPROVED_BY` mit `approved_by: aufgabe:<id>`, `HARNESS_FREIGABE` mit `von: vorarbeiter:<sitzung>` und `begruendung`,
`HARNESS_VORARBEITER_ERNANNT`, `HARNESS_LAUF_START/ENDE/STOPP`, `HARNESS_HERKUNFT_ABGELEHNT`, `HARNESS_KARTE_FRIST`.

## 8. Zusammenspiel mit der Wunsch-Anbindung

| Schritt (SPEC_WUNSCH) | Was Stufe 3 liefert | Was dem Wunsch-G2 bleibt |
|---|---|---|
| W1 Wunsch | Vorlage `vorarbeiter`, Sitzungskopf `vorlage`; ein Wunsch je Sitzung (WQ-4) = Aufgabe gebunden an Sitzungen | Datenformat des Wunsches (`W-<8 Hex>`), Ordner `runtime_data/wuensche/<ID>/`, Eingabe-Dialog (4000 Zeichen, WA-01) |
| W2 Spec-Entwurf | Katalog-Regel Schreiben `docs/spec_entwuerfe/**` = `frei`; Modell Qwen3.6-35B-A3B (WQ-1) als Vorlagen-Vorschlag | Vorlage `spec-schreiber`, Spec-Muster, Prüfung des Umfangs |
| W3 Gate | **Kartenart `aufgabe`** (Captain-fest, nie Vorarbeiter): der Captain gibt die Spec mit dem Bau-Rahmen (Schreibbereich, Befehle, Läufe, Modelle, Frist) frei; die Karte zeigt Umfang und offene Fragen aus der Spec (WA-03) | Inhalt der Karte (Diff der Spec, Zeilen, Stufen), Verknüpfung `wunsch_id` ↔ Aufgabe |
| W4 Bau | Aufgabe mit Zähler und Frist, Läufe (`devvm_build`) mit Fortschritt in der Taskleiste, Vorarbeiter-Freigabe für Zwischenschritte, harte Grenzen (WA-04/HS-28), Stopp (WA-08) | Aufteilung in höchstens 5 Stufen je Durchgang (WQ-3), jede Stufe mit versteckten Tests (WA-05), „neue Karte nach 5 Stufen“ |
| W5 Review | Vorlage `pruefer` (Gemma-4-12B, WQ-2) mit nur lesenden Rechten, Lauf-Typ `modell_laden` mit Aufgaben-Freigabe für das Rezept; Übernahme bleibt Captain-fest (WA-06, WA-07) | Prüfung „anderes Modell als der Coder“ (Test), Urteilsformat, Übernahme-Karte |

Zwei Punkte für das Wunsch-G2, die aus Stufe 3 folgen: (1) **Qwen3.6 (≈ 10,2 GB) und Gemma-4-12B passen nicht gleichzeitig in ~11,5 GB VRAM** – der Prüfer läuft nach dem Bau, mit Modellwechsel
über `modell_laden`/`modell_entladen` (Lade-Lease, Regel 2), nicht parallel. (2) Der Bau ist ein exklusiver Lauf (K13); Spec-Schreiber und Vorarbeiter pausieren währenddessen.

## 9. Berechtigungen vorab (ENTWICKLUNG.md: „Berechtigungen werden vorher eingeholt“)

Gilt für den **Bau von Stufe 3** (Aufgaben in `SPEC_HARNESS_SHELL_v1_G3_STUFE3.md`; dort je Aufgabe zugeordnet, gleiche Nummern). Was nicht hier steht, läuft nicht und wird nicht nachgefragt.
Jede Zeile: Captain gibt **ja**, **nein** oder **auf Ansage** (= erlaubt, Start aber erst auf Ansage in der Bau-Sitzung).

| Nr | Berechtigung | Begründung | Vorschlag |
|---|---|---|---|
| P-1 | Worktree und Branch `harness/stufe-3` ab `spec/agenten-orchestrierung` (`d9b8f97` oder neuer); Commits dort mit Anhang `Co-Authored-By`. **Kein Push, kein Merge nach `spec/agenten-orchestrierung`, kein `main`.** | Regel 12 (eigene Branches); Übernahme ist G4 des Captains | ja |
| P-2 | Schreiben im Paket `runtime/src/guppi_runtime/harness/`: neu `vorlagen.py`, `aufgabe.py`, `vorarbeiter.py`, `lauf.py`, `lauf_huelle.py`, `herkunft.py`; ändern `freigabe.py`, `vorbehalte.py`, `katalog.py` (nur `WERKZEUGE`), `werkzeuge.py`, `schleife.py`, `api.py`, `sitzung.py` | Kern von Stufe 3. `freigabe.py` und `vorbehalte.py` sind Harness-Code (SEDRA fasst sie nie an) – **das Ja hier ist das Captain-Gate dafür** (vorbehalte.py: „Liste ändert nur Claude mit Captain-Gate“) | ja |
| P-3 | Schreiben außerhalb des Pakets: `runtime/src/guppi_runtime/uix_server.py` (Wege, Herkunftsprüfung), `desk/decisions.py` (Kartenart `aufgabe`) | Einbindung; ohne sie sind die Wege nicht erreichbar | ja |
| P-4 | Schreiben `runtime/src/guppi_runtime/uix/shells/harness/`: `taskleiste.js`, `reiter.js`, `verlauf.js`, `karte.js`, `eingabe.js` (Schild), `seite.js` (Marke), `shell.css`, `shell.yaml`, `README.md`; neu `aufgabe.js`, `lauf.js` | Oberfläche HS-31 bis HS-33, Karten, Aufgabe | ja |
| P-5 | Schreiben Konfiguration im Repo: `runtime/config/harness_vorlagen/{vorarbeiter,bauagent,pruefer}.{yaml,md}`, `runtime/config/harness_laeufe.yaml`, `runtime/config/freigabe_katalog.beispiel.yaml` (neue Regeln, D-G6). **Nicht** `local_config/`. | Vorlagen und Lauf-Typen sind Daten des Repos; die Vorlage des Katalogs ist nur eine Vorlage | ja |
| P-6 | Schreiben Tests: neue `runtime/tests/test_harness_*.py`, `test_uix_harness_*.py`; `benchmarks/harness_abnahme.py` (Teil Stufe 3); Gruppe `harness` in `run_tests.py` nur falls das Muster nicht reicht | Tests ohne Modell | ja |
| P-7 | Schreiben Bau-Spezifikationen für SEDRA: `runtime/benchmarks/devvm_specs/harness_aufgabe_deckung.py`, `…/harness_lauf_fortschritt.py`, `runtime/benchmarks/devvm_refs/…` (Referenz und versteckte Prüfungen, je ≤ 20) und `docs/BAUSPEC_AUFGABE_DECKUNG.md`, `docs/BAUSPEC_LAUF_FORTSCHRITT.md` | L2/L3: kein Bau ohne Stempel; `devvm_*` ist Harness-Code | ja |
| P-8 | Schreiben Dokumente: `docs/BAUBERICHT_HARNESS_STUFE3_<datum>.md`, Logbuch-Zeilen (`docs/LOGBUCH_AGENT_MANAGER.md`, eine je Schritt, Uhrzeit aus `date`), Statuszeilen in diesen beiden Specs | Berichtspflicht | ja |
| P-9 | Befehle ohne Modell: `python benchmarks/run_tests.py <Gruppen>`, `python benchmarks/uix_check.py --shell harness --groesse 1024x700,1400x860`, `python benchmarks/spec_check.py <spec> --vm --project workspace/GUPPI_OS` (microVM, Stempel), `git status/diff/log/add/commit` auf `harness/stufe-3` | Abnahme ohne Modell | ja |
| P-10 | Browser-Durchlauf mit Modell-Attrappe (Playwright, lokal) für Karte an Vorarbeiter, Aufgabenkarte, Lauf in der Taskleiste, Benachrichtigung | HS-31 bis HS-33 prüfen | ja |
| P-11 | Modell laden und Lauf: **SEDRA-Bau B1** `devvm_build … --spec harness_aufgabe_deckung --profile standard` (Qwen3.6-35B-A3B, ~5–6 min, exklusive GPU, danach entladen) | erster SEDRA-Bau von Stufe 3; Muster wie `einstufen` | auf Ansage |
| P-12 | Modell laden und Lauf: **Pilot B3** `harness_lauf_fortschritt` **über die Harness** (Vorarbeiter-Sitzung Qwen3.6, Aufgaben-Freigabe nach Muster in §4.1, Lauf `devvm_build`, dazu `spec_check --vm`) | erster Bau von SEDRA unter einem Vorarbeiter (HS-E5); zugleich Abnahme der Kette Aufgabe → Lauf → Taskleiste | auf Ansage |
| P-13 | Modell laden: **Review-Lauf mit Gemma-4-12B** (Vorlage `pruefer`, nur lesend) über das Ergebnis von B1 und B3; Modellwechsel Qwen → Gemma → Qwen (kein gleichzeitiges Laden) | WQ-2; zweites Modell = **Vergleichslauf**, ausdrücklich beantragt | auf Ansage |
| P-14 | Modell laden: **Abnahme mit Qwen3.6-35B-A3B** (Szenario S3-A bis S3-D aus G3 §Abnahme: Karte an Vorarbeiter, Selbstfreigabe-Versuch, Aufgabe mit Rücknahme, Lauf mit Benachrichtigung) | Stufe 3 ohne echtes Modell nicht abnehmbar | auf Ansage |
| P-15 | Lesen nach Modellläufen: GPU-Zustand (`nvidia-smi`) und Ereignisprotokoll auf Treiberfehler (`nvlddmkm`, `LiveKernelEvent`), nur lesend | wie im Bericht Stufe 2 (Messung vor/nach) | ja |
| **nicht beantragt** | `local_config/` (auch der Katalog des Captains), Push, Merge, `main`, Löschen, Downloads, Engine-Wechsel, Guard/`core/**`, `nachtlauf_3d` oder andere Dauerläufe, Nemotron-/9B-Vergleichsläufe, Cloud-Modelle | nicht Teil von Stufe 3 | – |

## 10. Fragen an den Captain (Vorschlag jeweils fett)

| Nr | Frage | Vorschlag |
|---|---|---|
| D-G1 | **Vorarbeiter und exklusive Läufe (K13):** Der Bau (`devvm_build`) stoppt den Modellserver, auf dem der Vorarbeiter läuft. Soll er den Bau trotzdem starten dürfen? | **Ja.** Der Vorarbeiter startet, die Sitzung ist bis zum Ende „Modell belegt“, das Ergebnis liest er danach (kein Wecken von selbst). Alternative: ein zweites, kleines Modell als Vorarbeiter – passt nicht neben Qwen3.6 in den VRAM, daher nicht in Stufe 3. |
| D-G2 | **Wer weckt den Vorarbeiter?** Keine Karte soll an einer Sitzung hängen, die niemand weckt. | **Niemand automatisch.** Der Captain schreibt ihm; Karten `an: vorarbeiter` fallen nach **15 Minuten** an den Captain (5–60 einstellbar in der Vorlage). |
| D-G3 | **Rücknahme (HS-29):** Was heißt „zurücknehmen“ bei schon Geschriebenem, und werden Läufe der Aufgabe mit gestoppt? | **Nur Marker, Sperre ab dem nächsten Aufruf und Anzeige des Diffs; kein automatisches Zurückdrehen.** Läufe der Aufgabe werden gestoppt, außer der Captain schaltet das ab. |
| D-G4 | **Grenzen der Aufgabe:** Pflicht `bis` (≤ 24 h) oder `max_aufrufe` (≤ 500), mindestens eins; „weite“ Muster nur durch den Captain selbst, nie per Vorschlag des Vorarbeiters. | **Ja, so.** |
| D-G5 | **Herkunftsprüfung (S7/K14):** Bauen wir die Auflösung der Gegenstelle auf Windows (PID-Nachkommen von `befehl` und Läufen)? | **Ja, best effort** mit Origin/Host-Prüfung als Untergrenze und Warnung im Audit, wenn die Auflösung scheitert. Ohne S7 empfehle ich, `python *`-Muster in Aufgaben gar nicht zuzulassen. |
| D-G6 | **Katalog-Vorlage anpassen:** `docs/spec_entwuerfe/**` Schreiben `frei`; `run_tests`, `spec_check`, `lauf_stoppen` → `vorarbeiter`; `docs/LOGBUCH_AGENT_MANAGER.md` Schreiben → `vorarbeiter`; Läufe mit Modell und `modell_laden` bleiben `captain`. | **Ja** (nur die Vorlage im Repo; `local_config/freigabe_katalog.yaml` ändert der Captain selbst, D-F2). |
| D-G7 | **Läufe aus dem Terminal** (z. B. dein 6-Stunden-Test) in der Taskleiste? | **Nein in Stufe 3**; nur Läufe der Harness plus (Stufe 4) der Scheduler-Zustand im Statusbereich. |
| D-G8 | **Vorlagen:** Mitgeliefert `vorarbeiter`, `bauagent`, `pruefer`; `spec-schreiber` erst im Wunsch-G2. Ablage Repo + `local_config/` mit Vorrang. | **Ja.** |

G2 gilt als freigegeben, wenn der Captain D-G1 bis D-G8 entschieden und §9 beantwortet hat; dann folgt das Gate G3 (Bau-Aufgaben).

## 11. Entscheidungen des Captains (29.10.2026 08:52)

Captain: „Ja, so“ – D-G1 bis D-G8 gelten wie vorgeschlagen (fett in §10), ebenso die Berechtigungen §9: P-1 bis P-10 und P-15 **ja**, P-11 bis P-14 **auf Ansage**.
G2 Stufe 3 ist damit freigegeben. Nächstes Gate: G3 (`SPEC_HARNESS_SHELL_v1_G3_STUFE3.md`).
