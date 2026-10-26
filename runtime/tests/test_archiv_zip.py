"""archiv_zip.py (Umzug nach A1, U2-12): Zip und Manifest erzeugen, verifizieren, Manipulationen finden, nie überschreiben, nie löschen.
Nur mit einem kleinen temporären Baum; die echte Installation wird nicht berührt."""
import csv
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
import archiv_zip as az  # noqa: E402


def tree(root):
    files = {"a.txt": "alpha", "sub/b.bin": "x" * 3000, "sub/deep/\u00fcmlaut.txt": "Gr\u00fc\u00dfe", "leer.txt": ""}
    for rel, text in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return files


class Lease(unittest.TestCase):
    """Die Lease-Prüfung liest nur: die Datenbank der Installation bleibt Byte für Byte gleich und es entsteht keine Datei (kein Schema-2-Umbau, keine Sicherung)."""

    def make(self, root, heartbeat_age=None, ttl=300):
        import sqlite3
        d = Path(root) / "workspace" / "GUPPI_OS" / "runtime_data" / "testlab"
        d.mkdir(parents=True)
        db = d / "testlab.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE lease (name TEXT PRIMARY KEY, owner TEXT, purpose TEXT, heartbeat REAL, ttl_s REAL, pid INTEGER)")
        if heartbeat_age is not None:
            import time
            conn.execute("INSERT INTO lease VALUES ('gpu', 'wer', 'wozu', ?, ?, 1)", (time.time() - heartbeat_age, ttl))
        conn.commit()
        conn.close()
        return db

    def test_free_busy_and_stale_without_touching_the_file(self):
        with tempfile.TemporaryDirectory(prefix="archiv-lease-") as tmp:
            cases = {"frei": (None, []), "belegt": (10, ["belegt"]), "verwaist": (10_000, [])}
            for name, (age, expect) in cases.items():
                root = Path(tmp) / name
                db = self.make(root, age)
                before = (db.read_bytes(), sorted(p.name for p in db.parent.iterdir()))
                got = az.lease_problems(root)
                self.assertEqual(bool(got), bool(expect), name)
                self.assertEqual((db.read_bytes(), sorted(p.name for p in db.parent.iterdir())), before, name + ": nichts verändert")

    def test_no_database_means_no_problem(self):
        with tempfile.TemporaryDirectory(prefix="archiv-lease-") as tmp:
            self.assertEqual(az.lease_problems(tmp), [])


class Archiv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="archiv-zip-")
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name) / "quelle"
        self.dst = Path(self.tmp.name) / "ziel"
        self.src.mkdir()
        self.files = tree(self.src)

    def run_go(self, *extra):
        return az.main(["--source", str(self.src), "--target-dir", str(self.dst), "--name", "T.Archiv", "--no-checks", *extra])

    def test_dry_run_creates_nothing(self):
        self.dst.mkdir()
        self.assertEqual(az.main(["--source", str(self.src), "--target-dir", str(self.dst), "--name", "T.Archiv", "--no-checks"]), 0)
        self.assertEqual(list(self.dst.iterdir()), [])

    def test_go_writes_zip_manifest_and_result_and_deletes_nothing(self):
        self.assertEqual(self.run_go("--go"), 0)
        z = self.dst / "T.Archiv.zip"
        with zipfile.ZipFile(z) as zf:
            self.assertEqual(sorted(zf.namelist()), sorted(self.files))
            for rel, text in self.files.items():
                self.assertEqual(zf.read(rel).decode("utf-8"), text)
        rows = list(csv.reader(open(self.dst / "T.Archiv.manifest.csv", encoding="utf-8", newline="")))
        self.assertEqual(rows[0], ["path", "size", "sha256"])
        self.assertEqual(len(rows) - 1, len(self.files))
        result = json.loads((self.dst / "T.Archiv.ergebnis.json").read_text(encoding="utf-8"))
        self.assertEqual((result["zip_vs_manifest_problems"], result["source_vs_manifest_problems"], result["files"]), (0, 0, len(self.files)))
        self.assertEqual(sorted(p.relative_to(self.src).as_posix() for p in self.src.rglob("*") if p.is_file()), sorted(self.files), "die Quelle bleibt vollständig")
        self.assertFalse(list(self.dst.glob("*.part")))

    def test_an_existing_target_is_never_overwritten(self):
        self.assertEqual(self.run_go("--go"), 0)
        before = (self.dst / "T.Archiv.zip").read_bytes()
        self.assertEqual(self.run_go("--go"), 2)
        self.assertEqual((self.dst / "T.Archiv.zip").read_bytes(), before)

    def test_verify_finds_a_changed_source_and_a_damaged_zip(self):
        self.assertEqual(self.run_go("--go"), 0)
        args = ["--source", str(self.src), "--target-dir", str(self.dst), "--name", "T.Archiv", "--verify"]
        self.assertEqual(az.main(args), 0)
        (self.src / "a.txt").write_text("veraendert", encoding="utf-8")
        (self.src / "neu.txt").write_text("neu", encoding="utf-8")
        self.assertEqual(az.main(args), 3)
        (self.src / "a.txt").write_text("alpha", encoding="utf-8")
        (self.src / "neu.txt").unlink()
        self.assertEqual(az.main(args), 0)
        z = self.dst / "T.Archiv.zip"
        with zipfile.ZipFile(z) as zf:                 # gezielt die Nutzdaten eines Mitglieds zerstören
            info = zf.getinfo("sub/b.bin")
            offset = info.header_offset + 30 + len(info.filename.encode("utf-8")) + 0
        data = bytearray(z.read_bytes())
        with zipfile.ZipFile(z) as zf:
            local_extra = int.from_bytes(data[info.header_offset + 28:info.header_offset + 30], "little")
        offset += local_extra
        data[offset] ^= 0xFF
        z.write_bytes(bytes(data))
        self.assertEqual(az.main(args), 3, "ein beschädigtes Zip fällt auf")

    def test_exclude_leaves_the_path_out_of_zip_and_manifest(self):
        self.assertEqual(self.run_go("--go", "--exclude", "sub/deep"), 0)
        with zipfile.ZipFile(self.dst / "T.Archiv.zip") as zf:
            self.assertNotIn("sub/deep/\u00fcmlaut.txt", zf.namelist())
            self.assertIn("sub/b.bin", zf.namelist())

    def test_verify_works_when_the_source_folder_is_gone(self):
        self.assertEqual(self.run_go("--go"), 0)
        import shutil
        shutil.rmtree(self.src)
        self.assertEqual(az.main(["--source", str(self.src), "--target-dir", str(self.dst), "--name", "T.Archiv", "--verify"]), 0)


if __name__ == "__main__":
    unittest.main()
