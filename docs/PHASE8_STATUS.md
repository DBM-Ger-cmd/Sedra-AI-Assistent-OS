# Phase 8 – status (2026-10-01): Kontextlänge, Worker-Schleife, Token-Steuerung, Prüfgate

Fertig: 8a (Kontext/Laden), 8b (Worker-Schleife, Modellwechsel), 8c (Token-Steuerung, Kontext-Stufen), 8d (Prüfgate, erster E1-Fall
bis `READY_FOR_ACCEPTANCE`, real). Offene Punkte am Ende; die Abschnitte "Offen" von 8a/8b sind durch den Nachtrag teilweise überholt.

## Prüfung: kann GUPPI die Kontextlänge an LM Studio übergeben?

**Ja, aber nicht über die Chat-API.** Gemessen auf dem Ziel-PC (LM Studio, `lms` CLI):

- Die OpenAI-kompatible Chat-API kennt keinen Kontext-Parameter. Wird ein Modell erst beim ersten Aufruf geladen, gilt LM Studios
  eigener Standard (qwen: 9,8 GiB statt 8,3 GiB bei 8192).
- `lms load <modell> --context-length N` setzt ihn. `lms ps --json` meldet `contextLength` und `identifier` jeder Instanz.
- **Zweimal laden ersetzt nichts.** Ein zweiter `lms load` desselben Modells mit anderem Kontext legt `<modell>:2` an. Anfragen an
  `<modell>` gehen weiter an die **alte** Instanz. Beide zusammen belegten 11,76 von 12 GiB.
- `lms load --estimate-only` liefert LM Studios eigene Speicherschätzung (qwen bei 8192: 8,67 GiB; gemessen wurden 8,26 bis 8,6).
- `lms load` ohne `-y` kann auf eine Eingabe warten; ohne `stdin` und mit der Windows-Codepage kann die Ausgabe nicht gelesen werden.

## 8a – `model_loader.py` (Flag `model_loader.enabled`, Standard aus)

Ablauf in `confirm_start` des Supervisors:

1. Rolle auflösen (Router). Bei `hardware_pressure` und `evict_idle_models: true`: ungenutzte Modelle entladen, Hardware neu lesen,
   einmal erneut auflösen.
2. `clear_stale`: veraltete oder doppelte Instanzen **dieses** Modells mit anderem Kontext entladen (Richtlinie `reload`; `refuse`
   bricht stattdessen ab). Das passiert **vor** der Reservierung, sonst zählt der Scheduler ihren Speicher als „belegt“.
3. Reservierung. Ein bereits geladenes, wiederverwendbares Modell wird nicht als zweite Kopie gezählt (`resident_vram_gb`, nur auf
   der Messseite, nie über die Anfrage hinaus, das Hauptbuch bleibt unberührt).
4. `ensure`: LM Studios Schätzung gegen die Reservierung prüfen (Abbruch mit `hardware_pressure`, wenn sie größer ist als
   Reservierung + 0,5 GiB), laden mit `--context-length`, `--gpu`, `--identifier <modell>`, `--yes`, danach über `lms ps --json`
   prüfen, dass der Kontext wirklich gesetzt wurde. Sonst wird entladen und der Start schlägt mit `provider_unavailable` fehl.

Der Versuch trägt danach `model`, `model_identifier` und `loaded_context`; der Worker ruft genau diese Instanz.

Weitere Änderungen: `CommandRunner` (utf-8, `stdin` zu), `load_model(..., yes=)`, `HardwareManager.get_state(fresh=True)` umgeht jetzt
den 5-Sekunden-Cache der GPU-Werte (vorher las eine Entscheidung direkt nach dem Entladen noch den alten VRAM-Wert),
`ResourceScheduler.refresh()`, `resolution["load_profile"]`, `failure_classes`: ein Grund, der selbst eine Fehlerklasse ist, bedeutet
diese Klasse.

## 8b – `job_worker.py`

- `Worker.run_once` / `run_forever`: Reaper im konfigurierten Takt zwischen den Jobs, `startup_recovery` beim Start, Heartbeat auf
  eigenem Thread während der Handler arbeitet, Abbruch (`cancel`) wird bestätigt, verlorener Lease endet still.
- Ein Handler, der wirft, wird mit Ausnahme und `ctx.mark_mutated()` gemeldet; ein ändernder Versuch mit unbekanntem Ausgang wird
  nie wiederholt (Regel des Supervisors).
- `model_text_handler`: stellt dem aufgelösten Modell eine Frage über `ControlMasterModule.model_call` (gleicher Weg, Audit und
  Metriken wie bei Missionen). Eine leere oder abgeschnittene Antwort ist ein Fehler, kein Ergebnis.
- Der Worker setzt nie `PASSED`.

## Echt geprüft (Wegwerf-Kopie des Projekts, Schalter nur im Speicher, Modelle danach entladen)

| Lauf | Ergebnis |
|---|---|
| qwen mit **falschem** Kontext (4096) vorgeladen, Job gestartet | veraltete Instanz entladen, mit 8192 neu geladen und per `lms ps` bestätigt, Aufruf an die richtige Instanz, Audit-Kette gültig |
| gemma untätig geladen, Reviewer-Job (qwen) über den Worker | Start zuerst wegen Platzmangel abgelehnt, gemma verdrängt, qwen mit 8192 geladen, Antwort erhalten, Reservierung gebucht, Zähler 0 |
| Verifier-Job ohne gebauten Vorgänger | **abgelehnt** (`requirements_unmet`): ohne bekannten Builder-Schlüssel ist Unabhängigkeit „unbekannt“ |

## Messungen und Befunde aus den Läufen

- qwen verbrauchte für eine Zwei-Satz-Antwort 1128 bis 1195 Denk-Tokens (`max_tokens` 1500 war knapp). Reasoning-Modelle brauchen
  großzügige Limits; sonst kommt „leer, abgeschnitten“.
- Nach dem Laden zeigte die GPU 9,1 bis 9,5 GiB (Differenz zu vorher 8,3 bis 8,6 GiB).
- Beim Wechsel dauert Entladen + Laden rund 5 bis 6 Sekunden.

## Tests

`test_model_loader` (29), `test_job_worker` (18), dazu Ergänzungen in `test_resource_scheduler` und `test_hardware_manager`.
Letzter vollständiger Lauf vor der letzten Textänderung am Scheduler: 844 Tests, ein Fehlschlag (ein Quelltext-Test, der das Wort
„unloaded“ in einem Kommentar beanstandete, behoben, die Datei läuft wieder grün). Die ganze Suite danach nicht erneut gestartet.

## Grenzen und Offen

- **Der E1-Fall bis PASSED fehlt.** `mark_passed` braucht ein echtes Prüfgate (Nachweise im Evidence-Store, Unabhängigkeit). Die
  Laufzeit übergibt dem Supervisor bisher keines (`pass_gate=None`), also gibt es keinen realen Weg zu `READY_FOR_ACCEPTANCE`.
  Damit kann ein Verifier-Job nicht real von einem Coder-Job abhängen; das Zusammenspiel Coder → Verifier mit echten Schlüsseln
  (qwen ≠ gemma) ist nur in Unit-Tests gesehen, nicht real.
- `workers: 1`: ein Job hält den Worker bis zu seinem Ende. Ein Job in `VERIFYING` blockiert die Warteschlange.
- Der Worker läuft nicht von selbst; es gibt keinen Start (Thread oder Dienst) in der Laufzeit. Nichts davon ist aktiviert.
- `evict_idle_models` entlädt jedes Modell, das kein laufender Versuch nutzt, auch eines, das der Captain für den eigenen Chat
  geladen hat. Standard aus.
- Der Versuch ruft das Modell über `ModelRouter` und `HardwareManager`; der alte Mission-Pfad (Mission → `ModelRouter.chat`) lädt
  weiterhin nicht selbst.
- Mehrere Nutzer von LM Studio (z. B. Spiel oder zweite App) sind nicht berücksichtigt; der Scheduler sieht nur den Gesamtverbrauch.
- Kev wurde nicht angebunden.

## Entscheidungen für den Captain

1. Soll das echte Prüfgate (Nachweise → `READY_FOR_ACCEPTANCE`) als nächstes gebaut werden? Das ist der Kern des E1-Falls.
2. `evict_idle_models` und `model_loader` in der echten Konfiguration einschalten, oder weiter nur in Testläufen?
3. Soll der Worker als Hintergrunddienst in `runtime.py` starten (Flag), oder bleibt er ein Werkzeug, das du bewusst startest?


---

# Nachtrag: 8c Token-Steuerung und Kontext-Stufen, 8d Prüfgate

Stand: der Golden Path (Dokumentations-Job → deterministische Prüfung → unabhängige Prüfung → Gate → `READY_FOR_ACCEPTANCE`) lief real
auf dem Ziel-PC. **Nichts wird aktiviert oder übernommen**; `READY_FOR_ACCEPTANCE` ist der Punkt, an dem der Captain entscheidet.

## 8c – Token-Nutzung steuern (nicht nur das Fenster vergrößern)

### Messungen (diese LM-Studio-Installation, 2026-10-01)

Gleicher Prompt, zwei Modelle, `max_tokens` 3000:

| Variante | qwen3.5-9b Ausgabe (davon Denken) | gemma-4-12b Ausgabe (davon Denken) |
|---|---|---|
| Standard | 1342 (1268) | 489 (419) |
| `reasoning_effort: "none"` | **77 (0)** | **65 (0)** |
| `reasoning_effort: "low"` | 1408 (1344) | 418 (342) |
| `chat_template_kwargs.enable_thinking=false` | 887 (819) | 586 (511) |
| `reasoning.effort: "none"` | 1544 (1479) | 494 (425) |
| Systemprompt `/no_think` | 703 (639) | 424 (348) |

Der einzige Hebel, der auf beiden Modellen zuverlässig wirkt, ist `reasoning_effort: "none"` (Antwortlänge gleich, Denken weg).
**Nicht gemessen:** ob die Antwortqualität ohne Denken schlechter wird. Deshalb ist es eine Entscheidung pro Rolle.

Kontext (idle nach `lms load ... --gpu max --parallel 1`, Basis 0,85 GiB abgezogen; KV-Cache-Typen wie in LM Studios gespeicherten
Modellvorgaben: qwen q8_0, gemma f16):

| Kontext | qwen (GiB) | gemma (GiB) |
|---|---|---|
| 8192 | 7,96 | ca. 7,8 |
| 16384 | 8,17 | 7,87 |
| 32768 | 8,57 | 8,13 |
| 49152 | 8,97 | 8,40 |
| 65536 | **9,39** | **8,66** |

Beide Modelle laden real mit 64k. LM Studios eigene Schätzung (`--estimate-only`) ist bei großem Kontext viel zu hoch (qwen bei
65536: 11,99 geschätzt, 9,39 gemessen; gemma: 16,81 geschätzt, 8,66 gemessen). Sie ist deshalb in `model_loader.yaml` aus
(`check_estimate: false`); die Rezepte tragen gemessene Werte. Wachstum je 1000 Token: qwen 0,0248 GiB, gemma 0,0162 GiB.

Die KV-Cache-Typen kommen aus LM Studios gespeicherten Modellvorgaben; `lms load` hat keine Option dafür, und GUPPI ändert sie
nicht (das wären private Dateien von LM Studio). Dein Hinweis (q8: 64k, f16: 54k) deckt sich in der Größenordnung mit der Messung;
die exakten Zahlen weichen ab, vermutlich weil dort andere Einstellungen galten.

### Was gebaut ist (alles hinter Schaltern, Standard aus)

- **Kontext-Stufen** (`profile.context.tiers`, `measured_maximum`, `measured_context`, `kv_cache_gb_per_1k_tokens` im Rezept):
  ein Job lädt die **kleinste** Stufe, die hält, was er braucht (`requirements.context_min_tokens`), nicht die größte, die passt.
  Der VRAM-Bedarf kommt aus Messung + Rate (qwen: `8,3 + 0,026 × (Kontext − 8192)/1000`). `measured_maximum` hebt die generische
  Hardware-Klassen-Grenze an (hier 32768) bis zu dem Wert, der real geladen wurde, nie über das Rezept-Maximum.
- **Token-Richtlinie** (`token_policy.py`, `config/token_policy.yaml`): pro Rolle Denk-Aufwand und Ausgabe-Budget. `reviewer`,
  `documentation`, `context_curator`, `tool_operator`, `tester`: `none`. Urteilende Rollen (`planner`, `researcher`, `coder`,
  `verifier`, `security_reviewer`) behalten das Denken, mit größerem Budget. Ist die Eingabe so groß, dass im Fenster nichts für die
  Antwort bleibt, wird gar nicht erst gesendet (`context_overflow`). Eine abgeschnittene Antwort bekommt **einen** Versuch mit
  größerem Budget; der erste zählt als Verschwendung (`wasted_output_tokens`), nicht als blindes Wiederholen.
- **Abrechnung:** `reasoning_tokens` landen in den Kontext-Metriken (pro Job summiert); der Handler liefert einen `token_report`
  (Aufrufe, Ein-/Ausgabe, Denk-Tokens, Verschwendung, Aufwand, Budget).
- `--parallel 1` beim Laden (LM Studios Vorgabe war bei qwen 2: ein zweiter, hier nie genutzter Slot).

### Echt geprüft

| Fall | Ergebnis |
|---|---|
| Reviewer-Job, Denk-Aufwand `none` | 70–78 Ausgabe-Tokens statt 1195 bei gleichem Inhalt (rund 94 % weniger) |
| Eingabe von ca. 11 000 Tokens, `context_min_tokens` 21 000 | Stufe 32768 wurde geladen (GPU 9,46 GiB), Antwort in 31 Tokens |
| Eingabe größer als das Fenster | wurde nicht gesendet (`context_overflow`) |

Unsere Eingabe-Schätzung lag bei 19 636, der Provider zählte 11 129: die Schätzung ist auf wiederholtem Text 1,8-fach zu
vorsichtig (sicher, aber teuer). Die Kalibrierung pro Modell (ab 20 Messungen) soll sie lockern; dafür liegen noch zu wenige vor.

## 8d – Das Prüfgate (`verification_gate.py`)

`mark_passed` und das neue `accept_verification` fragen das Gate. Es antwortet mit einer Liste von Lücken; leer heißt: das PASS darf
stehen. Es entscheidet nie selbst und schreibt nie in einen Job.

1. **Der Prüfbericht ist unversehrt** (Digest stimmt) und gehört zu **diesem** Kandidaten und **diesem** Vertrag.
2. **Der Kandidat ist festgenagelt:** er hat einen Inhalts-Hash, und jeder deterministische Nachweis wurde für genau diesen Hash
   erzeugt.
3. **Jedes Akzeptanzkriterium mit `id`** ist durch einen deterministischen PASS abgedeckt, der an Job und Kandidat gebunden ist.
   Ein fehlschlagender deterministischer Nachweis legt ein Veto ein. Eine Modell-Meinung ist nie deterministischer Nachweis.
4. **Die Nachweiskette ist gültig** (nichts wurde geändert oder entfernt).
5. Verlangt der Plan eine **unabhängige Prüfung**, muss ein **Prüf-Job** existieren: Kind-Job dieses Jobs, erfolgreich beendet,
   Urteil PASS, auf einem Modell mit **bekanntem und anderem** Unabhängigkeitsschlüssel als der Bauer. Gleicher oder unbekannter
   Schlüssel gilt als „nicht unabhängig“.

Supervisor: `bind_candidate` (Inhalts-Hash festlegen), `park_for_verification` (Worker und reservierter Platz werden frei, Zustand
`WAITING_VERIFICATION`), `complete_review` (Prüf-Jobs, `kind=review`), `accept_verification` (Gate muss zustimmen, sonst bleibt der
Job geparkt), `reject_verification` (→ `REWORK`, verlangt einen **anderen** Kandidaten). Ein Prüf-Job ist Kind des geprüften Jobs;
der Schlüssel des Bauers wird dem Router als „zu vermeiden“ mitgegeben. Außerdem sind `verifier` und `security_reviewer` jetzt
unabhängig von allen Rollen, die etwas bauen (`coder`, `documentation`, `tool_operator`, `hardware_engineer`), nicht nur von `coder`.
Der Worker kennt `job_finished` für Handler, die den Versuch selbst beenden (parken, Prüfung abschließen).

Hilfen: `record_check`, `record_review` (Nachweise schreiben), `document_check` (deterministische Prüfung für Texte, ohne Modell:
ist Text, begrenzte Größe, hat Substanz, keine geheimnisähnlichen Werte, keine verbotenen Phrasen, ausgewogene Code-Zäune).

### Golden Path, real (Wegwerf-Kopie, Schalter nur im Speicher, Modelle danach entladen)

1. Dokumentations-Job (qwen, Kontext 8192, Denk-Aufwand `none`): 94 Ausgabe-Tokens, Kandidat festgenagelt, `document_check` PASS,
   Job geparkt (`WAITING_VERIFICATION`, keine Reservierung, Worker frei).
2. **Abnahme ohne Prüfung:** vom Gate mit `independent_review_required` abgelehnt, Job blieb geparkt.
3. Prüf-Job (gemma, anderer Modell-Schlüssel, Kontext 8192): qwen wurde als untätig verdrängt, gemma geladen, Urteil `PASS`,
   535 Ausgabe-Tokens (511 Denken, bei Rolle `verifier` bewusst nicht abgeschaltet).
4. `accept_verification` → `READY_FOR_ACCEPTANCE`. Nachweiskette und Audit-Kette gültig, Hauptbuch leer, Modelle entladen.

## Grenzen und Offen (8c/8d)

- **Qualität ohne Denken ist nicht gemessen.** Die Rollenzuordnung (`none` für `reviewer`/`documentation` …) ist ein begründeter
  Vorschlag aus Kostenmessungen, kein Qualitätsnachweis. Ein Vergleich mit echten Aufgaben fehlt.
- **Nur ein Fall:** ein Text-Kandidat (Dokumentation, E1) mit einer deterministischen Prüfung. Code-Kandidaten brauchen echte Tests
  (Sandbox) als Nachweis; `record_check` ist die Schnittstelle, ein Test-Handler dafür ist nicht gebaut.
- **Das Prüfurteil ist eine Modell-Meinung.** Das Gate verlangt sie zusätzlich, ersetzt aber keinen Test. Wie gut gemma Fehler
  findet, wurde nicht gemessen (ein richtiges PASS ist kein Beleg für ein richtiges FAIL).
- **Der Prüfer sieht den Text, die Nachweise nicht.** Er bekommt den Kandidaten und die Frage, nicht die Prüfdetails.
- `READY_FOR_ACCEPTANCE` ist nicht „aktiviert“. Aktivierung, Vergleich mit der Basisversion, Rollback und Captain-Gate
  (`activation_decision`) laufen weiter nur über den alten Entwicklungspfad.
- Die Stufen-Rezepte gelten nur für diese beiden Modelle in dieser Installation (KV-Typen aus LM Studios Vorgaben).
- Die Schätzung der Eingabe-Tokens ist bei wiederholtem Text 1,8-fach zu hoch.
