"""Markdown-Export mit Token-Verbrauch (03.11.2026, Wunsch des Captains im MasterChat): gleich unter der Überschrift steht „Token: N Antworten · X eingehend · Y erzeugt“
über die ganze Sitzung (nicht nur den heutigen Tag), Tausender mit Punkt."""
import unittest

from sedra_runtime.harness.export import markdown


def sitzung(*token):
    return {'titel': 'Test-Sitzung', 'modell': 'm', 'kopf': {'projekt': 'p', 'angelegt': '2026-11-01T12:00:00'},
            'eintraege': [{'typ': 'modell', 'zeit': f'2026-11-0{n + 1}T12:01:00', 'token': {'ein': ein, 'aus': aus}, 'zuege': 1} for n, (ein, aus) in enumerate(token)]}


class ExportToken(unittest.TestCase):
    def test_die_zeile_steht_gleich_unter_der_ueberschrift(self):
        zeilen = markdown(sitzung((100, 200), (50, 150)), 'S-12345678').splitlines()
        self.assertEqual(zeilen[0], '# Test-Sitzung')
        self.assertEqual(zeilen[2], 'Token: 2 Antworten · 150 eingehend · 350 erzeugt')
        self.assertEqual(zeilen[4], 'Modell: m', 'die Modellzeile steht unter der Token-Zeile')
        self.assertTrue(zeilen[5].startswith('Sitzung S-12345678'))

    def test_summe_ueber_alle_tage_und_tausenderpunkt(self):
        md = markdown(sitzung((20000, 3000), (11400, 1200)), 'S-12345678')
        self.assertIn('Token: 2 Antworten · 31.400 eingehend · 4.200 erzeugt', md)

    def test_ohne_modellantworten_null(self):
        self.assertIn('Token: 0 Antworten · 0 eingehend · 0 erzeugt', markdown({'titel': 'Leer', 'kopf': {}, 'eintraege': []}, 'S-00000001'))

    def test_modell_zeile_ist_unter_token_zeile(self):
        s = dict(sitzung((3, 2), (2, 3)), modell='GPT-4o', kopf={'angelegt': '2026-11-03T10:00:00', 'vorlage': 'Standard'})
        zeilen = markdown(s, 'S-00000123', 'Test-Projekt').splitlines()
        self.assertEqual(zeilen[2], 'Token: 2 Antworten · 5 eingehend · 5 erzeugt')
        self.assertEqual(zeilen[3], '')
        self.assertEqual(zeilen[4], 'Modell: GPT-4o')
        self.assertEqual(zeilen[5][:len('Sitzung S-00000123')], 'Sitzung S-00000123')
        self.assertNotIn(' · Modell ', zeilen[5], 'das Modell steht nicht mehr in der Sitzungszeile')

    def test_ohne_modell_keine_modellzeile_und_keine_doppelte_leerzeile(self):
        s = dict(sitzung((1, 1)), modell=None)
        zeilen = markdown(s, 'S-00000001').splitlines()
        self.assertEqual(zeilen[3], '')
        self.assertTrue(zeilen[4].startswith('Sitzung S-00000001'), 'direkt nach der Leerzeile, ohne zweite')
        self.assertFalse([z for z in zeilen if z.startswith('Modell')])


if __name__ == '__main__':
    unittest.main()
