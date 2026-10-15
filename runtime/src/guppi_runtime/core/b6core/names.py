"""B6-P0-10a: Namenserkennung ohne KI (Regeln + kleine Vornamenliste). NICHT vollstaendig, bewusst konservativ.

Erkennt Namen nur in belegbaren Formen (Selbstnennung, Anrede/Titel, Rollenwort + Vorname, bekannter Vorname + Nachname,
Unterschrift nach Grussformel). Ein grossgeschriebenes Wort allein ist nie ein Name (deutsche Nomen sind gross).
Die Muster laufen auf der normalisierten Sicht (`view`), mit begrenzten Quantoren und ohne verschachtelte offene
Wiederholungen (lineare Laufzeit). Die Listen sind synthetische Pilotdaten; 10c erweitert sie um eine Filterliste.
"""
import re

# Kleine Vorauswahl haeufiger, eindeutiger Vornamen (inkl. Namen der synthetischen Testkorpora).
FIRST_NAMES = frozenset('''
Alexander Alex Andrea Andreas Angelika Anja Anna Annette Antje Barbara Benjamin Bernd Birgit Britta Carina Carsten Christian
Christina Christoph Claudia Daniel Dennis Dieter Dirk Doris Elena Elisabeth Emma Eva Felix Florian Frank Franziska Gabriele
Georg Gerd Gisela Hannah Heike Heiko Helga Helmut Henrik Ingrid Jan Jana Janine Jasmin Jens Jessica Joachim Jonas Julia Jürgen
Katharina Karin Karl Katja Kerstin Klaus Kristin Lars Laura Lea Lena Leon Lisa Lukas Manfred Manuel Marc Marco Marcel Maria
Marie Marion Mark Markus Marlene Martin Martina Mara Matthias Max Melanie Michael Michaela Mina Monika Nadine Nicole Nils Nina
Norbert Olaf Oliver Paul Paula Peter Petra Philipp Piet Rainer Ralf Reinhard Renate Robert Roland Sabine Sandra Sarah
Sebastian Silke Simon Sophie Stefan Stefanie Susanne Sven Tanja Thomas Tim Tobias Torsten Ulrike Ulrich Ursula Uwe Vera
Verena Viktoria Walter Werner Wolfgang Yvonne
'''.split())
FIRST_NAMES = frozenset(n for n in FIRST_NAMES if n not in {'Mark', 'Marc'})   # Mehrdeutig (Nomen/Eigenname): bewusst nicht gefuehrt

_UC, _LC = 'A-ZÄÖÜ', 'a-zäöüß'
NAME = rf'[{_UC}][{_LC}]+(?:-[{_UC}][{_LC}]+)?(?![A-Za-zÄÖÜäöüß])'
_FIRST = '(?:' + '|'.join(sorted(FIRST_NAMES, key=lambda n: (-len(n), n))) + ')(?![A-Za-zÄÖÜäöüß])'
_ROLE_BASE = ('Sekretär', 'Einkäufer', 'Geschäftsführer', 'Buchhalter', 'Assistent', 'Projektleiter', 'Vertriebsleiter',
              'Sachbearbeiter', 'Ansprechpartner', 'Referent', 'Kunde', 'Karteninhaber', 'Mitarbeiter', 'Absender',
              'Teilnehmer', 'Bewerber', 'Patient', 'Mandant', 'Lieferant', 'Betreuer')
ROLE_WORDS = '(?:(?:' + '|'.join(_ROLE_BASE) + r')(?:in|innen|en|n)?|Kundin|Testperson|Betreuungsperson|Ansprechperson|Kontaktperson)'

_SP = r'[ \t]+'
_GREETING = (r'(?:Mit\s+freundlichen\s+Gr(?:ü|ue)ßen|Freundliche\s+Gr(?:ü|ue)ße|Viele\s+Gr(?:ü|ue)ße|Beste\s+Gr(?:ü|ue)ße|'
             r'Herzliche\s+Gr(?:ü|ue)ße|Gr(?:ü|ue)ße|Gruß|Gruss|Best\s+regards|Kind\s+regards|Regards)')

# (rule_id, regex, Gruppe mit dem Namen). Die Gruppe bestimmt die gemeldete Spanne.
RULES = (
    ('PERSON_SELF_V1', re.compile(rf'(?i:\bmein{_SP}name{_SP}ist{_SP})({NAME}(?:{_SP}{NAME}){{0,2}})'), 1),
    ('PERSON_TITLE_V1', re.compile(rf'\b(?:Herr|Herrn|Frau|Dr\.|Prof\.)(?:{_SP}(?:Dr\.|med\.))*{_SP}({NAME}(?:{_SP}{NAME})?)'), 1),
    ('PERSON_ROLE_V1', re.compile(rf'\b{ROLE_WORDS}[ \t]*:?{_SP}({_FIRST}(?:{_SP}{NAME})?)'), 1),
    ('PERSON_FIRSTNAME_V1', re.compile(rf'\b({_FIRST}{_SP}{NAME})'), 1),
    # B6-P0-10b (T-018): Strassenadresse mit Hausnummer, optional gefolgt von PLZ + Ort. Eine Adresse ist ein Personenbezug (P01).
    ('ADDRESS_V1', re.compile(rf'\b([{_UC}][{_LC}]+(?:straße|strasse|weg|allee|platz|gasse|ring|damm|ufer|chaussee)[ \t]*\d{{1,4}}[a-z]?(?:,?[ \t]*\d{{5}}[ \t]+{NAME})?)(?![\w])'), 1),
    ('PERSON_SIGNATURE_V1', re.compile(rf'{_GREETING}[,!.]?[ \t]*\r?\n[ \t]*({NAME}(?:{_SP}{NAME}){{0,2}})(?=[ \t]*(?:[,;]|\r?\n|$))'), 1),
)


def find_persons(view):
    """Liefert (rule_id, start, end) je Fundstelle und Regel; identische Treffer nur einmal. Ueberlappungen bleiben
    bewusst getrennt sichtbar (Regelzuordnung fuer Audit und Tests); die Pseudonymisierung fasst Spannen selbst zusammen."""
    seen = set()
    for rule_id, rx, group in RULES:
        for m in rx.finditer(view):
            seen.add((m.start(group), m.end(group), rule_id))
    return [(rule, a, b) for a, b, rule in sorted(seen)]
