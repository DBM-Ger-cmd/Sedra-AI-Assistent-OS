"""K5-3 und K5-5 (SPEC_WISSEN_KERN_v1 WK-20, WK-25; G2 K5 §2.3, §2.8): Word wird zu Markdown mit Köpfen und Tabellenzeilen, CSV zu
„Spalte: Wert“ in Blöcken (Trennzeichen, BOM, Windows-1252); der Adapter `dokumente` nimmt md, txt, docx und csv unter einem freigegebenen
Ordner auf, ein kaputtes Word steht mit Grund im Stand, die Grenze gilt je Art und lässt sich lokal nur senken; das GateWay liest Word
unverändert über den Kern. Kein Modell, kein Netz, keine GPU."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from guppi_runtime.gateway import dokumente as gw_dokumente
from guppi_runtime.wissen import adapter, konfig
from guppi_runtime.wissen.leser import docx as docx_leser, tabelle
from wissen_fixture import FakeEmbedServer, freigeben, oeffnen

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def absatz(text, stil=None):
    p = f'<w:pPr><w:pStyle w:val="{stil}"/></w:pPr>' if stil else ''
    return f'<w:p>{p}<w:r><w:t>{text}</w:t></w:r></w:p>'


def word(pfad, *bloecke):
    xml = f'<?xml version="1.0" encoding="UTF-8"?><w:document {NS}><w:body>{"".join(bloecke)}</w:body></w:document>'
    with zipfile.ZipFile(pfad, 'w') as z:
        z.writestr('word/document.xml', xml)
    return pfad


TABELLE = ('<w:tbl><w:tr><w:tc>' + absatz('Posten') + '</w:tc><w:tc>' + absatz('Betrag') + '</w:tc></w:tr>'
           '<w:tr><w:tc>' + absatz('Wartung') + '</w:tc><w:tc>' + absatz('120 EUR') + '</w:tc></w:tr></w:tbl>')


class Leser(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.d = Path(t.name)

    def test_word_wird_markdown_mit_koepfen_und_tabelle(self):
        p = word(self.d / 'v.docx', absatz('Rahmenvertrag', 'Title'), absatz('Laufzeit', 'Heading1'), absatz('Zwei Jahre ab Unterschrift.'),
                 absatz('Kündigung', 'berschrift2'), absatz('Drei Monate zum Quartal.'), TABELLE, absatz(''))
        md = docx_leser.markdown(p)
        self.assertEqual(md.split('\n\n'), ['# Rahmenvertrag', '# Laufzeit', 'Zwei Jahre ab Unterschrift.', '## Kündigung', 'Drei Monate zum Quartal.',
                                            'Posten | Betrag\nWartung | 120 EUR'])
        self.assertIn('Wartung', docx_leser.text(p), 'die Form des GateWay bleibt Text')

    def test_kaputtes_word_und_zu_grosses_archiv(self):
        (self.d / 'k.docx').write_bytes(b'kein zip')
        with self.assertRaisesRegex(ValueError, 'wis_docx_nicht_lesbar'):
            docx_leser.markdown(self.d / 'k.docx')
        with zipfile.ZipFile(self.d / 'ohne.docx', 'w') as z:
            z.writestr('anderes.xml', '<x/>')
        with self.assertRaisesRegex(ValueError, 'wis_docx_nicht_lesbar'):
            docx_leser.markdown(self.d / 'ohne.docx')

    def test_csv_trenner_kodierung_und_bloecke(self):
        (self.d / 'a.csv').write_bytes('Kunde;Ort;Umsatz\nMüller GmbH;Köln;1.200\nSchmidt;;800\n'.encode('cp1252'))
        md = tabelle.markdown(self.d / 'a.csv')
        self.assertIn('Spalten: Kunde, Ort, Umsatz', md)
        self.assertIn('- Kunde: Müller GmbH; Ort: Köln; Umsatz: 1.200', md)
        self.assertIn('- Kunde: Schmidt; Umsatz: 800', md, 'leere Werte fallen weg')
        (self.d / 'b.csv').write_bytes(('﻿a,b\n' + ''.join(f'{i},x{i}\n' for i in range(60))).encode('utf-8'))
        md = tabelle.markdown(self.d / 'b.csv')
        self.assertEqual([z for z in md.split('\n\n') if z.startswith('## ')], ['## Zeilen 2–26', '## Zeilen 27–51', '## Zeilen 52–61'])
        self.assertTrue(md.startswith('# b.csv\n\nSpalten: a, b'), 'BOM entfernt')
        (self.d / 'leer.csv').write_text('', encoding='utf-8')
        self.assertEqual(tabelle.markdown(self.d / 'leer.csv'), '')

    def test_gateway_liest_word_unveraendert(self):
        p = word(self.d / 'g.docx', absatz('Auftrag AUF-778 ist offen.'))
        self.assertEqual(gw_dokumente.lies_datei(p), 'Auftrag AUF-778 ist offen.')
        (self.d / 'k.docx').write_bytes(b'x')
        with self.assertRaises(gw_dokumente.DokumentFehler):
            gw_dokumente.lies_datei(self.d / 'k.docx')


class Grenzen(unittest.TestCase):
    def test_je_art_aus_dem_paket_lokal_nur_senken(self):
        with tempfile.TemporaryDirectory() as tmp:
            paket = Path(__file__).resolve().parents[1] / 'config' / 'wissen.yaml'
            lokal = Path(tmp) / 'wissen.yaml'
            lokal.write_text('wissen:\n  aufnahme:\n    je_art: {md: 1000, docx: 999999999999}\n', encoding='utf-8')
            k = konfig.load(paket, lokal)
            self.assertEqual((k.je_art['md'], k.je_art['docx'], k.je_art['csv']), (1000, 50_000_000, 50_000_000), 'senken ja, heben nein')
            lokal.write_text('wissen:\n  aufnahme:\n    je_art: {".md": 5}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'je_art'):
                konfig.load(paket, lokal)

    def test_adapter_grenze_je_art(self):
        with tempfile.TemporaryDirectory() as tmp:
            ad = adapter.adapter_fuer('dokumente', repo_root=tmp, projekt_root=tmp, datei_max_bytes=10, je_art={'md': 1000})
            self.assertEqual((ad.grenze_fuer(Path('a.md')), ad.grenze_fuer(Path('a.csv'))), (1000, 10))


class Dokumente(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wissen-k5-dok-')
        self.addCleanup(self.tmp.cleanup)
        self.srv = FakeEmbedServer(lazy=True)
        self.srv.__enter__()
        self.addCleanup(self.srv.__exit__, None, None, None)
        self.ordner = Path(self.tmp.name) / 'ablage'
        self.ordner.mkdir()
        word(self.ordner / 'vertrag.docx', absatz('Laufzeit', 'Heading1'), absatz('Der Vertrag mit der Firma Kranich läuft zwei Jahre.'))
        (self.ordner / 'kunden.csv').write_text('Kunde;Ort\nKranich AG;Bremen\n', encoding='utf-8')
        (self.ordner / 'notiz.md').write_text('# Notiz\n\n## Ablage\n\nDie Ablage liegt im Keller.\n', encoding='utf-8')
        (self.ordner / 'kaputt.docx').write_bytes(b'kein zip')
        (self.ordner / 'bild.png').write_bytes(b'\x89PNG')
        projekt = Path(self.tmp.name) / 'projekt'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'wissen_wurzeln.yaml').write_text(
            f"wurzeln:\n  - {{id: ablage, pfad: '{self.ordner.as_posix()}', name: Ablage}}\n", encoding='utf-8')
        self.sp = oeffnen(self.tmp.name, self.srv.port, server=self.srv)
        self.addCleanup(self.sp.schliessen)

    def test_word_csv_und_markdown_aus_einem_ordner(self):
        q = freigeben(self.sp, 'dokumente', '.', wurzel='w:ablage', muster='*.md, *.docx, *.csv')
        self.sp.abgleich()
        st = self.sp.dateien_stand(q['id'])
        self.assertEqual({d['datei']: d['zustand'] for d in st['dateien']},
                         {'vertrag.docx': 'aufgenommen', 'kunden.csv': 'aufgenommen', 'notiz.md': 'aufgenommen', 'kaputt.docx': 'uebersprungen'})
        self.assertEqual([d['grund'] for d in st['dateien'] if d['datei'] == 'kaputt.docx'], ['wis_docx_nicht_lesbar'])
        leser = {'art': 'captain', 'stufe': 6, 'projekt': None, 'agent_id': None}
        t = self.sp.suche('Kranich Vertrag Laufzeit', leser=leser)['treffer']
        self.assertEqual(t[0]['datei'], 'vertrag.docx')
        self.assertIn('Laufzeit', t[0]['stelle'], 'die Überschrift aus Word steht in der Stelle')
        self.assertIn('kunden.csv', [x['datei'] for x in self.sp.suche('Bremen', leser=leser)['treffer']])

    def test_muster_nur_erlaubte_arten(self):
        with self.assertRaisesRegex(ValueError, 'wis_dateiart_nicht_erlaubt'):
            freigeben(self.sp, 'dokumente', '.', wurzel='w:ablage', muster='*.png')
        with self.assertRaisesRegex(ValueError, 'wis_dateiart_nicht_erlaubt'):
            freigeben(self.sp, 'markdown', '.', wurzel='w:ablage', muster='*.docx')

    def test_zu_grosse_datei_der_art(self):
        self.sp.konfig.je_art = dict(self.sp.konfig.je_art, csv=10)
        q = freigeben(self.sp, 'dokumente', '.', wurzel='w:ablage', muster='*.csv')
        self.sp.abgleich()
        self.assertEqual([(d['datei'], d['grund']) for d in self.sp.dateien_stand(q['id'], zustand='uebersprungen')['dateien']],
                         [('kunden.csv', 'wis_datei_zu_gross')])


if __name__ == '__main__':
    unittest.main()
