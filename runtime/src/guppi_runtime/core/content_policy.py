"""Inhaltsschutz, Teil 1: Prüfen und Bewerten (SPEC_EIN_SICHERER_WEG_v1 §2, S1).

Herkunft: `scan.py`, `policy.py` und `reasons.py` der ersten externen Lieferung (KI GateWay 0.3.0, 15.10.2026), hier in einer
Datei, unverändert in der Sache. SEDRAs Guard bewacht, *ob* etwas getan werden darf; dieser Teil bewacht, *was* dabei an ein
Modell geht – Schlüssel, Karten, Anweisungen an die KI, unsichtbare Zeichen, Personenbezug – und bewertet die Funde nach
Herkunft des Teils und Route (lokal oder Cloud). Rein deterministisch, ohne Modell. Nie der Text, immer nur Regel und Hash.

Die Herkunft eines Teils entscheidet mit:
  system    Vorlagen von SEDRA selbst              captain   was der Captain schreibt
  project   Dateien aus dem eigenen Projekt         untrusted Web, fremde Module, Werkzeugausgaben, alles ohne Angabe
"""
from dataclasses import dataclass
from hashlib import sha256
import json

from .b6core.privacy import scan_text

# ---------------------------------------------------------------- Prüfen (scan)
TRUST_LEVELS = ('system', 'captain', 'project', 'untrusted')
ROLES = ('system', 'user', 'assistant', 'tool')
CHUNK = 150_000
OVERLAP = 4_000          # länger als jedes B6-Muster (Muster sind auf <= 200 Zeichen begrenzt)


class ScanFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class Hit:
    rule_id: str
    kind: str
    start: int
    end: int


@dataclass(frozen=True)
class SegmentScan:
    index: int
    role: str
    trust: str
    sha256: str
    chars: int
    hits: tuple

    @property
    def rule_ids(self):
        return tuple(sorted({h.rule_id for h in self.hits}))


def normalize_messages(messages):
    """Prüft die Form. Fehlt `trust`, gilt der Teil als fremd (fail-closed)."""
    if not isinstance(messages, (list, tuple)) or not messages:
        raise ScanFailure('SG_INPUT_INVALID')
    out = []
    for m in messages:
        if not isinstance(m, dict):
            raise ScanFailure('SG_INPUT_INVALID')
        role, content = m.get('role'), m.get('content')
        trust = m.get('trust', 'untrusted')
        if role not in ROLES or not isinstance(content, str) or trust not in TRUST_LEVELS:
            raise ScanFailure('SG_INPUT_INVALID')
        out.append({'role': role, 'content': content, 'trust': trust})
    return out


def _chunks(text):
    if len(text) <= CHUNK:
        yield 0, text
        return
    pos = 0
    while pos < len(text):
        yield pos, text[pos:pos + CHUNK]
        if pos + CHUNK >= len(text):
            break
        pos += CHUNK - OVERLAP


def scan_content(text, label='SEDRA'):
    """Gibt Treffer mit Position im ganzen Text zurück. Leerer Text hat keine Treffer."""
    if not text.strip():
        return ()
    seen, hits = set(), []
    for offset, piece in _chunks(text):
        if not piece.strip():
            continue
        try:
            result = scan_text(label, piece)
        except Exception as exc:                       # jeder Scannerfehler ist eine Sperre, nie ein "nichts gefunden"
            raise ScanFailure('SG_SCANNER_ERROR') from exc
        if result.status != 'COMPLETE':
            raise ScanFailure('SG_SCANNER_INCOMPLETE')
        for f in result.findings:
            key = (f.rule_id, offset + f.offset_start)
            if key in seen:
                continue
            seen.add(key)
            hits.append(Hit(f.rule_id, f.kind.value, offset + f.offset_start, offset + f.offset_end))
    return tuple(sorted(hits, key=lambda h: (h.start, h.rule_id)))


def scan_messages(messages, max_chars):
    scans = []
    for i, m in enumerate(messages):
        text = m['content']
        if len(text) > max_chars:
            raise ScanFailure('SG_INPUT_TOO_LARGE')
        scans.append(SegmentScan(i, m['role'], m['trust'], sha256(text.encode('utf-8')).hexdigest(), len(text),
                                 scan_content(text)))
    return scans


# ---------------------------------------------------------------- Bewerten (policy)
POLICY_VERSION = 'sedra-gw-0.1.0-PROPOSED'
ROUTES = ('local', 'cloud')
BLOCK, REVIEW, PSEUDO, NOTE = 'BLOCK', 'REVIEW', 'PSEUDONYMIZE', 'NOTE'
_ORDER = {BLOCK: 3, REVIEW: 2, PSEUDO: 1, NOTE: 0}

KEY_FORMATS = frozenset({'SECRET_KEYBLOCK_V1', 'SECRET_PREFIX_V1'})          # echte Schlüsselformate
SOFT_SECRETS = frozenset({'SECRET_V1', 'SECRET_DE_V1', 'SECRET_FORM_V2', 'SECRET_SENTENCE_V1', 'SECRET_PIN_V1',
                          'SECRET_BEARER_V1'})
INJECTION = frozenset({'INJECTION_V1', 'INJECTION_V2', 'INJECTION_ROLE_V1', 'INJECTION_REVEAL_V1'})
TEMPLATE_INJECTION = 'INJECTION_TEMPLATE_V1'                                    # Chat-Steuerzeichen, Datenmarker
PERSONAL = frozenset({'EMAIL_V1', 'EMAIL_OBFUSCATED_V1', 'PHONE_V1', 'CUSTID_TEST_V1'})
SENSITIVE = frozenset({'IBAN_V2', 'IBAN_V2_UNVERIFIED', 'PAN_V1', 'PAN_V1_UNVERIFIED', 'CTX_P02_V1', 'CTX_P03_V1',
                       'CTX_P04_V1', 'CTX_P04_UNVERIFIED_V1', 'CTX_V01_V1', 'CTX_G01_V1', 'CTX_G01_SUSPECT_V1',
                       'CTX_G02_V1'})


# Regelgruppen: so heißen die Regeln in der Oberfläche, und so werden sie einzeln scharf geschaltet (Captain 15.10.:
# zwei Wochen beobachten, mit der Möglichkeit, einzelne Punkte scharf zu schalten). Was den Rechner verlässt (Cloud),
# die Form des Aufrufs und Prüffehler sind nie nur beobachtet.
GROUPS = {
    'schluessel':  ('Schlüssel in echtem Format', 'Private Schlüssel, API-Schlüssel und Tokens, wie sie wirklich aussehen.'),
    'karten':      ('Kartennummer mit Prüfwert', 'Kreditkartennummer zusammen mit CVV oder PIN.'),
    'versteckt':   ('Versteckte Steuerzeichen', 'Zeichen, die Text unsichtbar umdrehen oder Anweisungen verstecken.'),
    'passwoerter': ('Passwörter in fremden Inhalten', 'Etwas wie ein Passwort oder Zugangswert in Webseiten, Werkzeugausgaben, fremden Dateien.'),
    'anweisungen': ('Fremde Anweisungen an die KI', 'Webseiten oder Dateien, die versuchen, der KI Befehle zu geben.'),
    'unbekannt':   ('Unbekannte Funde', 'Etwas, das die Regeln noch nicht kennen. Unbekannt ist nicht frei.'),
    'antworten':   ('Antworten der KI prüfen', 'Hält Antworten zurück, die Schlüssel, Kartendaten oder Steuerzeichen enthalten.'),
}
ALWAYS = {'cloud': ('Was den Rechner verlässt', 'Für die Cloud wird erst lokal geprüft und pseudonymisiert. Immer aktiv.'),
          'grundschutz': ('Grundschutz', 'Kaputte Aufrufe, Prüffehler, fehlendes Logbuch. Immer aktiv.')}
CODE_GROUP = {
    'SG_KEY_FORMAT': 'schluessel', 'SG_KEY_FORMAT_PROJECT': 'schluessel',
    'SG_CARD_WITH_CVV': 'karten', 'SG_CARD_WITH_CVV_PROJECT': 'karten',
    'SG_INVISIBLE_CONTROL': 'versteckt',
    'SG_SECRET_UNTRUSTED': 'passwoerter',
    'SG_INJECTION_UNTRUSTED': 'anweisungen', 'SG_TEMPLATE_INJECTION': 'anweisungen', 'SG_INVISIBLE_UNTRUSTED': 'anweisungen',
    'SG_RULE_UNKNOWN': 'unbekannt',
    'SG_OUTPUT_KEY_FORMAT': 'antworten', 'SG_OUTPUT_CARD': 'antworten', 'SG_OUTPUT_INVISIBLE': 'antworten',
    'SG_SECRET_CLOUD': 'cloud', 'SG_PLACEHOLDER_CLOUD': 'cloud', 'SG_SENSITIVE_CLOUD': 'cloud',
    'SG_PERSONAL_CLOUD': 'cloud', 'SG_CLOUD_DISABLED': 'cloud',
}


def group_of(code):
    return CODE_GROUP.get(code, 'grundschutz')


@dataclass(frozen=True)
class Verdict:
    outcome: str                 # ALLOW | REVIEW | PSEUDONYMIZE | BLOCK
    reasons: tuple               # Grundcodes SG_*, geordnet nach Schwere
    rule_ids: tuple              # welche B6-Regeln getroffen haben (nie der Text)
    notes: tuple                 # nur protokolliert, ändert nichts
    binding: str                 # sha256 über alles, was entschieden wurde
    route: str
    levels: tuple = ()           # (Grundcode, Stufe) für jede wirkende Regel


def effective(verdict, is_enforced):
    """Teilt die wirkenden Gründe in scharf und nur beobachtet. Ergebnis: (Ergebnis, scharfe Gründe, beobachtete)."""
    sharp, watched = [], []
    for code, level in verdict.levels:
        (sharp if is_enforced(group_of(code)) else watched).append((code, level))
    top = max((lvl for _, lvl in sharp), key=_ORDER.get, default=NOTE)
    return ('ALLOW' if top == NOTE else top, tuple(c for c, _ in sharp), tuple(c for c, _ in watched))


def _rule(rule_id):
    return rule_id.split(':', 1)[0]


OWN_TRUST = ('system', 'captain', 'project')      # was der Captain selbst schreibt, die Systemvorgabe, das eigene Projekt


def judge(rule_id, trust, route):
    """Eine Regel in einem Teil -> (Stufe, Grundcode). Unbekannte Regeln sind nie frei.

    Captain 28.10.2026 („auf dem eigenen PC schreiben, geprüft wird, wenn man in der Cloud arbeitet“, Weg „Eigenes frei“): lokal wird
    Eigenes nur notiert (`…_EIGEN`), nie gesperrt oder zur Entscheidung gestellt. Fremdes (`untrusted`: Werkzeugergebnisse, Web, fremde
    Dateien) bleibt lokal geschützt; die Cloud bleibt voll geprüft."""
    level, code = _judge(rule_id, trust, route)
    if route != 'cloud' and trust in OWN_TRUST and level != NOTE:
        return NOTE, code + '_EIGEN'
    return level, code


def _judge(rule_id, trust, route):
    r = _rule(rule_id)
    cloud = route == 'cloud'
    if r == 'PAN_CVV_V1':
        # Gemessen: im eigenen Projekt stehen Karte+Prüfwert nur in Testkorpora. Lokal also Entscheidung, sonst Sperre.
        return (REVIEW, 'SG_CARD_WITH_CVV_PROJECT') if (not cloud and trust == 'project') else (BLOCK, 'SG_CARD_WITH_CVV')
    if r.startswith('INVISIBLE_BLOCK'):
        # Bidi-/Tag-Zeichen bleiben überall Sperre, auch im eigenen Projekt: versteckte Anweisungen im Repo
        # ("Trojan Source") sind genau der Angriff auf einen Entwicklungsagenten.
        return BLOCK, 'SG_INVISIBLE_CONTROL'
    if r in KEY_FORMATS:
        # Ein echtes Schlüsselformat verlässt nie den Rechner und kommt nie aus fremder Quelle ins Modell.
        # Aus dem eigenen Projekt an das lokale Modell: Entscheidung (Testschlüssel in Tests sind häufig).
        if not cloud and trust == 'project':
            return REVIEW, 'SG_KEY_FORMAT_PROJECT'
        return BLOCK, 'SG_KEY_FORMAT'
    if r in SOFT_SECRETS:
        if cloud:
            return BLOCK, 'SG_SECRET_CLOUD'
        return (REVIEW, 'SG_SECRET_UNTRUSTED') if trust == 'untrusted' else (NOTE, 'SG_SECRET_NOTE')
    if r == TEMPLATE_INJECTION:
        return (BLOCK, 'SG_TEMPLATE_INJECTION') if trust == 'untrusted' else (NOTE, 'SG_TEMPLATE_NOTE')
    if r in INJECTION:
        return (REVIEW, 'SG_INJECTION_UNTRUSTED') if trust == 'untrusted' else (NOTE, 'SG_INJECTION_NOTE')
    if r.startswith('INVISIBLE_REVIEW'):
        return (REVIEW, 'SG_INVISIBLE_UNTRUSTED') if trust == 'untrusted' else (NOTE, 'SG_INVISIBLE_NOTE')
    if r == 'PLACEHOLDER_INJECTION_V1':
        return (BLOCK, 'SG_PLACEHOLDER_CLOUD') if cloud else (NOTE, 'SG_PLACEHOLDER_NOTE')
    if r in SENSITIVE:
        return (BLOCK, 'SG_SENSITIVE_CLOUD') if cloud else (NOTE, 'SG_SENSITIVE_LOCAL')
    if r in PERSONAL or r.startswith(('PERSON_', 'ADDRESS_', 'FILTER_')):
        return (BLOCK, 'SG_PERSONAL_CLOUD') if cloud else (NOTE, 'SG_PERSONAL_LOCAL')   # Klaus: bis zu einer einheitlichen Regel auf rechtlicher Grundlage keine Cloud für Personenbezug
    return REVIEW, 'SG_RULE_UNKNOWN'


def binding_hash(scans, route, model, verdict_parts):
    payload = {'policy': POLICY_VERSION, 'route': route, 'model': model,
               'segments': [[s.index, s.role, s.trust, s.sha256] for s in scans], 'verdict': verdict_parts}
    return sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def evaluate(scans, route, model, cloud_enabled=False):
    if route not in ROUTES or not isinstance(model, str) or not model.strip():
        reasons, outcome = ('SG_INPUT_INVALID',), BLOCK
        return Verdict(outcome, reasons, (), (), binding_hash(scans, str(route), str(model), [outcome, reasons]), str(route),
                       ((reasons[0], BLOCK),))
    found = {}
    rules = set()
    for s in scans:
        if s.trust not in TRUST_LEVELS:
            found.setdefault(BLOCK, set()).add('SG_INPUT_INVALID')
        for h in s.hits:
            level, code = judge(h.rule_id, s.trust, route)
            found.setdefault(level, set()).add(code)
            rules.add(_rule(h.rule_id))
    if route == 'cloud' and not cloud_enabled:
        found.setdefault(BLOCK, set()).add('SG_CLOUD_DISABLED')
    top = max(found, key=_ORDER.get, default=NOTE)
    outcome = 'ALLOW' if top == NOTE else top
    acting = tuple(c for lvl in (BLOCK, REVIEW, PSEUDO) for c in sorted(found.get(lvl, ())))
    levels = tuple((c, lvl) for lvl in (BLOCK, REVIEW, PSEUDO) for c in sorted(found.get(lvl, ())))
    notes = tuple(sorted(found.get(NOTE, ())))
    rule_ids = tuple(sorted(rules))
    return Verdict(outcome, acting, rule_ids, notes, binding_hash(scans, route, model, [outcome, acting, rule_ids]), route, levels)


# ---------------------------------------------------------------- Gründe im Klartext (reasons)
TEXT = {
    'SG_INPUT_INVALID': 'Der Aufruf hat keine gültige Form (Rolle, Inhalt, Herkunft, Route oder Modell fehlt).',
    'SG_INPUT_TOO_LARGE': 'Ein Teil ist größer als erlaubt; gekürzt wird nicht.',
    'SG_SCANNER_ERROR': 'Die Prüfung ist fehlgeschlagen. Ohne Prüfung geht nichts an das Modell.',
    'SG_SCANNER_INCOMPLETE': 'Die Prüfung ist nicht vollständig gelaufen.',
    'SG_CARD_WITH_CVV': 'Kartennummer mit Prüfwert im Text.',
    'SG_CARD_WITH_CVV_PROJECT': 'Kartennummer mit Prüfwert in einer Projektdatei. Synthetische Testdaten? Dann einmal freigeben.',
    'SG_INVISIBLE_CONTROL': 'Steuerzeichen, die Text unsichtbar umdrehen oder verstecken (Bidi/Tag-Zeichen).',
    'SG_KEY_FORMAT': 'Ein Schlüssel in echtem Format (privater Schlüssel, API-Präfix, Token). Geht nicht an das Modell.',
    'SG_KEY_FORMAT_PROJECT': 'Ein Schlüssel in echtem Format in einer Projektdatei. Testschlüssel? Dann einmal freigeben.',
    'SG_SECRET_CLOUD': 'Ein Passwort oder Zugangswert würde den Rechner verlassen.',
    'SG_SECRET_UNTRUSTED': 'Fremder Inhalt enthält etwas wie ein Passwort oder einen Zugangswert.',
    'SG_TEMPLATE_INJECTION': 'Fremder Inhalt enthält Steuermarken des Modells (Chat-Vorlage oder Datenmarker).',
    'SG_INJECTION_UNTRUSTED': 'Fremder Inhalt versucht, dem Modell Anweisungen zu geben.',
    'SG_INVISIBLE_UNTRUSTED': 'Fremder Inhalt enthält unsichtbare Zeichen.',
    'SG_PLACEHOLDER_CLOUD': 'Der Text enthält Platzhalter der Pseudonymisierung; die Rückübersetzung wäre angreifbar.',
    'SG_SENSITIVE_CLOUD': 'Besondere Daten (Gesundheit, Bank, Kalkulation, NDA …) würden den Rechner verlassen.',
    'SG_PERSONAL_CLOUD': 'Personenbezug geht nicht in die Cloud, bis eine einheitliche Regel auf rechtlicher Grundlage vorliegt.',
    'SG_RULE_UNKNOWN': 'Ein Fund, den diese Policy noch nicht kennt. Unbekannt ist nicht frei.',
    'SG_CLOUD_DISABLED': 'Cloud ist ausgeschaltet. Es gibt keinen stillen Ausweichweg.',
    'SG_DECISION_REQUIRED': 'Wartet auf eine Entscheidung des Captains.',
    'SG_APPROVAL_INVALID': 'Die Freigabe passt nicht zu diesem Aufruf, ist verbraucht oder abgelaufen.',
    'SG_PSEUDO_FAILED': 'Die Pseudonymisierung hat die erneute Prüfung nicht bestanden.',
    'SG_MODEL_ERROR': 'Das Modell hat nicht geantwortet. Kein Ausweichen auf ein anderes Modell.',
    'SG_OUTPUT_EMPTY': 'Das Modell hat nichts geliefert.',
    'SG_OUTPUT_KEY_FORMAT': 'Die Antwort enthält einen Schlüssel in echtem Format und wird zurückgehalten.',
    'SG_OUTPUT_CARD': 'Die Antwort enthält Kartennummer mit Prüfwert und wird zurückgehalten.',
    'SG_OUTPUT_INVISIBLE': 'Die Antwort enthält versteckende Steuerzeichen und wird zurückgehalten.',
    'SG_OUTPUT_TEMPLATE': 'Die Antwort enthält Steuermarken des Modells. Vor der Weiterverwendung ansehen.',
    'SG_OUTPUT_PSEUDO': 'Die Antwort passt nicht zu den Platzhaltern (unbekannt, verformt oder Originalwert).',
    'SG_AUDIT_FAILED': 'Das Logbuch hat nicht geschrieben. Ohne Logbuch kein Aufruf.',
}


def reason_text(code):
    return TEXT.get(code, 'Unbekannter Grund: ' + str(code))
