# SPEC Freigaben S4 v1 – G1 Anforderungen (05.11.2026)

Stand: `main` `d51083a`. Gate **G1** (Anforderungen); Design (G2) und Bau (G3) erst nach Freigabe durch den Captain.
Herkunft: `ANALYSE_FREIGABEN_VEREINFACHEN_2026-11-04.md` §3–§4 (S1–S3 gebaut, S4 offen), `ROADMAP_ONE_SEDRA_RENEW_2026-11-05.md` (Phase R3, Unterchat U5, offene Entscheidung 2 „Schutzcode bei Freigaben S4: ja/nein?“), `WISSEN_SEDRA_GESAMT.md` §8 Punkt 2 („Wiederholungs-Deckel“).

**Kurz:** Heute gibt es fünf Wege, auf denen der Satz „Werkzeug + Muster darf laufen“ entsteht, mit drei Ablagen, drei Prüfungen und drei Wortschätzen. S4 macht daraus **ein Modell „Erlaubnis mit Dauer“** (einmal · diese Sitzung · befristet · immer), mit **einer** Deckungsprüfung und **einer** Liste „Gilt gerade“. Der Schutz wird nicht schwächer. Drei Fragen entscheidet der Captain vor G2: Schutzcode (E1), Wiederholungs-Deckel (E2), Lücken in den festen Vorbehalten (E3).

## 1. Befund (im Code gelesen)

| Nr | Befund | Beleg |
|---|---|---|
| B1 | **Drei Ablagen für denselben Satz.** Katalogregel: `local_config/freigabe_katalog.yaml`. Sitzungs-Erlaubnis: Eintrag `erlaubnis` im Sitzungs-JSONL, Rücknahme als `aktiv: false`. Aufgabe: `runtime_data/harness/aufgaben/T-<8 Hex>.json`. | `harness/katalog.py:3–4`, `harness/erlaubnis.py:9`, `harness/sitzung.py:164–171`, `harness/aufgabe.py:5` |
| B2 | **Fünf Wege, die erteilen:** (1) Karte „Erlauben“, (2) Karte „Für diese Sitzung erlauben“, (3) Erlaubnisse einer Vorlage beim Anlegen der Sitzung (Karten-ID `V-<vorlage>-<n>`), (4) Aufgabe vom Captain, (5) Vorschlag des Vorarbeiters (Kartenart `aufgabe`). Dazu die Katalogregel als sechste, dauerhafte Form. | `harness/freigabe.py:32, 353–367, 333–350`; `harness/api.py:382–404` |
| B3 | **Die Deckung steht an einer Stelle, die Grenzen nicht.** `Kiste.aufruf` prüft Aufgabe vor Sitzungs-Erlaubnis, beides nur, wenn kein Vorbehalt und keine Warnkarte vorliegt. | `harness/freigabe.py:233–242` |
| B4 | **Ungleiche Grenzen.** Aufgabe: Frist höchstens 24 h, höchstens 500 Aufrufe, Prüfung „weites Muster“, Pfad außerhalb, Treffer auf Vorbehalt, S9 (Schreiben + beliebige Ausführung). Sitzungs-Erlaubnis: **kein Ende** außer Rücknahme oder Schließen, **kein Zähler**, **keine** dieser Prüfungen. | `harness/aufgabe.py:25–28, 103–119, 136–143`; `harness/erlaubnis.py:18–31, 34–47` |
| B5 | **Das Muster der Sitzungs-Erlaubnis ist breiter als der Klick.** Eine Karte für eine Datei öffnet den ganzen Ordner (`ordner/**`), eine Datei in der Wurzel öffnet `*` (alle Dateien der Wurzel). Ein Befehl öffnet seinen Anfang (`git commit*`). | `harness/erlaubnis.py:18–31` |
| B6 | **Aufgaben gelten nur für lokale Modelle, Sitzungs-Erlaubnisse auch für Cloud-Modelle.** Die Prüfung `self.lokal` steht nur vor der Aufgabe. Ob das gewollt ist, steht in keiner Spec (Vermutung: nicht bedacht). | `harness/freigabe.py:155, 234, 239` |
| B7 | **Lücken in den festen Vorbehalten.** Hart geschützt sind `freigabe.py`, `vorbehalte.py`, `befehl.py`, `aufgabe.py`, `aufgabe_deckung.py`, `vorarbeiter.py`, `lauf*.py`, `herkunft.py`, `code_stand.py`. **Nicht** geschützt: `erlaubnis.py` (entscheidet, was eine Sitzungs-Erlaubnis darf), `katalog.py` (enthält `einstufen`), `bausteine.py`, `runtime/config/freigabe_bausteine.yaml` (nur `**/freigabe_katalog*.yaml` steht in der Liste). Zusammen mit B5: Ein Klick „Für diese Sitzung“ auf eine Karte für eine Datei in `runtime/src/guppi_runtime/harness/` öffnet diese Dateien ohne weitere Karte. Die G4-Sperre für ungesehenen Code greift erst beim Ausführen, nicht beim Schreiben. | `harness/vorbehalte.py:10–40`; `harness/erlaubnis.py:29–31`; `harness/vorbehalte.py:73–76` |
| B8 | **Klassen stimmen schon.** Sitzungs-Erlaubnis, Aufgabe anlegen, Vorlage-Erlaubnisse und Vorschlag des Vorarbeiters sind Klasse H und gehen durch die Tür von G9 (Systemdialog oder `FREIGABE.bat`). Klasse H geht nie an den Vorarbeiter. | `desk/freigabeklasse.py:38, 42, 56–58`; `harness/freigabe.py:261–263`; `SPEC_APPS_v1_O3PLUS_G9_G2.md` §13.3 |
| B9 | **Die Dauerfreigabe der Agenten ist ein eigener, vierter Mechanismus im Kern.** `standing` gibt es nur für „Agent wecken“: höchstens 50 Nutzungen, 30 Tage, Stufe 3; Vorgabe 7 Tage / 50 Nutzungen; Token im Guard. | `core/guard.py:15–18, 193–213`; `config/orchestra.yaml:13`; `desk/gated.py:20–30` |
| B10 | **Wiederholungen haben keinen Deckel je Erlaubnis.** Die Schleife bremst nur denselben Aufruf **direkt hintereinander** in einer Antwort (2. Mal Hinweis, 3. Mal Schluss). Eine Aufgabe zählt jeden Aufruf; ein Agent, der denselben fehlschlagenden Befehl wiederholt, verbraucht die Aufgabe. Für Agenten gilt seit 22.10. „höchstens ein Wiederholungs-Weckruf je Aufgabe“ (HALT 2), für die Harness nichts Vergleichbares. | `harness/schleife.py:6, 301–305`; `harness/aufgabe.py:310–320`; `SPEC_AGENTEN_ORCHESTRIERUNG_v1.md:4270`; `KURS_PRAESENTATION_SEDRA.md:133` |
| B11 | **Drei Darstellungen.** „Gilt gerade“ lädt Sitzungs-Erlaubnisse einzeln je Sitzung (bis zu 20 Anfragen); Aufgaben haben eigene Zeilen und ein Formular (Vorgabe 2 h, 50 Aufrufe); „immer“ gibt es nur im Katalog-Editor, nicht auf der Karte. | `uix/shells/harness/erlaubnisse.js:31–44`; `uix/shells/harness/aufgabe.js:142–143`; `ANALYSE_FREIGABEN…` §5 Frage 3 |
| B12 | **Das Audit kennt schon den Kanal.** `HARNESS_APPROVED_BY` mit `aufgabe:<T>`, `sitzung:<K>`, `katalog:<regel>` und `kanal`. Das ist die Grundlage für ein gemeinsames Ereignis. | `harness/freigabe.py:248–250` |

**Was „Schutzcode“ heißt (zwei Lesarten).** In der Analyse vom 04.11. bedeutet „berührt Schutzcode“, dass S4 die Prüfdateien (`aufgabe.py`, `erlaubnis.py`, `freigabe.py`) umbaut (`ANALYSE_FREIGABEN…:47, 54`). Im Auftrag für U5 ist ein **Schutzcode als Geheimzahl** gemeint, die der Captain beim Erteilen eingibt. Diese Spec behandelt beides: Der Umbau der Prüfdateien ist Voraussetzung von S4 und läuft nur durch Claude mit Gate. Ob es eine Geheimzahl gibt, ist Entscheidung E1.

## 2. Ziel

Eine Erlaubnis ist überall derselbe Datensatz mit vier Angaben: **Was** (Werkzeug + Muster), **Wo** (Projekt, Sitzungen), **Wie lange** (einmal · diese Sitzung · befristet · immer), **Warum** (ein Satz). Sitzungs-Erlaubnis, Aufgabe, Vorlage-Erlaubnis und Vorschlag des Vorarbeiters sind nur noch Länge oder Herkunft dieser einen Erlaubnis. „Immer“ bleibt die Katalogregel. Eine reine Funktion prüft die Deckung, für alle Längen mit denselben Grenzen. Die Karte bietet eine Leiter **Einmal · Diese Sitzung · Befristet · Immer**. „Gilt gerade“ zeigt alles in einer Liste.

**Nicht Ziel:** den Guard oder `core/**` ändern; die Dauerfreigabe der Agenten (`standing`) umbauen (sie wird nur angezeigt); neue Rechte schaffen; `verboten`, Vorbehalte, Warnkarten, Schreibbereich oder die Tür von G9 lockern; die Berechtigungen der Apps (AM3, U6) bauen; Rollen (R4).

## 3. Anforderungen

### 3.1 Modell und Ablage

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| FS-01 | **Ein Datensatz „Erlaubnis“:** `{id, was: [{werkzeug, muster}], wo: {projekt, sitzungen}, dauer: {art: einmal\|sitzung\|befristet\|immer, bis?, max_aufrufe?}, warum, herkunft: {von: captain\|vorlage\|vorarbeiter, karte_id?, vorlage?}, modelle, status, aufrufe, angelegt, beendet, grund}`. Sitzungs-Erlaubnis = `dauer.art: sitzung`, Aufgabe = `befristet`, Vorlage-Erlaubnis = `sitzung` mit `herkunft.von: vorlage`, Vorschlag des Vorarbeiters = `befristet` mit `herkunft.von: vorarbeiter`. | Test: jede heutige Form wird verlustfrei in den Datensatz und zurück gewandelt |
| FS-02 | **„Immer“ ist die Katalogregel** und bleibt in `local_config/freigabe_katalog.yaml`. Es entsteht kein zweiter Speicher für Dauerregeln. In der Liste erscheint eine Katalogregel als Erlaubnis mit `dauer.art: immer` (nur Anzeige). | Test: Liste enthält die Regeln; Schreiben nur über den Antrag `request:harness_katalog` |
| FS-03 | **Bestehende Ablagen bleiben lesbar.** Alte Sitzungs-JSONL und `T-*.json` gelten ohne Umzug weiter. Ob neue Erlaubnisse eine gemeinsame Ablage bekommen, entscheidet E4. | Test mit Altbestand (Sitzung mit `erlaubnis`-Einträgen, Aufgabe Version 1) |
| FS-04 | **Ein Lesepunkt:** `GET /api/harness/erlaubnisse?projekt=&sitzung=&status=` liefert alle Erlaubnisse in einer Antwort (statt einer Anfrage je Sitzung, B11). Neuer Weg mit Eintrag in `HARNESS_WEGE`, `ROUTEN_HARNESS` und im Regex `WEG` von `harness/api.py`. | Test; `test_freigabe_vollstaendig` grün |

### 3.2 Eine Prüfung für alle Längen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| FS-10 | **Eine reine Deckungsfunktion** `deckt(erlaubnisse, sitzung_id, werkzeug, ziel, jetzt, weich)` ersetzt `erlaubnis.deckt` und den Aufruf von `aufgabe_deckung.deckt`. Reihenfolge wie heute: Vorbehalt → `verboten` → Warnkarte → Katalog `frei` (verbraucht nichts) → befristete Erlaubnis (gezählt) → Sitzungs-Erlaubnis → Karte. | Test: Wahrheitstabelle alt gegen neu, ohne Abweichung (wie `test_harness_aufgabe_deckung_vergleich`) |
| FS-11 | **Dieselben Grenzen beim Erteilen** für jede Länge außer „einmal“: Pfad relativ ohne `..`, Prüfung „weites Muster“, Probe gegen feste Vorbehalte, S9. Für den Captain sind das Warnungen, für einen Vorschlag des Vorarbeiters Fehler (wie heute bei Aufgaben). | Test je Grenze und Länge |
| FS-12 | **Das Muster der Karte ist eng:** „Diese Sitzung“ öffnet für eine Datei den Ordner der Datei, für eine Datei in der Wurzel nur genau diese Datei (nicht `*`). Die Karte zeigt das Muster und in Klartext, was es öffnet, bevor der Captain klickt. | Test `muster_fuer`; Node-Test der Karte |
| FS-13 | **Lokal oder Cloud gleich behandeln:** Ob Sitzungs-Erlaubnisse wie Aufgaben nur für lokale Modelle gelten, entscheidet E5. Bis dahin bleibt das heutige Verhalten. | Test mit `lokal=False` |
| FS-14 | **Sitzungs-Erlaubnis bekommt ein Ende:** zusätzlich zum Schließen der Sitzung eine Höchstdauer (Vorschlag: 24 h ab Erteilung, wie die Frist der Aufgabe). Vorlage-Erlaubnisse ebenso. | Test mit Uhr |
| FS-15 | **Rücknahme wirkt für jede Länge ab dem nächsten Aufruf** (HS-29), mit einem Knopf „Zurücknehmen“ und demselben Audit. | Test |

### 3.3 Karte und Oberfläche

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| FS-20 | **Leiter auf der Karte:** Einmal · Diese Sitzung · Befristet (Bausteine-Vorgabe 2 h, 50 Aufrufe, änderbar) · Immer. „Immer“ schreibt nicht selbst, sondern stellt den Antrag `request:harness_katalog` mit genau dieser Regel in den Posteingang. Nicht angeboten bei Vorbehalt, Warnkarte, `verboten`, Modell laden/entladen (wie `erlaubt_fuer_karte`). | Node-Test; Playwright `test_uix_harness_browser.py` |
| FS-21 | **Klassen:** „Diese Sitzung“, „Befristet“ und „Immer“ sind Klasse H und gehen durch die Tür von G9. Neue Wege (`befristet`, `immer`) stehen in `freigabeklasse.WEGE` und `_harness`. Unbekanntes bleibt H. | `test_freigabe_klasse`, `test_freigabe_vollstaendig`, `test_freigabe_tuer` |
| FS-22 | **Eine Liste „Gilt gerade“** mit gleichen Spalten für alle Längen: Was (Klartext, Muster unter „Genaue Regeln“) · Wo · Wie lange / noch · Warum · Herkunft · Zurücknehmen. Katalogregeln stehen im Reiter „Regeln“, nicht doppelt. | Node-Test; Bildvergleich |
| FS-23 | **Dauerfreigaben der Agenten** (`standing`) stehen in „Gilt gerade“ lesend mit „Widerrufen“ (bestehender Weg), ohne Änderung am Guard. | Test: Widerruf über den bestehenden Weg |
| FS-24 | **Ein Wortschatz:** Erlaubnis; Längen einmal · diese Sitzung · befristet · immer; Stufen Frei · Fragen · Verboten. Das Wort „Aufgabe“ verschwindet aus der Oberfläche (die Kennung `T-…` bleibt). | `uix_check`; Suche nach den alten Wörtern in `uix/shells/harness/` |

### 3.4 Was unverändert bleibt

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| FS-30 | `verboten`, harte und weiche Vorbehalte, Warnkarten (W-1/W-2), Schreibbereich des Projekts, G4 (ungesehener Code), Guard als einzige Stelle mit Tokens, Tür von G9, „Klasse H nie an den Vorarbeiter“: Verhalten gleich. | Die bestehenden Tests `test_harness_aufgabe`, `test_harness_karte_erlaubnisse`, `test_harness_vorbehalte`, `test_harness_katalog*`, `test_freigabe_*` laufen **unverändert** grün |
| FS-31 | **Ein Ereignis im Audit** `HARNESS_ERLAUBNIS {aktion: erteilt\|zurueckgenommen\|abgelaufen\|erschoepft\|gedeckelt, id, dauer, herkunft, kanal}` zusätzlich. Die alten Ereignisse (`HARNESS_AUFGABE_*`, `HARNESS_SITZUNG_ERLAUBT`, `HARNESS_APPROVED_BY`) bleiben ein Jahr, damit Auswertungen weiter laufen. | Test |
| FS-32 | **Vorarbeiter:** Sein Vorschlag bleibt eine Karte an den Captain, streng geprüft (keine weiten Muster, nicht für die eigene Sitzung, kein S9). Er kann keine Länge selbst erteilen. | bestehende Tests; Gegenprobe |

### 3.5 Lücken in den festen Vorbehalten (nach E3)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| FS-35 | Harte Vorbehalte werden zusätzlich: `harness/erlaubnis.py`, `harness/katalog.py`, `harness/bausteine.py`, die neue Deckungsdatei aus FS-10 und `runtime/config/freigabe_bausteine.yaml`. Änderung nur durch Claude mit Gate (die Liste ist selbst Vorbehalt). | `test_harness_vorbehalte`: je Pfad `pruefen` liefert einen Grund; Gegenprobe: Eintrag entfernt → Test rot |

### 3.6 Wiederholungs-Deckel (nach E2)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| FS-40 | **Eine Erlaubnis deckt denselben Aufruf nicht beliebig oft.** „Derselbe Aufruf“ = gleiche Bindung (Werkzeug, Ziel, Hash der Argumente) **ohne Wirkung dazwischen** (kein Schreiben in der Sitzung seit dem letzten Versuch). Ein Testlauf nach einer Korrektur am Code zählt also nicht als Wiederholung. | Test: Fehler – Wiederholung – Deckel; Fehler – Schreiben – Wiederholung zählt neu |
| FS-41 | Ist der Deckel erreicht, geht der nächste gleiche Aufruf als Karte an den Captain (mit Hinweis „n-mal ohne Änderung wiederholt“), das Audit vermerkt `gedeckelt`. Die Erlaubnis selbst bleibt bestehen. | Test |
| FS-42 | Der Deckel steht fest im Code mit dem Wert aus E2; `local_config` darf ihn nur **enger** stellen. | Test: weiter stellen wird abgelehnt |

### 3.7 Schutzcode als Geheimzahl (nur wenn E1 = ja oder „nur Klasse H“)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| FS-45 | Der Schutzcode wird **nie im Browser** eingegeben (Code in der Seite könnte ihn mitlesen, Befund K4/K5 in `SPEC_APPS_v1_AM0_E1…`). Eingabe nur in der Konsole (`FREIGABE.bat freigeben B-…`, Abfrage ohne Echo) oder später im eigenen Freigabefenster (G5, AM9). | Test: keine Route nimmt einen Code von der Seite an |
| FS-46 | Ablage nur als Hash mit Salz (`hashlib.scrypt`, Standardbibliothek) in `local_config/freigabe_schutzcode.yaml`; Vorbehalt `**/local_config/**` gilt schon; kein Klartext im Audit. | Test |
| FS-47 | Drei Fehlversuche → 10 Minuten Sperre für Bestätigungen mit Code; Audit `FREIGABE_SCHUTZCODE_FALSCH` ohne den Code. Vergessen: die Datei in `local_config` löschen (der Captain hat Dateizugriff, ein Modell nicht). | Test mit Uhr |
| FS-48 | Schalter `freigabe_schutzcode` in `local_config/switches.yaml`, Standard aus. Ohne Datei kein Code. | Test |

## 4. Abnahme

1. Alle Tests aus FS-30 unverändert grün; dazu neue Tests je Anforderung; ganze Bahn ohne Rot.
2. Gegenproben: (a) eine Grenze aus FS-11 für Sitzungs-Erlaubnisse entfernen → Test rot; (b) neuer Weg ohne Eintrag in `freigabeklasse.py` → `test_freigabe_vollstaendig` rot; (c) Wahrheitstabelle FS-10 mit einer vertauschten Reihenfolge → rot.
3. Browser-Abnahme an einer eigenen Testinstanz (`scratchpad/testserver.py`, eigener Token): Leiter auf der Karte, „Gilt gerade“ mit allen Längen, Zurücknehmen; Playwright `test_uix_harness_browser.py` grün.
4. Am PC des Captains: Klick „Befristet“ und „Immer“ erscheinen im Systemdialog bzw. als Antrag im Posteingang; der Captain prüft selbst im echten Sedra.

## 5. Reihenfolge (jede Stufe für sich lieferbar)

| Stufe | Inhalt | Berührt Prüfdateien | Hängt an |
|---|---|---|---|
| **S4.0** | Lücken der festen Vorbehalte schließen (FS-35) | `vorbehalte.py` (nur Liste) | E3 |
| **S4.1** | Datensatz als Sicht, Lesepunkt, eine Liste „Gilt gerade“ (FS-01–04, FS-22–24) | nein (lesen) | – |
| **S4.2** | Eine Deckungsfunktion mit Vergleichstest alt/neu, Rücknahme, Audit (FS-10, FS-15, FS-31) | ja | S4.1 |
| **S4.3** | Gleiche Grenzen, enges Muster, Ende der Sitzungs-Erlaubnis, lokal/Cloud (FS-11–14) | ja | E5 |
| **S4.4** | Leiter auf der Karte mit „Befristet“ und „Immer“ als Antrag (FS-20, FS-21) | `freigabeklasse.py` | S4.2 |
| **S4.5** | Wiederholungs-Deckel (FS-40–42) | ja | E2 |
| **S4.6** | Schutzcode (FS-45–48) | ja | E1 = ja / nur H |

S4.0 und S4.1 sind klein und gefahrlos und können sofort starten. S4.2–S4.5 bauen Schutzcode um; sie laufen nur durch Claude, mit Gate je Stufe.

## 6. Offene Entscheidungen des Captains

**E1 – Schutzcode (Geheimzahl) beim Erteilen?**

| Option | Vorteile | Nachteile |
|---|---|---|
| **a) Nein** | Nichts Neues zu merken; kein Ausfall, wenn der Code vergessen ist; G9 hält das Modell schon heraus (Klasse H nur über Systemdialog oder Konsole, B8). | Schützt nicht gegen eine andere Person am entsperrten PC und nicht gegen Klick-Müdigkeit („Ja“ im Dialog ohne Lesen). |
| **b) Ja, für jede Erteilung** | Jede Freigabe ist eine bewusste Handlung; schützt auch bei fremdem Zugriff auf den PC. | Viel Reibung im Alltag (auch Klasse N, auch „einmal“); im Browser nicht sicher eingebbar (FS-45), also müsste jede Freigabe in die Konsole – das widerspricht dem Ziel „weniger Klicks“. |
| **c) Nur für Klasse H** | Code nur dort, wo Rechte für später entstehen; Alltag (Klasse N, „einmal“) bleibt schnell; passt zu Rollen (R4), wo eine zweite Person am PC sitzt. | Klasse H läuft heute über den Systemdialog (Windows `MessageBoxW` kann keinen Text abfragen); mit Code bliebe nur die Konsole, bis G5 (eigenes Freigabefenster, AM9) steht. |

**Vorschlag:** für S4 **a) nein**. Option c) als Anforderung für R4/AM7 vormerken, wenn mehrere Personen an einem Sedra arbeiten, und dann zusammen mit G5 bauen. FS-45–48 bleiben bis dahin unbebaut.

**E2 – Wiederholungs-Deckel (WISSEN §8 Punkt 2): Soll eine Erlaubnis Wiederholungen desselben Aufrufs decken, und wie viele?**
Optionen: a) kein eigener Deckel, der Zähler der Aufgabe reicht; b) fester Deckel 3 gleiche Aufrufe je Erlaubnis und Stunde; c) Deckel nur für gleiche Aufrufe **ohne Änderung dazwischen** (FS-40). **Vorschlag: c) mit Wert 2** (ein Versuch und eine Wiederholung, danach Karte), wie HALT 2 bei den Agenten („höchstens ein Wiederholungs-Weckruf“). Für die Dauerfreigabe der Agenten bleibt HALT 2 unverändert.

**E3 – Vorbehalt-Lücken (B7) jetzt schließen?** Vorschlag: **ja, als S4.0 vor allem anderen**: `erlaubnis.py`, `katalog.py`, `bausteine.py`, `freigabe_bausteine.yaml` und die neue Deckungsdatei. `sitzung.py`, `api.py` und `werkzeuge.py` gehören in die Härtung A0 (U12), nicht hierher.

**E4 – Gemeinsame Ablage für neue Erlaubnisse?** a) nur Sicht über die alten Ablagen; b) neue Erlaubnisse in `runtime_data/harness/erlaubnisse/E-*.json`, alte werden gelesen, nicht umgezogen. Vorschlag: **a) für S4.1–S4.3**, b) erst entscheiden, wenn die Sicht im Alltag läuft.

**E5 – Gelten Sitzungs-Erlaubnisse auch für Cloud-Modelle (B6)?** Vorschlag: **nein**, wie Aufgaben (HS-27): Mit einem Cloud-Modell entscheidet jede Wirkung wieder die Karte. Das ändert Verhalten; wer Cloud nutzt, sieht mehr Karten.

**E6 – „Immer“ direkt auf der Karte (Analyse §5 Frage 3)?** Vorschlag: **ja, aber nur als Antrag** im Posteingang (FS-20), nie als direktes Schreiben des Katalogs.

## 7. Rückfall und nächste Gates

Rückfall: S4.1 ist reine Sicht; S4.2 hat den Vergleichstest alt/neu und lässt sich mit einem Rücksprung auf die alten Funktionen zurücknehmen; alte Ablagen bleiben gültig. Nächste Gates: G1 (dieses Dokument, Entscheidungen E1–E6) → G2 Design (Datensatz, Funktion, Karte, Wege) → G3 Bau in der Reihenfolge §5 → G4 Abnahme am PC.
