# SEDRA Kommandodeck – UIX-Konzept v1 (14.10.2026)

Auftrag des Captains: klare Strukturen statt vieler kleiner Kacheln; der Weg von der Modellwahl über die Teststrecke bis zur Eingabe
und Ausführung soll sich anfühlen wie ein modernes Betriebssystem, in dem man nur eingibt, was man will, und das Modell einen dabei
unterstützt. Dazu eine Agentenumgebung nach dem Vorbild von Paperclip, sinnvoll in die Oberfläche eingebunden. Die Grundlagen und
Mechaniken (Gates, Audit, Routing, DevVM, Chat-Werkzeuge, Standardtest) sind da; dieses Papier ordnet sie neu an.

## 1. Vier Regeln

1. **Ein Eingabefeld.** Alles beginnt im *Kommando* („Was willst du tun?“): auf dem Deck und mit Strg+K aus jedem Fenster.
   Eine kurze Navigationsphrase öffnet den richtigen Ort („neues Modell“, „Besatzung“, „thema nacht“); eine Frage oder ein Auftrag
   geht an GUPPI, der mit seinen Umgebungswerkzeugen antwortet und von dort eine Karte plant. Ohne Modell endet nichts in einer
   Sackgasse: GUPPI sagt es und bietet den nächsten Schritt an.
2. **Drei Orte statt zehn Fenster.** *Deck* (was wartet, was läuft, wer an Bord ist), *Werkstatt* (Modell → Teststrecke → bereit),
   *Besatzung* (Organigramm, Rollen, Agenten). Hardware, Maschinenraum, Logbuch, Entwicklungsumgebung bleiben erreichbar, aber als
   Nebenräume über Deck, Startmenü und Kommando – nicht als Knopfreihe in jedem Fenster.
3. **Verben statt Substantive auf Knöpfen, und nur die des eigenen Fensters.** Eine Werkzeugleiste trägt, was man *in diesem
   Fenster tun* kann („Neuer Chat“, „Teststrecke“, „Aktualisieren“). Navigation läuft über Deck, Taskleiste, Startmenü. Prüfbar:
   `test_deck_is_wired_and_toolbars_hold_only_their_own_verbs`.
4. **Zustand als Satz, nicht als Zahl.** Das Deck beginnt mit einem Satz („SEDRA ist READY. Qwen läuft mit Kontext 16384.
   Eine Freigabe wartet auf dich.“) und jede Stufe der Werkstatt-Leiste sagt in einem Satz, woran es hängt, mit genau einer Aktion.

## 2. Was in Build 5 umgesetzt ist

| Baustein | Datei | Was es tut |
| --- | --- | --- |
| Deck | `uix/js/deck.js`, Fenster `#deckWindow` | Startfenster. Satz, Kommando-Feld, Vorschlags-Chips aus dem Zustand, drei Spalten: *Wartet auf dich* (Karten mit Gates, Vorschläge aus dem Chat), *In Arbeit* (laufende Karten, zuletzt fertige), *Besatzung und Maschine* (Modell, Kombination, Agenten, Token heute, Entwicklungsumgebung, Runtime, Projekte). Jede Zeile öffnet das Fenster, in dem die Aktion liegt. Aktualisiert alle 5 s, nie unter der Hand beim Tippen. |
| Kommando | `uix/js/command.js`, Palette `#palette` | `routeCommand(text)` (rein, mit node geprüft): `/…` → Chat; Frage- oder Auftragswort → Chat (Auftrag mit Angebot „Als Karte planen“); ≤ 4 Wörter mit Treffer in der Befehlstabelle → Fenster. Palette mit Strg+K: Pfeile, Enter, Esc; bei Navigationsphrasen stehen die Fenster oben, sonst „An GUPPI senden“. |
| Werkstatt-Leiste | `uix/js/workbench.js`, oben im Modelle-Fenster | `workbenchModel()` (rein): 1 Modell (geladen / einrichten / laden / Schalter aus / **Schalter an, gilt erst nach Neustart** – der Fall aus dem Screenshot vom 14.10.), 2 Teststrecke (Kurztest, Standardtest, Ergebnis mit empfohlenem Kontext), 3 Bereit. Je Stufe eine Aktion. Die Abschnitte darunter bleiben; die Leiste springt dorthin (`openModelsAt`). |
| Organigramm | `uix/js/org.js`, erster Reiter der Besatzung | Captain (Freigaben) → GUPPI (Modell, Kontext, Karten in Arbeit) → Rollen aus den aktiven Rezepten (Modell geladen / nicht geladen / kein Modell; Agenten mit dieser Rolle). Budgetzeile aus dem Guppy-Meter. Rein lesend. |
| Erscheinungsbild | `uix/js/theme.js`, Tokens in `desktop.css` | Die geplante GUPPI-Funktion „Desktop wechseln/anpassen“ (Manifest 8): *Retro*, *Klar* (hell, flach, runde Ecken), *Nacht* (dunkel, passt zum Hardware-Fenster). 25 neue Flächen-Tokens (`--sky-*`, `--title-*`, `--bar-*`, `--start-*`, `--menu-*`, `--window-line`, `--window-radius`, `--font` …), Umschalten im Startmenü oder per Kommando („thema nacht“), gemerkt im Browser. Ein Theme setzt nur bekannte Token-Namen (Test). |
| Bibliothek | `uix_library.py`, `uix/js/library.js`, Fenster `#libraryWindow` | Captain 15:54: Skills ansehen und bearbeiten. Regale *Eigene* (editierbar, Gate + Sicherung + Flag-Prüfung; Ordner ist eine vollwertige Bibliothek mit `index.json` – `devvm_build.py --skills local_config/skill_library` kann sie dem Coder geben), *Core*/*Alle Domänen* (lesen, suchen, „Als Vorlage kopieren“), *SEDRA-Fähigkeiten* (`skill.yaml`, Vertrag der Runtime, nur lesen). Vorlage mit Kopf `name`/`description`; der Coder findet eigene Skills über die Beschreibung. |
| Aufräumen | `retro_desktop.html`, `main.js` | Werkzeugleisten auf eigene Verben reduziert; Taskleiste: Deck · GUPPI · Werkstatt · Besatzung · Projekte; Startmenü: Kommando, Deck, GUPPI, Neue Karte, Neues Projekt, Neues Modell, Chat-Verlauf, Nebenräume rechts, Erscheinungsbild unten. Das Inline-Script für die Icon-Verschiebung sitzt jetzt in `main.js` (Regel: Top-Level-Code nur dort; der Test `test_page_is_split_into_files…` war deshalb rot). |

## 3. Paperclip: Vorbild, nicht Einbau

Paperclip (paperclipai/paperclip, MIT, Node-Server mit React-UI und eingebettetem Postgres) ist ein Steuerpult für „Firmen aus
Agenten“: Organigramm mit Rollen und Berichtslinien, Ziele, Tickets, Heartbeats (Agenten wachen nach Plan auf und holen sich Arbeit),
Freigaben durch den Menschen als „Board“, Budgets je Agent mit Stopp am Limit, unveränderliches Audit; Adapter für Claude Code, Codex,
Cursor, HTTP-Bots u. a. ([README](https://github.com/paperclipai/paperclip)).

**Abbildung auf SEDRA (das meiste gibt es schon):**

| Paperclip | SEDRA heute | Oberfläche ab Build 5 |
| --- | --- | --- |
| Board / Approvals | Captain-Gates (`guard.create_gate`, Einmal-Token) | Deck-Spalte „Wartet auf dich“, Organigramm-Knoten Captain |
| Org chart, Rollen | Rollen des Routings (coder, planner, reviewer, tester …), Agent Manager (Templates, Instanzen, Zulassung) | Organigramm in der Besatzung |
| Goals / Issues | Projekte, Karten (Missionen) mit Phasen | Deck „In Arbeit“, Brücke |
| Heartbeats, Routines | Job-Supervisor; Nachtplan (geplant) | – (Nebenraum, später Deck-Zeile „Nächster Lauf“) |
| Budgets, Costs | Token-Richtlinie, Guppy-Meter (Kupfer/Silber/Gold) | Deck „Token heute“, Organigramm-Budgetzeile |
| Audit | Audit-Kette | Logbuch |
| Runtime-Adapter | llama-server lokal, DevVM; Claude über den Chat | – |

**Empfehlung: nativ nachbilden, nicht einbetten.** Gründe: (1) Ein zweites Steuerpult neben Guard, Audit und GPU-Sperre würde die
Autorität teilen – genau das, wovor die Konzeptprüfung (`concept_review/…/PRUEFBERICHT.md`: „kein zusätzlicher Supervisor“) warnt.
(2) Paperclip braucht Node 24 und Postgres auf dem Captain-PC; SEDRA ist bewusst ein Python-Paket mit einem Browserfenster.
(3) Die Freigaben müssen *vor* der Wirkung liegen; Paperclip kennt Approvals, aber nicht unsere Bindung an Inhalt und Ziel.
**Offen gehalten:** ein HTTP-Adapter, mit dem SEDRA in einer Paperclip-Firma als *ein* Agent erscheint (Heartbeat → Karte → Gate →
Ergebnis). Das ist sinnvoll, sobald der Captain mehrere Maschinen oder fremde Agenten unter einem Dach führen will; vorher nicht.

## 4. Die nächsten Scheiben (für GUPPI als Specs vorbereitet)

1. ~~Deck-Karten mit Seekarte~~ – Build 6.
2. ~~Freigabe direkt im Deck~~ – Build 6 (Token bleibt einmalig und inhaltsgebunden; Anträge werden einmal gezählt).
3. **Ein Chat**: `GUPPI` (Interface) und `Chat-Verlauf` (cchat) zusammenführen – Sitzungsliste links, Karten und Anhänge im Gespräch (Specs `chat_store`, `cchat`).
4. **Heartbeat-Zeile**: Nachtplan-Scheduler zeigt „Nächster Lauf 02:00 · 3 Specs“ im Deck; Paperclip-Begriff „Routine“ übernehmen.
5. **Rollen-Budgets**: Token-Richtlinie je Rolle (Guppy-Meter zählt heute global); dann steht im Organigramm „Coder: 12 k von 100 k heute“.
6. **Fenstervorlage** (Manifest 10): ein JS-Template für neue Fenster, damit Deck/Werkstatt/Besatzung dieselbe Kopfzeile, Leiste und Leerzustände haben.

## 5. Abnahme

`uix_check.py` 15/15 (jetzt mit Deck und Bibliothek); `test_uix_kommandodeck.py` 15 Tests (Router, Rangfolge, jeder Befehl hat einen Läufer, Werkstatt-Leiste inkl.
Neustart-Fall, Organigramm, Theme-Wörter, Verdrahtung, Token-Disziplin der Themes, Dateigrößen); Screenshots in `docs/shots/kommandodeck/`
(Deck, Palette, Werkstatt, Organigramm, Frage → GUPPI, Klar, Nacht). Volle Regression siehe `CHANGELOG.md` Build 5.

## 6. Schätzung „Neubau mit konsistentem Design“ (Captain 17:43)

Kompletter Neubau der Präsentationsschicht in derselben Technik: drei bis vier Bauabende (Builds) – (1) Fenstervorlage + Komponenten-Basisklassen + Tokens, Deck/Werkstatt/Besatzung/Bibliothek darauf; (2) ein Chat, „System“-Fenster mit Reitern (Projekt, Entwicklung, Maschinenraum, Logbuch), Hardware-Seite im selben Look; (3) Themes, Animationen, Abnahme auf dem PC. Empfohlen: Shell-Neubau mit Umzug Fenster für Fenster (jeder Build startfähig) statt grüner Wiese; GUPPIs Stücke (Münzloch, Chat-Verlauf, Meter, Standardtest) werden mitgenommen, nicht neu geschrieben.
