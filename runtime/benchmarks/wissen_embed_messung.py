r"""S7.1: Messung eines Embedding-Modells mit llama-server (`--embeddings`) gegen den Goldsatz. Nur Standardbibliothek, kein numpy.

Läuft nur unter der GPU-Lease des Testlabs (Aufruf, Pfade durch die eigenen ersetzen):

    <guppi>/runtime/.venv/Scripts/python.exe benchmarks/testlab_cli.py hold --owner spec7-s71 --purpose "S7.1 Embedding" --ttl 1800 --wait 600 -- \
        <guppi>/runtime/.venv/Scripts/python.exe -I benchmarks/wissen_embed_messung.py --gguf <modelle>/<ordner>/<datei>.gguf --name bge-m3 \
        --engine <guppi>/engines/llama.cpp/b11160/llama-server.exe --port 8094 --rev 0155a83 --json ergebnis_bge-m3.json

Ablauf: eigenen `llama-server --embeddings` starten (nur diese PID wird beendet), alle Abschnitte des Korpus von wissen_baseline.py einbetten
(GPU: 1 Aufwärmlauf + 3 Läufe, Zeit je 1000 Abschnitte als Median), VRAM über nvidia-smi (nur lesend), dann CPU (`-ngl 0`) mit einer Stichprobe
(jeder `--cpu-schritt`-te Abschnitt, hochgerechnet auf 1000), Vektorsuche in reinem Python, RRF (k = 60) mit der FTS5-Liste, Kennzahlen für
Wort, Vektor und hybrid. Rezepte, Engine und Schalter der Laufzeit werden nicht angefasst."""
import argparse
import json
import math
import operator
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wissen_baseline as wb  # noqa: E402

RRF_K = 60
TIEFE = 50
STAPEL = 16
MAX_ZEICHEN_EINGABE = 6000
ANWEISUNG = "Given a question, retrieve the document passage that answers the question"


def http(url, daten=None, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(daten).encode("utf-8") if daten is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def vram_mib():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout
        return int(out.strip().splitlines()[0])
    except Exception:
        return None


class VramWaechter(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.spitze, self.stop = 0, False

    def run(self):
        while not self.stop:
            v = vram_mib()
            if v:
                self.spitze = max(self.spitze, v)
            time.sleep(0.5)


class Server:
    def __init__(self, a, ngl):
        self.a, self.ngl, self.proc = a, ngl, None

    def __enter__(self):
        a = self.a
        cmd = [a.engine, "-m", a.gguf, "--embeddings", "--host", "127.0.0.1", "--port", str(a.port), "-ngl", str(self.ngl),
               "-c", str(a.kontext), "-b", str(a.kontext), "-ub", str(a.kontext), "-np", "1", "--alias", a.name]
        if a.pooling:
            cmd += ["--pooling", a.pooling]
        self.start = time.time()
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(240):
            if self.proc.poll() is not None:
                raise RuntimeError(f"llama-server beendet sich beim Start (Code {self.proc.returncode})")
            try:
                if http(f"http://127.0.0.1:{a.port}/health", timeout=3).get("status") == "ok":
                    self.startzeit = time.time() - self.start
                    return self
            except Exception:
                time.sleep(1)
        raise RuntimeError("llama-server wurde nicht bereit")

    def __exit__(self, *e):
        if self.proc and self.proc.poll() is None:      # nur die eigene PID
            self.proc.terminate()
            try:
                self.proc.wait(20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        time.sleep(2)


def einbetten(port, name, texte, stat):
    """Vektoren (L2-normiert) für die Texte; zu lange Eingaben werden gekürzt und gezählt."""
    ergebnis = []
    for i in range(0, len(texte), STAPEL):
        stapel = [t[:MAX_ZEICHEN_EINGABE] for t in texte[i:i + STAPEL]]
        stat["gekuerzt"] += sum(1 for t in texte[i:i + STAPEL] if len(t) > MAX_ZEICHEN_EINGABE)
        antwort = http(f"http://127.0.0.1:{port}/v1/embeddings", {"input": stapel, "model": name})
        stat["token"] += antwort.get("usage", {}).get("prompt_tokens", 0)
        for d in sorted(antwort["data"], key=lambda d: d["index"]):
            v = d["embedding"]
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            ergebnis.append([x / n for x in v])
    return ergebnis


def zeitlauf(a, texte, wiederholungen, ngl):
    zeiten, vektoren, vram = [], None, {}
    with Server(a, ngl) as s:
        vram["nach_start"] = vram_mib()
        w = VramWaechter()
        w.start()
        einbetten(a.port, a.name, texte[:min(32, len(texte))], {"gekuerzt": 0, "token": 0})      # Aufwärmen, nicht gewertet
        stat = {"gekuerzt": 0, "token": 0}
        for _ in range(wiederholungen):
            stat = {"gekuerzt": 0, "token": 0}
            t = time.time()
            v = einbetten(a.port, a.name, texte, stat)
            zeiten.append(time.time() - t)
            vektoren = vektoren or v
        w.stop = True
        w.join(2)
        vram["spitze"] = w.spitze
        startzeit = s.startzeit
    return {"zeiten_s": zeiten, "stat": stat, "vram": vram, "startzeit_s": startzeit}, vektoren


def cos(a, b):
    return sum(map(operator.mul, a, b))


def rang_von(treffer, daten, quellen):
    return next((r for r, idx in enumerate(treffer, 1) if any(wb.passt(daten, idx, q) for q in quellen)), None)


def rrf(listen):
    punkte = {}
    for liste in listen:
        for r, idx in enumerate(liste, 1):
            punkte[idx] = punkte.get(idx, 0.0) + 1.0 / (RRF_K + r)
    return [i for i, _ in sorted(punkte.items(), key=lambda x: -x[1])]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--engine", required=True, help="Pfad zu llama-server.exe (Engine b11160)")
    ap.add_argument("--port", type=int, required=True, help="eigener freier Port, nicht der der Laufzeit")
    ap.add_argument("--pooling", default="", help="leer = Angabe im Modell")
    ap.add_argument("--anfrage-anweisung", action="store_true", help="Anfragen mit 'Instruct: … Query: …' (Qwen3)")
    ap.add_argument("--kontext", type=int, default=8192)
    ap.add_argument("--rev", default=None)
    ap.add_argument("--repo", default=str(wb.REPO))
    ap.add_argument("--gold", default=str(wb.GOLD))
    ap.add_argument("--laeufe", type=int, default=3)
    ap.add_argument("--cpu-schritt", type=int, default=10, help="jeder n-te Abschnitt als CPU-Stichprobe")
    ap.add_argument("--json")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    fragen = json.loads(Path(a.gold).read_text(encoding="utf-8"))["fragen"]
    daten = wb.korpus(Path(a.repo), a.rev)
    db = wb.baue_index(daten)
    texte = [p + "\n" + t for _, p, t in daten]
    anfragen = [("Instruct: " + ANWEISUNG + "\nQuery: " + f["frage"]) if a.anfrage_anweisung else f["frage"] for f in fragen]
    res = {"modell": a.name, "gguf": Path(a.gguf).name, "abschnitte": len(daten), "korpus_stempel_stand": a.rev or "Arbeitsstand",
           "vram_vorher_mib": vram_mib()}
    print(f"{a.name}: {len(daten)} Abschnitte, VRAM vorher {res['vram_vorher_mib']} MiB", flush=True)

    # --- GPU: Zeit, VRAM, Vektoren
    gpu, vek = zeitlauf(a, texte + anfragen, a.laeufe, 99)
    med = statistics.median(gpu["zeiten_s"])
    gpu["median_s"] = med
    gpu["s_je_1000"] = med / (len(texte) + len(anfragen)) * 1000
    gpu["vram_vorher_mib"] = res["vram_vorher_mib"]
    gpu["vram_zusatz_spitze_mib"] = (gpu["vram"]["spitze"] - res["vram_vorher_mib"]) if gpu["vram"]["spitze"] and res["vram_vorher_mib"] else None
    gpu["vram_nachher_mib"] = vram_mib()
    res["gpu"] = gpu
    print(f"GPU: Läufe {[round(z, 1) for z in gpu['zeiten_s']]} s, {gpu['s_je_1000']:.1f} s je 1000 Abschnitte, VRAM-Spitze zusätzlich "
          f"{gpu['vram_zusatz_spitze_mib']} MiB, gekürzt {gpu['stat']['gekuerzt']}, Start {gpu['startzeit_s']:.1f} s", flush=True)
    dv, qv = vek[:len(texte)], vek[len(texte):]

    # --- CPU: Stichprobe, hochgerechnet; Vergleich der Vektoren mit der GPU
    idx = list(range(0, len(texte), a.cpu_schritt))
    cpu, cvek = zeitlauf(a, [texte[i] for i in idx], 1, 0)
    cpu["stichprobe"] = len(idx)
    cpu["s_je_1000"] = cpu["zeiten_s"][0] / len(idx) * 1000
    cpu["kosinus_gpu_cpu_min"] = min(cos(cvek[n], dv[i]) for n, i in enumerate(idx))
    res["cpu"] = cpu
    print(f"CPU: {len(idx)} Abschnitte in {cpu['zeiten_s'][0]:.1f} s = {cpu['s_je_1000']:.1f} s je 1000; Kosinus GPU/CPU min {cpu['kosinus_gpu_cpu_min']:.4f}", flush=True)

    # --- Qualität
    zeilen = {"wort": [], "vektor": [], "hybrid": []}
    for f, qvec in zip(fragen, qv):
        wort = wb.suche(db, f["frage"], "wort", TIEFE)
        vektor = [i for i, _ in sorted(enumerate(map(lambda d: cos(qvec, d), dv)), key=lambda x: -x[1])[:TIEFE]]
        for modus, liste in (("wort", wort), ("vektor", vektor), ("hybrid", rrf([wort, vektor]))):
            zeilen[modus].append({"id": f["id"], "art": f["art"], "rang": rang_von(liste, daten, f["quellen"]), "frage": f["frage"]})
    res["qualitaet"] = {}
    for modus, z in zeilen.items():
        k = wb.kennzahlen(z)
        je_art = {art: wb.kennzahlen([x for x in z if x["art"] == art]) for art in sorted({x["art"] for x in z})}
        anders = wb.kennzahlen([x for x in z if x["art"] != "wortgleich"])
        res["qualitaet"][modus] = {"gesamt": k, "je_art": je_art, "andere_worte": anders, "fragen": z}
        print(f"[{modus}] Treffer@5 {k['treffer_at_5']:.1%} Treffer@1 {k['treffer_at_1']:.1%} MRR@10 {k['mrr_at_10']:.3f} | andere Worte {anders['treffer_at_5']:.1%}"
              + "".join(f" | {art} {kk['treffer_at_5']:.1%}" for art, kk in je_art.items()), flush=True)
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
