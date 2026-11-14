"""F3-01 Server-Lese-Routen für Factory Studio: factory_lesen.py (Registry und Evidence Store, nur lesen) und GET /api/uix/factory/*.
Grenzen (F301): keine schreibende Route, keine Datei wird angelegt oder verändert, fehlende Quellen werden ehrlich gemeldet (nichts erfunden)."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from sedra_runtime import factory_lesen
from sedra_runtime.evidence_store import EvidenceStore
from sedra_runtime.factory_registry import FactoryRegistry
from test_harness_bau_2026_11_01 import SitzungsErlaubnisServer as Basis
from test_uix_harness_api import anfrage
from host_isolation import setUpModule, tearDownModule  # noqa: F401


def _stand(ordner):
    """Datenstand aller Dateien; die SQLite-Hilfsdateien des WAL-Modus (-shm, -wal) zählen nicht: sie enthalten keine Daten, und ein schreibgeschütztes
    Öffnen aktualisiert den Index (-shm), damit auch noch nicht eingecheckte Läufe sichtbar sind."""
    return {str(p.relative_to(ordner)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(ordner).rglob('*'))
            if p.is_file() and not p.name.endswith(('-shm', '-wal'))}


def _befuellen(root):
    cfg = Path(root) / 'local_config'
    reg = FactoryRegistry()
    reg.registriere_typ('webshop', 'Webshop', ['katalog'], gate_freigabe=True)
    reg.registriere_typ('3d', '3D Fabrik', ['stl'])
    reg.save(cfg / 'factory_registry.json')
    store = EvidenceStore(cfg / 'evidence' / 'evidence.db')
    for name, ok in (('Lauf A', True), ('Lauf B', False)):
        r = store.record_run_start('webshop', name, 'project')
        store.record_run_end(r.run_id, ok, error=None if ok else 'kaputt', metrics={'dauer': 1})
    store.close() if hasattr(store, 'close') else None


class LesenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_ohne_quellen_ehrliche_antwort_und_keine_datei(self):
        for fn in (factory_lesen.typen, factory_lesen.runs, factory_lesen.benchmarks):
            self.assertEqual(fn(self.root)['quelle'], 'fehlt')
        h = factory_lesen.health(self.root)
        self.assertFalse(h['ok'])
        self.assertFalse(h['registry']['erreichbar'])
        self.assertFalse(h['evidence']['erreichbar'])
        self.assertEqual(_stand(self.root), {}, 'Lesen legt nichts an')

    def test_typen_runs_und_health_mit_daten(self):
        _befuellen(self.root)
        t = factory_lesen.typen(self.root)
        self.assertEqual((t['quelle'], t['anzahl']), ('ok', 2))
        self.assertEqual({x['typ_id']: x['gate_freigabe'] for x in t['typen']}, {'webshop': True, '3d': False})
        r = factory_lesen.runs(self.root)
        self.assertEqual((r['quelle'], r['anzahl']), ('ok', 2))
        self.assertEqual({x['name']: x['erfolg'] for x in r['runs']}, {'Lauf A': True, 'Lauf B': False})
        self.assertEqual([x['fehler'] for x in r['runs'] if x['name'] == 'Lauf B'], ['kaputt'])
        self.assertEqual(factory_lesen.runs(self.root, typ='gibtsnicht')['anzahl'], 0)
        h = factory_lesen.health(self.root)
        self.assertTrue(h['ok'])
        self.assertEqual((h['registry']['typen'], h['evidence']['runs'], h['registry']['gate_freigegeben']), (2, 2, 1))

    def test_gegenprobe_lesen_veraendert_nichts(self):
        _befuellen(self.root)
        vorher = _stand(self.root)
        for fn in (factory_lesen.typen, factory_lesen.runs, factory_lesen.benchmarks, factory_lesen.health):
            fn(self.root)
        self.assertEqual(_stand(self.root), vorher)

    def test_gegenprobe_limit_wird_begrenzt_und_kaputte_werte_fallen_zurueck(self):
        self.assertEqual(factory_lesen._grenze(10_000), factory_lesen.LIMIT_MAX)
        self.assertEqual(factory_lesen._grenze(0), 1)
        self.assertEqual(factory_lesen._grenze('x'), factory_lesen.LIMIT_STANDARD)

    def test_gegenprobe_kaputte_dateien_sind_ein_fehlersatz_kein_absturz(self):
        cfg = self.root / 'local_config'
        (cfg / 'evidence').mkdir(parents=True)
        (cfg / 'factory_registry.json').write_text('{ kaputt', encoding='utf-8')
        (cfg / 'evidence' / 'evidence.db').write_bytes(b'kein sqlite')
        self.assertEqual(factory_lesen.typen(self.root)['quelle'], 'fehler')
        self.assertEqual(factory_lesen.runs(self.root)['quelle'], 'fehler')
        self.assertFalse(factory_lesen.health(self.root)['ok'])

    def test_keine_schreibenden_funktionen_im_modul(self):
        quelle = (Path(factory_lesen.__file__)).read_text(encoding='utf-8')
        for verboten in ('INSERT', 'UPDATE ', 'DELETE', 'DROP', 'CREATE TABLE', 'write_text', 'write_bytes', 'mkdir', '.save('):
            self.assertNotIn(verboten, quelle, verboten)


class ServerRouten(Basis):
    def _projekt(self):
        return Path(self.tmp.name) / 'project'

    def test_hub_liefert_die_daten_der_quellen(self):
        _befuellen(self._projekt())
        self.assertEqual(self.hub.factory_typen()['anzahl'], 2)
        self.assertEqual(self.hub.factory_runs()['anzahl'], 2)
        self.assertTrue(self.hub.factory_health()['ok'])
        self.assertEqual(self.hub.factory_benchmarks()['quelle'], 'ok')

    def test_die_routen_stehen_nur_im_get_zweig_des_servers(self):
        quelle = (Path(factory_lesen.__file__).parent / 'uix_server.py').read_text(encoding='utf-8')
        for pfad in ('health', 'typen', 'runs', 'benchmarks'):
            self.assertEqual(quelle.count(f"'/api/uix/factory/{pfad}'"), 1, pfad)       # genau ein Eintrag (die GET-Tabelle)

    def test_manifeste_nennen_sie_erst_wenn_der_code_sie_aufruft(self):
        # Die Prüfung test_uix_hardening_2026_10_30.RoutenImManifest verlangt api-Liste = aufgerufene Routen: Ansichten und Manifest-Eintrag kommen zusammen.
        yml = (Path(factory_lesen.__file__).parent / 'uix' / 'shells' / 'harness' / 'shell.yaml').read_text(encoding='utf-8')
        js = ''.join(p.read_text(encoding='utf-8') for p in (Path(factory_lesen.__file__).parent / 'uix' / 'shells' / 'harness').glob('factory_studio*.js'))
        self.assertEqual('/api/uix/factory/' in yml, '/api/uix/factory/' in js)

    def test_gegenprobe_nur_get_keine_schreibende_route(self):
        for pfad in ('typen', 'runs', 'health', 'benchmarks'):
            code, _out = anfrage(self.url, 'POST', f'/api/uix/factory/{pfad}', {})
            self.assertIn(code, (403, 404, 405), pfad)


for _name in [n for n in dir(Basis) if n.startswith('test_')]:
    setattr(ServerRouten, _name, None) if not _name.startswith('test_routen') and not _name.startswith('test_gegenprobe_nur') else None


if __name__ == '__main__':
    unittest.main()
