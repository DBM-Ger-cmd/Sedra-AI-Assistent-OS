"""Der Avatar der Harness-Shell (avatar.js): Rang der Anlässe, Platz der Sprechblase, Texte in beiden Sprachen,
und dass er nur liest (keine Freigabe, kein Start, kein Netz)."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from sedra_runtime.desk import gateway

SHELL = Path(gateway.__file__).resolve().parents[1] / 'uix' / 'shells' / 'harness'
SKRIPT = SHELL / 'avatar.js'
TEXTE = SHELL / 'strings_avatar.js'


def node(code, *args):
    aus = subprocess.run(['node', '-e', code, *map(str, args)], capture_output=True, text=True, timeout=60, encoding='utf-8')
    if aus.returncode:
        raise AssertionError(aus.stderr)
    return json.loads(aus.stdout)


class Avatar(unittest.TestCase):
    def test_shell_laedt_texte_vor_der_sprache_und_das_skript_vor_der_shell(self):
        text = (SHELL / 'shell.yaml').read_text(encoding='utf-8')
        self.assertLess(text.index('strings_avatar.js'), text.index('i18n.js'))
        self.assertLess(text.index(' avatar.js,'), text.index(' shell.js]'))          # vor shell.js, das zuletzt lädt; dazwischen dürfen weitere Skripte stehen
        self.assertIn('avatar.css', text)
        self.assertIn('H.avatar.mount(this)', (SHELL / 'shell.js').read_text(encoding='utf-8'))

    def test_texte_haben_in_beiden_sprachen_dieselben_schluessel(self):
        text = TEXTE.read_text(encoding='utf-8')
        de, en = text.split('root.sedraI18nStrings.en = ')
        schluessel = lambda t: sorted(re.findall(r'^\s+(av_[a-z_]+):', t, re.M))
        self.assertEqual(schluessel(de), schluessel(en))
        self.assertGreaterEqual(len(schluessel(de)), 10)
        for k in re.findall(r"T\([^)]*?'(av_[a-z_]+)'", SKRIPT.read_text(encoding='utf-8')):
            self.assertIn(k + ':', de)

    def test_avatar_liest_nur(self):
        text = SKRIPT.read_text(encoding='utf-8')
        for verboten in ('fetch(', 'XMLHttpRequest', 'entscheiden(', '.post(', 'https://', 'http://'):
            self.assertNotIn(verboten, text)
        self.assertIn('S.shellApi.decide()', text)                    # ohne Kennung und Weg: öffnet nur den Posteingang

    @unittest.skipUnless(shutil.which('node'), 'node fehlt')
    def test_rang_der_anlaesse(self):
        code = ("const A=require(process.argv[1]);const f=z=>{const h=A.anlass(z);return h?h.id:null;};"
                "console.log(JSON.stringify(["
                "f({freigaben:2,lauf:{id:'l1',name:'x',ok:false},modell:false,leer:true}),"
                "f({freigaben:0,lauf:{id:'l1',name:'x',ok:false},modell:false,leer:true}),"
                "f({freigaben:0,lauf:null,modell:false,leer:true}),"
                "f({freigaben:0,lauf:null,modell:true,leer:true}),"
                "f({freigaben:0,lauf:null,modell:true,leer:false}),"
                "A.anlass({freigaben:0,lauf:{id:'l1',name:'x',ok:false},modell:true,leer:false}).knopf]));")
        self.assertEqual(node(code, SKRIPT), ['freigabe:2', 'lauf:l1', 'modell', 'erste', None, ''])

    @unittest.skipUnless(shutil.which('node'), 'node fehlt')
    def test_sprechblase_bleibt_im_fenster(self):
        code = ("const A=require(process.argv[1]);const F={breite:1200,hoehe:800};"
                "const r=(l,t,w,h)=>({left:l,top:t,width:w,height:h,right:l+w,bottom:t+h});"
                "console.log(JSON.stringify([A.platz(r(600,500,80,30),F,90),A.platz(r(1150,770,40,24),F,90),A.platz(r(0,10,40,24),F,90),A.platz(r(300,400,800,160),F,90)]));")
        mitte, rechts_unten, links_oben, breit = node(code, SKRIPT)
        self.assertEqual(mitte['oben'], 500 - 90 - 12)                # über dem Anker
        self.assertLessEqual(rechts_unten['links'] + 300, 1200 - 12)
        self.assertGreaterEqual(links_oben['links'], 12)
        self.assertEqual(links_oben['oben'], 10 + 24 + 12)            # oben kein Platz: darunter
        self.assertEqual(breit['links'], 300 + 800 - 300)             # breiter Anker: rechtsbündig, das Feld bleibt frei


if __name__ == '__main__':
    unittest.main()
