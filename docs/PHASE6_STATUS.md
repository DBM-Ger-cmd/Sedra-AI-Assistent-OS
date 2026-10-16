# PHASE6_STATUS – Berechtigungsstufen, Freigaben, Kev-Anbindung

Stand: 2026-10-01 · Testumgebung: Windows 11, Python 3.14.7. **Keine Modelle, kein Kev-Server, kein Zielgerät.**

**Ergebnis:** `python -m unittest discover -s tests` → **738 Tests, 0 Fehler, 6 übersprungen** (alle 6 sind Symlink-Tests, siehe PHASE0_STATUS). `validate_package.py` und `compileall` OK. Beim Beenden der kleinen Test-Webserver kann eine Meldung `OSError WinError 10038` erscheinen. Sie stammt vom Abbau des Test-Sockets, die Tests selbst sind grün.

## Teil A – Berechtigungsstufen 0–6

**Grundsatz:** Eine Stufe ist eine **Obergrenze**, kein Recht. Der Guard entscheidet jede Aktion weiter selbst. Das Gate lehnt zuerst ab und fragt den Guard danach. Es kann dadurch nur öfter „nein" sagen als der Guard, nie „ja", wo der Guard „nein" sagt oder den Captain verlangt.

### Vorab erledigt: `guard_rules.yaml` wirklich gelesen
Alle 24 Regeln. Die Einordnung aus dem Vertrag war nach Namen geraten und stimmte in einem Punkt nicht:

| Vertrag (geraten) | Wirklichkeit (Regeln) | Folge |
|---|---|---|
| Stufe 3 „policy-abhängig, isoliert", Stufe 0–2 automatisch | `sandbox_execute` und `shell_execute` (Stufe 3) sind im Guard **immer `CAPTAIN_REQUIRED`**. Nur `read_project_file`, `git_read`, `create_new_artifact` sind `ALLOW` | Stufe 3 braucht immer eine Freigabe. Umgesetzt wie der Guard, strenger als der Vertrag |
| `file_delete` auf Stufe 5 | Zerstörender Schreibzugriff auf das Projekt | jetzt Stufe 4 |
| – | 3 Aktionen sind im Guard `BLOCK` (`modify_core_invariants`, `bypass_guard`, `silent_stable_replacement`) | als „nie automatisch" geführt, **auf keiner Stufe und mit keinem Token** |

### Umgesetzt
| Baustein | Datei |
|---|---|
| Zuordnung Aktion → Stufe, Pfadbindung | `config/permission_levels.yaml` |
| `PermissionGate` (`check`, `level_of`, `policy_hash`, `binding`) | `permission_levels.py` |
| `Guard.check_token` (prüft ein Token, **ohne es zu verbrauchen**) | `guard.py` (additiv; `authorize` nutzt dieselbe Prüfung und verbraucht danach) |
| `check_action`, `request_approval`, `resolve_approval`, `deny_approval`, `consume_approval`, `lower_permission_level` | `job_supervisor.py` |
| Verdrahtung, `/api/permissions` (nur lesend), `boot()`-Status | `runtime.py`, `uix_server.py` |

### Was belegt ist (71 neue Tests)
**Abgleich mit dem Guard (verhindert Auseinanderlaufen):** Jede der 24 Guard-Aktionen ist genau einmal eingeordnet, nichts Veraltetes steht in der Zuordnung. Keine Aktion ab Stufe 3 ist im Guard `ALLOW`, jede `ALLOW`-Aktion liegt ≤ Stufe 2, die `BLOCK`-Aktionen sind genau die „nie automatisch"-Liste, Stufe 5 und 6 verlangen immer den Captain. Fügt jemand eine Guard-Regel ohne Einordnung hinzu, schlägt der Test fehl.

**Gate**
- Die Stufe begrenzt, was ein Job anfordern darf (Stufe 2 darf lesen und neu anlegen, sonst nichts; Stufe 0 gar nichts). Eine nicht eingeordnete Aktion zählt als Stufe 6.
- Ausreichende Stufe heißt **nicht** erlaubt: der Guard entscheidet weiter (`sandbox_execute` → Freigabe nötig, selbst auf Stufe 6 bei `deployment`).
- „Nie automatisch": auf jeder Stufe und mit jedem Token abgelehnt.
- Der Guard kann das Ergebnis nur verschärfen (Stub-Guard mit `BLOCK`/`CAPTAIN_REQUIRED`/`ALLOW`; bei zu niedriger Stufe wird der Guard gar nicht erst gefragt).
- **Pfadbindung (Entwicklungsumgebung):** Pfad-Aktionen sind nur innerhalb der Scope-Wurzeln des Jobs erlaubt. Ohne Scope **kein** Pfadzugriff (fail closed). Geprüft: `..`-Ausbruch, Geschwisterordner mit gleichem Präfix (`dev2`), leerer und relativer Pfad, Windows-Groß/Kleinschreibung. Logische Ziele (`sandbox:…`) werden nicht als Pfad geprüft.
- **Policy darf sich unter einem laufenden Job nicht ändern:** Der Job speichert einen Fingerabdruck von Zuordnung und Guard-Regeln. Weicht er später ab, wird abgelehnt (`policy_changed_since_job_start`).
- Ein Captain-Token macht die Aktion „erlaubt", wird aber **nicht verbraucht** (das macht der Ausführer). Ein Token für ein anderes Ziel, einen anderen Job oder einen geänderten Vertrag hilft nicht. Ein verbrauchtes Token ist weg.
- Verweigerungen werden auditiert (`PERMISSION_DENIED` mit Grund und beiden Stufen), Erlaubnisse überlässt das Gate dem Audit des Guards.

**Supervisor**
- Ein verweigerter Antrag lässt den Job als `policy_denied` scheitern: Eskalation an den **Captain**, **kein** Fallback, `enqueue` und `resume` werden abgelehnt.
- **Freigabe als geparkter Zustand:** `request_approval` ist **kein Fehler**. Der Retry-Zähler bewegt sich nicht, kein Provider wird beschuldigt, der Versuch endet als `SUSPENDED`, der Worker-Platz wird frei. Der Job ist `WAITING_APPROVAL`, nicht einreihbar, nicht wiederaufnehmbar, vom Reaper unberührt, und überlebt einen Neustart.
- **Das Token wird beim Auflösen geprüft** (echt, passend zu Job, Aktion, Ziel, Vertrag, Policy), aber nicht verbraucht. Falsche, fremde und für etwas anderes ausgestellte Token werden abgelehnt, ohne den Zustand zu ändern. Wurden Vertrag oder Policy nach der Anfrage geändert, ist die Freigabe `approval_stale`.
- Das Token gibt es **genau einmal** an den Worker des neuen Versuchs (`consume_approval`) und liegt danach nicht mehr in der Job-Datei. Der Ausführer verbraucht es einmal beim Guard.
- Ablehnung durch den Captain beendet den Job (`CANCELLED`), nichts wird darum herum wiederholt. Auch ein Abbruch schließt eine offene Freigabe.
- Die Stufe eines Jobs kann **sinken, nie steigen** (die niedrigere Stufe gilt sofort). Mehr Rechte bedeuten einen neuen Job mit neuem Vertrag.
- Ohne Gate (Konfiguration fehlt/ungültig) kann **keine** Aktion geprüft werden, also ist keine erlaubt (`permission_gate_unavailable`).

## Teil B – Kev (Sie haben den Projektordner bereitgestellt)

Gelesen: `README.md`, `pyproject.toml`, `LICENSE`, `kev/api.py`, `kev/device.py`, Auszüge von `kev/serve.py` und der Modellkarte `kev-4b.md`. Nicht gelesen: Training, Evaluierung, die restlichen Module, Playground.

### Befund F-10 (hoch, behoben): Der v1.20-Adapter passte nicht zum echten Kev
Die ausgelieferte `kev.py` sendete `questions` als **Liste** und erwartete `answers` als **Liste** gleicher Länge. Der echte Server nutzt ein **Dictionary** (`questions: {id: {type, instructions, criteria}}`, `answers: {id: {...}}`), validiert mit pydantic (`SystemOneRequest`) und hätte die Anfrage mit einem Validierungsfehler abgelehnt. Außerdem: Standardport 8008 (Konfiguration sagte 8765), Bearer-Authentifizierung über `KEV_API_KEY` wurde nicht unterstützt, und die alte Antwortprüfung hätte jede echte Antwort verworfen. Kev wäre also **nie** ansprechbar gewesen, obwohl alle v1.20-Tests grün waren (sie prüften eine erfundene Form).

**Behoben** in `kev.py`: echtes Format, Bearer-Schlüssel aus der Umgebungsvariable (nie in einer Datei oder einem Bericht), Antwortprüfung nach der echten Logik (Antworten genau passend zu den Fragen, Typen stimmen, Wahrscheinlichkeiten in [0,1] mit Summe 1 ± 0,02 wie bei Kevs eigenen Clients, Wahl und Score im gültigen Bereich). `status` heißt jetzt `ANSWERED` statt `PASS`, damit niemand eine erfolgreiche Anfrage mit einer bestandenen Verifikation verwechselt. Das Ergebnis trägt `trust_level: model_assessment`.
Bewiesen mit: 47 Tests, einem **echten HTTP-Rundlauf** (Bearer, 401, nichts lauscht), und einem Test, der die **Originaldatei `kev/api.py`** lädt: Unsere Anfragen bestehen die pydantic-Validierung des echten Servers, und die vom echten Code (`to_answers`) gebauten Antworten bestehen unsere Prüfung. Die alte Listenform wird vom echten Modell abgelehnt (ebenfalls getestet).

### Was Kev tatsächlich ist (aus dem Projekt, nicht aus dem Handoff)
- Kleine **Entscheidungsmodelle** auf Qwen3.5/Qwen3.8-Basis: Ja/Nein, Auswahl, Bewertung, mit **kalibrierten Wahrscheinlichkeiten**. Es gibt **kein** PASS/FAIL, **keine** Codeprüfung, keine Begründung. Das passt zu unserer Regel „Kev ist eine Modell-Einschätzung, nie ein Testbeleg".
- Apache-2.0 (Projekt, Adapter und Basis). Die Datensätze haben eigene Lizenzen.
- Größen: 0,8B / 4B / 9B (Adapter auf eingefrorener Basis), 27B (51 GB volle Gewichte). Kev-4B braucht rund 9 GB GPU-Speicher für die Gewichte, ~14 GB mit Server-Puffern.
- **Eigene Genauigkeit (laut Projekt):** auf neuen Quellen 0,82 (4B/9B) bis 0,85 (27B). Kev-4B kann bei 5 % Fehlerbudget nur 0,52–0,69 der Entscheidungen automatisieren. Das Projekt sagt selbst: Schwellen auf eigenen Daten prüfen. Wissensfragen und Datumsrechnung sind schwach. Eine geänderte Antwortreihenfolge kann die Antwort ändern.

### Konsequenzen für GUPPI (offen, bitte entscheiden)
1. **Kev ist nicht portabel installierbar.** Es braucht Python 3.12/3.13 (hier läuft 3.14), `torch` 2.6–2.8, `transformers` ≥ 5.17, `uv` und eine **GPU oder Apple Silicon** (CPU-Pfad existiert, aber 0,8B/4B sind für L4/Mac gedacht). Das widerspricht dem Ziel „portabel ohne globale Installation". Nichts davon habe ich installiert oder gestartet. Möglich wäre ein **eigener portabler Ordner mit eigener Python-Umgebung**, gestartet von GUPPI nur nach Ihrer Freigabe (Guard-Aktion `model_runtime_control`, Stufe 5).
2. **Gemeinsame Abstammung:** Kev basiert auf **Qwen3.5**, unser Coder ebenfalls. Der `independence_key` (Familie + Gewichte) wäre `kev:…` gegen `qwen3.5:…`, also „unabhängig". Die gemeinsame Basis macht korrelierte Fehler wahrscheinlicher. Ob das als unabhängig genug gilt, ist eine **fachliche Entscheidung**, die das System nicht für Sie trifft. Möglicher Schritt: ein Feld `lineage` im Rezept, und Unabhängigkeit verlangt abweichende `lineage`, wenn beide bekannt sind.
3. **Wofür Kev taugt:** als **zusätzliche** Meinung (z. B. „erfüllt dieser Diff die Akzeptanzkriterien?") neben deterministischen Tests, nie als Ersatz. Die Regeln aus Phase 0.6 (PASS braucht deterministischen Beleg) bleiben bindend.
4. **Verifier-Rezept bleibt abgeschaltet** (`enabled: false`) und der Provider-Standard bleibt `enabled: false`, bis ein lokaler Server qualifiziert ist.

## Nicht umgesetzt / offene Grenzen (ehrlich)
1. **Die Werkzeuge laufen nicht über das Gate.** `check_action` ist die Prüfung, die ein Worker-Loop vor jedem Zugriff aufrufen muss. Filesystem-, Shell- und Sandbox-Werkzeuge rufen den Guard weiter **direkt** (mit `mission_id`) und kennen weder Job noch Stufe. Solange nichts Jobs automatisch ausführt, ist das ohne Folgen, aber **es gibt noch keine erzwungene Kette** Job → Gate → Werkzeug.
2. **Kein Zeitlimit** für wartende Freigaben. Ein Job bleibt unbegrenzt `WAITING_APPROVAL`.
3. **Der Token-Speicher (`approval_tokens.json`) wächst unbegrenzt**, der Guard räumt nichts auf (Bestand, nicht neu).
4. **Pfadprüfung** löst Symlinks auf und vergleicht Wurzeln, aber der **Symlink-Test lief hier nicht** (Windows-Recht, siehe Phase 0).
5. **Die Stufe 3-Aktionen sind nicht „isoliert"**: Sie sind nur freigabepflichtig. Die Isolation liefert die Sandbox, die hier nicht gelaufen ist.
6. **`GuppiRuntime.kev` ist weiter nirgends in einen Ablauf eingebunden.** Nichts ruft `verify` auf. Die Abbildung „Prüffrage aus Akzeptanzkriterium → Kev-Frage" gibt es nicht.
7. Die Aufteilung der Stufen ist **meine Einordnung** der Guard-Regeln. Der Captain sollte sie bestätigen, besonders `shell_execute` (3), `git_init` (4) und `execution_recovery` (4).

## Abweichungen vom Vertrag
| Vertrag | Umsetzung |
|---|---|
| Abschnitt 9: Stufe 3 „policy-abhängig, isoliert" | Stufe 3 braucht **immer** eine Captain-Freigabe (Guard-Regel) |
| Abschnitt 9: `file_delete` Stufe 5 | Stufe 4 |
| Abschnitt 5: Zustand `WAITING_APPROVAL` | als abgeleiteter Zustand (`approval.status == pending` auf einem `BLOCKED`-Job), nicht als gespeicherter |
| Abschnitt 5: Versuchsausgang | neuer Wert `SUSPENDED` für einen wegen Freigabe geparkten Versuch (zählt nicht als Fehler) |
| Abschnitt 5: `resolve_approval(job_id, token)` | prüft das Token über `Guard.check_token`, **verbraucht es nicht** |

## Entscheidungen für den Captain
1. **Stufen-Zuordnung bestätigen** (Tabelle in `config/permission_levels.yaml`).
2. **Kev:** Soll es als eigener portabler Ordner mit eigener Python-Umgebung vorbereitet werden (Download der Gewichte und der Abhängigkeiten, mehrere GB, braucht Ihre Freigabe), oder zunächst ohne Kev weiterarbeiten? Welche Größe und welche GPU hat der Ziel-PC?
3. **Abstammung:** Gilt „Kev auf Qwen3.5" als unabhängig vom Qwen3.5-Coder, oder soll ein `lineage`-Feld verlangen, dass sich auch die Basis unterscheidet?
4. **Werkzeug-Kette:** Soll Phase 7 oder 8 alle Werkzeugaufrufe eines Jobs durch `check_action` zwingen (eigener, schmaler Executor für Jobs)?

## Nächster Schritt: Phase 7 (Hardware-Bewusstsein)
Slots und Reservierungen (RAM/VRAM/KV-Cache) statt nur `max_jobs`, Anbindung des Hardware-Model-Passes an die Rollenauflösung (`load_check` ist vorbereitet), Temperatur- und Lastsignale. Vorab zu lesen: `hardware_manager/collector.py` (liefert er aktuelle VRAM-Belegung?) und `models/openai_local.py` in der Praxis.
