# SEDRA Cockpit – Modul-Festlegung v1 (14.10.2026, 18:24, vom Captain als Vorlage angenommen)

Diese Seite friert die Vorlage `shots/uix2/uix2_C.html` als **verbindliche Form des Cockpit-Moduls** ein. Herleitung und Alternativen
stehen in `STAERKEN_INVENTUR_2026-10-14.md`, `UIX_2_KONZEPT.md`, `UIX_2_RICHTUNG_C.md`; hier nur, was gilt. Änderungen an dieser
Seite brauchen einen Logbucheintrag mit Begründung.

## 1. Zonen (fest)

```
┌─ Instrumentenleiste (eine Zeile, ~60 px) ───────────────────────────────────────────────┐
│ SEDRA·Zustand │ Modell │ GPU │ Entscheidungen │ Aufgaben │ Modus·Grenzen │ Tastenhinweis │
├─ Baum (230 px) ─┬─ Werkbank ─────────────────────────────────────────────────────────────┤
│ Projekt        │ Reiter je Objekt … ＋ Neu ▾                                              │
│ Vorhaben       │ Zustandszeile · Handlungen des Objekts (zustandsabhängig)               │
│  └ Aufgaben    ├───────────────────────────┬────────────────────────────────────────────┤
│ Routinen       │ Inhalt (Kandidat/Datei/   │ Nachweise: Live · Verlauf (Seekarte, Spur)  │
│ Werkstatt      │ Modell/Skill)             │ · Tests · Kosten (Münzloch)                 │
│ Besatzung      │ Entscheidung (ein Ort)    │                                             │
│ Bibliothek     │                           │                                             │
│ System         │                           │                                             │
├─ Gespräch (unten, 2 Zeilen sichtbar, aufziehbar; EIN Eingabefeld für Reden und Navigation) ┤
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

## 2. Regeln (fest)

1. **Ein Eingabefeld**: das Gespräch. Es versteht Navigationsphrasen (Router wie heute `routeCommand`). Strg+K öffnet die Palette
   darüber; kein zweites Dauerfeld.
2. **Entscheidungen haben einen Ort**: der Entscheidungsblock an der Werkbank. Instrument zählt, Gespräch verweist; eine Antwort im
   Gespräch („einmal ja“) gilt und erzeugt dasselbe Audit.
3. **Werkzeugleiste = Handlungen des Objekts im aktuellen Zustand**, nie Navigation, nie Entscheidungen, nie „mit GUPPI besprechen“.
   Aufgabe: *Anhalten* (läuft) · *Erneut testen*, *Rückgängig* (fertig). Datei: *Speichern*, *An GUPPI geben*. Modell: *Laden/Entladen*, *Testen*.
4. **Reiter tragen Namen, Zeilen tragen Zustand.** Dateien öffnen aus dem Baum als eigener Reiter. Kein Sammelreiter „Dateien“/„Logbuch“.
5. **Nachweise rechts, immer in dieser Reihenfolge**: Live (was gerade gebaut wird, gestreamt) · Verlauf (Seekarte klein, Spur
   aufklappbar: Zeit · Ereignis · Hash) · Tests (Tabelle, fehlgeschlagene aufgeklappt) · Kosten (Münzloch live, Token, GPU-Zeit, Modell).
6. **Aufgaben statt Karten**: Satz, Fortschrittszeile, Ergebnis. Keine Missions-IDs und Phasen im Cockpit (nur im Logbuch).
7. **Modus und vier Grenzen je Projekt** (Projekt · Netz · Löschen · Kosten; frei · fragt · zu). Überschreitung → Entscheidung an der Grenze:
   *Einmal öffnen · Grenze ändern … · Ablehnen*. Lesen immer frei; Konfiguration immer Gate.
8. **＋ Neu**: Vorhaben · Projekt · Datei öffnen · Modell hinzufügen. Ein Vorhaben ist Gesprächsgegenstand; GUPPI macht Aufgaben daraus.
9. **Vorschläge statt Dauerknöpfe**: „Als Skill festhalten“, „Lektion speichern“, „Routine anlegen“ kommen von GUPPI im Gespräch, mit Gate.
10. **Haut, nicht Struktur**: Tokens wie heute (`desktop.css` :root), Erscheinungsbilder Klar/Nacht; Retro nur im Archiv. Guppy klein im ersten Instrument.
11. **Modul-Schnitt**: Shell (Leiste, Baum, Dock, Gespräch, Palette, Ereignisbus) + Werkzeuge mit `tool.yaml` (`UIX_2_RICHTUNG_C.md` §3).
    Auch Instrumente, Nachweise und das Gespräch sind Werkzeuge.

## 3. Standard für neue Projekte (offen, bewusst)

Der Captain ist unsicher, ob *Sandbox · Projekt: fragt · Netz: zu · Löschen: zu · Kosten: 100k* der richtige Standard ist. Festlegung:

- **Kein fester Standard im Code.** Beim ersten Öffnen eines Projekts schlägt GUPPI Modus und Grenzen **aus dem Projekt** vor
  (leerer Ordner → Sandbox; bestehendes Repo mit fremdem Code → Beobachten; eigenes Werkzeugprojekt → Vertraut) und begründet es in
  einem Satz; der Captain bestätigt oder stellt um (ein Gate). Nichts läuft, bevor das einmal passiert ist.
- **Die Kostengrenze wird gemessen, nicht geraten:** zwei Wochen Guppy-Meter auf dem PC (Token je Aufgabe, 90-%-Quantil), dann steht die
  Zahl; bis dahin *fragt* die Kostengrenze ab dem Doppelten der bisher teuersten Aufgabe.
- Netz und Löschen bleiben in jedem Modus mindestens *fragt*; *frei* gibt es dafür nicht (Konzeptprüfung P0/P4).

## 3a. Wo das Dock wohnt (Captain 18:27: eigenes kleines Dock; Kern oder Modul?)

Drei Schichten, damit Module austauschbar bleiben:

| Schicht | Enthält | Austauschbar? |
| --- | --- | --- |
| **Kern** (`sedra-core`) | Runtime, Guard, Audit, API – **keine Oberfläche** | nein |
| **UI-Vertrag** (`sedra-ui`, klein) | `tool.yaml`-Schema, `api()`, Ereignisbus (`object.open`, `task.changed`, `decision.pending`), Tokens, der Werkzeug-Lebenszyklus `mount(container, ctx)` / `unmount()` | selten (Versionen) |
| **Shell** (ein Modul) | Leiste, Baum, **Dock**, Gespräch, Palette – die *Cockpit-Shell*; daneben möglich: eine *Minimal-Shell* (macOS-ähnlich: Menüleiste, ein Werkzeug zur Zeit, Spotlight = Palette) | ja, je Shell ein Modul |
| **Werkzeuge** | Aufgabe, Kandidat, Tests, Werkstatt, Bibliothek, Besatzung, Meter … | ja, je Werkzeug ein Modul |

**Antwort: das Dock gehört in die Shell, nicht in den Kern** – und kein Werkzeug darf das Dock kennen. Ein Werkzeug bekommt vom
Shell-Vertrag nur einen Container und den Kontext (`mount(el, {object, api, bus, tokens})`); wie Container angeordnet werden (dockbare
Reiter im Cockpit, ein Vollbild-Fenster in der Minimal-Shell), entscheidet die Shell. Das Dock selbst: eigenes kleines System,
~300 Zeilen (Reiter, horizontal/vertikal teilen, Ziehen, Layout als JSON speichern; kein Popout), Teil der Cockpit-Shell, ersetzbar.
So lässt sich eine minimalistische Shell zum Vorzeigen bauen, ohne ein Werkzeug anzufassen – beide Shells laden dieselben Werkzeuge.

Folge für den Bauplan: Build 7 baut zuerst `sedra-ui` (Vertrag) und die Cockpit-Shell; die Minimal-Shell ist danach ein Wochenend-Modul.

## 3b. Repo-Zuschnitt (Captain 18:29: „das schreiben wir wie vorgeschlagen fest“)

**Ordner im Paket, derselbe Vertrag; Trennung in eigene Repos erst, wenn die zweite Shell existiert** – dann hat der Vertrag bewiesen,
dass er trägt. Bis dahin:

```
runtime/src/guppi_runtime/uix/
  ui/        ← sedra-ui: Vertrag (tool.yaml-Schema, api.js, bus.js, tokens.css, lifecycle)
  shells/cockpit/   ← Cockpit-Shell (Leiste, Baum, Dock, Gespräch, Palette)
  shells/minimal/   ← später: Minimal-Shell
  tools/<id>/       ← Werkzeuge mit tool.yaml, tool.js, tool.css
```

Jeder dieser Ordner wird so geschnitten, dass er ohne Änderung in ein eigenes Repo wandern kann (keine Querimporte außer `ui/`).

## 3c. Gegenentwurf D: Paperclip-Desktop als zweite Shell (Captain 18:35, Skizze `shots/uix2/uix2_D_paperclip.png`)

Dieselbe Lage (Kandidat fertig, Netzgrenze offen) als **Firmen-Steuerpult** nach Paperclip: dunkle Navigation (Dashboard · Posteingang ·
Issues · Ziele · Agenten · Routinen · Kosten), KPI-Reihe, **Posteingang** (Freigaben, Berichte, Einstellungsvorschläge – der Captain ist
das Board), Organigramm mit Budgetbalken, **Issues als Kanban** je Projekt, Gespräch als schwebender Knopf. Abbildung auf SEDRA:
Issue = Aufgabe, Ziel = Vorhaben, Heartbeat = Routine, Agent = Rolle mit Rezept/Instanz, Budget = Kostengrenze, Posteingang = Entscheidungen.

| | Cockpit (C) | Paperclip-Desktop (D) |
| --- | --- | --- |
| Blick | ein Werkstück, Nachweise daneben | die Organisation, viele Vorgänge |
| Stärke | Diff, Tests, Live, Spur – S1–S4 ständig sichtbar | Überblick über Agenten, Budgets, Warteschlangen; vorzeigbar |
| Schwäche | viele parallele Aufgaben nur im Baum | der Kandidat liegt zwei Klicks tief; Gefahr, dass Freigaben wieder „Kacheln“ werden |
| Gespräch | unten, immer da | schwebender Knopf, zweitrangig |
| Passt zu | Entwickeln, Prüfen | Betrieb mit mehreren Agenten, Nachtketten, Vorführung |

**Entscheidung:** D wird **nicht** die Hauptshell, aber ein gültiger **zweiter Shell-Kandidat** neben der Minimal-Shell – beide beweisen,
dass der Werkzeug-Vertrag trägt (Posteingang = Werkzeug „Entscheidungen“, Kanban = Werkzeug „Aufgaben“, Organigramm = Werkzeug
„Besatzung“, alle schon im Cockpit vorhanden). Reihenfolge nach Build 9: Minimal-Shell (klein) vor Paperclip-Shell (mehr Fläche).

## 3d. Entwurf E: Minimal-Shell im modernen Desktop-Stil (Captain 18:39, Skizze `shots/uix2/uix2_E_minimal.png`)

Minimale Bedienung, aber das Gefühl, dass sich alles *auf dem Desktop* abspielt: Menüleiste oben (SEDRA · Ablage · Aufgabe · Werkzeuge ·
Fenster · Hilfe; rechts Modell, GPU, Modus, Entscheidungen, ⌘K, Uhr), **jedes Werkzeug ein eigenes Fenster** (Ampelknöpfe, Segment-
Reiter statt Dock-Reiter: Kandidat · Live · Tests · Verlauf · Kosten), **Entscheidungen als Mitteilung** oben rechts (dieselben drei Wege),
GUPPI als Nachrichten-Fenster mit Sprechblasen, ein **Dock** unten mit den Werkzeugen (Punkt = offen), ⌘K als Spotlight-Palette.
Keine Baumspalte: Projekt ist ein Fenster. Kein Apple-Markenzeichen, nur die Formensprache (Glas, Ampel, Dock, Mitteilung).

Vertrag-Beweis: dieselben Werkzeuge wie im Cockpit, nur anders angeordnet – die Shell liefert Fenster statt Dock-Container, die
Mitteilung ist das Werkzeug „Entscheidungen“ in anderer Hülle. Stärke: vorzeigbar, vertraut, ruhig. Schwäche: Nachweise nebeneinander
(Kandidat **und** Tests) brauchen zwei Fenster; viele Aufgaben werden zu vielen Fenstern. Reihenfolge nach Build 9: **E vor D**.

## 4. Nächster Schritt

Alles Nötige ist festgelegt: Form (§1–2), offener Standard (§3), Dock in der Shell (§3a), Zuschnitt (§3b). Bauplan Build 7–9 nach
`UIX_2_RICHTUNG_C.md` §4. Build 7 beginnt auf das „bauen“ des Captains.
