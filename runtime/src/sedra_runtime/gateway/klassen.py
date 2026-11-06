"""Schutzklassen, Merkmale und das Regelwerk (K-04; Regelwerk Datenkategorien und Cloudsperre v0.1, 15.10.2026): deterministisch, Fail-Safe.

Drei Zustände sind getrennt (K-04): der **Weg** (LOCAL_ONLY, CLOUD_AFTER_PSEUDONYMIZATION, CLOUD_ALLOWED – Cloud ist im MVP
immer simuliert), der **Policy-Status** (AUTO_APPROVED, HUMAN_REVIEW_REQUIRED, BLOCKED) und der **Review** (NOT_REQUIRED, PENDING,
APPROVED, REJECTED). `NOT_DETECTED` ist keine Freigabe: ein Scan ohne Treffer ergibt SK0, und die Oberfläche sagt dazu, was das heißt.

Seit Ticket B6-G-03 (Entscheidung Klaus 15.10. 14:08) gilt das **Regelwerk** `REGELN`: jede Datenkategorie ist eine Regelzeile
R-01…R-16 mit Rechtsbezug (Annahme des Teams, keine Rechtsprüfung), und was in einer gesperrten Kategorie liegt, verlässt den
Rechner nicht – auch nicht pseudonymisiert (Erwägungsgrund 26 DSGVO). Personenbezug (R-01) geht deshalb nur lokal, bis eine
Rechtsgrundlage und ein AVV dokumentiert sind (`RECHTSGRUNDLAGE_CLOUD`, nur per Registereintrag, nie per Oberfläche).
Neue Regeln sind neue Zeilen in `REGELN` (und ein Muster oder ein manuelles Kästchen), mit neuer Versionsnummer des Regelbuchs.
Die Zuordnung Regel → Merkmal und Merkmal → Klasse ist eine Tabelle; wer sie fachlich anders sieht, ändert die Tabelle."""
from __future__ import annotations

from dataclasses import dataclass, field

POLICY_VERSION = 'b6-datenregeln-0.1'          # gemeinsamer Name für Prototyp und B6-Linie (Option C)
REGELWERK = 'REGELWERK_DATENKATEGORIEN_CLOUDSPERRE_v0.1_2026-10-15'
RECHTSGRUNDLAGE_CLOUD = False                   # R-01: Rechtsgrundlage + AVV + Drittlandprüfung dokumentiert? Nein → kein Cloudweg für Personenbezug
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
    'A01': ('Hochrisiko-Kontext nach EU AI Act (Personal, Kredit, Bildung, Strafverfolgung) – von Hand zu setzen', 'SK3'),
}
MANUELL = ('R01', 'A01')           # was kein Scanner findet: der Nutzer setzt es
WEGE = ('LOCAL_ONLY', 'CLOUD_AFTER_PSEUDONYMIZATION', 'CLOUD_ALLOWED')
WEG_WORT = {'LOCAL_ONLY': 'nur lokal', 'CLOUD_AFTER_PSEUDONYMIZATION': 'Cloud nach Pseudonymisierung', 'CLOUD_ALLOWED': 'Cloud zulässig'}
# Ob der Cloudweg ein eingeschalteter Anbieter ist oder die Simulation, sagt die Oberfläche am Vorgang (cloud.modus), nicht das Wort.
STATUS_WORT = {'AUTO_APPROVED': 'Automatisch erlaubt', 'HUMAN_REVIEW_REQUIRED': 'Menschliche Prüfung nötig', 'BLOCKED': 'Verarbeitung gesperrt'}

# Das Regelbuch: id -> (Merkmal oder Sonderfall, Kategorie, Rechtsbezug [Annahme], lokal, cloud, review, Satz für den Nutzer, was tun)
REGELN = {
    'R-01': ('P01', 'Personenbezogene Daten (Name, E-Mail, Telefon, Kundennummer, Adresse)', 'Art. 4 Nr. 1, Art. 6 DSGVO; Erwägungsgrund 26',
             'ja', 'nein, bis Rechtsgrundlage und AVV dokumentiert sind (dann nur pseudonymisiert)', 'nein',
             'Personenbezug: lokal ohne weitere Prüfung; in die Cloud nicht – pseudonymisierte Daten bleiben personenbezogen.',
             'Lokal freigeben. Für einen Cloudweg braucht es Rechtsgrundlage, AVV und Drittlandprüfung im Register.'),
    'R-02': ('P02', 'Besondere Kategorien (Gesundheit, Religion, Gewerkschaft, Sexualität, Herkunft, Biometrie, Genetik)', 'Art. 9 DSGVO',
             'nur nach Prüfung', 'nie', 'ja', 'Besondere Kategorie (Art. 9): streng vertraulich – nur lokal, und nur nach deiner Prüfung.',
             'Prüfen, ob die Angabe für den Entwurf nötig ist; sonst aus der Anfrage entfernen und neu prüfen.'),
    'R-03': ('P03', 'Strafrechtliche Daten', 'Art. 10 DSGVO', 'nur nach Prüfung', 'nie', 'ja',
             'Strafsache (Art. 10): streng vertraulich – nur lokal, nur nach deiner Prüfung.', 'Prüfen und lokal freigeben oder verwerfen.'),
    'R-04': ('P04', 'Amtliche Kennungen (Steuer-ID, Ausweis, Sozialversicherung)', '§ 139b AO; Art. 87 DSGVO', 'nur nach Prüfung', 'nie', 'ja',
             'Amtliche Kennung: streng vertraulich – nur lokal, nur nach deiner Prüfung.', 'Die Kennung wird für einen Entwurf selten gebraucht: entfernen und neu prüfen.'),
    'R-05': ('V01', 'Minderjährige', 'Art. 8 DSGVO; Erwägungsgrund 38', 'nur nach Prüfung', 'nie', 'ja',
             'Minderjährige: streng vertraulich – nur lokal, nur nach deiner Prüfung.', 'Prüfen und lokal freigeben oder verwerfen.'),
    'R-06': ('F01', 'Bankverbindung, Kartendaten', 'Vertraulichkeit; PCI-DSS (nicht DSGVO)', 'ja', 'nie', 'nein',
             'Bankverbindung oder Kartendaten: vertraulich – nur lokal.', 'Lokal freigeben; der Text geht ohne Platzhalter an das lokale Modell.'),
    'R-07': ('S01', 'Kartendaten mit Prüfwert, Zugangsdaten, Schlüssel', 'Hard Block (B6 P0-10a §7)', 'nein', 'nie', '–',
             'Zugangsdaten, Schlüssel oder Kartenprüfwert: kein Modellaufruf, auch nicht lokal – nicht übersteuerbar.',
             'Den Wert aus dem Text entfernen, Vorgang neu beginnen. Es gibt kein „trotzdem“.'),
    'R-08': ('S02', 'Anweisungen an die KI oder versteckte Zeichen im Dokument', 'Hard Block (B6 P0-10a §7)', 'nein', 'nie', '–',
             'Das Dokument enthält Anweisungen an die KI oder versteckte Zeichen: kein Modellaufruf – nicht übersteuerbar.',
             'Das Dokument prüfen und bereinigen; dann neu prüfen.'),
    'R-09': ('S02', 'Anweisungen an die KI in der eigenen Anfrage', 'Entscheidung P3 (Klaus, 15.10.2026): Review', 'nur nach Prüfung, ohne Platzhalter', 'nie', 'ja',
             'Die Anfrage enthält Anweisungen an die KI oder Steuerzeichen – sieh sie dir an, bevor etwas läuft.',
             'Sätze wie „ignoriere alle Anweisungen“ aus der Anfrage entfernen oder bewusst lokal freigeben.'),
    'R-10': ('G01', 'Geschäftsgeheimnis, Kalkulation', 'GeschGehG § 2 (nicht DSGVO)', 'nur nach Prüfung', 'nie', 'ja',
             'Kalkulationsdaten (TC-011): eine Berechtigung zum Lesen ist keine Freigabe zur Offenlegung – der Entwurf darf Preise und Margen nicht nennen.',
             'Lokal freigeben und im Entwurf prüfen, dass keine Preise oder Margen stehen.'),
    'R-11': ('G02', 'Vertraulichkeitsvereinbarung', 'Vertrag (NDA)', 'ja', 'nie', 'nein', 'Vertraulichkeitsvereinbarung: vertraulich – nur lokal.', 'Lokal freigeben.'),
    'R-12': ('R01', 'Rechtsstreit, laufendes Verfahren', 'Verschwiegenheit', 'ja', 'nie', 'nein', 'Rechtsstreit (von Hand gesetzt): vertraulich – nur lokal.', 'Lokal freigeben.'),
    'R-13': ('A01', 'Hochrisiko-Anwendungskontext (Personal, Kredit, Bildung, Strafverfolgung)', 'EU AI Act Anhang III (Annahme; Rolle Anbieter/Betreiber offen)',
             'nur nach Prüfung', 'nie', 'ja', 'Hochrisiko-Kontext nach AI Act (von Hand gesetzt): nur lokal, nur nach deiner Prüfung.',
             'Prüfen, ob der Entwurf eine Entscheidung über eine Person vorbereitet; dann bleibt die Entscheidung beim Menschen.'),
    'R-14': ('KENNZEICHNUNG', 'KI-Kennzeichnung des Entwurfs', 'EU AI Act Art. 50', '–', '–', '–',
             'Jeder Entwurf trägt den Hinweis „KI-Entwurf, menschlich geprüft: ja/nein“.', 'Vor einer Weitergabe den Entwurf als geprüft markieren.'),
    'R-15': ('KEINE', 'Keine Kategorie getroffen, Scan vollständig', '–', 'ja', 'ja', 'nein',
             'Keine Schutzmerkmale gefunden. Cloud wäre zulässig. Kein Treffer heißt nicht unbedenklich.', 'Lokal oder Cloud freigeben.'),
    'R-16': ('UNCLASSIFIED', 'Scan unvollständig, Datei unlesbar, Regelkonflikt', 'fail-closed (Projektanweisung)', 'nein', 'nein', 'ja',
             'Die Prüfung ist unvollständig (Datei nicht lesbar oder Scanner-Fehler). Ungeklärt ist keine Freigabe.', 'Datei prüfen (nur .md/.txt, UTF-8) und neu prüfen.'),
}
REGEL_VON_MERKMAL = {'P01': 'R-01', 'P02': 'R-02', 'P03': 'R-03', 'P04': 'R-04', 'V01': 'R-05', 'F01': 'R-06', 'F02': 'R-06', 'F03': 'R-07',
                     'S01': 'R-07', 'S02': 'R-08', 'G01': 'R-10', 'G02': 'R-11', 'R01': 'R-12', 'A01': 'R-13'}   # S02 in der Anfrage: R-09 (siehe regel_fuer)


def regel_fuer(merkmal, quelle=''):
    """Die Regelzeile zu einem Merkmal; S02 hängt davon ab, wo es steht (Dokument R-08, eigene Anfrage R-09)."""
    if merkmal == 'S02' and quelle == 'anfrage':
        return 'R-09'
    return REGEL_VON_MERKMAL.get(merkmal)


def regel(rid):
    r = REGELN[rid]
    return {'id': rid, 'merkmal': r[0], 'kategorie': r[1], 'bezug': r[2], 'lokal': r[3], 'cloud': r[4], 'review': r[5], 'satz': r[6], 'tun': r[7]}


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
    gruende: list = field(default_factory=list)        # Sätze für den Nutzer, je mit Regelnummer vorn
    regeln: list = field(default_factory=list)         # getroffene Regel-IDs (R-xx), geordnet wie gruende
    quelle: dict = field(default_factory=dict)         # Merkmal -> wo gefunden (anfrage/dokument/manuell)

    def as_dict(self):
        return {'policy_version': POLICY_VERSION, 'regelwerk': REGELWERK, 'klasse': self.klasse, 'klasse_wort': KLASSE_WORT.get(self.klasse, 'Ungeklärt'),
                'merkmale': [{'id': m, 'name': MERKMALE[m][0], 'quelle': self.quelle.get(m, ''), 'regel': regel_fuer(m, self.quelle.get(m, ''))} for m in self.merkmale],
                'hard_block': list(self.hard_block), 'wege': list(self.wege), 'wege_wort': [WEG_WORT[w] for w in self.wege],
                'policy': self.policy, 'policy_wort': STATUS_WORT[self.policy], 'review': self.review, 'gruende': list(self.gruende),
                'regeln': list(self.regeln),
                'hinweis': 'Kein Treffer heißt nicht unbedenklich: die Regeln kennen nicht alles. R01 (Rechtsstreit) und A01 (Hochrisiko-Kontext) setzt du von Hand.'}


def _grund(e, rid, text=None):
    e.regeln.append(rid)
    e.gruende.append(f'{rid}: ' + (text or REGELN[rid][6]))


def einstufen(hits_anfrage=(), hits_dokument=(), *, scan_ok=True, manuell=()):
    """Die Matrix. `hits_*` sind (rule_id, kind)-Paare; `manuell` Merkmal-IDs, die der Nutzer gesetzt hat."""
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
    # Hard Block: S01, F03 überall (R-07); S02 im Dokument (R-08). S02 in der Anfrage: Review (R-09, Entscheidung P3).
    e.hard_block = [m for m in e.merkmale if MERKMALE[m][1] == 'BLOCK' and not (m == 'S02' and gefunden[m] == 'anfrage')]
    if e.hard_block:
        e.policy, e.review, e.wege = 'BLOCKED', 'NOT_REQUIRED', []
        e.klasse = 'SK3'
        for m in e.hard_block:
            rid = 'R-08' if m == 'S02' else 'R-07'
            _grund(e, rid, f'{MERKMALE[m][0]} ({gefunden[m]}): kein Modellaufruf, auch nicht lokal – nicht übersteuerbar.')
        return e
    if not scan_ok:
        e.klasse, e.policy, e.review, e.wege = 'UNCLASSIFIED', 'HUMAN_REVIEW_REQUIRED', 'PENDING', []
        _grund(e, 'R-16')
        return e
    stufen = [MERKMALE[m][1] for m in e.merkmale if MERKMALE[m][1] in KLASSEN]
    if 'S02' in gefunden:
        stufen.append('SK3')
    e.klasse = max(stufen, key=KLASSEN.index) if stufen else 'SK0'
    if e.klasse == 'SK3':
        e.policy, e.review, e.wege = 'HUMAN_REVIEW_REQUIRED', 'PENDING', ['LOCAL_ONLY']
        for m in e.merkmale:
            if MERKMALE[m][1] == 'SK3':
                _grund(e, REGEL_VON_MERKMAL[m])
        if 'S02' in gefunden:
            _grund(e, 'R-09')
        for m in e.merkmale:                                       # die Nebenmerkmale (SK1/SK2) stehen mit dabei, damit der Nutzer alles sieht
            if MERKMALE[m][1] in ('SK1', 'SK2'):
                _grund(e, REGEL_VON_MERKMAL[m])
    elif e.klasse == 'SK2':
        e.policy, e.review, e.wege = 'AUTO_APPROVED', 'NOT_REQUIRED', ['LOCAL_ONLY']
        for m in e.merkmale:
            _grund(e, REGEL_VON_MERKMAL[m])
    elif e.klasse == 'SK1':
        e.policy, e.review = 'AUTO_APPROVED', 'NOT_REQUIRED'
        e.wege = ['LOCAL_ONLY', 'CLOUD_AFTER_PSEUDONYMIZATION'] if RECHTSGRUNDLAGE_CLOUD else ['LOCAL_ONLY']
        _grund(e, 'R-01', None if not RECHTSGRUNDLAGE_CLOUD else
               'Personenbezug: lokal ohne weitere Prüfung; in die Cloud nur mit Platzhaltern (Rechtsgrundlage und AVV liegen im Register).')
    else:
        e.policy, e.review, e.wege = 'AUTO_APPROVED', 'NOT_REQUIRED', ['LOCAL_ONLY', 'CLOUD_ALLOWED']
        _grund(e, 'R-15')
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
