"""Vektoren ohne numpy (Spec 7, D7.2, D7.5): normieren, als float32-Blob packen und lesen, Top-k über das Skalarprodukt.

Rein: `array`, `heapq`, `math`, `operator`, `sys`. Blobs sind `dim` Werte float32 Little Endian, L2-normiert beim Schreiben;
dann ist der Kosinus das Skalarprodukt. Auf Big-Endian-Rechnern wird beim Packen und Lesen gedreht (`byteswap`)."""
import heapq
import math
import operator
import sys
from array import array

_DREHEN = sys.byteorder == "big"


def normiere(werte):
    """Die Werte mit L2-Norm 1 als Liste; Norm 0 oder leer → `ValueError('wis_vektor_leer')`."""
    werte = [float(w) for w in werte]
    norm = math.sqrt(sum(w * w for w in werte))
    if not werte or norm == 0.0 or not math.isfinite(norm):
        raise ValueError("wis_vektor_leer")
    return [w / norm for w in werte]


def packe(werte):
    """Normierter Vektor als float32-Blob (Little Endian), 4 Bytes je Wert."""
    a = array("f", normiere(werte))
    if _DREHEN:
        a.byteswap()
    return a.tobytes()


def lese(blob, dim):
    """Blob → `array('f')` mit genau `dim` Werten; andere Länge → `ValueError('wis_vektor_dim')`."""
    if type(dim) is not int or dim < 1 or not isinstance(blob, (bytes, bytearray)) or len(blob) != 4 * dim:
        raise ValueError("wis_vektor_dim")
    a = array("f")
    a.frombytes(bytes(blob))
    if _DREHEN:
        a.byteswap()
    return a


def skalarprodukt(a, b):
    """Summe der Produkte zweier gleich langer Folgen (bei normierten Vektoren der Kosinus)."""
    if len(a) != len(b):
        raise ValueError("wis_vektor_dim")
    return float(sum(map(operator.mul, a, b)))


def top_k(anfrage, vektoren, k=50, erlaubt=None):
    """Die `k` ähnlichsten Abschnitte: `vektoren` = [(nr, array)], `erlaubt(nr)` filtert vorher; Rückgabe [(nr, kosinus)] absteigend,
    Gleichstand nach kleinerer nr (wiederholbar)."""
    if type(k) is not int or k < 1:
        raise ValueError("wis_k_ungueltig")
    paare = ((nr, skalarprodukt(anfrage, v)) for nr, v in vektoren if erlaubt is None or erlaubt(nr))
    return heapq.nlargest(k, paare, key=lambda p: (p[1], -p[0]))
