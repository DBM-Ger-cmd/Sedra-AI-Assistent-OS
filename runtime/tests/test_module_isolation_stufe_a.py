"""Stufe A der Modul-Isolation (Plan docs/PLAN_ISOLATION_UND_UPDATE_2026-10-19.md, Abschnitt 3):
der Kern-Zugang gibt Modulen keinen Token und keinen Zugang mit fremder Kennung; der Loader entfernt die globale Kopie."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'ui'
NODE = shutil.which('node')


def run_node(script):
    out = subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=60)
    return out.stdout.strip(), out.stderr.strip()


@unittest.skipIf(NODE is None, 'node ist nicht installiert')
class ApiOhneToken(unittest.TestCase):
    def setUp(self):
        self.api = json.dumps(str(UI / 'api.js'))

    def harness(self, body):
        # api.js in einer kleinen Umgebung laden: Adresse mit Token, fetch wird aufgezeichnet
        return ("const fs=require('fs'); const vm=require('vm'); const calls=[];\n"
                "const ctx={location:{hash:'#GEHEIM', origin:'http://x', pathname:'/', search:''},\n"
                "  fetch:async(p,o)=>{calls.push({p, h:o.headers}); return {ok:true,status:200,url:p,json:async()=>({})};},\n"
                "  EventSource:function(u){this.url=u;}, encodeURIComponent, decodeURIComponent, Object, Promise, JSON};\n"
                "ctx.window=ctx; vm.createContext(ctx);\n"
                "vm.runInContext(fs.readFileSync(" + self_api_literal() + ",'utf8'), ctx);\n" + body)

    def test_the_api_object_has_no_token_and_no_raw_call(self):
        out, err = run_node(self.harness("console.log(JSON.stringify(Object.keys(ctx.sedraApi).sort()));"))
        self.assertEqual(out, '["api","events","forModule"]', err)

    def test_a_module_only_reaches_the_api_with_its_own_id(self):
        body = ("const f=ctx.sedraApi.forModule({kind:'tool',id:'gateway'});\n"
                "f('/api/gateway/vorgaenge').then(()=>{ console.log(calls[0].h['X-SEDRA-Tool'], calls[0].h['X-GUPPI-Token']); });")
        out, err = run_node(self.harness(body))
        self.assertEqual(out, 'gateway GEHEIM', err)

    def test_the_event_stream_is_offered_without_showing_the_token(self):
        body = "const s=ctx.sedraApi.events(); console.log(s.url.indexOf('token=GEHEIM')>0, Object.keys(s).length);"
        out, err = run_node(self.harness(body))
        self.assertEqual(out, 'true 1', err)


class LoaderEntferntDieKopie(unittest.TestCase):
    def test_the_loader_takes_the_core_api_and_removes_the_global_copy(self):
        text = (UI / 'loader.js').read_text(encoding='utf-8')
        self.assertIn('const kern = root.sedraApi;', text)
        self.assertIn('delete root.sedraApi;', text)

    def test_no_script_reads_the_token_from_the_api_object(self):
        for js in UI.glob('*.js'):
            if js.name == 'api.js': continue
            self.assertNotIn('sedraApi.token', js.read_text(encoding='utf-8'), js.name)


def self_api_literal():
    return json.dumps(str(UI / 'api.js'))


if __name__ == '__main__':
    unittest.main()
