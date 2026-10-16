# Build 9 – Modus und Grenzen, Vorhaben, Installation (14.10.2026)

Gebaut nach `SHELL_WERKZEUG_VERTRAG_v1.md` §9 Punkt 3 und `COCKPIT_MODUL_v1.md` §3 / Regel 7 und 8, auf Build 8.
**Am Kern ändert sich nichts**, alle alten Routen bleiben, Build 6 bleibt unter `/retro`. Damit ist der Bauplan des Vertrags
(Builds 7–9) vollständig.

## 1. Modus und die vier Grenzen (`desk/boundaries.py`)

Die Stellen, an denen der Mensch steht – je Projekt, einmal bestätigt:

| Grenze | was sie betrifft |
|---|---|
| `projekt` | Dateien im Projekt ändern |
| `netz` | ins Netz gehen – nachladen, abrufen |
| `loeschen` | Dateien löschen |
| `kosten` | Token je Aufgabe |

Jede steht auf `frei`, `fragt` oder `zu`, die Kostengrenze zusätzlich auf einer Zahl. **Zwei Regeln sind nicht verhandelbar:**
Netz und Löschen gibt es nicht als `frei` (Konzeptprüfung P0/P4 – im Werkzeug fehlt der Knopf, nicht nur die Wirkung), und
**Lesen ist immer frei**.

**Kein Standard im Code** (Captain-Entscheidung §3): beim ersten Öffnen eines Projekts schlägt GUPPI aus dem Projekt vor und
begründet es in einem Satz – leerer Ordner → *Sandbox*, bestehendes Repository mit fremdem Code → *Beobachten*, eigenes
Werkzeugprojekt → *Vertraut*. Der Captain bestätigt einmal, über ein Gate. **Bis dahin läuft nichts, was eine Grenze berührt**,
und das Instrument in der Leiste sagt „nicht bestätigt“ statt einen Modus vorzutäuschen.

**Die Kostengrenze wird gemessen, nicht geraten**: bis zwei Wochen Guppy-Meter vorliegen, fragt sie ab dem Doppelten der bisher
teuersten Aufgabe. Die Zahl steht im Werkzeug und ist bis dahin als vorläufig gekennzeichnet.

### Die Entscheidung an der Grenze (Regel 7)

Eine Überschreitung wird zur Entscheidung mit denselben Wegen wie jede andere – *Einmal öffnen · Grenze ändern … · Ablehnen*:

- **Einmal öffnen** gilt für genau diese eine Handlung und ist danach verbraucht (`BOUNDARY_OPENED_ONCE`, beim Durchgang
  `BOUNDARY_PASSED_ONCE`) – dieselbe Logik wie der Einmal-Token des Guard.
- **Grenze ändern …** beantwortet die Entscheidung *nicht*: es öffnet die Entscheidung über die Grenze selbst, und die ist
  wieder eine Freigabe.
- **Ablehnen** lässt nichts geschehen – und steht trotzdem im Audit.
- Was auf `zu` steht, bietet gar kein „einmal“ an. Dann bleibt nur ändern oder ablehnen.

**Die Deckungsprüfung sitzt vor `guard.create_gate`** (§10): `actions._boundary_first()` fragt die Grenze, bevor ein Verb
überhaupt ein Gate erzeugt. Heute geht genau ein Verb der Oberfläche durch diese Prüfung: *Kandidat übernehmen* (das einzige,
das ins Projekt schreibt). Netz und Löschen sind verdrahtet und geprüft, aber kein Verb der Oberfläche kreuzt sie bisher – die
Werkzeuge der Runtime (`tools/web.py`, `tools/shell.py`) liegen wie bisher hinter dem Guard. Das steht hier, damit niemand
mehr Schutz annimmt, als da ist.

## 2. Vorhaben (`desk/intents.py`, Regel 8)

Ein Vorhaben ist der Satz, um den es geht, und die Klammer um die Aufgaben, die daraus entstehen. **Anlegen kostet nichts und
braucht keine Freigabe** – es wird nichts ausgeführt. Erst *Aufgabe daraus machen* beginnt den gewohnten Weg (Plan, Gates,
Ausführung), und die Aufgabe hängt danach am Vorhaben. Sein Zustand kommt aus seinen Aufgaben; einen eigenen hat es nicht.
Gespeichert in `local_config/intents.yaml`. „＋ Neu → Vorhaben“ führt dorthin, die Palette kennt das Wort.

## 3. Installation fremder Module (`desk/install.py`, Vertrag §6)

`POST /api/uix/install` legt vor, es baut nicht ein. Im Gate steht: das geprüfte Manifest, **jede Datei mit Größe und SHA-256**,
und was die Durchsicht gefunden hat – `eval`, `new Function`, eigenes `fetch`/`XMLHttpRequest`/`EventSource`, `import()`,
`localStorage`, `document.write`, `innerHTML`, fremde Adressen. Jeder Fund mit Datei, Zeile und dem Satz, warum er zählt.

- **Ein Fund ist kein Urteil** – er steht im Gate, der Captain entscheidet.
- **Vor der Freigabe wird nichts kopiert.** Beim Anwenden muss jede Datei noch genau den Hash haben, der im Gate stand; sonst
  bricht die Installation ab (`module_changed_since_the_request`).
- Ein fremdes Modul kann nie `CORE` werden, und als `COMMUNITY` bekommt es vom Gateway **nur Leserouten** – die
  `POST`-Einträge seines Manifests werden verworfen, nicht abgelehnt.
- **Entfernen ist kein Gate**, nur Audit (§6): was weg ist, kann nichts mehr tun.

## 4. Vorlagen für GUPPI (§7.4)

`uix/tools/_template/` und `uix/shells/_template/` – ein funktionierendes Minimum mit Kommentaren, das die vier Regeln erklärt,
die die Tests erzwingen. Ordner mit führendem `_` werden nie geladen. Die Vorlagen bestehen die Manifestprüfung bis auf die eine
Regel, die eine Vorlage nicht erfüllen kann (`id` = Ordnername) – das erledigt das Umbenennen beim Kopieren, Schritt 1 der README.
Ein Test hält beides fest, und dass die Vorlagen selbst keinen Fund der Durchsicht enthalten.

## 5. Abnahme auf diesem Stand

| Prüfung | Ergebnis |
|---|---|
| `benchmarks/uix_check.py` | **`result ok`, 26 von 26** (jetzt mit `boundaries` und `intent`) |
| `tests/test_desk_boundaries.py` | 15 Tests – nie `frei` für Netz/Löschen, Vorschlag aus dem Projekt, nichts vor der Bestätigung, einmal heißt einmal, Ablehnen lässt nichts zurück, Ändern führt zur Entscheidung über die Grenze |
| `tests/test_desk_install.py` | 17 Tests – Durchsicht, Hashes, nichts kopiert vor der Freigabe, geänderte Datei bricht ab, nur Leserouten, Vorlagen; dazu Vorhaben |
| `tests/test_desk_*`, `test_uix_contract` | unverändert grün |

## 6. Was damit offen bleibt

- **Routinen** (Nachtkette) sind im Baum angekündigt, nicht gebaut.
- **Netz und Löschen** kreuzt heute kein Verb der Oberfläche (siehe oben) – die Prüfung steht bereit, die Verben kommen mit den
  Werkzeugen, die sie brauchen.
- Die **Kostengrenze als Zahl** braucht zwei Wochen Guppy-Meter auf dem PC.
- Als nächstes nach dem Vertrag (§9.4): die **Minimal-Shell (E)**, dann die **Paperclip-Shell (D)**. Beide laden dieselben
  Werkzeuge; die Vorlage `shells/_template/` ist der Anfang. Danach die erste GUPPI-Spec für ein eigenes Werkzeug („Routinen“).
