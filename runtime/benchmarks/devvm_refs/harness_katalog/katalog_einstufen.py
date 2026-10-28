import re

STUFEN = ("frei", "vorarbeiter", "captain", "verboten")
STRENGE = {s: i for i, s in enumerate(STUFEN)}
KEINE_REGEL = "Keine Regel passt – ohne Regel entscheidet der Captain (HS-21)."


def befehl_normal(zeile):
    return " ".join(str(zeile or "").split()).casefold()


def pfad_normal(pfad):
    teile = [t for t in str(pfad or "").replace("\\", "/").split("/") if t not in ("", ".")]
    return "/".join(teile).casefold()


def _glob_regex(muster):
    out, i = [], 0
    while i < len(muster):
        if muster.startswith("**/", i):
            out.append("(?:.*/)?"); i += 3
        elif muster.startswith("**", i):
            out.append(".*"); i += 2
        elif muster[i] == "*":
            out.append("[^/]*"); i += 1
        elif muster[i] == "?":
            out.append("[^/]"); i += 1
        else:
            out.append(re.escape(muster[i])); i += 1
    return re.compile("".join(out) + r"\Z", re.S)


def passt(muster, werkzeug, ziel):
    if werkzeug == "befehl":
        m, z = befehl_normal(muster), befehl_normal(ziel)
        return z.startswith(m[:-1].rstrip()) if m.endswith("*") else z == m
    return bool(_glob_regex(pfad_normal(muster)).match(pfad_normal(ziel)))


def genauigkeit(muster):
    return len(str(muster).replace("*", "").replace("?", ""))


def einstufen(regeln, werkzeug, ziel):
    beste = None
    for r in regeln:
        if werkzeug not in r["werkzeug"] and "*" not in r["werkzeug"]:
            continue
        for m in r["muster"]:
            if not passt(m, werkzeug, ziel):
                continue
            schluessel = (genauigkeit(m), STRENGE[r["stufe"]])
            if beste is None or schluessel > beste[0]:
                beste = (schluessel, r)
    if beste is None:
        return {"stufe": "captain", "regel": None, "begruendung": KEINE_REGEL}
    r = beste[1]
    return {"stufe": r["stufe"], "regel": r["id"], "begruendung": r["begruendung"]}
