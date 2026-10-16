# GUPPIs eigene VM (microsandbox) – Stand der Grenzprüfung (2026-10-02)

Zweck: Belege für die Abnahme PC-03 (Isolation) und PC-07 (Aufräumen) aus `PC_DIAGNOSE_PLAN_v1.16.yaml`.
**`target_qualified` ist weiterhin `false`.** Die Entscheidung trifft der Captain nach diesem Bericht.

## Was eingerichtet ist

| Teil | Stand |
|---|---|
| SDK | microsandbox 0.7.4 (gepinntes Windows-Wheel aus `portable/sandbox/wheels`, Prüfsumme gegen `RELEASE_LOCK.json`), offline in `runtime/.venv` installiert |
| PyYAML | 6.0.3 in `runtime/.venv` (PyPI) |
| Gastimage | `python:3.12-slim`, von GUPPIs eigener Laufzeit `msb` geladen (ohne Docker), Archiv `runtime_data/tool_workspace/offline-assets/python-3.12-slim.tar`, SHA256 `b5f4a99f…41b4a6` |
| Import | über GUPPIs Importpfad, Mission `M-3E8064C0`, Gate `HG-94AD5BF2`: `IMPORTED_NOT_QUALIFIED` |
| Pin | `config/sandbox.yaml`: `image: python:3.12-slim@sha256:b0f67293…736721844` (lokaler Digest; der Registry-Digest `6b1f85a0…` überlebt `msb save/load` nicht). Sicherung `sandbox.yaml.bak-2026-10-02-before-image` |
| `sandbox-doctor` | einziger offener Blocker: `target_boundary_acceptance_pending` |

## Fehler, die erst der echte Lauf gezeigt hat (alle behoben, mit Tests)

| Ort | Fehler | Behebung |
|---|---|---|
| `sandbox/provider.py` | SDK startet nicht ohne `ProgramData`, `ALLUSERSPROFILE`, `SystemDrive`, `PUBLIC` | diese vier systemweiten Pfade werden durchgereicht; Nutzerordner, Schlüssel, Proxys bleiben draußen |
| `sandbox/worker.py` | Fehler vor dem ersten SDK-Aufruf wurde als „unbestätigt“ gemeldet (Sperre blieb stehen) | bekannter Ausgang `operation_confirmed=true` |
| `sandbox/worker.py` | SDK findet `name@sha256:…` nicht, nur `name` | Nachschlagen per Name, danach Digest-Vergleich (Abweichung → Ablehnung) |
| `sandbox/worker.py` | `copy_from_host` kopiert nur Einzeldateien („Zugriff verweigert“ bei Ordnern) | Verzeichnisse anlegen, Dateien einzeln schreiben |
| `sandbox/worker.py` | Exit-Code kommt im `exited`-Ereignis; `wait()` danach scheitert | Code aus dem Ereignis übernehmen |
| `sandbox/worker.py` | `exec_stream` setzt seinen Timeout **nicht** durch (`sleep 20` mit Limit 3 lief weiter) | Worker erzwingt das Limit selbst und beendet den Prozess (`guest_command_timeout`) |
| `sandbox/worker.py` | ephemere Sandbox ist nach `stop` schon weg; `remove` → „not found“ wurde als Aufräumfehler gewertet | „not found“ nach bestätigtem Stopp = entfernt; ursprünglicher Jobfehler bleibt in der Meldung erhalten |
| `sandbox/worker.py` | gescheiterter VM-Start ließ Aufräumen immer unbestätigt | nur wenn das SDK „not found“ meldet, gilt es als bestätigt; sonst bleibt die Sperre |

## Grenzprüfung (Werkzeug `benchmarks/sandbox_boundary_check.py`, Bericht `runtime_data/acceptance/sandbox_boundary_20261002T152413Z.json`)

Gestartet über denselben Code wie der Worker (`run_job`, Politik aus `config/sandbox.yaml`): kein Netz, RESTRICTED, tmpfs, Pull NEVER, Gastnutzer 65534.

| Prüfung | Ergebnis |
|---|---|
| Gast läuft als unprivilegierter Nutzer (uid 65534) | PASS |
| Host-Sentinel (neben der Quelle und im Projekt) nicht sichtbar, 4353 Dateien durchsucht | PASS |
| keine Host-Freigabe außer dem eigenen Laufzeitordner `/.msb` | PASS |
| keine TCP-Verbindung zu Internet oder Host-Diensten (8.8.8.8:443, 10.0.2.2, 172.17.0.1, 127.0.0.1:8089/1234 …) | PASS |
| keine Namensauflösung (`example.com`) | PASS |
| keine Host-Geheimnisse in der Umgebung | PASS |
| `/etc`, `/usr` nicht beschreibbar; `/workspace` beschreibbar | PASS |
| Speicher ≤ 1024 MiB, 2 CPUs, Prozesslimit 64 greift | PASS |
| läuft in einer VM (eigener Kernel 6.12, Hypervisor-Flag) | PASS |
| Befehls-Timeout wird durchgesetzt | PASS |
| Aufräumen vom Worker bestätigt, keine Sandbox übrig | PASS |
| **Befund: Port 53 erreichbar** | FINDING |
| `/.msb` vom Gast nicht beschreibbar (nach Gegenmaßnahme, Lauf `sandbox_boundary_20261002T184247Z`) | PASS |

### Befund 1: Port 53 trotz `Network.none()`

Der Gast hat `eth0` mit Route über `172.16.0.5`. Jede Anfrage an Port 53 (TCP und UDP, an 1.1.1.1, 8.8.8.8, 9.9.9.9, 172.16.0.5) wird beantwortet, immer mit 29/31 Bytes, also ohne Antwortdatensätze. Alles andere wird abgewiesen, `example.com` lässt sich nicht auflösen.
Das spricht für einen Resolver im Netzwerkstapel von microsandbox, der leer antwortet. Host-seitige Teilprüfung (ohne Adminrechte): Während der Gast 16 DNS-Anfragen stellte, wurde alle 0,2 s die Verbindungstabelle der `msb`-Prozesse gelesen. Ergebnis: **keine** TCP-Verbindung nach außen, **kein** UDP-Socket. Das spricht stark dafür, dass die Antworten lokal entstehen.
**Nicht belegt** ist es trotzdem: Die Verbindungstabelle ist kein Paketmitschnitt, und sehr kurze Sockets können zwischen zwei Abfragen liegen. DNS-Namen wären ein Kanal, um Daten hinauszuschmuggeln. Für die Abnahme nötig: ein Paketmitschnitt mit Adminrechten (`pktmon` oder Wireshark) während eines Laufs (PC-03 „network capture“).

**Paketmitschnitt (vorbereitet, braucht Adminrechte):** `runtime/benchmarks/sandbox_dns_capture.ps1`. Es zeichnet mit dem Windows-eigenen `pktmon` nur Port-53-Verkehr auf allen Adaptern auf. Dann startet es den Grenztest: Der Gast fragt einen einmaligen Zufallsnamen (`gp<zufall>.guppi-boundary.example.com`) per UDP und TCP bei 1.1.1.1, 8.8.8.8 und 9.9.9.9 ab. Anschließend sucht es diesen Namen im Mitschnitt. `NO_QUERY_LEFT_THE_HOST` heißt: Keine Anfrage hat den Rechner verlassen. Der pktmon-Filter wird am Ende wieder entfernt. Die Antworten im Gast sind auch hier leer (63/65 Bytes = nur Kopf und Frage).

### Befund 2: Laufzeitordner `/.msb` beschreibbar (BEHOBEN)

**Gegenmaßnahme seit 2026-10-02:** `sandbox/worker.py` (`protect_runtime_share`) setzt vor jedem Gast-Befehl `chmod 0700 /.msb` als root. Danach prüft es mit dem Gast-Nutzer 65534, dass Schreiben scheitert; gelingt es doch, läuft kein Gast-Befehl (`runtime_share_writable_by_guest`). Im echten Lauf geprüft: `/.msb`, `/.msb/rootfs/upperfs` und `/.msb/scripts` sind für den Gast nicht beschreibbar und nicht lesbar, die VM arbeitet normal. Grenzprüfung `runtime_share_not_writable_by_guest`: PASS. Root im Gast könnte weiterhin schreiben, aber Gast-Code läuft nie als root.

Ursprünglicher Befund:

microsandbox bindet den Ordner der Sandbox auf dem Host per virtiofs ein (`rootfs`, `scripts`, `sdk-process.json`, `tls`, …), lesend und schreibend, auch für uid 65534. Der Gast kann dort Dateien auf der Host-Platte anlegen oder ändern, die der Host-Prozess `msb` liest. Begrenzend: Der Ordner liegt unter `runtime_data/sandboxes/backend_home`, Sandboxen sind ephemer, der Sentinel war nicht erreichbar.
Offen: ob ein Gast darüber den Host-Prozess beeinflussen kann. Mögliche Gegenmaßnahmen: Größenlimit für den Ordner, eigener Windows-Nutzer mit Minimalrechten für `msb`, Rückfrage beim microsandbox-Projekt.

### Beobachtung: VM-Start nicht immer zuverlässig

In etwa 2 von 8 Starts endete die VM sofort („sandbox process exited … before agent relay became available“). Ein zweiter Versuch ging durch. Der Worker meldet das jetzt sauber. Eine automatische Wiederholung gibt es bewusst nicht.

## Paketmitschnitt (Captain, Adminrechte, 2026-10-02)

`dns_capture_20261002T185451Z`: Gastname `gpd6caba5d9f73217c.guppi-boundary.example.com`, **0 Treffer** in 38 844 Bytes Port-53-Mitschnitt.
Als Kontrolle enthält der Mitschnitt 132 DNS-Namen aus dem normalen Verkehr des Rechners, die Aufzeichnung hat also funktioniert.
Ergebnis: `NO_QUERY_LEFT_THE_HOST`. Befund 1 ist damit entkräftet: Port 53 wird nur lokal und leer beantwortet.

## Entscheidung des Captains

**Freigegeben am 2026-10-02:** `target_qualified: true` in `config/sandbox.yaml`, Sicherung `sandbox.yaml.bak-2026-10-02-before-qualification`.
`sandbox-doctor`: keine Blocker, `execution_ready: true`. (`vm_boundary_tested: false` ist ein fester Wert der Provider-Sonde. Die Abnahme steht in `target_qualified` und diesem Bericht.)
Zurücknehmen: `target_qualified` wieder auf `false` setzen.

## Wichtig beim Verschieben oder Umbenennen des Projektordners

Gelernt am 2026-10-02, als `GUPPI_Developer_Archive_v1.20_SELF_DEVELOPMENT_FOUNDATION` zu `GUPPI v1.20_S D A` wurde:
- **Image-Cache:** microsandbox speichert absolute Pfade (`backend_home\cache\fsmeta\…erofs`). Nach einem Umzug startet die VM nicht mehr („Data storage file … not found“). Abhilfe: `msb image rm python:3.12-slim` mit `MSB_HOME` auf `backend_home`, dann Neuimport über `dev-image-preview` und `dev-image-import` (ein Gate). Das Archiv in `offline-assets` bleibt gültig, gleicher Hash und gleicher Digest.
- **Vorbereitete Kandidaten:** Sie sind an absolute Pfade gebunden. Nach einem Umzug gilt `candidate_binding_changed_replan_required`, also neu generieren. Freigaben für den alten Plan gelten nicht mehr.
- **Pfadlänge:** msb ist nicht für lange Pfade ausgelegt. Projektpfad plus `backend_home\sandboxes\<name>\runtime\…tmp` muss unter 260 Zeichen bleiben. Der Worker nutzt deshalb kurze VM-Namen (`guppi-` plus 12 Hex-Zeichen).
