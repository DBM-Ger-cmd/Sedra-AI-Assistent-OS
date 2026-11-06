# Interface-Request [IF-MOD-01] – ENTWURF, nicht gestellt

**Status:** Entwurf von Coder 2 für den Koordinator. Er ist **nicht** gestellt. Der Koordinator entscheidet, ob und an wen er geht. Keine Datei geändert. Herkunft `NEW_AI_GENERATED`, Zitate `EXISTING_REUSE`.

- **Beantragender Coder/Task:** Coder 2, Vorbereitung für SEDRA-MOD-04 (Factory-Studio-Mock) und später SEDRA-F3-01 (Factory Studio App). Grundlage: Lücken A, B, C aus `docs/BESTAND_MOD_01_APPS.md` §5.
- **Betroffener Owner:** Updater (geteilte Dateien `desk/extensions.py`, `desk/gateway.py`), Captain (gesperrte `desk/freigabeklasse.py`), Coder 1 nur, wenn Variante 2 gewählt wird.
- **Aktueller Main-HEAD:** `2b13daa` (Git-Bundle, HEAD selbst geprüft).

## Gewünschte Funktion / minimaler Vertrag

Eine neue Paket-App mit Server-Teil muss drei Dinge eintragen können, ohne dass zwei Aufträge dieselbe Zeile gleichzeitig ändern:

| # | Stelle (`2b13daa`) | Heutiger Stand | Benötigter Wortlaut (Platzhalter, endgültige Namen erst aus MOD-03) |
|---|---|---|---|
| Z1 | `desk/extensions.py:3` `MODULES` | `("guppi_runtime.desk.orchestra_kinds", "guppi_runtime.wissen.desk_wissen", "guppi_runtime.workflows.desk")` | ein weiterer Eintrag am Ende, z. B. `"guppi_runtime.factory.desk"` |
| Z2 | `desk/gateway.py:23–30` `OBJECT_TYPES` | Tupel plus fünf `+=`-Zeilen (`issue/budget/gespraech`, `wissen`, `workflow`, `scenario`) | eine neue Zeile im selben Stil: `OBJECT_TYPES += ('factory',)  # Factory Studio (MOD-04/F3-01); Ausführung bleibt im Missionskern` |
| Z3 | `desk/freigabeklasse.py:20 ff.` `ARTEN` | Antragsarten mit Klasse | je freigabepflichtigem Factory-Verb eine Zeile `'request:factory_<art>': H,  # <Satz>`; die Liste der Arten kommt aus MOD-03 |

**Namensregel, die beim Wortlaut zu beachten ist:** Kind-Namen erlauben `[a-z][a-z0-9_]{1,31}` (`desk/kinds.py:52`). Einträge in `handles` erlauben nur `^[a-z0-9-]{2,40}` (`desk/gateway.py:32`, `HANDLE`). Ein Objekttyp, den eine App öffnen soll, darf deshalb **weder `_` noch `-`** enthalten (Beispiel `factory`, nicht `factory_project`). Hilfstypen ohne App wie `workflow_run` dürfen `_` haben.

## Warum die vorhandene API nicht genügt

- Kinds kommen nur aus der festen Liste `MODULES`. Ein installiertes Werkzeug bringt keinen Server-Code mit (`desk/install.py`, Vertrag §6).
- Paket-Werkzeuge dürfen in `handles` nur Typen aus `OBJECT_TYPES` nennen (`desk/gateway.py:164`).
- `tests/test_freigabe_vollstaendig.py` (`test_antragsarten_aus_dem_code`) lässt jede Antragsart aus `gated.request` ohne Eintrag in `ARTEN` fehlschlagen.

Die API ist ausreichend. Es fehlt nur eine Regel, **wer wann** diese drei Stellen ändern darf.

## Minimaler neuer Ein-/Ausgabetyp

Keiner. Es gilt dasselbe Objektmodell (`desk/kinds.py:31` `SHAPE`), dieselben Verben (`desk/actions.py:16`) und dasselbe Gate-Muster (`desk/gated.py`).

## Guard-, Captain- und Recovery-Auswirkungen

- Z1 und Z2 erteilen keine Rechte. Sie machen einen Typ sichtbar.
- Z3 ist sicherheitsrelevant (Klasse H). Er braucht immer einen eigenen Captain-Auftrag (Anweisung 06.11.: `freigabeklasse.py` gesperrt).
- Recovery: keine Wirkung. Ein Fehler beim Laden setzt nur das eine Modul zurück (`desk/extensions.py:13 ff.`, Audit `DESK_KIND_REFUSED`).

## Alternativen

| Variante | Inhalt | Kernänderung | Empfehlung |
|---|---|---|---|
| **1 – Reservierung je Auftrag** | Der Updater reserviert Z1/Z2 für genau einen Auftrag. Die Änderung ist je eine angehängte Zeile, der Updater führt sie beim Merge zusammen. Z3 nur mit Captain-Auftrag. | keine | **empfohlen für MOD-04** (eine App, eine Zeile) |
| 2 – Eintragspunkt | Coder 1 entwirft einen Weg, Erweiterungen und Objekttypen ohne geteilte Zeile anzumelden (z. B. eine Liste je Paket, die `extensions` und `gateway` einlesen). | ja (`desk/`) | erst, wenn mehrere Factory-Apps parallel entstehen (F3-02/03) |
| 3 – nichts ändern | MOD-04 nur als reines Mock ohne Server-Teil (nur vorhandene Typen, z. B. `workflow`, `task`). | keine | möglich für einen ersten Klick-Entwurf, deckt aber Factory-Objekte nicht ab |

## Risiko und Abnahmetests

- Risiko bei Variante 1: zwei offene Aufträge mit Z1/Z2 → `CONFLICT_PENDING` (Regel `02_ROADMAP/ABHAENGIGKEITEN.md`). Die Reservierung verhindert das.
- Abnahme (Vorschlag): `run_tests.py desk test_freigabe_vollstaendig workflow` grün. Dazu ein Test, dass das neue Modul in `MODULES` geladen wird und ein Fehler darin die anderen Kinds nicht stört. Vorbild ist `tests/test_desk_kinds.py`.

## Offene Entscheidungen

- **Koordinator:** IR stellen ja/nein; Variante 1, 2 oder 3.
- **Captain:** Z3 erst nach MOD-03 (die Antragsarten stehen erst dann fest).
- **One Sedra K3:** keine Wirkung auf die Shell-Dateien. Die neue App erscheint über `gruppe` im Start-Menü (`desk/gateway.py:46`).
