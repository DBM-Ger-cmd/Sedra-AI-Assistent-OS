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
- Freigabe ist **Klasse H**: im Browser "einmal" wählen, dann im Fenster von SEDRA bestätigen oder `FREIGABE.bat liste` und `FREIGABE.bat freigeben B-XXXX`. **Nie selbst freigeben**, das ist die Entscheidung des Captains.
- Danach im Editor "Nach Freigabe fortsetzen". Das Ergebnis erscheint je Knoten aufklappbar.

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
