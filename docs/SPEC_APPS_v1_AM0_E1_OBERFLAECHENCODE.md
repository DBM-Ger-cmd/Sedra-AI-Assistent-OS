# Entscheidungsvorlage AM0-E1: Wie schützen wir den Code der Oberfläche vor Änderungen durch das Modell? (03.11.2026)

Status: **offen.** Der Captain hat AM0-E1 am 03.11.2026 zur Ausarbeitung zurückgegeben („Das müssen wir mehr ausarbeiten, was am besten und praktikabel ist“). Bis zur Entscheidung gilt Teil A von `SPEC_APPS_v1_AM0_G2.md` als **nicht freigegeben**; alle anderen Teile von AM0 sind davon unabhängig.
Pfade relativ zu `runtime/src/guppi_runtime/`, Zeilen für c364081.

## 1. Die Frage

Darf ein Modell (MasterChat, Bauagent) Dateien unter `uix/**` schreiben, und wenn ja, unter welchen Bedingungen? G1 schlug einen harten Vorbehalt für ganz `uix/**` vor. Diese Vorlage prüft, was ein Schreibzugriff dort tatsächlich öffnet, wer dort heute schreibt, welche Wege es gibt, und empfiehlt einen.

## 2. Was ein Schreibzugriff unter `uix/**` heute öffnet

| Nr | Befund | Beleg |
|---|---|---|
| W1 | Code von Paket-Werkzeugen (`trust: CORE`) und von Shells wird **in die Seite** geladen. | `ui/loader.js:164–174` |
| W2 | Code in der Seite kann den Token aus der Adresse lesen. Der Vertrag sagt das selbst: „Honest limit: code on the same page can still read the token from the address; the real boundary is isolation (Stufe C).“ | `ui/api.js:6, 9` |
| W3 | Eine Anfrage **ohne** Modulkopf (`X-SEDRA-Tool`/`X-SEDRA-Shell`) gilt als Anfrage der Shell-Seite und hat alle Rechte des Browser-Tokens – darunter das Beantworten von Entscheidungen (`POST /api/decisions/answer`). | `uix_server.py:3562–3563`; Route in der Harness-Allowlist `shells/harness/shell.yaml` (`api`) |
| W4 | Dateien werden ohne Zwischenspeicher ausgeliefert; eine Änderung wirkt beim **nächsten Neuladen** der Seite. | `uix_server.py:3682` (`Cache-Control: no-store`) |
| W5 | **Folge:** Wer eine einzige JS-Datei eines Paket-Werkzeugs oder einer Shell ändern kann, kann nach dem nächsten Neuladen jede wartende Freigabe selbst erteilen. Das gilt für jeden der 42 CORE-Werkzeugordner und jede Shell mit Code – nicht nur für den Vertragscode in `uix/ui/`. | W1–W4 |
| W6 | Auch Dateien ohne Programmcode wirken: `tool.yaml`/`shell.yaml` (Vertrauen, Routen; ein neuer Ordner mit `trust: CORE` ist ein neues Werkzeug mit Seitenzugriff), CSS (kann Knöpfe umgestalten), Daten der Shells (`start_gruppen.json`), `arbeitsplatz.yaml` (wird als Arbeitsplatz-Wissen erfasst und dem Modell über das Werkzeug `arbeitsplatz_wissen` gegeben – eine Änderung dort ist eine dauerhafte Anweisung an das Modell). | `desk/arbeitsplatz.py:1–9`; `chat_tools.py:88–91` |
| W7 | Nur `README.md` hat keine Wirkung auf Laufzeit oder Modell (nicht gefunden, dass sie gelesen werden). | Suche nach Lesern nicht vollständig; G3 bestätigt |

**Das Gleiche gilt für Python.** Jede Datei unter `runtime/src/**`, die kein harter Vorbehalt ist (z. B. `desk/actions.py`, `harness/api.py`), wirkt nach dem nächsten Start von SEDRA mit allen Rechten. Die Oberfläche ist nur der Teil, der schon beim **Neuladen der Seite** wirkt statt beim **Neustart**.

## 3. Wer heute dort schreibt

| Wer | Wie | Beleg |
|---|---|---|
| **MasterChat** | Die Vorlage gibt nach einem Ja des Captains für die ganze Sitzung `datei_schreiben`/`datei_aendern` in `runtime/src/**`, `runtime/tests/**`, `docs/**`, `redesign/**` frei; der Systemprompt nennt `uix/shells/harness/` als Ort der Einstellungen. Modell: lokal (`verifier.llama_gemma`). | `runtime/config/harness_vorlagen/masterchat.yaml:5–9, 14–26, 28`; `masterchat.md:35`; `harness/api.py:336–351` (Vorlagen-Erlaubnisse werden Sitzungs-Erlaubnisse) |
| **Bauagent** | Schreiben im Schreibbereich des Projekts, Karten der Stufe `vorarbeiter` an den Vorarbeiter | `runtime/config/harness_vorlagen/bauagent.yaml:4–7` |
| **Claude** | direkt im Repo, nicht über die Harness | – (von Vorbehalten der Harness nicht betroffen) |
| **Captain** | von Hand | – |
| **GUPPI in der DevVM** | baut in einer Kopie, Übernahme per `adopt_plan` oder Handkopie | `docs/ARCHITEKTUR.md` §4, §6a (Linie L5) |

Wichtig für die Einordnung: Im beschriebenen Aufbau sind **das laufende SEDRA und das Projekt, das das Modell bearbeitet, derselbe Ordner** („der Ordner, in dem runtime/ und docs/ liegen“). SEDRA ändert sich selbst, während es läuft.
Beleg: `runtime/config/harness_projekte.beispiel.yaml:10`.

## 4. Die Wege

| Weg | Beschreibung | Schließt W5? | MasterChat kann Oberfläche anpassen? | Aufwand | Bewertung |
|---|---|---|---|---|---|
| **O1** ganz `uix/**` hart | jede Datei eine Karte an den Captain; keine Aufgabe, keine Sitzungs-Erlaubnis, kein Vorarbeiter | ja | nur mit einer Karte **je Schreibvorgang** (Stufe 6 der Harness berührte 7 Dateien, `SPEC_HARNESS_SHELL_v1_STUFE6_G1.md` §5 P6-2; mit Nacharbeit leicht 20–40 Karten) | sehr gering (Liste) | sicher, aber Freigabe-Müdigkeit: viele Karten werden ungelesen bestätigt; dann schützt die Karte nicht mehr |
| **O2** nur Vertragscode `uix/ui/**` hart | Rest wie heute | **nein** – jede Paket-JS-Datei reicht (W5) | ja, frei | sehr gering | sieht praktisch aus, schließt die Lücke aber nicht |
| **O3** gestuft | hart: Vertragscode, Manifeste, Arbeitsplatz-Wissen, Prüfstellen; **weich**: übriger Code von Shells und Werkzeugen – nur eine **Aufgabe**, die die Oberflächen-Pfade ausdrücklich nennt, deckt; frei: `README.md` | ja, solange keine Aufgabe dafür freigegeben ist; innerhalb einer Aufgabe bewusst nicht | ja, nach **einer** Aufgaben-Freigabe mit Zweck und Pfaden | gering (bestehendes Muster „weicher Vorbehalt“) | guter Kompromiss für jetzt; ehrliches Restrisiko innerhalb der Aufgabe |
| **O4** Siegel der Oberfläche | das Modell darf schreiben; der Server liefert aber nur einen **versiegelten** Stand aus; Änderungen werden erst nach einer Übernahme-Karte mit Gesamt-Diff wirksam | ja | ja, frei; Wirkung erst nach Übernahme | mittel bis hoch (Server muss alten Stand vorhalten, Manifeste und Arbeitsplatz-Wissen ebenfalls aus dem Siegel lesen) | wirksam, aber deckt Python nicht ab; doppelt sich mit O5 |
| **O5** Werkstatt und Betrieb trennen | SEDRA läuft aus einem **freigegebenen Stand**; das Modell arbeitet in einem **getrennten Arbeitsordner**; in den Betrieb kommt eine Änderung nur über die Übernahme mit Prüfsummen, Rechte-Diff, Sicherung und Rückweg | ja – für Oberfläche **und** Python | ja, frei in der Werkstatt; Wirkung erst nach Übernahme | hoch, aber vieles gibt es schon (Release-Updater, DevVM, Stick) | die grundsätzliche Lösung; Baustein AM9 |

Was es dafür schon gibt (O5): Der Release-Updater übernimmt nur einen vollständig geprüften Stand (`release/MANIFEST.sha256`, Prüfbereiche `runtime/src/guppi_runtime/` und `runtime/config/`), nennt jede Rechteänderung eines Moduls einzeln, braucht die Bestätigung genau dieser Liste, sichert vorher und kann zurück (`update_anwenden.py:3–11, 23–24, 89–115, 151–171`). Er holt heute aber nur Release-Tags von GitHub (`update_holen.py:1–4, 22–23`), keine lokale Werkstatt.

## 5. Empfehlung

**Jetzt (AM0): O3.** Später (eigener Baustein **AM9**): **O5**. O1, O2 und O4 nicht.

Begründung:
- O2 schließt die Lücke nicht (W5).
- O1 ist sicher, aber im Alltag des MasterChat nicht praktikabel; viele Einzelkarten führen zu Bestätigen ohne Lesen. Eine einzige, bewusste Entscheidung über Zweck und Pfade (O3) ist wirksamer als dreißig Karten.
- O4 löst nur die Hälfte (Python nicht) und baut einen zweiten Mechanismus neben dem Updater.
- O5 ist die eigentliche Antwort: Solange Werkstatt und Betrieb derselbe Ordner sind, ist jeder Schutz in der Harness ein Schutz an der Tür eines Hauses, an dessen Wänden das Modell baut. O5 ist aber ein großer Schritt und braucht eigene Entscheidungen (§7).

**Restrisiko von O3 – ehrlich:** Innerhalb einer freigegebenen Aufgabe kann das Modell Code schreiben, der nach dem Neuladen mit allen Rechten der Seite läuft – auch fehlerhaft oder durch eingeschleuste Anweisungen in gelesenen Dateien. Die Aufgabe begrenzt das auf genannte Pfade, eine Zahl von Aufrufen und eine Frist; sie verhindert es nicht. Deshalb sagt die Freigabe-Karte der Aufgabe das ausdrücklich (§6).

## 6. O3 im Detail (ersetzt Teil A von `SPEC_APPS_v1_AM0_G2.md`, wenn freigegeben)

**Hart** (`harness/vorbehalte.py` `PFADE`; nur Karte an den Captain):

| Muster | Grund |
|---|---|
| `runtime/src/guppi_runtime/uix/ui/**` | Vertragscode: Lader, Brücke, Rahmen, Bus, Token-Zugang |
| `runtime/src/guppi_runtime/uix/**/tool.yaml`, `…/uix/**/shell.yaml`, `…/uix/**/shell.vorgabe.yaml` | Manifeste: Vertrauen, Routen, neue Paket-Werkzeuge |
| `runtime/src/guppi_runtime/uix/**/arbeitsplatz.yaml` | Arbeitsplatz-Wissen, das das Modell liest (W6) |
| `runtime/src/guppi_runtime/uix/desk.html`, `…/uix/retro_desktop.html`, `…/uix/js/**` | Seiten des Servers; das Archiv `/retro` läuft mit `unsafe-inline` (`uix_server.py:3716`) |
| die Prüfstellen aus `SPEC_APPS_v1_AM0_G2.md` Teil A (`desk/gateway.py`, `desk/install.py`, `desk/registry.py`, `desk/herkunft.py`, `uix_server.py`, `uix_clients.py`, `cloud_settings.py`, `models/cloud_api.py`, `runtime/config/cloud_providers.yaml`) | unverändert |

**Weich** (neu in `vorbehalte.pruefen_weich`, für `datei_schreiben`/`datei_aendern`):
- Muster: `runtime/src/guppi_runtime/uix/shells/**`, `…/uix/tools/**`, `…/uix/css/**` – soweit nicht hart.
- Ergebnis `{grund: 'Captain-Vorbehalt: Code der Oberfläche (läuft in der Seite mit allen Rechten)', oberflaeche: <pfad>}`.
- Deckung: nur eine Aufgabe mit dem neuen Feld `oberflaeche: [muster …]`, in dem ein Muster den Pfad trifft – genau wie `modelle` beim weichen Vorbehalt für Modelle (`harness/aufgabe.py:302–307`). Eine Sitzungs-Erlaubnis (auch die der MasterChat-Vorlage) deckt nicht (`harness/freigabe.py:235` schließt sie bei weichem Vorbehalt schon heute aus). Der Vorarbeiter deckt nicht.
- Die Aufgaben-Freigabe zeigt beim Feld `oberflaeche` den Satz: „Code an diesen Stellen läuft in der Oberfläche mit allen Rechten der Seite – auch Freigaben. Er wirkt nach dem nächsten Neuladen. Gib nur Pfade frei, die zu diesem Zweck gehören.“ Ein Muster breiter als ein einzelner Shell- oder Werkzeugordner (z. B. `…/uix/tools/**`) wird abgewiesen (`oberflaeche_zu_breit`).

**Frei** (normaler Katalog): `runtime/src/guppi_runtime/uix/**/README.md`.

**MasterChat-Vorlage**: Der Hinweistext nennt die Ausnahme („Oberfläche nur über eine Aufgabe mit genannten Pfaden“). Die Vorlage ist selbst Vorbehalt (`runtime/config/harness_vorlagen/**`); die Änderung macht Claude.

**Zu prüfen in G3:** ob `katalog.passt` Muster wie `…/uix/**/tool.yaml` (Doppelstern in der Mitte) so auswertet wie erwartet (`harness/katalog.py:72ff`, Pfad-Teil nicht gelesen); wie lange Aufgaben gelten und wie die Zahl der Aufrufe begrenzt ist (`aufgabe.py`, `zaehlen`).

**Tests:** `tests/test_harness_vorbehalte.py` (hart/weich/frei je Muster), `tests/test_harness_aufgabe.py` (Deckung nur mit `oberflaeche`; zu breites Muster abgewiesen; Sitzungs-Erlaubnis deckt nicht), Test der MasterChat-Sitzung: Schreiben in `uix/shells/harness/x.js` ergibt ohne Aufgabe eine Karte.

## 7. O5 als Baustein AM9 „Werkstatt und Betrieb trennen“ (Skizze für ein späteres G1)

| Teil | Inhalt | Was es schon gibt |
|---|---|---|
| Betrieb | SEDRA läuft aus einem Ordner, in den nur der Updater schreibt; `local_config`, `runtime_data`, Modelle bleiben dort | Updater schützt diese Ordner schon (`update_anwenden.py:10–11`); USB-Stick ist bereits eine eigene Installation |
| Werkstatt | Git-Arbeitsordner des Projekts; hier arbeiten MasterChat, Bauagent, Claude; `uix/**` dort ohne harten Vorbehalt (Aufgaben genügen) | Harness-Projekte, DevVM |
| Prüfen in der Werkstatt | Tests und `uix_check` laufen gegen einen Prüfserver aus der Werkstatt, nicht gegen den Betrieb | `benchmarks/uix_check.py` startet schon eigene Server |
| Übernahme | „Lokales Release“: aus einem Commit der Werkstatt ein Manifest bauen, dann der bestehende Weg des Updaters (Prüfsummen, Rechte-Diff, Bestätigung genau dieser Liste, Sicherung, Neustart, Rückweg) | `update_anwenden.py` vollständig; **fehlt**: lokale Quelle statt GitHub-Tag (`update_holen.py`) |
| Nachweis | Übernahme als Gate im Posteingang, Audit mit Commit und Manifest-Hash | Muster vorhanden |

Offene Fragen für dieses spätere G1: Wie arbeitet der Captain im Alltag mit zwei Ordnern (Pfade, Starter)? Wo laufen Modelle für Tests in der Werkstatt (GPU-Sperre, `jobs/testlab.py`)? Wie passt das zum Stick (eigene Installation, gleiche Übernahme)? Wie werden eilige Korrekturen am Betrieb gemacht (nur über die Übernahme, oder ein Notweg für Claude)?

## 8. Entscheidung

| Nr | Frage | Vorschlag |
|---|---|---|
| AM0-E1 (neu) | Schutz des Oberflächen-Codes jetzt | **O3** (hart/weich/frei wie §6) |
| AM0-E1b | Werkstatt und Betrieb trennen als eigener Baustein AM9 (erst G1)? | ja |
