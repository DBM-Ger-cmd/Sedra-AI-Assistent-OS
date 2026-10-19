"""Auto-Update Teil 2: Prüfung, Rechte-Bestätigung, Sicherung und Rückweg. Ohne Netz: die Quelle ist ein Ordner."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime import update_anwenden as ua


def schreibe(base, dateien):
    for rel, text in dateien.items():
        p = Path(base) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')


def baum(routen=('GET /api/a',), trust='CORE'):
    return {
        'runtime/src/guppi_runtime/kern.py': 'X = 1\n',
        'runtime/config/llama.yaml': 'a: 1\n',
        'runtime/src/guppi_runtime/uix/tools/gw/tool.yaml': f'tool:\n  api: [{", ".join(routen)}]\n  trust: {trust}\n',
    }


class UpdateTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / 'installation'
        self.staging = Path(tmp.name) / 'release'
        schreibe(self.root, baum())
        schreibe(self.root, {'local_config/gateway/eingang/a.md': 'Original', 'workspace/x.txt': 'arbeit', 'runtime_data/db': 'daten'})
        self.staging.mkdir()
        schreibe(self.staging, baum())

    def manifest(self):
        return ua.manifest_erzeugen(self.staging)

    def test_gleicher_stand_hat_nichts_zu_tun(self):
        p = ua.plan(self.staging, self.root, self.manifest())
        self.assertEqual((p['dateien_geaendert'], p['dateien_entfallen'], p['rechte']), ([], [], []))

    def test_veraenderte_datei_wird_abgelehnt(self):
        manifest = self.manifest()
        schreibe(self.staging, {'runtime/src/guppi_runtime/kern.py': 'X = 2\n'})
        with self.assertRaisesRegex(ua.UpdateFehler, 'pruefsumme_falsch'):
            ua.plan(self.staging, self.root, manifest)

    def test_zusaetzliche_datei_ohne_manifest_wird_abgelehnt(self):
        manifest = self.manifest()
        schreibe(self.staging, {'runtime/src/guppi_runtime/neu.py': 'Y = 1\n'})
        with self.assertRaisesRegex(ua.UpdateFehler, 'dateien_passen_nicht'):
            ua.plan(self.staging, self.root, manifest)

    def test_manifest_darf_nur_programmpfade_nennen(self):
        for zeile in ('0' * 64 + '  local_config/gateway/eingang/a.md', '0' * 64 + '  runtime/src/../../x.py', '0' * 64 + '  /etc/passwd'):
            with self.assertRaises(ua.UpdateFehler, msg=zeile):
                ua.manifest_lesen(zeile + '\n')

    def test_rechteaenderung_wird_einzeln_genannt_und_braucht_bestaetigung(self):
        schreibe(self.staging, baum(routen=('GET /api/a', 'POST /api/xyz'), trust='CORE'))
        p = ua.plan(self.staging, self.root, self.manifest())
        self.assertEqual(p['rechte'], ['tool:gw: neue Route POST /api/xyz'])
        with self.assertRaisesRegex(ua.UpdateFehler, 'rechte_nicht_bestaetigt'):
            ua.anwenden(self.staging, self.root, self.manifest(), '', '1.22.0')
        self.assertEqual((self.root / 'runtime/src/guppi_runtime/kern.py').read_text(encoding='utf-8'), 'X = 1\n')

    def test_vertrauensstufe_aenderung_ist_eigene_zeile(self):
        schreibe(self.staging, baum(trust='COMMUNITY'))
        p = ua.plan(self.staging, self.root, self.manifest())
        self.assertIn('tool:gw: Vertrauensstufe CORE → COMMUNITY', p['rechte'])

    def test_uebernahme_mit_bestaetigung_sichert_und_der_rueckweg_stellt_her(self):
        schreibe(self.staging, {'runtime/src/guppi_runtime/kern.py': 'X = 2\n', 'runtime/src/guppi_runtime/neu.py': 'Y = 1\n'})
        manifest = self.manifest()
        ergebnis = ua.anwenden(self.staging, self.root, manifest, '', '1.22.0')
        self.assertEqual(ergebnis['status'], 'uebernommen')
        self.assertEqual((self.root / 'runtime/src/guppi_runtime/kern.py').read_text(encoding='utf-8'), 'X = 2\n')
        self.assertTrue((self.root / 'local_config/update/stand.json').is_file())
        zurueck = ua.zurueck(self.root)
        self.assertEqual(zurueck['status'], 'zurueckgesetzt')
        self.assertEqual((self.root / 'runtime/src/guppi_runtime/kern.py').read_text(encoding='utf-8'), 'X = 1\n')
        self.assertFalse((self.root / 'runtime/src/guppi_runtime/neu.py').exists())

    def test_geschuetzte_ordner_bleiben_unberuehrt(self):
        schreibe(self.staging, {'runtime/src/guppi_runtime/kern.py': 'X = 2\n'})
        ua.anwenden(self.staging, self.root, self.manifest(), '', '1.22.0')
        self.assertEqual((self.root / 'local_config/gateway/eingang/a.md').read_text(encoding='utf-8'), 'Original')
        self.assertEqual((self.root / 'workspace/x.txt').read_text(encoding='utf-8'), 'arbeit')
        self.assertEqual((self.root / 'runtime_data/db').read_text(encoding='utf-8'), 'daten')

    def test_rueckweg_ohne_sicherung_wird_abgelehnt(self):
        with self.assertRaisesRegex(ua.UpdateFehler, 'keine_sicherung'):
            ua.zurueck(self.root)


if __name__ == '__main__':
    unittest.main()
