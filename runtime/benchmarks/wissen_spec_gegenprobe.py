"""Gegenprobe Spec 7: die versteckten Stufen-Tests der Bau-Specs `wis_store`, `wis_chunk`, `wis_fuse` laufen gegen die Module des
Pakets `guppi_runtime.wissen` (schema.py, zerlegen.py, fusion.py) statt gegen die Referenz in `devvm_refs/`.

    python3 benchmarks/wissen_spec_gegenprobe.py [wis_store|wis_chunk|wis_fuse …]

Je Spec entsteht ein Arbeitsbaum wie beim Bau (`spec_check.run_stage`): die Paketdatei unter dem Namen, den die Spec erwartet,
dazu bei `wis_store` die Saat `wis_schema_seed/wis_ddl.py`. Jede Stufe muss `ok` sagen; die letzte Zeile ist `result ok` oder
`result FAIL`. Entscheidung des Captains (22.10.2026, 15:28): Claude baut die drei Module in der Cloud; die versteckten Tests
bleiben ihre Abnahme."""
import shutil
import sys
import tempfile
from pathlib import Path

BENCH = Path(__file__).resolve().parent
RUNTIME = BENCH.parent
sys.path.insert(0, str(BENCH))
import spec_check  # noqa: E402

PAKET = RUNTIME / "src" / "guppi_runtime" / "wissen"
SPECS = {
    "wis_store": [("schema.py", PAKET / "schema.py"), ("wis_ddl.py", BENCH / "wis_schema_seed" / "wis_ddl.py")],
    "wis_chunk": [("zerlegen.py", PAKET / "zerlegen.py")],
    "wis_fuse": [("fusion.py", PAKET / "fusion.py")],
}


def pruefe(name):
    spec = spec_check.load_spec(name)
    with tempfile.TemporaryDirectory(prefix="wissen-gegenprobe-") as tmp:
        tree = Path(tmp) / "tree"
        tree.mkdir()
        for ziel, quelle in SPECS[name]:
            shutil.copy(quelle, tree / ziel)
        rows = spec_check.matrix(tree, spec)
    spec_check.show(name, rows)
    return all(ok for _, ok, _ in rows)


def main(argv=None):
    namen = [a for a in (argv if argv is not None else sys.argv[1:]) if a in SPECS] or list(SPECS)
    ok = all([pruefe(n) for n in namen])
    print("result " + ("ok" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
