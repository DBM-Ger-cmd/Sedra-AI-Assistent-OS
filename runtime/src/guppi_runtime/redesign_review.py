"""Vorarbeiter-Prüfung für Änderungen aus der Sandbox (Grundsatz 16.10.2026): dieselben Regeln, die die Verträge testen,
plus Syntaxprüfung. Vergleicht die Sandbox mit dem Live-Stand und meldet, was gegen die Regeln verstößt. Ändert nichts."""
from __future__ import annotations
import re
import subprocess
from pathlib import Path

MAX_LINES = 400
HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
TOKENS = Path("ui") / "tokens.css"


def changed_files(live, sandbox):
    """Dateien, die sich unterscheiden oder nur in der Sandbox liegen (relative Pfade, mit /)."""
    live, sandbox = Path(live), Path(sandbox)
    out = []
    for p in sorted(sandbox.rglob("*")):
        if not p.is_file(): continue
        rel = p.relative_to(sandbox)
        twin = live / rel
        if not twin.is_file() or twin.read_bytes() != p.read_bytes():
            out.append(str(rel).replace("\\", "/"))
    return out


def review(sandbox, files=None):
    """Findings für die Dateien (alle, wenn nichts angegeben). Jede Zeile: (Datei, Regel, Hinweis)."""
    root = Path(sandbox)
    findings = []
    targets = files if files is not None else [str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file()]
    for rel in targets:
        p = root / rel
        if not p.is_file(): continue
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if p.suffix == ".js" and str(rel).startswith("tools/"):
            if re.search(r"\bfetch\s*\(", text): findings.append((rel, "tool-fetch", "Werkzeuge rufen selbst kein fetch auf"))
            if "localStorage" in text: findings.append((rel, "tool-localstorage", "Werkzeuge nutzen kein localStorage"))
        if len(lines) > MAX_LINES: findings.append((rel, "max-lines", f"{len(lines)} Zeilen, erlaubt sind {MAX_LINES}"))
        if rel.replace("\\", "/") != str(TOKENS).replace("\\", "/") and p.suffix in (".css", ".js", ".html"):
            hits = sorted(set(HEX.findall(text)))
            if hits: findings.append((rel, "raw-colour", "Hex-Farben außerhalb von tokens.css: " + ", ".join(hits[:6])))
        if p.suffix == ".js":
            done = subprocess.run(["node", "--check", str(p)], capture_output=True, text=True, encoding="utf-8")
            if done.returncode != 0: findings.append((rel, "syntax", done.stderr.strip().splitlines()[-1][:160] if done.stderr.strip() else "Syntaxfehler"))
    return findings
