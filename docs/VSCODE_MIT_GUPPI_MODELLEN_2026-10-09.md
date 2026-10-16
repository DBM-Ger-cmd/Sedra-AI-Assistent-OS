# GUPPIs Modelle in VS Code (Cline und Continue), Testplan vom 2026-10-09

Entscheidung des Captains: GUPPIs lokale Modelle sollen in VS Code arbeiten. VS Code (1.136.2) hat dafür schon die Erweiterungen **Cline** (`saoudrizwan.claude-dev`, ein Agent, der Dateien schreibt und Befehle ausführt, vergleichbar mit unserem DevVM-Coder) und **Continue** (`continue.continue`, Chat, Edit und Apply, bisher auf LM Studio eingestellt, Port 1234). Es wird nichts Neues gebaut: Beide sprechen mit GUPPIs `llama-server` über die OpenAI-kompatible Schnittstelle.

## 1. Modell bereitstellen (Claude startet es, nachdem die laufenden Tests fertig sind)

```
.venv\Scripts\python.exe benchmarks\serve_model.py serve ..\workspace\GUPPI_OS --recipe coder.llama_qwen36 --context 32768 --reasoning off
```

- Es lädt das Modell mit den Rezept-Einstellungen der Bauläufe (Flash Attention aus, `big_window_server`), hält die GPU-Lease und antwortet auf `http://127.0.0.1:8089/v1`. Der Modellname steht in `runtime_data/vscode_serve/endpoint.json`.
- Beenden: die Datei `runtime_data/vscode_serve/STOP` anlegen (oder Strg+C). Dann wird das Modell entladen.
- Während der Sitzung ist die GPU belegt. LM Studio und GUPPI-Bauläufe dürfen in dieser Zeit nicht laufen.

## 2. Cline einrichten (einmalig, in VS Code)

Einstellungen von Cline (Zahnrad): **API Provider = OpenAI Compatible**, **Base URL = `http://127.0.0.1:8089/v1`**, **API Key** = beliebiger Text (zum Beispiel `local`), **Model ID** = der Name aus `endpoint.json`.
In den erweiterten Einstellungen: Kontextfenster **32768**, maximale Ausgabe etwa **4096 bis 8192** Token (größere Antworten werden auch bei uns abgeschnitten, siehe Befund `answer_cut`).

## 3. Testaufgabe

- Arbeitsordner (leer): `workspace/GUPPI_OS/runtime_data/vscode_serve/am008_work` in VS Code öffnen.
- Aufgabe: den Inhalt von `runtime_data/vscode_serve/AUFGABE_am008_meter.txt` in Cline einfügen. Es ist dieselbe Aufgabe wie im DevVM-Bau (Meter-Datenmodul, drei Teile), in einem Stück.
- Nicht eingreifen und keine Hinweise zum Code geben. Wenn Cline nach Erlaubnis für Dateien oder Befehle fragt, darfst du erlauben.

## 4. Auswertung (Claude)

1. `serve_model.py stats ..\workspace\GUPPI_OS` liefert aus dem Serverlog: Anfragen, Prompt-Token und Einlesegeschwindigkeit, erzeugte Token und Erzeugungsgeschwindigkeit, belegte Zeit.
2. Die versteckte Suite `am008_meter` läuft über die Dateien in `am008_work` (microVM-Judge): bestanden oder nicht, pro Teil.
3. Beides kommt mit dem Bauergebnis aus dem DevVM in die Vergleichstabelle (`docs/MODELL_VERGLEICH_ERGEBNISSE.md`) und ins Logbuch. Ebenso, wie oft Cline an Grenzen stößt (abgeschnittene Antworten, Werkzeugfehler).

## 5. Continue (zweiter Test, optional)

`~/.continue/config.yaml` bleibt unverändert. Zum Ausprobieren in `models:` ergänzen (Port und Name aus `endpoint.json`):

```yaml
  - name: GUPPI Qwen3.6 (lokal)
    provider: openai
    model: qwen3.6-35b-a3b
    apiBase: http://127.0.0.1:8089/v1
    apiKey: local
    contextLength: 32768
    roles: [chat, edit, apply]
```

## Hinweise

- Cline und Continue senden eigene, lange Systemtexte mit. Das kostet Kontext und Einlesezeit. Die Auswertung zeigt es in den Prompt-Token.
- Der Test misst das Modell **im Werkzeug**, nicht das Modell allein. Unterschiede zum DevVM-Bau kommen auch vom Werkzeug.
