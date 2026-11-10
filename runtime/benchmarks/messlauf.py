r"""Messlauf fuer Modellserver-Einstellungen (Lagen im RAM, Kanaele, MTP, KV-Typ, Kontext): ein eigener llama-server pro Stufe, gleiche Aufgaben, Tempo und VRAM.

    python benchmarks/messlauf.py <stufen.json> <ausgabe.json> [--port 8110] [--modelle <Ordner>]

stufen.json:
  {"modell": "<modelle>/unsloth/.../Datei.gguf",            # <modelle> = Ordner aus runtime/config/local_paths.yaml oder --modelle
   "gemeinsam": ["-ngl", "99", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "-ub", "512", "--threads", "12", "--threads-batch", "20", "--jinja", "--reasoning", "off"],
   "aufgaben": ["Schreibe ...", "..."],                      # optional, sonst drei Code-Aufgaben
   "stufen": [{"name": "mtp_21", "kanaele": 1, "kontext": 81920, "args": ["--n-cpu-moe", "21", "--spec-type", "draft-mtp"]}]}
Je Stufe: `-c` = kanaele x kontext, `-np` = kanaele, 1 Aufwaermlauf, 3 Runden mit so vielen gleichzeitigen Anfragen wie Kanaele. Ergebnis je Stufe: Tempo je Strom
und zusammen (Token/s), Annahmequote der MTP-Entwuerfe, VRAM belegt und frei (MiB), geladene CPU-Variante. Vorher muss die GPU frei sein (hoechstens 3,5 GiB belegt, kein
llama-server); taucht waehrend einer Stufe ein fremder llama-server auf, gilt die Stufe als gestoert. Schreibt nur in <ausgabe.json> und Server-Logs daneben."""
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
AUFGABEN = ["Schreibe eine Python-Funktion parse_kv(text), die Zeilen der Form key = value in ein Dict umwandelt, Kommentare mit # ignoriert und bei Fehlern ValueError('line N') wirft. Nur Code.",
            "Schreibe eine Python-Klasse LruCache mit get, put und einer maximalen Groesse, ohne externe Pakete, mit kurzen Typhinweisen. Nur Code.",
            "Schreibe ein Python-Skript, das eine CSV-Datei einliest, nach der Spalte betrag summiert und das Ergebnis mit zwei Nachkommastellen ausgibt. Nur Code."]
GPU_GESAMT_MIB = 12282


def modelle_ordner(angabe=None):
    if angabe:
        return str(angabe)
    text = (RUNTIME / "config" / "local_paths.yaml").read_text(encoding="utf-8-sig")
    treffer = re.search(r"^\s*modelle:\s*'?\"?([^'\"\n]+)", text, re.M)
    if not treffer:
        raise SystemExit("Kein Modellordner: --modelle angeben oder local_paths.yaml pruefen")
    return treffer.group(1).strip()


def argv_fuer(exe, modell, port, gemeinsam, stufe):
    k = int(stufe.get("kanaele", 1))
    kontext = int(stufe.get("kontext", 32768))
    if not 1 <= k <= 8 or not 2048 <= kontext <= 262144:
        raise ValueError("stufe_ungueltig")
    return [str(exe), "-m", str(modell), "--host", "127.0.0.1", "--port", str(port), "-c", str(k * kontext), "-np", str(k), "--alias", "q", "--no-webui"] + list(gemeinsam) + list(stufe.get("args", []))


def auswerten(runden):
    """runden: Liste von Runden, je Runde eine Liste (Token/s, erzeugte Token, Entwuerfe, angenommen, Sekunden der Runde)."""
    n = len(runden)
    je_strom = sum(sum(x[0] for x in r) / len(r) for r in runden) / n
    zusammen = sum(sum(x[1] for x in r) / r[0][4] for r in runden) / n
    entwuerfe = sum(x[2] for r in runden for x in r)
    angenommen = sum(x[3] for r in runden for x in r)
    return {"tg_je_strom": round(je_strom, 1), "gesamt_tok_s": round(zusammen, 1), "annahme": round(angenommen / entwuerfe, 2) if entwuerfe else None}


def gpu_belegt():
    return int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip())


def fremde_server():
    ausgabe = subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe"], capture_output=True, text=True).stdout
    return ausgabe.lower().count("llama-server.exe")


def post(port, body, t=900):
    r = urllib.request.Request("http://127.0.0.1:%d/v1/chat/completions" % port, json.dumps(body).encode(), {"Content-Type": "application/json", "Authorization": "Bearer x"})
    return json.loads(urllib.request.urlopen(r, timeout=t).read())


def stufe_messen(exe, modell, port, gemeinsam, stufe, aufgaben, log):
    p = subprocess.Popen(argv_fuer(exe, modell, port, gemeinsam, stufe), stdout=subprocess.DEVNULL, stderr=open(log, "w"))
    try:
        ende = time.time() + 300
        while time.time() < ende:
            if p.poll() is not None:
                return {"fehler": "server_beendet"}
            try:
                if urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=3).status == 200:
                    break
            except Exception:
                time.sleep(2)
        else:
            return {"fehler": "start_timeout"}
        k = int(stufe.get("kanaele", 1))

        def eins(i):
            r = post(port, {"model": "q", "temperature": 0, "max_tokens": 400, "messages": [{"role": "user", "content": aufgaben[i % len(aufgaben)] + " " * (i // len(aufgaben))}]})
            t = r["timings"]
            return t["predicted_per_second"], t["predicted_n"], t.get("draft_n") or 0, t.get("draft_n_accepted") or 0
        eins(0)
        runden = []
        for _ in range(3):
            t0 = time.time()
            with cf.ThreadPoolExecutor(k) as ex:
                erg = list(ex.map(eins, range(k)))
            dt = time.time() - t0
            if fremde_server() > 1:
                return {"gestoert": "fremder llama-server"}
            runden.append([x + (dt,) for x in erg])
        out = auswerten(runden)
        belegt = gpu_belegt()
        out.update({"vram_mib": belegt, "frei_mib": GPU_GESAMT_MIB - belegt})
        text = Path(log).read_text(encoding="utf-8", errors="replace")
        out["cpu_backend"] = sorted(set(re.findall(r"load_backend: loaded CPU backend from (\S+)", text)))
        return out
    finally:
        p.terminate()
        try:
            p.wait(20)
        except Exception:
            p.kill()
        time.sleep(3)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8110
    modelle = modelle_ordner(argv[argv.index("--modelle") + 1] if "--modelle" in argv else None)
    plan = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    modell = plan["modell"].replace("<modelle>", modelle)
    build = re.search(r"^\s*engine_build:\s*(\S+)", (RUNTIME / "config" / "llama_server.yaml").read_text(encoding="utf-8"), re.M).group(1)
    exe = RUNTIME.parent / "engines" / "llama.cpp" / build / "llama-server.exe"
    if not Path(modell).is_file() or not exe.is_file():
        raise SystemExit("Modelldatei oder Motor fehlt: %s | %s" % (modell, exe))
    if fremde_server() or gpu_belegt() > 3584:
        raise SystemExit("GPU nicht frei (llama-server laeuft oder mehr als 3,5 GiB belegt): kein Messlauf")
    aufgaben = plan.get("aufgaben") or AUFGABEN
    ausgabe = Path(argv[1])
    ergebnis = {}
    for stufe in plan["stufen"]:
        name = stufe["name"]
        ergebnis[name] = stufe_messen(exe, modell, port, plan.get("gemeinsam", []), stufe, aufgaben, ausgabe.parent / f"server_{ausgabe.stem}_{name}.log")
        print(name, ergebnis[name], flush=True)
    ausgabe.write_text(json.dumps(ergebnis, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
