# Spec X5 – Sprache DE/EN & Barrierefreiheit (UIX Barrierefreiheit)

> **Prüfvermerk des Koordinators (14.11.2026):** Entwurf von Pi (A-011), nachgeprüft: 19 Anforderungs-IDs (X5-01 bis -19), 183 Zeilen, Sprache aus einer Textdatei, Tastatur, Fokus und Screenreader abgedeckt, keine lokalen Pfade. Hinweis für den Bau: X5-04 (Fallback auf DE mit Warnung) darf keine Warnungsflut erzeugen; Übersetzungstexte sind Daten und dürfen nie als HTML eingefügt werden (`textContent`). Status: Entwurf, noch nicht vom Captain freigegeben.


**Stand:** 2026-11-14  
**Register:** SEDRA-X5  
**Abhängig von:** X4 (Befehlspalette, auf main), X3 (Profile, auf main)  
**Quellen:** `docs/ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05.md` (Stufe X5, Abschnitt 2), `runtime/src/sedra_runtime/uix/` (Shell-Code, nur benennen, nichts ändern)  
**Ziel:** Spec für Sprache DE/EN und Barrierefreiheit – **kein Code**, nur Dokumentation. Datei unter 400 Zeilen.

> **Harte Regel:** Sprache wird aus einer Textdatei geladen (keine hardcodierten Strings in Shell-JS). Tastaturbedienung, Fokusreihenfolge und Screenreader-Beschriftung sind Pflicht. Keine Hex-Farben in Shell-CSS, `textContent` statt `innerHTML`, Dateien höchstens 400 Zeilen.

---

## 1. Zweck & Abgrenzung

| Aspekt | Beschreibung |
|---|---|
| **Zweck** | Oberfläche nutzbar für Fremde: Deutsch/Englisch umschaltbar aus einer zentralen Textdatei, vollständige Tastaturbedienung, logische Fokusreihenfolge, Screenreader-Beschriftung (Aria-Labels) auf allen interaktiven Elementen, Kontrastprüfung. |
| **Was sie NICHT ist** | Keine automatische Übersetzung von Inhalten (nur UI-Strings), keine eigene Übersetzungs-Datei pro Seite, keine Änderung von Chat-Werkzeugen oder Harness-Logik, keine hardcodierten Strings in Shell-JS. |
| **Einordnung** | UIX-Stufe X5 der UIX-Roadmap. Läuft als Teil der Shell (`runtime/src/sedra_runtime/uix/`). |

---

## 2. Anforderungen (mit IDs)

### 2.1 Sprache DE/EN

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| X5-01 | UI-Strings in einer zentralen Textdatei (z. B. `ui/strings_de.json`, `ui/strings_en.json` oder vergleichbar). Keine hardcodierten Strings in Shell-JS. | Unit-Test `SpracheTest.test_keine_hardcodierten_strings` |
| X5-02 | Sprache umschaltbar DE ↔ EN (z. B. über Einstellungen oder URL-Parameter), Änderung wirkt sofort (kein Neustart). | Integration-Test `SpracheTest.test_sprache_umschalten` |
| X5-03 | Standardsprache ist Deutsch (DE), falls keine Einstellung vorliegt. | Unit-Test `SpracheTest.test_standardsprache_de` |
| X5-04 | Alle UI-Strings existieren in beiden Sprachen (DE und EN). Fehlende Übersetzung → Fallback auf DE mit Warnung. | Unit-Test `SpracheTest.test_alle_strings_bereitschaft` |
| X5-05 | Sprach-Auswahl ist in den Einstellungen sichtbar und speicherbar (Profil-spezifisch, wie X3 Profile). | Unit-Test `SpracheTest.test_sprache_in_einstellungen` |

### 2.2 Tastaturbedienung

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| X5-06 | Alle interaktiven Elemente (Schaltflächen, Eingabefelder, Links, Menüeinträge) sind per Tastatur erreichbar (Tab-Reihenfolge). | Einheitstest `TastaturTest.test_alle_interaktiven_per_tab` |
| X5-07 | Fokus ist immer sichtbar (Fokus-Ring/Hervorhebung), nie versteckt. | Einheitstest `TastaturTest.test_fokus_sichtbar` |
| X5-08 | Fokusreihenfolge folgt der logischen Leserichtung (oben nach unten, links nach rechts). | Einheitstest `TastaturTest.test_fokus_reihenfolge_logisch` |
| X5-09 | Tastaturkürzel (aus X4) funktionieren unabhängig von Sprache. | Einheitstest `TastaturTest.test_kuerzel_unabhaengig_von_sprache` |
| X5-10 | Eingabefelder sind per Tastatur fokussierbar und beschreibbar. | Einheitstest `TastaturTest.test_eingabefelder_tastatur` |

### 2.3 Screenreader & Barrierefreiheit

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| X5-11 | Alle interaktiven Elemente haben Screenreader-Beschriftung (Aria-Label, Aria-Labelledby oder Aria-Describedby). | Einheitstest `BarrierefreiheitTest.test_aria_labels_vorhanden` |
| X5-12 | Rolle und Zustand von Schaltflächen, Schaltern, Schiebereglern sind über Aria-Attribute beschreibbar (`role`, `aria-pressed`, `aria-expanded`, `aria-checked`). | Einheitstest `BarrierefreiheitTest.test_aria_rolle_und_zustand` |
| X5-13 | Fehlermeldungen und Hinweise werden Screenreadern mitgeteilt (`aria-live` oder vergleichbar). | Einheitstest `BarrierefreiheitTest.test_fehlermeldungen_screenreader` |
| X5-14 | Bilder und Icons haben alternativen Text (`alt` oder Aria-Label), soweit sie nicht rein dekorativ sind. | Einheitstest `BarrierefreiheitTest.test_bilder_alternativtext` |
| X5-15 | Kontrastprüfung: Text auf Hintergrund erfüllt Mindestkontrast (WCAG AA, 4.5:1 für Normaltext, 3:1 für Großtext). | Einheitstest `BarrierefreiheitTest.test_kontrast_wcag_aa` |

### 2.4 UI-Regeln (harte Anforderungen)

| ID | Anforderung | Gegenprobe (muss fehlschlagen) |
|---|---|---|
| X5-16 | Keine Hex-Farben in Shell-CSS. Farben nur über Token/`tokens.css`. | CSS mit Hex-Farbe → Lint-Fehler / Test `UITest.test_keine_hex_farben` |
| X5-17 | `textContent` statt `innerHTML` überall in Shell-JS. | JS mit `innerHTML` → Test `UITest.test_textcontent_statt_innerhtml` |
| X5-18 | `setInterval` nur in Taskleiste und Start-Menü (keine neuen Intervalle anderswo). | Neues `setInterval` außerhalb → Test `UITest.test_setinterval_nur_taskleiste_startmenue` |
| X5-19 | Dateien höchstens 400 Zeilen. Neue Dateien für X5 unter 400 Zeilen. | Datei > 400 Zeilen → Test `UITest.test_dateien_max_400_zeilen` |

---

## 3. Datenmodell

| Entität / VO | Felder (Kern) | Herkunft |
|---|---|---|
| `Sprache` | `code` (de|en), `name` (Deutsch/Englisch), `aktiv` (bool) | Einstellung |
| `StringEintrag` | `schluessel` (z. B. `btn.speichern`), `wert_de`, `wert_en`, `kontext?` | Textdatei |
| `FokusElement` | `id`, `rolle`, `label`, `tab_index` (auto oder explizit) | DOM-Analyse |
| `BarrierefreiheitPruefung` | `element_id`, `kontrast_ok`, `aria_label_ok`, `fokus_sichtbar` | Prüfung |

---

## 4. Betroffene Dateien (nur benennen)

| Datei / Pfad | Rolle für X5 | Zeilen (ca.) |
|---|---|---|
| `runtime/src/sedra_runtime/uix/sprache.js` (neu) | Sprach-Laden, -Umschaltung, String-Abfrage (`t(schluessel)`) | Ziel: ≤ 400 |
| `runtime/src/sedra_runtime/uix/strings_de.json` (neu) | Deutsche UI-Strings | Ziel: beliebig (Daten) |
| `runtime/src/sedra_runtime/uix/strings_en.json` (neu) | Englische UI-Strings | Ziel: beliebig (Daten) |
| `runtime/src/sedra_runtime/uix/eingabe.js` | Fokus-Management, Tastatur-Events | ~350 (nur lesen, ggf. ergänzen) |
| `runtime/src/sedra_runtime/uix/core.js` | Registrierung von Sprache beim Start | ~450 (nur lesen) |
| `runtime/src/sedra_runtime/uix/einstellungen.js` | Sprach-Auswahl in Einstellungen | ~300 (nur lesen) |
| `runtime/src/sedra_runtime/uix/desktop.js` | Builder: Aria-Labels für Module | ~400 (nur lesen) |
| `runtime/src/sedra_runtime/uix/startmenue.js` | Aria-Labels, Fokusreihenfolge im Start-Menü | ~300 (nur lesen) |
| `runtime/src/sedra_runtime/uix/taskleiste.js` | Aria-Labels, Fokus in Taskleiste | ~350 (nur lesen) |
| `runtime/src/sedra_runtime/uix/tokens.css` | Farb-Token (Kontrast sicherstellen) | ~150 (nur lesen) |
| `runtime/src/sedra_runtime/uix/shell.css` | Shell-Styling (keine Hex-Farben) | ~550 (nur lesen, Ziel: Aufteilung ≤ 400) |

---

## 5. UI-Regeln im Detail

| Regel | Beschreibung | Wo geprüft |
|---|---|---|
| **Keine Hex-Farben in Shell-CSS** | Alle Farben über `tokens.css` Variablen. Keine `#rrggbb` in Shell-CSS-Dateien. | `UITest.test_keine_hex_farben` |
| **`textContent` statt `innerHTML`** | Kein `innerHTML` in Shell-JS. | `UITest.test_textcontent_statt_innerhtml` |
| **`setInterval` nur Taskleiste/Start-Menü** | Kein neues `setInterval` außerhalb `taskleiste.js`/`startmenue.js`. | `UITest.test_setinterval_nur_taskleiste_startmenue` |
| **Dateien ≤ 400 Zeilen** | Neue Dateien für X5 unter 400 Zeilen. | `UITest.test_dateien_max_400_zeilen` |

---

## 6. Tests (Namen und was sie prüfen)

| Testdatei | Testklasse / Funktion | Prüft |
|---|---|---|
| `test_uix_sprache.py` (neu) | `SpracheTest` | Keine hardcodierten Strings, Sprache umschalten, Standard DE, alle Strings beide Sprachen, Sprache in Einstellungen |
| `test_uix_tastatur_bedienung.py` (neu) | `TastaturTest` | Alle interaktiven per Tab, Fokus sichtbar, Fokusreihenfolge logisch, Kürzel unabhängig von Sprache, Eingabefelder tastaturbedienbar |
| `test_uix_barrierefreiheit.py` (neu) | `BarrierefreiheitTest` | Aria-Labels, Aria-Rolle/Zustand, Fehlermeldungen Screenreader, Bilder Alternativtext, Kontrast WCAG AA |
| `test_uix_ui_regeln.py` (neu) | `UITest` | Keine Hex-Farben, `textContent` statt `innerHTML`, `setInterval` nur erlaubtorte, Dateien ≤ 400 Zeilen |

**Testprinzip:** Keine Browser-Tests (Playwright) für MVP, nur Unit-/Integrationstests mit gemocktem Shell-Umfeld. `SEDRA_WISSEN_STANDARD=aus`.

---

## 7. Freigabegrenzen & Gegenproben (harte Anforderungen)

| Grenze | Beschreibung | Gegenprobe (muss fehlschlagen) |
|---|---|---|
| **Sprache aus Textdatei** | UI-Strings nie hardcodiert in Shell-JS. | Hardcodierter String → Test `test_keine_hardcodierten_strings` fehlschlägt |
| **Vollständige Tastaturbedienung** | Jede Maus-Aktion hat Tastatur-Äquivalent. | Element nur per Maus bedienbar → Test `test_alle_interaktiven_per_tab` fehlschlägt |
| **Screenreader-Beschriftung** | Jedes interaktive Element hat Aria-Label oder vergleichbar. | Element ohne Label → Test `test_aria_labels_vorhanden` fehlschlägt |
| **Kontrast WCAG AA** | Text-Kontrast erfüllt Mindestanforderung. | Kontrast zu niedrig → Test `test_kontrast_wcag_aa` fehlschlägt |
| **Keine Hex-Farben** | Shell-CSS enthält keine `#rrggbb`-Werte. | CSS mit Hex-Farbe → Lint/Test fehlschlägt |
| **`innerHTML` verboten** | Shell-JS nutzt kein `innerHTML`. | JS mit `innerHTML` → Test fehlschlägt |
| **Dateien ≤ 400 Zeilen** | Neue Dateien für X5 unter 400 Zeilen. | Datei > 400 Zeilen → Test fehlschlägt |

---

## 8. Reihenfolge der Schritte (Implementierungsfolge, für späteren Auftrag)

1. **Sprach-Dateien anlegen** (`strings_de.json`, `strings_en.json`) mit allen UI-Strings.
2. **`sprache.js` erstellen** (Laden, Umschaltung, `t(schluessel)`-Funktion, Fallback DE).
3. **Shell-JS auf `t(schluessel)` umstellen** (keine hardcodierten Strings mehr).
4. **Fokus-Management in `eingabe.js`** ergänzen (Tab-Reihenfolge, Fokus sichtbar).
5. **Aria-Labels in allen Shell-Dateien** ergänzen (Schaltflächen, Eingaben, Menüs).
6. **Kontrast in `tokens.css` prüfen** (WCAG AA).
7. **UI-Regeln prüfen:** Keine Hex-Farben, `textContent`, `setInterval`-Ort, Dateien ≤ 400 Zeilen.
8. **Tests schreiben** (siehe §6).
9. **Abnahme:** Sprache umschaltbar, Tastaturbedienung vollständig, Screenreader-Beschriftung, Kontrast OK, UI-Regeln eingehalten.

---

## 9. Offene Fragen (mit Vorschlag)

| Frage | Vorschlag | Begründung |
|---|---|---|
| X5-Q1: Wo liegen die Sprach-Dateien? | Unter `runtime/src/sedra_runtime/uix/sprachen/` (oder direkt unter `uix/`). | Zusammen mit dem Shell-Code, leicht auffindbar. |
| X5-Q2: Welche UI-Strings gehören in die Textdatei? | Alle sichtbarer Text in der Shell (Schaltflächen, Menüeinträge, Labels, Fehlermeldungen, Platzhalter). Nicht: Chat-Inhalte, Dokument-Inhalte. | Trennung UI vs. Inhalt. |
| X5-Q3: Wird die Sprachwahl im Profil gespeichert? | Ja, als Teil des Profils (X3), standardmäßig DE. | Konsistent mit Profil-Konzept. |
| X5-Q4: Gibt es eine Drittsprache später? | Nein, vorerst nur DE/EN. Architektur erlaubt späteres Hinzufügen (Schlüssel-basiert). | Einfachheit für MVP. |
| X5-Q5: Werden Fehlermeldungen aus dem Backend übersetzt? | Ja, über dieselbe Textdatei, falls sie feste Schlüssel haben. Dynamische Fehlermeldungen bleiben in Originalsprache. | Einheitliche UI-Sprache. |

---

## 10. Anforderungs-IDs (Zusammenfassung)

X5-01 bis X5-19 (19 Anforderungen).  
Offene Fragen: X5-Q1 bis X5-Q5 (5 Fragen).

---

## 11. Referenzen (nur Lesen)

- `docs/ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05.md`: Stufe X5 (Barrierefreiheit und Sprache), UI-Regeln (Abschnitt 2).
- `runtime/src/sedra_runtime/uix/sprache.js` (geplant): Sprach-Laden, -Umschaltung.
- `runtime/src/sedra_runtime/uix/strings_de.json` (geplant): Deutsche UI-Strings.
- `runtime/src/sedra_runtime/uix/strings_en.json` (geplant): Englische UI-Strings.
- `runtime/src/sedra_runtime/uix/eingabe.js`: Fokus-Management, Tastatur-Events.
- `runtime/src/sedra_runtime/uix/core.js`: Registrierung beim Start.
- `runtime/src/sedra_runtime/uix/einstellungen.js`: Sprach-Auswahl.
- `runtime/src/sedra_runtime/uix/desktop.js`: Builder Aria-Labels.
- `runtime/src/sedra_runtime/uix/startmenue.js`, `taskleiste.js`: Aria-Labels, Fokus.
- `runtime/src/sedra_runtime/uix/tokens.css`: Farb-Token (Kontrast).
- `runtime/src/sedra_runtime/uix/shell.css`: Shell-Styling (keine Hex-Farben).

---

**Ende der Spec X5.**  
Kein Code geschrieben. Dokument liegt im Worktree `pi-a011` unter `docs/SPEC_X5_SPRACHE_DE_EN_2026-11-14.md`.
