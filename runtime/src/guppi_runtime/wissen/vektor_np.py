"""Vektorsuche mit numpy, wenn es installiert ist (SPEC_WISSEN_KERN_v1 WK-23, G2 K5 §2.6, D-K5-2 Weg A).

Ohne numpy bleibt alles beim reinen Python in `vektor.py` (D7.2) – numpy ist ein Hilfswerkzeug, das der Captain installiert, keine Pflicht.
Mit numpy liegen die Vektoren als eine float32-Matrix (n × dim) im Speicher: gebaut direkt aus den Blobs (ohne eine Python-Liste je Vektor),
gesucht mit einem Matrixprodukt. Ergebnis wie `vektor.top_k`: [(nr, kosinus)] absteigend, Gleichstand nach kleinerer nr; der Filter
`erlaubt` (Rechte, Filter der Suche) gilt VOR dem Ranking, wie bisher. Float32 statt float64-Summe: Werte weichen in der 6. Stelle ab."""
from __future__ import annotations

import importlib.util
import sys

_DA = None


def verfuegbar():
    """True, wenn numpy importierbar ist (einmal geprüft)."""
    global _DA
    if _DA is None:
        _DA = importlib.util.find_spec("numpy") is not None
    return _DA


class Matrix:
    """Die Vektoren eines Modells als Matrix. `blobs`: [(nr, blob)] mit je 4·dim Bytes float32 Little Endian."""

    def __init__(self, blobs, dim):
        import numpy as np
        self.np, self.dim = np, dim
        paare = [(nr, b) for nr, b in blobs if isinstance(b, (bytes, bytearray)) and len(b) == 4 * dim]
        self.nr = np.fromiter((nr for nr, _ in paare), dtype=np.int64, count=len(paare))
        roh = b"".join(b for _, b in paare)
        m = np.frombuffer(roh, dtype="<f4").reshape(len(paare), dim) if paare else np.zeros((0, dim), dtype="<f4")
        self.m = m.astype(np.float32, copy=False) if sys.byteorder == "little" else m.astype(np.float32)

    def __len__(self):
        return int(self.nr.shape[0])

    @property
    def bytes(self):
        return int(self.m.nbytes + self.nr.nbytes)

    def top_k(self, anfrage, k=50, erlaubt=None):
        if type(k) is not int or k < 1:
            raise ValueError("wis_k_ungueltig")
        np = self.np
        if len(self) == 0:
            return []
        q = np.asarray(anfrage, dtype=np.float32)
        if q.shape != (self.dim,):
            raise ValueError("wis_vektor_dim")
        werte = self.m @ q
        if erlaubt is not None:
            maske = np.isin(self.nr, np.fromiter(erlaubt, dtype=np.int64, count=len(erlaubt)))
            werte = np.where(maske, werte, -np.inf)
            n = int(maske.sum())
        else:
            n = len(self)
        if n == 0:
            return []
        k = min(k, n)
        kandidaten = np.argpartition(-werte, k - 1)[:k] if k < len(self) else np.arange(len(self))
        paare = [(int(self.nr[i]), float(werte[i])) for i in kandidaten if np.isfinite(werte[i])]
        paare.sort(key=lambda p: (-p[1], p[0]))
        return paare[:k]
