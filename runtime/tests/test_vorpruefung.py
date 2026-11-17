import json
import unittest

from sedra_runtime.core.vorpruefung import vorpruefen

ADRESSE = 'Rechnung an Havelland Hospitality GmbH, Musterstraße 1, 12345 Berlin. Kontakt: anna.beispiel@example.org'


class VorpruefungTest(unittest.TestCase):
    def test_sauberer_text_ist_ok(self):
        r = vorpruefen('Position 1: 20 m2 Fliesen verlegen, 910,00 EUR', 'cloud', 'nvidia/x')
        self.assertEqual(r['stufe'], 'ok')
        self.assertFalse(r['blockt_spaeter'])

    def test_personenbezug_in_der_cloud_warnt_und_empfiehlt_lokal(self):
        r = vorpruefen(ADRESSE, 'cloud', 'nvidia/x')
        self.assertEqual(r['stufe'], 'warnung')
        self.assertTrue(r['blockt_spaeter'])
        self.assertIn('lokal', r['empfehlung'].lower())

    def test_lokal_blockt_nicht(self):
        r = vorpruefen(ADRESSE, 'local', 'llama')
        self.assertEqual(r['stufe'], 'ok')              # lokal bleibt die Notiz still
        self.assertTrue(r['funde'])
        self.assertFalse(r['blockt_spaeter'])

    def test_ergebnis_enthaelt_nie_den_text(self):
        raw = json.dumps(vorpruefen(ADRESSE, 'cloud', 'nvidia/x'), ensure_ascii=False)
        for geheim in ('Musterstraße', 'anna.beispiel', 'Havelland'):
            self.assertNotIn(geheim, raw)

    def test_wirft_nie_und_beraet_nur(self):
        for eingabe in (None, '', '   ', 5):
            self.assertTrue(vorpruefen(eingabe, 'cloud')['beratend'])
        self.assertEqual(vorpruefen('x', 'mars')['stufe'], 'hinweis')


if __name__ == '__main__':
    unittest.main()


class ModusDatenschutzTest(unittest.TestCase):
    def test_aus_blockt_personenbezug_nicht_mehr(self):
        r = vorpruefen(ADRESSE, 'cloud', 'nvidia/x', datenschutz_eu=False)
        self.assertEqual(r['stufe'], 'hinweis')
        self.assertFalse(r['blockt_spaeter'])
        self.assertTrue(r['beobachtet'])

    def test_aus_laesst_schluessel_gesperrt(self):
        r = vorpruefen('AKIAIOSFODNN7EXAMPLE', 'cloud', 'nvidia/x', datenschutz_eu=False)
        self.assertEqual(r['stufe'], 'warnung')

    def test_guard_aus_und_wieder_an(self):
        import tempfile, pathlib
        from sedra_runtime.core.content_guard import ContentGuard, ContentGuardStop
        d = pathlib.Path(tempfile.mkdtemp()) / 'ds.json'
        g = ContentGuard(cloud_enabled=True, state_path=d)
        self.assertTrue(g.datenschutz_eu)
        msgs = [{'role': 'user', 'content': ADRESSE}]
        with self.assertRaises(ContentGuardStop):
            g.call(msgs, model='m', route='cloud', complete=lambda m: 'ok')
        class A:  # Logbuch-Attrappe
            def append(self, *a, **k): pass
        g.audit = A()
        g.set_datenschutz_eu(False)
        self.assertEqual(g.call(msgs, model='m', route='cloud', complete=lambda m: 'ok').status, 'OK')
        self.assertFalse(ContentGuard(cloud_enabled=True, state_path=d).datenschutz_eu)   # bleibt gespeichert
        g.set_datenschutz_eu(True)
        with self.assertRaises(ContentGuardStop):
            g.call(msgs, model='m', route='cloud', complete=lambda m: 'ok')

    def test_ohne_logbuch_wird_nicht_gelockert(self):
        from sedra_runtime.core.content_guard import ContentGuard
        with self.assertRaises(RuntimeError):
            ContentGuard(cloud_enabled=True).set_datenschutz_eu(False)


if __name__ == '__main__' and False:
    pass


def _pdf(inhalt):
    """Ein gueltiges einseitiges PDF mit Xref - pypdf liest den Text wirklich."""
    nl = bytes([10])
    objs = [b'<</Type/Catalog/Pages 2 0 R>>', b'<</Type/Pages/Kids[3 0 R]/Count 1>>',
            b'<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>',
            b'<</Length %d>>' % len(inhalt) + nl + b'stream' + nl + inhalt + nl + b'endstream',
            b'<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>']
    out, offs = b'%PDF-1.4' + nl, []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b'%d 0 obj' % i + nl + o + nl + b'endobj' + nl
    x = len(out)
    out += b'xref' + nl + b'0 6' + nl + b'0000000000 65535 f ' + nl + b''.join(b'%010d 00000 n ' % o + nl for o in offs)
    return out + b'trailer' + nl + b'<</Size 6/Root 1 0 R>>' + nl + b'startxref' + nl + b'%d' % x + nl + b'%%EOF'


class StudioVerbTest(unittest.TestCase):
    def _hub(self, root, events):
        from types import SimpleNamespace
        return SimpleNamespace(project_root=root, content_guard=None,
                               runtime=SimpleNamespace(audit=SimpleNamespace(append=lambda *a, **k: events.append(a))))

    def test_verb_prueft_abgelegte_pdf_beratend_ohne_text(self):
        import tempfile, pathlib
        from sedra_runtime.workflows import desk
        from sedra_runtime.workflows.lokal_daten import Eingaben
        root = pathlib.Path(tempfile.mkdtemp())
        pdf = _pdf(b'BT /F1 10 Tf 40 800 Td (Projektbuero: Musterstrasse 1, 12345 Berlin, anna.beispiel@example.org) Tj ET')
        ref = Eingaben(root).speichern(pdf)
        events = []
        out = desk._vorpruefung(self._hub(root, events), None, {'datei': ref, 'provider': 'nvidia', 'model': 'nvidia/x'})
        self.assertTrue(out['beratend'])
        self.assertNotIn('anna.beispiel', json.dumps(out, ensure_ascii=False))
        self.assertEqual(out['route'], 'cloud')
        self.assertEqual(out['stufe'], 'warnung')        # die Adresse in der PDF wurde wirklich gelesen und erkannt
        self.assertTrue(out['blockt_spaeter'])

    def test_fehlende_datei_wirft_nicht(self):
        import tempfile, pathlib
        from sedra_runtime.workflows import desk
        out = desk._vorpruefung(self._hub(pathlib.Path(tempfile.mkdtemp()), []), None, {'datei': 'x' * 64, 'provider': 'nvidia'})
        self.assertEqual(out['stufe'], 'hinweis')
