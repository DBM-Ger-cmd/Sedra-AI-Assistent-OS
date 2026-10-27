"""Die gemeinsamen Messbausteine der Laufskripte: das Parsen ohne GPU und ohne PowerShell."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))
import messlauf_basis as basis  # noqa: E402


class Parse(unittest.TestCase):
    def test_vram_line(self):
        self.assertEqual(basis.parse_vram("9930, 12288, 40\n"), {"used_mib": 9930, "total_mib": 12288, "temp_c": 40})

    def test_vram_garbage_or_empty_is_none(self):
        for text in ("", "   ", "NVIDIA-SMI has failed", "1, 2"):
            self.assertIsNone(basis.parse_vram(text), text)

    def test_free_ram_in_gb(self):
        self.assertEqual(basis.parse_free_ram_gb("10485760\r\n"), 10.0)
        self.assertEqual(basis.parse_free_ram_gb("12582912", 1), 12.0)
        self.assertIsNone(basis.parse_free_ram_gb("kaputt"))
        self.assertIsNone(basis.parse_free_ram_gb(""))

    def test_servers_with_and_without_np(self):
        text = "100|llama-server.exe -m x.gguf -np 2 --port 8089\n200|llama-server.exe --parallel 4\n300|llama-server.exe -m y\nxx|nichts\n"
        self.assertEqual(basis.parse_servers(text), [{"pid": 100, "np": "2"}, {"pid": 200, "np": "4"}, {"pid": 300, "np": "?"}])

    def test_top_processes_keep_only_well_formed_entries(self):
        self.assertEqual(basis.parse_top("llama-server:17852:11.41 VirtuelleFirma:10852:2.85 Muell"), ["llama-server:17852:11.41", "VirtuelleFirma:10852:2.85"])


if __name__ == "__main__":
    unittest.main()
