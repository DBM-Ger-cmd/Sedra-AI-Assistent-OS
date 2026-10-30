"""Härtungsrunde UIX 30.10.2026 (docs/HARDENING_UIX_2026-10-30.md) – Server-Teil: jede Härtung ein Test.
HU-B2 Geheimnisse (Client-Token, Cloud-Schlüssel) nie als Anhang · HU-B3 Herkunft S7 auf jedem Gate-Weg · HU-B5 abgebrochene Verbindung
ohne Traceback · HU-B6 Nicht-ASCII im Token-Kopf · HU-B7 gescheiterter Applier schließt den Antrag · HU-B9 uix.yaml unter Sperre ·
HU-B10 SVG mit Script ist ein Fund · HU-B12 `code` in jeder 400."""
import http.client
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk import gated, install
from test_uix_contract import NODE, UIX, run_js
from guppi_runtime.uix_server import UIXHub, make_server
from test_desk_install import module
from test_uix_harness_api import ARCH


class ServerHaertung(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='uix-haertung-')
        cls.hub = UIXHub(Path(cls.tmp.name) / 'project', ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.token = cls.url.split('#')[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def anfrage(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            h = {'X-GUPPI-Token': self.token, 'Content-Type': 'application/json', **(headers or {})}
            c.request(method, path, json.dumps(body) if body is not None else None, h)
            r = c.getresponse(); data = r.read()
            try: return r.status, json.loads(data.decode('utf-8'))
            except ValueError: return r.status, data
        finally:
            c.close()

    def test_b2_client_token_und_cloud_schluessel_sind_geheim(self):
        d = Path(self.tmp.name) / 'geheim'; d.mkdir(exist_ok=True)
        (d / 'runtime_data' / 'uix' / 'clients').mkdir(parents=True, exist_ok=True)
        (d / 'runtime_data' / 'uix' / 'clients' / 'cli.json').write_text('{"token": "x"}', encoding='utf-8')
        (d / 'cloud_keys.json').write_text('{}', encoding='utf-8')
        (d / 'mcp.json').write_text('{}', encoding='utf-8')
        for p in (d / 'runtime_data' / 'uix' / 'clients' / 'cli.json', d / 'cloud_keys.json', d / 'mcp.json'):
            with self.assertRaises(ValueError) as cm:
                self.hub.chat_attach({'path': str(p)})
            self.assertEqual(str(cm.exception), 'secret_file_refused', p.name)

    def test_b3_herkunft_gilt_auf_jedem_gate_weg(self):
        alt = self.hub.harness.herkunft.pruefen
        self.hub.harness.herkunft.pruefen = lambda *_a: {'ok': False, 'grund': 'harness_prozess'}
        try:
            for weg in ('/api/decisions/answer', '/api/mission/approve', '/api/mission/reject', '/api/actions', '/api/switch/apply',
                        '/api/boundaries/apply', '/api/uix/install/apply', '/api/gateway/apply'):
                code, out = self.anfrage('POST', weg, {})
                self.assertEqual(code, 403, (weg, out))
                self.assertEqual(out.get('code'), 'herkunft_abgelehnt', weg)
            code, _ = self.anfrage('GET', '/api/decisions')
            self.assertEqual(code, 200, 'Lesen bleibt frei')
            code, _ = self.anfrage('POST', '/api/chat/attach', {'path': str(Path(self.tmp.name))})
            self.assertNotEqual(code, 403, 'ein Weg ohne Gate bleibt offen')
        finally:
            self.hub.harness.herkunft.pruefen = alt

    def test_b6_nicht_ascii_im_token_kopf_ist_403_kein_absturz(self):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            c.putrequest('GET', '/api/decisions'); c.putheader('X-GUPPI-Token', 'tok\xe9n\xff'); c.endheaders()
            self.assertEqual(c.getresponse().status, 403)
        finally:
            c.close()
        code, _ = self.anfrage('GET', '/api/decisions')
        self.assertEqual(code, 200, 'der Server lebt weiter')

    def test_e3_csp_ohne_inline_script_ausser_archiv(self):
        """E3 (Captain 30.10. 15:46): Desk-Seite, Rahmenseite und Hardware-Seite kommen ohne Inline-Script aus – die CSP erlaubt keines;
        nur der archivierte Desktop unter /retro (Build 6, onclick-Attribute) behält 'unsafe-inline'."""
        def hole(path):
            c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
            try:
                c.request('GET', path, headers={'X-GUPPI-Token': self.token}); r = c.getresponse(); return r.status, r.getheader('Content-Security-Policy') or '', r.read().decode('utf-8', 'replace')
            finally:
                c.close()
        for path in ('/', '/hardware', '/api/decisions'):
            status, csp, body = hole(path)
            self.assertEqual(status, 200, path)
            self.assertIn("script-src 'self';", csp, path)
            self.assertNotIn("script-src 'self' 'unsafe-inline'", csp, path)
            if path != '/api/decisions':
                self.assertNotRegex(body, r'<script>', path + ' trägt kein Inline-Script')
        status, csp, body = hole('/retro')
        self.assertEqual(status, 200); self.assertIn("script-src 'self' 'unsafe-inline'", csp, 'das Archiv bleibt, wie es ist')

    def test_e3_rahmenseite_traegt_das_manifest_als_attribut(self):
        from guppi_runtime.desk.gateway import Gateway
        page = self.hub.gateway.frame_page('rahmen-probe')
        if page is None:
            self.skipTest('rahmen-probe nicht geladen (Schalter entwicklung aus)')
        self.assertNotIn('<script>', page)
        self.assertIn('data-manifest=', page)
        self.assertIn('&quot;id&quot;: &quot;rahmen-probe&quot;', page.replace('&quot;id&quot;:&quot;', '&quot;id&quot;: &quot;'))

    def test_b12_jede_400_traegt_einen_code(self):
        code, out = self.anfrage('POST', '/api/decisions/answer', {'id': 'gibtsnicht', 'way': 'ablehnen'})
        self.assertEqual(code, 400)
        self.assertIn('code', out)
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            c.putrequest('POST', '/api/chat'); c.putheader('X-GUPPI-Token', self.token); c.putheader('Content-Length', 'abc'); c.endheaders()
            r = c.getresponse(); out = json.loads(r.read().decode('utf-8'))
            self.assertEqual((r.status, out['code']), (400, 'bad_content_length'))
        finally:
            c.close()

    def test_b5_abgebrochene_verbindung_ist_kein_fehler(self):
        import io
        from contextlib import redirect_stderr
        buf = io.StringIO()
        with redirect_stderr(buf):
            for _ in range(3):
                c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
                c.putrequest('GET', '/api/strip'); c.putheader('X-GUPPI-Token', self.token); c.endheaders()
                c.sock.close()                                    # der Browser lädt neu, bevor die Antwort da ist
            code, _ = self.anfrage('GET', '/api/decisions')
        self.assertEqual(code, 200)
        self.assertNotIn('Traceback', buf.getvalue())

    def test_b7_gescheiterter_applier_schliesst_den_antrag(self):
        hub = self.hub
        def kaputt(h, binding): raise RuntimeError('platte voll')
        gated._APPLIERS['haertung_probe'] = (kaputt, None)
        try:
            req = gated.request(hub, 'haertung_probe', 'PROBE_WRITE', 'probe:1', {'x': 1}, exact=True)
            with self.assertRaises(RuntimeError):
                gated.decide(hub, req['mission_id'])
            m = hub.runtime.missions.load(req['mission_id'])
            self.assertEqual(m['lifecycle']['status'], 'closed')
            self.assertNotIn('approval_tokens', m['execution'])
            self.assertIn('RuntimeError', m['result']['error'])
            rows = [json.loads(l) for l in hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
            self.assertIn('DESK_GATED_FAILED', [r['event_type'] for r in rows])
            self.assertFalse([d for d in hub.decisions_view()['items'] if d.get('mission_id') == req['mission_id']], 'kein Zombie im Posteingang')
        finally:
            gated._APPLIERS.pop('haertung_probe', None)

    def test_b9_uix_yaml_wird_unter_sperre_geschrieben(self):
        reg = self.hub.gateway.registry
        fehler = []
        def schreiben(n):
            try:
                for i in range(15): reg.save_shelf('cockpit', [{'kind': 'place', 'label': f'{n}-{i}', 'icon': 'arbeit', 'place': 'tasks'}])
            except Exception as exc: fehler.append(repr(exc))
        ts = [threading.Thread(target=schreiben, args=(n,)) for n in range(4)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertFalse(fehler, fehler)
        self.assertFalse(list(reg.config_path.parent.glob('uix.yaml.*.tmp')), 'keine Temp-Datei bleibt liegen')
        self.assertIsInstance(reg.config(), dict)


class LaufzeitHaertung(unittest.TestCase):
    """Reine Teile der Anbindung mit node: HU-L11 reservierte Ereignisse, HU-L13 closeEvents räumt den Neuaufbau, HU-L5 Verlauf aus dem Browser."""

    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_l11_werkzeuge_senden_keine_ereignisse_des_stroms(self):
        out = run_js([UIX / 'ui' / 'bus.js'], """
          const B = box.sedraBus; const abgelehnt = [];
          const bus = B.makeBus((name, why)=>abgelehnt.push(name + ': ' + why));
          const werkzeug = bus.forModule(['desk.resync', 'harness.lauf', 'object.close', 'decision.answered']);
          let gehoert = 0; bus.on('desk.resync', ()=>{ gehoert += 1; }); bus.on('object.close', ()=>{ gehoert += 1; });
          const r = [werkzeug.emit('desk.resync', {}), werkzeug.emit('harness.lauf', {id: 'L-1'}), werkzeug.emit('object.close', {type: 'task', id: 'x'}),
                     werkzeug.emit('decision.answered', {id: 'd'}), bus.emit('desk.resync', {})];
          console.log(JSON.stringify({r, gehoert, abgelehnt: abgelehnt.map(a=>a.split(':')[0])}));
        """)
        self.assertEqual(out['r'], [False, False, True, True, True], 'ein Werkzeug sendet keine Strom-Ereignisse, die Seite schon')
        self.assertEqual(out['gehoert'], 2)
        self.assertEqual(out['abgelehnt'], ['desk.resync', 'harness.lauf'])

    def test_l13_close_events_raeumt_den_geplanten_neuaufbau(self):
        # api.js liest `location` beim Laden; der Kern wird hier als Attrappe vor dem Loader gesetzt (vm-Box, sonst kein Fenster)
        kopf = ("box.window = box; box.location = {hash: '#t', origin: 'http://127.0.0.1:1'}; box.setTimeout = (f, ms)=>setTimeout(f, 1); box.clearTimeout = clearTimeout;"
                "let gebaut = 0; const quellen = []; box.sedraApi = {forModule: ()=>async()=>({}), api: async()=>({}), events(){ gebaut += 1; const s = {close(){ s.zu = true; }, addEventListener(){}, zu: false}; quellen.push(s); return s; }};"
                "vm.runInContext(fs.readFileSync(%s, 'utf8'), box);" % json.dumps(str(UIX / 'ui' / 'loader.js')))
        out = run_js([UIX / 'ui' / 'bus.js'], kopf + """
          const bus = box.sedraBus.makeBus(()=>{});
          const schliessen = box.sedraLoader.connectEvents(bus, ()=>{});
          quellen[0].onerror();                 // Verbindung weg: ein Neuaufbau ist geplant
          schliessen();
          setTimeout(()=>console.log(JSON.stringify({gebaut, zu: quellen.map(q=>q.zu)})), 30);
        """)
        self.assertEqual(out['gebaut'], 1, 'nach closeEvents entsteht keine neue Verbindung mehr')
        self.assertEqual(out['zu'], [True])


class RoutenImManifest(unittest.TestCase):
    """HU-S1/HU-T12: jede Route, die eine Shell oder ein Werkzeug ruft, steht in seiner `api`-Liste (sonst 403 zur Laufzeit) – und die
    Liste nennt nichts, was der Code nicht ruft (sonst ist die Allowlist zu weit). Helfer aus ui/ zählen mit der Kennung des Rufers."""
    ROUTE = re.compile(r"""['"`](/api/[a-z0-9_/\-]+)['"`]""")
    PRAEFIX = re.compile(r"""['"`](/api/[a-z0-9_/\-]*)['"`]\s*\+""")
    HELFER = {'sedraStand.entscheiden': ['POST /api/decisions/answer'],
              'sedraVorgabe.block': ['GET /api/uix/vorgaben', 'POST /api/uix/vorgabe', 'POST /api/uix/scaffold']}
    AUSNAHMEN = {'tools/rahmen-probe': {'/api/update/zurueck'},                         # ruft absichtlich eine verbotene Route als Probe
                 'tools/gateway': {'GET /api/decisions', 'GET /api/guard/status', 'POST /api/guard/probe'}}   # das eingebettete Werkzeug `schutz` läuft mit der Kennung von gateway (Befund T1, Entscheidung E4)

    @staticmethod
    def passt(path, eintrag):
        p = eintrag.split(' ', 1)[1] if ' ' in eintrag else eintrag
        if p.endswith('/*'):
            return path.startswith(p[:-1]) or (path.endswith('…') and p[:-2].startswith(path[:-1]))
        return path == p or (path.endswith('…') and p.startswith(path[:-1]))

    def test_routen_und_allowlist_passen_zusammen(self):
        import yaml
        for kind, mf, key in (('shells', 'shell.yaml', 'shell'), ('tools', 'tool.yaml', 'tool')):
            for d in sorted((UIX / kind).iterdir()):
                y = d / mf
                if not y.is_file():
                    continue
                man = (yaml.safe_load(y.read_text(encoding='utf-8')) or {}).get(key) or {}
                allow = [str(x) for x in (man.get('api') or [])]
                used = set()
                for js in d.glob('*.js'):
                    if js.name.endswith('.spec.js'):
                        continue
                    t = js.read_text(encoding='utf-8')
                    used |= {m.group(1) for m in self.ROUTE.finditer(t)}
                    used |= {m.group(1) + '…' for m in self.PRAEFIX.finditer(t)}
                    for helfer, routen in self.HELFER.items():
                        if helfer in t:
                            used |= {r.split(' ', 1)[1] for r in routen}
                ausnahme = self.AUSNAHMEN.get(f'{kind}/{d.name}', set())
                with self.subTest(f'{kind}/{d.name}'):
                    fehlt = sorted(u for u in used if u not in ausnahme and not any(self.passt(u, a) for a in allow))
                    zu_weit = sorted(a for a in allow if a not in ausnahme and not any(self.passt(u, a) for u in used))
                    self.assertEqual(fehlt, [], f'{kind}/{d.name} ruft Routen, die nicht in der api-Liste stehen (403 zur Laufzeit)')
                    self.assertEqual(zu_weit, [], f'{kind}/{d.name}: api-Liste nennt Routen, die der Code nicht ruft')


class UpdateGate(unittest.TestCase):
    """E1 (Captain 30.10. 15:46): die Übernahme eines Updates ist ein Gate mit Einmal-Token – ohne Freigabe wird nichts geschrieben,
    ein verändertes Manifest wird abgewiesen, der Token gilt genau einmal."""

    def setUp(self):
        from guppi_runtime import uix_server as us
        from test_update_anwenden import baum, schreibe
        from guppi_runtime import update_anwenden as ua
        self.tmp = tempfile.TemporaryDirectory(prefix='update-gate-'); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'installation'
        schreibe(self.root, baum())
        self.tag = 'v1.99.0'
        self.staging = self.root / 'local_config' / 'update' / 'staging' / self.tag
        schreibe(self.staging, dict(baum(), **{'runtime/src/guppi_runtime/kern.py': 'X = 2\n'}))
        (self.staging / ua.MANIFEST).parent.mkdir(parents=True, exist_ok=True)
        (self.staging / ua.MANIFEST).write_text(ua.manifest_erzeugen(self.staging), encoding='utf-8')
        self.alt = us.INSTALLATION; us.INSTALLATION = self.root
        self.addCleanup(lambda: setattr(us, 'INSTALLATION', self.alt))
        import guppi_runtime.update_holen as uh
        self.alt_laden = uh.herunterladen; uh.herunterladen = lambda root, tag: self.staging
        self.addCleanup(lambda: setattr(uh, 'herunterladen', self.alt_laden))
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH); self.addCleanup(self.hub.close)

    def kern(self):
        return (self.root / 'runtime/src/guppi_runtime/kern.py').read_text(encoding='utf-8')

    def test_e1_uebernahme_nur_nach_freigabe_und_genau_einmal(self):
        v = self.hub.update_vorschau({'tag': self.tag})
        self.assertIn('mission_id', v)
        self.assertEqual(self.kern(), 'X = 1\n', 'die Vorschau schreibt nichts')
        with self.assertRaises(ValueError) as cm:
            self.hub.update_uebernehmen({'mission_id': v['mission_id']})
        self.assertEqual(str(cm.exception), 'captain_approval_required')
        with self.assertRaises(ValueError):
            self.hub.update_uebernehmen({'tag': self.tag, 'rechte_schluessel': v['rechte_schluessel']})    # der alte Weg ohne Gate geht nicht mehr
        self.assertEqual(self.kern(), 'X = 1\n')
        d = next(x for x in self.hub.decisions_view()['items'] if x['mission_id'] == v['mission_id'])
        self.assertEqual((d['kind'], d['apply']), ('request:update', '/api/update/uebernehmen'))
        out = self.hub.decide({'id': d['id'], 'way': 'freigeben_und_anwenden'})
        self.assertEqual(out['result']['status'], 'uebernommen')
        self.assertEqual(self.kern(), 'X = 2\n')
        with self.assertRaises(ValueError):
            self.hub.update_uebernehmen({'mission_id': v['mission_id']})      # der Token ist verbraucht
        rows = [json.loads(l) for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        self.assertIn('UPDATE_UEBERNOMMEN', [r['event_type'] for r in rows])

    def test_e1_veraendertes_manifest_wird_abgewiesen(self):
        from guppi_runtime import update_anwenden as ua
        v = self.hub.update_vorschau({'tag': self.tag})
        d = next(x for x in self.hub.decisions_view()['items'] if x['mission_id'] == v['mission_id'])
        self.hub.approve_gate({'mission_id': d['mission_id'], 'gate_id': d['gate_id']})
        (self.staging / 'runtime/src/guppi_runtime/kern.py').write_text('X = 3\n', encoding='utf-8')
        (self.staging / ua.MANIFEST).write_text(ua.manifest_erzeugen(self.staging), encoding='utf-8')
        with self.assertRaises(ValueError) as cm:
            self.hub.update_uebernehmen({'mission_id': v['mission_id']})
        self.assertEqual(str(cm.exception), 'file_changed_repeat_request')
        self.assertEqual(self.kern(), 'X = 1\n')


class CloudAdresseGate(unittest.TestCase):
    """E2 (Captain 30.10. 15:46): `cloud/save` schreibt atomar mit Sicherung; eine geänderte Anbieter-Adresse wird nicht geschrieben,
    sondern als Antrag mit Gate vorgelegt – erst „Freigeben und anwenden“ setzt sie (Einmal-Token, Datei-Hash)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cloud-gate-'); self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH); self.addCleanup(self.hub.close)
        from guppi_runtime import cloud_settings
        self.cs = cloud_settings

    def cfg(self):
        return self.cs.load_config(self.hub.runtime.project_root)

    def test_e2_base_url_geht_nur_ueber_das_gate_rest_sofort(self):
        pid = next(iter(self.cfg()['providers']))
        alt = self.cfg()['providers'][pid].get('base_url')
        out = self.hub.cloud_save({'enabled': True, 'providers': {pid: {'enabled': True, 'base_url': 'https://neu.example.test/v1/'}}})
        self.assertTrue(out['saved']); self.assertEqual(len(out['antraege']), 1)
        cfg = self.cfg()
        self.assertTrue(cfg['enabled'] and cfg['providers'][pid]['enabled'], 'Schalter und Modell gelten sofort')
        self.assertEqual(cfg['providers'][pid].get('base_url'), alt, 'die Adresse wartet auf die Freigabe')
        d = next(x for x in self.hub.decisions_view()['items'] if x['mission_id'] == out['antraege'][0])
        self.assertEqual((d['kind'], d['apply']), ('request:cloud_url', '/api/cloud/base-url/apply'))
        self.assertTrue(any('Schlüssel' in r for r in d['risks']))
        res = self.hub.decide({'id': d['id'], 'way': 'freigeben_und_anwenden'})
        self.assertEqual(res['result']['status'], 'applied')
        self.assertEqual(self.cfg()['providers'][pid]['base_url'], 'https://neu.example.test/v1')
        with self.assertRaises(ValueError):
            self.hub.cloud_base_url_apply({'mission_id': out['antraege'][0]})     # Token verbraucht
        rows = [json.loads(l) for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        self.assertIn('CLOUD_BASE_URL_CHANGED', [r['event_type'] for r in rows])
        self.assertTrue(list(self.cs.settings_path(self.hub.runtime.project_root).parent.glob('cloud_providers.yaml.bak-*')), 'Sicherung vor dem Überschreiben')

    def test_e2_ablehnen_und_geaenderte_datei(self):
        pid = next(iter(self.cfg()['providers']))
        out = self.hub.cloud_save({'enabled': False, 'providers': {pid: {'base_url': 'https://a.example.test'}}})
        d = next(x for x in self.hub.decisions_view()['items'] if x['mission_id'] == out['antraege'][0])
        self.hub.decide({'id': d['id'], 'way': 'ablehnen'})
        self.assertNotEqual(self.cfg()['providers'][pid].get('base_url'), 'https://a.example.test')
        out = self.hub.cloud_save({'enabled': False, 'providers': {pid: {'base_url': 'https://b.example.test'}}})
        d = next(x for x in self.hub.decisions_view()['items'] if x['mission_id'] == out['antraege'][0])
        self.hub.approve_gate({'mission_id': d['mission_id'], 'gate_id': d['gate_id']})
        self.hub.cloud_save({'enabled': True, 'providers': {}})                 # die Datei ändert sich zwischen Freigabe und Anwenden
        with self.assertRaises(ValueError) as cm:
            self.hub.cloud_base_url_apply({'mission_id': d['mission_id']})
        self.assertEqual(str(cm.exception), 'file_changed_repeat_request')


class VertragParagraf2(unittest.TestCase):
    """E4 (Captain 30.10. 15:46): keine Querzugriffe am Vertrag vorbei. Kein Werkzeug greift auf die Registrierungen (`sedra.tools`,
    `sedra.shells`), den Prüfzugang (`sedraBoot.ctx`), den Wechsel der Seite (`sedraWechsel`) oder den Kern-Zugang (`sedraApi`) zu;
    keine Shell holt ein Werkzeug über `sedra.tools.get`. Einbetten geht nur über `ctx.einbetten` (N9)."""
    VERBOTEN_TOOLS = re.compile(r'\bsedra\.(tools|shells)\b|\bsedraBoot\.ctx\b|\bsedraWechsel\b|\bsedraApi\b')
    VERBOTEN_SHELLS = re.compile(r'\bsedra\.tools\.get\b|\bsedra\.shells\.get\b|\bsedraBoot\.ctx\b|\bsedraApi\b')
    AUSNAHMEN = {'tools/rahmen-probe/tool.js'}                      # prüft absichtlich, dass es den Kern-Zugang im Rahmen nicht gibt

    @staticmethod
    def ohne_kommentare(text):
        return '\n'.join(l.split('//')[0] for l in text.splitlines())

    def test_keine_querzugriffe_in_werkzeugen_und_shells(self):
        funde = []
        for kind, muster in (('tools', self.VERBOTEN_TOOLS), ('shells', self.VERBOTEN_SHELLS)):
            for js in sorted((UIX / kind).rglob('*.js')):
                rel = js.relative_to(UIX).as_posix()
                if js.name.endswith('.spec.js') or rel in self.AUSNAHMEN:
                    continue
                for n, line in enumerate(self.ohne_kommentare(js.read_text(encoding='utf-8')).splitlines(), 1):
                    if muster.search(line):
                        funde.append(f'{rel}:{n}: {line.strip()[:80]}')
        self.assertEqual(funde, [], 'Vertrag §2: Querzugriffe nur über ctx (einbetten, shell, bus, api)')

    def test_pruefzugang_nur_mit_schalter_oder_pruefung(self):
        import os
        from guppi_runtime.desk.gateway import Gateway
        g = self.__class__._gateway()
        alt = os.environ.pop('SEDRA_PRUEFZUGANG', None)
        try:
            g.entwicklung = False
            self.assertFalse(g.manifest()['pruefzugang'], 'im Betrieb kein Prüfzugang')
            g.entwicklung = True
            self.assertTrue(g.manifest()['pruefzugang'])
            g.entwicklung = False
            os.environ['SEDRA_PRUEFZUGANG'] = '1'
            self.assertTrue(g.manifest()['pruefzugang'])
        finally:
            if alt is None: os.environ.pop('SEDRA_PRUEFZUGANG', None)
            else: os.environ['SEDRA_PRUEFZUGANG'] = alt

    @classmethod
    def _gateway(cls):
        from guppi_runtime.desk.gateway import Gateway
        cls._tmp = tempfile.TemporaryDirectory(prefix='pruefzugang-')
        return Gateway(Path(cls._tmp.name))

    def test_einbetten_ueber_die_laufzeit(self):
        """N9: ctx.einbetten hängt ein Paket-Werkzeug mit eigener Kennung ein und baut es mit dem Einbettenden ab (node, ohne Browser)."""
        kopf = ("box.window = box; box.location = {hash: '#t', origin: 'http://127.0.0.1:1'}; box.document = {documentElement: {}};"
                "box.getComputedStyle = ()=>({}); const rufe = []; box.sedraApi = {forModule: (m)=>async(p)=>{ rufe.push((m && m.id) + ' ' + p); return {}; }, api: async()=>({}), events(){ return {close(){}, addEventListener(){}}; }};"
                "vm.runInContext(fs.readFileSync(%s, 'utf8'), box); vm.runInContext(fs.readFileSync(%s, 'utf8'), box);"
                % (json.dumps(str(UIX / 'ui' / 'lifecycle.js')), json.dumps(str(UIX / 'ui' / 'loader.js'))))
        out = run_js([UIX / 'ui' / 'bus.js'], kopf + """
          const L = box.sedraLifecycle, Ld = box.sedraLoader; const leben = [];
          const el = ()=>({replaceChildren(){}, append(){}, classList: {add(){}, remove(){}, toggle(){}}});
          const innen = {id: 'innen', mount(e, ctx){ leben.push('innen auf'); ctx.api('/api/innen'); ctx.bus.on('decision.answered', ()=>{}); }, unmount(){ leben.push('innen zu'); }};
          const aussen = {id: 'aussen', mount(e, ctx){ leben.push('aussen auf'); ctx.api('/api/aussen'); ctx.einbetten('innen', el(), {type: 'x', id: '1'}); try{ ctx.einbetten('rahmen', el()); }catch(err){ leben.push(err.message); } }, unmount(){ leben.push('aussen zu'); }};
          const entries = [{manifest: {id: 'innen', kind: 'object', trust: 'CORE', handles: ['x'], events: {emits: []}}, mod: innen},
                           {manifest: {id: 'aussen', kind: 'object', trust: 'CORE', handles: ['x'], events: {emits: []}}, mod: aussen},
                           {manifest: {id: 'rahmen', kind: 'object', trust: 'COMMUNITY', handles: ['x'], events: {emits: []}}, mod: {id: 'rahmen', mount(){}, unmount(){}}}];
          const reg = Ld.makeRegistry(entries); const bus = box.sedraBus.makeBus(()=>{});
          const shell = {open(){}, notify(){}, decide(){}, reload(){}};
          const ctx = Ld.makeContext(entries[1].manifest, {type: 'x', id: '1'}, bus, shell, ()=>{}, reg);
          const st = L.mountTool(aussen, el(), ctx, ()=>{});
          const offen = ctx._eingebettet.length;
          L.unmountTool(st, ()=>{});
          console.log(JSON.stringify({leben, rufe, offen, danach: ctx._eingebettet.length}));
        """)
        self.assertEqual(out['leben'], ['aussen auf', 'innen auf', 'einbetten_unbekannt:rahmen', 'innen zu', 'aussen zu'])
        self.assertEqual(sorted(out['rufe']), ['aussen /api/aussen', 'innen /api/innen'], 'jedes Werkzeug ruft mit seiner eigenen Kennung')
        self.assertEqual((out['offen'], out['danach']), (1, 0))


class InstallHaertung(unittest.TestCase):
    def test_b10_svg_mit_script_ist_ein_fund(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = module(Path(tmp) / 'fremd')
            (folder / 'bild.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><script>fetch("/")</script></svg>', encoding='utf-8')
            read = install.read_module(folder, 'tools')
            flags = {f['flag'] for f in read['findings'] if f.get('name', f.get('datei', '')) == 'bild.svg' or 'bild.svg' in json.dumps(f)}
            self.assertTrue({'<script in SVG/HTML', 'on…= in Markup'} & flags, read['findings'])


if __name__ == '__main__':
    unittest.main()
