# SEDRA – ein lokaler KI-Assistent, der sich selbst erweitert

**Namen (Stand 14.10.2026):** Das System heißt **SEDRA** (Self-Evolving Development & Research Assistant). **GUPPI** ist das Maskottchen und die Stimme im Chat – der Guppy auf dem Desktop, das Fenster „GUPPI Interface“, die Begrüßung. In Code, Paketen (`guppi_runtime`), Archiv und Logbuch bleibt der technische Name GUPPI.

SEDRA ist ein Agenten-Betriebssystem für den eigenen PC. Es plant Aufgaben, führt sie mit lokalen Sprachmodellen aus und baut dabei **neue Teile seines eigenen Codes**.
Jede Änderung mit Wirkung nach außen und jede Übernahme in den eigenen Code muss ein Mensch freigeben, der **Captain**.

*SEDRA (technical name GUPPI) is a local, self-extending AI agent OS. It runs on local models only and builds parts of its own code; every change with an effect needs the human "Captain" to approve it. The documentation is in German.*

## Was SEDRA heute kann (Stand Oktober 2026)

- **Läuft vollständig lokal:** eigener llama.cpp-Server, keine Cloud-Modelle. Hauptmodell ist Qwen3.6-35B-A3B auf einer RTX 4070 Ti (12 GB).
- **Missionen mit Kontrolle:** Jede Aufgabe durchläuft *verstehen → planen → ausführen → prüfen*. Ein Guard entscheidet jede Aktion: erlauben, sperren oder den Captain fragen. Alles landet in einem hash-verketteten Audit-Log.
- **Baut sich selbst:** In einer abgeschotteten Entwicklungsumgebung (DevVM, mit microVM für Tests) schreibt GUPPIs Coder neue Module. Ob ein Modul gut ist, entscheiden **versteckte Abnahmetests**, die das Modell nie sieht, nicht das Modell selbst.
- **Beispiele von GUPPI selbst gebaut:** die Coder-Erweiterungen E-01 bis E-11, die Grenzprüfung `core_boundary`, die Prüfung `mcp_shield` für MCP-Werkzeuge und die Schichten-Auswertung `layer_summary`. In einer Nacht waren es zuletzt rund 780 Zeilen neuer, abgenommener Code.
- **Kennt seine Grenzen:** Ein GPU-Selbsttest (Canary) läuft vor dem ersten Modellstart. Eine gemeinsame GPU-Sperre verhindert, dass sich zwei Läufe die Grafikkarte teilen. Kontextgrenzen sind pro Modell gemessen, nicht geschätzt.
- **Eigene Oberfläche:** ein Retro-Desktop im eigenen Fenster mit Missionen, Agenten, Modellen, Chat und Code-Zähler.

## Grundsätze

Captain First · Local First · Capability Before Tool · Evidence Before Evolution · Plan Before Code · Candidate Before Stable · Verify Before Accept · Least Privilege · Reversible Change · Learn From Results

Daraus folgen harte Regeln, die GUPPI auch bei der Selbstentwicklung nicht umgehen kann:
- Der Guard und die Captain-Freigaben werden nie umgangen.
- Selbstentwicklung erzeugt keine neuen Rechte.
- Der Kern (Stufe E3) wird nie automatisch geändert.
- Übernommener Code lässt sich zurückrollen.
- Es gibt keinen stillen Wechsel auf ein Cloud-Modell.

## Schnellstart (Windows)

1. Den Ordner an einen beschreibbaren Ort legen.
2. **`ERSTER_START.bat`** richtet Python und PyYAML im Paketordner ein. Vor Downloads fragt es nach.
3. Danach immer **`START_SEDRA.bat`**: SEDRAs eigenes Fenster mit der **Übersicht der Oberflächen**. `START_SEDRA.bat cockpit` startet direkt in eine Oberfläche (nur für diesen Start), `START_SEDRA.bat --gewaehlt` in die in `uix.yaml` gewählte. Schließt man das Fenster, wird der Server beendet und das Modell entladen. (`START_GUPPI.bat` leitet weiter.)
4. `READY_TEST_WINDOWS.bat` prüft die Voraussetzungen des PCs.

**macOS / Linux:** `./start_sedra.sh` bzw. `./start_sedra.sh cockpit` (macOS auch `START_SEDRA.command` per Doppelklick). Erster Lauf richtet `runtime/.venv` ein. Details und Grenzen: [docs/BETRIEB.md](docs/BETRIEB.md#macos-und-linux).

Modelle (GGUF-Dateien) und die llama.cpp-Engine sind **nicht** im Repository. Wo sie liegen und wie sie eingetragen werden, steht in [docs/BETRIEB.md](docs/BETRIEB.md).

## Dokumentation

| Dokument | Inhalt |
|---|---|
| [docs/README.md](docs/README.md) | Übersicht über alle Dokumente, Berichte und Logbücher |
| [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md) | Wie GUPPI aufgebaut ist: Kern, Jobs, Modelle, DevVM, Agent Manager, Oberfläche |
| [docs/BETRIEB.md](docs/BETRIEB.md) | Starten, Konfiguration, Modelle und Rezepte, GPU-Sperre, Tests, Störungen |
| [docs/ENTWICKLUNG.md](docs/ENTWICKLUNG.md) | Wie GUPPI sich selbst weiterbaut, und die Regeln für Menschen und KI-Sitzungen |
| [docs/MODELLE.md](docs/MODELLE.md) | Welche lokalen Modelle wofür eingesetzt werden, mit Messwerten |

## Projektstand

Version 1.20 (*Self-Development Foundation*) mit laufender Weiterentwicklung. Gebaut und gemessen wird auf **einem** PC: Ryzen 7 7700X, 31 GB RAM, RTX 4070 Ti.
Die Arbeit ist im [Logbuch](docs/LOGBUCH_AGENT_MANAGER.md) mit Datum und Uhrzeit festgehalten. Ältere Paket- und Versionsnotizen (v1.2 bis v1.20) liegen in [docs/historie/](docs/historie/).
