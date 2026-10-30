"""N1/N2 der Harness-Shell Stufe 5 (G2 §4/§5, D-U2/D-U4): Katalog und Grenzen werden nur über einen Antrag mit Gate geschrieben.
Antrag schreibt nichts; Freigeben schreibt mit Sicherung und Audit; geänderter Stand → stale; ungültiger Entwurf → 400 mit Satz;
Lockerung/weites Muster als Risiko am Gate; Herkunft aus einem Harness-Prozess → 403; entfernen → Vorlage gilt wieder."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.harness import antraege, katalog, vorlagen
from guppi_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, anfrage

KATALOG = 'local_config/freigabe_katalog.yaml'


def vorlage_regeln():
    return katalog.pruefen(yaml.safe_load(katalog.VORLAGE.read_text(encoding='utf-8')))


class ReinTests(unittest.TestCase):
    def test_befunde_weites_muster_lockerung_und_fehlende_verbotene(self):
        vorlage = vorlage_regeln()
        entwurf = [dict(r) for r in vorlage]
        geheim = next(r for r in entwurf if r['id'] == 'lesen-geheim')
        geheim['stufe'] = 'captain'
        entwurf.append({'id': 'alles-schreiben', 'werkzeug': ['datei_schreiben'], 'muster': ['**'], 'stufe': 'frei', 'begruendung': 'Probe.'})
        entwurf = katalog.pruefe_entwurf(entwurf)
        befunde, zahlen = katalog.befunde(entwurf, vorlage, vorlage)
        self.assertTrue(any('Lockerung' in b and 'lesen-geheim' in b for b in befunde), befunde)
        self.assertTrue(any('weites Muster' in b and 'alles-schreiben' in b for b in befunde), befunde)
        self.assertEqual(zahlen['neu'], ['alles-schreiben'])
        self.assertEqual(zahlen['geaendert'], ['lesen-geheim'])
        ohne = [r for r in vorlage if r['id'] != 'lesen-geheim']
        befunde, zahlen = katalog.befunde(ohne, vorlage, vorlage)
        self.assertTrue(any('verboten' in b and 'fehlt' in b for b in befunde), befunde)
        self.assertEqual(zahlen['entfernt'], ['lesen-geheim'])

    def test_hash_ist_stabil_und_entwurf_wird_geprueft(self):
        regeln = vorlage_regeln()
        self.assertEqual(katalog.hash_von(regeln), katalog.hash_von(list(reversed(list(reversed(regeln))))))
        with self.assertRaises(katalog.KatalogFehler):
            katalog.pruefe_entwurf([{'id': 'X', 'werkzeug': ['datei_lesen'], 'muster': ['a'], 'stufe': 'frei', 'begruendung': 'x'}])

    def test_schreiben_sichert_und_entfernen_laesst_vorlage_gelten(self):
        with tempfile.TemporaryDirectory() as tmp:
            regeln = vorlage_regeln()
            out = katalog.schreiben(tmp, regeln)
            self.assertIsNone(out['sicherung'])
            datei = Path(tmp) / KATALOG
            self.assertTrue(datei.is_file())
            self.assertTrue(datei.read_text(encoding='utf-8').startswith('# Freigabe-Katalog'))
            self.assertEqual(katalog.laden(tmp)['quelle'], 'local_config')
            out2 = katalog.schreiben(tmp, regeln[:-1])
            self.assertTrue(Path(out2['sicherung']).is_file(), 'die zweite Schreibung sichert die erste')
            self.assertEqual(len(katalog.laden(tmp)['regeln']), len(regeln) - 1)
            out3 = katalog.entfernen(tmp)
            self.assertTrue(out3['entfernt'] and Path(out3['sicherung']).is_file())
            self.assertFalse(datei.exists())
            self.assertEqual(katalog.laden(tmp)['quelle'], 'vorlage')
            self.assertEqual(katalog.entfernen(tmp), {'entfernt': False, 'sicherung': None})

    def test_grenzen_schreiben_kopiert_nur_mit_anderem_max_zuege(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = vorlagen.grenzen_schreiben(tmp, 'bauagent', 8)
            self.assertEqual(out['quelle_vorher'], 'repo')
            v = vorlagen.laden(tmp, 'bauagent')
            self.assertEqual((v['quelle'], v['max_zuege']), ('local_config', 8))
            repo = vorlagen.laden(tmp, 'bauagent', repo_dir=vorlagen.VORLAGEN_DIR) if False else None  # noqa: F841 – Repo-Datei bleibt (unten geprüft)
            self.assertEqual(yaml.safe_load((vorlagen.VORLAGEN_DIR / 'bauagent.yaml').read_text(encoding='utf-8'))['harness_vorlage']['max_zuege'], 24)
            out2 = vorlagen.grenzen_schreiben(tmp, 'bauagent', 12)
            self.assertTrue(Path(out2['sicherung']).is_file())
            with self.assertRaises(vorlagen.VorlageFehler):
                vorlagen.grenzen_schreiben(tmp, 'bauagent', 3)
            with self.assertRaises(vorlagen.VorlageFehler):
                vorlagen.grenzen_schreiben(tmp, 'gibtsnicht', 8)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-katalog-')
        cls.projekt = Path(cls.tmp.name) / 'project'
        (cls.projekt / 'local_config').mkdir(parents=True)
        cls.hub = UIXHub(cls.projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        datei = self.projekt / KATALOG
        if datei.exists():
            datei.unlink()
        for p in (self.projekt / 'local_config').glob('freigabe_katalog.yaml.bak-*'):
            p.unlink()

    def ereignisse(self):
        return [json.loads(l)['event_type'] for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]

    def offen(self, mission_id):
        items = self.hub.decisions_view()['items']
        return next((d for d in items if d.get('mission_id') == mission_id), None)

    def entscheiden(self, mission_id, way='freigeben_und_anwenden'):
        d = self.offen(mission_id)
        self.assertIsNotNone(d, 'der Antrag steht im Posteingang')
        return self.hub.decide({'id': d['id'], 'way': way})

    def test_antrag_schreibt_nichts_freigeben_schreibt_mit_sicherung_und_audit(self):
        regeln = vorlage_regeln()
        entwurf = [dict(r) for r in regeln] + [{'id': 'docs-frei', 'werkzeug': ['datei_schreiben'], 'muster': ['docs/notizen/**'], 'stufe': 'frei',
                                                'begruendung': 'Notizen sind ungefährlich.'}]
        code, out = anfrage(self.url, 'POST', '/api/harness/katalog/antrag', {'regeln': entwurf})
        self.assertEqual(code, 200, out)
        self.assertFalse((self.projekt / KATALOG).exists(), 'der Antrag schreibt nichts')
        self.assertEqual(out['zahlen']['neu'], ['docs-frei'])
        d = self.offen(out['mission_id'])
        self.assertEqual(d['kind'], 'request:harness_katalog')
        self.assertTrue(any('1 neu' in r for r in d.get('risks', [])), d)
        ergebnis = self.entscheiden(out['mission_id'])
        self.assertEqual(ergebnis['result']['status'], 'applied', ergebnis)
        self.assertTrue((self.projekt / KATALOG).is_file())
        _, k = anfrage(self.url, 'GET', '/api/harness/katalog')
        self.assertEqual(k['quelle'], 'local_config')
        self.assertIn('docs-frei', [r['id'] for r in k['regeln']])
        self.assertIn('HARNESS_KATALOG_WRITTEN', self.ereignisse())
        # zweiter Antrag: der Stand ist jetzt die Datei; die Sicherung entsteht beim Schreiben
        code, out2 = anfrage(self.url, 'POST', '/api/harness/katalog/antrag', {'regeln': regeln})
        self.assertEqual(code, 200, out2)
        self.assertEqual(out2['stand_hash'], katalog.hash_von(k['regeln']))
        self.entscheiden(out2['mission_id'])
        self.assertTrue(list((self.projekt / 'local_config').glob('freigabe_katalog.yaml.bak-*')), 'Sicherung vor dem Überschreiben')

    def test_stand_geaendert_macht_den_antrag_stale(self):
        regeln = vorlage_regeln()
        code, out = anfrage(self.url, 'POST', '/api/harness/katalog/antrag', {'regeln': regeln[:-1]})
        self.assertEqual(code, 200, out)
        katalog.schreiben(self.projekt, regeln[:-2])                   # der Captain ändert die Datei von Hand, bevor er freigibt
        ergebnis = self.entscheiden(out['mission_id'])
        self.assertEqual(ergebnis['result']['status'], 'binding_stale', ergebnis)
        self.assertEqual(len(katalog.laden(self.projekt)['regeln']), len(regeln) - 2, 'nichts überschrieben')
        self.assertIn('DESK_GATED_STALE', self.ereignisse())

    def test_ungueltiger_und_unveraenderter_entwurf_sind_400_mit_satz(self):
        code, out = anfrage(self.url, 'POST', '/api/harness/katalog/antrag', {'regeln': [{'id': 'kaputt'}]})
        self.assertEqual(code, 400, out)
        self.assertTrue(out['code'].startswith('entwurf_ungueltig:'), out)
        code, out = anfrage(self.url, 'POST', '/api/harness/katalog/antrag', {'regeln': vorlage_regeln()})
        self.assertEqual(code, 400, out)
        self.assertEqual(out['code'], 'entwurf_unveraendert')

    def test_lockerung_und_weites_muster_stehen_als_risiko_am_gate(self):
        entwurf = [dict(r) for r in vorlage_regeln()]
        next(r for r in entwurf if r['id'] == 'lesen-geheim')['stufe'] = 'captain'
        entwurf.append({'id': 'alles', 'werkzeug': ['befehl'], 'muster': ['*'], 'stufe': 'frei', 'begruendung': 'Probe.'})
        code, out = anfrage(self.url, 'POST', '/api/harness/katalog/antrag', {'regeln': entwurf})
        self.assertEqual(code, 200, out)
        risks = self.offen(out['mission_id']).get('risks', [])
        self.assertTrue(any('Lockerung' in r for r in risks), risks)
        self.assertTrue(any('weites Muster' in r for r in risks), risks)
        self.entscheiden(out['mission_id'], 'ablehnen')
        self.assertFalse((self.projekt / KATALOG).exists())

    def test_herkunft_aus_harness_prozess_ist_403(self):
        alt = self.hub.harness.herkunft.pruefen
        self.hub.harness.herkunft.pruefen = lambda *_a: {'ok': False, 'grund': 'harness_prozess'}
        try:
            for weg in ('/api/harness/katalog/antrag', '/api/harness/katalog/entfernen', '/api/harness/vorlagen/grenzen'):
                code, out = anfrage(self.url, 'POST', weg, {'regeln': []})
                self.assertEqual(code, 403, (weg, out))
            code, _ = anfrage(self.url, 'GET', '/api/harness/katalog')
            self.assertEqual(code, 200, 'Lesen bleibt frei')
        finally:
            self.hub.harness.herkunft.pruefen = alt

    def test_entfernen_laesst_die_vorlage_gelten(self):
        code, out = anfrage(self.url, 'POST', '/api/harness/katalog/entfernen', {})
        self.assertEqual(code, 400, 'ohne Datei des Captains gibt es nichts zu entfernen')
        katalog.schreiben(self.projekt, vorlage_regeln()[:-1])
        code, out = anfrage(self.url, 'POST', '/api/harness/katalog/entfernen', {})
        self.assertEqual(code, 200, out)
        self.assertTrue((self.projekt / KATALOG).is_file(), 'der Antrag entfernt nichts')
        ergebnis = self.entscheiden(out['mission_id'])
        self.assertEqual(ergebnis['result']['status'], 'applied', ergebnis)
        self.assertFalse((self.projekt / KATALOG).exists())
        _, k = anfrage(self.url, 'GET', '/api/harness/katalog')
        self.assertEqual(k['quelle'], 'vorlage')
        self.assertIn('HARNESS_KATALOG_REMOVED', self.ereignisse())

    def test_grenzen_antrag_und_freigabe(self):
        code, out = anfrage(self.url, 'POST', '/api/harness/vorlagen/grenzen', {'vorlage': 'bauagent', 'max_zuege': 99})
        self.assertEqual(code, 400, out)
        code, out = anfrage(self.url, 'POST', '/api/harness/vorlagen/grenzen', {'vorlage': 'bauagent', 'max_zuege': 24})
        self.assertEqual(code, 400); self.assertEqual(out['code'], 'grenze_unveraendert')
        code, out = anfrage(self.url, 'POST', '/api/harness/vorlagen/grenzen', {'vorlage': 'bauagent', 'max_zuege': 10})
        self.assertEqual(code, 200, out)
        self.assertFalse((self.projekt / 'local_config' / 'harness_vorlagen' / 'bauagent.yaml').exists(), 'der Antrag schreibt nichts')
        d = self.offen(out['mission_id'])
        self.assertEqual(d['kind'], 'request:harness_vorlage')
        ergebnis = self.entscheiden(out['mission_id'])
        self.assertEqual(ergebnis['result']['status'], 'applied', ergebnis)
        _, liste = anfrage(self.url, 'GET', '/api/harness/vorlagen')
        v = next(x for x in liste['vorlagen'] if x['id'] == 'bauagent')
        self.assertEqual((v['quelle'], v['max_zuege']), ('local_config', 10))
        self.assertEqual(yaml.safe_load((vorlagen.VORLAGEN_DIR / 'bauagent.yaml').read_text(encoding='utf-8'))['harness_vorlage']['max_zuege'], 24,
                         'die Datei im Repo bleibt')
        self.assertIn('HARNESS_VORLAGE_WRITTEN', self.ereignisse())

    def test_applier_registriert(self):
        from guppi_runtime.desk import gated
        self.assertIsNotNone(gated.applier(antraege.KIND_KATALOG))
        self.assertIsNotNone(gated.applier(antraege.KIND_VORLAGE))


if __name__ == '__main__':
    unittest.main()
