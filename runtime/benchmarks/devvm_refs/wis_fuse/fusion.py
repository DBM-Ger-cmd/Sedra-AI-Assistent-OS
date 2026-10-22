import math
import re

FUSION_VERSION = "f1"
STOPPWOERTER = frozenset("""der die das den dem des ein eine einen einem einer eines und oder mit ohne von vom zu zum zur im in am an auf aus bei für fuer
ist sind war wird werden wurde hat haben kann können koennen darf muss soll sollen es sie er wir ich man sich nicht kein keine wie was wer wo wann warum
welche welcher welches wieviel viele viel dass als auch noch nur schon so da dort hier dann wenn bis nach vor über ueber um ob wieder""".split())
ARTEN = ("captain", "agent")
ROUTEN = ("local", "cloud")
_WORT = re.compile(r"[\wäöüß]+(?:[-_][\wäöüß]+)*")


def woerter(frage, *, hoechstens=12):
    if not isinstance(frage, str):
        raise ValueError("wis_anfrage_leer")
    out = []
    for w in _WORT.findall(frage.lower()):
        if len(w) > 1 and w not in STOPPWOERTER and w not in out:
            out.append(w)
    return out[:hoechstens]


def fts_anfrage(woerter_):
    return " OR ".join('"' + w.replace('"', "") + '"' for w in woerter_ if w.replace('"', ""))


def idf(n_abschnitte, n_wort):
    if type(n_abschnitte) is not int or type(n_wort) is not int or n_abschnitte < 0 or n_wort < 0 or n_wort > n_abschnitte:
        raise ValueError("wis_idf_ungueltig")
    return math.log(1.0 + (n_abschnitte - n_wort + 0.5) / (n_wort + 0.5))


def guete(idf_je_wort, enthalten):
    summe = sum(max(0.0, float(v)) for v in idf_je_wort.values())
    if summe <= 0:
        return 0.0
    drin = sum(max(0.0, float(v)) for w, v in idf_je_wort.items() if w in enthalten)
    return min(1.0, drin / summe)


def _liste(werte):
    if not isinstance(werte, (list, tuple)) or any(type(x) is not int for x in werte) or len(set(werte)) != len(werte):
        raise ValueError("wis_liste_ungueltig")
    return list(werte)


def _k_aus(k_aus):
    if type(k_aus) is not int or not 1 <= k_aus <= 20:
        raise ValueError("wis_k_ungueltig")
    return k_aus


def _gewichte(gewichte):
    g = {"k": 60, "w_vektor": 1.0, "w_wort": 0.75, "guete": True, "spitzenschutz": False}
    g.update(gewichte or {})
    if type(g["k"]) is not int or g["k"] < 1:
        raise ValueError("wis_fusion_gewichte")
    for key in ("w_vektor", "w_wort"):
        if isinstance(g[key], bool) or not isinstance(g[key], (int, float)) or g[key] < 0:
            raise ValueError("wis_fusion_gewichte")
    if g["w_vektor"] == 0 and g["w_wort"] == 0:
        raise ValueError("wis_fusion_gewichte")
    return g


def _treffer(nr, punkte, rang_wort, rang_vektor, g):
    return {"nr": nr, "punkte": punkte, "rang_wort": rang_wort, "rang_vektor": rang_vektor, "guete": g}


def fusioniere(wort, vektor, g, gewichte, k_aus=5):
    wort, vektor, k_aus, gw = _liste(wort), _liste(vektor), _k_aus(k_aus), _gewichte(gewichte)
    rw = {nr: r for r, nr in enumerate(wort, 1)}
    rv = {nr: r for r, nr in enumerate(vektor, 1)}
    alle = []
    for nr in sorted(set(wort) | set(vektor)):
        faktor = float(g.get(nr, 0.0)) if gw["guete"] else 1.0
        punkte = (gw["w_vektor"] / (gw["k"] + rv[nr]) if nr in rv else 0.0) + (gw["w_wort"] * faktor / (gw["k"] + rw[nr]) if nr in rw else 0.0)
        alle.append(_treffer(nr, punkte, rw.get(nr), rv.get(nr), float(g.get(nr, 0.0))))
    alle.sort(key=lambda t: (-t["punkte"], t["nr"]))
    out = alle[:k_aus]
    if gw["spitzenschutz"]:
        schutz = vektor[:1] + [nr for nr in wort[:1] if nr not in vektor[:1] and float(g.get(nr, 0.0)) >= 0.5]
        fehlt = [nr for nr in schutz if nr not in [t["nr"] for t in out]]
        bleibt = [t for t in out if t["nr"] not in schutz]
        out = bleibt[: max(0, k_aus - len(fehlt))] + [t for t in out if t["nr"] in schutz] + [next(t for t in alle if t["nr"] == nr) for nr in fehlt]
        out.sort(key=lambda t: (-t["punkte"], t["nr"]))
        out = out[:k_aus]
    return out


def nur_volltext(wort, k_aus=5):
    wort, k_aus = _liste(wort), _k_aus(k_aus)
    return [_treffer(nr, 1.0 / (60 + r), r, None, None) for r, nr in enumerate(wort[:k_aus], 1)]


def _leser(leser):
    if not isinstance(leser, dict) or leser.get("art") not in ARTEN:
        raise ValueError("wis_leser_ungueltig")
    if type(leser.get("stufe")) is not int or not 0 <= leser["stufe"] <= 6:
        raise ValueError("wis_stufe_ungueltig")
    return leser


def _route(route):
    if route not in ROUTEN:
        raise ValueError("wis_route_ungueltig")
    return route


def darf_lesen(quelle, leser, route, *, befunde=(), befunde_sperren=True):
    leser, route = _leser(leser), _route(route)
    if not quelle.get("aktiv") or quelle.get("stufe") is None or quelle["stufe"] > leser["stufe"]:
        return False
    if leser["art"] == "agent" and quelle.get("projekt") is not None and quelle["projekt"] != leser.get("projekt"):
        return False
    if route == "cloud" and quelle.get("personenbezug"):
        return False
    if leser["art"] == "agent" and befunde_sperren and len(befunde) > 0:
        return False
    return True


def sql_filter(leser, route):
    leser, route = _leser(leser), _route(route)
    teile, params = ["q.aktiv = 1", "q.stufe <= ?"], [leser["stufe"]]
    if leser["art"] == "agent":
        teile.append("(q.projekt IS NULL OR q.projekt = ?)")
        params.append(leser.get("projekt"))
    if route == "cloud":
        teile.append("q.personenbezug = 0")
    return " AND ".join(teile), tuple(params)
