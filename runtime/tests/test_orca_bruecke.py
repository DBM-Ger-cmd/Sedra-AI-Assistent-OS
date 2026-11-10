"""Orca-Brücke: SSE-Zerlegung, Antwort mit Karte (nie von selbst bestätigt), Adresse und Token aus der Serverausgabe."""
import unittest

from sedra_runtime.harness import orca_bruecke as ob


class Sse(unittest.TestCase):
    def test_zerlegt_ereignisse_und_ignoriert_herzschlag(self):
        zeilen = [': ping\n', 'id: 1\n', 'event: text.ungeprueft\n', 'data: {"stueck": "Hal"}\n', '\n', 'id: 2\n', 'event: ende\n', 'data: {"ende": "antwort"}\n', '\n']
        self.assertEqual(list(ob.sse_ereignisse(zeilen)), [('1', 'text.ungeprueft', {'stueck': 'Hal'}), ('2', 'ende', {'ende': 'antwort'})])

    def test_url_muster(self):
        t = ob.URL_MUSTER.search('SEDRA Desktop (UIX): http://127.0.0.1:5123/#abc_DEF-9')
        self.assertEqual((t.group(1), t.group(2)), ('5123', 'abc_DEF-9'))


class FakeClient:
    def __init__(self):
        self.posts = []

    def strom(self, aid):
        if aid == 'A-1':
            yield '1', 'text.ungeprueft', {'stueck': 'Ich '}
            yield '2', 'karte', {'karte_id': 'K-1', 'werkzeug': 'datei_schreiben', 'ziel': 'x.txt', 'stufe': 'B'}
            yield '3', 'ende', {'ende': 'wartet'}
        else:
            yield '1', 'text.geprueft', {'text': 'fertig'}
            yield '2', 'ende', {'ende': 'antwort'}

    def aufruf(self, methode, pfad, nutzlast=None):
        self.posts.append((methode, pfad, nutzlast))
        return 200, {'antwort_id': 'A-2'}


class Antwort(unittest.TestCase):
    def test_karte_wird_nur_so_beantwortet_wie_gewaehlt_und_antwort_geht_weiter(self):
        c, zeilen = FakeClient(), []
        ende = ob.antwort_zeigen(c, 'A-1', ob.karte_immer_ablehnen, lambda *a, **k: zeilen.append(''.join(map(str, a))))
        self.assertEqual(c.posts, [('POST', '/api/harness/karten/K-1', {'weg': 'ablehnen'})])
        self.assertEqual(ende, 'antwort')
        self.assertIn('fertig', ''.join(zeilen))


class Tastatur(unittest.TestCase):
    def _wahl(self, eingaben):
        it = iter(eingaben)
        return ob.karte_per_tastatur({}, lambda _p: next(it))

    def test_leerzeile_und_unbekanntes_fragen_nach(self):
        self.assertEqual(self._wahl(['', 'vielleicht', 'J']), 'erlauben')
        self.assertEqual(self._wahl(['', 's']), 'sitzung')

    def test_nein_und_ende_der_eingabe_lehnen_ab(self):
        self.assertEqual(self._wahl(['', 'n']), 'ablehnen')

        def eof(_p):
            raise EOFError
        self.assertEqual(ob.karte_per_tastatur({}, eof), 'ablehnen')


if __name__ == '__main__':
    unittest.main()
