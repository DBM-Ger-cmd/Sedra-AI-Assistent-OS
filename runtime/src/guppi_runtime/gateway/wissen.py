"""Die Wissensbasis des KI GateWay – SEDRA sieht die Studio-Shell als seine Arbeitsumgebung (Ticket B6-G-03, Captain 15.10.2026 14:12/14:14).

Was hier liegt: das Regelbuch (R-01…R-16), die Merkmale, die Zustände eines Vorgangs mit dem jeweils nächsten Schritt, die
Fehlercodes mit Bedeutung und Abhilfe, und ein paar Begriffe. Dazu der **Live-Zustand**: welche Vorgänge es gibt, in welchem
Zustand, mit welcher Einstufung. Aus beidem beantwortet `antwort()` eine Frage des Nutzers im Gespräch – **deterministisch, ohne
Modellaufruf**: „Was muss ich als Nächstes machen?“, „Wo ist der Fehler in diesem Text: …“, „Warum ist der Vorgang gesperrt?“,
„Was sagt Regel R-02?“. Ein geladenes Modell kann dieselben Antworten über die Werkzeuge `gateway_*` (chat_tools.py) holen.

Ablage: `local_config/gateway/wissen.sqlite` (Standardbibliothek sqlite3). Die Tabelle `wissen` wird bei jedem Start aus dem
Code neu gefüllt (Versionsstempel = Policyversion); eigene Einträge des Nutzers stehen in `eigene` und bleiben erhalten.
Kein Text eines Vorgangs wird hier gespeichert – nur Zustand, Klasse, Merkmale, Regeln. Keine Verbindung nach außen.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path

from ..core.b6core.normalize import normalize
from ..core.content_policy import ScanFailure, scan_content
from . import klassen

# Der Leitfaden: so arbeitet ein Mensch mit dem GateWay – vom Anlegen bis zum Ablegen (Captain 15.10. 14:19). Teil des Moduls:
# die Shell zeigt ihn, die Wissensbasis antwortet daraus, und jeder Zustand eines Vorgangs kennt seinen Schritt.
LEITFADEN = [
    {'nr': 1, 'station': '00', 'zustand': None, 'titel': 'Vorbereiten',
     'mensch': 'Nur synthetische oder freigegebene Daten verwenden. Das Dokument, das mit soll, als .md oder .txt im Projektordner ablegen. Klären, wer die Freigabe verantwortet und wozu der Entwurf dient (Zweck).',
     'warten': '–', 'pruefen': 'Liegt die Datei im Projekt? Ist sie UTF-8-Text? Enthält sie nichts, was nie hinausdarf (Schlüssel, Kartenprüfwert)?',
     'ablegen': 'Das Dokument bleibt im Projektordner; das GateWay kopiert es nicht.',
     'sedra': 'Zeigt die Dateien des Projekts, nennt die Regeln (R-01…R-16) und prüft einen Text vorab: „Wo ist der Fehler in diesem Text: …“.'},
    {'nr': 2, 'station': '01', 'zustand': 'NEU', 'titel': 'Vorgang anlegen',
     'mensch': 'Im KI GateWay „Neuer Vorgang“: Titel eintragen, Wunsch wählen – lokale KI (das geladene Modell) oder Cloud-KI (ein eingeschalteter Anbieter; ohne Anbieter Simulation). Der Wunsch darf später nur restriktiver werden, nie offener.',
     'warten': '–', 'pruefen': 'Ist ein Modell geladen (Maschinenraum)? Sonst antwortet in Station 04 niemand.',
     'ablegen': 'Der Vorgang bekommt eine Nummer GW-… und liegt unter local_config/gateway/vorgaenge/.',
     'sedra': 'Öffnet das GateWay, sagt, ob ein Modell geladen ist, und erklärt den Weg.'},
    {'nr': 3, 'station': '02', 'zustand': 'NEU', 'titel': 'Eingeben und prüfen lassen',
     'mensch': 'Die Kundenanfrage und das Ziel in den Eingabeprompt schreiben; Dokument aus der Liste wählen; Zweck und verantwortliche Person setzen; R01 (Rechtsstreit) und A01 (Hochrisiko-Kontext) von Hand ankreuzen, wenn sie zutreffen. Dann „Datenschutz prüfen“.',
     'warten': 'Wenige Sekunden: Scan, Merkmale, Klasse, Übergabeprompt. Ergebnis ist GEPRÜFT, GESPERRT oder FEHLER.',
     'pruefen': 'Links die Markierungen im Original, rechts der Übergabeprompt mit Platzhaltern (oder der Hinweis, warum ohne). Fehlt eine Markierung, die du erwartest? Dann ist das eine Grenze der Regeln – im Zweifel R01/A01 setzen oder den Text ändern.',
     'ablegen': 'Anfrage und Einstufung liegen im Vorgang; bei GESPERRT wird kein Text gespeichert. Die Zuordnung der Platzhalter lebt nur im Prozess.',
     'sedra': 'Erklärt jeden Fund mit Regelnummer und sagt, was zu tun ist: „Warum ist der Vorgang gesperrt?“'},
    {'nr': 4, 'station': '03', 'zustand': 'GEPRUEFT', 'titel': 'Empfehlung lesen und freigeben',
     'mensch': 'Schutzklasse, Merkmale, Regeln und erlaubte Wege lesen. Nur erlaubte Wege haben einen Knopf; bei „Menschliche Prüfung nötig“ ist deine Freigabe die Prüfung R1. Freigeben – das ist eine Entscheidung mit Bindung (Anfrage, Dokument, Klasse, Merkmale, Weg, Übergabeprompt, Zweck, Person).',
     'warten': 'Die Freigabe erscheint in den Entscheidungen; der Vorgang steht auf WARTET, bis du dort „freigeben und anwenden“ oder „ablehnen“ wählst.',
     'pruefen': 'Stimmen Zweck und Person? Ist der Weg so restriktiv wie nötig? Bei Kalkulationsdaten (R-10): darf der Entwurf Preise nennen? Nein.',
     'ablegen': 'Die Entscheidung steht mit Bindung im Logbuch (Audit, ohne Text).',
     'sedra': 'Erklärt die Einstufung, öffnet die Entscheidungen und nennt die Bindung.'},
    {'nr': 5, 'station': '03→04', 'zustand': 'WARTET', 'titel': 'Auf die Auswertung warten',
     'mensch': 'Nach „freigeben und anwenden“ nichts am Vorgang ändern. Das lokale Modell bekommt den Übergabeprompt durch den Inhaltsschutz; die Cloud geht über den Anbieter, sonst ist sie simuliert. Die Antwort durchläuft Recheck 2 (vor der Rückübersetzung) und Recheck 3 (danach).',
     'warten': 'Je nach Modell Sekunden bis Minuten. Ergebnis ist ENTWURF oder FEHLER (dann ist nichts hinausgegangen, die Zuordnung ist gelöscht).',
     'pruefen': 'Bei FEHLER den Code lesen: entwurf_zurueckgehalten = der Entwurf enthielt Schlüssel/Kartenprüfwert; mapping_fehlt = Neustart dazwischen → neu prüfen.',
     'ablegen': 'Der Entwurf liegt getrennt unter local_config/gateway/entwuerfe/ mit Löschdatum; der Vorgang trägt nur seinen Hash.',
     'sedra': 'Sagt, ob ein Modell geladen ist, und erklärt jeden Fehlercode mit Abhilfe.'},
    {'nr': 6, 'station': '04', 'zustand': 'ENTWURF', 'titel': 'Entwurf prüfen (R2)',
     'mensch': 'Den Entwurf lesen. Prüfen: erfundene Termine, Preise, Zusagen? Platzhalter richtig zurückübersetzt? Die KI-Kennzeichnung steht dabei („KI-Entwurf – menschlich geprüft: nein“). Dann „Geprüft“ oder „Verwerfen“.',
     'warten': '–', 'pruefen': 'Alles, was im Entwurf steht, muss aus Anfrage oder Dokument belegbar sein. Offene Punkte müssen als offen stehen.',
     'ablegen': '„Geprüft“ setzt die Kennzeichnung auf „menschlich geprüft: ja“ und schließt den Vorgang ab; „Verwerfen“ löscht den Entwurf.',
     'sedra': 'Prüft den Entwurf auf Funde („Wo ist der Fehler in diesem Text: …“) und nennt das Löschdatum.'},
    {'nr': 7, 'station': 'Ablage', 'zustand': 'ABGESCHLOSSEN', 'titel': 'Ablegen',
     'mensch': 'Kein Versand aus dem GateWay. Wer den geprüften Entwurf behalten will, übernimmt ihn vor dem Löschdatum von Hand in das eigene System (E-Mail-Entwurf, Vorgangsakte). In der Minimal-Shell lässt sich der Vorgang an die Ablage heften.',
     'warten': '–', 'pruefen': 'Löschdatum im Entwurf (Vorgabe aus local_config/gateway/vorgaben.yaml). Danach ist der Entwurf weg; der Vorgang bleibt ohne Text.',
     'ablegen': 'Vorgang: local_config/gateway/vorgaenge/<GW-…>.json (Einstufung, Hashes, Verlauf, kein Entwurfstext). Entwurf: entwuerfe/<GW-…>.json bis zum Löschdatum (Audit GW_ENTWURF_GELOESCHT). Logbuch: GW_VORGANG_NEU, GW_GEPRUEFT, GW_ENTWURF, GW_PRUEFUNG – ohne Text.',
     'sedra': 'Nennt das Löschdatum, öffnet das Logbuch und listet die Vorgänge: „Wie ist der Stand?“'},
]
SCHRITT_VON_ZUSTAND = {'NEU': 3, 'GEPRUEFT': 4, 'WARTET': 5, 'ENTWURF': 6, 'ABGESCHLOSSEN': 7, 'VERWORFEN': 7, 'GESPERRT': 3, 'FEHLER': 3}


def leitfaden():
    return [dict(s) for s in LEITFADEN]


def schritt(nr):
    return next((s for s in LEITFADEN if s['nr'] == nr), None)


ZUSTAENDE = {
    'NEU': ('Angelegt, noch nicht geprüft.', 'Station 02: Anfrage eintragen, optional ein .md/.txt aus dem Projekt wählen, Zweck und verantwortliche Person setzen, dann „Datenschutz prüfen“.', 'pruefen'),
    'GEPRUEFT': ('Geprüft – wartet auf deine Freigabe.', 'Station 03: Empfehlung lesen, erlaubten Weg wählen und freigeben. Die Freigabe ist eine Entscheidung mit Bindung.', 'freigeben'),
    'GESPERRT': ('Gesperrt – Hard Block, kein Modellaufruf.', 'Den Grund (Schlüssel, Kartenprüfwert, Anweisung im Dokument) aus dem Text entfernen und neu beginnen. Es gibt kein „trotzdem“.', 'neu'),
    'WARTET': ('Freigabe liegt vor – wartet auf deine Antwort.', 'Entscheidungen: „freigeben und anwenden“ oder „ablehnen“. Erst dann läuft das Modell.', 'entscheiden'),
    'ENTWURF': ('Entwurf liegt vor – menschliche Prüfung (R2).', 'Station 04: Entwurf lesen; „Geprüft“ markieren oder „Verwerfen“. Kein Versand – das ist nicht Teil dieses MVP.', 'pruefung'),
    'ABGESCHLOSSEN': ('Abgeschlossen – Entwurf geprüft.', 'Nichts mehr zu tun. Der Entwurf wird am Löschdatum gelöscht.', None),
    'VERWORFEN': ('Verworfen – Entwurf und Zuordnung gelöscht.', 'Bei Bedarf einen neuen Vorgang anlegen.', 'neu'),
    'FEHLER': ('Fehler – nichts ist hinausgegangen, Mapping gelöscht.', 'Den Fehlercode ansehen (unten), den Text anpassen und neu prüfen.', 'pruefen'),
}

FEHLER = {
    'anfrage_leer': ('Die Anfrage ist leer.', 'Text in das Feld „Eingabeprompt“ eintragen.'),
    'anfrage_zu_lang': ('Die Anfrage ist länger als 20.000 Zeichen.', 'Kürzen oder in mehrere Vorgänge teilen.'),
    'dokument_nur_md_txt': ('Nur .md, .txt und .docx sind erlaubt.', 'PDF und das alte .doc sind nicht dabei. Als .docx oder .txt im Projekt ablegen.'),
    'dokument_zu_gross': ('Das Dokument ist größer als 200.000 Zeichen.', 'Den relevanten Ausschnitt als eigene Datei ablegen.'),
    'dokument_nicht_gefunden': ('Die Datei liegt nicht im Projektordner oder der Pfad zeigt hinaus.', 'Nur Dateien unterhalb des Projektordners wählen.'),
    'dokument_nicht_lesbar': ('Die Datei lässt sich nicht lesen (kein UTF-8-Text bzw. kein gültiges .docx).', 'Als UTF-8-.txt oder als .docx ohne Kennwort speichern.'),
    'zweck_unbekannt': ('Der Zweck ist nicht aus der Liste.', 'Einen Zweck aus der Auswahl nehmen (Antwortentwurf, Zusammenfassung, Übersetzung, Frage).'),
    'verantwortlich_fehlt': ('Die verantwortliche Person fehlt.', 'Namen eintragen – er ist Teil der Freigabe.'),
    'vorgang_laeuft': ('Der Vorgang wartet auf Freigabe oder hat schon einen Entwurf.', 'Erst ablehnen, verwerfen oder prüfen, dann neu prüfen.'),
    'nicht_geprueft': ('Der Vorgang ist noch nicht geprüft.', 'Station 02: „Datenschutz prüfen“.'),
    'weg_nicht_erlaubt': ('Dieser Weg ist für die Einstufung nicht erlaubt.', 'Nur die angebotenen Wege sind freigebbar – meist „nur lokal“.'),
    'weg_offener_als_wunsch': ('Der Weg ist offener als dein Wunsch.', 'Du darfst restriktiver wählen, nie offener (K-03). Wunsch auf Cloud stellen, falls das gemeint war.'),
    'bindung_passt_nicht': ('Die Freigabe passt nicht mehr zum Vorgang.', 'Etwas wurde geändert (Anfrage, Dokument, Weg, Zweck, Person). Neu prüfen und neu freigeben.'),
    'mapping_fehlt': ('Die Zuordnung der Platzhalter ist weg – meist nach einem Neustart.', 'Neu prüfen; die Zuordnung lebt nur im laufenden Prozess.'),
    'antwort_leer': ('Das Modell hat nichts geantwortet.', 'Modell prüfen (Maschinenraum), erneut freigeben.'),
    'entwurf_zurueckhalten': ('Der Entwurf enthielt einen Schlüssel oder Kartenprüfwert und wurde zurückgehalten (Recheck 3).', 'Entwurf verwerfen; die Anfrage auf solche Werte prüfen.'),
    'kein_entwurf': ('Es gibt keinen Entwurf zu prüfen.', 'Erst freigeben, dann prüfen.'),
    'B6_PSEUDO_RECHECK_FAILED': ('Die Pseudonymisierung ließ Originalwerte stehen (Recheck 1) – ein Cloudweg wäre erlaubt, deshalb Stopp.', 'Wunsch auf „lokal“ stellen oder die betroffenen Werte entfernen.'),
    'B6_PSEUDO_HARD_BLOCK': ('Der Text enthält etwas, das nie pseudonymisiert wird (Schlüssel, Anweisung an die KI).', 'Den Grund entfernen, neu prüfen.'),
    'captain_approval_required': ('Die Freigabe fehlt.', 'In den Entscheidungen beantworten.'),
    'captain_approval_invalid': ('Das Freigabe-Token passt nicht (abgelaufen oder für etwas anderes).', 'Neu freigeben.'),
    'no_project': ('Kein Projekt aktiv.', 'Erst ein Projekt anlegen oder wählen; Dokumente kommen aus dem Projektordner.'),
}

BEGRIFFE = {
    'pseudonymisierung': ('Pseudonymisierung ist keine Anonymisierung.', 'Namen, E-Mails, Telefonnummern, Kundennummern werden durch typisierte Platzhalter wie <PERSON_001> ersetzt; die Zuordnung bleibt nur im Prozess und wird nach der Rückübersetzung gelöscht. Pseudonymisierte Daten bleiben personenbezogen (Erwägungsgrund 26 DSGVO) – deshalb R-01: ohne Rechtsgrundlage kein Cloudweg.'),
    'schutzklasse': ('SK0 öffentlich · SK1 intern · SK2 vertraulich · SK3 streng vertraulich.', 'Die Klasse ist die höchste der getroffenen Merkmale; kein Merkmal = SK0. Schutzklassen sind keine EU-AI-Act-Risikoklassen.'),
    'bindung': ('Die Freigabe ist an alles gebunden, was entschieden wurde.', 'Hash über Anfrage, Dokument, Policyversion, Klasse, Merkmale, Weg, Übergabeprompt, Zweck und verantwortliche Person. Ändert sich eines, gilt die Freigabe nicht mehr.'),
    'recheck': ('Drei Rechecks.', '1 nach der Pseudonymisierung (keine Originale im Übergabeprompt), 2 nach der Antwort vor der Rückübersetzung (keine Originale, keine fremden Platzhalter), 3 nach der Rückübersetzung (kein Schlüssel, kein Kartenprüfwert im Entwurf).'),
    'cloud': ('Cloud geht nur über einen eingeschalteten Anbieter (config/cloud_providers.yaml, Schlüssel per Umgebungsvariable); ohne Anbieter ist sie simuliert.', 'Was den Rechner verlässt, entscheidet das Regelwerk: Personenbezug (R-01) nie. CLOUD_ALLOWED und AUTO_APPROVED sind Policy-Ergebnisse; die Übermittlung passiert erst nach der Freigabe.'),
    'hard block': ('Ein Hard Block ist nicht übersteuerbar.', 'Zugangsdaten, Schlüssel, Kartendaten mit Prüfwert (R-07) und Anweisungen an die KI im Dokument (R-08): kein Modellaufruf, auch nicht lokal.'),
    'review': ('R1 = Prüfung vor dem Modellaufruf, R2 = Prüfung des Entwurfs.', 'Bei HUMAN_REVIEW_REQUIRED ist deine Freigabe (R1) die Prüfung. R2 ist Station 04: „Geprüft“ oder „Verwerfen“. Es gibt keine Rollen – der Nutzer ist die Prüfung.'),
    'versand': ('Kein Versand.', 'Der Entwurf bleibt hier. Versand ist nicht Teil dieses MVP.'),
    'zweck': ('Der Zweck ist Teil der Freigabe.', 'Antwortentwurf, Zusammenfassung, Übersetzung oder Frage an die Wissensbasis (Vorgehen v2, Aufgabenart). Ein anderer Zweck ist eine andere Freigabe.'),
    'löschdatum': ('Entwürfe werden am Löschdatum gelöscht (F-04).', 'Standard aus local_config/gateway/vorgaben.yaml; beim Start und bei jedem Blick auf die Liste werden abgelaufene Entwürfe gelöscht (Audit GW_ENTWURF_GELOESCHT).'),
}

_WORT = re.compile(r'[a-zäöüß0-9\-]{3,}')
_STOPP = frozenset('''wie wird das der die den dem des ist was ein eine einen und mit ich mir mich mein meine im in zu zum zur nicht bitte kann
kannst gibt gibts auf für fuer von bei oder sich sind war hat habe haben dann noch auch nur hier dort dieser diese dieses jetzt mal doch
schon sehr soll sollte muss müssen muessen darf dürfen wo wer wann warum wieso weshalb welche welcher welches alles über ueber nach
vor aus als wenn dass etwas nichts einem einer eines ihm ihr ihre sein seine man uns wir ihr sie es da denn also ganz gut
gateway vorgang vorgänge vorgaenge sedra guppi modul shell'''.split())
# Wörter, unter denen ein Mensch nach einer Regel oder einem Merkmal fragt – stehen mit in den Stichworten
SYNONYME = {'P01': 'name namen e-mail email telefon telefonnummer kundennummer adresse anschrift personenbezug personenbezogen',
            'P02': 'gesundheit krank krankheit diagnose religion gewerkschaft sexualität herkunft biometrie genetik besondere kategorie art 9',
            'P03': 'straftat strafrecht strafsache vorstrafe ermittlung art 10', 'P04': 'steuer-id steuernummer ausweis ausweisnummer sozialversicherung rentenversicherung reisepass kennung',
            'F01': 'iban konto kontonummer bankverbindung bank überweisung ueberweisung', 'F02': 'kreditkarte karte kartennummer pan',
            'F03': 'cvv prüfwert pruefwert kartenprüfwert', 'S01': 'passwort kennwort schlüssel schluessel token api-key apikey zugangsdaten secret geheim',
            'S02': 'injection prompt anweisung anweisungen ignoriere steuerzeichen unsichtbar versteckt', 'G01': 'kalkulation preis preise marge einkaufspreis geschäftsgeheimnis betriebsgeheimnis',
            'G02': 'nda vertraulichkeitsvereinbarung geheimhaltung', 'R01': 'rechtsstreit gericht verfahren klage anwalt prozess',
            'V01': 'kind kinder minderjährig minderjaehrig jugendlich schüler schueler alter', 'A01': 'hochrisiko ai act anhang iii personal bewerbung kredit bildung strafverfolgung'}
_GW_ID = re.compile(r'\bGW-\d{8}-[0-9A-F]{6}\b')
_NAECHSTES = ('nächst', 'naechst', 'weiter', 'was muss ich', 'was soll ich', 'wie geht es', 'wie gehts', 'was jetzt', 'was nun', 'als nächstes', 'als naechstes', 'was tun')
_FEHLER = ('fehler', 'falsch', 'warum', 'wieso', 'weshalb', 'gesperrt', 'problem', 'geht nicht', 'funktioniert nicht', 'stimmt nicht')
_PRUEFEN = ('prüf', 'pruef', 'check', 'scan', 'was ist in diesem text', 'in diesem text', 'im text', 'folgenden text', 'diesen text')
_STAND = ('status', 'stand', 'übersicht', 'uebersicht', 'welche vorgänge', 'welche vorgaenge', 'liste', 'offen')
_ABLAUF = ('schritt', 'wie lege ich', 'wie geht das', 'wie funktioniert', 'ablauf', 'anleitung', 'leitfaden', 'schritte', 'wie arbeite', 'wie benutze', 'wie nutze', 'von anfang', 'ablegen', 'wo liegt', 'wo finde')
GATEWAY_WORTE = ('gateway', 'gate way', 'vorgang', 'vorgänge', 'vorgaenge', 'schutzklasse', 'merkmal', 'regel', 'pseudonym', 'platzhalter', 'entwurf',
                 'datenschutz', 'dsgvo', 'ai act', 'cloud', 'hard block', 'recheck', 'bindung', 'einstufung', 'freigeben', 'freigabe', 'sk0', 'sk1', 'sk2', 'sk3')


def _woerter(text):
    return [w for w in _WORT.findall((text or '').lower()) if w not in _STOPP]


class GatewayWissen:
    """Regelbuch + Zustände + Fehler + Begriffe in SQLite, Live-Zustand aus dem GateWay. Antworten ohne Modell."""

    def __init__(self, root: Path, gateway=None):
        self.root = Path(root) / 'local_config' / 'gateway'
        self.gw = gateway
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'wissen.sqlite'
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute('CREATE TABLE IF NOT EXISTS wissen (id TEXT PRIMARY KEY, art TEXT, titel TEXT, text TEXT, tun TEXT, stichworte TEXT, version TEXT)')
        self._db.execute('CREATE TABLE IF NOT EXISTS eigene (id INTEGER PRIMARY KEY AUTOINCREMENT, frage TEXT, antwort TEXT, erstellt TEXT)')
        self._fuellen()

    # ------------------------------------------------------------------ Inhalt
    def _fuellen(self):
        rows = []
        for rid in klassen.REGELN:
            r = klassen.regel(rid)
            rows.append((rid, 'regel', f'{rid} – {r["kategorie"]}', f'{r["satz"]} Bezug: {r["bezug"]}. Lokal: {r["lokal"]} · Cloud: {r["cloud"]} · Prüfung: {r["review"]}.',
                         r['tun'], ' '.join([rid, rid.replace('-', ''), r['merkmal'], r['kategorie'], r['bezug'], SYNONYME.get(r['merkmal'], ''), 'regel']).lower()))
        for m, (name, kl) in klassen.MERKMALE.items():
            rid = klassen.REGEL_VON_MERKMAL.get(m)
            rows.append((m, 'merkmal', f'{m} – {name}', f'Klasse {kl}; Regel {rid}.' + (' Von Hand zu setzen.' if m in klassen.MANUELL else ''),
                         klassen.regel(rid)['tun'] if rid else '', ' '.join([m, name, kl, rid or '', SYNONYME.get(m, ''), 'merkmal']).lower()))
        for z, (was, tun, _) in ZUSTAENDE.items():
            rows.append(('Z-' + z, 'zustand', f'Zustand {z}', was, tun, ' '.join([z, was, tun]).lower()))
        for code, (was, tun) in FEHLER.items():
            rows.append(('F-' + code, 'fehler', f'Fehler {code}', was, tun, ' '.join([code, code.replace('_', ' '), was, tun]).lower()))
        for b, (kurz, lang) in BEGRIFFE.items():
            rows.append(('B-' + b, 'begriff', b.capitalize(), kurz + ' ' + lang, '', ' '.join([b, kurz, lang]).lower()))
        for st in LEITFADEN:
            rows.append((f'L-{st["nr"]}', 'leitfaden', f'Schritt {st["nr"]} ({st["station"]}): {st["titel"]}',
                         f'Du: {st["mensch"]} Warten: {st["warten"]} Prüfen: {st["pruefen"]} Ablage: {st["ablegen"]}', st['sedra'],
                         ' '.join([st['titel'], st['station'], st['mensch'], st['pruefen'], st['ablegen'], 'leitfaden anleitung schritt']).lower()))
        rows.append(('A-ABLAUF', 'ablauf', 'Der Weg eines Vorgangs',
                     '01 Wunsch (lokal oder Cloud) → 02 Anfrage + Dokument, Zweck, Person → „Datenschutz prüfen“ (Scan, Merkmale, Klasse, Übergabeprompt mit Platzhaltern, Recheck 1) → 03 Empfehlung und Freigabe (Gate mit Bindung) → 04 Entwurf (lokal durch den Inhaltsschutz; Rechecks 2 und 3) → deine Prüfung (R2). Kein Versand.',
                     'Mit „Neuer Vorgang“ in Station 01 beginnen.', 'ablauf stationen weg vorgang anlegen neu beginnen studio flow'))
        with self._lock:
            self._db.execute('DELETE FROM wissen')
            self._db.executemany('INSERT INTO wissen VALUES (?,?,?,?,?,?,?)', [(*r, klassen.POLICY_VERSION) for r in rows])
            self._db.commit()

    def eintragen(self, frage, antwort):
        """Eigener Eintrag des Nutzers (bleibt über Neustarts). Kein Vorgangstext."""
        from datetime import datetime, timezone
        with self._lock:
            self._db.execute('INSERT INTO eigene (frage, antwort, erstellt) VALUES (?,?,?)',
                             (str(frage)[:300], str(antwort)[:2000], datetime.now(timezone.utc).isoformat(timespec='seconds')))
            self._db.commit()

    def suche(self, frage, limit=3):
        woerter = _woerter(frage)
        if not woerter:
            return []
        with self._lock:
            rows = self._db.execute('SELECT id, art, titel, text, tun, stichworte FROM wissen').fetchall()
            eigene = self._db.execute('SELECT frage, antwort FROM eigene').fetchall()
        scored = []
        low = (frage or '').lower()
        for rid, art, titel, text, tun, stich in rows:
            score = sum(2 if w in stich else 0 for w in woerter) + sum(1 for w in woerter if w in text.lower()) + sum(3 for w in woerter if w in titel.lower())
            if art == 'begriff' and score:
                score += 1
            if rid.lower() in low or rid.lower().replace('-', '') in low.replace('-', ''):
                score += 10
            if score:
                scored.append((score, {'id': rid, 'art': art, 'titel': titel, 'text': text, 'tun': tun}))
        for fr, an in eigene:
            score = sum(2 for w in woerter if w in fr.lower()) + sum(1 for w in woerter if w in an.lower())
            if score:
                scored.append((score + 1, {'id': 'eigene', 'art': 'eigene', 'titel': fr, 'text': an, 'tun': ''}))
        scored = [s for s in scored if s[0] >= 3]                # ein einzelnes Allerweltswort ist kein Treffer
        scored.sort(key=lambda s: -s[0])
        return [s[1] for s in scored[:limit]]

    # ------------------------------------------------------------------ Live-Zustand
    def vorgaenge(self):
        return self.gw.liste() if self.gw is not None else []

    def aktueller(self, frage='', vorgang_id=None):
        """Der Vorgang, um den es geht: genannt in der Frage, übergeben, sonst der jüngste, der noch nicht fertig ist."""
        if self.gw is None:
            return None
        m = _GW_ID.search(frage or '')
        vid = m.group(0) if m else vorgang_id
        if vid and vid in self.gw.vorgaenge:
            return self.gw.vorgaenge[vid]
        offen = [x for x in self.gw.vorgaenge.values() if x.zustand not in ('ABGESCHLOSSEN', 'VERWORFEN')]
        if not offen:
            return None
        return max(offen, key=lambda x: (x.erstellt, list(self.gw.vorgaenge).index(x.id)))     # der jüngste; bei gleicher Sekunde der zuletzt angelegte

    def naechster_schritt(self, v):
        if v is None:
            return ('Es gibt keinen offenen Vorgang.', ZUSTAENDE['NEU'][1].replace('Station 02', 'Station 01: „Neuer Vorgang“, dann Station 02'), 'neu')
        was, tun, aktion = ZUSTAENDE.get(v.zustand, ('Unbekannter Zustand.', 'Vorgang öffnen.', None))
        st = schritt(SCHRITT_VON_ZUSTAND.get(v.zustand, 0))
        if st:
            tun = f'Leitfaden Schritt {st["nr"]} ({st["titel"]}): ' + tun
        extra = ''
        e = v.einstufung or {}
        if v.zustand == 'GEPRUEFT' and e:
            extra = f' Einstufung {e["klasse"]} ({e["klasse_wort"]}), erlaubt: ' + (' / '.join(e['wege_wort']) or 'kein Weg') + '.' \
                    + (' Deine Freigabe ist die Prüfung (R1).' if e.get('review') == 'PENDING' else '')
        if v.zustand == 'FEHLER' and v.fehler:
            code = v.fehler.split(':', 1)[0]
            f = FEHLER.get(code) or FEHLER.get('entwurf_zurueckhalten' if code.startswith('entwurf_zurueckgehalten') else '')
            extra = f' Fehler „{v.fehler}“: ' + (f[0] + ' ' + f[1] if f else 'kein Eintrag im Regelbuch – Logbuch ansehen.')
        if v.zustand == 'GESPERRT' and e:
            extra = ' ' + ' '.join(e.get('gruende') or [])
        return (f'Vorgang „{v.titel}“ ({v.id}): {was}', tun + extra, aktion)

    # ------------------------------------------------------------------ Text prüfen
    def fehler_im_text(self, text):
        """Was die Regeln in einem Text finden – mit Regelnummer, Stelle und Abhilfe. Ruft kein Modell, speichert nichts."""
        clean = normalize(text or '').clean
        if not clean.strip():
            return {'ok': False, 'satz': 'Kein Text zum Prüfen.', 'funde': [], 'einstufung': None}
        try:
            hits = scan_content(clean)
            ok = True
        except ScanFailure as exc:
            hits, ok = [], False
        e = klassen.einstufen([(h.rule_id, h.kind) for h in hits], (), scan_ok=ok)
        funde, gesehen = [], set()
        for h in hits:
            m = klassen.merkmal_von(h.rule_id, h.kind)
            if not m or (m, h.start) in gesehen:
                continue
            gesehen.add((m, h.start))
            rid = klassen.regel_fuer(m, 'anfrage')
            r = klassen.regel(rid) if rid else None
            funde.append({'merkmal': m, 'name': klassen.MERKMALE[m][0], 'regel': rid, 'von': h.start, 'bis': h.end,
                          'ausschnitt': _ausschnitt(clean, h.start, h.end), 'tun': r['tun'] if r else ''})
        d = e.as_dict()
        if not funde and ok:
            satz = 'Die Regeln finden in diesem Text nichts (SK0). Kein Treffer heißt nicht unbedenklich – die Regeln kennen nicht alles.'
        elif not ok:
            satz = 'Der Scanner konnte den Text nicht vollständig prüfen (R-16). Ungeklärt ist keine Freigabe.'
        else:
            satz = f'{len(funde)} Fund(e) – Einstufung {d["klasse"]} ({d["klasse_wort"]}), {d["policy_wort"]}; erlaubt: ' + (' / '.join(d['wege_wort']) or 'kein Weg') + '.'
        return {'ok': ok, 'satz': satz, 'funde': funde, 'einstufung': d}

    # ------------------------------------------------------------------ die Antwort
    @staticmethod
    def zustaendig(frage, aktive_shell=None):
        low = (frage or '').lower()
        if _GW_ID.search(frage or ''):
            return True
        if any(w in low for w in GATEWAY_WORTE):
            return True
        if aktive_shell == 'gateway-studio' and (any(w in low for w in _NAECHSTES) or any(w in low for w in _FEHLER) or any(w in low for w in _PRUEFEN) or any(w in low for w in _STAND)):
            return True
        return False

    def antwort(self, frage, vorgang_id=None):
        """Eine Antwort auf eine Frage des Nutzers: Satz + Knöpfe (nichts läuft von allein)."""
        frage = str(frage or '').strip()
        low = frage.lower()
        v = self.aktueller(frage, vorgang_id)
        actions = []
        # 1) ein Text zum Prüfen in der Frage? („… in diesem Text: …“, Zeilenumbruch, oder „…“)
        text = _text_in_frage(frage)
        if text and (any(w in low for w in _PRUEFEN) or any(w in low for w in _FEHLER)):
            r = self.fehler_im_text(text)
            lines = [r['satz']]
            for f in r['funde'][:8]:
                lines.append(f'- {f["regel"]} {f["name"]} ({f["merkmal"]}) bei „{f["ausschnitt"]}“ → {f["tun"]}')
            if r['funde']:
                actions.append(self._knopf_neu('Als Vorgang prüfen'))
            return self._out('\n'.join(lines), actions, 'text')
        # 2) nächster Schritt – aber „wie lege ich an / Ablauf / ablegen“ ist eine Frage an den Leitfaden (3b), nicht nach dem nächsten Schritt
        if any(w in low for w in _NAECHSTES) and not any(w in low for w in _ABLAUF if w != 'schritt'):
            was, tun, aktion = self.naechster_schritt(v)
            actions.append(self._knopf_oeffnen(v) if v else self._knopf_neu('Neuer Vorgang'))
            return self._out(was + '\n' + tun, actions, 'schritt')
        # 3) Fehler / warum gesperrt – am aktuellen Vorgang
        if any(w in low for w in _FEHLER) and v is not None and v.zustand in ('GESPERRT', 'FEHLER', 'GEPRUEFT', 'ENTWURF', 'WARTET'):
            was, tun, _ = self.naechster_schritt(v)
            e = v.einstufung or {}
            lines = [was]
            for g in (e.get('gruende') or []):
                lines.append('- ' + g)
            for m in (e.get('merkmale') or []):
                r = klassen.regel(m['regel']) if m.get('regel') else None
                if r:
                    lines.append(f'- {m["regel"]} ({m["id"]}, gefunden in: {m["quelle"]}) → {r["tun"]}')
            lines.append(tun)
            actions.append(self._knopf_oeffnen(v))
            return self._out('\n'.join(lines), actions, 'vorgang')
        # 3b) Ablauf / Anleitung / Ablage → der Leitfaden
        if any(w in low for w in _ABLAUF):
            m = re.search(r'schritt\s*(\d)', low)
            if m and schritt(int(m.group(1))):
                st = schritt(int(m.group(1)))
                return self._out(self._schritt_text(st), [self._knopf_oeffnen(v) if v else self._knopf_neu('Zum GateWay')], 'leitfaden')
            if any(w in low for w in ('ableg', 'ablage', 'wo liegt', 'wo finde', 'ergebnis ab', 'aufbewahr', 'löschdatum', 'loeschdatum', 'gespeichert')):
                return self._out(self._schritt_text(schritt(7)), [self._knopf_oeffnen(v) if v else self._knopf_neu('Zum GateWay')], 'leitfaden')
            lines = ['So arbeitest du mit dem KI GateWay – sieben Schritte:'] + [f'{st["nr"]}. {st["titel"]} ({st["station"]}): {st["mensch"]}' for st in LEITFADEN]
            lines.append('Frag nach „Schritt 3“ für Einzelheiten; „Was muss ich als Nächstes machen?“ sagt dir den Schritt zum aktuellen Vorgang.')
            return self._out('\n'.join(lines), [self._knopf_oeffnen(v) if v else self._knopf_neu('Zum GateWay')], 'leitfaden')
        # 4) Stand / Liste
        if any(w in low for w in _STAND) and 'regel' not in low:
            rows = self.vorgaenge()
            if not rows:
                return self._out('Keine Vorgänge. ' + ZUSTAENDE['NEU'][1], [self._knopf_neu('Neuer Vorgang')], 'stand')
            lines = [f'{len(rows)} Vorgänge:'] + [f'- {r["id"]} „{r["titel"]}“: {r["zustand_wort"]}' + (f' · {r["klasse"]}' if r.get('klasse') else '') for r in rows[:10]]
            if v:
                actions.append(self._knopf_oeffnen(v))
            return self._out('\n'.join(lines), actions, 'stand')
        # 5) Frage nach einer Datenart („darf eine IBAN in die Cloud?“) → die Regelzeile dazu, eindeutig
        m = _merkmal_aus_frage(low)
        if m:
            rid = klassen.regel_fuer(m, 'anfrage' if m == 'S02' else '')
            r = klassen.regel(rid)
            lines = [f'{rid} – {r["kategorie"]} ({m}): {r["satz"]}', f'Lokal: {r["lokal"]} · Cloud: {r["cloud"]} · Prüfung: {r["review"]}.',
                     'Was tun: ' + r['tun'], 'Bezug (Annahme, keine Rechtsprüfung): ' + r['bezug']]
            return self._out('\n'.join(lines), actions, 'wissen')
        # 6) Regelbuch, Begriffe, Fehlercodes, Leitfaden, eigene Einträge
        treffer = self.suche(frage, 3)
        if treffer:
            t = treffer[0]
            lines = [t['titel'] + ': ' + t['text']]
            if t['tun']:
                lines.append('Was tun: ' + t['tun'])
            if len(treffer) > 1:
                lines.append('Siehe auch: ' + ' · '.join(x['titel'] for x in treffer[1:]))
            return self._out('\n'.join(lines), actions, 'wissen')
        was, tun, _ = self.naechster_schritt(v)
        return self._out('Dazu steht nichts im Regelbuch. ' + was + ' ' + tun, [self._knopf_oeffnen(v) if v else self._knopf_neu('Neuer Vorgang')], 'unbekannt')

    def close(self):
        with self._lock:
            try: self._db.close()
            except Exception: pass

    @staticmethod
    def _schritt_text(st):
        return (f'Schritt {st["nr"]} ({st["station"]}) – {st["titel"]}\nDu: {st["mensch"]}\nWarten: {st["warten"]}\nPrüfen: {st["pruefen"]}\n'
                f'Ablage: {st["ablegen"]}\nSEDRA: {st["sedra"]}')

    @staticmethod
    def _out(reply, actions, art):
        return {'reply': reply, 'ui_actions': [a for a in actions if a], 'art': art, 'quelle': 'gateway-wissen ' + klassen.POLICY_VERSION}

    @staticmethod
    def _knopf_oeffnen(v):
        return {'kind': 'open', 'object': {'type': 'gateway', 'id': v.id, 'title': v.titel[:60]}, 'title': 'Vorgang ' + v.titel[:40]}

    @staticmethod
    def _knopf_neu(label):
        return {'kind': 'open', 'object': {'type': 'gateway', 'id': 'alle', 'title': 'KI GateWay', 'collection': True}, 'title': label}


def _merkmal_aus_frage(low):
    """Nennt die Frage eine Datenart (Synonym, Merkmal-ID) – aber keine Regelnummer (die geht über die Suche)?"""
    if re.search(r'\br-?\d{2}\b', low):
        return None
    woerter = set(_WORT.findall(low))
    for m, syn in SYNONYME.items():
        if m.lower() in woerter:
            return m
    best = None
    for m, syn in SYNONYME.items():
        treffer = [w for w in syn.split() if len(w) >= 4 and w in woerter]
        if treffer and (best is None or len(treffer) > best[0]):
            best = (len(treffer), m)
    return best[1] if best else None


def _ausschnitt(text, a, b, rand=12):
    s = text[max(0, a - rand):min(len(text), b + rand)].replace('\n', ' ')
    return ('…' if a > rand else '') + s + ('…' if b + rand < len(text) else '')


def _text_in_frage(frage):
    """Der Teil der Frage, der geprüft werden soll: nach dem ersten Doppelpunkt, nach einem Zeilenumbruch oder in „…“/"…"."""
    m = re.search(r'[„"»]([^“"«]{8,})[“"«]', frage)
    if m:
        return m.group(1)
    if '\n' in frage:
        head, rest = frage.split('\n', 1)
        if len(rest.strip()) >= 8:
            return rest.strip()
    if ':' in frage:
        head, rest = frage.split(':', 1)
        if len(rest.strip()) >= 8 and len(head) <= 120:
            return rest.strip()
    return ''
