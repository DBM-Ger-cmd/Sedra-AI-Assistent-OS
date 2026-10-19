# Build 20 (Arbeitsstand) – Feinschliff Shell gateway-kmu, Cockpit, Schutz · 19.10.2026

Grundlage: `entwickler_paket_sedra_kern.zip` (Build 24 / 1.20, Stand 15.10.) mit der uncommitteten Shell `gateway-kmu`
aus `entwickler_archiv_kmu_shell.zip` – beide Pakete enthalten die Shell identisch. **Nichts committet, nichts gepusht.**
Die Änderungen liegen als `sedra_geaendert_2026-10-19.zip` (70 Dateien, über den Baum legen) und als
`aenderungen_2026-10-19.patch` vor. Zeilenenden der Quelldateien wie im Checkout (CRLF), nur die Shell-Skripte LF.

## 1. Tests zu Beginn (Stand der Pakete, vor jeder Änderung)

| Test | Ergebnis |
|---|---|
| `test_uix_contract` | 33/33 grün – auch `test_the_tree_shows_every_zone_and_marks_what_waits`, der im Archiv noch als rot vermerkt war (die `tree.js` im Kern-Paket ist schon nachgezogen) |
| `test_gateway_kmu_shell` | 1/1 grün |
| `test_gateway_menu_browser` | 1/1 grün |
| `test_uix_start` | **rot**: `start_sedra.sh` mit CRLF (Punkt 3) |
| `test_desk_gateway` | **rot** (2 Subtests): `gateway/tool.yaml` nennt `/api/guard/group` und `/api/guard/demo`, der Server hat sie nicht (Punkt 2) |

## 2. Priorisierung der offenen Punkte

| # | Punkt | Einordnung | Stand |
|---|---|---|---|
| 2 | Routen `/api/guard/group`, `/api/guard/demo` | **zuerst** – toter Knopf im Werkzeug, roter Test, Entscheidung liegt schon vor (Build 16: „`/api/guard/group` gibt es bewusst nicht – die Schärfe kommt aus dem Modus“) | **erledigt**, siehe 3.1 |
| 3 | `start_sedra.sh` CRLF | klein, sicher, roter Test | **erledigt**, siehe 3.2 |
| 4 | Shell zeigt keine Folieninhalte | hängt an Punkt 1: ohne Entscheidung zur Präsentations-Shell ist unklar, ob Folien in die Arbeits-Shell gehören oder in eine eigene | **offen**, Vorschlag unter 5 |
| 1 | Präsentations-Shell | Entscheidung beim Captain; Vorlagen jetzt vollständig vorhanden (V4a/V4b-Texte, Dashboard V4d, Designvorschlag V4.2 von Klaus) | **offen**, Vorschlag unter 5 |

## 3. Was geändert wurde

### 3.1 Schutz-Werkzeug (`tools/schutz`) – keine Server-Route erfunden, das Werkzeug an Build 16 angeglichen
- `tool.js`: Reiter „Regeln“ zeigt die Schärfe nur noch an (Pille *Scharf* / *Beobachtet* / *Immer scharf*) mit dem Satz, dass die
  Schärfe aus dem Modus des Projekts kommt und unter „Modus und Grenzen“ umgestellt wird. Umschalter, `setGroup`, `setAll`,
  Rückfragen entfernt. Reiter „Vorführung“ samt `demo`/`playView` entfernt (die Attrappen-KI der Lieferung ist nicht Teil von SEDRA;
  der Reiter erschien ohnehin nie). 293 → 226 Zeilen.
- `tool.css`: tote Regeln (`.t-schutz-seg`, `.t-schutz-cases`, `.t-schutz-play`) entfernt. `README.md` beschreibt den Stand.
- `tools/gateway/tool.yaml`: die zwei Routen aus der `api`-Liste gestrichen → `test_desk_gateway` grün.
- Menütext „Regeln · Schalter und Regelbuch“ → „Regelbuch und Schärfe“ (`cockpit/tree.js`, `gateway/nav.js`), weil es keine Schalter mehr gibt.
- **Neuer Vertragstest** `test_uix_contract.Files.test_every_api_route_a_module_names_exists_in_the_server`: jede
  `/api/…`-Zeichenkette in Shell oder Werkzeug muss im Server registriert sein. Vor der Änderung fand er genau die zwei Routen, sonst nichts.
- **Nebenfund, behoben:** `GET /api/gateway/vorgaben` stand im Server nur unter POST; das Werkzeug liest per GET (laut `tool.yaml`).
  Im Regeln-Bereich stand deshalb „Die gemerkten Vorgaben sind nicht lesbar: Diesen Weg gibt es nicht“. Jetzt auch als GET registriert
  (`uix_server.py`, read-only). Der bestehende Test `test_every_route_a_shipped_tool_lists_exists_in_the_server` prüft nur den Pfad,
  nicht die Methode – das hat ihn übersehen; ein methodengenauer Test wäre ein nächster Schritt.

### 3.2 Zeilenenden
- `start_sedra.sh`, `START_SEDRA.command`, `runtime/run_*.sh`, `runtime/setup_unix.sh` auf LF (alle hatten CRLF). `test_uix_start` 8/8 grün.
- Neue `.gitattributes` (nur `*.sh` und `*.command` → `eol=lf`), damit ein Windows-Checkout das nicht wieder umstellt.
  Bewusst nicht mehr: der Checkout hält alle Quellen in CRLF; eine allgemeine Regel würde jede Datei als geändert zeigen.

### 3.3 Bezeichnung GUPPI → SEDRA (nur sichtbare Texte, Rückfrage mit Klaus 19.10.)
- 155 Stellen in 51 Dateien unter `uix/` (js, yaml, html, md, css-Kommentare): alles, was Nutzer lesen – „Mit SEDRA sprechen“,
  „Auftrag an SEDRA“, „SEDRA fragen“, Sprecherzeile im Gespräch, Shell-Name „SEDRA XP“ (Kennung `guppi-xp` bleibt).
- Server-Texte, die in die Oberfläche gehen: `CHAT_SYSTEM` „Du bist SEDRA, der Assistent des Captains.“, Risiko-Satz
  „Neustart der SEDRA-Oberfläche“, Startzeile „SEDRA Desktop (UIX)“.
- **Unverändert:** Paketname `guppi_runtime`, Importe, Pfade (`GUPPI_OS`, `GUPPI_Architecture…`), Kennungen (`GUPPI_BUILT`,
  `X-GUPPI-Token`, `GUPPI_SECRET_`, `root.sedra…`, CSS-Klassen `guppi-…`), Tests/Benchmarks/Docs-Kommentare.
- Tests nachgezogen: `test_uix_shell_start` (Liste der Shell-Namen, Knopf „SEDRA fragen“), `test_uix_flows` („Auftrag an SEDRA“).

### 3.4 Shell gateway-kmu – ein Layoutfehler
- Die Kopf-Grafik (416×576 px, Breite 220 px) ragte ~60 px unter den Kopf in das Werkstück und verdeckte die Zeile
  „Kundenanfrage → … Kein Versand.“ Jetzt nimmt sie die Höhe des Kopfes (`height:calc(100% - 28px)`, `object-fit:contain`),
  Breite daraus, höchstens 220 px. Keine Farben, keine Hex-Werte.

### 3.5 Test robuster
- `test_uix_flows…switcher…`: wartete fest 2,5 s auf die Start-Shell; auf dem langsamen Rechner hier dauert der Wechsel 3–4 s.
  Jetzt `wait_for_selector('.st-head-text', 15 s)`. Kein Produktcode betroffen.

## 4. Tests am Ende
`test_uix_contract` 34, `test_gateway_kmu_shell`, `test_gateway_menu_browser`, `test_uix_start`, `test_uix_shell_start`,
`test_uix_flows`, `test_desk_gateway`, `test_desk_install`, `test_uix_server`, `test_uix_guppi_moves`, `test_content_guard`,
`test_gateway`, `test_uix_kommandodeck`: **282 Tests, grün bis auf den bekannten Umgebungsfehler** (`library_not_built`,
`skill_library_core/index.json` fehlt hier) und einen Skip. Alle Shell- und Werkzeugdateien ≤ 400 Zeilen, keine Hex-Farben außerhalb `tokens.css`.

## 5. Vorschlag zu den offenen Punkten 1 und 4 (Entscheidung beim Captain)

Klaus’ Designvorschlag V4.2 (19.10.) bestätigt die Richtung der Shell: Mitternachtsblau, Türkis, Bild rechts mit weichem Verlauf.
Die Werte liegen nah an den Tokens `--kmu-…` (Hintergrund `#080d24` statt `#0d174e`, Fläche `#11194b`, Linie `#2a3568`/`#313c68`,
Akzent `#50dfcf` statt `#53ddd0`, Untertitel `#aebde7` statt `#b4c2ec`). Eine Angleichung wäre eine Änderung in `tokens.css` allein.

Zwei Wege für die Folien:
- **A – eigene Shell `praesentation`** (Folien aus einer Datei, Timer, Sprechernotizen per Taste, „Demo“-Folie schaltet in die
  Shell `gateway-kmu` um). Trennt Vortrag und Arbeitsfläche sauber; die Shell `gateway-kmu` bleibt wie sie ist. Aufwand: eine Shell
  (≤ 400 Zeilen js + css), die Folientexte als `shell.yaml`-Daten oder eigene Datei im Shell-Ordner (der Server liefert nur js/css/json/svg/png/html).
- **B – Folien in die Shell `gateway-kmu`** als zuschaltbare Ebene über dem Werkstück. Weniger Dateien, aber die Shell wird größer
  und vermischt Vortrag und Arbeit.

Empfehlung: A. Nicht entschieden werden kann hier: Einsatzort der übrigen Folienbilder, Folienschrift (Lizenz), Demo-Adresse.
Keine Aussage zur Rechtskonformität; die B6-Cloud bleibt eine Simulation (steht so in den Folientexten V4.1).

## 6. Nachtrag 17:55 – Shell gateway-kmu: Bilder, Bedienung, Bewegung (Wunsch Klaus: „Look and Feel einer Hochklasse-Webseite“)

**Bilder** (Folienbilder, Lizenz laut Klaus geklärt; verkleinert und auf 256 Farben gebracht, damit sie klein bleiben):
- `kmu-hero.png` (Folie 11, Bogen mit Schild, 1280×720, 215 KB): rechts im Kopf, läuft mit einem weichen Verlauf in den
  Hintergrund (wie `pdfArt` im Designvorschlag V4.2). Ersetzt `kmu-grafik.png`.
- `kmu-glow.png` (Folie 4, die Kugel, 560 px, 123 KB): schwach (Opazität .32) hinter dem Werkstück, unten rechts, radial ausgeblendet.
- Die übrigen drei Folienbilder bleiben in `runtime/assets/kmu-praesentation/` unbenutzt (Einsatzort beim Captain).

**Aufbau:** Die Shell ist jetzt eine App, keine Seite: Kopf und Gespräch stehen, das Werkstück rollt dazwischen (`height:100vh`,
Werkstück `overflow:auto`). Rollt man im Werkstück, wird der Kopf kompakt (Titel und Ablauf in einer Zeile, zwei Schwellen gegen
Flackern) und wächst oben wieder. Das Gespräch nimmt seine Höhe aus `--talk-h` (Standard 160 px) und lässt sich am Griff des
Werkzeugs ziehen – vorher saß es unter der Seite und war ohne Rollen nicht zu sehen.

**Bedienung und Schaltflächen:** Eyebrow „B6 / SEDRA · Ein sicherer Weg zur KI“ über dem Titel. Der Ablauf ist ein Stepper:
nummerierte Glas-Pillen mit Verbindungslinien, der letzte Schritt („selbst entscheiden.“) in Akzentfarbe – weiterhin nur zum Lesen.
Die Schaltflächen des Vertrags (`.s-btn`) sind in dieser Shell Pillen mit Licht beim Zeigen, die erste Handlung des Werkstücks gefüllt;
Eingabefelder dunkel mit Akzentrand im Fokus; Rollbalken in den Shell-Farben. Alles über Tokens und `color-mix`, kein Hex.

**Bewegung** (nur `transform`/`opacity`, lange Wege; `prefers-reduced-motion` schaltet in `tokens.css` alles ab):
Bogen schwebt (22 s), Kugel atmet (11 s), Parallaxe mit der Maus über dem Kopf (`--kmu-px/--kmu-py`, `translate`-Eigenschaft,
getrennt vom `transform` der Animation), gestaffeltes Erscheinen von Marke und Ablauf beim Start, Puls am fünften Schritt,
wanderndes Licht auf der Gesprächskante. Im kompakten Kopf pausiert das Schweben.

**Abnahme:** `uix_check --shell gateway-kmu` **25/25** (vorher 23/29): der Ablauf trägt jetzt `data-tool` und `b` wie jedes
Instrument, und das Profil sagt `no_evidence` – Nachweise (`slot: nachweis`) gelten in dieser Shell als „nicht geprüft“ statt als
Fehler. Cockpit unverändert 29/31 (dieselben zwei Befunde wie im Ausgangsstand: `rahmen-probe`, Schutz ohne eigenen Reiter).
Tests: `test_uix_contract` 34, `test_gateway_kmu_shell`, `test_gateway_menu_browser`, `test_uix_shell_start` grün.
Dateien: `shell.js` 113 Zeilen, `shell.css` 217 Zeilen.

**Nicht gemacht:** das Entwickler-Archiv `entwickler_archiv_kmu_shell` ist nicht nachgezogen – Quelle ist jetzt das Kern-Paket.

## 7. Nachtrag 18:30 – Cockpit: optisch und funktionell aufgewertet, Charakter behalten (Wunsch Klaus)

**Befund zuerst:** Im gelieferten Stand fehlten in `shells/cockpit/shell.css` sämtliche Regeln für das Dock (`.dk-*`), die Palette
(`.pal*`) und das Menü „＋ Neu“ (`.ck-menu`). Die Reiter lagen als nackte Zeilen übereinander, „＋ Neu“ und „Teilen“ waren
unbeschriftete Kästchen, Baumzeilen liefen mit ihrem Zustand in einer Zeile zusammen, die Palette hatte keine Hervorhebung.
Das Bildschirmfoto `docs/shots/cockpit/shell.png` zeigt, wie es gemeint war – daran habe ich mich gehalten.

**Was jetzt gilt (nur `shell.css`, `dock.js` +4, `tree.js` +3 Zeilen; Werkzeuge unverändert):**
- Leiste: Instrumente geben nach statt überzuhängen (Abnahme „breite“), Werte mit Ellipse, Hinweiszelle gestrichelt rechts;
  ein Werkzeug im abgeschotteten Rahmen (iframe) bekommt die Zelle, nicht 300×150; ein Instrument, das die Zelle zentriert nutzt,
  wird rechts beschnitten, nie links (der Guppy stand links abgeschnitten).
- Baum: Titel und Zustand untereinander, aktive Zeile mit Akzentstreifen und Hauch von Akzent (`color-mix`), klebende Gruppenköpfe,
  und der Baum rollt zur markierten Zeile (`scroll-margin`, damit sie nicht unter dem Kopf liegt).
- Werkbank: Reiterzeile mit Akzentkante am aktiven Reiter, Schließkreuz erst beim Zeigen, mittlere Maustaste schließt, das Rad rollt
  die Reiterreihe; „＋ Neu“ als Knopf, „Teilen“ als Kachel; Handlungszeile mit Titel links, Handlungen rechts; geteilte Werkbank
  mit Trennlinien; Nachweisspalte klebt beim Rollen.
- Palette und Menü: Feld, Treffer mit Hervorhebung, kurzes Aufklappen (`prefers-reduced-motion` schaltet ab). Die Variablen stehen
  auch auf `.pal`/`.ck-menu`, weil beide am `body` hängen, nicht in `.ck`.
- Schrift nur in Token-Stufen (die Pixelwerte aus Build 13, „nachziehen, wenn angefasst“, sind damit nachgezogen); kein Hex.
- Beide Themen (Nacht, Klar) geprüft.

**Abnahme:** `uix_check --shell cockpit` 29/31 – dieselben zwei Befunde wie im Ausgangsstand: Instrument `rahmen-probe` ohne Wert
(Prüfwerkzeug der Stufe C, CAPTAIN; laut seinem README „kann nach der Abnahme von C5 ausgeblendet werden“) und `schutz` ohne eigenen
Reiter (das Cockpit bettet ihn ins GateWay ein – Build 19; die Abnahme erwartet noch die Spalte daneben). `minimal` 29/31 unverändert.
Tests: `test_uix_contract` 34, `test_uix_flows`, `test_gateway_menu_browser`, `test_uix_shell_start`, `test_gateway_kmu_shell`,
`test_desk_gateway`, `test_uix_start` – 78 grün.

**Offen (klein):** die Abnahme für `schutz` im Cockpit an Build 19 anpassen (eingebettet statt Spalte) und entscheiden, ob
`rahmen-probe` in der Leiste bleibt – beides Hauptsitzung.

## 8. Nachtrag 21:40 – Baum und Leiste geprüft; Paperclip für mehrstufige Arbeit (Use Case: 3D-Assets über einen Etsy-Shop)

### 8.1 Baum und Leiste des Cockpits, inhaltlich
- **Leiste, Instrument „Aufgaben“:** „2 läuft · 0 wartet“ → „2 laufen · 0 warten auf dich“ (Plural je Zahl, `strip_view`); die Zelle wird
  gelb, sobald eine Aufgabe auf den Captain wartet. Die übrigen Instrumente stimmen (Zustand, Modell, Online-KI, GPU, Entscheidungen, Modus).
- **Baum:** „Master-Chat“ stand zweimal unter Werkstatt (das Gespräch unten und das Werkzeug `entwurf`) – die zweite Zeile heißt jetzt
  „Entwurf · Gespräch mit Befehlen und Vorschau, groß“. Leere Zustandszeilen bekommen einen Satz (Logbuch, Guppy-Meter, Hardware,
  Maschinenraum). „Projekt project“ ist der Name des Prüfprojekts, kein Fehler.
- Bleibt: die Rahmen-Probe in der Leiste (siehe Abschnitt 7).

### 8.2 Ein Ziel ist ein Weg in Stufen (Kern)
- `desk/intents.py`: ein Vorhaben trägt `stufen` (Name, Satz, die Aufgaben daran; höchstens 12), `check_stufen` prüft, `stufen_of`
  leitet je Stufe den Zustand aus ihren Aufgaben ab (offen · in Arbeit · wartet auf dich · fertig) – die erste nicht fertige Stufe ist die
  aktuelle. `attach(…, stufe=i)` hängt eine Aufgabe an die Stufe und an das Vorhaben.
- `desk/vorhaben_vorlagen.py`: Vorlagen, nur Text – „3D-Assets über einen Etsy-Shop vertreiben“ (8 Stufen: Nische → Modellieren →
  Prüfen/Export → Vorschaubilder → Listing-Texte → Shop und Preise → Veröffentlichen → Betreuen/Auswerten; jede Stufe sagt, was
  herauskommen soll) und „Kundenanfrage beantworten“ (der Weg des KI Gateway, 4 Stufen). Rechts-, Steuer- und Plattformfragen stehen
  darin als „prüfen“, nicht als erledigt.
- `uix_server.py`: `POST /api/intent/create` nimmt `vorlage` oder `stufen`; `GET /api/intent/vorlagen` (read-only); das Verb
  `aufgabe_machen` nimmt `args.stufe` – der Auftrag an SEDRA ist dann „<Vorhaben> – Stufe n von m: <Name>. <Satz>“, die Aufgabe hängt
  an der Stufe; `_intent_object` liefert `stufen`, `vorlage` und einen Satz „k von m Stufen fertig · jetzt: …“. Audit wie bisher
  (`INTENT_CREATED` mit Stufenzahl, `INTENT_TASK_CREATED` mit Stufe). Ohne Stufen verhält sich alles wie vorher.
- Tests: `test_desk_intent_stufen` (6, je Zusage einer, bis zum Verb-Weg über den Hub); `test_desk_install.Intents` unverändert grün.

### 8.3 Werkzeug „Vorhaben“ (`tools/intent`, 207 Zeilen)
- Sammlung: je Vorhaben Zustand als Pille und ein Fortschrittsbalken, ein Segment je Stufe; auf einer Übersicht (`kompakt`) ohne Formular.
- Ein Vorhaben: die Stufen als Weg (Linie, Nummer, Name, Zustand, Satz, die Aufgaben daran mit Phase auf Deutsch); an jeder nicht
  fertigen Stufe „Aufgabe daraus machen“, an der aktuellen hervorgehoben; danach öffnet die Aufgabe. Die Handlungszeile der Shell
  sagt „Aufgabe daraus machen (Stufe n)“ und meint die aktuelle Stufe.
- Anlegen: Titel, Satz, **Vorlage** (Auswahl füllt Titel und Satz, zeigt die Stufen vorab). Der erste Knopf bleibt „Vorhaben anlegen“
  (`test_uix_flows` klickt ihn).
- **Fehler gefunden und behoben:** das Werkzeug ist ein Objekt für alle Container; die Antwort der Sammlung kam nach dem Öffnen
  eines Vorhabens an und übermalte dessen Seite. `refresh` zeichnet nur noch in den Container, für den es gefragt wurde.

### 8.4 Paperclip
- Dashboard: **„Ziele“ als erste, breite Karte** (Vorhaben mit Stufen, kompakt) über Posteingang, Organigramm, Issues – die Firma
  arbeitet an Zielen entlang, jede Stufe wird ein Issue. `arbeitsplatz.yaml` kennt Ziel und Stufe (SEDRA antwortet daraus).
- Die Rahmen-Probe-Kachel im abgeschotteten Rahmen bleibt in ihrer Kachel (vorher 300×150 über die Kacheln hinweg).
- Use Case geklickt: Ziele → Vorlage „3D-Assets …“ → anlegen → Stufe 1 „Aufgabe daraus machen“ → Aufgabe (bereit, Schritt 1 von 1,
  Live und Kosten daneben) → zurück im Ziel: Stufe 1 „in Arbeit“, Balken grün, Issues zeigen die Aufgabe, Dashboard zeigt den Stand.
  Keine Seitenfehler. Bilder: `uc_ziel.png`, `uc_dashboard.png`, `uc_issues.png`.
- Abnahme `uix_check --shell paperclip` 30/31 – wie im Ausgangsstand (Rahmen-Probe). Tests: 108 grün über Vertrag, Paperclip,
  Klick-Wege, Stufen, Install, Objekte, GateWay-Menü, KMU-Shell.

**Nicht gemacht / beim Captain:** Stufen von Hand hinzufügen oder umsortieren (heute nur über Vorlage oder `stufen` im Aufruf);
Issues als Kanban je Stufe (das Werkzeug `task` zeichnet die Liste); Routinen (bewusst nicht da, Build 24).

## 9. Nachtrag 22:20 – Der Planungstisch: eine Arbeitsumgebung für KI-Assistenten in Paperclip (Wunsch Klaus)

**Was es ist.** In Paperclip links unter „Assistenten → Planungstisch“ (auch per Strg+K „Planungstisch“, in jeder Shell als Objekt
`planung:tisch`): links das Gespräch mit einem Assistenten in einer Rolle (Planer voreingestellt; Rechercheur, Entwickler, Prüfer,
Dokumentar … – die Rollen aus den Rezepten, wie in der Besatzung), rechts der Tisch mit den **Vorschlägen** als Karten – ein Ziel mit
seinen Stufen, ein Auftrag, eine Handlung – und darunter **Heute festgelegt** mit Sprung zum Objekt. **Übernehmen** legt an,
**Verwerfen** wirft weg. Nichts läuft ohne den Klick des Captains; der Assistent kann nichts selbst anlegen.

**Wie es gebaut ist (am Bestand von Build 19 „SEDRA bewegt sich“):**
- `chat_tools.py`: `propose_intent` nimmt jetzt `stufen` (2–12 Namen in Reihenfolge); neu `propose_task` (ein Auftrag mit klarem
  Ergebnis). Beides sind Vorschläge (`ui_actions`), wie bisher. Neu `PLANUNG_TOOLS` – die Werkzeuge des Planens – und `ChatTools(hub, names)`.
  Ort `planung` in `PLACES` (und in `ui/places.js`, ein Test vergleicht beide).
- `uix_server.py`: `POST /api/planung/reply` → `planung_reply` → `chat_reply(modus='planung', rolle)`: derselbe Weg (Control Master,
  Audit, Inhaltsschutz), nur der Systemsatz der Rolle (`PLANUNG_SYSTEM`, `PLANUNG_ROLLEN`) und die Werkzeuge des Planens. Audit
  `UIX_CHAT_TOOLS` trägt `modus`. Ohne Modell: `no_model` wie im Gespräch.
- Werkzeug `tools/planung` (201 Zeilen, CORE): Routen `/api/planung/reply`, `/api/intent/create` (mit Stufen), `/api/chat` (Auftrag =
  Aufgabe, geplant, nicht ausgeführt), `/api/actions`, `/api/models` (Rollen), `/api/objects`. Ohne Modell bleibt der Tisch nutzbar:
  „Als Ziel“ / „Als Auftrag“ machen aus dem Satz im Feld einen Vorschlag, den der Captain übernimmt. Gespräche werden nicht gespeichert.
- `desk/gateway.py`: `planung` in `OBJECT_TYPES` (im Paket gibt es keine Privatsprache). Minimal-Shell: ein Zeichen für den Ort.
- Gespräch (`tools/talk`, exakt 400 Zeilen): „Als Vorhaben anlegen“ reicht Stufen weiter; neu „Als Auftrag anlegen“ (`propose_task`).
- Paperclip: Navigation „Assistenten · Planungstisch“, `arbeitsplatz.yaml` kennt den Ort (SEDRA antwortet daraus).

**Prüfung:** `test_uix_planung` (3): Vorschläge tragen Stufen, `propose_task` ist nur ein Vorschlag; Planungsmodus hat die Rolle im
Systemsatz und nur die Werkzeuge des Planens (Fake-Modell); im Browser (Paperclip) macht ein Fake-Modell einen Vorschlag mit vier
Stufen → „Übernehmen“ → das Ziel steht mit genau diesen Stufen; „Als Auftrag“ → Aufgabe „bereit“. 244 Tests grün über Vertrag,
Shells, Klick-Wege, Desk. Abnahme: das Werkzeug `planung` in allen vier Shells „ok“; Befunde wie zuvor (Rahmen-Probe, Schutz-Spalte).
Bilder: `pt1_vorschlag.png`, `pt2_festgelegt.png`.

**Beim Captain:** ob der Planungstisch auch im Cockpit-Baum stehen soll (heute dort über Strg+K); ob der Assistent beim Übernehmen
eines Ziels gleich die erste Stufe als Aufgabe vorschlagen soll (heute: ein Klick im Ziel).

## 10. Nachtrag 23:10 – Shell „Fisch“ mit drei Werkzeugen aus VoiceBrief, LocalScribe und Translator Fisch (Wunsch Klaus)

**Was die drei Pakete sind:** *VoiceBrief* (Entwickler-Übergabe 08.10.): ein lokaler Audio-to-Knowledge-Workspace in Rust/WebView2
für Windows – Aufnahme (WASAPI), Session-Zustandsautomat, Whisper lokal, Privacy-Gate, Review → Golden Record, Export; geliefert
sind nur Dokumente (Status, ADRs, Integrationsprüfung „Translator Fisch“). *LocalScribe* (Teilnehmerpaket 21.09.): ein macOS-
Transkriptionskern in Swift – Datei-Import, Voz-Modell, Suche, Export TXT/SRT/VTT/JSON, Privacy-Diagnose; Quellcode geliefert, läuft
nur mit Xcode und Apple Silicon. *Translator Fisch* (Konzept v0.1): ein kleiner Chatbot – rollenbasiertes Übersetzen, News-Modus mit
Profil und Morning Brief, Goldfischglas mit Wolke und Blasen; nur Konzept, kein Code.

**Was daraus in SEDRA wurde – ehrlich, nach der Klassifikation der VoiceBrief-Prüfung:**

| Baustein | Klasse | In SEDRA |
|---|---|---|
| Goldfischglas, Wolke, Blasen, Modi, Fisch-Zustände (Konzept) | NEW | Shell `fisch`: CSS-Zeichnung (keine Bilddatei, keine fremde Figur), Tokens `--fisch-…` hell/nachts, drei Modi, Modus je Browser gemerkt, Gespräch als Schublade |
| Translator-Skill (PROMPT_SPEC A, Rollen, Regeln) | REUSE der Regeln | `fisch/uebersetzer.py` + Werkzeug `uebersetzer`: Systemsatz nach Spec, festes Antwortformat, gelesen statt geraten; Modellaufruf durch den Control Master |
| News-Skill (PROMPT_SPEC B, Profil, vier Ebenen) | ADAPT | `fisch/nachrichten.py` + Werkzeug `nachrichten`: Profil im Projekt, Brief **nur aus gegebenen Quellen** (kein Netz in der Runtime); Quelle ohne Namen → „unsicher“; keine Mindestmenge |
| Transkript, Exporter, Cue-Gruppierung, Suche (LocalScribe) | REUSE der Form | `fisch/transkripte.py`: Cues mit Zeiten, Export TXT/SRT/VTT/JSON in LocalScribe-Form, Suche nach ganzen Wörtern in Reihenfolge |
| Record-Regeln (VoiceBrief ADR-009/011/014/008) | REUSE | Versionen additiv; Export ändert den Record nie; Mapping getrennt (`T-….mapping.json`), nie im Export; Golden Record erst nach „geprüft“; Platzhalter heißen so |
| Pseudonymisierung | REUSE aus SEDRA | `core/b6core` wie im GateWay (kein Modell) |
| STT (Whisper/Voz), Aufnahme (WASAPI), Voz-Sprachwächter | DEPRECATE hier / NEW anderswo | kein Provider in dieser Runtime – `transkribieren()` sagt es; die Sprache ist eine Angabe des Captains (wie bei LocalScribe vor dem Modell) |
| Netz-Recherche, Dubletten über Quellen hinweg | nicht gebaut | die Stelle ist `fisch/nachrichten.py`; die Lese- und Profilregeln bleiben |

**Dateien:** `fisch/__init__.py`, `uebersetzer.py`, `nachrichten.py`, `transkripte.py`, `hub.py` (Routen `/api/fisch/*`, elf Stück, am
Hub als `hub.fisch`); Werkzeuge `tools/uebersetzer` (103 Zeilen), `tools/nachrichten` (157), `tools/transkript` (178); Shell
`shells/fisch` (shell.js 190, shell.css 118, `arbeitsplatz.yaml`, `preview.png`); Objekttypen `uebersetzung`, `nachrichten`,
`transkript` in `desk/gateway.py`; Orte „Übersetzer“ und „Transkripte“ (Strg+K, Gespräch; `ui/places.js` und `chat_tools.PLACES`),
Zeichen in der Minimal-Shell; Profil `fisch` in `uix_check`.

**Prüfung:** `test_fisch_kern` (9: Lesen der Übersetzung, unsichere Quelle, SRT rein/raus, Suche, Record-Versionen/Freigabe/Export,
Hub-Weg ohne und mit Fake-Modell, Import → Pseudonymisieren → Freigeben → Export), `test_uix_shell_fisch` (2: kein Hex, je Modus
genau ein Werkzeug; Browser: Wolke → Übersetzung mit Fake-Modell, Transkript importieren → aus der Wolke suchen → Pseudonymisieren →
prüfen → Golden Record, Modus übersteht Neuladen, Gespräch als Schublade). Abnahme `uix_check --shell fisch` **32/32**; die anderen
Shells wie zuvor (die neuen Werkzeuge „ok“ in allen). 201 Tests grün über Vertrag, Shells, Desk, Fisch.

**Gefunden beim Bau:** `sedraDom.el(tag, cls, text)` nimmt nur Text, keine Kinder – zwei Werkzeuge hatten Kinder übergeben
(Selects waren unsichtbar); und ein Werkzeug darf keine `@keyframes` tragen (Vertrag: nur `.t-…`-Selektoren) – Bewegung gehört der Shell.

**Beim Captain:** ob der Fisch auch ohne Thema „Klar“ hell sein soll (heute: nachts dunkler Raum, leuchtendes Glas); Lizenz der
Translator-Fisch-Texte (Konzept ohne Lizenzangabe); ob ein STT-Provider angebunden wird (Whisper lokal wäre der VoiceBrief-Weg).

## 11. Nachtrag 23:30 – Sprache als Kern: Rekorder für jede Shell, WhisperX als Provider, SEDRA liest Erkenntnisse (Wunsch Klaus)

**Wunsch:** „baue die Fisch-Shell weiter aus mit dem SEDRA-KI-Zugang; kann eine Voice-Recorder-App umgesetzt werden“ – und dann:
„können wir das in den Kern aufnehmen, damit alle Shells auf die Spracherkennung zugreifen können“; Hinweis auf **m-bain/whisperX**
(GitHub: Whisper mit faster-whisper-Backend, Wort-Zeitstempel über wav2vec2-Alignment, VAD gegen Halluzinationen, Sprecher-Trennung
über pyannote; BSD-2; `pip install whisperx`; läuft auch CPU-only mit `--compute_type int8`).

**Was gebaut wurde – als Kern, nicht als Fisch-Teil:**

| Baustein | Wo | Was |
|---|---|---|
| Paket `sprache/` | `sprache/stt.py` | Provider-Erkennung auf dem Rechner (`whisperx` bevorzugt, sonst `whisper`; ffmpeg muss da sein), Einstellung `local_config/sprache.stt.json` (modell, geraet, rechenart, befehl), Kommandozeile mit fester Sprache und SRT-Ausgabe, Lauf als Unterprozess mit Zeitlimit. Ohne Provider: benannter Platzhalter **mit Installationsbefehl** – nichts wird erfunden (VoiceBrief ADR-008) |
| | `sprache/aufnahmen.py` | Record je Aufnahme (`<Projekt>/sprache/aufnahmen/<id>.webm` + `<id>.json`): Status laeuft → fertig, Stücke base64 **je unter dem 1-MiB-Request-Limit** des Servers (das Limit bleibt), Größe bis 200 MB, Abspielen bis 24 MB als base64 (darüber nur der Pfad), leere Aufnahme wird kein Record, Löschen nicht während einer Transkription |
| | `sprache/hub.py` (`hub.sprache`) | Routen `GET /api/sprache/status`, `GET /api/sprache/aufnahmen`, `POST /api/sprache/aufnahme` (abspielen), `…/beginnen`, `…/stueck`, `…/beenden`, `…/loeschen`, `…/transkribieren`. Transkription **im Hintergrund** (Thread, Stand im Record: offen · laeuft · fertig · fehler); das Ergebnis wird ein Transkript-Record mit Herkunft `stt:whisperx`; mit `text` wird die **Abschrift von Hand** ein Transkript mit Herkunft `manuell`. Audit ohne Inhalt |
| Kern-Helfer | `ui/sprache.js` (in `desk.html`) | `sedraSprache.aufnehmen(ctx.api, {titel, sprache, onStand})` → Griff mit pause/weiter/stop/abbrechen; MediaRecorder in 4-s-Stücken, Pegel über AudioContext, Stücke nacheinander über die `api()` des Werkzeugs (kein eigenes fetch). Jedes Werkzeug jeder Shell bekommt damit ein Mikrofon mit wenigen Zeilen; die Routen muss es im Manifest nennen (§6) |
| Werkzeug `rekorder` | `tools/rekorder` (199 Zeilen) | zeichnet den Typ **`aufnahme`**: Auskunft zum Provider (grün bereit / gelb mit Befehl), Pult (Titel, Sprache, runder Knopf, Uhr, Pegel, Pause/Weiter/Verwerfen), Aufnahmen als Karten (Abspielen, „Sprache → Text (whisperx)“ nur wenn bereit, „Transkript öffnen“, Löschen, Abschrift von Hand); fragt alle 3 s nach, solange eine Transkription läuft |
| Für jede Shell | `desk/gateway.py`, `ui/places.js`, `chat_tools.PLACES`, `minimal/icons.js`, `cockpit/tree.js`, `paperclip/nav.js` | Objekttyp `aufnahme`; Ort **„Rekorder“** (Wörter: rekorder, aufnahme, mikrofon, diktat …) – „öffne den Rekorder“ im Gespräch geht in Cockpit, Paperclip, Minimal, Fisch und KMU; Zeile „Rekorder“ und „Transkripte“ im Cockpit-Baum (Werkstatt), „Rekorder“ in der Paperclip-Navigation (Assistenten); Mikrofon-Zeichen |
| Fisch | `shells/fisch` | vierter Modus **Aufnahme** (`aufnahme:rekorder`); der Satz aus der Wolke wird der Titel im ersten Feld der Blase (kein neues Mounten, das Pult bleibt); die Shell kennt das Werkzeug weiter nicht beim Namen |
| SEDRA-KI-Zugang | `fisch/erkenntnisse.py`, `POST /api/fisch/transkript/erkenntnisse`, Werkzeug `transkript` (230 Zeilen) | **„Erkenntnisse mit SEDRA“**: das lokale Modell liest die Fassung in vier Blöcken (Zusammenfassung · Entscheidungen · offene Fragen · Aufgaben), gelesen statt geraten, **an die Fassung gebunden** (VoiceBrief: Wissen hängt an der Eingabe-Version – eine neue Fassung macht sie „aus Fassung n“, „Neu lesen“ bindet neu); je Aufgabe **„Als Auftrag anlegen“** (POST /api/chat → Aufgabe, geplant, nicht ausgeführt, wie im Gespräch); **„An den Übersetzer“** reicht die Zusammenfassung als Wolke weiter. Ein Objekt `transkript:T-…` öffnet den Record direkt (so führt der Rekorder her) |

**Was bewusst nicht gebaut wurde:** Sprecher-Trennung von WhisperX (pyannote: Hugging-Face-Token, Modellvertrag, Netz beim ersten
Laden) – Entscheidung des Captains; Browser-Spracherkennung (`SpeechRecognition` schickt in Chrome die Stimme an Google – keine
lokale Lösung, deshalb nicht angeboten); ein Mikrofon-Knopf im Gespräch (`talk/tool.js` steht auf genau 400 Zeilen – ein Diktat
dort wäre ein eigener Schritt mit Umbau).

**Prüfung:** `test_sprache_kern` (8: Platzhalter mit Befehl, ffmpeg-Fall, whisperx vor whisper und die Kommandozeile, Einstellung
mit Rückfall, Stücke unter dem Limit / leere Aufnahme / Löschen, Hub ohne Provider → Abschrift von Hand, Hub mit Provider-Attrappe →
Transkript `stt:whisperx` und ein Provider-Fehler landet im Record, Erkenntnisse in vier Blöcken und an die Fassung gebunden),
`test_uix_rekorder` (2: Rekorder ist ein Ort jeder Shell und `ui/sprache.js` ist Vertragscode; Browser mit **Fake-Mikrofon** in
Chromium: Modus Aufnahme → Wolke wird Titel → aufnehmen 5 s → Pause/Weiter → Stopp → Datei im Projekt, Stücke angekommen → ohne
Provider kein Knopf, der so tut → Abschrift von Hand → „Transkript öffnen“ wechselt den Modus → Erkenntnisse aus dem Fake-Modell
mit „Als Auftrag anlegen“). Abnahme `uix_check`: fisch **33/33**, gateway-kmu 30/30, cockpit 34/36, paperclip 35/36, minimal 34/36
(dieselben drei Altfunde wie in §4; `rekorder` „ok“ in allen fünf). `test_fisch_kern` fragt den Kern jetzt ohne Provider, damit
der Test auch auf einem Rechner mit whisperx grün bleibt.

**So wird es auf dem Rechner lebendig:** `pip install whisperx` (und ffmpeg), SEDRA neu starten – die Auskunft im Rekorder wird grün,
„Sprache → Text (whisperx)“ erscheint; erste Transkription lädt das Modell `small` (etwa 500 MB, einmalig). Für eine Grafikkarte:
`local_config/sprache.stt.json` mit `{"geraet": "cuda", "rechenart": "float16", "modell": "large-v3"}`.

**Beim Captain:** Sprecher-Trennung ja/nein (Token, Netz); ob das Standardmodell `small` reicht (Deutsch: `medium` ist deutlich
besser, aber langsamer auf CPU); ein Diktat-Knopf im Gespräch.

## 12. Nachtrag 23:50 – Verbindungsprüfung und Entwickler-Archiv Build 25 (Wunsch Klaus)

**Geprüft, statisch über den ganzen Baum (`verbindungen.py`, Ergebnis im Archiv-Lies-mich):** jede Route eines Manifests existiert
im Server (154 Routen); jedes Werkzeug ruft nur Routen seines Manifests – **neuer Vertragstest**
`test_every_route_a_tool_calls_stands_in_its_own_manifest`; jeder Objekttyp, den eine Shell öffnet (`type: '…'` in jeder
Shell-Datei), und jeder Ort im Gespräch hat ein Werkzeug (23 von 24 Typen; `routine` ohne, gewollt seit Build 24) und ein Zeichen;
`ui/places.js` und `chat_tools.PLACES` sind gleich (19 Orte); jedes Skript in `desk.html` existiert; jede Route am Hub zeigt auf
eine Methode (auch `hub.fisch.*`, `hub.sprache.*`); alle Python-Module importieren (DevVM-Module brauchen `dulwich`, steht in
`requirements.txt`); `compileall` sauber.

**Ein Befund, behoben:** das Gespräch rief für „lade …“ `/api/models` und `/api/model/load`, die nicht in seinem Manifest standen –
der Server antwortete 403, der Befehl war tot. Jetzt liest es die Modelle read-only über `/api/objects {type: model}` und lädt über
das Verb „laden“ (`/api/actions`), wie jeder Werkzeugknopf; die Modellroute bleibt dem Gespräch verwehrt (`test_desk_gateway`
will das so). Im Browser geprüft: „lade qwen“ → „Kein Modell gefunden“, „lade coder“ → Rückfrage → „ja“ → ehrliche Antwort
(hier: „nicht einsatzbereit – Werkstatt: Datei hinterlegen“). `talk/tool.js` bleibt bei 400 Zeilen.

**Archiv:** `entwickler_archiv_sedra_build25_2026-10-19.zip` – `sedra/` (Build 25 nach `make_build.py`, frische `PRUEFSUMMEN.sha256`,
CHANGELOG-Eintrag, 17 Bildschirmfotos unter `docs/shots/build20/`), `assets/` (KMU-Shell-Archiv, die drei Quellpakete VoiceBrief ·
LocalScribe · Translator Fisch), `patches/` (Build 24 → 25, 152 Dateien), `00_LIES_MICH.md`. Aus einem frischen Entpacken geprüft:
Prüfsummen stimmen, Vertrag/Gateway/Sprache/Rekorder-Tests grün.
