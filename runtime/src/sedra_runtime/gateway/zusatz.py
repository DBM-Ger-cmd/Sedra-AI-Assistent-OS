"""Zusätzliche Erkennung im GateWay (Prüfung der Prüffälle, 20.10.2026), neben dem eingefrorenen B6-Scanner.

Der B6-Kern (core/b6core/privacy.py) bleibt unverändert, weil seine Herkunft geprüft wird (HERKUNFT.sha256). Diese Datei liefert
zusätzliche Treffer im selben Format wie der Scanner – (Regelname, Art) –, die `klassen.einstufen` wie jeden anderen Treffer
einordnet. Die Regelnamen beginnen mit den Präfixen, die `klassen.merkmal_von` schon kennt, deshalb ist keine Tabelle zu ändern.

Was hier erkannt wird (Muster, kein Beweis; im Zweifel eher zu viel als zu wenig):
- Zugangsdaten (SECRET_ → S01, Hard Block: kein Modellaufruf, R-07)
- Geschäftsinformation, Konditionen, Gehalt, öffentlicher externer Dienst (CTX_G01 → G01, SK3, nie Cloud, R-10)
- Personalnummern, Anschlüsse, Geburtsdaten (PERSON_ → P01, Personenbezug, nur lokal, R-01)
- Kontokennungen (IBAN_ → F01, vertraulich, nur lokal, R-06)

Nicht erkannt: Personennamen außerhalb der Muster des Kerns. Dafür ist eine Erweiterung des B6-Kerns nötig (Entscheidung des Captains)."""
from __future__ import annotations

import re

# (Regelname, Art, Muster) – die Reihenfolge ist egal; mehrere Treffer je Regel sind erlaubt
_MUSTER = (
    # Zugangsdaten: Stichwort, optional „ist/lautet/:“, dann ein Wert ohne Leerzeichen
    ('SECRET_ZUSATZ_KENNWORT', 'SECRET',
     re.compile(r'(?i)\b(?:kennwort|passwort|passphrase|api[- ]?schl(?:ü|ue|u)ssel|zugangsschl(?:ü|ue|u)ssel|access[- ]?token|geheimer?\s+schl(?:ü|ue|u)ssel)\b'
                r'(?:\s+(?:ist|lautet))?\s*[:=]?\s*\S{4,}')),
    # Geschäftsinformation, die nicht nach außen darf
    ('CTX_G01_ZUSATZ_VERTRAULICH', 'G01',
     re.compile(r'(?i)\b(?:vertraulich\w*|streng vertraulich|nicht ver(?:ö|oe)ffentlicht\w*|preisuntergrenze|sonderrabatt|einkaufspreis\w*|'
                r'kaufpreis|verhandelte?\w*\s+(?:rabatt|konditionen|preis)|marge\w*|konditionen|gesch(?:ä|ae)ftsgeheimnis|betriebsgeheimnis)')),
    # Gehalt und Vergütung einzelner Personen
    ('CTX_G01_ZUSATZ_GEHALT', 'G01',
     re.compile(r'(?i)\b(?:gehalt\w*|verg(?:ü|ue)tung\w*|bruttogehalt|brutto\s+monatlich|lohnhöhe|gehaltsliste)\b')),
    # Die Anfrage soll in einen öffentlichen externen Dienst
    ('CTX_G01_ZUSATZ_EXTERN', 'G01',
     re.compile(r'(?i)\böffentlich\w*\s+(?:KI|Dienst|Cloud|Plattform|Dienst\w*)')),
    # Personalnummern, Anschlüsse, Geburtsdaten
    ('PERSON_ZUSATZ_PERSONALNUMMER', 'PERSON', re.compile(r'\bP-\d{2,}\b')),
    ('PERSON_ZUSATZ_ANSCHLUSS', 'PERSON', re.compile(r'\bTEL-[A-Z0-9][A-Z0-9-]{2,}\b')),
    ('PERSON_ZUSATZ_GEBURT', 'PERSON', re.compile(r'(?i)\bgeb\.?\s*\d{2}\.\d{2}\.\d{4}\b')),
    # Kontokennung
    ('IBAN_ZUSATZ_KONTOKENNUNG', 'IBAN', re.compile(r'(?i)\bkontokennung\b')),
    # Anweisung an die KI, Regeln zu übergehen (INJECTION_ → S02; in der Anfrage: Review, R-09)
    ('INJECTION_ZUSATZ_IGNORIEREN', 'INJECTION',
     re.compile(r'(?i)\bignorier\w*\s+(?:alle|die|sämtliche|saemtliche|bisherigen|vorherigen)?\s*(?:\w+\s+){0,2}'
                r'(?:anweisungen|regeln|schutzregeln|vorgaben|instruktionen|richtlinien)\b')),
)


def treffer(text: str) -> list[tuple[str, str]]:
    """Die zusätzlichen Treffer als (Regelname, Art), dieselbe Form wie der Scanner. Leerer Text: keine Treffer."""
    if not isinstance(text, str) or not text.strip():
        return []
    out = []
    for rid, kind, rx in _MUSTER:
        if rx.search(text):
            out.append((rid, kind))
    return out
