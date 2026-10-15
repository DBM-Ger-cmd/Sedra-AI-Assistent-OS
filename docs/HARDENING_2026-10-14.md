# Härtungsrunde 2026-10-14 (auf dem Build vom 14.10.)

Gezielt, nicht flächig: geprüft wurden die Stellen, an denen eine lokale App verwundbar oder stumm ausfallen kann – der HTTP-Vermittler `uix_server.py`, Dateizugriffe aus dem Chat, Subprozesse, unsichere Sprachmuster, Fehlerbehandlung der Oberfläche und die neuen Buildflow-Module der Nachtkette G.

## 1. Was geprüft wurde und in Ordnung ist

| Bereich | Befund |
|---|---|
| Unsichere Muster im Code (`shell=True`, `eval`, `pickle`, `yaml.load`, `os.system`) | keine; das einzige `exec` ist der Testläufer in `devvm_evidence.py`, der in der microVM läuft (so gewollt). |
| Undefinierte Namen (AST-Prüfung aller 140 Module und Benchmarks) | 0 Treffer; `compileall` ohne Fehler. |
| HTML-Einfügung in der Oberfläche (17 Stellen `innerHTML`/`insertAdjacentHTML`) | alle mit `escapeHtml()` oder konstantem Markup; Daten der Runtime gehen sonst über `textContent`/`el()`. |
| Herkunftsprüfung des Vermittlers | Host muss `127.0.0.1:<port>` sein (schützt vor DNS-Rebinding), Origin nur eigener; Token im URL-Fragment mit `Referrer-Policy: no-referrer`; CSP ohne externe Quellen; Statik aus Whitelist `[a-z_]+`. |
| Eingaben des Vermittlers | JSON-Body ≤ 1 MiB, kein `Transfer-Encoding`, nur Objekte; Pfade des Projektfensters ohne `..`, `:` oder führenden Schrägstrich und durch das Dateisystem-Tool auf den Projektordner begrenzt; `max_steps` 1–32; Gate-IDs müssen exakt stimmen; Prozess-Stopp nur für gelistete PIDs mit Startzeit-Vergleich. |
| Buildflow (`devenv/buildflow_*`, GUPPI gebaut) | Argumente als Liste (kein Shell), `task_id` per Regex, Sperrdatei mit `O_EXCL` und Stale-Erkennung, Schreiben über Temp-Datei + `os.replace`. |

## 2. Was geändert wurde

| Nr. | Härtung | Datei | Test |
|---|---|---|---|
| H1 | **Geheimnisse nie in einen Prompt.** `chat_attach` lehnt `.env*`, `tokens.json`, `*.token`, `id_rsa*`, `*.pem/.key/.pfx/.p12/.kdbx` und alles unter `.ssh/.gnupg/.aws/.azure/.kube/.docker` ab (`secret_file_refused`); Ordnerlisten blenden sie aus. Die Liste folgt `.gitignore`. Vorher las der Chat jede absolute Datei, die der Captain nannte, und schickte sie an das Modell. | `uix_server.py` | `test_chat_attach_refuses_secrets_and_is_audited` |
| H2 | **Jeder Anhang-Lesezugriff steht im Audit** (`UIX_CHAT_ATTACH` mit Pfad, Art, Größe), auch beim erneuten Lesen für jede Antwort. Vorher war das der einzige Dateizugriff der Oberfläche ohne Spur. | `uix_server.py` | dito |
| H3 | **Leerlauf-Timeout 30 s** für Verbindungen: ein Client, der nach dem Verbinden nichts mehr sendet, hält keinen Thread mehr fest. Gemessen: Verbindung wird nach 30 s geschlossen. | `uix_server.py` (`Handler.timeout`) | `test_shell_reports_errors_and_server_times_out_idle_clients` |
| H4 | **Keine stummen Fehler in der Oberfläche.** Globale Handler für `error` und `unhandledrejection` schreiben den Fehler als GUPPI-Nachricht mit Details in den Chat (`uiError`). Vorher verschwanden z. B. ein Fehler beim Öffnen der Brücke oder beim Anlegen eines Projekts in der Konsole. | `main.js`, `chat.js` | dito + Browser-Probe |
| H5 | **Netzfehler auf Deutsch.** `api()` übersetzt „Failed to fetch“ in „Keine Verbindung zur Runtime …“ und 403 in „Zugriff verweigert (Token oder Herkunft …)“. | `core.js` | dito |
| H6 | Einstiege `openBridge`, `createProject`, `openProjectRegistry` fangen Fehler selbst ab. | `missions.js`, `projects.js` | Browser-Probe |

Dynamisch geprüft (Headless-Chromium gegen laufenden Server): Leerlauf-Client nach 30 s getrennt, 2-MiB-Body → 400, erzwungene Promise-Ablehnung und synchroner Fehler erscheinen im Chat; `uix_check.py` 13/13; UIX-Tests grün.

## 3. Bewusst nicht geändert, aber notiert

- `/api/diagnose/command` mit `/rebind ja` ändert die Hardware-Bindung ohne Mission-Gate. Begründung im Code: der Captain tippt es selbst. Wer es strenger will: Gate `change_hardware_binding` wie bei Schaltern.
- 503-Antworten enthalten den Text der Ausnahme (auch lokale Pfade). Nur Loopback und hilfreich für die Diagnose; für eine spätere Mehrbenutzer- oder Netzvariante kürzen.
- `buildflow_store.write` schreibt ohne `fsync`; `core/util.atomic_write_json` hätte es. Bei Stromausfall mitten im Schreiben kann ein Task-Datensatz leer sein. Kleiner Eingriff in GUPPI-Code, daher dem Captain überlassen.
- Modellaufrufe der Agenten laufen auf dem Host hinter Guard, nur Tests in der microVM (siehe Abgleich SEDRA, Frage 5).
- `dulwich` ist in `requirements.txt` gepinnt (1.2.17), aber in diesem Container nicht installierbar (Index-Sperre); auf dem PC vorhanden.
- Audit-Ereignisse `UIX_CHAT_ATTACH` entstehen bei jeder Antwort mit Anhängen erneut; bei langen Chats mit Anhängen wächst das Audit entsprechend.

## 4. Nebenfund an der Arbeitsweise
Ein Hilfsskript namens `tokenize.py` im Arbeitsordner hat beim Prüflauf die Standardbibliothek verdeckt (`import inspect` → `tokenize`). Genau der Fall, den `ENTWICKLUNG.md` für Downloads beschreibt – gilt auch für eigene Skripte: keine Dateinamen von Standardmodulen im Suchpfad.
