"""Phase 5: role -> capability -> provider routing, provider health, fallback, verifier independence. No model, no hardware."""
import json
import re
import tempfile
import threading
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import env_skip

import yaml

from guppi_runtime.audit import AuditLog
from guppi_runtime.context_budget import ContextBudgetManager
from guppi_runtime.development_contracts import development_contract
from guppi_runtime.job_supervisor import JobError, JobSupervisor, SupervisorConfig, SupervisorJobStore
from guppi_runtime.models.base import ModelAdapterError
from guppi_runtime.models.router import ModelRouter
from guppi_runtime.role_routing import (PROVIDER_FAULTS, ProviderHealth, ResolutionError, RoleRouter, RoutingConfig, check_independence,
                                        independence_key)
from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]
ROUTING = RUNTIME / 'config' / 'role_routing.yaml'
SUPERVISOR = RUNTIME / 'config' / 'job_supervisor.yaml'
ARCH = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'


class Clock:
    def __init__(self): self.wall = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc); self.mono = 1000.0
    def now(self): return self.wall
    def monotonic(self): return self.mono
    def advance(self, s): self.wall += timedelta(seconds=s); self.mono += s


def recipe(cid, roles, provider, family, weights='w1', **kw):
    base = {'id': cid, 'version': 1, 'roles': roles, 'provider': provider, 'model': None, 'model_family': family, 'weights_id': weights,
            'location': 'local', 'requirements': {'min_ram_gb': 8, 'min_vram_gb': 0}, 'model_size_gb': None,
            'profile': {'context': {'recommended': 8192, 'maximum': 32768}, 'gpu_layers': 0}, 'permissions': {'max_level': 2},
            'network': {'allowed': False}, 'tests': ['capability_smoke_test'], 'rollback': {'supported': True},
            'metadata': {'source': 'builtin', 'trust_level': 'BUILT_IN'}}
    base.update(kw)
    return base


def routing_raw(capabilities=None, enabled=True, **policy):
    raw = {'enabled': enabled, 'policy': {'allowed_trust_levels': ['BUILT_IN', 'KNOWN_GOOD', 'CAPTAIN_CUSTOM'], 'cloud_allowed': False},
           'provider_health': {'degraded_after': 2, 'cooldown_after': 3, 'base_cooldown_s': 30, 'max_cooldown_s': 600},
           'capabilities': capabilities if capabilities is not None else [recipe('coder.a', ['coder'], 'prov-a', 'fam-a', 'wa'),
                                                                          recipe('verifier.b', ['verifier'], 'prov-b', 'fam-b', 'wb')]}
    raw['policy'].update(policy)
    return raw


HOST = SimpleNamespace(hardware_class='cpu_32plus', cpu_threads=16, gpu_vendor=None, ram_gb=64, vram_gb=0)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.clock = Clock()
        self.audit = AuditLog(self.root / 'audit.jsonl')

    def router(self, raw=None, snapshot=HOST, **kw):
        config = RoutingConfig(raw or routing_raw())
        self.health = ProviderHealth(config, self.root / 'health.json', audit=self.audit, clock=self.clock.now)
        return RoleRouter(config, snapshot=snapshot, health=self.health, audit=self.audit, clock=self.clock.now, **kw)

    def types(self):
        path = self.root / 'audit.jsonl'
        return [json.loads(x)['event_type'] for x in path.read_text(encoding='utf-8').splitlines() if x.strip()] if path.exists() else []

    def codes(self, router, role, requirements=None, **kw):
        with self.assertRaises(ResolutionError) as ctx: router.resolve_role(role, requirements, **kw)
        return ctx.exception.code, ctx.exception.detail


class ConfigTests(unittest.TestCase):
    def test_shipped_config_is_valid_off_and_conservative(self):
        config = RoutingConfig.load(ROUTING)
        self.assertFalse(config.enabled)
        self.assertEqual(config.allowed_trust, {'BUILT_IN', 'KNOWN_GOOD', 'CAPTAIN_CUSTOM'})
        self.assertFalse(config.cloud_allowed)
        by_id = {r['id']: r for r in config.recipes}
        self.assertFalse(by_id['verifier.local_kev']['enabled'])          # nothing may claim to verify with a layer that does not exist yet
        self.assertIsNone(independence_key(by_id['coder.local_primary']))   # no weights id chosen: independence cannot be proven yet

    def test_untrusted_levels_can_never_be_allowed(self):
        for level in ('GUPPI_GENERATED', 'EXTERNAL_UNVERIFIED'):
            with self.assertRaises(ValueError, msg=level): RoutingConfig(routing_raw(allowed_trust_levels=['BUILT_IN', level]))

    def test_invalid_values_refuse_start(self):
        good = recipe('x.y', ['coder'], 'p', 'f')
        mutations = [lambda r: r.pop('roles'), lambda r: r.update(roles=[]), lambda r: r.update(provider=''), lambda r: r.update(location='moon'),
                     lambda r: r.update(permissions={'max_level': 9}), lambda r: r.update(metadata={'trust_level': 'WISHFUL'}),
                     lambda r: r.update(id='Bad Id'), lambda r: r.update(enabled='yes'), lambda r: r.update(requirements={'min_ram_gb': -1}),
                     lambda r: r.update(model_size_gb=0), lambda r: r.update(network={'allowed': 'no'})]
        for mutate in mutations:
            bad = deepcopy(good); mutate(bad)
            with self.assertRaises(ValueError): RoutingConfig(routing_raw([bad]))
        with self.assertRaises(ValueError): RoutingConfig(routing_raw([good, good]))                       # duplicate id
        for health in ({'degraded_after': 5, 'cooldown_after': 2}, {'base_cooldown_s': 900, 'max_cooldown_s': 60}):
            raw = routing_raw(); raw['provider_health'] = health
            with self.assertRaises(ValueError): RoutingConfig(raw)
        with self.assertRaises(ValueError): RoutingConfig(routing_raw(enabled='yes'))
        with self.assertRaises(ValueError): RoutingConfig.load(Path(tempfile.gettempdir()) / 'nope_routing.yaml')

    def overlay(self, tmp, body):
        path = Path(tmp) / 'role_routing.local.yaml'
        path.write_text(yaml.safe_dump({'role_routing': body}), encoding='utf-8')
        return path

    def test_a_machine_specific_overlay_adds_and_replaces_capabilities_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            mine = recipe('coder.local_primary', ['coder'], 'lm-studio', 'fam-x', 'wx')
            extra = recipe('verifier.local_gemma', ['verifier'], 'lm-studio', 'fam-y', 'wy')
            config = RoutingConfig.load(ROUTING, self.overlay(tmp, {'enabled': True, 'capabilities': [mine, extra], 'provider_health': {'base_cooldown_s': 45}}))
            by_id = {r['id']: r for r in config.recipes}
            self.assertEqual(list(by_id), ['coder.local_primary', 'verifier.local_kev', 'verifier.local_gemma'])      # replaced in place, new one appended
            self.assertEqual((by_id['coder.local_primary']['provider'], by_id['coder.local_primary']['weights_id']), ('lm-studio', 'wx'))
            self.assertFalse(by_id['verifier.local_kev']['enabled'])                                                  # untouched
            self.assertEqual((config.enabled, config.base_cooldown_s, config.max_cooldown_s), (True, 45, 600))
            shipped = RoutingConfig.load(ROUTING)
            self.assertEqual((shipped.enabled, len(shipped.recipes)), (False, 2))                                      # the shipped file is unchanged

    def test_a_missing_overlay_changes_nothing(self):
        self.assertEqual(len(RoutingConfig.load(ROUTING, Path(tempfile.gettempdir()) / 'no_such_overlay.yaml').recipes), 2)

    def test_the_overlay_is_validated_like_the_shipped_file(self):
        bad_bodies = [{'policy': {'allowed_trust_levels': ['BUILT_IN', 'GUPPI_GENERATED']}}, {'telepathy': True}, {'capabilities': [{'no_id': 1}]},
                      {'capabilities': 'x'}, {'capabilities': [dict(recipe('x.y', ['coder'], 'p', 'f'), location='moon')]}, {'policy': 'x'}, {'enabled': 'yes'},
                      {'capabilities': [dict(recipe('coder.local_primary', ['coder'], 'p', 'f'), metadata={'trust_level': 'GUPPI_GENERATED'})]}]
        for body in bad_bodies[:7]:
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError, msg=str(body)[:60]): RoutingConfig.load(ROUTING, self.overlay(tmp, body))
        with tempfile.TemporaryDirectory() as tmp:                       # an untrusted recipe loads, but the default policy still refuses to use it
            config = RoutingConfig.load(ROUTING, self.overlay(tmp, bad_bodies[7]))
            self.assertNotIn('GUPPI_GENERATED', config.allowed_trust)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'broken.yaml'; path.write_text('role_routing: [unclosed', encoding='utf-8')
            with self.assertRaises(ValueError) as ctx: RoutingConfig.load(ROUTING, path)
            self.assertEqual(str(ctx.exception), 'role_routing_local_config_unreadable')

    def test_runtime_reads_the_overlay_from_the_project_not_from_the_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'project'
            (project / 'local_config').mkdir(parents=True)
            (project / 'local_config' / 'role_routing.yaml').write_text(yaml.safe_dump({'role_routing': {'capabilities': [recipe('verifier.local_gemma', ['verifier'], 'lm-studio', 'g', 'w')]}}), encoding='utf-8')
            rt = GuppiRuntime(project, ARCH)
            self.assertIn('verifier.local_gemma', [c['id'] for c in rt.routing_status()['capabilities']])
            self.assertFalse(rt.role_router.enabled)                       # the overlay did not switch routing on
        with tempfile.TemporaryDirectory() as tmp:
            self.assertNotIn('verifier.local_gemma', [c['id'] for c in GuppiRuntime(Path(tmp) / 'p2', ARCH).routing_status()['capabilities']])

    def test_independence_key_and_check(self):
        self.assertEqual(independence_key(recipe('a.b', ['coder'], 'p', 'fam', 'w9')), 'fam:w9')
        self.assertIsNone(independence_key(recipe('a.b', ['coder'], 'p', 'fam', None)))
        self.assertEqual(check_independence('a', 'b'), 'INDEPENDENT')
        self.assertEqual(check_independence('a', 'a'), 'SAME')
        for pair in ((None, 'b'), ('a', None), (None, None), ('', 'b')):
            self.assertEqual(check_independence(*pair), 'UNVERIFIABLE')


class ResolveTests(Base):
    def test_role_resolves_to_a_recipe_and_reports_why(self):
        res = self.router().resolve_role('coder')
        self.assertEqual((res['provider_ref'], res['capability_id'], res['independence_key'], res['health_state']), ('prov-a', 'coder.a', 'fam-a:wa', 'HEALTHY'))
        self.assertEqual(res['requirements']['network'], 'denied')
        self.assertEqual(res['role'], 'coder')
        self.assertIn('ROLE_RESOLVED', self.types())

    def test_disabled_routing_resolves_nothing(self):
        self.assertEqual(self.codes(self.router(routing_raw(enabled=False)), 'coder')[0], 'no_capability')

    def test_unknown_role_is_no_capability(self):
        self.assertEqual(self.codes(self.router(), 'astronaut')[0], 'no_capability')

    def test_healthy_beats_degraded_then_declared_order_decides(self):
        raw = routing_raw([recipe('c.one', ['coder'], 'p1', 'f1', 'w1'), recipe('c.two', ['coder'], 'p2', 'f2', 'w2')])
        router = self.router(raw)
        self.assertEqual(router.resolve_role('coder')['capability_id'], 'c.one')
        self.health.report_failure('p1', 'timeout'); self.health.report_failure('p1', 'timeout')       # DEGRADED
        self.assertEqual(self.health.state('p1'), 'DEGRADED')
        self.assertEqual(router.resolve_role('coder')['capability_id'], 'c.two')

    def test_offline_preference_puts_local_first(self):
        raw = routing_raw([recipe('c.cloud', ['coder'], 'pc', 'fc', 'wc', location='cloud', network={'allowed': True}),
                           recipe('c.local', ['coder'], 'pl', 'fl', 'wl')], cloud_allowed=True)
        router = self.router(raw)
        res = router.resolve_role('coder', {'network': 'allowed', 'offline_preferred': True}, captain_cloud_approved=True)
        self.assertEqual(res['capability_id'], 'c.local')
        res = router.resolve_role('coder', {'network': 'allowed', 'offline_preferred': False}, captain_cloud_approved=True)
        self.assertEqual(res['capability_id'], 'c.cloud')                                                 # declared order when locality does not matter

    def test_unsupported_or_malformed_requirements_are_never_ignored(self):
        router = self.router()
        for requirements in ({'telepathy': True}, {'network': 'wifi'}, {'data_class': 'secret'}, {'permission_level': 9}, {'context_min_tokens': -1},
                             {'max_vram_gb': 'lots'}, {'exclusive': 'yes'}):
            self.assertEqual(self.codes(router, 'coder', requirements)[0], 'requirements_unmet', str(requirements))

    def test_static_requirements(self):
        router = self.router()
        self.assertEqual(self.codes(router, 'coder', {'max_ram_gb': 4})[1]['considered'][0]['reason'], 'ram_requirement_exceeds_limit')
        self.assertEqual(self.codes(router, 'coder', {'context_min_tokens': 10 ** 7})[1]['considered'][0]['reason'], 'context_capacity')
        poor = self.router(snapshot=SimpleNamespace(hardware_class='cpu_small', cpu_threads=2, gpu_vendor=None, ram_gb=4, vram_gb=0))
        self.assertEqual(self.codes(poor, 'coder')[1]['considered'][0]['reason'], 'host_ram_below_minimum')
        gpu_recipe = recipe('c.gpu', ['coder'], 'pg', 'fg', 'wg', requirements={'min_ram_gb': 8, 'min_vram_gb': 24})
        self.assertEqual(self.codes(self.router(routing_raw([gpu_recipe])), 'coder')[1]['considered'][0]['reason'], 'host_vram_below_minimum')

    def test_context_window_follows_the_hardware_pass_cap(self):
        small = self.router(snapshot=SimpleNamespace(hardware_class='cpu_small', cpu_threads=4, gpu_vendor=None, ram_gb=16, vram_gb=0))
        self.assertEqual(small.resolve_role('coder')['context_window'], 4096)           # recipe says 32768, this host class is capped
        self.assertEqual(self.router().resolve_role('coder')['context_window'], 16384)  # cpu_32plus
        self.assertEqual(self.codes(small, 'coder', {'context_min_tokens': 8000})[1]['considered'][0]['reason'], 'context_capacity')

    def test_hardware_pass_can_reject_a_model_that_does_not_fit(self):
        huge = recipe('c.huge', ['coder'], 'ph', 'fh', 'wh', model_size_gb=200.0)
        self.assertEqual(self.codes(self.router(routing_raw([huge])), 'coder')[1]['considered'][0]['reason'], 'hardware_incompatible')

    def test_load_check_reports_pressure(self):
        router = self.router(load_check=lambda recipe, estimated, req: 'vram_in_use_by_active_job')
        code, detail = self.codes(router, 'coder')
        self.assertEqual(code, 'hardware_pressure')
        seen = []
        router = self.router(load_check=lambda recipe, estimated, req: seen.append(estimated) or None)
        router.resolve_role('coder')
        self.assertEqual(seen[0]['ram_gb'], 8)

    def test_disabled_recipe_is_skipped(self):
        raw = routing_raw([recipe('c.off', ['coder'], 'p', 'f', enabled=False)])
        self.assertEqual(self.codes(self.router(raw), 'coder')[1]['considered'][0]['reason'], 'recipe_disabled')


class ContextTierTests(Base):
    GPU = SimpleNamespace(hardware_class='nvidia_10_12', cpu_threads=16, gpu_vendor='NVIDIA', ram_gb=32, vram_gb=12)

    def tiered(self, maximum=65536, measured_maximum=None, **kw):
        context = {'recommended': 8192, 'maximum': maximum, 'tiers': [8192, 16384, 32768, 65536]}
        if measured_maximum: context['measured_maximum'] = measured_maximum
        base = dict(profile={'context': context, 'gpu_layers': 99, 'kv_cache': {'placement': 'gpu'}}, model_size_gb=6.0,
                    measured_vram_gb=8.0, measured_context=8192, kv_cache_gb_per_1k_tokens=0.025)
        base.update(kw)
        return self.router(routing_raw([recipe('c.t', ['coder'], 'pt', 'ft', 'wt', model='m-t', **base)]), snapshot=self.GPU)

    def test_smallest_tier_that_holds_the_need_is_loaded_not_the_biggest_that_fits(self):
        router = self.tiered(measured_maximum=65536)
        self.assertEqual(router.resolve_role('coder')['context_window'], 8192)
        self.assertEqual(router.resolve_role('coder', {'context_min_tokens': 9000})['context_window'], 16384)
        self.assertEqual(router.resolve_role('coder', {'context_min_tokens': 32768})['context_window'], 32768)
        self.assertEqual(router.resolve_role('coder', {'context_min_tokens': 40000})['context_window'], 65536)

    def test_generic_hardware_cap_is_raised_only_by_a_declared_measurement_and_never_above_the_recipe_maximum(self):
        capped = self.tiered()                                                                        # no measured_maximum
        window = capped.resolve_role('coder')['context_window']; self.assertEqual(window, 8192)
        reason = lambda r, req: self.codes(r, 'coder', req)[1]['considered'][0]['reason']
        self.assertEqual(reason(self.tiered(maximum=65536), {'context_min_tokens': 40000}), 'context_capacity')    # class cap 32768
        low = self.tiered(maximum=16384, measured_maximum=65536)
        self.assertEqual(reason(low, {'context_min_tokens': 20000}), 'context_capacity')              # measurement cannot exceed the recipe's own maximum

    def test_a_chosen_window_that_was_measured_is_loaded_as_chosen(self):
        # Der Nutzer wählt 64k im Dropdown (context_recommended), der Hardware-Check kappt auf 32k; mit gemessener Grenze gilt 64k.
        def chosen(recommended, **kw):
            context = {'recommended': recommended, 'maximum': 65536, 'tiers': [8192, 16384, 32768, 65536]}
            context.update(kw)
            base = dict(profile={'context': context, 'gpu_layers': 99, 'kv_cache': {'placement': 'gpu'}}, model_size_gb=6.0,
                        measured_vram_gb=8.0, measured_context=8192, kv_cache_gb_per_1k_tokens=0.025)
            return self.router(routing_raw([recipe('c.t', ['coder'], 'pt', 'ft', 'wt', model='m-t', **base)]), snapshot=self.GPU)
        self.assertEqual(chosen(65536, measured_maximum=65536).resolve_role('coder')['context_window'], 65536)
        self.assertEqual(chosen(32768).resolve_role('coder')['context_window'], 32768)          # ohne Messung gilt die Kappe
        self.assertEqual(chosen(16384, measured_maximum=65536).resolve_role('coder')['context_window'], 16384)   # gewählt, was klein ist

    def test_moe_offload_uses_the_measurement_even_below_the_size_rule(self):
        # gpt-oss-20b: 11.28 GB of weights, 9.92 GiB measured with n_cpu_moe 4 (experts partly in host RAM)
        server = {'gguf': 'x.gguf', 'n_cpu_moe': 4}
        profile = {'context': {'recommended': 8192, 'maximum': 16384, 'tiers': [8192, 16384]}, 'gpu_layers': 99,
                   'kv_cache': {'placement': 'gpu'}, 'server': server}
        moe = self.tiered(profile=profile, model_size_gb=11.28, measured_vram_gb=9.92)
        self.assertEqual(moe.resolve_role('coder')['estimated_resources']['vram_gb'], 9.92)
        dense = self.tiered(model_size_gb=11.28, measured_vram_gb=9.92)                               # no offload: the size rule stays the floor
        self.assertEqual(dense.resolve_role('coder')['estimated_resources']['vram_gb'], round(11.28 * 1.05, 2))

    def test_vram_grows_with_the_tier_from_the_measurement_and_the_rate(self):
        router = self.tiered(measured_maximum=65536)
        small = router.resolve_role('coder')['estimated_resources']
        big = router.resolve_role('coder', {'context_min_tokens': 33000})['estimated_resources']
        self.assertEqual((small['vram_gb'], small['kv_cache_gb'], small['complete']), (8.0, 0.0, True))
        self.assertEqual((big['vram_gb'], big['kv_cache_gb'], big['complete']), (8.0, round(0.025 * (65536 - 8192) / 1000, 3), True))

    def test_without_tiers_nothing_changes_and_bad_tiers_are_refused(self):
        self.assertEqual(self.router().resolve_role('coder')['context_window'], 16384)
        for bad in ([], [8192, 4096], [8192, 8192], [0, 8192], ['a'], 'x'):
            with self.assertRaises(ValueError, msg=str(bad)):
                RoutingConfig(routing_raw([recipe('c.b', ['coder'], 'pb', 'fb', 'wb', profile={'context': {'recommended': 8192, 'maximum': 32768, 'tiers': bad}})]))
        with self.assertRaises(ValueError):
            RoutingConfig(routing_raw([recipe('c.b', ['coder'], 'pb', 'fb', 'wb', measured_context=0)]))


class PolicyTests(Base):
    def test_permission_level_above_the_capability_is_denied(self):
        code, detail = self.codes(self.router(), 'coder', {'permission_level': 3})
        self.assertEqual((code, detail['considered'][0]['reason']), ('policy_denied', 'permission_level_exceeds_capability'))
        self.assertEqual(self.router().resolve_role('coder', {'permission_level': 2})['permission_level_allowed'], 2)

    def test_network_rules(self):
        online = recipe('c.net', ['coder'], 'pn', 'fn', 'wn', network={'allowed': True})
        router = self.router(routing_raw([online]))
        self.assertEqual(self.codes(router, 'coder', {'network': 'denied'})[0], 'policy_denied')
        self.assertEqual(router.resolve_role('coder', {'network': 'allowed'})['capability_id'], 'c.net')
        cloud = recipe('c.cl', ['coder'], 'pcl', 'fcl', 'wcl', location='cloud', network={'allowed': True})
        router = self.router(routing_raw([cloud], cloud_allowed=True))
        self.assertEqual(self.codes(router, 'coder', {'network': 'local'}, captain_cloud_approved=True)[1]['considered'][0]['reason'], 'location_not_local')

    def test_cloud_needs_policy_and_captain_approval_and_a_harmless_data_class(self):
        cloud = recipe('c.cl', ['coder'], 'pcl', 'fcl', 'wcl', location='cloud', network={'allowed': True})
        closed = self.router(routing_raw([cloud], cloud_allowed=False))
        self.assertEqual(self.codes(closed, 'coder', {'network': 'allowed'}, captain_cloud_approved=True)[1]['considered'][0]['reason'], 'cloud_not_allowed')
        opened = self.router(routing_raw([cloud], cloud_allowed=True))
        self.assertEqual(self.codes(opened, 'coder', {'network': 'allowed'})[1]['considered'][0]['reason'], 'cloud_needs_captain_approval')
        for data_class in ('confidential', 'restricted'):
            self.assertEqual(self.codes(opened, 'coder', {'network': 'allowed', 'data_class': data_class}, captain_cloud_approved=True)[1]['considered'][0]['reason'],
                             'data_class_forbids_cloud')
        self.assertEqual(opened.resolve_role('coder', {'network': 'allowed', 'data_class': 'internal'}, captain_cloud_approved=True)['location'], 'cloud')

    def test_untrusted_capabilities_are_refused_by_default(self):
        for level in ('GUPPI_GENERATED', 'EXTERNAL_UNVERIFIED'):
            made = recipe('c.made', ['coder'], 'pm', 'fm', 'wm', metadata={'source': 'x', 'trust_level': level})
            code, detail = self.codes(self.router(routing_raw([made])), 'coder')
            self.assertEqual((code, detail['considered'][0]['reason']), ('policy_denied', f'trust_level_not_allowed:{level}'))

    def test_policy_denial_wins_only_when_every_candidate_is_denied_by_policy(self):
        mixed = routing_raw([recipe('c.hi', ['coder'], 'p1', 'f1', 'w1', permissions={'max_level': 1}),
                             recipe('c.off', ['coder'], 'p2', 'f2', 'w2', enabled=False)])
        self.assertEqual(self.codes(self.router(mixed), 'coder', {'permission_level': 2})[0], 'requirements_unmet')   # one is disabled, not denied
        allpolicy = routing_raw([recipe('c.hi', ['coder'], 'p1', 'f1', 'w1', permissions={'max_level': 1})])
        self.assertEqual(self.codes(self.router(allpolicy), 'coder', {'permission_level': 2})[0], 'policy_denied')


class FallbackTests(Base):
    def two(self):
        return self.router(routing_raw([recipe('c.one', ['coder'], 'p1', 'f1', 'w1'), recipe('c.two', ['coder'], 'p2', 'f2', 'w2')]))

    def test_fallback_picks_another_provider_for_the_same_role(self):
        router = self.two(); first = router.resolve_role('coder')
        second = router.resolve_fallback(first, 'timeout')
        self.assertEqual((first['provider_ref'], second['provider_ref'], second['fallback_of']), ('p1', 'p2', 'c.one'))
        self.assertEqual(second['requirements'], first['requirements'])

    def test_policy_denied_never_falls_back(self):
        router = self.two(); first = router.resolve_role('coder')
        code, detail = self.codes_fallback(router, first, 'policy_denied')
        self.assertEqual((code, detail['reason']), ('policy_denied', 'fallback_never_bypasses_policy'))

    def codes_fallback(self, router, first, failure_class, requirements=None, **kw):
        with self.assertRaises(ResolutionError) as ctx: router.resolve_fallback(first, failure_class, requirements, **kw)
        return ctx.exception.code, ctx.exception.detail

    def test_fallback_cannot_loosen_what_the_job_demanded(self):
        router = self.two(); first = router.resolve_role('coder', {'network': 'denied', 'data_class': 'confidential', 'permission_level': 1})
        for looser in ({'network': 'allowed', 'data_class': 'confidential', 'permission_level': 1},
                       {'network': 'denied', 'data_class': 'public', 'permission_level': 1},
                       {'network': 'denied', 'data_class': 'confidential', 'permission_level': 2}):
            code, detail = self.codes_fallback(router, first, 'rate_limit', looser)
            self.assertEqual((code, detail['reason']), ('policy_denied', 'fallback_loosens_requirements'), str(looser))
        stricter = router.resolve_fallback(first, 'rate_limit', {'network': 'denied', 'data_class': 'restricted', 'permission_level': 0})
        self.assertEqual(stricter['provider_ref'], 'p2')

    def test_last_provider_exhausted_is_provider_unavailable(self):
        router = self.two(); first = router.resolve_role('coder')
        second = router.resolve_fallback(first, 'timeout')
        self.assertEqual(self.codes_fallback(router, second, 'timeout', exclude=['p1'])[0], 'provider_unavailable')

    def test_exclude_matches_provider_or_independence_key(self):
        router = self.two()
        self.assertEqual(router.resolve_role('coder', exclude=['p1'])['provider_ref'], 'p2')
        self.assertEqual(router.resolve_role('coder', exclude=['f1:w1'])['provider_ref'], 'p2')
        self.assertEqual(self.codes(router, 'coder', exclude=['p1', 'p2'])[0], 'provider_unavailable')

    def test_a_cooling_provider_is_not_chosen(self):
        router = self.two()
        self.health.report_failure('p1', 'rate_limit', retry_after_s=60)
        self.assertEqual(router.resolve_role('coder')['provider_ref'], 'p2')
        self.health.report_failure('p2', 'rate_limit', retry_after_s=60)
        self.assertEqual(self.codes(router, 'coder')[0], 'provider_unavailable')
        self.clock.advance(61)
        self.assertEqual(router.resolve_role('coder')['health_state'], 'DEGRADED')            # one trial after the cooldown


class IndependenceTests(Base):
    def verifier_router(self, verifier_weights='wv', verifier_family='fv'):
        return self.router(routing_raw([recipe('c.a', ['coder'], 'pa', 'fa', 'wa'), recipe('v.x', ['verifier'], 'pv', verifier_family, verifier_weights)]))

    def test_independent_verifier_resolves(self):
        router = self.verifier_router(); builder = router.resolve_role('coder')
        res = router.resolve_role('verifier', independent_of=[builder['independence_key']])
        self.assertEqual(res['independence_key'], 'fv:wv')

    def test_same_model_is_not_independent_even_under_another_role(self):
        router = self.router(routing_raw([recipe('c.a', ['coder', 'verifier'], 'pa', 'fa', 'wa')]))
        builder = router.resolve_role('coder')
        code, detail = self.codes(router, 'verifier', independent_of=[builder['independence_key']])
        self.assertEqual((code, detail['considered'][0]['reason']), ('requirements_unmet', 'not_independent'))

    def test_unknown_identity_is_never_independent(self):
        router = self.verifier_router(verifier_weights=None)
        self.assertEqual(self.codes(router, 'verifier', independent_of=['fa:wa'])[1]['considered'][0]['reason'], 'independence_unverifiable')
        known = self.verifier_router()
        self.assertEqual(self.codes(known, 'verifier', independent_of=[None])[1]['considered'][0]['reason'], 'independence_unverifiable')

    def test_key_for_role_is_none_when_unprovable_and_quiet(self):
        router = self.verifier_router(verifier_weights=None); events = len(self.types())
        self.assertIsNone(router.key_for_role('verifier'))
        self.assertIsNone(router.key_for_role('astronaut'))
        self.assertEqual(router.key_for_role('coder'), 'fa:wa')
        self.assertEqual(len(self.types()), events)                                                  # probing writes no audit entries


class ProviderHealthTests(Base):
    def health_(self, **kw):
        raw = routing_raw(); raw['provider_health'].update(kw)
        return ProviderHealth(RoutingConfig(raw), self.root / 'h.json', audit=self.audit, clock=self.clock.now)

    def test_escalation_from_healthy_to_cooldown(self):
        h = self.health_()
        self.assertEqual(h.state('p'), 'HEALTHY')
        self.assertEqual(h.report_failure('p', 'timeout'), 'HEALTHY')
        self.assertEqual(h.report_failure('p', 'timeout'), 'DEGRADED')
        self.assertTrue(h.allows('p'))
        self.assertEqual(h.report_failure('p', 'timeout'), 'COOLDOWN')
        self.assertFalse(h.allows('p'))

    def test_cooldown_grows_exponentially_and_is_capped(self):
        h = self.health_(base_cooldown_s=30, max_cooldown_s=100)
        for _ in range(3): h.report_failure('p', 'timeout')
        waits = []
        for _ in range(4):
            entry = h.view()['p']
            waits.append((datetime.fromisoformat(entry['cooldown_until']) - self.clock.now()).total_seconds())
            self.clock.advance(waits[-1] + 1)
            self.assertEqual(h.state('p'), 'DEGRADED')                    # trial
            h.report_failure('p', 'timeout')                              # the trial fails again
        self.assertEqual(waits[0], 30)
        self.assertLess(waits[0], waits[1]); self.assertLessEqual(max(waits), 100)
        self.assertEqual(waits[-1], 100)                                  # grew until the cap and stayed there

    def test_success_restores_health_and_resets_the_count(self):
        h = self.health_()
        for _ in range(3): h.report_failure('p', 'timeout')
        self.clock.advance(31)
        self.assertEqual(h.report_success('p'), 'HEALTHY')
        self.assertEqual(h.view()['p']['consecutive_faults'], 0)
        self.assertEqual(h.report_failure('p', 'timeout'), 'HEALTHY')     # the counter started over

    def test_rate_limit_cools_down_at_once_and_respects_retry_after_within_the_cap(self):
        h = self.health_()
        self.assertEqual(h.report_failure('p', 'rate_limit', retry_after_s=90), 'COOLDOWN')
        self.clock.advance(89); self.assertEqual(h.state('p'), 'COOLDOWN')
        self.clock.advance(2); self.assertEqual(h.state('p'), 'DEGRADED')
        h.report_failure('q', 'rate_limit', retry_after_s=10 ** 9)
        entry = h.view()['q']
        self.assertLessEqual((datetime.fromisoformat(entry['cooldown_until']) - self.clock.now()).total_seconds(), 600)

    def test_runtime_crash_cools_down_immediately(self):
        self.assertEqual(self.health_().report_failure('p', 'runtime_crash'), 'COOLDOWN')

    def test_model_unavailable_needs_a_probe(self):
        h = self.health_()
        self.assertEqual(h.report_failure('p', 'model_unavailable'), 'UNAVAILABLE')
        self.clock.advance(10 ** 6); self.assertEqual(h.state('p'), 'UNAVAILABLE')       # time alone does not bring it back
        self.assertEqual(h.probe('p', False), 'UNAVAILABLE')
        self.assertEqual(h.probe('p', True), 'DEGRADED')
        self.assertEqual(h.report_success('p'), 'HEALTHY')

    def test_faults_that_are_not_the_providers_do_not_count(self):
        h = self.health_()
        for failure_class in ('policy_denied', 'deterministic_test_failure', 'context_overflow', 'context_quality_degraded',
                              'validation_failure', 'hardware_pressure', 'unknown_failure'):
            self.assertNotIn(failure_class, PROVIDER_FAULTS)
            for _ in range(10): h.report_failure('p', failure_class)
        self.assertEqual(h.state('p'), 'HEALTHY')
        self.assertNotIn('p', h.view())

    def test_state_survives_a_restart(self):
        h = self.health_()
        for _ in range(3): h.report_failure('p', 'timeout')
        again = self.health_()
        self.assertEqual(again.state('p'), 'COOLDOWN')
        self.assertEqual(again.view()['p']['faults_total'], 3)

    def test_a_clock_set_backwards_cannot_freeze_a_provider(self):
        h = self.health_(max_cooldown_s=600)
        for _ in range(3): h.report_failure('p', 'timeout')
        self.assertEqual(h.state('p'), 'COOLDOWN')
        self.clock.advance(-86400)                                                         # clock found a day BEFORE the cooldown began
        self.assertEqual(h.state('p'), 'DEGRADED')                                         # ends early (one trial) instead of freezing
        self.assertTrue(h.allows('p'))
        self.clock.advance(86400 + 5)                                                      # clock is back, 5 s into the original 30 s window
        self.assertEqual(h.state('p'), 'COOLDOWN')                                         # the remainder applies again: bounded by that cooldown, never longer
        self.clock.advance(30)
        self.assertEqual(h.state('p'), 'DEGRADED')
        h.report_failure('p', 'timeout')                                                   # the trial fails: a fresh cooldown, bounded by the maximum
        entry = h.view()['p']
        self.assertEqual(h.state('p'), 'COOLDOWN')
        self.assertLessEqual((datetime.fromisoformat(entry['cooldown_until']) - datetime.fromisoformat(entry['cooldown_started'])).total_seconds(), 600)
        self.clock.advance(-1)                                                             # a small step back also ends it early, never extends it
        self.assertEqual(h.state('p'), 'DEGRADED')

    def test_only_changes_are_audited(self):
        h = self.health_()
        h.report_failure('p', 'timeout')                  # HEALTHY -> HEALTHY
        h.report_success('p')                             # HEALTHY -> HEALTHY
        self.assertNotIn('PROVIDER_HEALTH_CHANGED', self.types())
        h.report_failure('p', 'timeout'); h.report_failure('p', 'timeout')
        self.assertEqual(self.types().count('PROVIDER_HEALTH_CHANGED'), 1)
        self.assertTrue(self.audit.verify_chain())

    def test_concurrent_reports_lose_no_fault(self):
        h = self.health_()
        threads = [threading.Thread(target=lambda: [h.report_failure('p', 'timeout') for _ in range(10)]) for _ in range(6)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(h.view()['p']['faults_total'], 60)

    def test_without_a_file_it_works_in_memory(self):
        h = ProviderHealth(RoutingConfig(routing_raw()), None, clock=self.clock.now)
        for _ in range(3): h.report_failure('p', 'timeout')
        self.assertEqual(h.state('p'), 'COOLDOWN')


class ModelRouterIntegrationTests(Base):
    class Adapter:
        def __init__(self, adapter_id, fail=None): self.id = adapter_id; self.fail = fail; self.calls = 0
        def health(self): return True
        def chat(self, messages, model=None, **kw):
            self.calls += 1
            if self.fail: raise self.fail
            return {'provider': self.id, 'model': 'm', 'content': 'ok'}

    def build(self, *adapters, with_health=True):
        router = ModelRouter(self.audit)
        for a in adapters: router.register(a)
        self.health = ProviderHealth(RoutingConfig(routing_raw()), None, clock=self.clock.now)
        if with_health: router.provider_health = self.health
        return router

    def test_without_the_hook_nothing_changes(self):
        a = self.Adapter('p1', fail=TimeoutError('slow'))
        router = self.build(a, with_health=False)
        for _ in range(5):
            with self.assertRaises(TimeoutError): router.chat('M-1', [{'role': 'user', 'content': 'x'}])
        self.assertEqual(a.calls, 5)
        self.assertEqual(self.health.view(), {})

    def test_failures_are_reported_and_a_cooling_provider_is_skipped(self):
        bad, good = self.Adapter('p1', fail=TimeoutError('slow')), self.Adapter('p2')
        router = self.build(bad, good)
        for _ in range(3):
            with self.assertRaises(TimeoutError): router.chat('M-1', [{'role': 'user', 'content': 'x'}], provider='p1')
        self.assertEqual(self.health.state('p1'), 'COOLDOWN')
        with self.assertRaises(ModelAdapterError) as ctx: router.chat('M-1', [{'role': 'user', 'content': 'x'}], provider='p1')
        self.assertEqual(str(ctx.exception), 'provider_cooldown:p1')
        self.assertEqual(bad.calls, 3)                                                       # the fourth call never reached the provider
        self.assertEqual(router.chat('M-1', [{'role': 'user', 'content': 'x'}])['provider'], 'p2')   # automatic choice skips it

    def test_success_is_reported(self):
        router = self.build(self.Adapter('p1'))
        self.health.report_failure('p1', 'timeout'); self.health.report_failure('p1', 'timeout')
        router.chat('M-1', [{'role': 'user', 'content': 'x'}])
        self.assertEqual(self.health.state('p1'), 'HEALTHY')

    def test_errors_that_are_not_provider_faults_do_not_punish(self):
        router = self.build(self.Adapter('p1', fail=ModelAdapterError('messages_required')))
        for _ in range(5):
            with self.assertRaises(ModelAdapterError): router.chat('M-1', [{'role': 'user', 'content': 'x'}])
        self.assertEqual(self.health.state('p1'), 'HEALTHY')


class SupervisorIntegrationTests(Base):
    def setUp(self):
        super().setUp()
        self.router_ = self.router(routing_raw([recipe('c.one', ['coder', 'reviewer'], 'p1', 'f1', 'w1'),
                                                recipe('c.two', ['coder', 'reviewer'], 'p2', 'f2', 'w2'),
                                                recipe('v.one', ['verifier'], 'p3', 'f3', 'w3')]))
        self.reports = []
        raw = yaml.safe_load(SUPERVISOR.read_text(encoding='utf-8'))['job_supervisor']; raw['enabled'] = True
        self.sup = JobSupervisor(SupervisorJobStore(self.root / 'jobs', self.audit), SupervisorConfig(raw), audit=self.audit,
                                 clock=self.clock.now, monotonic=self.clock.monotonic, pass_gate=lambda job, v: [],
                                 resolver=lambda role, req, exclude, independent_of: self.router_.resolve_role(role, req, exclude=exclude, independent_of=independent_of),
                                 provider_report=self.report)

    def report(self, ref, outcome, failure_class=None):
        self.reports.append((ref, outcome, failure_class))
        (self.health.report_success(ref) if outcome == 'success' else self.health.report_failure(ref, failure_class))

    def contract(self, **kw):
        kw.setdefault('acceptance_criteria', [{'type': 'capability_smoke_test', 'id': 's'}]); kw.setdefault('verification_plan', [{'type': 'deterministic_tests'}])
        return development_contract(objective='probe', classification='E1', **kw)

    def start(self, role='reviewer', worker='w1', **kw):
        job = self.sup.create_job(self.contract(), requested_role=role, **kw)
        self.sup.enqueue(job['job_id']); self.sup.claim(worker, [role])
        return job['job_id'], self.sup.confirm_start(job['job_id'], worker)

    def load(self, job_id): return self.sup.store.load(job_id)

    def test_start_records_the_resolution_on_the_attempt(self):
        job_id, started = self.start('coder')
        attempt = self.load(job_id)['attempt_log'][0]
        self.assertEqual((attempt['provider_ref'], attempt['capability'], attempt['independence_key']), ('p1', 'c.one', 'f1:w1'))
        self.assertEqual(started['status'], 'running')

    def test_requirements_are_stored_validated_and_used(self):
        with self.assertRaises(JobError) as ctx: self.sup.create_job(self.contract(), requested_role='coder', requirements={'telepathy': 1})
        self.assertEqual(ctx.exception.code, 'invalid_requirements')
        job = self.sup.create_job(self.contract(), requested_role='coder', requirements={'network': 'local'})
        self.assertEqual(job['role_requirements'], {'network': 'local'})

    def test_permission_level_of_the_job_reaches_the_router(self):
        job = self.sup.create_job(self.contract(permission_level=3), requested_role='coder')    # recipes allow level 2 only
        self.sup.enqueue(job['job_id']); self.sup.claim('w1', ['coder'])
        out = self.sup.confirm_start(job['job_id'], 'w1')
        self.assertEqual((out['status'], out['code']), ('resolution_failed', 'policy_denied'))
        stored = self.load(job['job_id'])
        self.assertEqual((stored['state'], stored['supervisor_flags']['escalated_to']), ('BLOCKED', 'captain'))
        self.assertEqual(stored['attempt_log'][0]['outcome'], 'FAILED')
        self.assertEqual(self.reports, [])                                                    # no provider was involved, none is blamed

    def test_resolution_failures_follow_the_retry_rules(self):
        cases = {'provider_unavailable': ('QUEUED', None), 'hardware_pressure': ('QUEUED', None),
                 'no_capability': ('BLOCKED', 'guppi'), 'requirements_unmet': ('BLOCKED', 'guppi'), 'policy_denied': ('BLOCKED', 'captain')}
        for code, (state, escalated) in cases.items():
            with self.subTest(code=code):
                self.setUp()
                self.sup.resolver = lambda role, req, exclude, independent_of, code=code: (_ for _ in ()).throw(ResolutionError(code))
                job = self.sup.create_job(self.contract(), requested_role='reviewer')
                self.sup.enqueue(job['job_id']); self.sup.claim('w1', ['reviewer'])
                out = self.sup.confirm_start(job['job_id'], 'w1')
                stored = self.load(job['job_id'])
                self.assertEqual((out['status'], stored['state'], stored['supervisor_flags']['escalated_to']), ('resolution_failed', state, escalated))
                self.assertIsNone(stored['worker'])

    def test_a_resolver_that_crashes_does_not_strand_the_job(self):
        self.sup.resolver = lambda role, req, exclude, independent_of: (_ for _ in ()).throw(RuntimeError('router exploded'))
        job = self.sup.create_job(self.contract(), requested_role='reviewer')
        self.sup.enqueue(job['job_id']); self.sup.claim('w1', ['reviewer'])
        with self.assertRaises(RuntimeError): self.sup.confirm_start(job['job_id'], 'w1')
        self.clock.advance(self.sup.config.claim_timeout_s + 1); self.sup.reap()
        self.assertEqual(self.load(job['job_id'])['state'], 'QUEUED')                         # the claim simply expires

    def test_provider_outcomes_reach_the_health_tracker(self):
        job_id, _ = self.start('reviewer')
        self.sup.fail(job_id, 'w1', exception=TimeoutError('slow'))
        self.assertEqual(self.reports, [('p1', 'failure', 'timeout')])
        self.assertEqual(self.health.view()['p1']['faults_total'], 1)

    def test_fallback_end_to_end_after_repeated_timeouts_and_cooldown(self):
        job_id, _ = self.start('reviewer')
        used = []
        for _ in range(3):
            used.append(self.load(job_id)['attempt_log'][-1]['provider_ref'])
            self.sup.fail(job_id, 'w1', exception=TimeoutError('slow'))
            self.clock.advance(300)
            if len(used) < 3:
                self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
        # Two timeouts make p1 DEGRADED, so the health-aware router already prefers the HEALTHY p2 for the third attempt.
        self.assertEqual(used, ['p1', 'p1', 'p2'])
        self.assertEqual(self.load(job_id)['retry']['exclude'], ['p2'])                       # the third timeout asked for a fallback away from p2
        self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
        self.assertEqual(self.load(job_id)['attempt_log'][-1]['provider_ref'], 'p1')          # the new attempt runs elsewhere (p1 is DEGRADED, not cooling)

    def test_lost_worker_signals_the_provider(self):
        job_id, _ = self.start('reviewer')
        self.sup.reap(); self.clock.advance(self.sup.config.lease_s + self.sup.config.suspect_after_s + 1); self.sup.reap()
        self.clock.advance(self.sup.config.grace_s + 1); self.sup.reap()
        self.assertEqual(self.reports, [('p1', 'failure', 'timeout')])

    def test_verification_success_is_reported_to_the_provider(self):
        job_id, _ = self.start('reviewer')
        self.sup.complete_step(job_id, 'w1', 'TESTING'); self.sup.complete_step(job_id, 'w1', 'VERIFYING')
        self.sup.mark_passed(job_id, 'w1', {'result': 'PASS', 'verification_digest': 'd' * 64})
        self.assertEqual(self.reports, [('p1', 'success', None)])

    def finish_builder(self, key_recipe_role='coder'):
        builder_id, _ = self.start('coder', worker='wb')
        self.sup.complete_step(builder_id, 'wb', 'TESTING'); self.sup.complete_step(builder_id, 'wb', 'VERIFYING')
        self.sup.mark_passed(builder_id, 'wb', {'result': 'PASS', 'verification_digest': 'b' * 64})
        return builder_id

    def verify(self, builder_id, worker='wv'):
        job = self.sup.create_job(self.contract(), requested_role='verifier', depends_on=[builder_id])
        self.sup.enqueue(job['job_id']); self.sup.claim(worker, ['verifier'])
        started = self.sup.confirm_start(job['job_id'], worker)
        if started['status'] != 'running': return job['job_id'], started
        self.sup.complete_step(job['job_id'], worker, 'TESTING'); self.sup.complete_step(job['job_id'], worker, 'VERIFYING')
        return job['job_id'], started

    def test_an_independent_verifier_may_pass_the_candidate(self):
        builder = self.finish_builder()
        job_id, started = self.verify(builder)
        self.assertEqual(self.load(job_id)['attempt_log'][0]['independence_key'], 'f3:w3')
        done = self.sup.mark_passed(job_id, 'wv', {'result': 'PASS', 'verification_digest': 'v' * 64})
        self.assertEqual(done['job']['state'], 'READY_FOR_ACCEPTANCE')

    def test_a_verifier_on_the_same_model_as_the_builder_cannot_pass(self):
        raw = routing_raw([recipe('c.one', ['coder', 'verifier'], 'p1', 'f1', 'w1')])
        self.router_ = self.router(raw)
        builder = self.finish_builder()
        job_id, started = self.verify(builder)
        # The resolver already refuses: the only verifier candidate is the builder's own model.
        self.assertEqual((started['status'], started['code']), ('resolution_failed', 'requirements_unmet'))
        self.assertEqual(self.load(job_id)['supervisor_flags']['escalated_to'], 'guppi')

    def test_a_verifier_without_a_provable_identity_cannot_pass(self):
        self.router_ = self.router(routing_raw([recipe('c.one', ['coder'], 'p1', 'f1', 'w1'), recipe('v.one', ['verifier'], 'p3', 'f3', None)]))
        builder = self.finish_builder()
        job_id, started = self.verify(builder)
        self.assertEqual((started['status'], started['code']), ('resolution_failed', 'requirements_unmet'))

    def test_mark_passed_re_checks_independence_itself(self):
        builder = self.finish_builder()
        job_id, started = self.verify(builder)
        with self.sup.store.mutate(job_id) as job:                       # simulate a verifier attempt that ran on the builder's model
            job['attempt_log'][-1]['independence_key'] = 'f1:w1'
        with self.assertRaises(JobError) as ctx: self.sup.mark_passed(job_id, 'wv', {'result': 'PASS', 'verification_digest': 'v' * 64})
        self.assertEqual((ctx.exception.code, ctx.exception.detail), ('verification_inconclusive', {'independence': ['SAME']}))
        with self.sup.store.mutate(job_id) as job: job['attempt_log'][-1]['independence_key'] = None
        with self.assertRaises(JobError) as ctx: self.sup.mark_passed(job_id, 'wv', {'result': 'PASS', 'verification_digest': 'v' * 64})
        self.assertEqual(ctx.exception.detail, {'independence': ['UNVERIFIABLE']})
        self.assertEqual(self.load(job_id)['state'], 'VERIFYING')

    def test_a_verifier_without_any_builder_is_unverifiable(self):
        job = self.sup.create_job(self.contract(), requested_role='verifier')
        self.sup.enqueue(job['job_id']); self.sup.claim('wv', ['verifier'])
        out = self.sup.confirm_start(job['job_id'], 'wv')
        self.assertEqual(out['status'], 'resolution_failed')

    def test_roles_without_an_independence_rule_are_unaffected(self):
        job_id, _ = self.start('reviewer')
        self.sup.complete_step(job_id, 'w1', 'TESTING'); self.sup.complete_step(job_id, 'w1', 'VERIFYING')
        self.assertEqual(self.sup.mark_passed(job_id, 'w1', {'result': 'PASS', 'verification_digest': 'd' * 64})['status'], 'PASSED')

    def test_config_validates_the_independence_rule(self):
        for roles in ({'a': {'mutates': False, 'capability': 'c', 'independent_of': ['ghost']}},
                      {'a': {'mutates': False, 'capability': 'c', 'independent_of': ['a']}},
                      {'a': {'mutates': False, 'capability': 'c', 'independent_of': 'b'}}):
            raw = yaml.safe_load(SUPERVISOR.read_text(encoding='utf-8'))['job_supervisor']; raw['roles'] = roles
            with self.assertRaises(ValueError): SupervisorConfig(raw)


class RuntimeAndBoundaryTests(unittest.TestCase):
    def test_runtime_wires_routing_off_and_reports_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
            self.assertIsNotNone(rt.role_router); self.assertFalse(rt.role_router.enabled)
            self.assertFalse(hasattr(rt.model_router, 'provider_health'))                    # the model router is untouched while routing is off
            self.assertIsNone(rt.job_supervisor.resolver)
            self.assertIsNone(rt.self_development.independence_check)
            status = rt.boot()['role_routing']
            self.assertFalse(status['enabled'])
            self.assertEqual({c['id'] for c in status['capabilities']}, {'coder.local_primary', 'verifier.local_kev'})
            with self.assertRaises(ResolutionError) as ctx: rt.control.resolve_role('coder')
            self.assertEqual(ctx.exception.code, 'no_capability')

    @env_skip.needs_ram(16)
    def test_enabled_routing_wires_every_hook_and_resolves_through_the_control_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            import guppi_runtime.runtime as runtime_module
            real = runtime_module.RoutingConfig.load

            def enabled(path, local_path=None):
                config = real(path, local_path); config.enabled = True; return config

            runtime_module.RoutingConfig.load = staticmethod(enabled)
            try:
                rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
            finally:
                runtime_module.RoutingConfig.load = real
            self.assertTrue(rt.role_router.enabled)
            self.assertIs(rt.model_router.provider_health, rt.provider_health)
            self.assertIsNotNone(rt.job_supervisor.resolver); self.assertIsNotNone(rt.job_supervisor.provider_report)
            self.assertIsNotNone(rt.self_development.independence_check)
            res = rt.control.resolve_role('coder', {'permission_level': 1})
            self.assertEqual(res['capability_id'], 'coder.local_primary')
            self.assertIsNone(res['independence_key'])                                       # no weights id configured: unprovable
            with self.assertRaises(ResolutionError) as ctx: rt.control.resolve_role('verifier')
            self.assertEqual(ctx.exception.detail['considered'][0]['reason'], 'recipe_disabled')    # the verification layer is off until the Captain enables it
            self.assertEqual(rt.self_development.independence_check('coder', 'verifier'), 'UNVERIFIABLE')
            rt.control.model_router = SimpleNamespace()
            fb = rt.control.resolve_fallback(res, 'timeout') if False else None
            with self.assertRaises(ResolutionError) as ctx: rt.control.resolve_fallback(res, 'policy_denied')
            self.assertEqual(ctx.exception.code, 'policy_denied')
            rt.routing_status()

    def test_dev_path_downgrades_a_pass_without_provable_independence(self):
        from guppi_runtime.self_development import SelfDevelopmentManager
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH); sd = rt.self_development
            job_id = sd.start('independence_probe', evidence=[{'source': 't'}])['job']['job_id']
            sd.prepare_development_environment(job_id, {'execution_ready': True})
            sd.bind_candidate(job_id, attempt_id='a1', stage=f'guppi-candidates/{job_id}/p', parent_version='1', candidate_hash='a' * 64, builder='coder')
            cid = sd.jobs.load(job_id)['candidate']['candidate_id']
            ev = rt.development_evidence.add('t', job_id=job_id, candidate_id=cid, payload={'status': 'PASS'}, trust_level='deterministic')['evidence_id']
            calls = []
            sd.independence_check = lambda builder, verifier: calls.append((builder, verifier)) or 'SAME'
            record = sd.attach_verification(job_id, verifier='verifier', result='PASS', evidence_refs=[ev])
            self.assertEqual((record['result'], calls), ('INCONCLUSIVE', [('coder', 'verifier')]))
            self.assertIn('pass_downgraded:independence_same', record['findings'])

    def test_budget_floor_is_exact_and_explicit(self):
        mgr = ContextBudgetManager()
        self.assertEqual(ContextBudgetManager.MIN_CONTEXT_WINDOW, 3145)
        for window in range(1024, 3145):
            with self.assertRaises(ValueError, msg=window) as ctx: mgr.build_budget(window)
            self.assertEqual(str(ctx.exception), 'context_window_too_small', window)          # one clear message for the whole range
        for window in range(3145, 40000):
            self.assertEqual(mgr.build_budget(window)['context_window'], window)
        with self.assertRaises(ValueError): mgr.build_budget(1000)
        self.assertEqual(mgr.build_budget(2000, reserved_output_tokens=256, safety_margin=256, system_budget=200, project_context_budget=200,
                                          task_context_budget=400, tool_result_budget=200, recent_history_budget=100)['context_window'], 2000)   # explicit splits are still honoured

    def test_routing_source_names_no_provider_or_model(self):
        for name in ('role_routing.py', 'job_supervisor.py'):
            source = (RUNTIME / 'src' / 'guppi_runtime' / name).read_text(encoding='utf-8').lower()
            for word in ('lm-studio', 'lmstudio', 'llama', 'qwen', 'kev', 'openai', 'anthropic', 'gpt'):
                self.assertNotRegex(source, rf'\b{re.escape(word)}\b', f'{name}:{word}')


if __name__ == '__main__':
    unittest.main()


class ProfileRouting(Base):
    """The Captain's switchable model combination (routing_profiles.py), 2026-10-03."""
    def caps(self):
        return [recipe('coder.q', ['coder'], 'prov', 'qwen', 'wq'), recipe('coder.g', ['coder'], 'prov', 'gpt', 'wg'),
                recipe('verifier.m', ['verifier'], 'prov', 'gemma', 'wm')]

    def test_profile_reorders_and_may_lend_a_recipe_to_another_role(self):
        from guppi_runtime.routing_profiles import RoutingProfiles
        profiles = RoutingProfiles({'active': 'p', 'profiles': {'p': {'coder': {'prefer': ['verifier.m']},
                                                                      'rework': {'prefer': ['coder.g'], 'temperature': 1.0},
                                                                      'verifier': {'prefer': ['coder.g']}}}})
        router = self.router(routing_raw(self.caps()), profiles=profiles)
        self.assertEqual(router.resolve_role('coder')['capability_id'], 'verifier.m')          # gemma lent to the coder role
        rework = router.resolve_role('coder', purpose='rework')
        self.assertEqual((rework['capability_id'], rework['purpose'], rework['sampling']), ('coder.g', 'rework', {'temperature': 1.0}))
        self.assertEqual(router.resolve_role('verifier')['capability_id'], 'coder.g')
        # independence still holds: a verifier of the same family as the builder is skipped for the next one
        key_g = router.resolve_role('coder', purpose='rework')['independence_key']
        self.assertEqual(router.resolve_role('verifier', independent_of=[key_g])['capability_id'], 'verifier.m')

    def test_without_profile_the_recipe_order_stays(self):
        router = self.router(routing_raw(self.caps()))
        self.assertEqual(router.resolve_role('coder')['capability_id'], 'coder.q')
        self.assertEqual(router.resolve_role('coder', purpose='rework')['capability_id'], 'coder.q')
