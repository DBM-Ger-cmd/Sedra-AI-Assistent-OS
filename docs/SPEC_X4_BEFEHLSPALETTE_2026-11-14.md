# Spec X4 – Befehlspalette & Tastaturkürzel (UIX Bedienung)

> **Prüfvermerk des Koordinators (14.11.2026):** Entwurf von Pi (A-011), nachgeprüft: 20 Anforderungs-IDs (X4-01 bis -20), 183 Zeilen (Pis Angabe stimmt), harte Regel mit Gegenproben (Schreibwerkzeug aus der Palette nur über Antrag und Captain-Freigabe), UI-Regeln benannt, keine lokalen Pfade. Hinweis für den Bau: Die Palette ruft Werkzeuge nur über denselben Weg wie der Chat auf (Freigabe-Einstufung in `harness/katalog.py`/`desk/freigabeklasse.py`), nie direkt; Tastaturkürzel dürfen keine Kürzel des Browsers oder der Bedienungshilfen belegen. Status: Entwurf, noch nicht vom Captain freigegeben.


**Stand:** 2026-11-14  
**Register:** SEDRA-X4  
**Abhängig von:** W3 (Werkzeuge `desktop_aendern`, `profil_wechseln`, auf main), X1 (Alltag, auf main)  
**Quellen:** `docs/ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05.md` (Stufe X4, Abschnitt 2), `runtime/src/sedra_runtime/uix/` (Shell-Code, nur benennen, nichts ändern)  
**Ziel:** Spec für Befehlspalette und Tastaturkürzel – **kein Code**, nur Dokumentation. Datei unter 400 Zeilen.

> **Harte Regel:** Befehle der Palette dürfen **nie** ein Schreibwerkzeug ohne Freigabe auslösen. Jeder Aufruf eines Schreibwerkzeugs über die Palette braucht eine Captain-Freigabe (Karte), wie alle Schreibwerkzeuge in der Harness.  
> **UI-Regeln:** Keine Hex-Farben in Shell-CSS, `textContent` statt `innerHTML`, `setInterval` nur in Taskleiste und Start-Menü, Dateien höchstens 400 Zeilen.

---

## 1. Zweck & Abgrenzung

| Aspekt | Beschreibung |
|---|---|
| **Zweck** | Weniger Klicks: Eine Befehlspalette (Cmd+K / Strg+K) listet alle verfügbaren Befehle, Werkzeuge und Shell-Aktionen. Tastaturkürzel decken die häufigsten Aktionen ab (öffnen, schließen, suchen, speichern, zurück, wiederholen, Hilfe). Vorschläge aus Dateien und Vorlagen werden in die Palette aufgenommen. |
| **Was sie NICHT ist** | Keine direkte Code-Ausführung, kein Schreiben ohne Freigabe, keine Umgehung der Harness-Gates, keine neuen `setInterval` außerhalb Taskleiste/Start-Menü, keine Hex-Farben in Shell-CSS. |
| **Einordnung** | UIX-Stufe X4 der UIX-Roadmap. Läuft als Teil der Shell (`runtime/src/sedra_runtime/uix/`), nicht als separates Chat-Werkzeug. |

---

## 2. Anforderungen (mit IDs)

### 2.1 Befehlspalette

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| X4-01 | Befehlspalette erreichbar über Tastaturkürzel (Cmd+K / Strg+K) und über Menü-Eintrag „Befehle“. | Unit-Test `BefehlspaletteTest.test_palette_offnen_per_kuerzel` |
| X4-02 | Palette listet alle registrierten Befehle: Shell-Aktionen, Chat-Werkzeuge (aus `NAMEN`/`SCHEMAS`), Datei-Öffnen, Vorlagen-Laden, Profil-Wechsel, Einstellungen. | Unit-Test `BefehlspaletteTest.test_palette_listet_befehle` |
| X4-03 | Suche filtert Befehle nach Titel, Beschreibung und Schlagworten (fuzzy, nicht case-sensitiv). | Unit-Test `BefehlspaletteTest.test_palette_suche_filtert` |
| X4-04 | Auswahl eines Befehls führt die zugehörige Aktion aus (Shell-Aktion direkt, Chat-Werkzeug über `Kiste.aufruf`). | Integration-Test `BefehlspaletteTest.test_befehl_ausfuehren` |
| X4-05 | **Schreibwerkzeug ohne Freigabe:** Auswahl eines Schreibwerkzeugs (z. B. `datei_schreiben`, `datei_aendern`, `desktop_aendern`) in der Palette legt **keine direkte Wirkung** aus, sondern einen Antrag im Posteingang des Captains an (Karte mit Freigabe). | Integration-Test `BefehlspaletteTest.test_schreibwerkzeug_ohne_freigabe_ablehnen` |
| X4-06 | Schreibwerkzeug mit Freigabe: Nach Captain-Entscheidung `erlauben` wird das Werkzeug ausgeführt, sonst nicht. | Integration-Test `BefehlspaletteTest.test_schreibwerkzeug_mit_freigabe_ausfuehren` |
| X4-07 | Vorschläge aus Dateien und Vorlagen erscheinen als eigene Einträge in der Palette (Titel, Vorschau, Aktion „Öffnen“). | Unit-Test `BefehlspaletteTest.test_vorschlaege_in_palette` |
| X4-08 | Letzte Befehle (History) werden gespeichert und oben angezeigt (max. 10 Einträge, pro Sitzung). | Unit-Test `BefehlspaletteTest.test_historie_letzte_befehle` |

### 2.2 Tastaturkürzel

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| X4-09 | Globale Kürzel: `Strg+K` / `Cmd+K` öffnet die Befehlspalette, `Esc` schließt sie, `Strg+S` speichert (falls Kontext vorhanden), `Strg+Z` / `Strg+Y` Rückgängig/Wiederholen **nur im Builder**. | Unit-Test `TastaturKuerzelTest.test_globale_kuerzel` |
| X4-10 | Builder-spezifische Kürzel: `Strg+Z` Rückgängig, `Strg+Y` Wiederholen im Layout-Builder (Layout-Rückgängig/Wiederholen). | Unit-Test `TastaturKuerzelTest.test_builder_kuerzel` |
| X4-11 | Jedes Kürzel ist in einer zentralen Tabelle registriert (`KUERZEL` in `command.js` oder vergleichbar). Doppelbelegungen werden beim Start erkannt und gemeldet. | Unit-Test `TastaturKuerzelTest.test_kuerzel_doppelt_erkannt` |
| X4-12 | Kürzel lassen sich über Einstellungen anpassen (optional, später). Überschreiben eines belegten Kürzels warnt. | Unit-Test `TastaturKuerzelTest.test_kuerzel_ueberschreiben_warnt` |
| X4-13 | Screenreader-freundliche Beschriftung aller Kürzel (Aria-Labels, Tastatur-Fokus sichtbar). | Einheitstest `TastaturKuerzelTest.test_kuerzel_barrierefrei` |

### 2.3 Vorschläge ausbauen (Dateien, Vorlagen)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| X4-14 | Dateivorschläge: Öffnen einer Datei über die Palette zeigt eine Vorschau (erster Absatz, Metadaten) vor dem Öffnen. | Unit-Test `VorschlaegeTest.test_dateivorschlag_mit_vorschau` |
| X4-15 | Vorlagen-Vorschläge: Laden einer Vorlage (`bauagent`, `modellierer`, `pruefer`, `vorarbeiter`, `masterchat`, `desktop-designer`, `rueckblick`) über die Palette. | Unit-Test `VorschlaegeTest.test_vorlage_vorschlag_laden` |
| X4-16 | Rechtsklick-Module für alle Seiten: Kontextmenü mit den häufigsten Aktionen der Seite (Öffnen, Bearbeiten, Schließen, Verschieben, Duplizieren). | Unit-Test `VorschlaegeTest.test_rechtsklick_module` |

### 2.4 UI-Regeln (harte Anforderungen)

| ID | Anforderung | Gegenprobe (muss fehlschlagen) |
|---|---|---|
| X4-17 | Keine Hex-Farben in Shell-CSS (z. B. `#ff0000`). Farben nur über Token/`tokens.css`. | CSS mit Hex-Farbe → Lint-Fehler / Test `UITest.test_keine_hex_farben` |
| X4-18 | `textContent` statt `innerHTML` überall in Shell-JS. | JS mit `innerHTML` → Test `UITest.test_textcontent_statt_innerhtml` |
| X4-19 | `setInterval` nur in Taskleiste und Start-Menü (keine neuen Intervalle anderswo). | Neues `setInterval` außerhalb → Test `UITest.test_setinterval_nur_taskleiste_startmenue` |
| X4-20 | Dateien höchstens 400 Zeilen. Neue Dateien für Befehlspalette unter 400 Zeilen. | Datei > 400 Zeilen → Test `UITest.test_dateien_max_400_zeilen` |

---

## 3. Datenmodell

| Entität / VO | Felder (Kern) | Herkunft |
|---|---|---|
| `Befehl` | `id`, `titel`, `beschreibung`, `kuerzel` (optional), `kategorie` (shell|werkzeug|datei|vorlage|einstellung), `aktion` (Funktionsreferenz oder String), `schreibwerkzeug` (bool), `freigabe_erforderlich` (bool) | Registrierung |
| `BefehlsEintrag` | `befehl_id`, `titel`, `vorschau` (optional), `kuerzel_anzeige`, `aktiv` (bool) | Palette-Rendering |
| `HistorieEintrag` | `befehl_id`, `zeitpunkt` (ISO8601) | Palette-Nutzung |
| `VorschlagEintrag` | `typ` (datei|vorlage), `pfad` oder `id`, `titel`, `vorschau`, `aktion` | Dateisystem / Vorlagen-Verzeichnis |

---

## 4. Betroffene Dateien (nur benennen)

| Datei / Pfad | Rolle für X4 | Zeilen (ca.) |
|---|---|---|
| `runtime/src/sedra_runtime/uix/command.js` | Befehlspalette-Logik, Kürzel-Tabelle, Aufruf-Dispatch | ~300 (Ziel: ≤ 400) |
| `runtime/src/sedra_runtime/uix/core.js` | Registrierung von Befehlen beim Start, Kürzel-Doppelbelegung prüfen | ~450 (nur lesen) |
| `runtime/src/sedra_runtime/uix/eingabe.js` | Fokus auf Palette, Tastatur-Events an Palette weiterleiten | ~350 (nur lesen) |
| `runtime/src/sedra_runtime/uix/desktop.js` | Builder: Layout-Rückgängig/Wiederholen (`Strg+Z`/`Strg+Y`) | ~400 (nur lesen) |
| `runtime/src/sedra_runtime/uix/startmenue.js` | `setInterval` erlaubt (Taskleiste/Start-Menü), keine neuen Intervalle für Palette | ~300 (nur lesen) |
| `runtime/src/sedra_runtime/uix/taskleiste.js` | `setInterval` erlaubt (Taskleiste/Start-Menü) | ~350 (nur lesen) |
| `runtime/src/sedra_runtime/uix/tokens.css` | Farb-Token (keine Hex-Farben in anderen CSS-Dateien) | ~150 (nur lesen) |
| `runtime/src/sedra_runtime/uix/shell.css` | Shell-Styling (keine Hex-Farben, nur Token) | ~550 (nur lesen, Ziel: Aufteilung ≤ 400) |
| `runtime/src/sedra_runtime/harness/werkzeuge.py` | `NAMEN`, `SCHEMAS` – Chat-Werkzeuge für Palette-Aufrufe | ~860 (nur lesen, nicht ändern) |
| `runtime/src/sedra_runtime/harness/freigabe.py` | Gate für Schreibwerkzeuge aus der Palette | ~700 (nur lesen) |

---

## 5. UI-Regeln im Detail

| Regel | Beschreibung | Wo geprüft |
|---|---|---|
| **Keine Hex-Farben in Shell-CSS** | Alle Farben über `tokens.css` Variablen (`--farbe-akzent`, `--farbe-hintergrund`, …). Keine `#rrggbb` in `shell.css`, `desktop.css`, `einstellungen.css`, etc. | `UITest.test_keine_hex_farben` |
| **`textContent` statt `innerHTML`** | Kein `innerHTML` in Shell-JS-Dateien. Text nur über `textContent` setzen, HTML nur über Template-Funktionen mit Escaping. | `UITest.test_textcontent_statt_innerhtml` |
| **`setInterval` nur Taskleiste/Start-Menü** | Neue `setInterval`-Aufrufe nur in `taskleiste.js` und `startmenue.js`. Befehlspalette nutzt nur Event-Listener (kein Polling). | `UITest.test_setinterval_nur_taskleiste_startmenue` |
| **Dateien ≤ 400 Zeilen** | Neue Dateien für Befehlspalette (`command.js` Ergänzungen, Palette-UI) unter 400 Zeilen. Bestehende große Dateien nicht weiter wachsen lassen. | `UITest.test_dateien_max_400_zeilen` |

---

## 6. Tests (Namen und was sie prüfen)

| Testdatei | Testklasse / Funktion | Prüft |
|---|---|---|
| `test_uix_befehlspalette.py` (neu) | `BefehlspaletteTest` | Palette öffnen, Befehle auflisten, Suche filtern, Befehl ausführen, Schreibwerkzeug ohne Freigabe → Antrag, Schreibwerkzeug mit Freigabe → Ausführung, Vorschläge, Historie |
| `test_uix_tastaturkuerzel.py` (neu) | `TastaturKuerzelTest` | Globale Kürzel, Builder-Kürzel, Doppelbelegung, Überschreiben-Warnung, Barrierefreiheit |
| `test_uix_vorschlaege.py` (neu) | `VorschlaegeTest` | Dateivorschlag mit Vorschau, Vorlagen-Vorschlag, Rechtsklick-Module |
| `test_uix_ui_regeln.py` (neu) | `UITest` | Keine Hex-Farben, `textContent` statt `innerHTML`, `setInterval` nur Taskleiste/Start-Menü, Dateien ≤ 400 Zeilen |
| `test_uix_rechtsklick.py` (neu) | `RechtsklickTest` | Kontextmenü pro Seite mit üblichen Aktionen |

**Testprinzip:** Keine Browser-Tests (Playwright) für MVP, nur Unit-/Integrationstests mit gemocktem Shell-Umfeld. `SEDRA_WISSEN_STANDARD=aus`.

---

## 7. Freigabegrenzen & Gegenproben (harte Anforderungen)

| Grenze | Beschreibung | Gegenprobe (muss fehlschlagen) |
|---|---|---|
| **Schreibwerkzeug nie ohne Freigabe** | Befehl aus Palette, der ein Schreibwerkzeug aufruft, braucht immer Captain-Freigabe (Karte). Keine direkte Ausführung. | Schreibwerkzeug per Palette ohne Gate → 403 `gate_required` / Antrag statt Wirkung |
| **Keine Umgehung der Harness-Gates** | Palette nutzt denselben `Kiste.aufruf`-Pfad wie der Chat. Keine Abkürzung. | Direkter Aufruf um Gate herum → Test fehlschlägt |
| **Keine Hex-Farben** | Shell-CSS enthält keine `#rrggbb`-Werte. | CSS mit Hex-Farbe → Lint/Test fehlschlägt |
| **`innerHTML` verboten** | Shell-JS nutzt kein `innerHTML`. | JS mit `innerHTML` → Test fehlschlägt |
| **`setInterval` nur erlaubtorte** | Kein neues `setInterval` außerhalb `taskleiste.js`/`startmenue.js`. | Neues `setInterval` elsewhere → Test fehlschlägt |
| **Dateien ≤ 400 Zeilen** | Neue Dateien für X4 unter 400 Zeilen. | Datei > 400 Zeilen → Test fehlschlägt |

---

## 8. Reihenfolge der Schritte (Implementierungsfolge, für späteren Auftrag)

1. **Befehlspalette-Gerüst** in `command.js` (Öffnen/Schließen, Rendering, Suche).
2. **Kürzel-Tabelle** in `command.js` oder `core.js` (globale + Builder-Kürzel).
3. **Registrierung aller Befehle** (Shell-Aktionen, Chat-Werkzeuge aus `NAMEN`, Dateien, Vorlagen, Einstellungen).
4. **Dispatch:** Shell-Aktion direkt, Chat-Werkzeug über `Kiste.aufruf`, Schreibwerkzeug → Antrag/Karte.
5. **Vorschläge:** Datei- und Vorlagen-Vorschläge in die Palette aufnehmen.
6. **Rechtsklick-Module:** Kontextmenü für alle Seiten.
7. **UI-Regeln prüfen:** Keine Hex-Farben, `textContent`, `setInterval`-Ort, Dateien ≤ 400 Zeilen.
8. **Tests schreiben** (siehe §6).
9. **Abnahme:** Palette öffnet, Kürzel wirken, Schreibwerkzeuge brauchen Freigabe, UI-Regeln eingehalten.

---

## 9. Offene Fragen (mit Vorschlag)

| Frage | Vorschlag | Begründung |
|---|---|---|
| X4-Q1: Wo wird die Befehls-Historie gespeichert? | Nur im Speicher der Sitzung (nicht persistent), max. 10 Einträge. | Einfachheit, keine Dateiänderung ohne Freigabe. |
| X4-Q2: Welche Kürzel sind standardmäßig belegt? | `Strg+K` Palette, `Esc` schließen, `Strg+S` speichern, `Strg+Z`/`Strg+Y` nur Builder. | Wenige, gut bekannte Kürzel, keine Konflikte mit Browser. |
| X4-Q3: Darf die Palette auch Schreibwerkzeuge mit `frei`-Einstufung direkt ausführen? | Nein. Selbst `frei` erfordert über die Palette eine Karte (Vorsorge gegen versehentliche Auslösung). | Schreibwerkzeuge nie ohne Freigabe aus der Palette heraus. |
| X4-Q4: Wie werden Vorschläge aus Dateien gefunden? | Über `dateien_auflisten` + Endpunkt-Muster (`.md`, `.json`, `.html` im Schreibbereich). | Kein globales Dateisystem-Scannen, nur Schreibbereich. |
| X4-Q5: Gibt eine Such-History für Befehle? | Ja, die letzten 10 Befehle pro Sitzung, oben in der Palette. | Schnellere Wiederholung häufiger Aktionen. |

---

## 10. Anforderungs-IDs (Zusammenfassung)

X4-01 bis X4-20 (20 Anforderungen).  
Offene Fragen: X4-Q1 bis X4-Q5 (5 Fragen).

---

## 11. Referenzen (nur Lesen)

- `docs/ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05.md`: Stufe X4 (Bedienung), UI-Regeln (Abschnitt 2).
- `runtime/src/sedra_runtime/uix/command.js`: Befehlspalette, Kürzel (geplant).
- `runtime/src/sedra_runtime/uix/core.js`: Registrierung, Kürzel-Doppelbelegung.
- `runtime/src/sedra_runtime/uix/eingabe.js`: Fokus, Tastatur-Events.
- `runtime/src/sedra_runtime/uix/desktop.js`: Builder Rückgängig/Wiederholen.
- `runtime/src/sedra_runtime/uix/taskleiste.js`, `startmenue.js`: `setInterval` erlaubt.
- `runtime/src/sedra_runtime/uix/tokens.css`: Farb-Token.
- `runtime/src/sedra_runtime/uix/shell.css`: Shell-Styling (keine Hex-Farben).
- `runtime/src/sedra_runtime/harness/werkzeuge.py`: `NAMEN`, `SCHEMAS` für Chat-Werkzeug-Aufrufe.
- `runtime/src/sedra_runtime/harness/freigabe.py`: Gate für Schreibwerkzeuge.

---

**Ende der Spec X4.**  
Kein Code geschrieben. Dokument liegt im Worktree `pi-a011` unter `docs/SPEC_X4_BEFEHLSPALETTE_2026-11-14.md`.
