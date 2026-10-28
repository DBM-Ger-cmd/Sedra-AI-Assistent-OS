# SPEC Harness-Shell v1 – G1 Anforderungen (28.10.2026)

Stand: Zweig `spec/agenten-orchestrierung`, `f044f11`. Gate **G1** (Anforderungen); Design (G2) und Bau-Aufgaben (G3) folgen erst nach Freigabe.
Auftrag des Captains 28.10.2026: „Sedra Cockpit ist aktuell nicht zu gebrauchen … wir müssen mehr an das Look and Feel einer echten
Harness-Oberfläche wie Hermes, Bionic oder DeepSeek kommen“; „wir haben so viele Unterbau-Funktionen eingebettet, was das Frontend nicht
mehr mitmacht“. Referenzbilder: Bionic (Chat-Startseite, Einstellungen) und die Windows-Taskleiste („wichtig die Leiste unten für aktive
Anwendungen“). Skizze: zweite Fassung im Chat vom 28.10.2026 (Seitenleiste, Reiter, Gespräch, Eingabefeld, Taskleiste).

## 1. Befund

| Nr | Befund | Beleg |
|---|---|---|
| B1 | **Das Backend ist größer als die Oberfläche.** `uix_server.py` bietet 166 API-Wege, `uix/tools` hat 43 Werkzeuge (32 `object`, 10 `instrument`, 1 `panel`). Das Cockpit zeigt fast alles gleichzeitig: 8 Baumgruppen, Leiste mit bis zu 11 Zellen, Reiter, Palette, Mini-Hub. | `uix/shells/cockpit/`, SPEC_UIX_STUFE6 A1 |
| B2 | **Das Gespräch ist Beiwerk.** Der Master-Chat (`tools/entwurf`) sitzt fest unten; eine Antwort kommt erst ganz am Ende (kein Streamen), Werkzeugaufrufe sieht der Captain nicht. | ANALYSE_KETTE_EINGABE_AUSFUEHRUNG §1, §3 |
| B3 | **Das Modell kann nichts tun.** Die Werkzeuge in `chat_tools.py` lesen Zustand oder **bieten an** (`propose_action`, `open_place` …); ausgeführt wird nichts. Ein Auftrag wie „Logbuch-Eintrag schreiben“ ist im Gespräch nicht erledigbar. | ANALYSE_KETTE §3, Befund 2 |
| B4 | **Bekannte Fehler der Kette:** Plan ohne Ausführung gilt als Erfolg; das Modell darf dasselbe Werkzeug achtmal rufen; Stichwörter (`CHAT_MOVE_WORDS`) erzwingen ein Werkzeug, kleine Modelle antworten dann leer. | ANALYSE_KETTE Befunde 1, 4, 5 |
| B5 | **Kein Ort für Sitzungen.** Es gibt eine einzige Chat-Mission je Fenster; frühere Gespräche, Projekte und Vorlagen (z. B. „Vorarbeiter“) lassen sich nicht wählen. | `uix_server.chat_reply` |
| B6 | **Ein externer Vorarbeiter in Bionic ist keine Lösung:** Bionic (früher LM Studio) und llama-server teilen sich ~11,5 GB VRAM, das Hauptmodell belegt ~10,2 GB; der Bionic-Dienst hing am 12.10.2026. | `config/model_runtimes.yaml`, START_PROMPT_VORARBEITER_BIONIC |

Vorhanden und nutzbar: Streamen im Adapter (`models/openai_local._chat_streamed`), Ereignisstrom `/api/events` (SSE), Guard über
`control.execute`, Freigaben/Posteingang (`/api/decisions`), Werkzeugschleife `devenv/model_tools.run_tool_loop`, Rekorder, Shell-Vertrag (`shell.yaml`).

## 2. Ziel

Eine neue Shell **`harness`**: das Gespräch mit einem Agenten steht in der Mitte, der Agent arbeitet sichtbar mit Werkzeugen, jede
Handlung mit Folgen geht über eine Freigabe-Karte im Verlauf. Alles andere aus dem Unterbau ist **nicht dauernd sichtbar**, sondern als
App im Start-Menü, als Befehl oder in den Einstellungen erreichbar. Unten zeigt eine Taskleiste, was gerade offen ist oder läuft.

Nicht Ziel: das Backend umbauen, das Cockpit löschen, eine Kopie von Bionic. Übernommen wird das Bedienmuster, nicht Code oder Gestaltung.

## 3. Anforderungen

### 3.1 Aufbau (Bildschirm)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-01 | Die Shell hat genau fünf Zonen: **Seitenleiste** (links), **Reiterleiste** (oben), **Arbeitsfläche** (Mitte), **Eingabefeld** (unter der Arbeitsfläche, im Gesprächsreiter), **Taskleiste** (unten, volle Breite). Keine Instrumentenleiste oben, kein Baum, kein schwebender Mini-Hub. | uix_check: Zonen-Marken vorhanden, verbotene Marken fehlen |
| HS-02 | **Seitenleiste:** oben „Neue Sitzung“; Gruppe **Projekte** (je Projekt seine Sitzungen, aufklappbar); Gruppe **Chats** (Sitzungen ohne Projekt); unten **Einstellungen**. Mit Strg+B ein-/ausblendbar. | Test der Shell |
| HS-03 | **Reiter:** Ein Reiter ist eine Sitzung oder eine geöffnete App/Datei. „+“ öffnet einen neuen Sitzungsreiter. Mittlere Maustaste schließt. Reiter merken sich ihre Reihenfolge je Browser. | Test der Shell |
| HS-04 | **Leere Sitzung:** Figur SEDRA (Seedrache) mittig, darunter das Eingabefeld groß, darunter die Projektwahl. Nach der ersten Nachricht rückt das Eingabefeld nach unten. | Bildvergleich |
| HS-05 | Mindestgröße 1024×700 ohne waagerechtes Rollen und ohne abgeschnittene Werte; unter 1100 px Breite klappt die Seitenleiste von selbst zu. | uix_check bei 1024×700 und 1400×860 |

### 3.2 Gespräch

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-10 | **Streamen:** Die Antwort erscheint Wort für Wort, über einen neuen Endpunkt (SSE) der Sitzung. Der Inhaltsschutz (`content_guard`) gilt weiter; hält er etwas zurück, steht im Verlauf der Grund statt Text. | Test mit Attrappe des Modells |
| HS-11 | **Werkzeugaufrufe sichtbar:** Jeder Aufruf steht als eigene Zeile im Verlauf (Name, Kurzfassung der Eingabe, Dauer, Zustand läuft/ok/Fehler), aufklappbar zu vollständiger Eingabe und Ausgabe (gekürzt ab 4000 Zeichen, mit „ganz anzeigen“). | Test |
| HS-12 | **Denken einklappbar:** Liefert das Modell Denktext (`reasoning`), steht er als eingeklappte Zeile „Denkt nach · n s“. Standard: eingeklappt. | Test |
| HS-13 | **Stopp:** Ein Stopp-Knopf (und Esc) bricht die laufende Antwort und die Werkzeugschleife ab; der Verlauf zeigt „abgebrochen“. | Test |
| HS-14 | **Wiederholung erkennen (B4/4):** Ruft das Modell dasselbe Werkzeug mit denselben Argumenten zum zweiten Mal hintereinander, bekommt es statt des Ergebnisses einen Hinweis; beim dritten Mal endet die Schleife mit einer Antwort ohne Werkzeuge. | Einheitstest der Schleife |
| HS-15 | **Kein Zwang durch Stichwörter (B4/5):** In der Harness-Shell wird `tool_choice=required` nicht über Stichwörter gesetzt. | Einheitstest |
| HS-16 | **Ehrliches Ende (B4/1):** Eine Sitzung meldet „erledigt“ nur, wenn eine Handlung ausgeführt und geprüft wurde; ein reiner Plan heißt „nur Plan“. | Test |
| HS-17 | **Eingabefeld:** mehrzeilig (Enter sendet, Umschalt+Enter Zeilenumbruch); „+“ für Dateien aus dem Projekt; **Schild** zeigt und wechselt den Freigabe-Modus (HS-31); **Modellwahl** (Rezept, Slots, Kontextgröße; geprüfte schnelle Modelle oben wie S6-E2); **Mikrofon** = vorhandener Rekorder; `/` öffnet Befehle, `@` Dateien. | Test |
| HS-18 | **Sitzungen bleiben:** Jede Sitzung wird gespeichert (Verlauf, Werkzeugaufrufe, Modell, Projekt, Vorlage) unter `runtime_data/harness/sitzungen/`, eine Datei je Sitzung (JSONL). Nach Neustart ist alles wieder da. Löschen einer Sitzung nur mit Rückfrage im Feld (wie S6-E2 „Leeren“). | Test |
| HS-19 | **Vorlagen:** Eine Sitzung kann aus einer Vorlage starten (Systemprompt, erlaubte Werkzeuge, Modell). Erste Vorlage: **Vorarbeiter** (Inhalt aus `START_PROMPT_VORARBEITER_BIONIC.md`, ohne die Bionic-Hinweise). Vorlagen liegen als Dateien im Projekt. | Test |

### 3.3 Werkzeuge und Freigaben

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-20 | **Neue Werkzeuge mit Wirkung** für den Agenten, alle über `control.execute` und den Guard: `datei_lesen` (abschnittsweise), `suchen` (Text im Projekt), `dateien_auflisten`, `befehl` (nur aus einer festen Liste, HS-E2), `datei_schreiben` / `datei_aendern` (nur im Schreibbereich), `lauf_starten` / `lauf_stoppen` (vorhandene Läufe, z. B. `nachtlauf_3d`, `run_tests`). Die bisherigen `chat_tools` bleiben zusätzlich nutzbar. | Einheitstests je Werkzeug |
| HS-21 | **Lesen ist frei, Wirkung braucht Freigabe:** `datei_lesen`, `suchen`, `dateien_auflisten` und Befehle der Klasse „lesen“ laufen ohne Rückfrage. Alles andere erzeugt eine **Freigabe-Karte im Verlauf** und wartet. | Test |
| HS-22 | **Freigabe-Karte:** Werkzeug, Ziel (Datei/Befehl), bei Schreiben ein Diff, bei Befehlen die genaue Zeile; Knöpfe „Erlauben“, „Diff zeigen“, „Ablehnen“. Die Entscheidung erzeugt dasselbe Audit wie der Posteingang (Regel 2 des Cockpits); dieselbe Freigabe steht auch im Posteingang. | Test, Audit-Zeile |
| HS-23 | **Grenzen:** Schreiben nie außerhalb des Projekt-Schreibbereichs, nie in `local_config/`, nie Harness-Code (Guard, Bridge, Suite, Bauskripte), nie Löschen. Das prüft der Guard, nicht die Oberfläche. | Guard-Tests |
| HS-24 | Werkzeugergebnisse sind **Daten**: Text aus Dateien, Logs oder Webseiten wird dem Modell als Ergebnis gegeben, nie als Anweisung des Captains. | Prompt-Test |

### 3.4 Taskleiste

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-30 | **Links „Start“:** öffnet das Start-Menü (HS-40). | Test |
| HS-31 | **Mitte – aktive Anwendungen:** jede offene Sitzung, App und jeder **laufende Lauf** als Knopf mit Symbol und Namen; aktive unterstrichen, laufende mit Fortschritt (z. B. „3D-Lauf 42 %“) oder Zeit. Ein Klick holt den Reiter nach vorn; ein Lauf ohne Reiter öffnet seine Ansicht. | Test |
| HS-32 | **Rechts – Statusbereich (ersetzt die Instrumentenleiste):** offene Freigaben (Zahl, Klick öffnet Posteingang), GPU-Temperatur und VRAM, freier RAM, Modellserver bereit/aus, Uhrzeit. Ein Wert mit Ton `warn`/`bad` färbt sich; Hinweis im `title`. Daten aus `/api/strip` bzw. `/api/events`, keine neue Messung. | Test |
| HS-33 | Benachrichtigung: Endet ein Lauf oder wartet eine Freigabe, blinkt der Knopf einmal und bleibt markiert, bis er angeklickt wird. | Test |

### 3.5 Start-Menü und Einstellungen (wohin der Unterbau geht)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-40 | **Start-Menü:** alle Werkzeuge vom Typ `object`/`panel` als Apps mit Suche, gruppiert (Arbeit, Modelle, Wissen, System, Prüfung); zuletzt benutzte oben. Eine App öffnet als Reiter. Werkzeuge mit `zweck: pruefung` nur mit Schalter `entwicklung` (wie S6-E4). | Test |
| HS-41 | **Andere Oberflächen** (Cockpit, KI-GateWay, Wissensbasis …) sind Einträge im Start-Menü; der Wechsel ersetzt hier den Mini-Hub. | Test |
| HS-42 | **Einstellungen** als eigene Seite mit Navigation links, gruppiert: *Allgemein* (Sprache, Darstellung, Benachrichtigungen) · *Agent* (Vorlagen, Freigabe-Modus, Grenzen der Schleife) · *Sprache* (Rekorder, Quelle) · *Integrationen* (MCP, KI-GateWay, Cloud) · *Lokale Modelle* (Bibliothek, Rezepte, Slots, geladene Instanzen, Laufzeit) · *System* (Guard, Schalter, Modus und Grenzen, Audit). Jede Seite nutzt die vorhandenen API-Wege; Änderungen an `local_config/` nur mit Freigabe des Captains. | Test je Seite |
| HS-43 | **Instrumente** (`kind: instrument`) erscheinen nicht als Leiste, sondern nur im Statusbereich (HS-32) oder auf ihrer Einstellungsseite. | uix_check |

### 3.6 Betrieb

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| HS-50 | Die Shell nutzt nur den vorhandenen Modellserver (llama-server, Port 8080); kein zweiter Modellprozess, kein Bionic. | Test, Konfiguration |
| HS-51 | `START_SEDRA harness` startet sie; das Cockpit bleibt unverändert erreichbar (`START_SEDRA cockpit`, Start-Menü). | Startprobe |
| HS-52 | Antwortzeit der Oberfläche: erstes Wort spätestens 1 s nach dem ersten Token des Modells; Taskleiste frischt höchstens alle 2 s auf. | Messung |
| HS-53 | Ohne geladenes Modell zeigt das Eingabefeld „Kein Modell geladen – Modell wählen“, statt still zu scheitern. | Test |

## 4. Abgrenzung

- Kein Umbau der 166 API-Wege; neue Wege nur für Sitzungen, Streamen und die Werkzeuge aus HS-20.
- Kein Löschen von Shells oder Werkzeugen. Das Cockpit wird nicht weiter ausgebaut, bis G4 dieser Spec durch ist.
- Cloud-Modelle: dieselbe Oberfläche, aber nur über die Regeln aus Spec 3 (Entscheidung je Lauf) – hier nicht neu geregelt.
- Mehrere Agenten gleichzeitig in einer Sitzung: nicht v1.

## 5. Fragen an den Captain (Entscheidungen für G1)

| Nr | Frage | Vorschlag |
|---|---|---|
| HS-E1 | Neue Shell neben dem Cockpit oder Cockpit ersetzen? | **Neben** dem Cockpit; Standard bei `START_SEDRA` wird `harness` erst nach Abnahme. |
| HS-E2 | Werkzeug `befehl`: feste Liste oder jeder Befehl mit Einzelfreigabe? | **Feste Liste** (z. B. `git status/log/diff`, `run_tests`, `nvidia-smi`, `spec_check`, Trockenläufe); Liste in `local_config/harness_befehle.yaml`, Änderung nur durch den Captain. Alles außerhalb der Liste ist nicht möglich. |
| HS-E3 | Freigabe für Schreiben: jedes Mal oder „für diese Sitzung erlauben“? | Drei Modi am Schild: **fragt** (Standard, jedes Mal), **Sitzung** (Schreiben im Schreibbereich für diese Sitzung frei, Läufe weiter einzeln), **nur lesen**. |
| HS-E4 | Vorarbeiter als erste Vorlage? | **Ja**, als Vorlage im Projekt; er bekommt Lesen frei, Logbuch-Schreiben mit Freigabe, keine Läufe ohne Ja. |
| HS-E5 | Wer baut was (Linie L4)? | Claude: Shell, Integration, Endpunkte, Guard-Anbindung. SEDRA (Bau-Specs): reine Module – Sitzungsspeicher (JSONL lesen/schreiben/kürzen), Wiederholungserkennung (HS-14), Prüfer der Befehlsliste (HS-E2), Diff-Kurzfassung für die Freigabe-Karte. |
| HS-E6 | Reihenfolge der Stufen? | 1 Gespräch mit Streamen, Sitzungen, Taskleiste (nur Sitzungen) · 2 Werkzeuge Lesen + Freigabe-Karte + Schreiben · 3 Start-Menü und Statusbereich · 4 Einstellungen · 5 Läufe in der Taskleiste, Vorlage Vorarbeiter. Jede Stufe einzeln abgenommen. |

## 6. Nächste Gates

- **G1** (diese Datei): Captain entscheidet HS-E1 bis HS-E6 und gibt die Anforderungen frei oder ändert sie.
- **G2** Design: Endpunkte (Sitzung, SSE-Strom, Werkzeuge), Datenformat der Sitzung, Ereignisse, Aufteilung in Dateien der Shell.
- **G3** Bau-Aufgaben je Stufe, mit versteckten Tests für die SEDRA-Module (höchstens 20 Prüfungen je Stufe, L3).
- **G4** Übernahme je Stufe nach Review.
