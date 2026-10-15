# Spec: Eine Shell aus einer Vorgabe (15.10.2026, GEBAUT in Build 17 – Schritt 1 und 2 ganz, Schritt 3 als Block im Einstieg und im Werkzeug; der Weg über das Gespräch offen)

**Captain, 02:18:** *„Aus den Shells, die wir gebaut haben, und der externen Arbeit kann man doch die Methode, wie man seine
eigene Shell aus einer Vorgabe baut, verbessern und einbringen als Feature.“*

## 1. Was die vier Shells gezeigt haben

Cockpit, Minimal, Paperclip und Start sind von Hand geschrieben – 1 400 Zeilen zusammen. Legt man sie nebeneinander, besteht
jede aus **denselben Teilen**, nur anders angeordnet:

| Teil | Cockpit | Minimal | Paperclip | Start |
|---|---|---|---|---|
| Instrumente | Leiste oben | rechts in der Menüleiste | Kacheln auf dem Dashboard | – |
| Orte (Navigation) | Baum links | Ablage unten + Menü | Liste links | – |
| Werkstück + Nachweise | Reiter, zwei Spalten | Fenster mit Umschalter | Seite mit Seitenleiste | – |
| Gespräch | Zone unten | Fenster ohne Schließknopf | Schublade | Zone unten |
| Entscheidungen | Werkzeug im Reiter | Karte rechts oben | Posteingang-Karte | rechts, wenn eine wartet |
| Palette / Suche | Strg+K Overlay | Menü „Werkzeuge“ | Suchfeld oben | – |
| Neues anlegen | „＋ Neu“ | Menü „Ablage“ | Kopfzeile | – |

Die Mechanik dahinter ist in allen vier gleich: Werkzeug mounten, `ready` abwarten, Verben zeigen, `unmount` beim Wechsel,
Marken setzen, `talk.context` senden, nach einer Handlung auffrischen. **Das ist kein Shell-Code, das ist Vertrag** – und es ist
viermal geschrieben. Die externe Lieferung hat es noch einmal gezeigt: ihre Vorführung baut einen „Rahmen im Stil von Shell E“
nach, weil es keinen anderen Weg gab, die Werkzeuge zu zeigen.

## 2. Die Idee: die Anordnung beschreiben, nicht programmieren

Eine **Vorgabe** (`shell.vorgabe.yaml`) sagt, *was wo steht*; ein **Rahmen** im Vertrag (`ui/frame.js`) baut daraus die Shell.
Wer eine eigene Form will, schreibt zwölf Zeilen YAML – oder sagt es GUPPI, das die Vorgabe schreibt.

```yaml
vorgabe:
  id: meine-bruecke
  name: "Meine Brücke"
  raster: [leiste, [orte, werkstueck], gespraech]     # Zeilen; eine Zeile mit Liste = Spalten
  leiste:      {inhalt: instrumente}
  orte:        {inhalt: orte, breite: 220, orte: [aufgaben, vorhaben, projekt, logbuch, module]}
  werkstueck:  {inhalt: objekt, nachweise: seitenleiste}     # oder: umschalter · spalten · keine
  gespraech:   {inhalt: gespraech, hoehe: 104}
  entscheidungen: karte                                       # karte · werkzeug · posteingang
  suche: strg-k                                               # strg-k · feld · keine
  start: {type: task, id: alle}
```

Der Rahmen kennt sechs Inhalte (`instrumente`, `orte`, `objekt`, `gespraech`, `entscheidungen`, `leer`) und drei Darstellungen
für Nachweise. Alles andere – Mounten, Verben, Marken, Verlauf, Layout merken – tut er selbst, **einmal, geprüft**. Eine Shell aus
Vorgabe besteht dann nur noch aus `shell.yaml`, `shell.vorgabe.yaml` und optional einer `shell.css` für Farben und Abstände.

## 3. Was das als Feature heißt

| Für wen | Was |
|---|---|
| **Der Captain** | Im Einstieg „Eigene Oberfläche anlegen“ wird aus dem Namensfeld ein kleines Formular: Raster wählen (drei Vorlagen: *Reiter* · *Fenster* · *Seiten*), Orte ankreuzen, Gespräch unten oder als Schublade, Entscheidungen als Karte oder Werkzeug. Anlegen → läuft sofort, `uix_check` sagt ok. |
| **GUPPI** | „Ich will links die Aufgaben, rechts das Gespräch, keine Instrumente“ → GUPPI schreibt die Vorgabe, legt sie an, zeigt sie. Die erste GUPPI-Spec für ein eigenes Modul – ohne dass GUPPI JavaScript schreiben muss. |
| **Jemand von außen** | Eine Lieferung bringt eine Vorgabe statt 400 Zeilen Code mit; die Durchsicht hat nichts zu finden, weil kein Code kommt. |
| **Die Abnahme** | Eine Shell aus Vorgabe ist **vollständig prüfbar**: der Rahmen setzt die Marken, kennt seine Zonen und sein Layout – `uix_check` braucht kein Profil, alles ist „geprüft“, nichts „nicht geprüft“. |

## 4. Was es nicht ersetzt – ehrlich

- Eine Shell aus Vorgabe wird **schlichter** sein als eine von Hand: kein Dashboard mit vier Karten (Paperclip), kein freies
  Ziehen von Fenstern (Minimal), es sei denn, der Rahmen lernt es als Darstellung. Die handgebauten bleiben; die Vorgabe ist der
  Einstieg für alle, die nicht programmieren – und für GUPPI.
- Der Rahmen ist **neuer Vertragscode** (`ui/frame.js`, ≤ 400 Zeilen, oder zwei Dateien). Er muss dieselbe Prüfung bestehen wie
  jede Shell – und er wird zum fünften Beweis, dass der Vertrag trägt: wenn der Rahmen alle vier Formen *beschreiben* kann,
  gibt es in ihnen nichts, was nicht Vertrag wäre.
- Die Vorgabe ist Daten, kein Code: strenge Prüfung wie bei `uix.yaml` (unbekannter Schlüssel → Ablehnung mit Satz).

## 5. Bauplan (klein, drei Schritte)

| Schritt | Inhalt | Abnahme |
|---|---|---|
| 1 | `ui/frame.js` + `ui/schema/vorgabe.schema.json`: der Rahmen, mit `raster`, sechs Inhalten, Nachweise als Seitenleiste/Umschalter/Spalten, Gespräch unten/Schublade, Entscheidungen als Karte/Werkzeug. Pure Teile (Raster parsen, Vorgabe prüfen) mit node. | eine Vorgabe, die das Cockpit nachbaut, läuft 27/27 |
| 2 | Einstieg und Werkzeug Module: „Eigene Oberfläche anlegen“ mit den drei Vorlagen und den Kreuzchen; `scaffold` nimmt `vorgabe` statt nur `id`. | Klick-Test: anlegen, nehmen, neu laden, Aufgaben öffnen |
| 3 | GUPPI: der Ort „Oberfläche“ in der Ortskunde; ein Auftrag „bau mir eine Oberfläche mit …“ wird eine Vorgabe (Verb `oberflaeche_anlegen` am Objekt `module`, ohne Gate – eigene Form). | Gespräch → Vorgabe → Shell, in einem Zug |

Vorher offen für den Captain: **ob der Rahmen die vier bestehenden Shells ersetzen soll** (eine Datei statt 1 400 Zeilen) oder
nur neben ihnen steht. Mein Vorschlag: daneben – die handgebauten sind die Beweise, der Rahmen ist das Werkzeug. Ersetzen kann
man später, wenn er es kann.

## 6. Nachtrag 15.10., 02:40 – was Photocraft dazu beiträgt

Der Captain fragte nach `storytold/photocraft` (Bildeditor in Rust/egui, 24 Crates, MIT/Apache). **Als Shell oder Einbau: nein** –
die Oberfläche wird im Immediate-Mode in ein Canvas gezeichnet, es gibt kein DOM, keine Zonen, nichts für `mount(el, ctx)`.
Als **Muster** sind drei Dinge für den Rahmen wertvoll:

| Muster bei Photocraft | Was es für die Vorgabe heißt |
|---|---|
| **Command-Registry** (`crates/engine/src/commands.rs`): jede Oberfläche – UI, CLI, Steuerkanal, MCP – ruft nur `id + JSON-Params` | bestätigt „Verben statt Routen“; die Vorgabe nennt Verben, nie Routen |
| **UI-Zustand als reine Daten** (`UiState`, serde; von außen lesbar und setzbar) | der Rahmen hält seinen Zustand als JSON (gewählter Ort, Layout, offenes Objekt), nichts lebt versteckt im DOM – damit GUPPI und `uix_check` ihn lesen können |
| **Benannte Layouts** („Workspaces“: Essentials, Photography …; Dock-Snapshot in den Prefs) | eine Vorgabe darf mehrere `ansichten:` tragen (etwa *schreiben* · *prüfen*), umschaltbar über die Palette; das Layout-Merken des Rahmens wird je Ansicht gespeichert |
| **Plugin-Manifest mit Parameter-Schema**, aus dem der Dialog entsteht (`docs/plugins.md`: number/int/bool/choice) | wenn ein Werkzeug Einstellungen braucht, stehen sie als Schema in `tool.yaml` (`settings:`), und der Rahmen baut das Formular – kein Werkzeug schreibt eigene Einstellungs-Oberfläche |

Nicht übertragbar: Rendering, Engine, WASM-Sandbox, TCP-Steuerkanal. Der Bauplan in §5 bekommt dadurch in Schritt 1 die zwei
Punkte *ansichten* und *settings-Schema*; der Rest bleibt.

## 7. Nachtrag 15.10., 09:10 – was der Bau geändert hat

- `raster` schreibt Spalten als **ein String mit |** (`"orte|werkstueck"`) statt verschachtelter Listen: so bleibt das Schema in der
  flachen Teilmenge, mit der ein lokales Modell gezwungen wird (`models/structured.py`). Zonen sind zugleich Inhalte; eigene
  Zonennamen mit `inhalt:` gibt es nicht – sechs Zonen, jede höchstens einmal.
- `entscheidungen: karte` ist in der Raster-Zone **oder** schwebend rechts; `suche: feld` braucht die Leiste.
- Die Vorgabe wird an **einer** Stelle geprüft (`desk/vorgabe.check`) – für die Datei im Ordner wie für die Antwort des Modells.
- Schritt 3 ist als Block gebaut („Eigene Oberfläche aus einer Vorgabe“: Satz an GUPPI oder Vorlage → Skizze → anlegen), nicht als
  Ort in der Ortskunde und nicht als Verb im Gespräch. Das Verb `oberflaeche_anlegen` bleibt offen.
- Die Frage aus §5 (ersetzt der Rahmen die handgebauten Shells?) ist mit drei Vorgaben, die die drei Formen 27/27 nachbauen,
  beantwortbar – entschieden ist sie nicht. Details: `BUILD_17_SHELL_CREATOR_2026-10-15.md`.
