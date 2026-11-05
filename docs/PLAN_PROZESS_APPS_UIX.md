# Plan: Prozess-Apps näher an ihre Vorlagen (UIX-Überarbeitung)

Stand 05.11.2026. Basis: main a261f87 (SEDRA 1.22.2). Arbeitszweig: `feat/prozess-apps-uix`
im Worktree `E:\Sedra Umgebung\A1-wt-prozess-apps-uix`. Entscheidungen des Captains:
helles Thema zusätzlich zum dunklen; Make-Screenshots liegen als Vorlage vor; Arbeit im Worktree.

Übernommen werden Layout, Bedienlogik und Formensprache. Nicht übernommen werden Logos,
Markenfarben-Assets, Texte oder Marken der Hersteller. Die Apps bleiben eigene Oberflächen
(kein eingebettetes n8n/Make). Ausführungsrechte, Freigaben und Guard bleiben unverändert.

## Befund (Vorlage gegen Ist)

### n8n
| Bereich | Vorlage | Ist |
|---|---|---|
| Knoten | kleine Icon-Kacheln (~64 px), Name darunter, Untertitel grau | Textkarten 220x105, winzige Schrift, kein Icon, Typ-Info überfrachtet |
| Canvas | fast ganzes Fenster, Punktraster, Zoom/Fit unten links | unter ~20 Knöpfen, halbe Höhe, kein Raster |
| Linien | grün, weich geschwungen, "1 item", true/false an IF | dünn grau, "Ja/Nein" |
| Eigenschaften | Dialog per Doppelklick | Dauer-Panel rechts |
| Kopf | Name, Speichern/Publish rechts, Tabs Editor/Ausführungen | Knopfwand, Name als Eingabefeld |
| Knotenauswahl | "+" öffnet durchsuchbares Panel nach Kategorien | feste Knöpfe |
| Ausführung | einklappbare Logleiste, Ausführungsliste | nur JSON-Ausgabe |
| Rahmen | linke Navigation (Assistent, Übersicht, Persönlich, Projekte), Startseite | keine |

### Make (Szenario Studio)
| Bereich | Vorlage | Ist |
|---|---|---|
| Rahmen | violette Icon-Leiste links, zweite Leiste mit Unterpunkten, Suche oben (Strg+K), "Create scenario" oben rechts | keiner |
| Startseite | Begrüßung, Beschreibungsfeld, Karten "Start from scratch" | keine |
| Szenarioliste | Ordner, Labels, leerer Zustand mit Aktion | Auswahlliste |
| Module | große Kreise (~150 px), Icon, Zähler-Blase, Name + Aktion darunter, Trigger-Marker | Kreise ohne Icon, kleine Schrift |
| Verbindungen | Halbkreis-Anschlüsse und gepunktete Strecke zwischen Modulen | durchgezogene Linie |
| Konfiguration | kleines Fenster direkt am Modul ("Step 1", Verbindung, Weiter/Zurück) | Formular in fester Spalte |
| Hintergrund | glatt hellgrau, kein Raster | dunkel |
| Vorlagen | Kachelgalerie mit App-Icons, Suche, Nutzungszähler | Beispielknopf |
| Geführtes Einrichten | Schritt für Schritt, "Skip guided setup" | keines |

Der n8n-Assistent-Chat entspricht der Harness. Er wird nicht nachgebaut, später nur verknüpft.

## Phasen

### Phase 0 – Festlegungen
- Gestaltungsregeln: Raster 8 px, Knotengrößen, Linienstile, Typografie; hell und dunkel über Tokens.
- Icon-Satz: eigene schlichte Symbole je Knoten-/Modultyp (SVG, kein Fremdmaterial).
- Abnahmeliste: je Phase Vergleichs-Screenshots Vorlage gegen Ist (1400 und 1024 px, hell und dunkel).

### Phase 1 – Gemeinsame Bausteine (`uix/ui/`)
- `tokens.css`: helles und dunkles Thema, Umschalter, Gestaltungstokens je App (n8n: Grün/Rosa-Akzent
  neutral umgesetzt, Szenario: Violett-Akzent).
- Canvas: Raster-/Glatt-Hintergrund je App, Zoom/Fit unten links, Minimap, weiche Kurven,
  Linienbeschriftung, Anschlusspunkte.
- Icon-Modul mit Zuordnung Typ -> Symbol.
- Konfigurationsdialog (am Knoten verankert), durchsuchbares Knoten-/Modulpanel, Rahmenbausteine
  (linke Leisten, Kopfzeile mit Suche, Aktionsknopf).
- Kein Querimport zwischen Apps bleibt erhalten; Bausteine liegen nur in `ui/`.

### Phase 2 – n8n Workflows
- Icon-Kacheln, Zweig-Beschriftungen (true/false), "1 item"-Marker aus echten Daten
  (nur wenn die Engine-Antwort sie liefert, sonst nichts anzeigen).
- Kopfzeile aufräumen: Name, Speichern, Export-Menü, Prüfen; Tabs Editor / Versionen / Ausführungen.
- Doppelklick öffnet Konfiguration; Prozessangaben (SIPOC, Rollen) in eigener Seitenleiste auf Abruf.
- Untere Leiste: Ausführung und Log, einklappbar.
- Startseite mit Workflow-Übersicht.

### Phase 3 – Szenario Studio
- Rahmen mit Symbolleiste und zweiter Leiste (Szenarien, Vorlagen, Datenspeicher nur soweit vorhanden).
- Große Kreismodule mit Icon, Zählerblase, Name und Aktion, Trigger-Marker, Router-Zweige,
  gepunktete Verbindungsstrecken mit Halbkreis-Anschlüssen.
- Modul-Konfiguration als Fenster am Modul, Feldzuordnung dort.
- Untere Leiste: Run once (ausschließlich über bestehende Freigabe), Zeitplan nur anzeigen/nicht
  ausführen, Einstellungen.
- Vorlagengalerie (Kacheln, Suche) und Startseite; geführtes Einrichten für die Beispielvorlagen.
- Keine Marken-Icons von Drittanbietern; Module bleiben auf das beschränkt, was der Adapter kann.

### Phase 4 – Prüfung und Paket
- Vorhandene Tests anpassen, neue UI-Verträge ergänzen; JS-Modultests; Browserabnahme in Edge
  (1400/1024 px, hell/dunkel) mit Screenshots.
- Gezielte Python-Abnahme der Workflow-, Desk- und Update-Tests wie beim Kandidaten 1.22.2.
- Paket 1.22.3 über `package_n8n_update.py` / `verify_n8n_update.py`, Einspielen erst nach Freigabe.

### Phase 5 – Selbstabbild: SEDRA bildet seine eigenen Abläufe ab (Test und Dauerprobe)
Anforderung des Captains (05.11.2026): als Test sollen die Arbeitsabläufe von SEDRA selbst in den
Apps dargestellt werden; SEDRA soll seine eigenen Prozesse abbilden können.

- **Prozessmodelle, nicht ausführbar.** Die Abbilder sind Prozessmodelle im Sinn von
  `workflows/process.py` (Rollen, Lieferant, Input, Output, Empfänger, Nachweis, Abschlusskriterium).
  Menschliche Schritte (Captain-Freigabe) erscheinen als Rolle, nie als technischer noOp.
  Sie bekommen keine Ausführungsrechte.
- **Aus der Wahrheit erzeugt, nicht von Hand gemalt.** Ein Generator liest die tatsächlichen Quellen
  und erzeugt daraus Prozessmodelle, damit sie nicht veralten: `runtime/config` (Harness-Vorlagen,
  Freigabebausteine, Router, Rollenrouting, Token- und Modellrichtlinien), die Missions- und
  Rezeptdefinitionen sowie die Ablaufdokumente (ARCHITEKTUR, ABLAUF_GESPRAECH, ANALYSE_KETTE_EINGABE_AUSFUEHRUNG).
  Jeder Schritt trägt seine Quelle (Datei und Stelle) als Nachweis.
- **Erste Abläufe (Vorschlag, mit dem Captain zu bestätigen):**
  1. Auftrag -> Antwort (Eingabe, Router, Modell, Werkzeugkette, Antwort).
  2. Freigabe (Guard, Posteingang, Captain, Fortsetzen, Audit).
  3. Bauablauf (Vorarbeiter, Bauagent, Prüfer).
  4. Lernschleife (Lob/Korrektur, Belohnung, Lessons, Systemprompt).
  5. Modell laden und Scheduler.
  6. Update (Vorschau, Bestätigung, Übernahme, Sicherung, Rückweg).
- **Speicherung.** Als Revisionen im gemeinsamen Prozessbestand, Änderungsgrund "aus Quellen erzeugt
  <Stand>". Beide Apps zeigen denselben Bestand: n8n-Stil (technische Sicht) und Szenario-Stil
  (Modulsicht) dürfen denselben Ablauf unterschiedlich darstellen.
- **Abweichungsprüfung als Test.** Ein Test erzeugt die Modelle neu und vergleicht sie mit dem
  gespeicherten Stand; weicht die Wirklichkeit (Config/Code) ab, schlägt er fehl und zeigt den
  Unterschied über den vorhandenen Vorher/Nachher-Vergleich. So wird das Selbstabbild zur
  Dauerprobe der Prozess-Apps und der Dokumentation zugleich.
- **Grenze.** Es entsteht nur eine Darstellung. SEDRA ändert sich nicht über diese Modelle, und eine
  Rückrichtung (Modell -> Code/Config) gibt es nicht.

### Phase 6 – Prozesse in SEDRA anlegen (Stufe 6)
Anforderung des Captains (05.11.2026): Als nächste Stufe sollen in SEDRA solche Prozesse
angelegt werden können, nicht nur importiert oder aus Quellen erzeugt.
(Lesart: Anlegen durch den Captain in den Apps und durch SEDRA selbst auf Auftrag, z. B. aus dem Chat.
Bei abweichender Absicht vor Baubeginn klären.)

- **Anlegen in den Apps.** "Neuer Prozess" aus leerer Fläche, aus Vorlage (Galerie) oder aus
  einem Selbstabbild-Ablauf (Phase 5) als Kopie. Pflichtangaben: Name, Zweck, Rollen, Änderungsgrund.
- **Anlegen durch SEDRA.** Ein Harness-Werkzeug `prozess_anlegen` / `prozess_aendern` erzeugt aus
  einer Beschreibung im Chat einen Entwurf (Prozessmodell). Der Entwurf landet als neue Revision
  mit Herkunft "Harness, Auftrag <ID>" und wird nie automatisch aktiv. Der Captain sieht ihn im
  Editor und übernimmt ihn ausdrücklich; Änderungen laufen über den bestehenden
  Freigabeweg (Guard, Posteingang, Audit).
- **Vorlagen für eigene Prozesse.** Vorlagenkatalog (Name, Zweck, Rollen, Beispielkette),
  eigene Prozesse als Vorlage speichern; Beispiele aus den Selbstabbildern.
- **Prüfung beim Anlegen.** Vollständigkeit der Prozessangaben (Rolle, Input, Output, Nachweis,
  Abschlusskriterium), Warnung bei Lücken; Unterscheidung Beschreibung/ausführbar bleibt strikt,
  Ausführbarkeit nur durch bewusste Umwandlung mit eigener Freigabe.
- **Verwaltung.** Liste mit Suche, Ordnern/Labels (wie Make), Archivieren statt Löschen,
  Versionsfolge unverändert.
- **Test.** SEDRA legt per Chat-Auftrag einen Beispielprozess an, der Captain übernimmt ihn,
  die Revisionskette und das Audit werden geprüft; ohne Freigabe bleibt es beim Entwurf.
- **Grenze.** Angelegte Prozesse sind Darstellung und Planung. Sie erweitern keine Rechte von SEDRA
  und führen nichts aus.

## Reihenfolge und Abnahmen
1 -> 2 -> 3 -> 5 -> 6 (Phase 4 läuft jeweils mit), nach jeder Phase Screenshots zur Abnahme durch den Captain. Phase 1 zuerst, damit
beide Apps dieselben Bausteine nutzen und nicht doppelt angepasst werden.

## Risiken
- Der Worktree braucht für Läufe die `engines`-Verbindung und eine Kopie der `local_paths`
  (siehe Hinweis zur Modellablage), für reine UI-Arbeit nicht.
- Tests mit festen Texten/Selektoren der alten Oberfläche müssen mitgezogen werden.
- Helles Thema berührt gemeinsame Tokens: Gegenprobe, dass die übrigen One-Sedra-Ansichten
  unverändert bleiben (Themenumschalter nur im Geltungsbereich der Prozess-Apps).
- Hersteller-Markenmaterial wird nicht nachgebaut; Ähnlichkeit betrifft Layout und Bedienung.

## Nicht Teil dieses Plans
Echte Engine-Anbindung, weitere Knotentypen, Make-Blueprints, Cloud-Verbindung, Veröffentlichung/Tag.
