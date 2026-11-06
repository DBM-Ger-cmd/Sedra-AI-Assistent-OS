"""Erstaufnahme einer Quelle des Wissens als Lauf der Harness (Lauftyp `wissen_aufnahme`, SPEC_WISSEN_KERN_v1 WK-24, G2 K5 §2.7).

    python benchmarks/wissen_aufnahme.py --project ../workspace/SEDRA_OS --quelle Q-1a2b3c4d

Abgleich in Schritten bis alle Dateien drin sind, dann Einbetten auf der CPU. Stopp jederzeit; ein neuer Lauf macht weiter.
Die Arbeit macht `sedra_runtime.wissen.aufnahme_lauf`; dieses Skript ist nur der Einstieg."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sedra_runtime.wissen.aufnahme_lauf import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
