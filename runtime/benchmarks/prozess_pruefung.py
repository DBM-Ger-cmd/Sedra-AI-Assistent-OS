"""Prueft laufende SEDRA-Prozesse: laufen sie noch etwas, oder stehen sie nur herum?

Nur lesend. Beendet nichts. Ausgabe: eine Tabelle und ein Urteil je Prozess:
  AKTIV        CPU-Zeit in den letzten 10 s gestiegen -> wird gerade benutzt
  ROUTER       llama-server mit Antwort auf /health; Modell geladen oder nicht (/v1/models)
  STILL        keine CPU-Zeit in 10 s, aelter als 30 min -> pruefen, ob noch gebraucht
  JUNG_STILL   keine CPU-Zeit in 10 s, jung (unter 30 min) -> noch beobachten

Aufruf:  python benchmarks/prozess_pruefung.py [--sekunden 10] [--json]
Beenden macht dieses Werkzeug nie. Ein Prozess wird nur auf ausdrueckliches Ja des Captains beendet.
"""
import json
import re
import subprocess
import sys
import time
import urllib.request

MUSTER = ("llama-server", "devvm_build", "bau_schleife", "unittest", "uix_server", "spec_check", "run_tests", "harness")
ROUTER_PORT = 8090
STILL_MIN = 30


def _ps(skript):
    lauf = subprocess.run(["powershell", "-NoProfile", "-Command", skript], capture_output=True, encoding="utf-8", errors="replace")
    return (lauf.stdout or "").strip()


def liste():
    skript = (
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -notmatch 'Get-CimInstance' -and ("
        + " -or ".join(f"$_.CommandLine -match '{m}'" for m in MUSTER)
        + ") } | Select-Object ProcessId,Name,@{n='AlterMin';e={[int]((Get-Date)-$_.CreationDate).TotalMinutes}},"
        "@{n='MB';e={[int]($_.WorkingSetSize/1MB)}},CommandLine | ConvertTo-Json -Depth 2"
    )
    text = _ps(skript)
    if not text:
        return []
    daten = json.loads(text)
    return [daten] if isinstance(daten, dict) else daten


def cpu_stand(pids):
    if not pids:
        return {}
    ids = ",".join(str(p) for p in pids)
    text = _ps(f"Get-Process -Id {ids} -ErrorAction SilentlyContinue | ForEach-Object {{ \"$($_.Id) $($_.TotalProcessorTime.TotalSeconds)\" }}")
    stand = {}
    for zeile in text.splitlines():
        teile = zeile.split()
        if len(teile) == 2:
            stand[int(teile[0])] = float(teile[1].replace(",", "."))
    return stand


def router_status():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{ROUTER_PORT}/health", timeout=3) as r:
            gesund = r.status == 200
    except Exception:
        return {"antwortet": False, "modelle": []}
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{ROUTER_PORT}/v1/models", timeout=3) as r:
            modelle = json.loads(r.read().decode("utf-8")).get("data", [])
    except Exception:
        modelle = []
    geladen = [m["id"] for m in modelle if (m.get("status") or {}).get("value") == "loaded"]
    return {"antwortet": gesund, "modelle": geladen}


def urteil(p, cpu_delta, router):
    name = (p.get("Name") or "").lower()
    if name == "llama-server.exe" and _ist_router(p):
        if router["antwortet"]:
            return "ROUTER", "Modell geladen: " + (", ".join(router["modelle"]) or "keins")
        return "ROUTER", "antwortet nicht auf /health"
    if cpu_delta is not None and cpu_delta > 1.0:
        return "AKTIV", f"CPU +{cpu_delta:.1f} s in 10 s"
    if int(p.get("AlterMin") or 0) >= STILL_MIN:
        return "STILL", f"seit {p.get('AlterMin')} min ohne CPU-Zeit: pruefen, ob noch gebraucht"
    return "JUNG_STILL", f"seit {p.get('AlterMin')} min ohne CPU-Zeit"


def _ist_router(p):
    return bool(re.search(rf"--port\s+{ROUTER_PORT}\b", p.get("CommandLine") or "")) or "llama_server\\router" in (p.get("CommandLine") or "")


def main(argv):
    sekunden = 10
    if "--sekunden" in argv:
        sekunden = int(argv[argv.index("--sekunden") + 1])
    prozesse = liste()
    pids = [int(p["ProcessId"]) for p in prozesse]
    vorher = cpu_stand(pids)
    time.sleep(sekunden)
    nachher = cpu_stand(pids)
    router = router_status()
    zeilen = []
    for p in prozesse:
        pid = int(p["ProcessId"])
        delta = None if pid not in vorher or pid not in nachher else nachher[pid] - vorher[pid]
        status, grund = urteil(p, delta, router)
        zeilen.append({"pid": pid, "name": p.get("Name"), "status": status, "grund": grund, "minuten": p.get("AlterMin"), "mb": p.get("MB"),
                       "befehl": (p.get("CommandLine") or "")[:120]})
    if "--json" in argv:
        print(json.dumps(zeilen, ensure_ascii=False, indent=2))
    else:
        if not zeilen:
            print("Keine SEDRA-Prozesse gefunden.")
        for z in zeilen:
            print(f"{z['pid']:>6}  {z['status']:<10} {str(z['name']):<18} {str(z['minuten']):>5} min  {str(z['mb']):>5} MB  {z['grund']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
