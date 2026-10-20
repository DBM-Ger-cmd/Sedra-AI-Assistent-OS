"""Beweis der Aufteilung: lokale KI filtert Personendaten, nur das Bereinigte darf in die Cloud-KI (Auswertung).

Die Prüfwerte (was verschwinden muss, was erhalten bleiben muss) stehen NUR hier. Ans Modell geht ausschließlich der
Eingabetext, nie eine Erwartung. Die Erwartungen sind also dem Modell unbekannt – das ist der „versteckte“ Teil.

Zwei Beine:
- lokal (Pflicht, wenn der llama-server läuft): das Modell auf GUPPI_BEWEIS_LOKAL_URL (Standard 127.0.0.1:8089) bereinigt jeden Fall.
  Danach prüft ein fester Code (nicht das Modell) den Ausgabetext: keine Kennung aus dem Prüfwert darf übrig bleiben.
- Cloud (nur mit GUPPI_BEWEIS_ANBIETER=<id> und eingeschaltetem Anbieter in config/cloud_providers.yaml): die Cloud-KI wertet
  NUR den bereinigten Text aus. Ohne Anbieter wird dieses Bein übersprungen – es geht nie personenbezogener Text hinaus.

Ausführen (aus dem runtime-Ordner, mit PYTHONPATH=src;tests):
  py -m pytest -q -s tests/test_ki_aufteilung_beweis.py
"""
import os
import re
import unittest

from guppi_runtime.models.llamacpp import LlamaCppServerAdapter
from guppi_runtime.models.base import ModelAdapterError

LOKAL_URL = os.environ.get('GUPPI_BEWEIS_LOKAL_URL', 'http://127.0.0.1:8089')
CLOUD_ANBIETER = os.environ.get('GUPPI_BEWEIS_ANBIETER', '')

# Eingaben (synthetisch, keine echten Personen) und die verdeckten Prüfwerte
FAELLE = [
    {
        'name': 'kontakt_mit_kennungen',
        'text': ('Max Muster (max.muster@beispiel.test) fragt nach dem Stand von NORD-42. Kundennummer K-1042. '
                 'Er möchte am Montag antworten.'),
        'verschwinden': ['Max Muster', 'max.muster@beispiel.test', 'K-1042', 'Muster'],
        'erhalten': ['NORD-42'],
    },
    {
        'name': 'telefon_und_anschrift',
        'text': ('Lena Beispiel, Telefon +49 170 1234567, wohnt in der Musterstraße 12, 10115 Berlin. '
                 'Sie fragt nach der Lieferung von Auftrag AUF-778.'),
        'verschwinden': ['Lena Beispiel', '+49 170 1234567', '1234567', 'Musterstraße 12', '10115 Berlin', 'Lena'],
        'erhalten': ['AUF-778'],
    },
    {
        'name': 'ohne_personenbezug',
        'text': 'Einkaufspreis 120 EUR, Marge 30 %, Verkaufspreis 170 EUR. Bitte eine Übersicht für den Kunden.',
        'verschwinden': [],
        'erhalten': ['120', '170', '30'],
    },
]

FILTER_PROMPT = ('Du bereinigst einen Text. Entferne alle personenbezogenen Angaben: Namen, E-Mail-Adressen, Telefonnummern, '
                 'Anschriften und Kundennummern. Ersetze sie durch allgemeine Wörter wie „die Person“ oder „der Kunde“. '
                 'Alle übrigen Angaben (Beträge, Projekt- und Auftragsnummern, Aussagen) bleiben unverändert. '
                 'Gib nur den bereinigten Text zurück, ohne Erklärung.')


def _lokal_erreichbar():
    try:
        return LlamaCppServerAdapter(base_url=LOKAL_URL, timeout=5).health()
    except (ModelAdapterError, ValueError):
        return False


def bereinige_lokal(text):
    """Das lokale Modell filtert. Gibt nur den Ausgabetext zurück."""
    adapter = LlamaCppServerAdapter(base_url=LOKAL_URL, timeout=300)
    # Ohne Begrenzung denkt das Reasoning-Modell lange (300-s-Timeout, real 08:51 und 12:02). Die Bereinigung braucht kein Nachdenken.
    out = adapter.chat([{'role': 'system', 'content': FILTER_PROMPT}, {'role': 'user', 'content': text}], temperature=0,
                       reasoning_effort='none', max_tokens=800)
    return out.get('content') or ''


def uebrig_geblieben(ausgabe, fall):
    """Fester Code, kein Modell: welche verbotenen Kennungen stehen noch im Text (Groß-/Kleinschreibung egal)."""
    return [w for w in fall['verschwinden'] if re.search(re.escape(w), ausgabe, re.IGNORECASE)]


def fehlt(ausgabe, fall):
    return [w for w in fall['erhalten'] if w not in ausgabe]


@unittest.skipUnless(_lokal_erreichbar(), f'llama-server unter {LOKAL_URL} antwortet nicht')
class LokalerFilter(unittest.TestCase):
    def test_personenbezug_verschwindet_und_fakten_bleiben(self):
        ergebnis = []
        for fall in FAELLE:
            ausgabe = bereinige_lokal(fall['text'])
            rest, weg = uebrig_geblieben(ausgabe, fall), fehlt(ausgabe, fall)
            ergebnis.append((fall['name'], rest, weg))
            print(f"\n[{fall['name']}] ausgabe: {ausgabe!r}\n  übrig: {rest}  fehlt: {weg}")
        for name, rest, weg in ergebnis:
            self.assertEqual(rest, [], f'{name}: Personenbezug blieb übrig')
            self.assertEqual(weg, [], f'{name}: Fakt ging verloren')


@unittest.skipUnless(CLOUD_ANBIETER, 'kein Cloud-Anbieter gesetzt (GUPPI_BEWEIS_ANBIETER): das Cloud-Bein läuft nicht')
class CloudAuswertung(unittest.TestCase):
    """Nur wenn ein Anbieter ausdrücklich eingeschaltet und gesetzt ist. Die Cloud bekommt ausschließlich den bereinigten Text."""

    def test_cloud_sieht_nur_das_bereinigte(self):
        raise unittest.SkipTest('Cloud-Bein noch nicht verdrahtet: wartet auf Freigabe, Anbieter einzuschalten')


if __name__ == '__main__':
    unittest.main()
