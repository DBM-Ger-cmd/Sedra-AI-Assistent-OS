r"""Kurzstart eines Modells aus diesem Arbeitsstand (Umzug nach A1, U2-9 Punkt 5): GPU-Lease, Server laden, zwei gleichzeitige kurze Fragen, entladen, Lease frei.

    .venv\Scripts\python.exe benchmarks/kurzstart.py <project_dir>                         Trockenlauf: Plan und Prüfungen, startet NICHTS
    .venv\Scripts\python.exe benchmarks/kurzstart.py <project_dir> --go                    der Kurzstart (braucht das Ja des Captains für die GPU)
    optionen: --recipe coder.llama_qwen35 (Vorgabe)  --slots 2  --context <je Slot>  --min-free-ram-gb 6  --abort-free-ram-gb 3  --max-temp 85  --set KEY=VALUE (nur für diesen Lauf)

RAM-Schutz (der Captain braucht den Arbeitsspeicher für seine Anwendungen): Der Lauf startet nur, wenn mindestens --min-free-ram-gb frei sind, und bricht ab (Server wird über die eigene PID
beendet, Lease frei), sobald der freie RAM unter --abort-free-ram-gb fällt. Das Hauptmodell (coder.local_primary, n_cpu_moe 28) hält einen großen Teil der Gewichte im Hauptspeicher; es bekommt einen eigenen
Lauf, wenn der Captain den Speicher freigibt. Der Trockenlauf nennt die Schätzung.
Was der Lauf nie tut: ein Rezept, die Engine oder einen Schalter ändern, einen Prozess nach Namen beenden, einen zweiten GPU-Nutzer starten. Ergebnis: runtime_data/measurements/kurzstart_<rezept>_p<N>_<datum>.json."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))


def ram():
    """(frei GB, gesamt GB) des Hauptspeichers (Windows)."""
    class Status(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                    ("tpage", ctypes.c_ulonglong), ("apage", ctypes.c_ulonglong), ("tvirt", ctypes.c_ulonglong), ("avirt", ctypes.c_ulonglong), ("ext", ctypes.c_ulonglong)]
    s = Status()
    s.length = ctypes.sizeof(Status)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return round(s.avail / 2 ** 30, 2), round(s.total / 2 ** 30, 2)


def vram():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip().split(",")
    used, total, temp = (int(x) for x in out)
    return {"used_mib": used, "total_mib": total, "free_gib": round((total - used) / 1024, 2), "temp_c": temp}


def rss_gb(pid):
    if not pid:
        return None
    out = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue).WorkingSet64"], capture_output=True, text=True).stdout.strip()
    return round(int(out) / 2 ** 30, 2) if out.isdigit() else None


def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def ask(endpoint, alias, text, result, key):
    body = json.dumps({"model": alias, "messages": [{"role": "user", "content": text}], "max_tokens": 48, "temperature": 0}).encode()
    req = urllib.request.Request(endpoint + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
        msg = data["choices"][0]["message"]
        result[key] = {"start": t0, "end": time.time(), "seconds": round(time.time() - t0, 2), "answer": (msg.get("content") or msg.get("reasoning_content") or "")[:160],
                       "tokens": (data.get("usage") or {}).get("completion_tokens"), "ok": True}
    except Exception as exc:
        result[key] = {"start": t0, "end": time.time(), "ok": False, "error": str(exc)[:200]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--recipe", default="coder.llama_qwen35")
    ap.add_argument("--slots", type=int, default=2)
    ap.add_argument("--context", type=int, default=None, help="Fenster je Slot (Vorgabe: per_slots des Rezepts)")
    ap.add_argument("--min-free-ram-gb", type=float, default=6.0)
    ap.add_argument("--abort-free-ram-gb", type=float, default=3.0)
    ap.add_argument("--max-temp", type=int, default=85)
    ap.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE", help="Servereinstellung nur für diesen Lauf (das Rezept bleibt unberührt), z. B. --set mmap=false")
    ap.add_argument("--go", action="store_true")
    args = ap.parse_args(argv)
    project = Path(args.project)
    local = yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8-sig"))["role_routing"]["capabilities"]
    recipes = {r["id"]: r for r in local}
    recipe = recipes.get(args.recipe)
    problems = []
    if not recipe or recipe.get("provider") != "llama-cpp-server":
        problems.append(f"{args.recipe} ist kein llama-cpp-server-Rezept dieses Projekts")
        recipe = None
    gguf = Path(str((recipe or {}).get("profile", {}).get("server", {}).get("gguf", ""))) if recipe else None
    if recipe and not gguf.is_file():
        problems.append(f"Modelldatei fehlt: {gguf}")
    per = ((recipe or {}).get("profile", {}).get("context", {}).get("per_slots") or {}) if recipe else {}
    context = args.context or per.get(args.slots) or per.get(str(args.slots)) or 8192
    free_ram, total_ram = ram()
    size = (recipe or {}).get("model_size_gb")
    moe = ((recipe or {}).get("profile", {}).get("server", {}) or {}).get("n_cpu_moe")
    estimate = "gering (Gewichte auf der GPU, nur Seitencache beim Laden)" if not moe else f"hoch: n_cpu_moe {moe} hält einen großen Teil der {size} GB im Hauptspeicher"
    vr = vram()
    from guppi_runtime.jobs.testlab import TestLab, default_path
    holder = TestLab(default_path(project)).holder()
    running = subprocess.run(["powershell", "-NoProfile", "-Command", "@(Get-Process llama-server -ErrorAction SilentlyContinue).Count"], capture_output=True, text=True).stdout.strip()
    print(f"Rezept {args.recipe} | Slots {args.slots} | Fenster je Slot {context} | Modell {size} GB | RAM-Bedarf: {estimate}")
    print(f"RAM frei {free_ram} von {total_ram} GB (Start ab {args.min_free_ram_gb}, Abbruch unter {args.abort_free_ram_gb}) | VRAM belegt {vr['used_mib']} MiB, {vr['temp_c']} °C")
    print("GPU-Lease:", "frei" if not holder or holder["stale"] else f"BELEGT von {holder['owner']} ({holder['purpose']})", "| llama-server-Prozesse:", running)
    if free_ram < args.min_free_ram_gb:
        problems.append(f"zu wenig freier RAM: {free_ram} GB < {args.min_free_ram_gb} GB")
    if holder and not holder["stale"]:
        problems.append("GPU-Lease belegt")
    if running not in ("0", ""):
        problems.append("es läuft schon ein llama-server")
    for p in problems:
        print("PROBLEM:", p)
    if not args.go:
        print("Trockenlauf: nichts gestartet. Mit --go nach dem Ja des Captains.")
        return 1 if problems else 0
    if problems:
        return 2
    from guppi_runtime.models.gpu_preflight import clear_leftovers
    from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
    switches = yaml.safe_load((project / "local_config" / "switches.yaml").read_text(encoding="utf-8-sig"))["switches"]
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml")
    config.enabled, config.mtp = True, bool((switches.get("llama_server") or {}).get("mtp", False))
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_kurzstart_")))
    alias = str(recipe.get("model") or recipe["id"])
    report = {"recipe": args.recipe, "model": alias, "slots": args.slots, "per_slot": context, "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "engine_build": config.engine_build, "mtp": config.mtp, "ram_before": {"free_gb": free_ram, "total_gb": total_ram}, "vram_before": vr, "status": "gestartet"}
    stop = {"abort": None}
    low = {"min_free_gb": free_ram}

    def watch():
        while not stop.get("done"):
            f = ram()[0]
            low["min_free_gb"] = min(low["min_free_gb"], f)
            t = vram()["temp_c"]
            if f < args.abort_free_ram_gb or t > args.max_temp:
                stop["abort"] = f"freier RAM {f} GB" if f < args.abort_free_ram_gb else f"GPU {t} °C"
                try:
                    runtime.unload_model(all_models=True)
                except Exception:
                    pass
                return
            time.sleep(0.5)
    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    lab = TestLab(default_path(project))
    owner = os.environ.get("TESTLAB_OWNER", "kurzstart")
    try:
        with lab.lease(owner, f"Kurzstart {args.recipe} aus A1", ttl_s=900, wait_s=0, preflight=clear_leftovers):
            t0 = time.time()
            server = dict(recipe["profile"]["server"])
            if args.overrides:
                sys.path.insert(0, str(RUNTIME / "benchmarks"))
                from devvm_build import server_settings
                server.update(server_settings(args.overrides))
                report["overrides"] = args.overrides
            runtime.load_model(alias, context_length=context * args.slots, gpu="max", identifier=alias, parallel=args.slots, server=server)
            report["load_s"] = round(time.time() - t0, 1)
            st = runtime.status()
            report["pid"] = st.get("pid")
            report["vram_loaded"] = vram()
            report["ram_loaded"] = {"free_gb": ram()[0], "server_rss_gb": rss_gb(st.get("pid"))}
            props = get_json(runtime.endpoint + "/props")
            report["props_n_ctx"], report["props_total_slots"] = props.get("default_generation_settings", {}).get("n_ctx"), props.get("total_slots")
            try:
                report["slots_endpoint"] = [{"id": s.get("id"), "n_ctx": s.get("n_ctx")} for s in get_json(runtime.endpoint + "/slots")]
            except Exception as exc:
                report["slots_endpoint"] = f"nicht lesbar: {str(exc)[:80]}"
            answers, threads = {}, []
            for i in range(args.slots):
                th = threading.Thread(target=ask, args=(runtime.endpoint, alias, "Nenne die Hauptstadt von Frankreich in einem Wort.", answers, f"slot{i + 1}"))
                threads.append(th)
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            report["answers"] = {k: {x: v for x, v in a.items() if x not in ("start", "end")} for k, a in answers.items()}
            spans = sorted((a["start"], a["end"]) for a in answers.values())
            report["overlap"] = len(spans) > 1 and all(spans[i][1] > spans[i + 1][0] for i in range(len(spans) - 1))
            report["vram_after_answers"] = vram()
            report["ram_after_answers"] = {"free_gb": ram()[0], "server_rss_gb": rss_gb(st.get("pid"))}
            runtime.unload_model(all_models=True)
            deadline = time.time() + 30
            while time.time() < deadline and vram()["used_mib"] > vr["used_mib"] + 300:
                time.sleep(1)
            report["vram_unloaded"] = vram()
            report["running_after"] = runtime.status().get("running")
    except Exception as exc:
        report["status"] = f"FEHLER: {str(exc)[:300]}"
        try:
            runtime.unload_model(all_models=True)
        except Exception:
            pass
    stop["done"] = True
    report["ram_min_free_gb"] = low["min_free_gb"]
    report["abort"] = stop["abort"]
    after = lab.holder()
    report["lease_after"] = "frei" if not after or after["stale"] else f"belegt von {after['owner']}"
    report["ram_after"] = {"free_gb": ram()[0]}
    answers_ok = all(a.get("ok") for a in (report.get("answers") or {}).values()) and bool(report.get("answers"))
    freed = report.get("vram_unloaded", {}).get("used_mib", 10 ** 9) <= vr["used_mib"] + 400
    report["status"] = "bestanden" if (report["status"] == "gestartet" and answers_ok and report.get("overlap") and freed and report["lease_after"] == "frei" and not report["abort"]) else report["status"] if report["status"] != "gestartet" else "NICHT bestanden"
    out = project / "runtime_data" / "measurements"
    out.mkdir(parents=True, exist_ok=True)
    tag = ("_" + "_".join(o.replace("=", "-") for o in args.overrides)) if args.overrides else ""
    path = out / f"kurzstart_{args.recipe}_p{args.slots}{tag}_{date.today().isoformat()}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("status", "abort", "load_s", "props_n_ctx", "props_total_slots", "overlap", "vram_before", "vram_loaded", "vram_unloaded", "ram_before", "ram_loaded", "ram_min_free_gb", "lease_after", "running_after")}, indent=2, ensure_ascii=False, default=str))
    print("Ergebnis:", path)
    return 0 if report["status"] == "bestanden" else 3


if __name__ == "__main__":
    sys.exit(main())
