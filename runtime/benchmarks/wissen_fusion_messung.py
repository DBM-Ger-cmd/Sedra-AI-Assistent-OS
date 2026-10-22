"""Messung S7.2-F (Spec 7, D7.5; G2-S7-c, -d): Fusion und Zerlegen auf der CPU, offline über die Listen beider Suchen.

    python3 benchmarks/wissen_fusion_messung.py --server-url http://127.0.0.1:8094 [--projekt <guppi>/workspace/GUPPI_OS]
                                                [--goldsatz benchmarks/wissen_goldsatz.json] [--zerleger z2|z1|beide] [--json Pfad] [--listen]
    python3 benchmarks/wissen_fusion_messung.py --fake          # Selbstprüfung ohne Modell (Fake-Server mit Dimension 8)

Ablauf: Korpus über die Adapter aus D7.3 (Doku, Logbuch, bei --projekt die drei Speicher) und wie in S7.1 aus den Python-Dateien
(Weg `datei`), Zerleger `z2` (Paket) und wahlweise `z1` (wissen_baseline, bis 2500 Zeichen); ein Einbett-Lauf auf der CPU über einen
laufenden `llama-server --embeddings` (der Captain startet ihn mit -ngl 0 --device none; keine Lease, D7.4). Je Frage die Top 50
beider Listen mit Rang, BM25, Kosinus und g(d); dann rechnet jede Fusionsvariante offline: w_w ∈ {0,5; 0,75; 1,0} × Gütefaktor
{aus, an} × Spitzenschutz {aus, an} = 12 Varianten, k = 60 fest. Berichtet werden Treffer@5, Treffer@1, MRR@10 gesamt, je Art und
je `erwartet_ueber`; dazu die Auswahlregel aus D7.5 (Startvariante bleibt, außer eine andere ist um mindestens 2 Fragen besser und in
keiner Art um mehr als 1 schlechter) und Leave-one-out. Der Goldsatz wird nie zum Abstimmen benutzt, nur gemessen."""
import argparse
import itertools
import json
import sys
import tempfile
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
RUNTIME = BENCH.parent
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(BENCH))

from guppi_runtime.wissen import embed, fusion, schema, vektor, zerlegen  # noqa: E402
from guppi_runtime.wissen import konfig as konfig_mod  # noqa: E402
from guppi_runtime.wissen import speicher as speicher_mod  # noqa: E402
from guppi_runtime.wissen.adapter import ERSTBESTUECKUNG  # noqa: E402
import wissen_baseline  # noqa: E402

START = {"k": 60, "w_vektor": 1.0, "w_wort": 0.75, "guete": True, "spitzenschutz": False}
RASTER = [{"k": 60, "w_vektor": 1.0, "w_wort": w, "guete": g, "spitzenschutz": s} for w in (0.5, 0.75, 1.0) for g in (False, True) for s in (False, True)]
TIEFE = 50


def name_von(g):
    return f"w_w={g['w_wort']} guete={'an' if g['guete'] else 'aus'} spitze={'an' if g['spitzenschutz'] else 'aus'}"


class LaufenderServer(embed.EmbeddingDienst):
    """Ein schon laufender Embedding-Server (vom Captain gestartet): keine Engine, kein Start, nur Anfragen."""

    def bereit(self):
        return (True, "") if self.gesund(2.0) else (False, "wis_server_start")

    def starte(self):
        if not self.gesund(2.0):
            raise ValueError("wis_server_start")
        return True

    def pruefsumme(self):
        return self.e.gguf_sha256


def speicher_bauen(tmp, repo, projekt, dienst_bauen, zerleger):
    """Ein Speicher im Temp-Projekt: Quellen wie die Erstbestückung (z2) oder die Zerlegung z1 aus wissen_baseline, plus die
    Python-Dateien von S7.1 als eigene Quelle (Weg `datei`)."""
    k = konfig_mod.load(RUNTIME / "config" / "wissen.yaml")
    k.takt_an = False
    projekt_root = Path(projekt) if projekt else Path(tmp) / "projekt"
    audit = []
    sp = speicher_mod.WissenSpeicher(k, projekt_root=projekt_root, repo_root=repo, audit=lambda e, p: audit.append((e, p)), dienst=None)
    sp.dienst = dienst_bauen(sp)
    sp.konfig.dim = sp.dienst.e.dim
    jetzt = sp.uhr()
    if zerleger == "z2":
        for q in ERSTBESTUECKUNG:
            if q["wurzel"] == "projekt" and not projekt:
                continue
            try:
                sp.quelle_freigeben(q, gate_id="messung", mission_id="messung")
            except ValueError as exc:
                print(f"  Quelle {q['pfad']} übersprungen: {exc}")
        sp.abgleich()
    with schema._immediate(sp.db):
        sp.db.execute("INSERT OR IGNORE INTO quellen (id, art, adapter, wurzel, pfad, muster, freigabe_gate, freigabe_mission, stufe, projekt, personenbezug, aktiv, erstellt) "
                      "VALUES ('Q-PY', 'ordner', 'text', 'repo', 'runtime/src', '*.py', 'messung', 'messung', 1, NULL, 0, 1, ?)", (jetzt,))
        if zerleger == "z1":
            sp.db.execute("INSERT OR IGNORE INTO quellen (id, art, adapter, wurzel, pfad, muster, freigabe_gate, freigabe_mission, stufe, projekt, personenbezug, aktiv, erstellt) "
                          "VALUES ('Q-Z1', 'ordner', 'markdown', 'repo', 'docs', '*.md', 'messung', 'messung', 1, NULL, 0, 1, ?)", (jetzt,))
    daten = wissen_baseline.korpus(repo)
    gesehen, py, z1 = {}, [], []
    for rel, pfad, text in daten:
        ziel = py if rel.endswith(".py") else z1
        if ziel is z1 and zerleger != "z1":
            continue
        teil = gesehen.get((rel, pfad), 0) + 1
        gesehen[(rel, pfad)] = teil
        ziel.append({"datei": rel, "stelle": pfad, "teil": teil, "text": text, "hash": zerlegen.abschnitt_hash(pfad, text, "z1" if ziel is z1 else zerlegen.ZERLEGER_VERSION), "datum": jetzt})
    schema.wende_an(sp.db, "Q-PY", schema.vergleiche(sp.db, "Q-PY", py), jetzt=jetzt)
    if zerleger == "z1":
        schema.wende_an(sp.db, "Q-Z1", schema.vergleiche(sp.db, "Q-Z1", z1), jetzt=jetzt)
    return sp, audit


def einbetten(sp):
    t0 = time.monotonic()
    gesamt = 0
    while True:
        out = sp.einbetten_schritt()
        gesamt += out["eingebettet"]
        if out["ende"] in ("fertig", "fehler", "pause"):
            if out["ende"] != "fertig":
                raise SystemExit(f"Einbetten endete mit {out['ende']}: {out.get('grund')}")
            break
    return gesamt, round(time.monotonic() - t0, 1)


def listen(sp, frage):
    """Die Top 50 beider Listen mit Rang, BM25, Kosinus und g(d), wie die Fassade sie rechnet (D7.5)."""
    woerter = fusion.woerter(frage)
    wort = [(r[0], r[1]) for r in sp.db.execute("SELECT a.nr, bm25(abschnitte_fts, 2.0, 1.0) FROM abschnitte_fts f JOIN abschnitte a ON a.nr = f.rowid "
                                                "WHERE abschnitte_fts MATCH ? ORDER BY bm25(abschnitte_fts, 2.0, 1.0), a.nr LIMIT ?", (fusion.fts_anfrage(woerter), TIEFE))] if woerter else []
    n_alle = sp.db.execute("SELECT count(*) FROM abschnitte").fetchone()[0]
    g = sp._guete(woerter, [nr for nr, _ in wort], n_alle)
    anfrage = sp.dienst.anfrage_vektor(frage)
    vek = vektor.top_k(anfrage, sp._vektoren_laden(sp.dienst.modell_id()), TIEFE) if anfrage is not None else []
    return {"woerter": woerter, "wort": [{"nr": nr, "bm25": b, "g": g.get(nr, 0.0)} for nr, b in wort], "vektor": [{"nr": nr, "kosinus": c} for nr, c in vek]}


def passt(zeile, quelle, ueber):
    if ueber == "adapter":
        return zeile["datei"].startswith(quelle.get("datei", "")) and quelle.get("stelle", "").lower() in zeile["stelle"].lower()
    return zeile["datei"] == quelle.get("datei") and quelle.get("abschnitt", quelle.get("stelle", "")).lower() in zeile["stelle"].lower()


def rang(reihe, zeilen, frage, ueber):
    quellen = frage.get("quellen_datei") if ueber == "datei" and "quellen_datei" in frage else frage.get("quellen") or []
    for r, nr in enumerate(reihe, 1):
        if any(passt(zeilen[nr], q, ueber) for q in quellen):
            return r
    return None


def kennzahlen(raenge):
    n = len(raenge) or 1
    return {"fragen": len(raenge), "treffer_at_5": sum(1 for r in raenge if r and r <= 5) / n, "treffer_at_1": sum(1 for r in raenge if r == 1) / n,
            "mrr_at_10": sum(1.0 / r for r in raenge if r and r <= 10) / n}


def fusionsreihe(l, gewichte):
    g = {w["nr"]: w["g"] for w in l["wort"]}
    return [t["nr"] for t in fusion.fusioniere([w["nr"] for w in l["wort"]], [v["nr"] for v in l["vektor"]], g, gewichte, k_aus=10)]


def auswahl(ergebnisse, fragen, arten):
    """D7.5: die Startvariante bleibt, außer eine andere ist um ≥ 2 Fragen besser in Treffer@5 und in keiner Art um > 1 schlechter."""
    start = ergebnisse[name_von(START)]
    beste = name_von(START)
    for name, e in ergebnisse.items():
        if e["treffer5"] - start["treffer5"] >= 2 and all(e["je_art"][a] >= start["je_art"][a] - 1 for a in arten):
            if ergebnisse[beste] is start or e["treffer5"] > ergebnisse[beste]["treffer5"]:
                beste = name
    return beste


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=str(RUNTIME.parent))
    ap.add_argument("--projekt", help="<guppi>/workspace/GUPPI_OS: dann kommen knowledge, arbeitsumfeld und gateway als Quellen dazu")
    ap.add_argument("--goldsatz", default=str(BENCH / "wissen_goldsatz.json"))
    ap.add_argument("--server-url", default="http://127.0.0.1:8094", help="laufender llama-server --embeddings (CPU)")
    ap.add_argument("--dim", type=int, default=1024)
    ap.add_argument("--modell", default="bge-m3-q8_0")
    ap.add_argument("--zerleger", choices=("z2", "z1", "beide"), default="z2")
    ap.add_argument("--json", help="Ergebnis mit Listen als JSON")
    ap.add_argument("--listen", action="store_true", help="die Top 50 beider Listen je Frage in die JSON-Datei")
    ap.add_argument("--fake", action="store_true", help="Selbstprüfung ohne Modell: Fake-Server aus tests/wissen_fixture.py")
    args = ap.parse_args(argv)
    gold = json.loads(Path(args.goldsatz).read_text(encoding="utf-8"))
    fragen = gold["fragen"] if isinstance(gold, dict) else gold
    arten = sorted({f["art"] for f in fragen})
    bericht = {"goldsatz": Path(args.goldsatz).name, "fragen": len(fragen), "raster_k": 60, "laeufe": {}}
    fake = None
    if args.fake:
        sys.path.insert(0, str(RUNTIME / "tests"))
        import wissen_fixture
        fake = wissen_fixture.FakeEmbedServer().__enter__()
        args.server_url, args.dim, args.modell = f"http://127.0.0.1:{fake.port}", wissen_fixture.DIM, "fake-embed"
    port = int(args.server_url.rsplit(":", 1)[1].strip("/"))

    def dienst_bauen(sp):
        e = embed.EmbedEinstellung(engine=None, gguf=None, gguf_sha256="messung", name=args.modell, port=port, dim=args.dim, anfrage_timeout_s=60.0, stapel=16, schritt_s=3600.0)
        return LaufenderServer(e, gpu=embed.OhneGpuZugang(), audit=sp.audit, pid_datei=Path(sp.pfad).parent / "embed_messung.pid")

    try:
        for zer in (["z2", "z1"] if args.zerleger == "beide" else [args.zerleger]):
            with tempfile.TemporaryDirectory(prefix="wissen-messung-") as tmp:
                print(f"== Zerleger {zer}")
                sp, _ = speicher_bauen(tmp, Path(args.repo), args.projekt, dienst_bauen, zer)
                n = sp.db.execute("SELECT count(*) FROM abschnitte").fetchone()[0]
                eingebettet, dauer = einbetten(sp)
                print(f"  {n} Abschnitte, {eingebettet} eingebettet in {dauer} s (CPU)")
                zeilen = {r["nr"]: {"datei": r["datei"], "stelle": r["stelle"], "id": r["id"]} for r in sp.db.execute("SELECT nr, datei, stelle, id FROM abschnitte")}
                je_frage = {f["id"]: listen(sp, f["frage"]) for f in fragen}
                lauf = {"abschnitte": n, "eingebettet": eingebettet, "dauer_s": dauer, "varianten": {}, "einzeln": {}}
                for weg in ("adapter", "datei"):
                    gruppe = [f for f in fragen if f.get("erwartet_ueber", "datei") == weg or weg == "datei" and "quellen_datei" in f]
                    if not gruppe:
                        continue
                    for name, reihen in (("nur_wort", {f["id"]: [w["nr"] for w in je_frage[f["id"]]["wort"]] for f in gruppe}),
                                         ("nur_vektor", {f["id"]: [v["nr"] for v in je_frage[f["id"]]["vektor"]] for f in gruppe})):
                        lauf["einzeln"][f"{weg}/{name}"] = kennzahlen([rang(reihen[f["id"]], zeilen, f, weg) for f in gruppe])
                    ergebnisse = {}
                    for g in RASTER:
                        raenge = {f["id"]: rang(fusionsreihe(je_frage[f["id"]], g), zeilen, f, weg) for f in gruppe}
                        e = kennzahlen(list(raenge.values()))
                        e["treffer5"] = sum(1 for r in raenge.values() if r and r <= 5)
                        e["je_art"] = {a: sum(1 for f in gruppe if f["art"] == a and raenge[f["id"]] and raenge[f["id"]] <= 5) for a in arten}
                        e["raenge"] = raenge
                        ergebnisse[name_von(g)] = e
                    gewaehlt = auswahl(ergebnisse, gruppe, arten)
                    loo = 0
                    for f in gruppe:                                   # Leave-one-out: Auswahl auf n−1, Prüfung auf der einen
                        rest = [x for x in gruppe if x is not f]
                        teil = {k: dict(v, treffer5=sum(1 for x in rest if v["raenge"][x["id"]] and v["raenge"][x["id"]] <= 5),
                                        je_art={a: sum(1 for x in rest if x["art"] == a and v["raenge"][x["id"]] and v["raenge"][x["id"]] <= 5) for a in arten}) for k, v in ergebnisse.items()}
                        r = ergebnisse[auswahl(teil, rest, arten)]["raenge"][f["id"]]
                        loo += 1 if r and r <= 5 else 0
                    lauf["varianten"][weg] = {"gewaehlt": gewaehlt, "leave_one_out_treffer5": loo / len(gruppe), "tabelle": {k: {x: v[x] for x in ("treffer_at_5", "treffer_at_1", "mrr_at_10", "je_art")} for k, v in ergebnisse.items()}}
                    print(f"  Weg {weg} ({len(gruppe)} Fragen): Wort {lauf['einzeln'][weg + '/nur_wort']['treffer_at_5']:.3f} · Vektor {lauf['einzeln'][weg + '/nur_vektor']['treffer_at_5']:.3f} Treffer@5")
                    for k, v in ergebnisse.items():
                        print(f"    {k:<36} Treffer@5 {v['treffer_at_5']:.3f}  @1 {v['treffer_at_1']:.3f}  MRR@10 {v['mrr_at_10']:.3f}  je Art {v['je_art']}")
                    print(f"    gewählt: {gewaehlt} · Leave-one-out Treffer@5 {loo / len(gruppe):.3f}")
                if args.listen:
                    lauf["listen"] = {fid: {"woerter": l["woerter"], "wort": [dict(w, **zeilen[w["nr"]]) for w in l["wort"]], "vektor": [dict(v, **zeilen[v["nr"]]) for v in l["vektor"]]} for fid, l in je_frage.items()}
                bericht["laeufe"][zer] = lauf
                sp.schliessen()
    finally:
        if fake is not None:
            fake.__exit__(None, None, None)
    if args.json:
        Path(args.json).write_text(json.dumps(bericht, ensure_ascii=False, indent=1), encoding="utf-8")
        print("geschrieben:", args.json)
    print("result ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
