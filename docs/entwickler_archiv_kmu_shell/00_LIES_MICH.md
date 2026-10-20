# SEDRA – Entwickler-Übergabe „KI Gateway für KMU“ (Shell und Design, ohne Engine)

Stand: 19.10.2026. Dieses Archiv gibt einem Entwickler alles, um die Oberfläche **KI Gateway für KMU** (Shell `gateway-kmu`)
und ihr Design zu übernehmen, weiterzuentwickeln oder in eine andere Oberfläche zu überführen. Es enthält **keine Engine**:
keine Python-Laufzeit, kein llama.cpp, keine Modelle, keine Laufzeitdaten, keine Git-Historie.

## Was im Archiv liegt

| Ordner / Datei | Inhalt |
|---|---|
| `00_LIES_MICH.md` | diese Seite |
| `01_UEBERBLICK.md` | was die Shell ist, was sie zeigt, was nicht |
| `02_DESIGN.md` | Farben, Schrift, Raster, Grafik, Herkunft der Werte, Lizenz |
| `03_EINBINDUNG.md` | Dateien, Anschluss an SEDRA, Abhängigkeiten von der Engine, Tests |
| `04_OFFENES.md` | was noch offen ist und wer entscheidet |
| `shell/` | die Shell: `shell.yaml`, `shell.js`, `shell.css`, `README.md`, `kmu-grafik.png` |
| `ui/tokens.css` | die Farb- und Maßtokens (vollständig, mit dem Block `--kmu-…`) |
| `assets/` | Folienbilder, Kopf-Ausschnitte in zwei Größen, `design-ableitungen.json` |
| `tests/test_gateway_kmu_shell.py` | der Browser-Test der Shell |
| `patches/gemeinsame_dateien.patch` | die Änderungen in drei gemeinsamen Dateien (Tokens, Abnahme-Profil, Shell-Liste im Test) |
| `PRUEFSUMMEN.sha256` | SHA-256 aller Dateien im Archiv |
| `../entwickler_archiv_kmu_shell.zip` | dasselbe Archiv als eine Datei |

## Schnelleinstieg

1. **Lesen:** `01_UEBERBLICK.md`, dann `02_DESIGN.md`.
2. **Einbinden:** `03_EINBINDUNG.md`. Die Shell-Dateien aus `shell/` in `runtime/src/guppi_runtime/uix/shells/gateway-kmu/`
   legen und das Patch auf die gemeinsamen Dateien anwenden (`git apply patches/gemeinsame_dateien.patch`).
3. **Prüfen:** der Browser-Test `tests/test_gateway_kmu_shell.py` (braucht die Engine, siehe `03`).
4. **Offenes:** `04_OFFENES.md` vor jeder Veröffentlichung lesen.

## Hinweise zum Stand

- **Nichts ist committet.** Die Shell liegt als Arbeitsstand vor; das Patch beschreibt die Änderungen an den gemeinsamen Dateien.
- **Der Kopf nutzt eine Grafik** aus der Präsentation (Lizenz laut Klaus geklärt, 19.10.2026). Die übrigen Folienbilder liegen in `assets/`, sind aber noch nicht eingebunden.
- **Keine Aussage zur Rechtskonformität.** Sicherheit ist in dieser Präsentation ein Entwicklungsziel, keine Garantie.
- **Keine Cloud-Behauptung.** Die historische B6-Cloudsimulation ist kein Nachweis realer Cloud-Verarbeitung.
- **Der frühere B6-Loopback-Link wird nicht übernommen.**
