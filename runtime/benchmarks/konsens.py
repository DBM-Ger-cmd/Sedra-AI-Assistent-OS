"""Konsens ueber mehrere Kandidaten (Entwurf, docs/KONZEPT_KONSENS_BAU_2026-11-11.md): ohne Referenz den Kandidaten waehlen, der am wenigsten von der Mehrheit abweicht.

  python benchmarks/konsens.py <spec> <kandidatenordner> <kandidatenordner> ... [--referenz]

Liest nur vorhandene Kandidaten, baut nichts, braucht keine GPU. Eingaben: der Pool der Spec (benchmarks/ab_diff/<spec>.py). Mit --referenz wird zusaetzlich gezeigt,
wie jeder Kandidat gegen die Referenz abweicht (nur fuer Vergleichslaeufe, im echten Betrieb gibt es keine)."""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_bau  # noqa: E402

MAX_STREIT = 20


def abdruck(spec, kandidat):
    """Verhalten eines Kandidaten auf dem Eingabenpool der Spec: {(funktion, index): Ergebnis}. None, wenn die Spec keinen Pool hat oder die Datei fehlt."""
    datei = ab_bau.BENCH / "ab_diff" / f"{spec}.py"
    if not datei.is_file():
        return None
    cfg = ab_bau.modul_laden(datei, f"konsens_cfg_{spec}")
    ziel = Path(kandidat) / f"{cfg.MODUL}.py"
    if not ziel.is_file():
        return None
    kand = ab_bau.modul_laden(ziel, f"konsens_kand_{abs(hash(str(ziel)))}")
    ergebnis = {}
    for fn, liste in cfg.faelle(None).items():
        for i, args in enumerate(liste):
            ergebnis[(fn, i)] = ab_bau._ruf(getattr(kand, fn), *args)
    return ergebnis


def waehle(abdruecke):
    """abdruecke: Liste von Abdruecken (gleiche Faelle). Rueckgabe: Index des gewaehlten, Abweichungen je Kandidat, Anteil einstimmiger Faelle, Streitfaelle.
    Je Fall zaehlt die eindeutige Mehrheit; ohne eindeutige Mehrheit ist es ein Streitfall und zaehlt nicht. Gleichstand der Wertung: der fruehste."""
    if not abdruecke:
        raise ValueError("keine Kandidaten")
    faelle = sorted(abdruecke[0])
    abweichungen = [0] * len(abdruecke)
    streit, einstimmig = [], 0
    for fall in faelle:
        zaehler = collections.Counter(a[fall] for a in abdruecke)
        (erste, n1), *rest = zaehler.most_common()
        if len(zaehler) == 1:
            einstimmig += 1
            continue
        if rest and rest[0][1] == n1:
            streit.append((fall, dict(zaehler)))
            continue
        for i, a in enumerate(abdruecke):
            if a[fall] != erste:
                abweichungen[i] += 1
    bester = min(range(len(abdruecke)), key=lambda i: (abweichungen[i], i))
    return {"gewaehlt": bester, "abweichungen": abweichungen, "einstimmig": einstimmig, "faelle": len(faelle),
            "streitfaelle": streit, "gleichstand": abweichungen.count(abweichungen[bester]) > 1}


ORTE = ("Spec: Hinweis in den Notizen und Randfall im versteckten Test (wirkt am sichersten, weil der Bau die Spec liest)",
        "Arbeitsanweisung bau_coder, Regel 4 (Randfaelle): ein Satz; danach die englische Fassung neu erzeugen und freigeben",
        "Wissensdatenbank / bekannte_fehler.json: greift nur, wenn eine Stufe mit genau diesem Fehlertext scheitert; die versteckten Tests loesen diesen Fall hier nicht aus")


def _signatur(soll, ist):
    """Art der Abweichung eines Kandidaten von der Referenz, grob genug, um gleiche Fehler zusammenzufassen."""
    if ist[0] == "fehler":
        text = re.sub(r"'[^']*'", "'X'", str(ist[1]))
        return ("wirft eine Ausnahme", text[:120])
    if ist[0] == "MUTIERT":
        return ("veraendert seine Eingabe", "")
    if soll[0] == "ok" and ist[0] == "ok":
        try:
            s, i = json.loads(soll[1]), json.loads(ist[1])
        except ValueError:
            return ("anderes Ergebnis", "")
        if isinstance(s, list) and isinstance(i, list):
            fehlt = sorted(str(x) for x in s if x not in i)
            extra = sorted(str(x) for x in i if x not in s)
            if fehlt or extra:
                return ("andere Liste", ("es fehlt " + ", ".join(fehlt) if fehlt else "") + ("; zusaetzlich " + ", ".join(extra) if extra else ""))
            return ("andere Reihenfolge", "")
        return ("anderes Ergebnis", "")
    return ("Referenz und Kandidat enden verschieden (Ausnahme gegen Ergebnis)", "")


def fehlermuster(abdruecke, referenz, mindest=2, beschreiber=repr, beispiele=2):
    """Gemeinsame Fehler: Abweichungen von der Referenz, die mindestens `mindest` Kandidaten teilen (nur im Vergleichslauf moeglich, dort gibt es eine Referenz).
    Rueckgabe: Liste von Vorschlaegen {muster, beschreibung, loesung, orte, faelle, kandidaten, von}, die haeufigsten zuerst. Es wird nichts geschrieben."""
    gruppen = {}
    for nr, a in enumerate(abdruecke):
        for fall, ist in a.items():
            soll = referenz[fall]
            if ist == soll:
                continue
            g = gruppen.setdefault((fall[0], _signatur(soll, ist)), {"kandidaten": set(), "faelle": {}})
            g["kandidaten"].add(nr)
            g["faelle"].setdefault(fall, (soll, ist))
    erg = []
    for (fn, (art, detail)), g in gruppen.items():
        if len(g["kandidaten"]) < mindest:
            continue
        bsp = [f"{fn}{beschreiber(f)}: Referenz {s[1] if s[0] == 'ok' else s}, Kandidat {i[1] if i[0] == 'ok' else i}"[:240] for f, (s, i) in list(g["faelle"].items())[:beispiele]]
        erg.append({"muster": f"{fn}: {art}" + (f" ({detail})" if detail else ""),
                    "beschreibung": f"{len(g['kandidaten'])} von {len(abdruecke)} Kandidaten weichen in {len(g['faelle'])} Faellen gleich von der Referenz ab. Beispiele: " + " | ".join(bsp),
                    "loesung": "offen: der Captain formuliert die Regel (Entwurf aus dem Beispiel ableiten, nicht aus dem Namen des Fehlers)",
                    "orte": list(ORTE), "faelle": len(g["faelle"]), "kandidaten": len(g["kandidaten"]), "von": len(abdruecke)})
    erg.sort(key=lambda e: (-e["kandidaten"], -e["faelle"]))
    return erg


def streit_vorschlaege(ergebnis, beschreiber=repr, beispiele=3):
    """Streitfaelle (kein Mehrheitsentscheid) je Funktion zusammengefasst, als Pruefliste fuer die Durchsicht. Ohne Referenz moeglich."""
    je_fn = {}
    for fall, antworten in ergebnis["streitfaelle"]:
        je_fn.setdefault(fall[0], []).append((fall, antworten))
    erg = []
    for fn, liste in je_fn.items():
        bsp = [f"{fn}{beschreiber(f)}: " + " / ".join(f"{(k[1] if k[0] == 'ok' else k)[:60]} (x{v})" for k, v in a.items()) for f, a in liste[:beispiele]]
        erg.append({"muster": f"Streit {fn}", "beschreibung": f"Die Kandidaten sind in {len(liste)} Faellen uneinig. Beispiele: " + " | ".join(bsp),
                    "loesung": "offen: der Captain oder die Durchsicht entscheidet, welche Antwort stimmt", "faelle": len(liste)})
    return sorted(erg, key=lambda e: -e["faelle"])


def befunde(laeufe, mindest=2, abstand=3):
    """Konsens ueber Befunde mehrerer Durchsichten (Art 'Befunde' im Konzept, Abschnitt 8): ein Befund gilt als bestaetigt, wenn mindestens `mindest` verschiedene Laeufe ihn nennen.
    laeufe: Liste von Laeufen, jeder Lauf eine Liste von Befunden {"datei", "zeile", "art", "text"}. Zwei Befunde aus verschiedenen Laeufen sind derselbe, wenn Datei und Art
    gleich sind und die Zeilen hoechstens `abstand` auseinanderliegen (fehlt die Zeile, passt nur ein Befund ohne Zeile). Verglichen wird mit dem ersten Befund der Gruppe
    (keine Ketten). Ergebnis: {"bestaetigt": [...], "unsicher": [...]}, je Eintrag {"befund", "laeufe", "anzahl"}, die haeufigsten zuerst."""
    if mindest < 1:
        raise ValueError("mindest")
    gruppen = []

    def gleich(a, b):
        if a.get("datei") != b.get("datei") or a.get("art") != b.get("art"):
            return False
        za, zb = a.get("zeile"), b.get("zeile")
        if za is None or zb is None:
            return za is None and zb is None
        return isinstance(za, int) and isinstance(zb, int) and abs(za - zb) <= abstand

    for nr, lauf in enumerate(laeufe):
        for b in lauf or []:
            if not isinstance(b, dict):
                continue
            for g in gruppen:
                if nr not in g["laeufe"] and gleich(g["befund"], b):
                    g["laeufe"].add(nr)
                    break
            else:
                gruppen.append({"befund": b, "laeufe": {nr}})
    eintraege = [{"befund": g["befund"], "laeufe": sorted(g["laeufe"]), "anzahl": len(g["laeufe"])} for g in gruppen]
    eintraege.sort(key=lambda e: -e["anzahl"])
    return {"bestaetigt": [e for e in eintraege if e["anzahl"] >= mindest], "unsicher": [e for e in eintraege if e["anzahl"] < mindest]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("kandidaten", nargs="+")
    ap.add_argument("--referenz", action="store_true", help="zusaetzlich die Abweichung jedes Kandidaten von der Referenz zeigen")
    ap.add_argument("--vorschlaege", metavar="DATEI", help="Antrag (JSON) mit Streitfaellen und, mit --referenz, gemeinsamen Fehlern schreiben; schreibt sonst nirgends")
    a = ap.parse_args()
    if len(a.kandidaten) < 2:
        raise SystemExit("mindestens zwei Kandidaten")
    liste = [(k, abdruck(a.spec, k)) for k in a.kandidaten]
    fehlen = [k for k, d in liste if d is None]
    if fehlen:
        raise SystemExit("kein Eingabenpool oder keine Moduldatei: " + ", ".join(fehlen))
    erg = waehle([d for _, d in liste])
    print(f"{a.spec}: {len(liste)} Kandidaten, {erg['faelle']} Faelle, einstimmig {erg['einstimmig']} ({100 * erg['einstimmig'] / erg['faelle']:.1f} %), Streitfaelle {len(erg['streitfaelle'])}")
    for i, (k, _) in enumerate(liste):
        zusatz = ""
        if a.referenz:
            d = ab_bau.differenz(a.spec, k)
            zusatz = f", gegen die Referenz {len(d['abweichungen'])}"
        print(f"  {'*' if i == erg['gewaehlt'] else ' '} {k}: weicht von der Mehrheit in {erg['abweichungen'][i]} Faellen ab{zusatz}")
    if erg["gleichstand"]:
        print("  Hinweis: Gleichstand in der Wertung, der fruehste Kandidat gewaehlt.")
    for fall, antworten in erg["streitfaelle"][:MAX_STREIT]:
        print("  Streit", fall, "->", {k[1][:60] if k[0] == 'ok' else k: v for k, v in antworten.items()})
    if a.vorschlaege:
        cfg = ab_bau.modul_laden(ab_bau.BENCH / "ab_diff" / f"{a.spec}.py", f"konsens_cfg2_{a.spec}")
        eingaben = {(fn, i): args for fn, liste in cfg.faelle(None).items() for i, args in enumerate(liste)}

        def beschreiber(fall):
            return "(" + ", ".join(repr(x) for x in eingaben[fall]) + ")"
        antrag = {"spec": a.spec, "kandidaten": [k for k, _ in liste], "hinweis": "ANTRAG, nichts davon ist in die Wissensdatenbank oder eine Spec geschrieben; der Captain entscheidet je Eintrag ueber den Ort",
                  "streitfaelle": streit_vorschlaege(erg, beschreiber)}
        if a.referenz:
            ref = abdruck(a.spec, ab_bau.BENCH / "devvm_refs" / a.spec)
            antrag["gemeinsame_fehler"] = fehlermuster([d for _, d in liste], ref, beschreiber=beschreiber)
        Path(a.vorschlaege).parent.mkdir(parents=True, exist_ok=True)
        Path(a.vorschlaege).write_text(json.dumps(antrag, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Antrag geschrieben: {a.vorschlaege} ({len(antrag['streitfaelle'])} Streit-Gruppen, {len(antrag.get('gemeinsame_fehler', []))} gemeinsame Fehler)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
