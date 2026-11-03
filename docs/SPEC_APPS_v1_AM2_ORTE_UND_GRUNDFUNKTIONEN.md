# SPEC Apps v1 – AM2: Orte aus Manifesten, Shell-eigene Apps, Grundfunktionen (03.11.2026)

Status: **G1** (Anforderungen mit Entwurf), nichts gebaut. Teil von `docs/KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` §11. Setzt AM1 (`shells`) voraus.
Ziel: (1) Eine App bringt ihren Ort (Name, Wörter, Gruppe) im Manifest mit, statt in zwei Listen des Kerns zu stehen. (2) Shells können eigene Apps haben. (3) Die bestätigten Grundfunktionen sind in jeder Shell erreichbar, und das wird geprüft.
Pfade relativ zu `runtime/src/guppi_runtime/`, Zeilen für c364081.

## 1. Befund

| Nr | Befund | Beleg |
|---|---|---|
| B1 | Orte stehen in `ui/places.js` (`PLACES`: id, label, hint, words, object) und in `chat_tools.py` (`PLACES`: id → label, hint). Ein Test vergleicht die IDs (Kommentar `chat_tools.py:107`; Test vermutlich `tests/test_uix_vertrag11.py`, nicht gelesen). | `ui/places.js:14`, `chat_tools.py:108` |
| B2 | Das Modell öffnet Fenster mit `app_oeffnen` nur für Orte aus `chat_tools.PLACES`. | `harness/werkzeuge.py:49–54, 420–433` |
| B3 | Das Start-Menü der Harness baut Apps aus den Orten **und** erzeugt für Werkzeuge ohne Ort einen Ort `werkzeug-<id>` aus dem ersten Objekttyp. Die Ableitung aus Manifesten gibt es also schon zum Teil. | `shells/harness/startliste.js:40–63` |
| B4 | Gruppen: `gruppe` im Manifest gewinnt, sonst `start_gruppen.json` (Ort-ID oder Objekttyp → Gruppe), sonst `arbeit`. | Vertrag Nachtrag N2; `startliste.js:62`; `shells/harness/start_gruppen.json` |
| B5 | Orte gelten „in jeder Shell“; eine Shell ohne Werkzeug für einen Ort zeigt ihren Leerzustand. | Vertrag, Nachtrag 21.10. „Orte (G2-S4-21)“ |
| B6 | Shells haben keinen Platz für eigene Werkzeuge; alle Werkzeuge liegen in `uix/tools/` oder `local_config/tools/`. | `desk/registry.py` `module_dirs` (`:205`) |
| B7 | Grundfunktionen sind nicht festgelegt. Was die Shells heute anbieten (nur nach `provides` in `shell.yaml`, **nicht im Browser geprüft**): | siehe Tabelle unten |

| Shell | `provides` / Art | Gespräch | Entscheidungen | Bemerkung |
|---|---|---|---|---|
| `harness` | `seite, reiter, flaeche, eingabe, taskleiste` | eigen | Posteingang in der Seitenleiste (`uix/shells/harness/arbeitsplatz.yaml:7–8`) | Einstellungen eigen; Logbuch, Module usw. als Apps im Start-Menü |
| `cockpit` | `strip, tree, dock, talk, palette` | `talk` | über Ort | – |
| `paperclip` | `tree, dock, windows, talk, notify, palette, inbox` | `talk` | `inbox` | – |
| `minimal` | `menubar, windows, talk, notify` | `talk` | über Ort | – |
| `fisch` (Translator) | `dock, talk, notify` | `talk` | über Ort? | nicht geprüft |
| `gateway-kmu` | `dock, talk` | `talk` | nur Antwortroute `POST /api/decisions/answer` | keine Leiste, kein Baum, keine Palette |
| `start` | `chooser, talk, notify, inbox` | `talk` | `inbox` | Einstieg/Auswahl |
| `guppi-xp` | `chooser` | – | – | leitet nur auf das Archiv `/retro` um |
| `gateway-studio`, `wissensbasis` | Vorgabe (Rahmen `ui/frame.js`) | Zone `gespraech` | Zone `entscheidungen` (falls im Raster) | `FRAME_ZONES` `desk/gateway.py:70` |

## 2. Anforderungen

### 2.1 Orte

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM2-01 | **Eine Quelle für die Kernorte**: `uix/ui/orte_kern.json` mit allen heutigen Einträgen aus `places.js` (id, label, hint, words, object). `chat_tools.PLACES` wird daraus gelesen (Python), `places.js` bekommt die Liste beim Start aus dem Manifest (`/uix/manifest` → `orte`) und behält eine eingebaute Kopie nur als Rückfall für Node-Tests; ein Test stellt Gleichheit Kopie = JSON sicher. | Test; bestehende Navigationstests |
| AM2-02 | **Feld `ort`** in `tool.yaml`: `{id, label, hint, words, object: {type, id, title?, view?}, symbol?}`. `id` wie Werkzeug-IDs; `label` 1–40, `hint` ≤ 80 Zeichen; `words` 1–12 Wörter, je 2–30 Zeichen, klein; `symbol` ein Zeichen aus einer festen Liste der Shell (kein Bild); `object.type` muss in `handles` stehen. | Schema-Test |
| AM2-03 | **Kollisionen**: Eine `ort.id`, die es als Kernort oder bei einer anderen App gibt → `ort_id_belegt`. Ein Wort, das ein Kernort nutzt oder das in `ORDER_WORDS`/`QUESTION_WORDS`/`OPEN_WORDS` von `places.js` steht → `ort_wort_reserviert:<wort>`. Zwei Apps mit demselben Wort → beide geladen, das Wort gilt für keine (Meldung im Werkzeug „Module“). | Test |
| AM2-04 | **Zusammensetzung je Shell**: `orte(shell) = Kernorte ∪ { app.ort | app verfügbar in shell (AM1) und (ab AM3) aktiviert }`. Der Server liefert sie in `/uix/manifest` als `orte`; der Chat nutzt dieselbe Funktion mit der aktiven Shell aus `uix.yaml`. | Test mit zwei Shells |
| AM2-05 | `app_oeffnen` öffnet nur Orte aus `orte(aktive Shell)`; bei unbekanntem Ort nennt die Fehlermeldung die verfügbaren IDs (wie heute `unknown_place`, `chat_tools.py:210`). | Test |
| AM2-06 | Das Start-Menü (`startliste.bauen`) nutzt `orte(shell)`; die Ableitung `werkzeug-<id>` bleibt für Werkzeuge ohne `ort`. `start_gruppen.json` behält nur die Zuordnung der Kernorte und die Gruppen. | Node-Test `startliste` |

### 2.2 Shell-eigene Apps

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM2-07 | Eine Shell darf Apps in `uix/shells/<shell>/apps/<id>/tool.yaml` mitbringen (Paket) bzw. `local_config/shells/<shell>/apps/<id>/` (eingebaut mit der Shell). Sie gelten nur in dieser Shell: `shells` ist implizit `[<shell>]`; ein anderes `shells` im Manifest → `shell_app_shells_fest`. | Test |
| AM2-08 | Die `id` ist **global eindeutig** (über `uix/tools`, alle `apps/`-Ordner und `local_config`), weil Allowlist, Ablage und Audit über die `id` laufen (`X-SEDRA-Tool`). Dopplung → beide abgewiesen mit `id_doppelt`. | Test |
| AM2-09 | Vertrauen folgt der Herkunft der **App**, nicht der Shell: im Paket CORE möglich; eingebaut immer `COMMUNITY` (auch wenn die Shell `CAPTAIN` ist). Apps einer fremden Shell laufen damit im Rahmen. | Test |
| AM2-10 | Dateien werden unter dem bestehenden Pfad `/uix/tools/<id>/<datei>` ausgeliefert; der Server findet den Ordner über die Registrierung (kein neues URL-Schema, `MODULE_FILE` `uix_server.py:3515` bleibt). | Test |
| AM2-11 | Shell-Wechsel: Offene Reiter von Apps, die in der Ziel-Shell nicht verfügbar sind, werden nicht geöffnet; ein Hinweis nennt sie; der Arbeitsstand behält sie für die Rückkehr. | Test der Shells mit Arbeitsstand |

### 2.3 Grundfunktionen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM2-12 | Die sieben Grundfunktionen (bestätigt): `entscheidungen`, `gespraech`, `aufgaben`, `logbuch`, `modus_grenzen`, `module_berechtigungen`, `einstellungen_zustand`. Jede hat einen **festen Kernweg** (Konzept §7), den keine Shell nachbaut. | Doku + Test der Kernwege |
| AM2-13 | Die Paket-Werkzeuge `decisions`, `talk`, `task`, `logbook`, `boundaries`, `modules`, `system` tragen `grundfunktion: <name>`. Das Feld ist nur im Paket (`origin == 'package'`, `trust: CORE`) erlaubt, sonst `grundfunktion_nur_im_paket`. `shells` wird bei ihnen ignoriert (immer verfügbar). | Schema-Test |
| AM2-14 | Jede Shell **erklärt** in `shell.yaml` unter `grundfunktionen:` je Grundfunktion, wie sie erreichbar ist: `ort` (über einen Ort/Start-Menü/Palette), `slot:<name>` (eigener Slot, z. B. `slot:inbox`), `eigen` (eigene Fläche der Shell, die den Kernweg nutzt), `verwaltung` (nur über den Verwaltungszugang, ab AM7). Vorgabe-Shells bekommen die Erklärung vom Rahmen (aus Raster und Zonen). | Schema-Test |
| AM2-15 | Prüfung: fehlende Erklärung → im Vertrag 1.1 eine **Warnung** (`grundfunktion_nicht_erklaert:<name>`, sichtbar im Werkzeug „Module“), ab Vertrag 1.2 ein **Fehler** (Shell wird abgewiesen). Zeitpunkt AM2-E2. | Test |
| AM2-16 | `uix_check` prüft je Shell, dass jede erklärte Grundfunktion tatsächlich erreichbar ist: `ort` → Öffnen ergibt eine gezeichnete Fläche; `slot:x` → Element vorhanden; `eigen` → die Shell meldet ein Element mit `data-grundfunktion="<name>"`. | Browser-Prüfung je Shell |
| AM2-17 | Ausnahme für Shells, die keine Arbeitsoberfläche sind: `archiv: true` in `shell.yaml` (heute `guppi-xp`, leitet auf `/retro`) und `einstieg: true` (heute `start`). Sie müssen nur `module_berechtigungen` und den Wechsel in eine andere Shell erreichbar machen. | Schema-Test |
| AM2-18 | Eine App, die eine Grundfunktion überdecken würde (gleiche `ort.id`, gleiches Wort, gleicher Objekttyp mit `collection`), wird abgewiesen (`grundfunktion_ueberdeckt`). | Test |

### 2.4 Vorbereitung für später

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM2-19 | `needs.apps: {<id>: "<bereich>"}` wird geprüft: fehlt die App oder passt die Version nicht → `needs_app_fehlt:<id>` bzw. `needs_app_version:<id>`. | Test |
| AM2-20 | `rollen: [...]` ist im Schema erlaubt (Muster wie IDs), wird aber bis AM7 **nicht ausgewertet**; das Werkzeug „Module“ zeigt „Rollen: noch ohne Wirkung“. | Schema-Test |

## 3. Entwurf

- `orte_kern.json` liegt in `uix/ui/` (Vertragscode, Vorbehalt AM0-01). Python liest sie mit `json`; der Server legt `orte` in `/uix/manifest` ab (öffentlich, keine Geheimnisse).
- `places.js` erhält `setzen(liste)`; `ui/start.js` bzw. der Lader ruft es nach dem Manifest. Die Wortlogik (`wantsOpen`, `ORDER_WORDS` …) bleibt in `places.js`.
- `desk/registry.py` `module_dirs('tools')` liefert zusätzlich `(<shells-ordner>/<shell>/apps/<id>, origin, shell)`; `check_tool` erhält die Shell, um AM2-07 zu prüfen.
- Grundfunktionen-Erklärung (Beispiel Harness):
```yaml
shell:
  id: harness
  grundfunktionen:
    entscheidungen: eigen          # Posteingang der Seitenleiste, Antwort über sedraStand.entscheiden
    gespraech: eigen
    aufgaben: eigen
    logbuch: ort
    modus_grenzen: ort
    module_berechtigungen: ort
    einstellungen_zustand: eigen
```
- KMU-Shell heute: `entscheidungen` nur als Antwortroute, `logbuch`/`modus_grenzen`/`module_berechtigungen`/`einstellungen_zustand` nicht erreichbar → nach AM2-15 zunächst Warnungen; die Lösung für Beschäftigte und Betreiber kommt mit AM7 (`verwaltung`).

## 4. Tests und Abnahme

Schema-Tests (`tests/test_apps_am2_*.py`), Node-Tests `places`, `startliste`, Browser-Prüfung je Shell (AM2-16), Test des Chat-Werkzeugs `app_oeffnen`. Abnahme am PC: eine Test-App mit `ort` erscheint im Start-Menü der Harness und lässt sich mit „öffne <wort>“ im Chat öffnen; dieselbe App mit `shells: [cockpit]` erscheint in der Harness nicht.

## 5. Rückfall

Kernorte bleiben vollständig; ohne `ort` in Manifesten ist der Zustand wie heute. Grundfunktionen-Prüfung zuerst als Warnung. `apps/`-Ordner leer = heutiger Zustand.

## 6. Abgrenzung

Keine Rechte (AM3), keine Rollen-Auswertung (AM7). Kein eigenes Bild als Symbol. Kein Umbenennen bestehender Orte.

## 7. Risiken

- AM2-01 berührt die Navigation aller Shells und den Chat; Fehler zeigen sich als „ich kann das nicht öffnen“. Gegenmittel: Gleichheitstest Kopie = JSON, bestehende Navigationstests.
- Wörter-Kollisionen können Gewohnheiten des Captains brechen, wenn eine App ein beliebtes Wort beansprucht; deshalb gilt ein doppelt beanspruchtes Wort für keine App.
- Die Prüfung der Grundfunktionen deckt Lücken in bestehenden Shells auf (KMU, Translator). Das ist gewollt, darf aber nicht zur Abweisung im Betrieb führen, bevor sie behoben sind (AM2-15 Warnung zuerst).

## 8. Entscheidungen des Captains

| Nr | Frage | Vorschlag |
|---|---|---|
| AM2-E1 | Kernorte als JSON-Datei, die Python und Browser lesen? | ja |
| AM2-E2 | Ab wann ist eine fehlende Grundfunktion ein Fehler? | nach AM7 (dann gibt es `verwaltung` für die KMU-Shell) |
| AM2-E3 | Ausnahmen `archiv` und `einstieg` so? | ja |
| AM2-E4 | Gilt die Grundfunktion „Gespräch“ auch für Shells, in denen Beschäftigte (AM7) kein Gespräch haben sollen? | nein vorwegnehmen; in AM7 entscheiden |

## 9. Berechtigungen vorab

Schreiben `uix/ui/{places.js, orte_kern.json}`, `chat_tools.py`, `harness/werkzeuge.py` (nur Orte), `desk/{gateway.py, registry.py}`, `uix/shells/*/shell.yaml` (nur `grundfunktionen`, `archiv`, `einstieg`), `uix/shells/harness/{startliste.js, start_gruppen.json}`, Manifeste der sieben Grundfunktions-Werkzeuge, `benchmarks/uix_check.py`, Tests.

## 10. Nächste Gates

G1 → G2 (genaue Liste reservierter Wörter, Erklärung je bestehender Shell geprüft im Browser) → G3 → G4.
