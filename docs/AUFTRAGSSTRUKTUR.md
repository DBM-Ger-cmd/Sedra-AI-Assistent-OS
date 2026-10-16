# Übertragbare Auftragsstruktur

Stand 16.10.2026. Gehört zum Regelwerk Standardläufe (`REGELWERK_STANDARDLAEUFE.md`), Abschnitt 11.
Code: `runtime/src/guppi_runtime/auftrag.py`. Tests: `runtime/tests/test_auftrag.py`. Beispiel: `docs/auftrag_beispiel/`.

## Zweck

Ein Auftrag an ein Modell ist ein Ordner. Er ist gleich auf jedem Rechner, weil er keine Pfade dieses PCs enthält.
Er beschreibt Spezifikation, Eingaben, Ausgaben, Schreibbereich, Prüf- und Abbruchregeln. Das Protokoll entsteht bei der
Ausführung (siehe unten).

## Ordnerlayout

```
<auftrag>/
  auftrag.json       Manifest (Pflicht)
  spezifikation.md   Auftragstext (Pflicht, relativ, höchstens 4000 Zeichen)
```

Keine weiteren Dateien sind Pflicht. Eingaben liegen nicht im Auftragsordner, sondern im Labor des Laufs.

## Manifest `auftrag.json`

| Feld | Pflicht | Regel |
|---|---|---|
| `format` | ja | genau `guppi-auftrag` |
| `version` | ja | genau `1` |
| `name` | ja | Kleinbuchstaben, Ziffern, Bindestrich, 2–40 Zeichen; eindeutig im Labor |
| `art` | nein | `bewerten` (Standard) oder `bauen` |
| `beschreibung` | nein | eine Zeile, höchstens 300 Zeichen |
| `modell` | ja | `{"provider": "...", "model": "..."}`; wird im Lauf festgelegt |
| `spezifikation` | ja | relativer Pfad zu einer `.md`-Datei im Auftragsordner, ohne `..` |
| `lab` | ja | relativer Ordner unter `redesign/`, ohne `..` und ohne Laufwerk |
| `eingaben` | nein | relative Pfade im Labor, nur lesen; höchstens 20 |
| `schreibbereich` | ja | erlaubte Dateien oder Ordner, relativ; höchstens 20 |
| `ausgaben` | ja | Dateien, die am Ende existieren müssen; jede liegt im Schreibbereich |
| `pruefregeln` | ja | Auswahl aus der festen Liste unten; `schreibbereich` und `ausgaben_vollstaendig` sind Pflicht |
| `abbruchregeln` | nein | `max_schritte` (≤ 40), `max_wiederholungen` (≤ 2), `schritt_timeout_s` (≤ 240), `token_limit` (≤ 12000); unbekannte Schlüssel werden abgelehnt |

Name, Art, Pfade, Modell, Schreibbereich und Ausgaben werden durch `laufdefinition.pruefen` geprüft,
also mit denselben Regeln wie frei anlegbare Läufe.

### Prüfregeln (feste Liste)

| Regel | Art | Was sie prüft |
|---|---|---|
| `schreibbereich` | maschinell | nur erlaubte Dateien wurden geschrieben (Schreibprotokoll des Laufs) |
| `ausgaben_vollstaendig` | maschinell | jede Ausgabe existiert und ist nicht leer |
| `zeilen_max_400` | maschinell | `.js`, `.css`, `.html`, `.md` haben höchstens 400 Zeilen |
| `keine_fetch_localstorage` | maschinell | in `.js` kein `fetch(` und kein `localStorage` |
| `syntax_js` | maschinell | `node --check` für `.js`; ohne `node` → „nicht geprüft“, kein Fehlschlag |
| `belege` | manuell | jede Aussage verweist auf eine Zeile oder Quelle; prüft der Vorarbeiter |

Ergebnis (`ergebnis`): `nacharbeit`, wenn eine maschinelle Regel nicht besteht, sonst `maschinell_ok`.
`maschinell_ok` ist keine Übernahme. Die Entscheidung trifft der Captain (Regelwerk, Abschnitt 3, Punkt 6).

### Abbruchregeln

Die Obergrenzen sind fest (Regelwerk, Abschnitt 4). Das Manifest darf nur niedrigere Werte nennen.
**Offen:** Der Lauf liest die Werte aus dem Manifest noch nicht; er nutzt seine Konstanten in `redesign_agent.py`.

## Protokoll

Der Lauf schreibt `lauf_<name>.jsonl` in den Labor-Ordner (Regelwerk, Abschnitt 7). Das Protokoll enthält keine Prompt- und Dateiinhalte.
Der Auftrag ändert daran nichts.

## Portabilität

- Im Manifest und im Auftragstext stehen keine Pfade dieses PCs. `auftrag.portabel_pruefen(ordner)` meldet Laufwerke
  (`C:\`), Benutzerordner (`\Users\…`, `/home/…`) und UNC-Pfade.
- Maschinenordner werden über Platzhalter wie `<modelle>` angegeben, wie in `local_paths.py`. Platzhalter sind erlaubt.
- Die Werkstatt-Wurzel (Ordner mit `redesign/`) steht nie im Auftrag. Sie gibt der Aufrufer an.
- `auftrag.paket(ordner, ziel)` kopiert Manifest und Auftragstext in einen neuen Ordner, aber nur nach bestandener Prüfung.

## Ablauf

1. Auftragsordner anlegen und `auftrag.json` sowie `spezifikation.md` schreiben.
2. Prüfen: `auftrag.laden(ordner)` (wirft ValueError mit Grund) und `auftrag.portabel_pruefen(ordner)` (leer = portabel).
3. Anlegen: `vorarbeiter.aktion(werkstatt, "lauf_anlegen", auftrag.als_laufdefinition(ordner))`.
   Der Auftragstext wird dabei zusammen mit den Eingaben als Lauf-Auftrag gespeichert.
4. Starten: `lauf_starten` mit dem Namen (wie bei frei anlegbaren Läufen, eine Sperre von sechs Stunden je Name).
5. Prüfen nach dem Lauf: `auftrag.pruefe_ausgaben(labor, manifest, schreibprotokoll)`, dann `auftrag.ergebnis(...)`.
   Die Befunde gehen an den Vorarbeiter. Die Regel `belege` bleibt manuell.

## Beispiel

`docs/auftrag_beispiel/` enthält einen Bewertungsauftrag: liest `quelle/README.md`, schreibt `out/bewertung.md`,
Prüfregeln `schreibbereich`, `ausgaben_vollstaendig`, `belege`. Der Ordner ist portabel (`portabel_pruefen` meldet nichts).

## Offen

- Der Lauf liest die Abbruchregeln aus dem Manifest noch nicht (siehe oben).
- Die Werkstatt-Wurzel wird noch nicht über einen Platzhalter aus `local_paths.yaml` aufgelöst. Heute gibt der Aufrufer sie an.
- Der Vorarbeiter hat noch keine Aktion, die einen Auftragsordner direkt annimmt. Heute muss der Umweg über `als_laufdefinition` gegangen werden.
- `pruefe_ausgaben` ist nicht an den Lauf angeschlossen. Der Vorarbeiter müsste es nach `LAUF_ENDE` aufrufen.
- Die Prüfung der Belege (Regel `belege`) ist nicht automatisiert.
- Keine Versionierung zwischen Auftragsversionen; `version` ist 1 und wird bei einer Formatänderung erhöht.
- Die Regelwerk-Datei in `docs/` ist in dieser Arbeitskopie noch nicht übernommen; ein Verweis dorthin steht dort noch aus.
