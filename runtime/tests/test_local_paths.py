import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from guppi_runtime import local_paths  # noqa: E402
from guppi_runtime.models.gpu_canary import CanaryConfig  # noqa: E402


class LocalPathsTests(unittest.TestCase):
    """2026-10-12: tracked files name machine folders as <placeholders>; runtime/config/local_paths.yaml (not in git) holds this PC's folders."""

    def test_expand_known_names_and_keep_unknown_ones(self):
        paths = {"modelle": r"D:\models", "projekte": "/srv/p"}
        self.assertEqual(local_paths.expand(r"<modelle>\a\b.gguf", paths), r"D:\models\a\b.gguf")
        self.assertEqual(local_paths.expand("<projekte>/x <modelle>", paths), r"/srv/p/x D:\models")
        self.assertEqual(local_paths.expand("<nix>/y", paths), "<nix>/y")
        self.assertTrue(local_paths.unresolved("<nix>/y"))
        self.assertFalse(local_paths.unresolved(r"D:\models"))
        self.assertIsNone(local_paths.expand(None, paths))

    def test_load_missing_file_is_empty_and_a_broken_one_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(local_paths.load(Path(tmp) / "none.yaml"), {})
            good = Path(tmp) / "good.yaml"; good.write_text("local_paths:\n  modelle: 'D:\\m'\n", encoding="utf-8")
            self.assertEqual(local_paths.load(good), {"modelle": "D:\\m"})
            for text in ("local_paths: [1]\n", "local_paths:\n  'Bad Name': x\n", "local_paths:\n  modelle: ''\n"):
                bad = Path(tmp) / "bad.yaml"; bad.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError, msg=text):
                    local_paths.load(bad)

    def test_a_relative_folder_counts_from_the_runtime_folder(self):
        """USB stick: K:\\SEDRA\\runtime\\config\\local_paths.yaml with `..\\modelle` finds K:\\SEDRA\\modelle, whatever the drive letter is."""
        with tempfile.TemporaryDirectory() as tmp:
            text = "local_paths:\n  modelle: '..\\modelle'\n  abs: 'D:\\m'\n"
            cfg = Path(tmp) / "local_paths.yaml"
            cfg.write_text(text, encoding="utf-8")
            loaded = local_paths.load(cfg)
            self.assertEqual(Path(loaded["modelle"]), local_paths.RUNTIME.parent / "modelle")
            self.assertEqual(loaded["abs"], "D:\\m")
            # expand setzt nur den Ordner ein; der Rest bleibt, wie er geschrieben ist – hier mit dem Trennzeichen dieses Systems
            self.assertEqual(local_paths.expand("<modelle>" + os.sep + "x.gguf", loaded), str(local_paths.RUNTIME.parent / "modelle" / "x.gguf"))

    def test_a_canary_whose_model_folder_is_not_set_up_is_off(self):
        config = CanaryConfig({"enabled": True, "gguf": "<not-set-up-here>/x.gguf"})
        self.assertEqual((config.enabled, config.disabled_reason), (False, "local_paths_missing"))
        plain = CanaryConfig({"enabled": True, "gguf": "C:/m/x.gguf"})
        self.assertEqual((plain.enabled, plain.disabled_reason), (True, None))


if __name__ == "__main__":
    unittest.main()
