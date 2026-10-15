# Spec: Shell E (Minimal) und das Werkzeug „Module“ (14.10.2026)

Zwei Stücke, die zusammengehören: die **zweite Shell** beweist, dass der Werkzeug-Vertrag trägt, und das **Werkzeug Module**
macht aus dem Einbau, der heute nur als Route existiert, etwas, das der Captain anfassen kann. Diese Spec wird **vor** dem Bau
geschrieben, weil beide Stücke Löcher im Vertrag sichtbar machen – und ein Loch, das man erst beim Coden sieht, wird meist
zugeklebt statt geschlossen.

Gebaut wird in dieser Reihenfolge: **erst E, dann Module** (Entscheidung des Captains). Was E über den Vertrag lernt, steht
danach in §4 und geht ins Werkzeug Module ein.

---

## 1. Was Shell E beweisen soll

> Dieselben Werkzeuge, eine andere Form, **keine Zeile an einem Werkzeug geändert.**

Das ist die Prüfung. Muss ein Werkzeug angefasst werden, damit E funktioniert, ist das **ein Mangel des Vertrags** und gehört in
den Vertrag – nicht in die Shell. Jeder solche Fall wird in §4 aufgeschrieben, auch wenn er klein ist.

### 1.1 Die Form (Entwurf `docs/shots/uix2/uix2_E_minimal.html`)

Ein Schreibtisch statt eines Cockpits: oben eine Menüleiste, darauf freie Fenster, unten eine Ablage, rechts oben die
Entscheidung. Kein Baum, keine Reiter, keine zwei Spalten.

| Zone | Was dort steht | Woher es kommt |
|---|---|---|
| **Menüleiste** (26 px) | GUPPI-Marke, fünf Menüs, rechts die Instrumente | Instrumente sind Werkzeuge der Art `instrument` mit `update(reading)` aus `GET /api/strip` – **genau wie im Cockpit** |
| **Fenster** (frei, ziehbar) | je ein Objekt; im Körper das Werkzeug, das es zeichnet | `ctx.tools.for(type)` |
| **Umschalter** im Fenster | `inhalt` zuerst, dann die `nachweis`-Werkzeuge | `manifest.slot` – dieselbe Unterscheidung wie die zwei Spalten des Cockpits, nur anders dargestellt |
| **Gespräch** | ein eigenes Fenster, das sich **nicht schließen lässt** | das Werkzeug `talk` (Regel 1: ein Eingabefeld) |
| **Ablage** (unten) | Sammlungen: Aufgaben, Vorhaben, Projekt, Werkstatt, Besatzung, Bibliothek, Logbuch | feste Objekte, keine Werkzeugnamen |
| **Entscheidungskarte** (rechts oben) | was wartet, mit seinen Wegen | `GET /api/decisions`, Antwort über `POST /api/decisions/answer` |

### 1.2 Die Entscheidungen, die diese Form erzwingt

1. **Ein Fenster zeigt immer nur ein Werkzeug.** Im Cockpit stehen Werkstück und Nachweise nebeneinander; in einem 760-px-Fenster
   geht das nicht. Also: Umschalter, und beim Umschalten wird das alte Werkzeug **ge-unmountet**, nicht versteckt. Das ist die
   härtere Prüfung für den Vertrag – `unmount()` wird hier dauernd gerufen, im Cockpit selten.
2. **Das Gesprächsfenster hat keinen Schließknopf.** Ein geschlossenes Gespräch wäre eine Shell ohne Eingabefeld. Lieber ein
   Fenster, das bleibt, als eine Regel, die man wegklicken kann.
3. **Strg+K öffnet das Menü „Werkzeuge“ mit Suchfeld** – keine zweite Palette. Die Palette des Cockpits ist Cockpit-Code
   (145 Zeilen); E darf sie nicht erben, sonst beweist E nichts.
4. **Kein Baum.** Navigation läuft über Ablage, Menü und Fensterliste. Damit fällt auf, was der Baum im Cockpit leistet – und
   ob ein Werkzeug sich heimlich darauf verlässt.
5. **Layout gehört der Shell**: `localStorage['sedra.minimal.windows']` (Objekt + Rahmen je Fenster). Daten gehören der Runtime.
6. **Die Entscheidungskarte ist kein zweiter Ort.** Sie zeigt, was `GET /api/decisions` sagt, und antwortet über dieselbe Route
   wie jeder Knopf im Werkzeug (Regel 2). Sie entscheidet nichts selbst.

### 1.3 Was E **nicht** tut

- Kein Werkzeug beim Namen kennen – mit der einen Ausnahme `talk`, die der Vertrag selbst nennt (die Vorlage tut dasselbe).
- Kein eigener Zugriff auf Daten eines Werkzeugs; nur `el` und `ctx` hinein, `unmount()` hinaus.
- Keine Farbe ohne Token, kein Stil außerhalb von `.sh-min*`, ≤ 400 Zeilen je Datei, keine Zeile im HTML.

### 1.4 Dateien

```
uix/shells/minimal/
  shell.yaml     Manifest: id, provides [menubar, windows, talk, notify], api (inkl. der Routen, die die Shell selbst ruft)
  shell.js       registerShell, Start, Verdrahtung, decide(), notify()
  windows.js     Fenster: öffnen, fokussieren, ziehen, Größe, Umschalter, Handlungen, Layout merken (reine Geometrie: placeBox/clampBox)
  menubar.js     Menüs (Ablage · Aufgabe · Werkzeuge · Fenster · Hilfe) und die Instrumente rechts
  shelf.js       die Ablage unten
  shell.css      nur .sh-min*
  README.md      wofür diese Shell da ist und was sie bewusst nicht kann
```

### 1.5 Abnahme (hier wird der Vertrag wirklich geprüft)

`benchmarks/uix_check.py` ist heute **Cockpit-förmig**: die Prüfungen suchen `.ck-strip`, `.dk-tab`, `.pal-box`. Für eine zweite
Shell wird daraus:

- `--shell <id>` setzt die Shell im Prüfprojekt (`uix.yaml`) und prüft genau diese.
- **Shell-unabhängige Prüfungen** (gelten für jede Shell): `load`, jedes Werkzeug (Container gefüllt, Text, Handlungen,
  Absenderkopf bei jedem Aufruf), `unmount`, `talk` (das sind Selektoren des *Werkzeugs*, `.t-talk-*`, also shell-unabhängig),
  `console`, `allowlist`, `retro`.
- **Shell-eigene Prüfungen** stehen als Profil **im Prüfwerkzeug**, nicht in der Shell: Zonen, wie man ein Objekt öffnet, wo der
  Container liegt, ob das Layout ein Neuladen übersteht. Zwei Profile: `cockpit` und `minimal`.
  *Begründung:* Eine Shell, die ihre eigene Prüfung mitbringt, prüft sich selbst – das ist keine Abnahme.
- Ziel: `uix_check --shell minimal` sagt `result ok`, und `uix_check` (Cockpit) bleibt bei 26/26.

Dazu ein Test, der beide Shells startet und vergleicht, **dass dieselben Werkzeuge geladen werden** – unterschiedlich dargestellt,
aber dieselbe Liste.

---

## 2. Das Werkzeug „Module“

Heute gilt: die Installation ist fertig und gehärtet, aber **kein Werkzeug ruft sie** (geprüft: in der ganzen Oberfläche greift
nichts auf `/api/uix/install` zu). Einbauen geht nur als HTTP-Aufruf von Hand. Das Werkzeug schließt das.

### 2.1 Was es zeigt

| Abschnitt | Inhalt |
|---|---|
| **Aktive Shell** | welche läuft, welche es sonst gibt, mit einem Satz Beschreibung |
| **Werkzeuge** | je Modul: Name, `id`, Herkunft (Paket / eigener Ordner), Vertrauen, Slot, Routen, an/aus |
| **Abgelehnt** | was nicht geladen wurde – mit dem Grund im Klartext (`id_must_match_folder`, `needs_ui_not_met`, …) |
| **Vorlagen** | die beiden `_template`-Ordner mit dem Weg „kopieren, umbenennen, prüfen“ |

### 2.2 Verben (jedes mit seinem Weg)

| Verb | Weg | Freigabe |
|---|---|---|
| **Modul vorlegen …** | Ordner angeben → `POST /api/uix/install` → Gate mit Manifest, Hashes, Funden | **Gate** (fremder Code) |
| **Entfernen** | `POST /api/uix/remove` | kein Gate, nur Audit (§6) – was weg ist, kann nichts mehr tun |
| **An / Aus** | `uix.yaml` `disabled` | kein Gate, Audit |
| **Shell wechseln** | `uix.yaml` `shell`, danach **Seite neu laden** (der Loader lädt genau eine Shell beim Start) | kein Gate, Audit |
| **Aus Vorlage anlegen** | `_template` → `local_config/tools/<id>`, `id` umbenannt | kein Gate, Audit |

**Begründung für „kein Gate“ bei den letzten drei:** es ist unsere eigene, bekannte Form; nichts Fremdes kommt herein, nichts
verlässt den Rechner, alles ist mit einem Klick zurückzunehmen. Ein Gate an dieser Stelle würde die Freigabe zur Gewohnheit
machen – und genau das soll sie nicht sein. **Fremder Code bleibt ein Gate.**
*(Vom Captain bestätigt am 14.10.2026, 23:35. Damit ist es die Linie, nicht mehr mein Vorschlag.)*

### 2.3 Was dafür im Backend fehlt

| Nr. | Route | Warum |
|---|---|---|
| M1 | `GET /api/uix/modules` | Das Manifest kennt heute nur die **ids** der Shells und keinen Ordnerpfad. Das Werkzeug braucht: beide Listen vollständig (Name, Beschreibung, Vertrauen, Herkunft, Routen), die abgelehnten mit Gründen, die aktive Shell, die abgeschalteten. |
| M2 | `POST /api/uix/shell` | aktive Shell setzen (`uix.yaml`), Audit `UIX_SHELL_CHANGED`; nur eine Shell, die das Manifest kennt. |
| M3 | `POST /api/uix/enabled` | Werkzeug an/aus (`uix.yaml` `disabled`), Audit. |
| M4 | `POST /api/uix/scaffold` | Vorlage kopieren, `id` auf den Ordnernamen setzen, Audit `UIX_MODULE_SCAFFOLDED`. Prüft vorher mit demselben `check_tool`, dass das Ergebnis geladen würde. |

Alles vier schreibt **nur** `local_config` – nie den Projektordner. Damit berührt keine davon eine Grenze aus Build 9. Das ist
Absicht und steht so auch im Werkzeug.

### 2.4 Was das Werkzeug nicht tut

- Es zeigt **keinen fremden Code als Text an**, bevor der Captain ihn sehen will: die Funde der Durchsicht stehen mit Datei und
  Zeile im Gate, nicht als bunte Vorschau im Fenster. Wer eine Datei lesen will, öffnet sie im Dateiwerkzeug.
- Es installiert nichts aus dem Netz. Ein Ordner auf diesem Rechner, mehr nicht.
- Es schreibt kein Modul um. „Aus Vorlage anlegen“ kopiert und benennt um; alles Weitere macht der Captain oder GUPPI im Editor.

---

### 2.5 Gebaut am 15.10.2026

Alles aus §2.1–§2.4 steht, mit einer Abweichung und einer Ergänzung:

- **`GET /api/uix/modules` ist ein GET**, nicht wie zuerst gedacht ein POST – es ist ein Blick, kein Eingriff. (Im ersten Anlauf
  stand es in der POST-Tabelle; die Abnahme meldete prompt eine 404 in der Konsole.)
- **Neuer Objekttyp `module`** in `OBJECT_TYPES` und im Schema, damit das Werkzeug ihn zeichnen darf.
- **Der Ort „Module“ steht in `ui/places.js`** – dadurch kennen ihn Palette, Menü *und* das Gespräch, in beiden Shells, ohne
  dass eine Shell davon wüsste. Das ist der erste sichtbare Nutzen aus Fund F1 der Shell E.
- **„Aus der Vorlage anlegen“ baut in `.im-bau-<id>/<id>`**: die Prüfung verlangt `id` = Ordnername, ein Zwischenname wie
  `routinen.im-bau` fiele genau darüber. Bricht etwas ab, bleibt nichts liegen.
- Die Zusage „fasst den Projektordner nicht an“ ist **kein Satz, sondern ein Test**: er fotografiert den Projektordner vor und
  nach Shell-Wechsel, An/Aus und Vorlage und vergleicht.

## 3. Reihenfolge und Abnahme

1. **Shell E** bauen (Dateien §1.4), `uix_check` um `--shell` und zwei Profile erweitern, Test „beide Shells, dieselben
   Werkzeuge“. Abnahme: `uix_check` 26/26 (Cockpit) **und** `uix_check --shell minimal` `result ok`.
2. **§4 schreiben**: was E über den Vertrag gelernt hat.
3. **Backend M1–M4** mit Tests (jede Route ein Test, dazu einer, der zeigt, dass keine davon den Projektordner anfasst).
4. **Werkzeug Module** in beiden Shells sichtbar; im Cockpit als Zeile unter „System“, in E im Menü „Werkzeuge“.
5. Abnahme beider Shells erneut, Paket, Doku.

---

## 4. Was E über den Vertrag gelernt hat

Vier Funde – drei davon hätte man ohne eine zweite Shell nie gesehen. Jeder ist im Vertrag geschlossen worden, nicht in der
Shell umgangen, und jeder hat einen Test.

| Nr. | Fund | Geschlossen durch | Test |
|---|---|---|---|
| **F1** | **Das Gespräch griff nach Cockpit-Code.** `talk/tool.js` rief `window.sedraPalette.routeText(...)` – ein Global der Cockpit-Palette. In jeder anderen Shell verstummte die Navigation stillschweigend: „logbuch“ ging an das Modell statt an den Ort. Ein Werkzeug darf nichts aus einer Shell holen. | Die Ortskunde ist **Vertrag geworden**: `ui/places.js` (Orte, Wörter, `routeText`, `matchPlaces`, `paletteRows`). Palette und Menüleiste benutzen sie beide, das Gespräch auch. | `test_uix_contract` (Router), `test_a_tool_imports_nothing_of_another_tool_or_of_the_shell` |
| **F2** | **Die Prüfung dagegen war zu schwach.** Sie zählte verbotene Namen von Hand auf – `sedraDock`, `sedraTree`, `sedraStrip` – und ausgerechnet `sedraPalette` fehlte. | Die Prüfung **sucht die Namen jetzt selbst**: jedes `root.sedraX`, das eine Shell definiert, ist für ein Werkzeug tabu. Damit gilt sie auch für die Globals von E und jeder künftigen Shell. | `test_a_tool_imports_nothing_of_another_tool_or_of_the_shell` |
| **F3** | **Ein Werkzeug trug Cockpit-Klassen.** Das Instrument „Zustand“ setzte `ck-with-guppy`/`ck-guppy`; gestylt wurden die in `shells/cockpit/shell.css`. In E fehlte der Guppy, ohne dass irgendetwas fehlschlug. | Das Instrument bringt **seinen Stil selbst mit** (`tools/gauge-state/tool.css`, `.t-gauge-state*`); die Cockpit-Regeln dafür sind entfallen. | `test_no_tool_carries_the_class_names_of_a_shell` |
| **F4** | **Die Abnahme war Cockpit-förmig.** `uix_check` suchte `.ck-strip`, `.dk-tab`, `.pal-box`; eine zweite Shell war damit nicht prüfbar. | `--shell <id>` und **zwei Profile im Prüfwerkzeug** (nicht in der Shell): Zonen, Container, Umschalter, Layout, Menü. Alles andere (Werkzeuge, Gespräch, Konsole, Allowlist, Retro) gilt für jede Shell. | `uix_check --shell minimal` |

Dazu zwei Fehler, die E bei sich selbst gefunden hat – beide durch die Abnahme, nicht durch Nachdenken:

- **Das Gesprächsfenster löschte das Layout.** Es geht vor dem Wiederherstellen auf, und sein `save()` überschrieb den gemerkten
  Stand, bevor ihn jemand las. Jetzt wird das Layout **beim Bauen** gelesen, und während des Wiederherstellens wird nicht
  geschrieben. *(Der erste Entwurf hätte außerdem stillschweigend nur acht Fenster zurückgebracht – ein Schreibtisch, der beim
  Neuladen Fenster schluckt, lügt über den eigenen Zustand.)*
- **Eine Sammlung bekam Nachweise.** „Alle Aufgaben“ zeigte die Umschalter „Live“ und „Kosten“ – die es für eine Liste nicht
  gibt. Dieselbe Regel wie im Cockpit, jetzt auch hier (`orderTools(manifests, object)`).

**Vor dem Bau schon bekannt (Build 9):** eine Shell braucht ihre eigene Route-Allowlist in `shell.yaml`, genau wie ein Werkzeug.
Gefunden durch 403 auf `/api/boundaries`, als der Baum die Grenzen anzeigen wollte.

### Das Urteil über den Vertrag

Er trägt – aber nicht von allein. **Vier Löcher in einem Vertrag, der seit drei Builds steht und 29 Tests hat**, und alle vier
lagen genau dort, wo etwas „nur im Cockpit“ gebraucht wurde. Eine zweite Form ist kein Luxus; sie ist die einzige Prüfung, die
diese Art Loch findet. Die dritte Shell (D, Paperclip) wird weniger finden – wenn sie nichts findet, ist der Vertrag erwachsen.


---

## 5. Shell D (Paperclip) – die dritte Form (ausgearbeitet 15.10.2026, vor dem Bau)

Entwurf `docs/shots/uix2/uix2_D_paperclip.html`: **eine Firma statt eines Cockpits.** Dunkle Navigation links, oben eine
Kopfzeile mit Titel und Suchfeld, in der Mitte Seiten – und die wichtigste Seite ist ein **Dashboard, das mehrere Werkzeuge
zugleich zeigt**: Kennzahlen, Posteingang, Organigramm, Issues. Das Gespräch liegt hinter einem Knopf rechts unten und fährt
als Schublade herein.

### 5.1 Was D prüft, was E nicht prüfen konnte

| Neu in D | Was es am Vertrag belastet |
|---|---|
| **Mehrere Werkzeuge zu mehreren Objekten auf einer Seite** (Dashboard) | Das Cockpit zeigt ein Objekt mit seinen Werkzeugen, Minimal ein Werkzeug je Fenster. D mountet vier Werkzeuge zu vier verschiedenen Sammlungen nebeneinander. Hält ein Werkzeug sich an seinen Container, wenn drei andere daneben stehen? |
| **Das Gespräch ist nicht immer sichtbar** | Regel 1 („ein Eingabefeld“) – aber nicht „immer offen“. Was passiert mit `talk.context`, Hinweisen und Problemen, während die Schublade zu ist? Sie müssen ankommen, wenn sie aufgeht. |
| **Ein Suchfeld in der Kopfzeile** | Das wäre ein zweites Eingabefeld. Lösung: es ist die **Ortskunde** (`ui/places.js`), kein Gespräch. Ein Auftrag oder eine Frage dort öffnet die Schublade mit dem Text – **gesendet wird nur im Gespräch.** |
| **Firmenwörter** | „Posteingang“ ist die Entscheidungsliste, „Issues“ sind Aufgaben, „Ziele“ sind Vorhaben, „Agenten“ die Besatzung. Die Shell **benennt um, sie baut nichts nach** – jede Seite ist ein Objekt, das ein vorhandenes Werkzeug zeichnet. |

### 5.2 Die Entscheidungen

1. **Das Dashboard ist eine Komposition, kein eigenes Werkzeug.** Vier Karten, in jeder ein Werkzeug zu einer Sammlung
   (`decision:alle`, `agent:alle`, `task:alle`, dazu die Instrumente als Kennzahlen). Die Shell schreibt keine Zahl selbst.
2. **Routinen bekommen eine Seite, die ehrlich leer ist.** Kein Werkzeug zeichnet `routine` – die Seite sagt das, statt einen
   Platzhalter zu zeigen. Sobald jemand das Werkzeug baut, füllt sich die Seite ohne eine Zeile Shell-Code.
3. **Ein einzelnes Objekt** (eine Aufgabe, ein Kandidat) öffnet als Seite: Werkstück links, Nachweise als Karten in einer
   rechten Spalte – die dritte Darstellung von `slot: inhalt|nachweis` (Cockpit: Spalten, Minimal: Umschalter, D: Seitenleiste).
4. **Verlauf statt Reiter oder Fenster**: „Zurück“ in der Kopfzeile, die zuletzt besuchte Seite wird gemerkt. Das ist, was D
   beim Neuladen zurückbringen muss.
5. **Das Gespräch als Schublade.** Das `talk`-Werkzeug wird beim Start gemountet und bleibt gemountet; die Schublade zeigt
   oder verbirgt nur seinen Container. Ein Hinweis bei geschlossener Schublade zeigt den Knopf an („1 neu“).
6. **Keine Zahl ohne Werkzeug**: der Badge am Posteingang kommt aus `GET /api/decisions` – derselben Route wie überall.

### 5.3 Dateien und Abnahme

```
uix/shells/paperclip/
  shell.yaml   provides [nav, pages, talk, notify, palette], api [strip, decisions, decisions/answer]
  shell.js     registerShell, Start, Schublade, decide(), notify()
  nav.js       Navigation links mit Badge
  pages.js     Seiten: Dashboard (Komposition), Sammlung, einzelnes Objekt mit Seitenleiste; Verlauf (rein: pageFor, pushHistory)
  topbar.js    Titel, Zurück, Suchfeld (Ortskunde), Hauptknopf
  shell.css    nur .pc-*
```

Drittes Profil in `uix_check` (im Prüfwerkzeug): Zonen `pc-nav · pc-top · pc-page`, Kennzahlen `.pc-kpi`, Container
`.pc-tool[data-tool]`, Nachweise in `.pc-side`, Verlauf als das, was ein Neuladen überstehen muss, Suchfeld als Palette.
Ziel: **27/27 in allen drei Shells**, und **§4 bleibt leer** – oder wird ehrlich länger.

### 5.4 Ergebnis (15.10.2026, 01:20)

**§4 ist leer geblieben.** Die dritte Shell lädt alle 23 Werkzeuge, `uix_check --shell paperclip` sagt 27/27 – und kein
Werkzeug, keine Datei unter `ui/` musste angefasst werden. Vier Werkzeuge zu vier Sammlungen nebeneinander, das Gespräch
in einer Schublade, Nachweise in einer Seitenleiste: der Vertrag hat alles getragen, was E ihm beigebracht hat.

Was D stattdessen gefunden hat, lag **im Prüfwerkzeug und in der Shell selbst**, nicht im Vertrag:

- `uix_check` musste zwei Handgriffe lernen, die der Captain in D auch tut: erst aufs Dashboard, bevor die Kennzahlen
  gezählt werden (sie stehen nur dort), und die Schublade öffnen, bevor jemand ins Gespräch tippt. Beides als Haken im
  Profil (`before_tools`, `before_talk`) – nicht in der Shell.
- Ein Gitter ohne Zeilenmaß lief unten aus dem Bild (`grid-template-rows: minmax(0, 1fr)` fehlte); ein `display: grid` schlug
  das Attribut `hidden` der Schublade, sie stand beim Start offen. Beides hat die Abnahme gemeldet, nicht das Nachdenken.
- Zwei Knöpfe „Mit GUPPI sprechen“ (Kopfzeile und rechts unten) – einer reicht; der Entwurf hatte auch nur einen.

Damit gilt das Urteil aus §4 in der zweiten Hälfte: **der Vertrag ist erwachsen.** Die vierte Form wird ihn nicht mehr
verändern; sie wird nur noch zeigen, was eine Shell gut oder schlecht macht.


---

## 6. Eigene Shells: der Einstieg „Start“ und die allgemeine Abnahme (15.10.2026)

Der Captain fragte: *wie sieht die Möglichkeit aus, eine eigene Shell zu erstellen?* Die Antwort war „halb fertig“ –
Unterbau ja, Oberfläche nein, Abnahme nur für drei bekannte. Jetzt:

### 6.1 Drei Lücken im Werkzeug Module, geschlossen
- „Aus der Vorlage“ und „Fremdes Modul vorlegen“ haben einen Umschalter **Werkzeug / Shell**.
- Eine eigene Shell lässt sich **entfernen** – aber nicht, solange sie läuft (`shell_is_active`): sonst stünde die Seite beim
  nächsten Laden leer.

### 6.2 Die Start-Shell (`uix/shells/start/`) – neutral benannt, auf Wunsch des Captains
- **Standard, solange `uix.yaml` keine Shell nennt** (`DEFAULT_SHELL = 'start'`). Einmal gewählt, startet SEDRA direkt in der
  gewählten; zurück führt „Module → Start → Diese Shell nehmen“.
- Karten je Oberfläche mit Bild (`shells/<id>/preview.png`, nur wenn die Liste sagt, dass es eines gibt – kein 404 ins Leere),
  Beschreibung, Herkunft; „Diese Oberfläche nehmen“ wechselt und lädt neu. Die Auswahl selbst steht nicht zur Wahl.
- **Eigene anlegen** (Vorlage, Audit) und **von außen vorlegen** (Gate) – dieselben Routen wie im Werkzeug Module.
- Das Gespräch unten; die Entscheidungen rechts, sobald eine wartet (das Werkzeug `decisions`, dieselbe Antwortroute).
- **Öffnet keine Objekte** – `provides: [chooser, talk, notify, inbox]`. Wer eines will, bekommt den Satz, wo es sich öffnet.

### 6.3 Die allgemeine Abnahme (Punkt 4)
Eine Shell, die niemand im Prüfwerkzeug kennt, bekam bisher keine Abnahme. Jetzt bekommt sie eine **ehrliche**:

- **Vertragsmarken** (§4 des Vertrags, Nachtrag): eine Shell markiert jeden Werkzeug-Container mit `data-tool="<id>"`, die
  Verbenzeile mit `data-verbs`, die Nachweisfläche mit `data-slot="nachweis"`. Alle drei Shells und die Vorlage tun das.
- `uix_check --shell <jede id>`: ohne Profil gilt das **allgemeine Profil** – Laden, jedes Werkzeug über die Marken (Container
  gefüllt, Verben, Nachweis am richtigen Ort, im scrollenden Rahmen), Gespräch, Konsole, Allowlist, Retro. Was das Profil
  nicht wissen kann (Zonen, Layout nach Neuladen, Palette), heißt im Bericht **„– nicht geprüft“** und zählt nicht als ok.
  Eine Shell, die laut Manifest keine Objekte öffnet (`provides` ohne `dock`/`windows`), bekommt die Werkzeugprüfung gar
  nicht erst – mit Satz.
- **Was die allgemeine Abnahme beim ersten Lauf an der Vorlage fand**: der Körper scrollte nicht (`height:100%` ohne
  Bezug – die Werkzeuge ragten aus dem Rahmen), und die Vorlage zeigte die Verben des Objekts nicht. Beides ist behoben;
  wer heute die Vorlage kopiert, bekommt eine Shell, die `result ok` sagt. Ein Test legt eine Shell aus der Vorlage an, wählt
  sie und nimmt sie ab (`test_uix_shell_start`).

### 6.4 Was damit gilt
Eine eigene Shell entsteht in der Start-Shell mit einem Namen, läuft sofort (Vorlage), hat eine Abnahme, lässt sich
entfernen, und zeigt dieselben 23 Werkzeuge wie die drei im Paket. Was sie *gut* macht, entscheidet ihr Autor – die
Abnahme sagt ihm, was sie *richtig* macht.
