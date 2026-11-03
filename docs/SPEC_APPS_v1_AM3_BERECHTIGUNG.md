# SPEC Apps v1 – AM3: App-Berechtigung (03.11.2026)

Status: **G1**, Entscheidungen getroffen (03.11.2026, wie vorgeschlagen); G2 steht noch aus. Nichts gebaut. Teil von `docs/KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` §5, §8, §9, §11. Setzt AM0 voraus.
Ziel: Jede App außerhalb des Pakets hat eine **Berechtigung**: was sie beantragt, was gewährt ist, ob sie aktiv ist. Gewährt wird im Posteingang mit Gate, entzogen sofort. Updates zeigen Datei- und Rechteänderungen. Ereignisse werden nach Klassen gefiltert. Fremde Apps sind sichtbar als fremd gekennzeichnet und können eine Leistenzelle als reine Daten liefern.
Pfade relativ zu `runtime/src/guppi_runtime/`, Zeilen für c364081.

## 1. Befund

| Nr | Befund | Beleg |
|---|---|---|
| B1 | Rechte sind heute Routen (`api:`). `/api/actions` ist eine Route für **alle** Verben; welches Verb eine App ruft, steht im Körper und wird von der Allowlist nicht gesehen. | `desk/gateway.py:282` `route_allowed`; `uix_server.py:3561–3572` |
| B2 | Rechte-Erhöhung gibt es nur als Ganzes: `trust_request` legt **alle** Nicht-GET-Routen des Manifests vor; `trust_apply` setzt danach `trust: CAPTAIN` **in die Manifestdatei** des Moduls. | `uix_server.py:1269–1299, 1301–1335` (Zeile `doc[key]['trust'] = 'CAPTAIN'`) |
| B3 | Auch der Einbau schreibt in das Manifest (`trust: COMMUNITY`), nach der Hashprüfung. | `uix_server.py:462–466` |
| B4 | Folge aus B2/B3 für AM0-02: Eine Hashprüfung nach dem Einbau muss das umgeschriebene Manifest erfassen, und jede spätere Erhöhung über `trust_apply` würde sie brechen. **Rechte dürfen deshalb nicht im Manifest gespeichert werden.** | – |
| B5 | Ein Modul ist mit dem Einbau sofort geladen; es gibt keinen Zustand „eingebaut, aus“. | `install_apply`, danach `tools.refresh` (`uix_server.py:478`) |
| B6 | Gleiche `id` beim Einbau → Fehler „zuerst entfernen“; kein Update-Weg. | `uix_server.py:404–406` |
| B7 | Der Release-Updater kennt schon eine Rechteliste je Modul und verlangt die Bestätigung genau dieser Liste (Schlüssel = Hash der Liste). | `update_anwenden.py:7–8, 72–115` |
| B8 | Die Brücke reicht Ereignisse aus `events.listens` mit voller Nutzlast an den Rahmen. `decision.pending` trägt u. a. `title` (bis 120 Zeichen aus dem Antragstext). `gateway.py` prüft nur die Schreibweise der Namen. | `ui/bruecke.js:91–97`; `uix_server.py:1184`; `gateway.py` `EVENT_NAME` |
| B9 | `shell.notify(text, ton)` aus dem Rahmen erscheint ungefiltert in der Hinweiszeile der Shell. | `bruecke.js:70–83`; `shells/harness/shell.js:58` |
| B10 | Ein Rahmen ist optisch nicht als fremd erkennbar; er bekommt nur das eigene CSS des Werkzeugs (`PLAN_STUFE_C` §10). | `ui/loader.js:149–158` |
| B11 | `emits` in einem Nicht-CORE-Manifest ist wirkungslos: `emit` im Rahmen tut nichts. | `ui/rahmen.js:49` |
| B12 | Instrumente im Rahmen bekommen keine Werte (keine Brückennachricht dafür). | `bruecke.js:11` (`OPS = ['api', 'shell']`) |
| B13 | Das Werkzeug „Module“ zeigt Module, Vertrauen und Abgewiesene (`/api/uix/modules`, `uix_server.py:487`). Was es im Einzelnen anzeigt, wurde nicht gelesen. | – |

## 2. Anforderungen

### 2.1 Antrag im Manifest

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM3-01 | Nicht-CORE-Apps mit `needs.ui >= 1.1` tragen `rechte:` mit den Schlüsseln `lesen` (Objekttypen), `verben` (`typ.verb`), `ereignisse` (Namen), `zelle` (`nein`/`text`), `ablage` (Größe, Vorgabe `0`), `dienst` (`nein`/`host`/`microvm`, nur `kind: dienst`, AM4). Unbekannte Schlüssel → `rechte_unbekannt:<schlüssel>`. | Schema-Test |
| AM3-02 | Für diese Apps wird `api:` **aus `rechte` abgeleitet**: `lesen` → `POST /api/objects`, `verben` → `POST /api/actions`, `ablage` → die beiden Ablage-Routen (`gateway.py:49`). Eigene `api:`-Einträge sind nur noch als `route:`-Übergang erlaubt (AM3-03). | Test |
| AM3-03 | **Übergang**: Apps mit `needs.ui` 1.0 behalten `api:`; jede Route wird als Fähigkeit `route:<METHOD pfad>` geführt (GET = Schutzstufe A nur wenn nicht auf der Sperrliste AM0-03, sonst unzulässig; alles andere B). | Test |
| AM3-04 | `emits` muss bei Nicht-CORE-Apps leer sein; sonst Warnung `emits_im_rahmen_wirkungslos`. | Schema-Test |

### 2.2 Gewährung und Aktivierung

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM3-05 | Gewährungen stehen in **einer** Datei des Kerns: `local_config/apps/berechtigung.yaml` (Vorbehalt `**/local_config/**`), je App `{manifest_sha256, aktiv, gewaehrt: {…}}`. Weder Einbau noch Gewährung schreiben in das Manifest der App (Ersatz für B2/B3). Das Vertrauen nach dem Einbau (`COMMUNITY`) steht ebenfalls dort und nicht mehr im Manifest. | Test: Manifest-Hash vor und nach Einbau/Gewährung gleich |
| AM3-06 | **Wirksam** ist `beantragt ∩ gewährt ∩ Obergrenze(Vertrauen)` (Konzept §5.2). Beantragt die App mehr als gewährt, wird sie **nicht geladen** (`rechte_nicht_gewaehrt:<liste>`), sie wird nicht gekürzt. Weicht `manifest_sha256` ab, gilt keine Gewährung (`gewaehrung_veraltet`). | Test |
| AM3-07 | Mit dem Einbau gewährt sind nur Fähigkeiten der **Schutzstufe A**; sie stehen im Einbau-Gate einzeln mit Wirkungsklasse. Fähigkeiten der Stufe B brauchen einen **Antrag** `POST /api/apps/rechte {id, faehigkeiten}` → Gate `grant_app_rights` (AM0-08) mit Klartext je Fähigkeit, gebunden an `manifest_sha256` und die Liste. Anwenden prüft beides erneut (Muster `trust_apply`). Stufe C wird abgewiesen, ohne Gate. | Test |
| AM3-08 | **Aktivierung**: Nach dem Einbau ist eine App `aktiv: false`. `POST /api/apps/aktivieren {id}` setzt `true` – kein Gate, aber nur aus der Grundfunktion „Module und Berechtigungen“ (Kopf `X-SEDRA-Tool: modules` oder Shell-Seite, nie aus einem Rahmen, nie über Client-Token `cli`/`mcp`), Audit `UIX_APP_ACTIVATED`. Inaktive Apps erscheinen nicht in Orten, Zellen, Start-Menü; ihre Routen antworten 403 `app_inaktiv`. | Test je Weg |
| AM3-09 | **Entzug und Deaktivieren** wirken sofort (nächste Anfrage 403, Brücke meldet den Rahmen ab, Reiter schließen mit Hinweis), ohne Gate, mit Audit. | Test |
| AM3-10 | Das Modell (Chat-Werkzeuge, Harness) kann Rechte **beantragen** (ein Antrag im Posteingang), aber weder gewähren noch aktivieren. | Test: kein Chat-Werkzeug ruft `grant`/`aktivieren` |

### 2.3 Verben und Lesen am Server prüfen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM3-11 | Für Anfragen mit `X-SEDRA-Tool` einer Nicht-CORE-App prüft der Server vor `desk/objects.py`/`desk/actions.py` den Körper: `POST /api/objects` nur für gewährte `lesen`-Typen (`typ_nicht_gewaehrt`), `POST /api/actions` nur für gewährte `verben` (`verb_nicht_gewaehrt`). 403, Audit `UIX_APP_VERB_DENIED`. Das Gate des Verbs selbst bleibt unverändert. | Test |
| AM3-12 | Eigene Objekttypen einer App (`own_types`, `gateway.py:122`) gelten als `lesen` Stufe A für diese App. | Test |

### 2.4 Update

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM3-13 | `install_request` mit einer `id`, die als eingebaute App existiert, ist ein **Update**, wenn `version` größer ist; gleich oder kleiner → `update_version_nicht_hoeher`. | Test |
| AM3-14 | Das Update-Gate zeigt: Datei-Diff (neu, entfernt, geändert mit Größe und Hash; Text-Diff für Dateien ≤ 50 KB), **Rechte-Diff** (neu beantragt, entfallen) mit Wirkungsklasse, Funde der Durchsicht. Neue Stufe-B-Rechte sind Teil desselben Gates (eine Entscheidung über genau diese Liste, Schlüssel = Hash, wie `update_anwenden.rechte_schluessel`). | Test |
| AM3-15 | Bis zur Freigabe läuft die alte Fassung; Anwenden ersetzt den Ordner atomar, schreibt Herkunft (AM0-02) und Gewährung neu, behält `aktiv`. Ablehnen ändert nichts. Rückweg: die alte Fassung bleibt als `<id>.vorher` bis zum nächsten Update. | Test |

### 2.5 Ereignisse

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM3-16 | Zwei Klassen (Konzept §9). `öffentlich`: `system.state`, `model.changed`, `desk.resync`, `tools.refresh`, `slot.changed`. `inhalt`: alle anderen. | Test der Liste in `ui/bus.js` und `desk/gateway.py` |
| AM3-17 | Nicht-CORE-Apps: `öffentlich` ist Stufe A; `inhalt` ist Stufe B und wird **gefiltert**: Die Brücke reicht nur Schlüssel einer festen Liste je Ereignis weiter (Vorschlag: `decision.pending`/`decision.answered` → `{id, kind, way?}`; `task.changed` → `{id, phase}`; `object.open` → `{type, id}`; `agent.changed`/`issue.changed` → `{id}`; `budget.warning` → `{agent_id, stufe}`; `live.line`, `talk.context`, `desk.error`, `harness.*` → **nie**). | Node-Test der Filterfunktion |
| AM3-18 | Der Filter sitzt in der Brücke (`ui/bruecke.js`, Vertragscode), nicht in der App und nicht in der Shell. | Code-Prüfung, Test |

### 2.6 Darstellung fremder Apps

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM3-19 | **Fremd-Kennzeichen**: Der Lader legt um jeden Rahmen einen Rand mit Kopfzeile „<Name> · fremde App · <Vertrauen>“, gezeichnet in der Seite, außerhalb des Rahmens, mit Design-Tokens. Gilt in jeder Shell. | Browser-Test |
| AM3-20 | `shell.notify` aus einem Rahmen: Text mit Präfix „<Name>: “, höchstens 200 Zeichen, Steuerzeichen entfernt, Ton nur `note`, kein Blinken, keine Browser-Benachrichtigung, höchstens 1 Hinweis je 5 s je App. | Node-Test |
| AM3-21 | **Design im Rahmen**: Die Rahmenseite lädt `ui/tokens.css` (nur Variablen, kein Shell-CSS), damit fremde Apps die Farben der Oberfläche nutzen können (B: `PLAN_STUFE_C` §10 „nur das Werkzeug-CSS“). | Test der Rahmenseite |
| AM3-22 | **Tastatur**: Esc im Rahmen gibt den Fokus an die Shell zurück (Brückennachricht `fokus_zurueck`); Tastenkürzel der Shell wirken nicht in den Rahmen hinein. | Browser-Test mit Tastatur |

### 2.7 Fremde Leistenzellen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM3-23 | Eine Nicht-CORE-App mit `kind: instrument`, `zelle` im Manifest und gewährtem `zelle: text` liefert ihren Wert über eine neue Brückennachricht `zelle {wert, hinweis, ton}` (`wert` ≤ 24, `hinweis` ≤ 80 Zeichen, `ton` ∈ `ok|warn|off`; `bad` ist dem Kern vorbehalten), höchstens 1 je Sekunde. | Node-Test |
| AM3-24 | Die Shell zeichnet die Zelle selbst (Datenzelle, AM1-10) mit Kennzeichen „fremd“; ein Klick öffnet nur den Ort der App. In der Harness steht die Zelle nur, wenn der Captain sie in `leiste.json` aufnimmt. Der Rahmen des Instruments läuft unsichtbar (außerhalb des sichtbaren Bereichs, nicht `display:none`, damit Zeitgeber laufen). | Browser-Test |

### 2.8 Berechtigungsseite und Verzeichnis

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM3-25 | Die Grundfunktion „Module und Berechtigungen“ (Werkzeug `modules`, in der Harness zusätzlich Einstellungen → System → Module) zeigt je App: Herkunft (Quelle, Commit, Einbaudatum), Vertrauen, Aktivierung, je Fähigkeit beantragt/gewährt mit **Wirkungsklasse** und Schutzstufe, Ablage (Größe, Export), letzte 20 Audit-Einträge der App. Handlungen: Aktivieren, Deaktivieren, Recht beantragen, Recht entziehen, Update vorlegen, Entfernen (mit Wahl: Ablage behalten/löschen). | uix_check |
| AM3-26 | Export: `GET /api/apps/verzeichnis` liefert alle Apps mit Gewährungen als JSON (für den Nachweis, auch AM7). Nur Shell-Seite, nicht für Rahmen. | Test |
| AM3-27 | Audit-Ereignisse: bestehend und weiter genutzt `UIX_MODULE_INSTALLED` (`uix_server.py:475`), `UIX_MODULE_REMOVED` (`:1353`), `UIX_MODULE_SCAFFOLDED` (`:659`), `UIX_TOOL_DENIED`, `UIX_MODULE_WRITE_ROUTES_GRANTED` (Übergang); neu `UIX_APP_ACTIVATED`, `UIX_APP_DEACTIVATED`, `UIX_APP_RIGHTS_REQUESTED`, `UIX_APP_RIGHTS_GRANTED`, `UIX_APP_RIGHTS_REVOKED`, `UIX_APP_UPDATE_REQUESTED`, `UIX_APP_UPDATED`, `UIX_APP_VERB_DENIED`, `UIX_APP_MIGRATED`. Nie Inhalte, nur IDs, Listen, Hashes. | Test |

### 2.9 Vertrauen beim Einbau festlegen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM3-29 | Das Vertrauen nach dem Einbau setzt der Kern, nie das Manifest: Vorgabe `COMMUNITY`. `GUPPI_BUILT` nur, wenn die Quelle ein von SEDRA gebauter, abgenommener Kandidat ist und das Gate den Nachweis trägt (Mission/Kandidat mit bestandenem verstecktem Test, Vertrag §7.1–7.3). Heute vergibt kein Code-Pfad `GUPPI_BUILT` (Konzept F15). Welche Obergrenze `GUPPI_BUILT` gegenüber `COMMUNITY` hat (z. B. Dienst auf dem Host, AM4-07), steht in der Berechtigung. | Test: Einbau ohne Nachweis → COMMUNITY; mit gültigem Nachweis → GUPPI_BUILT |
| AM3-30 | `CAPTAIN` bleibt den Modulen vorbehalten, die der Captain selbst ablegt oder aus der Vorlage anlegt; über das Einbau-Gate entsteht nie `CAPTAIN`. | Test |

### 2.10 Werkseinstellung

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM3-28 | Werkseinstellung für `COMMUNITY` nach dem Einbau: aus; gewährt nur Stufe A (`lesen` eigener Typen, `ereignisse` der Klasse `öffentlich`, `ablage` bis 1 MB, Ort im Start-Menü). Alles andere auf Antrag. Endgültig nach AM3-E1. | Test |

## 3. Entwurf

**Datei `local_config/apps/berechtigung.yaml`** (Beispiel):
```yaml
schema: 1
apps:
  rechnung:
    vertrauen: COMMUNITY
    manifest_sha256: 9f2c…
    aktiv: true
    gewaehrt:
      lesen: [rechnung]
      verben: [rechnung.ablegen]          # Stufe B, Gate M-… am 2026-11-20
      ereignisse: [system.state]
      zelle: text
      ablage: 1MB
```
- Lesen in `desk/gateway.py` (`Gateway.manifest`), Schreiben nur im Hub (`uix_server.py`) nach Gate oder Aktivierungsklick, atomar.
- **Übergang**: Module, die heute über `trust_apply` `CAPTAIN` wurden, werden einmalig übernommen: Vertrauen `CAPTAIN` und alle ihre Routen als gewährte `route:`-Fähigkeiten, `aktiv: true`. Audit `UIX_APP_MIGRATED`. Danach schreibt `trust_apply` nicht mehr ins Manifest; die Route `/api/uix/trust` bleibt als Hülle auf `/api/apps/rechte` (ein Jahr, wie Vertrag §10 Grundsatz 1 für alte Routen).
- **Brücke**: `OPS` um `zelle`, `fokus_zurueck` erweitern; Filterfunktion `nutzlastFiltern(name, daten)` rein und getestet.
- **Wirkungsklassen der Verben**: Jedes Desk-Verb muss eine Wirkungsklasse tragen, damit die Berechtigungsseite sie zeigen kann. Woher sie kommt (Feld in `desk/kinds.py` `Kind.verbs`?), ist offen, weil `desk/kinds.py` nur teilweise und `desk/actions.py` nicht gelesen wurden (G2).

## 4. Tests und Abnahme

Server: `tests/test_apps_am3_{schema,gewaehrung,aktivierung,verben,update,verzeichnis}.py`. Node: Brückenfilter, `notify`-Filter, `zelle`-Nachricht. Browser: Fremd-Kennzeichen, Tastatur, fremde Zelle in Cockpit und Harness, Deaktivieren schließt den Reiter. Angriffs-Probe (AM0-10) zusätzlich: Verb ohne Gewährung, Ereignis der Klasse `inhalt` ohne Gewährung.
Abnahme am PC: eine Test-App einbauen (aus), aktivieren, ein Verb beantragen (Gate), entziehen; ein Update mit neuem Recht vorlegen und ablehnen.

## 5. Rückfall

Schalter `app_berechtigung` (Standard an nach Abnahme). Aus = Verhalten wie nach AM0 (Routenlisten, sofort aktiv). Die Datei `berechtigung.yaml` wird dabei nicht gelöscht.

## 6. Abgrenzung

Keine Rollen (AM7). Keine Dienste (AM4). Kein Senden von App-Ereignissen. Keine Rechte für CORE-Apps (Paket, Review); ihre Routen werden auf der Seite nur angezeigt.

## 7. Risiken

- Die Umstellung von Routen auf Fähigkeiten berührt jede Anfrage mit `X-SEDRA-Tool` (Körperprüfung). Fehler zeigen sich als 403 in Apps; das Audit nennt sie.
- „Mehr beantragt als gewährt → lädt nicht“ ist streng; ein Update ohne neue Rechte ist davon nicht betroffen, ein Update mit neuen Rechten nur, wenn das Gate abgelehnt wird (dann bleibt die alte Fassung).
- Ein unsichtbarer Rahmen je fremder Zelle kostet Speicher; deshalb nur, wenn die Zelle in der Leiste steht.

## 8. Entscheidungen des Captains

**Entschieden vom Captain am 03.11.2026: alle Vorschläge dieser Tabelle übernommen.**

| Nr | Frage | Vorschlag |
|---|---|---|
| AM3-E1 | Werkseinstellung (AM3-28) so? | ja |
| AM3-E2 | Darf eine App ohne Gate aktiviert werden (nur Klick)? | ja, weil der Einbau schon ein Gate war; im Unternehmen entscheidet die Richtlinie (AM7) |
| AM3-E3 | Größe der Ablage je App | 1 MB Vorgabe, mehr auf Antrag |
| AM3-E4 | Alte Fassung nach Update behalten? | ja, eine Fassung |

## 9. Berechtigungen vorab

Schreiben in `desk/{gateway.py, install.py}`, `uix_server.py` (neue Routen `/api/apps/*`, Körperprüfung, Übergang), `ui/{bruecke.js, rahmen.js, loader.js, bus.js}`, `uix/tools/modules/*`, Harness-Einstellungen (Seite Module), Tests. Keine Änderung an Guard-Logik (Regeln aus AM0-08).

## 10. Nächste Gates

G1 → G2 (Wirkungsklassen der Desk-Verben nach Lesen von `desk/actions.py`/`gated.py`; Text-Diff-Darstellung; Liste der gefilterten Schlüssel endgültig) → G3 → G4.
