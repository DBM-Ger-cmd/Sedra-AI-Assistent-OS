# SEDRA UIX 2.0 – Konzept für den Neubau der Oberfläche (Entwurf, 14.10.2026)

Vorgaben des Captains (17:43–17:46): beim Neubau das Konzept neu denken – *so einfache Benutzung wie möglich, starke Bedienung, passende
Werkzeuge, die bei der Arbeit unterstützen*; die Karten waren eher lästig, man verlor schnell den Überblick; den Menschen in der Schleife
behalten, **aber nur dort, wo es wichtig ist**. Skizze: `shots/uix2/uix2_skizze.png` (HTML daneben, zum Weiterzeichnen).

## 1. Leitsätze

1. **Ein Gespräch, ein Arbeitsplatz, ein Pult.** Nicht zehn Fenster. Das Gespräch mit GUPPI ist der Ausgangspunkt für alles; der
   Arbeitsplatz zeigt das Objekt, um das es gerade geht; das Pult ist eine Zeile mit allem, was man wissen muss. Fenster bleiben für
   Nebenräume (Hardware, Maschinenraum, Logbuch), aber sie sind nicht mehr der Normalfall.
2. **Karten verschwinden aus dem Blick, nicht aus dem System.** Eine Mission bleibt die Buchführung der Runtime (Audit, Gates, Phasen),
   aber der Captain sieht eine *Aufgabe*: ein Satz, eine Fortschrittszeile („Parser schreiben ✓ · Tests laufen …“), ein Ergebnis.
   Keine Karte pro Zwischenschritt, keine Missions-IDs im Gespräch (nur im Logbuch), keine Phasen-Namen (EXECUTE, VERIFY) nach außen.
3. **Mensch in der Schleife: genau an den Stellen, an denen etwas Bleibendes passiert.** Nicht beim Planen, nicht beim Rechnen in der
   Sandbox, nicht beim Testen. Sondern wenn etwas (a) ins Projekt geschrieben, (b) gelöscht oder überschrieben, (c) an der Konfiguration
   geändert, (d) nach außen geschickt wird oder (e) Geld/GPU über eine Grenze kostet. Jede dieser Stellen ist eine **Entscheidung**
   im Gespräch – mit Vorschau („schreibt 2 Dateien“), Rücknahme und genau einem Klick.
4. **Vertrauen wird einmal eingestellt, nicht bei jedem Schritt erfragt.** Je Projekt eine Stufe: *Sandbox frei · Übernahme fragt*
   (Standard), *alles fragt* (fremder Code), *Übernahme kleiner Änderungen frei* (eigenes Werkzeugprojekt). Der Guard bleibt maßgeblich
   (Konzeptprüfung P0: Gates binden Inhalt und Ziel); die Stufe entscheidet nur, welche Gates als Projektregel vorab erteilt sind.
5. **Starke Bedienung:** Strg+K für alles, Enter sendet, Strg+Enter führt aus, Esc schließt; Ziehen von Dateien ins Gespräch hängt sie an;
   jedes Objekt hat Werkzeuge, die zu ihm passen – nie allgemeine Knopfreihen.
6. **Zustand als Satz, Details auf Abruf.** „Qwen3.5 9B · 16k · 40 Token/s“ statt Tabellen; Experten-Details hinter *Mehr*.

## 2. Grundlayout (siehe Skizze)

| Zone | Inhalt | Werkzeuge |
| --- | --- | --- |
| **Pult** (oben, eine Zeile) | Zustand, Modell, GPU, offene Entscheidungen, laufende Aufgaben, Vertrauensstufe des Projekts, Kommando-Feld, Erscheinungsbild | Klick auf ein Element öffnet den passenden Nebenraum |
| **Gespräch** (links) | Ein Gespräch mit GUPPI (Verlauf mit Sitzungen); Aufgaben als Fortschrittszeile; Entscheidungen als eine hervorgehobene Zeile mit zwei bis drei Knöpfen; Ergebnisse als Satz mit Verweis auf den Arbeitsplatz | Anhängen per Ziehen, `/`-Befehle optional, Vorschläge für den nächsten Schritt |
| **Arbeitsplatz** (Mitte) | Das aktive Objekt: Projektdateien (Explorer mit Vorschau), Aufgabe (Fortschritt, Seekarte klein), **Kandidat (Diff)**, Tests, Logbuch-Auszug; Modell (Werkstatt-Leiste), Skill (Editor) | Werkzeugleiste des Objekts: Übernehmen/Verwerfen, Erst ansehen, Mit GUPPI besprechen, Als Skill festhalten, Laden/Testen, Bearbeiten |
| **Besatzung und Maschine** (rechts, schmal) | Rollen mit Modell und Zustand, Entwicklungsumgebung, Token heute, nächste Routine, Bibliothek | Klick öffnet Besatzung/Werkstatt/Bibliothek |
| **Leiste** (unten) | Deck · Gespräch · Werkstatt · Besatzung · Bibliothek · System ▾ · Uhr | – |

## 3. Was wegfällt, was bleibt

- **Weg:** zwei Chats (Interface + Chat-Verlauf) → ein Gespräch. Brücke als eigenes Fenster → Aufgabenliste im Arbeitsplatz. Gate-Boxen
  mit JSON-Rückfrage → Entscheidungszeile mit Vorschau. Phasen und IDs im Gespräch. Knopfreihen zur Navigation. Prozessor-Fenster
  („Verarbeitung“) → Vorschau im Arbeitsplatz.
- **Bleibt (umgezogen):** Werkstatt-Leiste, Standardtest, Neues Modell in drei Schritten, Organigramm, Bibliothek, Guppy-Meter mit
  Münzloch (als Reiter), Seekarte (klein, in der Aufgabe), Erscheinungsbilder, Guppy-Maskottchen mit Stimmung (im Pult, klein).
- **Neu:** Vertrauensstufe je Projekt; Kandidat-Diff als Hauptansicht vor der Übernahme; „Erst ansehen“ als dritter Weg neben
  Übernehmen/Verwerfen; Routinen (Nachtkette) sichtbar; Aufgaben-Zusammenfassung statt Karten.

## 4. Werkzeuge, die bei der Arbeit tragen (Reihenfolge nach Nutzen)

1. **Kandidat-Diff** mit Datei-Liste, Übernehmen je Datei oder ganz – das ist der Moment, in dem der Captain wirklich gebraucht wird.
2. **Projekt-Explorer mit Vorschau** (Text, Bild, Markdown gerendert) und „An GUPPI geben“ per Ziehen.
3. **Testergebnis als Satz + Tabelle** (bestanden/fehlgeschlagen, Dauer, Token/s), fehlgeschlagene Tests aufklappbar.
4. **Vertrauensstufe** im Pult, je Projekt umschaltbar (selbst ein Gate).
5. **Kommando** (Strg+K) mit den Objekten des Arbeitsplatzes („öffne export/parser.py“, „teste nochmal“, „thema nacht“).
6. **Routinen**: Nachtkette und Standardtest als geplante Läufe mit „nächster Lauf“ im Pult; Ergebnis am Morgen als eine Zeile im Gespräch.
7. **Als Skill festhalten**: aus einer gelungenen Aufgabe wird mit einem Klick ein eigener Skill (Bibliothek, mit Gate).

## 5. Weg dorthin (ohne grüne Wiese)

Shell-Neubau, Umzug Fenster für Fenster; jeder Build startfähig:

- **Build 7 – Rahmen:** Pult, Dreispalten-Layout, Fenstervorlage/Komponenten-Basisklassen, Gespräch = heutiger Interface-Chat mit
  Sitzungen; Aufgaben als Fortschrittszeile (Karten nur noch im Logbuch); Entscheidungszeile statt Gate-Box.
- **Build 8 – Arbeitsplatz:** Explorer mit Vorschau, Kandidat-Diff, Tests, Aufgabe mit Seekarte; Werkstatt und Skill-Editor als Objekte.
- **Build 9 – Vertrauen und Routinen:** Vertrauensstufe je Projekt (Guard-Regel + Gate), Routinen-Zeile, „Als Skill festhalten“; Nebenräume
  ins System-Fenster; Abnahme auf dem PC; Retro bleibt als Erscheinungsbild.

Aufwand: drei Bauabende dieser Größe (Schätzung aus `UIX_KOMMANDODECK_v1.md` §6). GUPPI bekommt daraus Specs für die reinen Teile
(Aufgaben-Zusammenfassung, Entscheidungsregeln, Diff-Modell), wie bisher mit versteckten Tests.

## 6. Ökosystem statt Monolith (Captain 17:47, Vorbild github.com/storytold – ArtCraft)

ArtCraft ist eine Familie eigenständiger Werkzeuge (Photo-, Film-, Vector-, Deck-, PDF-Craft …) mit gemeinsamen Bibliotheken
(`craft-libs`), einem Launcher und einem Dienst-Repo – jedes Werkzeug ein eigenes Git-Repo, alle in einem Look. Übertragen auf SEDRA:

| ArtCraft | SEDRA | Repo (Vorschlag) |
| --- | --- | --- |
| craft-libs | Design-Tokens, Komponenten-Basisklassen, Fenstervorlage, `api()`-Helfer | `sedra-ui` (heute `uix/css/desktop.css` + `core.js`/`desktop.js`) |
| craft-launcher | Pult + Leiste + Kommando (öffnet Werkzeuge, zeigt Zustand) | `sedra-shell` |
| artcraft-services | Runtime, Guard, Audit, API | `sedra-core` (heute `guppi_runtime`) |
| ein Craft-Werkzeug | ein **Werkzeug** für einen Objekttyp: Explorer, Kandidat-Diff, Tests, Werkstatt (Modelle), Bibliothek, Besatzung, Meter | `sedra-tool-<name>`, je ein Repo |

**Werkzeug-Vertrag** (`tool.yaml`, Geschwister von `skill.yaml`): `id`, `name`, `handles` (Objekttypen: file, task, candidate, model, skill, agent),
`entry` (eine JS- und eine CSS-Datei, klassische Skripte wie heute), `api` (Allowlist der Routen, die es rufen darf), `trust`
(`CORE` · `CAPTAIN` · `GUPPI_BUILT` · `COMMUNITY`), `version`, `tests` (Browserabnahme wie `uix_check.py`). Der Arbeitsplatz fragt
bei einem Objekt die installierten Werkzeuge: wer `handles` passt, bekommt einen Reiter.

**Installation = Git + Gate.** Ein Werkzeug kommt als Repo nach `local_config/tools/<id>` (git clone oder Kopie, Commit-ID wird
festgehalten); ein Gate zeigt Vertrag, Dateiliste, Hashes und die API-Allowlist, dann liefert der Server die Dateien unter
`/tools/<id>/…` aus – nur von der eigenen Platte, CSP wie heute (kein Netz, kein Inline-Code). Dieselbe Flag-Prüfung wie bei Skills,
dazu: Werkzeuge sind *ausführbarer* UI-Code, deshalb Rang `COMMUNITY` nie ohne Durchsicht, und ein Werkzeug darf nur die Routen seiner
Allowlist rufen (der Server prüft den Referer/Tool-Header, nicht nur der Browser).

**Was das bringt:** GUPPI baut Werkzeuge als Repos mit Spec und verstecktem Test – genau sein heutiger Bauweg (`devvm_specs`), nur mit
einem klaren Einbauort. Der Captain kann ein Werkzeug entfernen, ohne dass die Shell bricht. Dritte können Werkzeuge beisteuern, ohne
Zugriff auf den Kern. Die Bibliothek bekommt ein viertes Regal: *Werkzeuge* (installiert · verfügbar · von GUPPI vorgeschlagen).

**Erster Schritt (Build 7):** `tool.yaml` + Lader für *lokale* Werkzeuge aus dem Paket selbst – Explorer, Werkstatt, Bibliothek, Besatzung,
Meter werden intern schon als Werkzeuge registriert. Externe Repos erst, wenn der Vertrag an fünf eigenen Werkzeugen gehalten hat.

## 7. Offene Entscheidungen für den Captain

1. Standard-Vertrauensstufe neuer Projekte: *Sandbox frei · Übernahme fragt*?
2. Soll das Retro-Deck als Erscheinungsbild bleiben (Himmel, Hügel, Guppy) oder wird *Klar* der Standard?
3. Bleibt die Brücke als Fenster für den Überblick über viele Aufgaben, oder reicht die Aufgabenliste im Arbeitsplatz?
4. Ökosystem: ein Repo je Werkzeug schon jetzt (mehr Pflege, klare Grenzen) oder zunächst Ordner im Paket mit demselben Vertrag und Trennung später?
