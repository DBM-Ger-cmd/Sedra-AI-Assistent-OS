import env_skip; env_skip.need_dulwich()   # devvm_build braucht den DevVM-Git (dulwich); ohne ihn wird das Modul mit Grund uebersprungen
import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))
sys.path.insert(0, str(RUNTIME / "src"))

from devvm_build import acceptance  # noqa: E402

S1 = {"name": "S1", "hidden": {"h1.py": "s1"}}
S2 = {"name": "S2", "hidden": {"h2.py": "s2"}}
S3 = {"name": "S3", "hidden": {"h3.py": "s3"}}


def vm_mit(ausfaelle):
    """Fake fuer vm_copy: laeuft ein Test, dessen Quelltext in `ausfaelle` steht, scheitert er; die Aufrufe werden in `gesehen` gesammelt."""
    gesehen = []

    def vm(ws, commands, files):
        gesehen.append(sorted(files))
        code = next(iter(files.values()))
        return {"status": "failed" if code in ausfaelle else "completed", "output": f"AssertionError in {code}" if code in ausfaelle else "ok"}
    vm.gesehen = gesehen
    return vm


class FruehereStufenAufDemEndstand(unittest.TestCase):
    def test_ohne_fruehere_stufen_wie_bisher(self):
        vm = vm_mit({"s1"})
        r = acceptance(vm, None, S2)
        self.assertEqual(r["status"], "completed")
        self.assertEqual(vm.gesehen, [["h2.py"]])

    def test_bestehen_alle_laeuft_jede_stufe_einmal_in_der_reihenfolge(self):
        vm = vm_mit(set())
        r = acceptance(vm, None, S3, [S1, S2])
        self.assertEqual(r["status"], "completed")
        self.assertEqual(vm.gesehen, [["h1.py"], ["h2.py"], ["h3.py"]])

    def test_eine_fruehere_stufe_die_bricht_macht_die_abnahme_rot_und_nennt_die_stufe(self):
        vm = vm_mit({"s1"})
        r = acceptance(vm, None, S2, [S1])
        self.assertEqual(r["status"], "failed")
        self.assertIn("REGRESSION", r["output"])
        self.assertIn("earlier stage S1", r["output"])
        self.assertIn("AssertionError in s1", r["output"])

    def test_die_eigene_stufe_scheitert_ohne_regressionstext(self):
        vm = vm_mit({"s2"})
        r = acceptance(vm, None, S2, [S1])
        self.assertEqual(r["status"], "failed")
        self.assertNotIn("REGRESSION", r["output"])

    def test_beide_scheitern_beide_stehen_in_der_ausgabe(self):
        vm = vm_mit({"s1", "s2"})
        r = acceptance(vm, None, S2, [S1])
        self.assertIn("REGRESSION", r["output"])
        self.assertIn("AssertionError in s2", r["output"])

    def test_der_schalter_existiert(self):
        quelle = (RUNTIME / "benchmarks" / "devvm_build.py").read_text(encoding="utf-8")
        self.assertIn("--no-regression-check", quelle)
        self.assertIn("args.no_regression_check", quelle)


if __name__ == "__main__":
    unittest.main()
