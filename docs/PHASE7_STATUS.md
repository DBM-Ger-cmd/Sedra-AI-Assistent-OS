# PHASE7_STATUS – Hardware-Bewusstsein: Reservierungen für RAM, VRAM und KV-Cache

Stand: 2026-10-01 · Testumgebung: Windows 11, Python 3.14.7. **Alle Hardwarewerte in den Tests sind nachgebaut. Es lief kein Modell, kein echtes Telemetriesignal einer GPU wurde ausgewertet.**

**Ergebnis:** `python -m unittest discover -s tests` → **782 Tests, 0 Fehler, 6 übersprungen** (alle 6 sind Symlink-Tests, siehe PHASE0_STATUS). `validate_package.py` und `compileall` OK.
Alles bleibt hinter dem Flag `resource_scheduler.enabled` (AUS). Ausgeschaltet wird nichts reserviert, keine Reservierungsdatei angelegt, und der Router bekommt keinen Lastprüfer (Test).

## Vorab gelesen: was der Bestand wirklich liefert
`hardware_manager/collector.py` und `manager.py` (nicht nur Namen):
- **VRAM:** gesamt/belegt/frei **je GPU, nur für NVIDIA** (über `nvidia-smi`). AMD, Intel und Apple liefern **keine** GPU-Werte. Ohne `nvidia-smi` ist die GPU-Liste leer.
- **RAM:** gesamt/verfügbar über die Windows- bzw. Linux-Systemaufrufe (verlässlich).
- **Thermik:** `thermal_state` (NORMAL, WARM, HOT, CRITICAL, SENSOR_FAULT, RECOVERY) nur als **Zulassungssignal**. Auf Windows kommen Sensoren nur, wenn LibreHardwareMonitor läuft, sonst ist der Zustand `SENSOR_FAULT`.
- **Grenzen im Bestand:** `HardwareManager.job()` zählt nur **laufende Modellaufrufe im eigenen Prozess** gegen `max_jobs` und prüft Thermik plus RAM-Reserve. Es kennt **weder VRAM, noch KV-Cache, noch was andere Jobs versprochen haben**. Zusätzlich hält es seine Sperre, während es die GPU- und Sensorabfrage (bis zu rund 9 s) ausführt.
- Der Hardware-Model-Pass modelliert KV-Cache ausdrücklich nicht.

## Umgesetzt

| Baustein | Datei |
|---|---|
| Konfiguration (Reserve, Verhalten ohne GPU-Telemetrie, WARM-Grenze) | `config/resource_scheduler.yaml` |
| `ResourceScheduler`: `reserve`, `release_job`, `reconcile`, `explain`, `view`, persistentes Hauptbuch | `resource_scheduler.py` |
| KV-Cache-Schätzung aus **deklarierter** Rate je Modell | `role_routing.py` (`kv_cache_gb_per_1k_tokens`) |
| Reservieren beim Start, Freigeben bei jedem Ende, Abgleich im Reaper und nach Neustart | `job_supervisor.py` |
| Lastprüfung bei der Rollenauflösung (`load_check`), Verdrahtung, `/api/resources` (nur lesend), `boot()`-Status | `runtime.py`, `uix_server.py` |

## So funktioniert die Entscheidung
Eine Reservierung wird nur erteilt, wenn **beides** Platz lässt, jeweils nach einer Sicherheitsreserve:
- **(a) das Hauptbuch** (Kapazität − Reserve − bereits Versprochenes ≥ Anforderung) und
- **(b) die Messung** (gemessen frei − Reserve ≥ Anforderung).

Dazu: Thermik muss Arbeit zulassen (WARM: höchstens eine Reservierung), das Jobslimit des Hardwareprofils, exklusive Jobs laufen allein. Bei mehreren GPUs gewinnt die mit dem meisten Platz, sie wird festgehalten. Jede Ablehnung nennt Grund, Fehlmenge und Alternativen (`queue`, kleineres Modell oder CPU-Offload).

**Reservierungen enden durch Zustand, nicht durch die Uhr.** Der Supervisor gibt sie frei, wenn ein Versuch endet (Fehler, bestanden, abgebrochen, Worker verloren, geparkt für eine Freigabe, Start gescheitert). `reconcile` entfernt die von Jobs, die nicht mehr laufen. Ein Sprung der Wanduhr kann den Platz eines lebenden Jobs deshalb nicht freigeben (Test).

## Was belegt ist (44 neue Tests)
- **Das Beispiel aus dem Handoff** (16-GB-Karte, 2 GB Reserve, ein Job mit 8,5 GB Gewichten + 3,5 GB KV-Cache, ein zweiter will 6 GB mehr): wird **nicht parallel gestartet** (`vram_insufficient`, frei 2 GB), nach Freigabe gelingt er.
- **Beide Prüfungen einzeln wirksam:** Das Hauptbuch allein lehnt ab, obwohl die Karte noch frei aussieht (versprochen, aber noch nicht geladen). Die Messung allein lehnt ab, obwohl nichts versprochen war (fremder Prozess belegt die Karte). Gleiches für RAM, mit Reserve aus dem Profil oder der Konfiguration.
- **Fehlende Telemetrie wird nie als „reichlich" gelesen:** RAM-Messung ungültig → abgelehnt. VRAM angefordert, aber keine GPU-Werte → abgelehnt (`no_gpu_telemetry_for_vram_request`), außer `declared_only` ist ausdrücklich gewählt. Eine reine CPU-Anfrage braucht keine GPU-Werte. Eine GPU mit unbrauchbarer Anzeige wird ignoriert.
- Thermik (HOT, CRITICAL, SENSOR_FAULT, RECOVERY sperren, WARM begrenzt auf einen), Jobslimit folgt dem Profil, exklusive Jobs, Auswahl der GPU mit dem meisten Platz, ein Job zählt nie doppelt, Hauptbuch überlebt einen Neustart.
- **Unlesbares Hauptbuch** verspricht nichts und wird **nicht überschrieben**. **Kein Bild vom Host** → keine Zusage. Eine Statusansicht wirft nie.
- **Nebenläufigkeit:** 8 Threads und 5 Prozesse bei Platz für zwei Jobs → genau zwei erhalten die Reservierung, nie drei.
- **KV-Cache:** nur aus einer deklarierten Rate je Modell (0,5 GB je 1k Token bei Arbeitskontext 8192 ergibt 4,096 GB), wird dort gezählt, wo das Profil es hinlegt (GPU oder RAM). **Ohne Rate steht `null` und `complete: false`**, die Zahl gilt dann als Mindestwert und das Hauptbuch vermerkt es. Unbekannt ist nie 0.
- **Kleineres Modell statt Absage:** Passt das große Modell wegen Last nicht, wählt der Router über `load_check` das kleinere (Rezept erscheint mit Kategorie `pressure` in der Begründung). Passt keines, kommt `hardware_pressure`.
- **Supervisor:** Start reserviert, der Versuch merkt sich die Reservierung. Jedes Ende gibt den Platz frei (vier Wege einzeln getestet, dazu geparkte Jobs, Neustart, gescheiterter Start). Ein Heartbeat berührt das Hauptbuch nicht. Der Reaper entfernt verwaiste Reservierungen, **nie** die eines lebenden Jobs. Ein kaputtes Hauptbuch hält einen endenden Job nicht auf (Audit `JOB_RESOURCE_RELEASE_FAILED`).
- **Ablehnung heißt „jetzt nicht":** Der Job wird mit Wartezeit neu eingereiht, nicht eskaliert. Mit Platz startet er. Wiederholte Ablehnungen enden nach dem Retry-Limit in der Eskalation an GUPPI statt in einer Schleife.
- Exklusive Jobs warten auf eine freie Maschine.
- Der Scheduler **schreibt nichts an der Maschine** (statisch geprüft: kein `subprocess`, keine Profil-Schreibzugriffe, kein Beenden von Prozessen) und nennt keinen Provider.

## Fehler, die erst die Tests sichtbar machten (alle behoben)
| Befund | Folge | Behebung |
|---|---|---|
| **Eine Ressourcen-Ablehnung schloss den Provider aus** (`retry.exclude`): Der abgelehnte Versuch trug schon den `provider_ref`, die FALLBACK-Regel schloss ihn aus. Beim nächsten Start hätte der Router dann `provider_unavailable` gemeldet, obwohl der Provider gesund war. Der Job wäre nie wieder gelaufen | schwerwiegend (Dauerschleife bis zur Eskalation) | Ein abgelehnter Start trägt keinen `provider_ref` (nur `refused_provider_ref` zur Nachvollziehbarkeit). Der Provider wird weder ausgeschlossen noch gemeldet |
| `explain` hielt einen Hardwarefehler für ein unlesbares Hauptbuch (beide waren `RuntimeError`) | falscher Grund in der Auflösung | eigene Ausnahme `LedgerUnreadable` |

## Nicht umgesetzt / offene Grenzen (ehrlich)
1. **Nur NVIDIA hat Live-Werte.** Auf AMD, Intel oder Apple bleibt VRAM entweder abgelehnt (Standard) oder rein deklariert (`declared_only`). Die Live-Prüfung fehlt dort. Windows-Sensoren brauchen LibreHardwareMonitor.
2. **Alles ist nur gegen nachgebaute Hardware getestet.** Das reale Verhalten von `nvidia-smi`-Abfrage, Dauer, Zeitüberschreitung und Windows-Zählern ist hier nicht gemessen.
3. **Die Schätzung ist so gut wie die deklarierten Werte** (`model_size_gb`, `min_vram_gb`, KV-Rate). Die ausgelieferten Rezepte haben **keine** `model_size_gb` und keine KV-Rate: Sie sind `complete: false`, die Zahlen sind Mindestwerte. **Mit der ausgelieferten Konfiguration schützt der Scheduler also nur gegen das, was dort deklariert ist.** Die Werte müssen für das echte Modell eingetragen werden (Entscheidung unten).
4. **Doppelzählung bei geteiltem Modell:** Hält eine Laufzeit ein Modell geladen und mehrere Jobs nutzen es nacheinander, zählt jeder Job die Gewichte erneut. Das ist **konservativ** (zu vorsichtig), nicht zu großzügig. Eine „resident model"-Erkennung gibt es nicht.
5. **Die Zusage gilt nur für Jobs, die über den Supervisor laufen.** Der bestehende Pfad Mission → `ModelRouter.chat` (über `HardwareManager.job()`) kennt das Hauptbuch nicht. Zwei Wege können sich also gegenseitig überraschen. Die Messung (b) fängt das nur teilweise ab.
6. **Prüfung bei der Auflösung ist beratend** (`explain`, kein Hold): Zwischen Auflösung und Start kann sich die Lage ändern. Bindend ist die Reservierung beim Start. Eine Ablehnung dort führt zu einer erneuten Einreihung.
7. **Die Last der CPU und der Festplatte** wird nicht berücksichtigt (nur RAM, VRAM, Thermik, Jobanzahl). Ebenso keine Temperaturtrends.
8. **Keine Zeitbegrenzung der Reservierung.** Ohne Reaper-Lauf oder Neustart-Abgleich bleibt eine verwaiste Reservierung bestehen. Das ist bewusst (Uhr-Sprünge), aber heißt: **Der Reaper muss laufen**, und bisher ruft ihn niemand automatisch auf.
9. **`HardwareManager.job()` hält seine Sperre während der Sensorabfrage** (bis zu rund 9 s). Das ist ein bestehendes Verhalten und wird durch den Scheduler nicht schlimmer, aber auch nicht behoben.
10. **Windows-Antivirus und Dateisystemlast** für das Hauptbuch (Schreiben bei jedem Reservieren) sind nicht gemessen.

## Abweichungen vom Handoff
| Handoff §8 | Umsetzung |
|---|---|
| „Ressourcenanforderungen: RAM, VRAM, CPU-Threads, GPU, Kontext, KV-Cache, temporärer Speicher, Netzwerk, Laufzeitklasse, Exklusivität" | RAM, VRAM (je GPU), KV-Cache, Exklusivität, Thermik, Jobanzahl. **Nicht** umgesetzt: CPU-Threads, temporärer Speicher, Laufzeitklasse |
| „Alternativen: Queue, kleineres Modell, CPU-Offload, Cloud, anderer Worker" | `queue` (automatisch), kleineres Modell (über die Rollenauflösung), Hinweis auf CPU-Offload. Cloud und anderer Worker nicht (Cloud existiert nicht, es gibt nur einen Worker) |
| Beispiel mit „Sicherheitsreserve 2 GB" | konfigurierbar (`vram_reserve_gb`, Standard 1,0) |

## Entscheidungen für den Captain
1. **Modellgrößen und KV-Raten eintragen:** `model_size_gb`, `min_vram_gb` und `kv_cache_gb_per_1k_tokens` für das tatsächliche Coder-Modell (und Kev). Ohne sie ist die Zusage ungenau (siehe 3).
2. **Anderer Hersteller als NVIDIA?** Welche Grafikkarte hat der Ziel-PC? Bei AMD/Intel/Apple müsste ein eigener Messweg gebaut werden, oder `declared_only` gilt.
3. **Der alte Pfad (Mission → `ModelRouter.chat`):** Soll er ebenfalls über das Hauptbuch laufen, oder bleibt er bis Phase 8 getrennt?
4. **Reaper:** Soll er als Hintergrundaufgabe laufen (Phase 8, zusammen mit dem Worker-Loop)? Ohne ihn werden verwaiste Reservierungen erst beim nächsten Neustart abgeräumt.

## Nächster Schritt: Phase 8 (Selbstentwicklung auf dem Supervisor)
Laut Plan erst, wenn 1–7 stabil sind. Vor Beginn sollten zwei Dinge geklärt sein: die offenen Entscheidungen oben und ein **echter Lauf auf dem Ziel-PC**, denn alle Phasen sind bisher nur gegen nachgebaute Provider, Hardware und Kev getestet. Phase 8 würde den Worker-Loop (mit Reaper, Health-Probes und Werkzeug-Kette über das Gate) bauen und den ersten kontrollierten E1-Entwicklungsfall abbilden, aber **ohne** reale Modelle bleibt er ein Test der Mechanik.
