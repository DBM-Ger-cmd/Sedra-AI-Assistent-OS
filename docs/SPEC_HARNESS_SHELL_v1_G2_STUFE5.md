# SPEC Harness-Shell v1 – G2 Design für Stufe 5 (30.10.2026)

Grundlage: `SPEC_HARNESS_SHELL_v1.md` (G1 §3.5 HS-42, §6 Stufe 5), Stufe 4 (`…_G2_STUFE4.md`, `…_G3_STUFE4.md`, `BAUBERICHT_HARNESS_STUFE4_2026-10-29.md`).
Stand des Codes: Branch `harness/stufe-4` `942bc1d` (auf `main` `ce433c0`; `origin/main` am 30.10. 07:45 unverändert). **G4 Stufe 4 steht noch aus**
(Prüfung des Captains am PC); Stufe 5 setzt auf Stufe 4 auf und wird erst nach G4 gebaut. Baut: Claude allein (Captain 29.10. 15:53).

Stufe 5 = **Einstellungen** (HS-42): eine eigene Seite mit Navigation links und sechs Gruppen – *Allgemein · Agent · Sprache · Integrationen ·
Lokale Modelle · System* –, darin der **Katalog-Editor** („Änderungen nur durch den Captain“). Grundsatz aus G1: jede Seite nutzt die
**vorhandenen API-Wege**; Änderungen an `local_config/` nur mit Freigabe des Captains.

## 1. Was vorhanden ist und genutzt wird

| Baustein | Stand | Nutzung in Stufe 5 |
|---|---|---|
| App-Reiter `app.js` (Stufe 4) | hängt jedes Werkzeug des Vertrags in einen Reiter: `forObject` → `makeContext` → `mountTool`, Werkbank-Zeile, Nachweise | **die meisten Einstellungsseiten sind vorhandene Werkzeuge** – die Seite hängt sie mit demselben Code ein (kein Nachbau): Bibliothek, Werkstatt, Slots, Modus und Grenzen, Logbuch, Schutz, KI GateWay, Rekorder, Module |
| Seitenleiste `seite.js` | Knopf „Einstellungen“ sagt heute „kommt in Stufe 5“ | öffnet den Reiter `einstellungen:` |
| Reiter-Arten (`reiter.js`, `verlauf.ansicht`) | `S-…`, `diff:`, `aufgaben:`, `lauf:`, `app:` | neue Art `einstellungen:[gruppe]` (eine Instanz, wie `aufgaben:`) |
| Start-Menü (Stufe 4) | Apps aus Orten; Gruppe System | fester Eintrag „Einstellungen“ in der Gruppe System (kein Ort, kein Werkzeug: die Shell trägt ihn ein) |
| `GET /api/switches` (nur lesen), `switch_request`/`switch_apply` (Gate `SWITCH_ACTION`, Risiko „wirkt erst nach Neustart“) | Schalter aus `local_switches.ALLOWED` | Seite *System → Schalter*: Liste mit Stand, Änderung = Antrag mit Gate, wie heute im Werkzeug Modelle |
| `GET /api/harness/katalog` (nur lesen) | Regeln aus `local_config/freigabe_katalog.yaml` (Captain, D-F2) oder Vorlage; `harness_katalog.pruefen(doc)` | **Katalog-Editor**: lesen wie heute; schreiben nur über einen Antrag mit Gate (§4) |
| `desk/gated.py` | `request`/`apply`/`register_applier`/`decide`: Antrag mit Gate und Bindung, Anwenden nur mit Einmal-Token; Herkunftsprüfung (S7) auf den Antwort-Wegen | der Weg für **jede** Änderung an `local_config/` in den Einstellungen: Katalog, Schalter, Grenzen |
| `GET /api/harness/vorlagen` | Vorlagen (Repo, `local_config/harness_vorlagen/` mit Vorrang), je Vorlage `max_zuege` (4–40), Werkzeuge, Rechte, Modell | Seite *Agent*: Vorlagen lesen; „Grenzen der Schleife“ sind die `max_zuege` je Vorlage |
| `GET /api/models`, `/api/library*`, Slots-View, `llama_server.status()` | Rezepte, geladenes Modell, Bibliothek, Slots, Engine | Seite *Lokale Modelle* über die Werkzeuge `workshop`, `library`, `slots`; „Laufzeit“ = `server`-Zelle aus `/api/strip` plus `engine_check` |
| `GET /api/cloud`, `POST /api/cloud/save` (Audit, `restart_needed`), `/api/cloud/key` | Cloud-Anbieter und Schlüssel | Seite *Integrationen → Cloud* über das Werkzeug `labor` (Anbieter, Schlüssel) – kein eigener Nachbau |
| `GET /api/guard/status`, Werkzeug `schutz`, `boundaries`, `logbook`, `modules` | Inhaltsschutz, Modus und Grenzen, Audit, Module | Seite *System* |
| `/api/sprache/status`, `/api/sprache/kern/*`, Werkzeug `rekorder` | Rekorder im Kern, Aufnahmen | Seite *Sprache*; das Pult der Seite (`wechsel.js`) fehlt in der Harness seit `umschalter: menue` – der Rekorder ist hier ein Werkzeug (Stufe 4) |
| Darstellung/Schrift (`sedraBoot.setTheme`, `sedraWechsel.setScale`), Menü-Seite | im Start-Menü (Stufe 4) | Seite *Allgemein* zeigt dieselben Schalter (ein Code) |
| Benachrichtigung (HS-33: Blinken in der Taskleiste) | kein Browser-Hinweis | Seite *Allgemein → Benachrichtigungen*: Browser-Benachrichtigung bei `decision.pending`, wenn das Fenster nicht vorn ist (= Pi/Herdr-Plan L11/A4, hier gebaut, nicht doppelt) |

## 2. Konflikte und Entscheidungen

| Nr | Konflikt | Entscheidung |
|---|---|---|
| K1 | **Eigene Seite oder Werkzeuge einhängen?** HS-42 verlangt eine Seite mit Navigation; die Inhalte gibt es fast alle als Werkzeuge. | Die Seite ist **Navigation + Einhängen**: je Unterpunkt ein Werkzeug (über `app.js`-Code) oder eine kleine eigene Fläche (Darstellung, Benachrichtigungen, Schalter, Grenzen, Katalog-Editor). Kein Werkzeug wird nachgebaut. → D-U1 |
| K2 | **Katalog schreiben:** D-F2 sagt „die Datei legt nur der Captain an“. Ein Editor in der Oberfläche schreibt sie. | Der Editor schreibt **nie direkt**: er legt einen **Antrag mit Gate** an (`gated.request`, Art `harness_katalog`, Aktion `HARNESS_KATALOG_WRITE`); erst „Freigeben und anwenden“ des Captains im Posteingang schreibt die Datei (Applier). Vorher: `harness_katalog.pruefen` auf den Entwurf, Diff gegen den Stand, Sicherung `freigabe_katalog.yaml.bak-<zeit>`. Die Herkunftsprüfung (S7) gilt für Antrag und Entscheidung: nie aus einem Harness-Prozess, nie durch einen Vorarbeiter (Stufe `captain`, keine Vorarbeiter-Entscheidung, keine Aufgaben-Deckung). → D-U2 |
| K3 | **Was darf der Editor?** Alle Felder einer Regel (`id`, `werkzeug`, `muster`, `stufe`, `begruendung`) oder nur die Stufe? | **Alle Felder**, aber mit den harten Grenzen des Katalogs: `verboten`-Regeln der Vorlage bleiben (keine Lockerung unter die Vorlage, S4/S9 wie bei Aufgaben), „weite Muster“ (`**`, `*`) werden rot gezeigt und im Gate als Risiko genannt. → D-U3 |
| K4 | **Grenzen der Schleife** (HS-42 *Agent*): heute `max_zuege` je Vorlage (Datei), `max_tokens`/`temperature` fest im Code. | Stufe 5 zeigt `max_zuege` je Vorlage und lässt es **je Vorlage** ändern – als Antrag mit Gate, der eine Kopie der Vorlage nach `local_config/harness_vorlagen/` schreibt (Vorrang-Mechanik gibt es schon). `max_tokens`/`temperature` bleiben Code (Anzeige, nicht änderbar) – sie sind keine Captain-Einstellung, sondern Messwerte der Modelle. → D-U4 |
| K5 | **Schalter** (`local_switches.ALLOWED`): Änderung heute im Werkzeug Modelle mit Gate. | Dieselben zwei Wege (`switch_request`/`switch_apply`), neue Oberfläche in *System → Schalter*; der Hinweis „wirkt erst nach Neustart“ bleibt. Kein zweiter Schreibweg. |
| K6 | **Cloud** (`cloud/save` schreibt mit Audit, ohne Gate – so gebaut in Build 5). | Unverändert über das Werkzeug `labor`; Stufe 5 ändert die Regel nicht (sie steht außerhalb der Harness-Spec). → D-U5 (bewusst nicht anfassen) |
| K7 | **MCP** (HS-42 *Integrationen*): es gibt keinen Lese-Weg für den MCP-Stand (`desk_mcp.py`, Client-Token R5). | Neue, nur lesende Route `GET /api/uix/clients` (Clients `cli`/`mcp`: vorhanden ja/nein, Port, seit wann – nie den Token) aus `uix_clients`; die Seite zeigt sie und den Aufruf-Weg (`desk_mcp.py`). Keine Konfiguration (es gibt keine). |
| K8 | **Sprache → Quelle**: welches Mikrofon/welche Quelle der Rekorder nimmt. | Nur, was `/api/sprache/status` heute liefert (Gerät, Zustand); eine Wahl der Quelle gibt es im Kern nicht → Anzeige, kein Schalter. Wenn der Captain die Quelle wählbar will: eigene Spec (Sprache). |
| K9 | **Browser-Benachrichtigung** (K1 oben, Pi/Herdr L11): Erlaubnis liegt im Browser, nicht in `local_config/`. | Schalter in *Allgemein*: an/aus je Browser (`localStorage`, Komfort), Erlaubnis über `Notification.requestPermission()` nur nach Klick; Inhalt nur „SEDRA: eine Freigabe wartet“, nie der Karteninhalt (gilt auch für den Stick-Plan V/W7). Der Pi/Herdr-Plan A4 verweist hierher. |
| K10 | **Dateigrenze 400 Zeilen.** | `einstellungen.js` (Navigation, Seiten-Register, kleine Flächen) ≤ 320; `katalog_editor.js` ≤ 300; `katalog_editor_pruefung.js` (rein: Diff, weite Muster, Lockerung erkennen) ≤ 120 mit node geprüft. |

## 3. Die Seite

### 3.1 Aufbau

Reiter `einstellungen:` (Titel „Einstellungen“, höchstens einer; `einstellungen:<gruppe>/<punkt>` aktiviert den Punkt). Links die Navigation
(sechs Gruppen, darunter die Punkte), rechts die Fläche des gewählten Punkts. Öffnet über den Knopf in der Seitenleiste, das Start-Menü
(System → Einstellungen), `/einstellungen` und den Klick auf die Zelle „Zustand“ (statt Maschinenraum → D-U6).

| Gruppe | Punkt | Fläche | Schreibt? |
|---|---|---|---|
| Allgemein | Darstellung | Klar/Nacht, Schrift, Menü-Seite – dieselben Funktionen wie im Start-Menü | Browser |
| | Benachrichtigungen | Schalter Browser-Hinweis (K9), Blinken in der Taskleiste an/aus | Browser |
| | Sprache der Oberfläche | nur Anzeige „Deutsch“ (es gibt keine zweite) | – |
| Agent | Vorlagen | Liste aus `/api/harness/vorlagen` (Quelle Repo/local_config, Werkzeuge, Rechte, Modell), Text der `.md` lesbar | – |
| | Freigabe-Modus | Katalog-Stand (Datei des Captains oder Vorlage), Zahl der Regeln je Stufe, Knopf „Katalog bearbeiten“ → §4 | Gate |
| | Grenzen der Schleife | `max_zuege` je Vorlage (4–40) ändern → Antrag mit Gate (K4); `max_tokens`, `temperature` nur Anzeige | Gate |
| Sprache | Rekorder | Werkzeug `rekorder` eingehängt | – |
| | Quelle | Anzeige aus `/api/sprache/status` (K8) | – |
| Integrationen | MCP | `GET /api/uix/clients` (K7), Aufruf-Weg | – |
| | KI GateWay | Werkzeuge `gateway` und `schutz` eingehängt | – |
| | Cloud | Werkzeug `labor` eingehängt (K6) | wie heute |
| Lokale Modelle | Bibliothek | Werkzeug `library` | wie heute |
| | Rezepte / Werkstatt | Werkzeug `workshop` | wie heute (Gates im Werkzeug) |
| | Slots | Werkzeug `slots` | – |
| | Geladene Instanzen · Laufzeit | `/api/models` (geladen, Kontext, Slots), `server`-Zelle, Engine-Build und `engine_check` | – |
| System | Guard / Inhaltsschutz | Werkzeug `schutz` (`/api/guard/status`) | – |
| | Schalter | Liste aus `/api/switches`; Änderung → `switch_request` (Gate), Hinweis Neustart (K5) | Gate |
| | Modus und Grenzen | Werkzeug `boundaries` | wie heute (Gate) |
| | Module | Werkzeug `modules` | wie heute (Gate) |
| | Audit | Werkzeug `logbook` | – |

Ein eingehängtes Werkzeug bekommt dasselbe `objekt` wie im Start-Menü (`places.js`), denselben Kontext (`makeContext`), dieselbe
Werkbank-Zeile; es weiß nicht, dass es in den Einstellungen steht. Ein Punkt ohne geladenes Werkzeug zeigt den Satz aus `app.js`.

### 3.2 Zustand

Gewählter Punkt im Browser (`sedra.harness.einstellungen`, Komfort). Nichts aus den Einstellungen wird ohne Gate auf den Rechner geschrieben.
Offene Anträge (Katalog, Schalter, Grenzen) stehen im Posteingang und als Hinweis auf der jeweiligen Seite („Antrag offen – im Posteingang“).

## 4. Der Katalog-Editor (HS-42, „Änderungen nur durch den Captain“)

1. **Lesen:** `GET /api/harness/katalog` → Regeln (`id`, `werkzeug`, `muster`, `stufe`, `begruendung`, Herkunft Vorlage/Datei). Tabelle, je Zeile
   bearbeitbar, Zeile hinzufügen/entfernen; die Vorlage-Regeln mit `verboten` sind gesperrt (K3).
2. **Prüfen (rein, `katalog_editor_pruefung.js`):** Diff gegen den Stand; weite Muster rot; eine Lockerung (Regel der Vorlage von `verboten`/`captain`
   nach `vorarbeiter`/`frei`) wird genannt; doppelte IDs, leere Muster → Fehler mit Satz.
3. **Antrag:** `POST /api/harness/katalog/antrag {regeln}` → Server prüft mit `harness_katalog.pruefen` (dieselbe Prüfung wie beim Laden), legt über
   `gated.request` einen Antrag an (Art `harness_katalog`, Aktion `HARNESS_KATALOG_WRITE`, Ziel `local_config/freigabe_katalog.yaml`, Bindung =
   Hash des Entwurfs + Hash des Stands, Risiken = die Befunde aus 2). Herkunftsprüfung S7 wie bei Karten. Keine Vorarbeiter-Entscheidung, keine
   Aufgaben-Deckung: Stufe immer `captain` (Bindung `exact`).
4. **Anwenden (Applier):** nach „Freigeben und anwenden“ im Posteingang: Stand unverändert (Hash)? sonst `binding_stale`; Sicherung
   `.bak-<zeit>`; Datei schreiben (atomar); `HARNESS_KATALOG_WRITTEN` im Audit (Zahl der Regeln, Hash); die laufenden Sitzungen sehen den neuen
   Katalog beim nächsten Aufruf (Katalog wird je Aufruf geladen – prüfen, sonst Hinweis „gilt ab der nächsten Sitzung“).
5. **Zurück:** „Zurück zur Vorlage“ = Antrag, die Datei zu entfernen (dann gilt wieder `freigabe_katalog.beispiel.yaml`) – auch mit Gate, Sicherung bleibt.

## 5. Endpunkte (neu)

| Weg | Methode | Zweck | Gate |
|---|---|---|---|
| `/api/harness/katalog/antrag` | POST | Entwurf prüfen und Antrag anlegen (§4.3) | ja (`HARNESS_KATALOG_WRITE`) |
| `/api/harness/katalog/entfernen` | POST | Antrag: Datei des Captains entfernen (§4.5) | ja |
| `/api/harness/vorlagen/grenzen` | POST | Antrag: `max_zuege` einer Vorlage (Kopie nach `local_config/harness_vorlagen/`) | ja (`HARNESS_VORLAGE_WRITE`) |
| `/api/uix/clients` | GET | MCP/CLI-Clients: vorhanden, Port, seit – nie Token (K7) | – |

Ereignisse: `harness.katalog` (nach dem Anwenden), sonst die vorhandenen (`decision.pending/answered`).

## 6. Dateien

| Datei | Neu/geändert | Inhalt | Zeilen (Ziel) |
|---|---|---|---|
| `shells/harness/einstellungen.js` | neu | Reiter, Navigation, Seiten-Register, kleine Flächen (Darstellung, Benachrichtigungen, Grenzen, Schalter, Laufzeit, MCP, Quelle), Einhängen über `app.js` | ≤ 320 |
| `shells/harness/katalog_editor.js` | neu | Tabelle, Bearbeiten, Antrag, Stand der Anträge | ≤ 300 |
| `shells/harness/katalog_editor_pruefung.js` | neu, rein | Diff, weite Muster, Lockerung, Fehler | ≤ 120 |
| `shells/harness/app.js` | geändert | `einhaengen(S, manifest, objekt, ziel)` als wiederverwendbare Funktion (für die Einstellungen) | +15 |
| `shells/harness/{reiter,verlauf,seite,eingabe,startmenue,taskleiste}.js`, `shell.yaml` (1.5.0, Routen), `shell.css`, `arbeitsplatz.yaml`, `README.md` | geändert | Art `einstellungen:`, Knopf, Eintrag im Start-Menü, `/einstellungen`, Zelle Zustand | klein |
| `harness/api.py`, `harness/katalog.py` (`schreiben`, `sichern`), `harness/vorlagen.py` (`grenzen_schreiben`) | geändert | Routen §5, Applier (`gated.register_applier('harness_katalog', …)`, `'harness_vorlage'`) | +150 |
| `uix_server.py` | geändert | `GET /api/uix/clients` | +20 |
| `tests/test_harness_katalog_editor.py` (neu), `tests/test_uix_harness_einstellungen.py` (neu), `test_uix_harness_shell.py`, `test_uix_contract` | neu/geändert | Prüfung rein (node), Antrag/Applier/Stale/Herkunft (Python), Seite im Browser (uix_check) | – |
| `benchmarks/harness_abnahme.py --stufe5`, `uix_check.py` Profil | geändert | S5-A bis S5-D | – |

## 7. Tests und Abnahme

- Rein (node): Diff, weite Muster, Lockerung erkannt, doppelte ID, leeres Muster → Satz.
- Python: Antrag legt Gate an, schreibt nichts; Anwenden ohne Token → abgelehnt; geänderter Stand → `binding_stale`; Sicherung liegt; Audit;
  Antrag aus einem Harness-Prozess (Herkunft) → 403; Vorarbeiter kann nicht entscheiden; `max_zuege` außerhalb 4–40 → Fehler; `/api/uix/clients` ohne Token.
- Browser (`uix_check --shell harness`, Marken `hs-einst`, `hs-einst-nav`, `hs-katalog`): jede der 21 Flächen öffnet ohne Konsolenfehler; eingehängte Werkzeuge haben `[data-tool]`.
- Abnahme ohne Modell: **S5-A** jede Seite erreichbar (Seitenleiste, Start-Menü, `/einstellungen`), **S5-B** Katalog: Regel ändern → Antrag im
  Posteingang → Ablehnen: Datei unverändert; Freigeben: Datei geschrieben, Sicherung da, Audit; **S5-C** Schalter `entwicklung` → Antrag → Freigeben
  → Hinweis Neustart; **S5-D** Grenzen: `max_zuege` der Vorlage `bauagent` auf 12 → Kopie in `local_config/harness_vorlagen/`, `GET vorlagen` zeigt Quelle `local_config`.

## 8. Berechtigungen vorab

| Nr | Was | Vorschlag |
|---|---|---|
| P5-1 | Schreiben: `uix/shells/harness/**`, `harness/api.py`, `harness/katalog.py`, `harness/vorlagen.py`, `uix_server.py` (nur `clients`-Route), `desk/gated.py` **nicht** (nur Registrierung eines Appliers von außen), Tests, `benchmarks/harness_abnahme.py`, `uix_check.py`, Docs, Logbuch | ja |
| P5-2 | Befehle wie Stufe 4 (`run_tests.py`, `node`, `uix_check`, `harness_abnahme --stufe5`), ohne Modell | ja |
| P5-3 | **Nicht:** `local_config/` des Captains (die Tests schreiben nur in temporäre Prüfprojekte), `config/freigabe_katalog.beispiel.yaml` (die Vorlage bleibt), Modelle, Läufe, Push | – |
| P5-4 | Lieferung wie Stufe 4: Fork-ZIP, Branch `harness/stufe-5` auf `harness/stufe-4` | – |

## 9. Fragen an den Captain (Vorschlag jeweils fett)

| ID | Frage | Vorschlag |
|---|---|---|
| D-U1 | **Seiten aus Werkzeugen** (K1): die Einstellungen hängen vorhandene Werkzeuge ein, nur fünf kleine Flächen sind eigene. | **Ja** – keine Nachbauten. |
| D-U2 | **Katalog-Editor schreibt nur über Antrag + Gate** (K2); Entscheidung nur durch den Captain, nie Vorarbeiter. | **Ja.** |
| D-U3 | **Editor darf alle Felder**, Vorlage-`verboten` gesperrt, Lockerungen und weite Muster rot und als Risiko im Gate (K3). | **Ja.** Alternative: nur `stufe` änderbar – zu wenig für neue Projekte. |
| D-U4 | **Grenzen der Schleife** = `max_zuege` je Vorlage, über Gate als Kopie nach `local_config/harness_vorlagen/`; `max_tokens`/`temperature` nur Anzeige (K4). | **Ja.** |
| D-U5 | **Cloud bleibt wie gebaut** (Speichern mit Audit, ohne Gate) – nicht in dieser Stufe ändern (K6). | **Ja**, Hinweis im Bericht. |
| D-U6 | **Klick auf die Zelle „Zustand“** öffnet die Einstellungen (System) statt den Maschinenraum. | **Ja.** |
| D-U7 | **Browser-Benachrichtigung** hier bauen (K9) und im Pi/Herdr-Plan A4 als erledigt verweisen. | **Ja.** |
| D-U8 | **Reihenfolge:** G3 und Bau erst nach deinem G4 für Stufe 4? Oder G3 schon schreiben, Bau wartet. | **G3 jetzt schreiben, Bau nach G4** – falls dein G4 Änderungen bringt, fließen sie vor dem Bau ein. |

## 10. Entscheidungen des Captains

Captain 30.10.2026 07:53: „lass uns weiter an Stufe 5 arbeiten und im Anschluss nochmal alles prüfen“ – gelesen als: D-U1 bis D-U7 wie vorgeschlagen; **D-U8: Bau jetzt**, nicht erst nach G4 Stufe 4 (G4 bleibt offen und wird mit der Gesamtprüfung am Ende nachgeholt). G2 Stufe 5 freigegeben; Bau-Aufgaben: `SPEC_HARNESS_SHELL_v1_G3_STUFE5.md`.
