# SPEC Profile v1 – G1 Anforderungen (05.11.2026)

Stand: `main` `d51083a`. Gate **G1**; G2/G3 erst nach Freigabe. Unterchat **U4** (Phase R2, UIX X3, Werkzeug W3).
Grundlage: Beschlüsse des Captains vom 05.11.2026 – Zuschnitt für Auftraggeber über **Profile**, nicht über neue Shells; **`shells:` bleibt** im Manifest, **`profile:` kommt daneben**; Minimal wird ein Profil; Wissen ist Grundfunktion (nie ausblendbar, neben Posteingang und Aufgaben). Entwurf: `docs/ENTWURF_AUFTRAGGEBER_PROFILE_2026-11-05.md`. Grenze: `docs/SPEC_APPS_v1_AM7_UNTERNEHMEN.md`.
Pfade relativ zu `runtime/src/guppi_runtime/`, sonst ab Repo-Wurzel.

**Ergebnis in einem Satz:** Speichern, Anwenden, Exportieren und Importieren eines Profils mit Prüfung **sind schon gebaut** (Server und Desktop Builder, 24 + 6 Tests) – es fehlen ein Dateiformat mit Kennung und Version, Export/Import als Datei, Schutz vor stillem Überschreiben, die Bindung an Apps (`profile:` im Manifest), vier Profilvorlagen und ein vollständiger Roundtrip-Test.

## 1. Befund

### 1.1 Was schon da ist

| Nr | Befund | Beleg |
|---|---|---|
| B1 | **Zwei Ebenen:** die gültige **Wahl** (`runtime_data/harness/desktop.json`) und benannte **Profile** (`runtime_data/harness/profile/<id>.json`), „speicher-, anwend-, export- und importierbar“; ausdrücklich **keine Erlaubnis** und kein Schutz. | `harness/desktop.py:1–10, 51–56` |
| B2 | Ein Profil hat fünf Teile: `start` (ausblenden, Gruppe), `zellen` (ausblenden, Reihenfolge), `marke` (Name ≤ 40, Akzent `#rrggbb`, Logo als Daten-Adresse ≤ 200 000 Zeichen, Schrift aus 4), `startseite` (Ort, Titel ≤ 60, Text ≤ 300), `layout` (Raster 12×40, vier Leisten, Zonen). Dazu `name`, `auftraggeber`, `beschreibung`. | `harness/desktop.py:26, 41–48, 138–177, 237–238` |
| B3 | **Prüfung beim Laden und Importieren:** `pruefen()` weist unbekannte Schlüssel, falsche Werte und jedes Ausblenden einer Grundfunktion ab (`desktop_grundfunktion`); eine kaputte `desktop.json` gilt als Vorgabe, nie als Startfehler. | `harness/desktop.py:138–158, 184–192`; Test `test_kaputte_datei_ist_kein_fehler_beim_start` (`runtime/tests/test_harness_desktop.py:42`) |
| B4 | **Export** = `GET /api/harness/desktop?profil=<id>` → JSON; **Import** = `POST … {aktion: profil_importieren, profil}`; dazu `profil_speichern`, `profil_anwenden`, `profil_loeschen`. | `harness/api.py:313–321`; `harness/desktop.py:230–292` |
| B5 | **Desktop Builder**, Reiter „Profile und Marke“: Export schreibt das JSON in ein **Textfeld** („Text kopieren und weitergeben“), Import liest aus dem Textfeld. **Keine Datei** zum Herunterladen oder Hochladen (FileReader nur für das Logo). | `uix/shells/harness/builder.js:112–116, 133–139, 165, 171, 175–178` |
| B6 | Tests: 24 im Server (u. a. Export/Import in ein anderes Projekt, Layout reist mit, Grundfunktion beim Import abgewiesen, Obergrenze 40 Profile, Beispiel im Skill `desktop-designer` importierbar), 6 im Client (Grundfunktionen gleich in Client und Server, Schriften ohne Netz). | `runtime/tests/test_harness_desktop.py:28–278`; `runtime/tests/test_uix_harness_desktop.py:15–72` |
| B7 | Chat: Werkzeug `desktop_lesen` liest Wahl oder Profil samt Grundfunktionen und erlaubten Werten (nur lesen); Vorlage `desktop-designer`. | `harness/api.py:1074–1081` |

### 1.2 Was fehlt oder wackelt

| Nr | Befund | Beleg |
|---|---|---|
| L1 | **Kein Dateiformat:** Das Export-JSON hat keine Kennung (`format`), keine Version, keinen Stand von Sedra. Ein späterer Feldwechsel ist beim Import nicht erkennbar. | `harness/desktop.py:237–238` (Rückgabe ohne `format`/`version`) |
| L2 | **Import überschreibt still:** Ein Profil mit vorhandener ID wird ersetzt, ohne Rückfrage. | `harness/desktop.py:242` („ein vorhandenes Profil gleicher ID wird ersetzt“), `:290` |
| L3 | **Roundtrip nur teilweise geprüft:** Der Test vergleicht nach dem Import nur `start` (und in einem zweiten Test `layout`), nicht das ganze Profil, und nicht Export → Import → Export gleich. | `runtime/tests/test_harness_desktop.py:78–87, 195` |
| L4 | **Grundfunktionen uneinheitlich:** Server und Client kennen nur `decisions`, `tasks` (Start) und `decisions` (Zelle); **Wissen fehlt**, obwohl seit 05.11. Grundfunktion. Drei Listen im Bestand: AM2-12 (sieben), Roadmap Kern §1 (neun), `desktop.py` (zwei Orte). | `harness/desktop.py:19–20`; `uix/shells/harness/desktop.js:14–15`; `docs/SPEC_APPS_v1_AM2_ORTE_UND_GRUNDFUNKTIONEN.md:58`; `docs/ROADMAP_ONE_SEDRA_APPS_KERN_SHELL_2026-11-05.md` §1 |
| L5 | **Keine Bindung an Apps:** Ein Profil blendet Orte nur aus (Negativliste). Welche Apps zu einem Profil gehören, steht nirgends; der Manifest-Prüfer kennt weder `shells` noch `profile` (unbekannter Schlüssel wird abgewiesen). | `desk/gateway.py:63, 98`; `docs/SPEC_APPS_v1_AM1_ZELLEN_UND_SHELLS.md` AM1-01 (`shells`, nicht gebaut) |
| L6 | **Keine Vorlagen:** Es gibt keine mitgelieferten Profile (KMU, Privat, Stick, Minimal); jedes Profil entsteht aus der aktuellen Wahl. | `harness/desktop.py:249–251`; Verzeichnis `profile/` nur unter `runtime_data/` |
| L7 | **Profil beim Start wählen / an Projekt binden:** nicht gebaut (Entwurf §5). | `docs/ENTWURF_AUFTRAGGEBER_PROFILE_2026-11-05.md:46–51` |
| L8 | Ausgeblendete IDs werden nur auf das Muster geprüft, nicht gegen vorhandene Orte/Apps; ein Tippfehler bleibt still wirkungslos. | `harness/desktop.py:21, 66–77, 156` |
| L9 | **Minimal-Shell** (freie Fenster, Menüleiste, Ablage mit 8 Feldern, Entscheidungskarte oben rechts) – als Profil abbildbar sind nur Auswahl und Reihenfolge (Ablage ≈ Start-Menü „zuletzt“/Startseite), nicht freie Fenster. | `uix/shells/minimal/README.md:3–6, 41–47`; `uix/shells/minimal/shelf.js:16–25` |

### 1.3 Grenze zu Richtlinie und Rollen (AM7)

Das Profil **wählt** (was sichtbar ist), die Richtlinie **erlaubt** (Positivliste der Apps, Obergrenzen, Rolle, Person; `local_config/richtlinie.yaml`, nur vom Betreiber, AM7-04 bis -06). „Ein Profil schützt nichts“ (`ENTWURF_AUFTRAGGEBER_PROFILE_2026-11-05.md:13`). AM7 ist G1 mit Betriebsart A entschieden, nichts gebaut (`SPEC_APPS_v1_AM7_UNTERNEHMEN.md:3–5`).

## 2. Ziel und Nicht-Ziel

**Ziel:** Ein Profil ist eine **Datei mit Format und Version**, die man exportiert, auf einem anderen Rechner prüft, ohne stilles Überschreiben importiert und anwendet; der Roundtrip ist verlustfrei bewiesen. Apps tragen im Manifest `profile:` (zu welchen Profilen sie gehören); ein Profil kann darauf aufbauen. Vier **Vorlagen** liegen im Paket: KMU, Privat, Stick, Minimal.

**Nicht-Ziel:**
- Rechte, Positivliste, Rollen, Person, Signatur (AM7/U6). Ein Profil vergibt nie ein Recht und blendet nie eine Grundfunktion aus.
- `shells:` ersetzen (Beschluss: bleibt).
- Freie Fenster der Minimal-Shell nachbauen; Minimal-Shell löschen.
- Profile aus dem Netz laden, Logo als eigene Datei, Profilwechsel durch den Chat ohne Freigabe (W3 `profil_wechseln` nur als Vorschlag mit Ja).

## 3. Anforderungen

### 3.1 Dateiformat, Export, Import

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| PR-01 | Export liefert eine Hülle: `{"format": "sedra-profil", "version": 1, "sedra": "<Version des Pakets>", "erstellt": "<ISO-Zeit>", "profil": {id, name, auftraggeber, beschreibung, vorlage?, start, zellen, marke, startseite, layout}}`. Ohne Hülle (heutiges Format, B4) wird beim Import weiter angenommen und als `version 0` gelesen. | Test: Export hat Hülle; Import einer alten Fassung gelingt |
| PR-02 | **Export als Datei** im Desktop Builder: Knopf „Als Datei speichern“ (`<id>.sedra-profil.json`, Download über `Blob`, keine Route nötig); das Textfeld bleibt. | Browser-Test an Testinstanz |
| PR-03 | **Import aus Datei:** Dateiwahl (nur `.json`, ≤ 300 KB wegen Logo), danach dieselbe Prüfung wie heute (`pruefen`). | Browser-Test, Test: zu große Datei abgewiesen |
| PR-04 | **Kein stilles Überschreiben:** Gibt es die ID schon, meldet der Server `profil_vorhanden` mit Name des vorhandenen; der Import geht nur mit `ersetzen: true` (Rückfrage im Feld) oder mit neuer ID. | Test |
| PR-05 | **Vorschau vor dem Import:** Der Builder zeigt, was das Profil ändert (ausgeblendete Apps/Zellen, Marke, Startseite, Layout geändert ja/nein) und welche IDs es nicht gibt (L8: Warnung `unbekannt: …`, kein Fehler). | Test (Server liefert `warnungen`), Browser-Test |
| PR-06 | Format oder Version unbekannt (`format` ≠ `sedra-profil` oder `version` > bekannt) → `profil_format_unbekannt`, nichts wird geschrieben. | Test |

### 3.2 Prüfung beim Laden

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| PR-10 | Jedes Laden (Start, Anwenden, Import, Vorlage) geht durch **eine** Prüfung (`pruefen`); kein zweiter Prüfweg im Client. Client-Konstanten der Grundfunktionen kommen aus der Antwort des Servers oder werden per Test gleich gehalten. | Test `test_grundfunktionen_stehen_im_client_wie_im_server` erweitert |
| PR-11 | **Grundfunktionen nie ausblendbar**, eine Liste an einer Stelle (Vorschlag PR-E1): Posteingang (`decisions`), Aufgaben (`tasks`), **Wissen** (`wissen`), Zelle Freigaben, Schild, Senden, App-Gruppen, Einstellungen, Desktop Builder. Ein Profil, das eine davon ausblendet, wird abgewiesen – auch als Vorlage, auch beim Import. | Test je Grundfunktion |
| PR-12 | Eine kaputte oder unbekannte Profildatei verhindert nie den Start: Wahl fällt auf die Vorgabe der Shell, ein Hinweis im Posteingang/Info nennt Datei und Grund. | Test (wie B3, plus Hinweis) |
| PR-13 | Logo: nur PNG/JPEG/WebP/SVG als Daten-Adresse (wie heute), Anzeige nur als `<img src>` (SVG ohne Skriptausführung); kein `innerHTML`. | Code-Prüfung, Test |

### 3.3 Apps im Profil: Feld `profile:` im Manifest

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| PR-20 | `tool.yaml` darf `profile: [<profil-art>, …]` tragen (Muster `^[a-z0-9-]{2,40}$`, 1–20, keine Dopplung). **`shells:` bleibt daneben** (AM1-01, unverändert). Der Manifest-Prüfer kennt beide Felder (`desk/gateway.py` `TOOL_KEYS`). | Schema-Test |
| PR-21 | Bedeutung: `profile:` sagt, in welchen **Profil-Arten** eine App zum Lieferumfang gehört (Sichtbarkeit), `shells:` sagt, in welcher Oberfläche sie überhaupt läuft. Fehlt `profile:`, gehört die App zu allen Profil-Arten (heutiges Verhalten). Grundfunktionen (`grundfunktion:` nach AM2-13) ignorieren `profile:` – immer da. | Test |
| PR-22 | Ein Profil kann eine **Vorlage** (`vorlage: kmu|privat|stick|minimal`) nennen. Dann gilt: sichtbar sind die Apps, deren `profile:` die Vorlage enthält (oder kein `profile:` haben), **minus** `start.ausblenden` des Profils. Ohne `vorlage` wie heute (alle Apps minus ausblenden). | Test der Startliste (`startliste.js`) mit Manifesten |
| PR-23 | Der Stick-Bau liest `profile:` (U8, `SPEC_STICK_AUS_PROFIL_v1.md`): was zur Art `stick` gehört, kommt ins Paket. | Test in U8 |
| PR-24 | `profile:` ist **Wahl, nicht Schutz**: eine App ohne passende Art bleibt per Suche oder Chat-Ort erreichbar, solange keine Richtlinie sie sperrt (§3.5). | Test, Hinweistext im Builder |

### 3.4 Profilvorlagen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| PR-30 | Vier Vorlagen im Paket unter `uix/shells/harness/profile/` (Dateien im Format PR-01, nur lesen; Kopie nach `runtime_data/…/profile/` beim ersten „Übernehmen“). Der Builder zeigt sie als „Vorlagen“ getrennt von eigenen Profilen. | Test: jede Vorlage besteht `pruefen`; Builder-Test |
| PR-31 | **KMU:** Gruppen Arbeit, Wissen, System; ohne Modell-Werkstatt und Prüfung im Menü; Startseite Posteingang; Marke leer (füllt der Betreiber). Hinweis im Profil: „Rechte und Positivliste über die Richtlinie (AM7)“. | Vorlagen-Test |
| PR-32 | **Privat:** alles sichtbar wie die Vorgabe der Shell; Startseite leere Sitzung. (Die Vorgabe als benanntes Profil, damit man zurückfindet.) | Vorlagen-Test |
| PR-33 | **Stick:** nur Apps mit `profile: [… stick …]` (Vorschlag: Gespräch, Translator, Wissen im Volltext, Posteingang, Aufgaben, Einstellungen, Modelle laden); Zellen ohne Werkzeug ausgeblendet (`PRUEFUNG_STICK_SHELLS_2026-11-02.md:16–17`); Startseite leere Sitzung. Abgleich mit U8. | Vorlagen-Test, U8 |
| PR-34 | **Minimal** (Ersatz der Minimal-Shell als Profil): Start-Menü auf die acht Felder der Minimal-Ablage reduziert (Aufgaben, Vorhaben, Projekt, Werkstatt, Besatzung, Bibliothek, Logbuch, Maschine; `shelf.js:16–25`) plus Grundfunktionen; Abschnitte „zuletzt“ und „Auf einen Blick“ ausgeblendet; Taskleiste nur Freigaben, Modell, Uhr; Seitenleiste zu. Freie Fenster: Nicht-Ziel. | Vorlagen-Test; Gleichstandsliste gegen `uix/shells/minimal/README.md` |
| PR-35 | Eine Vorlage nennt nur Orte/Apps, die es im Paket gibt (Test gegen `places.js` und Manifeste); fehlt eine, ist das ein Testfehler, kein stiller Ausfall. | Test |

### 3.5 Grenze zu Richtlinie und Rollen (AM7)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| PR-40 | Profil und Richtlinie bleiben getrennte Dateien und Wege: Profil in `runtime_data/harness/` (Captain/Nutzer, ohne Gate), Richtlinie in `local_config/richtlinie.yaml` (Betreiber, Gate). Kein Feld der Richtlinie im Profil und umgekehrt. | Schema-Test beider |
| PR-41 | Ist eine Richtlinie aktiv (ab U6/AM7), wird sie **über** das Profil gelegt: das Profil zeigt nur, was die Richtlinie erlaubt; ein Profil kann eine verbotene App nie sichtbar machen. Vorher (heute) gilt nur das Profil. | Test in U6 (hier nur Vertrag) |
| PR-42 | AM7 „Profile je Rolle“ wird auf dieses Format gebaut: die Richtlinie nennt je Rolle ein Profil (`profil: <id>`), nicht umgekehrt. | Doku, Abgleich in U6 |

### 3.6 Roundtrip-Test

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| PR-50 | **Roundtrip:** Profil mit allen fünf Teilen (inkl. Logo, Layout mit Raster und Zonen, Vorlage) in Projekt A speichern → exportieren (Hülle) → in Projekt B importieren → anwenden → exportieren: beide Exporte gleich bis auf `erstellt`. Zusätzlich jede Vorlage einmal durch den Roundtrip. | `test_harness_desktop` neu `test_roundtrip_verlustfrei` |
| PR-51 | Negativ-Roundtrip: dasselbe mit (a) Grundfunktion im Ausblenden, (b) fremdem Format, (c) vorhandener ID ohne `ersetzen` – nichts wird geschrieben, Zustand B unverändert. | Test |
| PR-52 | Client: Builder exportiert Datei, importiert sie wieder, Vorschau zeigt „keine Änderung“. | Browser-Test an Testinstanz |

## 4. Abnahme

1. Server-Tests PR-01, -04, -06, -10–12, -20–22, -30–35, -50–51 grün; die 30 bestehenden Tests (24 + 6) bleiben grün.
2. Browser-Test an eigener Testinstanz: Datei-Export/-Import, Vorschau, Rückfrage beim Überschreiben, Vorlagen übernehmen (PR-02, -03, -05, -30, -52).
3. Captain im echten Sedra (nach Neustart + Strg+F5): Vorlage „Minimal“ übernehmen und anwenden, Profil exportieren, in einer zweiten Instanz (Stick) importieren.

## 5. Reihenfolge (Vorschlag)

| Schritt | Inhalt | IDs | Berührt |
|---|---|---|---|
| 1 | Hülle, Version, `profil_vorhanden`, Roundtrip-Test | PR-01, -04, -06, -50, -51 | `harness/desktop.py`, Tests |
| 2 | Datei-Export/-Import, Vorschau im Builder | PR-02, -03, -05, -52 | `builder.js` |
| 3 | Grundfunktionen eine Liste (mit Wissen) | PR-10–12 | `desktop.py`, `desktop.js` |
| 4 | Vorlagen Privat, Minimal, KMU (ohne `profile:`, nur ausblenden) | PR-30–32, -34, -35 | neue Dateien `uix/shells/harness/profile/` |
| 5 | Feld `profile:` im Manifest und `vorlage` im Profil; Vorlage Stick | PR-20–24, -33 | `desk/gateway.py`, `startliste.js` – **gehört zu U12** (Manifest v1.1); U4 liefert nur die Anforderung und die Tests |

Schritte 1–4 sind gefahrlos parallel zu U2/U3 (andere Dateien). Schritt 5 erst mit U12, weil `TOOL_KEYS` und Startliste dort ohnehin angefasst werden.

## 6. Offene Entscheidungen (mit Vorschlag)

| Nr | Frage | Vorschlag |
|---|---|---|
| PR-E1 | Welche Liste der Grundfunktionen gilt (zwei in `desktop.py`, sieben in AM2-12, neun in der Roadmap, dazu Wissen)? | **Eine Liste im Kern** (`desktop.py` oder AM2-Modul): Posteingang, Aufgaben, Wissen, Gespräch, Logbuch, Modus und Grenzen, Module und Berechtigungen, Einstellungen, Freigaben; der Client liest sie vom Server. |
| PR-E2 | Wo liegen die Vorlagen: im Paket (nur lesen) oder als Beispiel-Profile in `runtime_data`? | **Im Paket**, Übernahme als Kopie; so ändert ein Update die Vorlage, nie das Profil des Nutzers. |
| PR-E3 | `profile:`-Werte: Profil-Arten (`kmu`, `privat`, `stick`, `minimal`, `standard`) oder einzelne Profil-IDs? | **Arten**, nicht IDs – IDs sind Sache des Auftraggebers und ändern sich; Vorlagen nennen ihre Art. |
| PR-E4 | Darf der Chat (W3) ein Profil anwenden? | Nur **als Vorschlag mit Vorschau und Ja** (wie W3 `desktop_aendern`); Lesen bleibt frei (`desktop_lesen`). |
| PR-E5 | Profil beim Start wählen / an Projekt binden (L7)? | **Nach v1**; zuerst Stick (U8) mit festem Profil „Stick“ in der Stick-Konfiguration. |
| PR-E6 | Wird die Minimal-Shell nach dem Profil „Minimal“ eingefroren? | Ja, nach Abnahme der Gleichstandsliste (PR-34), wie bei `fisch`; nicht löschen. |
