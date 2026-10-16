"""Dateiwerkzeuge für ein Cloud-Modell im Sandbox-Bereich (Grundsatz des Captains, 16.10.2026).

Das Modell darf nur unter der Wurzel der Sandbox lesen und schreiben. Pfade werden aufgelöst und geprüft; Ausbrüche
(absolute Pfade, `..`, Links aus der Wurzel heraus) werden abgelehnt. Geschrieben wird nur bestimmte Dateitypen, mit Größengrenze.
Jeder Schreibvorgang kommt ins Audit (Pfad und Größe, nie der Inhalt). Der Live-Code wird hier nie berührt.

Das Protokoll ist Text: das Modell schreibt je Schritt ein JSON-Objekt mit `tool` und `args`. So prüft der Inhaltsschutz jeden
Schritt wie jeden Cloudaufruf, und es gibt kein Sonderformat, das den Schutz umgeht.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

WRITABLE = {".css", ".js", ".html", ".md", ".yaml", ".yml", ".txt"}
MAX_WRITE_BYTES = 200_000
MAX_READ_CHARS = 12_000
MAX_LIST = 300
TOOLS_HELP = (
    'Antworte in jedem Schritt mit genau EINEM JSON-Objekt, ohne weiteren Text:\n'
    '{"tool": "list_files", "args": {"prefix": "shells/cockpit"}}\n'
    '{"tool": "read_file", "args": {"path": "shells/cockpit/shell.css"}}\n'
    '{"tool": "write_file", "args": {"path": "shells/cockpit/shell.css", "content": "...vollständiger Dateiinhalt..."}}\n'
    '{"tool": "finish", "args": {"summary": "was du geändert hast und warum"}}\n'
    'Schreibe immer den vollständigen Inhalt einer Datei, nie nur einen Ausschnitt. Dateien außerhalb der Wurzel gibt es nicht.'
)


class SandboxError(ValueError):
    pass


class Sandbox:
    def __init__(self, root: Path, audit=None, allow=None):
        """`allow`: Liste erlaubter Dateien oder Ordner (relativ zur Wurzel). Ohne Liste darf der ganze Sandbox-Bereich benutzt werden.
        Jeder Lauf bekommt nur seine eigenen Dateien, damit parallele Läufe einander nicht überschreiben."""
        self.root = Path(root).resolve()
        if not self.root.is_dir(): raise SandboxError("sandbox_root_missing")
        self.audit = audit
        self.allow = [a.replace("\\", "/").strip("/") for a in allow] if allow else None
        self.writes = []

    def _allowed(self, rel):
        if self.allow is None: return True
        posix = rel.replace("\\", "/")
        return any(posix == a or posix.startswith(a + "/") for a in self.allow)

    def _path(self, rel):
        if not isinstance(rel, str) or not rel.strip(): raise SandboxError("path_required")
        if rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel) or ".." in Path(rel).parts:
            raise SandboxError("path_outside_sandbox")
        target = (self.root / rel).resolve()
        if self.root not in target.parents and target != self.root: raise SandboxError("path_outside_sandbox")
        return target

    def list_files(self, prefix=""):
        base = self._path(prefix) if prefix else self.root
        names = sorted(str(p.relative_to(self.root)).replace("\\", "/") for p in base.rglob("*") if p.is_file())
        return names[:MAX_LIST]

    def read_file(self, path):
        target = self._path(path)
        if not target.is_file(): raise SandboxError("file_not_found")
        text = target.read_text(encoding="utf-8", errors="replace")
        return text[:MAX_READ_CHARS] + ("\n[… gekürzt]" if len(text) > MAX_READ_CHARS else "")

    def write_file(self, path, content):
        target = self._path(path)
        if not self._allowed(str(target.relative_to(self.root))): raise SandboxError("file_not_in_scope")
        if target.suffix.lower() not in WRITABLE: raise SandboxError("file_type_not_writable")
        if not isinstance(content, str): raise SandboxError("content_must_be_text")
        data = content.encode("utf-8")
        if len(data) > MAX_WRITE_BYTES: raise SandboxError("content_too_large")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        rel = str(target.relative_to(self.root)).replace("\\", "/")
        self.writes.append({"path": rel, "bytes": len(data)})
        if self.audit is not None:
            self.audit.append("SANDBOX_WRITE", component="sandbox-edit", payload={"path": rel, "bytes": len(data)})
        return f"geschrieben: {rel} ({len(data)} Bytes)"


def parse_action(text):
    """Das erste JSON-Objekt mit `tool` aus der Antwort. Gibt (tool, args) oder None, wenn keins da ist."""
    if not isinstance(text, str): return None
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("tool"), str):
            args = obj.get("args") if isinstance(obj.get("args"), dict) else {}
            return obj["tool"], args
    return None


def run_action(sandbox, tool, args):
    """Führt einen Schritt aus. Gibt (Ergebnistext, fertig) zurück. Fehler kommen als Text zurück, damit das Modell korrigiert."""
    try:
        if tool == "list_files": return "\n".join(sandbox.list_files(str(args.get("prefix", "")))) or "(leer)", False
        if tool == "read_file": return sandbox.read_file(str(args.get("path", ""))), False
        if tool == "write_file": return sandbox.write_file(str(args.get("path", "")), args.get("content")), False
        if tool == "finish": return "fertig: " + str(args.get("summary", ""))[:2000], True
        return f"unbekanntes Werkzeug: {tool}", False
    except SandboxError as exc:
        return f"Fehler: {exc}", False
