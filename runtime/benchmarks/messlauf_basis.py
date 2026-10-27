"""Gemeinsame Messbausteine der Laufskripte (`scheduler_probelauf`, `nachtlauf_3d`): VRAM, freier RAM, llama-server, groesste Prozesse.

Nur lesend. Vorher hatte jedes Skript eine eigene Kopie; die Nachtmessung vom 27.10.2026 zeigte, dass Messung und Schutz an einer Stelle
stimmen muessen. Das Parsen steht in reinen Funktionen (`parse_*`), damit es ohne GPU getestet werden kann.
"""
from __future__ import annotations

import subprocess

PS = ["powershell", "-NoProfile", "-Command"]


def sh(cmd, timeout=20):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def parse_vram(text):
    """`nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits` -> dict oder None."""
    lines = (text or "").strip().splitlines()
    if not lines:
        return None
    try:
        used, total, temp = [int(x.strip()) for x in lines[0].split(",")[:3]]
    except ValueError:
        return None
    return {"used_mib": used, "total_mib": total, "temp_c": temp}


def parse_free_ram_gb(text, digits=2):
    """Ausgabe von `FreePhysicalMemory` (KiB) -> GB, sonst None."""
    text = (text or "").strip()
    return round(int(text) / 1048576, digits) if text.isdigit() else None


def parse_servers(text):
    """Zeilen `PID|Kommandozeile` -> [{'pid', 'np'}] (np: Wert von -np/--parallel, sonst '?')."""
    found = []
    for line in (text or "").splitlines():
        pid, _, cmd = line.partition("|")
        if pid.strip().isdigit():
            parts = cmd.split()
            np_ = next((parts[i + 1] for i, p in enumerate(parts[:-1]) if p in ("-np", "--parallel")), "?")
            found.append({"pid": int(pid), "np": np_})
    return found


def parse_top(text):
    """Zeilen `Name:PID:GB` -> Liste von Strings; leere Zeilen weg."""
    return [t for t in (text or "").split() if t.count(":") == 2]


def vram():
    return parse_vram(sh(["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"]))


def free_ram_gb(digits=2):
    return parse_free_ram_gb(sh(PS + ["(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"]), digits)


def servers():
    return parse_servers(sh(PS + ["Get-CimInstance Win32_Process -Filter \"Name like 'llama-server%'\" | ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }"]))


def top_prozesse(n=6):
    """Die groessten Prozesse nach privatem Speicher als `Name:PID:GB` (zeigt, wer den RAM frisst)."""
    return parse_top(sh(PS + [f"Get-Process | Sort-Object PrivateMemorySize64 -Descending | Select-Object -First {int(n)} | ForEach-Object "
                              "{ $_.ProcessName + ':' + $_.Id + ':' + [math]::Round($_.PrivateMemorySize64/1GB,2) }"]))
