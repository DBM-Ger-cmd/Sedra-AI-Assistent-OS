# Entscheidungsvorlage AM0-E1: Wie schützen wir den Code der Oberfläche vor Änderungen durch das Modell? (03.11.2026)

Status: **entschieden** am 03.11.2026: O3+ (§6 mit G1, G2, G3, G6, G7), G4 sofort, AM9 mit G5. G9–G11 aus §5b am selben Tag übernommen. Verlauf: Der Captain hatte AM0-E1 zuerst zur Ausarbeitung zurückgegeben („Das müssen wir mehr ausarbeiten, was am besten und praktikabel ist“), danach das Restrisiko (§5a) und den Fall „bestätigter schädlicher Code“ (§5b) nacharbeiten lassen.
Pfade relativ zu `runtime/src/sedra_runtime/`, Zeilen für c364081.

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
| **SEDRA in der DevVM** | baut in einer Kopie, Übernahme per `adopt_plan` oder Handkopie | `docs/ARCHITEKTUR.md` §4, §6a (Linie L5) |

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

Was es dafür schon gibt (O5): Der Release-Updater übernimmt nur einen vollständig geprüften Stand (`release/MANIFEST.sha256`, Prüfbereiche `runtime/src/sedra_runtime/` und `runtime/config/`), nennt jede Rechteänderung eines Moduls einzeln, braucht die Bestätigung genau dieser Liste, sichert vorher und kann zurück (`update_anwenden.py:3–11, 23–24, 89–115, 151–171`). Er holt heute aber nur Release-Tags von GitHub (`update_holen.py:1–4, 22–23`), keine lokale Werkstatt.

## 5. Empfehlung

**Jetzt (AM0): O3.** Später (eigener Baustein **AM9**): **O5**. O1, O2 und O4 nicht.

Begründung:
- O2 schließt die Lücke nicht (W5).
- O1 ist sicher, aber im Alltag des MasterChat nicht praktikabel; viele Einzelkarten führen zu Bestätigen ohne Lesen. Eine einzige, bewusste Entscheidung über Zweck und Pfade (O3) ist wirksamer als dreißig Karten.
- O4 löst nur die Hälfte (Python nicht) und baut einen zweiten Mechanismus neben dem Updater.
- O5 ist die eigentliche Antwort: Solange Werkstatt und Betrieb derselbe Ordner sind, ist jeder Schutz in der Harness ein Schutz an der Tür eines Hauses, an dessen Wänden das Modell baut. O5 ist aber ein großer Schritt und braucht eigene Entscheidungen (§7).

**Restrisiko von O3:** nachgearbeitet in §5a. Ergebnis vorweg: O3 allein reicht nicht; es braucht zwei Ergänzungen (Abnahme vor Wirkung, Ausführung von Modell-Code nur nach Sicht), und eine davon betrifft alle Vorbehalte, nicht nur die Oberfläche.

## 5a. Restrisiko der gestuften Lösung – nachgearbeitet (Auftrag des Captains, 03.11.2026)

### 5a.1 Die Kette, um die es geht

| Schritt | Was passiert | Beleg |
|---|---|---|
| K1 | Das Modell schreibt in einer freigegebenen Aufgabe JavaScript in einen Oberflächen-Pfad (z. B. `uix/shells/harness/`). | O3, §6 |
| K2 | Der Captain lädt die Seite neu (oder öffnet sie neu). Der neue Code läuft in der Seite. | `uix_server.py:3682` (`no-store`) |
| K3 | Der Code liest den Token aus der Adresse. | `ui/api.js:6, 9` |
| K4 | Mit dem Token beantwortet er wartende Karten und Entscheidungen, legt Aufgaben an, ernennt den Vorarbeiter oder gibt Module frei. Die zusätzliche Herkunftsprüfung S7 hilft hier **nicht**: Sie lehnt Anfragen aus Prozessen ab, die die Harness gestartet hat (`befehl`, Läufe); der Browser ist keiner davon. | `harness/herkunft.py:1–10`; `harness/api.py:85–87, 223`; `uix_server.py:3609–3618` |
| K5 | Damit fallen auch die **harten** Vorbehalte (`core/**`, Guard-Regeln, Freigabe-Code): Ihr Schutz ist eine Karte an den Captain – und die Karte kann der Code beantworten. | `harness/freigabe.py:38–44` |

Was die Kette **begrenzt**: Die Seite darf nur mit dem eigenen Server sprechen (`connect-src 'self'`, `uix_server.py:3686–3687`); Daten können nicht direkt ins Netz abfließen, nur über Wege des Servers – deren Gates der Code aber nach K4 selbst beantworten könnte (z. B. eine Cloud-Adresse ändern, `uix_server.py:2673–2703`). Am Ende hängt alles an **K2 und K4**.

### 5a.2 Woher eine schädliche Änderung kommen kann

| Quelle | Beispiel | Einschätzung |
|---|---|---|
| Fehler des Modells | kaputter Code, falscher Pfad, Endlosschleife | am wahrscheinlichsten; meist kein Angriff, aber eine **kaputte Oberfläche** (§5a.4) |
| Eingeschleuste Anweisungen in gelesenen Inhalten | eine Datei im Projekt, ein Dokument, ein Text aus der Skill-Bibliothek (verdächtige werden markiert, `skill_library/__init__.py:8–10`), der Wissensspeicher, eine Antwort eines fremden Modells (Langdock, AM6), `arbeitsplatz.yaml` (W6) | heute niedrig bis mittel (lokales Modell, wenige fremde Quellen); steigt mit Cloud, Langdock und fremden Dokumenten |
| Manipuliertes Modell (Gewichte) | – | niedrig; außerhalb dieses Konzepts |

Eine Zahl für die Wahrscheinlichkeit gibt es nicht; dafür fehlen Messungen. Die Einschätzung ist qualitativ.

### 5a.3 Neuer Befund: ein zweiter Weg an **allen** Vorbehalten vorbei

| Schritt | Beleg |
|---|---|
| Die MasterChat-Vorlage gibt für die Sitzung frei: Schreiben in `runtime/tests/**` und `runtime/src/**`, den Lauf `run_tests`. | `runtime/config/harness_vorlagen/masterchat.yaml:14–26` |
| `run_tests` startet `python benchmarks/run_tests.py <gruppen>` **auf dem Rechner** (Hülle ohne Shell, aber ohne VM). | `runtime/config/harness_laeufe.yaml` (`run_tests`); `harness/lauf_huelle.py:1–5` |
| Die Gruppen sind Muster; neue Testdateien werden mitgenommen („Glob nimmt neue Dateien auf“); einzelne Testdateien lassen sich auch beim Namen nennen. | `runtime/benchmarks/run_tests.py:3–9, 32, 38` |
| Folge: Das Modell schreibt eine Testdatei (oder eine Python-Datei, die ein Test importiert) und startet `run_tests`. Der Code läuft mit den Rechten des Captains und kann **jede Datei** schreiben – `uix/ui/**`, `core/**`, `local_config/**`. Die Vorbehalte prüfen nur die Werkzeuge `datei_schreiben`/`datei_aendern` (`harness/vorbehalte.py:35`, `SCHREIBEN`). S7 verhindert nur, dass dieser Prozess Karten über HTTP beantwortet. | – |

Das ist **kein** Problem der Oberfläche allein und besteht heute schon. Es muss unabhängig von AM0-E1 geschlossen werden (§5a.5, G4).

Ebenso, aber schwächer: Python-Dateien unter `runtime/src/**`, die das Modell in einer MasterChat-Sitzung schreibt, wirken beim **nächsten Start** von SEDRA ohne weitere Prüfung.

### 5a.4 Verfügbarkeit: wenn die Oberfläche kaputt ist

Ein Fehler in einer Shell-Datei kann die Oberfläche unbenutzbar machen – auch den Posteingang. Was es heute gibt:
- Wechsel in eine andere Shell (Start-Shell, Auswahl in `local_config/uix.yaml`). Ob der Wechsel bei einer kaputten aktiven Shell aus der Oberfläche heraus möglich ist, wurde nicht geprüft.
- Die Karte einer Dateiänderung ist mit `rollback_available=True` angelegt (`harness/freigabe.py:240`); einen Rückweg-Mechanismus für einzelne Dateien habe ich im Harness-Code **nicht** gefunden. Der Rückweg ist heute Git (von Hand).
- Ob die CLI (`sedra …`) Freigaben beantworten kann, wurde nicht geprüft (ARCHITEKTUR §6 nennt „Freigaben“ unter den Befehlen).

### 5a.5 Gegenmaßnahmen

| Nr | Maßnahme | Bricht | Aufwand | Empfehlung |
|---|---|---|---|---|
| G1 | **Aufgabe eng**: `oberflaeche` höchstens ein Shell- oder Werkzeugordner (§6); Ende Pflicht (`bis` oder `max_aufrufe`, besteht schon: `harness/aufgabe.py:123–125`); höchstens **eine** aktive Aufgabe mit `oberflaeche` je Projekt | verkleinert K1 | gering | ja |
| G2 | **Abnahme vor Wirkung**: Schreibt das Modell unter einer Aufgabe in einen Oberflächen-Pfad, liefert der Server im Betrieb **weiter die zuletzt bestätigte Fassung** dieser Datei aus. Die neue Fassung liegt auf der Platte (Tests und `uix_check` sehen sie), wirkt aber nicht in der Oberfläche des Captains. Am Ende der Aufgabe (erledigt, abgelaufen, zurückgenommen) oder auf Wunsch entsteht **eine** Sammelkarte „Oberflächen-Änderungen übernehmen“ mit dem vollständigen Diff je Datei. Erst nach Freigabe liefert der Server die neue Fassung. Zum Ansehen vorher: **Vorschau im Prüfserver** – ein eigener Server mit leerem Prüfprojekt und eigenem Token auf einem anderen Port (wie `benchmarks/uix_check.py:298–316` ihn schon startet); dort erreicht Code keine echten Entscheidungen. | bricht **K2** im Betrieb | mittel | **ja – Kern der Nacharbeit** |
| G3 | **Hinweise im Diff**: Die Sammelkarte markiert Zeilen mit Mustern wie Zugriff auf `location`/Adresse, `decisions/answer`, `/api/harness/karten`, `aufgaben`, `/api/uix/install`, `trust`, `eval`, `new Function`, `innerHTML` (Muster wie `desk/install.py:26–46`). Umgehbar, aber eine Lesehilfe. | erleichtert das Prüfen in G2 | gering | ja |
| G4 | **Ausführung von Modell-Code nur nach Sicht**: Hat die Sitzung seit dem letzten vom Captain gesehenen Lauf `.py`-Dateien unter `runtime/**` geschrieben oder geändert, wird `lauf_starten` (jeder Lauf, der Python im Projekt ausführt) zu einer **Karte** mit der Liste und dem Diff dieser Dateien; keine Sitzungs-Erlaubnis und keine Aufgabe deckt das. Gleiches gilt für `befehl`, wenn die Befehlszeile eine Datei im Projekt ausführt (`python <datei>`). Alternative: Läufe mit vom Modell geschriebenem Code nur in der microVM. | schließt den Weg aus §5a.3 | gering bis mittel | **ja, sofort und unabhängig von AM0-E1** |
| G5 | **Freigaben auf eigener Herkunft**: Posteingang und Antworten auf Karten laufen auf einem **zweiten Port** mit eigenem Token und nur Vertragscode; der Token der Arbeitsoberfläche kann keine Entscheidung mehr beantworten. Wie bei Android, wo Berechtigungsdialoge nicht von der App gezeichnet werden. | bricht **K4** grundsätzlich – auch für Code, der durch G2 durchgerutscht ist | hoch (Karten stehen heute im Gespräch und in der Seitenleiste; sie würden zu eingebetteten Fenstern einer anderen Herkunft) | später, mit AM9 |
| G6 | **Startbericht**: Beim Start nennt SEDRA die Dateien unter `runtime/src/**`, die seit dem letzten Start über die Harness geändert wurden (aus dem Audit), im Posteingang. | macht Python-Änderungen beim Neustart sichtbar (verhindert nichts) | gering | ja, als Übergang bis AM9 |
| G7 | **Rückweg**: Die bestätigten Fassungen aus G2 bleiben gespeichert; „Übernahme zurücknehmen“ stellt die vorige Fassung wieder her – auch ohne Oberfläche (Befehl der CLI). | Verfügbarkeit (§5a.4) | gering (fällt bei G2 mit an) | ja |
| G8 | **Werkstatt und Betrieb trennen** (AM9) | K2 für Oberfläche **und** Python | hoch | ja, als Baustein |

### 5a.6 Restrisiko nach den Maßnahmen

| Mit | Was bleibt | Wie groß |
|---|---|---|
| O3 + G1, G2, G3, G4, G6, G7 | (1) Der Captain bestätigt die Sammelkarte, ohne den Diff zu lesen, oder übersieht gut versteckten Code. G3 hilft, verhindert es nicht. (2) Python-Änderungen im Betrieb wirken beim Neustart; G6 zeigt sie nur an. (3) Bestätigter schädlicher Code kann danach Entscheidungen beantworten (K4) – nachgearbeitet in §5b: mit G9 nur noch Klasse N. (4) Änderungen, die Claude direkt im Repo macht, laufen an der Harness vorbei – das ist der vertraute Weg und bleibt so. (5) Fehler in den neuen Prüfstellen selbst. | (1) und (3) hängen an einem bewussten Schritt des Captains statt an einem Neuladen; (2) bleibt bis AM9; (5) durch Tests begrenzt |
| zusätzlich G5 | (3) entfällt: Auch bestätigter Code kann keine Entscheidung mehr erteilen | – |
| zusätzlich G8 | (2) entfällt: Python und Oberfläche kommen nur über die Übernahme in den Betrieb | – |

**Ehrliche Kurzfassung:** Mit O3 allein ist das Restrisiko groß, weil ein Neuladen genügt und weil Testläufe heute alle Vorbehalte umgehen. Mit G2 und G4 hängt jeder Schritt von Modell-Code in den Betrieb an einer Entscheidung des Captains, die er mit vollem Diff sieht. Ganz weg ist es erst mit G5 und G8.

### 5a.7 Was G2 und G4 im Code bedeuten (für ein späteres G2-Dokument)

- **G2**: Die Harness merkt sich beim Schreiben unter einer Oberflächen-Aufgabe Pfad und vorige Fassung (Ablage unter `runtime_data/harness/oberflaeche/` – dort schon harter Vorbehalt `**/runtime_data/harness/**`, `harness/vorbehalte.py`). `Gateway.file` (die eine Stelle, die `/uix/{ui,shells,tools}/…` ausliefert, `uix_server.py:3575–3590`) liefert für gemerkte Pfade die bestätigte Fassung. Sammelkarte als Gate mit Bindung an die Liste der Hashes. Vorschau: neue Route, die einen Prüfserver wie `uix_check.start_server` startet und seine Adresse nennt.
- **G4**: Die Harness führt je Sitzung eine Liste „seit dem letzten gesehenen Lauf geschriebene `.py`-Dateien“. `vorbehalte.pruefen` gibt für `lauf_starten` (und `befehl` mit `python <datei im Projekt>`) einen Vorbehaltsgrund zurück, solange die Liste nicht leer ist; die Karte zeigt die Diffs; nach der Antwort ist die Liste leer.
- Beides berührt Harness-Code unter Vorbehalt (`harness/freigabe.py`, `vorbehalte.py`, `lauf.py`) – Änderung nur durch Claude, mit Freigabe des Captains.

## 5b. „Bestätigter schädlicher Code kann Freigaben erteilen“ – gezielt nachgearbeitet (Auftrag des Captains, 03.11.2026)

Gemeint ist der Fall nach G2: Code steht in der Oberfläche, weil er bestätigt wurde (oder aus dem Paket, von Claude oder über den Updater kam), und er ist schädlich oder fehlerhaft. Frage: Was hindert ihn daran, Freigaben zu erteilen?

### 5b.1 Warum man den Token in der Seite nicht verstecken kann

Geprüft und verworfen: den Token nach dem Lesen aus der Adresse entfernen und nur in `ui/api.js` halten.
- Alle Skripte einer Herkunft teilen sich Fenster, DOM und eingebaute Funktionen. Ein späteres Skript kann `fetch` umhüllen, die Funktionen von `api.js` ersetzen oder den Token aus der Liste der geladenen Adressen lesen (der Ereignisstrom trägt ihn in der Adresse, `ui/api.js:40`).
- Ohne Token in der Adresse ginge außerdem das Neuladen der Seite verloren.
- Der Vertrag sagt es selbst: Die Grenze ist die Abschottung, nicht das Verstecken (`ui/api.js:6`).

**Folgerung:** Gegen Code in der Seite hilft nur ein Weg, den dieser Code **nicht erreicht**: eine andere Herkunft (G5) oder ein Kanal außerhalb des Browsers.

### 5b.2 Alle Wege, auf denen heute eine Freigabe erteilt wird

| Nr | Weg | Wo | Was er erteilt |
|---|---|---|---|
| F1 | `POST /api/decisions/answer` (Posteingang) | `uix_server.py:261–310` | alle Entscheidungen: Missions-Gates, Grenzüberschreitungen, Scheduler (`cloud_offload`, `slot_server`), Inhaltsschutz, Harness-Karten und -Aufgaben, Anträge mit Anwenden: Schalter, Routing, Modell hinzufügen, Bibliothek, Grenzen, **Modul einbauen**, **Schreibrechte für Module**, Gateway, **Update übernehmen**, **Cloud-Adresse** (`:302–306`) |
| F2 | `POST /api/mission/approve` | `uix_server.py:2196–2213` | ein Missions-Gate direkt |
| F3 | `POST /api/harness/karten/<id>` | `harness/api.py:245`; `harness/freigabe.py:303–324` | eine Harness-Karte; mit Weg `sitzung` zusätzlich eine **Sitzungs-Erlaubnis** für gleichartige Aufrufe |
| F4 | `POST /api/harness/aufgaben` | `harness/api.py` (Route, geschützt durch S7) | eine **Aufgabe** = Freigabe im Voraus für eine Liste von Aufrufen (`harness/freigabe.py:230–243`) |
| F5 | `POST /api/harness/vorarbeiter` | `harness/api.py:85` | ernennt den **Vorarbeiter**, der Karten der Stufe `vorarbeiter` selbst beantwortet |
| F6 | `POST /api/harness/katalog/antrag` und Anwenden | `harness/api.py:85–86` | ändert den **Freigabe-Katalog** (künftig `frei`) |
| F7 | Verben des Desk mit Gate | `desk/gated.py:145` | Freigabe eines Desk-Verbs |
| F8 | `POST /api/update/uebernehmen` | `uix_server.py:3862` | übernimmt einen geprüften Release-Stand mit der Rechte-Bestätigung aus der Vorschau |
| F9 | ohne Gate, nur Audit: Shell wechseln, Werkzeug an/aus, künftig App aktivieren (AM3-08) | `uix_server.py:3848–3850` | Form, keine Rechte |
| F10 | **Konsole**: `sedra approve <mission> <gate>` | `cli.py:316–324` | ein Missions-Gate – **außerhalb des Browsers** |

Alle Wege F1–F9 nimmt der Server mit dem Browser-Token an. S7 schützt F3–F6 gegen Prozesse der Harness, nicht gegen den Browser (§5a.1, K4). F10 ist der einzige Weg, den Code in der Seite nicht erreicht.

### 5b.3 Was bestätigter schädlicher Code damit tun könnte

| Wirkung | über | Klasse |
|---|---|---|
| beliebige Programme auf dem Rechner starten | Karte zu `befehl` beantworten (F3); Lauf freigeben (F3/F4) | **H** |
| dauerhaft weiter freigeben, auch ohne Seite | Aufgabe anlegen (F4), Vorarbeiter ernennen (F5), Sitzungs-Erlaubnis (F3, Weg `sitzung`), Katalog lockern (F6) | **H** |
| Regeln und Kern ändern | Karten zu harten Vorbehalten (`core/**`, Guard, Harness-Code), Grenzen, Schalter (F1, F3) | **H** |
| weiteren Code in den Betrieb bringen | G2-Sammelkarte, Modul einbauen, Schreibrechte für Module, Update übernehmen (F1, F8) | **H** |
| Daten nach außen geben | Cloud-Adresse ändern, Inhaltsschutz-Entscheidung für die Cloud, Langdock-Frage (AM6), Gateway-Weg Cloud (F1, F7) | **H** |
| Dateien im Projekt schreiben (außerhalb der Vorbehalte) | Karte zu `datei_schreiben`/`datei_aendern` (F3) | **N** – Python davon wirkt beim Neustart (G6 zeigt es an) |
| Modelle laden, lokale Gateway-Vorgänge freigeben, Inhaltsschutz lokal | F1, F3 | **N** |
| ablehnen, zurücknehmen, stören | alle | **N** – lästig, keine neuen Rechte |
| lesen, was die Seite lesen darf | Leserouten | – (ohne Weg nach außen bleibt es lokal; der Weg nach außen ist **H**) |

**Klasse H** = erteilt Rechte für später, führt Code oder Programme aus, ändert Regeln oder Kern, bringt Code in den Betrieb oder gibt Daten nach außen. **Klasse N** = einzelne Handlung im Projekt ohne diese Folgen.

### 5b.4 Maßnahmen

| Nr | Maßnahme | Was sie bewirkt | Aufwand | Empfehlung |
|---|---|---|---|---|
| **G9 (neu)** | **Bestätigung außerhalb des Browsers für Klasse H.** Antwortet die Seite auf eine Freigabe der Klasse H, führt der Server sie **nicht** aus, sondern zeigt ein Fenster des Betriebssystems (Windows: Systemdialog aus dem Server-Prozess, immer im Vordergrund) mit dem Text, den **der Kern** erzeugt (Gate-Beschreibung, Klasse, Ziel, Kennung) und „Freigeben“/„Ablehnen“. Erst das Ja dort ruft `guard.approve`. Ohne Dialog möglich (anderes System, keine Anzeige): nur über die Konsole (`sedra freigeben <kennung>`, wie F10). | Code in der Seite erreicht weder das Fenster noch die Konsole. Klasse H ist damit für ihn **gesperrt**, auch wenn er bestätigt wurde. | gering bis mittel | **ja, vor oder mit O3+** |
| G5 | Freigaben auf eigener Herkunft (AM9, beschlossen) | macht die Freigabe im Browser selbst vertrauenswürdig; kann G9 für viele Fälle ersetzen | hoch | ja (AM9) |
| G10 (neu) | **Kanal im Audit**: jede Freigabe trägt `kanal` = `seite` · `systemdialog` · `konsole` · `freigabefenster` (G5) · `aufgabe` · `sitzung` · `vorarbeiter` · `katalog` | Nachweis, woher eine Freigabe kam; macht Missbrauch erkennbar | gering | ja |
| G11 (neu) | **Vollständigkeitstest**: ein Test findet jede Stelle, die `guard.approve` ruft (heute `cli.py:322`, `harness/freigabe.py:243, 324`, `uix_server.py:2213`, `desk/gated.py:145`, `agent_manager/cli.py:74`), und jede geschützte Route, und verlangt für jede eine Klasse (H/N) | verhindert, dass ein neuer Freigabe-Weg die Klasse H umgeht | gering | ja |
| – | Heuristiken (z. B. „Freigabe schneller als 1 s nach Erscheinen der Karte“ anhalten) | Code in der Seite kann Wartezeiten nachahmen; nur als Hinweis brauchbar | gering | nein (falsche Sicherheit) |

**Wie häufig wäre der Systemdialog?** Nur bei Klasse H. Im Alltag des MasterChat sind das: Aufgaben anlegen, Karten zu `befehl` außerhalb der freien Muster, Läufe nach G4, die G2-Sammelkarte, Änderungen an Regeln und Modulen, Updates. Dateien schreiben, Modelle laden und lokale Gateway-Vorgänge bleiben im Browser (Klasse N). Eine Messung, wie oft das am Tag ist, gibt es nicht; das Audit (`HARNESS_EINGESTUFT`, `HARNESS_APPROVED_BY`) erlaubt sie nachträglich.

### 5b.5 Was danach bleibt

| Bleibt | Warum | Wer/was hilft |
|---|---|---|
| Der Captain bestätigt den Systemdialog, ohne zu lesen | Gewohnheit | Klasse H ist selten; der Text kommt vom Kern, nicht von der Seite; die Seite kann ihn nicht beeinflussen |
| Täuschung: die Seite löst eine echte, aber andere Freigabe aus, während der Captain eine erwartet | Code kann den Zeitpunkt wählen | der Dialog nennt Ziel und Kennung; G10 zeigt den Kanal; ganz verhindern lässt es sich nicht |
| Klasse N durch Code in der Seite (Dateien im Projekt, Modelle laden) | bewusst im Browser gelassen | Python-Änderungen wirken erst beim Neustart (G6 zeigt sie an); mit AM9 kommen sie nur über die Übernahme in den Betrieb |
| Andere Programme unter dem Konto des Captains können das Fenster bedienen (Eingaben simulieren) | Betriebssystem erlaubt das demselben Benutzer | außerhalb dieses Konzepts; G4 verhindert, dass vom Modell geschriebener Code ohne Sicht auf dem Rechner läuft |
| Ein vergessener Freigabe-Weg | Code wächst | G11 |

**Kurzfassung:** Mit G9 kann bestätigter schädlicher Code keine Freigabe der Klasse H mehr erteilen, und Klasse H umfasst alles, was zu mehr Rechten, zu Programmausführung, zu Kernänderungen, zu weiterem Code im Betrieb oder zu Daten nach außen führt. Was ihm bleibt, ist Klasse N und Lesen.

### 5b.6 G9 im Code (Skizze für G2)

- Neue Datei `desk/freigabeklasse.py`: Tabelle Entscheidungsart/Harness-Werkzeug/Route → Klasse; Vorgabe für Unbekanntes: **H**.
- An den Stellen F1–F8: Ist die Klasse H und kam die Antwort über die Seite, wird statt `approve` ein **Wartezustand** gespeichert („wartet auf Bestätigung außerhalb des Browsers“) und der Dialog angestoßen; die Seite zeigt den Zustand.
- Dialog: unter Windows `MessageBoxW` (ohne neue Abhängigkeit, wie `harness/herkunft.py` schon `ctypes` nutzt) mit `MB_YESNO | MB_TOPMOST | MB_SETFOREGROUND | MB_SYSTEMMODAL` in einem eigenen Thread; Antwort ruft `approve` oder `reject`; Zeitlimit 10 min, dann bleibt die Entscheidung offen. Ob ein Server ohne angemeldete Sitzung (z. B. als Dienst) Dialoge zeigen kann: nein – dann gilt nur die Konsole.
- Konsole: `sedra freigeben <kennung>` / `sedra ablehnen <kennung>` für alle Entscheidungen (heute nur Missions-Gates, `cli.py:316`).
- Audit: `FREIGABE_AUSSERHALB_BESTAETIGT {id, kanal}`, `…_ABGELEHNT`, `…_ZEIT_ABGELAUFEN`.
- Test: Antwort der Klasse H über die Seite führt nie zu `approve` ohne Dialog-/Konsolen-Antwort (Fake-Dialog im Test); G11.

## 6. O3 im Detail (ersetzt Teil A von `SPEC_APPS_v1_AM0_G2.md`, wenn freigegeben)

**Hart** (`harness/vorbehalte.py` `PFADE`; nur Karte an den Captain):

| Muster | Grund |
|---|---|
| `runtime/src/sedra_runtime/uix/ui/**` | Vertragscode: Lader, Brücke, Rahmen, Bus, Token-Zugang |
| `runtime/src/sedra_runtime/uix/**/tool.yaml`, `…/uix/**/shell.yaml`, `…/uix/**/shell.vorgabe.yaml` | Manifeste: Vertrauen, Routen, neue Paket-Werkzeuge |
| `runtime/src/sedra_runtime/uix/**/arbeitsplatz.yaml` | Arbeitsplatz-Wissen, das das Modell liest (W6) |
| `runtime/src/sedra_runtime/uix/desk.html`, `…/uix/retro_desktop.html`, `…/uix/js/**` | Seiten des Servers; das Archiv `/retro` läuft mit `unsafe-inline` (`uix_server.py:3716`) |
| die Prüfstellen aus `SPEC_APPS_v1_AM0_G2.md` Teil A (`desk/gateway.py`, `desk/install.py`, `desk/registry.py`, `desk/herkunft.py`, `uix_server.py`, `uix_clients.py`, `cloud_settings.py`, `models/cloud_api.py`, `runtime/config/cloud_providers.yaml`) | unverändert |

**Weich** (neu in `vorbehalte.pruefen_weich`, für `datei_schreiben`/`datei_aendern`):
- Muster: `runtime/src/sedra_runtime/uix/shells/**`, `…/uix/tools/**`, `…/uix/css/**` – soweit nicht hart.
- Ergebnis `{grund: 'Captain-Vorbehalt: Code der Oberfläche (läuft in der Seite mit allen Rechten)', oberflaeche: <pfad>}`.
- Deckung: nur eine Aufgabe mit dem neuen Feld `oberflaeche: [muster …]`, in dem ein Muster den Pfad trifft – genau wie `modelle` beim weichen Vorbehalt für Modelle (`harness/aufgabe.py:302–307`). Eine Sitzungs-Erlaubnis (auch die der MasterChat-Vorlage) deckt nicht (`harness/freigabe.py:235` schließt sie bei weichem Vorbehalt schon heute aus). Der Vorarbeiter deckt nicht.
- Die Aufgaben-Freigabe zeigt beim Feld `oberflaeche` den Satz: „Code an diesen Stellen läuft in der Oberfläche mit allen Rechten der Seite – auch Freigaben. Er wirkt nach dem nächsten Neuladen. Gib nur Pfade frei, die zu diesem Zweck gehören.“ Ein Muster breiter als ein einzelner Shell- oder Werkzeugordner (z. B. `…/uix/tools/**`) wird abgewiesen (`oberflaeche_zu_breit`).

**Frei** (normaler Katalog): `runtime/src/sedra_runtime/uix/**/README.md`.

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

**Entschieden vom Captain am 03.11.2026:**

| Nr | Frage | Entscheidung |
|---|---|---|
| AM0-E1 | Schutz des Oberflächen-Codes | **O3+**: gestuft hart/weich/frei (§6) mit G1, G2, G3, G6, G7 |
| AM0-E1c | Ausführung von Modell-Code nur nach Sicht (G4) | **sofort**, als eigener Punkt, unabhängig von O3+ |
| AM0-E1b/d | Werkstatt und Betrieb trennen | **AM9 aufnehmen, mit G5** (Freigaben auf eigener Herkunft) |

**Entschieden vom Captain am 03.11.2026 (zweiter Schritt):** G9 (Bestätigung außerhalb des Browsers für Klasse H, Konsole als Ersatz), G10 (Kanal im Audit), G11 (Vollständigkeitstest der Freigabe-Wege) übernommen. Die Klasseneinteilung H/N aus §5b.3 (Unbekanntes = H) ist die Grundlage von G9 und gilt damit als mit übernommen; wenn der Captain sie einzeln ändern will, ist das in G2 von G9 möglich.

Nächster Schritt: G2 für G4 in `docs/SPEC_APPS_v1_G4_MODELLCODE_G2.md` (gebaut, Release 1.22.0). G2 für O3+ und G9–G11: `docs/SPEC_APPS_v1_O3PLUS_G9_G2.md` (03.11.2026, wartet auf Freigabe).
