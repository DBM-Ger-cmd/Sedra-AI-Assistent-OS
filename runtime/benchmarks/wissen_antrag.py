"""Ein Schritt: einen Ordner im Projekt als Wissensquelle beantragen. Der Antrag landet im Posteingang des Captains.

Aufruf (aus dem Ordner runtime):
  python benchmarks/wissen_antrag.py <Ordner relativ zum Projekt> [--projekt <Projektordner>]
Beispiel:
  python benchmarks/wissen_antrag.py local_config/wissen/eingang/E-20261109-122349-1394

Prüft zuerst (Quelle lesbar, Anzahl Dateien, schon aufgenommen?), dann stellt es den Antrag.
Die Freigabe selbst bleibt beim Captain im Posteingang.
"""
import sys
import threading
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
STANDARD_PROJEKT = RUNTIME.parent / "workspace" / "SEDRA_OS"
STANDARD_ARCH = RUNTIME.parent / "architecture" / "SEDRA_Architecture_v1.20_SELF_DEVELOPMENT"


class _Hub:
    """Die Schnittstelle, die die Wissens-Anträge brauchen: die Runtime, eine Sperre, und das Merken des Antrags."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.lock = threading.RLock()

    def _remember(self, kind, data):
        return data


def _offen_schon(projekt, ordner):
    """Gibt es schon einen offenen Antrag für diesen Ordner? Dann kein zweiter (er stünde doppelt im Posteingang)."""
    import json
    for pfad in (Path(projekt) / "runtime_data" / "missions").glob("M-*.json"):
        try:
            m = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ctx = m.get("context") or {}
        wartet = (m.get("human_gates") or {}).get("pending") or []
        if wartet and str(ordner).replace("\\", "/") in json.dumps(ctx, ensure_ascii=False).replace("\\\\", "/"):
            return m.get("identity", {}).get("mission_id") or pfad.stem
    return None


def antrag(ordner, projekt=STANDARD_PROJEKT, arch=STANDARD_ARCH):
    from sedra_runtime.runtime import SedraRuntime
    from sedra_runtime.wissen import desk_wissen
    schon = _offen_schon(projekt, ordner)
    if schon:
        return {"ok": True, "grund": f"Antrag liegt schon im Posteingang ({schon}), kein zweiter nötig"}
    rt = SedraRuntime(Path(projekt), Path(arch))
    hub = _Hub(rt)
    bindung = {"adapter": "markdown", "wurzel": "projekt", "pfad": str(ordner).replace("\\", "/"), "muster": "*.md", "stufe": 1, "personenbezug": 0}
    pruefung = desk_wissen._quelle_pruefen(hub, None, bindung)
    if pruefung.get("status") == "fehler":
        return {"ok": False, "grund": pruefung.get("satz") or pruefung.get("code")}
    if pruefung.get("schon_da"):
        return {"ok": True, "grund": "schon aufgenommen, kein neuer Antrag nötig"}
    erg = desk_wissen._quelle_beantragen(hub, None, bindung)
    if erg.get("status") == "fehler":
        return {"ok": False, "grund": erg.get("satz") or erg.get("code")}
    return {"ok": True, "grund": erg.get("text", "Antrag liegt im Posteingang"), "antrag": erg.get("decision_id"), "pruefung": pruefung.get("satz")}


if __name__ == "__main__":
    args = sys.argv[1:]
    projekt = STANDARD_PROJEKT
    if "--projekt" in args:
        i = args.index("--projekt")
        projekt = Path(args[i + 1])
        args = args[:i] + args[i + 2:]
    if not args:
        print(__doc__)
        sys.exit(0)
    erg = antrag(args[0], projekt=projekt)
    print(erg)
    sys.exit(0 if erg["ok"] else 1)
