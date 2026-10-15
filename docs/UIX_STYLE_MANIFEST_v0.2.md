# UIX Style Manifest v0.2 (Stand 14.10.2026)

Abgeleitet aus dem, was in `runtime/src/guppi_runtime/uix/` tatsächlich steht: `css/desktop.css` (451 Zeilen), `retro_desktop.html` (9 Fenster), 15 Skripte in `js/`. Nichts hier ist erfunden; wo das Manifest etwas vorschreibt, das der Code noch nicht einhält, steht es unter „Soll“ oder in Abschnitt 9. Das Übergabepaket vom 13.10. verlangt dieses Dokument als ersten Schritt vor Shell-Architektur, Tokens, Komponenten und Design-Skills.

Zahlen zur Ausgangslage: 301 Farbangaben im CSS, davon 178 verschiedene; 13 Tokens in `:root`, aber nur 15-mal per `var()` benutzt. 186 CSS-Klassen. Das Erscheinungsbild ist konsistent, weil **eine** Hand es geschrieben hat, nicht weil es festgehalten wäre. Dieses Manifest hält es fest.

## 1. Charakter

GUPPI OS ist ein **Retro-Desktop im Stil von Windows XP** mit nautisch-technischer Sprache (Captain, Brücke, Maschinenraum, Logbuch, Besatzung) und einem Maskottchen, dem Guppy. Die Oberfläche ist freundlich, hell und dicht: kleine Schrift, viele Informationen, klare Kästen. Sie soll vertraut wirken (Fenster, Taskleiste, Startmenü) und dabei immer sagen, was wirklich ist. Vier Grundsätze, alle schon im Code sichtbar:

1. **Ehrlich.** Jeder Zustand kommt aus `/api/...`. Ohne Verbindung steht „OFFLINE“, ohne Modell „nur planen“, ohne Projekt ein ganzer Satz. Platzhalter wie „null“ oder „undefined“ sind Fehler (Test `test_model_without_name_is_shown_by_recipe_id`).
2. **Deutsch, in ganzen Sätzen.** Beschriftungen und Hinweise in der Sprache des Captains; technische Namen (Rezept-IDs, Phasen wie READY, Fehlercodes) bleiben englisch und werden daneben erklärt.
3. **Freigaben sind sichtbar und einmalig.** Alles, was etwas verändert, zeigt vorher genau, was passiert (Ziel, Risiken, Rücknahme), und gilt nur für diese eine Aktion.
4. **Nichts flackert unter der Hand.** Ansichten werden abseits gebaut und nur bei Änderung getauscht; während der Captain tippt, wird nicht neu gezeichnet (`swapModelView`, `modelViewBusy`).

## 2. Shell-Architektur: drei Schichten, drei Regeln

| Schicht | Wo | Darf | Darf nicht |
|---|---|---|---|
| **Oberfläche** | `uix/*.html`, `uix/css`, `uix/js` | darstellen, Fenster verwalten, `/api/...` lesen, Aktionen anstoßen, Anzeige-Komfort in `localStorage`/`sessionStorage` halten | Runtime-Zustand speichern oder erfinden, Statusbegriffe umdeuten, ein Gate umgehen |
| **Vermittler** | `uix_server.py`, `uix_diag.py` | Loopback + Token + CSP, Routen auf die Runtime, Lese-Routen als solche markieren, schreibende Routen nur über Mission + Gate | Geschäftslogik, eigene Zustandsautomaten |
| **Runtime** | `core/`, `jobs/`, `models/`, `devenv/`, `selfdev/` | entscheiden, ausführen, protokollieren | von der Oberfläche abhängen |

Regeln, die daraus für jede Datei in `uix/js` folgen (heute eingehalten, künftig per Test):
- Code auf oberster Ebene nur in `main.js` (`test_only_main_runs_code_at_load`).
- Jede Datei unter 400 Zeilen, damit GUPPI sie als Kandidat ändern kann.
- Namen so, wie die Runtime sie nennt: Phasen `READY`, `PAUSED`, `COMPLETE`, `FAILED`; Zustände `ok`/`warn`/`bad`; nie eigene Synonyme.
- Browser-Speicher nur für Anzeige-Komfort (Fensterlage, Chat-Anzeige, Filter) und immer in `try/catch`; nie für etwas, das die Runtime wissen muss.
- Die Abnahme ist der echte Browser: `benchmarks/uix_check.py` muss `result ok` melden.

## 3. Tokens

### 3.1 Ist: `:root` in `desktop.css`

| Token | Wert | Bedeutung |
|---|---|---|
| `--blue1` `--blue2` `--blue3` | `#58b8ff` `#2584e8` `#0b66cf` | Himmel des Desktops (Verlauf oben → unten) |
| `--task` `--task2` | `#2359bd` `#17479f` | Taskleiste (definiert, aber unbenutzt) |
| `--green` | `#43aa48` | Start-Knopf, Fortschritt |
| `--cream` `--cream2` | `#ece9d8` `#d8d2be` | Fensterhintergrund (XP-Beige) |
| `--line` | `#7f9db9` | Rahmen von Eingabefeldern |
| `--text` `--muted` | `#15263b` `#53677b` | Text, Nebentext |
| `--white` | `#fff` | (unbenutzt; 41-mal hart geschrieben) |
| `--shadow` | `0 18px 34px rgba(0,0,0,.28)` | Schatten des fokussierten Fensters |

### 3.2 Soll: die Farben, die im CSS wiederkehren, bekommen Namen

Aus den 178 verschiedenen Werten sind rund 30 wirklich bedeutungstragend; der Rest sind Verlaufsstufen und Einzelfälle. Vorgeschlagene Tokens (Werte = heutige Werte, nichts ändert sich sichtbar):

| Token | Wert (heute) | Verwendung heute |
|---|---|---|
| `--card-bg` | `#fff` | alle Karten, Blasen, Eingaben |
| `--card-line` | `#c0cbd8` | Rahmen von Karten (`.info-card`, `.mcard`, `.mr-card`, `.file-card`, `.dev-card`, `.mission`) |
| `--panel-bg` | `#f8f6ec` | Fensterinhalt (`.content`) |
| `--panel-side` | `linear-gradient(180deg,#fdfbf2,#e7e1cd)` | Seitenspalten |
| `--panel-bar` | `linear-gradient(180deg,#fffdf4,#e6e1cf)` | Werkzeugleiste |
| `--panel-line` | `#c2bcaa` / `#c6c0ad` | Trennlinien in Beige (heute zwei fast gleiche Werte → einer) |
| `--heading` | `#214b75` / `#294d72` / `#345b81` | Überschriften (drei Blautöne → einer, `#294d72`) |
| `--muted-2` | `#60758a` | Nebentext in Karten (heute neben `--muted` `#53677b`; zusammenlegen) |
| `--accent` | `#2468d4` | Links, Titelleiste-Mitte, Fokusrahmen in Menüs |
| `--title-bar` | `linear-gradient(180deg,#4096fb,#2468d4 48%,#124da8)` | fokussierte Titelleiste |
| `--title-bar-off` | `linear-gradient(180deg,#8fb1de,#6f93c6 48%,#5a7fb5)` | unfokussierte Titelleiste |
| `--btn-tool` | `linear-gradient(180deg,#fff,#ebe5d0)` + Rahmen `#b7b19f` | `.tool` |
| `--btn-action` | `linear-gradient(180deg,#fff,#cfe2fb)` + Rahmen `#6d98cd`, Text `#234d78` | `.action`, `.send`, `.dev-primary` |
| `--ok-bg` `--ok-fg` `--ok-line` | `#e6f6e8` `#28763a` `#bce1c2` | Zustand gut: `.badge`, `.phase`, `.tag`, `.step.done`, `.dev-state`, `.ok` (`#2b7c36`, angleichen) |
| `--warn-bg` `--warn-fg` `--warn-line` | `#fff3da` `#8b6517` `#ecd49a` | Zustand Achtung: `.phase.warn`, `.tag.warn`, `.step.active`, `.gate` |
| `--bad-bg` `--bad-fg` `--bad-line` | `#fbe3df` `#a13b32` `#e6b4ad` | Zustand schlecht: `.phase.bad`, `.tag.bad`, `.step.fail`, `.mbad`, `.bad`, `.dev-state.bad` |
| `--loaded-bg` `--loaded-line` | `#f2fbf3` `#6bbf78` | geladenes Modell / aktive Karte (`.mcard.loaded`) |
| `--diag-ok` `--diag-warn` `--diag-bad` | `#2f9e44` `#e0a100` `#d9480f` | Punkte der Diagnose-Leiste (kräftiger als die Karten-Zustände, bewusst) |
| `--guppy-1` `--guppy-2` `--guppy-line` | `#9ff1ff` `#0f84b5` `#09668e` | Guppy-Figur, Avatar, Icon des Chat-Fensters |
| `--folder-1` `--folder-2` `--folder-line` | `#ffd96a` `#e9ad25` `#9d7118` | Ordner-Icons, Fenster-Icons |
| `--chat-you` | `linear-gradient(180deg,#b7caff,#6f8fdc)` | Avatar „Du“ (heute inline in `chat.js`) |

Regel: **Eine neue Farbe im CSS braucht ein Token oder eine Begründung im Kommentar.** Die Zustandsfarben (ok/warn/bad) sind Pflicht-Tokens; sie dürfen nirgends anders herkommen.

### 3.3 Typografie

| Rolle | Ist | Soll |
|---|---|---|
| Grundschrift | `Tahoma, Verdana, Segoe UI, sans-serif` | unverändert, als `--font-ui` |
| Monospace | `Consolas, monospace` (Rohdaten, Diagnose, Dateivorschau) | `--font-mono` |
| Serife | `Georgia, serif` nur im Fenster „GUPPI Chat“ (`.cc-a`, `.cc-empty h2`) | bewusste Ausnahme, solange das Fenster den Claude-Desktop-Stil nachahmt; fällt mit der Entscheidung zu den zwei Chats (UIX_ANALYSE 4.1 Nr. 3) |
| Größen | 12 px Standard (29-mal), 13 px Fließtext/Chat (11), 11 px Nebentext (8), 10 px Badges (8), 20–22 px Fensterüberschriften, 44 px Datei-Symbol | Stufen: `--fs-xs 10`, `--fs-s 11`, `--fs-m 12`, `--fs-l 13`, `--fs-h 20`; die Einzelwerte 12.5/14.5/15/21 auf die Stufen ziehen |
| Zeilenhöhe | 1.4–1.55 in Fließtext | `1.45` |

### 3.4 Abstände, Radien, Schatten

- Abstände: 6 / 8 / 10 / 12 / 14 px innen, 7–9 px zwischen Knöpfen, 18 px Desktop-Rand. Soll: `--sp-1 6`, `--sp-2 8`, `--sp-3 12`, `--sp-4 16`.
- Radien: **4 px** Knöpfe und Eingaben, **7 px** Karten und Fensterrahmen oben, **999 px** Badges/Pillen, **50 %** Avatare/Punkte. Soll: `--r-btn 4`, `--r-card 7`, `--r-pill 999`. (Heute zusätzlich 2/3/5/8/10/14 px vereinzelt – auf die drei Stufen ziehen.)
- Schatten: fokussiertes Fenster `--shadow`, unfokussiert `0 4px 14px rgba(20,40,80,.25)`, Karten ohne Schatten (nur Rahmen), Datei-Platzhalter leicht.

## 4. Komponenten-Katalog (Ist)

| Komponente | Klassen | Verhalten / Regel |
|---|---|---|
| **Fenster** | `.window` (+ `.active .focused .minimized .maximized`) | Flex-Spalte: `.titlebar` → optional `.toolbar` → `.content` (flex 1). Verschiebbar an der Titelleiste, 8 Griffe `.rz-*` zum Vergrößern, Doppelklick maximiert. Mindestgröße 320×200. Nie feste Höhen im Inhalt (Fehler vom 13.10.). Jedes Fenster hat `role="dialog"` + `aria-label` (heute 3 von 9). |
| Titelleiste | `.titlebar .title-left .title-icon .controls .ctrl .ctrl.close` | 32 px; Icon 17×14 (Ordner-Gelb, Chat: rund Guppy-Blau); Knöpfe — □ × je 24×22; □ wechselt zu ❐ im Maximiert-Zustand; per Tastatur bedienbar. |
| Werkzeugleiste | `.toolbar .tool` (+ `.on`, `.diag-warn`, `.diag-bad`) | 12 px, umbrechend; Reiter sind `.tool.on` mit `aria-pressed`. |
| Inhalt | `.content` + Layout-Klasse (`.chat-body`, `.project-layout`, `.dev-layout`, `.model-main`, `.processor`, `.agent-main`, `.meter-main`) | scrollt selbst oder teilt in Spalten; Seitenspalten scrollen eigenständig. |
| **Karten** | `.info-card` (Projekt), `.dev-card`, `.mcard` (+ `.loaded`), `.mr-card` (+ `.wide`, `.big`, `.line`), `.meter-card`, `.file-card` (+ `.file-ico`, `.dir`), `.mission` | weiß, 1 px `--card-line`, Radius 7, Innenabstand 10–12 px. `.mcard` ist das Standardmuster „Info links, Knöpfe rechts“. Soll: ein `.card` als Basis, die anderen als Modifikatoren. |
| Zeilen in Karten | `.info-row`, `.dev-row`, `.mr-card .line` | Beschriftung links (darf umbrechen), Wert rechts (bricht nicht). Drei Klassen, ein Muster → Soll: `.row`. |
| **Knöpfe** | `.action` (Handlung, blau), `.tool` (Werkzeug, beige), `.send` (= `.action`), `.dev-primary/.dev-secondary/.dev-danger`, `.cc-new`, `.cc-bar button` | Handlung mit Wirkung = `.action`; Ansicht/Navigation = `.tool`; gefährlich = `.dev-danger` (rot). `chatButton` sperrt sich während der Aktion, `actionButton` meldet Fehler per `alert`. Soll: `.dev-*` und `.send` auf `.action`/`.tool` zurückführen. |
| **Zustandsmarken** | `.badge` (Mission-Liste), `.phase` (+ `.warn .bad`), `.tag` (+ `.warn .bad`), `.step` (+ `.done .active .fail`), `.dev-state` (+ `.bad`), `.ok`, `.bad`, `.mbad` | Pille 10 px fett; Farbe nur aus ok/warn/bad. `.badge` und `.phase` sind dasselbe Element → Soll: `.pill` mit Zustandsmodifikator; `.step` behält die Leiste. |
| **Chat** | `.msg .av .bub`, `.bub .card .gate .row .muted`, `.attachbar .chip`, `.modelbar`, `.inputbar`, `.diag-pane .diag-row .diag-dot .diag-out .diag-details` | GUPPI-Avatar Guppy-Blau, „Du“ Blau-Violett; Gate-Karte warn-gelb mit zwei Knöpfen (Ablehnen / genau diese Aktion einmal freigeben); Fehler mit `<details>` und Kopierknopf. |
| Desktop | `.desktop .hill .projects .stations .desktop-icon .folder .guppi-dock .guppi-bubble .guppi` | Icons sind nur Launcher (Doppelklick/Enter), `.selected` zur Hervorhebung; Sprechblase ist GUPPIs einzige „Stimme“ außerhalb der Fenster. |
| Taskleiste | `.taskbar .start .taskbtn (+ .launcher .open .on) .tray .clock` | ein Knopf je offenem Fenster; Launcher verbirgt sich, solange sein Fenster offen ist; Knöpfe schrumpfen mit Ellipse; Uhr und Zustand bleiben immer sichtbar. |
| Startmenü / Kontextmenü | `.startmenu .starthead .menu-main .menu-side .menuitem`, `.context-menu .ctx-item .ctx-sep` | schließen bei Klick daneben und Escape; Einträge per Tastatur. |
| Verarbeitungsfenster | `.processor .preview .processor-side .meta .proc-actions .file-placeholder .steps .mr-grid` | ein gemeinsames Fenster für Datei, Mission, Brücke, Logbuch, Maschinenraum (Grenze: nur eines zur Zeit, siehe UIX_ANALYSE 4.1 Nr. 1). Vorschau ist eine Spalte; Bild/Platzhalter zentriert. |
| Tabellen | `.agent-table` | Kopf beige, Zellen mit Rahmen, 12 px; einziges Tabellenmuster (Besatzung). |
| Guppy-Meter | `.meter-*`, `.coin-*` | Karten + Wochenraster (5 Grünstufen) + Münzloch-Canvas. |

## 5. Zustandssprache

| Zustand | Farbe | Wo sie gilt |
|---|---|---|
| gut / fertig / geladen | ok-Grün | READY nur bei Missionen (bereit zum Ausführen), COMPLETE, „bestanden“, geladenes Modell, Kette intakt |
| Achtung / wartet / läuft | warn-Gelb | PAUSED, CAPTAIN_REVIEW, offenes Gate, „läuft …“, verwaiste Lease, kein Modell geladen |
| schlecht / blockiert / gebrochen | bad-Rot | FAILED, BLOCKED, Audit-Kette gebrochen, Fehlertexte |
| neutral | `--muted` | Nebentext, Datenstand, Hinweise |

Regel: Grün heißt „es ist gut“, nie „es ist ein Zustand“. Ein `BLOCKED` in Grün (Fehler vom 13.10.) verstößt dagegen.

## 6. Sprache und Texte

- Anrede „du“, GUPPI spricht als „ich“, der Mensch heißt Captain.
- Ein Hinweis sagt **was ist, warum, und was man tun kann** („Nicht genug freier Grafikspeicher … Beende andere Programme … oder wähle ein kleineres Modell“). `explainModelError` und `/api/diagnose/explain` sind die Vorbilder.
- Keine Schein-Dialoge: `alert()`/`confirm()`/`prompt()` nur für Freigaben und Fehler, nicht für Hinweise (seit 13.10.: „Projekte“ ohne `alert`). Offene Ausnahmen: `attachPath` (Pfad per `prompt`), `requestCodeCandidate` (zwei `prompt`), `createProject`. Soll: eigene kleine Eingabe im Fenster.
- Jede Zahl mit Einheit und Bezug („10,7 GB frei von 12,0 GB“, „Kontext 8192“).

## 7. Bedienung mit der Tastatur (Phase 5, begonnen)

Ist: Tab/Enter/Leertaste für Fenstersteuerung, Startmenü, Kontextmenü, Taskleiste, Projektordner; Enter sendet, Umschalt+Enter neue Zeile (GUPPI Chat); Escape schließt Menüs; sichtbarer Fokusrahmen (weiß auf Blau, Blau in Menüs).
Soll: echte `<button>`-Elemente statt `div` + `makeKeyboardButton`; Alt-Tab-Ersatz (Fensterwechsel per Tastatur); Fokus landet beim Öffnen eines Fensters auf dessen erstem Bedienelement.

## 8. Themes: wie ein Wechsel möglich wird, ohne die Shell anzufassen

Ein Theme ist ein zweiter `:root`-Block mit denselben Token-Namen, aktiviert über `html[data-theme="…"]`. Voraussetzung ist 3.2 (alle bedeutungstragenden Farben als Token). Danach:
- Umschalten per Startmenü („Erscheinungsbild“), Merken im `localStorage`, Rücknahme = Standard-Theme oder Neuladen.
- Das Hardware-Fenster (`hardware_manager/dashboard.html`, dunkel `#101722`) bekommt dieselben Tokens über den Rahmen gereicht oder ein helles Pendant; heute ist es der einzige Bruch im Bild.
- Mac-ähnliche Skins sind nur andere Token-Werte und Radien; Fensterlogik, Gates und Texte bleiben gleich (Vorgabe des Übergabepakets: Austausch betrifft nur die Präsentationsschicht).

## 9. Abweichungen heute und ihre Tickets

**Ticket 1 erledigt (14.10., 09:39):** 42 Tokens in `:root` (13 alte + 29 neue aus 3.2, dazu `--heading-2`, `--gate-bg`, `--action-line-2`, `--beige-1..3`, weil diese Werte mehr als 4 % von ihrem Nachbarn abweichen und deshalb nicht zusammengelegt wurden); 183 `var()`-Verwendungen statt 15; im Regelteil bleiben 121 Hex-Angaben (111 verschiedene), fast alle Verlaufsstufen und Einzelfälle. Zusammengelegt wurden nur Werte mit höchstens 10/255 Abstand je Kanal (Überschriften-Blau 5 → 1, Nebentext-Grau 3 → 1, Beige-Linien 4 → 1, ok-Grün 4 → 1). `#fff` ist `--white`; nur Karten, Blasen und Eingabefelder nutzen `--card-bg` (= `--white`), damit ein Theme sie getrennt setzen kann. Beleg: `uix_check.py` 13/13 vorher und nachher; Screenshot-Vergleich aller Fenster zeigt Unterschiede nur an Uhr und Messzeit (dynamisch) und Farbdeltas ≤ 10. Test `test_state_colours_come_from_tokens`.


| Abweichung | Ticket (klein, kein GPU-Lauf) |
|---|---|
| ~~178 Farbwerte, 13 Tokens~~ | erledigt, siehe oben |
| ~~drei Überschriften-Blau, zwei Nebentext-Grau, zwei Beige-Linien~~ | erledigt (Ticket 1) |
| `.badge`/`.phase`/`.tag` dreifach, `.info-row`/`.dev-row`/`.line` dreifach, `.dev-primary`/`.send` doppelt zu `.action` | `.pill`, `.row`, `.action` als Basis; alte Namen bleiben als Aliase, bis die JS-Dateien nachgezogen sind |
| 9 Titelleisten von Hand im HTML | Fenstervorlage `<template id="windowFrame">` + `makeWindow(id, title, toolbar)` (UIX_ANALYSE 4.3 Nr. 12); danach kann `showProcessor` mehrere Fenster öffnen |
| `role="dialog"` nur bei 3 von 9 Fenstern | mit der Fenstervorlage automatisch |
| Serife nur im GUPPI Chat | fällt mit der Chat-Entscheidung |
| Hardware-Fenster dunkel | mit Themes (8) |

Reihenfolge: ~~Tokens~~ → Komponenten-Basisklassen → Fenstervorlage → Themes. Jeder Schritt einzeln, jeder mit `uix_check.py` abgenommen; die ersten drei eignen sich als GUPPI-Kandidaten (CSS/HTML-Änderung mit Browser-Abnahme als verstecktem Test), sobald `uix_check.py` auf dem GUPPI-PC läuft.

## 10. Quellen

`uix/css/desktop.css`, `uix/retro_desktop.html`, `uix/js/*.js` (Stand 13.10. nach den Korrekturen), `docs/UIX_ROADMAP.md`, `docs/UIX_ANALYSE_2026-10-13.md`, Übergabepaket `04_SHELL_UI_DESIGN.md` (13.10.), `docs/ABGLEICH_UEBERGABEPAKET_SEDRA_2026-10-14.md`.

## 11. Nachtrag 14.10., Bewegung und Name

**Name:** Das System heißt SEDRA (Startknopf, Startmenü, Tray, Seitentitel, Hardware-Seite, README). GUPPI bleibt Maskottchen und Stimme: der Guppy, „GUPPI:“ im Chat, die Fenster „GUPPI Interface“ und „GUPPI Chat“. Systemfenster tragen keinen Präfix mehr („Modelle“, „Hardware“, „Besatzung“, „Entwicklungsumgebung“, „Verarbeitung“).

**Bewegung (Regel: nur wo sie Zustand trägt, höchstens eine halbe Sekunde je Ereignis, alles unter `prefers-reduced-motion` aus):**
- Der Guppy ist der Ambient-Status (`#guppyFigure`, Klassen `idle`/`busy`/`gate`/`offline`, gesetzt von `setGuppyMood` aus `/api/models` und `/api/missions` nach jedem Statuslauf): ruhiges Atmen im Leerlauf; schnellerer Flossenschlag und Schwimmen, wenn ein Modell geladen ist oder lädt; Blase mit der Zahl offener Freigaben (Klick öffnet die Brücke); grau mit geschlossenem Auge ohne Verbindung.
- Fenster blenden in 120 ms ein (`winin`) und schrumpfen beim Minimieren 160 ms Richtung Taskleiste (`.minimizing`, `winout`), danach erst `minimized`.
- „Denkt nach“ pulsiert mit laufenden Punkten (`.thinking`), bis die Antwort da ist.
- Seekarte (`js/sea_chart.js`, `.sea-chart`): in jeder Missionskarte und im Mission-Fenster. Hafen → eine Boje je Plan-Schritt → Zielflagge; erledigte Bojen grün, die aktive pulsiert gelb; das Schiff steht an der Phase (im Hafen bis READY, unterwegs bei EXECUTE/VERIFY mit Kielwasser, am Ziel bei COMPLETE, rotes Segel bei FAILED); eine gestrichelte Schranke „Freigabe“ vor der nächsten Boje, solange ein Gate offen ist. `chartModel()` ist rein und wird mit Node geprüft.
- Anhängen ohne `prompt()`: ein Eingabefeld in der Anhang-Leiste (Enter hängt an, Escape schließt, Fehler erscheinen als GUPPI-Nachricht). Offen bleiben `createProject` und `requestCodeCandidate`.

Abgenommen mit `uix_check.py` (13/13), Browser-Proben für Formular, Minimieren und die drei Guppy-Zustände, Node-Test für `chartModel`.

## 12. Nachtrag 14.10. (Build 5, Kommandodeck)

- **Themes (8) umgesetzt:** `html[data-theme="klar"|"nacht"]` als zweite Token-Blöcke am Ende von `desktop.css`; dafür 25 Flächen-Tokens (`--sky-1..3`, `--hill-1..3`, `--title-1..3`, `--title-off-1..3`, `--window-line`, `--window-radius`, `--toolbar-1/2`, `--bar-1..3`, `--bar-line`, `--start-1..3`, `--taskbtn-*`, `--clock-1/2`, `--menu-*`, `--inputbar-bg`, `--input-bg`, `--bub-line`, `--font`). Regel: ein Theme setzt nur Token-Namen, die `:root` kennt (`test_themes_redefine_only_known_tokens_and_cover_the_surfaces`); ein paar Komponenten-Überschreibungen (Knöpfe, Eingabefelder) stehen direkt unter dem Block, weil ihre Verläufe noch feste Hex-Werte tragen – nächster Ticket-Kandidat (Komponenten-Basisklassen, 10).
- **Neue Regel 3.4 – Werkzeugleisten:** Eine `.toolbar` trägt nur Verben, die im eigenen Fenster wirken. Navigation zu anderen Fenstern gehört in Deck, Taskleiste, Startmenü, Kommando. Prüfbar in `test_uix_kommandodeck.py`.
- **Neue Bausteine:** `.deck-*` (Spalten, Zeilen mit Ton `warn|ok|bad`), `.palette*`, `.wb-rail/.wb-step` (Zustände `done|active|open|fail`), `.org*` (Knoten, Pills). Alle nutzen ausschließlich Tokens.
- Konzept und Paperclip-Einordnung: `UIX_KOMMANDODECK_v1.md`.

## 11. Nachtrag Build 7: der Vertrag hat die Tokens übernommen

Seit Build 7 steht die verbindliche Token-Liste in `uix/ui/tokens.css` (UI-Vertrag 1.0) – nicht mehr in `desktop.css`. Was hier als
*Soll* beschrieben ist, ist dort umgesetzt: Flächen (`--bg`, `--panel`, `--panel-2`, `--line`), Text (`--text`, `--muted`, `--heading`),
Bedeutung (`--accent`, `--ok*`, `--warn*`, `--bad*`), Live-Konsole, Seekarte, Guppy, und die Maße (`--gap*`, `--radius*`, `--strip-h`,
`--tree-w`, `--talk-h`, Schrift und Größen).

Zwei Regeln sind jetzt Tests statt Vorsätze (`tests/test_uix_contract.py`):

1. **Keine Farbe ohne Token.** In `ui/`, `shells/` und `tools/` darf kein `#rrggbb` stehen; nur `tokens.css` kennt Farbwerte.
2. **Ein Werkzeug stylt nur sich selbst.** Jeder Selektor einer `tool.css` beginnt mit `.t-<id>`.

Themes sind damit das, was Abschnitt 8 vorschlägt: ein zweiter Block mit denselben Namen unter `html[data-theme="nacht"]`.
Erscheinungsbilder in Build 7: **Klar** (Standard, folgt beim ersten Start der Systemeinstellung) und **Nacht**. *Retro* ist mit der
alten Shell ins Archiv gewandert und lebt dort unter `/retro` weiter (Cockpit-Regel 10: Haut, nicht Struktur).

`desktop.css` bleibt unverändert – es gehört jetzt zum Archiv und ist von den beiden Regeln oben ausgenommen.
