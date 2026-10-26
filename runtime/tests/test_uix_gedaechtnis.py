"""Gedächtnis der Oberfläche auf dem Server (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §9.2, §10; Abnahme A10, A17, A18, A19, A20).

Der reine Teil (`desk/arbeitsstand.py`) mit Schein-Uhr, dann die Routen über HTTP: Shells melden den Arbeitsstand, Werkzeuge lesen
nur ihre eigene Ablage, der Gesprächsverlauf läuft über die Routen des Gesprächs, „Gedächtnis leeren“ schreibt nur Zahlen ins Audit."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from guppi_runtime.desk import arbeitsstand as A
from guppi_runtime.desk.gateway import check_tool
from guppi_runtime.uix_server import UIXHub, make_server
from host_isolation import setUpModule, tearDownModule  # noqa: F401

ARCH = Path(__file__).resolve().parents[2] / 'architecture/GUPPI_Architecture_v1.17_RUNTIME_SYNC'


class Uhr:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


def audit_lesen(hub):
    path = hub.runtime.audit.path
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()] if path.exists() else []


def obj(t, i, **k):
    return dict({'type': t, 'id': i, 'title': f'{t} {i}'}, **k)


class Arbeitsstand(unittest.TestCase):
    def setUp(self):
        self.uhr = Uhr(); self.g = A.Gedaechtnis(self.uhr)

    def test_melden_und_uebernehmen(self):
        self.g.melden([obj('wissen', 'speicher', view='suche'), obj('task', 'M-1')], vorn='wissen:speicher', shell='cockpit')
        st = self.g.arbeitsstand()
        self.assertEqual([o['type'] + ':' + o['id'] for o in st['offen']], ['wissen:speicher', 'task:M-1'])
        self.assertEqual(st['vorn'], 'wissen:speicher'); self.assertEqual(st['shell'], 'cockpit')
        self.assertEqual(st['offen'][0]['view'], 'suche')

    def test_nicht_gezeichnetes_bleibt_stehen(self):
        """A20: Eine Shell, die ein Objekt nicht zeichnen kann, nennt es nicht – es bleibt trotzdem im Arbeitsstand."""
        self.g.melden([obj('task', 'M-1'), obj('gateway', 'alle')], vorn='gateway:alle')
        self.g.melden([obj('task', 'M-1')], vorn='task:M-1', shell='fisch')
        keys = [o['type'] + ':' + o['id'] for o in self.g.arbeitsstand()['offen']]
        self.assertEqual(keys, ['task:M-1', 'gateway:alle'])

    def test_schliessen_vergisst_objekt_und_ablage(self):
        """A18: Schließen in irgendeiner Shell löscht das Objekt und die Ablage aller Werkzeuge daran."""
        self.g.melden([obj('wissen', 'speicher'), obj('task', 'M-1')])
        self.g.ablage_schreiben('wissen', 'wissen:speicher', {'frage': 'Wo steht D7.4?'})
        self.g.ablage_schreiben('fundstelle', 'wissen:speicher', {'id': 'W0123456789'})
        self.g.ablage_schreiben('task', 'task:M-1', {'x': 1})
        self.g.melden([obj('task', 'M-1')], geschlossen=['wissen:speicher'])
        self.assertEqual(self.g.ablage_lesen('wissen', 'wissen:speicher')['werte'], {})
        self.assertEqual(self.g.ablage_lesen('fundstelle', 'wissen:speicher')['werte'], {})
        self.assertEqual(self.g.ablage_lesen('task', 'task:M-1')['werte'], {'x': 1})
        self.assertEqual([o['id'] for o in self.g.arbeitsstand()['offen']], ['M-1'])

    def test_vergessen_nach_ruhezeit(self):
        self.g.melden([obj('task', 'M-1')]); self.g.ablage_schreiben('task', 'task:M-1', {'x': 1})
        self.uhr.t += A.RUHE_S - 1
        self.assertEqual(self.g.ablage_lesen('task', 'task:M-1')['werte'], {'x': 1})   # Lesen zählt als Zugriff
        self.uhr.t += A.RUHE_S + 1
        self.assertEqual(self.g.ablage_lesen('task', 'task:M-1')['werte'], {})
        self.assertEqual(self.g.arbeitsstand()['offen'], [])

    def test_grenzen(self):
        with self.assertRaisesRegex(ValueError, 'ablage_zu_gross'):
            self.g.ablage_schreiben('wissen', 'wissen:speicher', {'t': 'x' * (A.MAX_EINTRAG + 1)})
        with self.assertRaisesRegex(ValueError, 'objekt_ungueltig'):
            self.g.ablage_schreiben('wissen', '../etc', {'a': 1})
        with self.assertRaisesRegex(ValueError, 'werkzeug_ungueltig'):
            self.g.ablage_lesen('Böse Werkzeug', 'wissen:speicher')
        self.g.melden([obj('task', str(i)) for i in range(40)])
        self.assertEqual(len(self.g.arbeitsstand()['offen']), A.MAX_OFFEN)

    def test_volle_ablage_verdraengt_das_aelteste(self):
        voll = {'t': 'x' * (A.MAX_EINTRAG - 20)}
        n = A.MAX_ABLAGE // A.MAX_EINTRAG
        for i in range(n):
            self.uhr.t += 1; self.g.ablage_schreiben('wissen', f'task:{i}', voll)
        self.uhr.t += 1
        out = self.g.ablage_schreiben('wissen', 'task:neu', voll)
        self.assertGreaterEqual(out['verdraengt'], 1)
        self.assertEqual(self.g.ablage_lesen('wissen', 'task:0')['werte'], {})
        self.assertTrue(self.g.ablage_lesen('wissen', 'task:neu')['werte'])

    def test_verlauf_grenze_und_leeren(self):
        for i in range(A.MAX_VERLAUF + 5):
            self.g.verlauf_merken('user', f'Frage {i}')
        e = self.g.verlauf()['eintraege']
        self.assertEqual(len(e), A.MAX_VERLAUF); self.assertEqual(e[-1]['text'], f'Frage {A.MAX_VERLAUF + 4}')
        self.assertEqual(self.g.verlauf_leeren(), A.MAX_VERLAUF); self.assertEqual(self.g.verlauf()['eintraege'], [])

    def test_uebersicht_ohne_inhalt(self):
        self.g.ablage_schreiben('wissen', 'wissen:speicher', {'frage': 'GEHEIM-123'})
        self.g.verlauf_merken('user', 'GEHEIM-456')
        self.assertNotIn('GEHEIM', json.dumps(self.g.uebersicht()))


class Manifest(unittest.TestCase):
    def tool(self, **extra):
        doc = {'tool': dict({'id': 'probe', 'name': 'Probe', 'version': '1.0.0', 'kind': 'object', 'handles': ['task'],
                             'entry': {'js': 'tool.js'}, 'trust': 'CORE', 'needs': {'ui': '>=1.0 <2'}}, **extra)}
        folder = Path(self.tmp.name) / 'probe'; folder.mkdir(exist_ok=True); (folder / 'tool.js').write_text('', encoding='utf-8')
        return check_tool(doc, folder)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)

    def test_neue_felder(self):
        man, errors = self.tool(instanzen='viele', gedaechtnis='ablage')
        self.assertEqual(errors, []); self.assertEqual(man['instanzen'], 'viele'); self.assertEqual(man['gedaechtnis'], ['ablage'])
        man, errors = self.tool()
        self.assertEqual((man['instanzen'], man['gedaechtnis']), ('eine', []))
        self.assertIn('instanzen_invalid', self.tool(instanzen='drei')[1])
        self.assertIn('gedaechtnis_invalid', self.tool(gedaechtnis=['platte'])[1])


class Routen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH); self.addCleanup(self.hub.close)
        self.server, url = make_server(self.hub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)
        self.token = url.split('#')[1]

    def call(self, method, path, body=None, **headers):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            data = json.dumps(body) if body is not None else None
            h = dict({'X-GUPPI-Token': self.token}, **headers)
            if data is not None: h.update({'Content-Type': 'application/json', 'Content-Length': str(len(data.encode()))})
            c.request(method, path, data, h); r = c.getresponse()
            return r.status, json.loads(r.read() or b'{}')
        finally:
            c.close()

    def test_shell_meldet_neue_shell_uebernimmt(self):
        s, out = self.call('POST', '/api/arbeitsstand', {'offen': [obj('wissen', 'speicher', view='suche')], 'vorn': 'wissen:speicher'},
                           **{'X-SEDRA-Shell': 'cockpit'})
        self.assertEqual(s, 200, out)
        s, st = self.call('GET', '/api/arbeitsstand', **{'X-SEDRA-Shell': 'paperclip'})
        self.assertEqual((s, st['vorn'], st['shell']), (200, 'wissen:speicher', 'cockpit'))

    def test_ablage_nur_eigene_und_nur_mit_manifest(self):
        """A17: wissen (gedaechtnis: ablage) liest und schreibt; ein Werkzeug ohne Angabe bekommt 403 und einen Audit-Eintrag."""
        s, _ = self.call('POST', '/api/ablage/schreiben', {'objekt': 'wissen:speicher', 'werte': {'frage': 'D7.4'}}, **{'X-SEDRA-Tool': 'wissen'})
        self.assertEqual(s, 200)
        s, out = self.call('POST', '/api/ablage/lesen', {'objekt': 'wissen:speicher'}, **{'X-SEDRA-Tool': 'wissen'})
        self.assertEqual(out['werte'], {'frage': 'D7.4'})
        s, out = self.call('POST', '/api/ablage/lesen', {'objekt': 'wissen:speicher'}, **{'X-SEDRA-Tool': 'logbook'})
        self.assertEqual((s, out['error']), (403, 'tool_route_not_allowed'))
        s, out = self.call('POST', '/api/ablage/lesen', {'objekt': 'wissen:speicher'})        # die Seite selbst hat keine Ablage
        self.assertEqual(s, 400)
        denied = [e for e in audit_lesen(self.hub) if e.get('event_type') == 'UIX_TOOL_DENIED']
        self.assertTrue(denied)

    def test_verlauf_ueber_die_route_und_leeren(self):
        """A10: was über die Route des Gesprächs ging, steht im Verlauf; Leeren schreibt nur eine Zahl ins Audit."""
        self.hub._verlauf('reply', {'text': 'Wie heißt das Modell?'}, {'status': 'completed', 'reply': 'Qwen', 'model': 'q'})
        self.hub._verlauf('reply', {'text': 'Ohne Modell'}, {'status': 'no_model'})
        s, out = self.call('GET', '/api/chat/verlauf', **{'X-SEDRA-Tool': 'talk'})
        self.assertEqual(s, 200)
        self.assertEqual([(e['rolle'], e['text']) for e in out['eintraege']], [('user', 'Wie heißt das Modell?'), ('assistant', 'Qwen')])
        self.assertEqual(self.call('GET', '/api/chat/verlauf', **{'X-SEDRA-Tool': 'wissen'})[0], 403)
        s, out = self.call('POST', '/api/chat/verlauf/leeren', {}, **{'X-SEDRA-Tool': 'talk'})
        self.assertEqual((s, out['eintraege']), (200, 2))
        audit = [e for e in audit_lesen(self.hub) if e.get('event_type') == 'CHAT_VERLAUF_GELEERT']
        self.assertEqual(len(audit), 1); self.assertNotIn('Qwen', json.dumps(audit))

    def test_gedaechtnis_leeren_ohne_inhalt_im_audit(self):
        self.call('POST', '/api/ablage/schreiben', {'objekt': 'wissen:speicher', 'werte': {'frage': 'GEHEIM-789'}}, **{'X-SEDRA-Tool': 'wissen'})
        s, out = self.call('POST', '/api/arbeitsstand/leeren', {})
        self.assertEqual((s, out['status'], out['ablage']), (200, 'geleert', 1))
        self.assertNotIn('GEHEIM', json.dumps(audit_lesen(self.hub)))
        self.assertEqual(self.call('POST', '/api/ablage/lesen', {'objekt': 'wissen:speicher'}, **{'X-SEDRA-Tool': 'wissen'})[1]['werte'], {})

    def test_nichts_auf_der_platte(self):
        """A19: Die Ablage liegt nur im Prozess – kein Text daraus in einer Datei des Projekts."""
        self.call('POST', '/api/ablage/schreiben', {'objekt': 'wissen:speicher', 'werte': {'frage': 'NUR-IM-SPEICHER-42'}}, **{'X-SEDRA-Tool': 'wissen'})
        hits = [p for p in Path(self.tmp.name).rglob('*') if p.is_file() and p.stat().st_size < 5_000_000
                and b'NUR-IM-SPEICHER-42' in p.read_bytes()]
        self.assertEqual(hits, [])


if __name__ == '__main__':
    unittest.main()
