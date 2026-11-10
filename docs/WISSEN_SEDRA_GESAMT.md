# SEDRA – Wissensdatei (alle Chats zusammengeführt)

Stand: 31.10.2026. Quellen: Gedächtnisdateien von Claude (Memory), die Sitzungsliste des Cockpits (alle Chats, auch archivierte), das Logbuch `docs/LOGBUCH_AGENT_MANAGER.md`, der Git-Verlauf (527 Commits auf `main`) und der Arbeitschat vom 27. bis 31.10.2026. Kein Inhalt ist erfunden; was nur vermutet ist, steht als Vermutung da. Der Captain ist der Nutzer (David); er entscheidet alle Freigaben.

## 1. Was SEDRA ist
- SEDRA: lokales KI-Betriebssystem mit Cockpit-Oberfläche (UIX), Agenten-Orchestrierung (Orchestra), Modell-Scheduler, Freigabe-Prinzip („Captain entscheidet“, Guard, Gates) und lokalen Modellen (llama-server).
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
- **Desk/Cockpit/UIX:** Server `sedra_runtime.uix_server`, mehrere Shells (cockpit, minimal, paperclip, start, harness, fisch, gateway-kmu), Werkzeuge unter `uix/tools/*`. Werkzeuge rufen nur `ctx.api()` auf und nutzen kein `fetch` und kein `localStorage` (Vertrags-Test `test_uix_contract`); Speichern ist Sache der Shell.
- **Orchestra:** Agenten (Leitung `foreman`, Recherche `researcher`), Aufgaben, Weckrufe (`wakeups`, Ausgang u. a. `antrag`, `lauf`, `abgelehnt`), Heartbeat, Anträge über `desk/gated.py` und `desk/orchestra_kinds.py` (Applier mit `binding_stale`).
- **Freigaben:** Jeder Lauf braucht eine Einzelfreigabe, außer bei einer Dauerfreigabe (Art `standing`, Token genau einmal). Ein Antrag ist an einen Stand gebunden (Revision/Fingerabdruck); ändert sich der Stand, endet er mit `binding_stale`.
- **Modell-Scheduler:** `ResourceScheduler`, Slots, Rezepte in `workspace/SEDRA_OS/local_config/role_routing.yaml` (nicht in Git). Dynamische Rezepte R1–R6: Block `profile.dynamisch`, `models/aufteilung.py`, Messspeicher `runtime_data/model_messwerte.json`.
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
- **Cockpit ohne Fenster starten:** `PYTHONPATH=src python -B -u -m sedra_runtime.uix_server --root workspace/SEDRA_OS --architecture architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT --port 8765` (URL mit Token steht in der Ausgabe, Header `X-SEDRA-Token`). `START_SEDRA.bat cockpit --replace` beendet vorher alle laufenden SEDRA-Server; der Start meldet sonst „SEDRA läuft bereits“.
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
- Das Audit-Log (`workspace/SEDRA_OS/runtime_data/audit/events.jsonl`) zuerst selbst lesen, bevor man den Captain fragt (`SLOT_SERVER_STARTED`, `ROLE_RESOLUTION_FAILED`, `LADEPROBE`, `HARNESS_BELOHNUNG`).

**Offen (Stand 05.11.2026):** Freigaben S4; Funktionen der anderen Shells als Apps in One Sedra holen (Reihenfolge nennt der Captain, Vorschlag Translator oder Wissensbasis); Richtlinie für Betreiber (Stufe 4 des Apps-Modells); Lernsystem und Cache-Zahl im echten Sedra ausprobieren (Anträge für Betriebslog und gute Antworten im Posteingang freigeben); E1–E5 des Plans CPU-Hilfswerkzeuge, MasterChat-Probelauf, Stick-Branch `claude/usb-stick-minimal-3c1b19`.

## 11. Arbeit im Chat vom 05.–06.11.2026 (Claude Code: Prozess-Apps, Updates, Skills)
**Stand:** `main` = `226c8ba`, lokal, 34 Commits vor `origin/main` (`d51083a`), nichts gepusht. SEDRA 1.22.2. Vorab-Prüfung des Pushs: keine Schlüssel im Verlauf; vier Beispielpfade stehen noch in `aacf07e` (Verlauf unverändert gelassen, Beispiele im aktuellen Stand durch Platzhalter ersetzt).

**Gebaut (Ort und Test in Klammern):**
- **Update 1.22.2 Prozess-Apps** eingespielt (Updater-Weg des Pakets, Sicherung vorhanden). Das Paket enthielt weder Tests noch Paketier-Skript; die Tests kamen aus der Entwicklungskopie (`test_n8n_*`, `test_process_*`, `n8n_model.test.cjs`).
- **UIX der Prozess-Apps** (`runtime/src/sedra_runtime/uix/ui/workflow-*.js`, Plan `docs/PLAN_PROZESS_APPS_UIX.md`): helles und dunkles Thema (Farben in `tokens.css`), Symbolsatz des Workflow-Diagramms (Oval, Raute, Parallelogramm, Zylinder), Seitenleiste (einklappbar) mit Startseite, Vorlagen Muster A/B/C, Knotenauswahl mit gesperrten n8n-Knoten, Folgeschritt per „+“, Schnellleiste am Knoten, Leiste an der Verbindung (einfügen, löschen), Aufräumen, Haftnotiz, Minimap, geführtes Einrichten, Parameteransicht (Eingabe, Parameter, lokale Vorschau der Ausgabe), Marke des letzten Laufs. Nach dem Vorbild von n8n und Make, ohne deren Code (n8n: Sustainable Use License).
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

## 12. Arbeit im Chat vom 08.–09.11.2026 (Claude Code: Nachtlauf, Bau-Wiederholung, Register)
**Stand:** `main` = `f8575e1`, gleich `origin/main` (nach GitHub gepusht: `6250384` und `f8575e1`). Offen im Arbeitsbaum: nur die automatisch geschriebenen BAU-Zeilen im Logbuch (21:53 bis 22:54), siehe unten.

**Gebaut bzw. integriert (Ort und Beleg in Klammern):**
- **F0-05C-Nachtlauf** als docs-only-Commit `6250384` auf `main`: `docs/SPEC_F0_05C_SHUTDOWN_REIHENFOLGE.md`, `docs/ANALYSE_F0_06A_RESOURCEWARNINGS.md`, `docs/TESTPLAN_GATE-01_VER-01.md` (Prüfsummen OK, `git apply --check` OK gegen `52f33f3`, `git ls-remote` bestätigt).
- **Logbuch** `f8575e1`: zwei BAU-Zeilen zum Bau vom 17:16 und 17:54 (beide nicht bestanden).
- **Register** `04_REGISTER/auftraege.json` (Quelle außerhalb des Repos, im Koordinator-Paket): Notizen zu SEDRA-F0-05C, SEDRA-F0-06A, SEDRA-GATE-01, SEDRA-VER-01 mit Verweis auf die integrierten Dateien. Keine Statusänderung. Sicherungen `auftraege.json.bak_vor_f005c_20261108` und `auftraege.json.bak_vor_nachtlauf_f006a_20261108`. Validator: 35 Aufträge, OK. Dashboard neu gerendert und nach `E:\Sedra Umgebung\KOORDINATOR_DASHBOARD.html` kopiert.
- **Korrektur:** SEDRA-F0-05B steht bereits auf `MAIN_VERIFIED` (Integrationscommit `e83d0af`, Testbericht PASS mit Vorbehalt). Eine Notiz der Nachtlauf-Sitzung sagte fälschlich `SPEC_APPROVED`; das Register wurde deshalb nicht geändert.
- **Korrektur:** SEDRA-F0-06A existierte bereits im Register. Meine Suche hatte nur `F0-06A` statt `SEDRA-F0-06A` gesucht und einen fehlenden Eintrag gemeldet.

**Factory-Bau `factory_sdk_grundlage` (Ergebnis: nicht bestanden):**
- Lauf v4 (21:24) endete mit `BAU_ENDE exit=127`. Der Lauf wurde mit `Stop-Process` angehalten (Captain-Auftrag), danach keine `devvm_build`-Prozesse.
- Lauf v5 ab Stufe 2 vom Snapshot `after_S1` (21:45 bis 21:53): Stufe 2 „hidden FAILED“, S3 und S4 nicht gebaut. Kandidat `attempt_01_20261108_215340`. Log `runtime_data\bau_factory_sdk_grundlage_v5_ab_S2.log`.
- Wiederholung (Skript `runtime_data\bau_wiederholung_s2_status.log` und `bau_wiederholung_s2.sh`, außerhalb des Repos): `coder.local_primary` Versuch 1 (22:09), Versuch 2 (22:19), dann `qwen3coder` Versuch 1 (bis 22:41), Versuch 2 (bis 22:54). Alle vier fehlgeschlagen. Kandidaten `attempt_01_20261108_220936`, `_221909`, `_224153`, `_225422`.
- In den Versuchen 2 (beide Modelle) steht `SERVER CRASH … ConnectionResetError` im Log. Diese Versuche sind damit keine saubere Modellprüfung.
- Nicht geprüft: welcher Hidden-Test in Stufe 2 scheitert. Die Log-Zeilen nennen den Test nicht; die Ursache steht in den Kandidatenordnern.

**Nachtlauf-Sitzung** (`nachtlauf-sedra-bau-berw`, Gruppe „Sedra Vorarbeiter“): Bau überwacht; GATE-01-Test 17/17 grün (Angabe der Sitzung, im Register belegt); REL-02-Verifier bricht ab (Angabe der Sitzung); VER-01 nicht gelaufen; keine Commits.

**Entscheidungen des Captains (08.–09.11.):**
- F0-05C und F0-06A-Analyse, GATE-01/VER-01-Testplan in `main` übernehmen (ja).
- Logbuch-Änderung committen (ja, Quelle vertrauenswürdig).
- Factory-Bau ab Stufe 2 fortsetzen (ja); F0-06A-Eintrag und GATE-01/VER-01 erfassen (ja).
- Dashboard-Abarbeitung durch die Nachtlauf-Sitzung: Freigabe nur für Dokumentation und Register, ohne Integration.
- VER-01 „ja soll jetzt“ in diesem Chat. Die Nachtlauf-Sitzung verlangt ein „ja“ in ihrem eigenen Chat, weil dort zuvor „Nein, später“ stand. Eine Weitergabe zwischen Sitzungen gilt nicht als Freigabe.

**Offen (Stand 09.11.2026):**
- VER-01 (Windows-Live-Lauf): braucht „ja“ in der Nachtlauf-Sitzung und einen Stopp des SEDRA-Routers (`llama-server`, PID 13908, Port 8090), weil der Testplan „kein laufender Modellserver“ verlangt. Entscheidung des Captains offen.
- REL-02: Verifier bricht ab (Nachtlauf-Sitzung). Ursache nicht untersucht.
- Factory-Bau: Entscheidung offen, ob der Bau mit anderer Einstellung neu versucht wird. Vorschlag: zuerst die Testfehler in den Kandidatenordnern lesen, dann Server-Abbrüche prüfen (`--context` senken oder Modellserver stabilisieren), danach erst erneut bauen.
- Arbeitsbaum: `docs/LOGBUCH_AGENT_MANAGER.md` mit den BAU-Zeilen 21:53 bis 22:54 (automatisch geschrieben).
- Worktrees und Branches unverändert: `A1-wt-f0-05-drain`, `A1-wt-freigabe-luecken`, `A1-wt-wissen-k5-v5` sowie `claude/usb-stick-minimal-3c1b19` und `codex/n8n-workflow-app`. Löschen nur auf Ja.

**Fallen und Praxiswissen dieser Sitzung:**
- Wiederholung ohne Ursachenanalyse war ein Fehler. Vor einer Wiederholung zuerst den Fehler im Testlog oder Kandidatenordner lesen und dem Captain eine Alternative vorschlagen.
- Eine Freigabe, die im Chat einer Sitzung gegeben wird, gilt nur dort. Eine Weitergabe per Nachricht an eine andere Sitzung ist keine Freigabe.
- `Monitor` mit `until`-Schleife läuft 30 Minuten und endet dann von selbst. Bei noch laufendem Prozess neu starten.
- Ein `sleep 60` im Bash-Tool wurde blockiert. Warten über Monitor oder `run_in_background`.
- Die Baulogs enthalten keine Zeile mit dem Namen des fehlgeschlagenen Tests. Die Testausgabe steht im Kandidatenordner.
- Der Bau schreibt die BAU-Zeile im Logbuch selbst (außer mit `--no-logbook`). Diese Zeilen nicht doppelt von Hand eintragen.

## 13. Arbeit im Chat vom 08.–09.11.2026 (Claude Code: Fabrik-Bau, Cloud-Modelle, Manager, Prozess-Live-Ansicht)
**Stand (13:01):** `main` = `467460f`, lokal eine Änderung voraus: `740749e` (Live-Meldungen der Schleife), **nicht gepusht**. Nicht committet: `docs/LOGBUCH_AGENT_MANAGER.md` (BAU-Zeilen aus den Läufen) und `runtime/config/cloud_providers.yaml.bak_vor_nvidia_20261109` (Sicherung, bleibt draußen).

**Gebaut bzw. integriert (Ort und Beleg in Klammern):**
- **F0-05C-Abgabe** als docs-Commit `6250384` (Spec Shutdown-Reihenfolge, Analyse F0-06A, Testplan GATE-01/VER-01). Logbuch `f8575e1`.
- **Factory SDK 1** (`cd5b774`, Paket `runtime/src/factory_sdk`): Prüfung von project, workflow, task_run, artifact, evidence, approval gegen die Schemata. Die Schemata sind als Daten in `schemas_data.py` eingebettet. Lokal und in der microVM bestanden S1 bis S4. Register `SEDRA-FSDK-01` MERGED.
- **Ursache der Fehlläufe v4/v5 (Modelle):** Der Coder hat ein erfundenes task_run-Schema verwendet (`task_run_id`, `execution`), weil die Schemata nicht im Arbeitsbereich lagen. Der handgeschriebene Kandidat `manuell_01` (eigene Prüfung gegen die Schemata) besteht alle vier Stufen.
- **Spec v5** (`4270d70`): Regelblätter je Objekt in den NOTES (aus `regeln_aus_schema.py`), 35 Negativfälle je Schemaregel. Stempel vm ok. Referenz `devvm_refs/factory_sdk_grundlage_v5`.
- **Bau-Schleife** (`ebe89ca`, `514b148`, `42cd72a`, `740749e` lokal, `runtime/benchmarks/bau_schleife.py`): Einzelbetrieb per Sperrdatei, Fortsetzen nach Abbruch (Stand `bau_schleife_stand.json`), Vorprüfung (spec_check --vm plus GPU: kein Modellserver, höchstens 3 GiB belegt), vier Parametersätze, Fehler-Fingerabdruck und bekannte Fehler (`bekannte_fehler.json`), Wissensdatenbank-Treffer im Fehlerbericht, automatisches Merken geänderter Dateien, Regressionsprüfung (Bereiche workflow und runtime) vor dem Produktbericht, Vorlauf-Fehler brechen sofort ab, Live-Meldungen an die Prozessansicht (ohne Modul ein No-op).
- **Prozesse im Selbstabbild** (`selbstabbild.yaml`, Commit `4270d70`/`514b148`): `factory-bau`, `wissensbasis`, `vollautomatischer-bau`. Im Workflow-Speicher angelegt: `WF-3e50882b2ad94f95aca0c1e4` (factory-bau), `WF-f871d588444b41ad9f5f5d0e` (wissensbasis), `WF-626c29dd21a34c0eb09a809b` (vollautomatischer-bau).
- **Prozessprüfung** (`7092d33`, `runtime/benchmarks/prozess_pruefung.py`, Skill `sedra-schnellpruefung`): liest laufende SEDRA-Prozesse und gibt je Prozess ein Urteil (AKTIV, ROUTER, STILL, JUNG_STILL), beendet nichts.
- **Cloud (NVIDIA):** Hauptschalter und Anbieter eingeschaltet (Captain-Ja), Schlüssel im Schlüssel-Speicher von SEDRA (Status bereit), Zeitlimit 120 s (`cloud_providers.yaml`, Commit `42cd72a`). Der Schlüsselwert wurde nie gelesen oder eingetragen.
- **Fähigkeitstest** (`benchmarks/modell_faehigkeiten.py`, Bericht `workspace/SEDRA_OS/wissen_quellen/modelle/faehigkeiten_2026-11-09_1214.md`): drei kurze Aufgaben (Folgen, Code, JSON) für 22 Textmodelle. Bestanden haben nur drei: `nvidia/nemotron-3.5-lightning-30b-a3b`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`, `poolside/laguna-xs-2.1`. 19 Modelle: 404 (nicht freigeschaltet) oder Zeitlimit. Der 3D-Test (OBJ-Würfel) ist am festen Berater-Modell nicht bestanden (leere Antwort). Im NVIDIA-Katalog (84 Modelle) gibt es kein 3D-Erzeugungsmodell.
- **Manager** (`runtime/src/sedra_runtime/manager/`, Commit `42cd72a` und `340f159`, `config/manager/`): Verfassung (`verfassung.md`), Gesetze (`gesetze.yaml`: Cloud-Aufgabentypen, Captain-Rechte, Untergebene höchstens zwei Ebenen, Werkzeuge, Tagesbudget), Prüfung je Entscheidung mit Journal (`runtime_data/manager/journal.jsonl`). Werkzeuge: Taschenrechner, Notizblock, Dashboard-Stand, Journal, Modellwahl, Wissenssuche, Dokumente lesen, Prozess beantragen, Laufstatus, Sitzungen, Bau starten. Die Harness führt die Werkzeuge noch nicht über den Manager aus.
- **Berater** (`benchmarks/berater.py`): ein Cloud-Modell, nur Text, Antwort wird in einen neuen Kandidaten geschrieben und in der microVM geprüft. Das feste Modell ist `nvidia/nemotron-3.5-lightning-30b-a3b` (`config/manager/berater.yaml`). Ein echter Lauf war erfolgreich (4 s).
- **Vorarbeiter-Kanal** (`manager/kanal.py`, `verteile`): nimmt Aufträge, prüft sie gegen die Gesetze, wählt das Modell aus den Tests, gibt Ergebnis oder Grund zurück. Getestet mit verbotenem, erlaubtem und leerem Auftrag.
- **Wissensquelle:** Modellliste und Fähigkeitsbericht in die Eingangssitzung `E-20261109-122349-1394` kopiert, Antrag über `benchmarks/wissen_antrag.py` (Doppelschutz). Der Captain hat in der App freigegeben. Quelle `Q-f6cce280` aktiv, 6 Abschnitte, keine Dopplung. Die Dopplung im Repo (vier identische Platzhalter-README) ist bereinigt: drei entfernt, Kopien archiviert in `E:\Sedra Umgebung\Updates\_archiv_doppelte_readme_2026-11-09\`, Commit `07436b6`.
- **Register:** `SEDRA-FSDK-01`, `SEDRA-WORKFLOW-A-01`, `B-01`, `D-01`, `SEDRA-WISSEN-PLUS-01`, `SEDRA-HILF-01` auf MERGED (jeweils Captain-Ja im Chat). `SEDRA-WORKFLOW-E-01` (Live-Reiter, Sitzung VORARBEITER, `467460f`) ist nach Captain-Ja im Chat auf MERGED gesetzt (Stand 09.11., 13:04, auch im Koordinator-Dashboard).

**Entscheidungen des Captains (08.–09.11.):**
- NVIDIA ja. Cloud für Code und Spec des Baus, Texte und Recherche ohne Personenbezug, 3D nur wenn der Anbieter es kann.
- Der Manager entscheidet selbst im Rahmen von Verfassung und Gesetzen. Quellen, Ausgabe und Freigaben werden bei der Einrichtung im Chat festgelegt.
- Berater fest auf das Nemotron-Modell. Zeitlimit erhöht, langsame Modelle nicht im bevorzugten Modus.
- Harness-Werkzeuge und Bau-Start durch den Manager ja. Vorarbeiter-Kanal ja. Modellkatalog und Testbericht als Wissensquelle ja.
- Nachtlauf-Sitzung ausgesetzt, bis der Captain sie wieder freigibt.

**Fallen und Praxiswissen dieser Sitzung:**
- Das Cloud-Modell lehnt Werkzeugaufrufe ab (`tools` in `UNSUPPORTED_OPTIONS`). Die Bau-Agenten brauchen Werkzeuge, daher nutzt der Berater nur Text.
- `labor.cloud_chat` liefert die Antwort im Feld `reply`, nicht `content`. Der Inhaltsschutz braucht ein Audit-Objekt mit `.append`, ein Lambda blockiert den Aufruf (`SG_AUDIT_FAILED`).
- Nicht freigeschaltete Modelle antworten sofort mit 404, nicht mit Zeitüberschreitung. Beim Test sind das zwei verschiedene Fehler.
- Ein Wissens-Antrag entsteht nur, wenn der Runtime-Hub vorhanden ist. Ohne ihn bleibt die Posteingangsliste leer. Der Antrag wird erst durch die Freigabe in der App wirksam.
- Ein Duplikat-Schutz muss vor dem ersten Antrag stehen. Sonst landen zwei gleiche Anträge im Posteingang.
- Das Monitor-Werkzeug läuft nach 30 Minuten ab, auch wenn der Prozess noch läuft. Dann neu starten.
- Die Grafikkarte hat 12 GB. Der Bau belegt fast 10 GB, ein zweiter Modellslot passt nicht dazu.
- Ein Bau, der mit altem Code gestartet wurde, nutzt die neuen Meldungen und Prüfungen erst beim nächsten Start.
- Vor jedem Push: auf Schlüssel und Tokens prüfen (Muster-Suche auf dem Diff, ohne Treffer bei 340f159).

**Unterchats (Gruppe „Sedra Vorarbeiter“):**
- `nachtlauf-sedra-bau-berw` (Nachtlauf, ausgesetzt, hat nichts laufen), `nachtlauf-sedra` (älter, 08.11.), `neustart-sedra` (06.11.), `k3-sedra` und `k3-nachricht` (K3-Nachricht, 06.11.), `updater-uebergabe` (06.11.), `tester-f05b-main` und `tester-main-verif` (Testläufe F0-05B und F0-05A, 06.11.).

**Erledigt (Stand 09.11., 13:04):**
- `SEDRA-WORKFLOW-E-01`: MERGED nach Bestätigung des Captains hier im Chat.
- `main` nach `origin/main` gepusht (`467460f..2cd20ed`), enthält `740749e` (Live-Meldungen der Schleife).
- Branch `workflow-live` (Commit `c160112`, Live-Ansicht) war bereits per Fast-Forward in `main` gemergt. Der Branch existiert nicht mehr.

**Offen (Stand 09.11., 13:04):**
- Verfassung des Managers: Bestätigung durch den Captain (Entwurf).
- Harness-Werkzeuge über den Manager ausführen (Verbindung fehlt).
- Lokale Slots: erst nach dem Bau, mit Speicherprüfung.
- Factory-Bau v5: Stand nach S3 nicht geprüft; Logbuch-Zeilen dazu liegen unversioniert in `docs/LOGBUCH_AGENT_MANAGER.md`.

## 15. Arbeit im Chat vom 09.–10.11.2026 (Claude Code: n8n-Import, Ryzen-9-Tuning des Hauptmodells, Profile, Nachtlauf)
Stand beim Sichern: `main` = `1ceff20`, gepusht (Abstand zu `origin/main` 0/0). Worktree `nachtlauf` (Branch `nachtlauf`) enthält ungemergte Änderungen, siehe unten.

**Gebaut und gepusht (alles in `main`)**
- `ee9f450` n8n-Import auf der Startseite beider Workflow-Apps: Karte „n8n-Workflow importieren“ (Datei, Ziehen, Einfügen), Vorschau mit Urteil, Funden, Bild und Schrittliste; Server-Teil `workflows/vorschau.py` mit Verb `import_vorschau` (nur lesen), Oberfläche `uix/ui/workflow-import.js`. Tests: 20 (`test_workflow_vorschau`) und 1 Browser-Test (`test_workflow_import_browser`), dazu die bestehenden Import-Tests grün (59 + 21 im Lauf). Das Dateifeld entsteht erst beim Klick, damit der Testweg `input[type=file]` des Editors eindeutig bleibt.
- `8556f21` Referenz für den Standardtest `bench_std` (5 Dateien in `devvm_refs/bench_std`); besteht alle vier Stufen auf dem Host und in der microVM.
- `1ceff20` Testläufer: Voreinstellung 12 statt 6 parallele Gruppen; voller Lauf mit 4.618 Tests **274 s statt 397 s**, in beiden Läufen dieselben 4 roten Tests (zwei Cloud-Einstellungen, ein Gateway-Test, alte Namen; Ursache nicht untersucht, nicht von dieser Änderung). Whisper-Threads: Standard sind die Kerne ohne Hyperthreads (4 bis 12), einstellbar mit `threads` in `local_config/sprache.stt.json`. VM-Kerne 2 → 4 bringen nichts (6 s gegen 7 s) und wurden verworfen.
- Gelöscht (Captain-Ja): Worktrees und Branches `workflow-import` und `fabrik-notaus` (vorher vollständig in `main`).

**Tinas Rechnungsprüfung (n8n-Paket)**
- Das Paket `Rechnungspruefung_Tina_n8n_Importpaket.zip` (am 10.11. erneut gesendet) ist unverändert gegenüber dem ersten Stand. Workflow 01: 20 Schritte, 22 Verbindungen, davon nur 3 (If-Knoten) in SEDRA ausführbar; Workflow 02: 11 Schritte, 1 ausführbar. Dateien 03 und 05 sind keine Workflows (Daten, Prüfbericht) und werden mit klarem Satz abgelehnt.
- Lokale Fassung von Workflow 01 auf Qwen3.6-35B-A3B (neue Datei im Ausgabeordner des Pakets, Unterordner `n8n_lokal_qwen36`, das Original bleibt): beide Modell-Knoten auf `lmChatOpenAi`, Temperatur 0 (Extractor) und 0,1 (Agent), Token-Grenzen 512 und 1024, Zugang „SEDRA lokal“ (Basis-URL der OpenAI-Schnittstelle des Routers, Port 8090 mit `/v1`). Der Extractor-Prompt von Tina (Schutzzeile gegen Anweisungen im Text, `{format_instructions}`) bleibt, dazu Regeln für Datum, Betragsbasis und Währung und ein Datumsmuster im Schema. Test gegen das lokale Modell (Werkzeugaufruf wie n8n, Denken aus): Extractor 28 von 28 Feldern bei vier Rechnungen (Grundprompt: 25 von 28), Agent ruft das Werkzeug auf und liefert das JSON mit den drei Feldern, drei gleichzeitige Anfragen je etwa 5 s. Kein echter Lauf in n8n selbst.

**Messungen am Ryzen 9 9900X (12 Kerne, 24 Threads; 12 GB VRAM; 31 GB RAM), Motor b11160, FA an, KV q8_0, ubatch 512** (Messdateien lagen im Scratchpad der Sitzung, nicht im Repo)
- Qwen3.5-9B Q6_K (ganz im VRAM): Threads 6 bis 22 ohne Wirkung (60,1 bis 61,8 Token/s).
- Qwen3.6-35B-A3B UD-IQ4_XS, 1 Kanal: Threads ohne Wirkung; der Hebel ist `n_cpu_moe`. Bei 32k: 16 Lagen 72,1 Token/s (0,5 GiB frei, zu knapp), 18: 69,0, 20: 65,4, 24: 60,4; 14 und weniger laufen in den VRAM-Überlauf (21 bis 30 Token/s). Bei 80k (81.920): 18 Lagen 68,5 (0,37 GiB frei), 19: 66,7 (0,71), 20: 66,0 (1,06). Der alte Stand (28 Lagen) lag bei etwa 40 Token/s. KV-Rate gemessen: 0,0144 GiB je 1.000 Token (vorher 0,0125 im Rezept).
- Mehrere Kanäle ohne MTP: 3 × 48k mit 22 Lagen 36,7 bis 40,9 Token/s je Strom (zusammen etwa 74); 4 × 32k mit 22 Lagen 24,9 je Strom (zusammen etwa 100 reine Erzeugung); mit 21 Lagen bleiben nur 0,46 GiB frei.
- MTP (neue Datei `Qwen3.6-35B-A3B-MTP-GGUF`, UD-IQ4_XS, 18.209.036.576 Byte, SHA-256 `df27a780…f7adf` geprüft, im Modellordner unter `unsloth`): 1 Kanal 80k: ohne MTP 65,4, **mit MTP 93,4 (20 Lagen, 0,37 GiB frei) und 90,1 (22 Lagen, 0,8 GiB frei)**, Annahmequote etwa 90 %. Dauertest bis 71k im Prompt: 20 Lagen stabil (9/9 Stufen), 0,39 GiB frei, Tempo fällt von 76 auf 49 Token/s; **21 Lagen stabil, 0,48 GiB frei, 68 bis 71 Token/s bei vollem Kontext**. 2 × 64k mit MTP und 24 Lagen: 61,0 je Strom, zusammen etwa 97, 0,65 GiB frei; 3 × 48k mit MTP und 24 Lagen: 49,2 je Strom, zusammen 96, 0,45 GiB frei; 3 × 48k mit MTP und 22 Lagen wird langsamer (29,7). Unter etwa 0,45 GiB frei bricht das Tempo ein.
- Standardbau `bench_std` (4 Stufen): 96,9 s (1 Slot, 18 Lagen), 109,2 s (2 Slots mit Prüfer gleichzeitig), 98,4 s (80k, feste 20 Lagen), 100,7 s (MTP, 22 Lagen): der Bau ist zu klein für den Tempogewinn, die microVM-Tests machen rund 90 s aus.

**Entscheidungen des Captains (10.11.)**: 18 Lagen sind bei Einbruch von 16 der Sweet Spot; 80k Kontext für den Einzelkanal anzielen (dann 20 bis 21 Lagen); 0,37 GiB frei sind akzeptabel, wenn es stabil läuft (Dauertest bestätigt es für 21 Lagen); Profil 3 × 48k eintragen; MTP-Modell laden; Wechsel auf `bau-1x80k`; Referenz committen und pushen; alten Nachtlauf löschen.

**Einstellungen in `local_config` (nicht in git; Sicherungen `*.bak-2026-11-10-*` daneben)**
- `role_routing.yaml`: Rezept `coder.local_primary` = 3 × 48k, 22 Lagen fest, kein MTP; `coder.local_primary_1x80k` = 1 Kanal, 81.920, **MTP-Datei, 21 Lagen**, Untergrenze 21, Stufe 81920 in der Kontext-Leiter; `coder.local_primary_4x32k` = 4 × 32k, 22 Lagen. Tabelle der dynamischen Auswahl neu (18, 20, 24 Lagen mit korrigierter Grundlast 0,26 GiB), `kv_cache_gb_per_1k_tokens` 0,0144.
- `routing_profiles.yaml`: Profile `bau` (3 × 48k), `bau-1x80k` (**aktiv**), `bau-4x32k`.
- Die Profile mit 2 und 3 Kanälen und MTP (24 Lagen) sind gemessen, aber noch nicht eingetragen.

**Fallen und Befunde**
- **`devvm_build.py` und die Bau-Schleife umgehen die dynamische Auswahl** (eigener Server-Start): sie nehmen `n_cpu_moe` fest aus dem Server-Block des Rezepts. Darum steht die Lagenzahl der Profile dort fest. Erkannt an der VRAM-Spitze (8,5 GiB statt 11,2 GiB).
- Testprojekte außerhalb des echten Projektordners haben keinen Sandbox-Unterbau: die microVM scheitert (`VM run failed`), auch mit einer richtigen Referenz. Bauläufe immer mit dem echten Projekt.
- Der Spec-Stempel kann nach einem Commit ungültig werden (`spec_changed_since_check`): `spec_check.py <spec> --vm --project <Projekt>` erneuert ihn.
- Beim Einbau eines Prompts den bestehenden Wert vorher lesen: Ich habe Tinas Extractor-Prompt überschrieben und musste ihn aus dem Original wiederherstellen.
- Fremde `llama-server` auf der GPU verfälschen Messungen; die Messskripte brechen jetzt ab, wenn einer auftaucht.
- `START_SEDRA.bat --replace` aus einer Hilfsshell ersetzte die laufende Sitzung nicht; die alte Sitzung musste beendet und `START_SEDRA.bat` neu gestartet werden.

**Alter Nachtlauf gelöscht**: die zwei geplanten Windows-Aufgaben „GUPPI Nachtkette 2026-10-13“ und „SEDRA Nachtkette A1 2026-10-26“ (beide schon deaktiviert) und die Auftragsliste `nacht_auftraege.json` (jetzt leer). Die Skripte `night_chain.py` und `start_nachtkette.ps1` liegen noch im Repository.

**Nachtlauf 10.11., 01:15 bis 07:00** (Läufer `benchmarks/nachtlauf.py`, Protokoll im Koordinationsordner unter `09_PLAN/NACHTPROTOKOLL_2026-11-10.md`, Plan `NACHTPLAN_2026-11-10_ENTWURF.md`): Schritt 2 Factory-Bau der neuen Spec `n8n_modell_umstellen` (Modell-Knoten eines n8n-Workflows auf das lokale Modell umstellen, Stufen S1 bis S4, Referenz in der microVM bestanden) über den Manager (`bau_starten` mit Spec, Rezept `coder.local_primary_1x80k`, 81.920); Schritt 3 Messung KV-Cache f16 gegen q8_0 mit Auslesen der geladenen CPU-Variante; Schritt 4 volle Testsuite. Ergebnisse standen beim Sichern noch aus (**nicht geprüft**). Nichts wird integriert, gemergt oder gepusht.
- Dafür im Worktree `nachtlauf` (Branch `nachtlauf`, **nicht committet**): `bau_schleife.py` mit `--spec`, `--rezept`, `--kontext` (andere Specs enden nach S4 mit Kurzbericht statt Produktprüfung), `manager/werkzeuge.py` (`bau_starten` reicht die drei Angaben durch), neue Spec, Referenz, `nachtlauf.py`, `tests/test_bau_schleife_spec.py` (7 Tests grün; 35 mit `test_fabrik_notaus` und `test_manager_verfassung`). Junction `engines` im Worktree zeigt auf die Engines des Hauptordners.

**Offene Punkte**
1. Ergebnis des Nachtlaufs auswerten (Protokoll, Kandidat in `devvm_candidates`, Kurzbericht, KV-Messung, Testsuite) und die Änderungen im Worktree `nachtlauf` nach Prüfung committen, mergen und pushen (nur mit Ja des Captains).
2. Profile mit 2 und 3 Kanälen und MTP (24 Lagen) eintragen; den normalen Bau-Standard (`coder.local_primary`) über die Schleife ggf. auf das MTP-Rezept stellen.
3. Register und Dashboard nachziehen (Einträge für n8n-Import, CPU/Tuning, Nachtlauf; Status nur durch den Koordinator).
4. Knopf „Auf lokales Modell umstellen“ in der Import-Vorschau (die Funktion dafür entsteht gerade im Nachtbau).
5. MOD-02 (n8n-Adapter, Gap-Analyse) und MOD-01 sind laut Dashboard offen und ohne Abhängigkeit; F2-01 hängt an der Kette F0-05C bis F0-05E, F0-06A/B, F1-01, F1-02 und MOD-03.
6. Bau-Schleife soll die Haltemarke (roter Knopf) zwischen Stufen prüfen und Live-Meldungen schreiben (offen aus früherer Sitzung).
7. Worktrees `cpu-nutzung` (in `main`, kann gelöscht werden), `nachtlauf` (noch gebraucht), `f0-05-drain`, `freigabe-luecken`, `wissen-k5-v5` (fremde Sitzungen, nicht angefasst).
8. Nicht geprüft: Zen-optimierter Motor (nur wenn die Messung der CPU-Variante einen Gewinn zeigt), echter Lauf von Tinas Workflow in n8n, MTP mit 3 bis 4 Kanälen im Bau.

## 9. Alle Chats (Sitzungen), nach Datum
**Sedra Vorarbeiter (Gruppe):**
- 09.–10.11. Claude Code, Chat „n8n-Import, Ryzen-9-Tuning, Profile, Nachtlauf“: Import-Vorschau auf der Startseite, Tinas Workflow auf das lokale Modell, Messungen Threads/Lagen/MTP/Kanäle, Profile `bau`, `bau-1x80k`, `bau-4x32k`, alter Nachtlauf gelöscht, neuer Nachtlauf (siehe Abschnitt 15).
- 08.–09.11. Claude Code, Chat „Fabrik-Bau, Cloud-Modelle, Manager“: Factory SDK, Bau-Schleife, Berater, Fähigkeitstest, Manager mit Verfassung und Werkzeugen, Vorarbeiter-Kanal, Wissensquelle (siehe Abschnitt 13). Unterchats: nachtlauf-sedra-bau-berw (ausgesetzt), nachtlauf-sedra, neustart-sedra, k3-sedra, k3-nachricht, updater-uebergabe, tester-f05b-main, tester-main-verif.
- 08.–09.11. Claude Code, Chat „Nachtlauf SEDRA“ (Koordinator): F0-05C-Abgabe in `main` übernommen, Factory-Bau v5 und Wiederholung (nicht bestanden), Register-Notizen, Dashboard; Sitzung „Nachtlauf SEDRA: Bau überwachen, Dashboard abarbeiten“ (siehe Abschnitt 12).
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

## 14. Nachbesprechung 09.11.2026: Factory-Bau v5 und Manager (4 W)

**Was war geplant:** Factory SDK Grundlage v5 in vier Stufen (S1 bis S4) durch die Bau-Schleife bauen. Dazu den Manager mit Verfassung, Gesetzen, Werkzeugen und Journal aufbauen und seine Werkzeuge über die Harness ausführen.

**Was ist passiert (belegt):**
- Lauf v4 (08.11., 21:24) endete mit `BAU_ENDE exit=127`. Lauf v5 (08.11., 21:45 bis 21:53) scheiterte in Stufe 2 am Hidden-Test. Die Wiederholung mit vier Versuchen am 08.11. scheiterte ebenfalls. Ursache: Der Coder verwendete ein erfundenes task_run-Schema, weil die Schemata nicht im Arbeitsbereich lagen. Quelle: Abschnitt 12 und 13 dieser Datei.
- Spec v5 (`4270d70`) mit Regelblättern und 35 Negativfällen. Lauf v5 am 09.11.: S1 bestanden (11:16, 2. Versuch), S2 bestanden (11:27), S3 bestanden (13:04, 2. Versuch). S4 startete um 13:04. Der Agent meldete um 13:12 nach 33 Aufrufen in 453 s. S4 bestanden um 13:28:05 (Kandidat `attempt_01_20261109_132805`). Danach „alle Stufen S1 bis S4 bestanden“ und Produktprüfung ok um 13:28:12, Bericht `runtime_data\produktbericht_20261109_132812.md`. Quelle: `runtime_data\bau_schleife_status.log`, `devvm_build_factory_sdk_grundlage_v5_2026-11-09_130433.log`. Noch nicht in `main` übernommen; die Übernahme braucht die Freigabe des Captains.
- Im S4-Log steht zu Beginn `S0 connection check: coder.local_primary missing`. Der Lauf ging trotzdem weiter. Ob das ein Fehlalarm ist, ist nicht geprüft.
- Manager gebaut (`42cd72a`, `340f159`): Verfassung, Gesetze, Journal, elf Werkzeuge. Berater einmal erfolgreich (4 s). Harness-Werkzeuge noch nicht über den Manager angeschlossen. Verfassung noch nicht vom Captain bestätigt.
- Die Angabe „Bau bestanden“ in Abschnitt 13 gilt für Factory SDK 1 (`cd5b774`). Der Lauf v5 ist nicht abgeschlossen.

**Wie können wir es besser machen:**
1. Vor jedem Coder-Lauf prüfen, dass Schemata und Referenzdateien im Arbeitsbereich liegen. Fehlen sie, startet der Lauf nicht.
2. Den Vorlauf-Fehler `coder.local_primary missing` klären, bevor der nächste Lauf startet.
3. Manager-Werkzeuge erst freigeben, wenn die Verfassung bestätigt und die Harness-Anbindung getestet ist.
4. Eine Aussage über Ergebnisse nur mit Beleg (Log, Commit, Pfad). Sonst „nicht geprüft“.
5. Die beiden offenen Verfassungsfragen klären: Rolle „Planer“ und Schutz personenbezogener Daten in den Gesetzen.

**Was lernen wir:**
- Ein Fehlschlag des Modells war oft ein Eingabefehler: Fehlende Vorgaben führten zu erfundenen Strukturen. Zuerst die Eingabe prüfen, dann das Modell wechseln.
- Ein Bau gilt erst als bestanden, wenn alle Stufen bestanden und der Produktbericht vorliegt.
- Regeln gehören in den Code, nicht nur in den Text. Die Gesetze prüfen heute den Aufgabentyp, nicht den Inhalt.
- Cloud-Modelle lehnen Werkzeugaufrufe ab (siehe Abschnitt 13).
