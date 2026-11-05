"""Selbstabbild: SEDRA-Abläufe als Prozessmodelle aus Quellen (Plan UIX Phase 5)."""
import tempfile
import unittest
from pathlib import Path

import yaml

from guppi_runtime.workflows import selbstabbild as sa
from guppi_runtime.workflows.policy import assessment
from guppi_runtime.workflows.process import metadata
from guppi_runtime.workflows.store import WorkflowStore


class Selbstabbild(unittest.TestCase):
    def test_alle_ablaeufe_sind_gueltige_nicht_ausfuehrbare_modelle(self):
        ablaeufe = sa.laden()
        self.assertGreaterEqual(len(ablaeufe), 6)
        for a in ablaeufe:
            doc = sa.modell(a)
            self.assertTrue(all(n.get('disabled') for n in doc['nodes']), a['id'])
            self.assertFalse(assessment(doc)['executable'], a['id'])
            kinds = [metadata(n)['kind'] for n in doc['nodes']]
            self.assertEqual(kinds.count('start'), 1)
            self.assertIn('end', kinds)
            for n in doc['nodes']:
                self.assertTrue(metadata(n)['original_notes'].startswith('Quelle: '))

    def test_menschliche_schritte_sind_rollen_nie_technische_freigaben(self):
        doc = sa.modell(next(a for a in sa.laden() if a['id'] == 'freigabe'))
        karte = next(n for n in doc['nodes'] if n['name'] == 'Freigabe-Karte beantworten')
        self.assertEqual(metadata(karte)['mode'], 'manual')
        self.assertEqual(metadata(karte)['role'], 'Captain')
        self.assertTrue(karte['type'].endswith('.noOp') and karte['disabled'])

    def test_entscheidung_hat_zwei_wege(self):
        doc = sa.modell(next(a for a in sa.laden() if a['id'] == 'freigabe'))
        zweige = doc['connections']['Schon erlaubt?']['main']
        self.assertEqual([[e['node'] for e in z] for z in zweige], [['Werkzeug ausführen'], ['Freigabe-Karte beantworten']])

    def test_quellen_stimmen_mit_dem_stand_ueberein(self):
        self.assertEqual(sa.pruefen(), [], 'Selbstabbild weicht vom Code ab: Quelle oder Abbild anpassen')

    def test_abweichung_wird_gemeldet_und_anlegen_verweigert(self):
        with tempfile.TemporaryDirectory() as tmp:
            kopie = Path(tmp) / 'sa.yaml'
            doc = yaml.safe_load(sa.KONFIG.read_text(encoding='utf-8'))
            doc['ablaeufe'][0]['schritte'][0]['quelle']['suche'] = 'diese_funktion_gibt_es_nicht'
            doc['ablaeufe'][1]['schritte'][0]['quelle']['datei'] = 'runtime/gibt_es_nicht.py'
            kopie.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding='utf-8')
            gruende = sorted(p['grund'] for p in sa.pruefen(kopie))
            self.assertEqual(gruende, ['datei_fehlt', 'text_nicht_mehr_vorhanden'])
            with self.assertRaises(ValueError) as ctx:
                sa.anlegen(WorkflowStore(tmp), kopie)
            self.assertIn('selbstabbild_quellen_abweichend', str(ctx.exception))
            self.assertEqual(WorkflowStore(tmp).listing(), [])

    def test_anlegen_ist_wiederholbar_und_erzeugt_nur_bei_aenderung_eine_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowStore(tmp)
            self.assertTrue(all(x['status'] == 'fehlt' for x in sa.abweichung(store)))
            erst = sa.anlegen(store)
            self.assertTrue(all(x['status'] == 'angelegt' and x['revision'] == 1 for x in erst))
            zweit = sa.anlegen(store)
            self.assertTrue(all(x['status'] == 'unveraendert' and x['revision'] == 1 for x in zweit))
            self.assertTrue(all(x['status'] == 'gleich' for x in sa.abweichung(store)))
            # Änderung eines Schrittnamens in der Konfiguration -> neue Revision, nicht neuer Ablauf
            kopie = Path(tmp) / 'sa.yaml'
            doc = yaml.safe_load(sa.KONFIG.read_text(encoding='utf-8'))
            doc['ablaeufe'][0]['schritte'][0]['ergebnis'] = 'Geänderte Beschreibung'
            kopie.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding='utf-8')
            self.assertEqual(sa.abweichung(store, kopie)[0]['status'], 'abweichend')
            neu = sa.anlegen(store, kopie)
            self.assertEqual((neu[0]['status'], neu[0]['revision']), ('aktualisiert', 2))
            self.assertEqual(len(store.listing()), len(erst))

    def test_kaputte_konfiguration_ist_ein_satz(self):
        with tempfile.TemporaryDirectory() as tmp:
            kopie = Path(tmp) / 'sa.yaml'
            doc = yaml.safe_load(sa.KONFIG.read_text(encoding='utf-8'))
            doc['ablaeufe'][0]['schritte'][0]['weiter'] = ['gibt-es-nicht']
            kopie.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding='utf-8')
            with self.assertRaises(ValueError) as ctx:
                sa.laden(kopie)
            self.assertIn('selbstabbild_weiter_unbekannt', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
