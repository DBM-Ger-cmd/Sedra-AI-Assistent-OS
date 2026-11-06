# SEDRA / GUPPI – Wissensdatei (alle Chats zusammengeführt)

Stand: 31.10.2026. Quellen: Gedächtnisdateien von Claude (Memory), die Sitzungsliste des Cockpits (alle Chats, auch archivierte), das Logbuch `docs/LOGBUCH_AGENT_MANAGER.md`, der Git-Verlauf (527 Commits auf `main`) und der Arbeitschat vom 27. bis 31.10.2026. Kein Inhalt ist erfunden; was nur vermutet ist, steht als Vermutung da. Der Captain ist der Nutzer (David); er entscheidet alle Freigaben.

## 1. Was SEDRA ist
- SEDRA/GUPPI: lokales KI-Betriebssystem mit Cockpit-Oberfläche (UIX), Agenten-Orchestrierung (Orchestra), Modell-Scheduler, Freigabe-Prinzip („Captain entscheidet“, Guard, Gates) und lokalen Modellen (llama-server).
- Repo `DBM-Ger-cmd/Sedra-AI-Assistent-OS`. Hauptumgebung A1: `E:\Sedra Umgebung\A1 Sedra Main Branch Entwicklungs umgebung`, Zweig `spec/agenten-orchestrierung`; `main` steht auf demselben Commit.
- Seit 31.10.2026: Minimal-/USB-Stick-Version wird in `E:\Sedra Umgebung\Sedra Test umgebung für Minimale USB Stick Version` entwickelt und getestet. A1 bleibt die Hauptumgebung der PC-Version (Stable). Ohne Rückfrage nichts verschieben, kopieren oder umbenennen.
- Modelle: `I:\KI-Daten\modelle` (seit 29.10.2026; vorher `E:\HermesAgentOrdner\lokale-modelle`).

## 2. Zeitachse
| Datum | Was |
|---|---|
| 20./21.10. | „Linie“ Bauwerkzeuge vereinheitlichen (L1–L3), Pipeline (PIPE-06/07/09/10/12), Spec 0 Kern-API, Spec 1 Orchestrierung (Design → G2, Bau-Specs s1_* → G3), Spec 4 Shell D (Design, Bau). |
| 22.10. | Spec 1 Harness S1.H7/H8 (Desk-Verben, Runner, Dauerfreigabe), Spec 3 Cloud/GateWay, Spec 7 Wissen/Goldsatz (Messplan). |
| 24./25.10. | Spec 7 Abnahmesatz/Goldsatz, Spec 2 Modelle & Scheduler (Abgleich → G1), Spec 2 Harness S2.H1/H3/H4a, Umstiegsplan, Spec 7 Cloud-Auflagen. |
| 26.10. | S2.H5 Router-Haken, Werkstatt, Slots-Schnappschuss; Index und Plan zum Zusammenlegen von `E:\Sedra Umgebung`. |
| 27.10. | Freigabe-Härtung; UIX-Paket Stufe 1–6 mit Mini-Hub gemergt; 3D-Lauf-Skript `benchmarks/nachtlauf_3d.py`; 6-Stunden-Dauerlauf (15:53–21:53). |
| 28.10. | Auswertung des 6h-Laufs; Härtungslücken, Rekorder mit PC-Ton; Harness Stufe 1 und 2 übernommen; Kurs-Präsentation. |
| 29.10. | Modelle nach `I:\KI-Daten\modelle`; Harness Stufe 3 (Plan, Bau, Cloud-Sitzung); C-Laufwerk aufgeräumt. |
| 30.10. | Harness Stufen 3–6 und Dynamische Rezepte R1–R5 auf `main`/GitHub; R6 mit Modell gelaufen; UIX-Härtungsrunde E1–E4 übernommen. |
| 31.10. | USB-Stick-Version auf `K:\` (Sitzungen laufen), Arbeitsumgebung für Minimal angelegt. |

## 3. Architektur in Stichpunkten
- **Desk/Cockpit/UIX:** Server `guppi_runtime.uix_server`, mehrere Shells (cockpit, minimal, paperclip, start, harness, fisch, gateway-kmu), Werkzeuge unter `uix/tools/*`. Werkzeuge rufen nur `ctx.api()` auf und nutzen kein `fetch` und kein `localStorage` (Vertrags-Test `test_uix_contract`); Speichern ist Sache der Shell.
- **Orchestra:** Agenten (Leitung `foreman`, Recherche `researcher`), Aufgaben, Weckrufe (`wakeups`, Ausgang u. a. `antrag`, `lauf`, `abgelehnt`), Heartbeat, Anträge über `desk/gated.py` und `desk/orchestra_kinds.py` (Applier mit `binding_stale`).
- **Freigaben:** Jeder Lauf braucht eine Einzelfreigabe, außer bei einer Dauerfreigabe (Art `standing`, Token genau einmal). Ein Antrag ist an einen Stand gebunden (Revision/Fingerabdruck); ändert sich der Stand, endet er mit `binding_stale`.
- **Modell-Scheduler:** `ResourceScheduler`, Slots, Rezepte in `workspace/GUPPI_OS/local_config/role_routing.yaml` (nicht in Git). Dynamische Rezepte R1–R6: Block `profile.dynamisch`, `models/aufteilung.py`, Messspeicher `runtime_data/model_messwerte.json`.
- **Harness-Shell** (SPEC_HARNESS_SHELL_v1): Gespräch, Streamen, Sitzungen, Taskleiste (Stufe 1); Werkzeuge, Freigabe-Katalog, Karten, Überschreib-Warnung (Stufe 2); danach Klartext der Aufgaben, Projekte, Vorschau, Modell laden im Eingabebereich, Dateien anhängen mit `+` und `@`.
- **SEDRA baut selbst:** Bau über den Vorarbeiter (`devvm_build`), Claude schreibt Spec, Referenz und versteckte Prüfungen und prüft den Kandidaten. Scheitert der Bau → V4: Referenz bleibt, Befund ins Logbuch.
- **Aufnahme (Sprache):** `sprache/kern.py` (16 kHz, mono, 16 Bit, WAV), Quelle wählbar: Mikrofon (`sounddevice`) oder PC-Ton (WASAPI-Loopback über `PyAudioWPatch`); Route `POST /api/sprache/kern/start {titel, sprache, quelle}`.

## 4. Messergebnisse und Befunde
- **GPU/Treiber:** Ohne NVIDIA-Debug-Modus gab es seit 24.10. Treiber-Zurücksetzungen (nvlddmkm 13/153, LiveKernelEvent 141) und llama-server-Abbrüche. Mit Debug-Modus: 30 Minuten und 6 Stunden stabil (VRAM konstant ca. 9,2–9,3 GiB, max. 72 °C). Der Browserfehler `ERR_NO_BUFFER_SPACE` ist getrennt davon (Windows-Socket-Puffer).
- **6h-Lauf 27.10.:** Keine Modellabbrüche, 88 % der 3D-Objekte; die 88 % sagen nur, dass das Modell acht einfache Formen sauber wiederholt (Vase scheitert öfter). Zur Konstruktionsfähigkeit sagt der Test wenig.
- **Recherche-Fehler (behoben 27.10.):** Zweite Weckrufe hängten sich an einen wartenden Antrag und blieben nach der Entscheidung für immer auf `antrag`; leere Adressen aus dem Hilfsmodell (`research_invalid:urls`). Behoben in `heartbeat.finish`, `pending_request`, `runner.outcome`.
- **Nemotron E4B Q4_K_M:** Abnahme nicht bestanden (C2, C4), ohne Rolle. Nemotron ignorierte Werkzeugergebnisse. Der Nemotron-3.5-Bolt-Test (lmstudio-community, Q6_K) steht aus, weil die Modelldatei fehlt.
- **Qwen3.6-35B-A3B** bleibt Standard-Coder. R6 (30.10.): 28 Lagen, Kontext 65536, VRAM gemessen ca. 8,4 GB gegen 10,5 gerechnet; 40 Lagen starten nicht (CUDA OOM, vermutlich RAM).
- **Hauptmodell** wird bei weniger als ca. 13 GB freiem RAM abgelehnt; ein laufendes Spiel (Mechabellum) blockierte das einmal.
- **Lehre aus SEDRA-Bauten:** Versteckte Prüfungen müssen Rückgabewerte prüfen; Qwen als Vorarbeiter erfindet Lauf-IDs und muss ausdrücklich zum Werkzeugaufruf aufgefordert werden; nach `devvm_build` ist das Gespräch ohne Modell (neu laden).

## 5. Arbeit im Chat vom 27.–31.10.2026 (Claude Code)
- Härtungslücken geschlossen (Commits `4167068`, `0772140`): Scheduler-Poll startet mit dem Server statt erst mit dem Browser (B7); `unknown_decision`/`way_not_offered` zeigen einen deutschen Satz (`FRIENDLY_400`, Feld `code`); ein veralteter Wecken-Antrag (`binding_stale`) schließt jetzt seinen Weckruf (`abgelehnt`); `known_red.txt` bereinigt.
- Rekorder mit wählbarer Quelle (`78f08fb`, `e7c67fe`): Mikrofon oder PC-Ton; Live-Test mit abgespieltem Ton ergab echtes Signal. Die Auswahl wird nicht gespeichert (Werkzeuge dürfen kein `localStorage`).
- Startfehler `UnicodeDecodeError` (cp1252, Byte 0x81) in der Prozessliste behoben: PowerShell gibt UTF-8 aus und Python liest UTF-8 (`models/gpu_preflight.py`). Vorher blieb ein altes Cockpit unerkannt.
- Kurs-Präsentation `docs/KURS_PRAESENTATION_SEDRA.md` (14 Folien) durch eigene Sitzung; ihre Zahlen sind noch nicht gegen das Logbuch geprüft.
- **Arbeitsumgebung Minimal (31.10.):** Sedra A1 bleibt Hauptumgebung für die PC-Version (Stable). Für Entwicklung und Test der Minimal-Version gibt es `E:\Sedra Umgebung\Sedra Test umgebung für Minimale USB Stick Version`. Dorthin wurde die Minimal-Version von `K:\SEDRA` kopiert (752 Dateien, 44,26 GB, ohne `_speedtest_tmp.bin`; Anzahl und Größe stimmen überein). Arbeitsweg: auf E entwickeln, auf K testen; Änderungen müssen vor dem Test auf K übertragen werden (nur auf Ansage). Modelle liegen weiterhin unter `I:\KI-Daten\modelle`. Die Kopie auf K enthält 40,5 GB Modelle unter `modelle`.

## 6. Fallen und Praxiswissen
- **Zwei Python-Umgebungen:** Das Cockpit läuft in `runtime\.venv` (Python 3.14), das System-Python hat mehr Pakete. `sounddevice` fehlte in der venv (jetzt 0.5.6 und `PyAudioWPatch` dort installiert); `numpy` fehlt in der venv, deshalb überspringt der Runner `test_sprache_kern` – direkt starten: im Ordner `runtime/tests` `PYTHONPATH=../src python -m unittest test_sprache_kern`. Stand 30.10.: die Test-Attrappe `_kern_fake` braucht kein numpy mehr.
- **Tests:** Im Ordner `runtime` `PYTHONIOENCODING=utf-8 python benchmarks/run_tests.py scheduler desk orchestra uix`; Browser-Bahn nur mit `--slow`. Bekannt rote Tests in `runtime/tests/known_red.txt` (derzeit `test_uix_flows…Build24…workplace_answers`).
- **Git:** `main` nachziehen: `git branch -f main HEAD`, `git push origin spec/agenten-orchestrierung:refs/heads/main` (nie force). Push, Merge nach `main`, Löschen von Worktrees/Branches und das Beenden fremder Prozesse nur auf ausdrückliches Ja. Commit-Anhang `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Logbuch** `docs/LOGBUCH_AGENT_MANAGER.md`: Zeilen `| Datum Zeit | TYP | Text | OP-S2-18 |` unten anhängen, CRLF-bewusst (mit `newline=''` lesen/schreiben).
- **Heredocs im Bash-Tool** verfälschen Backslashes und `\x00` in Python-Strings; Dateien mit Write/Edit schreiben.
- **Cockpit ohne Fenster starten:** `PYTHONPATH=src python -B -u -m guppi_runtime.uix_server --root workspace/GUPPI_OS --architecture architecture/GUPPI_Architecture_v1.20_SELF_DEVELOPMENT --port 8765` (URL mit Token steht in der Ausgabe, Header `X-GUPPI-Token`). `START_SEDRA.bat cockpit --replace` beendet vorher alle laufenden SEDRA-Server; der Start meldet sonst „SEDRA läuft bereits“.
- **Worktree-Bau** (`devvm_build`) braucht `runtime/config/local_paths.yaml` (Kopie, gitignoriert) und `engines` (Junction auf A1; mit `rmdir` entfernen, nie rekursiv löschen), sonst `llama_server_not_found`/`engine_not_installed`.
- **`per_slots`-Werte** im Rezept müssen auf den `tiers` liegen, sonst wird die ganze `role_routing.yaml` ungültig; `server.slots > 1` ohne `per_slots` → `slots_not_measured`. Inhaltsschutz ohne bestätigten Modus ist scharf → Harness zeigt keinen Live-Text.
- **llama-server** überlebt das Beenden des Cockpits und hält VRAM/RAM; am Ende mit `nvidia-smi` prüfen (Beenden nur mit Ja).
- **Stille Aufnahme?** Erst Mikrofon-Stummschaltung/Headset prüfen; die Windows-Mikrofonfreigabe war erlaubt. Der PC-Ton liefert nur, solange etwas abgespielt wird.
- Der Auto-Modus sperrt zusammengesetzte Befehle mit `branch -D` und Remote-Löschen: einzeln ausführen. Die Bash/PowerShell-Prüfung fällt manchmal aus; erneut versuchen.

## 7. Arbeitsweise des Captains
Deutsch, kurz, Ergebnis zuerst, Zahlen belegen, Unsicheres als Vermutung kennzeichnen. Nach Messläufen: Logbuch, Commit, `main` nachziehen, dann berichten. Unbeaufsichtigte/lange Läufe, Downloads und Freigaben nur auf ausdrückliches Ja; Berechtigungen zu Beginn einer Aufgabe gesammelt abholen. Entwicklung zuerst als Spec (G1 Anforderungen, G2 Design, G3 Bau), jedes Gate entscheidet der Captain; Entscheidungsfragen mit Vorschlag stellen. Oberfläche: wo gehandelt werden kann, steht die Handlung selbst, kein Verweis. Der Captain testet am Ende selbst im Cockpit; vorher Browser-Abnahme mit Playwright (`harness_abnahme.py --stufeN`, `uix_check`). Bei langem Kontext lagert er Arbeit in eigene Sitzungen aus und macht `/clear`.

## 8. Offene Punkte (Stand 31.10.2026)
1. **Nemotron-Test:** Modelldatei fehlt; Download nur mit Ja; die Sitzung `lauf-und-nemotron` wartet auf zwei Klicks im Cockpit.
2. **Wiederholungs-Deckel:** Soll eine Dauerfreigabe Wiederholungen derselben Aufgabe decken (wie viele)? Entscheidung des Captains.
3. **Dynamische Rezepte:** Tempo je Lagenzahl und Laden bei knappem Speicher nicht gemessen; `kv_cache_gb_per_1k_tokens` (0,0125 GiB/1k) noch nicht im Rezept; LibreHardwareMonitor nicht gestartet.
4. **Harness:** `harness.nemotron_e4b` `per_slots` ungemessen; 18 hängende Chat-Sitzungs-Missionen; Web-Browser-Spec (WBQ-3, WBQ-6, WBQ-7) und Wunsch-Anbindung G2 warten auf Entscheidungen.
5. **Alt:** Freigabe-Antrag „Agent Leitung Betriebsstunde (foreman) an T-6206f857dda4“ im Posteingang (Altbestand?); „kindi“ auf GitHub nicht gefunden (Link/Autor nötig); Cockpit-Test `test_k5`/Docktest wackelt unter Last.
6. **Minimal/USB:** Die Minimal-Version liegt auf `E:\Sedra Umgebung\Sedra Test umgebung für Minimale USB Stick Version` (Kopie von `K:\SEDRA` vom 31.10.). Offen: Rückübertragung nach K vor Tests; ob eine Modellablage im neuen Ordner sinnvoll ist; Aufbau auf `K:\` in den Sitzungen „Sedra USB-Stick auf K:\ einrichten“ und „Sedra Minimal USB-Stick Arbeitsumgebung“.
7. **Kurs-Präsentation:** Zahlen der 14 Folien noch gegen das Logbuch prüfen.

## 10. Arbeit im Chat vom 04.–05.11.2026 (Claude Code, One Sedra)
**Stand:** alles auf `main` bis `b9913bc` (GitHub `DBM-Ger-cmd/Sedra-AI-Assistent-OS`). Das Gespräch liegt als Export in `C:\Users\David\Downloads\session-export-1793880935459.zip` (20 MB).

**Entscheidung des Captains (05.11.):** Die Harness ist der zentrale Punkt und heißt **One Sedra** (nur der Anzeigename; Kennung `harness` bleibt). Sedra XP und der Retro-Desktop werden nicht weiterentwickelt; die Funktionen der anderen Shells wandern in One Sedra. Zuschnitt für Auftraggeber über Profile, nicht über neue Shells.

**Gebaut (Ort und Test in Klammern):**
- **Modelle laden:** „Fenster Auto“ nahm für Rezepte mit Stufen immer die größte Stufe und wurde mit `vram_insufficient` abgelehnt. Fix in `models/role_routing.py`: Auto = größtes Fenster, das passt; eine gewählte Stufe ist „höchstens so viel“ (`fenster_angepasst`); Ladeprobe nach jedem Start (`harness/ladeprobe.py`); Vertragstest auf den Rezepten der Maschine (`tests/test_model_laden_vertrag.py`).
- **Info-Hub und Betriebslog** (`harness/info.py`, `betriebslog.py`): Einstellungen → System → Info; Tagesdateien unter `runtime_data/harness/betriebslog/` als Wissensquelle (Antrag, Freigabe im Posteingang).
- **Freigaben** (S1–S3): Aufgaben-Formular mit Bausteinen, Reiter „Freigaben“ (Wartet / Gilt gerade / Regeln). S4 (gemeinsames Modell „Erlaubnis mit Dauer“) offen.
- **YouTube-Transkript** mit yt-dlp-Rückfall und Übersetzen; **Neue Vorlage** per Maske und Chat-Werkzeug; Start ohne Auswahl direkt in One Sedra.
- **Desktop Builder** (Start → System; `harness/desktop.py`, `builder.js`, `layouteditor.js`, `bausteine.js`, `kontext.js`): Rechtsklick-Menü mit „Im Chat anpassen“, Reiter Module, Start-Menü, Taskleiste, Layout (Bühne, Raster, Seitenaufbau, Start-Menü-Abschnitte) und Profile mit Marke, Logo, Schrift, Startseite; Grundfunktionen (Posteingang, Aufgaben, Freigaben, Schild, Senden, App-Gruppen, Einstellungen) nie ausblendbar; Entwurf `docs/ENTWURF_AUFTRAGGEBER_PROFILE_2026-11-05.md`. Vorlage **Oberflächen-Designer** (`desktop-designer`) und Chat-Werkzeug `desktop_lesen`.
- **Lernsystem** (`harness/belohnung.py`, `config/belohnung.yaml`, Entwurf `docs/ENTWURF_BELOHNUNG_UND_LERNEN_2026-11-05.md`): Lob („danke“, „perfekt“) = ★/★★, Korrektur („das stimmt nicht“) = ⚑, Tagesdateien in `runtime_data/harness/belohnungen/` für die Wissensdatenbank, bei Code mit den geänderten Dateien; Vorlage **Rückblick** (Hermes-Muster aus `E:\HermesAgentOrdner\hermes-config-backup\…\skills\workflow\rueckblick`), Werkzeug `belohnungen_lesen`, gelernte Regeln `docs/AAR/LESSONS.md` im Systemprompt (höchstens 25 Zeilen); **Vorhersagen beim Tippen** (`vorschlaege.js`, Tab übernimmt, ⚑-Warnung).
- **Cache-Messung:** Prompt-Cache des Modellservers (`cache_n`, `prompt_n`) je Zug in der Sitzungszeile, auf der Token-Seite („Aus dem Cache x %“) und in der Token-Zelle. Der Systemprompt muss mitgeschickt werden (zustandslos), kostet aber fast nichts, solange sein Anfang gleich bleibt; Veränderliches steht hinten.
- **Taskleiste:** Temp, VRAM (belegt) und RAM (frei) als drei Zellen.

**Fallen und Praxiswissen dieser Sitzung:**
- Bash-Heredocs verdoppeln Backslashes und machen aus `\n` echte Zeilenumbrüche: Python-Skripte mit Zeichenketten über das Write-Werkzeug als Datei schreiben, nicht per Heredoc (auch Windows-Pfade mit `\U` brechen dort).
- Neue Wege der Harness brauchen Einträge in `desk/freigabeklasse.py` (`HARNESS_WEGE`, `HARNESS_UNTERWEGE`, `ROUTEN_HARNESS`) und im Regex `WEG`/`GESCHUETZT` in `harness/api.py`; Test `test_freigabe_vollstaendig` liegt außerhalb der Gruppen `harness uix desk`.
- Vorlagen-Kennungen dürfen nur `a-z 0-9 -` enthalten (kein Unterstrich).
- Browser-Prüfung nur an einer eigenen Testinstanz (`scratchpad/testserver.py`, eigener Token), nie am laufenden Sedra des Captains.
- Wackelige Tests unter Last: `test_harness_lauf`, `test_uix_harness_lauf`, `test_uix_stufe6.ImBrowser` (einzeln grün).
- Das Audit-Log (`workspace/GUPPI_OS/runtime_data/audit/events.jsonl`) zuerst selbst lesen, bevor man den Captain fragt (`SLOT_SERVER_STARTED`, `ROLE_RESOLUTION_FAILED`, `LADEPROBE`, `HARNESS_BELOHNUNG`).

**Offen (Stand 05.11.2026):** Freigaben S4; Funktionen der anderen Shells als Apps in One Sedra holen (Reihenfolge nennt der Captain, Vorschlag Translator oder Wissensbasis); Richtlinie für Betreiber (Stufe 4 des Apps-Modells); Lernsystem und Cache-Zahl im echten Sedra ausprobieren (Anträge für Betriebslog und gute Antworten im Posteingang freigeben); E1–E5 des Plans CPU-Hilfswerkzeuge, MasterChat-Probelauf, Stick-Branch `claude/usb-stick-minimal-3c1b19`.

## 11. Arbeit im Chat vom 05.–06.11.2026 (Claude Code: Prozess-Apps, Updates, Skills)
**Stand:** `main` = `226c8ba`, lokal, 34 Commits vor `origin/main` (`d51083a`), nichts gepusht. SEDRA 1.22.2. Vorab-Prüfung des Pushs: keine Schlüssel im Verlauf; vier Beispielpfade stehen noch in `aacf07e` (Verlauf unverändert gelassen, Beispiele im aktuellen Stand durch Platzhalter ersetzt).

**Gebaut (Ort und Test in Klammern):**
- **Update 1.22.2 Prozess-Apps** eingespielt (Updater-Weg des Pakets, Sicherung vorhanden). Das Paket enthielt weder Tests noch Paketier-Skript; die Tests kamen aus der Entwicklungskopie (`test_n8n_*`, `test_process_*`, `n8n_model.test.cjs`).
- **UIX der Prozess-Apps** (`runtime/src/guppi_runtime/uix/ui/workflow-*.js`, Plan `docs/PLAN_PROZESS_APPS_UIX.md`): helles und dunkles Thema (Farben in `tokens.css`), Symbolsatz des Workflow-Diagramms (Oval, Raute, Parallelogramm, Zylinder), Seitenleiste (einklappbar) mit Startseite, Vorlagen Muster A/B/C, Knotenauswahl mit gesperrten n8n-Knoten, Folgeschritt per „+“, Schnellleiste am Knoten, Leiste an der Verbindung (einfügen, löschen), Aufräumen, Haftnotiz, Minimap, geführtes Einrichten, Parameteransicht (Eingabe, Parameter, lokale Vorschau der Ausgabe), Marke des letzten Laufs. Nach dem Vorbild von n8n und Make, ohne deren Code (n8n: Sustainable Use License).
- **Selbstabbild** (`config/selbstabbild.yaml`, `workflows/selbstabbild.py`, `test_selbstabbild`): sechs SEDRA-Abläufe als nicht ausführbare Prozessmodelle, jeder Schritt mit Quelle; der Test schlägt bei Abweichung fehl.
- **Prozess-Entwurf durch SEDRA:** Werkzeug `prozess_beantragen` (nur Antrag im Posteingang, Entwurf erst nach dem Ja des Captains), Vorlage `prozessmodellierer`; aus den Apps startet „Von SEDRA entwerfen lassen“ eine Harness-Sitzung, die links unter „Sitzungen“ erscheint.
- **Bauablauf angepasst:** Testgruppe `workflow` und `runtime` in `run_tests.py`, Lauf `workflow_js`, `belohnungen_lesen` für Prüfer und Vorarbeiter.
- **Übernommene Übergaben:** Wissen im Kern K1/K2 (v2) und K5 (v4, als Delta zu v2), F0-01 Startfix, F0-02 Shutdown/SQLite, F0-03 Verbindungen, F0-04 Boot und Service-Bereitschaft. Wissen ist dadurch Standard an.
- **Skills** (Quelle `skills/`, Kopien in `.claude/skills/`, eigene SEDRA-Bibliothek `sedra`, Test `test_skills_sedra`): `update-einspielen`, `sedra-tests-windows`, `sedra-ui-vertrag`, `selbstabbild-erweitern`, `chat-sichern`.
- **Unterchats:** „Updates einspielen und prüfen“ (spielt künftig Pakete ein, testet, berichtet) und „Aufräumen der Umgebung“ (Bericht, gruppenweise Freigabe, Verschieben in ein Archiv statt Löschen).

**Entscheidungen des Captains:** Prozess-Apps ohne Marken der Vorlagen, aber nah an deren Funktion und Aussehen; helles Thema zusätzlich zum dunklen; SEDRA bildet seine Abläufe selbst ab und kann Prozesse vorschlagen (Antrag); Updates nur über den Update-Chat und nie direkt auf `main`; Skills im Projekt und für SEDRA; Worktrees und Branches bleiben vorerst stehen.

**Fallen und Praxiswissen:**
- Heredocs und Backslashes: Skripte mit dem Write-Werkzeug anlegen (siehe Skill `sedra-tests-windows`).
- Wissen ist Standard an und hält `wissen.sqlite` in Temp-Ordnern offen, Windows verweigert dann das Aufräumen: der Testlauf setzt `SEDRA_WISSEN_STANDARD=aus`, Tests mit Hub oder Runtime schließen sie, Wissens-Tests schalten es selbst ein.
- Vertragstest der Oberfläche: höchstens 400 Zeilen je Datei, Farben nur in `tokens.css`, Routen in `tool.yaml` samt Eintrag im Allowlist-Test.
- Unsichtbare SVG-Trefferflächen brauchen sichtbare Geometrie, sonst findet Playwright sie nicht; schmale Felder in der oberen Leiste machten Export-Tests instabil.
- Update-Pakete bauen aufeinander (F0-01 bis F0-04 in Reihenfolge); Übergaben gegen alten Basisstand als Delta über zwei Detached-Worktrees bilden.

**Offen (Stand 06.11.2026):** Push nach GitHub nur auf ausdrückliches Ja (Entscheidung, ob der Verlauf mit den vier Beispielpfaden bleibt); Paket 1.22.3 (Paketier-Skript fehlt im Repo); echter Windows-Lauf der F0-Updates (Erst-/Zweitstart, `--replace`); offene SQLite-Warnungen in Orchestra, Scheduler und Job-Supervisor; Worktrees `A1-wt-prozess-apps-uix`, `A1-wt-wissen-k5-v4` und die Branches `feat/prozess-apps-uix`, `f0-runtime-updates`, `wissen-k5-v4`, `wissen-kern-k1k2` entfernen, sobald der Captain abgenommen hat; Anbindung der Startseite an den Chat bleibt bei „Sitzung starten“ (kein eigener Chat-Dialog in den Apps).

## 9. Alle Chats (Sitzungen), nach Datum
**Sedra Vorarbeiter (Gruppe):**
- 05.–06.11. Claude Code, Chat „Prozess-Apps einspielen und überarbeiten“: Update 1.22.2, UIX der Prozess-Apps, Selbstabbild, F0-01 bis F0-04, Wissen K1/K2/K5, Skills; Unterchats „Updates einspielen und prüfen“ und „Aufräumen der Umgebung“ (siehe Abschnitt 11).
- 04.–05.11. Claude Code, Vorarbeiter-Sitzung „VORARBEITER“: One Sedra, Desktop Builder, Lernsystem, Cache-Messung (siehe Abschnitt 10).
- 31.10. Sedra Minimal USB-Stick Arbeitsumgebung (läuft); Sedra USB-Stick auf K:\ einrichten; SEDRA: minimale USB-Version auf K:\ einrichten (Worktree `claude/usb-stick-minimal-3c1b19`).
- 30.10. Test: Bonsai und Nemotron gleichzeitig (Worktree `claude/test-bonsai-nemotron-ac86cc`); Earth 2140 DOS-zu-Windows AI-Integration (archiviert); Start-Prompt für Seadra-Vorarbeiter (Vorarbeiter-Sitzung, startete die Harness-Sitzungen).
- 29.10. Harness Stufe 3 planen (G2, G3); C-Laufwerk Datenmüll aufräumen; Modelle zu KI-Daten hinzufügen; Harness-Shell Stufe 1 bauen.
- 28.10. Produktaktivierung Altersrestriktion; Sedra-Zusammenfassung für Studienkurs; Sedra master chat window error; 6h-Lauf auswerten, dann Nemotron-Test; Sedra-Projekt Zusammenfassung; Sedra: Kurs-Zusammenfassung und Arbeitsübersicht.
- 27.10. Projekt online gehen (anderes Projekt, `H:\WirschreibendeineBewerbung.de`).
- 26.10. S2.H5 Router-Haken, Werkstatt, Slots-Schnappschuss; E:\Sedra Umgebung: Index und Plan zum Zusammenlegen.
- 25.10. Umstiegsplan: Installation auf aktuellen Stand; Spec 2 Harness S2.H1/H3/H4a; Spec 7 Cloud-Auflagen; Spec 2 Modelle & Scheduler (Abgleich → G1).
- 24.10. Spec 7 Abnahmesatz und Goldsatz.
- 22.10. Spec 1 Harness C1, C2, H1–H5; Shell D bauen S4.3–S4.8; Spec 7 S7.1 Goldsatz und Messplan; Spec 3 Cloud & GateWay (→ G1).
- 21.10. PIPE-12 versteckte Tests schärfen; Spec 1 Bau-Specs → G3; Spec 1 Design → G2; Spec 0 Harness K0.7–K0.25, F1–F3; Shell D bauen S4.1, S4.2, S4.9; PROFIL-01/02 und PIPE-10.
- 20.10. Spec 4 Shell D Design → G2; PIPE-09 (ein Bau-Ort, Gleichlauf-Test); Pipeline PIPE-06/07, V1–V4, ANA-06/08/10; Linie L1–L3 Bauwerkzeuge.

**Hermes Agent Optimierung (Gruppe):** 28.10. Hermes-Einrichtung starten (`E:\HermesAgentOrdner\Hermes Arbeits ordner`).

Nur die Titel und Orte der Sitzungen sind hier erfasst. Inhalte einzelner Sitzungen stehen im jeweiligen Verlauf oder in den Berichten unter `docs/` (zum Beispiel `BAUBERICHT_*`, `docs/UEBERGABE_CLOUD_2026-10-29.md`).
