"""Glossar der Wortsuche (Spec 7, S7.6 A2): Gruppen gleichbedeutender Begriffe (VRAM ↔ Videospeicher, Lease ↔ GPU-Sperre,
englisch ↔ deutsch). Ein Fragewort, das zu einer Gruppe gehört, nimmt die anderen Begriffe der Gruppe als ODER-Alternativen in die
FTS5-Anfrage mit; der Gütefaktor zählt ein Fragewort als abgedeckt, wenn der Abschnitt das Wort oder eine Alternative enthält.

Rein: nur `re` und `unicodedata`; keine Datei (die Gruppen liest `konfig`), keine Datenbank. Ein Begriff passt auf ein Fragewort,
wenn beide nach Kleinschreibung und ohne Akzente gleich sind oder das Fragewort mit dem Begriff (ab 5 Zeichen) beginnt und höchstens
3 Zeichen länger ist (Beugung: „Videospeichers“, „Stichwörtern“). Fehler: `ValueError('wis_glossar_ungueltig')`."""
import re
import unicodedata

GLOSSAR_VERSION = "g1"
JE_WORT = 4                                                    # höchstens so viele Alternativen je Fragewort
_ERLAUBT = re.compile(r"^[\w äöüß.\-]{2,40}$")


def norm(wort):
    """Kleinschreibung ohne Akzente (wie `remove_diacritics` des Index); ß bleibt."""
    zerlegt = unicodedata.normalize("NFKD", str(wort).strip().lower().replace("ß", "\0"))
    return "".join(c for c in zerlegt if not unicodedata.combining(c)).replace("\0", "ß")


def pruefe(gruppen):
    """Gruppen als Liste von Listen; jede mit mindestens zwei Begriffen, je 2 bis 40 Zeichen (Buchstaben, Ziffern, Leerzeichen,
    Punkt, Bindestrich). Rückgabe die Gruppen kleingeschrieben und ohne Doppelte, in fester Reihenfolge."""
    if not isinstance(gruppen, (list, tuple)):
        raise ValueError("wis_glossar_ungueltig")
    out = []
    for g in gruppen:
        if not isinstance(g, (list, tuple)) or len(g) < 2 or any(not isinstance(b, str) or not _ERLAUBT.match(b.strip()) for b in g):
            raise ValueError("wis_glossar_ungueltig")
        begriffe = list(dict.fromkeys(b.strip().lower() for b in g))
        if len(begriffe) >= 2:
            out.append(begriffe)
    return out


def _passt(wort, begriff):
    w, b = norm(wort), norm(begriff)
    return w == b or (len(b) >= 5 and w.startswith(b) and len(w) - len(b) <= 3)


def alternativen(woerter, gruppen, *, je_wort=JE_WORT):
    """{fragewort: [alternativen]} für jedes Fragewort, das zu einer Gruppe passt; das Wort selbst und Doppelte fehlen."""
    out = {}
    for w in woerter:
        alt = []
        for g in gruppen:
            if any(_passt(w, b) for b in g):
                alt += [b for b in g if not _passt(w, b) and norm(b) != norm(w) and b not in alt]
        if alt:
            out[w] = alt[:je_wort]
    return out


def anfrage_woerter(woerter, alt):
    """Die Wörter der FTS5-Anfrage: erst die Fragewörter, dann ihre Alternativen, ohne Doppelte."""
    return list(dict.fromkeys(list(woerter) + [a for w in woerter for a in alt.get(w, [])]))
