"""Gemeinsamer KV-Pool (`kv_unified`): Manager mit grossem Fenster, Angestellte mit kleinem, ein Server (models/kv_pool.py)."""
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.models import aufteilung, kv_pool
from sedra_runtime.models.llama_server_runtime import build_command
from sedra_runtime.models.role_routing import RoutingConfig
from test_role_routing import recipe, routing_raw

POOL = {'kv_unified': True, 'kv_pool_je_angestellter': 45056, 'slots': 3}
GLEICH = {'slots': 3}


class RechnungTest(unittest.TestCase):
    def test_pool_ist_manager_plus_angestellte(self):
        self.assertEqual(kv_pool.gesamt(POOL, 102400, 3), 102400 + 2 * 45056)
        self.assertEqual(kv_pool.zusatz(POOL, 3), 2 * 45056)
        self.assertEqual(kv_pool.zusatz(POOL, 1), 0, 'ein Slot: kein Zusatz')

    def test_ohne_schalter_bleibt_fenster_mal_slots(self):
        self.assertEqual(kv_pool.gesamt(GLEICH, 61440, 3), 61440 * 3)
        self.assertIsNone(kv_pool.zusatz(GLEICH, 3))
        self.assertEqual(kv_pool.gesamt(None, 8192, 1), 8192)

    def test_gemeldetes_fenster_ist_das_des_managers(self):
        pool = kv_pool.gesamt(POOL, 102400, 3)
        self.assertEqual(kv_pool.fenster_aus_gesamt(POOL, pool, 3), 102400)
        self.assertEqual(kv_pool.fenster_aus_gesamt(GLEICH, 61440 * 3, 3), 61440)

    def test_speicherbedarf_des_pools_ist_kleiner_als_gleiche_slots(self):
        dyn = {"n_cpu_moe": {"min": 24, "max": 40}, "vram_fix_gb": 1.5, "ram_aufschlag_gb": 1.5, "ram_untergrenze_gb": 8,
               "tabelle": {"bei_kontext": 32768, "punkte": [{"lagen": 28, "vram_gb": 10.5, "tokens_s": 45.0}, {"lagen": 40, "vram_gb": 6.1, "tokens_s": 35.5}]}}
        gleich = aufteilung.bedarf(dyn, 28, 102400, 0.0144, 17.73, 3)['vram_gb']
        pool = aufteilung.bedarf(dyn, 28, 102400, 0.0144, 17.73, 3, kv_pool.zusatz(POOL, 3))['vram_gb']
        self.assertLess(pool, gleich)
        self.assertAlmostEqual(gleich - pool, 0.0144 * (3 * 102400 - 102400 - 2 * 45056) / 1000, places=2)


class StartbefehlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.gguf = Path(self.tmp.name) / 'm.gguf'; self.gguf.write_bytes(b'x')

    def test_schalter_steht_nur_bei_kv_unified_im_befehl(self):
        kw = dict(gguf=self.gguf, context=192512, host='127.0.0.1', port=8089, alias='m', parallel=3)
        self.assertIn('--kv-unified', build_command('llama-server.exe', kv_unified=True, **kw))
        self.assertNotIn('--kv-unified', build_command('llama-server.exe', **kw))
        argv = build_command('llama-server.exe', kv_unified=True, **kw)
        self.assertEqual(argv[argv.index('-c') + 1], '192512')
        self.assertEqual(argv[argv.index('-np') + 1], '3')


class RezeptPruefungTest(unittest.TestCase):
    def rezept(self, server):
        profile = {'context': {'recommended': 61440, 'maximum': 102400, 'measured_maximum': 102400, 'tiers': [61440, 102400], 'per_slots': {3: 102400}},
                   'gpu_layers': 99, 'server': dict({'gguf': 'x.gguf'}, **server)}
        return recipe('coder.pool', ['coder'], 'llama-cpp-server', 'fam', profile=profile)

    def test_pool_rezept_wird_angenommen(self):
        RoutingConfig(routing_raw([self.rezept(POOL)]))

    def test_pool_mit_mehreren_slots_verlangt_den_anteil_der_angestellten(self):
        with self.assertRaises(ValueError):
            RoutingConfig(routing_raw([self.rezept({'kv_unified': True, 'slots': 3})]))

    def test_ungueltige_werte_werden_abgelehnt(self):
        for bad in ({'kv_unified': 'ja', 'slots': 1}, {'kv_unified': True, 'slots': 3, 'kv_pool_je_angestellter': 10}):
            with self.assertRaises(ValueError, msg=str(bad)):
                RoutingConfig(routing_raw([self.rezept(bad)]))


if __name__ == '__main__':
    unittest.main()
