"""Die Delegations-Karte der Harness-Shell (delegation.js, SPEC_DELEGATION_IM_GESPRAECH_v1 T6): Zeilen je Helfer, Kopf, Dauer,
Helfer unter der Hauptsitzung in der Seitenleiste, Texte in beiden Sprachen, und dass die Karte nichts entscheidet."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from sedra_runtime.desk import gateway

SHELL = Path(gateway.__file__).resolve().parents[1] / 'uix' / 'shells' / 'harness'
SKRIPT = SHELL / 'delegation.js'
TEXTE = SHELL / 'strings_delegation.js'
STAND = {'delegation': 'T-0000ABCD', 'eltern': 'S-00000001', 'fertig': False, 'helfer': [
    {'nr': 1, 'sitzung_id': 'S-0000000A', 'rolle': 'Leser', 'auftrag_kurz': 'Lies eins.', 'zustand': 'laeuft', 'zuege': 2, 'token': {'ein': 900, 'aus': 100}, 'sekunden': 75, 'karte_id': None, 'grund': None},
    {'nr': 2, 'sitzung_id': 'S-0000000B', 'rolle': 'Schreiber', 'auftrag_kurz': 'Ändere zwei.', 'zustand': 'freigabe', 'zuege': 1, 'token': {'ein': 10, 'aus': 5}, 'sekunden': 9, 'karte_id': 'K-00000001', 'grund': None},
    {'nr': 3, 'sitzung_id': None, 'rolle': 'Prüfer', 'auftrag_kurz': 'Prüfe drei.', 'zustand': 'wartet', 'zuege': 0, 'token': {'ein': 0, 'aus': 0}, 'sekunden': 0, 'karte_id': None, 'grund': None}]}


def node(code, *args):
    aus = subprocess.run(['node', '-e', code, *map(str, args)], capture_output=True, text=True, timeout=60, encoding='utf-8')
    if aus.returncode:
        raise AssertionError(aus.stderr)
    return json.loads(aus.stdout)


class Delegation(unittest.TestCase):
    def test_shell_laedt_texte_skript_und_stil(self):
        text = (SHELL / 'shell.yaml').read_text(encoding='utf-8')
        self.assertLess(text.index('strings_delegation.js'), text.index('i18n.js'))
        self.assertLess(text.index('delegation.js, shell.js]'), text.index('css:'))
        self.assertIn('delegation.css', text)
        self.assertIn('H.delegation.mount(this)', (SHELL / 'shell.js').read_text(encoding='utf-8'))

    def test_texte_haben_in_beiden_sprachen_dieselben_schluessel(self):
        de, en = TEXTE.read_text(encoding='utf-8').split('root.sedraI18nStrings.en = ')
        schluessel = lambda t: sorted(re.findall(r'^\s+(dg_[a-z_]+):', t, re.M))
        self.assertEqual(schluessel(de), schluessel(en))
        for k in re.findall(r"T\('(dg_[a-z_]+)'\)", SKRIPT.read_text(encoding='utf-8')):       # ganze Schlüssel; `dg_z_` + Zustand prüft die Schleife darunter
            self.assertIn(k + ':', de)
        for z in ('wartet', 'laeuft', 'freigabe', 'fertig', 'gescheitert', 'angehalten'):
            self.assertIn(f'dg_z_{z}:', de)

    def test_karte_entscheidet_nichts(self):                          # DG-11, DG-14
        text = SKRIPT.read_text(encoding='utf-8')
        for verboten in ('/api/harness/karten', 'entscheiden(', '/api/decisions', 'https://', 'http://', 'innerHTML'):
            self.assertNotIn(verboten, text)
        self.assertIn('S.shellApi.decide()', text)                    # ohne Kennung und Weg: öffnet nur den Posteingang
        self.assertEqual(re.findall(r"S\.api\('([^']+)'", text), ['/api/harness/team/', '/api/harness/team'])

    @unittest.skipUnless(shutil.which('node'), 'node fehlt')
    def test_zeilen_kopf_und_dauer(self):                             # DG-10
        code = ("const D=require(process.argv[1]);const s=JSON.parse(process.argv[2]);"
                "const f=JSON.parse(JSON.stringify(s));f.helfer.forEach(h=>h.zustand='fertig');f.helfer[2].zustand='gescheitert';f.helfer[2].grund='Zeitlimit';"
                "console.log(JSON.stringify({z:D.zeilen(s),k:D.kopf(s),zf:D.zeilen(f),kf:D.kopf(f),d:[D.dauer(0),D.dauer(59.4),D.dauer(60),D.dauer(125)]}));")
        o = node(code, SKRIPT, json.dumps(STAND))
        z = o['z']
        self.assertEqual([x['ton'] for x in z], ['aktiv', 'warn', 'still'])
        self.assertEqual([x['anhalten'] for x in z], [True, True, True])
        self.assertEqual([x['freigabe'] for x in z], [False, True, False])
        self.assertEqual([x['verlauf'] for x in z], [True, True, False], 'ein wartender Helfer hat noch keine Sitzung')
        self.assertEqual(z[0]['messung'], 'dg_zuege · dg_token · 1:15 min')          # ohne Sprachdatei bleibt der Schlüssel stehen: die Funktion ist rein
        self.assertEqual((o['k']['aktiv'], o['k']['gesamt'], o['k']['fertig']), (3, 3, False))
        self.assertTrue(o['kf']['fertig'])
        self.assertEqual([x['anhalten'] for x in o['zf']], [False, False, False])
        self.assertEqual(o['zf'][2]['grund'], 'Zeitlimit'); self.assertEqual(o['zf'][2]['ton'], 'bad')
        self.assertEqual(o['d'], ['0 s', '59 s', '1:00 min', '2:05 min'])

    @unittest.skipUnless(shutil.which('node'), 'node fehlt')
    def test_helfer_stehen_unter_ihrer_hauptsitzung(self):            # DG-02
        code = ("global.window=global;global.localStorage={getItem:()=>null,setItem(){}};require(process.argv[1]);"
                "const L=window.sedraHarness.seitenleiste;const s=(id,e)=>({id,eltern:e});"
                "console.log(JSON.stringify([L.helferEinordnen([s('h1','a'),s('b'),s('a'),s('h2','a'),s('x','weg')]).map(x=>x.id),L.helferEinordnen([s('a'),s('b')]).map(x=>x.id)]));")
        self.assertEqual(node(code, SHELL / 'seitenleiste.js'), [['b', 'a', 'h1', 'h2', 'x'], ['a', 'b']])
        self.assertIn("' hs-sz-helfer'", (SHELL / 'seite.js').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
