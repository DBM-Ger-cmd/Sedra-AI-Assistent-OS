"""Conservative, deterministic rule scanner. NOT comprehensive DLP.

B6-P0-09a: Die Muster laufen auf dem normalisierten Text (NFKC, unsichtbare Zeichen entfernt, Latein-aehnliche
Buchstaben abgebildet, siehe normalize.py). Findings tragen Positionen im normalisierten Text.
Unsichtbare Zeichen werden als eigene Findings (INVISIBLE_CHARS) gefuehrt. Alle Muster sind auf lineare
Laufzeit ausgelegt (begrenzte Quantoren, keine verschachtelten offenen Wiederholungen).
"""
from dataclasses import dataclass
from hashlib import sha256
import re
import uuid
from .contracts import PrivacyFinding, FindingKind
from .normalize import normalize
from .names import find_persons


def _ws(expr):
    """Leerzeichen im Muster -> \\s+ (Zeilenumbruch, Tab, mehrfache Leerzeichen)."""
    return expr.replace(' ', r'\s+')

_VAL = r'(?=[^\s"\'`,;]{0,63}[\d!@#$%^&*+=/\\~|?<>_-])[^\s"\'`,;]{6,64}'
_VAL4 = _VAL.replace('{6,64}', '{4,64}')
_KEYWORDS = (r'(?:passwort|password|passwd|kennwort|pwd|secret|geheimnis|zugangscode|client[_ -]?secret|'
             r'api[_ -]?(?:key|schl[uü]ssel)|access[_ -]?token|zugriffs?token|token)')

PATTERNS = (
 # EMAIL: Lookbehind schliesst '%' aus, damit nur der Beginn eines Zeichenlaufs ein Startpunkt ist (DR-03, linear).
 (FindingKind.EMAIL, 'EMAIL_V1', r'(?<![\w.%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w-])', .99),
 # B6-P0-10b (T-023): verschleierte Schreibweise mit [at]/(at)/{at} und [dot]/(dot); ausgeschriebene Woerter werden nicht erkannt.
 (FindingKind.EMAIL, 'EMAIL_OBFUSCATED_V1', r'(?i)(?<![\w.%+-])[a-z0-9._%+-]+[ \t]*[\[({][ \t]*at[ \t]*[\])}][ \t]*[a-z0-9-]+(?:\.[a-z0-9-]+|[ \t]*[\[({][ \t]*dot[ \t]*[\])}][ \t]*[a-z0-9-]+)+(?![\w-])', .9),
 (FindingKind.PHONE, 'PHONE_V1', r'(?<!\w)(?:\+49|0049|0)[ -]?(?:\(?\d{2,5}\)?[ /-]?){1,3}\d{3,9}(?!\w)', .72),
 (FindingKind.SECRET, 'SECRET_V1', r'(?i)\b(?:api[_ -]?key|password|passwort|secret|token)\s*[:=]\s*[\"\']?[A-Za-z0-9_./+=-]{6,}', .9),
 # B6-P0-05: deutsche Schluesselwoerter, optional mit Klammerzusatz, z. B. 'API-Schlüssel (Schnittstelle): ...'
 (FindingKind.SECRET, 'SECRET_DE_V1', r'(?i)\b(?:kennwort|passwort|zugangscode|zugangsdaten|api[_ -]?(?:schlüssel|schluessel)|zugriffs?token|geheimschlüssel)\s{0,20}(?:\([^)\n]{0,40}\))?\s{0,20}[:=]\s*[\"\']?[A-Za-z0-9_./+=-]{6,}', .9),
 # B6-P0-09a / DR-02: Markdown-/Sonderzeichenform, Satzform, PIN, Bearer, Schluesselbloecke, bekannte Praefixe.
 (FindingKind.SECRET, 'SECRET_FORM_V2', r'(?i)\b' + _KEYWORDS + r'\b[\s*_`"\')\]]{0,8}(?:\([^)\n]{0,40}\)[\s*_`"\']{0,8})?[:=][\s*_`"\']{0,8}' + _VAL, .85),
 (FindingKind.SECRET, 'SECRET_SENTENCE_V1', r'(?i)\b(?:passwort|password|kennwort|zugangscode)\s+(?:lautet|ist|is)\s*[:=]?\s*["\'`]?' + _VAL4, .8),
 (FindingKind.SECRET, 'SECRET_PIN_V1', r'(?i)\b(?:pin|pin[- ]?code|geheimzahl)\b\s*(?:lautet|ist|is|[:=])\s*["\'`*]{0,3}\d{4,8}(?!\d)', .85),
 (FindingKind.SECRET, 'SECRET_BEARER_V1', r'(?i)\b(?:bearer\s+[A-Za-z0-9._~+/=-]{16,}|authorization\s*:\s*(?:basic|bearer)\s+[A-Za-z0-9._~+/=-]{8,})', .85),
 (FindingKind.SECRET, 'SECRET_KEYBLOCK_V1', r'-----BEGIN(?: [A-Z0-9]+){0,3} PRIVATE KEY(?: BLOCK)?-----', .95),
 (FindingKind.SECRET, 'SECRET_PREFIX_V1', r'\b(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,})', .9),
 (FindingKind.PROMPT_INJECTION, 'INJECTION_V1', '(?i)(?:' + _ws('ignore (?:all )?(?:the )?(?:previous|prior|above) instructions') + '|' + _ws('ignoriere (?:alle )?(?:vorherigen|bisherigen) anweisungen') + '|' + _ws('system ?prompt ?(?:überschreiben|override)').replace(' ?', r'\s*') + r'|developer\s*message)', .85),
 # B6-P0-06 / SB-04: weitere deutsche und englische Umgehungsformulierungen (heuristisch)
 (FindingKind.PROMPT_INJECTION, 'INJECTION_V2', r'(?i)(?:\b(?:ignoriere|missachte|vergiss|umgehe|deaktiviere)\s+(?:bitte\s+)?(?:alle\s+|sämtliche\s+|die\s+)?(?:vorherigen\s+|bisherigen\s+|obigen\s+|geltenden\s+)?(?:sicherheits)?(?:regeln|prüfungen|anweisungen|vorgaben|richtlinien|sicherheitsregeln|filter)\b|\bhinweis\s+an\s+(?:den\s+|die\s+)?ki(?:-assistent(?:en)?|-modell)?\b|\bignore\s+(?:all\s+|any\s+)?(?:previous\s+|prior\s+|above\s+)?(?:safety\s+|security\s+)?(?:rules|checks|guidelines|instructions)\b|\bohne\s+(?:jede\s+|weitere\s+)?prüfung\s+(?:direkt\s+)?(?:an|senden|versenden|ausgeben)\b)', .8),
 (FindingKind.PROMPT_INJECTION, 'INJECTION_ROLE_V1', r'(?i)\b(?:you\s+are\s+now|du\s+bist\s+jetzt|ab\s+jetzt\s+bist\s+du|from\s+now\s+on\s+you\s+are|sie\s+sind\s+jetzt)\b[^\n]{0,40}?\b(?:assistant|assistent|ki|ai|bot|modell|model|system|admin|administrator|developer|entwickler|dan|jailbreak|unrestricted|uneingeschränkt|uneingeschraenkt|ohne\s+(?:regeln|einschränkungen|einschraenkungen|filter))\b', .8),
 (FindingKind.PROMPT_INJECTION, 'INJECTION_REVEAL_V1', r'(?i)\b(?:zeige|zeig|nenne|gib|offenbare|verrate|wiederhole|reveal|show|print|output|repeat|leak|tell)\b[^\n]{0,30}?\b(?:system\s*-?\s*prompt|systemnachricht|system\s+message|(?:deine|dein|your|vorherigen|previous|initial\w*)\s+(?:anweisungen|instructions|regeln|rules|prompt))\b', .8),
 (FindingKind.PROMPT_INJECTION, 'INJECTION_TEMPLATE_V1', r'(?i)(?:<\|(?:im_start|im_end|system|user|assistant|endoftext)\|>|\[/?inst\]|<<\s*/?sys\s*>>|(?<!=)={3,}\s*(?:beginn|ende)\s+daten\s*={3,}|#{3}\s*(?:system|instruction|anweisung)\b)', .85),
 # NF-01 / DAV-10: synthetisches Kundennummernformat des Korpus; kein allgemeines Kundennummern-DLP.
 (FindingKind.IDENTIFIER, 'CUSTID_TEST_V1', r'(?<![A-Za-z0-9])K-TEST-\d{3,8}(?!\d)', .9),
)

# B6-P0-10a / K-04: Schutzmerkmale aus Schluesselwortkontext. Ein Schluesselwort allein ist nie ein Secret (S01/S02 bleiben
# an Wert-/Formmuster gebunden). Treffer sind "CONFIRMED" nur, wo das Muster eindeutig ist; sonst SUSPECTED (siehe classify.py).
_CTX = FindingKind.CONTEXT_ATTRIBUTE
CONTEXT_PATTERNS = (
 (_CTX, 'CTX_P02_V1', r'(?i)\b(?:diagnose\w*|befund\w*|krankheit\w*|erkrankung\w*|allergie\w*|medizinisch\w*|arbeitsunfähig\w*|arbeitsunfaehig\w*|schwerbehinder\w*|religion\w*|konfession\w*|gewerkschaft\w*|politische[nr]?\s+(?:meinung|partei)\w*|sexuelle[nr]?\s+orientierung|ethnische[nr]?\s+herkunft|biometrisch\w*|genetisch\w*)', .85),
 (_CTX, 'CTX_P03_V1', r'(?i)\b(?:strafrechtlich\w*|verurteilung\w*|verurteilt\w*|vorstrafe\w*|straftat\w*|ermittlungsverfahren|strafverfahren)\b', .85),
 (_CTX, 'CTX_P04_V1', r'(?i)\b(?:steuer-?id\w*|steueridentifikationsnummer|sozialversicherungsnummer|rentenversicherungsnummer|personalausweisnummer|ausweisnummer|reisepassnummer)\b[^\n\d]{0,40}\d{11}(?!\d)', .9),
 (_CTX, 'CTX_P04_UNVERIFIED_V1', r'(?i)\b(?:steuer-?id\w*|steueridentifikationsnummer|sozialversicherungsnummer|rentenversicherungsnummer|personalausweisnummer|ausweisnummer|reisepassnummer)\b', .6),
 (_CTX, 'CTX_V01_V1', r'(?i)\b(?:minderjährig\w*|minderjaehrig\w*|jugendlich\w*|jugendarbeit\w*)', .85),
 # B6-P0-10c: Platzhalterformat im Eingangstext = moegliche Manipulation der Rueckuebersetzung -> Pruefung (U02)
 (_CTX, 'PLACEHOLDER_INJECTION_V1', r'<(?:PERSON|EMAIL|PHONE|CUSTOMER_ID|COMPANY|ROLE|TERM|ADDRESS)_\d{1,4}>', .9),
 (_CTX, 'CTX_G02_V1', r'(?:\bNDA\b|(?i:\b(?:geheimhaltungsvereinbarung|vertraulichkeitsvereinbarung|nichtoffenlegungsvereinbarung)\w*))', .85),
)

# G01 (Geschaeftsgeheimnis): mindestens zwei verschiedene Kalkulationsbegriffe UND mindestens eine Betragsangabe.
# Eine blosse Frage nach Einkaufspreis/Marge ohne Zahlen ist kein vorliegendes Geschaeftsgeheimnis (TC-011).
_G01_WORDS = re.compile(r'(?i)\b(stückkosten|stueckkosten|einkaufspreis\w*|selbstkosten|marge\w*|margenplanung|kalkulation\w*|deckungsbeitrag\w*|rohertrag\w*|rabattstaffel\w*|verkaufspreis\w*|wettbewerbsrelevant\w*)')
# G01-Verdacht (SUSPECTED): mindestens zwei Hinweise auf nicht offengelegte interne Planung/Strategie, auch ohne Betrag.
_G01_SUSPECT = re.compile(r'(?i)\b(wettbewerb\w*|strategi\w*|planung\w*|codename|interne\s+annahmen|nicht\s+freigegeben|keine\s+externe\s+weitergabe|nicht\s+veröffentlicht\w*)')
_AMOUNT = re.compile(r'(?i)\d[\d.,]*\s?(?:EUR\b|€|Euro\b|%|Prozent\b)')

_IBAN_LEN = {'DE': 22, 'AT': 20, 'CH': 21, 'FR': 27, 'IT': 27, 'ES': 24, 'NL': 18, 'BE': 16, 'LU': 20, 'DK': 18, 'SE': 24,
             'NO': 15, 'FI': 18, 'PL': 28, 'CZ': 24, 'GB': 22, 'IE': 22, 'PT': 25}
_IBAN = re.compile(r'(?<![A-Za-z0-9])(' + '|'.join(_IBAN_LEN) + r')(\d{2})((?:[ ]?[A-Z0-9]){11,30})')
_CARD_WORDS = re.compile(r'(?i)(?:kartennummer|kreditkarte|karteninhaber\w*|\bkarte\b|\bpan\b|visa|mastercard|amex|\bcard\b|ec-karte|girocard)')


def iban_mod97(compact):
    rearranged = compact[4:] + compact[:4]
    return int(''.join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def _iban_findings(view, case_id):
    out = []
    for m in _IBAN.finditer(view):
        end, count, needed = m.start(3), 0, _IBAN_LEN[m.group(1)] - 4
        for i, ch in enumerate(m.group(3)):
            if ch == ' ': continue
            count += 1
            if count == needed:
                end = m.start(3) + i + 1; break
        else:
            end = m.end()
        if end < len(view) and view[end].isalnum():
            continue        # laeuft in ein weiteres Wort hinein: keine IBAN-Grenze
        compact = view[m.start():end].replace(' ', '')
        ok = len(compact) == _IBAN_LEN[m.group(1)] and iban_mod97(compact)
        out.append((m.start(), end, 'IBAN_V2' if ok else 'IBAN_V2_UNVERIFIED', .99 if ok else .6))
    return out


def _overlaps(a, b, spans):
    return any(a < y and x < b for x, y in spans)

# K1 (DAV-11): Kartennummer (Luhn) zusammen mit Kartenpruefwert/PIN im selben Text -> harte Sperre.
_PAN = re.compile(r'(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)')
_CVV = re.compile(r'(?i)\b(?:cvv2?|cvc2?|cid|sicherheitscode|kartenprüfnummer|kartenpruefnummer|prüfwert|pruefwert|prüfziffer|pin)\b[\s:=*(]{0,6}\d{3,8}(?!\d)')


def luhn_valid(digits):
    total, alt = 0, False
    for ch in reversed(digits):
        n = ord(ch) - 48
        if alt:
            n *= 2
            if n > 9: n -= 9
        total += n; alt = not alt
    return total % 10 == 0


def _pan_cvv(view):
    pans = [m for m in _PAN.finditer(view) if 13 <= sum(c.isdigit() for c in m.group()) <= 19
            and luhn_valid(''.join(c for c in m.group() if c.isdigit()))]
    if not pans: return []
    cvvs = list(_CVV.finditer(view))
    return [(m.start(), m.end()) for m in pans + cvvs] if cvvs else []

@dataclass(frozen=True)
class ScanResult:
    case_id: str
    input_sha256: str
    findings: tuple[PrivacyFinding, ...]
    status: str = 'COMPLETE'
    scanner_version: str = 'rules-0.4.0'
    filter_version: str = ''       # B6-P0-10c: Version/SHA-256 der angewendeten Filterliste (leer = keine Filterliste)
    filter_sha256: str = ''


def scan_text(case_id: str, content: str, hidden=(), filters=None) -> ScanResult:
    """hidden: optionale Fundstellen unsichtbarer Zeichen aus vorgelagerter Normalisierung einzelner Teile
    (Eingabe, Anhaenge, Quellentexte) als (HiddenFinding, label). Der Scanner normalisiert `content` zusaetzlich selbst."""
    if not isinstance(content, str) or not content.strip():
        raise ValueError('B6_SCAN_INPUT_INVALID')
    if len(content) > 200000:
        raise ValueError('B6_SCAN_INPUT_TOO_LARGE')
    norm = normalize(content)
    view = norm.view
    found = []
    for kind, rule, expression, confidence in PATTERNS + CONTEXT_PATTERNS:
        for match in re.finditer(expression, view):
            found.append(PrivacyFinding(str(uuid.uuid4()),case_id,kind,match.start(),match.end(),confidence,rule))
    # G01: Kalkulationsbegriffe (>= 2 verschiedene) zusammen mit Betragsangabe
    g01 = list(_G01_WORDS.finditer(view))
    if len({m.group(1).lower() for m in g01}) >= 2 and _AMOUNT.search(view):
        found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.CONTEXT_ATTRIBUTE,g01[0].start(),g01[0].end(),.8,'CTX_G01_V1'))
    g01s = list(_G01_SUSPECT.finditer(view))
    if len({re.sub(r'\s+', ' ', m.group(1).lower())[:9] for m in g01s}) >= 2:
        found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.CONTEXT_ATTRIBUTE,g01s[0].start(),g01s[0].end(),.55,'CTX_G01_SUSPECT_V1'))
    # Bank-/Kartendaten (F01/F02/F03). Telefon- und Kartentreffer innerhalb einer IBAN werden verworfen (DR-07).
    financial = []
    for a, b, rule, conf in _iban_findings(view, case_id):
        found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.FINANCIAL,a,b,conf,rule)); financial.append((a, b))
    pan_cvv = _pan_cvv(view)
    for m in _PAN.finditer(view):
        digits = ''.join(c for c in m.group() if c.isdigit())
        if not (13 <= len(digits) <= 19 and luhn_valid(digits)) or _overlaps(m.start(), m.end(), financial): continue
        near = _CARD_WORDS.search(view[max(0, m.start() - 40):m.start()])
        if near:
            found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.FINANCIAL,m.start(),m.end(),.95,'PAN_V1'))
        elif digits[0] in '3456' and len(digits) in (15, 16):
            found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.FINANCIAL,m.start(),m.end(),.6,'PAN_V1_UNVERIFIED'))
        financial.append((m.start(), m.end()))
    found = [f for f in found if not (f.rule_id == 'PHONE_V1' and _overlaps(f.offset_start, f.offset_end, financial))]
    for a, b in pan_cvv:
        found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.SECRET,a,b,.95,'PAN_CVV_V1'))
    for rule, a, b in find_persons(view):
        found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.PERSON,a,b,.8,rule))
    # B6-P0-10c: Filterliste (Rollen/Begriffe). In den Findings steht nur die Eintrags-ID, nie der Begriff.
    if filters is not None:
        for m in filters.find(view):
            if m.action == 'NAME_DAHINTER':
                if m.name_start >= 0: found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.PERSON,m.name_start,m.name_end,.8,'FILTER_ROLE_NAME_V1:'+m.entry_id))
                else: found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.CONTEXT_ATTRIBUTE,m.start,m.end,.3,'FILTER_ROLE_HINT_V1:'+m.entry_id))
            elif m.action == 'ERSETZEN':
                found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.PERSON,m.start,m.end,.9,'FILTER_TERM_V1:'+m.entry_id))
            else:
                found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.CONTEXT_ATTRIBUTE,m.start,m.end,.9,'FILTER_REVIEW_V1:'+m.entry_id))
    pieces = [(f, '') for f in norm.findings] + list(hidden)
    for f, label in pieces:
        rule = f'INVISIBLE_{f.severity}_V1' + (':' + label if label else '')
        found.append(PrivacyFinding(str(uuid.uuid4()),case_id,FindingKind.INVISIBLE_CHARS,f.start,f.end,1.0,rule))
    found.sort(key=lambda f:(f.offset_start,f.offset_end,f.rule_id))
    return ScanResult(case_id,sha256(content.encode('utf-8')).hexdigest(),tuple(found),'COMPLETE','rules-0.4.0',
                      filters.version if filters is not None else '',filters.sha256 if filters is not None else '')
