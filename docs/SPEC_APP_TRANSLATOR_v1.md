# SPEC App Translator v1 – G1 Anforderungen (05.11.2026)

Stand: `main` `d51083a`. Gate **G1** (Anforderungen); Design (G2) und Bau-Aufgaben (G3) erst nach Freigabe. Unterchat **U2** (Phase R1, Stufe A3, UIX X2, Werkzeug W2).
Grundlage: Beschlüsse des Captains vom 05.11.2026 (`ROADMAP_ONE_SEDRA_RENEW_2026-11-05.md` §1, `ROADMAP_ONE_SEDRA_APPS_KERN_SHELL_2026-11-05.md` §2, §4, §7): One Sedra (Kennung `harness`) ist die Zentrale; Funktionen der anderen Shells kommen als Apps; die alte Shell bleibt bis zum Gleichstand unverändert; nur eigene Pakete bis A0/A4.
Pfade relativ zu `runtime/src/guppi_runtime/`, sonst ab Repo-Wurzel. Zeilen für `d51083a`.

**Ergebnis in einem Satz:** Die vier Werkzeuge des Translators laufen in One Sedra schon – aber nur als vier lose Reiter; es fehlt **eine** App „Translator“ mit Modus-Reitern, einer gemeinsamen Eingabe („Wolke“), Zustand je Modus und einer Übergabe Transkript → Übersetzer, die auch bei offenem Reiter ankommt. Kein neuer Kernweg, keine neue Route nötig.

## 1. Befund

| Nr | Befund | Beleg |
|---|---|---|
| B1 | Die Shell „Translator“ hat die Kennung **`fisch`** (Anzeigename „Translator“); interne Kennungen `fisch`, `/api/fisch/…` bleiben laut Technik-Übersicht „vorerst unverändert“. | `uix/shells/fisch/shell.yaml:5–6`; `docs/SHELL_TRANSLATOR_TECHNIK_2026-10-20.md:4–5` |
| B2 | Die Shell hat **vier Modi** als feste Liste: Übersetzen → `uebersetzung:wolke`, News → `nachrichten:brief`, Aufnahme → `aufnahme:rekorder`, Transkript → `transkript:alle`; der Modus wird je Browser gemerkt (`sedra.fisch.modus`). | `uix/shells/fisch/shell.js:11–21, 48–50, 118` |
| B3 | **Wolke:** Der Satz aus der Eingabe geht als `frage` in das Objekt des Modus; Ausnahme Aufnahme: der Satz wird der Titel im ersten Feld, nichts wird neu eingehängt. | `uix/shells/fisch/shell.js:123–135` |
| B4 | Die Werkzeuge lesen `ctx.object.frage`: Übersetzer übersetzt sofort, Nachrichten nimmt sie als Interessen, Transkript sucht damit. | `uix/tools/uebersetzer/tool.js:18–22`; `uix/tools/nachrichten/tool.js:22, 45`; `uix/tools/transkript/tool.js:23, 91` |
| B5 | **Zustand je Modus fehlt in der alten Shell:** Jeder Moduswechsel hängt alle Werkzeuge aus und neu ein (`unmountTool` → `replaceChildren`); eingegebener Text und Ergebnisse eines Modus sind danach weg. Nur der Rekorder überlebt, weil die Aufnahme im Kern läuft. | `uix/shells/fisch/shell.js:143–144`; `uix/tools/rekorder/tool.yaml:15–16` |
| B6 | In One Sedra öffnen die vier Werkzeuge **schon als einzelne App-Reiter** (`app:<typ>:<id>`), über denselben Einhängeweg wie Cockpit und Minimal. Drei haben einen Ort (Übersetzer, Transkripte, Rekorder), **Nachrichten hat keinen Ort** in `places.js` und erscheint nur als „App ohne Ort“ über `/api/uix/modules`. | `uix/shells/harness/app.js:1–10, 46–70`; `uix/ui/places.js:30–32` (kein Eintrag `nachrichten`); `docs/PRUEFUNG_STICK_SHELLS_2026-11-02.md:15` |
| B7 | Start-Menü: `uebersetzung`, `transkript`, `aufnahme` stehen in der Gruppe `arbeit`; `nachrichten` fehlt in der Zuordnung (fällt auf `arbeit` zurück). Eine Gruppe „Translator“ gibt es nicht. | `uix/shells/harness/start_gruppen.json:2, 22–24` |
| B8 | Höchstens **8 App-Reiter**; die vier Translator-Werkzeuge belegen als lose Reiter bis zu vier davon. | `uix/shells/harness/app.js:16, 55–66` |
| B9 | **Vorbild Sammel-App vorhanden:** „Sedra Token“ ist eine App mit drei Reitern in einem App-Reiter (`tokenReiter`), Felder werden versteckt statt neu gebaut. Heute als Sonderfall für `meter` verdrahtet. | `uix/shells/harness/app.js:118–138, 148` |
| B10 | **Transkript → Übersetzer existiert schon** als Knopf „An den Übersetzer“ (`ctx.shell.open({type: 'uebersetzung', id: 'wolke', frage: …})`, Zusammenfassung oder bis 2000 Zeichen Text). In One Sedra wird daraus `H.app.oeffnen`; ist der Reiter `app:uebersetzung:wolke` schon offen, bleibt der alte Eintrag stehen und die neue `frage` kommt **vermutlich nicht an** (Reiter-ID ohne `frage`, kein Neu-Einhängen beim Aktivieren). *Nicht im Browser geprüft.* | `uix/tools/transkript/tool.js:154`; `uix/shells/harness/shell.js:57`; `uix/shells/harness/app.js:21–24, 52–54` |
| B11 | **Zwei verschiedene „Übersetzungen“:** (a) Übersetzer-Werkzeug = Umformulieren für eine **Rolle** (6 Rollen, deutsch, Format ÜBERSETZUNG/UNSICHERHEITEN/HINWEISE); (b) `harness/uebersetzen.py` = Übersetzen in eine **Sprache** (8 Sprachen, Teile à 2500–3000 Zeichen), heute nur im Chat-Werkzeug `youtube_transkript` (`uebersetzen_nach`). | `fisch/uebersetzer.py:7–14, 19–26`; `harness/uebersetzen.py:10–12, 41–52`; `harness/werkzeuge.py:99, 454–459`; `harness/api.py:942–954` |
| B12 | **Kein Chat-Werkzeug `uebersetzen`.** Die 20 Chat-Werkzeuge enthalten keins; die Roadmap verlangt für jedes neue Werkzeug Schema, Zweig, Wegeinträge, Regex, Karte oder `OHNE_KARTE`, Test. | `docs/ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05.md` §1, §3 (Regel); `harness/katalog.py:20` |
| B13 | Die Routen `/api/fisch/*` sind im Freigabe-Katalog eingestuft (Übersetzen, Brief, Erkenntnisse = `handlung`, „lokales Modell“; Suche, Status = `liest`). | `desk/freigabeklasse.py:193–202` |
| B14 | **Begriffskollision „Profil“:** Das Werkzeug Nachrichten hat ein News-Profil (`local_config/fisch.profil.json`); U4 führt Oberflächen-Profile ein. | `uix/tools/nachrichten/README.md:5–6`; `harness/desktop.py:8` |
| B15 | Alle vier Werkzeuge tragen `trust: CORE` und kein `shells:`/`profile:` (Felder kennt der Manifest-Prüfer noch nicht). | `uix/tools/*/tool.yaml` (je Zeile `trust: CORE`); `desk/gateway.py:63` |

Vorhanden und nutzbar: Einhängen über `S.ctx.tools.forObject` + `makeContext` (`app.js:74–115`), Werkbank-Zeile `actionsOf`, Nachweis-Spalte, Arbeitsstand `sedraStand` (§10.2), Rekorder im Kern, Freigabe-Einstufung der Routen.

## 2. Ziel und Nicht-Ziel

**Ziel:** Eine App **„Translator“** in One Sedra: ein App-Reiter mit vier Modus-Reitern (Übersetzen · News · Aufnahme · Transkript), oben eine gemeinsame Eingabe (die „Wolke“, ohne Goldfisch-Zeichnung), darunter das Werkzeug des Modus. Jeder Modus behält seinen Zustand, solange die App offen ist. Ein Transkript lässt sich mit einem Klick an den Übersetzer geben, auch wenn der Übersetzer schon offen ist. Optional ein Chat-Werkzeug `uebersetzen`.

**Nicht-Ziel:**
- Die Shell `fisch` ändern, umbenennen oder löschen (bleibt bis Gleichstand, A3-Regel). Kein Umbenennen von `/api/fisch/*`.
- Goldfisch, Glas, Blasen nachbauen (Gestaltung der alten Shell, nicht Funktion).
- Neue Kernwege, neue Routen, neue Rechte, Netz-Nachrichten, STT-Anbieter einbinden, `fenster/rekorder.html` nachbauen (fehlt, `PLAN_USB_STICK_MINIMAL.md` §8.1).
- Den Einhänge-Vertrag der Werkzeuge ändern; die Werkzeuge bleiben auch einzeln als Apps öffenbar.

## 3. Anforderungen

### 3.1 App und Rahmen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| TR-01 | Neues Paket `uix/tools/translator/` (`kind: object`, `handles: [translator]`, `trust` wie die vier Werkzeuge – heute `CORE`, Neueinstufung mit A0/U12 –, `api: []` – es ruft selbst keine Route), Ort `translator` in `ui/places.js` mit Wörtern „translator“, „übersetzen“, „news“, „transkript“. Es zeichnet nur den Rahmen und hängt die vier vorhandenen Werkzeuge über **denselben** Weg ein (`ctx.tools.forObject` / `makeContext` / `mountTool`, wie `app.js:flaeche`). Kein Kopieren von Werkzeugcode. | Node-Test: Manifest, Ort; Code-Prüfung „kein zweiter Einhängeweg“ |
| TR-02 | Der App-Rahmen (Titel, Werkbank-Zeile, Nachweis-Spalte, Fehlersatz, Arbeitsstand) kommt vom Kern (`app.js`), nicht von der App (Roadmap Kern/Shell §4). Die Modus-Reiter nutzen das Muster von `tokenReiter` (`app.js:118–138`); der Sonderfall `meter` wird dabei zu einem allgemeinen Feld „Reiter einer App“ (Vorschlag TR-E1). | Test der Harness: App mit Reitern ohne Sonderfall im Code |
| TR-03 | Start-Menü: Translator steht in der Gruppe `arbeit` (Zuordnung in `start_gruppen.json`); die vier Einzel-Apps bleiben erreichbar (Suche, Chat-Ort), ob sie zusätzlich im Menü stehen, entscheidet TR-E2. `nachrichten` bekommt eine Zuordnung. | Test `start_gruppen` |

### 3.2 Modi und Wolke

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| TR-10 | Vier Modus-Reiter mit denselben Objekten wie die Shell `fisch` (`uebersetzung:wolke`, `nachrichten:brief`, `aufnahme:rekorder`, `transkript:alle`). Eine Liste in einer Datei; Shell und App lesen dieselben Objekte (Gleichstand prüfbar). | Node-Test: Liste der App = `sedraFischPure.MODI` (Objekte) |
| TR-11 | **Wolke:** ein mehrzeiliges Feld über den Reitern; Enter sendet, Umschalt+Enter Zeilenumbruch; Platzhalter je Modus wie `fisch/shell.js:12–19`. Senden übergibt den Satz als `frage` an das Werkzeug des aktiven Modus (Übersetzen → sofort übersetzen, News → Interessen, Transkript → Suche, Aufnahme → Titel ins erste Feld, kein Neu-Einhängen). | Browser-Test an Testinstanz, je Modus ein Fall |
| TR-12 | Strg+K fokussiert die Wolke, solange der Translator-Reiter vorn ist; außerhalb bleibt Strg+K, was One Sedra festlegt. Kein Alt+S (in One Sedra ruft Alt+S das Start-Menü). | Test der Tastatur |
| TR-13 | Text nur mit `textContent`, keine Hex-Farben (Tokens), Dateien ≤ 400 Zeilen, kein `setInterval` (UIX-Regeln). | `uix_check`, Linter-Tests |

### 3.3 Zustand je Modus

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| TR-20 | Ein Modus wird beim ersten Öffnen eingehängt und beim Wechsel nur **versteckt**, nicht ausgehängt (Unterschied zu B5). Eingaben, Ergebnisse und Auswahl (Rollen, Ton, Tiefe, geöffnetes Transkript) bleiben, solange der Translator-Reiter offen ist. Beim Schließen des Reiters werden alle vier ausgehängt. | Browser-Test: Text in Übersetzen, Wechsel zu News und zurück, Text noch da; Unmount-Zähler beim Schließen = Zahl der eingehängten |
| TR-21 | Gemerkt je Browser: der zuletzt aktive Modus (`localStorage`, eigener Schlüssel `sedra.harness.translator.modus`, nie der Text). Nach Neuladen öffnet der Translator im gemerkten Modus. Inhalte bleiben, wo sie heute liegen (Kern, Projekt), nicht im Browser. | Test |
| TR-22 | Werkbank-Zeile zeigt die Handlungen des **aktiven** Modus (`actionsOf` nur seiner Werkzeuge), Nachweis-Spalte ebenso. | Test |
| TR-23 | Arbeitsstand (§10.2): Der Translator meldet sich als ein Objekt (`translator:<modus>`), damit ein Shell-Wechsel ihn mitnimmt; beim Öffnen von Cockpit/Paperclip ohne Translator-Werkzeug gilt AM2-11 (Hinweis, kein Fehler). | Test mit `sedraStand` |

### 3.4 Verbindung Transkript → Übersetzer

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| TR-30 | „An den Übersetzer“ (`transkript/tool.js:154`) öffnet im Translator den Modus Übersetzen und übergibt den Text als neue `frage` – **auch wenn** der Übersetzer schon eingehängt ist. Weg: die App fängt `ctx.shell.open` für die eigenen vier Objekttypen ab und reicht `frage` an das eingehängte Werkzeug (oder hängt den Modus mit dem neuen Objekt neu ein, TR-E3). Außerhalb des Translators bleibt das Verhalten wie heute. | Browser-Test: Transkript öffnen, Übersetzer vorher offen, Klick, Übersetzer zeigt den neuen Text |
| TR-31 | Derselbe Fehler (B10) wird für den **einzelnen** App-Reiter `app:uebersetzung:wolke` behoben oder als bekannt vermerkt: Ein `open` mit neuer `frage` auf einen offenen Reiter darf nicht still verloren gehen (entweder ankommen oder Hinweis „schon offen – Text in die Zwischenablage“). | Test der Harness |
| TR-32 | Rekorder → Transkript („Transkript öffnen“, `rekorder/tool.js:190`) wechselt im Translator in den Modus Transkript und öffnet dort das neue Transkript. | Browser-Test mit Fake-Mikrofon (wie `test_uix_rekorder`) |
| TR-33 | Nur Text wandert, keine Datei, kein neuer Speicher; Inhaltsschutz und Audit wie heute (`FISCH_UEBERSETZT` ohne Text). | Code-Prüfung, Audit-Zeile |

### 3.5 Chat-Werkzeug `uebersetzen` (optional, TR-E4)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| TR-40 | Werkzeug `uebersetzen` für den Agenten: Eingabe `text` (≤ 6000 Zeichen) **oder** `pfad` (Datei im Projekt, Lesegrenze wie `datei_lesen`), dazu entweder `sprache` (die 8 aus `harness/uebersetzen.py:10`) oder `rolle` (die 6 aus `fisch/uebersetzer.py:7–14`) – genau eins. Sprache → `harness/uebersetzen.py`, Rolle → `fisch/uebersetzer.py`; beide über den Modellaufruf des Servers (Mission, Audit, Inhaltsschutz), kein zweiter Weg. | Einheitstests je Zweig, Attrappe des Modells |
| TR-41 | Wirkung: liest nur und antwortet; es **legt nichts ab**. Ablegen geht weiter über `datei_schreiben` (mit Karte). Damit läuft es ohne Karte (`OHNE_KARTE`), ist aber durch eine Regel `verboten` abschaltbar; Modell belegt → `modell_belegt`, kein Modell → `kein_modell`. | Test `test_freigabe_vollstaendig`, Einstufung |
| TR-42 | Pflicht-Einträge nach der Werkzeug-Regel: `SCHEMAS`, `vorbereiten`/`ausführen`, `HARNESS_WEGE`/`HARNESS_UNTERWEGE`/`ROUTEN_HARNESS`, Regex `WEG`/`GESCHUETZT` in `harness/api.py`, Katalog. Werkzeugergebnis ist Daten, nie Anweisung (HS-24). | `test_freigabe_vollstaendig`, Prompt-Test |

### 3.6 Gleichstand und alte Shell

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| TR-50 | `uix/shells/fisch/` bleibt unverändert (kein Byte), bis der Captain den Gleichstand abnimmt. `test_uix_shell_fisch` und `test_fisch_kern` bleiben grün. | `git diff --stat uix/shells/fisch` leer; Tests |
| TR-51 | Gleichstandsliste (Abnahme): alle Funktionen der Shell `fisch` laut `arbeitsplatz.yaml:4–14` und `README.md` – vier Modi, Wolke, Modus gemerkt, Strg+K, Nachweis-Spalte, Werkbank-Zeile, Gespräch (in One Sedra: das Gespräch selbst), Hinweise ohne Modell/ohne Mikrofon – sind in der App vorhanden oder begründet weggelassen (Fisch-Zeichnung). | Tabelle im Baubericht, Captain |
| TR-52 | Erst nach Abnahme: `fisch` als „eingefroren, Funktion in One Sedra“ kennzeichnen (README-Hinweis); Löschen ist eine eigene Entscheidung. | Captain |

## 4. Abnahme

1. Node-Tests: Manifest/Ort (TR-01), Modusliste gleich (TR-10), Reiter ohne `meter`-Sonderfall (TR-02).
2. Browser-Test an eigener Testinstanz (nie am laufenden Sedra): Wolke je Modus (TR-11), Zustand bleibt (TR-20), gemerkter Modus (TR-21), Transkript → Übersetzer bei offenem Übersetzer (TR-30), Rekorder → Transkript (TR-32).
3. Optional TR-40ff: Einheitstests mit Attrappe, `test_freigabe_vollstaendig` grün.
4. `test_uix_shell_fisch`, `test_fisch_kern`, `test_uix_rekorder`, `test_uix_harness_*` grün; `uix_check --shell harness`.
5. Gleichstandsliste (TR-51) vom Captain im echten Sedra durchgeklickt (nach Neustart + Strg+F5).

## 5. Reihenfolge (Vorschlag)

| Schritt | Inhalt | IDs |
|---|---|---|
| 1 | App-Reiter mit Unter-Reitern allgemein machen (aus `tokenReiter`), Paket `translator` mit vier Modi, Zustand je Modus | TR-01–03, TR-10, TR-20–22 |
| 2 | Wolke, Tasten, gemerkter Modus | TR-11–13, TR-21 |
| 3 | Übergaben Transkript → Übersetzer, Rekorder → Transkript; Fehler B10 im Einzelreiter | TR-30–33 |
| 4 | Arbeitsstand, Gleichstandsliste, Browser-Test | TR-23, TR-50–51 |
| 5 | (optional) Chat-Werkzeug `uebersetzen` | TR-40–42 |

Abhängig: nichts Neues im Kern. U12 (Manifest v1.1, `profile:`) kann später `profile: [standard, privat, stick]` am Paket nachtragen; U2 wartet nicht darauf. U13 (App-Rahmen) berührt `app.js` – nicht gleichzeitig mit Schritt 1 bauen.

## 6. Offene Entscheidungen (mit Vorschlag)

| Nr | Frage | Vorschlag |
|---|---|---|
| TR-E1 | Modus-Reiter: eigenes Paket `translator` oder allgemeines Feld im App-Rahmen (`reiter:` im Manifest, das mehrere Objekte zu einer App bündelt)? | **Paket `translator`** mit Reiterliste im Code jetzt; das allgemeine Feld erst mit U13 (A2), dann wird `meter` mit umgestellt. |
| TR-E2 | Einzel-Apps Übersetzer, Nachrichten, Rekorder, Transkripte zusätzlich im Start-Menü lassen? | **Nur Translator im Menü**, Einzel-Apps über Suche und Chat-Ort erreichbar (Rekorder bleibt zusätzlich in der Taskleiste, `shell.yaml:35–37`). |
| TR-E3 | TR-30: `frage` ins eingehängte Werkzeug reichen (braucht eine kleine Methode `frage(text)` im Werkzeug) oder Modus neu einhängen (verliert Zustand dieses Modus)? | **Neu einhängen nur des Übersetzers** (kein Vertragswechsel, Zustand der anderen drei bleibt); `frage()`-Methode erst, wenn es stört. |
| TR-E4 | Chat-Werkzeug `uebersetzen` jetzt oder später? Sprache, Rolle oder beides? | **Später als Schritt 5, beides** (ein Werkzeug, zwei Zweige); vorher W1 (U10) abschließen. |
| TR-E5 | Name „News-Profil“ vs. Oberflächen-Profil (B14)? | Im Werkzeug Nachrichten „**Interessen**“ statt „Profil“ anzeigen; Datei und Route bleiben. |
| TR-E6 | Ab wann gilt die alte Shell `fisch` als ersetzt? | Nach Abnahme TR-51 durch den Captain; bis dahin unverändert, danach eingefroren (nicht gelöscht). |
