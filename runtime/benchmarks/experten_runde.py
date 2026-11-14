r"""Messung fuer das Konzept Experten-Schleifen (docs/KONZEPT_EXPERTEN_SCHLEIFEN_2026-11-12.md, offene Frage 3): vier kurze Experten-Vorschlaege einer Runde,
nacheinander im Power-Modus (1 Kanal) oder gleichzeitig im Team-Pool (mehrere Kanaele, gemeinsamer Speicher). Gemessen wird die Dauer der ganzen Runde, oft wiederholt.

    python benchmarks/experten_runde.py <plan.json> <ausgabe.json> [--runden 10] [--port 8111] [--modelle <Ordner>]

plan.json wie bei messlauf.py ("modell", "gemeinsam", "stufen"), je Stufe zusaetzlich "ablauf": "nacheinander" oder "gleichzeitig". Optional "experten": Liste von
{"name", "frage"}; sonst die vier Vorgabe-Experten. Je Stufe ein eigener llama-server (Motor aus config/llama_server.yaml), 1 Aufwaermlauf, dann <runden> Runden mit
denselben vier Fragen. Ergebnis je Stufe: Dauer je Runde (Mittel, Median, kleinste, groesste), Token und Tempo je Vorschlag, VRAM, und die Texte der ersten Runde.
Vorher muss die GPU frei sein (hoechstens 3,5 GiB belegt, kein llama-server); taucht waehrend der Messung ein fremder llama-server auf, gilt die Stufe als gestoert.
Schreibt nur in <ausgabe.json> und Server-Logs daneben."""
import concurrent.futures as cf
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from messlauf import GPU_GESAMT_MIB, RUNTIME, argv_fuer, fremde_server, gpu_belegt, modelle_ordner, post

AUFGABE = ("Aufgabe des Projekts: Ein Programm build_index.py scannt einen Ordner und schreibt daraus dashboard_data.json (einzige Datenquelle), INDEX.md und eine "
           "einzelne HTML-Seite PROJEKT_DASHBOARD.html. Es zaehlt Dateien und Ordner direkt und rekursiv, ordnet Kategorien zu, nimmt git_info auf und muss auf Windows "
           "und Linux laufen.")
FORMAT = " Nenne bis zu 5 nummerierte Punkte, je mit 'pruefbar durch: <Beispiel oder Befehl>'. Hoechstens 250 Woerter, nur Deutsch."
EXPERTEN = [
    {"name": "architektur", "frage": AUFGABE + " Du bist Experte fuer Architektur: Dateien, Funktionen, Schichten, Abhaengigkeiten." + FORMAT},
    {"name": "schnittstellen", "frage": AUFGABE + " Du bist Experte fuer Schnittstellen und Daten: Felder, Typen, Fehlerrueckgaben, Formatversion." + FORMAT},
    {"name": "randfaelle", "frage": AUFGABE + " Du bist Experte fuer Randfaelle und Fehler: leere Eingaben, Sonderzeichen, Unicode, gesperrte Dateien." + FORMAT},
    {"name": "pruefbarkeit", "frage": AUFGABE + " Du bist Experte fuer Pruefbarkeit und Plattform: Windows und Linux, Pfadtrenner, ausfuehrbare Beispiele." + FORMAT},
]


def anfrage(port, experte, max_tokens):
    t0 = time.time()
    r = post(port, {"model": "q", "temperature": 0.7, "max_tokens": max_tokens, "messages": [{"role": "user", "content": experte["frage"]}]}, 600)
    t = r["timings"]
    return {"name": experte["name"], "tokens": t["predicted_n"], "tok_s": round(t["predicted_per_second"], 1), "sekunden": round(time.time() - t0, 1),
            "text": (r["choices"][0]["message"].get("content") or "")}


STOP = set("der die das und oder ein eine einer einen eines den dem des ist sind wird werden muss mit von fuer auf in im zu zum zur als bei nicht auch dass dies durch wie nach aus über nur kann soll sowie dabei wenn sich es sie er an um oder bis pruefbar".split())


def woerter(text):
    return {w for w in re.findall(r"[a-zäöüß_]{4,}", text.lower()) if w not in STOP}


def ueberlappung(erg):
    mengen = [woerter(x["text"]) for x in erg]
    paare = [(a, b) for i, a in enumerate(mengen) for b in mengen[i + 1:]]
    return round(statistics.mean(len(a & b) / len(a | b) for a, b in paare if a | b), 3) if paare else 0.0


def ausfuehrbar(erg):
    zeilen = [l for x in erg for l in x["text"].splitlines() if "pruefbar durch" in l.lower() or "prüfbar durch" in l.lower()]
    gut = [l for l in zeilen if "`" in l and not re.search(r"visuell|sudo|manuell|browser", l.lower())]
    return len(gut), len(zeilen)


def runde(port, experten, ablauf, max_tokens):
    t0 = time.time()
    if ablauf == "nacheinander":
        erg = [anfrage(port, e, max_tokens) for e in experten]
    else:
        with cf.ThreadPoolExecutor(len(experten)) as ex:
            erg = list(ex.map(lambda e: anfrage(port, e, max_tokens), experten))
    return round(time.time() - t0, 1), erg


def stufe_messen(exe, modell, port, gemeinsam, stufe, experten, runden, log):
    experten = stufe.get("experten") or experten
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
        ablauf = stufe.get("ablauf", "nacheinander")
        max_tokens = int(stufe.get("max_tokens", 500))
        runde(port, experten, ablauf, max_tokens)
        dauern, alle, ueber, ausf = [], [], [], []
        for _ in range(runden):
            dauer, erg = runde(port, experten, ablauf, max_tokens)
            if fremde_server() > 1:
                return {"gestoert": "fremder llama-server", "runden_bis_dahin": dauern}
            dauern.append(dauer)
            alle.append(erg)
            ueber.append(ueberlappung(erg))
            ausf.append(ausfuehrbar(erg))
        belegt = gpu_belegt()
        je_vorschlag = [x for erg in alle for x in erg]
        text = Path(log).read_text(encoding="utf-8", errors="replace")
        return {"ablauf": ablauf, "runden": runden, "dauer_s": {"mittel": round(statistics.mean(dauern), 1), "median": round(statistics.median(dauern), 1),
                                                             "klein": min(dauern), "gross": max(dauern)}, "dauern": dauern,
                "ueberlappung_mittel": round(statistics.mean(ueber), 3), "ausfuehrbar_anteil": round(sum(a for a, _ in ausf) / max(1, sum(b for _, b in ausf)), 2),
                "punkte_je_runde": round(statistics.mean(b for _, b in ausf), 1),
                "tokens_je_vorschlag": round(statistics.mean(x["tokens"] for x in je_vorschlag)),
                "tok_s_je_strom": round(statistics.mean(x["tok_s"] for x in je_vorschlag), 1),
                "vram_mib": belegt, "frei_mib": GPU_GESAMT_MIB - belegt,
                "cpu_backend": sorted(set(re.findall(r"load_backend: loaded CPU backend from (\S+)", text))),
                "texte_runde_1": alle[0]}
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
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8111
    runden = int(argv[argv.index("--runden") + 1]) if "--runden" in argv else 10
    modelle = modelle_ordner(argv[argv.index("--modelle") + 1] if "--modelle" in argv else None)
    plan = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    modell = plan["modell"].replace("<modelle>", modelle)
    build = re.search(r"^\s*engine_build:\s*(\S+)", (RUNTIME / "config" / "llama_server.yaml").read_text(encoding="utf-8"), re.M).group(1)
    exe = RUNTIME.parent / "engines" / "llama.cpp" / build / "llama-server.exe"
    if not Path(modell).is_file() or not exe.is_file():
        raise SystemExit("Modelldatei oder Motor fehlt: %s | %s" % (modell, exe))
    if fremde_server() or gpu_belegt() > 3584:
        raise SystemExit("GPU nicht frei (llama-server laeuft oder mehr als 3,5 GiB belegt): keine Messung")
    experten = plan.get("experten") or EXPERTEN
    ausgabe = Path(argv[1])
    ergebnis = {}
    for stufe in plan["stufen"]:
        name = stufe["name"]
        ergebnis[name] = stufe_messen(exe, modell, port, plan.get("gemeinsam", []), stufe, experten, runden, ausgabe.parent / f"server_{ausgabe.stem}_{name}.log")
        print(name, {k: v for k, v in ergebnis[name].items() if k != "texte_runde_1"}, flush=True)
        ausgabe.write_text(json.dumps(ergebnis, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
