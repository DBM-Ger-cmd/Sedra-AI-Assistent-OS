"""Hardening (26.10.2026): keine Geheimnisse im Repository. Prüft die von Git verwalteten Dateien auf echte Schlüssel und Token, verbietet Geheimnisdateien im Index und sorgt dafür,
dass `cloud_keys.json` und die Freigabe-Tokens ignoriert bleiben. Bekannte Demo- und Testwerte stehen mit Grund in ALLOWED; ein neuer Treffer ist ein Befund, kein Grund, die Liste zu erweitern."""
import re
import subprocess
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
PATTERNS = {
    "OpenAI/Anthropic-Schlüssel": re.compile(r"sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{32,}"),
    "NVIDIA-Schlüssel": re.compile(r"nvapi-[A-Za-z0-9_\-]{20,}"),
    "GitHub-Token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}"),
    "AWS-Schlüssel": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Private-Key-Block mit Inhalt": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----\s*\n[A-Za-z0-9+/=\s]{40,}"),
    "JWT": re.compile(r"eyJ[A-Za-z0-9_\-]{15,}\.[A-Za-z0-9_\-]{15,}\.[A-Za-z0-9_\-]{10,}"),
    "Zuweisung mit langem Wert": re.compile(r"(?i)(?:api[_-]?key|secret|password|passwort|token)[\"']?\s*[:=]\s*[\"']([A-Za-z0-9_\-/+=]{24,})[\"']"),
}
# Pfad -> (Muster, Grund): bekannte Demo- und Testwerte
ALLOWED = {
    "runtime/src/guppi_runtime/uix/tools/schutz/tool.js": ("Zuweisung mit langem Wert", "Beispieltext `sk-Demo…` für die Anzeige des Inhaltsschutzes"),
}
FORBIDDEN_NAMES = ("cloud_keys.json", "approval_tokens.json", "tokens.json", ".env", "id_rsa", "id_ed25519")
FORBIDDEN_SUFFIX = (".pem", ".key", ".pfx", ".p12", ".token")
SKIP_SUFFIX = {".png", ".jpg", ".gif", ".ico", ".woff", ".woff2", ".zip", ".gguf", ".pyc", ".exe", ".dll", ".whl", ".pdf", ".bundle"}


def scan(text):
    """[(Muster, Fund)] in einem Text; Demo-Werte (`Demo`, `example`, `xxxx`) zählen nicht."""
    out = []
    for label, rx in PATTERNS.items():
        for m in rx.finditer(text):
            value = m.group(0)
            if re.search(r"(?i)demo|example|beispiel|xxxx|dummy|placeholder", value):
                continue
            out.append((label, value[:24]))
    return out


def tracked():
    done = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True)
    if done.returncode != 0:
        raise unittest.SkipTest("kein Git-Repository")
    return [p for p in done.stdout.decode("utf-8", "replace").split("\0") if p]


class Secrets(unittest.TestCase):
    def test_scanner_finds_real_looking_keys_and_ignores_demo_values(self):
        self.assertTrue(scan('key = "sk-ant-' + "a1B2" * 12 + '"'))
        self.assertTrue(scan("nvapi-" + "Ab1_" * 8))
        self.assertTrue(scan("ghp_" + "A" * 36))
        self.assertTrue(scan("AKIA" + "ABCDEFGH12345678"))
        self.assertTrue(scan("-----BEGIN RSA PRIVATE KEY-----\n" + "MIIEowIBAAKCAQEA" * 5 + "\n-----END RSA PRIVATE KEY-----"))
        self.assertFalse(scan('client = Client(api_key="sk-Demo7Xq2Lm9Rt4Vb8Nc1Kp6")'))
        self.assertFalse(scan("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"), "abgeschnittener Test-Schlüssel")
        self.assertFalse(scan("password = 'kurz'"))

    def test_no_secrets_in_tracked_files(self):
        findings = []
        for rel in tracked():
            path = ROOT / rel
            if path.suffix.lower() in SKIP_SUFFIX or not path.is_file() or path.stat().st_size > 2_000_000:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for label, value in scan(text):
                if ALLOWED.get(rel, (None,))[0] == label:
                    continue
                findings.append(f"{rel}: {label} ({value}…)")
        self.assertEqual(findings, [], "echte Schlüssel oder Token in Git-Dateien")

    def test_no_secret_files_are_tracked(self):
        bad = [p for p in tracked() if Path(p).name in FORBIDDEN_NAMES or Path(p).suffix.lower() in FORBIDDEN_SUFFIX]
        self.assertEqual(bad, [], "Geheimnisdateien dürfen nicht im Git-Index stehen")

    def test_secret_paths_stay_ignored(self):
        for rel in ("workspace/GUPPI_OS/local_config/cloud_keys.json", "workspace/GUPPI_OS/runtime_data/guard/approval_tokens.json",
                    "runtime/config/local_paths.yaml", "workspace/GUPPI_OS/runtime_data/guard/tokens.json"):
            done = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", rel])
            self.assertEqual(done.returncode, 0, f"{rel} muss in .gitignore stehen")


if __name__ == "__main__":
    unittest.main()
