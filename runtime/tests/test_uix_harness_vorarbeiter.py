"""N4 der Harness-Shell Stufe 3 (mit Server, ohne Modell): Vorarbeiter-Freigabe – Szenarien S3-A und S3-B der Abnahme, Schutz gegen Selbstfreigabe (S1 bis S6),
Vorlegen, Frist, Rücknahme, Aufgabenvorschlag. Ersetzt werden nur `geladen` und `execute` (Modell)."""
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, MODELL, anfrage, strom
from test_uix_harness_freigabe import Skript

KATALOG = """freigabe_katalog:
  version: 1
  regeln:
    - {id: lesen-alles, werkzeug: [datei_lesen, dateien_auflisten, suchen], muster: ['**'], stufe: frei, begruendung: Lesen ändert nichts.}
    - {id: schreiben-docs, werkzeug: [datei_schreiben, datei_aendern], muster: ['docs/**'], stufe: vorarbeiter, begruendung: Dokumente prüft der Vorarbeiter.}
    - {id: schreiben-code, werkzeug: [datei_schreiben, datei_aendern], muster: ['runtime/**'], stufe: captain, begruendung: Code sieht der Captain.}
"""
NOTIZ = 'docs/notiz.md'
GUTE_BEGRUENDUNG = 'Der Diff ändert nur die Notiz, sonst nichts.'


class VorarbeiterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-vorarbeiter-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'docs').mkdir(parents=True)
        (cls.wurzel / 'runtime').mkdir()
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'freigabe_katalog.yaml').write_text(KATALOG, encoding='utf-8')
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: pruef\n    name: Prüfprojekt\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**, runtime/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        self.api = self.hub.harness
        self.api.geladen = lambda: (MODELL, None)
        (self.wurzel / NOTIZ).write_text('alt\n', encoding='utf-8')
        (self.wurzel / 'runtime' / 'x.py').write_text('a = 1\n', encoding='utf-8')
        self.api.vorarbeiter._schreiben({'projekte': {}, 'entscheidungen': {}})       # nur im Test: sauberer Stand
        for datei in list(self.api.aufgaben.ordner.glob('T-*.json')) if self.api.aufgaben.ordner.is_dir() else []:
            datei.unlink()
        self.modell = Skript([])
        self.api.execute = self.modell
        self.v = self.neu('vorarbeiter')
        self.b = self.neu('bauagent')
        code, out = anfrage(self.url, 'POST', '/api/harness/vorarbeiter', {'projekt': 'pruef', 'sitzung_id': self.v})
        self.assertEqual(code, 200, out)

    def neu(self, vorlage):
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef', 'vorlage': vorlage})
        self.assertEqual(code, 200, kopf)
        return kopf['id']

    def box(self, sid):
        return self.api._kiste(self.api._sitzung(sid))[0]

    def audit(self, event):
        rows = [json.loads(l) for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        return [r['payload'] for r in rows if r['event_type'] == event]

    @staticmethod
    def notiz(neu='neu'):
        return ('datei_aendern', {'pfad': NOTIZ, 'alt': 'alt', 'neu': neu})

    def karte_des_agenten(self, pfad=None, neu='neu'):
        (self.wurzel / NOTIZ).write_text('alt\n', encoding='utf-8')
        name, args = self.notiz(neu)
        if pfad:
            args = dict(args, pfad=pfad, alt='a = 1')
        r = self.box(self.b).aufruf(name, args, antwort_id='A-00000000')
        self.assertEqual(r['status'], 'wartet', r)
        return r['karte']

    def entscheiden(self, karte, weg='erlauben', begruendung=GUTE_BEGRUENDUNG, hash_=None, sid=None):
        return self.box(sid or self.v).aufruf('freigabe_entscheiden', {'karte_id': karte['karte_id'], 'weg': weg, 'begruendung': begruendung,
                                                                       'vorschau_hash': hash_ or karte['vorschau_hash']})

    # ---- S3-A
    def test_s3a_vorarbeiter_entscheidet_die_karte_des_agenten(self):
        self.modell.zuege = [('calls', [self.notiz()]), ('text', 'Notiz geändert.')]
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{self.b}/nachricht', {'text': 'Ändere die Notiz'})
        ev = strom(self.url, out['antwort_id'])
        karte = next(e[2] for e in ev if e[1] == 'karte')
        self.assertEqual((karte['an'], karte['stufe'], karte['regel']), ('vorarbeiter', 'vorarbeiter', 'schreiben-docs'))
        self.assertEqual(ev[-1][2]['ende'], 'wartet')
        liste = self.box(self.v).aufruf('freigaben_offen', {})
        self.assertEqual(liste['status'], 'ok')
        self.assertIn(karte['karte_id'], liste['ergebnis'])
        self.assertIn(karte['vorschau_hash'], liste['ergebnis'])
        self.assertEqual((self.wurzel / NOTIZ).read_text(encoding='utf-8'), 'alt\n', 'vor der Entscheidung nichts geschrieben')
        _c, entsch = anfrage(self.url, 'GET', '/api/decisions')
        eintrag = next(d for d in entsch['items'] if d['id'] == 'harness:' + karte['karte_id'])
        self.assertIn('beim Vorarbeiter', eintrag['title'], 'der Captain sieht auch die Karten beim Vorarbeiter')
        r = self.entscheiden(karte)
        self.assertEqual(r['status'], 'ok', r)
        self.assertEqual((self.wurzel / NOTIZ).read_text(encoding='utf-8'), 'neu\n')
        frei = self.audit('HARNESS_FREIGABE')[-1]
        self.assertEqual((frei['von'], frei['ueber'], frei['weg'], frei['begruendung']), (f'vorarbeiter:{self.v}', 'werkzeug', 'erlauben', GUTE_BEGRUENDUNG))
        _c, k = anfrage(self.url, 'GET', '/api/harness/karten/' + karte['karte_id'])
        self.assertEqual((k['status'], k['von'], k['an']), ('beantwortet', f'vorarbeiter:{self.v}', 'vorarbeiter'))
        self.assertTrue(k['neue_antwort_id'], 'die Schleife des Agenten läuft weiter')
        ev2 = strom(self.url, k['neue_antwort_id'])
        self.assertEqual(ev2[-1][2]['ende'], 'erledigt')

    # ---- S3-B und die Schutzregeln
    def test_s3b_captain_stufe_bleibt_beim_captain(self):
        k = self.karte_des_agenten('runtime/x.py')
        self.assertEqual((k['an'], k['stufe']), ('captain', 'captain'))
        r = self.entscheiden(k)
        self.assertEqual(r['status'], 'fehler')
        self.assertIn('nur_captain', r['ergebnis'])
        self.assertEqual(self.api.karten.laden(k['karte_id'])['status'], 'offen')
        self.assertEqual((self.wurzel / 'runtime' / 'x.py').read_text(encoding='utf-8'), 'a = 1\n')

    def test_selbstfreigabe_in_der_eigenen_sitzung(self):
        r = self.box(self.v).aufruf(*self.notiz())
        self.assertEqual((r['status'], r['karte']['an']), ('wartet', 'captain'), 'S2: in der eigenen Sitzung wirkt „vorarbeiter“ wie „captain“')
        self.assertIn('nur_captain', self.entscheiden(r['karte'])['ergebnis'])
        k = self.api.karten.laden(r['karte']['karte_id'])
        k['an'] = 'vorarbeiter'                                  # auch wenn die Karte irrtümlich an ihn ginge:
        self.api.karten.speichern(k)
        self.assertIn('selbstfreigabe', self.entscheiden(r['karte'])['ergebnis'])
        self.assertEqual((self.wurzel / NOTIZ).read_text(encoding='utf-8'), 'alt\n')

    def test_hash_begruendung_ernennung_und_recht(self):
        k = self.karte_des_agenten()
        self.assertIn('hash_veraltet', self.entscheiden(k, hash_='0' * 64)['ergebnis'])
        self.assertIn('begruendung_fehlt', self.entscheiden(k, begruendung='ok')['ergebnis'])
        self.assertIn('weg_unbekannt', self.entscheiden(k, weg='egal')['ergebnis'])
        v2 = self.neu('vorarbeiter')                             # hat das Recht, ist aber nicht ernannt
        self.assertIn('nicht_ernannt', self.entscheiden(k, sid=v2)['ergebnis'])
        r = self.box(self.b).aufruf('freigabe_entscheiden', {'karte_id': k['karte_id'], 'weg': 'erlauben', 'begruendung': GUTE_BEGRUENDUNG, 'vorschau_hash': k['vorschau_hash']})
        self.assertEqual(r['status'], 'fehler')                  # der Agent hat das Werkzeug nicht (Whitelist der Vorlage)
        self.assertEqual(self.api.karten.laden(k['karte_id'])['status'], 'offen')
        self.assertEqual((self.wurzel / NOTIZ).read_text(encoding='utf-8'), 'alt\n')

    def test_bremse_30_je_stunde(self):
        for _ in range(30):
            self.api.vorarbeiter.merken('pruef')
        k = self.karte_des_agenten()
        self.assertIn('zu_viele', self.entscheiden(k)['ergebnis'])
        self.assertEqual(self.api.karten.laden(k['karte_id'])['status'], 'offen')

    def test_ablehnen_und_vorlegen(self):
        k = self.karte_des_agenten()
        r = self.entscheiden(k, 'vorlegen', 'Das Logbuch betrifft den Captain, bitte selbst ansehen.')
        self.assertEqual(r['status'], 'ok', r)
        gelegt = self.api.karten.laden(k['karte_id'])
        self.assertEqual((gelegt['status'], gelegt['an'], gelegt['vorgelegt']['von']), ('offen', 'captain', f'vorarbeiter:{self.v}'))
        self.assertIn('nur_captain', self.entscheiden(k)['ergebnis'], 'nach dem Vorlegen entscheidet nur noch der Captain')
        k2 = self.karte_des_agenten(neu='anders')
        r = self.entscheiden(k2, 'ablehnen', 'Die Änderung gehört nicht zur Aufgabe.')
        self.assertEqual(r['status'], 'ok', r)
        self.assertEqual(self.api.karten.laden(k2['karte_id'])['entscheidung'], 'ablehnen')
        self.assertEqual((self.wurzel / NOTIZ).read_text(encoding='utf-8'), 'alt\n')

    def test_frist_laesst_die_karte_an_den_captain_fallen(self):
        k = self.karte_des_agenten()
        alt = self.api.karten.laden(k['karte_id'])
        alt['angelegt'] = (datetime.now().astimezone() - timedelta(minutes=20)).isoformat(timespec='seconds')
        self.api.karten.speichern(alt)
        code, oeff = anfrage(self.url, 'GET', '/api/harness/karten/' + k['karte_id'])
        self.assertEqual((code, oeff['an']), (200, 'captain'))
        self.assertTrue(oeff['frist_abgelaufen'])
        self.assertIn('nur_captain', self.entscheiden(k)['ergebnis'])

    # ---- HTTP: der Captain
    def test_http_antwort_ist_immer_der_captain_und_ruecknahme(self):
        k = self.karte_des_agenten()
        code, out = anfrage(self.url, 'POST', '/api/harness/karten/' + k['karte_id'], {'weg': 'ablehnen', 'notiz': 'nein', 'von': f'vorarbeiter:{self.v}'})
        self.assertEqual(code, 200, out)
        self.assertEqual(self.audit('HARNESS_FREIGABE')[-1]['von'], 'captain', '`von` aus der Nutzlast zählt nicht (S1)')
        self.assertEqual(anfrage(self.url, 'POST', f"/api/harness/karten/{k['karte_id']}/zuruecknehmen", {})[0], 400, 'das war keine Vorarbeiter-Entscheidung')
        k2 = self.karte_des_agenten(neu='drei')
        self.assertEqual(self.entscheiden(k2)['status'], 'ok')
        code, z = anfrage(self.url, 'POST', f"/api/harness/karten/{k2['karte_id']}/zuruecknehmen", {'grund': 'Doch nicht'})
        self.assertEqual(code, 200, z)
        self.assertEqual(z['zurueckgenommen']['grund'], 'Doch nicht')
        self.assertEqual(anfrage(self.url, 'POST', f"/api/harness/karten/{k2['karte_id']}/zuruecknehmen", {})[0], 400, 'nur einmal')
        self.assertIn('HARNESS_KARTE_ZURUECKGENOMMEN', [json.loads(l)['event_type'] for l in
                                                         self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()])
        _c, verlauf = anfrage(self.url, 'GET', f'/api/harness/sitzungen/{self.v}')
        self.assertTrue(any(e.get('entscheidung') == 'zurueckgenommen' for e in verlauf['eintraege']), 'auch in der Sitzung des Vorarbeiters vermerkt')

    def test_ernennung_braucht_das_recht_und_laesst_sich_entziehen(self):
        code, body = anfrage(self.url, 'POST', '/api/harness/vorarbeiter', {'projekt': 'pruef', 'sitzung_id': self.b})
        self.assertEqual((code, body['code'].split(':')[0]), (400, 'kein_vorarbeiter_recht'))
        v2 = self.neu('vorarbeiter')
        self.assertEqual(anfrage(self.url, 'POST', '/api/harness/vorarbeiter', {'projekt': 'pruef', 'sitzung_id': v2})[0], 200)
        _c, liste = anfrage(self.url, 'GET', '/api/harness/vorarbeiter')
        self.assertEqual(liste['vorarbeiter']['pruef']['sitzung_id'], v2)
        k = self.karte_des_agenten()
        self.assertIn('nicht_ernannt', self.entscheiden(k, sid=self.v)['ergebnis'], 'der bisherige Vorarbeiter ist es nicht mehr')
        self.assertEqual(self.entscheiden(k, sid=v2)['status'], 'ok')
        code, out = anfrage(self.url, 'DELETE', '/api/harness/vorarbeiter?projekt=pruef')
        self.assertEqual((code, out['entzogen']), (200, True))
        k2 = self.karte_des_agenten(neu='ohne')
        self.assertEqual(k2['an'], 'captain', 'ohne Vorarbeiter bleibt „vorarbeiter“ beim Captain')

    # ---- Aufgabenvorschlag
    def vorschlag(self, **kw):
        doc = {'titel': 'Notiz pflegen', 'zweck': 'Notiz pflegen', 'projekt': 'pruef', 'sitzungen': [self.b], 'erlaubt': [{'werkzeug': 'datei_aendern', 'muster': NOTIZ}],
               'ende': {'max_aufrufe': 3}}
        doc.update(kw)
        return self.box(self.v).aufruf('aufgabe_vorschlagen', doc)

    def test_aufgabe_vorschlagen_der_captain_entscheidet(self):
        r = self.vorschlag()
        self.assertEqual(r['status'], 'ok', r)
        karten = [k for k in self.api.karten.alle('offen') if k.get('art') == 'aufgabe']
        self.assertEqual(len(karten), 1)
        k = karten[0]
        self.assertEqual((k['an'], k['vorschlag_von']), ('captain', self.v))
        self.assertEqual(self.api.aufgaben.alle(), [], 'angelegt wird erst auf die Antwort des Captains')
        _c, entsch = anfrage(self.url, 'GET', '/api/decisions')
        self.assertEqual(next(d for d in entsch['items'] if d['id'] == 'harness:' + k['karte_id'])['kind'], 'harness_aufgabe')
        self.assertIn('nur_captain', self.entscheiden(k)['ergebnis'])
        # der Vorarbeiter bleibt ansprechbar, solange der Vorschlag offen ist
        self.modell.zuege = [('text', 'Ich warte auf den Captain.')]
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{self.v}/nachricht', {'text': 'Stand?'})
        self.assertEqual(code, 200, out)
        strom(self.url, out['antwort_id'])
        # der Captain kürzt und gibt frei
        code, out = anfrage(self.url, 'POST', '/api/harness/karten/' + k['karte_id'], {'weg': 'erlauben', 'aenderungen': {'max_aufrufe': 2}})
        self.assertEqual(code, 200, out)
        a = self.api.aufgaben.alle()
        self.assertEqual(len(a), 1)
        self.assertEqual((a[0]['von'], a[0]['vorschlag_von'], a[0]['ende']['max_aufrufe']), ('captain', self.v, 2))
        r = self.box(self.b).aufruf(*self.notiz('mit aufgabe'))
        self.assertEqual((r['status'], r['stufe']), ('ok', 'aufgabe'))
        self.assertEqual(self.box(self.v).aufruf('aufgabe_beenden', {'id': a[0]['id'], 'grund': 'fertig'})['status'], 'ok')
        self.assertEqual(self.api.aufgaben.laden(a[0]['id'])['status'], 'erledigt')

    def test_vorschlag_streng_und_ablehnen(self):
        for kw, grund in (({'erlaubt': [{'werkzeug': 'befehl', 'muster': 'git *'}]}, 'muster_weit'),
                          ({'sitzungen': [self.b, self.v]}, 'selbstfreigabe'),
                          ({'projekt': 'anderes'}, 'projekt_passt_nicht'),
                          ({'erlaubt': [{'werkzeug': 'datei_schreiben', 'muster': 'docs/skript.py'}, {'werkzeug': 'befehl', 'muster': 'python -c *'}]}, 'S9'),
                          ({'ende': {}}, 'ende_fehlt')):
            r = self.vorschlag(**kw)
            self.assertEqual(r['status'], 'fehler', kw)
            self.assertIn(grund, r['ergebnis'], kw)
        self.assertEqual([k for k in self.api.karten.alle('offen') if k.get('art') == 'aufgabe'], [])
        self.assertEqual(self.vorschlag()['status'], 'ok')
        k = next(k for k in self.api.karten.alle('offen') if k.get('art') == 'aufgabe')
        code, _ = anfrage(self.url, 'POST', '/api/harness/karten/' + k['karte_id'], {'weg': 'ablehnen', 'notiz': 'zu viel'})
        self.assertEqual(code, 200)
        self.assertEqual(self.api.aufgaben.alle(), [])

    def test_ohne_ernennung_keine_werkzeuge_wirken_und_agent_hat_sie_nicht(self):
        schemas = {s['function']['name'] for s in self.box(self.v).schemas()}
        self.assertTrue({'freigaben_offen', 'freigabe_entscheiden', 'aufgabe_vorschlagen', 'aufgabe_beenden'} <= schemas)
        schemas_b = {s['function']['name'] for s in self.box(self.b).schemas()}
        self.assertFalse(schemas_b & {'freigaben_offen', 'freigabe_entscheiden', 'aufgabe_vorschlagen', 'aufgabe_beenden', 'lauf_starten'})
        self.api.vorarbeiter.entziehen('pruef')
        self.assertIn('nicht_ernannt', self.box(self.v).aufruf('freigaben_offen', {})['ergebnis'])


if __name__ == '__main__':
    unittest.main()
