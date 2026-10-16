# Redesign-Plan: visueller Overhaul der SEDRA-Oberflächen

Stand: 16.10.2026. Nur Planung. Es wurde noch kein Code geändert. Umsetzung erst nach Freigabe.

## 0. Entscheidungen aus der Abstimmung

| Frage | Antwort |
|---|---|
| Design-Sparringspartner | NVIDIA `nemotron-3.5-super-vl-120b-a12b` (über die KI Labor, Cloud, durch den Inhaltsschutz) |
| Stil | Dunkel und premium, angelehnt an die Modellseite von build.nvidia.com |
| Marke | Keine Markenfarben vorgegeben. Die Palette in Abschnitt 2 ist ein Vorschlag, den du prüfst. |
| Umfang Phase 1 | Nur das Cockpit und das Design-System (Tokens) |

Hinweis zum Auftrag: Die Umgebungsvariable `SEDRA_API_KEY` gibt es in diesem Projekt nicht. Der Schlüssel liegt verschlüsselt in der KI Labor. Der Zugriff läuft darüber, nicht über eine Umgebungsvariable.

## 1. Bestandsaufnahme

**Technik:** reines HTML, CSS und JavaScript. Kein Framework, kein Tailwind, kein CSS-in-JS. Ein Token-System in `uix/ui/tokens.css` (152 Zeilen CSS-Variablen für Flächen, Text, Akzent, Status, Schatten, Radien, hell als Standard).

**Umfang:**
- 83 JavaScript-Dateien mit rund 10.500 Zeilen.
- 1.820 Zeilen CSS, verteilt auf Shells, Werkzeuge und Rahmen.
- 8 Shell-Ordner (Cockpit, Minimal, Paperclip, KI GateWay Studio, GUPPI XP, Start, Vorlagen).
- 28 Werkzeuge.
- Zwei Einstiegsseiten: `desk.html` und `retro_desktop.html`.
- Keine Webfonts. Fünf Vorschaubilder.

**Harte Regeln aus den Verträgen (vom Test geprüft, sie gelten für das Redesign):**
- Farben nur über Tokens. Kein Hex-Wert außerhalb von `tokens.css`.
- Keine Datei länger als 400 Zeilen.
- Werkzeuge rufen selbst kein `fetch` und kein `localStorage` auf. Der Zugriff läuft über den Kontext der Shell.
- Jede Datei hat ihre README, die sagt, wofür sie da ist.
- Kontrast mindestens 5:1 auf der Fläche (Projektregel B6-G-04).

**Technische Einschränkungen:**
- Die Oberfläche läuft im lokalen Browser. Kein Netzwerk nötig, aber auch keine Webfonts aus dem Netz.
- Ein Modell läuft auf der GPU, die Oberfläche selbst kostet wenig. Animationen dürfen die GPU-Anzeige nicht ausbremsen.
- Ziel: aktuelle Chromium-Browser und die Desktop-Ansicht bei 1280 Pixel Breite und mehr. Das Phone-Layout ist nicht Ziel.

**Betroffene Oberflächen:** alle 8 Shells, die Desktop-Oberfläche, die 28 Werkzeuge. In Phase 1 nur Cockpit und die Tokens.

## 2. Designvision

**Richtung:** „Deep Space Command“ (Vorschlag aus der Abstimmung), ruhig, sachlich, technisch. Fokus auf Datendichte und Agentenstatus auf einen Blick. Keine Verspieltheit.

**Referenzen:** die Modellseite von build.nvidia.com (Karten mit Badges, Filterspalte, Suche), eine Kommandozentrale mit dunkler Statusleiste.

**Palette (Vorschlag, noch zu prüfen):**

| Rolle | Hex | Kontrast auf `#161619` |
|---|---|---|
| Hintergrund | `#0B0B0D` | Basis |
| Fläche | `#161619` | Basis |
| erhöhte Fläche | `#1E1E23` | Basis |
| Text | `#EAEAEF` | 15,1:1 |
| Sekundärtext | `#8A8A92` | 5,3:1 (auf `#1E1E23` nur 4,85:1, zu dunkel) |
| Akzent | `#00D9A5` | 9,9:1 |
| Warnung | `#FFB74D` | 10,4:1 |
| Erfolg | `#34C759` | 8,1:1 |

Zwei Punkte zur Entscheidung:
1. **Akzent:** Der Vorschlag ist Türkis (`#00D9A5`). Du hattest NVIDIA-Grün (`#76B900`) gewünscht. Beides ist möglich. Das wäre eine Frage an dich.
2. **Sekundärtext:** Auf erhöhten Flächen muss er heller sein, damit er die 5:1 hält (z. B. ein helleres Grau, zu prüfen).

## 3. Design-System (Tokens)

- **Farben:** wie oben, als Tokens in `tokens.css`. Hell als zweites Thema erhalten, damit die bisherige Klar-Ansicht nicht bricht.
- **Typografie:** nur Systemschriften (`system-ui`, Segoe UI). Größen 11, 13, 15, 17, 20, 24, 32 Pixel. Gewichte 400, 500, 600. Keine Webfonts.
- **Abstände:** 4-Pixel-Raster, 4 bis 48 Pixel.
- **Radien:** 4 (klein), 8 (Standard), 12 (Karten).
- **Schatten:** zwei Stufen, dezent. Keine dauerhaften Leuchteffekte.
- **Hintergründe:** ein sehr leichter Verlauf im Rahmen, keine Bilder. Ein feines Raster nur auf der Hauptfläche, abschaltbar.
- **Bewegung:** Karten blenden in 200 Millisekunden leicht ein. Hover mit dezentem Glanz. Einmaliger Farbimpuls bei Statuswechsel. Keine Dauerschleifen. Alles aus bei `prefers-reduced-motion`.

## 4. Komponenten

**Neu bauen:**
- Kartenraster mit Badges und Filterspalte (Vorbild Modellseite). Ist schon im KI Labor angelegt und wird zum Baustein.
- Statusleiste oben (Instrumente mit Wert, Hinweis und Ton).
- Gesprächsleiste unten mit Modellwahl und ziehbarer Höhe (ist schon umgesetzt, wird ins Design übernommen).

**Überarbeiten:**
- Buttons (Primär, Sekundär, Gefahr), Eingabefelder, Auswahlfelder.
- Baumnavigation im Cockpit (Gruppen, Zeilen, Auswahlzustand).
- Tabellen und Listen.
- Hinweise (Erfolg, Warnung, Fehler).

## 5. Seiten und Screens

**Phase 1 (Cockpit):**
- Layout: schmale linke Navigation mit Gruppen, zentrales Raster, rechte Detailspalte bei Bedarf, Statusleiste oben, Gespräch unten.
- Die Ansicht „KI Labor“ wird zum Referenzbild für das Kartenraster.

**Später:**
- Minimal, Paperclip, KI GateWay Studio, GUPPI XP, Start-Übersicht.
- Desktop-Oberfläche (`retro_desktop.html`), die bewusst retro bleiben könnte. Das ist eine Frage an dich.

## 6. Technische Umsetzung

- **Keine neuen Bibliotheken.** Alles in reinem CSS und JavaScript, passend zum Projekt.
- **Struktur:** Tokens bleiben in `ui/tokens.css`. Neue Komponentenstile je Shell oder Werkzeug, ohne Farben im Werkzeug selbst.
- **Migrationsweg:**
  1. Tokens umstellen (dunkel als Thema), alte Werte als Thema „Klar“ erhalten.
  2. Cockpit-Shell auf die neuen Tokens und Komponenten.
  3. Werkzeuge einzeln nachziehen.
  4. Übrige Shells.
- **Tests:** die bestehenden Vertragstests bleiben grün. Zusätzlich ein Test für die Kontraste der Tokens (mindestens 5:1 für Text auf Flächen).

## 7. Phasen und Reihenfolge

| Phase | Inhalt | Aufwand (grob) | Priorität |
|---|---|---|---|
| A | Tokens: Palette, Typografie, Abstände, Themen, Kontrasttest | klein | hoch |
| B | Cockpit-Shell: Layout, Statusleiste, Navigation | mittel | hoch |
| C | Kartenraster und Filterspalte als wiederverwendbarer Baustein | mittel | hoch |
| D | Gesprächsleiste, Buttons, Felder, Hinweise | klein | mittel |
| E | Werkzeuge einzeln (28) | groß | mittel |
| F | Übrige Shells und Desktop-Oberfläche | groß | niedrig |

Jede Phase endet mit einer Sichtprüfung im Browser und den Vertragstests. Erst dann die nächste.

## 8. Risiken und offene Fragen

**Risiken:**
- **Kontrast:** kleine Schrift und Badges können unter 5:1 fallen. Der Kontrasttest in Phase A fängt das ab.
- **Überladung:** zu viele Schatten, Glanz und Verläufe wirken schnell unruhig. Deshalb nur zwei Schattenstufen und keine Daueranimationen.
- **Barrierefreiheit:** Fokus-Markierungen, Tastaturbedienung und `prefers-reduced-motion` müssen erhalten bleiben.
- **Responsivität:** Phase 1 zielt auf Desktop ab. Das muss ausdrücklich so bleiben.
- **Dark Mode:** als Standard vorgesehen. Die Klar-Ansicht bleibt als zweites Thema erhalten.
- **Performance:** Animationen nur mit `transform` und `opacity`. Die GPU gehört dem Modell.

**Offene Fragen an dich:**
1. Akzent: Türkis (Vorschlag) oder NVIDIA-Grün?
2. Soll die Desktop-Oberfläche retro bleiben oder mitgezogen werden?
3. Sind die Modellkarten und das Raster als Baustein für alle Ansichten gewünscht?
4. Soll der Sekundärtext heller werden, auch wenn das vom Modell anders vorgeschlagen war?

## Zusammenfassung

Phase A bis C ergeben einen sichtbaren Schritt: dunkle Tokens, neue Cockpit-Ansicht und das Kartenraster. Das ist überschaubar und testbar. Danach entscheidest du über Akzent und Desktop, bevor es weitergeht.

**Freigabe ausstehend.** Nichts wird umgesetzt, bevor du den Plan freigibst.
