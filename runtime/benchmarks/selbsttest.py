"""Selbsttest der Harness: ein Lauf, ein Ergebnis (Lauf-Typ `selbsttest`).

Startet benchmarks/run_tests.py mit den angegebenen Gruppen (Standard: alle schnellen Gruppen),
liest die Zusammenfassung aus, nimmt den Git-Stand dazu und schreibt das Ergebnis als JSON und Markdown
nach runtime_data/selbsttest/. Ändert keinen Code und keine Git-Objekte.

    python benchmarks/selbsttest.py              # alle schnellen Gruppen (all)
    python benchmarks/selbsttest.py runtime orchestra
Exit-Code 0 nur bei GRUEN (Zusammenfassung gefunden, 0 rot, Exit 0 des Laufs).
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]          # .../runtime
REPO = RUNTIME.parent                                  # Projektwurzel (git)
OUT = RUNTIME / "runtime_data" / "selbsttest"           # gitignoriert (runtime_data/)
SUMMARY = re.compile(r"(\d+) Tests, (\d+) \S*bersprungen, (\d+) rot")


def git(*args):
    try:
        r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, encoding="utf-8", timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"fehler: {type(exc).__name__}"
    return r.stdout.strip() if r.returncode == 0 else f"fehler: {r.stderr.strip()[:200]}"


def main(argv):
    gruppen = list(argv) or ["all"]
    jetzt = datetime.now()
    stamp = jetzt.strftime("%Y-%m-%d_%H%M%S")
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / f"selbsttest_{stamp}.log"
    befehl = [sys.executable, "benchmarks/run_tests.py", *gruppen]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    with log.open("w", encoding="utf-8") as f:
        r = subprocess.run(befehl, cwd=str(RUNTIME), stdout=f, stderr=subprocess.STDOUT, env=env)
    text = log.read_text(encoding="utf-8", errors="replace")
    m = SUMMARY.search(text)
    tests, uebersprungen, rot = (int(m.group(i)) for i in (1, 2, 3)) if m else (None, None, None)
    gruen = bool(m) and r.returncode == 0 and rot == 0
    ergebnis = {
        "zeitpunkt": jetzt.isoformat(timespec="seconds"),
        "repo_head": git("rev-parse", "HEAD"),
        "repo_status": git("status", "--short") or "sauber",
        "gruppen": gruppen,
        "exit_code": r.returncode,
        "tests": tests,
        "uebersprungen": uebersprungen,
        "rot": rot,
        "zusammenfassung_gefunden": bool(m),
        "bewertung": "GRUEN" if gruen else "ROT_ODER_UNVOLLSTAENDIG",
        "log": log.name,
        "grenzen": "Keine Browser-Bahn (ausser all --slow), keine Windows-Live-Abnahme, keine GPU-Tests.",
    }
    (OUT / f"selbsttest_{stamp}.json").write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        f"# Selbsttest {stamp}",
        "",
        f"- Bewertung: **{ergebnis['bewertung']}**",
        f"- Repo-HEAD: `{ergebnis['repo_head']}`",
        f"- Arbeitsstand: {ergebnis['repo_status']}",
        f"- Gruppen: {' '.join(gruppen)}",
        f"- Tests: {tests}, uebersprungen: {uebersprungen}, rot: {rot}",
        f"- Exit-Code: {r.returncode}",
        f"- Log: {log.name}",
        "",
        ergebnis["grenzen"],
    ]
    (OUT / f"selbsttest_{stamp}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(ergebnis["bewertung"], tests, rot, str(OUT / f"selbsttest_{stamp}.md"))
    return 0 if gruen else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
