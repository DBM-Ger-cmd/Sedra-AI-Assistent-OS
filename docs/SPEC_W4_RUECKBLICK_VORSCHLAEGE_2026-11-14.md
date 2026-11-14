# Spec W4 – Rückblick & Vorschläge (Harness-Werkzeuge)

> **Prüfvermerk des Koordinators (14.11.2026):** Entwurf von Pi (A-010), nachgeprüft: 16 Anforderungs-IDs (W4-01 bis -16), Gegenproben ohne Gate → 403 `gate_required`, keine lokalen Pfade. Pis Zeilenangabe im ERGEBNIS (108) war falsch, die Datei hat 145 Zeilen. Vor dem Bau zu klären: (1) W4-08 erlaubt `status_setzen` auf `offen`/`geprüft` ohne Freigabe; das ist ein Schreibvorgang und braucht mindestens eine Katalogregel (`frei` nur durch den Captain), nicht stillschweigend ohne Gate. (2) Das Ziel `docs/AAR/LESSONS.md` existiert im Repo nicht; Ort und Anlage sind mit dem Captain zu klären (W4-Q-Fragen). (3) Die Wirkungsklasse `proposal_only` kommt bisher nur im Agent-Manager vor; die Harness-Klassen aus `desk/freigabeklasse.py` sind maßgeblich. Status: Entwurf, noch nicht vom Captain freigegeben.


**Stand:** 2026-11-14  
**Register:** SEDRA-W4  
**Abhängig von:** W3 (Werkzeuge `desktop_aendern`, `profil_wechseln`, auf main), SPEC_HARNESS_SHELL_v1 (Harness-Rahmen, Werkzeug-Regel)  
**Quellen:** `docs/SPEC_W3_DESKTOP_AENDERN_2026-11-14.md` (Form der Spec), `docs/ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05.md` (W4-Stufe), `runtime/src/sedra_runtime/harness/werkzeuge.py` (NAMEN, SCHEMAS, vorbereiten/ausfuehren), `runtime/src/sedra_runtime/harness/freigabe.py` (Einstufung, Karten), `runtime/src/sedra_runtime/harness/katalog.py` (einstufen, OHNE_KARTE)  
**Ziel:** Spec für die Schreibwerkzeuge `rueckblick_schreiben` und `vorschlaege_pflegen` in der Harness — **kein Code**, nur Dokumentation. Datei unter 400 Zeilen.

> **Harte Regel:** `rueckblick_schreiben` und `vorschlaege_pflegen` sind Schreibwerkzeuge. Sie brauchen immer eine Freigabe (Antrag/Karte), nie ohne Freigabe ausführbar. Maßnahmen aus einem Rückblick werden nur mit Zustimmung des Captains umgesetzt.

---

## 1. Zweck & Abgrenzung

| Aspekt | Beschreibung |
|---|---|
| **Zweck** | Zwei neue Chat-Werkzeuge für die Lernschleife im Harness: `rueckblick_schreiben` erfasst einen strukturierten Rückblick (Antrag für `docs/AAR/LESSONS.md` mit Maßnahmen), `vorschlaege_pflegen` pflegt eine Liste von Verbesserungsvorschlägen (Anlage, Änderung, Status). Beide legen nur Anträge im Posteingang des Captains an; wirksam werden sie erst nach Freigabe. |
| **Was sie NICHT ist** | Keine direkte Änderung von `docs/AAR/LESSONS.md` ohne Freigabe, keine automatische Umsetzung von Maßnahmen, kein Schreiben außerhalb des Schreibbereichs, keine Änderung bestehender Dokumente ohne Gate. Keine eigene Runtime, läuft als Chat-Werkzeug in der Harness. |
| **Einordnung** | Harness-Werkzeug nach W4-Stufe der Werkzeug-Roadmap (Lernschleife). Wirkungsklasse: `proposal_only` (Antrag, keine direkte Wirkung). Wird über `NAMEN`, `SCHEMAS`, `vorbereiten()`/`ausfuehren()` in `werkzeuge.py` eingebunden. |

---

## 2. Anforderungen (mit IDs)

### 2.1 rueckblick_schreiben

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| W4-01 | `rueckblick_schreiben` erstellt einen Rückblick mit Feldern: `titel`, `sitzung_id`, `datum`, `was_gelaufen_ist`, `was_schief_lief`, `massnahmen` (Liste: `beschreibung`, `verantwortlich`, `frist?`), `dokument_ziel` (Default `docs/AAR/LESSONS.md`). | Unit-Test `RueckblickTest.test_rueckblick_erstellen` |
| W4-02 | `rueckblick_schreiben` legt nur einen **Antrag** im Posteingang an (keine direkte Dateiänderung). Der Rückblick wird erst nach Captain-Freigabe in `docs/AAR/LESSONS.md` eingetragen. | Integration-Test `RueckblickTest.test_antrag_nur_posteingang` |
| W4-03 | Maßnahmen aus dem Rückblick werden nur mit Zustimmung des Captains umgesetzt. Keine Maßnahme ohne Freigabe-Karte. | Integration-Test `RueckblickTest.test_massnahme_mit_freigabe` |
| W4-04 | `rueckblick_schreiben` benötigt mindestens `titel` und `was_gelaufen_ist`. Fehlende Pflichtfelder → `argument_fehlt`. | Unit-Test `RueckblickTest.test_pflichtfelder` |
| W4-05 | Rückblick-Antrag trägt Wirkungsklasse `proposal_only`, Gate-Typ `rueckblick_antrag`, Freigabe durch Captain. | Schema-Test `RueckblickSchemaTest.test_wirkungsklasse` |

### 2.2 vorschlaege_pflegen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| W4-06 | `vorschlaege_pflegen` verwaltet eine Liste von Vorschlägen: Aktion `anlegen`/`aendern`/`status_setzen`, Felder `titel`, `beschreibung`, `quelle` (z. B. `rueckblick`, `chat`, `test`), `status` (offen/geprüft/umgesetzt/abgelehnt), `prioritaet` (niedrig/mittel/hoch), `captain_zustimmung?`. | Unit-Test `VorschlageTest.test_vorschlag_anlegen` |
| W4-07 | `vorschlaege_pflegen` mit Aktion `anlegen` oder `aendern` legt nur einen Antrag im Posteingang an. Keine direkte Dateiänderung. | Integration-Test `VorschlageTest.test_antrag_nur_posteingang` |
| W4-08 | `vorschlaege_pflegen` mit Aktion `status_setzen` auf `umgesetzt` oder `abgelehnt` benötigt Captain-Freigabe (Karte). `offen` und `geprüft` dürfen ohne Captain-Freigabe gesetzt werden (nur Dokumentation). | Integration-Test `VorschlageTest.test_status_mit_freigabe` |
| W4-09 | Vorschlag benötigt mindestens `titel` und `aktion`. Fehlende Pflichtfelder → `argument_fehlt`. | Unit-Test `VorschlageTest.test_pflichtfelder` |
| W4-10 | Vorschläge werden nicht automatisch umgesetzt. Umsetzung braucht eigenständigen Antrag oder Captain-Freigabe. | Unit-Test `VorschlageTest.test_keine_automatische_umsetzung` |

### 2.3 Einbindung in die Harness

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| W4-11 | Beide Werkzeuge werden in `NAMEN` (werkzeuge.py) aufgenommen. Wirkungsklasse: `proposal_only`. | Schema-Test `HarnessTest.test_w4_in_namen` |
| W4-12 | Beide Werkzeuge erhalten ein Schema in `SCHEMAS` (werkzeuge.py) mit den Pflichtfeldern aus §2.1/§2.2. | Schema-Test `HarnessTest.test_w4_schemas` |
| W4-13 | Beide Werkzeuge erhalten Zweige in `vorbereiten()` (Ziel, Vorschau, Gate) und `ausfuehren()` (nur Antrag anlegen, keine Wirkung). | Unit-Test `HarnessTest.test_w4_vorbereiten_ausfuehren` |
| W4-14 | Gate-Einstufung für beide: `captain` (Antrag/Karte). Nie `frei`, nie ohne Karte. | Einstufung-Test `EinstufungTest.test_w4_captain` |
| W4-15 | Beide Werkzeuge werden in `HARNESS_WEGE`/`HARNESS_UNTERWEGE`/`ROUTEN_HARNESS` (falls vorhanden) und in `harness/api.py` (Regex `WEG`/`GESCHUETZT`) eingetragen, soweit die Harness-Regel es verlangt. | Einstufung-Test `EinstufungTest.test_w4_wege_routen` |
| W4-16 | Karte im Katalog (oder `OHNE_KARTE`), falls die Harness-Regel eine Karte verlangt. Schreibwerkzeug nie ohne Freigabe. | Einstufung-Test `EinstufungTest.test_w4_karte` |

---

## 3. Datenmodell

| Entität / VO | Felder (Kern) | Herkunft |
|---|---|---|
| `Rueckblick` | `titel`, `sitzung_id`, `datum` (ISO8601), `was_gelaufen_ist`, `was_schief_lief`, `massnahmen: list[Massnahme]`, `dokument_ziel` (Default `docs/AAR/LESSONS.md`), `status` (offen/freigegeben/abgelehnt), `antrag_id` | Eingabe |
| `Massnahme` | `beschreibung`, `verantwortlich`, `frist?` (ISO8601), `status` (geplant/umgesetzt/abgelehnt), `captain_zustimmung?` | Rückblick |
| `Vorschlag` | `titel`, `beschreibung`, `quelle` (rueckblick/chat/test), `status` (offen/geprüft/umgesetzt/abgelehnt), `prioritaet` (niedrig/mittel/hoch), `captain_zustimmung?`, `antrag_id` | Eingabe |
| `Antrag` | `antrag_id`, `werkzeug` (rueckblick_schreiben/vorschlaege_pflegen), `ziel`, `dokument`, `status` (offen/freigegeben/abgelehnt), `captain_entscheidung?`, `entschieden_am?` | Harness-Gate |

Value Objects: `AntragId`, `SitzungId`, `Prioritaet`, `VorschlagStatus`, `MassnahmeStatus`.

---

## 4. Betroffene Dateien (nur benennen)

| Datei / Pfad | Rolle für W4 |
|---|---|
| `runtime/src/sedra_runtime/harness/werkzeuge.py` | `NAMEN` um beide Werkzeuge ergänzen, `SCHEMAS` um beide Schemas, `WIRKUNGSKLASSE` um `proposal_only`, Zweige in `vorbereiten()` und `ausfuehren()` |
| `runtime/src/sedra_runtime/harness/katalog.py` | Einstufung der beiden Werkzeuge (`proposal_only`, `captain`-Gate) |
| `runtime/src/sedra_runtime/harness/freigabe.py` | Gate-Typ `rueckblick_antrag` / `vorschlag_antrag`, Karte für Captain-Freigabe |
| `runtime/src/sedra_runtime/harness/api.py` | Regex `WEG`/`GESCHUETZT` für beide Werkzeuge, soweit die Harness-Regel es verlangt |
| `runtime/src/sedra_runtime/harness/vorbehalte.py` | Vorbehalts-Prüfung für beide Werkzeuge (Schreibbereich, keine direkte Wirkung) |
| `docs/AAR/LESSONS.md` | Ziel-Dokument für genehmigte Rückblicke (nur nach Freigabe) |
| `runtime/src/sedra_runtime/harness/` | Neue Tests für beide Werkzeuge (siehe §2, Spalte „Prüfbar durch“) |

---

## 5. Freigabegrenzen & Gegenproben (harte Anforderungen)

| Grenze | Beschreibung | Gegenprobe (muss fehlschlagen) |
|---|---|---|
| **Nie ohne Freigabe** | Beide Werkzeuge brauchen immer eine Captain-Freigabe (Karte). Kein Aufruf ohne Gate. | Aufruf ohne Gate → 403 `gate_required` |
| **Keine direkte Dateiänderung** | `rueckblick_schreiben` schreibt nicht direkt in `docs/AAR/LESSONS.md`. Nur Antrag im Posteingang. | Direkter Schreibversuch → 403 `direkte_aenderung_verboten` |
| **Maßnahmen nur mit Captain-Zustimmung** | Maßnahmen aus einem Rückblick werden nur umgesetzt, wenn der Captain freigibt. | Maßnahme ohne Zustimmung → `umsetzung_gesperrt` |
| **Keine automatische Umsetzung** | Vorschläge werden nicht automatisch umgesetzt. Umsetzung braucht eigenständigen Antrag. | Automatische Umsetzung → `nicht_erlaubt` |
| **Wirkungsklasse proposal_only** | Beide Werkzeuge haben Wirkungsklasse `proposal_only`, nie `frei` oder ohne Karte. | Einstufung `frei` → Test fehlschlägt |
| **Pflichtfelder** | `titel` und `was_gelaufen_ist` (Rückblick) bzw. `titel` und `aktion` (Vorschlag) sind Pflicht. | Ohne Pflichtfelder → `argument_fehlt` |

---

## 6. Reihenfolge der Schritte (Implementierungsfolge, für späteren Auftrag)

1. **Werkzeugnamen in `NAMEN`** aufnehmen (`rueckblick_schreiben`, `vorschlaege_pflegen`).
2. **Schemas in `SCHEMAS`** anlegen (Pflichtfelder aus §2.1/§2.2).
3. **Wirkungsklasse `proposal_only`** in `WIRKUNGSKLASSE` eintragen.
4. **Zweige in `vorbereiten()`** für beide Werkzeuge (Ziel, Vorschau, Gate-Typ `captain`).
5. **Zweige in `ausfuehren()`** für beide Werkzeuge (nur Antrag anlegen, keine direkte Wirkung).
6. **Gate-Einstufung** in `freigabe.py` / `katalog.py` (Captain-Freigabe, Karte).
7. **`HARNESS_WEGE`/`HARNESS_UNTERWEGE`/`ROUTEN_HARNESS`** und Regex in `harness/api.py` ergänzen, soweit die Harness-Regel es verlangt.
8. **Tests** (siehe §2, Spalte „Prüfbar durch“).
9. **Abnahme**: Captain prüft keine direkte Änderung, keine Umsetzung ohne Freigabe, Karte immer vorhanden, Pflichtfelder geprüft.

---

## 7. Offene Fragen (mit Vorschlag)

| Frage | Vorschlag | Begründung |
|---|---|---|
| W4-Q1: Wo liegt die Vorschlagsliste vor der Freigabe? | Im Posteingang des Captains (Antrag), nicht in einer eigenen Datei. Genehmigte Vorschläge werden nach Freigabe in `docs/AAR/LESSONS.md` oder einer Vorschlagsdatei eingetragen. | Konsistent mit anderen Antrag-Werkzeugen (`projekt_beantragen`, `vorlage_beantragen`). |
| W4-Q2: Welches Format hat `docs/AAR/LESSONS.md`? | Markdown mit Sektionen pro Rückblick (Datum, Titel, Was lief gut, Was schief lief, Maßnahmen mit Status). | Einfache, lesbare Form für den Captain. |
| W4-Q3: Kann ein Vorschlag direkt aus einem Rückblick entstehen? | Ja, `rueckblick_schreiben` kann `quelle: rueckblick` für `vorschlaege_pflegen` erzeugen, aber nur als Antrag. | Vermeidung von Doppelarbeit, aber keine automatische Umsetzung. |
| W4-Q4: Welche Rollen dürfen Rückblicke schreiben? | Alle authentifizierten Sitzungen, aber Freigabe immer durch Captain. | Rückblick-Schreiben ist geringrisiko, Umsetzung ist die Entscheidung. |
| W4-Q5: Gibt es eine Frist für Captain-Entscheidungen? | Nein, vorerst keine Frist. Entscheidung im Chat / Posteingang. | Einfachheit für MVP. |

---

## 8. Anforderungs-IDs (Zusammenfassung)

W4-01 bis W4-16 (16 Anforderungen).  
Offene Fragen: W4-Q1 bis W4-Q5 (5 Fragen).

---

## 9. Referenzen (nur Lesen)

- `docs/SPEC_W3_DESKTOP_AENDERN_2026-11-14.md`: Form-Vorlage für diese Spec (W3).
- `docs/ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05.md`: W4-Stufe der Werkzeug-Roadmap.
- `runtime/src/sedra_runtime/harness/werkzeuge.py`: `NAMEN`, `SCHEMAS`, `WIRKUNGSKLASSE`, `vorbereiten()`, `ausfuehren()`.
- `runtime/src/sedra_runtime/harness/freigabe.py`: Einstufung, Karten, Gate-Typen.
- `runtime/src/sedra_runtime/harness/katalog.py`: `einstufen`, `OHNE_KARTE`.
- `runtime/src/sedra_runtime/harness/api.py`: Regex `WEG`/`GESCHUETZT`, Routen.
- `runtime/src/sedra_runtime/harness/vorbehalte.py`: Vorbehalts-Prüfung.
- `docs/AAR/LESSONS.md`: Ziel-Dokument für genehmigte Rückblicke.

---

**Ende der Spec W4.**  
Kein Code geschrieben. Dokument liegt im Worktree `pi-a010` unter `docs/SPEC_W4_RUECKBLICK_VORSCHLAEGE_2026-11-14.md`.
