"""Schwerere Objekt-Aufgaben fuer den Modelltest (Captain 28.10.2026: der alte Test liess das Modell achtmal dieselben einfachen Formen bauen).

Jede Runde bekommt andere, aber reproduzierbare Masse (Zufall aus der Rundennummer: zwei Modelle bekommen in Runde n genau dieselben Aufgaben). Die Aufgaben sind
mehrteilig (Gewinde-freie Schraube, Gehaeuse mit Bohrungen, Rohr mit Flansch ...). Gelungen ist ein Objekt erst, wenn die fertige STL stimmt:
ein zusammenhaengender Koerper, Abmessungen (sortiert, die Lage im Raum ist frei) und Volumen passen zur Aufgabe. Nur zu rendern reicht nicht.

    aufgaben(runde)  ->  Liste von (name, text, pruefer);  pruefer(stl_pfad) -> None (in Ordnung) oder ein Fehlertext fuer das Modell.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

MASS_TOL = 1.0          # mm, Abmessungen
VOLUMEN_TOL = 0.05      # 5 Prozent (Polygon-Naeherung runder Formen)


def lese_stl(pfad: Path):
    """Dreiecke einer ASCII-STL: Liste von drei Eckpunkten (x, y, z)."""
    punkte, dreiecke = [], []
    for zeile in Path(pfad).read_text(encoding="utf-8", errors="ignore").splitlines():
        teile = zeile.split()
        if len(teile) == 4 and teile[0] == "vertex":
            punkte.append((float(teile[1]), float(teile[2]), float(teile[3])))
            if len(punkte) == 3:
                dreiecke.append(tuple(punkte))
                punkte = []
    return dreiecke


def messen(dreiecke):
    """(sortierte Abmessungen, Volumen, Anzahl zusammenhaengender Koerper)."""
    if not dreiecke:
        return (0.0, 0.0, 0.0), 0.0, 0
    alle = [p for d in dreiecke for p in d]
    dims = tuple(sorted(max(p[i] for p in alle) - min(p[i] for p in alle) for i in range(3)))
    vol = 0.0
    for a, b, c in dreiecke:
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    ids, eltern = {}, []

    def finde(i):
        while eltern[i] != i:
            eltern[i] = eltern[eltern[i]]
            i = eltern[i]
        return i
    for d in dreiecke:
        ks = []
        for p in d:
            k = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
            if k not in ids:
                ids[k] = len(eltern)
                eltern.append(ids[k])
            ks.append(ids[k])
        for k in ks[1:]:
            eltern[finde(k)] = finde(ks[0])
    return dims, abs(vol), len({finde(i) for i in range(len(eltern))})


def pruefer_fuer(soll_dims, soll_vol):
    soll = tuple(sorted(soll_dims))

    def pruefe(stl):
        try:
            dims, vol, teile = messen(lese_stl(stl))
        except (OSError, ValueError) as exc:
            return f"Die STL-Datei ist nicht lesbar ({type(exc).__name__})."
        probleme = []
        if teile != 1:
            probleme.append(f"Der Koerper besteht aus {teile} getrennten Teilen, verlangt ist genau ein zusammenhaengender Koerper")
        if any(abs(a - b) > MASS_TOL for a, b in zip(dims, soll)):
            probleme.append("Die Abmessungen (Lage im Raum egal, sortiert) sind " + " x ".join(f"{x:.1f}" for x in dims) + " mm, verlangt sind " + " x ".join(f"{x:.1f}" for x in soll) + " mm")
        if abs(vol - soll_vol) > VOLUMEN_TOL * soll_vol:
            probleme.append(f"Das Volumen ist {vol:.0f} mm3, erwartet werden etwa {soll_vol:.0f} mm3 (Toleranz {int(VOLUMEN_TOL * 100)} Prozent) - es fehlt oder ueberschuesst Material")
        return "; ".join(probleme) + "." if probleme else None
    return pruefe


def _zahnrad(r):
    n = r.choice([8, 12, 16, 20, 24])
    d, dicke, bohr, zh, zb = r.choice([40, 50, 60]), r.choice([5, 6, 8]), r.choice([6, 8, 10]), r.choice([3, 4]), 4
    wl = r.choice([30, 40])
    text = (f"Ein Zahnrad auf einer Welle, alles ein Koerper: Scheibe {d} mm Durchmesser, {dicke} mm dick, {n} rechteckige Zaehne ({zh} mm hoch, {zb} mm breit) gleichmaessig am Rand; "
            f"durch die Mitte eine Welle mit {bohr} mm Durchmesser und {wl} mm Gesamtlaenge, die Scheibe sitzt mittig auf der Welle. Der Aussendurchmesser ueber die Zaehne ist {d + 2 * zh} mm.")
    # Volumen: Scheibe + Zaehne + Wellenanteil ausserhalb der Scheibe; Zaehne ueberlappen die Scheibe nicht (sitzen aussen)
    vol = math.pi * d ** 2 / 4 * dicke + n * zh * zb * dicke + math.pi * bohr ** 2 / 4 * (wl - dicke)
    return "zahnrad_welle", text, pruefer_fuer((d + 2 * zh, d + 2 * zh, wl), vol)


def _gehaeuse(r):
    a, b, h = r.choice([60, 70, 80]), r.choice([40, 50]), r.choice([25, 30, 35])
    w, bd = r.choice([2, 3]), r.choice([3, 4])
    text = (f"Ein offenes Gehaeuse (Kasten ohne Deckel): aussen {a} x {b} x {h} mm (Hoehe {h}), Wandstaerke {w} mm, Boden {w} mm. "
            f"Im Boden vier Durchgangsbohrungen mit {bd} mm Durchmesser, Mittelpunkte je 8 mm von den beiden naechsten Aussenkanten.")
    vol = a * b * h - (a - 2 * w) * (b - 2 * w) * (h - w) - 4 * math.pi * bd ** 2 / 4 * w
    return "gehaeuse_bohrungen", text, pruefer_fuer((a, b, h), vol)


def _winkel(r):
    a, l, b, t, d = r.choice([40, 50, 60]), r.choice([20, 25, 30]), r.choice([30, 40]), r.choice([3, 4]), r.choice([4, 5, 6])
    text = (f"Ein Winkelprofil: eine waagrechte Platte {a} mm breit, {l} mm lang, {t} mm dick; an einer Schmalseite (Laenge {l}) steht eine senkrechte Platte, "
            f"ebenfalls {l} mm lang und {t} mm dick, gesamte Hoehe des Winkels {b} mm (beide Platten bilden zusammen einen Koerper). "
            f"In der waagrechten Platte zwei Durchgangsbohrungen mit {d} mm Durchmesser, mittig in der Breite der freien Flaeche, bei einem Viertel und bei drei Vierteln der Laenge.")
    vol = l * t * (a + b - t) - 2 * math.pi * d ** 2 / 4 * t
    return "winkel_bohrungen", text, pruefer_fuer((a, l, b), vol)


def _rohr(r):
    dd, di, ln, df, tf = r.choice([30, 40]), r.choice([20, 26]), r.choice([50, 60, 70]), r.choice([50, 60]), r.choice([5, 6])
    text = (f"Ein Rohr mit Flansch an einem Ende: Rohr {dd} mm aussen, {di} mm innen, Gesamtlaenge {ln} mm; am einen Ende ein Flansch (Scheibe) mit {df} mm Aussendurchmesser und {tf} mm Dicke, "
            f"die Rohrbohrung geht durch den Flansch durch. Der Flansch gehoert zur Gesamtlaenge.")
    vol = math.pi / 4 * ((dd ** 2 - di ** 2) * (ln - tf) + (df ** 2 - di ** 2) * tf)
    return "rohr_flansch", text, pruefer_fuer((df, df, ln), vol)


def _treppe(r):
    n, bw, tt, hh = r.choice([4, 5, 6, 7]), r.choice([30, 40]), r.choice([8, 10]), r.choice([6, 8])
    text = (f"Eine massive Treppe mit {n} Stufen: Breite {bw} mm, jede Stufe {tt} mm tief und {hh} mm hoeher als die vorige (erste Stufe {hh} mm hoch), "
            f"alles ein Koerper bis zum Boden (Stufe k hat die Hoehe k mal {hh} mm). Gesamtlaenge {n * tt} mm, Gesamthoehe {n * hh} mm.")
    vol = bw * tt * hh * n * (n + 1) / 2
    return "treppe", text, pruefer_fuer((bw, n * tt, n * hh), vol)


def _schale(r):
    rr, w = r.choice([25, 30, 40]), r.choice([2, 3])
    text = (f"Eine Halbkugelschale (Schale, oben offen, unten flach): Aussenradius {rr} mm, Wandstaerke {w} mm, die flache Kante liegt in einer Ebene. "
            f"Aussendurchmesser {2 * rr} mm, Hoehe {rr} mm.")
    vol = 2 / 3 * math.pi * (rr ** 3 - (rr - w) ** 3)
    return "halbkugelschale", text, pruefer_fuer((2 * rr, 2 * rr, rr), vol)


def _schraube(r):
    sw, k, d, ln = r.choice([13, 17, 19]), r.choice([5, 6, 7]), r.choice([8, 10]), r.choice([20, 30, 40])
    text = (f"Eine Sechskantschraube ohne Gewinde, ein Koerper: Kopf Sechskant (Ecken auf der x-Achse, wie cylinder mit $fn = 6) mit Schluesselweite {sw} mm und {k} mm Hoehe, darunter mittig ein glatter Schaft mit {d} mm Durchmesser und {ln} mm Laenge. "
            f"Gesamthoehe {k + ln} mm.")
    flaeche = math.sqrt(3) / 2 * sw ** 2
    vol = flaeche * k + math.pi * d ** 2 / 4 * ln
    ecke = 2 * sw / math.sqrt(3)
    return "sechskantschraube", text, pruefer_fuer((sw, ecke, k + ln), vol)


GENERATOREN = [_zahnrad, _gehaeuse, _winkel, _rohr, _treppe, _schale, _schraube]


def aufgaben(runde: int, anzahl: int | None = None):
    """Aufgaben der Runde; Namen enden auf _r<runde>. anzahl begrenzt die Liste (Kurzlauf)."""
    gen = GENERATOREN if anzahl is None else GENERATOREN[:anzahl]
    out = []
    for i, g in enumerate(gen):
        name, text, pruefer = g(random.Random(runde * 1000 + i))
        out.append((f"{name}_r{runde}", text, pruefer))
    return out
