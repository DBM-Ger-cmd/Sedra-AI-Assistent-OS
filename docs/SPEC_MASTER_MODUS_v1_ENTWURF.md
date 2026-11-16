# SPEC Master-Modus und Gedächtnis für neue Chats v1 – ENTWURF (16.11.2026)

Status: **G1 und G4 vom Captain erteilt (16.11.2026, in der Sitzung: „ja“); O-1 bis O-6 gelten wie vorgeschlagen.** Teil A gebaut (A1 bis A6), Teil B folgt. Schreibt: Claude (Sitzung „Master-Modus“), Branch `claude/master-modus-927426` (Worktree `master-modus-927426`), kein Merge, kein Push.
Quellen gelesen: `SPEC_HARNESS_SHELL_v1.md` (HS-17, HS-21 bis HS-29), `SPEC_HARNESS_SHELL_v1_G2.md` §3.5, `harness/freigabe.py`, `katalog.py`, `befehl.py`, `vorbehalte.py`, `aufgabe.py`, `aufgabe_deckung.py`, `deckung.py`, `erlaubnis.py`, `code_stand.py`, `harness/gedaechtnis.py`, `desk/freigabeklasse.py`, `tests/test_freigabe_vollstaendig.py`, `projekte.py`, `config/harness_projekte.beispiel.yaml`. Keine lokalen Pfade in dieser Datei: `<sedra>` = Wurzel des Repos.

## 0. Ergebnis in Kürze

1. **Teil A (Master-Modus):** Die Aufgaben-Freigabe trägt den größten Teil (Sitzung, Frist, Zähler, Audit, Schild, Rücknahme), **passt aber nicht als Sonderfall**: sie ist eine positive Liste mit Obergrenzen (24 h, 500 Aufrufe), warnt vor weiten Mustern und vor „Schreiben + beliebig ausführen“ (S9), und liegt als Datei auf der Platte. Der Master-Modus ist das Gegenteil – eine weite Erlaubnis mit **Sperrliste**, nur im Speicher. Beides in `aufgabe.py` zu verbiegen würde eine Prüfstelle lockern. Vorschlag: **kleines eigenes Modul `harness/master.py`** (rein), das **als eine weitere Deckungsquelle in `deckung.deckt`** hängt, neben Aufgabe und Sitzungs-Erlaubnis. Gleicher Guard-Weg, gleicher `approve`-Ort, kein neuer Freigabe-Weg (MM-12).
2. **Der Master-Modus macht nur aus „Karte“ ein „gedeckt“.** Er erzeugt nie `verboten`, hebt nie `verboten`, keinen harten Vorbehalt, keine Warnkarte, keinen Oberflächen-Code, keinen ungesehenen Code (G4). Eine Sperre heißt: der Master deckt nicht, es gilt die normale Einstufung (meist Karte).
3. **Zwei Befunde, die der Captain entscheiden muss (§7):** (O-1) Der Vorbehalt „ungesehener Code“ (G4) lässt jeden `befehl` und `lauf_starten` nach einem vom Modell geschriebenen Code-Stück wieder zur Karte werden – der Master nähme dann nur einen Teil der Karten weg. (O-2) `del`, `rm`, `rmdir` stehen heute als **fester Vorbehalt** in `vorbehalte.BEFEHLE`; „Löschen bis 20 Dateien in der Wurzel“ geht nur, wenn dieser Vorbehalt eine Master-Ausnahme bekommt. Vorschlag für v1: Löschbefehle bleiben Karte.
4. **Teil B (Gedächtnis):** Ergänzung, kein Ersatz: kuratierte Markdown-Notizen mit Index `MEMORY.md` neben dem bestehenden jsonl-Protokoll. Der Index wird beim Start einer Sitzung eingefroren in den Systemprompt gelegt (Größenkappe, Cache-stabil). Das Modell legt Notizen nur als **Antrag** an (Captain bestätigt), der Captain kann selbst anlegen und ändern. Die Übernahme der vorhandenen Claude-Notizen ist **nicht entschieden** (O-B2).

## 1. Befund (Ist-Stand, belegt im Code)

| Befund | Beleg |
|---|---|
| Reihenfolge je Aufruf: Vorbehalt → Katalog → Deckung → Guard; die Deckung entscheidet eine Funktion | `freigabe.einstufung`, `Kiste.aufruf`, `deckung.deckt` |
| `deckung.deckt` kennt zwei Quellen: Aufgabe (nur lokale Modelle), Sitzungs-Erlaubnis (nur lokale Modelle, nie bei weichem Vorbehalt) | `deckung.py` Z. 1 bis 25 |
| Es gibt genau einen `approve`-Ort für gedeckte Aufrufe: `Kiste.aufruf`; `test_freigabe_vollstaendig` hält jede Stelle in `desk/freigabeklasse.APPROVE_STELLEN` fest | `freigabe.py`, Test `ApproveStellen` |
| Aufgabe: Datei je Aufgabe, `bis` höchstens 24 h, `max_aufrufe` höchstens 500, positive Liste `erlaubt`, Warnung bei weiten Mustern und bei Schreiben+Interpreter (S9), angelegt nur vom Captain hinter der Tür (`harness:aufgabe_anlegen`, Klasse H) | `aufgabe.py`, `api.aufgabe_anlegen` |
| Rücknahme einer Aufgabe beendet auch einen laufenden `befehl` (`befehl.RUECKNAHME`, Schlüssel `aufgabe_id`) | `befehl.py` |
| Fester Vorbehalt für Befehle: `git push`, `git branch -f`, `git reset --hard`, `del`, `rm`, `rmdir`, `remove-item`, `format`, `curl`, `wget`, `invoke-webrequest`, `pip install`, `winget` | `vorbehalte.BEFEHLE` |
| Fester Vorbehalt Pfade: `local_config`, Katalog, Kern, Harness-Code, Prüfstellen, `runtime_data/harness/**`, `.git`; außerhalb der Wurzel | `vorbehalte.PFADE` |
| Weicher Vorbehalt: Modelle laden/entladen (nur eine Aufgabe, die das Modell nennt, deckt) und Code der Oberfläche (`uix/shells`, `tools`, `css`; nur Aufgabe mit `oberflaeche`) | `vorbehalte.pruefen_weich` |
| **Ungesehener Code (G4):** liegt im Projekt Code, den der Captain nicht gesehen hat, ist jeder `befehl`/`lauf_starten` ein harter Vorbehalt; vom Modell geschriebener Code gilt nie als gesehen | `vorbehalte.pruefen` (Parameter `ungesehen`), `code_stand.py` |
| `befehl` läuft ohne Shell (keine Pipes, `&&`, `;`), im Ordner in der Wurzel, höchstens 600 s | `befehl.py` |
| `datei_schreiben` auf eine bestehende Datei mit starker Änderung: Hinweis, beim zweiten Mal Warnkarte (bleibt beim Captain) | `Kiste.aufruf` W-1/W-2 |
| Der Schreibbereich je Projekt ist die harte Grenze für Schreiben; `projekte.py` schreibt die Projektliste beim Speichern **neu aus festen Feldern** (`id, name, wurzel, schreibbereich`) – ein neues Feld geht dabei verloren, wenn es dort fehlt | `projekte.py` Z. 122 |
| Gedächtnis heute: eine Notiz je Antwort (jsonl, ohne Modell), Suche mit `erinnern`, Verdichtung auf Wunsch; **kein Index im Systemprompt, keine Typen**; Einstellung `gedaechtnis_reichweite` kann die Suche auf alle Projekte ausdehnen | `gedaechtnis.py`, `api._reichweite` |

## 2. Ziel

**A:** Der Captain schaltet in einer Harness-Sitzung für ein Projekt den Master-Modus ein; Dateien, Läufe und Modelle laufen dort ohne Karte, Befehle ohne Karte außer der Sperrliste. Jederzeit ein Knopf zum Ausschalten, deutliche Anzeige, jeder automatisch freigegebene Aufruf steht im Audit. **B:** Neue Chats eines Projekts starten mit einem kurzen, lesbaren Index des gesicherten Wissens dieses Projekts und können es gezielt nachlesen.

## 3. Anforderungen Teil A: Master-Modus

Quelle der Entscheidungen: Captain, 16.11.2026 im Chat. „Prüfbar durch“ nennt Test oder Beleg.

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| MM-01 | **Ort:** neues Feld `master` je Projekt in `local_config/harness_projekte.yaml` (Vorlage `runtime/config/harness_projekte.beispiel.yaml`): Liste von Mustern relativ zur Wurzel, ohne `..` und ohne Laufwerk, wie `schreibbereich` (`runtime/**`, `docs/**`). Fehlt es oder ist es leer, **kann der Master-Modus in diesem Projekt nicht eingeschaltet werden**. `projekte.py` liest, prüft und **erhält** das Feld beim Zurückschreiben der Datei. Das Feld ist die *Erlaubnis und Eingrenzung*, nicht der Schalter. | Einheitstest `projekte` (gültig, ungültig, Rundlauf Speichern/Laden) |
| MM-02 | **Wer schaltet:** nur der Captain, in der Oberfläche der Harness-Sitzung: `POST /api/harness/sitzungen/<id>/master` mit `{an: true}`. Das ist **Klasse H** (Rechte für später): es läuft durch die Tür (`api._tuer`, Ja außerhalb des Browsers) und durch die Herkunftsprüfung (S7: Anfrage aus einem Harness-Prozess wird abgelehnt). Es gibt **kein Werkzeug des Modells**, keine Vorlagen-Eigenschaft und keine Datei, die ihn einschaltet; eine Vorlage mit `erlaubnisse` oder Aufgabe kann ihn nicht auslösen. | Test: Werkzeugliste, Vorlagen-Prüfung; Test Herkunft; Eintrag in `freigabeklasse` |
| MM-03 | **Dauer:** der Zustand lebt nur im Speicher des Servers, gebunden an die `sitzung_id` und das Projekt der Sitzung. Er endet durch Aus-Knopf (MM-04), Löschen oder Aufräumen der Sitzung, Neustart des Servers, oder nach **24 Stunden** (Vorschlag, gleiche Höchstdauer wie die Sitzungs-Erlaubnis, FS-14; O-5). Nichts steht in einer Datei außer dem Audit; nach einem Neustart ist jede Sitzung ohne Master. | Test: neue `HarnessApi`-Instanz; Test Ablauf mit festgelegter Uhr |
| MM-04 | **Aus:** `POST …/master` mit `{an: false}` und der Knopf in Schild und Taskleiste: **Klasse N**, ohne Tür, sofort. Ab dem nächsten Aufruf gilt wieder die normale Einstufung; ein unter dem Master laufender `befehl` endet wie bei der Rücknahme einer Aufgabe (`befehl.RUECKNAHME`, Schlüssel `master:<sitzung_id>`). | Test: Aus, danach Karte; Test: laufender Befehl endet |
| MM-05 | **Was der Master deckt** (nur diese Werkzeuge, nur in diesem Rahmen): `datei_lesen`, `dateien_auflisten`, `suchen`, `datei_schreiben`, `datei_aendern` – Pfad im Muster aus MM-01 **und** im Schreibbereich (Schreiben); `befehl` – Arbeitsordner im Muster, Zeile nicht in der Sperrliste (MM-07); `lauf_starten`, `lauf_stoppen`; `modell_laden`, `modell_entladen` (deckt den weichen Vorbehalt „Modell“ für das ganze Projekt, unabhängig vom Muster). Jedes andere Werkzeug (Vorarbeiter, `desktop_aendern`, `profil_wechseln`, `auftraege_verteilen`, `sitzungen_aufraeumen`, …) bleibt unverändert. | Wahrheitstabelle Werkzeug × Fall |
| MM-06 | **Der Master hebt nie:** die Stufe `verboten`; einen **harten Vorbehalt** (`vorbehalte.pruefen`, Pfade und Befehle); eine **Warnkarte** (W-2); den weichen Vorbehalt der **Oberfläche** (Klasse H); **ungesehenen Code** (G4, siehe O-1); alles außerhalb der Wurzel und des Schreibbereichs; Netz/Cloud, Push/Merge, Installationen; den Inhaltsschutz (greift im Modellaufruf, nicht in der Kiste). Der Master wirkt nur bei **lokalem Modell** (wie Aufgabe und Sitzungs-Erlaubnis, HS-27, FS-13); Cloud-Modell: unverändert Karte (O-4). | Vergleichstest `deckung` alt/neu ohne Abweichung bei Master aus; Tests je Fall mit Master an |
| MM-07 | **Sperrliste für `befehl`** (im Code von `master.py`, nicht konfigurierbar, nur enger zu stellen): Treffer = der Master deckt nicht. Mindestens: **Netz** (`curl`, `wget`, `invoke-webrequest`, `iwr`, `invoke-restmethod`, `ssh`, `scp`, `ftp`, `nc`, `telnet`, `git fetch/pull/clone/remote`); **Installieren** (`pip install` auch als `python -m pip`, `py -m pip`, `npm install/i/ci`, `npx`, `yarn`, `pnpm`, `winget`, `choco`); **Git-Verlauf und Zweige** (`git push`, `git merge`, `git rebase`, `git checkout`/`switch` auf `main` oder `master`, `git branch -d/-D/-m/-f`, `git reset --hard`, `git update-ref`, `git clean`, `git config`); **Löschen** (`del`, `erase`, `rm`, `rmdir`, `rd`, `remove-item`, `format`); **Shell-Ausbruch** (`powershell`, `pwsh`, `cmd`, `bash`, `sh`, `wsl`, `wscript`, `cscript`, `mshta`, `rundll32`, `regsvr32`, `certutil`, `bitsadmin`, `start`; dazu `python -c` und `python -m http.server/urllib/webbrowser/ensurepip`). Was ein gestartetes Skript selbst tut, erkennt die Zeile nicht (siehe §6). Die Liste ist eine Zeilenprüfung, kein Käfig (§6). | Einheitstest je Sperre; Test der Normalisierung (Groß/Klein, Mehrfach-Leerzeichen, `.exe`) |
| MM-08 | **Nichts außerhalb der Wurzel:** der Arbeitsordner und jedes Argument, das wie ein Pfad aussieht (Laufwerk, `\\`, `/`, `..`, beginnt mit `~`, `%…%`), wird gegen die Wurzel aufgelöst (`resolve`, Junctions und Links aufgelöst); liegt eines außerhalb der Wurzel oder des Musters, deckt der Master nicht. Umgebungsvariablen und Pfadteile, die nicht aufzulösen sind (Platzhalter in Pfaden mit `..`), gelten als Treffer. | Test mit `..`, absolutem Pfad, Junction, UNC |
| MM-09 | **Menge beim Löschen:** In v1 bleiben alle Löschbefehle Karte (fester Vorbehalt, MM-06/O-2). Die Grenze „mehr als 20 Dateien“ wird **als Zahl in `master.py` festgehalten** (`LOESCHEN_MAX = 20`) und von der Entscheidungsfunktion geprüft, damit eine spätere Master-Ausnahme im Vorbehalt (nur mit G4 und Entscheidung O-2) sofort sicher ist; heute greift sie nie, weil der Vorbehalt vorher trifft. | Test der Zählung (Platzhalter, Ordner rekursiv) |
| MM-10 | **Audit:** Einschalten `HARNESS_MASTER_AN {sitzung_id, projekt, muster, bis}`, Ausschalten `HARNESS_MASTER_AUS {sitzung_id, grund: captain|sitzung_weg|ablauf|neustart, aufrufe}`; **je automatisch freigegebenem Aufruf** `HARNESS_MASTER_AUFRUF {sitzung_id, werkzeug, ziel[:300], nr, master: true}` zusätzlich zum bestehenden `HARNESS_APPROVED_BY` mit `approved_by: master:<sitzung_id>`, `kanal: master`; je Sperre `HARNESS_MASTER_NICHT {werkzeug, ziel[:300], grund}`; zusätzlich `HARNESS_ERLAUBNIS` (Aktion erteilt/zurückgenommen, Dauer `sitzung`, Herkunft `master`). Der Aufruf im Verlauf trägt das Kennzeichen `master`. | Audit-Test je Ereignis; Verlauf-Test |
| MM-11 | **Anzeige und Aus-Knopf:** siehe §5 (UIX). Die Harness liefert dafür `GET /api/harness/sitzungen/<id>/master` → `{aktiv, seit, bis, aufrufe, projekt, muster, gesperrt: n}` und das Ereignis `harness.master` (wie `harness.aufgabe`). | Test der Wege und des Ereignisses |
| MM-12 | **Kein neuer Weg an der Freigabe vorbei:** Reihenfolge Vorbehalt → Katalog → Deckung bleibt. Der Master ist **eine Quelle in `deckung.deckt`** (neuer Parameter `master_treffer`, Standard `None`, Ergebnis `via_master`); `Kiste.aufruf` ruft dafür **denselben** `guard.approve(gate)` wie für Katalog, Aufgabe und Sitzung – keine neue `approve`-Stelle. Neu in `desk/freigabeklasse.py`: Art `harness:master_schalten` = H und der Weg `master` in `ROUTEN_HARNESS`; neu in `harness/api.py`: der Weg im Muster `WEG` und `GESCHUETZT`. `tests/test_freigabe_vollstaendig.py` bleibt grün. | `test_freigabe_vollstaendig`, `test_harness_deckung_vergleich` |
| MM-13 | **Schnittstelle für fremde Harnesses** (nur festgehalten, nicht gebaut): `master.entscheiden(zustand, *, werkzeug, ziel, args, herkunft, projekt, wurzel) -> {entscheidung: 'gedeckt'\|'karte', regel, grund}`. Reine Funktion, ruft intern dieselben Prüfungen wie die Kiste (`vorbehalte`, Sperrliste, Wurzel). Der spätere Anschluss ruft sie für **Rückfragen des fremden Harness nach Dateien und Befehlen in der Wurzel desselben Projekts**; was **die Rechte des fremden Harness selbst** betrifft (Berechtigungsmodus, Werkzeug freischalten, Netz, MCP, Hooks, Sandbox), ist nie gedeckt (`karte`, Grund `fremdes_recht`). Befehlszeilen mit Shell-Zeichen (`\| > & ; $(`) sind nie gedeckt (ein fremdes Harness kennt die Shell-Regel von `befehl.py` nicht). Die Funktion gibt nur eine Entscheidung zurück; ein Anschluss, der danach `approve` ruft, braucht einen Eintrag in `APPROVE_STELLEN` (der Test erzwingt das). | Einheitstest der Funktion mit `herkunft: fremd`; Test: Rechte-Fragen → Karte |
| MM-14 | **Rückfall:** Master aus = Verhalten wie vor diesem Paket (Vergleichstest). Jeder Fehler in `master.py` (Ausnahme, unlesbare Zeile, unbekanntes Werkzeug) = **keine Deckung**, also Karte – nie ein stilles Freigeben. Ist das Feld `master` ungültig, nennt die Harness den Grund und der Schalter bleibt aus. | Test: Ausnahme im Treffer → Karte |
| MM-15 | **Wiederholungsdeckel bleibt:** der Schutz FS-40/41 (derselbe gedeckte Aufruf ohne Schreiben dazwischen höchstens 2-mal) gilt auch für `via_master`; er darf nur enger werden (FS-42). Ein Schleifenfehler eines lokalen Modells holt den Captain also weiter an die Karte. | Test: dritter gleicher Aufruf → Karte |
| MM-16 | **Harness-Code:** `harness/master.py` kommt in `vorbehalte.PFADE` (Harness-Code, kein Schreiben durch das Modell). Änderungen an `freigabe.py`, `deckung.py`, `vorbehalte.py`, `desk/freigabeklasse.py` und der Test-Bestandsliste nur mit **G4** des Captains in der Sitzung. | Test `vorbehalte` |

## 4. Entwurf Teil A

### 4.1 Aufbau

```
Aufruf ─► Vorbehalt (hart) ─► Katalog ─► (Warnkarte? / weicher Vorbehalt Oberfläche?) ─► deckung.deckt
                                                                          1 frei
                                                                          2 Vorbehalt/Warnkarte: keine Deckung
                                                                          3 Aufgabe (zählt)
                                                                          3b MASTER  (neu; nur ohne Aufgabe, lokal, Sitzung hat Master)
                                                                          4 Sitzungs-Erlaubnis
                                                                          5 Karte
  gedeckt ─► guard.create_gate → approve (EIN Ort) → Audit approved_by master:<sitzung> → Werkzeug
```

Die Aufgabe geht vor dem Master (genauer, hat Zähler); der Master vor der Sitzungs-Erlaubnis. Er **zählt** nur für Anzeige und Audit, nicht als Grenze. `weich_werkzeug()` mit `oberflaeche` → der Master deckt nicht; mit `modell` → er deckt (MM-05).

### 4.2 `harness/master.py` (rein, neu)

- `pruefen_feld(muster_liste)`: Gültigkeit von `master` (MM-01).
- `Zustand` (im Speicher, Sperre): `an(sitzung_id, projekt, muster, jetzt)`, `aus(sitzung_id, grund)`, `aktiv(sitzung_id, jetzt)`, `zaehlen`, `ablauf`.
- `deckt(zustand, sitzung_id, werkzeug, ziel, args, wurzel, jetzt) -> {sitzung_id, regel} | None`: Werkzeug in MM-05, Muster, bei `befehl` Sperrliste (MM-07) und Wurzel (MM-08), jede Ausnahme → `None`.
- `entscheiden(...)` (MM-13) ruft dieselbe Prüfung, mit `herkunft` und ohne Zustand der Kiste.

### 4.3 Änderungen in bestehenden Dateien (alles G4)

| Datei | Änderung |
|---|---|
| `harness/deckung.py` | Parameter `master_treffer=None`; Ergebnis `via_master`; bei `None` bit-gleich zu heute |
| `harness/freigabe.py` | `Kiste.__init__(…, master=None)`; Aufruf von `deckt` mit `master_treffer`; `von`/`kanal` `master`; `HARNESS_MASTER_AUFRUF`/`_NICHT`; `kontext['aufgabe_id'] = 'master:<sitzung>'` für die Rücknahme laufender Befehle |
| `harness/vorbehalte.py` | nur der Eintrag `harness/master.py` in `PFADE` (und bei O-2 später eine Ausnahme) |
| `desk/freigabeklasse.py` | Art `harness:master_schalten` (H), Weg `master` in `ROUTEN_HARNESS` |
| `harness/api.py` | Weg `master` (GET, POST), Zustand je Server, Anbindung an `_kiste`, Aufräumen bei Sitzung löschen, Ereignis `harness.master` |
| `harness/projekte.py`, `config/harness_projekte.beispiel.yaml` | Feld `master` |
| `tests/test_freigabe_vollstaendig.py` | nur falls die Zahl der Wege es verlangt (neuer Eintrag, keine Lockerung) |

### 4.4 Bau in kleinen Schritten (je Commit, nach dem Ja zur Spec)

| Schritt | Inhalt | Prüfung |
|---|---|---|
| A1 | `master.py` (Sperrliste, Wurzel, Muster, Zustand) + Einheitstests; noch nicht angeschlossen | neue Tests, Gruppe Harness |
| A2 | Feld `master` in `projekte.py`/Vorlage | Tests `projekte` |
| A3 | `deckung.py` + `freigabe.py` Einbau, Audit | Vergleichstest `deckung`, `test_harness_freigabe`, `test_freigabe_vollstaendig` |
| A4 | Wege in `api.py`, Tür, Herkunft, `freigabeklasse`, Ereignis | `test_freigabe_*`, API-Tests |
| A5 | `entscheiden()` und Test der Schnittstelle | Einheitstests |
| A6 | Beschreibung der Oberflächen-Schnittstelle für den UIX-Koordinator (Datei in `docs/`), keine Shell-Änderung | Review |

## 5. UIX (Abstimmung mit dem UIX-Koordinator; nicht von dieser Sitzung gebaut)

Die Harness-Shell wird hier **nicht** umgebaut. Die Spec legt nur fest, was die Oberfläche bekommt und tun muss (Bezug HS-17, Schild):

- **Schild** (`eingabe.js`, heute „⛨ Captain gibt frei · Katalog n Regeln“): bei aktivem Master dauerhaft **„⛨ MASTER · <Projekt> · <n> Aufrufe“** in Warnfarbe, nicht wegklappbar, mit **Aus-Knopf** direkt daran (ein Klick, keine Bestätigung).
- **Taskleiste:** Eintrag „Master an · <Sitzung>“, Klick = Aus.
- **Einschalten:** Knopf im Schild-Menü der Sitzung, nur sichtbar, wenn das Projekt `master` hat; zeigt vorher **Projekt, Muster und die Sperrliste in Klartext**; danach die Tür (Ja außerhalb des Browsers).
- **Karte bei Sperre:** wenn der Master einen Aufruf nicht deckte, nennt die Karte den Grund („Master-Modus deckt nicht: Netz“).
- **Verlauf:** Aufrufe unter dem Master tragen ein Zeichen `master`.
- **Daten:** `GET …/master` und Ereignis `harness.master` (MM-11). Texte in `strings_de*.js`/`strings_en*.js`.
- **Offen mit dem UIX-Koordinator:** Platz des Knopfs, Farbe/Token der Warnanzeige, ob die Taskleiste ihn zeigt.

## 6. Abgrenzung und ehrliche Grenzen

- **Nicht Teil:** das Hosten fremder Harnesses (Claude Code, Pi, Hermes), nur die Schnittstelle MM-13. Keine Dauerfreigabe in einer Datei. Kein Master für Cloud-Modelle (O-4). Keine Änderung am Katalog, am Guard, am Inhaltsschutz.
- **Die Sperrliste ist eine Prüfung der Befehlszeile.** Was ein freigegebener Aufruf **danach tut**, sieht sie nicht: ein Modell kann eine Datei schreiben (gedeckt) und ein Programm starten (`python skript.py`), das im Netz oder an Dateien arbeitet. Gegenmaßnahmen im Bestand: der Vorbehalt „ungesehener Code“ (G4) und die Wurzel-/Schreibbereichs-Grenze für Dateien. Darum bewusst O-1: Solange G4 gilt, holt jeder Code-Lauf nach neuem Modellcode den Captain; fällt G4 für den Master, ist **der Master-Modus für lokale Modelle de facto Vollzugriff als Windows-Benutzer** – der Captain entscheidet das mit Kenntnis.
- Der Master ändert nichts an der Sperre von `local_config`, Katalog, Kern, Guard, Harness-Code, Prüfstellen: Das Modell kann sich den Master weder einschalten noch lockern (MM-02, MM-16).
- Nicht geprüft in dieser Spec: Verhalten bei mehreren gleichzeitigen Sitzungen desselben Projekts (jede Sitzung hat ihren eigenen Schalter; keine Vererbung auf Unter-Sitzungen oder Vorarbeiter-Sitzungen).

## 7. Offene Fragen an den Captain (Teil A)

| Nr | Frage | Vorschlag |
|---|---|---|
| O-1 | **Ungesehener Code (G4):** soll der Master ihn decken? Ohne: nach jedem vom Modell geschriebenen Code-Stück (`.py`, `.js`, `.bat`, …) geht der nächste `befehl`/`lauf_starten` wieder als Karte. Mit: das Modell schreibt und startet Code ohne Sicht des Captains. | **Nein, G4 bleibt** (Sicherheit). In der Abnahme zählt der Bericht, wie oft das passiert; danach neu entscheiden (z. B. „Sammelkarte: Code der Sitzung gesehen“, ein Klick). |
| O-2 | **Löschen:** `del`/`rm`/`rmdir` sind fester Vorbehalt. Soll es unter dem Master bis 20 Dateien in der Wurzel ohne Karte gehen? Das braucht eine Ausnahme im Vorbehalt (G4) und eine Pfad- und Mengenprüfung der Argumente. | **v1: Löschen bleibt Karte** (MM-09 hält die Zahl 20 bereit). Wenn du es willst: eigener, kleiner Schritt A7. |
| O-3 | **„Schalten über Oberfläche oder `local_config`“:** ich lese es so: `local_config` trägt die *Erlaubnis und Eingrenzung* (Feld `master`), die Oberfläche den *Schalter je Sitzung*. Kein Beginn des Master aus einer Datei. | wie gelesen; sag, wenn du „beim Start einschalten“ aus der Datei meinst (das wäre eine Dauerfreigabe, widerspricht deiner Entscheidung). |
| O-4 | **Cloud-Modelle und fremde Harnesses:** heute deckt keine Aufgabe und keine Sitzungs-Erlaubnis bei Cloud-Modellen. Claude Code/Pi sind meist Cloud-Modelle. Soll der Master für fremde Harnesses trotzdem decken (MM-13, `herkunft: fremd`)? | v1: für Sedras eigene Harness nur lokal; **die Entscheidung für fremde Harnesses fällt beim Anschluss**, die Funktion hat dafür den Parameter. |
| O-5 | **Höchstdauer 24 h** als zusätzliche Grenze (neben „endet mit der Sitzung“)? | ja, gleiche Grenze wie die Sitzungs-Erlaubnis; ohne sie könnte eine tagelang offene Sitzung ewig weit freigegeben bleiben. |
| O-6 | **Wiederholungsdeckel** (MM-15) auch unter dem Master? | ja (Schleifenschutz; ohne ihn wiederholt ein hängendes Modell unbegrenzt Läufe). |

## 8. Teil B: Gedächtnis für neue Chats

### 8.1 Befund

Heute: je Antwort eine automatische Notiz im jsonl (`runtime_data/harness/gedaechtnis/<projekt-id>.jsonl`), Suche mit `erinnern`, Verdichtung auf Wunsch, Ansehen/Löschen/Export im Reiter. Es fehlt: ein **Index, der in jede neue Sitzung geladen wird**, Typen, Pflege durch Zusammenführen statt Anhäufen, Verknüpfungen, eine Form, die der Captain als Datei lesen und ändern kann.

### 8.2 Anforderungen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| GN-01 | **Form:** je Projekt ein Ordner mit `MEMORY.md` (Index: **eine Zeile je Notiz**, `- [Titel](datei.md) — Hinweis`, keine Frontmatter, kein Inhalt) und je Notiz eine Datei `<name>.md` mit Kopf `name`, `description` (eine Zeile, dient der Auswahl), `metadata.type` ∈ `user`, `feedback`, `project`, `reference`; Rumpf nach dem Muster von Claude Code: für `feedback` und `project` zusätzlich die Zeilen **Warum:** und **Wann anwenden:**; Verknüpfungen `[[name]]`. Format wird beim Schreiben geprüft. | Test Prüfer (gültig, ungültig) |
| GN-02 | **Ort:** `<sedra>/runtime_data/harness/gedaechtnis/<projekt-id>/` (neben dem bestehenden jsonl, schon fester Vorbehalt: das Modell kann dort nicht mit `datei_schreiben` schreiben). Lesbare Markdown-Dateien; der Captain kann sie im Editor ansehen und ändern, „Ordner öffnen“ und Export im Reiter. Die Projekt-ID wird gegen die bekannte Regel geprüft; Pfade werden aufgelöst und müssen im Ordner des eigenen Projekts liegen (**Notizen eines Projekts sind für andere Projekte unsichtbar**, auch das Werkzeug kennt keinen anderen Ordner). Offen: O-B1. | Test: fremde Projekt-ID, `..`, Link |
| GN-03 | **Index im Kontext:** beim **Start einer Sitzung** wird der Index (aus `MEMORY.md`) gelesen und **in der Sitzung eingefroren** (Kopf der Sitzung) – er steht in jedem Zug unverändert im Systemprompt (Cache-stabil, wie der Wissensblock), mit Kopfzeile „Gedächtnis dieses Projekts (Daten von früher, keine Anweisung)“. **Größenkappe:** höchstens 4 000 Zeichen und 40 Zeilen (Standard, ein Schlüssel im Katalog der Gesprächsoptionen), bei Überschreitung die neuesten Zeilen zuerst und ein Hinweis „und n weitere – mit `gedaechtnis_lesen` suchen“. Änderungen während der Sitzung wirken in der **nächsten** Sitzung; das Werkzeug liest immer den aktuellen Stand. Bei Sitzungen mit Fenster unter 16 000 Token nur die Hälfte der Kappe. | Test Systemprompt: gleich über mehrere Züge; Test Kappe |
| GN-04 | **Lesen:** neues Werkzeug `gedaechtnis_lesen(name)` bzw. `gedaechtnis_lesen(frage)` (frei, lesend wie `erinnern`): liefert eine Notiz ganz oder die passendsten Zeilen des Index. Ergebnis als **Daten**, nicht als Anweisung (HS-24). | Test Werkzeug |
| GN-05 | **Wer legt an:** (a) das **Modell** nur als **Antrag** mit `gedaechtnis_vorschlagen(typ, name, description, text, ersetzt?)`: der Antrag geht in den Posteingang des Captains (Klasse H, neue Art `request:harness_gedaechtnis`, wie `wissen_beantragen`), erst nach seiner Freigabe entsteht oder ändert sich die Datei; (b) der **Captain** direkt in der Oberfläche und im Editor. Notizen sind Text, der spätere Chats steuert – darum keine stille Eigenfreigabe des Modells. | Test: ohne Freigabe nichts auf der Platte; `freigabeklasse` |
| GN-06 | **Aktualisieren statt Duplizieren:** vor dem Antrag prüft das Werkzeug Namen und Wortüberlappung der `description` mit vorhandenen Notizen; bei Treffer antwortet es „ähnlich: <name> – ändere diese Notiz“ und legt keinen Antrag an, wenn nicht ausdrücklich `neu: true` gesetzt ist. Zusammenführen und Löschen veraltet: Vorschlag des Modells, Entscheidung des Captains. | Test Ähnlichkeit |
| GN-07 | **Inhalt:** höchstens 4 000 Zeichen je Notiz, höchstens 100 Notizen je Projekt; ein Prüfer lehnt Schlüssel-Muster (API-Schlüssel, Token), absolute lokale Pfade und Zeilen ab, die wie Anweisungen an das System aussehen („ignoriere …“); das Modell erfährt den Grund. | Test Prüfer |
| GN-08 | **Verhältnis zum jsonl:** **ergänzen, nicht ersetzen.** Das jsonl bleibt das automatische Protokoll (Suche mit `erinnern`, Verdichtung); die Notizen sind das kuratierte Wissen. Keine automatische Migration. Eine Zusammenfassung aus der Verdichtung kann der Captain per Knopf „Als Notiz vorschlagen“ in einen Antrag verwandeln (später, nicht v1). | Test: jsonl unverändert |
| GN-09 | **Privatsphäre:** die Notizen liegen lokal und gehen in keine Cloud-Anfrage, außer das Gespräch selbst läuft über ein Cloud-Modell (dann steht der Index im Systemprompt – wie jeder andere Projekttext; der Inhaltsschutz wirkt wie bei jeder Anfrage). Eine Sitzung mit Cloud-Modell bekommt den Index nur, wenn der Captain es in den Gesprächsoptionen erlaubt (Standard: aus). | Test: Cloud-Sitzung ohne Index |
| GN-10 | **Rückfall:** fehlt der Ordner oder ist `MEMORY.md` kaputt, startet die Sitzung ohne Index (Hinweis in der Sitzung); eine kaputte Notiz bricht nichts. Option „Gedächtnis-Index aus“ je Projekt. | Test Fehlerfälle |

### 8.3 Entwurf

- Neues Modul `harness/gedaechtnis_notizen.py` (Ordner, Prüfer, Index lesen/schreiben, Ähnlichkeit, Kappe); `gedaechtnis.py` bleibt unverändert.
- `schleife.system(...)` bekommt einen Block `GEDAECHTNIS_KOPF` (wie `GELERNT_KOPF`/`WISSEN_KOPF`); der Text kommt aus dem eingefrorenen Stand im Sitzungskopf.
- Werkzeuge `gedaechtnis_lesen` (ohne Karte, in `OHNE_KARTE`) und `gedaechtnis_vorschlagen` (Antrag, in `OHNE_KARTE`, wie `wissen_beantragen`); Eintrag in `katalog.WERKZEUGE`, in den Vorlagen der Harness, in `freigabeklasse` (Art `request:harness_gedaechtnis` = H).
- Wege in `harness/api.py` unter `gedaechtnis/…` (Liste, Lesen, Anlegen/Ändern/Löschen durch den Captain über die Tür, wo Klasse H).
- Oberfläche: Seite im Reiter „Gedächtnis“ (UIX-Koordinator): Liste mit Typ, Hinweis, Bearbeiten, „Ordner öffnen“, Anträge des Modells als Karten im Posteingang.

Bau: B1 Prüfer und Ordner, B2 Index und Kappe, B3 Werkzeuge, B4 Anträge/Wege, B5 Systemprompt-Einbau, B6 Beschreibung für die Oberfläche. Getrennte Commits, **nach Teil A**.

### 8.4 Offene Fragen an den Captain (Teil B)

| Nr | Frage | Vorschlag |
|---|---|---|
| O-B1 | **Ort:** in Sedras Ablage `runtime_data/harness/gedaechtnis/<projekt>/` (geschützt, das Modell schreibt nur über den Antrag) oder im Projektordner selbst (`<wurzel>/.sedra/gedaechtnis/`, sichtbar beim Projekt, aber dann braucht es einen festen Vorbehalt für diese Pfade, sonst schreibt das Modell mit `datei_schreiben` daran vorbei)? | Sedras Ablage; „Ordner öffnen“ und Export im Reiter. |
| O-B2 | **Übernahme der vorhandenen Claude-Notizen** (aus dem Gedächtnis dieser Claude-Code-Umgebung): ja, teilweise oder nein? Sie enthalten private Angaben und lokale Pfade. **Keine Entscheidung von mir; ich habe nichts übernommen.** Möglich: (1) gar nicht; (2) nur die Struktur anlegen, leer; (3) Notiz für Notiz nach deiner Durchsicht, mit entfernten Pfaden und persönlichen Angaben, über den Antrag-Weg. | (2), bis du (3) ausdrücklich willst. |
| O-B3 | **Einstellung `gedaechtnis_reichweite`** (Suche über alle Projekte im jsonl): soll sie für die Notizen **nie** gelten (strikt je Projekt)? | ja, die Notizen bleiben immer je Projekt. |
| O-B4 | **Cloud-Modelle** bekommen den Index nur mit deiner ausdrücklichen Option (GN-09)? | ja. |

## 9. Rückfall (Gesamt)

Teil A: Master aus = Verhalten wie heute, Ausnahme in `master.py` = Karte (MM-14). Zurückbauen: Eintrag `master_treffer` in `deckung.py` und der Weg in `api.py` entfernen; das Feld `master` in der YAML wird ignoriert. Teil B: Index aus = Sitzungen wie heute; die Ordner mit Notizen bleiben als lesbare Dateien liegen; das jsonl-Gedächtnis ist unberührt.

## 10. Fertig heißt

1. Diese Spec vom Captain freigegeben (**G1**); die Änderungen an den Prüfstellen aus §4.3 mit **G4** in der Sitzung.
2. Teil A als A1 bis A6, Teil B als B1 bis B6, je Schritt Tests der Gruppen aus `benchmarks/run_tests.py` (Exit-Code geprüft, bekannte rote Tests verglichen), je Teil ein eigener Commit auf dem Branch; `test_freigabe_vollstaendig` und `test_harness_deckung_vergleich` grün.
3. Bericht mit Zahlen, was nicht geprüft wurde, was am PC abzunehmen ist (Einschalten über die Tür, Aus-Knopf, Karte bei Sperre, ein Lauf mit Modell unter dem Master, Neustart des Servers).
