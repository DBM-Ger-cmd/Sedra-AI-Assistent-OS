"""Differenztest-Faelle fuer den A/B-Bau und den Konsens (ab_bau.py, konsens.py): am0_herkunft (4 Stufen, groesser als die bisherigen Specs).
Das Modul arbeitet mit Dateien, Uhrzeit und einer Klasse mit Zustand. Darum nutzt diese Datei HILFEN (Signatur h(modul, *args)): jede Hilfe legt ihre eigenen Ordner an,
vergleicht nur Dinge, die in beiden Laeufen gleich sein muessen (keine Pfade, keine Uhrzeit), und raeumt auf.
Nur Faelle, die die Spec eindeutig festlegt. Bewusst NICHT enthalten: Zeilenumbruch am Ende der Kennung (Python-Eigenheit von `$`), schema 1.0 oder True,
ungueltige area und mid zugleich, ungueltiger area bei lesen und entfernen, ungueltiger Ordner bei schreiben (die Spec sagt dazu nichts Eindeutiges)."""
import atexit
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

MODUL = "herkunft_kern"
_ZEIT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FIX = {}


def _fixtures():
    if _FIX:
        return _FIX
    wurzel = Path(tempfile.mkdtemp(prefix="ab_herkunft_"))
    atexit.register(shutil.rmtree, str(wurzel), True)
    baue = {
        "leer": {},
        "einfach": {"tool.yaml": b"a", "sub/x.js": b"bb", "README.md": b""},
        "tief": {"a/b/c/d.txt": b"d", "a/z.txt": b"z", "B.txt": b"B", "ä.txt": b"ae", "sub dir/file x.txt": b"s", "a/b.txt": b"\x00\xff"},
        "punktdatei": {"x.txt": b"x", ".hidden": b"h"},
        "punktordner": {"x.txt": b"x", ".git/config": b"c"},
        "punktunten": {"sub/.x": b"x", "sub/y": b"y"},
        "kopf": {"1.txt": b"1", "10.txt": b"10", "2.txt": b"2", "A.txt": b"A", "a.txt": b"a"},
    }
    for name, dateien in baue.items():
        (wurzel / name).mkdir()
        for rel, inhalt in dateien.items():
            p = wurzel / name / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(inhalt)
    (wurzel / "eine_datei.txt").write_bytes(b"x")
    (wurzel / "punktleer").mkdir()
    (wurzel / "punktleer" / "x.txt").write_bytes(b"x")
    (wurzel / "punktleer" / ".leer").mkdir()      # leerer Ordner mit Punkt: nur die Ordnerpruefung sieht ihn
    _FIX.update({name: str(wurzel / name) for name in baue})
    _FIX["punktleer"] = str(wurzel / "punktleer")
    _FIX["nix"] = str(wurzel / "gibt_es_nicht")
    _FIX["datei"] = str(wurzel / "eine_datei.txt")
    return _FIX


def _liste(root):
    return sorted(p.relative_to(root).as_posix() for p in Path(root).rglob("*") if p.is_file())


def _ordner(fix, key):
    """Ordnerangabe als Text oder als Path; 'P:<name>' gibt einen Path."""
    return Path(fix[key[2:]]) if key.startswith("P:") else fix[key]


def h_schreiben(m, area, mid, key, vertrauen, quelle, mission, vorher):
    fix = _fixtures()
    with tempfile.TemporaryDirectory() as root:
        ziel = Path(root) / "local_config" / "uix_herkunft" / area / (mid + ".json") if area in ("tools", "shells") and isinstance(mid, str) and re.match(r"^[a-z0-9][a-z0-9-]{1,39}$", mid) else None
        if vorher and ziel is not None:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_text("alt", encoding="utf-8")
        try:
            ret = m.schreiben(root, area, mid, _ordner(fix, key), quelle=quelle, mission_id=mission, vertrauen=vertrauen)
        except ValueError as e:
            return {"fehler": str(e), "dateien": _liste(root)}
        if ziel is None:
            return {"angenommen": True, "dateien": _liste(root)}
        gelesen = json.loads(ziel.read_text(encoding="utf-8"))
        zeit_ok = bool(_ZEIT.match(ret.get("eingebaut_am", ""))) and bool(_ZEIT.match(gelesen.get("eingebaut_am", "")))
        ret.pop("eingebaut_am", None)
        gelesen.pop("eingebaut_am", None)
        return {"ret": ret, "gleich": ret == gelesen, "zeit_ok": zeit_ok, "dateien": _liste(root)}


def h_erfassen(m, folder, area):
    """Als Liste von Paaren, damit die vorgeschriebene Sortierung nach Schluessel sichtbar wird (ein dict wird beim Vergleich sortiert)."""
    return list(m.erfassen(folder, area).items())


def h_lesen(m, inhalt, area, mid):
    with tempfile.TemporaryDirectory() as root:
        if inhalt is not None:
            p = Path(root) / "local_config" / "uix_herkunft" / area / (mid + ".json")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(inhalt if isinstance(inhalt, bytes) else inhalt.encode("utf-8"))
        return m.lesen(root, area, mid)


def h_entfernen(m, vorhanden, area, mid):
    with tempfile.TemporaryDirectory() as root:
        basis = Path(root) / "local_config" / "uix_herkunft"
        for a, n in (("tools", "andere"), ("shells", mid), ("tools", mid)):
            (basis / a).mkdir(parents=True, exist_ok=True)
            if vorhanden or a != area or n != mid:
                (basis / a / (n + ".json")).write_text("{}", encoding="utf-8")
        erg = m.entfernen(root, area, mid)
        return {"ret": erg, "dateien": _liste(root)}


def h_pruefer(m, schritte):
    """Szenario fuer HerkunftsPruefer. Schritte: ("pruefen", ordnerkey, area, eintragkey) | ("schreibe", rel, bytes) | ("loesche", rel). Ordnerkeys: m, nix, punkt."""
    fix = _fixtures()
    with tempfile.TemporaryDirectory() as root:
        arbeit = Path(root) / "m"
        shutil.copytree(fix["einfach"], arbeit)
        punkt = Path(root) / "punkt"
        shutil.copytree(fix["punktdatei"], punkt)
        ordner = {"m": str(arbeit), "nix": str(Path(root) / "nix"), "punkt": str(punkt), "datei": fix["datei"]}
        ref_e = m.erfassen(fix["einfach"], "tools")
        eintraege = {"E": {"dateien": ref_e}, "E2": {"dateien": {**ref_e, "tool.yaml": "x" * 64}}, "None": None, "kein": {"dateien": []}}
        pruefer = m.HerkunftsPruefer()
        erg, vorige = [], None
        for s in schritte:
            if s[0] == "schreibe":
                p = arbeit / s[1]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(s[2])
            elif s[0] == "loesche":
                (arbeit / s[1]).unlink()
            else:
                r = pruefer.pruefen(ordner[s[1]], s[2], eintraege[s[3]])
                erg.append({"ergebnis": r, "hash_laeufe": pruefer.hash_laeufe, "selbes_objekt": r is vorige})
                vorige = r
        return erg


def _mids():
    return ["ab", "a1", "a-b", "x" * 40, "0a", "9-", "tool-1", "a" * 20]


def _mids_falsch():
    return ["a", "", "x" * 41, "-ab", "Ab", "aB", "a b", "a_b", "a.b", "a/b", "../x", "äb", "abä", "a١", None, 5, b"ab", ["ab"], True]


def faelle(ref):
    fix = _fixtures()
    e_ok = ref.erfassen(fix["einfach"], "tools")
    alt = dict(e_ok)
    alt["tool.yaml"] = "0" * 64
    fehlt = {k: v for k, v in e_ok.items() if k != "sub/x.js"}
    neu = {**e_ok, "zzz.txt": "h", "AAA": "h"}
    EINTRAEGE = [{"dateien": e_ok}, {"dateien": alt}, {"dateien": fehlt}, {"dateien": neu}, {"dateien": {}}, {"dateien": e_ok, "extra": 1, "schema": 1},
                 {"dateien": None}, {"dateien": []}, {"dateien": "x"}, {"dateien": 5}, {}, {"x": 1}, None, [], "x", 5, [("dateien", e_ok)], {"dateien": {"b": "1", "a": "2", "B": "3"}}]
    ORDNER = ["einfach", "leer", "tief", "punktdatei", "punktordner", "punktunten", "kopf", "punktleer", "nix", "datei"]
    gueltig = ["einfach", "leer", "tief", "kopf"]
    inhalte = [None, json.dumps({"schema": 1, "dateien": {}}), json.dumps({"schema": 1, "x": [1, 2], "dateien": {"a": "h"}}), json.dumps({"schema": 2}), json.dumps({"schema": "1"}),
               json.dumps({"schema": None}), json.dumps({}), json.dumps({"dateien": {}}), "[]", "[1]", '"text"', "5", "null", "{", "", "   ", "{'schema': 1}", '{"schema": 1',
               b"\xff\xfe\x00", json.dumps({"schema": 1, "t": "ä"}, ensure_ascii=False), json.dumps({"schema": 1}) + " trailing"]
    szenarien = [
        [("pruefen", "m", "tools", "E"), ("pruefen", "m", "tools", "E")],
        [("pruefen", "m", "tools", "E"), ("pruefen", "m", "tools", "E"), ("pruefen", "m", "tools", "E")],
        [("pruefen", "m", "tools", "E"), ("schreibe", "tool.yaml", b"andere laenge"), ("pruefen", "m", "tools", "E")],
        [("pruefen", "m", "tools", "E"), ("schreibe", "neu.txt", b"n"), ("pruefen", "m", "tools", "E")],
        [("pruefen", "m", "tools", "E"), ("loesche", "tool.yaml"), ("pruefen", "m", "tools", "E"), ("pruefen", "m", "tools", "E")],
        [("pruefen", "m", "tools", "E"), ("pruefen", "m", "tools", "E2"), ("pruefen", "m", "tools", "E2"), ("pruefen", "m", "tools", "E")],
        [("pruefen", "nix", "tools", "E"), ("pruefen", "nix", "tools", "E")],
        [("pruefen", "datei", "tools", "E"), ("pruefen", "datei", "tools", "E")],
        [("pruefen", "punkt", "tools", "E"), ("pruefen", "punkt", "tools", "E")],
        [("pruefen", "m", "tools", "E"), ("pruefen", "nix", "tools", "E"), ("pruefen", "m", "tools", "E"), ("pruefen", "nix", "tools", "E")],
        [("pruefen", "m", "tools", "None"), ("pruefen", "m", "tools", "None"), ("pruefen", "m", "tools", "kein")],
        [("pruefen", "m", "tools", "E"), ("pruefen", "m", "tools", "E"), ("pruefen", "m", "tools", "E2"), ("pruefen", "m", "tools", "E")],
        [("schreibe", "sub/neu.js", b"1"), ("pruefen", "m", "tools", "E"), ("loesche", "sub/neu.js"), ("pruefen", "m", "tools", "E")],
    ]
    return {
        "pfad": [(r, a, m) for r in ("R", Path("R")) for a in ("tools", "shells") for m in _mids()] + [("R", a, m) for a in ("tools", "shells") for m in _mids_falsch()]
                + [("R", a, "ab") for a in ("tool", "Tools", "", None, 5, "tools ", "TOOLS", ["tools"], b"tools")],
        "h_erfassen": [(_ordner(fix, k), a) for k in ORDNER[:8] for a in ("tools", "shells")] + [(Path(fix[k]), "tools") for k in ORDNER[:8]]
                    + [(fix[k], "tools") for k in ("nix", "datei")] + [(fix["einfach"], a) for a in ("tool", "Tools", "", None, 5, "TOOLS")],
        "pruefen": [(fix[k], "tools", e) for k in ORDNER for e in EINTRAEGE] + [(fix["einfach"], "shells", EINTRAEGE[0]), (Path(fix["einfach"]), "tools", EINTRAEGE[1])],
        "h_schreiben": [(a, m, k, v, q, mi, vor) for a in ("tools", "shells") for m in ("ab", "tool-1") for k in ("einfach", "leer", "P:tief", "kopf")
                        for v in ("COMMUNITY", None) for q, mi in (("quelle", "m1"), (Path("a/b"), None)) for vor in (False, True)]
                       + [("tools", "ab", "einfach", 5, q, mi, False) for q, mi in ((None, 5), ("äö", "x"), ("", ""), (["x"], {"a": 1}))]
                       + [("tools", m, "einfach", "v", "q", "m", False) for m in _mids_falsch()] + [(a, "ab", "einfach", "v", "q", "m", False) for a in ("tool", "Tools", "", None, 5)],
        "h_lesen": [(i, a, m) for i in inhalte for a in ("tools", "shells") for m in ("ab", "tool-1")],
        "h_entfernen": [(v, a, m) for v in (True, False) for a in ("tools", "shells") for m in ("ab", "x" * 40)],
        "h_pruefer": [(s,) for s in szenarien],
    }


HILFEN = {"h_erfassen": h_erfassen, "h_schreiben": h_schreiben, "h_lesen": h_lesen, "h_entfernen": h_entfernen, "h_pruefer": h_pruefer}
