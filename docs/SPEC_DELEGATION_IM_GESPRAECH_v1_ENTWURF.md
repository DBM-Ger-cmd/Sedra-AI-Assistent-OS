# Spec: Delegation im Gespräch (mehrere Agenten gleichzeitig an einer Aufgabe) – Entwurf v1

Stand: 15.11.2026. **G1 (Anforderungen) und G2 (Design) vom Captain freigegeben am 15.11.2026 im Chat des Koordinators.** **G3 (Aufgaben) freigegeben am 15.11.2026 („G3 frei, bauen“), mit den Vorschlägen aus Abschnitt 5.** T1 bis T6 sind gebaut (Abschnitt 7), T7 (Abnahme am PC) steht aus. Gehört zu `SEDRA-UIX-3D-01`, Baustein D aus
`docs/AUFTRAG_UIX_NAECHSTE_STUFE_2026-11-15.md`.

## 0. Entscheidungen des Captains (15.11.2026)

| Frage | Entscheidung |
|---|---|
| Grundlage | Neu: Delegation im Gespräch. Nicht die Orchestrierung (`orchestra`, ausgeschaltet), nicht nur die Cloud. |
| Rechte der Helfer | Schreiben mit Karte: jede Änderung eines Helfers kommt als eigene Freigabe-Karte zum Captain. |
| Umfang | Nur die Harness-Shell (One Sedra). |

## 1. Befund: was es heute gibt

- **`auftraege_verteilen`** (`manager/werkzeuge.py`, `manager/kanal.py`, `harness/werkzeuge.py`): bis zu 5 Teilaufträge an die
  Cloud, **nacheinander**, Ergebnis erst am Ende als ein Text, eine Karte für den ganzen Aufruf. Keine Ereignisse je Auftrag.
- **Feste Slots**: eine Sitzung lässt sich an einen Platz des Modellservers binden (`sitzung.slot_waehlen`, `id_slot` in
  `schleife.py`; Pool: Manager 0, Angestellte 1 und 2). Jede Sitzung führt der Captain bisher selbst.
- **Jede Sitzung antwortet in einem eigenen Faden** mit eigener Werkzeug-Kiste (`api._starten`, `freigabe.Kiste`); eine Karte
  trägt die Kennung ihrer Sitzung. Mehrere Sitzungen können also schon gleichzeitig antworten.
- **`orchestra`**: dauerhaftes Team mit Aufgabenbrett und Herzschlag, gebaut, beim Captain ausgeschaltet. Bleibt unberührt.

Folgerung: Es fehlt nur das Stück, das aus einer Sitzung heraus Helfer-Sitzungen anlegt, sie gleichzeitig arbeiten lässt und
die Ergebnisse zurückbringt. Sitzungen, Slots, Karten und Ströme sind vorhanden und werden wiederverwendet.

## 2. Anforderungen (für G1)

| ID | Anforderung | Abnahme |
|---|---|---|
| DG-01 | WENN das Modell der Hauptsitzung `team_verteilen` mit 1 bis 3 Teilaufträgen ruft, DANN SOLL der Server je Teilauftrag eine Helfer-Sitzung anlegen und sie gleichzeitig antworten lassen. | Test: 3 Aufträge, 3 Helfer-Sitzungen, Antworten überlappen zeitlich. |
| DG-02 | Eine Helfer-Sitzung SOLL an die Hauptsitzung gebunden sein (`eltern`), dasselbe Projekt haben und in der Seitenleiste unter ihr stehen, nicht als eigener Chat. | Test der Sitzungsliste; Sichtprüfung. |
| DG-03 | WENN das Profil des Modellservers weniger freie Slots hat als Aufträge, DANN SOLLEN die übrigen Aufträge warten und nacheinander laufen; kein Auftrag fällt weg. | Test mit 1 Slot und 3 Aufträgen: 3 Ergebnisse. |
| DG-04 | Ein Helfer SOLL dieselben Regeln haben wie eine Sitzung des Projekts: Lesen frei nach Katalog; was schreibt oder ausführt, legt eine Freigabe-Karte vor. Die Karte nennt Helfer und Auftrag. | Test: Schreibversuch eines Helfers erzeugt eine Karte mit `sitzung_id` des Helfers; ohne Freigabe keine Datei. |
| DG-05 | Ein Helfer SOLL selbst nicht delegieren können (`team_verteilen` und `auftraege_verteilen` fehlen in seiner Kiste). | Test der Kiste. |
| DG-06 | Der Aufruf `team_verteilen` selbst SOLL keine Karte brauchen, solange der Text den Rechner nicht verlässt; er zählt aber als Werkzeugaufruf im Verlauf und im Audit. | Audit-Eintrag `HARNESS_TEAM_START` und `HARNESS_TEAM_ENDE`. |
| DG-07 | WENN alle Helfer geendet haben, DANN SOLL die Hauptsitzung je Auftrag den Schlusstext des Helfers als Werkzeug-Ergebnis bekommen, gekennzeichnet als ungeprüfter Text. | Test: Ergebnis enthält je Auftrag Rolle, Ende, Text. |
| DG-08 | WENN ein Helfer scheitert oder sein Zeitlimit überschreitet, DANN SOLL das im Ergebnis mit Grund stehen; die anderen laufen weiter. | Test mit einem erzwungenen Fehler. |
| DG-09 | Der Captain SOLL einen Helfer anhalten können und alle Helfer einer Delegation zusammen. Angehalten heißt: der laufende Zug endet, das Ergebnis lautet „angehalten“. | Test der Route; Sichtprüfung. |
| DG-10 | Die Oberfläche SOLL im Gespräch eine Delegations-Karte zeigen: je Helfer eine Zeile mit Rolle, Auftrag in einem Satz, Zustand (wartet, läuft, wartet auf Freigabe, fertig, gescheitert, angehalten), Zügen, Token und Dauer; aufklappbar zum Verlauf des Helfers. | Sichtprüfung; node-Test der reinen Zeilen-Funktion. |
| DG-11 | Die Zeile eines Helfers, der auf eine Freigabe wartet, SOLL die Karte direkt öffnen. Entschieden wird nur auf der Karte, nie in der Zeile. | Sichtprüfung. |
| DG-12 | Die Taskleiste SOLL zeigen, wie viele Helfer laufen; der Avatar meldet „Freigabe wartet“ wie bisher. | Sichtprüfung. |
| DG-13 | Grenzen: höchstens 3 Helfer je Delegation, höchstens eine laufende Delegation je Hauptsitzung, Zeitlimit je Helfer (Vorgabe 10 Minuten), Auftragstext höchstens 12000 Zeichen. | Tests der Grenzen. |
| DG-15 | WENN zwei Helfer einer Delegation dieselbe Datei ändern wollen, DANN SOLL die zweite Karte das sichtbar sagen. | Test: zwei Vorlagen für dieselbe Datei, zweite Karte trägt den Hinweis. |
| DG-14 | Nichts aus dieser Spec SOLL ein neues Recht schaffen: kein neuer Freigabe-Weg, kein Schreiben ohne Karte, keine Änderung am Guard. | Review; `test_core_boundary_src` bleibt grün. |

## 3. Design (für G2)

### 3.1 Werkzeug `team_verteilen`
Aufruf des Modells: `{auftraege: [{rolle, text}]}`. `rolle` ist ein kurzer Name für die Anzeige (zum Beispiel „Prüfer“) oder die
Kennung einer Vorlage (`pruefer`, `bauagent`); eine Vorlage bringt ihre Arbeitsanweisung und ihre Werkzeugliste mit.
Ablage: eigene Datei `harness/werkzeug_team.py` (unter 400 Zeilen), in die Kiste gereicht wie `cloud_verteilen`.

### 3.2 Ablauf im Server (`harness/api.py` reicht nur durch, die Arbeit liegt in `harness/team.py`)
1. Prüfen der Grenzen (DG-13). Audit `HARNESS_TEAM_START` mit Delegations-ID `T-…`.
2. Je Auftrag eine Sitzung anlegen: Kopf mit `eltern: <Hauptsitzung>`, `delegation: T-…`, `rolle`, gleiches Projekt, gleiche
   Vorlage-Regeln; Slot aus den freien Plätzen des laufenden Profils (Hauptsitzung behält ihren Slot).
3. Den Auftrag als erste Nachricht über denselben Weg wie `nachricht()` geben. Damit gelten Kiste, Katalog, Karten, Strom,
   Token-Zählung und Audit ohne Sonderweg.
4. Warten, bis jeder Helfer geendet hat (Ereignis `harness.antwort` mit `fertig`), oder Zeitlimit, oder angehalten. Eine offene
   Karte eines Helfers hält nur diesen Helfer an; das Zeitlimit zählt in dieser Zeit nicht weiter.
5. Ergebnis je Auftrag zusammenstellen (DG-07, DG-08). Audit `HARNESS_TEAM_ENDE`.

Der Aufruf blockiert den Zug der Hauptsitzung, so wie heute ein Lauf. Die Hauptsitzung zeigt währenddessen die Delegations-Karte.

### 3.3 Daten für die Oberfläche
- Ereignis `harness.team` auf dem Bus: `{delegation, eltern, helfer: [{sitzung_id, rolle, auftrag_kurz, zustand, zuege, token, sekunden, karte_id|null}]}` bei jedem Zustandswechsel.
- `GET /api/harness/team/<delegation>` liefert denselben Stand (für Neuladen der Seite).
- `POST /api/harness/team/<delegation>/stopp` mit `{sitzung_id|null}` (DG-09).
Beide Routen liegen unter dem vorhandenen Muster `/api/harness/*` der Shell.

### 3.4 Oberfläche (`shells/harness/delegation.js`, `delegation.css`)
- Delegations-Karte als Eintrag im Verlauf der Hauptsitzung (wie die Zeile eines Werkzeugaufrufs, aber aufgeklappt).
- Reine Funktion `zeilen(stand)` → Anzeigezeilen, unter node geprüft.
- Helfer-Sitzungen in der Seitenleiste eingerückt unter der Hauptsitzung, zugeklappt, wenn fertig.
- Zelle „Team“ in der Taskleiste nur, solange Helfer laufen.

### 3.5 Fehlerfälle
| Fall | Verhalten |
|---|---|
| Kein Modell geladen | `team_verteilen` antwortet mit Grund, legt nichts an. |
| Lauf belegt das Modell | wie `nachricht()`: Grund zurück, nichts angelegt. |
| Server-Neustart während einer Delegation | Helfer-Sitzungen bleiben als Sitzungen erhalten; die Delegation gilt als abgebrochen, das steht im Verlauf. |
| Zwei Helfer wollen dieselbe Datei ändern | Heute nicht abgesichert: `datei_aendern` scheitert nur, wenn die Stelle `alt` nicht mehr genau einmal vorkommt; `datei_schreiben` würde die Fassung des anderen ersetzen. Neu zu bauen: `team.py` merkt je Delegation, welche Datei ein Helfer zur Änderung vorgelegt hat; eine zweite Karte für dieselbe Datei trägt den Hinweis „auch von Helfer X geändert“ (DG-15). |

## 4. Aufgaben (für G3)

Jede Aufgabe endet mit grünen Tests und einem eigenen Commit auf dem Branch `uix-3d-naechste-stufe`. Nach `main` geht nichts ohne
eigenes Ja. Kein Schritt ändert `core/` oder den Guard.

| Nr | Aufgabe | Dateien | Deckt | Fertig, wenn |
|---|---|---|---|---|
| T1 | Kern, rein und ohne Server: Aufträge prüfen (Anzahl, Länge, Rolle), Slots vergeben (freie Plätze, Rest in die Warteschlange), Zustandsmodell je Helfer, Ergebnistext, Merkliste „Datei von Helfer X vorgelegt“. | `harness/team.py` (neu), `tests/test_harness_team.py` (neu) | DG-03, DG-07, DG-08, DG-13, DG-15 (Kern) | Tests ohne Modell grün |
| T2 | Sitzungskopf mit `eltern`, `delegation`, `rolle`; die Sitzungsliste gibt die drei Felder aus. Alte Sitzungen ohne die Felder bleiben lesbar. | `harness/sitzung.py`, Test dazu | DG-02 | Test: anlegen, laden, Liste |
| T3 | Ablauf im Server: Helfer-Sitzungen anlegen, Auftrag über den Weg von `nachricht()` geben, auf das Ende warten, Zeitlimit, Anhalten, Audit. Die Arbeit liegt in einer eigenen Datei, `api.py` reicht nur durch (sie hat schon 1920 Zeilen). | `harness/team_lauf.py` (neu), `harness/api.py` (Durchreichen, Routen `team/<T-…>` und `…/stopp`), Test mit Schein-Modell | DG-01, DG-06, DG-08, DG-09, DG-14 | Test: 3 Aufträge überlappen; Stopp wirkt |
| T4 | Werkzeug `team_verteilen` in der Kiste, Wirkungsklasse, Namensliste; in der Kiste eines Helfers fehlen `team_verteilen` und `auftraege_verteilen`. Freischaltung über die Vorlage. | `harness/werkzeug_team.py` (neu), `harness/werkzeuge.py`, `config/harness_vorlagen/manager.yaml`, Tests | DG-04, DG-05 | Test: Schreibversuch eines Helfers erzeugt Karte mit seiner `sitzung_id` |
| T5 | Hinweis auf der zweiten Karte, wenn zwei Helfer dieselbe Datei vorlegen. | `harness/team_lauf.py`, Kartentext, Test | DG-15 | Test mit zwei Vorlagen |
| T6 | Oberfläche: Delegations-Karte im Verlauf, reine Funktion `zeilen(stand)`, Helfer eingerückt in der Seitenleiste, Zelle „Team“ in der Taskleiste, Texte DE/EN. | `shells/harness/delegation.js`, `delegation.css`, `strings_delegation.js` (neu), `seitenleiste.js`, `taskleiste.js`, `shell.yaml`, Tests | DG-10, DG-11, DG-12 | node-Test, Vertragstest, Sichtprüfung im Wegwerf-Projekt |
| T7 | Abnahme am PC: Profil `team-35b`, eine Aufgabe, drei Helfer, ein Schreibvorgang mit Karte, einmal Anhalten. Messung Token pro Sekunde je Helfer. | keine | alle | Captain sieht es am PC |

Reihenfolge: T1, T2, T3, T4, T5, T6, T7. T6 kann nach T3 beginnen. T7 macht der Captain mit dem Koordinator.

Nicht in dieser Spec: Cloud-Helfer, Helfer, die selbst delegieren, mehr als drei Helfer, ein dauerhaftes Team (`orchestra`).

## 5. Entschiedene Punkte (Captain 15.11.2026: Vorschläge gelten)

1. **Welche Sitzungen dürfen delegieren?** Vorschlag: nur Sitzungen mit einer Vorlage, die `team_verteilen` nennt (zuerst `manager`), nicht jede Sitzung.
2. **Zeitlimit je Helfer:** Vorschlag 10 Minuten, einstellbar.
3. **Cloud-Helfer:** in dieser Spec nicht enthalten; `auftraege_verteilen` bleibt daneben bestehen.
4. **Wer baut?** Teile 1 und 2 eignen sich für einen Bau durch SEDRA mit versteckten Tests; 3 bis 5 sind Harness-Arbeit des Koordinators.

## 7. Stand des Baus (15.11.2026)

| Aufgabe | Stand | Wo |
|---|---|---|
| T1 Kern | gebaut | `runtime/src/sedra_runtime/harness/team.py`, `tests/test_harness_team.py` |
| T2 Sitzungskopf | gebaut | `harness/sitzung.py`, `tests/test_harness_sitzung.py` |
| T3 Ablauf, Routen, Anhalten | gebaut | `harness/team_lauf.py`, `harness/api.py`, `harness/strom.py` (`letzte_in`), `tests/test_harness_team_lauf.py`, `tests/test_uix_harness_team.py` |
| T4 Werkzeug, Helfer-Kiste | gebaut | `harness/werkzeug_team.py`, `harness/werkzeuge.py`, `harness/katalog.py`, `config/harness_vorlagen/manager.yaml`, `tests/test_harness_team_werkzeug.py` |
| T5 Hinweis bei doppelter Datei | gebaut | `team_lauf.datei_hinweis`, `werkzeuge.py` (Vorschau der Karte) |
| T6 Oberfläche | gebaut | `uix/shells/harness/delegation.js`, `delegation.css`, `strings_delegation.js`, `seitenleiste.js`, `seite.js`, `shell.js`, `ui/bus.js` (Ereignis `harness.team`), `tests/test_uix_delegation.py` |
| T7 Abnahme am PC | zum Teil erledigt (15.11.2026, 21:23 bis 21:26) | Abschnitt 8 |

Abweichungen vom Entwurf und Befunde aus dem Bau:

1. **Drei Helfer zugleich brauchen vier Plätze.** Die Hauptsitzung behält ihren Platz (ihr Zwischenspeicher bleibt warm). Mit dem Profil
   `team-35b` (3 Plätze) arbeiten also zwei Helfer gleichzeitig, der dritte wartet und kommt danach dran. Bei einem Platz laufen alle nacheinander.
2. **Rolle ist nur ein Name.** Eine Vorlage über die Rolle zu wählen (§3.1) ist nicht gebaut; ein Helfer hat die Werkzeuge einer Sitzung ohne
   Vorlage, ohne Läufe, ohne `team_verteilen` und ohne `auftraege_verteilen`.
3. **Karte nach dem Neuladen.** Eine laufende Delegation erscheint nach dem Neuladen der Seite wieder (GET `/api/harness/team`), eine beendete
   nicht; die Helfer-Sitzungen stehen weiter in der Seitenleiste. Ist der Reiter der Hauptsitzung zu, zeigt nur die Taskleiste „Team a/n“.
4. **Zeitlimit** ist 600 s fest im Code (`team.ZEITLIMIT_S`), noch nicht in den Vorgaben einstellbar.
5. **Wirkungsklasse** von `team_verteilen` ist `read_only`: der Aufruf selbst ändert nichts; was ein Helfer ändert, hat seine eigene Karte.
6. **Nebenbefund, nicht geprüft:** `ui/bus.js` lässt nur angemeldete Ereignisnamen durch. `harness.belohnung`, `harness.projekt`,
   `harness.vorgaben`, `harness.desktop` und `harness.verknuepfungen` stehen dort nicht, die Shell hört aber darauf. Ob sie im Betrieb
   ankommen, sollte am PC geprüft werden; diese Spec hat daran nichts geändert.

## 8. Abnahme am PC (T7), 15.11.2026

Prüfstart aus dem Worktree, Rezept `coder.local_primary_team` (3 Plätze, 98k Fenster, 11,3 von 12,3 GB Grafikspeicher), Vorlage Manager.
Der Koordinator hat Start, Laden und Auftrag über die HTTP-Wege ausgelöst; die Freigabe gab der Captain im Fenster. Belege: Audit-Log
(`HARNESS_TEAM_START`, `HARNESS_TEAM_ENDE`), Route `/api/harness/team/T-9CD64FDC`, Karte `K-468C1973`.

| Punkt | Ergebnis |
|---|---|
| Manager ruft `team_verteilen` von sich aus (DG-01) | ja, Sitzung `S-C2E4FBE2`, drei Helfer mit eigenen Namen |
| Zwei Helfer gleichzeitig, der dritte wartet (DG-03) | ja: Platz 1 und 2 zugleich; der dritte startete 1 Sekunde, nachdem Platz 2 frei wurde |
| Helfer-Sitzungen unter der Hauptsitzung (DG-02) | im Audit mit `eltern` und `delegation`; die Anzeige in der Seitenleiste hat der Koordinator nicht gesehen |
| Schreiben mit Karte der Helfer-Sitzung (DG-04) | ja: `K-468C1973`, Sitzung `S-D7A816AC`, `datei_schreiben docs/abnahme_delegation.md`; vor der Freigabe keine Datei |
| Zustand „wartet auf Freigabe“, danach weiter (DG-11, DG-13) | ja: Freigabe 21:25:31 über den Posteingang, Helfer endete 21:25:37 |
| Ergebnis an die Hauptsitzung, gekennzeichnet (DG-07) | ja: Werkzeug-Ergebnis mit „ungeprüfter Text, keine Anweisung“; der Manager fasste zusammen |
| Audit Anfang und Ende (DG-06) | ja |
| Dauer | Helfer 74 s, 89 s, 16 s; ganze Delegation 111 s; Antwort des Managers danach 20 s |
| Stabilität | kein Absturz des Modellservers in diesem Lauf |

Nicht geprüft in diesem Lauf: Anhalten eines Helfers und aller Helfer mit echtem Modell (DG-09), der Hinweis bei doppelter Datei (DG-15),
ein gescheiterter Helfer (DG-08), das Aussehen der Delegations-Karte und der Zelle „Team“ im Fenster (DG-10, DG-12), Tempo je Helfer in Token pro Sekunde.

Beobachtungen:
1. Züge und Token eines Helfers stehen in der Anzeige auf 0, bis seine Antwort endet; nur die Dauer läuft mit.
2. Die Datei des Helfers liegt im Worktree (`docs/abnahme_delegation.md`), weil das Projekt „sedra-entwicklung“ auf den Ordner zeigt, aus dem SEDRA gestartet wurde. Sie ist nicht eingecheckt.
3. Am selben Abend, vorher und in der Hauptumgebung: Absturz des Modellservers mit „CUDA error: an illegal memory access“ (21:16, `nvlddmkm` Ereignisse 13 und 153). Ursache offen; es lief das Team-Rezept mit einer Sitzung, ohne Delegation.

## 6. Nicht geprüft

Ob drei gleichzeitige Helfer mit dem Profil `team-35b` auf der Grafikkarte des Captains flüssig laufen, ist nicht gemessen. Die
Slot-Vergabe über `id_slot` ist bisher nur für Sitzungen belegt, die der Captain selbst führt.
