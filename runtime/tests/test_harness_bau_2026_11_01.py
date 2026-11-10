"""Bau 1.11.2026 (ANALYSE_HARNESS_2026-11-01, Pakete P0–P3): je Befund/Maßnahme ein Test.

P0 M1: Sitzungs-Erlaubnis („Für diese Sitzung erlauben“), ${schreibbereich} im Katalog, Testbefehle frei.
Ein echter UIXHub auf einem Prüfprojekt; das Harness-Projekt zeigt auf einen Wegwerf-Ordner. Ersetzt werden nur `harness.geladen` und `harness.execute`."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.harness import dateien, erlaubnis, export, katalog, projekte
from sedra_runtime.harness.sitzung import SitzungFehler, Sitzungen
from sedra_runtime.uix_server import UIXHub, make_server
from test_uix_contract import NODE, UIX, run_js
from test_uix_harness_api import ARCH, MODELL, anfrage, strom
from test_uix_harness_freigabe import Skript


class ErlaubnisRein(unittest.TestCase):
    def test_muster_fuer(self):
        self.assertEqual(erlaubnis.muster_fuer('datei_schreiben', 'lauf/test/x.py'), 'lauf/test/**')
        self.assertEqual(erlaubnis.muster_fuer('datei_aendern', 'x.py'), '*')
        self.assertEqual(erlaubnis.muster_fuer('befehl', 'python -m unittest -v'), 'python -m unittest*')
        self.assertEqual(erlaubnis.muster_fuer('befehl', 'git commit -m "x"'), 'git commit*')
        self.assertEqual(erlaubnis.muster_fuer('befehl', 'pytest'), 'pytest*')
        self.assertEqual(erlaubnis.muster_fuer('lauf_starten', 'run_tests'), 'run_tests')

    def test_deckt_und_aktive(self):
        eintraege = [{'typ': 'captain', 'text': 'x'},
                     {'typ': 'erlaubnis', 'karte_id': 'K-1', 'werkzeug': 'datei_schreiben', 'muster': 'lauf/**', 'aktiv': True},
                     {'typ': 'erlaubnis', 'karte_id': 'K-2', 'werkzeug': 'befehl', 'muster': 'python -m unittest*', 'aktiv': True},
                     {'typ': 'erlaubnis', 'karte_id': 'K-3', 'werkzeug': 'befehl', 'muster': 'git commit*', 'aktiv': True},
                     {'typ': 'erlaubnis', 'karte_id': 'K-3', 'aktiv': False}]
        a = erlaubnis.aktive(eintraege)
        self.assertEqual([e['karte_id'] for e in a], ['K-1', 'K-2'], 'Rücknahme hebt auf')
        self.assertEqual(erlaubnis.deckt(a, 'datei_schreiben', 'lauf/tief/y.py')['karte_id'], 'K-1')
        self.assertIsNone(erlaubnis.deckt(a, 'datei_schreiben', 'docs/y.md'))
        self.assertIsNone(erlaubnis.deckt(a, 'datei_aendern', 'lauf/y.py'), 'nur dasselbe Werkzeug')
        self.assertEqual(erlaubnis.deckt(a, 'befehl', 'python -m unittest discover')['karte_id'], 'K-2')
        self.assertIsNone(erlaubnis.deckt(a, 'befehl', 'git commit -m x'), 'zurückgenommen')

    def test_erlaubt_fuer_karte(self):
        self.assertTrue(erlaubnis.erlaubt_fuer_karte({'werkzeug': 'befehl', 'ziel': 'python x.py', 'stufe': 'captain'}))
        self.assertFalse(erlaubnis.erlaubt_fuer_karte({'werkzeug': 'befehl', 'ziel': 'rm x', 'stufe': 'captain', 'vorbehalt': True}))
        self.assertFalse(erlaubnis.erlaubt_fuer_karte({'werkzeug': 'datei_schreiben', 'ziel': 'a.py', 'stufe': 'captain', 'warnung': {'text': 'x'}}))
        self.assertFalse(erlaubnis.erlaubt_fuer_karte({'werkzeug': 'aufgabe_vorschlagen', 'ziel': 'x', 'art': 'aufgabe'}))
        self.assertFalse(erlaubnis.erlaubt_fuer_karte({'werkzeug': 'modell_laden', 'ziel': 'coder', 'stufe': 'captain'}))

    def test_sitzung_speichert_erlaubnis(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Sitzungen(Path(tmp))
            sid = s.anlegen('p')['id']
            s.erlauben(sid, 'K-00000001', 'befehl', 'pytest*', regel='befehl-python')
            self.assertEqual([(e['werkzeug'], e['muster']) for e in s.laden(sid)['erlaubnisse']], [('befehl', 'pytest*')])
            s.erlaubnis_zuruecknehmen(sid, 'K-00000001')
            self.assertEqual(s.laden(sid)['erlaubnisse'], [])
            with self.assertRaises(SitzungFehler):
                s.erlaubnis_zuruecknehmen(sid, 'K-00000001')


class KatalogSchreibbereich(unittest.TestCase):
    def setUp(self):
        self.regeln = katalog.laden(Path('/nirgends'))['regeln']          # die Vorlage

    def test_platzhalter_wird_je_projekt_ersetzt(self):
        r = katalog.mit_projekt(self.regeln, {'schreibbereich': ['lauf/**', 'notizen/*.md']})
        regel = next(x for x in r if x['id'] == 'schreiben-schreibbereich')
        self.assertEqual(regel['muster'], ['lauf/**', 'notizen/*.md'])
        self.assertEqual(katalog.einstufen(r, 'datei_schreiben', 'lauf/x.py')['stufe'], 'frei')
        self.assertEqual(katalog.einstufen(r, 'datei_schreiben', 'anderswo/x.py')['stufe'], 'captain')

    def test_genauere_regeln_gewinnen_und_ohne_projekt_faellt_die_regel_weg(self):
        r = katalog.mit_projekt(self.regeln, {'schreibbereich': ['**']})
        self.assertEqual(katalog.einstufen(r, 'datei_schreiben', 'runtime/x.py')['regel'], 'schreiben-runtime', 'runtime/** ist genauer als **')
        self.assertEqual(katalog.einstufen(r, 'datei_schreiben', 'docs/x.md')['stufe'], 'captain')
        self.assertEqual(katalog.einstufen(r, 'datei_schreiben', 'lauf/x.py')['stufe'], 'frei')
        ohne = katalog.mit_projekt(self.regeln, None)
        self.assertNotIn('schreiben-schreibbereich', [x['id'] for x in ohne])
        self.assertEqual(katalog.einstufen(ohne, 'datei_schreiben', 'lauf/x.py')['stufe'], 'captain')

    def test_testbefehle_frei_python_sonst_captain(self):
        r = katalog.mit_projekt(self.regeln, {'schreibbereich': ['**']})
        for z in ('python -m unittest -v', 'python -m pytest tests', 'pytest -q', 'python3 -m unittest'):
            self.assertEqual(katalog.einstufen(r, 'befehl', z)['regel'], 'befehl-unittests', z)
        self.assertEqual(katalog.einstufen(r, 'befehl', 'python setup.py install')['regel'], 'befehl-python')
        self.assertEqual(katalog.einstufen(r, 'befehl', 'python x.py')['stufe'], 'captain')


class SitzungsErlaubnisServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-bau-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'docs').mkdir(parents=True)
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: pruef\n    name: Prüfprojekt\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**, lauf/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        self.hub.harness.geladen = lambda: (MODELL, None)

    def sitzung(self, zuege):
        self.modell = Skript(zuege)
        self.hub.harness.execute = self.modell
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef'})
        self.assertEqual(code, 200, kopf)
        return kopf['id']

    def senden(self, sid, text):
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{sid}/nachricht', {'text': text})
        self.assertEqual(code, 200, out)
        return strom(self.url, out['antwort_id'])

    def warte_threads(self):
        for _ in range(100):
            if not self.hub.harness.threads: return
            time.sleep(0.05)

    def audit(self, event):
        rows = [json.loads(l) for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        return [r['payload'] for r in rows if r['event_type'] == event]

    def test_schreibbereich_frei_docs_captain(self):
        sid = self.sitzung([('calls', [('datei_schreiben', {'pfad': 'lauf/a.py', 'inhalt': 'print(1)\n'})]), ('text', 'Geschrieben.')])
        ev = self.senden(sid, 'Schreib lauf/a.py')
        self.assertEqual(ev[-1][2]['ende'], 'erledigt', 'im Schreibbereich außerhalb docs/runtime: frei (M1)')
        self.assertEqual((self.wurzel / 'lauf' / 'a.py').read_text(encoding='utf-8'), 'print(1)\n')
        ende = next(e[2] for e in ev if e[1] == 'werkzeug.ende')
        self.assertEqual((ende['status'], ende['stufe'], ende['regel']), ('ok', 'frei', 'schreiben-schreibbereich'))

    def test_fuer_diese_sitzung_erlauben_spart_die_naechste_karte(self):
        sid = self.sitzung([('calls', [('datei_schreiben', {'pfad': 'docs/eins.md', 'inhalt': 'eins\n'})]),
                            ('calls', [('datei_schreiben', {'pfad': 'docs/zwei.md', 'inhalt': 'zwei\n'})]),
                            ('calls', [('datei_aendern', {'pfad': 'docs/zwei.md', 'alt': 'zwei', 'neu': 'drei'})]),
                            ('text', 'Fertig.')])
        ev = self.senden(sid, 'Leg docs/eins.md und docs/zwei.md an')
        self.assertEqual(ev[-1][2]['ende'], 'wartet')
        kid = next(e[2] for e in ev if e[1] == 'karte')['karte_id']
        self.warte_threads()
        code, out = anfrage(self.url, 'POST', f'/api/harness/karten/{kid}', {'weg': 'sitzung'})
        self.assertEqual(code, 200, out)
        self.assertEqual((out['weg'], out['ergebnis_status'], out['fortsetzung']), ('sitzung', 'ok', 'laeuft'))
        self.assertEqual(out['erlaubnis'], {'werkzeug': 'datei_schreiben', 'muster': 'docs/**', 'regel': 'schreiben-docs'})
        ev2 = strom(self.url, out['antwort_id'])
        # zweite Datei im selben Ordner: ohne Karte; datei_aendern ist ein anderes Werkzeug → wieder Karte
        enden = [e[2] for e in ev2 if e[1] == 'werkzeug.ende']
        self.assertEqual([(x['status'], x['stufe'], x['regel']) for x in enden], [('ok', 'sitzung', 'sitzung:' + kid), ('wartet', 'captain', 'schreiben-docs')])
        self.assertEqual(ev2[-1][2]['ende'], 'wartet', 'datei_aendern hat keine Erlaubnis')
        self.assertEqual((self.wurzel / 'docs' / 'zwei.md').read_text(encoding='utf-8'), 'zwei\n')
        self.warte_threads()
        self.assertEqual([p['approved_by'] for p in self.audit('HARNESS_APPROVED_BY') if p['approved_by'].startswith('sitzung:')], ['sitzung:' + kid])
        self.assertEqual([(p['sitzung_id'], p['karte_id'], p['muster']) for p in self.audit('HARNESS_SITZUNG_ERLAUBT')], [(sid, kid, 'docs/**')])
        _c, karte = anfrage(self.url, 'GET', f'/api/harness/karten/{kid}')
        self.assertEqual((karte['entscheidung'], karte['erlaubnis']['muster']), ('sitzung', 'docs/**'))
        _c, s = anfrage(self.url, 'GET', f'/api/harness/sitzungen/{sid}')
        self.assertEqual([(e['werkzeug'], e['muster']) for e in s['erlaubnisse']], [('datei_schreiben', 'docs/**')])
        # Zurücknehmen (PATCH) – danach wieder Karte
        kid2 = next(e[2] for e in ev2 if e[1] == 'karte')['karte_id']
        anfrage(self.url, 'POST', f'/api/harness/karten/{kid2}', {'weg': 'ablehnen'})
        self.warte_threads()
        code, s = anfrage(self.url, 'PATCH', f'/api/harness/sitzungen/{sid}', {'erlaubnis_zuruecknehmen': kid})
        self.assertEqual((code, s['erlaubnisse']), (200, []))
        code, body = anfrage(self.url, 'PATCH', f'/api/harness/sitzungen/{sid}', {'erlaubnis_zuruecknehmen': kid})
        self.assertEqual((code, body.get('code')), (400, 'erlaubnis_unbekannt'))
        self.modell.zuege = [('calls', [('datei_schreiben', {'pfad': 'docs/vier.md', 'inhalt': 'vier\n'})]), ('text', 'ok')]
        ev3 = self.senden(sid, 'noch eine')
        self.assertEqual(ev3[-1][2]['ende'], 'wartet', 'nach der Rücknahme wieder eine Karte')
        self.warte_threads()

    def test_sitzung_nicht_bei_vorbehalt(self):
        sid = self.sitzung([('calls', [('befehl', {'befehl': 'rm -rf docs'})]), ('text', 'ok')])
        ev = self.senden(sid, 'räum auf')
        karte = next(e[2] for e in ev if e[1] == 'karte')
        self.assertTrue(karte['vorbehalt'])
        self.warte_threads()
        code, body = anfrage(self.url, 'POST', f"/api/harness/karten/{karte['karte_id']}", {'weg': 'sitzung'})
        self.assertEqual(code, 400, body)
        self.assertTrue(body.get('code', '').startswith('sitzung_nicht_moeglich'))
        _c, k = anfrage(self.url, 'GET', f"/api/harness/karten/{karte['karte_id']}")
        self.assertEqual(k['status'], 'offen', 'die Karte bleibt offen')
        anfrage(self.url, 'POST', f"/api/harness/karten/{karte['karte_id']}", {'weg': 'ablehnen'})
        self.warte_threads()

    def test_v6_export_weg(self):
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef', 'titel': 'Export'})
        code, out = anfrage(self.url, 'GET', f"/api/harness/sitzungen/{kopf['id']}/export")
        self.assertEqual(code, 200, out)
        self.assertTrue(out['markdown'].startswith('# Export\n')); self.assertEqual(out['dateiname'], kopf['id'] + '-export.md')
        self.assertIn('Projekt Prüfprojekt', out['markdown'])
        code, _ = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/export", {})
        self.assertEqual(code, 404)

    def test_einstufen_mit_projekt(self):
        code, e = anfrage(self.url, 'POST', '/api/harness/einstufen', {'werkzeug': 'datei_schreiben', 'ziel': 'lauf/x.py', 'projekt': 'pruef'})
        self.assertEqual((code, e['stufe'], e['regel']), (200, 'frei', 'schreiben-schreibbereich'))
        code, e = anfrage(self.url, 'POST', '/api/harness/einstufen', {'werkzeug': 'datei_schreiben', 'ziel': 'lauf/x.py'})
        self.assertEqual((code, e['stufe']), (200, 'captain'), 'ohne Projekt kein Schreibbereich')

    def test_v1_modelle_passt_urteil_vom_router(self):
        code, v = anfrage(self.url, 'GET', '/api/harness/modelle')
        self.assertEqual(code, 200, v)
        self.assertIn('modelle', v); self.assertIn('frei_vram_gb', v)
        for m in v['modelle']:
            self.assertIn(m['passt'], (True, False, None))
            if m['passt'] is False: self.assertTrue(m['grund'])
            for feld in ('beschreibung', 'einsatz', 'kontexte_ungemessen', 'kontext_gemessen_bis'): self.assertIn(feld, m)
            self.assertTrue(all(t > (m['kontext_gemessen_bis'] or 0) for t in m['kontexte_ungemessen']), 'ungemessen = ueber der Messgrenze')
            self.assertFalse(set(m['kontexte_ungemessen']) & set(m['kontexte']), 'eine Stufe ist waehlbar oder ungemessen, nie beides')
        self.assertEqual(v['modelle'], sorted(v['modelle'], key=lambda e: (not e['geladen'], not e['passt'], not e['gemessen'], e['bedarf_vram_gb'] or 0, e['id'])))

    def test_herkunft_auch_auf_nachricht_patch_delete_stopp(self):
        h = self.hub.harness
        for method, path in (('POST', '/api/harness/sitzungen/S-00000001/nachricht'), ('PATCH', '/api/harness/sitzungen/S-00000001'),
                             ('DELETE', '/api/harness/sitzungen/S-00000001'), ('POST', '/api/harness/antworten/A-00000001/stopp'),
                             ('POST', '/api/harness/karten/K-00000001')):
            self.assertTrue(h.herkunft_verlangt(method, path), (method, path))
        self.assertFalse(h.herkunft_verlangt('GET', '/api/harness/sitzungen/S-00000001'))
        self.assertFalse(h.herkunft_verlangt('POST', '/api/harness/sitzungen'), 'Anlegen bleibt frei')
        from sedra_runtime import uix_server
        self.assertTrue(uix_server.HERKUNFT_WEGE.fullmatch('/api/model/load'))
        self.assertTrue(uix_server.HERKUNFT_WEGE.fullmatch('/api/model/unload'))


HARNESS = UIX / 'shells' / 'harness'


class StromLeserRein(unittest.TestCase):
    """V8 (P3): der Strom-Leser als Modul – SSE-Zerlegung, Phasen, Texte – mit node, ohne Browser."""

    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_zerlegen_teilstuecke_kommentare_und_kaputte_daten(self):
        out = run_js([HARNESS / 'strom.js'], """
          const Z = box.sedraHarness.strom.zerlegen;
          const a = Z('id: 1\\nevent: zug.start\\ndata: {"zug":1}\\n\\n: herzschlag\\n\\nid: 2\\nevent: text.ungeprueft\\ndata: {"stueck":"Hal');
          const b = Z(a.rest + 'lo"}\\n\\nid: 3\\nevent: fehler\\ndata: {kaputt\\n\\nevent: ohne_id\\n\\n');
          console.log(JSON.stringify({a: a.ereignisse, rest: a.rest, b: b.ereignisse, brest: b.rest}));
        """)
        self.assertEqual(out['a'], [{'id': 1, 'event': 'zug.start', 'daten': {'zug': 1}}])
        self.assertTrue(out['rest'].startswith('id: 2'), 'ein halbes Ereignis bleibt im Rest')
        self.assertEqual(out['b'], [{'id': 2, 'event': 'text.ungeprueft', 'daten': {'stueck': 'Hallo'}},
                                    {'id': 3, 'event': 'fehler', 'daten': {}},
                                    {'id': None, 'event': 'ohne_id', 'daten': {}}])
        self.assertEqual(out['brest'], '')

    def test_phasen_und_texte(self):
        out = run_js([HARNESS / 'strom.js'], """
          const S = box.sedraHarness.strom;
          console.log(JSON.stringify([S.phaseFuer('zug.start'), S.phaseFuer('text.ungeprueft'), S.phaseFuer('werkzeug.start', {name: 'befehl'}), S.phaseFuer('karte'),
            S.phaseFuer('ende'), S.phaseFuer('kontext') === undefined, S.dauerText(0.25), S.dauerText(12.34), S.dauerText(null), S.denkText({t: 13.5}, 1.0), S.denkText({verborgen: true})]));
        """)
        self.assertEqual(out, ['denkt', 'schreibt', 'Werkzeug befehl', 'wartet auf Freigabe', None, True, '250 ms', '12,3 s', '', 'Denkt nach · 12,5 s',
                               'Denkt nach (scharfer Modus: Inhalt erst nach dem Urteil)'])

    def test_lesen_ruft_je_ereignis_und_endet_mit_ende(self):
        out = run_js([HARNESS / 'strom.js'], """
          const S = box.sedraHarness.strom;
          const stuecke = ['id: 5\\nevent: zug.start\\ndata: {}\\n\\nid: 6\\nevent: text.ungeprueft\\nda', 'ta: {"stueck":"x"}\\n\\n', 'id: 7\\nevent: ende\\ndata: {"ende":"erledigt"}\\n\\nid: 8\\nevent: nie\\n\\n'];
          box.TextDecoder = TextDecoder; const enc = new TextEncoder();
          let i = 0, kopf = null, url = null;
          box.fetch = async (u, opts)=>{ url = u; kopf = opts.headers; return {ok: true, body: {getReader(){ return {read: async ()=>i < stuecke.length ? {value: enc.encode(stuecke[i++]), done: false} : {value: undefined, done: true}}; }}}; };
          const z = {letzte: 4, fertig: false}; const gesehen = []; let abgebrochen = 0;
          S.lesen('A-00000001', z, (n, d)=>gesehen.push([n, d]), {'X-SEDRA-Shell': 'harness'}, {signal: null, abort(){ abgebrochen++; }})
            .then(r=>console.log(JSON.stringify({r, z, gesehen, abgebrochen, url, last: kopf['Last-Event-ID'], shell: kopf['X-SEDRA-Shell']})));
        """)
        self.assertEqual(out['r'], True); self.assertEqual(out['z'], {'letzte': 7, 'fertig': True}); self.assertEqual(out['abgebrochen'], 1)
        self.assertEqual([g[0] for g in out['gesehen']], ['zug.start', 'text.ungeprueft', 'ende'], 'nach ende kommt nichts mehr')
        self.assertEqual((out['url'], out['last'], out['shell']), ('/api/harness/antworten/A-00000001/strom', '4', 'harness'))


class P1Befunde(unittest.TestCase):
    def test_a10_liste_liest_nur_geaenderte_dateien(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Sitzungen(Path(tmp))
            a, b = s.anlegen('p')['id'], s.anlegen('p')['id']
            s.anhaengen(a, {'typ': 'captain', 'text': 'x'})
            erste = s.liste()
            self.assertEqual(sorted(x['id'] for x in erste), sorted([a, b]))
            gelesen = []
            alt = s.laden
            s.laden = lambda sid: (gelesen.append(sid), alt(sid))[1]
            zweite = s.liste()
            self.assertEqual(gelesen, [], 'nichts geändert → nichts gelesen')
            self.assertEqual(zweite, erste)
            time.sleep(0.01)
            s.anhaengen(b, {'typ': 'captain', 'text': 'y'})
            s.liste()
            self.assertEqual(gelesen, [b], 'nur die geänderte Datei')
            self.assertEqual(next(x for x in s.liste() if x['id'] == b)['nachrichten'], 1)
            s.loeschen(a)
            self.assertEqual([x['id'] for x in s.liste()], [b])

    def test_a24_gesperrter_ordner_erscheint_nicht(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Path(tmp)
            (w / 'local_config').mkdir(); (w / 'local_config' / 'x.yaml').write_text('a: 1', encoding='utf-8')
            (w / 'docs').mkdir(); (w / 'docs' / 'a.md').write_text('x', encoding='utf-8')
            regeln = katalog.laden(w)['regeln']
            pfade = [e['pfad'] for e in dateien.liste(w, regeln)['eintraege']]
            self.assertIn('docs', pfade)
            self.assertNotIn('local_config', pfade)

    def test_v1_modelle_mit_urteil(self):
        from sedra_runtime.harness import api as harness_api
        self.assertTrue(harness_api.WEG.fullmatch('/api/harness/modelle'))
        self.assertTrue(harness_api.WEG.fullmatch('/api/harness/vorgaben'))

    def test_v6_export_markdown(self):
        s = {'kopf': {'id': 'S-00000001', 'projekt': 'pruef', 'angelegt': '2026-11-01T21:00:00+01:00', 'vorlage': None}, 'titel': 'Textstats bauen', 'modell': 'qwen',
             'eintraege': [{'typ': 'captain', 'text': 'Schreib textstats.py', 'zeit': '2026-11-01T21:00:01+01:00'},
                           {'typ': 'karte', 'karte_id': 'K-1', 'werkzeug': 'datei_schreiben', 'ziel': 'textstats.py', 'zustand': 'offen'},
                           {'typ': 'karte', 'karte_id': 'K-1', 'entscheidung': 'sitzung', 'von': 'captain', 'notiz': None, 'zustand': 'beantwortet'},
                           {'typ': 'erlaubnis', 'karte_id': 'K-1', 'werkzeug': 'datei_schreiben', 'muster': '*', 'aktiv': True},
                           {'typ': 'werkzeug', 'name': 'befehl', 'args': {'befehl': 'python -m unittest'}, 'status': 'ok', 'stufe': 'frei', 'regel': 'befehl-unittests', 'dauer_s': 2.5, 'ergebnis': 'x' * 2000},
                           {'typ': 'modell', 'text': 'Fertig.', 'ende': 'erledigt', 'zuege': 3, 'denken_zeichen': 42, 'denken_text': 'hmm', 'zeit': '2026-11-01T21:01:00+01:00'}]}
        md = export.markdown(s, 'S-00000001', 'Prüfprojekt')
        self.assertTrue(md.startswith('# Textstats bauen\n'))
        for teil in ('## Captain · 21:00', 'Schreib textstats.py', '**Freigabe K-1** · datei_schreiben `textstats.py` · sitzung (gilt für diese Sitzung) von captain',
                     'Erlaubnis für diese Sitzung: datei_schreiben `*`', '**befehl**', '→ ok (frei · befehl-unittests) · 2.5 s', 'Zeichen, gekürzt)',
                     '## SEDRA · 21:01 · erledigt · 3 Züge', 'Dachte nach · 42 Zeichen', 'hmm', 'Fertig.', 'runtime_data/harness/sitzungen/S-00000001.jsonl'):
            self.assertIn(teil, md, teil)
        self.assertNotIn('x' * 1300, md, 'Werkzeugausgabe gekürzt')
        self.assertEqual(export.dateiname('S-00000001', 'Textstats bauen!'), 'S-00000001-textstats-bauen.md')

    def test_a6_fehlertexte(self):
        from sedra_runtime.uix_server import FRIENDLY_400
        for code in ('antwort_laeuft', 'zu_viele_antworten', 'karte_offen', 'titel_leer', 'zweck_fehlt', 'projekt_unbekannt', 'erlaubnis_unbekannt'):
            self.assertIn(code, FRIENDLY_400)
            self.assertNotIn('_', FRIENDLY_400[code].split(' ')[0], 'ein Satz, kein Code')


class ModellHalten(unittest.TestCase):
    """P0 M2: laufende Antworten, offene Karten und der Nachlauf halten das Modell; der Supervisor fragt den Haken."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-m2-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'docs').mkdir(parents=True)
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: pruef\n    name: Prüfprojekt\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        self.hub.harness.geladen = lambda: (MODELL, None)
        self.hub.harness._zuletzt = (0.0, None)

    def test_supervisor_fragt_den_haken(self):
        sup = self.hub.runtime.job_supervisor
        self.assertEqual(sup.in_use_extra, self.hub.harness.modelle_in_gebrauch)
        self.hub.harness._aktiv['A-X'] = 'qwen-9b'
        try:
            self.assertIn('qwen-9b', sup._models_in_use())
        finally:
            self.hub.harness._aktiv.pop('A-X')
        self.assertNotIn('qwen-9b', sup._models_in_use())
        sup.in_use_extra = lambda: 1 / 0
        try:
            self.assertEqual(sup._models_in_use(), set(), 'ein kaputter Haken bricht nichts')
        finally:
            sup.in_use_extra = self.hub.harness.modelle_in_gebrauch

    def test_laufende_antwort_nachlauf_und_offene_karte(self):
        h = self.hub.harness
        frei = threading.Event()

        def langsam(mission, request):
            frei.wait(5)
            request['stream']('antwort', 'ok')
            return {'status': 'completed', 'model_result': {'content': 'ok', 'message': {'role': 'assistant', 'content': 'ok'}, 'usage': None}}
        h.execute = langsam
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef'})
        code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'hallo'})
        self.assertEqual(code, 200, out)
        modell = MODELL[0].get('identifier') or MODELL[0].get('modelKey')
        self.assertIn(modell, h.modelle_in_gebrauch(), 'läuft → in Gebrauch')
        frei.set()
        strom(self.url, out['antwort_id'])
        for _ in range(100):
            if not h.threads: break
            time.sleep(0.02)
        self.assertIn(modell, h.modelle_in_gebrauch(), 'Nachlauf nach dem Ende')
        h._zuletzt = (h._zuletzt[0] - 1000, h._zuletzt[1])
        self.assertNotIn(modell, h.modelle_in_gebrauch(), 'nach dem Nachlauf frei')
        # offene Werkzeug-Karte: alle geladenen Modelle bleiben
        h.execute = Skript([('calls', [('datei_schreiben', {'pfad': 'docs/k.md', 'inhalt': 'x\n'})]), ('text', 'ok')])
        code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'schreib'})
        ev = strom(self.url, out['antwort_id'])
        kid = next(e[2] for e in ev if e[1] == 'karte')['karte_id']
        for _ in range(100):
            if not h.threads: break
            time.sleep(0.02)
        h._zuletzt = (0.0, None)
        self.assertIn(modell, h.modelle_in_gebrauch(), 'offene Karte hält das Modell')
        anfrage(self.url, 'POST', f'/api/harness/karten/{kid}', {'weg': 'ablehnen'})
        for _ in range(100):
            if not h.threads: break
            time.sleep(0.02)
        h._zuletzt = (0.0, None)
        self.assertNotIn(modell, h.modelle_in_gebrauch())

    def test_a1_kaputte_vorlage_laesst_keine_antwort_haengen(self):
        h = self.hub.harness
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef'})
        alt = h._vorlage
        h._vorlage = lambda s: (_ for _ in ()).throw(ValueError('vorlage_kaputt: Prüffall'))
        try:
            code, body = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'hallo'})
            self.assertEqual((code, body.get('code', '')[:15]), (400, 'vorlage_kaputt:'))
        finally:
            h._vorlage = alt
        _c, liste = anfrage(self.url, 'GET', '/api/harness/sitzungen')
        self.assertEqual(liste['laufend'], {}, 'keine Antwort bleibt „laufend“ (A1)')
        self.assertEqual(h.stroeme.laufende(), [])
        code, out = anfrage(self.url, 'DELETE', f"/api/harness/sitzungen/{kopf['id']}")
        self.assertEqual(code, 200, 'die Sitzung lässt sich verschieben')
        _c, s = anfrage(self.url, 'GET', f"/api/harness/sitzungen/{kopf['id']}")
        self.assertEqual(_c, 404)

    def test_vorgaben_und_auto_laden_nur_bei_frei(self):
        h = self.hub.harness
        self.hub._last_recipe = lambda: ''
        code, v = anfrage(self.url, 'GET', '/api/harness/vorgaben')
        self.assertEqual((code, v['rezept_standard'], v['auto_laden']), (200, None, None))
        self.assertTrue(v['auto_laden_grund'].startswith('kein_rezept'))
        self.hub._last_recipe = lambda: 'coder.local_primary'
        code, v = anfrage(self.url, 'GET', '/api/harness/vorgaben')
        self.assertEqual((v['rezept_standard'], v['auto_laden']), ('coder.local_primary', None), 'die Vorlage stellt modell_laden nicht frei')
        self.assertTrue(v['auto_laden_grund'].startswith('katalog_captain'), v['auto_laden_grund'])
        h.geladen = lambda: ([], None)
        code, out = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef'})
        code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{out['id']}/nachricht", {'text': 'hallo'})
        self.assertEqual((code, out['status'], out['auto_laden']), (200, 'kein_modell', None))
        # eigener Katalog mit modell_laden frei → Auto-Laden erlaubt
        katalog_datei = self.hub.project_root / 'local_config' / 'freigabe_katalog.yaml'
        katalog_datei.write_text('freigabe_katalog:\n  version: 1\n  regeln:\n    - id: modelle-frei\n      werkzeug: modell_laden\n      muster: ["coder.*"]\n      stufe: frei\n      begruendung: Der Stick lädt selbst.\n', encoding='utf-8')
        try:
            code, v = anfrage(self.url, 'GET', '/api/harness/vorgaben')
            self.assertEqual(v['auto_laden'], {'rezept': 'coder.local_primary', 'regel': 'modelle-frei'})
            code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{out.get('sitzung_id') or anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef'})[1]['id']}/nachricht", {'text': 'hallo'})
            self.assertEqual((out['status'], out['auto_laden']['rezept']), ('kein_modell', 'coder.local_primary'))
        finally:
            katalog_datei.unlink()
            del self.hub._last_recipe


class OrdnerOeffnen(unittest.TestCase):
    """P0 M3: Ordner öffnen als Antrag mit Gate; Laufzeitdatei statt local_config; Vorgaben."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-m3-')
        cls.projekt = Path(cls.tmp.name) / 'project'
        (cls.projekt / 'local_config').mkdir(parents=True)
        cls.ordner = Path(cls.tmp.name) / 'Mein Projekt'
        (cls.ordner / 'src').mkdir(parents=True)
        cls.hub = UIXHub(cls.projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def offen(self, mission_id):
        return next((d for d in self.hub.decisions_view()['items'] if d.get('mission_id') == mission_id), None)

    def audit(self, event):
        rows = [json.loads(l) for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        return [r['payload'] for r in rows if r['event_type'] == event]

    def test_rein_neues_projekt(self):
        self.assertEqual(projekte.id_aus('Mein Projekt', ['mein-projekt']), 'mein-projekt-2')
        self.assertEqual(projekte.id_aus('--Ärger--'), 'rger')
        with self.assertRaises(projekte.ProjektFehler):
            projekte.neues_projekt(str(self.projekt / 'local_config'), sperrzonen=[self.projekt / 'local_config'])
        with self.assertRaises(projekte.ProjektFehler):
            projekte.neues_projekt('relativ/pfad')
        with self.assertRaises(projekte.ProjektFehler):
            projekte.neues_projekt(str(self.ordner), schreibbereich=['../x'])

    def test_antrag_schreibt_nichts_freigabe_schreibt_laufzeitdatei(self):
        code, body = anfrage(self.url, 'POST', '/api/harness/projekte', {'wurzel': str(self.projekt / 'local_config')})
        self.assertEqual((code, body.get('code', '')[:16]), (400, 'wurzel_gesperrt:'))
        code, out = anfrage(self.url, 'POST', '/api/harness/projekte', {'wurzel': str(self.ordner), 'schreibbereich': ['src/**']})
        self.assertEqual(code, 200, out)
        self.assertEqual((out['projekt']['id'], out['projekt']['name'], out['projekt']['schreibbereich']), ('mein-projekt', 'Mein Projekt', ['src/**']))
        self.assertFalse(projekte.laufzeit_pfad(self.projekt).exists(), 'der Antrag schreibt nichts')
        self.assertFalse((self.projekt / 'local_config' / 'harness_projekte.yaml').exists(), 'nie local_config')
        d = self.offen(out['mission_id'])
        self.assertEqual(d['kind'], 'request:harness_projekt')
        self.assertEqual([p['id'] for p in anfrage(self.url, 'GET', '/api/harness/projekte')[1]['projekte']], ['sedra-entwicklung'])
        r = self.hub.decide({'id': d['id'], 'way': 'freigeben_und_anwenden'})
        self.assertNotIn('error', r, r)
        liste = anfrage(self.url, 'GET', '/api/harness/projekte')[1]['projekte']
        self.assertEqual([(p['id'], p.get('quelle')) for p in liste], [('sedra-entwicklung', None), ('mein-projekt', 'laufzeit')])
        self.assertTrue(projekte.laufzeit_pfad(self.projekt).is_file())
        self.assertFalse((self.projekt / 'local_config' / 'harness_projekte.yaml').exists())
        self.assertEqual([p['projekt'] for p in self.audit('HARNESS_PROJEKT_ADDED')], ['mein-projekt'])
        # eine Sitzung darin schreiben: im Schreibbereich frei, außerhalb nie
        code, body = anfrage(self.url, 'POST', '/api/harness/projekte', {'wurzel': str(self.ordner)})
        self.assertEqual((code, body.get('code', '')[:20]), (400, 'ordner_schon_projekt'))
        code, e = anfrage(self.url, 'POST', '/api/harness/einstufen', {'werkzeug': 'datei_schreiben', 'ziel': 'src/a.py', 'projekt': 'mein-projekt'})
        self.assertEqual((e['stufe'], e['regel']), ('frei', 'schreiben-schreibbereich'))
        # Vorgaben
        code, v = anfrage(self.url, 'POST', '/api/harness/vorgaben', {'projekt_standard': 'mein-projekt', 'rezept_standard': 'coder.local_primary'})
        self.assertEqual((code, v['projekt_standard'], v['rezept_standard']), (200, 'mein-projekt', 'coder.local_primary'))
        code, v = anfrage(self.url, 'GET', '/api/harness/vorgaben')
        self.assertEqual((v['projekt_standard'], v['rezept_standard']), ('mein-projekt', 'coder.local_primary'))
        code, body = anfrage(self.url, 'POST', '/api/harness/vorgaben', {'projekt_standard': 'gibt-es-nicht'})
        self.assertEqual((code, body.get('code')), (400, 'projekt_unbekannt'))
        code, v = anfrage(self.url, 'POST', '/api/harness/vorgaben', {'rezept_standard': None})
        self.assertEqual((v['projekt_standard'], v['rezept_standard']), ('mein-projekt', None))
        self.assertTrue(list(projekte.laufzeit_pfad(self.projekt).parent.glob('projekte.yaml.bak-*')), 'Sicherung beim Überschreiben')
        self.assertEqual([p['id'] for p in anfrage(self.url, 'GET', '/api/harness/projekte')[1]['projekte']], ['sedra-entwicklung', 'mein-projekt'], 'Vorgaben lassen die Projekte stehen')

    def test_stale_wenn_die_datei_sich_aendert(self):
        ordner2 = Path(self.tmp.name) / 'zwei'; ordner2.mkdir(exist_ok=True)
        code, out = anfrage(self.url, 'POST', '/api/harness/projekte', {'wurzel': str(ordner2)})
        self.assertEqual(code, 200, out)
        anfrage(self.url, 'POST', '/api/harness/vorgaben', {'rezept_standard': 'x.y'})       # ändert die Laufzeitdatei nach dem Antrag
        d = self.offen(out['mission_id'])
        r = self.hub.decide({'id': d['id'], 'way': 'freigeben_und_anwenden'})
        self.assertIn('binding_stale', json.dumps(r))
        self.assertNotIn('zwei', [p['id'] for p in anfrage(self.url, 'GET', '/api/harness/projekte')[1]['projekte']])
        self.assertTrue(self.hub.harness.herkunft_verlangt('POST', '/api/harness/projekte'))
        self.assertTrue(self.hub.harness.herkunft_verlangt('POST', '/api/harness/vorgaben'))


if __name__ == '__main__':
    unittest.main()
