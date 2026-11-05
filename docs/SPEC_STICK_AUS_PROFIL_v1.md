# SPEC Stick aus Profil v1 – G1 Anforderungen (05.11.2026)

Stand: `main` `d51083a`. Gate **G1**; G2/G3 erst nach Freigabe. Unterchat **U8** (Phase R6, Stufe A9, UIX X3). Braucht U1 (Inventur, liegt vor) und U4 (`SPEC_PROFILE_v1.md`).
Grundlage: Beschlüsse des Captains vom 05.11.2026 – One Sedra ist die Zentrale; „Minimal-Stick mit 4 Shells“ wird **Profil „Stick“ von One Sedra** (`ROADMAP_ONE_SEDRA_APPS_KERN_SHELL_2026-11-05.md` §2, A9); Wissen ist Grundfunktion; nur eigene Pakete. Die Entscheidungen zum Stick vom 30./31.10. gelten weiter (`docs/ENTSCHEIDUNGEN_USB_STICK.md`), soweit dieser Beschluss sie nicht ändert.
Pfade relativ zu `runtime/src/guppi_runtime/`, sonst ab Repo-Wurzel.

**Ergebnis in einem Satz:** Der Paketbau für den Stick ist schon auf `main` (Liste, Importhülle, Manifest, relative Modellordner, Tests), aber die Liste ist **von Hand** und nach Shells geschnitten: sie bringt vier Oberflächen, von denen nur zwei tragen, und lässt Grundfunktionen (Posteingang, Aufgaben, Wissen) als Apps weg. Ziel: Die Liste entsteht aus dem Profil „Stick“ (Apps mit `profile: [stick]` + Grundfunktionen), nur One Sedra kommt mit, Wissen läuft dort im Volltext.

## 1. Befund

### 1.1 Stand des Stick-Baus

| Nr | Befund | Beleg |
|---|---|---|
| B1 | **Paketbau ist auf `main`:** `stick_paket.py` (Liste lesen, Python-Importhülle per AST, Kopie ohne Verknüpfungen, `STICK_MANIFEST.json`, `--pruefen`), Liste `stick_liste.txt`, relative Modellordner in `local_paths.py`, Tests `test_stick_paket.py` (4 Fälle) und `test_local_paths.py`. | `runtime/benchmarks/stick_paket.py:1–11, 58–77, 183–189`; `runtime/benchmarks/stick_liste.txt:1–41`; `local_paths.py:22, 37–44`; `runtime/tests/test_stick_paket.py:33–61` |
| B2 | **Branch `claude/usb-stick-minimal-3c1b19` ist in diesem Repo nicht sichtbar** (lokale Branches: `main`, `claude/wissen-kern-k1`, Worktree-Branches; Verlauf hier nur 1 Commit). Laut Wissensdatei liegt er nur auf dem Bau-PC, 5 Commits, nicht gepusht; laut Prüfung vom 02.11. 17 Commits hinter `main`. Ob alle seine Inhalte auf `main` sind, ist **offen** (Vermutung: Plan, Paketbau, Liste, `local_paths` ja – sie liegen hier; Stick-eigene `model_profiles.yaml` nein, sie liegt nur auf K:). | `git branch -a` (diese Sitzung); `docs/WISSENSDATENBANK_USB_STICK_CHAT.md:34–38`; `docs/PRUEFUNG_STICK_SHELLS_2026-11-02.md:29–30`; `docs/PLAN_USB_STICK_MINIMAL.md:131` |
| B3 | `docs/PLAN_USB_STICK_v1.md` ist **nicht im Repo** (nur `PLAN_USB_STICK_MINIMAL.md`); es steht als Projekt-Dokument `claude/PLAN_USB_STICK_v1.md` im Claude-Projekt und war in dieser Sitzung nicht lesbar. Abgleich **offen**. | Dateisuche `docs/PLAN_USB_STICK*` (ein Treffer) |
| B4 | Die Liste ist **nach Shells** geschnitten: `cockpit`, `harness`, `paperclip`, `fisch` + Werkzeuge `uebersetzer`, `nachrichten`, `transkript`, `rekorder`. Kein Werkzeug `decisions`, `task`, `wissen`, keine `gauge-*`. | `runtime/benchmarks/stick_liste.txt:22–25, 33–36` |
| B5 | **Probe 02.11.:** Start ohne `--shell` scheitert („Keine Shell verfügbar: start“); in One Sedra nur 5 Apps statt 40; Zellen GPU, RAM, Scheduler, Zustand führen auf „kein Werkzeug“; Cockpit meldet `400` auf `/api/objects`, Paperclip zeigt Einträge ohne Werkzeug. **Nur Harness und Translator tragen.** | `docs/PRUEFUNG_STICK_SHELLS_2026-11-02.md:12–20, 24–26` |
| B6 | Ein fehlendes Werkzeug fällt erst im Gebrauch auf: Shell-Manifeste nennen keine Werkzeuge (`needs` kennt nur `ui`). | `docs/PRUEFUNG_STICK_SHELLS_2026-11-02.md:21`; `desk/gateway.py:63–64` |
| B7 | Stick-Stand 31.10.: 734 Dateien, 781 499 521 Byte (Stand `c1a9d29`), Engine `b11160` geprüft, portables Python grün, 7 Modelldateien 40,49 GiB; **Modellstart über SEDRA nicht versucht**; Nemotron nach Reparatur nicht neu gestartet. | `docs/PLAN_USB_STICK_MINIMAL.md:116–147`; `docs/WISSENSDATENBANK_USB_STICK_CHAT.md:66–68, 104–106` |
| B8 | Weitergabe an den Kollegen erst nach **Signatur** der Releases (Entscheidung B2, 03.11.); Werkzeug „System“ (Updates) nicht in der Liste. | `docs/PLAN_USB_STICK_MINIMAL.md:109` |
| B9 | Stick ist laut AM7 der **Pilot** für Betriebsart A (Richtlinie als Datei auf dem Stick, nicht über SEDRA änderbar). | `docs/SPEC_APPS_v1_AM7_UNTERNEHMEN.md:21–23` |
| B10 | `fenster/rekorder.html` fehlt im Repo; der Rekorder läuft ohne eigenes Fenster als Werkzeug. | `docs/PLAN_USB_STICK_MINIMAL.md:101`; `docs/STICK_VORSCHLAEGE_PUNKTE_5_7_2026-11-01.md` §6 |

### 1.2 Wissen auf dem Stick

| Nr | Befund | Beleg |
|---|---|---|
| W1 | Die Suche hat einen **Volltext-Rückfall** (FTS5/BM25): läuft kein Einbett-Dienst, gibt es keinen Anfrage-Vektor oder zu wenig Abdeckung, ist `modus: volltext` mit Hinweis; Audit `WIS_RUECKFALL_VOLLTEXT`. Die Suche startet nie selbst einen Server und wartet nie. | `wissen/suche.py:1–3, 57–61, 64–65, 100–117, 129` |
| W2 | Einbetten braucht einen eigenen `llama-server --embeddings` (CPU, Port 8094) und ein Modell (Beispiel `bge-m3-q8_0.gguf` unter `<modelle>`); fehlen Engine oder Modell, meldet der Dienst `wis_engine_fehlt` / `wis_modell_fehlt`. | `runtime/config/wissen.yaml:4–5, 12–19`; `wissen/embed.py:130–133` |
| W3 | Kein Einbett-Modell steht in der Stick-Modellliste (nur Bonsai, Nemotron, Qwen3.6, Qwen3.5-9B, Gemma). → Auf dem Stick gibt es **nur Volltext**. | `docs/ENTSCHEIDUNGEN_USB_STICK.md:18–27`; `docs/PLAN_USB_STICK_MINIMAL.md:46–52` |
| W4 | Ohne antwortenden Dienst setzt die Suche den Grund `server_startet` und stößt einen Start an; auf dem Stick ohne Modell ist dieser Hinweis **vermutlich irreführend** (Start schlägt mit `wis_modell_fehlt` fehl, der Nutzer liest „Server startet“). *Nicht gelaufen.* | `wissen/suche.py:103–107`; `wissen/embed.py:132–133` |
| W5 | Die Python-Module `wissen/` kommen vermutlich über die Importhülle mit (Importe in Funktionen von `uix_server.py` und `runtime.py`; `ast.walk` erfasst auch diese). Das Werkzeug `uix/tools/wissen` (Oberfläche) fehlt in der Liste. *Folgt aus dem Code, `--pruefen` nicht gelaufen.* | `uix_server.py:2001, 2198, 2229, 2261`; `runtime.py:203–205`; `runtime/benchmarks/stick_paket.py:80–97`; B4 |

## 2. Ziel und Nicht-Ziel

**Ziel:** Ein Stick-Paket, das **aus dem Profil „Stick“** gebaut wird: Kern + One Sedra + alle Apps mit `profile: [… stick …]` + alle Grundfunktionen (Posteingang, Aufgaben, Wissen, Einstellungen …) + deren Werkzeuge, ohne weitere Shells. One Sedra startet auf dem Stick direkt mit dem Profil „Stick“. Wissen läuft im Volltext, ehrlich gekennzeichnet. Der Bau prüft vorher, dass jede sichtbare App ihr Werkzeug mitbringt.

**Nicht-Ziel:**
- Modelle, Engine, portables Python neu regeln (Entscheidungen 30./31.10. gelten; `bestand`-Zeilen bleiben).
- Einbett-Modell auf den Stick bringen (Vorschlag ST-E3: später), Downloads, Läufe auf der GPU.
- Richtlinie/Rollen bauen (AM7/U6); hier nur der Platz dafür.
- Signatur der Releases (eigene Entscheidung B2); Updater auf dem Stick.
- Cockpit, Paperclip, Translator-Shell `fisch` auf dem Stick (ersetzt durch Apps in One Sedra; siehe ST-E1).
- Schreiben auf K:\ in diesem Unterchat (nur nach Ja des Captains, wie bisher).

## 3. Anforderungen

### 3.1 Liste aus dem Profil

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| ST-01 | `stick_paket.py` bekommt eine Quelle `profil <art>` (Zeile in `stick_liste.txt`, z. B. `profil stick`): sie nimmt alle Werkzeuge, deren `tool.yaml` `profile:` die Art enthält, **plus** alle Werkzeuge mit `grundfunktion:` (AM2-13) bzw. aus der Grundfunktionsliste (U4 PR-11). Je Werkzeug der ganze Ordner `uix/tools/<id>/`. | `test_stick_paket`: Testbaum mit drei Werkzeugen, eines mit `profile: [stick]`, eines Grundfunktion, eines ohne → genau zwei im Plan |
| ST-02 | Shells: nur `uix/shells/harness/` (One Sedra). Die Zeilen `cockpit`, `paperclip`, `fisch` fallen aus der Liste, sobald Translator (U2) als App da ist (ST-E1). | Listentest, `--pruefen` |
| ST-03 | Python-Module der Apps kommen über die Importhülle; was ein Werkzeug nur per Route braucht (z. B. `fisch/`, `sprache/`, `wissen/`), steht als `modul`-Zeile oder wird aus den `api:`-Routen der Manifeste abgeleitet (ST-E2). | `--pruefen` meldet keine fehlenden Module; Test |
| ST-04 | **Vollständigkeit vor dem Kopieren:** `--pruefen` bricht ab, wenn (a) ein Ort des Profils kein Werkzeug im Paket hat, (b) eine Zelle der Taskleiste im Profil sichtbar ist, deren `gauge-*` fehlt, (c) eine Grundfunktion kein Werkzeug hat. Ausgabe: Liste „fehlt: …“. | Test mit absichtlich fehlendem Werkzeug |
| ST-05 | Das Manifest `STICK_MANIFEST.json` nennt zusätzlich `profil` (Art und ID), die Liste der Apps und die Grundfunktionen; Prüfsummen wie heute (A9: „Prüfsummen stimmen“). Stick-eigene Konfigurationsdateien (`model_profiles.yaml`, `local_paths.yaml`, `uix.yaml`, Profil) stehen mit Hash im Manifest (heute fehlt `model_profiles.yaml`, B7). | Test, Manifest-Vergleich |
| ST-06 | Keine Verknüpfungen, kein `local_config/` aus dem Repo, keine PC-Pfade (bleibt wie `stick_paket.py:24–25`, `PLAN …:60–68`). | bestehende Tests |

### 3.2 Profil „Stick“ und Start

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| ST-10 | Das Profil „Stick“ ist die **Vorlage** aus U4 (PR-33) im Format `sedra-profil` v1; der Bau legt es als `runtime_data/harness/profile/stick.json` und als gültige Wahl (`desktop.json` mit `profil: stick`) in den Arbeitsbereich des Sticks. | Test: Paket enthält beide, `desktop.laden` liefert `profil == 'stick'` |
| ST-11 | Inhalt (Vorschlag, Abgleich mit U4): Gespräch, **Translator** (U2), **Wissen** (Volltext), Posteingang, Aufgaben, Einstellungen (Modell laden, Info), Rekorder; Taskleiste nur Zellen mit Werkzeug im Paket (Freigaben, Modell, Temp/VRAM/RAM, wenn `gauge-*` dabei); Startseite leere Sitzung. | Vorlagen-Test, `--pruefen` (ST-04) |
| ST-12 | Start: `START_SEDRA.bat --gewaehlt` und der Start **ohne** Argument öffnen One Sedra (nie die fehlende Shell `start`, B5). Lösung über `uix.yaml` des Sticks (`shell: harness`) **und** Rückfall des Servers auf die erste vorhandene Shell, wenn die gewünschte fehlt (Vorschlag a aus der Prüfung 02.11.). | Startprobe aus dem Paket (wie Prüfung 02.11., Playwright), kein „Keine Shell verfügbar“ |
| ST-13 | Das Profil kann auf dem Stick gewechselt, aber eine Grundfunktion nie ausgeblendet werden (U4 PR-11). | Test |

### 3.3 Wissen nur mit Volltext

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| ST-20 | Wissen ist auf dem Stick da (Werkzeug `uix/tools/wissen` und `wissen/` im Paket, Grundfunktion) und sucht **ohne Einbett-Modell im Volltext**; die Antwort trägt `modus: volltext`. | Test aus dem Paket: Quelle aufnehmen, suchen → Treffer, `modus == 'volltext'` |
| ST-21 | Fehlt das Einbett-Modell (oder die Engine), versucht der Stick **keinen** Start des Einbett-Dienstes bei jeder Suche; der Hinweis sagt „Volltext – kein Einbett-Modell auf diesem Rechner“ statt „Server startet“ (W4). Einmal je Sitzung Audit `WIS_RUECKFALL_VOLLTEXT {grund: modell_fehlt}`. | Test mit Konfiguration ohne `modell`; Audit-Zeile |
| ST-22 | Aufnahme von Quellen (Zerlegen, FTS-Index) läuft ohne Modell; das Einbetten wird übersprungen und als „ausstehend“ vermerkt, damit ein späteres Modell nachziehen kann. | Test |
| ST-23 | Keine Netz- oder Cloud-Wege für Wissen auf dem Stick (Inhaltsschutz wie heute). | Code-Prüfung, bestehende Tests |

### 3.4 Abgleich mit dem bisherigen Plan und dem Branch

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| ST-30 | Vor dem Bau: Branch `claude/usb-stick-minimal-3c1b19` auf dem Bau-PC gegen `main` vergleichen (`git log main..<branch>`, `git diff main...<branch> --stat`); jede Datei als **eingearbeitet** (schon auf `main`), **übernehmen** oder **verwerfen** in eine Tabelle im Baubericht. Danach ist der Branch abgelöst (U8-Ziel). | Tabelle im Baubericht; Captain |
| ST-31 | `PLAN_USB_STICK_MINIMAL.md` bekommt einen Kopf „§3.1 Umfang ersetzt durch `SPEC_STICK_AUS_PROFIL_v1`“; §3.2–§10 (Modelle, Pfade, Stand K:) gelten weiter. `PLAN_USB_STICK_v1.md` (Projekt-Dokument) wird abgeglichen, sobald lesbar. | Doku |
| ST-32 | Offene Punkte des Plans bleiben offen und werden nicht still erledigt: Nemotron vom Stick neu starten, SHA-256 von Gemma/Qwen3.6, Modellrezepte, zweiter PC ohne Netz, 8-GB-Abnahme, `fenster/rekorder.html`. | Liste im Baubericht |

## 4. Abnahme

1. `test_stick_paket` mit den neuen Fällen (ST-01, -04, -05, -10) grün; `test_local_paths` grün.
2. Probe wie am 02.11.: Paket aus `main` mit `profil stick` ohne `bestand`-Zeilen bauen, Server aus dem Paket mit leerem Arbeitsbereich, Playwright: One Sedra öffnet ohne Argument (ST-12), jede App des Profils öffnet ein Werkzeug (keine „kein Werkzeug“-Fläche), Wissen findet eine Quelle im Volltext (ST-20, -21).
3. `--pruefen` gegen den Bau-PC: Dateizahl und Summe im Bericht, Vergleich zu 734 Dateien / 781 MB vom 31.10.
4. Erst nach Ja des Captains: Schreiben auf K:\, Start mit `--gewaehlt`, Modellstart (Basis) mit Antwortprüfung.

## 5. Reihenfolge (Vorschlag)

| Schritt | Inhalt | IDs | braucht |
|---|---|---|---|
| 1 | Branch-Abgleich auf dem Bau-PC (nur lesen) | ST-30 | Captain/Bau-PC |
| 2 | Wissen ohne Einbett-Modell ehrlich (Hinweis, kein Startversuch) | ST-20–23 | – (unabhängig, `wissen/`) |
| 3 | `--pruefen` mit Vollständigkeit; Profil-Quelle in `stick_paket.py` | ST-01, -03, -04, -05 | U12 (`profile:` im Manifest) für ST-01; ST-04 geht vorher |
| 4 | Profil „Stick“ als Vorlage einlegen, Start auf One Sedra | ST-10–13 | U4 Schritt 1+4 |
| 5 | Shells aus der Liste nehmen | ST-02 | U2 abgenommen |
| 6 | Probe aus dem Paket, Bericht; dann K:\ nur nach Ja | Abnahme | 1–5 |

## 6. Offene Entscheidungen (mit Vorschlag)

| Nr | Frage | Vorschlag |
|---|---|---|
| ST-E1 | Kommen Cockpit, Paperclip und die Shell `fisch` noch auf den Stick? | **Nein**, nur One Sedra; `fisch` bleibt so lange in der Liste, bis U2 abgenommen ist (sonst fehlt der Translator). Cockpit/Paperclip sofort raus (tragen nicht, B5). |
| ST-E2 | Python-Module der Apps: von Hand als `modul`-Zeile oder aus den `api:`-Routen der Manifeste ableiten? | **Von Hand** in v1 (drei Zeilen: `fisch`, `sprache`, `wissen`), plus Prüfung ST-04; Ableitung erst, wenn fremde Apps kommen. |
| ST-E3 | Einbett-Modell (z. B. bge-m3, CPU) auf den Stick? | **Nicht in v1** – Volltext reicht für den Piloten; nach Messung am Stick (32 MB/s Lesen) neu entscheiden. |
| ST-E4 | Gehört die Richtlinie (AM7-Pilot) schon auf diesen Stick? | **Nein**, nur der Platz (`local_config/` leer); Richtlinie mit U6. Weitergabe an den Kollegen ohnehin erst nach Signatur (B8). |
| ST-E5 | Ein Profil „Stick“ für alle Sticks oder je Empfänger eine Kopie (Marke, Name)? | **Vorlage „Stick“** + je Empfänger ein eigenes Profil aus ihr (U4-Export/-Import); der Bau nimmt die Profil-ID als Argument (`--profil <id>`, Vorgabe `stick`). |
| ST-E6 | Was passiert mit dem Branch `claude/usb-stick-minimal-3c1b19` nach dem Abgleich? | Nach ST-30 **nicht löschen**, nur als abgelöst vermerken; Löschen entscheidet der Captain. |
