# Spec: Delegation im Gespräch (mehrere Agenten gleichzeitig an einer Aufgabe) – Entwurf v1

Stand: 15.11.2026. Entwurf für G1 und G2. Es ist noch nichts gebaut. Gehört zu `SEDRA-UIX-3D-01`, Baustein D aus
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

## 4. Aufgaben (für G3, Reihenfolge)

1. `harness/team.py` rein: Grenzen, Slot-Vergabe, Zustandsmodell, Ergebnistext. Mit Tests ohne Modell.
2. Sitzungskopf `eltern`, `delegation`, `rolle`; Sitzungsliste gibt sie aus.
3. `werkzeug_team.py` und Einhängen in Kiste und Katalog (`WIRKUNGSKLASSE`, `NAMEN`, Vorlage `manager.yaml` und eine neue Vorlage oder Freischaltung je Projekt).
4. Routen und Bus-Ereignis.
5. Oberfläche: Delegations-Karte, Seitenleiste, Taskleiste. Sichtprüfung.
6. Echter Lauf am PC mit Profil `team-35b` (3 Slots): eine Aufgabe, drei Helfer, ein Schreibvorgang mit Karte.

## 5. Offene Punkte für den Captain

1. **Welche Sitzungen dürfen delegieren?** Vorschlag: nur Sitzungen mit einer Vorlage, die `team_verteilen` nennt (zuerst `manager`), nicht jede Sitzung.
2. **Zeitlimit je Helfer:** Vorschlag 10 Minuten, einstellbar.
3. **Cloud-Helfer:** in dieser Spec nicht enthalten; `auftraege_verteilen` bleibt daneben bestehen.
4. **Wer baut?** Teile 1 und 2 eignen sich für einen Bau durch SEDRA mit versteckten Tests; 3 bis 5 sind Harness-Arbeit des Koordinators.

## 6. Nicht geprüft

Ob drei gleichzeitige Helfer mit dem Profil `team-35b` auf der Grafikkarte des Captains flüssig laufen, ist nicht gemessen. Die
Slot-Vergabe über `id_slot` ist bisher nur für Sitzungen belegt, die der Captain selbst führt.
