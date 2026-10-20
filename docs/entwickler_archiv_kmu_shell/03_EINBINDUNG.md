# 03 – Einbindung

## Dateien und Orte
| Archiv | Im Repository |
|---|---|
| `shell/shell.yaml`, `shell.js`, `shell.css`, `README.md`, `kmu-grafik.png` | `runtime/src/guppi_runtime/uix/shells/gateway-kmu/` |
| `ui/tokens.css` (vollständig) | `runtime/src/guppi_runtime/uix/ui/tokens.css` |
| `assets/` | `runtime/assets/kmu-praesentation/` (wird vom Server nicht ausgeliefert) |
| `tests/test_gateway_kmu_shell.py` | `runtime/tests/test_gateway_kmu_shell.py` |
| `patches/gemeinsame_dateien.patch` | auf `benchmarks/uix_check.py`, `tests/test_uix_shell_start.py` und `ui/tokens.css` anwenden |

Anwendung: die Shell-Dateien an den Ort kopieren, dann im Repository-Wurzelverzeichnis `git apply patches/gemeinsame_dateien.patch`.

## Wichtig: der Server liefert Shell-Bilder nur direkt aus dem Shell-Ordner
Der Server (`desk/gateway.py`, `SERVE_TYPES`) liefert aus einem Modulordner nur Dateien direkt darin aus, und nur die Typen
`js`, `css`, `json`, `svg`, `png`, `html`. Deshalb liegt die Kopf-Grafik als Kopie im Shell-Ordner. Ein JPEG käme nicht durch.

## Abhängigkeiten von der Engine
Die Shell selbst ist reines Frontend. Sie braucht zur Laufzeit die SEDRA-Engine (diese liegt **nicht** im Archiv):
- `/uix/manifest` und die Modul-Dateien (Shell, Werkzeuge) vom laufenden UIX-Server,
- das Werkzeug „KI GateWay“ mit seinen Routen (`/api/gateway/…`) und das Werkzeug „Gespräch“ (`talk`),
- den Ereignisstrom `/api/events`.
Ohne Engine startet die Oberfläche nicht. Die Shell braucht die Engine nicht zur Gestaltung: Farben und Schrift liegen in
Dateien dieses Archivs.

## Tests
- Browser-Test der Shell: `runtime/tests/test_gateway_kmu_shell.py` (startet den Server mit der Shell, prüft Kopf, Ablauf,
  Grafik, Gateway in der Mitte, Gespräch unten, Farbe des Titels und Seitenfehler). Braucht Playwright und Chromium.
- Vertragstests: `test_uix_contract.py` (keine Hex-Farben in Shells, Tokens nur in `ui/tokens.css`, Datei-Längen ≤ 400 Zeilen,
  README je Modul) und `test_uix_shell_start.py` (Auswahl der Shells).
- Abnahme: `benchmarks/uix_check.py` kennt das Profil `gateway-kmu` (Zonen, Ablauf als Messwerte).

Stand dieses Archivs: `test_gateway_kmu_shell` und die Shell-Tests sind grün. In `test_uix_contract` schlägt **ein** Test fehl
(`test_the_tree_shows_every_zone_and_marks_what_waits`); er hängt an einer anderen, nicht committeten Änderung am Baum
(`uix/shells/cockpit/tree.js`) und nicht an dieser Shell.
