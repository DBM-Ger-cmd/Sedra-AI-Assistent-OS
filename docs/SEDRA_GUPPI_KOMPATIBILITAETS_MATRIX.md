# SEDRA/GUPPI Kompatibilitätsmatrix (F1-01)

**Status:** Entwurf für F1-01 (IN_DEVELOPMENT)  
**Basis:** lokaler `main` = `74bf792`  
**Ziel:** GUPPI nur noch in der Historie (Captain-Ziel). Alte Bezeichnungen werden als Legacy erkannt und migriert, nie neu geschrieben.

## 1. Übersicht der Namensklassen

| Klasse | Alter Name (GUPPI) | Neuer Name (SEDRA) | Übergang | Letzte Neuschreibung |
|---|---|---|---|---|
| Paket | `guppi_runtime` | `sedra_runtime` | `legacy_names.py` (sichert alt, kopiert nicht neu) | Nie mehr (nur lesen für alte Installationen) |
| Projektordner | `GUPPI_OS` | `SEDRA_OS` | `legacy_names.umziehen()` (benennt um, sichert alt) | Nie mehr |
| Architekturordner | `GUPPI_Architecture_*` | `SEDRA_Architecture_*` | `legacy_names.umziehen()` (sichert alt) | Nie mehr |
| Umgebungsvariable | `GUPPI_*` | `SEDRA_*` | `legacy_names.env_aliase()` (spiegelt, wenn neu fehlt) | Nie mehr |
| Engine-Manifest | `guppi_engine.json` | `sedra_engine.json` | `engine_provision.LEGACY_MANIFESTS` (nur lesen) | Nie mehr |
| Anzeige / Doku | Wort "GUPPI" | Wort "SEDRA" | — | Nicht mehr in neuem Code |

## 2. Technische Details je Klasse

### 2.1 Paketname (`guppi_runtime` → `sedra_runtime`)
- **Wo ercodiert war:** `runtime/src/guppi_runtime/` (alles)
- **Neuer Ort:** `runtime/src/sedra_runtime/` (alles)
- **Übergang:** `legacy_names.py` definiert `PAKET_ALT = 'guppi_runtime'` und `PAKET_NEU = 'sedra_runtime'`. Altes Paket wird gesichert (nicht gelöscht), neues ist aktiv.
- **Prüfung:** Keine Datei unter `runtime/src/sedra_runtime/` darf `guppi_runtime` als Import oder Pfad referenzieren.

### 2.2 Projektordner (`GUPPI_OS` → `SEDRA_OS`)
- **Wo ercodiert war:** `workspace/GUPPI_OS`
- **Neuer Ort:** `workspace/SEDRA_OS`
- **Übergang:** `legacy_names.umziehen()` benennt um, wenn der neue Ordner noch nicht existiert. Existieren beide, wird nichts verschoben (Hinweis).
- **Prüfung:** `workspace/GUPPI_OS` darf nicht mehr als aktiver Projektordner verwendet werden.

### 2.3 Architekturordner (`GUPPI_Architecture_*` → `SEDRA_Architecture_*`)
- **Wo ercodiert war:** `architecture/GUPPI_Architecture_*`
- **Neuer Ort:** `architecture/SEDRA_Architecture_*`
- **Übergang:** `legacy_names.umziehen()` sichert alte Ordner nach `local_config/update/sicherung/alt_namen/`.
- **Prüfung:** Kein neuer Code unter `architecture/GUPPI_Architecture_*`.

### 2.4 Umgebungsvariablen (`GUPPI_*` → `SEDRA_*`)
- **Wo ercodiert war:** `GUPPI_API_KEY`, `GUPPI_ENDPOINT`, etc.
- **Neuer Ort:** `SEDRA_API_KEY`, `SEDRA_ENDPOINT`, etc.
- **Übergang:** `legacy_names.env_aliase()` kopiert alte Variablen auf neue, wenn die neue noch nicht gesetzt ist. Gibt die neu gesetzten Namen zurück.
- **Prüfung:** Neue Installation setzt nur `SEDRA_*`-Variablen.

### 2.5 Engine-Manifest (`guppi_engine.json` → `sedra_engine.json`)
- **Wo ercodiert war:** `engines/llama.cpp/<build>/guppi_engine.json`
- **Neuer Ort:** `engines/llama.cpp/<build>/sedra_engine.json`
- **Übergang:** `engine_provision.LEGACY_MANIFESTS = ("guppi_engine.json",)` — wird bei `verify_engine()` mitgelesen, aber nie neu geschrieben. `_manifest_path()` prüft zuerst `sedra_engine.json`, dann `guppi_engine.json`.
- **Prüfung:** Neue Installation schreibt nur `sedra_engine.json`.

### 2.6 Anzeige und Dokumentation (Wort "GUPPI" → Wort "SEDRA")
- **Zählung auf main (06.11.2026):** GUPPI in 7909 Zeilen, 1096 Dateien, 1107 Dateinamen; Wort GUPPI in Anzeige und Doku 2058 Treffer.
- **Übergang:** Logbuch, `historie/`, `concept_review/` und datierte Berichte bleiben unverändert (siehe SEDRA-NAME-01 Acceptance).
- **Prüfung:** Neuer Code und neue Dokumentation verwenden nur "SEDRA".

## 3. Mapping, Backup, Deprecation und Rollback

| Klasse | Mapping | Backup | Deprecation | Rollback |
|---|---|---|---|---|
| Paket | `guppi_runtime` → `sedra_runtime` | Altes Paket gesichert unter `local_config/update/sicherung/alt_namen/` | `guppi_runtime` Imports sind veraltet, werden aber beim Lesen alter Installationen toleriert | `legacy_names.py` kann zurückgesichert werden (kein automatischer Rückweg im neuen Code) |
| Projektordner | `GUPPI_OS` → `SEDRA_OS` | Altes Verzeichnis umbenannt (nicht kopiert) | `GUPPI_OS` als Projektordner veraltet | Manuell rückbenennbar |
| Architekturordner | `GUPPI_Architecture_*` → `SEDRA_Architecture_*` | Gesichert unter `alt_namen/` | Alte Ordner veraltet | Manuell rückbenennbar |
| Umgebungsvariable | `GUPPI_X` → `SEDRA_X` | — | `GUPPI_X` als primäre Variable veraltet (nur Spiegelung) | `SEDRA_X` entfernen, `GUPPI_X` wieder nutzen |
| Engine-Manifest | `guppi_engine.json` → `sedra_engine.json` | — | `guppi_engine.json` wird nur noch gelesen | Manuell zurückkopieren |

## 4. Abnahme (G3-Vorschlag)

1. Keine Datei unter `runtime/src/sedra_runtime/` importiert `guppi_runtime` (Test: `test_f1_01_keine_alten_imports`).
2. Keine Datei unter `runtime/src/sedra_runtime/` referenziert den Pfad `guppi_runtime/` (Test: `test_f1_01_keine_alten_pfade`).
3. `legacy_names.env_aliase()` spiegelt `GUPPI_*` auf `SEDRA_*` (bestehender Test `test_legacy_names.py`).
4. `engine_provision.LEGACY_MANIFESTS` enthält `guppi_engine.json` (bestehender Test `test_engine_provision.py`).
5. `legacy_names.umziehen()` benennt `GUPPI_OS` zu `SEDRA_OS` um (bestehender Test `test_legacy_names.py`).

## 5. Offene Fragen

1. Soll `guppi_engine.json` bei `verify_engine()` künftig ganz entfernt werden (Breaking Change für alte Installationen)? Vorschlag: nein, solange alte Installationen existieren.
2. Soll das Wort "GUPPI" in Logbuch und datierten Berichten durchsuchbar bleiben? Vorschlag: ja, diese sind historisch unverändert (SEDRA-NAME-01 Acceptance).
