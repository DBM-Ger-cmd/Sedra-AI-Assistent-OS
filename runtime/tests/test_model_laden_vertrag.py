"""Vertrag des Modell-Ladens (Captain 05.11.2026: „ich möchte nicht, dass nach jedem Update das Laden der Modelle nicht mehr funktioniert“).

Gilt für die Rezepte dieser Maschine: die ausgelieferte `config/role_routing.yaml` mit der Datei des Captains darüber (`workspace/SEDRA_OS/local_config/role_routing.yaml`, nicht im Git).
Ohne diese Datei (andere Maschine, CI) wird übersprungen; die allgemeine Regel prüfen `AutoWindowMemoryTests` in test_role_routing.py mit eigenen Rezepten. Jedes aktive Rezept des
llama-server muss sich mit „Auto“ und mit jeder seiner Stufen auflösen lassen, solange die kleinste Stufe in den Speicher passt – und nie ein Fenster wählen, dessen Bedarf das Budget übersteigt. Ein Update, das das bricht (neues Rezept
ohne Stufen, Messung ohne Fenster, Prüfung, die zu streng wird), macht diesen Test rot, bevor der Captain es merkt."""
import unittest
from pathlib import Path
from types import SimpleNamespace

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.models.role_routing import ResolutionError, RoleRouter, RoutingConfig

RUNTIME = Path(__file__).resolve().parents[1]
ROUTING = RUNTIME / 'config' / 'role_routing.yaml'
LOKAL = RUNTIME.parent / 'workspace' / 'SEDRA_OS' / 'local_config' / 'role_routing.yaml'
GPU = SimpleNamespace(hardware_class='nvidia_10_12', cpu_threads=16, gpu_vendor='NVIDIA', ram_gb=32, vram_gb=12)


def router_mit(budget, gesehen=None):
    def pruefung(recipe, estimated, req):
        bedarf = round((estimated.get('vram_gb') or 0) + (estimated.get('kv_cache_gb') or 0), 3)
        if gesehen is not None:
            gesehen.append((recipe['id'], bedarf))
        return None if bedarf <= budget else 'vram_insufficient'
    return RoleRouter(RoutingConfig.load(ROUTING, LOKAL), snapshot=GPU, load_check=pruefung)


def llama_rezepte():
    cfg = RoutingConfig.load(ROUTING, LOKAL)
    return [r for r in cfg.recipes if r.get('provider') == 'llama-cpp-server' and r.get('enabled') and not (r['profile'].get('dynamisch')) and (r['profile'].get('context') or {}).get('tiers')]


@unittest.skipUnless(LOKAL.exists(), 'keine Rezepte des Captains auf dieser Maschine')
class LadeVertrag(unittest.TestCase):
    def test_es_gibt_rezepte_zu_pruefen(self):
        self.assertTrue(llama_rezepte(), 'die ausgelieferte Konfiguration hat kein aktives llama-server-Rezept mit Stufen – dieser Vertrag prüfte sonst nichts')

    def test_jedes_rezept_loest_sich_mit_viel_speicher_in_auto_und_jeder_stufe_auf(self):
        router = router_mit(1000.0)
        for r in llama_rezepte():
            auto = router.resolve_recipe(r['id'], kontext='auto')
            self.assertIn(auto['context_window'], r['profile']['context']['tiers'], r['id'])
            for stufe in r['profile']['context']['tiers']:
                try:
                    wahl = router.resolve_recipe(r['id'], kontext=stufe)
                except ResolutionError as exc:
                    # eine Stufe jenseits der Hardwareklasse darf abgelehnt werden, aber mit dem Grund „Fenster nicht verfügbar“, nie mit Speicher
                    self.assertIn('context_not_available', str(exc.detail), f'{r["id"]} {stufe}')
                    continue
                self.assertLessEqual(wahl['context_window'], stufe, r['id'])

    def test_bei_knappem_speicher_wird_das_fenster_kleiner_statt_abgelehnt_und_das_budget_gilt(self):
        for r in llama_rezepte():
            frei = router_mit(1000.0)
            gesehen = []
            router_mit(1000.0, gesehen).resolve_recipe(r['id'], kontext='auto')
            klein = min(t for t in r['profile']['context']['tiers'])
            gesehen = []
            try:
                router_mit(0.0, gesehen).resolve_recipe(r['id'], kontext='auto')
            except ResolutionError:
                pass
            bedarf_klein = min(b for i, b in gesehen if i == r['id']) if gesehen else None
            if bedarf_klein is None:
                continue                                                                 # die Hardwareklasse lässt nur ein Fenster zu: es gibt nichts zu verkleinern
            budget = bedarf_klein + 0.01
            wahl = router_mit(budget).resolve_recipe(r['id'], kontext='auto')
            self.assertLessEqual(wahl['context_window'], max(r['profile']['context']['tiers']), r['id'])
            est = wahl['estimated_resources']
            self.assertLessEqual(round((est['vram_gb'] or 0) + (est['kv_cache_gb'] or 0), 3), budget, f'{r["id"]}: das gewählte Fenster überschreitet das Budget')
            del frei, klein

    def test_ein_budget_unter_dem_kleinsten_fenster_ist_eine_ablehnung_mit_speichergrund(self):
        for r in llama_rezepte():
            with self.assertRaises(ResolutionError) as ctx:
                router_mit(0.5).resolve_recipe(r['id'], kontext='auto')
            self.assertEqual(ctx.exception.code, 'hardware_pressure', r['id'])


if __name__ == '__main__':
    unittest.main()
