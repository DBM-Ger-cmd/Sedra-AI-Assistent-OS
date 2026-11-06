"""K5-4 (SPEC_WISSEN_KERN_v1 WK-20; G2 K5 §2.3, D-K5-3): PDF, Excel und PowerPoint werden in einem eigenen Prozess zu Markdown – zuerst
MarkItDown, für PDF sonst pypdf; fehlt beides, steht die Datei mit dem Installationsbefehl im Stand; eine PDF ohne Textschicht ist
`wis_kein_text`; die Zeitgrenze greift. Echte Umwandlungen nur, wenn die Pakete hier installiert sind (sonst übersprungen); die Fälle
„fehlt“, „Zeitgrenze“ und „Stand“ laufen immer. Kein Modell, kein Netz, keine GPU."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guppi_runtime.wissen.leser import extern
from guppi_runtime.wissen.speicher import satz
from wissen_fixture import FakeEmbedServer, freigeben, oeffnen

DA = {n: importlib.util.find_spec(n) is not None for n in ('pypdf', 'markitdown', 'openpyxl', 'pptx')}
OHNE_BEIDE = {'SEDRA_UMWANDELN_OHNE': 'markitdown,pypdf'}


def pdf(pfad, text=None):
    """Eine kleine PDF mit einer Seite, wahlweise mit Text (Helvetica, ASCII) – von Hand, ohne Paket."""
    inhalt = (f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET' if text else '').encode('latin-1')
    objekte = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
               b'<< /Length ' + str(len(inhalt)).encode() + b' >>\nstream\n' + inhalt + b'\nendstream',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    out, stellen = bytearray(b'%PDF-1.4\n'), []
    for i, o in enumerate(objekte, 1):
        stellen.append(len(out))
        out += f'{i} 0 obj\n'.encode() + o + b'\nendobj\n'
    xref = len(out)
    out += f'xref\n0 {len(objekte) + 1}\n0000000000 65535 f \n'.encode() + b''.join(f'{s:010d} 00000 n \n'.encode() for s in stellen)
    out += f'trailer\n<< /Size {len(objekte) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    Path(pfad).write_bytes(bytes(out))
    return pfad


class Umwandeln(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.d = Path(t.name)

    @unittest.skipUnless(DA['pypdf'], 'pypdf fehlt')
    def test_pdf_mit_pypdf_wenn_markitdown_fehlt(self):
        p = pdf(self.d / 'v.pdf', 'Kuendigungsfrist drei Monate Kranich')
        with mock.patch.dict(os.environ, {'SEDRA_UMWANDELN_OHNE': 'markitdown'}):
            md = extern.markdown(p)
        self.assertTrue(md.startswith('## Seite 1'))
        self.assertIn('Kuendigungsfrist drei Monate Kranich', md)

    @unittest.skipUnless(DA['markitdown'], 'markitdown fehlt')
    def test_pdf_mit_markitdown(self):
        md = extern.markdown(pdf(self.d / 'v.pdf', 'Kuendigungsfrist drei Monate Kranich'))
        self.assertIn('Kuendigungsfrist drei Monate Kranich', md)

    @unittest.skipUnless(DA['markitdown'] and DA['openpyxl'], 'markitdown/openpyxl fehlt')
    def test_excel_mit_markitdown(self):
        import openpyxl
        wb = openpyxl.Workbook()
        wb.active.title = 'Kunden'
        wb.active.append(['Kunde', 'Ort'])
        wb.active.append(['Kranich AG', 'Bremen'])
        wb.save(self.d / 'k.xlsx')
        md = extern.markdown(self.d / 'k.xlsx')
        self.assertIn('Kranich AG', md)
        self.assertIn('Kunden', md, 'das Blatt wird zum Kopf')

    @unittest.skipUnless(DA['markitdown'] and DA['pptx'], 'markitdown/python-pptx fehlt')
    def test_powerpoint_mit_markitdown(self):
        from pptx import Presentation
        pr = Presentation()
        folie = pr.slides.add_slide(pr.slide_layouts[1])
        folie.shapes.title.text = 'Quartalsziel'
        folie.placeholders[1].text = 'Umsatz in Bremen verdoppeln'
        pr.save(self.d / 'f.pptx')
        self.assertIn('Umsatz in Bremen verdoppeln', extern.markdown(self.d / 'f.pptx'))

    @unittest.skipUnless(DA['pypdf'] or DA['markitdown'], 'kein Werkzeug für PDF')
    def test_pdf_ohne_textschicht(self):
        with self.assertRaisesRegex(ValueError, 'wis_kein_text'):
            extern.markdown(pdf(self.d / 'scan.pdf'))

    def test_ohne_werkzeug_und_mit_zeitgrenze(self):
        p = pdf(self.d / 'v.pdf', 'Text')
        with mock.patch.dict(os.environ, OHNE_BEIDE):
            with self.assertRaisesRegex(ValueError, 'wis_hilfswerkzeug_fehlt'):
                extern.markdown(p)
        with self.assertRaisesRegex(ValueError, 'wis_umwandeln_zeitgrenze'):
            extern.markdown(p, zeitgrenze=0.001)
        self.assertIn('pip install "markitdown[pdf,xlsx,pptx]"', satz('wis_hilfswerkzeug_fehlt'), 'der Satz nennt den Befehl')

    def test_kaputte_datei_ist_ein_fehler_kein_absturz(self):
        (self.d / 'k.pdf').write_bytes(b'%PDF-1.4 kaputt')
        with self.assertRaises(ValueError) as ctx:
            extern.markdown(self.d / 'k.pdf')
        self.assertIn(str(ctx.exception), ('wis_umwandeln_fehler', 'wis_kein_text', 'wis_hilfswerkzeug_fehlt'))


class ImStand(unittest.TestCase):
    """Im Ordner: fehlt das Werkzeug, stehen PDF und Excel als übersprungen mit Grund da; Markdown daneben wird aufgenommen."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wissen-k5-umw-')
        self.addCleanup(self.tmp.cleanup)
        self.srv = FakeEmbedServer(lazy=True)
        self.srv.__enter__()
        self.addCleanup(self.srv.__exit__, None, None, None)
        self.ordner = Path(self.tmp.name) / 'ablage'
        self.ordner.mkdir()
        pdf(self.ordner / 'vertrag.pdf', 'Kuendigungsfrist drei Monate Kranich')
        (self.ordner / 'notiz.md').write_text('# Notiz\n\nDie Ablage liegt im Keller.\n', encoding='utf-8')
        projekt = Path(self.tmp.name) / 'projekt'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'wissen_wurzeln.yaml').write_text(
            f"wurzeln:\n  - {{id: ablage, pfad: '{self.ordner.as_posix()}', name: Ablage}}\n", encoding='utf-8')
        self.sp = oeffnen(self.tmp.name, self.srv.port, server=self.srv)
        self.addCleanup(self.sp.schliessen)

    def test_fehlendes_werkzeug_steht_mit_grund_da(self):
        q = freigeben(self.sp, 'dokumente', '.', wurzel='w:ablage', muster='*.md, *.pdf')
        with mock.patch.dict(os.environ, OHNE_BEIDE):
            self.sp.abgleich()
        st = self.sp.dateien_stand(q['id'])
        self.assertEqual({d['datei']: (d['zustand'], d['grund']) for d in st['dateien']},
                         {'notiz.md': ('aufgenommen', None), 'vertrag.pdf': ('uebersprungen', 'wis_hilfswerkzeug_fehlt')})

    @unittest.skipUnless(DA['pypdf'] or DA['markitdown'], 'kein Werkzeug für PDF')
    def test_pdf_wird_gefunden(self):
        q = freigeben(self.sp, 'dokumente', '.', wurzel='w:ablage', muster='*.pdf')
        self.sp.abgleich()
        self.assertEqual(self.sp.dateien_stand(q['id'])['summen']['aufgenommen'], 1)
        t = self.sp.suche('Kuendigungsfrist Kranich', leser={'art': 'captain', 'stufe': 6, 'projekt': None, 'agent_id': None})['treffer']
        self.assertEqual(t[0]['datei'], 'vertrag.pdf')


if __name__ == '__main__':
    unittest.main()
