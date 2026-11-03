# SPEC Apps v1 – G4 „Ausführung von Modell-Code nur nach Sicht“ – G2 Design (03.11.2026)

Grundlage: `docs/SPEC_APPS_v1_AM0_E1_OBERFLAECHENCODE.md` §5a.3 (Befund), §5a.5 (Maßnahme G4), §5a.7 (Skizze); Entscheidung des Captains vom 03.11.2026: **G4 sofort**, als eigener Punkt, unabhängig von O3+.
Da G4 kein eigenes G1 hat, stehen die Anforderungen hier mit (Teil 1). G2 freigegeben am 03.11.2026; Bau (G3) auf dem Branch `claude/intelligent-goldberg-7arr50`.
Pfade relativ zu `runtime/src/guppi_runtime/`, Zeilen für c364081.

## 0. Ziel in einem Satz

Die Harness startet keinen Lauf und keinen Befehl, solange es im Projekt Code gibt, den der Captain in seiner aktuellen Fassung nicht gesehen hat – außer der Captain sieht ihn auf der Karte und gibt frei.

## 1. Befund (warum)

| Nr | Befund | Beleg |
|---|---|---|
| B1 | Die Vorbehalte prüfen nur `datei_schreiben`/`datei_aendern` (Pfade) und einige Befehlsanfänge. | `harness/vorbehalte.py:33–35, 46–67` |
| B2 | Die MasterChat-Vorlage gibt für die Sitzung Schreiben in `runtime/src/**` und `runtime/tests/**` und den Lauf `run_tests` frei. | `runtime/config/harness_vorlagen/masterchat.yaml:14–26` |
| B3 | `run_tests` startet `python benchmarks/run_tests.py <gruppen>` auf dem Rechner; neue Testdateien werden über Muster mitgenommen. | `runtime/config/harness_laeufe.yaml` (`run_tests`); `harness/lauf_huelle.py:1–5`; `runtime/benchmarks/run_tests.py:32, 38` |
| B4 | `befehl` startet Programme auf dem Rechner (ohne Shell, mit Zeitlimit). | `harness/befehl.py:136` |
| B5 | Folge: Vom Modell geschriebener Code kann über einen Lauf oder Befehl mit den Rechten des Captains laufen und jede Datei schreiben – auch an allen Vorbehalten vorbei. | Vorlage AM0-E1 §5a.3 |
| B6 | Alle Ausführungen eines Harness-Werkzeugs laufen über zwei Stellen: die automatische Freigabe (Katalog `frei`, Aufgabe, Sitzungs-Erlaubnis) und die Antwort auf eine Karte. Beide rufen `ausfuehren`. | `harness/freigabe.py:229–247` und `:303–334` |
| B7 | Ein Vorbehalt schließt Aufgabe, Sitzungs-Erlaubnis und Vorarbeiter aus; es bleibt nur die Karte an den Captain. | `harness/freigabe.py:230, 235, 250` |
| B8 | Eine Freigabe ist an eine **Bindung** gebunden; `beantworten` bereitet den Aufruf neu vor, und weicht die Bindung ab, lehnt der Guard das Token ab (`request_digest_mismatch`). | `harness/freigabe.py:326–333` (Kommentar `:332`) |
| B9 | Für Läufe und Befehle ist die Bindung heute Typ/Argumente bzw. Befehlszeile/Ordner. | `harness/werkzeuge.py:286–287`; `harness/befehl.py:102` |
| B10 | Im Projekt SEDRA liegen rund 1.235 Code-Dateien (`.py`, `.js`, Skripte, Konfiguration), zusammen etwa 13 MB (gezählt am 03.11.2026 ohne `.git`, `node_modules`, `.venv`, `engines`, `__pycache__`, `runtime_data`). | Zählung |

## 2. Anforderungen

### 2.1 Was „Code“ ist

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G4-01 | **Code-Datei** ist jede Datei im Projekt mit einer Endung aus `CODE_ENDUNGEN` = `.py .pyw .pth .js .mjs .cjs .ps1 .psm1 .bat .cmd .sh .vbs .exe .dll` oder einem Namen aus `CODE_NAMEN` = `pyproject.toml setup.cfg setup.py tox.ini pytest.ini package.json conftest.py sitecustomize.py usercustomize.py`. Übersprungen werden die Ordner aus `werkzeuge.UEBERSPRINGEN` (`harness/werkzeuge.py:34`), versteckte Ordner und `runtime_data`. | Test der Erkennung |
| G4-02 | Die Liste ist bewusst weit (Konfiguration wie `pytest.ini` oder `package.json` kann bestimmen, was ausgeführt wird). Sie ist eine Heuristik; was nicht darauf steht, wird nicht geprüft (§7). | Doku |

### 2.2 Gesehener Stand

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G4-03 | Je Projekt führt die Harness einen **gesehenen Stand**: für jede Code-Datei den SHA-256 der Fassung, die als gesehen gilt. Datei `runtime_data/harness/code_stand.json` (harter Vorbehalt `**/runtime_data/harness/**`, das Modell kann sie nicht schreiben). | Test |
| G4-04 | **Ausgangsstand**: Gibt es die Datei noch nicht, gilt der Stand beim ersten Gebrauch als gesehen (er ist das, was der Captain heute betreibt). Audit `HARNESS_CODE_STAND_ANGELEGT {dateien, hash_des_stands}`. Ehrlich: Der Ausgangsstand wird nicht geprüft, er wird angenommen. | Test |
| G4-05 | **Ungesehen** ist eine Code-Datei, deren aktueller Hash vom gesehenen abweicht, die neu ist oder die fehlt. Ermittelt wird bei jeder Prüfung (G4-08) durch Vergleich mit dem Dateisystem – damit wird **jede** Änderung erkannt, auch durch Programme, Läufe oder von außen. Neu gehasht wird nur, wenn sich Größe oder Änderungszeit einer Datei geändert haben. | Test mit Änderung über `datei_schreiben`, über einen Lauf und von außen |
| G4-06 | **Herkunft einer Änderung** (nur Anzeige): Schreibt die Harness eine Code-Datei, merkt sie sich Sitzung, Zeit und Weg (`karte` / `aufgabe` / `sitzung` / `katalog` / `vorarbeiter`) und **vor dem Schreiben** die vorige Fassung, wenn diese gesehen war (Ablage `runtime_data/harness/code_vorher/<sha256>`, je Inhalt einmal). Änderungen ohne Eintrag heißen „außerhalb der Harness geändert“. | Test |
| G4-07 | **Einzeln gesehen**: Wird eine Code-Datei über eine **Karte** geschrieben, die der Captain mit `erlauben` beantwortet (nicht `sitzung`, nicht Vorarbeiter), und war die Datei davor gesehen (oder neu), gilt die neue Fassung als gesehen. Der Captain hat genau diesen Diff auf der Karte gesehen. | Test |

### 2.3 Prüfung vor Ausführung

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G4-08 | Vor jedem `lauf_starten` und jedem `befehl` ermittelt `vorbereiten` die Liste der ungesehenen Code-Dateien (`plan['code_ungesehen']`). | Test |
| G4-09 | Ist die Liste nicht leer, gibt `vorbehalte.pruefen` den Grund „Captain-Vorbehalt: Ausführung von Code, den du noch nicht gesehen hast (n Dateien)“ zurück. Es ist ein **harter** Vorbehalt: keine Aufgabe, keine Sitzungs-Erlaubnis, kein Vorarbeiter, kein Katalog-`frei` (B7). | Test je Weg |
| G4-10 | **Ausnahmen** (führen keinen Projekt-Code aus): Befehle, deren Zeile mit `python -m py_compile` oder `node --check` beginnt (`NUR_PRUEFEN`). `lauf_stoppen` und `lauf_status` sind ohnehin nicht betroffen. | Test |
| G4-11 | Die Liste geht in die **Bindung** des Gates (`plan['gate']['bindung']['code_ungesehen'] = [[pfad, hash_neu], …]`). Ändert sich eine Datei zwischen Karte und Antwort, passt die Bindung nicht mehr und die Freigabe greift nicht (B8); die Harness legt eine neue Karte an. | Test |
| G4-12 | Nach einer Freigabe mit `erlauben` durch den Captain und erfolgreichem Start gilt der Stand der gelisteten Dateien als gesehen (nur wenn ihr Hash noch dem gebundenen entspricht). Audit `HARNESS_CODE_GESEHEN {karte_id, anzahl, von, kanal}`. | Test |

### 2.4 Karte

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G4-13 | Die Karte zeigt unter dem Lauf/Befehl einen Block „Code, den du noch nicht gesehen hast“: zuerst die Dateien mit Herkunft „Harness“ (Sitzung, Weg) mit **Diff** gegen die gesehene Fassung; dann „außerhalb der Harness geändert“ mit Größe, Hash und – weil die vorige Fassung nicht vorliegt – den ersten 200 Zeilen bzw. dem Hinweis „vorige Fassung nicht gespeichert; im Repo mit `git diff` ansehen“. | Test der Vorschau |
| G4-14 | Höchstens 30 Dateien und 2.000 Zeilen Diff auf der Karte; darüber ein Satz „n weitere Dateien – Karte zu groß zum Prüfen; Stand über die Konsole ansehen und übernehmen“ und die Karte lässt sich nicht im Browser freigeben (nur über die Konsole, G4-16). | Test |
| G4-15 | Die Karte ist Klasse **H** (G9): Sobald G9 gebaut ist, braucht ihr „Erlauben“ die Bestätigung außerhalb des Browsers. Bis dahin wird sie im Browser beantwortet wie jede Karte. | Test nach G9 |

### 2.5 Konsole, Bericht, Nachweis

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| G4-16 | Konsole: `guppi code-stand <projekt> [--zeigen]` listet die ungesehenen Dateien mit Diff, wo möglich; `guppi code-stand <projekt> --uebernehmen` erklärt den aktuellen Stand als gesehen (z. B. nach eigener Arbeit von Claude oder einem `git pull`). Audit `HARNESS_CODE_STAND_UEBERNOMMEN {anzahl, kanal: konsole}`. | Test der CLI |
| G4-17 | Beim Start einer Harness-Sitzung (und für G6 beim Start von SEDRA) steht eine Zeile im Posteingang bzw. in der Sitzung, wenn ungesehener Code vorliegt („n Code-Dateien ungesehen – Läufe und Befehle brauchen deine Sicht“). | Test |
| G4-18 | Audit ohne Inhalte, nur Pfade, Hashes, Zahlen: `HARNESS_CODE_STAND_ANGELEGT`, `HARNESS_CODE_UNGESEHEN {karte_id, anzahl}`, `HARNESS_CODE_GESEHEN`, `HARNESS_CODE_STAND_UEBERNOMMEN`. | Test |

## 3. Entwurf

**Neue Datei `harness/code_stand.py`** (Harness-Code; ≤ 400 Zeilen; harter Vorbehalt, Eintrag in `vorbehalte.PFADE`):
```python
CODE_ENDUNGEN, CODE_NAMEN, NUR_PRUEFEN
def ist_code(rel) -> bool
def erfassen(wurzel, alt=None) -> dict          # {rel: [size, mtime_ns, sha256]}; nutzt `alt` als Zwischenspeicher (nur geänderte neu hashen)
def laden(wurzel) -> dict | None                # runtime_data/harness/code_stand.json
def anlegen_wenn_noetig(wurzel, audit) -> dict
def ungesehen(wurzel, stand) -> list            # [{pfad, hash_alt|None, hash_neu|None, herkunft|None}]
def vorher_merken(wurzel, rel, stand)           # vor dem Schreiben: vorige Fassung ablegen, wenn gesehen
def spur(wurzel, rel, sitzung_id, weg)          # Herkunft (G4-06)
def gesehen(wurzel, eintraege)                  # nur Einträge, deren Hash noch stimmt
def vorschau(wurzel, liste) -> str              # Text für die Karte (G4-13/14)
```
- Ablage: `runtime_data/harness/code_stand.json` (`{schema: 1, gesehen: {rel: sha}, angelegt, zuletzt}`), `runtime_data/harness/code_spur.json` (Herkunft), `runtime_data/harness/code_vorher/<sha>`; atomar geschrieben (`core.util.atomic_write_json`); eine Sperre je Projekt (Muster `harness/freigabe.py` `Karten._sperre`).

**Änderungen an bestehendem Harness-Code** (alle unter Vorbehalt, Änderung nur durch Claude):

| Datei | Änderung |
|---|---|
| `harness/werkzeuge.py` `vorbereiten` | für `befehl` und `lauf_starten`: `plan['code_ungesehen'] = code_stand.ungesehen(…)` (außer `NUR_PRUEFEN`); Liste in `plan['gate']['bindung']`; Vorschau-Block anhängen. Für `datei_schreiben`/`datei_aendern` auf eine Code-Datei: `plan['code'] = True`. |
| `harness/vorbehalte.py` `pruefen` | neuer Grund für `befehl`/`lauf_starten`, wenn `plan['code_ungesehen']` nicht leer ist (Parameter `ungesehen`); `PFADE` um `runtime/src/guppi_runtime/harness/code_stand.py` ergänzt |
| `harness/freigabe.py` `einstufung` | reicht `plan.get('code_ungesehen')` an `vorbehalte.pruefen` |
| `harness/freigabe.py` `aufruf` (automatischer Weg) und `beantworten` (Karte) | vor `ausfuehren` einer Code-Schreibung: `vorher_merken`; danach `spur` mit Weg (`aufgabe`/`sitzung`/`katalog` bzw. `karte`/`vorarbeiter`); bei Karte + `erlauben` + `von == 'captain'`: `gesehen` für diese Datei (G4-07). Nach `ausfuehren` eines Laufs/Befehls über eine Karte mit Code-Liste: `gesehen` für die gebundene Liste (G4-12). |
| `cli.py` | Befehl `code-stand` (G4-16) |
| `harness/api.py` | Zeile im Sitzungsstart (G4-17) |

**Warum Vergleich mit dem Dateisystem statt nur Mitschreiben:** Ein freigegebener Lauf kann selbst Dateien erzeugen; ein Mitschreiben nur der Werkzeug-Schreibvorgänge sähe das nicht. Der Vergleich findet jede Änderung, gleich von wem.

**Kosten:** Ein Vergleich liest Größe und Änderungszeit aller Code-Dateien (≈ 1.235) und hasht nur geänderte. Erwartung: deutlich unter 1 s; in G3 messen (Ziel < 300 ms auf dem PC des Captains), sonst Zwischenspeicher je Sitzung.

## 4. Abläufe

**A – MasterChat schreibt Tests und startet sie**
1. `datei_schreiben runtime/tests/test_x.py` – gedeckt durch die Sitzungs-Erlaubnis der Vorlage, läuft ohne Karte; Spur: Weg `sitzung`, vorige Fassung gemerkt (neu: keine).
2. `lauf_starten run_tests` – sonst durch die Sitzungs-Erlaubnis frei; jetzt **Karte** (harter Vorbehalt) mit dem Lauf und dem Inhalt von `test_x.py`.
3. Captain liest, gibt frei → Lauf startet; `test_x.py` gilt als gesehen. Der nächste `run_tests` ohne neue Code-Änderung läuft wieder ohne Karte.

**B – Claude hat im Repo gearbeitet, danach startet der MasterChat Tests**
- Die Karte listet die von Claude geänderten Dateien unter „außerhalb der Harness geändert“ (ohne Diff). Weg für den Captain: `guppi code-stand <projekt> --uebernehmen` in der Konsole, nachdem er die Änderung kennt – oder die Karte freigeben.

**C – Bauagent mit Aufgabe: schreiben, testen, schreiben, testen**
- Jeder Testlauf nach einer Code-Änderung ist eine Karte. Das bremst selbständige Bau-Schleifen bewusst (§6, G4-E3).

## 5. Tests (für G3)

| Datei | Fälle |
|---|---|
| neu `tests/test_harness_code_stand.py` | Erkennung von Code-Dateien; Ausgangsstand; ungesehen nach Schreiben, nach Änderung durch einen Prozess, von außen, nach Löschen; Zwischenspeicher (nur Geändertes gehasht); `gesehen` nur bei passendem Hash; Ablage der vorigen Fassung nur, wenn gesehen; Vorschau-Grenzen (30 Dateien / 2.000 Zeilen) |
| `tests/test_harness_vorbehalte.py` | Grund für `befehl`/`lauf_starten` mit/ohne Liste; `NUR_PRUEFEN` |
| `tests/test_harness_freigabe*.py` (Namen in G3) | Aufgabe, Sitzungs-Erlaubnis, Katalog `frei`, Vorarbeiter decken nicht; Karte `erlauben` → Lauf läuft, Stand gesehen; `sitzung`-Weg auf dieser Karte nicht möglich; Bindung: Datei zwischen Karte und Antwort geändert → Freigabe greift nicht |
| `tests/test_harness_masterchat.py` | Ablauf A von Anfang bis Ende mit Fake-Lauf |
| CLI-Test | `code-stand --zeigen`, `--uebernehmen`, Audit |
| bestehende Harness-Suiten | Tests, die heute nach einem Schreiben ohne Karte einen Lauf/Befehl starten, müssen angepasst werden (erwartete Karte) – in G3 auflisten |

## 6. Folgen für die Praxis

| Wer | Folge |
|---|---|
| MasterChat | Erster Testlauf nach neuen oder geänderten Code-Dateien braucht eine Karte; danach frei, bis wieder Code geändert wird. |
| Bauagent / Aufgaben | Selbständige Schleifen „ändern → testen“ halten an jeder Testrunde an. |
| Captain nach eigener Arbeit / Claude / `git pull` | Einmal `guppi code-stand … --uebernehmen` oder die nächste Karte freigeben. |
| Claude direkt im Repo | nicht betroffen (läuft nicht über die Harness). |

## 7. Grenzen (ehrlich)

- **Heuristik der Code-Dateien**: Ein Lauf kann Code aus Dateien laden, die nicht auf der Liste stehen (z. B. eine YAML-Datei, die ein Skript als Befehlsliste liest). Solche Fälle erkennt G4 nicht. Die Lauf-Typen selbst sind fest (`harness_laeufe.yaml`, harter Vorbehalt); die heutigen (`run_tests`, `spec_check`, `devvm_build`) starten Python-Skripte, die auf der Liste stehen.
- **Ausgangsstand ungeprüft** (G4-04): Was vor G4 im Projekt lag, gilt als gesehen.
- **„Außerhalb der Harness“ ohne Diff**: Für solche Änderungen fehlt die vorige Fassung; die Karte zeigt nur Hash, Größe und den Anfang. Der Captain kann `git diff` nutzen.
- **Freigabe ohne Lesen** bleibt möglich. G9 macht sie zu einem bewussten Schritt außerhalb des Browsers, mehr nicht.
- **Neustart von SEDRA** führt geänderten Python-Code aus, ohne dass G4 greift (G4 prüft Läufe und Befehle der Harness). Das deckt G6 (Bericht) nur als Hinweis ab; die Lösung ist AM9.
- **Programme, die nach dem Lauf weiterlaufen** (abgelöste Kindprozesse), können später schreiben. Die Hülle beendet bei Stopp den Prozessbaum (`harness/lauf_huelle.py`, `beenden`); was sich danach ändert, findet der nächste Vergleich (G4-05) – vor der nächsten Ausführung, nicht vorher.

## 8. Rückfall

Schalter `code_sicht` in `local_switches` (Standard **an**). Aus = heutiges Verhalten; die Stand-Dateien bleiben liegen, und beim Wiedereinschalten gilt der dann aktuelle Stand **nicht** automatisch als gesehen (die Karte listet alle Abweichungen).

## 9. Entscheidungen des Captains

**Entschieden vom Captain am 03.11.2026: G4-E1 bis G4-E4 wie vorgeschlagen; G2 freigegeben, G3 bauen.**

| Nr | Frage | Vorschlag |
|---|---|---|
| G4-E1 | Ausnahmen nur `python -m py_compile` und `node --check`? | ja |
| G4-E2 | Änderungen außerhalb der Harness (Claude, `git pull`) mit derselben Karte bzw. über die Konsole übernehmen? | ja |
| G4-E3 | Selbständige Bau-Schleifen (Bauagent mit Aufgabe) halten an jeder Testrunde an. Später: Läufe mit ungesehenem Code ohne Karte, **wenn** sie vollständig in der microVM laufen (eigener Punkt; braucht VM-Lauf-Typen und eine geprüfte VM auf dem PC). | jetzt so; VM-Läufe als eigener Punkt |
| G4-E4 | Ausgangsstand beim ersten Gebrauch als gesehen annehmen? | ja; die Alternative (alles einmal prüfen) ist bei ≈ 1.235 Dateien nicht praktikabel |

## 10. Berechtigungen vorab (für G3)

Schreiben (nur Claude, Harness-Code unter Vorbehalt): `harness/code_stand.py` (neu), `harness/werkzeuge.py`, `harness/vorbehalte.py`, `harness/freigabe.py`, `harness/api.py`, `cli.py`; Tests unter `runtime/tests/`. Nicht: Lauf-Typen (`harness_laeufe.yaml`), Vorlagen, Guard, `local_config/`.

## 11. Reihenfolge für G3

| Nr | Aufgabe |
|---|---|
| T1 | `code_stand.py` mit Erkennung, Stand, Vergleich, Ablage, Vorschau + Tests |
| T2 | Prüfung vor Ausführung: `werkzeuge.vorbereiten`, `vorbehalte.pruefen`, `freigabe.einstufung`, Bindung + Tests |
| T3 | Mitschreiben und „gesehen“ in `freigabe.aufruf`/`beantworten` + Tests |
| T4 | Konsole `code-stand` + Sitzungszeile + Audit |
| T5 | bestehende Harness-Tests anpassen, Laufzeit messen |

## 12. Nächste Gates

G2 (diese Datei) → Freigabe durch den Captain → G3 T1–T5 → G4 Abnahme am PC: MasterChat schreibt einen Test und startet `run_tests` → Karte mit Inhalt; nach Freigabe läuft der Test; zweiter Lauf ohne Änderung ohne Karte; nach `git pull` → Karte bzw. `code-stand --uebernehmen`.
