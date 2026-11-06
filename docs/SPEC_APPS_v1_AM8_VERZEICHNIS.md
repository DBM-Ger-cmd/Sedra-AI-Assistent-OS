# SPEC Apps v1 – AM8: Ein Verzeichnis für alle Erweiterungen, gemeinsame Wirkungsklassen, Auslieferungsprofile (03.11.2026)

Status: **G1**, Entscheidungen getroffen (03.11.2026, wie vorgeschlagen); G2 steht noch aus. Nichts gebaut. Teil von `docs/KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` §2.1, §2.2, §5.3, §11. Setzt AM3 voraus.
Ziel: Die acht Erweiterungswege (E1–E8) bleiben technisch, wie sie sind, bekommen aber **eine gemeinsame Sicht**: ein Verzeichnis, in dem jede Erweiterung mit Herkunft, Vertrauen, Wirkungsklassen ihrer Fähigkeiten und Abhängigkeiten steht. Daraus lassen sich Auslieferungen (z. B. der USB-Stick) ableiten statt von Hand aufzählen.
Pfade relativ zu `runtime/src/sedra_runtime/`, Zeilen für c364081.

## 1. Befund

| Nr | Befund | Beleg |
|---|---|---|
| B1 | Acht Erweiterungswege mit eigener Form und Prüfung (Konzept §2.1). Es gibt keine Stelle, die sie gemeinsam zeigt. | Konzept §2.1 |
| B2 | Fünf Vokabulare für Rechte/Wirkung (Konzept §2.2). Am genauesten sind die Wirkungsklassen der Agenten-Vorlagen. | `agent_manager/agent_import.py:126–186` |
| B3 | Für die USB-Ausgabe werden die Abhängigkeiten der Translator-Shell von Hand aufgezählt (Werkzeuge, Kern-Module `fisch/`, `sprache/`, ui-Dateien, Fenster). **Nachtrag 03.11.:** Auf dem Branch `plan/usb-stick-minimal` gibt es `runtime/benchmarks/stick_liste.txt` (Zeilen `repo`, `bestand`, `modul`; `modul` nimmt ein Python-Modul mit allen statischen Importen `sedra_runtime.*` mit) und `stick_paket.py` (prüfen, kopieren ohne Verknüpfungen, `STICK_MANIFEST.json` mit Hashes). Werkzeuge und Shells stehen dort als ganze Ordner; was die Oberfläche braucht, wird weiter von Hand gewählt. | `docs/ENTSCHEIDUNGEN_USB_STICK.md:7–9`; Branch `plan/usb-stick-minimal` |
| B4 | Der Release-Updater führt eine Liste aller Programmdateien mit Hash (`release/MANIFEST.sha256`) und vergleicht Rechte von Modulen zwischen Ständen. | `update_anwenden.py:3–8, 36–115` |
| B5 | Harness-Werkzeuge haben Gruppen (`LESEN`, `WIRKUNG`, `LAUF`, …), aber keine Wirkungsklasse. | `harness/werkzeuge.py:35–42` |
| B6 | Ob Desk-Verben eine Wirkungsklasse tragen, ist nicht bekannt (`desk/kinds.py` teilweise, `desk/actions.py` nicht gelesen). | – |

## 2. Anforderungen

### 2.1 Verzeichnis

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM8-01 | `GET /api/erweiterungen` (nur Shell-Seite, nur lesen) liefert eine Liste aller Erweiterungen mit: `art` (E1–E8 als Wort: `werkzeug`, `shell`, `kern_erweiterung`, `architektur_modul`, `faehigkeit`, `agenten_vorlage`, `harness_vorlage`, `daten`), `id`, `name`, `herkunft` (`paket`, `captain`, `eingebaut`, `selbst_gebaut`, `importiert`), `vertrauen` (wo vorhanden), `version`, `faehigkeiten: [{name, wirkungsklasse}]`, `abhaengigkeiten`, `zustand` (`aktiv`, `aus`, `abgewiesen` mit Grund). | Test je Art |
| AM8-02 | Quellen je Art: E1/E2 aus `desk/gateway.py` und `berechtigung.yaml` (AM3); E3 aus `desk/extensions.MODULES` und dem eingefrorenen Register; E4 aus `core/registry.py`; E5 aus `capabilities/` und den Übernahme-Missionen; E6 aus dem Agenten-Register; E7 aus `runtime/config/harness_vorlagen/`; E8 aus `skill_library` (Index), `cloud_providers.yaml` (mit Empfänger, AM5-08), Wissensquellen. Wo eine Quelle nicht lesbar ist, steht die Art mit `zustand: unbekannt` und Grund in der Liste – nichts fehlt still. | Test |
| AM8-03 | Die Grundfunktion „Module und Berechtigungen“ zeigt das Verzeichnis mit Filter nach Art, Herkunft, Wirkungsklasse; Klick auf eine App führt zur Berechtigungsseite (AM3-25), bei anderen Arten zu ihrer bestehenden Stelle (Agenten → Besatzung, Vorlagen → Einstellungen → Agent, Anbieter → Integrationen). | uix_check |
| AM8-04 | Export (JSON und lesbar) für Nachweis und Prüfung (AM7-13). | Test |

### 2.2 Gemeinsame Wirkungsklassen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM8-05 | Sieben Wirkungsklassen aus `agent_import.py` sind die gemeinsame **Anzeigesprache**: `read_only`, `proposal_only`, `preview`, `reversible_write`, `destructive_write`, `external_side_effect`, `privileged`. Sie ersetzen keine Entscheidung (Guard, Katalog, Permission-Stufen bleiben). | Doku |
| AM8-06 | Jedes Harness-Werkzeug bekommt eine Wirkungsklasse (Vorschlag, in G2 je Werkzeug prüfen): `datei_lesen`, `dateien_auflisten`, `suchen` → `read_only`; `datei_schreiben`, `datei_aendern` → `reversible_write` (Sicherung vorhanden? in G2 prüfen, sonst `destructive_write`); `befehl` → `destructive_write` (ein Programm kann alles tun, was der Katalog nicht verbietet); `lauf_starten` → `reversible_write`; `modell_laden`/`entladen` → `reversible_write`; `app_oeffnen` → `read_only`; `projekt_beantragen` → `proposal_only`; `sitzungen_aufraeumen` → `reversible_write` (verschiebt nach `geloescht/`, „nichts wird endgültig gelöscht“, `harness/werkzeuge.py:98`). | Test: jedes Werkzeug aus `NAMEN` hat eine Klasse |
| AM8-07 | Jedes Desk-Verb bekommt eine Wirkungsklasse (Feld im Register; Verben ohne Klasse → beim Start gemeldet). | Test |
| AM8-08 | Agenten-Vorlagen behalten ihre Prüfung (`destructive_write`, `external_side_effect`, `privileged` dort nicht erlaubt, `agent_import.py:178–180`). Das Verzeichnis zeigt die Klassen nur an. | Test |
| AM8-09 | Eine Abbildungstabelle (Konzept §5.3) steht als Datei `runtime/config/wirkungsklassen.yaml` mit Bedeutung je Klasse und der Lesehilfe „entspricht ungefähr“. Sie wird nur angezeigt. | Test: Datei vollständig |

### 2.3 Auslieferungsprofile

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM8-10 | Manifeste nennen Abhängigkeiten: `needs.apps` (AM2-19), `needs.kern` (Liste von Kern-Paketen, z. B. `[fisch, sprache]`), `needs.ui` (Vertragsdateien, z. B. `[sprache.js, wechsel.js]`). Shells nennen ihre Apps über Grundfunktionen und Start-Gruppen. | Schema-Test |
| AM8-11 | **Kein zweites Werkzeug:** `stick_paket.py` bekommt eine Zeilenart `shell <id>` bzw. `app <id>`, die aus den Manifesten (`needs.apps`, `needs.kern`, `needs.ui`, Grundfunktionen) die Hülle der Ordner und Module ableitet; `--pruefen` meldet fehlende Abhängigkeiten. Voraussetzung: der Stick-Branch ist auf `main`. | Test im Stil von `test_stick_paket.py` |
| AM8-12 | Gegenprobe: Für den Stick ergibt die Ableitung aus den Manifesten mindestens die Zeilen der heutigen `stick_liste.txt`; Abweichungen werden als Befund aufgeschrieben, nicht still angeglichen. | Test |

## 3. Entwurf

- `desk/verzeichnis.py` (neu, ≤ 400 Zeilen, nur lesen) sammelt aus den Quellen in AM8-02; je Quelle eine kleine Lesefunktion, die bei Fehlern `zustand: unbekannt` liefert.
- Wirkungsklassen in `harness/werkzeuge.py` als Wörterbuch neben `SCHEMAS`; Test gegen `NAMEN`.
- Auslieferung: Erweiterung von `runtime/benchmarks/stick_paket.py` (Branch `plan/usb-stick-minimal`) statt einer neuen Datei; nutzt `Registry.module_dirs` und die Manifeste; Kern-Pakete als Ordner unter `sedra_runtime/`.

## 4. Tests und Abnahme

Je Art ein Test mit Fake-Quellen; Vollständigkeit der Wirkungsklassen; Gegenprobe Stick. Abnahme: Verzeichnis am PC ansehen; der Captain prüft stichprobenartig fünf Einträge gegen die bekannten Stellen.

## 5. Rückfall

Reine Anzeige; ohne den Baustein bleibt alles wie heute.

## 6. Abgrenzung

Keine Zusammenlegung der Vokabulare, keine neue Entscheidungsinstanz, kein gemeinsamer Einbauweg für alle Arten (E3–E5 bleiben Paket bzw. Selbstentwicklung mit ihren Gates). Keine Kopie von Dateien durch das Auslieferungswerkzeug.

## 7. Risiken

- Gering für den Betrieb (nur lesen). Die Wirkungsklassen der Harness-Werkzeuge können umstritten sein; sie sind Anzeige und werden in G2 einzeln begründet.
- Das Verzeichnis kann veraltete Quellen zeigen (z. B. Architektur-Module, die nicht mehr genutzt werden); das ist ein nützlicher Befund, kein Fehler des Bausteins.

## 8. Entscheidungen des Captains

**Entschieden vom Captain am 03.11.2026: alle Vorschläge dieser Tabelle übernommen.**

| Nr | Frage | Vorschlag |
|---|---|---|
| AM8-E1 | Wirkungsklassen der Agenten als gemeinsame Anzeigesprache übernehmen? | ja |
| AM8-E2 | `befehl` als `destructive_write` einstufen? | ja (ehrliche Obergrenze; der Katalog entscheidet weiter im Einzelfall) |
| AM8-E3 | Auslieferungswerkzeug jetzt oder erst beim nächsten Stick-Stand? | mit dem nächsten Stick-Stand |

## 9. Berechtigungen vorab

Schreiben `desk/verzeichnis.py`, `auslieferung.py`, `harness/werkzeuge.py` (nur Wirkungsklassen), `runtime/config/wirkungsklassen.yaml`, Werkzeug `modules`, Tests. Lesen aller Quellen aus AM8-02.

## 10. Nächste Gates

G1 → G2 (Lesen von `desk/actions.py`, Agenten-Register, Wissensquellen) → G3 → G4.
