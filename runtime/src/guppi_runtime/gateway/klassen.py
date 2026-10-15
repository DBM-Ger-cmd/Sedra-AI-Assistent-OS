"""Schutzklassen und Merkmale (K-04, SPEC_GATEWAY_VORGANG_v1 §2/§3): deterministisch, Fail-Safe, aus den B6-Regeln.

Drei Zustände sind getrennt (K-04): der **Weg** (LOCAL_ONLY, CLOUD_AFTER_PSEUDONYMIZATION, CLOUD_ALLOWED – Cloud ist im MVP
immer simuliert), der **Policy-Status** (AUTO_APPROVED, HUMAN_REVIEW_REQUIRED, BLOCKED) und der **Review** (NOT_REQUIRED, PENDING,
APPROVED, REJECTED). `NOT_DETECTED` ist keine Freigabe: ein Scan ohne Treffer ergibt SK0, und die Oberfläche sagt dazu, was das heißt.
Die Zuordnung Regel → Merkmal und Merkmal → Klasse ist eine Tabelle; wer sie fachlich anders sieht (KLA-O1/O2), ändert die Tabelle."""
from __future__ import annotations

from dataclasses import dataclass, field

POLICY_VERSION = 'sedra-gateway-1.0'
KLASSEN = ('SK0', 'SK1', 'SK2', 'SK3')
KLASSE_WORT = {'SK0': 'Öffentlich', 'SK1': 'Intern', 'SK2': 'Vertraulich', 'SK3': 'Streng vertraulich'}
# Merkmal -> (Name, Klasse oder BLOCK)
MERKMALE = {
    'P01': ('Personenbezug', 'SK1'),
    'P02': ('Besondere Kategorien (Gesundheit, Religion, Weltanschauung …)', 'SK3'),
    'P03': ('Strafsachen', 'SK3'),
    'P04': ('Amtliche Kennungen (Steuer-ID, Ausweis, Sozialversicherung)', 'SK3'),
    'F01': ('Bankverbindung', 'SK2'),
    'F02': ('Kartendaten', 'SK2'),
    'F03': ('Kartendaten mit Prüfwert', 'BLOCK'),
    'S01': ('Zugangsdaten, Schlüssel, Passwörter', 'BLOCK'),
    'S02': ('Anweisungen an die KI, versteckte Steuerzeichen', 'BLOCK'),
    'G01': ('Kalkulation, Geschäftsgeheimnis', 'SK3'),
    'G02': ('Vertraulichkeitsvereinbarung (NDA)', 'SK2'),
    'R01': ('Rechtsstreit, laufendes Verfahren – nicht automatisch erkennbar, von Hand zu setzen', 'SK2'),
    'V01': ('Minderjährige', 'SK3'),
}
MANUELL = ('R01',)                 # was kein Scanner findet: der Captain setzt es
WEGE = ('LOCAL_ONLY', 'CLOUD_AFTER_PSEUDONYMIZATION', 'CLOUD_ALLOWED')
WEG_WORT = {'LOCAL_ONLY': 'nur lokal', 'CLOUD_AFTER_PSEUDONYMIZATION': 'Cloud nach Pseudonymisierung (simuliert)',
            'CLOUD_ALLOWED': 'Cloud zulässig (simuliert)'}
STATUS_WORT = {'AUTO_APPROVED': 'Automatisch erlaubt', 'HUMAN_REVIEW_REQUIRED': 'Menschliche Prüfung nötig', 'BLOCKED': 'Verarbeitung gesperrt'}


def merkmal_von(rule_id, kind=''):
    """Welches Merkmal eine B6-Regel trifft – oder None (Hinweisregeln wie PLACEHOLDER_INJECTION im eigenen Text)."""
    r = rule_id.split(':', 1)[0]
    if r == 'PAN_CVV_V1':
        return 'F03'
    if r.startswith('PAN_'):
        return 'F02'
    if r.startswith('IBAN_'):
        return 'F01'
    if r.startswith('SECRET_'):
        return 'S01'
    if r.startswith(('INJECTION_', 'INVISIBLE_')) or r == 'PLACEHOLDER_INJECTION_V1':
        return 'S02'
    if r.startswith('CTX_P02'): return 'P02'
    if r.startswith('CTX_P03'): return 'P03'
    if r.startswith('CTX_P04'): return 'P04'
    if r.startswith('CTX_G01'): return 'G01'
    if r.startswith('CTX_G02'): return 'G02'
    if r.startswith('CTX_V01'): return 'V01'
    if r.startswith(('PERSON_', 'EMAIL_', 'PHONE_', 'CUSTID_', 'ADDRESS_', 'FILTER_', 'KI_', 'GW_EMAIL')) or kind in ('PERSON', 'EMAIL', 'PHONE', 'IDENTIFIER'):
        return 'P01'
    return None


@dataclass
class Einstufung:
    klasse: str                      # SK0..SK3, oder 'UNCLASSIFIED'
    merkmale: list = field(default_factory=list)       # getroffene Merkmal-IDs, geordnet
    hard_block: list = field(default_factory=list)     # Merkmale, die sperren
    wege: list = field(default_factory=list)           # erlaubte Wege
    policy: str = 'BLOCKED'          # AUTO_APPROVED | HUMAN_REVIEW_REQUIRED | BLOCKED
    review: str = 'NOT_REQUIRED'     # NOT_REQUIRED | PENDING
    gruende: list = field(default_factory=list)        # Sätze für den Captain
    quelle: dict = field(default_factory=dict)         # Merkmal -> wo gefunden (anfrage/dokument/manuell)

    def as_dict(self):
        return {'policy_version': POLICY_VERSION, 'klasse': self.klasse, 'klasse_wort': KLASSE_WORT.get(self.klasse, 'Ungeklärt'),
                'merkmale': [{'id': m, 'name': MERKMALE[m][0], 'quelle': self.quelle.get(m, '')} for m in self.merkmale],
                'hard_block': list(self.hard_block), 'wege': list(self.wege), 'wege_wort': [WEG_WORT[w] for w in self.wege],
                'policy': self.policy, 'policy_wort': STATUS_WORT[self.policy], 'review': self.review, 'gruende': list(self.gruende),
                'hinweis': 'Kein Treffer heißt nicht unbedenklich: die Regeln kennen nicht alles. R01 (Rechtsstreit) setzt du von Hand.'}


def einstufen(hits_anfrage=(), hits_dokument=(), *, scan_ok=True, manuell=()):
    """Die Matrix. `hits_*` sind (rule_id, kind)-Paare; `manuell` Merkmal-IDs, die der Captain gesetzt hat."""
    e = Einstufung('SK0')
    gefunden = {}
    for where, hits in (('anfrage', hits_anfrage), ('dokument', hits_dokument)):
        for rule_id, kind in hits:
            m = merkmal_von(rule_id, kind)
            if m and m not in gefunden:
                gefunden[m] = where
    for m in manuell:
        if m in MANUELL and m not in gefunden:                    # von Hand nur, was kein Scanner finden kann
            gefunden[m] = 'manuell'
    e.merkmale = sorted(gefunden, key=lambda m: (MERKMALE[m][1] != 'BLOCK', -KLASSEN.index(MERKMALE[m][1]) if MERKMALE[m][1] in KLASSEN else 9, m))
    e.quelle = gefunden
    # Hard Block: S01, F03 überall; S02 im Dokument (fremder Inhalt, der der KI befehlen will). S02 in der Anfrage: Review.
    e.hard_block = [m for m in e.merkmale if MERKMALE[m][1] == 'BLOCK' and not (m == 'S02' and gefunden[m] == 'anfrage')]
    if e.hard_block:
        e.policy, e.review, e.wege = 'BLOCKED', 'NOT_REQUIRED', []
        e.klasse = 'SK3'
        e.gruende = [f'{MERKMALE[m][0]} ({gefunden[m]}): kein Modellaufruf, auch nicht lokal – nicht übersteuerbar.' for m in e.hard_block]
        return e
    if not scan_ok:
        e.klasse, e.policy, e.review, e.wege = 'UNCLASSIFIED', 'HUMAN_REVIEW_REQUIRED', 'PENDING', []
        e.gruende = ['Die Prüfung ist unvollständig (Datei nicht lesbar oder Scanner-Fehler). Ungeklärt ist keine Freigabe.']
        return e
    stufen = [MERKMALE[m][1] for m in e.merkmale if MERKMALE[m][1] in KLASSEN]
    if 'S02' in gefunden:
        stufen.append('SK3')
    e.klasse = max(stufen, key=KLASSEN.index) if stufen else 'SK0'
    if e.klasse == 'SK3':
        e.policy, e.review, e.wege = 'HUMAN_REVIEW_REQUIRED', 'PENDING', ['LOCAL_ONLY']
        e.gruende = [f'{MERKMALE[m][0]}: streng vertraulich – nur lokal, und nur nach deiner Prüfung.' for m in e.merkmale if MERKMALE[m][1] == 'SK3']
        if 'S02' in gefunden:
            e.gruende.append('Die Anfrage enthält Anweisungen an die KI oder Steuerzeichen – sieh sie dir an, bevor etwas läuft.')
        if 'G01' in gefunden:
            e.gruende.append('Kalkulationsdaten (TC-011): eine Berechtigung zum Lesen ist keine Freigabe zur Offenlegung – der Entwurf darf Preise und Margen nicht nennen.')
    elif e.klasse == 'SK2':
        e.policy, e.review, e.wege = 'AUTO_APPROVED', 'NOT_REQUIRED', ['LOCAL_ONLY']
        e.gruende = [f'{MERKMALE[m][0]}: vertraulich – nur lokal.' for m in e.merkmale if MERKMALE[m][1] == 'SK2']
    elif e.klasse == 'SK1':
        e.policy, e.review, e.wege = 'AUTO_APPROVED', 'NOT_REQUIRED', ['LOCAL_ONLY', 'CLOUD_AFTER_PSEUDONYMIZATION']
        e.gruende = ['Personenbezug: lokal ohne weitere Prüfung; in die Cloud nur mit Platzhaltern – und im MVP nur simuliert.']
    else:
        e.policy, e.review, e.wege = 'AUTO_APPROVED', 'NOT_REQUIRED', ['LOCAL_ONLY', 'CLOUD_ALLOWED']
        e.gruende = ['Keine Schutzmerkmale gefunden. Cloud wäre zulässig – im MVP simuliert.']
    return e


def weg_erlaubt(einstufung, wunsch):
    """Der Nutzer darf restriktiver wählen, nie offener (K-03): lokal geht immer, wenn überhaupt etwas geht."""
    if einstufung.policy == 'BLOCKED':
        return None
    if wunsch == 'local':
        return 'LOCAL_ONLY' if 'LOCAL_ONLY' in einstufung.wege else None
    for w in ('CLOUD_ALLOWED', 'CLOUD_AFTER_PSEUDONYMIZATION'):
        if w in einstufung.wege:
            return w
    return None
