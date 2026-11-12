---
name: n8n-workflow-vorfuehren
description: Einen n8n-Workflow in SEDRA importieren, im Projekt speichern, mit Tabellen und Beispieldatei startbereit machen und die Freigabe-Kette bis zum Ergebnis begleiten (inklusive "Posteingang leer"). Nutzen, wenn ein Workflow vorgeführt oder zum Laufen gebracht werden soll, der Captain ihn nicht findet oder eine Freigabe nicht ankommt.
---

# Workflow vorführen

## 1. Importieren und finden
- Die Datei durch `workflows.vorschau.vorschau` prüfen (Urteil "Läuft in SEDRA als Eigenablauf" erwartet).
- Im **Live-Projekt** speichern (`workspace/SEDRA_OS`, dort liegt `runtime_data/workflows/`), nicht in ein Temp-Projekt: `WorkflowStore(<projekt>).save(doc, None, None, 'Import aus <Datei>')`. Den Namen so setzen, wie der Captain ihn nennt. Der Captain sucht in "Zuletzt gespeichert" (Seite neu laden).
- Ein Workflow, den ich nur in Tests laufen ließ, steht **nicht** in der Oberfläche. Sagen, was gespeichert wurde und unter welchem Namen.

## 2. Startbereit machen
- Tabellen des Workflows (`lokal.bewerten(doc)['liest']`) ins Live-Projekt laden: `Tabellen(<projekt>).importieren(name, text, 'json')`. Beispieldaten nur aus den Dateien des Captains (z. B. `06_Basisdaten_editierbar.json`), nichts erfinden.
- Der Captain lädt die Eingabedatei selbst: Reiter "Ausführungen", Schritt 2.
- Der Server nutzt neuen Python-Code erst nach **Neustart**; JS/CSS genügen nach F5.

## 3. Die Kette (Schritte der Oberfläche)
Daten bereit - Datei wählen - zur Freigabe vorlegen - freigeben und fortsetzen - Ergebnis.
- Vorlegen legt eine Mission an (Phase `CAPTAIN_REVIEW`, Gate `run_sedra_workflow`). Es läuft noch nichts.
- Nach dem Vorlegen öffnet sich ein Freigabe-Fenster in der Seite (Risiken, "Jetzt freigeben"). Der Lauf des Eigenablaufs (`run_sedra_workflow`) ist seit 12.11. ausdrücklich **Klasse N** (`freigabeklasse.KLASSE_N_GATES`): dieses Fenster ist die einzige Bestätigung, danach läuft er sofort. Alle anderen Gates bleiben Klasse H (Windows-Fenster oder `FREIGABE.bat freigeben B-XXXX`). **Nie selbst freigeben**, das ist die Entscheidung des Captains; weitere Aktionen nur mit seiner ausdrücklichen Einstufung in die Liste aufnehmen.
- Wird ein Windows-Fenster mit `bestaetigung_hinfaellig` verworfen, fehlt dem Gate die Bindung (`gate_decision.binding`); "Nein" im Windows-Fenster lehnt das Gate ab und pausiert die Mission (kein "Fortsetzen" mehr, neu vorlegen).
- Danach im Editor "Nach Freigabe fortsetzen". Das Ergebnis erscheint je Knoten aufklappbar.

## Reiter Live
Läufe des Eigenablaufs melden sich selbst (`workflows/live.py`, Prozess `wf-<workflowkennung>`): beim Vorlegen "wartet auf deine Freigabe" (`captain=True`, wird nie "ohne Meldung"), dann jeder Knoten, am Ende fertig oder Fehler. `ids` ordnet Schritt `s<n>` dem Knoten des Workflows zu, `workflow_id` dem gespeicherten Workflow; `desk._live` findet das Diagramm darüber. Eine abgelehnte Freigabe (Mission PAUSED) zeigt die Karte als Fehler. Die Karte hat "Jetzt freigeben …" beziehungsweise "Ergebnis ansehen".

## 4. Wenn der Posteingang leer bleibt
1. Läuft SEDRA überhaupt? `Get-NetTCPConnection -State Listen` (PowerShell) auf den Serverport; Git-Bash-`netstat` zeigt hier oft nichts.
2. Mission suchen: `workspace/SEDRA_OS/runtime_data/missions/M-*.json`, Phase `CAPTAIN_REVIEW` und `human_gates.pending` lesen.
3. Offline prüfen, ob daraus ein Eintrag wird: `sedra_runtime.desk.decisions.collect([mission], [])`. Kommt ein Eintrag heraus, liegt es an der laufenden Oberfläche (alter Stand, Server aus): Neustart, F5, dann Posteingang.
   Bekannte Ursache (behoben 12.11.): `decisions.collect` bekam vom Hub die **kompakte** Mission (`gates`, kein `human_gates`) und verschluckte jedes Mission-Gate; die Freigabe kam nie im Posteingang an. Jetzt liest `_offene_gates` beide Formen. Beim Nachprüfen den Hub-Weg testen (`hub.decisions_view()`), nicht nur `collect` mit einer vollen Mission.
4. Dem Captain Mission, Gate und Kennung nennen und genau sagen, was er klicken muss.

## 5. Kontrastfall für die Vorführung
Einen Einzelpreis in `Auftragspositionen` ändern (Zeile im Editor unter "Tabellen verwalten"), dieselbe Rechnung laufen lassen: Zweig "Klärung erforderlich". Danach den Preis zurücksetzen.

## Ehrlich berichten
Was nur im Skript oder Temp-Projekt lief und was der Captain im echten Projekt sehen wird, getrennt nennen.
