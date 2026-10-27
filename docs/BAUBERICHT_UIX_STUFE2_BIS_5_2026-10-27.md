# Baubericht UIX Stufe 2 bis 5 – 27.10.2026

Stand: Zweig `uix-stufe1-vertrag`, Basis `main` = `0179960`. Fortsetzung von `BAUBERICHT_UIX_STUFE1_2026-10-26.md`.
Specs: `SPEC_DOCK_OHNE_NEUAUFBAU_v1`, `SPEC_WERKZEUG_WISSEN_v2`, `SPEC_COCKPIT_BAUM_v1`, `SPEC_SHELL_WISSEN_v1` (alle Entscheidungen des Captains vom 26.10.2026 wie vorgeschlagen).
**Nicht abgenommen** – die Abnahme auf dem PC (Browser, lokales Modell) steht aus.

## 1. Was gebaut ist

| Stufe | Commit | Inhalt |
|---|---|---|
| 1 | `34ed735` | Vertrag 1.1: Gedächtnis (Memo, Sitzung, Ablage), Arbeitsstand am Server, Gesprächsverlauf, Knöpfe senden kein Formular ab, Ortskunde Wissen |
| 2 | `6d42cfd` | Cockpit-Dock ohne Neuaufbau: nur die geänderte Gruppe, je Reiter eine Fläche, Einzelstücke nie doppelt, Layout geprüft |
| 3 | `492f1f1` | alle Shells melden und übernehmen den Arbeitsstand (gateway-kmu, paperclip, minimal, Rahmen, fisch, start, Vorlage) |
| 4 | `dab26e9` | Werkzeug Wissen v2 (Suche als Start, Karten, Quellen-Liste, geführter Antrag, Messung, Werkbank-Zeile), Gespräch mit Verlauf, Ereignis `object.actions` |
| 5 | (dieser) | Cockpit-Baum und Rahmen, Palette, neue Shell „Wissensbasis“, Fundstelle, Wissen-Instrument, Notizen, Filter, „Frag das Wissen“ |

### Stufe 5 im Einzelnen
- **Cockpit** (`shells/cockpit/`): Wissen unter Bibliothek mit Zustand und „Wissens-Shell öffnen“; Gruppen klappen und merken sich (`sedra.cockpit.baum`, nur Namen); „⚠ n wartet“ an zugeklappten Gruppen; „… n weitere“; „Aufgabe ohne Titel“; Tastatur als Baum; Palette mit Baumzeilen, „Zuletzt“ und „Im Wissen suchen“; Gespräch aufziehbar, Baum mit Strg+B, „?“ für die Kürzel; „＋ Neu“ mit Tastatur und „Quelle für Wissen“. Logbucheintrag zu COCKPIT_MODUL_v1 §1.
- **Shell „Wissensbasis“** (`shells/wissensbasis/`): Vorgabe ohne Code; Orte Suche, Quellen, Vorschläge, Eigenes, Bibliothek, Logbuch, Messung, Entscheidungen; Start Wissen › Suche; Fundstelle als Nachweis; `gespraech.wissen: true`.
- **Vertrag/Rahmen:** Orte der Vorgabe aus `ui/places.js` (ein Ort, eine Wahrheit), `start.view`, `start.type: wissen`, `gespraech.wissen`; Objekt `shell` wechselt die Oberfläche (`sedraWechsel.zurShell`), Arbeitsstand geht mit; die Leiste der Rahmen-Shells hat jetzt feste Höhe (vorher wuchs sie auf 177 px).
- **Werkzeuge:** `fundstelle` (Abschnitt mit davor/danach, Stand, Stufe, Personenbezug, markierte Suchwörter), `gauge-wissen` (Modus, Abdeckung, Vorschläge); Wissen mit Filter (Art, Quelle, Projekt, Zeitraum – vor dem Ranking) und Ansicht „Eigenes“.
- **Server:** Objekttyp `wissen_abschnitt`; Verben `notizen`, `notiz_anlegen|aendern|loeschen` (Notizen in `local_config/wissen/notizen/{mit-personenbezug,allgemein}`, einmal freigegeben – ein Antrag, zwei Gates –, danach ohne Gate, Audit `WIS_NOTIZ` nur mit Aktion, Datei-Kennung, Zeichenzahl); `suche` mit `filter`; `/api/strip` → `wissen`; `chat_reply {wissen: true}` mit Zitatprüfung (D7.6), ohne Modell die Fundstellen.

## 2. Schutz, wie verabredet
- Inhalte (Frage, Treffer, Notiz-Entwurf, Projekt im Filter) nie in `sessionStorage`/`localStorage` – nur in der Ablage des Servers (RAM). Geprüft im Browser (`test_uix_wissen_v2`) und im Schein-DOM (Spec Wissen).
- Personenbezug nie in einen Cloud-Weg: eine Antwort aus dem Wissen mit Personenbezug wird in der History `nurLokal`, im Verlauf `nur_lokal`; Cloud und Lokal + KI bekommen sie nicht (`fuerCloud`). Die Suche fürs Gespräch läuft immer mit Route `local`.
- Die Frage aus der Palette geht nur ins Memo des Werkzeugs, nicht ins Objekt (das Objekt steht im Layout und im Arbeitsstand).
- Audit ohne Inhalt: `WIS_NOTIZ` (geprüft: kein Name, kein Kunde im Audit).

## 3. Prüfungen
- Python/Node gesamt: siehe Abschnitt 5 (gleiche Altfunde wie auf `main`, keine neuen).
- Neu: `test_wissen_basis` (8), `test_uix_cockpit_baum` (8, davon 3 im Browser), `test_uix_wissen_v2` (3 im Browser: Cockpit und Wissensbasis), Specs `wissen` (20), `fundstelle` (6), `gauge-wissen` (2).
- `uix_check`: cockpit 40/41, wissensbasis 40/42. Offen sind nur Altfunde, die schon auf `main` rot sind (`tool:meter` „Container leer“, `breite` der Rahmen-Shells).

## 4. Bewusst offen
- „Datei öffnen“ in der Fundstelle: die Quelle liegt relativ zum Projektordner, das Werkzeug `files` zeigt den Arbeitsordner – braucht eine Abbildung, eigener Punkt.
- Projekt je Notiz: heute gelten Notizen für alle Projekte (Stufe 3, Personenbezug je Ordner).
- „Aus dem GateWay“ als zweite Liste unter „Eigenes“: heute ein Hinweis; die Einträge sind als Quelle „GateWay“ beantragbar.
- Bibliothek und Lektionen als Quelle (W-E5): später, eigener Punkt.
- Maschinenraum „Gedächtnis der Oberfläche“ (Zahlen aus `/api/arbeitsstand`): nicht gebaut; „Gedächtnis leeren“ steht im Umschalter.
- Bildschirmfotos `docs/shots/cockpit/shell.png`, `docs/shots/wissensbasis/shell.png` und `preview.png` stammen aus dem Prüfprojekt (Chromium) – auf dem PC mit echten Daten erneuern.
- Endabnahme „Frag das Wissen“ mit geladenem Modell (W7) nur auf dem PC möglich.

## 5. Gesamtlauf
Siehe `INTEGRATION.md` im Download-Paket: Ergebnis des letzten Laufs und die vier Altfunde (`test_night_chain` Umgebung, `test_uix_browser` Vertragstest, `test_uix_flows` paperclip „Routinen“, `test_uix_shell_start` `tool:meter`), die auf `main` genauso rot sind.
