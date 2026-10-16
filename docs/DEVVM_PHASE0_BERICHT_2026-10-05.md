# DevVM Phase 0: Bestandsaufnahme der VM als Entwicklerumgebung (2026-10-05)

Messung, nichts geändert. Skript: `runtime/benchmarks/devvm_probe.py` (und ein kleiner Zusatztest zur Ausführbarkeit). Rohdaten: `workspace/GUPPI_OS/runtime_data/measurements/logs/devvm_probe_2026-10-05_215705.{log,json}`.
Gelaufen über denselben Code wie der Sandbox-Worker (Politik aus `config/sandbox.yaml`: kein Netz, RESTRICTED, tmpfs, Gastnutzer 65534).

## 1. Ergebnisse

| Bereich | Messwert |
|---|---|
| **VM-Start** | 8 von 8 Jobs erfolgreich, Median **1,0 s** (0,9 bis 1,1 s), Aufräumen jedes Mal bestätigt. Die früheren Fehlstarts (etwa 2 von 8, 2026-10-02) traten heute nicht auf, Stichprobe klein. |
| **Ein Job mit 6 Befehlen** | 12,9 s gesamt, alle Befehle Exit 0. Davon 8 s für den bewusst scheiternden Online-Installationsversuch. |
| **Dateien hineinkopieren** | 1 Datei 1,0 s, 50 Dateien 1,3 s, 200 Dateien 1,8 s (Eingabelimit 200 Dateien, 4 MiB). |
| **Image** | Debian mit Linux 6.12, Python **3.12.15**, pip 25.0.1 (nur pip installiert, kein setuptools, kein wheel, kein pytest). |
| **Vorhandene Programme** | `sh`, `bash`, `grep`, `diff`, `find`, `sed`, `awk`, `tar`, `cp`, `mv`, `rm`, `mkdir`, `timeout`, `pip` |
| **Fehlende Programme** | **`git`**, `pytest`, `patch`, `unzip`, `make`, `gcc`, `curl`, `wget` |
| **Python-Module da** | `unittest`, `doctest`, `venv`, `ensurepip`, `sqlite3`, `difflib`, `ast`, `py_compile`, `compileall`, `subprocess`, `threading`, `multiprocessing`, `ctypes`, `ssl`, `zipfile`, `tarfile`, `zoneinfo` |
| **Speicher und CPU** | 986 MiB RAM (891 frei), 2 CPUs; Platten `/`, `/workspace`, `/tmp` je 256 MiB (alles flüchtig) |
| **Grenzen je Befehl** | 64 Prozesse, **128 offene Dateien**, **1 MiB je Datei** (Schreiben von 3 MiB scheitert, 0,9 MiB geht), **30 s CPU-Zeit**, Befehls-Timeout 30 s, Job 120 s, Ausgabe 32 KiB, Export 4 MiB gesamt |
| **Tempo im Gast** | Python-Start 7 ms, 5 Mio. Schleifenschritte 0,32 s, `unittest discover` 0,13 s, `py_compile` 0,07 s |
| **Dateioperationen** | Ordner anlegen (verschachtelt), kopieren, verschieben, löschen gehen; 2000 Dateien in `/workspace` angelegt ohne Fehler (das 200er-Limit gilt nur für die Eingabe); Schreiben in `/etc` verweigert, in `/tmp` erlaubt |
| **Zustand zwischen Befehlen** | Dateien bleiben bestehen **innerhalb eines Jobs**; Umgebungsvariablen nicht (jeder Befehl ist ein eigener Prozess); nach dem Job ist alles weg |
| **Export** | Dateien bis 900 KB kamen zurück; es werden nur **vorher einzeln benannte Dateien** exportiert (kein Ordnerexport) |
| **Pakete offline** | `pip install --no-index --find-links /workspace/wheels --target /workspace/lib` funktioniert (0,6 s), das Paket lässt sich danach importieren. Online-Installation scheitert nach 8 s an der Namensauflösung (erwartet, kein Netz). |
| **Programme ausführen** | `/workspace` liegt auf dem Overlay-Wurzeldateisystem (nicht `noexec`). Hineinkopierte Dateien haben aber Modus 0666 (kein Ausführungsbit), gehören root, und der Gastnutzer darf sie nicht `chmod`en: direkter Aufruf `Permission denied`, `sh datei.sh` geht. |
| **Symlinks** | im Gast anlegbar (z. B. nach `/etc/passwd`); der Export-Pfad des Workers verweigert Symlinks, die Werkzeugschicht (`ToolBox`) hat keinen Symlink-Befehl. |

## 2. Was das für die Anforderungen bedeutet

| Anforderung | Befund | Folge |
|---|---|---|
| A1 Sitzung / Arbeitsbereich über mehrere Befehle | Innerhalb **eines** Jobs ja. Der Job endet nach spätestens 120 s, der Agentenlauf darf aber 10 Minuten dauern. | **Kern-Entscheidung:** der Arbeitsbereich muss auf dem **Host** liegen (Ordner je Mission) und pro Werkzeugaufruf als kleiner Job hinein- und herauskopiert werden. Mit 1 s Startzeit ist das bezahlbar. |
| A1 Export | Nur namentlich genannte Dateien, je höchstens 1 MiB, insgesamt 4 MiB. | Ordner zurückholen braucht entweder eine Dateiliste (zweistufig) oder eine Erweiterung des Workers (Ordnerexport). |
| A2 Git | Fehlt. Ausführbare Dateien kopieren geht nicht ohne Ausführungsbit. | Drei Wege, siehe unten. |
| A2 Testläufer | `unittest` reicht und ist schnell. `pytest` ließe sich offline per Wheel einbringen. | Kein Image-Eingriff nötig. |
| A3 Grenzen | 128 offene Dateien, 30 s CPU, 1 MiB je Datei, 120 s Job können Git und größere Testläufe stören. | Anhebung nur per Änderung in `config/sandbox.yaml` mit Gate; erst messen, ob nötig. |
| B Werkzeugsatz | Alle vorgesehenen Werkzeuge (`list_dir`, `make_dir`, `move_file`, `search_text`, `diff_files`, `run_tests`, `run_python`) sind im Gast ohne Zusatzprogramme machbar (`difflib`, `os`, `unittest`). | Keine Image-Änderung nötig. |
| C Unter-Agenten | Je Werkzeugaufruf eine VM: bei 40 Aufrufen etwa 40 bis 60 s VM-Startzeit zusätzlich. | Innerhalb der 10 Minuten. Mehrere Aufrufe lassen sich in einem Job bündeln. |

## 3. Git im Gast: Wege (Entscheidung steht an, nichts davon ist umgesetzt)
1. **Gastimage ändern** (echtes `git`): ein neues Image mit Git offline herstellen und über den Importpfad mit Prüfsumme und Gate einspielen. Sauberste Lösung, aber der größte Aufwand (Beschaffung des Pakets offline, neuer Pin).
2. **Statisch gebautes `git` im Arbeitsbereich** und Worker ändern, damit hineinkopierte Programme ein Ausführungsbit bekommen (Änderung am Worker, Gate; Sicherheitsfolgen prüfen).
3. **Git in reinem Python** (z. B. `dulwich` als Wheel, Wheels funktionieren offline, kein Ausführungsbit nötig): deckt Anlegen, Commit, Diff, Log ab, aber nicht den vollen Funktionsumfang.

Mein Vorschlag: **Weg 3 jetzt** (sofort nutzbar, keine Änderung an der Sicherheitsgrenze), **Weg 1 als Ziel** nach deiner Freigabe. Beschaffung der Wheels oder des Pakets braucht eine Netzverbindung auf dem Host; das ist deine Entscheidung (wie bei `engine_install.py`).

## 4. Offene Punkte für Phase 1
- Entscheidung Arbeitsbereich: Host-Ordner je Mission mit Kopie hinein/heraus (Vorschlag) oder längere VM-Sitzung (müsste das 120-s-Limit anheben).
- Ordnerexport als Worker-Erweiterung (Gate) oder Dateiliste zweistufig.
- Soll das Ausführungsbit-Problem durch eine Worker-Änderung (Gate) gelöst werden oder reicht Git in Python?
- Wenn `pytest` gewünscht: Wheels beschaffen (Netz auf dem Host, Captain).
