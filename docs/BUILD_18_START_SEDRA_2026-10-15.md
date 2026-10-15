# Build 18: START_SEDRA – ein sauberer Einstieg, und GUPPI XP als Wahl (15.10.2026)

**Captain, 09:19:** *„SEDRA startet in die alte GUPPI-XP-Oberfläche, die eigentlich archiviert sein sollte.“* –
**09:21:** *„Bau einen neuen sauberen Einstieg, nicht START_GUPPI, sondern START_SEDRA, in die Shell-Übersicht; mit Option, gleich in
die gewünschte Shell zu starten.“* – **09:22:** *„Hinterlege GUPPI XP auch als Shell zur Auswahl, so ist alles sauber gelöst.“*

## 1. Der Befund

Im Paket gibt es keinen Weg, der beim Start die alte Oberfläche liefert: `/` ist `desk.html` (Einstieg oder gewählte Shell), der
Build-6-Desktop liegt nur unter `/retro`, und nichts ruft ihn auf. Was auf dem PC passiert sein muss: `START_GUPPI.bat` startet
**keinen zweiten** UIX neben einem laufenden – es meldet „läuft bereits (PID …)“ und endet. Läuft noch ein Prozess aus einem
**alten Paket**, ist sein Fenster das, was man sieht. Die Meldung nannte nur die PID; woher der Prozess kam, nicht.

## 2. Was gebaut ist

| | Was | Wo |
|---|---|---|
| **`START_SEDRA.bat`** | *Der* Start. Ohne Argument: die **Übersicht der Oberflächen** (Start-Shell) – auch wenn in `uix.yaml` schon eine gewählt ist. `START_SEDRA.bat cockpit` startet **direkt** in diese Oberfläche, nur für diesen Start (die Wahl in `uix.yaml` bleibt). `--gewaehlt`: die gewählte. `--replace`, `--open` wie bisher. | Paketwurzel; `start_sedra.sh` / `START_SEDRA.command` gleich |
| `START_GUPPI.bat` | nur noch Weiterleitung mit Hinweis – alte Verknüpfungen laufen weiter | |
| `uix_start --shell <id>` · `--uebersicht` | die Shell dieses Starts; `uix_server.choose_start_shell` prüft, dass es sie gibt, und sagt sonst, welche es gibt (Exit 4, kein stiller Rückfall) | `uix_start.py`, `uix_server.py` |
| Registrierung | `shell_override` für diesen Prozess; eine **ausdrückliche Wahl** („Diese Oberfläche nehmen“, Werkzeug Module) hebt ihn auf – sonst käme man aus der erzwungenen Übersicht nie heraus | `desk/registry.py`, `shell_set` |
| Laufender UIX | die Meldung nennt jetzt **PID und Paketordner** des laufenden Prozesses („SEDRA läuft bereits: PID 4711, aus C:\…\Build_009“) und sagt, dass das das Fenster ist, das man sieht | `uix_start.describe_running` |
| **GUPPI XP als Shell** | `shells/guppi-xp`: eine Karte im Einstieg mit Bild; wer sie nimmt, landet auf dem archivierten Desktop (`location.replace('/retro' + hash)`). Kein Nachbau, keine Vertragswerkzeuge, `api: []`. Zurück: `START_SEDRA` (Übersicht). | `uix/shells/guppi-xp/` |
| Abnahme | `uix_check --shell guppi-xp`: lädt der alte Desktop mit Token? 3/3, acht „nicht geprüft“ – ehrlich, dort gibt es keine Marken | `benchmarks/uix_check.py` |

## 3. Abnahme

`test_uix_start` 8 (Starter, Optionen, Ordner des laufenden), `test_uix_shell_start` 7 (Override hält bis zur Wahl, unbekannte
Shell ist ein Satz, XP führt ins Archiv, Karten im Einstieg), `test_desk_modules` angepasst (fünf Shells). Fünf Shells:
Start 6/6, Cockpit/Minimal/Paperclip 27/27, GUPPI XP 3/3. Suite: 2050 Tests, grün bis auf den bekannten Umgebungsfehler (`library_not_built`).
