"""B6-P0-10c / K04-PSEUDO-01: lokale Pseudonymisierung ohne KI. Standardbibliothek.

Kette: Finding -> typisierter Platzhalter -> erneute Pruefung des transformierten Texts -> (simulierte) Cloudroute ->
Output-Pruefung vor Rueckuebersetzung -> lokale Rehydrierung. Alles deterministisch und fail-closed.

Grenzen (siehe KNOWN_LIMITS, nie als vollstaendig dargestellt):
- Namen werden nur in belegbaren Formen erkannt (names.py, Rollenfilter). Ein frei im Text stehender Name bleibt stehen.
- Pseudonymisierung ist keine Anonymisierung. Kontext, Rollen und Zahlen koennen weiter identifizieren.
- Gleiche Werte (ohne Gross-/Kleinschreibung) bekommen denselben Platzhalter; rehydriert wird die Schreibweise des ersten Vorkommens.

Das Mapping (Platzhalter -> Originalwert) liegt ausschliesslich im Arbeitsspeicher des Prozesses (PseudoVault), mit Ablaufzeit,
und wird weder gespeichert noch protokolliert. Nach einem Neustart ist ein Vorgang nicht mehr rehydrierbar.
"""
from dataclasses import dataclass, field
from hashlib import sha256
import re
import threading
import time
from .contracts import FindingKind
from .normalize import normalize
from .privacy import scan_text

TYPES = ('PERSON', 'EMAIL', 'PHONE', 'CUSTOMER_ID', 'COMPANY', 'TERM', 'ADDRESS', 'ORT')
KNOWN_LIMITS = ('NAMEN_AUSSERHALB_DER_REGELN', 'KEINE_ANONYMISIERUNG', 'ROLLE_ALLEIN_KANN_INDIREKT_IDENTIFIZIEREN',
                'FREITEXT_IDENTIFIKATOREN_NICHT_ERKANNT')
DEFAULT_TTL_SECONDS = 86400          # Testdefault (Klaus-Empfehlung), keine Produktpolicy
MAX_TTL_SECONDS = 7 * 86400
DEFAULT_MAX_ENTRIES = 100            # Testdefault (B6-P0-12), keine Produktpolicy
MAX_ENTRIES_LIMIT = 10000
_PRIORITY = {t: i for i, t in enumerate(('EMAIL', 'PHONE', 'CUSTOMER_ID', 'ADDRESS', 'ORT', 'PERSON', 'COMPANY', 'TERM'))}
_TYPE_ALT = '|'.join(TYPES)
STRICT_RX = re.compile(rf'<(?:{_TYPE_ALT})_\d{{3}}>')
_INPUT_RX = re.compile(rf'<(?:{_TYPE_ALT}|ROLE)_\d{{1,4}}>')
_LOOSE_RX = re.compile(rf'[<\[{{(]{{1,2}}\s*(?:{_TYPE_ALT}|ROLE)\s*[_\- ]?\s*\d+\s*[>\]}})]{{1,2}}', re.IGNORECASE)
_CUSTOMER_RX = re.compile(r'(?i)\b(?:kundennummer|kundennr\.?|kunden-nr\.?|kd\.?-?\s?nr\.?)[ \t]*[:#]?[ \t]*((?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{3,19})(?![\w-])')
# Ortsnamen (Spezifikation Gateway, Abschnitt 6b, Regeln O-1 und O-2). Ersetzt wird nur bei Anschrift oder Wohnbezug;
# ein Ortsname bei einem Ereignis oder Thema (z. B. "in DEF geknallt") bleibt stehen.
_STRASSENWORT = r'(?i:Stra(?:ß|ss)e|Str\.|Weg|Platz|Gasse|Allee|Ring|Damm)'
_STRASSE_NAME_RX = re.compile(rf'{_STRASSENWORT}[ \t]+([A-ZÄÖÜ][\wäöüß-]{{1,40}})')                  # "Straße XYZ" → Anschrift
_ORT_NACH_PLZ_RX = re.compile(r'\b\d{5}[ \t]+([A-ZÄÖÜ][\wäöüß-]{1,40})\b')                               # "12345 DEF"
_ORT_NACH_NUMMER_RX = re.compile(rf'{_STRASSENWORT}[ \t]*\d+[a-z]?[ \t]*,?[ \t]*(?:in[ \t]+)?([A-ZÄÖÜ][\wäöüß-]{{1,40}})\b')  # "Hauptstraße 1 in DEF"
_ORT_WOHNEN_RX = re.compile(r'\b(?:wohne|wohnhaft|wohnt|wohnen|lebt)[ \t]+(?:in|im)[ \t]+(?:(?:der|dem|den)[ \t]+)?([A-ZÄÖÜ][\wäöüß-]{1,40})\b')  # "ich wohne in DEF"
_KEIN_ORT_RX = re.compile(rf'(?i:{_STRASSENWORT}$)')          # Endung: "Hauptstraße" ist eine Straße, kein Ort


def _orte_spans(text):
    spans = []
    for m in _STRASSE_NAME_RX.finditer(text):
        if not _KEIN_ORT_RX.search(m.group(1)): spans.append((m.start(1), m.end(1), 'ADDRESS'))
    for rx in (_ORT_NACH_PLZ_RX, _ORT_NACH_NUMMER_RX, _ORT_WOHNEN_RX):
        for m in rx.finditer(text):
            name = m.group(1)
            if _KEIN_ORT_RX.search(name) or name in _LEAD_STOP: continue
            spans.append((m.start(1), m.end(1), 'ORT'))
    return spans


_UC = 'A-ZÄÖÜ'
_COMPANY_RX = re.compile(rf'\b((?:[{_UC}][\wäöüßÄÖÜ&.-]*[ \t]+){{1,4}}'
                         r'(?:GmbH(?:[ \t]*&[ \t]*Co\.?[ \t]*KG)?|AG|UG(?:[ \t]*\(haftungsbeschränkt\))?|KG|OHG|GbR|e\.K\.|mbH))(?![\w])')
_LEAD_STOP = frozenset('''Die Der Das Den Dem Des Ein Eine Einer Firma Von Bei Und Wir Ich Sie Herr Herrn Frau Danach Dann Auch Mit An
Für Fuer Zur Zum Im Am Aus Als Wie Wenn Dort Hier Bitte Danke Gruß Gruss'''.split())
_HARD_RULES = ('PAN_CVV_V1',)
_RECHECK_KINDS = (FindingKind.PERSON, FindingKind.EMAIL, FindingKind.PHONE, FindingKind.IDENTIFIER, FindingKind.SECRET,
                  FindingKind.PROMPT_INJECTION, FindingKind.FINANCIAL)


class PseudoError(ValueError):
    pass


@dataclass(frozen=True)
class PseudoResult:
    text: str
    mapping: dict = field(repr=False)
    counts: dict
    sha256: str
    filter_version: str = ''
    filter_sha256: str = ''
    limits: tuple = KNOWN_LIMITS
    complete: bool = False            # nie True: Vollstaendigkeit ist nicht nachweisbar

    @property
    def placeholders(self):
        return tuple(sorted(self.mapping))


def _key(value):
    return re.sub(r'\s+', ' ', value).strip().casefold()


def _typ_of(f):
    rid = f.rule_id
    if f.kind == FindingKind.EMAIL: return 'EMAIL'
    if f.kind == FindingKind.PHONE: return 'PHONE'
    if f.kind == FindingKind.IDENTIFIER: return 'CUSTOMER_ID'
    if f.kind == FindingKind.PERSON:
        if rid.startswith('FILTER_TERM_V1'): return 'TERM'
        if rid.startswith('ADDRESS_V1'): return 'ADDRESS'
        return 'PERSON'
    return None


def _company_spans(text):
    for m in _COMPANY_RX.finditer(text):
        a, b = m.start(1), m.end(1)
        words = text[a:b].split()
        cut = 0
        while cut < len(words) - 2 and words[cut] in _LEAD_STOP: cut += 1     # fuehrende Artikel/Satzanfaenge nicht mitnehmen
        idx = a
        for w in words[:cut]: idx = text.index(w, idx) + len(w)
        if cut: a = text.index(words[cut], idx)
        yield a, b


def collect_spans(text, scan):
    spans = []
    for f in scan.findings:
        t = _typ_of(f)
        if t: spans.append((f.offset_start, f.offset_end, t))
    for m in _CUSTOMER_RX.finditer(text): spans.append((m.start(1), m.end(1), 'CUSTOMER_ID'))
    spans.extend(_orte_spans(text))
    if spans:                                                     # Firmenname nur mit Personenbezug im selben Vorgang
        for a, b in _company_spans(text): spans.append((a, b, 'COMPANY'))
    spans = [s for s in spans if 0 <= s[0] < s[1] <= len(text)]
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    merged = []
    for a, b, t in spans:
        if merged and a < merged[-1][1]:
            pa, pb, pt, plen = merged[-1]
            nlen = max(plen, b - a)
            nt = pt if (plen, -_PRIORITY[pt]) >= (b - a, -_PRIORITY[t]) else t
            merged[-1] = (pa, max(pb, b), nt, nlen)
        else:
            merged.append((a, b, t, b - a))
    return [(a, b, t) for a, b, t, _ in merged]


def pseudonymize(text, scan, filters=None):
    if not isinstance(text, str) or scan is None or scan.status != 'COMPLETE': raise PseudoError('B6_PSEUDO_INPUT_INVALID')
    if sha256(text.encode('utf-8')).hexdigest() != scan.input_sha256: raise PseudoError('B6_PSEUDO_INPUT_INVALID')
    if normalize(text).clean != text: raise PseudoError('B6_PSEUDO_TEXT_NOT_NORMALIZED')
    if any(f.kind in (FindingKind.SECRET, FindingKind.PROMPT_INJECTION) or f.rule_id in _HARD_RULES or f.rule_id.startswith('INVISIBLE_BLOCK')
           for f in scan.findings):
        raise PseudoError('B6_PSEUDO_HARD_BLOCK')                  # Hard Block bleibt Hard Block: nie pseudonymisiert weitergereicht
    if _INPUT_RX.search(text): raise PseudoError('B6_PSEUDO_PLACEHOLDER_IN_INPUT')
    ids, counters, mapping, counts, out, pos = {}, {}, {}, {}, [], 0
    for a, b, t in collect_spans(text, scan):
        value = text[a:b]; k = (t, _key(value))
        if k not in ids:
            counters[t] = counters.get(t, 0) + 1
            if counters[t] > 999: raise PseudoError('B6_PSEUDO_TOO_MANY')
            ids[k] = f'<{t}_{counters[t]:03d}>'; mapping[ids[k]] = value; counts[t] = counts.get(t, 0) + 1
        out.append(text[pos:a]); out.append(ids[k]); pos = b
    out.append(text[pos:])
    result = ''.join(out)
    return PseudoResult(result, mapping, counts, sha256(result.encode('utf-8')).hexdigest(),
                        getattr(scan, 'filter_version', ''), getattr(scan, 'filter_sha256', ''))


def _value_rx(value):
    return re.compile(r'(?<![\w])' + re.escape(' '.join(value.split())).replace(r'\ ', r'\s+') + r'(?![\w])', re.IGNORECASE)


def recheck(text, mapping, filters=None):
    """Erneute Pruefung des transformierten Texts. Leeres Tuple = sauber, sonst Grundcodes (fail-closed)."""
    for value in mapping.values():
        if _value_rx(value).search(text): return ('B6_PSEUDO_RECHECK_FAILED',)
    again = scan_text('RECHECK', text, filters=filters)
    if again.status != 'COMPLETE' or any(f.kind in _RECHECK_KINDS for f in again.findings): return ('B6_PSEUDO_RECHECK_FAILED',)
    return ()


def check_output(text, mapping):
    """Pruefung der Modellantwort VOR der Rehydrierung. Wirft PseudoError mit Grundcode."""
    if not isinstance(text, str) or not text.strip(): raise PseudoError('B6_PSEUDO_OUTPUT_EMPTY')
    unknown = False
    for m in _LOOSE_RX.finditer(text):
        s = m.group()
        if not STRICT_RX.fullmatch(s): raise PseudoError('B6_PSEUDO_MALFORMED_PLACEHOLDER')
        if s not in mapping: unknown = True
    if unknown: raise PseudoError('B6_PSEUDO_UNKNOWN_PLACEHOLDER')
    for value in mapping.values():
        if _value_rx(value).search(text): raise PseudoError('B6_PSEUDO_ORIGINAL_IN_OUTPUT')


def rehydrate(text, mapping):
    """Einmaliger Durchlauf: ersetzte Werte werden nie erneut aufgeloest."""
    def one(m):
        if m.group() not in mapping: raise PseudoError('B6_PSEUDO_UNKNOWN_PLACEHOLDER')
        return mapping[m.group()]
    return STRICT_RX.sub(one, text)


@dataclass(frozen=True)
class VaultEntry:
    mapping: dict = field(repr=False)
    text: str = field(repr=False)
    sha256: str
    expires: float


class PseudoVault:
    """Mapping je Vorgang, nur im Speicher, mit Ablaufzeit. Kein Schreiben auf Datentraeger, kein Protokoll."""

    def __init__(self, ttl_seconds=DEFAULT_TTL_SECONDS, clock=time.monotonic, max_entries=DEFAULT_MAX_ENTRIES):
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)) or not 1 <= ttl_seconds <= MAX_TTL_SECONDS:
            raise ValueError('B6_PSEUDO_TTL_INVALID')
        if isinstance(max_entries, bool) or not isinstance(max_entries, int) or not 1 <= max_entries <= MAX_ENTRIES_LIMIT:
            raise ValueError('B6_PSEUDO_LIMIT_INVALID')
        self.ttl = float(ttl_seconds); self.max_entries = max_entries; self._clock = clock; self._items = {}; self._lock = threading.Lock()

    def _purge(self):
        now = self._clock()
        for k in [k for k, e in self._items.items() if e.expires <= now]: del self._items[k]

    def purge(self):
        """Physisches Loeschen abgelaufener Eintraege (B6-P0-12, F-02): bei jedem Request und per Timer."""
        with self._lock:
            self._purge()

    def put(self, case_id, mapping, text, digest):
        with self._lock:
            self._purge()
            self._items.pop(case_id, None)
            while len(self._items) >= self.max_entries:          # Limit (F-03): aeltester Eintrag weicht; der Vorgang scheitert spaeter fail-closed
                del self._items[next(iter(self._items))]
            self._items[case_id] = VaultEntry(dict(mapping), text, digest, self._clock() + self.ttl)

    def get(self, case_id):
        with self._lock:
            self._purge()
            e = self._items.get(case_id)
            if e is None: raise PseudoError('B6_PSEUDO_MAPPING_UNAVAILABLE')
            return e

    def drop(self, case_id):
        with self._lock:
            self._items.pop(case_id, None)

    def size(self):
        with self._lock:
            self._purge(); return len(self._items)
