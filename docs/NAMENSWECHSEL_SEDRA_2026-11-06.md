# Namenswechsel: der alte Produktname verschwindet aus dem System (Stand 06.11.2026)

Der Captain wollte den alten Produktnamen nur noch in der Historie. Dieser Stand benennt alles um: Programmpaket, Ordner, Umgebungsvariablen, Dateinamen und Texte.

## Was heißt jetzt wie

| Bereich | neu |
|---|---|
| Programmpaket | `runtime/src/sedra_runtime` (Aufruf `python -m sedra_runtime.uix_start`) |
| Projektordner | `workspace/SEDRA_OS` |
| Architekturordner | `architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC`, `…_v1.20_SELF_DEVELOPMENT` |
| Umgebungsvariablen | `SEDRA_*` (z. B. `SEDRA_SECRET_NVIDIA_API_KEY`) |
| HTTP-Kopf der Oberfläche | `X-SEDRA-Token` (der alte Kopf wird mit 403 abgelehnt) |
| Namensräume und Kennungen | `sedra.devvm.*`, `sedra.orchestra.*`, Schema `sedra.agent-template/v1` usw. |
| Befehle | `sedra`, `sedra-uix` (Einträge in `runtime/pyproject.toml`) |

## Was bleibt als Verlauf unverändert

`docs/LOGBUCH_AGENT_MANAGER.md`, `docs/historie/`, `concept_review/` und alle datierten Berichte (`*_2026-…`). Der Ereignis-Verlauf in `runtime_data/audit/events.jsonl` und die bisherigen Einträge der Agenten-Registry bleiben ebenfalls, wie sie sind (Altdaten).

## Übergang für bestehende Installationen

Einzige Stelle mit dem alten Namen: `runtime/src/sedra_runtime/legacy_names.py` (der Name ist dort zerlegt, damit die Suche ihn nicht findet).

- **Umgebungsvariablen:** Beim Import des Pakets werden alte Variablen auf `SEDRA_*` gespiegelt, wenn die neue fehlt. Wer eine alte Variable gesetzt hat (etwa den Schlüssel für NVIDIA), muss nichts tun.
- **Projektordner:** `START_SEDRA.bat` und `start_sedra.sh` benennen `workspace/<alter Name>_OS` beim ersten Start in `workspace/SEDRA_OS` um, bevor sie etwas anlegen. Der Inhalt bleibt unberührt. Existieren beide Ordner, wird nichts verschoben.
- **Altes Programmpaket und alte Architekturordner:** Wenn das neue Paket da ist, wandern die alten Ordner nach `local_config/update/sicherung/alt_namen/`. Es wird nichts gelöscht.
- **Browser:** Gespeicherte Positionen der Desktop-Symbole liegen unter neuen Schlüsseln; sie müssen einmal neu gesetzt werden.

## Umstieg einer Installation vor 1.23.0

Der eingebaute Updater einer älteren Installation prüft nur Pfade unter `runtime/src/<alter Paketname>/` und lehnt ein Manifest mit `runtime/src/sedra_runtime/` ab. Für diesen einen Schritt gibt es deshalb ein eigenes Paket mit eigenem Installer (`INSTALL_NAMENSWECHSEL.py`, Quelle `release/install_namenswechsel.py`, gebaut mit `runtime/benchmarks/package_namenswechsel.py` aus einem Commit). Er arbeitet ohne den alten Updater:

1. **Vorschau** (Standard, schreibt nichts): prüft das Paket gegen `release/MANIFEST_NAMENSWECHSEL.sha256` (Pfade nur unter `runtime/src/sedra_runtime/`, `runtime/config/`, den Architekturordnern und den drei Startskripten; Zusatzdateien im Paket werden abgelehnt), nennt neue und geänderte Dateien und den Bestätigungsschlüssel.
2. **`--apply --confirm <Schlüssel>`**: sichert jede überschriebene Datei nach `local_config/update/sicherung/<Zeit>_vor_namenswechsel`, kopiert die neuen Dateien (`local_paths.yaml` und `.bak-`-Dateien bleiben unberührt), benennt den Projektordner um und sichert das alte Programmpaket und die alten Architekturordner nach `…/alt_namen`. Bei einem Fehler nimmt er selbst alles zurück. Das Protokoll liegt in `local_config/update/namenswechsel.json`.
3. **`--rollback`**: stellt Dateien, Ordner und Projektordnernamen wieder her.

SEDRA vorher beenden. Danach laufen weitere Updates wieder über den eingebauten Updater, weil die Installation die neuen Pfade kennt. Der Updater-Weg über das GitHub-Release (Tag `v1.23.0`) bleibt für Installationen vor 1.23.0 gesperrt; sie brauchen dieses Paket. Ein Entwicklungsordner, der per `git merge` nachzieht, braucht den Installer nicht: `START_SEDRA.bat` führt den Übergang aus.

## Grenzen

- Gespeicherte Werte in laufenden Datenbanken (Registry-Einträge der Agenten-Vorlagen mit den alten Kennungen) werden nicht umgeschrieben. Neue Vorlagen werden unter den neuen Kennungen angelegt; Altzuweisungen bleiben als Verlauf lesbar.
- Geprüft sind: der volle Testlauf der schnellen Gruppen (4447 Tests, 0 rot), der Start des Servers mit den neuen Namen und mit einer Kopie der echten Registry, und der Umstieg Ende zu Ende an einer wegwerfbaren Kopie einer Installation mit den alten Namen (Vorschau, Anwenden, Serverstart, Rollback: alle 2502 Dateien des alten Stands unverändert zurück). Ein Lauf mit Modell und die Browser-Bahn stehen aus.

## Prüfung

- `runtime/tests/test_keine_alten_namen.py`: kein alter Name in Dateinamen oder Inhalt außerhalb des Verlaufs.
- `runtime/tests/test_legacy_names.py`: Umzug des Projektordners, Sicherung statt Löschen, zweiter Lauf tut nichts, Umgebungsvariablen.
- `runtime/tests/test_install_namenswechsel.py`: Vorschau schreibt nichts, falsche Bestätigung schreibt nichts, Anwenden sichert und stellt um, Rollback stellt den Ausgangszustand byte-gleich her, falsche Prüfsumme, fremder Manifestpfad und eingeschmuggelte Datei werden abgelehnt.
