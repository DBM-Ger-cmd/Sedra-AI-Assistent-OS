# SEDRA UIX 2.0 – Richtung C, Berechtigungsplan, Oberfläche als Modul (Planung, 14.10.2026, 18:02)

Antworten des Captains auf die vier Fragen der Stärken-Inventur: (1) **Richtung C** – mehr Ausarbeitung; (2) Gespräch **unten**;
(3) Berechtigungen: beim Start eines Projekts in der Sandbox **einmal vorgeben**, erneut gefragt wird nur bei einer **ungeplanten**
Berechtigung; (4) Retro-Desktop ins **Logbuch/Entwickler-Archiv**, nicht Teil des neuen Moduls oder des Kerns. Dazu (17:57): Vorlagen
aus anderen GitHub-Projekten, modularer Ansatz ausbauen, **Oberfläche als Modul**.

## 1. Richtung C (Skizze `shots/uix2/uix2_C.png`)

Werkbank (B) als Grundform, Instrumentenstreifen (A) oben, Gespräch (A) unten:

- **Instrumente** (eine schmale Reihe, ~60 px, Captain 18:05: „die obere Leiste ist zu groß“): Zustand · Modell · GPU · Entscheidungen ·
  Aufgaben · Berechtigungen des Projekts · Kommando. Wert und Untertitel in einer Zeile, dünne Balken; die Werkbank hat den Platz.
  Jede Anzeige ist ein Werkzeug (siehe §3) und öffnet ihren Raum. **Vom Captain als Vorlage angenommen (18:05).**
- **Objektbaum** links: Projekt (Dateien), Aufgaben (wartende zuerst), Werkstatt, Besatzung, Bibliothek, System. Abschnitte klappen.
- **Werkbank** Mitte: Reiter je geöffnetem Objekt (Aufgabe, Datei, Modell, Skill); Werkzeugleiste des Objekts; darunter zwei Spalten
  (Kandidat/Inhalt links, Verlauf · Tests · Kosten rechts). Reiter sind dockbar (§2), der Captain kann teilen und verschieben.
- **Gespräch** unten, zwei Zeilen sichtbar, aufziehbar; Entscheidungen erscheinen *dort und* an der Werkbank, nie in einem anderen Fenster.
- Kein Retro: neutrale Haut (Tokens wie heute), Guppy klein im ersten Instrument. Retro-Dateien wandern nach `docs/historie/retro_desktop/`
  mit einem Logbucheintrag; sie werden nicht mehr ausgeliefert.

## 2. Berechtigungsplan statt Rückfragen (Antwort 3, erste Fassung – ersetzt durch 2a)

Heute: ein Gate pro Aktion (Guard, Einmal-Token). Neu: **ein Plan pro Projektstart**, die Gates bleiben darunter.

1. Beim Anlegen oder ersten Öffnen eines Projekts in der Sandbox schlägt GUPPI einen **Berechtigungsplan** vor (aus Machbarkeit und
   Aufgabe): Lesen Workspace · Schreiben Sandbox · Tests ausführen · Übernahme kleiner Änderungen (≤ n Dateien, keine Löschung) ·
   Netz aus · keine Konfigurationsänderung. Der Captain sieht ihn als eine Liste mit Schaltern und erteilt ihn **einmal** (ein Gate,
   Ziel `project:<id>:permissions`, inhaltsgebunden).
2. Der Guard führt den Plan als Projektregel: jede Aktion, die der Plan deckt, erhält ihr Einmal-Token automatisch (Audit vermerkt
   „gedeckt durch Plan v1“). Alles bleibt nachvollziehbar, nichts wird still erlaubt.
3. Eine Aktion **außerhalb des Plans** (Netz, Löschen, Konfiguration, große Übernahme, Kosten über Richtlinie) erzeugt genau eine
   Entscheidung mit drei Wegen: *Einmal erlauben* · *In den Plan aufnehmen* (neue Planversion, Gate) · *Ablehnen*. Die Skizze zeigt
   den Fall „Netzzugriff auf pypi.org“.
4. Der Plan ist im Instrument „Berechtigungen“ sichtbar und im Baum unter Projekt änderbar (jede Änderung = Gate). Versionen im Logbuch.
5. Umsetzung im Kern: `permission_levels.py`/`guard.py` kennen Projektregeln bereits in Ansätzen; neu ist der versionierte Plan als
   Datei `local_config/projects/<id>/permissions.yaml` und die Deckungsprüfung vor `create_gate`. Konzeptprüfung P0 bleibt gewahrt
   (Bindung an Inhalt und Ziel, leerer Scope ist keine Freigabe).

## 2a. Neu gedacht (Captain 18:19): Modus und Grenzen statt Berechtigungsplan; „＋ Neu“ und Vorhaben

Der Captain: das Instrument „Berechtigungen“ nochmal neu denken – was brauchen wir wirklich? Antwort: nicht eine Liste erteilter
Rechte, sondern **einen Modus und vier Grenzen**. Das deckt dieselben Fälle, ist aber auf einen Blick lesbar und braucht keine
Planversionen im Kopf.

- **Modus je Projekt** (ein Wort): *Beobachten* (GUPPI schlägt nur vor), **Sandbox** (Standard: arbeitet frei in der
  Entwicklungsumgebung, fragt an der Grenze), *Vertraut* (schreibt auch kleine Änderungen ins Projekt). Der Modus ist eine Voreinstellung
  der Grenzen; Wechsel = ein Gate.
- **Vier Grenzen**, jede *frei · fragt · zu*: **Projekt** (ins Projekt schreiben; Sandbox: fragt), **Netz** (Sandbox: zu), **Löschen**
  (zu), **Kosten** (Token/GPU je Aufgabe; Zahl, darüber: fragt). Mehr braucht es nicht: Konfigurationsänderungen bleiben immer ein Gate
  (sie sind keine Projektsache), Lesen ist immer frei.
- Das Instrument zeigt `Modus · Export  Sandbox  Projekt: fragt · Netz: zu · Löschen: zu · Kosten: 100k`. Klick öffnet die vier
  Schalter. Eine Überschreitung wird zur **Entscheidung an der Grenze**: *Einmal öffnen* · *Grenze ändern …* (für dieses Projekt, Gate)
  · *Ablehnen*. Der Live-Block markiert den nächsten Aufruf schon vorher („⟂ Netzgrenze“).
- Im Kern: `local_config/projects/<id>/boundaries.yaml` (mode + 4 Werte, versioniert), Deckungsprüfung vor `create_gate`; §2 oben
  (Plan) wird dadurch ersetzt – die Gate-Mechanik bleibt identisch.

**„＋ Neu“ in der Reiterleiste** (Captain: „ein + für neue Funktion, die man im Chat bespricht, sowie neue Projekte“): öffnet ein
kleines Menü – *Neues Vorhaben* (eine Funktion/Idee; wird als Reiter „Entwurf: …“ geöffnet, das Gespräch bezieht sich darauf, GUPPI
stellt Rückfragen und schlägt die Aufgaben vor), *Neues Projekt*, *Datei öffnen*, *Modell hinzufügen*. Daraus folgt eine Ebene im
Baum: **Projekt → Vorhaben → Aufgaben** (plus *Routinen*). Ein Vorhaben ist das, worüber man spricht; Aufgaben sind das, was GUPPI
daraus macht. Die Missionen der Runtime hängen an Aufgaben, unverändert.

## 3. Oberfläche als Modul – Machbarkeit und Vorlagen

**Ja, das lässt sich umsetzen**, und zwar ohne Framework-Wechsel. Vorlagen, die genau diesen Ansatz leben:

| Projekt | Was wir übernehmen | Lizenz / Form |
| --- | --- | --- |
| [dockview-core](https://www.npmjs.com/package/dockview-core) (v8.5, 2026) | Dock-Layout: Reiter, Gruppen, Teilen, Ziehen, Layout speichern/laden, Popout; framework-frei, `dist/dockview-core.min.js` (Styles eingebaut) – lokal ausgeliefert, kein CDN | MIT |
| [OpenHands GUI](https://docs.openhands.dev/openhands/usage/key-features) | Das Reiter-Muster für Agentenarbeit: Chat · Changes (Diff) · Editor · Terminal · App · Browser – unser Werkbank-Satz: Aufgabe · Kandidat · Tests · Dateien · Logbuch | MIT (Muster, kein Code) |
| Grafana-Panels / Home-Assistant-Karten | Oberfläche als **Manifest + Modul**: ein Panel ist ein Plugin mit Beschreibung, Einstiegsdatei, erlaubten Datenquellen; Dashboards sind Daten (YAML/JSON), nicht Code – Vorbild für `tool.yaml` und gespeicherte Layouts | AGPL/Apache (Muster) |
| JupyterLab / Lumino | Dock-Workbench mit Erweiterungen, die Befehle, Menüs und Panels beisteuern; Befehlspalette (unser Kommando) | BSD (Muster) |
| [diff2html](https://github.com/rtfpessoa/diff2html) | Diff-Darstellung aus unified diff, framework-frei | MIT |
| ArtCraft (storytold) | Repo je Werkzeug, gemeinsame Bibliothek, Launcher (`UIX_2_KONZEPT.md` §6) | Apache (Muster) |

Nicht geeignet: Open WebUI, LibreChat, Lobe Chat (chat-zentriert, React/Svelte-Bundles, genau das, was es nicht werden soll);
Theia/code-server (zu schwer, eigener Kern); Paperclip (zweites Steuerpult, siehe Kommandodeck §3).

**Architektur „Oberfläche als Modul“:**

```
runtime/src/guppi_runtime/uix/            ← sedra-shell (Kern-nah, klein)
  shell.html, shell.js                    Pult, Baum, Dock (dockview-core), Gespräch, Kommando, Erscheinungsbild
  core.js                                 api(), Ereignisbus (sedra.on/emit: object.open, task.changed, decision.pending), Tokens
  tools/<id>/tool.yaml + tool.js + tool.css   ← ein Werkzeug je Objekttyp, im Paket (später: eigene Repos)
local_config/tools/<id>/                  ← vom Captain installierte Werkzeuge (git clone + Gate, Commit-ID und Hashes gebunden)
```

- `tool.yaml`: `id`, `name`, `handles` (file · task · candidate · model · skill · agent · instrument), `entry`, `api` (Routen-Allowlist),
  `trust` (CORE · CAPTAIN · GUPPI_BUILT · COMMUNITY), `version`, `tests` (Browserabnahme).
- Die Shell lädt Werkzeuge nach Manifest, registriert ihre Panels beim Dock und ihre Befehle beim Kommando; ein Objekt im Baum fragt
  „wer `handles` das?“ und bekommt die Reiter. Layout und offene Reiter werden je Browser gespeichert (dockview `toJSON`).
- Server: `/tools/<id>/…` nur aus registrierten Werkzeugordnern; CSP bleibt `self`; ein Werkzeug darf nur Routen seiner Allowlist
  rufen (Server prüft den Werkzeug-Header). Flag-Prüfung wie bei Skills; `COMMUNITY` nie ohne Durchsicht.
- GUPPI baut Werkzeuge auf seinem Spec-Weg; `uix_check.py` wird zur Werkzeug-Abnahme (ein Lauf je Werkzeug).
- Auch das Gespräch, die Instrumente und die Werkstatt sind Werkzeuge – nur der Rahmen (Shell) ist fest. So kann ein Werkzeug entfernt,
  ersetzt oder von Dritten beigesteuert werden, ohne den Kern zu berühren.

**Abhängigkeiten:** dockview-core und diff2html werden ins Paket gelegt (`uix/vendor/`, mit Lizenztexten in `THIRD_PARTY_NOTICE`),
nie aus dem Netz geladen – der Captain-PC ist offline-fähig, die CSP erlaubt nur die eigene Herkunft.

## 3a. Logikprüfung der Vorlage (Captain-Kommentare 18:12)

Der Captain hat die Skizze kommentiert: die Knopfkette an der Werkbank neu denken („Mit GUPPI besprechen ist im Grunde der Chat“), nach
solchen Logikfehlern suchen; die rechte Spalte (Verlauf · Tests · Kosten) ausbauen, die Münzloch-Ideen dort unterbringen; die Baum-
Einteilung passt; eine Live-Ansicht dessen, was gerade gebaut wird (wie in VS Code); die Entscheidung „ungeplante Berechtigung“ passt.

**Gefundene Logikfehler und ihre Regel:**

| # | Fehler in der Skizze | Regel ab jetzt |
| --- | --- | --- |
| L1 | *Mit GUPPI besprechen* als Knopf – das Gespräch ist eine Handbreit darunter | Kein Knopf führt zum Chat. Stattdessen folgt das Gespräch dem gewählten Objekt (Kontextzeile „bezieht sich auf: Aufgabe CSV-Parser“); Anhänge per Ziehen. |
| L2 | *Spur im Logbuch* als Knopf **und** Spalte *Verlauf* | Eine Spur: die Spalte. Das Logbuch ist der Nebenraum für alles, die Spur der Aufgabe steht an der Aufgabe. |
| L3 | *Übernehmen/Verwerfen* in der Leiste **und** als Entscheidung – und im Skizzenfall ist die Übernahme vom Plan gedeckt, also gar keine Entscheidung | Entscheidungen haben genau einen Ort (den Entscheidungsblock). Die Werkzeugleiste trägt nur Objekt-Handlungen, die keine Entscheidungen sind, und nur die, die im aktuellen Zustand gelten (*Anhalten* solange es läuft; *Erneut testen*, *Rückgängig* danach). |
| L4 | *Als Skill festhalten* als Dauerknopf | Ein Vorschlag, kein Knopf: nach einer gelungenen Aufgabe fragt GUPPI im Gespräch; der Captain sagt ja (Gate wie bei jedem eigenen Skill). |
| L5 | Zwei Eingabefelder: Kommando im Instrumentenstreifen **und** Gespräch unten | Ein Feld: das Gespräch. Es versteht Navigationsphrasen wie heute das Deck (`routeCommand`). Strg+K bleibt als Palette **über** dem Bildschirm, nicht als zweites Feld. Der Streifen wird dadurch schmaler. |
| L6 | Dieselbe Entscheidung dreimal mit Knöpfen (Instrument, Werkbank, Chat-Frage „Einmal erlauben?“) | Instrument = Zähler (Navigation), Werkbank = die Entscheidung mit Knöpfen, Gespräch = GUPPIs Satz mit Verweis. Eine Antwort im Gespräch („einmal ja“) gilt – GUPPI ordnet sie der offenen Entscheidung zu und schreibt dasselbe Audit. |
| L7 | Titelzeile **und** Reiter tragen denselben Namen | Der Reiter trägt den Namen, die Zeile darunter nur den Zustand. |
| L8 | Reiter *Dateien* neben dem Dateibaum links | Dateien öffnen aus dem Baum als eigener Reiter (`parser.py`); kein Sammelreiter. *Logbuch* ebenso: Nebenraum, kein Dauerreiter. |

**Ausbau der rechten Spalte (Nachweise), oben neu: Live.**

- **Live** zeigt, was gerade gebaut wird – wie das Terminal/Changes-Paar in VS Code bzw. OpenHands: Ausgabe des laufenden Schritts
  (Testläufer, Werkzeugaufrufe, „Coder schreibt src/export/parser.py (+24 −3)“, Token/s), gestreamt. Quelle: `run_log`, `step_journal`
  und der llama-server-Stream, den `runaway_guard` ohnehin beobachtet – ein SSE-Endpunkt `/api/task/<id>/live`. Ein nicht gedeckter
  nächster Aufruf wird hier bereits markiert („⟂ nicht im Plan“), bevor die Entscheidung entsteht.
- **Verlauf**: Seekarte klein, darunter die Spur (Zeit · Ereignis · Hash) aufklappbar.
- **Tests**: Tabelle, fehlgeschlagene aufgeklappt mit Ausgabe.
- **Kosten mit Münzloch**: GUPPIs `coin_hole.js` zieht hier ein – Münzen fallen live mit den verbrauchten Token (Kupfer 100 · Silber 1.000 ·
  Gold 10.000), daneben Token, GPU-Zeit, Modell. Das Meter-Fenster wird dadurch zum Reiter in der Besatzung (GUPPI-Anteil).

Die Skizze `uix2_C.png` ist entsprechend geändert (ein Eingabefeld, zustandsabhängige Leiste, Live-Block, Münzloch in Kosten).

## 4. Bauplan (erst nach Freigabe des Captains)

- **Build 7 – Shell und Vertrag:** `tool.yaml`, Lader, Ereignisbus, Dock mit dockview-core, Instrumente, Baum, Gespräch unten;
  die heutigen Fenster werden als erste Werkzeuge registriert (Werkstatt, Bibliothek, Besatzung, Meter, Logbuch). Retro ins Archiv.
- **Build 8 – Werkbank:** Aufgabe (Fortschritt, Seekarte, Spur, Kosten mit Münzloch), **Live-Block** (SSE), Kandidat-Diff (diff2html), Tests, Dateien als Reiter mit Vorschau.
- **Build 9 – Modus und Grenzen:** `boundaries.yaml`, Deckungsprüfung im Guard, Instrument mit vier Schaltern, Entscheidung an der Grenze
  „einmal öffnen · Grenze ändern · ablehnen“, Vorhaben-Ebene und „＋ Neu“, Routinen; Abnahme auf dem PC.
- GUPPI parallel: Specs für die reinen Teile (Deckungsprüfung, Aufgaben-Zusammenfassung, Diff-Modell, Manifest-Prüfer).

## 5. Noch offen

1. Darf dockview-core (MIT, ~14 MB Paket, davon ~400 kB nötig) ins Paket? Alternative: eigenes, kleineres Dock (Reiter + Teilen, ohne Popout).
2. Standardmodus neuer Projekte: *Sandbox* mit Projekt: fragt · Netz: zu · Löschen: zu · Kosten: 100k Token je Aufgabe – so richtig?
3. Name des Moduls im Repo-Zuschnitt: `sedra-shell` (Rahmen) + `sedra-tools` (Werkzeuge im Paket) + `sedra-ui` (Tokens/Komponenten)?
