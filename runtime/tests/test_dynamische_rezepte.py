"""Dynamische Rezepte R3 bis R5 (ohne Modell, ohne Hardware): Rezeptblock im Routing, Auswahl beim Auflösen, Lader mit frischen Zahlen, Messspeicher,
Antwort und Ablehnung mit Zahlen. Die Rechenmodule selbst prüft test_models_aufteilung."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from guppi_runtime.core.audit import AuditLog
from guppi_runtime.models.messwerte import Messwerte
from guppi_runtime.models.model_loader import LoadError, LoaderConfig, ModelLoader
from guppi_runtime.models.role_routing import ProviderHealth, ResolutionError, RoleRouter, RoutingConfig
from host_isolation import setUpModule, tearDownModule  # noqa: F401
from test_model_loader import FakeController
from test_role_routing import Clock, recipe, routing_raw

DYN = {"n_cpu_moe": {"min": 24, "max": 40}, "vram_fix_gb": 1.5, "ram_aufschlag_gb": 1.5, "ram_untergrenze_gb": 8,
       "tabelle": {"bei_kontext": 32768, "punkte": [{"lagen": 28, "vram_gb": 10.5, "tokens_s": 45.0}, {"lagen": 32, "vram_gb": 9.1, "tokens_s": 41.7},
                                                    {"lagen": 36, "vram_gb": 7.6, "tokens_s": 38.5}, {"lagen": 40, "vram_gb": 6.1, "tokens_s": 35.5}]}}
HOST = SimpleNamespace(hardware_class='cpu_32plus', cpu_threads=16, gpu_vendor='nvidia', ram_gb=32, vram_gb=12)
STAND = {"frei_vram_gb": 10.65, "frei_ram_gb": 14.3, "reserve_vram_gb": 0.7, "reserve_ram_gb": 1.5}


def moe_rezept(**kw):
    profile = {'context': {'recommended': 32768, 'maximum': 65536, 'measured_maximum': 65536, 'tiers': [8192, 16384, 32768, 65536]}, 'gpu_layers': 99,
               'server': {'gguf': 'x.gguf', 'n_cpu_moe': 28, 'kv_cache_type': 'q8_0'}, 'dynamisch': copy.deepcopy(DYN)}
    return recipe('coder.moe', ['coder'], 'llama-cpp-server', 'qwen', 'w1', model='qwen-moe', model_size_gb=17.73, kv_cache_gb_per_1k_tokens=0.04,
                  requirements={'min_ram_gb': 12, 'min_vram_gb': 0}, profile=profile, **kw)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root, self.clock = Path(self.tmp.name), Clock()
        self.audit = AuditLog(self.root / 'audit.jsonl')

    def router(self, rezept=None, stand=STAND, gemessen=None, **kw):
        config = RoutingConfig(routing_raw([rezept or moe_rezept()]))
        health = ProviderHealth(config, self.root / 'health.json', audit=self.audit, clock=self.clock.now)
        r = RoleRouter(config, snapshot=HOST, health=health, audit=self.audit, clock=self.clock.now, **kw)
        r.speicher_stand = (lambda: dict(stand)) if stand is not None else None
        r.messwerte = (lambda rid: gemessen) if gemessen is not None else None
        return r

    def test_rezeptblock_wird_geprueft(self):
        kaputt = moe_rezept()
        kaputt['profile']['dynamisch']['tabelle']['punkte'] = kaputt['profile']['dynamisch']['tabelle']['punkte'][:1]
        with self.assertRaises(Exception) as ctx:
            RoutingConfig(routing_raw([kaputt]))
        self.assertIn('profile.dynamisch', str(ctx.exception))
        RoutingConfig(routing_raw([moe_rezept()]))                   # der gültige Block lädt

    def test_auswahl_beim_aufloesen_30_lagen_bei_dem_befund_vom_29_10(self):
        res = self.router().resolve_recipe('coder.moe')
        a = res['estimated_resources']['auswahl']
        self.assertEqual((a['lagen'], a['kontext']), (30, 32768))
        self.assertAlmostEqual(res['estimated_resources']['vram_gb'], 9.8, places=2)
        self.assertEqual(res['context_window'], 32768)
        self.assertEqual(res['dynamisch_plan']['kontexte'], [32768, 16384, 8192])         # nie größer als gewünscht, nie unter dem Mindestkontext (hier die kleinste Stufe)

    def test_zu_wenig_ram_nimmt_zuerst_mehr_lagen_dann_kleineren_kontext(self):
        res = self.router(stand=dict(STAND, frei_vram_gb=8.3, frei_ram_gb=16.0)).resolve_recipe('coder.moe')      # budget 7,6: 36 Lagen passen bei 32 768
        self.assertEqual((res['estimated_resources']['auswahl']['lagen'], res['context_window']), (36, 32768))
        res = self.router(stand=dict(STAND, frei_vram_gb=7.0, frei_ram_gb=19.0)).resolve_recipe('coder.moe')   # budget 6,3: 40 Lagen bei 32 768 brauchen 6,1, 39 schon 6,5
        self.assertEqual(res['estimated_resources']['auswahl']['lagen'], 40)

    def test_ram_zu_knapp_fuer_die_vielen_lagen_dann_kleinerer_kontext(self):
        res = self.router(stand=dict(STAND, frei_vram_gb=8.3)).resolve_recipe('coder.moe')      # 36 Lagen bräuchten 13,1 GB RAM, frei sind 12,8: erst bei 16 384 reicht es
        self.assertEqual((res['estimated_resources']['auswahl']['lagen'], res['context_window']), (35, 16384))

    def test_ablehnung_mit_zahlen_statt_nur_hardware_pressure(self):
        with self.assertRaises(ResolutionError) as ctx:
            self.router(stand=dict(STAND, frei_vram_gb=3.0, frei_ram_gb=6.0)).resolve_recipe('coder.moe')
        self.assertEqual(ctx.exception.code, 'hardware_pressure')
        grund = ctx.exception.detail['considered'][0]['reason']
        self.assertIn('GB VRAM', grund)
        self.assertIn('Lagen im RAM', grund)

    def test_gemessene_werte_werden_bevorzugt(self):
        res = self.router(gemessen={(24, 32768): {'vram_gb': 9.0, 'ram_gb': 9.0}}).resolve_recipe('coder.moe')
        a = res['estimated_resources']['auswahl']
        self.assertEqual((a['lagen'], a['quelle']), (24, 'gemessen'))

    def test_ohne_speicherstand_oder_ohne_block_bleibt_alles_wie_vorher(self):
        res = self.router(stand=None).resolve_recipe('coder.moe')
        self.assertNotIn('auswahl', res['estimated_resources'])
        self.assertIsNone(res['dynamisch_plan'])
        ohne = moe_rezept()
        del ohne['profile']['dynamisch']
        res = self.router(ohne).resolve_recipe('coder.moe')
        self.assertNotIn('auswahl', res['estimated_resources'])


class LoaderTests(unittest.TestCase):
    def aufloesung(self, **plan_kw):
        plan = {'dyn': copy.deepcopy(DYN), 'kontexte': [32768, 16384], 'kv_rate': 0.04, 'groesse_gb': 17.73, 'slots': 1}
        plan.update(plan_kw)
        return {'model': 'org/m', 'capability_id': 'coder.moe', 'context_window': 32768, 'estimated_resources': {'vram_gb': 9.8, 'auswahl': {'lagen': 28, 'kontext': 32768, 'vram_gb': 10.5, 'ram_gb': 10.2}},
                'load_profile': {'gpu_layers': 99, 'server': {'gguf': 'x.gguf', 'n_cpu_moe': 28}}, 'dynamisch_plan': plan}

    def lader(self, stand, ctl=None, gemessen=None):
        ctl = ctl or FakeController()
        l = ModelLoader(LoaderConfig({'enabled': True, 'check_estimate': False}), ctl)
        l.speicher_stand = (lambda **_: dict(stand)) if stand is not None else None
        l.messwerte = (lambda rid: gemessen) if gemessen is not None else None
        return l, ctl

    def test_lader_waehlt_vor_dem_start_neu_und_startet_mit_den_lagen(self):
        gesehen = {}
        class Ctl(FakeController):
            def load_model(self, key, **kw):
                gesehen.update(kw); return super().load_model(key, **kw)
        l, ctl = self.lader(STAND, Ctl())
        out = l.ensure(self.aufloesung())
        self.assertEqual((out['auswahl']['lagen'], out['auswahl']['kontext']), (30, 32768), 'frischer Stand schlägt die Wahl des Routings (28)')
        self.assertEqual(gesehen['server']['n_cpu_moe'], 30)
        self.assertEqual(gesehen['context_length'], 32768)

    def test_lader_rechnet_die_eigene_reservierung_des_starts_nicht_ab(self):
        """Live-Fund 30.10.: der Modell-Scheduler reserviert vor dem Start; der Lader darf sich diese Reservierung nicht selbst abziehen."""
        gefragt = []
        l, ctl = self.lader(STAND)
        l.speicher_stand = lambda **kw: gefragt.append(kw) or dict(STAND)
        l.ensure(self.aufloesung())
        self.assertEqual(gefragt, [{'ignore': ('server:coder.moe',)}])

    def test_lader_verkleinert_den_kontext_wenn_der_speicher_nur_dafuer_reicht(self):
        l, ctl = self.lader(dict(STAND, frei_vram_gb=6.0, frei_ram_gb=19.0))        # budget 5,3: 40 Lagen bei 32 768 (6,1) zu viel, bei 16 384 gutgeschrieben 5,4? → noch zu viel
        with self.assertRaises(LoadError) as ctx:
            l.ensure(self.aufloesung())
        self.assertIn('GB VRAM', str(ctx.exception))
        self.assertEqual([c[0] for c in ctl.calls], [], 'nichts wurde gestartet')

    def test_ohne_messung_gilt_die_wahl_des_routings(self):
        l, ctl = self.lader(None)
        out = l.ensure(self.aufloesung())
        self.assertEqual(out['auswahl']['lagen'], 28)

    def test_kein_dynamisches_rezept_gleiche_antwort_wie_vorher(self):
        l, ctl = self.lader(STAND)
        res = self.aufloesung()
        res.pop('dynamisch_plan')
        out = l.ensure(res)
        self.assertNotIn('auswahl', out)


class MesswerteTests(unittest.TestCase):
    def test_merken_lesen_und_grenzen(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = Messwerte(Path(tmp) / 'sub' / 'messwerte.json')
            self.assertEqual(m.fuer('a'), {})
            self.assertTrue(m.merken('a', 30, 32768, 9.8, 10.9))
            self.assertTrue(m.merken('a', 30, 32768, 9.9, 11.0))                      # derselbe Schlüssel: der jüngste gilt
            self.assertEqual(m.fuer('a'), {(30, 32768): {'vram_gb': 9.9, 'ram_gb': 11.0}})
            self.assertEqual(m.fuer('b'), {})
            for kaputt in ((30, 32768, 0, 5), (30, 32768, -1, 5), (30, 32768, 'x', 5), (30.5, 32768, 5, 5), (30, True, 5, 5)):
                self.assertFalse(m.merken('a', *kaputt), kaputt)
            for i in range(250):
                m.merken('z', 24 + i % 17, 1000 + i, 5.0, 5.0)
            doc = json.loads((Path(tmp) / 'sub' / 'messwerte.json').read_text(encoding='utf-8'))
            self.assertLessEqual(len(doc['eintraege']), 200)
            (Path(tmp) / 'sub' / 'messwerte.json').write_text('kaputt', encoding='utf-8')
            self.assertEqual(m.fuer('a'), {}, 'eine kaputte Datei zählt als leer')


class ServerHilfenTests(unittest.TestCase):
    def test_ablehnung_haengt_den_grund_mit_den_zahlen_an(self):
        from guppi_runtime.uix_server import UIXHub
        exc = ResolutionError('hardware_pressure', {'considered': [{'reason': 'Es fehlen 0.60 GB VRAM und 0.00 GB RAM bei 40 Lagen im RAM und 8192 Kontext.'}]})
        self.assertEqual(UIXHub._ablehnung(exc), ':Es fehlen 0.60 GB VRAM und 0.00 GB RAM bei 40 Lagen im RAM und 8192 Kontext.')
        self.assertEqual(UIXHub._ablehnung(ResolutionError('no_capability', None)), '')
        self.assertEqual(UIXHub._ablehnung(ValueError('x')), '')

    def test_messwert_wird_nach_dem_laden_gemerkt_nur_bei_dynamischer_wahl_und_echtem_laden(self):
        from guppi_runtime.uix_server import UIXHub
        with tempfile.TemporaryDirectory() as tmp:
            audit = []
            hub = SimpleNamespace(runtime=SimpleNamespace(messwerte=Messwerte(Path(tmp) / 'm.json'), audit=SimpleNamespace(append=lambda *a, **k: audit.append((a, k)))))
            vor, nach = {'frei_vram_gb': 10.6, 'frei_ram_gb': 14.0}, {'frei_vram_gb': 0.9, 'frei_ram_gb': 4.0}
            wahl = {'lagen': 30, 'kontext': 32768}
            UIXHub._messwert_merken(hub, 'coder.moe', {'action': 'loaded', 'auswahl': wahl}, vor, nach)
            self.assertEqual(hub.runtime.messwerte.fuer('coder.moe'), {(30, 32768): {'vram_gb': 9.7, 'ram_gb': 10.0}})
            self.assertEqual(audit[0][0][0], 'MODEL_LOAD_MEASURED')
            UIXHub._messwert_merken(hub, 'coder.moe', {'action': 'reused', 'auswahl': wahl}, vor, nach)          # nichts geladen: nichts gemessen
            UIXHub._messwert_merken(hub, 'coder.moe', {'action': 'loaded'}, vor, nach)                              # kein dynamisches Rezept
            UIXHub._messwert_merken(hub, 'coder.moe', {'action': 'loaded', 'auswahl': wahl}, None, nach)           # keine Messung
            UIXHub._messwert_merken(hub, 'coder.moe', {'action': 'loaded', 'auswahl': dict(wahl, lagen=31)}, nach, vor)   # Unterschied negativ: nicht gemerkt
            self.assertEqual(list(hub.runtime.messwerte.fuer('coder.moe')), [(30, 32768)])
            self.assertEqual(len(audit), 1)


if __name__ == '__main__':
    unittest.main()
