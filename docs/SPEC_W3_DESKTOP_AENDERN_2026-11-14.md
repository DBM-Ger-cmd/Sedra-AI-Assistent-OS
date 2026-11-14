# Spec W3 – Chat baut die Oberfläche mit (desktop_aendern, profil_wechseln)

**Stand:** 2026-11-14  
**Quelle:** `docs/ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05.md` Abschnitt 3 (W3)  
**Regel für jedes neue Werkzeug:** Schema in `SCHEMAS`, Zweig in `vorbereiten`/`ausführen`, Eintrag in `HARNESS_WEGE`/`HARNESS_UNTERWEGE`/`ROUTEN_HARNESS`, Regex in `harness/api.py` (`WEG`/`GESCHUETZT`), Karte im Katalog (oder `OHNE_KARTE`), Test; Schreibwerkzeuge nie ohne Freigabe.  
**Ziel:** Spec für zwei Werkzeuge – **kein Code**, nur Dokumentation. Dateien unter 400 Zeilen.

> **Prüfvermerk des Koordinators (14.11.2026):** Entwurf von Pi (A-006), formal nachgeprüft. Bezeichner `vorbereiten`, `ausfuehren`, `speichern`, `einstufen`, `GESCHUETZT`, `SCHEMAS` existieren im Code. **Lücke:** `HARNESS_WEGE`, `HARNESS_UNTERWEGE` und `ROUTEN_HARNESS` stehen in `desk/freigabeklasse.py`, nicht in `harness/`; diese Datei gehört in die Liste der betroffenen Dateien (Abschnitt 2) und in die Implementierungsfolge (Abschnitt 8). Die vier offenen Fragen in Abschnitt 9 sind noch nicht vom Captain entschieden; vor Code keine Umsetzung.

---

## 1. Überblick W3

| Werkzeug | Zweck | Art | Freigabe |
|---|---|---|---|
| `desktop_aendern` | Profil/Layout der Oberfläche ändern – **nur als Vorschlag mit Vorschau**, Übernahme per Freigabe (Captain) | Schreibwerkzeug (Wirkung auf `desktop.json` + Profile) | `captain` (Karte mit Diff-Vorschau) |
| `profil_wechseln` | Ein gespeichertes Profil oder eine Vorlage als aktive Wahl anwenden | Schreibwerkzeug (setzt `profil` in `desktop.json`) | `captain` (Karte mit Vorschau der Änderungen) |

Beide Werkzeuge **ändern nichts unmittelbar**. Sie legen eine **Karte** vor, der Captain entscheidet (`erlauben`/`ablehnen`). Erst nach Freigabe wird die Wahl/ das Profil gespeichert und die Oberfläche meldet die Änderung über `harness.desktop` Event.

---

## 2. Betroffene Dateien (nur lesen und benennen)

| Datei | Rolle für W3 | Zeilen (ca.) |
|---|---|---|
| `harness/werkzeuge.py` | Schemas (`SCHEMAS`), `NAMEN`, `WIRKUNGSKLASSE`, `Werkzeuge.vorbereiten`/`ausfuehren` für beide Werkzeuge | ~860 (Ziel: ≤ 400 durch Auslagerung) |
| `harness/katalog.py` | `WERKZEUGE`, `OHNE_KARTE`, `einstufen` – neue Werkzeuge eintragen, Freigabestufe default `captain` | ~400 |
| `harness/desktop.py` | `laden`, `speichern`, `profil_anwenden`, `vorlage_uebernehmen`, `pruefen`, `aktion` – Kernlogik für Profil/Layout | ~650 (Ziel: ≤ 400 durch Auslagerung) |
| `harness/api.py` | `WEG`/`GESCHUETZT` Regex, Endpunkte `GET/POST desktop`, `POST desktop/aktion` (Profil-Aktionen) | ~1860 (nur Regex-Einträge hinzufügen) |
| `harness/freigabe.py` | `Kiste.aufruf` – Guard-Gate für Schreibwerkzeuge, Karte anlegen, `beantworten` | ~700 (unverändert, nur neue Werkzeuge laufen drüber) |
| `harness/oberflaeche.py` | (Bestand) Rückhalde von Oberflächen-Dateien unter Aufgabe – für W3 **nicht** genutzt (keine Aufgabe) | – |

**Hinweis:** `harness/werkzeuge.py` und `harness/desktop.py` überschreiten 400 Zeilen. Für W3 ist **kein Code zu schreiben**, aber die Spec nennt, wo die neuen Werkzeuge einzuordnen sind. Eine spätere Aufteilung (z. B. `werkzeuge_desktop.py`, `desktop_profil.py`) ist separat zu planen.

---

## 3. Werkzeug: `desktop_aendern`

### 3.1 Zweck
Ändert den Zuschnitt der Oberfläche (Start-Menü, Taskleiste, Marke, Startseite, Layout, Zonen).  
**Wichtig:** Der Aufruf **schreibt nicht direkt**. Er erstellt einen **Vorschlag** (Diff gegen aktuelle Wahl), legt eine **Karte** vor, der Captain sieht die Vorschau und entscheidet. Erst bei `erlauben` wird `harness/desktop.py:speichern` bzw. `aktion` aufgerufen.

### 3.2 Eingabeschema (für `SCHEMAS` in `werkzeuge.py`)

```python
'desktop_aendern': _fn('desktop_aendern',
    'Ändert den Zuschnitt der Oberfläche (Profil/Layout). Liefert einen Vorschlag mit Diff-Vorschau; der Captain entscheidet per Freigabe. '
    'Teile: start, zellen, marke, startseite, layout. null setzt einen Teil auf die Vorgabe der Shell zurück.',
    {
        'start': {'type': 'object', 'properties': {
            'ausblenden': {'type': 'array', 'items': {'type': 'string'}, 'description': 'IDs auszublendender Bausteine (Grundfunktionen nie möglich)'},
            'zuordnung': {'type': 'object', 'additionalProperties': {'type': 'string', 'enum': ['arbeit','modelle','token','wissen','system','pruefung']}, 'description': 'Baustein → Gruppe im Start-Menü'}
        }, 'description': 'Start-Menü: Ausblenden und Gruppenzuordnung'},
        'zellen': {'type': 'object', 'properties': {
            'ausblenden': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Zellen der Taskleiste auszublenden (Freigaben-Zelle nie)'},
            'reihenfolge': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Reihenfolge der Zellen'}
        }, 'description': 'Taskleiste (Zellen): Ausblenden und Reihenfolge'},
        'marke': {'type': 'object', 'properties': {
            'name': {'type': 'string', 'maxLength': 40},
            'akzent': {'type': 'string', 'pattern': '^#[0-9a-fA-F]{6}$', 'description': 'Hex-Farbe #rrggbb'},
            'logo': {'type': 'string', 'description': 'Data-URL (PNG/JPEG/WebP/SVG, base64, max 200k Zeichen)'},
            'schrift': {'type': 'string', 'enum': ['', 'serif', 'mono', 'humanist', 'breit']}
        }, 'description': 'Marke: Name, Akzentfarbe, Logo, Schrift'},
        'startseite': {'type': 'object', 'properties': {
            'ort': {'type': 'string', 'description': 'Ort-Kennung (ui/places.js) der Start-App'},
            'titel': {'type': 'string', 'maxLength': 60},
            'text': {'type': 'string', 'maxLength': 300}
        }, 'description': 'Startseite: welche App beim Start vorn liegt'},
        'layout': {'type': 'object', 'properties': {
            'start': {'type': 'object', 'description': 'Bausteine der leeren Sitzung auf 12-Spalten-Raster: {id: {x,y,b,h,sichtbar}}'},
            'zeile': {'type': 'object', 'properties': {
                'reihenfolge': {'type': 'array', 'items': {'type': 'string'}},
                'ausblenden': {'type': 'array', 'items': {'type': 'string'}}
            }, 'description': 'Zeile unter Eingabefeld (Projekt, Vorlage, Ordner, …)'},
            'werkzeuge': {'type': 'object', 'properties': {
                'reihenfolge': {'type': 'array', 'items': {'type': 'string'}},
                'ausblenden': {'type': 'array', 'items': {'type': 'string'}}
            }, 'description': 'Leiste im Eingabefeld (Plus, Schild, Modell, Mikro, Senden) – Schild und Senden nie ausblendbar'},
            'menue': {'type': 'object', 'properties': {
                'reihenfolge': {'type': 'array', 'items': {'type': 'string'}},
                'ausblenden': {'type': 'array', 'items': {'type': 'string'}}
            }, 'description': 'Abschnitte des Start-Menüs – Gruppen nie ausblendbar'},
            'blick': {'type': 'object', 'properties': {
                'reihenfolge': {'type': 'array', 'items': {'type': 'string'}},
                'ausblenden': {'type': 'array', 'items': {'type': 'string'}}
            }, 'description': 'Kacheln „Auf einen Blick“ – Einstellungen nie ausblendbar'},
            'zonen': {'type': 'object', 'properties': {
                'seite': {'type': 'object', 'properties': {
                    'platz': {'type': 'string', 'enum': ['links', 'rechts']},
                    'breite': {'type': 'integer', 'minimum': 0, 'maximum': 480}
                }},
                'taskleiste': {'type': 'object', 'properties': {
                    'platz': {'type': 'string', 'enum': ['unten', 'oben']}
                }},
                'eingabe': {'type': 'object', 'properties': {
                    'platz': {'type': 'string', 'enum': ['unten', 'oben']},
                    'breite': {'type': 'integer', 'minimum': 0, 'maximum': 1400}
                }}
            }, 'description': 'Seitenaufbau: Platz und Breiten der Zonen'}
        }, 'description': 'Layout: Raster, Leisten, Menü, Blick, Zonen'}
    },
    []  # keine Pflichtfelder – leere Teile heißen „keine Änderung“
)
```

### 3.3 Ausgabe (Plan aus `vorbereiten`)

```python
{
    'ziel': 'desktop/<teil1>,<teil2>',           # z. B. "desktop/start,layout"
    'vorhanden': True,
    'vorschau': 'Diff-Text (Einheitlich: desktop.py.pruefen normiert, dann Diff alt vs. neu)',  # für Karte
    'kurz': 'Desktop: start, layout',
    'fsargs': None,                               # kein direkter Schreibvorgang
    'warnung': None,
    'code': False,
    'gate': {
        'aktion': 'update_desktop',               # neue Aktion für Guard
        'ziel': 'desktop/<teil1>,<teil2>',
        'bindung': {'werkzeug': 'desktop_aendern', 'args': {...}, 'diff': '...'}
    },
    'teile': ['start', 'layout'],                 # welche TEILE betroffen
    'diff': '...',                                # vereinheitlichtes Diff (für Vorschau + Guard-Bindung)
    'neu_wahl': {...}                             # normierte neue Wahl (Ergebnis von desktop.pruefen)
}
```

### 3.4 Freigabeklasse
- **Katalog:** Default `captain` (keine `frei`-Regel in der Vorlage).
- **Vorbehalt:** `harness/vorbehalte.py` prüft: Grundfunktionen (`GRUND_START`, `GRUND_ZELLEN`, `GRUND_WERKZEUGE`, `GRUND_MENUE`, `GRUND_BLICK`) dürfen nicht in `ausblenden` stehen → `captain` mit Begründung.
- **Karte:** Art `werkzeug`, `an: captain`, Vorschau = Diff, `gate.aktion = 'update_desktop'`.
- **Guard:** Neue Aktion `update_desktop` in `freigabe.py` / Guard registrieren (nur Token-Ausgabe, keine Logik).

### 3.5 Ausführen (`ausfuehren` in `werkzeuge.py`)
```python
# Nur bei Freigabe (Token vom Guard):
# 1. desktop.speichern(projekt_root, {teil: neu_wahl[teil] for teil in teile})
# 2. Event 'harness.desktop' publizieren (Shell lädt neu)
# 3. Rückgabe: {status: 'ok', ergebnis: 'Desktop aktualisiert (start, layout)', wirkung: True}
```
Kein direkter Dateizugriff – delegiert an `harness/desktop.py:speichern`.

---

## 4. Werkzeug: `profil_wechseln`

### 4.1 Zweck
Wendet ein **gespeichertes Profil** (`profile/<id>.json`) oder eine **Vorlage** (`vorlage/<id>`) als aktive Wahl an.  
Wie `desktop_aendern`: **nur Vorschlag + Karte**, Übernahme per Captain-Freigabe.

### 4.2 Eingabeschema

```python
'profil_wechseln': _fn('profil_wechseln',
    'Wendet ein gespeichertes Profil oder eine Vorlage als aktiven Zuschnitt an. Liefert Vorschau (Diff aktuelle Wahl vs. Profil/Vorlage); Captain entscheidet per Freigabe.',
    {
        'profil': {'type': 'string', 'description': 'ID eines gespeicherten Profils (profile/<id>.json)'},
        'vorlage': {'type': 'string', 'description': 'ID einer Vorlage (aus harness/uix/shells/harness/profile/)'}
    },
    []  # genau eins von profil/vorlage muss gesetzt sein (Validierung in vorbereiten)
)
```

### 4.3 Ausgabe (Plan aus `vorbereiten`)

```python
{
    'ziel': 'profil/<id>' or 'vorlage/<id>',
    'vorhanden': True,
    'vorschau': 'Diff: aktuelle Wahl vs. Profil/Vorlage (nur TEILE, die sich unterscheiden)',
    'kurz': 'Profil wechseln: <id>',
    'gate': {
        'aktion': 'update_desktop',
        'ziel': 'profil/<id>',
        'bindung': {'werkzeug': 'profil_wechseln', 'args': {...}, 'diff': '...', 'quelle': 'profil|vorlage'}
    },
    'quelle': 'profil',          # 'profil' oder 'vorlage'
    'profil_id': 'kmU-standard', # die ID
    'neu_wahl': {...}            # normierte Wahl aus dem Profil/Vorlage (desktop.pruefen)
}
```

### 4.4 Freigabeklasse
- **Katalog:** Default `captain`.
- **Vorbehalt:** Kein spezieller (Profil/Vorlage wurde schon beim Speichern geprüft).
- **Karte:** Art `werkzeug`, `an: captain`, Vorschau = Diff, `gate.aktion = 'update_desktop'`.

### 4.5 Ausführen (`ausfuehren` in `werkzeuge.py`)
```python
# Nur bei Freigabe:
if quelle == 'profil':
    desktop.profil_anwenden(projekt_root, profil_id)
else:
    desktop.vorlage_uebernehmen(projekt_root, profil_id)  # kopiert bei Bedarf nach profile/, dann anwenden
# Event 'harness.desktop' publizieren
# Rückgabe: {status: 'ok', ergebnis: f'Profil {profil_id} angewendet', wirkung: True}
```

---

## 5. Einträge in Katalog & Regex (harness/api.py)

### 5.1 `katalog.py:WERKZEUGE` und `OHNE_KARTE`
```python
# In WERKZEUGE aufnehmen (nach LAUF):
WERKZEUGE = DATEI_WERKZEUGE + ('befehl', 'lauf_starten', 'lauf_stoppen', 'modell_laden', 'modell_entladen', 'auftraege_verteilen') + OHNE_KARTE + ('desktop_aendern', 'profil_wechseln')

# NICHT in OHNE_KARTE – beide brauchen Karte (Schreibwirkung auf Oberfläche)
```

### 5.2 `api.py:WEG` Regex
Bestehender `WEG` matcht `desktop` bereits (GET/POST). Für die neuen Werkzeuge **keine neuen API-Wege nötig** – sie laufen über die bestehende Harness-Werkzeug-Schleife (`/api/harness/...` wird vom Server geroutet, nicht direkt).  
**Aber:** Die Guard-Aktion `update_desktop` muss in `GESCHUETZT` erfasst werden, damit Herkunft geprüft wird (Captain-only):
```python
# In GESCHUETZT ergänzen (oder über bestehende 'desktop' abgedeckt):
GESCHUETZT = re.compile(r'...|desktop|oberflaeche/...')  # 'desktop' deckt POST desktop ab
```
Die Werkzeuge selbst sind **keine API-Endpunkte**, sie werden über die Chat-Schleife aufgerufen.

### 5.3 `api.py:handle` – `POST desktop` (bestehend)
Schon vorhanden: `fest == 'desktop' and method == 'POST'` ruft `harness_desktop.aktion` (Profil-Aktionen) oder `harness_desktop.speichern` (Wahl-Teile).  
**Für W3:** Die Werkzeuge nutzen **nicht** diesen Endpunkt direkt. Sie laufen über `Kiste.aufruf` → `werkzeuge.vorbereiten/ausfuehren` → `desktop.speichern/profil_anwenden`. Der API-Endpunkt bleibt für die Einstellungen-Oberfläche (manuelle Bedienung durch Captain).

---

## 6. Tests (Namen und was sie prüfen)

| Testdatei | Testklasse / Funktion | Prüft |
|---|---|---|
| `test_harness_werkzeuge.py` (neu/erweitern) | `DesktopAendernTest` | Schema gültig, `vorbereiten` liefert Diff, `ausfuehren` nach Freigabe ruft `desktop.speichern`, Event `harness.desktop` wird gepublisht |
| `test_harness_werkzeuge.py` | `ProfilWechselnTest` | Schema gültig, `vorbereiten` lädt Profil/Vorlage, Diff gegen aktuelle Wahl, `ausfuehren` ruft `profil_anwenden`/`vorlage_uebernehmen` |
| `test_harness_katalog.py` (erweitern) | `EinstufenDesktopTest` | `einstufen(regeln, 'desktop_aendern', 'desktop/start')` → `captain` (Default), `verboten`-Regel greift |
| `test_harness_freigabe.py` (erweitern) | `DesktopKarteTest` | Karte wird angelegt mit `aktion='update_desktop'`, `beantworten` mit `erlauben` führt zu `desktop.speichern`, `ablehnen` ändert nichts |
| `test_harness_desktop.py` (erweitern) | `DesktopAendernIntegrationTest` | Ganzheitlich: Werkzeug → Karte → Freigabe → `desktop.laden` spiegelt neue Wahl, `harness.desktop` Event |
| `test_uix_harness_desktop.py` (erweitern) | `DesktopAendernBrowserTest` | (Optional, Browser) Oberfläche lädt neue Wahl nach Freigabe (Playwright) |

**Testprinzip:** Kein `appium`, nur Unit-Tests mit gemocktem `guard`, `projekt_root` (Temp-Ordner). `SEDRA_WISSEN_STANDARD=aus`.

---

## 7. Grenzen & Regeln

1. **Keine unmittelbare Wirkung.** Beide Werkzeuge legen **immer** eine Karte vor. `frei` im Katalog ist für diese Werkzeuge **nicht vorgesehen** (auch nicht per Regel des Captains – `vorbehalte.py` kann `verboten` erzwingen, aber `frei` würde die Vorschau umgehen).
2. **Grundfunktionen unantastbar.** `desktop.pruefen` lehnt Ausblenden von `GRUND_START`, `GRUND_ZELLEN`, `GRUND_WERKZEUGE`, `GRUND_MENUE`, `GRUND_BLICK` ab → Vorbehalt `captain` mit Begründung.
3. **Profil vs. Vorlage.** `profil_wechseln` mit `vorlage` kopiert die Vorlage einmalig nach `profile/` (wie `vorlage_uebernehmen`), dann anwenden. Ein vorhandenes Profil gleicher ID bleibt unberührt (PR-E2).
4. **Layout-Raster.** `desktop_aendern` mit `layout.start` validiert gegen `RASTER_SPALTEN=12`, `RASTER_ZEILEN=40`, `RASTER_HOEHE=20`. Ungültige Koordinaten → `WerkzeugFehler` in `vorbereiten`.
5. **Zeilengrenzen.** `harness/werkzeuge.py` und `harness/desktop.py` sind > 400 Zeilen. Für W3 **kein Refactoring**, aber die Spec dokumentiert, wo neue Funktionen einzufügen sind. Spätere Aufteilung: `werkzeuge_desktop.py` (beide Werkzeuge), `desktop_profil.py` (Profil-Logik).
6. **Keine Aufgabe-Deckung.** Diese Werkzeuge sind **nicht** über Aufgaben freigebar (`via_aufgabe` in `Kiste.aufruf` bleibt `None`), da sie keine Code-Änderungen sind, sondern Oberflächen-Zuschnitt. Nur Captain oder Sitzungs-Erlaubnis (selten).
7. **Guard-Aktion `update_desktop`.** Neu in `freigabe.py` / Guard registrieren. `rollback_available=True` (da `desktop.speichern` atomar mit `.tmp` schreibt, alte Wahl kann wiederhergestellt werden).

---

## 8. Reihenfolge der Schritte (Implementierungsfolge)

1. **Schemas in `werkzeuge.py:SCHEMAS`** eintragen (`desktop_aendern`, `profil_wechseln`).
2. **`NAMEN`, `WIRKUNGSKLASSE`, `WERKZEUGE` (katalog.py)** erweitern.
3. **`vorbereiten` in `Werkzeuge`** für beide Werkzeuge implementieren (Diff-Erstellung via `desktop.pruefen` + `bereinigt`, Vergleich mit `laden`).
4. **`ausfuehren` in `Werkzeuge`** für beide (Delegation an `desktop.speichern` / `profil_anwenden` / `vorlage_uebernehmen`).
5. **Guard-Aktion `update_desktop`** in `freigabe.py` / Guard bekannt machen.
6. **Katalog-Vorlage** (`freigabe_katalog.beispiel.yaml`) um Default-Regeln für `desktop_aendern`/`profil_wechseln` → `captain` ergänzen.
7. **Tests** schreiben (siehe §6).
8. **API-Regex prüfen** (`GESCHUETZT` deckt `desktop` ab – OK).

---

## 9. Offene Fragen / Entscheidungsbedarf

| Frage | Vorschlag | Entscheidung |
|---|---|---|
| Soll `desktop_aendern` auch `profil` setzen/klaren? | Nein – `profil` wird nur durch `profil_wechseln` oder manuell im Builder gesetzt. `desktop_aendern` ändert nur die **Wahl** (`start`, `zellen`, `marke`, `startseite`, `layout`). `profil` bleibt, bis explizit gewechselt. | Offen |
| `update_desktop` als eigene Guard-Aktion oder `write_text` wiederverwenden? | Eigene Aktion (`update_desktop`), da Ziel `desktop/...` keine Datei im Schreibbereich ist, sondern ein logischer Schlüssel. Guard prüft nur Token, Logik in `werkzeuge.py`. | Offen |
| Diff-Format für Vorschau? | Einheitlich: `difflib.unified_diff` über JSON-Dump (sortiert, indent=1) von `alt_wahl` vs. `neu_wahl`. In Karte als Text. | Offen |
| Sitzungs-Erlaubnis für `desktop_aendern` zulassen? | Ja (wie bei `datei_schreiben`), aber **nicht** für Vorbehaltsfälle (Grundfunktionen). | Offen |

---

## 10. Dateien-Referenz (für Implementierer)

| Datei | Stelle | Was hinzufügen |
|---|---|---|
| `harness/werkzeuge.py` | `SCHEMAS` | Zwei `_fn`-Einträge (siehe §3.2, §4.2) |
| `harness/werkzeuge.py` | `NAMEN` | `+ ('desktop_aendern', 'profil_wechseln')` |
| `harness/werkzeuge.py` | `WIRKUNGSKLASSE` | `'desktop_aendern': 'reversible_write', 'profil_wechseln': 'reversible_write'` |
| `harness/werkzeuge.py` | `Werkzeuge.vorbereiten` | `elif name == 'desktop_aendern': ...` und `elif name == 'profil_wechseln': ...` |
| `harness/werkzeuge.py` | `Werkzeuge.ausfuehren` | `elif name in ('desktop_aendern', 'profil_wechseln'): ...` |
| `harness/katalog.py` | `WERKZEUGE` | Beide Namen anhängen |
| `harness/katalog.py` | `pruefen` | Erlaubt neue Werkzeug-Namen (automatisch durch `WERKZEUGE`) |
| `harness/desktop.py` | (keine Änderung) | Bestehende `speichern`, `profil_anwenden`, `vorlage_uebernehmen`, `pruefen`, `laden` nutzen |
| `harness/freigabe.py` | Guard-Aktionen | `update_desktop` in `risks`/`rollback_available` bekannt |
| `runtime/config/freigabe_katalog.beispiel.yaml` | `regeln` | Zwei Default-Regeln: `desktop_aendern` → `captain`, `profil_wechseln` → `captain` |
| `test_harness_werkzeuge.py` | neu/erweitern | Testklassen `DesktopAendernTest`, `ProfilWechselnTest` |
| `test_harness_katalog.py` | erweitern | `einstufen` für neue Werkzeuge |
| `test_harness_freigabe.py` | erweitern | Karte `update_desktop` erlauben/ablehnen |
| `test_harness_desktop.py` | erweitern | Integrationstest Werkzeug → Karte → Freigabe → `laden` |

---

**Ende der Spec.**  
Kein Code geschrieben. Dokument liegt im Worktree `pi-a006` unter `docs/SPEC_W3_DESKTOP_AENDERN_2026-11-14.md`.