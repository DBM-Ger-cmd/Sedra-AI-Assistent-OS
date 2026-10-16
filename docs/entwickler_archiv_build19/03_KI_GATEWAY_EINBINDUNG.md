# 03 – Das KI GateWay in SEDRA: Herkunft, Einbindung, Betrieb

Dieses Dokument ist für Entwickler gedacht, die das KI GateWay verstehen, prüfen, erweitern oder in einen anderen Anwendungsfall übertragen müssen.

## 1. Was das KI GateWay ist

Das KI GateWay prüft, **bevor** Text an ein Modell geht, was darin steckt, und entscheidet, ob und wohin er gehen darf. Der Ablauf ist ein **Vorgang** mit vier Stationen: Der Nutzer wählt den Weg (lokal oder Cloud), gibt eine Anfrage und optional eine Textdatei ein, bekommt eine Empfehlung mit Freigabe und sieht am Ende einen Entwurf, den ein Mensch prüft. **Es gibt keinen Versand.** Das GateWay schreibt nichts nach außen.

Das Modul heißt in der Oberfläche **KI GateWay**. Die Texte sprechen vom „Assistenten“, nicht von SEDRA. Intern heißen Paket und Werkzeug noch `sedra_gateway` bzw. `schutz`; das sieht der Nutzer nicht.

## 2. Herkunft: Drei Quellen, eine Einbindung

| Quelle | Was daraus wurde | Wo im Paket |
|---|---|---|
| **B6-KI-Gateway** (Projektakte V4: Entscheidungsregister, Aufgabenregister, Übergabe v1.1, offene Fragen) | die fachlichen Regeln: 13 Merkmale, Schutzklassen SK0–SK3, Matrix, drei Rechecks, Löschfristen | `gateway/klassen.py`, `gateway/vorgang.py`, `core/b6core/` (sieben Dateien, mit `HERKUNFT.sha256`) |
| **Lieferung 0.3.0** eines anderen Chats (Paket `sedra_gateway`, 88 Tests, plus zwei Werkzeuge `gateway` und `schutz`) | die Werkzeuge, die Oberfläche, der Studio Flow; das Paket selbst wurde **nicht** übernommen | `uix/tools/gateway/`, `uix/tools/schutz/` (Build 15 und 19) |
| **Studio Flow v1.1** (Klickvorschau der Oberfläche) | die vier Stationen und die Gestaltung | `uix/tools/gateway/`, `uix/shells/gateway-studio/` |

Die Abnahme der Lieferung ist in `ABNAHME_EXTERNE_LIEFERUNG_KI_GATEWAY_2026-10-15.md` im Projekt dokumentiert. Die Vertragsbefunde V1 (eigene Objekttypen) und V2 (Vertrauen aus der Datei des Fremden) sind dort beschrieben und in Build 15 geschlossen.

**Umsetzung:** Das GateWay ist auf den SEDRA-Kern gesetzt und nicht als eigener Stapel gebaut (Begründung und Gegenüberstellung in `06_ENTSCHEIDUNGEN_UND_OFFENES.md`).

## 3. Die Einbaustellen im Kern und in den Schichten

Das GateWay berührt SEDRA an fünf Stellen. Jede ist in einem Test festgehalten.

| Stelle | Datei | Was dort geschieht |
|---|---|---|
| 1. Modellaufruf | `models/router.py` (`ModelRouter.chat`) | Jeder Aufruf durchläuft den Inhaltsschutz (`ContentGuard`, Build 16). Das GateWay nutzt denselben Weg. |
| 2. Schutzklassen | `gateway/klassen.py` | Merkmale aus den Scan-Ergebnissen, Klasse, Matrix |
| 3. Vorgang | `gateway/vorgang.py` (`GateWay`, `Vorgang`, `Entwurf`) | Zustände, Ablage, Bindung, Ausführung, Prüfung |
| 4. Hub | `uix_server.py` (`UIXHub`, Methoden `gateway_*`) und `desk/gateway.py`, `desk/decisions.py` | Routen, Gate, Entscheidung |
| 5. Oberfläche | `uix/tools/gateway/`, `uix/tools/schutz/`, `uix/shells/gateway-studio/` | Werkzeuge und Shell; Objekttyp `gateway` in `OBJECT_TYPES`, Ort in der Ortskunde, Starttyp in der Vorgabe |

## 4. Die Merkmale und die Schutzklassen

Die 13 Merkmale stammen aus den B6-Regeln. Die Zuordnung steht in `gateway/klassen.py` (`MERKMALE`):

| Merkmal | Bedeutung | Klasse |
|---|---|---|
| P01 | Personenbezug (Name, E-Mail, Telefon, Kundennummer) | SK1 |
| P02 | Besondere Kategorien (Gesundheit, Religion, Weltanschauung) | SK3 |
| P03 | Strafsachen | SK3 |
| P04 | Amtliche Kennungen (Steuer-ID, Ausweis, Sozialversicherung) | SK3 |
| F01 | Bankverbindung | SK2 |
| F02 | Kartendaten | SK2 |
| F03 | Kartendaten mit Prüfwert | **Hard Block** |
| S01 | Zugangsdaten, Schlüssel, Passwörter | **Hard Block** |
| S02 | Anweisungen an die KI, versteckte Steuerzeichen | **Hard Block** im Dokument; Review in der Anfrage |
| G01 | Kalkulation, Geschäftsgeheimnis | SK3 |
| G02 | Vertraulichkeitsvereinbarung (NDA) | SK2 |
| R01 | Rechtsstreit, laufendes Verfahren | SK2; **nicht automatisch erkennbar**, der Captain setzt es von Hand (`MANUELL`) |
| V01 | Minderjährige | SK3 |

**Schutzklasse** ist die höchste Klasse aller getroffenen Merkmale. Kein Merkmal heißt SK0. Wer eine Zuordnung ändern will (etwa die Benennung von R01 oder die Einordnung von F01/F02), ändert die Tabelle und den zugehörigen Test, nicht die Logik.

### Die Matrix (deterministisch, Fail-Safe)

| Klasse oder Fund | erlaubte Wege | Policy-Status | Review |
|---|---|---|---|
| Hard Block (S01, F03, S02 im Dokument) | keiner | `BLOCKED` | – (nicht übersteuerbar) |
| UNCLASSIFIED (Scan unvollständig, Datei nicht lesbar) | keiner bis zur Prüfung | `HUMAN_REVIEW_REQUIRED` | PENDING |
| SK3 | nur lokal | `HUMAN_REVIEW_REQUIRED` | PENDING |
| SK2 | nur lokal | `AUTO_APPROVED` | NOT_REQUIRED |
| SK1 | lokal oder Cloud nach Pseudonymisierung (simuliert) | `AUTO_APPROVED` | NOT_REQUIRED |
| SK0 | lokal oder Cloud (simuliert) | `AUTO_APPROVED` | NOT_REQUIRED |

Drei Grundregeln aus der Akte (K-03, K-04):

- Der Wunsch des Nutzers (lokal oder Cloud) darf **nur restriktiver** sein als die Policy erlaubt. Die Freigabe bietet nur die erlaubten Wege an.
- **Route, Policy-Status und Review sind getrennt.** Eine Freigabe „automatisch erlaubt“ heißt nicht „ohne Prüfung“, und „kein Treffer“ heißt nicht „unbedenklich“. Die Oberfläche sagt das ausdrücklich.
- Ein unvollständiger Scan führt zu UNCLASSIFIED und damit zur Prüfung.

Die Tests dazu: `test_gateway` (21 Tests), u. a. je ein Test für SK0, SK1, SK2, SK3, Hard Block und unvollständigen Scan.

## 5. Der Vorgang: Zustände und Ablauf

`gateway/vorgang.py` führt den Vorgang. Die Methoden in der Reihenfolge des Ablaufs:

| Schritt | Methode | Hub-Route | Was passiert |
|---|---|---|---|
| Neu | `neu(titel, wunsch)` | `POST /api/gateway/neu` | Vorgang mit Zustand NEU; Wunsch lokal oder Cloud |
| Prüfen | `pruefen(vid, anfrage, dokument, manuell)` | `POST /api/gateway/pruefen` | Liest die Datei aus dem Projekt (nur unterhalb des Arbeitsordners, nur `.md`/`.txt`), scannt, stuft ein, pseudonymisiert, baut den Übergabeprompt mit Platzhaltern (Recheck 1). Zustand GEPRUEFT oder GESPERRT. |
| Bindung | `bindung(vid, weg)` | intern | Hash über Anfrage, Dokument, Policy-Version, Klasse, Merkmale, Weg und Übergabeprompt |
| Freigabe | Hub `gateway_freigabe` | `POST /api/gateway/freigabe` | Legt ein Gate an (Aktion `gateway_release`) mit der Bindung; Entscheidungsart `request:gateway`; Zustand WARTET |
| Ausführen | `ausfuehren(vid, weg, binding, complete_local)` | `POST /api/gateway/apply` | Nur im Zustand WARTET und mit unveränderter Bindung. Lokal: `complete_local` ruft den Router, also den Inhaltsschutz. Cloud: Simulation. Rechecks 2 und 3. Zustand ENTWURF, oder FEHLER. |
| Prüfung (R2) | `pruefung(vid, urteil)` | `POST /api/gateway/pruefung` | Der Captain markiert den Entwurf als „geprüft“ oder „verworfen“. Zustand ABGESCHLOSSEN oder VERWORFEN. |
| Verwerfen | `verwerfen(vid)` | `POST /api/gateway/verwerfen` | Löscht Zuordnung und Entwurf, Zustand VERWORFEN |

Lehnt der Captain die Freigabe ab, kehrt der Vorgang zu GEPRUEFT zurück (Test `test_rejecting_the_gate_returns_the_case_to_checked`).

Lesend: `GET /api/gateway/vorgaenge` (Liste, Vorgaben, Textdateien des Projekts), `GET /api/gateway/vorgang` (ein Vorgang mit Entwurf).

### Die Bindung ist die Sicherung

Die Freigabe gilt **nur für genau diesen Stand**. Ändert sich die Anfrage, das Dokument, der Weg oder der Übergabeprompt, passt der Hash nicht mehr und die Freigabe ist hinfällig (`bindung_wartend`). Test: `test_the_binding_dies_with_every_change`.

### Die Platzhalter und die Zuordnung

- Personen, Kennungen und Konten werden durch typisierte Platzhalter ersetzt (`<PERSON_001>` und so weiter). Die Zuordnung (Platzhalter → Original) liegt **nur im Speicher des Prozesses** (`_vaults`, `PseudoVault` aus `b6core.pseudo`). Sie wird nach der Rückübersetzung gelöscht, ebenso bei Abbruch und Fehler. Nichts davon landet auf der Platte.
- Der Entwurf wird **nach** dem Modell zurückübersetzt. Drei Rechecks: nach der Pseudonymisierung, nach der Modellantwort vor der Rückübersetzung, nach der Rückübersetzung.
- Schlägt ein Recheck fehl, geht der Vorgang in den Zustand FEHLER: die Zuordnung wird gelöscht, es entsteht kein Entwurf, und es gibt keine automatische Wiederholung. Enthält der Entwurf nach der Rückübersetzung einen Hard-Block-Fund (S01, F03), wird er zurückgehalten (`entwurf_zurueckgehalten`).

### Der lokale Aufruf läuft durch den Schutz

`gateway_apply` im Hub baut die Funktion `complete_local(messages)`, die `ModelRouter.chat` aufruft. Damit gilt für den GateWay-Entwurf dieselbe Prüfung wie für jeden anderen Modellaufruf. Ein Treffer, der eine Entscheidung braucht, erscheint in der einen Entscheidungsliste; im GateWay selbst gibt es keinen zweiten Prüfweg.

## 6. Die Freigabe: Gate und Entscheidung

Die Freigabe läuft über die **eine** Entscheidungsliste von SEDRA:

- `gateway_freigabe` legt eine Mission an, ein Gate mit der Aktion `gateway_release` und der Bindung als `request_binding`, und eine Entscheidung der Art `request:gateway`.
- `desk/decisions.py` ordnet der Art `gateway` die Route `/api/gateway/apply` zu (`APPLY`) und den Titel „GateWay-Vorgang freigeben“. Ablehnen führt zu `gw.abgelehnt`.
- Der Titel nennt Weg, Schutzklasse, Merkmale und Policy-Status, zum Beispiel: „Vorgang … freigeben: nur lokal · SK1 Intern · P01 · Automatisch erlaubt“.
- Bei `HUMAN_REVIEW_REQUIRED` steht im Gate der Satz, dass die Prüfung die Freigabe ist.

Die Freigabe gilt also nur einmal und nur für die gebundene Fassung.

## 7. Der Inhaltsschutz (Build 16) in Kürze

Der Inhaltsschutz ist der Teil, der **jeden** Modellaufruf schützt, nicht nur das GateWay.

- **Gruppen** fassen die Scan-Treffer zusammen. Ein Treffer in einer Gruppe, die den Rechner verlassen würde, ist immer scharf.
- **Modi:** Sandbox ist scharf; Beobachten, Vertraut und unbestätigt beobachten nur protokollieren. Die Schärfe kommt aus dem Modus des Projekts.
- **Entscheidung:** Ein Treffer, der eine Entscheidung braucht, erscheint in der Entscheidungsliste (`kind: content`) mit den Wegen *einmal* (zehn Minuten, genau dieser Aufruf) und *ablehnen*.
- **Audit:** Ereignisse `SG_MODEL_CALL`, `SG_OUTPUT_OK`, `SG_BLOCKED`, `SG_DECISION_PENDING`, `SG_ONCE_GRANTED`, `SG_ONCE_USED`, `SG_DECISION_REJECTED`, `SG_STOPPED`, `SG_MODE_SET`. Sie enthalten Hashes, Regeln und Zählungen, **nie Text**.
- **Status** für das Werkzeug `schutz`: `GET /api/guard/status` liefert Gruppen, Zählungen, letzte Ereignisse und Schärfe, ohne Text. `POST /api/guard/probe` zeigt, was der Schutz täte, ohne Modell und ohne Speicher.

## 8. Die Oberfläche

| Teil | Was der Nutzer sieht |
|---|---|
| **Werkzeug `gateway`** (CORE) | Die vier Stationen: 01 Wunsch (lokal oder Cloud, nur ein Wunsch) · 02 Anfrage und Datei, „Datenschutz prüfen“, links das Original mit Markierungen, rechts der Übergabeprompt mit Platzhaltern, Legende und dem Satz „Die Zuordnung bleibt lokal“ · 03 Empfehlung mit Klasse, Merkmalen, erlaubten Wegen und Review; Freigabeknöpfe nur für erlaubte Wege; `BLOCKED` ohne Knopf · 04 Entwurf mit Weg, Modell, Rechecks und Löschdatum, „Geprüft“ oder „Verwerfen“ |
| **Werkzeug `schutz`** (CORE) | Nachweis neben dem Werkstück: Gruppen, Schärfe, Zählungen, letzte Ereignisse, „Selbst ausprobieren“ |
| **Shell „KI GateWay Studio“** | Eine Shell aus Vorgabe (`shell.vorgabe.yaml`): Das GateWay ist die Bühne. Orte und Leiste sind am Rand verborgen (`einblenden: rand`) und fahren beim Anfahren des linken bzw. oberen Randes heraus. Start im GateWay. |

Der Studio Flow ist ein Vertragswerkzeug: vanilla JS, nur `ctx.api`, Farben nur über Token, Selektoren mit `.t-gateway`.

## 9. Was bewusst nicht drin ist (MVP 1)

- **Kein echter Cloudweg.** `CLOUDS = ('simuliert',)`. Ein echter Adapter wäre Build S6, hinter der Netzgrenze, mit eigenem Beschluss (KLA-O6).
- **Keine Anhänge außer `.md` und `.txt`.** PDF und DOCX sind MVP 2.
- **Keine Rollen und Berechtigungen.** Der Captain ist der Review.
- **Kein MCP und keine Agenten** (Option A der Akte: nur dokumentiert).
- **Der Bestandsablauf der 0.3.0** (Dateien → Einheiten → Stichprobe, Vorgaben als Datei, Tresor über den Prozess hinaus) ist nicht im Paket; er bleibt als Option für MVP 2.
- **Keine Produkt-Aufbewahrungspolicy.** Die Löschfrist 23.10.2026 (`entwuerfe_loeschen_am` in `local_config/gateway/vorgaben.yaml`) ist der Testwert aus dem synthetischen MVP-Test, Uhrzeit Ende des Tages. Entwürfe liegen getrennt unter `local_config/gateway/entwuerfe/`; beim Start und bei jedem Blick werden abgelaufene gelöscht (Audit `GW_ENTWURF_GELOESCHT`).

Jeder dieser Punkte steht als Satz im Werkzeug unter „Was dieses MVP nicht tut“, damit ihn ein Nutzer nicht erst vermisst.

## 10. Ablage und Dateien

| Pfad (unter dem Projektordner) | Inhalt |
|---|---|
| `local_config/gateway/vorgaenge/<id>.json` | Vorgang ohne Entwurfstext: Zustand, Klasse, Merkmale, Bindung, Weg, Gründe |
| `local_config/gateway/entwuerfe/<id>.json` | Entwurf, getrennt, mit `loeschen_am` |
| `local_config/gateway/vorgaben.yaml` | Löschfrist, Cloudmodus, Hinweis |
| im Speicher des Prozesses | Zuordnung Platzhalter → Original (`_vaults`), nie auf der Platte |

Gesperrte Vorgänge (Hard Block) speichern **keinen Text**, nur Hashes und Gründe.

## 11. Tests und Abnahme

| Test | Anzahl | Was er prüft |
|---|---|---|
| `test_gateway` | 21 | Matrix (z. B. `test_sk3_needs_the_captain_even_locally`, `test_hard_blocks_have_no_way_and_no_override`), Bindung (`test_the_binding_dies_with_every_change`), Cloud-Simulation und Rückübersetzung, Löschfrist (`test_drafts_die_at_the_end_date_f04`), ganzer Weg (`test_the_whole_way`) |
| `test_content_guard` | 27 | ein Test je Zusage des Inhaltsschutzes (S1 bis S5) |
| `test_model_structured` | 10 | Schema-Zwang, Fehlersätze, Wiederholung |
| `test_desk_gateway` | – | Objekttyp `gateway`, eigene Typen für Fremdwerkzeuge (V1), Vertrauen (V2) |
| `test_uix_frame` | 16 | der Rahmen, Zonen, Schublade, Rand |
| Klick-Test | – | Studio Flow: prüfen, freigeben, Antwort, geprüft |
| `uix_check` | – | `--tool gateway`, `--tool schutz`, Shell `gateway-studio` (29/29) |

Die Suite umfasst 2072 Tests. Bekannt ist ein Umgebungsfehler (`library_not_built`), der nur auf Systemen ohne gebaute Bibliothek auftritt.

## 12. Wie man einen zweiten Anwendungsfall darauf setzt

Das ist der Zweck des Kerns. Ein neuer Anwendungsfall braucht in der Regel **keine** Änderung am Schutz:

1. **Modellaufrufe** laufen über `ModelRouter.chat`. Der Schutz greift automatisch, ein Aufruf am Router vorbei ist nicht zulässig.
2. **Eigene Fachregeln** kommen in ein Modul wie `gateway/klassen.py`: Merkmale, Klassen, Matrix, mit je einem Test pro Zeile.
3. **Ein Vorgang** folgt dem Muster aus `gateway/vorgang.py`: Zustände, Bindungs-Hash, Gate, Ausführung nur mit Einmal-Token, Prüfung durch den Menschen.
4. **Eine neue Entscheidungsart** braucht einen Eintrag in `desk/decisions.py` (`APPLY`, Titel, Bindungsschlüssel) und eine Route im Hub mit Kommentar.
5. **Die Oberfläche** ist ein Werkzeug (`uix/tools/<name>/`, Manifest `tool.yaml`) oder eine Shell (`shell.yaml` oder `shell.vorgabe.yaml`). `uix_check` prüft beides.
6. **Tests:** ein Test je Zusage, Grenzen über `test_core_boundary_src`, Abnahme über `uix_check`.

Nicht erlaubt ist: Text in den Audit schreiben, einen Hard Block überstimmbar machen, eine Freigabe ohne Bindung ausführen, eine Cloud ohne Beschluss anschließen.
