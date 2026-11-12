---
name: n8n-eigenablauf-erweitern
description: Den SEDRA-Eigenablauf (Profil sedra-lokal-v1, n8n-Workflows lokal ohne n8n ausführen) um einen Knotentyp erweitern oder einen neuen n8n-Export lauffähig machen - Prüfer, Handler, Typtabelle der Oberfläche, Icons, Tests. Nutzen, wenn ein importierter n8n-Workflow "nicht ausführbar" ist, ein Knotentyp fehlt oder ein KI-Knoten über das lokale Modell laufen soll.
---

# Eigenablauf erweitern (workflows/lokal.py)

Der Eigenablauf führt importierte n8n-Workflows ganz lokal aus. Er ist **geschlossen**: was `lokal._plan` nicht kennt, wird vor dem Lauf mit einem Grund abgelehnt. Gestartet wird nur über das Captain-Gate (Aktion `run_sedra_workflow`, `execution.py`); `lokal.py` kennt keine Freigaben.

## Erst feststellen, woran es liegt
1. Export durch die Vorschau schicken: `workflows.vorschau.vorschau(text, name)` und `lokal.bewerten(doc)['reason']`. Der Grund nennt den Knoten (`unsupported_node:<Name>`, `unsupported_parameters`, `unreachable_nodes:<Name>`, `model_node_missing:<Name>`).
2. Typ und Version stehen in `VERSIONEN`? Parameter in `PRUEFER`? Sonst ergänzen.
3. Knoten, die vom Start aus nicht erreichbar sind, bleiben im Dokument und laufen nie (KI-Zweige ohne Anschluss). Das ist gewollt, nicht reparieren.

## Neuen Knotentyp einbauen (immer alle fünf Stellen)
1. `lokal.py`: Typ und Versionen in `VERSIONEN`, Anzeigename in `LABEL`, Prüffunktion `_pruefe_<typ>` in `PRUEFER` (nur bekannte Schlüssel zulassen, Rest ablehnen), bei mehreren Ausgängen `_ausgaenge()`, Handler `knoten_<typ>(lauf, n, items)` in `HANDLER`. Ein Handler gibt eine **Liste von Ausgängen** zurück, jeder Ausgang eine Liste von Einträgen `{'json': {...}, 'binary': {...}}`.
2. `uix/ui/workflow-lokal.js`: dieselbe Typ/Version-Tabelle in `sedraWorkflowLokalTypen` spiegeln, sonst steht der Knoten im Bild weiter auf "nicht ausführbar".
3. `uix/ui/workflow-icons.js`: Symbol und Label unter dem **letzten Teil des n8n-Typs** (`formTrigger`, `dataTable`, ...). Icons selbst zeichnen (24x24, Linie), nie aus n8n übernehmen (Lizenz, Regel des UI-Vertrags).
4. Gate-Text in `execution.py` ergänzen, wenn der Knoten etwas Neues tut (schreibt Tabelle, ruft Modell).
5. Tests: `tests/test_workflow_lokal_knoten.py` (kleine Workflows mit Hilfsfunktionen `wf`, `knoten`, `code`) und die echte Datei als Fixture (`tests/rechnungspruefung.json`).

## Regeln, die nicht aufweichen
- **Ausdrücke und Code** laufen nur in `lokal_runner.js` (Node mit `--permission`, frischer `vm`-Kontext, `codeGeneration` aus, Daten nur als Text). Nie `eval`, nie Python-Auswertung von JavaScript.
- Unbekannte Optionen ablehnen statt ignorieren (`_schluessel`). Typen streng prüfen wie n8n; `Set` mit Typ `string` lässt Listen durch, weil n8n-Exporte das tun.
- **KI-Knoten nur lokal:** `execution._modell` ruft den Router mit `provider='llama-cpp-server'` und `schema=` (geprüftes JSON). Das angeschlossene Cloud-Modell des Exports wird nie benutzt. Ohne Modell bricht der Lauf mit `kein_lokales_modell` ab.
- Tabellen (`lokal_daten.Tabellen`): Name wird über Kurzform gefunden (n8n-Exporte verlieren Umlaute, "Kosten bersicht" = "Kostenübersicht"). Schreibzugriffe stehen im Gate.
- Mehrere Eingänge nur bei `merge` (Eingang 0/1); alle anderen Knoten haben Eingang 0.

## Prüfen
- `runtime/.venv/Scripts/python.exe` mit `sys.path` auf `src` und `tests`, dann `unittest` für `test_workflow_lokal`, `test_workflow_lokal_knoten`, `test_n8n_missions`, `test_workflow_vorschau`, `test_uix_contract` (400-Zeilen-Grenze!).
- Echter Test mit den Beispielrechnungen aus `TestDaten/Steinbach_Nowak_...` (zwei Rechnungen, beide müssen "ALLE POSITIONEN STIMMEN ÜBEREIN" ergeben; einen Preis im Auftrag ändern, dann Zweig "Klärung erforderlich").
- Das Modell nur mit Attrappe testen, wenn kein Server läuft, und im Bericht sagen, dass der echte Aufruf nicht geprüft ist.
