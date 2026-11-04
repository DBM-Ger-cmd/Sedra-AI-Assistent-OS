"""release_manifest.py: Manifest aus dem Commit (nicht aus dem Arbeitsbaum), Pruefung eines Tags wie der Updater."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

import release_manifest  # noqa: E402
from guppi_runtime.update_anwenden import MANIFEST, UpdateFehler, manifest_lesen  # noqa: E402


def _schreibe(wurzel, rel, text):
    pfad = Path(wurzel, rel)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "w", encoding="utf-8", newline="") as f:      # genau die Bytes des Textes: write_text machte unter Windows CRLF, der Commit trüge sie
        f.write(text)


@unittest.skipUnless(shutil.which("git"), "git fehlt")
class ReleaseManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git("init", "-q")
        _schreibe(self.repo, "runtime/src/guppi_runtime/kern.py", "X = 1\n")
        _schreibe(self.repo, "runtime/src/guppi_runtime/uix/tools/t/tool.yaml", "tool:\n  api: [GET /api/x]\n  trust: COMMUNITY\n")
        _schreibe(self.repo, "runtime/config/a.yaml", "a: 1\n")
        _schreibe(self.repo, "docs/x.md", "nicht im Pruefbereich\n")
        self.commit("Stand")
        # Arbeitsbaum: gehoert nicht ins Release
        _schreibe(self.repo, "runtime/config/local_paths.yaml", "modelle: D:/m\n")
        _schreibe(self.repo, "runtime/src/guppi_runtime/__pycache__/kern.cpython-311.pyc", "x")
        _schreibe(self.repo, "runtime/src/guppi_runtime/kern.py", "X = 2  # nicht committet\n")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                              check=True, capture_output=True, text=True).stdout

    def commit(self, text):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", text)

    def test_manifest_aus_dem_commit_nicht_aus_dem_arbeitsbaum(self):
        text, n = release_manifest.erzeugen(self.repo, "HEAD")
        eintraege = manifest_lesen(text)
        self.assertEqual(sorted(eintraege), ["runtime/config/a.yaml", "runtime/src/guppi_runtime/kern.py",
                                             "runtime/src/guppi_runtime/uix/tools/t/tool.yaml"])
        self.assertEqual(n, 3)
        import hashlib
        self.assertEqual(eintraege["runtime/src/guppi_runtime/kern.py"], hashlib.sha256(b"X = 1\n").hexdigest(), "Inhalt aus dem Commit")

    def test_schreiben_taggen_pruefen(self):
        self.git("checkout", "-q", "--", ".")
        self.assertEqual(release_manifest.main(["--repo", str(self.repo)]), 0)
        self.assertTrue((self.repo / MANIFEST).is_file())
        self.git("add", MANIFEST)                                 # nur das Manifest; der Arbeitsbaum bleibt aussen vor
        self.git("commit", "-q", "-m", "Release-Manifest")
        self.git("tag", "v9.9.9")
        self.assertEqual(release_manifest.pruefen(self.repo, "v9.9.9")["anzahl"], 3)
        self.assertEqual(release_manifest.main(["--repo", str(self.repo), "--pruefen", "v9.9.9"]), 0)
        # Ein spaeterer Commit macht das Manifest auf main veraltet – der Tag bleibt stimmig.
        _schreibe(self.repo, "runtime/src/guppi_runtime/kern.py", "X = 3\n")
        self.git("commit", "-q", "-am", "weiter")
        with self.assertRaisesRegex(UpdateFehler, "pruefsumme_falsch"):
            release_manifest.pruefen(self.repo, "HEAD")
        self.assertEqual(release_manifest.pruefen(self.repo, "v9.9.9")["anzahl"], 3)

    def test_tag_ohne_manifest(self):
        self.git("tag", "v1.0.0")
        with self.assertRaisesRegex(UpdateFehler, "update_manifest_fehlt"):
            release_manifest.pruefen(self.repo, "v1.0.0")
        self.assertEqual(release_manifest.main(["--repo", str(self.repo), "--pruefen", "v1.0.0"]), 2)


if __name__ == "__main__":
    unittest.main()
