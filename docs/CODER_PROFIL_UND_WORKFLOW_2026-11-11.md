# Coder-Profil und Workflow (Stand 11.11.2026)

Grundlage: der Nachtlauf vom 10./11.11.2026 (neun Bau-Specs, zwei Rezepte), belegt in `KOORDINATION_SEDRA/00_UEBERGABE/UEBERGABE_NACHTLAUF_2026-11-11.md`, im Bau-Statuslog des Bauprojekts und in den Dateiköpfen der eingebauten Kandidaten. Was nicht belegt ist, steht als „nicht geprüft“.

## 1. Das Profil

**Wer.** Der Coder der Factory ist ein lokales Modell (Qwen3.6-35B-A3B mit MTP, Quantisierung IQ4_XS, über llama.cpp). Er sieht nur den Aufgabentext und den Arbeitsbereich; Richter ist der versteckte Test.

**Rezepte** (Einstellungen liegen in `local_config/role_routing.yaml`, nicht im Repo):

| Rezept | Wofür | Fenster |
|---|---|---|
| `coder.local_primary_1x80k` | **Standard für Bauaufträge**: ein Kanal, großes Fenster | 81920 |
| `coder.local_primary_team` | Manager und zwei Angestellte auf einem geladenen Modell (gemeinsamer Pool) | Pool 163840 |

**Messwerte** (neun Specs, je Stufe ein Test; Minuten bis alle Stufen bestanden):

| Aufgabenart | 1x80k | Team |
|---|---|---|
| Python, reine Funktionen (7 Specs mit 1x80k, 6 mit Team) | 3,3 bis 7,4, jede Stufe im 1. Versuch | 3,5 bis 7,2, jede Stufe im 1. Versuch |
| JavaScript `zellen.js` | 7,1, im 1. Versuch | 15,9, Stufe 2 erst im 2. Versuch |

Die Datenbasis ist schmal (je ein Lauf je Spec und Rezept, einige Zeiten durch parallele Tests verzerrt). Es ist eine Tendenz, kein Beweis.

**Stärken (belegt).** Kleine, genau beschriebene Kerne mit reinen Funktionen: alle neun Specs bestanden. Der Aufgabentext darf Namen, Rückgabewerte und Fehlermeldungen wörtlich vorgeben, der Coder hält sie ein.

**Schwächen (belegt, 6 von 9 Kandidaten).** Er erfüllt die genannten Fälle und übersieht die nicht genannten:

| Muster | Beispiel aus dem Nachtlauf |
|---|---|
| Wert neu berechnen statt lesen | `rechte_urteil` rechnete die Stufe aus dem Namen, statt die Stufe des Eintrags zu nehmen |
| Zeichenklassen zu weit | `str.isdigit()` lässt `²` durch, `int("²")` wirft |
| Endung statt ganzer Pfad | `route.endswith("/api/*")` wies `GET /api/x/api/*` ab |
| unhashbare Werte | `x in set(...)` mit einer YAML-Liste wirft `TypeError` |
| Objekt als Menge | `seen[name]` mit dem Namen „constructor“; `obj.hasOwnProperty` bei eigenem Schlüssel oder ohne Prototyp |
| Fremden Fehlertext durchreichen | JSON-Fehler statt `herkunft_unlesbar` |
| Unbegrenztes Wachstum | Zwischenspeicher mit einem Eintrag je Zustand |
| Regel „keine Kommentare“ ignoriert | Kommentare in `bruecke_filter.js` trotz `NOTES` (nicht zu jedem Kandidaten geprüft) |

Alle bestanden die ersten, ungeschärften versteckten Tests. Die Fehler fand erst das Lesen.

## 2. Der Workflow

1. **Lohnt sich?** Spec, Tests und Referenz zusammen größer als der Code: Claude schreibt direkt (Regel V4). Bau lohnt für kleine, reine Kerne.
2. **Spec mit Randfall-Block.** Aufgabentext und versteckte Tests nennen die Randfälle aus Abschnitt 4 ausdrücklich; die Referenz besteht sie.
3. **Gegenprobe der Tests.** Vor dem Stempel die Tests gegen bewusst naive Varianten laufen lassen (die Muster aus Abschnitt 1): Sie müssen durchfallen. Zurzeit von Hand (`spec_check <name> --tree <ordner> --host-ok`); ein Werkzeug dafür ist nicht gebaut.
4. **Stempel** (`spec_check <name> --vm --project <projekt>`), jede Änderung macht ihn ungültig.
5. **Vorprüfung** (Skill `sedra-schnellpruefung`): GPU frei, kein fremder Modellserver (der Bau startet sonst nicht und meldet es nur im Statuslog).
6. **Bau mit 1x80k** (`--rezept coder.local_primary_1x80k --kontext 81920`). Bei Vergleichen vor jedem Lauf den Stand beiseite legen oder `--neu` nehmen, sonst setzt die Schleife nur fort.
7. **Kandidat lesen** mit der Checkliste aus Abschnitt 3, nicht nur die Tests ansehen. Den Kandidaten außerdem gegen die geschärften Tests laufen lassen.
8. **Einbau von Hand** in den echten Code (Claude): Kern als eigene Datei übernehmen, Fehler beheben, im Dateikopf vermerken, was der Coder lieferte und was geändert wurde. Anbindung nie dem Coder überlassen, solange er `uix_server.py`-große Dateien nicht lesen kann.
9. **Tests** mit `benchmarks/run_tests.py` (nicht mit `unittest` aus dem Testordner: unter Windows sperrt `wissen.sqlite`). Neue Testdateien `test_apps_*` stehen in keiner Gruppe von `run_tests.py`, also gezielt benennen.
10. **Übergabe** im Format der vier W; Register und Dashboard; Commit nur auf das Ja des Captains.

## 3. Checkliste für den Kandidaten

- Wird ein Wert gelesen, den der Aufruf mitbringt, oder neu berechnet?
- Zeichenklassen: `isdigit`, `isalpha`, `\d` mit Unicode? ASCII-Prüfung nötig?
- Ganzer Pfad oder nur das Ende, der Anfang?
- Unhashbare Eingaben (Liste, dict) in `in set(...)`, als Dict-Schlüssel?
- JavaScript: Objekte als Menge (`obj[name]`), `hasOwnProperty` direkt am Objekt, Objekte ohne Prototyp?
- Eigene Fehlermeldung oder die der Bibliothek?
- Wird etwas ohne Grenze gemerkt?
- Hält der Kandidat die Regeln aus `NOTES` ein (keine Kommentare, keine Docstrings, nur Standardbibliothek)?
- Ändert er seine Eingaben? Gibt er dieselbe Liste zurück statt einer Kopie?

## 4. Checkliste für die versteckten Tests (Randfälle)

Je Funktion mindestens: leere Eingabe, `None`, falscher Typ, Text statt Liste, doppelte Einträge, unbekannter Schlüssel. Dazu die Muster aus Abschnitt 1:

- Stufe oder Wert im **Eintrag** anders als der **berechnete**, damit „neu berechnen“ auffällt.
- Zeichen `²` (U+00B2) und `٣` (U+0663) wo Ziffern geprüft werden.
- Bei Pfaden und Routen: dasselbe Muster mitten im Pfad (`/api/x/api/*`), als Vorsilbe (`/xapi/*`).
- Namen wie `constructor`, `__proto__`, `hasOwnProperty`, `toString` als Schlüssel; Objekte ohne Prototyp (JavaScript).
- Listen und dicts, wo ein Text oder eine Kennung erwartet wird.
- Eigene Fehlermeldung wörtlich prüfen, nicht nur „wirft ValueError“.
- Eingaben vorher und nachher vergleichen (keine Änderung), Ergebnis ist eine neue Liste.

## 5. Offen

- Die Specs `am0_routen`, `am0_herkunft`, `am1_manifest_felder`, `zellen`, `am3_rechte_diff` und `bruecke_filter` sind mit diesen Fällen geschärft; die anderen drei (`am0_gate_texte`, `am0_shell_regeln`, `am3_berechtigung`) noch nicht auf die Muster durchgesehen.
- Ein Werkzeug für die Gegenprobe (Abschnitt 2, Punkt 3) fehlt: Mutanten aus einer Liste naiver Varianten erzeugen und gegen die Tests laufen lassen.
- `bau_schleife.py` geht von vier Stufen aus (`unknown stage 'S4'` bei drei).
- Nicht gemessen: größere Aufgaben (ein Eingriff in `uix_server.py`-große Dateien), Saat-Ordner mit vorhandenem Code, Aufgaben über mehrere Dateien. Das ist die eigentliche Probe für A3 und weiter.
