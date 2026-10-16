"""Vorbereitung von Texten für Cloud-Läufe, damit der Inhaltsschutz die Arbeit nicht bei jeder Kleinigkeit unterbricht.

Der Schutz selbst bleibt unverändert. Vor dem Versand werden die exakten Fundstellen durch eigene Begriffe ersetzt, nach Art
benannt: [SCHLUESSEL-001], [PERSON-001], [SENSIBEL-001] usw. Gleiche Werte bekommen überall denselben Begriff, damit der Text
zusammenhängend bleibt. Die Zuordnung Begriff → Original bleibt lokal in einer eigenen Datei und geht nie an das Modell.
Danach prüft der Schutz den bereinigten Text erneut; besteht er nicht, wird die Datei nicht gesendet."""
from __future__ import annotations
import json
from pathlib import Path

from .core.content_policy import scan_content, ScanFailure, KEY_FORMATS, SOFT_SECRETS, PERSONAL, SENSITIVE
from .core.content_guard import ContentGuard

TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".js", ".css", ".html"}


def _label(rule_id):
    rule = rule_id.split(":", 1)[0]
    if rule in KEY_FORMATS or rule in SOFT_SECRETS: return "SCHLUESSEL"
    if rule in SENSITIVE: return "SENSIBEL"
    if rule in PERSONAL or rule.startswith(("PERSON_", "ADDRESS_", "FILTER_")): return "PERSON"
    return "BEGRIFF"


def pseudonymize(text, passes=4):
    """(bereinigter Text, Zuordnung Begriff → Original). Wiederholt, bis der Scanner nichts mehr findet; Fehler geben (text, None)."""
    mapping_all = {}
    for _ in range(passes):
        text, mapping = _once(text)
        if mapping is None: return text, None
        if not mapping: break
        mapping_all.update(mapping)
    return text, mapping_all


def _once(text):
    try:
        hits = scan_content(text)
    except ScanFailure:
        return text, None
    names, counters, mapping = {}, {}, {}
    pieces, last = [], 0
    for h in sorted({(h.start, h.end, h.rule_id) for h in hits}):
        start, end, rule = h
        if start < last: continue                      # überlappende Fundstellen: die erste zählt
        original = text[start:end]
        key = (_label(rule), original)
        if key not in names:
            counters[key[0]] = counters.get(key[0], 0) + 1
            names[key] = f"[{key[0]}-{counters[key[0]]:03d}]"
            mapping[names[key]] = original
        pieces += [text[last:start], names[key]]
        last = end
    pieces.append(text[last:])
    return "".join(pieces), mapping


def prepare(src, dst, mapping_dir=None, audit=None):
    """Kopiert Textdateien von src nach dst, mit eigenen Begriffen. Die Zuordnungen landen in mapping_dir (lokal, nie gesendet)."""
    src, dst = Path(src), Path(dst)
    guard = ContentGuard(cloud_enabled=True)
    report = []
    for path in sorted(src.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES: continue
        rel = path.relative_to(src)
        clean, mapping = pseudonymize(path.read_text(encoding="utf-8", errors="replace"))
        # ALLOW, oder PSEUDONYMIZE: der Schutz ersetzt Personenbezug beim Versand selbst (route cloud), nichts Gesperrtes bleibt
        outcome = guard.check([{"role": "user", "content": clean}], model="m", route="cloud")[1].outcome if mapping is not None else "BLOCK"
        ok = outcome in ("ALLOW", "PSEUDONYMIZE")
        if ok:
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            (dst / rel).write_text(clean, encoding="utf-8")
            if mapping and mapping_dir is not None:
                target = Path(mapping_dir) / (str(rel) + ".zuordnung.json")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        entry = {"file": str(rel).replace("\\", "/"), "begriffe": len(mapping or {}), "bestanden": ok}
        report.append(entry)
        if audit is not None:
            audit.append("TEXT_BEGRIFFE_ERSETZT", component="redesign-prep", payload=entry)
    return report


def restore(text, mapping):
    """Die Begriffe in einer Antwort wieder durch die Originale ersetzen – lokal, nach dem Lauf."""
    for name, original in sorted((mapping or {}).items(), key=lambda kv: -len(kv[0])):
        text = text.replace(name, original)
    return text
