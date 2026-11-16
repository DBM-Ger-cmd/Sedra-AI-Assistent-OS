"""Die 3D-Bühne der Harness-Shell (buehne3d.js): das Modell liegt bei der Shell, der Server liefert es aus,
der Leser versteht es, und nichts kommt aus dem Netz."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from sedra_runtime.desk import gateway

SHELL = Path(gateway.__file__).resolve().parents[1] / 'uix' / 'shells' / 'harness'
SKRIPT = SHELL / 'buehne3d.js'
MODELL = SHELL / 'seedrache-web.glb'


class Buehne3d(unittest.TestCase):
    def test_modell_liegt_bei_der_shell_und_ist_ein_glb(self):
        kopf = MODELL.read_bytes()[:12]
        self.assertEqual(kopf[:4], b'glTF')
        self.assertEqual(int.from_bytes(kopf[8:12], 'little'), MODELL.stat().st_size)

    def test_server_kennt_den_dateityp(self):
        self.assertTrue(gateway.SERVE_NAME.match(MODELL.name))
        self.assertEqual(gateway.SERVE_TYPES['glb'], 'model/gltf-binary')
        self.assertFalse(gateway.SERVE_NAME.match('../seedrache-web.glb'))

    def test_shell_laedt_skript_und_stil(self):
        text = (SHELL / 'shell.yaml').read_text(encoding='utf-8')
        self.assertLess(text.index('buehne3d.js'), text.index(' shell.js]'))          # vor shell.js, das zuletzt lädt
        self.assertIn('buehne3d.css', text)

    def test_nichts_aus_dem_netz(self):
        text = SKRIPT.read_text(encoding='utf-8')
        self.assertIsNone(re.search(r'https?://', text))
        self.assertIn("'/uix/shells/harness/seedrache-web.glb'", text)

    def test_rueckfall_und_ruhe_regeln_stehen_im_skript(self):
        text = SKRIPT.read_text(encoding='utf-8')
        for wort in ('prefers-reduced-motion', 'visibilitychange', 'IntersectionObserver', 'webglcontextlost', 'WEBGL_lose_context', 'DPR_MAX'):
            self.assertIn(wort, text)

    def test_flug_nimmt_keine_eingaben_und_kennt_drei_modi(self):
        text = SKRIPT.read_text(encoding='utf-8')
        self.assertIn("const MODI = ['hintergrund', 'buehne', 'aus'];", text)
        self.assertIn('RUHE_MS', text)
        stil = (SHELL / 'buehne3d.css').read_text(encoding='utf-8')
        regel = re.search(r'\.hs-grund\{([^}]*)\}', stil).group(1)
        self.assertIn('pointer-events:none', regel)

    @unittest.skipUnless(shutil.which('node'), 'node fehlt')
    def test_leser_versteht_das_modell(self):
        code = ("const B=require(process.argv[1]);const b=require('fs').readFileSync(process.argv[2]);"
                "const m=B.teileVon(B.glbLesen(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)));"
                "console.log(JSON.stringify({teile:m.teile.length,halb:m.halb,mitte:m.mitte}));")
        aus = subprocess.run(['node', '-e', code, str(SKRIPT), str(MODELL)], capture_output=True, text=True, timeout=60)
        self.assertEqual(aus.returncode, 0, aus.stderr)
        wert = json.loads(aus.stdout)
        self.assertEqual(wert['teile'], 14)
        self.assertTrue(all(h > 0 for h in wert['halb']))

    @unittest.skipUnless(shutil.which('node'), 'node fehlt')
    def test_leser_lehnt_fremdes_ab(self):
        code = ("const B=require(process.argv[1]);try{B.glbLesen(new ArrayBuffer(64));console.log('ok');}"
                "catch(e){console.log(e.message);}")
        aus = subprocess.run(['node', '-e', code, str(SKRIPT)], capture_output=True, text=True, timeout=60)
        self.assertEqual(aus.stdout.strip(), 'kein_glb')


if __name__ == '__main__':
    unittest.main()
