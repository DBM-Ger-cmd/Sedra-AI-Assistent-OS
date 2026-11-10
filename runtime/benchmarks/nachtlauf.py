r"""Der Nachtlauf des Captains vom 10.11.2026: eine Folge von Schritten, jeder Schritt mit Zeit und Ergebnis im Protokoll.

    python benchmarks/nachtlauf.py <Projektordner> --bis 07:00 [--protokoll <Datei.md>]

Reihenfolge: 1. Vorpruefung (Fabrik nicht angehalten, GPU frei), 2. Factory-Bau n8n_modell_umstellen ueber den Manager (bau_starten -> bau_schleife.py --spec),
3. Messung KV-Cache f16 gegen q8_0 mit dem MTP-Modell (und die geladene CPU-Variante), 4. volle Testsuite. Nichts wird integriert, gemergt oder gepusht.
Jeder Schritt startet nur, wenn die Fabrik nicht angehalten ist (roter Knopf) und die Endzeit nicht ueberschritten ist."""
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
SPEC = "n8n_modell_umstellen"
AUFTRAG = "Modell-Knoten eines n8n-Workflows auf das lokale Modell umstellen (n8n_lokal.py, S1 bis S4)"
REZEPT = "coder.local_primary_1x80k"
KONTEXT = 81920


def jetzt():
    return datetime.datetime.now().strftime("%H:%M:%S")


class Protokoll:
    def __init__(self, pfad):
        self.pfad = Path(pfad)
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        if not self.pfad.exists():
            self.pfad.write_text("# Nachtprotokoll 10.11.2026\n\nJede Zeile: Uhrzeit, Schritt, Ergebnis. Geschrieben vom Nachtlauf (benchmarks/nachtlauf.py).\n\n", encoding="utf-8")

    def zeile(self, text):
        with self.pfad.open("a", encoding="utf-8") as f:
            f.write(f"- {jetzt()} {text}\n")
        print(f"{jetzt()} {text}", flush=True)


def lauf(befehl, log, timeout):
    with open(log, "w", encoding="utf-8") as f:
        try:
            return subprocess.run(befehl, cwd=str(RUNTIME), stdout=f, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            return 124


def gpu_belegt():
    try:
        return int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip())
    except (ValueError, OSError):
        return -1


def vor_ende(ende):
    return datetime.datetime.now() < ende


def main(argv):
    projekt = Path(argv[0])
    bis = argv[argv.index("--bis") + 1] if "--bis" in argv else "07:00"
    stunde, minute = (int(x) for x in bis.split(":"))
    ende = datetime.datetime.now().replace(hour=stunde, minute=minute, second=0, microsecond=0)
    if ende < datetime.datetime.now():
        ende += datetime.timedelta(days=1)
    pfad = Path(argv[argv.index("--protokoll") + 1]) if "--protokoll" in argv else projekt / "runtime_data" / "nachtprotokoll.md"
    p = Protokoll(pfad)
    logs = projekt / "runtime_data" / "nachtlauf"
    logs.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    p.zeile(f"Nachtlauf startet, Endzeit {ende:%H:%M}, Projekt {projekt.name}")
    from sedra_runtime.workflows import fabrik
    halt = fabrik.angehalten(projekt)
    if halt:
        p.zeile(f"ABBRUCH: Fabrik angehalten ({halt.get('grund')})")
        return 1
    belegt = gpu_belegt()
    p.zeile(f"Vorpruefung: GPU {belegt} MiB belegt")
    if belegt > 3072:
        p.zeile("ABBRUCH: GPU belegt (ueber 3 GiB), Baulauf wuerde scheitern")
        return 1

    # 2. Factory-Bau ueber den Manager
    from sedra_runtime.manager import werkzeuge
    p.zeile(f"Schritt 2: Factory-Bau {SPEC} ueber den Manager (Rezept {REZEPT}, Fenster {KONTEXT})")
    start = werkzeuge.bau_starten(projekt, AUFTRAG, SPEC, REZEPT, KONTEXT)
    p.zeile(f"Manager: {json.dumps(start, ensure_ascii=False)}")
    if start.get("gestartet"):
        sperre = projekt / "runtime_data" / "bau_schleife.lock"
        time.sleep(15)
        while sperre.exists() and vor_ende(ende) and not fabrik.angehalten(projekt):
            time.sleep(20)
        stand = projekt / "runtime_data" / "bau_schleife_stand.json"
        text = stand.read_text(encoding="utf-8") if stand.exists() else "{}"
        p.zeile(f"Bau beendet (Sperre weg: {not sperre.exists()}); Stand {text[:300].replace(chr(10), ' ')}")
        berichte = sorted((projekt / "runtime_data").glob(f"bau_bericht_{SPEC}_*.md"))
        p.zeile(f"Kurzbericht: {berichte[-1].name if berichte else 'keiner'}")
    else:
        p.zeile("Bau nicht gestartet: " + str(start.get("grund")))

    # 3. Messung KV f16 gegen q8_0 (nur wenn Zeit)
    messung = Path(os.environ.get("SEDRA_NACHT_MESSUNG", ""))
    if messung.is_file() and vor_ende(ende) and not fabrik.angehalten(projekt):
        p.zeile("Schritt 3: Messung KV-Cache f16 gegen q8_0 und CPU-Variante")
        code = lauf([py, "-I", "-B", str(messung), str(logs / "kv_messung.json")], logs / "kv_messung.log", 3000)
        p.zeile(f"Messung beendet, Code {code}; Ergebnis: {(logs / 'kv_messung.json').name if (logs / 'kv_messung.json').exists() else 'keines'}")

    # 4. volle Testsuite
    if vor_ende(ende) and not fabrik.angehalten(projekt):
        p.zeile("Schritt 4: volle Testsuite")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        with open(logs / "tests_voll.log", "w", encoding="utf-8") as f:
            code = subprocess.run([py, "-B", "benchmarks/run_tests.py", "all"], cwd=str(RUNTIME), stdout=f, stderr=subprocess.STDOUT, env=env, timeout=3000).returncode
        letzte = (logs / "tests_voll.log").read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1:]
        p.zeile(f"Testsuite beendet, Code {code}: {letzte[0] if letzte else ''}")
    p.zeile("Nachtlauf zu Ende")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
