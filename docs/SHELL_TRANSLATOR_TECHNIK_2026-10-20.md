# Shell „Translator“ (früher „Fisch“): technische Übersicht

**Stand:** 20.10.2026 · **Zweck:** Zusammenfassung für das Kurs-Dashboard
**Status:** Die Umbenennung von „Fisch“ zu „Translator“ läuft gerade in einer eigenen Sitzung. Die internen Kennungen
(`fisch`, `/api/fisch/…`) bleiben vorerst unverändert. Die Ausbaustufen (Aufnahme, Transkript, Aufwertung) sind
teilweise vorhanden und werden ausgebaut.

## 1. Was die Shell ist

Eine kleine Oberfläche mit einem Goldfischglas, einer Eingabe als Wolke und Antworten als Blasen. Sie hat vier Modi:

| Modus | Inhalt | Werkzeug |
|---|---|---|
| Übersetzen | Text zwischen Rollen übersetzen | `uebersetzer` |
| News | Nachrichten-Brief aus gegebenen Quellen | `nachrichten` |
| Aufnahme | Sprache aufnehmen (Rekorder) | `rekorder` |
| Transkript | Transkript prüfen, durchsuchen, exportieren, Erkenntnisse | `transkript` |

Die Shell kennt kein Werkzeug beim Namen. Sie ist Schale: Die Werkzeuge zeichnen den Inhalt der Blase.

## 2. Bausteine im Code

**Oberfläche** (`runtime/src/guppi_runtime/uix/`)
- `shells/fisch/shell.js` (196 Zeilen), `shell.css` (112), `shell.yaml`, `arbeitsplatz.yaml`, `README.md`
- `tools/uebersetzer/` (103 Zeilen), `tools/nachrichten/` (157), `tools/transkript/` (230), `tools/rekorder/` (199)
- `ui/sprache.js` (100): gemeinsamer Aufnahme-Helfer für alle Werkzeuge
- `fenster/rekorder.html` (107): eigenes Aufnahmefenster, überlebt den Shell-Wechsel
- `ui/wechsel.js`: Rekorder-Leiste unten rechts, in jeder Shell

**Kern** (`runtime/src/guppi_runtime/`)
- `fisch/uebersetzer.py` (60), `fisch/nachrichten.py` (73), `fisch/transkripte.py` (223), `fisch/erkenntnisse.py` (52), `fisch/hub.py` (181)
- `sprache/stt.py` (99): Spracherkennung. Ohne installierten Anbieter sagt der Kern das, statt etwas vorzutäuschen.
- `sprache/aufnahmen.py` (131), `sprache/hub.py` (113)

## 3. Schnittstellen

Die Routen liegen unter `/api/fisch/…` (13 Routen, u. a. `uebersetzen`, `brief`, `profil`, `rollen`,
`transkript`, `transkript/suche`, `transkript/export`, `transkript/import`, `transkript/pseudonymisieren`,
`transkript/erkenntnisse`) und unter `/api/sprache/…` (Aufnahme: `beginnen`, `stueck`, `beenden`, `loeschen`,
`transkribieren`).

Die Schutzregeln des Projekts gelten: Personendaten bleiben lokal, Zugangsdaten werden nie gespeichert, ohne Freigabe
geht nichts in die Cloud.

## 4. Aufnahme und Transkription

- **Aufnahme:** Der Browser nimmt auf. Stücke von etwa 4 Sekunden gehen nacheinander an den Kern, jedes unter dem
  Request-Limit. Die Aufnahme läuft im eigenen Fenster weiter, auch wenn die Hauptseite neu lädt oder die Shell wechselt.
- **Transkription:** Der Kern erkennt einen lokalen Anbieter (whisperx bevorzugt, sonst whisper; ffmpeg muss installiert
  sein). Ohne Anbieter ist der Weg „Abschrift von Hand“. Entscheidung für den Ausbau: offen (siehe Abschnitt 6).
- **Transkript-Datensatz:** Versionen werden angehängt, der Export ändert den Datensatz nie, die Zuordnung von
  Pseudonymen liegt getrennt und wird nicht exportiert.

## 5. Tests (Stand heute)

| Test | Inhalt |
|---|---|
| `test_fisch_kern` | Kern: Übersetzung, Quelle ohne Namen, SRT, Suche, Versionen, Freigabe, Export |
| `test_uix_shell_fisch` | Oberfläche: kein Hex außerhalb der Tokens, je Modus ein Werkzeug, Browser-Ablauf |
| `test_sprache_kern` | Anbieter-Erkennung, Kommandozeile, Stücke, Erkenntnisse |
| `test_uix_rekorder` | Rekorder als Ort jeder Shell, Browser mit Fake-Mikrofon |
| `test_rekorder_fenster` | Aufnahme überlebt das Neuladen der Hauptseite, Stopp speichert |

Stand der letzten Läufe: grün. Die Umbenennung ist noch nicht geprüft.

## 6. Offene Entscheidungen (vom Captain zu klären)

1. **Konzept:** Das Dokument „Translator Fisch (Konzept v0.1)“ liegt als ZIP vor und beschreibt nur die Modi Übersetzen
   und News. Aufnahme, Transkript und Aufwertung stehen dort nicht. Diese Teile folgen aus dem Vorhandenen.
2. **Darstellung am Tag:** Heute dunkel. Ob der Tag hell sein soll, ist nicht entschieden.
3. **Transkription:** Heute ohne Anbieter. Ob whisper oder whisperx angebunden wird, ist nicht entschieden.

## 7. Für das Dashboard

- Kurzbeschreibung: „Translator – Übersetzen, Nachrichten und Transkripte, lokal und mit Schutzregeln.“
- Was live gezeigt werden kann: Übersetzung einer Anfrage, Brief aus gegebenen Quellen, Aufnahme (mit Mikrofon),
  Transkript mit Suche. Ohne Mikrofon und ohne Modell zeigt die Oberfläche den ehrlichen Hinweis, was fehlt.
- Was nicht behauptet werden sollte: eine automatische Transkription ohne installierten Anbieter, eine Cloud-Verarbeitung
  ohne Freigabe, eine Aussage zur Rechtskonformität.
