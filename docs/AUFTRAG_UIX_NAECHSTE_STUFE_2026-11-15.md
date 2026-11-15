# Auftrag: One Sedra auf die nächste Stufe (Design, Bedienung, 3D, parallele Agenten)

Stand: 15.11.2026. Überarbeitete Fassung des Auftrags des Captains vom selben Tag. Arbeitsort: Worktree
`E:\Sedra Umgebung\A1-wt-uix-3d`, Branch `uix-3d-naechste-stufe` (von `main` 7e46c27). Nichts geht ohne Ja des Captains nach `main`.

## 1. Der Auftrag im Wortlaut (sinngemäß) und was daraus wird

Der Captain: Design und Bedienung von SEDRA weiter verbessern, auch neue Wege gehen; Orientierung an Unsloth, Pi Desktop und
Claude; Hermes und Pi dürfen helfen; Bestandsaufnahme und Index nutzen; 3D integrieren, wie moderne Apps es tun; eigener
Worktree. Nachträge während der Arbeit: mehrere Agenten sollen gleichzeitig an einem Problem arbeiten können, mit Delegation
wie bei Claude; zuerst nur die Harness-Shell (One Sedra), die anderen Shells werden ausgelagert; der Drache soll wie ein alter
Bildschirmschoner im Hintergrund und durch die Menüs fliegen und als Avatar mit Hilfestellungen dienen.

Daraus wird dieser Auftrag:

**Ziel.** One Sedra (Shell `harness`) fühlt sich an wie ein aktuelles Agenten-Werkzeug: ein Blick zeigt, was läuft und wer
woran arbeitet; Tiefe ordnet die Oberfläche; 3D zeigt Zustand, nicht Schmuck; mehrere Agenten an einer Aufgabe sind sichtbar
und steuerbar.

**Nicht-Ziele.** Andere Shells (Cockpit, XP, Paperclip, Gateway, Minimal). Neue Rechte oder Freigabe-Wege. Ein Framework
oder Build-Schritt. Bibliotheken oder Schriften aus dem Netz zur Laufzeit.

**Feste Regeln (bleiben).** UI-Vertrag: Farben nur als Token, keine Datei über 400 Zeilen, Texte deutsch, `aria-label`,
Tastatur. Kontrast mindestens 5:1. Die Anzeige darf ein laufendes Modell nicht bremsen. Freigaben gibt nur der Captain.

## 2. Was die Vorbilder gut machen (Orientierung, kein Nachbau)

| Vorbild | Was dort trägt | Was One Sedra daraus nimmt |
|---|---|---|
| Claude (Desktop, Code) | Seitenleiste mit allen Sitzungen samt Zustand; Aufgabenliste unter der Antwort; Arbeit an Unter-Agenten abgeben und das Ergebnis zurückbekommen; geteilte Ansicht | Baustein D (Delegation), Zustand an jeder Sitzung, Aufgabenliste im Gespräch |
| Unsloth Studio | Modell wählen und laden ohne Umweg; zwei Modelle nebeneinander vergleichen; Einstellungen automatisch | Modellwahl direkt im Startbild; später Vergleich zweier Modelle als geteilte Ansicht |
| Pi (Oberflächen der Gemeinschaft) | Mehrere Sitzungen in Reitern; Werkzeugaufrufe live; Sitzungen suchen, anheften, archivieren | Reiter gibt es; Anheften und Archivieren fehlen in der Seitenleiste |

Quellen stehen in Abschnitt 7. Von Pi gibt es keine offizielle Desktop-App; gemeint sind Oberflächen Dritter.

## 3. Befund am Ist-Zustand (Sichtprüfung im Wegwerf-Projekt, 15.11.)

1. Start-Menü zeigte rohe Textschlüssel (`start_blick_aufgaben`, `einst_titel`). Ursache: `startmenue.js` lädt vor
   `i18n.js` und las die Titel schon beim Laden. **Behoben** (Titel als Funktion).
2. Köpfe der Kategorie-Kacheln waren weiß und unlesbar: dem Knopf fehlte die Rücksetzung. **Behoben.**
3. Eingabe hatte zwei Rahmen ineinander. **Behoben** (ein Rahmen, Glanz beim Schreiben).
4. Die Oberfläche ist flach: Menü, Karten und Grund liegen optisch auf einer Ebene.
5. `ui/seedrache-3d.js` und `ui/figur/drache.js` laden Three.js aus dem Netz und sind nirgends eingebunden. Die GLB-Modelle
   lagen ungenutzt unter `shells/harness/assets/`; der Server lieferte weder Unterordner noch `.glb` aus.
6. Das Startbild ist eine Checkliste. Es zeigt nicht, was SEDRA gerade kann oder tut.
7. Eine Konsolenmeldung „403“ beim Start bestand schon vorher; Ursache noch nicht geklärt.

## 4. Bausteine

### A. Tiefe als Ordnung – begonnen
Drei Ebenen: Grund, Arbeit (Karten, Eingabe), Schwebend (Menüs, Dialoge). Neue Tokens `--glas`, `--glas-unschaerfe`,
`--glanz`, `--lichthof`, `--tiefe`, gebaut aus den vorhandenen Farben, damit jedes Thema folgt.
Erledigt: Start-Menü als Glas, Kacheln heben sich beim Zeigen, Eingabe mit Glanz.
Offen: Freigabe-Karte, Dialoge, Kommandopalette, Vorschau, Seitenleiste; helles Thema „Klar“ ansehen.

### B. 3D-Bühne – begonnen
Erledigt: `shells/harness/buehne3d.js` zeigt den Seedrachen als echtes 3D-Modell, in drei Wahlen (`localStorage`
`sedra.harness.buehne3d`): `hintergrund` (Vorgabe: der Drache fliegt als Bildschirmschoner über das ganze Fenster, auch über
die Menüs; blass, solange der Captain arbeitet, deutlich nach 25 Sekunden ohne Regung; nimmt keine Klicks), `buehne` (nur im
Startbild über dem Titel), `aus`. Eigener kleiner GLB-Leser und
WebGL2-Zeichner, keine Bibliothek, nichts aus dem Netz. Rückfall auf die Zeichnung, wenn WebGL2 fehlt. Zeichnet nur, wenn
sichtbar; bei „weniger Bewegung“ ein Standbild; Pixelverhältnis höchstens 1,5. Der Server liefert `.glb` aus der Shell.
Offen, in dieser Reihenfolge:
1. Schalter in den Einstellungen für die drei Wahlen (heute nur über `localStorage`).
2. **Zustand statt Schmuck:** der Drache zeigt, was SEDRA tut (ruht, denkt, wartet auf Freigabe, Fehler) über Haltung und Licht.
3. Messung auf dem PC des Captains mit geladenem Modell: Bildrate und Token pro Sekunde mit und ohne Bühne.
4. Pyramide (`assets/pyramide-web.glb`, mit Texturen) als Token-Anzeige; braucht Textur-Unterstützung im Zeichner.
5. Entscheidung: bei eigenem Zeichner bleiben oder Three.js fest ins Paket legen (Download, braucht das Ja des Captains).
6. Die zwei verwaisten Dateien mit Netz-Bezug entfernen (Löschen braucht das Ja des Captains).

### C. Startbild als Leitstand
Statt Checkliste: ein Satz zum Zustand, Modellwahl direkt, die letzten Sitzungen, offene Freigaben, laufende Agenten.
Vorschläge für den ersten Schritt als Karten.

### D. Mehrere Agenten an einer Aufgabe (Delegation)
Der Captain gibt eine Aufgabe; ein Leiter zerlegt sie und verteilt Teile an Agenten, die gleichzeitig arbeiten; die
Ergebnisse kommen zusammen zurück. Vorhanden und zu nutzen: Werkzeug `auftraege_verteilen` mit Karte, Team-Rezepte, Profil
`team-35b` (ein Server, mehrere Kanäle), feste Slots, App „Team“, Nebensitzungen-Übersicht.
Neu an der Oberfläche:
1. **Delegations-Karte im Gespräch:** je Agent eine Zeile mit Rolle, Auftrag in einem Satz, Zustand, Token, Dauer; aufklappbar zum Verlauf.
2. **Agenten-Leiste:** wer läuft, auf welchem Kanal; Klick springt zur Zeile.
3. **Steuern:** einen Agenten anhalten, nachfragen, neu ansetzen; alle anhalten.
4. **Zusammenführen:** Ergebnisse nebeneinander, der Leiter fasst zusammen; was etwas ändert, geht als eine Freigabe an den Captain.
Vorarbeit: lesen, was `auftraege_verteilen` heute an Ereignissen liefert, und daraus eine Spec schreiben.
Grenze der Hardware: gleichzeitige Agenten teilen sich Kontext und Grafikspeicher; die Zahl folgt dem Profil.

### F. Der Drache als Avatar mit Hilfestellungen (Captain 15.11.)
Erste Fassung gebaut (`shells/harness/avatar.js`, `avatar.css`, `strings_avatar.js`): vier Anlässe nach Rang (Freigabe wartet,
Lauf fertig oder gescheitert, kein Modell geladen, leere Sitzung), ein Satz und höchstens ein Knopf, Schließen mit × oder Esc,
der Drache landet an der Sprechblase und hebt danach wieder ab. Ein geschlossener Hinweis kommt in diesem Fenster nicht wieder.
Ganz abschalten: `localStorage` `sedra.harness.avatar` = `aus`. Er liest nur; der Knopf öffnet die Stelle, an der der Captain handelt.
Offen: Schalter in den Einstellungen, Abschalten je Anlass, im Browser gesehen ist bisher nur der Anlass „kein Modell“,
die Sprechblase verdeckt im Startbild den Knopf „Ins Feld“ zum Teil. Der Plan dazu:
Der fliegende Drache ist nicht nur Schmuck: er kann sich an eine Stelle setzen und einen kurzen Hinweis zeigen.
1. **Landen:** bei einem Hinweis fliegt er neben das betroffene Bedienelement und hält dort.
2. **Sprechblase:** ein Satz und höchstens ein Knopf („Modell wählen“, „Freigabe ansehen“). Per Tastatur erreichbar, mit Esc zu.
3. **Anlässe (nur lesend):** kein Modell geladen, Freigabe wartet, Lauf fertig, Fehler im Lauf, erste Schritte in einer leeren Sitzung.
4. **Abschaltbar** je Anlass und ganz; nie mehr als ein Hinweis zugleich; er entscheidet nichts und löst nichts aus.
Vorarbeit: Liste der Anlässe aus den vorhandenen Zuständen (Taskleiste, Posteingang) ableiten; die Hinweistexte kommen in die Textdateien (DE/EN).

### E. Seitenleiste und Sitzungen
Zustand je Sitzung (läuft, wartet auf Freigabe, fertig), anheften, archivieren, gruppieren.

## 5. Aufteilung der Arbeit

| Paket | Wer | Inhalt | Fertig, wenn |
|---|---|---|---|
| P1 | Koordinator (dieser Chat) | Bausteine A und B fortsetzen, Sichtprüfung, Tests | Bilder vorher/nachher, Tests grün |
| P2 | Pi | Spec „Delegation an der Oberfläche“ (Baustein D): Ereignisse von `auftraege_verteilen` lesen, Datenvertrag, Abnahmepunkte. Nur Dokument, kein Bau | Spec liegt vor, vom Koordinator geprüft |
| P3 | Hermes | Baustein E: Zustand je Sitzung in der Seitenleiste, mit Test, im eigenen Worktree von diesem Branch | Test grün, Sichtprüfung durch Koordinator |
| P4 | Koordinator | Baustein C nach P1 | Sichtprüfung |

Hermes und Pi bekommen ihre Pakete erst nach dem Ja des Captains (sie belegen die Grafikkarte). Ihre Meldungen prüft der
Koordinator selbst nach, bevor etwas als fertig gilt.

## 6. Stand der ersten Stufe (15.11.)

Geändert im Worktree, nicht committet:
- `runtime/src/sedra_runtime/uix/shells/harness/buehne3d.js`, `buehne3d.css` (neu)
- `runtime/src/sedra_runtime/uix/shells/harness/seedrache-web.glb` (aus `assets/` hierher verschoben)
- `runtime/src/sedra_runtime/uix/shells/harness/shell.yaml`, `verlauf.js`, `startmenue.js`
- `runtime/src/sedra_runtime/uix/ui/tokens.css`
- `runtime/src/sedra_runtime/desk/gateway.py` (Dateityp `.glb` für die Auslieferung)
- `runtime/tests/test_uix_buehne3d.py` (neu)
- `runtime/src/sedra_runtime/uix/shells/harness/avatar.js`, `avatar.css`, `strings_avatar.js` (neu), `shell.js` (eine Zeile)
- `runtime/tests/test_uix_avatar.py` (neu)

Tests: Gruppen harness, uix, desk: 1620 Tests, 23 übersprungen, 0 rot (vor dem Flug-Modus); danach die fünf Module um die
Shell erneut grün.

Geprüft: Sichtprüfung in Edge ohne Grafikkarte (Software-Zeichner) im Wegwerf-Projekt. Nicht geprüft: der PC des Captains
mit geladenem Modell, das helle Thema, die Bildrate.

## 7. Quellen

- Unsloth Studio: https://unsloth.ai/docs/new/studio und https://unsloth.ai/docs/new/studio/chat
- Claude Code Desktop, Neugestaltung für parallele Agenten: https://claude.com/blog/claude-code-desktop-redesign und https://code.claude.com/docs/en/desktop
- Pi, Oberflächen Dritter: https://github.com/marcbaque/pi-ui und https://github.com/icekale/pi-web
- 3D in Produktoberflächen: https://locallylost-project.pages.dev/guides/immersive-3d-spatial-ux-2026/
- Im Repo: `docs/REDESIGN_PLAN.md`, `docs/UIX_2_KONZEPT.md`, `UI_OPTIMIZATION_PLANS_SUMMARY.md`,
  `SEDRA_3D_Assets_Sammlung_2026-11-13/SEDRA_3D_Assets/05_Dokumentation/WEB_INTEGRATION.md`
