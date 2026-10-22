r"""Ausgangswert der heutigen Wortsuche für Spec 7 (S7.1, Vorbereitung): Treffer@5 und MRR des Goldsatzes mit SQLite FTS5 (BM25).

    .venv\Scripts\python.exe benchmarks/wissen_baseline.py [--detail] [--json PFAD] [--rev COMMIT]

Nur Standardbibliothek (und `git`, nur mit --rev), liest das Repo, keine GPU, kein Netz, schreibt nichts (außer mit --json). Die Quellen sind die von G1-S7-b:
docs/*.md (ohne Unterordner) und die Speicher knowledge.py, arbeitsumfeld_wissen.py, gateway/wissen.py (dazu gateway/klassen.py, das Regelbuch
des Gateway-Speichers). Markdown wird nach Überschriften zerlegt, Python nach Blöcken (Konstante, Klasse.Methode, Schlüssel eines Wörterbuchs),
das Logbuch nach Tabellenzeilen. Abschnitte über 2500 Zeichen werden an Zeilengrenzen geteilt. Der Abschnitt 'Vorbereitung S7.1' der Spec
bleibt draußen, damit die Messung sich nicht selbst findet.

Zwei Läufe: 'wort' (die Wörter der Frage, ODER-verknüpft, ohne Füllwörter) und 'stamm' (Wörter ab 6 Buchstaben als Präfix, ein grober Stamm).
Ausgangswert für WIS-05 ist 'wort'. Treffer@5: Anteil der Fragen mit einer erwarteten Quelle unter den ersten 5 Abschnitten. MRR@10: Mittel von
1/Rang des ersten Treffers (0 ab Rang 11)."""
import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GOLD = Path(__file__).resolve().parent / "wissen_goldsatz.json"
PY_QUELLEN = ["runtime/src/guppi_runtime/knowledge.py", "runtime/src/guppi_runtime/arbeitsumfeld_wissen.py",
              "runtime/src/guppi_runtime/gateway/wissen.py", "runtime/src/guppi_runtime/gateway/klassen.py"]
LOGBUCH = "docs/LOGBUCH_AGENT_MANAGER.md"
AUSGESCHLOSSEN = ("Vorbereitung S7.1",)
MAX_ZEICHEN = 2500
STOPP = frozenset("""der die das den dem des ein eine einen einem einer eines und oder mit ohne von vom zu zum zur im in am an auf aus bei für fuer
ist sind war wird werden wurde hat haben kann können darf muss soll sollen es sie er wir ich man sich nicht kein keine wie was wer wo wann warum
welche welcher welches wieviel viele viel dass als auch noch nur schon so da dort hier dann wenn bis nach vor über um ob wieder""".split())


def chunk_text(pfad, zeilen, ausgabe):
    """Teilt einen Abschnitt an Zeilengrenzen in Stücke bis MAX_ZEICHEN; leere Abschnitte entfallen."""
    stuecke, cur, n = [], [], 0
    for z in zeilen:
        if cur and n + len(z) > MAX_ZEICHEN:
            stuecke.append(cur)
            cur, n = [], 0
        cur.append(z)
        n += len(z) + 1
    if cur:
        stuecke.append(cur)
    for i, s in enumerate(stuecke):
        text = "\n".join(s).strip()
        if len(text) < 3:
            continue
        ausgabe.append((pfad + (f" (Teil {i + 1})" if len(stuecke) > 1 else ""), text))


def zerlege_markdown(datei, text, ausgabe):
    pfade, stack, cur, fence = [], {}, [], False
    kopf = datei.rsplit("/", 1)[-1]

    def schliessen():
        pfad = " > ".join(stack[k] for k in sorted(stack)) or kopf
        chunk_text(pfad, cur, ausgabe)

    for z in text.splitlines():
        if z.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"^(#{1,6})\s+(.*\S)\s*$", z)
        if m:
            schliessen()
            cur = []
            stufe = len(m.group(1))
            for k in [k for k in stack if k >= stufe]:
                del stack[k]
            stack[stufe] = m.group(2)
        else:
            cur.append(z)
    schliessen()


def zerlege_logbuch(datei, text, ausgabe):
    titel = next((z[2:].strip() for z in text.splitlines() if z.startswith("# ")), "Logbuch")
    intro = []
    for z in text.splitlines():
        if z.startswith("| 20"):
            zellen = [c.strip() for c in z.strip().strip("|").split("|")]
            zeit, art, eintrag = (zellen + ["", "", ""])[:3]
            ausgabe.append((f"{titel} > Zeile {zeit} {art} {eintrag[:60]}", z))
        else:
            intro.append(z)
    chunk_text(titel, intro, ausgabe)


def zerlege_python(datei, text, ausgabe):
    """Blöcke: Modul-Beschreibung, jede Konstante, Funktion, Klasse.Methode; in Wörterbüchern und Listen ein Abschnitt je Schlüssel/Eintrag."""
    zeilen = text.splitlines()
    grenzen = []                      # (Zeilennummer, Bezeichnung)
    block, klasse, ende_doc = None, None, 0
    m = re.match(r'\s*r?(""".*?"""|\'\'\'.*?\'\'\')', text, re.S)
    if m:
        ende_doc = text[:m.end()].count("\n") + 1
        grenzen.append((0, "Modul-Beschreibung"))
    for i, z in enumerate(zeilen):
        if i < ende_doc:
            continue
        top = re.match(r"^(?:def|class)\s+(\w+)", z) or re.match(r"^([A-Za-z_]\w*)\s*(?::[^=]+)?=", z)
        if top:
            block, klasse = top.group(1), (top.group(1) if z.startswith("class") else None)
            grenzen.append((i, block))
            continue
        if klasse:
            mm = re.match(r"^    def\s+(\w+)", z)
            if mm:
                grenzen.append((i, f"{klasse}.{mm.group(1)}"))
                continue
        if block and not klasse and not z.startswith("def"):
            mm = re.match(r"""^    ['"]([^'"]+)['"]\s*:""", z)
            if mm:
                grenzen.append((i, f"{block} / {mm.group(1)}"))
                continue
            mm = re.match(r"^    \{'nr':\s*(\d+).*?'titel':\s*'([^']+)'", z)
            if mm:
                grenzen.append((i, f"{block} / Schritt {mm.group(1)} {mm.group(2)}"))
    # Kommentare direkt über einer Grenze gehören zu ihr
    korrigiert = []
    for i, name in grenzen:
        while i > 0 and zeilen[i - 1].lstrip().startswith("#") and (not korrigiert or i - 1 > korrigiert[-1][0]):
            i -= 1
        korrigiert.append((i, name))
    if not korrigiert or korrigiert[0][0] > 0:
        korrigiert.insert(0, (0, "Kopf"))
    kopf = datei.rsplit("/", 1)[-1]
    for n, (i, name) in enumerate(korrigiert):
        bis = korrigiert[n + 1][0] if n + 1 < len(korrigiert) else len(zeilen)
        chunk_text(f"{kopf} > {name}", zeilen[i:bis], ausgabe)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


def korpus(repo, rev=None):
    """Mit rev (ein Commit) liest die Messung genau diesen Stand aus Git, unabhängig vom Arbeitsstand."""
    daten = []
    if rev:
        namen = git(repo, "ls-tree", "--name-only", rev, "docs/").decode("utf-8").splitlines()
        quellen = sorted(n for n in namen if n.startswith("docs/") and n.endswith(".md")) + PY_QUELLEN
    else:
        quellen = sorted(p.relative_to(repo).as_posix() for p in (repo / "docs").glob("*.md")) + PY_QUELLEN
    for rel in quellen:
        try:
            raw = git(repo, "show", f"{rev}:{rel}") if rev else (repo / rel).read_bytes()
        except (subprocess.CalledProcessError, OSError):
            print(f"WARNUNG: Quelle fehlt: {rel}", file=sys.stderr)
            continue
        text = raw.decode("utf-8", errors="replace")
        teile = []
        if rel.endswith(".py"):
            zerlege_python(rel, text, teile)
        elif rel == LOGBUCH:
            zerlege_logbuch(rel, text, teile)
        else:
            zerlege_markdown(rel, text, teile)
        daten += [(rel, p, t) for p, t in teile if not any(a in p for a in AUSGESCHLOSSEN)]
    return daten


def baue_index(daten):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE VIRTUAL TABLE f USING fts5(pfad, text, tokenize='unicode61 remove_diacritics 2')")
    db.executemany("INSERT INTO f(rowid, pfad, text) VALUES (?,?,?)", [(i, p, t) for i, (_, p, t) in enumerate(daten)])
    return db


def woerter(frage):
    return [w for w in re.findall(r"[\wäöüß]+(?:[-_][\wäöüß]+)*", frage.lower()) if len(w) > 1 and w not in STOPP]


def anfrage(frage, modus):
    teile = []
    for w in woerter(frage):
        w = w.replace('"', "")
        if modus == "stamm" and len(w) >= 6:
            teile.append('"' + w[:max(5, len(w) - 2)] + '"*')
        else:
            teile.append('"' + w + '"')
    return " OR ".join(teile)


def suche(db, frage, modus, limit=20):
    q = anfrage(frage, modus)
    if not q:
        return []
    return [r[0] for r in db.execute("SELECT rowid FROM f WHERE f MATCH ? ORDER BY bm25(f, 2.0, 1.0) LIMIT ?", (q, limit))]


def passt(daten, idx, quelle):
    datei, pfad, _ = daten[idx]
    return datei == quelle["datei"] and quelle["abschnitt"].lower() in pfad.lower()


def messe(daten, db, fragen, modus):
    zeilen = []
    for f in fragen:
        treffer = suche(db, f["frage"], modus)
        rang = next((r for r, idx in enumerate(treffer, 1) if any(passt(daten, idx, q) for q in f["quellen"])), None)
        zeilen.append({"id": f["id"], "art": f["art"], "rang": rang, "frage": f["frage"],
                       "top1": daten[treffer[0]][0] + " > " + daten[treffer[0]][1][:90] if treffer else ""})
    return zeilen


def kennzahlen(zeilen):
    n = len(zeilen) or 1
    return {"fragen": len(zeilen), "treffer_at_5": sum(1 for z in zeilen if z["rang"] and z["rang"] <= 5) / n,
            "treffer_at_1": sum(1 for z in zeilen if z["rang"] == 1) / n,
            "mrr_at_10": sum(1.0 / z["rang"] for z in zeilen if z["rang"] and z["rang"] <= 10) / n}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=str(REPO))
    ap.add_argument("--gold", default=str(GOLD))
    ap.add_argument("--rev", help="Commit, dessen Stand gemessen wird (Standard: Arbeitsstand)")
    ap.add_argument("--detail", action="store_true", help="eine Zeile je Frage")
    ap.add_argument("--json", help="Ergebnis zusätzlich als JSON schreiben")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    gold = json.loads(Path(a.gold).read_text(encoding="utf-8"))
    fragen = gold["fragen"]
    daten = korpus(Path(a.repo), a.rev)
    db = baue_index(daten)
    fehlend = [(f["id"], q["datei"], q["abschnitt"]) for f in fragen for q in f["quellen"]
               if not any(d == q["datei"] and q["abschnitt"].lower() in p.lower() for d, p, _ in daten)]
    stempel = hashlib.sha256("\n".join(d + p + t for d, p, t in daten).encode("utf-8")).hexdigest()[:12]
    print(f"Stand: {a.rev or 'Arbeitsstand'}; Korpus: {len(set(d for d, _, _ in daten))} Dateien, {len(daten)} Abschnitte, Stempel {stempel}; SQLite {sqlite3.sqlite_version}; Goldsatz {len(fragen)} Fragen")
    for f in fehlend:
        print(f"FEHLER im Goldsatz: {f[0]}: kein Abschnitt für {f[1]} / {f[2]}")
    ergebnis = {"korpus_stempel": stempel, "abschnitte": len(daten), "fehlende_erwartungen": fehlend, "laeufe": {}}
    for modus in ("wort", "stamm"):
        zeilen = messe(daten, db, fragen, modus)
        k = kennzahlen(zeilen)
        je_art = {art: kennzahlen([z for z in zeilen if z["art"] == art]) for art in sorted({z["art"] for z in zeilen})}
        ergebnis["laeufe"][modus] = {"gesamt": k, "je_art": je_art, "fragen": zeilen}
        print(f"\n[{modus}] Treffer@5 {k['treffer_at_5']:.1%}  Treffer@1 {k['treffer_at_1']:.1%}  MRR@10 {k['mrr_at_10']:.3f}")
        for art, kk in je_art.items():
            print(f"    {art:12s} n={kk['fragen']:2d}  Treffer@5 {kk['treffer_at_5']:.1%}  MRR@10 {kk['mrr_at_10']:.3f}")
        if a.detail:
            for z in zeilen:
                print(f"    {z['id']} {z['art'][:6]:6s} Rang {z['rang'] or '-':>2}  {z['frage'][:70]}")
                if not z["rang"] or z["rang"] > 5:
                    print(f"          Top 1: {z['top1']}")
    if a.json:
        Path(a.json).write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if fehlend else 0


if __name__ == "__main__":
    sys.exit(main())
