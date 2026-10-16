"""B6-P0-09a: Normalisierung vor dem Scan (NFKC, unsichtbare Zeichen, Homoglyphen fuer den Mustervergleich).

Ergebnis:
  clean    Text fuer Scan, Bindung (R1) und Modell: NFKC, unsichtbare Zeichen entfernt (ausser legitimen
           Zero-Width-Verwendungen in Emoji-Folgen, arabischen/persischen und indischen Schriften).
  view     clean mit Latein-aehnlichen Kyrillisch-/Griechisch-Buchstaben auf Latein abgebildet, gleiche Laenge
           wie clean. Nur fuer den Mustervergleich, nie fuer Modell oder Anzeige.
  findings Fundstellen unsichtbarer Zeichen; Positionen beziehen sich auf den ORIGINALtext.
           severity 'BLOCK' (Tag-Zeichen, Bidi-Override/-Isolate): Policy sperrt.
           severity 'REVIEW' (ZWSP, Wordjoiner, Steuerzeichen u. a.): Policy verlangt Pruefung.
Still normalisiert, kein Befund: geschuetztes Leerzeichen, Soft Hyphen, BOM am Anfang, LRM/RLM/ALM,
Variation Selectors in Emoji (U+FE0E/FE0F).
Heuristik, kein Nachweis. Nur Standardbibliothek.
"""
from dataclasses import dataclass
import unicodedata

_BLOCK_RANGES = ((0xE0000, 0xE007F), (0x202A, 0x202E), (0x2066, 0x2069))
_SILENT = {0x00AD, 0x200E, 0x200F, 0x061C, 0x034F, 0xFE0E, 0xFE0F}
_REVIEW = {0x200B, 0x200C, 0x200D, 0x2060, 0x180E, 0x2061, 0x2062, 0x2063, 0x2064, 0x115F, 0x1160, 0x3164, 0xFFA0,
           0x206A, 0x206B, 0x206C, 0x206D, 0x206E, 0x206F}
_ARABIC = ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF), (0x08A0, 0x08FF))
_INDIC = ((0x0900, 0x0DFF),)

# Latein-aehnliche Zeichen (gleiche Laenge, 1:1). Nur fuer den Mustervergleich.
_HOMOGLYPHS = {
    # Kyrillisch
    'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'х': 'x', 'у': 'y', 'к': 'k', 'м': 'm', 'т': 't', 'н': 'h',
    'в': 'b', 'і': 'i', 'ј': 'j', 'ѕ': 's', 'ԁ': 'd', 'ӏ': 'l', 'һ': 'h', 'ԛ': 'q', 'ԝ': 'w',
    'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M', 'Н': 'H', 'О': 'O', 'Р': 'P', 'С': 'C', 'Т': 'T', 'Х': 'X',
    'У': 'Y', 'І': 'I', 'Ј': 'J', 'Ѕ': 'S',
    # Griechisch
    'α': 'a', 'ο': 'o', 'ν': 'v', 'ρ': 'p', 'ε': 'e', 'ι': 'i', 'κ': 'k', 'υ': 'u', 'τ': 't', 'χ': 'x', 'γ': 'y',
    'Α': 'A', 'Β': 'B', 'Ε': 'E', 'Ζ': 'Z', 'Η': 'H', 'Ι': 'I', 'Κ': 'K', 'Μ': 'M', 'Ν': 'N', 'Ο': 'O', 'Ρ': 'P',
    'Τ': 'T', 'Υ': 'Y', 'Χ': 'X',
}
_FOLD = str.maketrans(_HOMOGLYPHS)


@dataclass(frozen=True)
class HiddenFinding:
    severity: str      # 'BLOCK' | 'REVIEW'
    start: int         # Position im Originaltext
    end: int
    codepoint: int
    name: str


@dataclass(frozen=True)
class NormResult:
    clean: str
    view: str
    findings: tuple
    total_hidden: int = 0     # Gesamtzahl unsichtbarer Zeichen (findings ist auf MAX_FINDINGS je Text begrenzt)


MAX_FINDINGS = 500


def _in(cp, ranges): return any(a <= cp <= b for a, b in ranges)


def _is_emoji_like(ch):
    if not ch: return False
    cp = ord(ch)
    return unicodedata.category(ch) in ('So', 'Sk') or 0x1F000 <= cp <= 0x1FAFF or cp == 0xFE0F


def char_name(cp):
    try: return unicodedata.name(chr(cp))
    except ValueError: return 'UNASSIGNED' if cp > 0x10FFFF else 'CONTROL' if cp < 0x20 or 0x7F <= cp < 0xA0 else 'UNNAMED'


def fold_homoglyphs(text): return text.translate(_FOLD)


def _legit_joiner(cp, prev, nxt):
    """ZWJ/ZWNJ in Emoji-Folgen sowie arabischer/persischer/indischer Schrift sind kein Befund."""
    p = ord(prev) if prev else -1; n = ord(nxt) if nxt else -1
    if cp == 0x200D:
        if _is_emoji_like(prev) and _is_emoji_like(nxt): return True
        if _in(p, _INDIC) and _in(n, _INDIC): return True
        return _in(p, _ARABIC) and _in(n, _ARABIC)
    if cp == 0x200C:
        if _in(p, _ARABIC) and _in(n, _ARABIC): return True
        return _in(p, _INDIC) and _in(n, _INDIC)
    return False


def normalize(text):
    if not isinstance(text, str): raise ValueError('B6_NORMALIZE_INPUT_INVALID')
    findings, kept = [], []
    total = 0
    per = {'BLOCK': 0, 'REVIEW': 0}     # Obergrenze je Schwere, damit ein BLOCK-Befund nie verdraengt wird
    n = len(text)
    for i, ch in enumerate(text):
        cp = ord(ch)
        if _in(cp, _BLOCK_RANGES):
            total += 1
            per['BLOCK'] += 1
            if per['BLOCK'] <= MAX_FINDINGS: findings.append(HiddenFinding('BLOCK', i, i + 1, cp, char_name(cp)))
            continue
        if cp in _SILENT or (cp == 0xFEFF and i == 0):
            continue
        if cp in _REVIEW or cp == 0xFEFF or 0xE0100 <= cp <= 0xE01EF:
            if cp in (0x200C, 0x200D) and _legit_joiner(cp, text[i - 1] if i else '', text[i + 1] if i + 1 < n else ''):
                kept.append(ch); continue
            total += 1
            per['REVIEW'] += 1
            if per['REVIEW'] <= MAX_FINDINGS: findings.append(HiddenFinding('REVIEW', i, i + 1, cp, char_name(cp)))
            continue
        if unicodedata.category(ch) == 'Cc' and ch not in '\t\n\r':
            total += 1
            per['REVIEW'] += 1
            if per['REVIEW'] <= MAX_FINDINGS: findings.append(HiddenFinding('REVIEW', i, i + 1, cp, char_name(cp)))
            continue
        kept.append(ch)
    clean = unicodedata.normalize('NFKC', ''.join(kept))
    return NormResult(clean, fold_homoglyphs(clean), tuple(findings), total)


def visible_snippet(text, start, end, radius=20):
    """Ausschnitt fuer die lokale Anzeige: unsichtbare Zeichen als [U+XXXX] sichtbar gemacht. Nie ins Audit."""
    a, b = max(0, start - radius), min(len(text), end + radius)
    out = []
    for ch in text[a:b]:
        cp = ord(ch)
        hidden = _in(cp, _BLOCK_RANGES) or cp in _REVIEW or cp in _SILENT or cp == 0xFEFF or 0xE0100 <= cp <= 0xE01EF \
            or (unicodedata.category(ch) == 'Cc' and ch not in '\t\n\r')
        out.append(f'[U+{cp:04X}]' if hidden else ch)
    return ''.join(out)
