"""Phase 7: reservations for RAM, VRAM and KV cache, thermal and job limits, and their place in the job lifecycle."""
import importlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import yaml

from guppi_runtime.core.audit import AuditLog
from guppi_runtime.selfdev.development_contracts import development_contract
from guppi_runtime.jobs.job_supervisor import JobError, JobSupervisor, SupervisorConfig, SupervisorJobStore
from guppi_runtime.jobs.resource_scheduler import ResourceConfig, ResourceScheduler, need_of
from guppi_runtime.models.role_routing import ProviderHealth, ResolutionError, RoleRouter, RoutingConfig
from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]
CONFIG = RUNTIME / 'config' / 'resource_scheduler.yaml'
SUPERVISOR = RUNTIME / 'config' / 'job_supervisor.yaml'
ARCH = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
SRC = str(RUNTIME / 'src')


def metric(value, state='valid'):
    return {'value': value, 'unit': 'GiB', 'source': 'test', 'state': state if value is not None else 'unavailable'}


def sample(*, thermal='NORMAL', ram_total=64.0, ram_available=60.0, gpus=((16.0, 16.0),), ram_valid=True):
    return {'thermal_state': thermal,
            'memory': {'total': metric(ram_total if ram_valid else None), 'available': metric(ram_available if ram_valid else None)},
            'gpus': [{'device_id': f'GPU-{i}', 'vram_total': metric(t), 'vram_available': metric(a)} for i, (t, a) in enumerate(gpus)]}


class FakeHardware:
    """Stands in for HardwareManager: a fixed picture of the host that tests change by hand."""
    def __init__(self, **kw): self.state = sample(**kw); self.profile = {'ram_reserve_gib': 2.0, 'max_jobs': 2}; self.fail = False; self.reads = 0
    def get_state(self, fresh=False):
        self.reads += 1
        if self.fail: raise RuntimeError(self.fail if isinstance(self.fail, str) else 'sensor stack down')
        return deepcopy(self.state)
    def active_profile(self): return dict(self.profile)


def raw_config(**overrides):
    raw = yaml.safe_load(CONFIG.read_text(encoding='utf-8'))['resource_scheduler']
    raw['enabled'] = True
    raw['vram_reserve_gb'] = 1.0      # the arithmetic of the tests is for a reserve of 1.0; the shipped value (0.7 since 2026-10-13) is checked on its own
    raw.update(overrides)
    return raw


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audit = AuditLog(self.root / 'audit.jsonl')
        self.hw = FakeHardware()
        self.clock_now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    def scheduler(self, hardware=None, **overrides):
        return ResourceScheduler(ResourceConfig(raw_config(**overrides)), hardware or self.hw, self.root / 'ledger.json', audit=self.audit, clock=lambda: self.clock_now)

    def types(self):
        path = self.root / 'audit.jsonl'
        return [json.loads(x)['event_type'] for x in path.read_text(encoding='utf-8').splitlines() if x.strip()] if path.exists() else []


class ConfigAndNeedTests(unittest.TestCase):
    def test_shipped_config_is_valid_and_off(self):
        config = ResourceConfig.load(CONFIG)
        self.assertFalse(config.enabled)
        self.assertEqual((config.vram_reserve_gb, config.unknown_vram, config.warm_max), (0.7, 'deny', 1))
        self.assertEqual(config.ram_reserve_gb, 1.5)

    def test_invalid_values_refuse_start(self):
        for bad in (dict(enabled='yes'), dict(vram_reserve_gb=-1), dict(vram_reserve_gb=True), dict(ram_reserve_gb='lots'), dict(warm_max_reservations=0),
                    dict(warm_max_reservations=2.5), dict(unknown_vram_telemetry='guess')):
            with self.assertRaises(ValueError, msg=str(bad)): ResourceConfig(raw_config(**bad))
        with self.assertRaises(ValueError): ResourceConfig.load(Path(tempfile.gettempdir()) / 'nope_resources.yaml')

    def test_kv_cache_counts_where_the_profile_puts_it_and_unknown_is_not_zero(self):
        self.assertEqual(need_of({'ram_gb': 4, 'vram_gb': 6, 'kv_cache_gb': 2, 'kv_cache_placement': 'gpu'}), {'ram_gb': 4.0, 'vram_gb': 8.0, 'complete': True})
        self.assertEqual(need_of({'ram_gb': 4, 'vram_gb': 0, 'kv_cache_gb': 2, 'kv_cache_placement': 'cpu'}), {'ram_gb': 6.0, 'vram_gb': 0.0, 'complete': True})
        unknown = need_of({'ram_gb': 4, 'vram_gb': 6, 'kv_cache_gb': None})
        self.assertEqual((unknown['vram_gb'], unknown['complete']), (6.0, False))               # the number is a minimum, and says so
        self.assertFalse(need_of({'ram_gb': 4, 'vram_gb': 6, 'kv_cache_gb': 1, 'complete': False})['complete'])
        self.assertEqual(need_of({}), {'ram_gb': 0.0, 'vram_gb': 0.0, 'complete': False})


class ReserveTests(Base):
    def test_stand_gibt_den_freien_speicher_fuer_die_aufteilung(self):
        """Dynamische Rezepte: frei = das kleinere von Ledger und Messung; die Reserven stehen dabei, nicht abgezogen; ohne Messung None."""
        hw = FakeHardware(ram_total=31.0, ram_available=14.3, gpus=((12.0, 10.65),))
        s = self.scheduler(hw)
        self.assertEqual(s.stand(), {'frei_vram_gb': 10.65, 'frei_ram_gb': 14.3, 'reserve_vram_gb': 1.0, 'reserve_ram_gb': s.config.ram_reserve_gb if s.config.ram_reserve_gb is not None else 2.0})
        s.reserve('J-1', 'A-1', {'ram_gb': 5.0, 'vram_gb': 4.0, 'complete': True})
        stand = s.stand()
        self.assertEqual((stand['frei_vram_gb'], stand['frei_ram_gb']), (8.0, 14.3 if 31.0 - 5.0 > 14.3 else 26.0))
        eigen = s.stand(ignore=('J-1',))
        self.assertEqual((eigen['frei_vram_gb'], eigen['frei_ram_gb']), (10.65, 14.3), 'die Reservierung des Starts, der gerade wählt, zählt nicht gegen ihn')
        self.assertEqual(s.stand(ignore=('J-2',))['frei_vram_gb'], 8.0, 'eine fremde Kennung ändert nichts')
        self.assertEqual(s.stand(nur_messung=True)['frei_vram_gb'], 10.65, 'nur die Messung: das Ledger zählt nicht')
        hw.fail = True
        self.assertIsNone(s.stand(), 'ohne Messung gibt es keinen Stand')
        self.assertIsNone(self.scheduler(FakeHardware(ram_valid=False)).stand())
        self.assertIsNone(self.scheduler(FakeHardware(gpus=())).stand(), 'ohne Grafikkarte kein Stand')

    def test_disabled_scheduler_promises_nothing_and_writes_nothing(self):
        s = ResourceScheduler(ResourceConfig(dict(raw_config(), enabled=False)), self.hw, self.root / 'ledger.json', audit=self.audit)
        out = s.reserve('SDJ-1', 'A1', {'vram_gb': 99})
        self.assertEqual((out['status'], out['reason'], out['reservation']), ('GRANTED', 'scheduler_disabled', None))
        self.assertEqual((s.release_job('SDJ-1'), s.reconcile([]), s.explain({'vram_gb': 99})), (0, [], None))
        self.assertFalse((self.root / 'ledger.json').exists())
        self.assertEqual(self.hw.reads, 0)

    def test_the_handoff_example_a_second_job_does_not_fit_beside_a_big_one(self):
        # 16 GB card, 2 GB safety reserve, one job holds 8.5 GB weights + 3.5 GB KV cache, a new job wants 6 GB more.
        s = self.scheduler(vram_reserve_gb=2.0)
        first = s.reserve('SDJ-A', 'A1', {'ram_gb': 4, 'vram_gb': 8.5, 'kv_cache_gb': 3.5, 'kv_cache_placement': 'gpu'})
        self.assertEqual((first['status'], first['reservation']['vram_gb'], first['reservation']['device_id']), ('GRANTED', 12.0, 'GPU-0'))
        self.hw.state = sample(gpus=((16.0, 4.0),))                                              # the first job really occupies its 12 GB now
        second = s.reserve('SDJ-B', 'A1', {'ram_gb': 4, 'vram_gb': 6})
        self.assertEqual((second['status'], second['reason']), ('DENIED', 'vram_insufficient'))
        self.assertEqual(second['detail']['best_free_gb'], 2.0)
        self.assertIn('queue', second['alternatives']); self.assertIn('smaller_model_or_cpu_offload', second['alternatives'])
        self.assertEqual([r['job_id'] for r in s.reservations()], ['SDJ-A'])
        s.release_job('SDJ-A'); self.hw.state = sample()
        self.assertEqual(s.reserve('SDJ-B', 'A2', {'ram_gb': 4, 'vram_gb': 6})['status'], 'GRANTED')

    def test_the_ledger_alone_can_refuse_even_when_the_measurement_looks_free(self):
        s = self.scheduler(vram_reserve_gb=1.0)
        s.reserve('SDJ-A', 'A1', {'vram_gb': 10})                                               # promised but not loaded yet: the card still reads 16 free
        out = s.reserve('SDJ-B', 'A1', {'vram_gb': 6})
        self.assertEqual((out['status'], out['reason'], out['detail']['best_free_gb']), ('DENIED', 'vram_insufficient', 5.0))

    def test_resident_instance_is_credited_to_the_measurement_but_never_above_the_request_or_past_the_ledger(self):
        self.hw.state = sample(gpus=((12.0, 3.0),))                                              # the model itself holds 9 GiB of the card
        s = self.scheduler(vram_reserve_gb=1.0)
        self.assertEqual(s.reserve('SDJ-A', 'A1', {'vram_gb': 8.0})['reason'], 'vram_insufficient')           # looks like a second copy
        self.assertEqual(s.explain({'vram_gb': 8.0}), 'vram_insufficient')
        self.assertIsNone(s.explain({'vram_gb': 8.0}, resident_vram_gb=8.0))
        self.assertEqual(s.reserve('SDJ-A', 'A2', {'vram_gb': 8.0}, resident_vram_gb=8.0)['status'], 'GRANTED')
        self.assertEqual(s.reserve('SDJ-B', 'A1', {'vram_gb': 8.0}, resident_vram_gb=8.0)['status'], 'DENIED')   # ledger: 8 already promised, 12 - 1 - 8 < 8
        s.release_job('SDJ-A')
        self.hw.state = sample(gpus=((12.0, 0.5),))                                              # a credit larger than the request counts only up to the request
        self.assertEqual(self.scheduler(vram_reserve_gb=1.0).reserve('SDJ-C', 'A1', {'vram_gb': 8.0}, resident_vram_gb=50.0)['reason'], 'vram_insufficient')

    def test_the_measurement_alone_can_refuse_even_when_nothing_was_promised(self):
        self.hw.state = sample(gpus=((16.0, 3.0),))                                              # another process occupies the card
        out = self.scheduler().reserve('SDJ-A', 'A1', {'vram_gb': 6})
        self.assertEqual((out['status'], out['reason'], out['detail']['best_free_gb']), ('DENIED', 'vram_insufficient', 2.0))

    def test_ram_follows_the_same_two_checks_and_the_profile_reserve(self):
        s = self.scheduler()                                                                     # reserve 2 GiB from the profile
        s.reserve('SDJ-A', 'A1', {'ram_gb': 40})
        out = s.reserve('SDJ-B', 'A1', {'ram_gb': 25})
        self.assertEqual((out['reason'], out['detail']['promised_gb']), ('ram_ledger', 40.0))     # 64 - 2 - 40 = 22 < 25
        s.release_job('SDJ-A'); self.hw.state = sample(ram_available=20.0)
        out = s.reserve('SDJ-B', 'A1', {'ram_gb': 25})
        self.assertEqual((out['reason'], out['detail']['available_gb']), ('ram_measured', 20.0))
        self.hw.state = sample()
        self.assertEqual(self.scheduler(ram_reserve_gb=45.0).reserve('SDJ-C', 'A1', {'ram_gb': 25})['reason'], 'ram_ledger')       # 64 - 45 = 19 < 25: the config overrides the profile's 2 GiB

    def test_missing_telemetry_is_never_read_as_plenty(self):
        self.hw.state = sample(ram_valid=False)
        self.assertEqual(self.scheduler().reserve('SDJ-A', 'A1', {'ram_gb': 1})['reason'], 'telemetry_unavailable_ram')
        self.assertEqual(self.scheduler().reserve('SDJ-A', 'A1', {'vram_gb': 0})['status'], 'GRANTED')            # asks for nothing, needs no reading
        self.hw.state = sample(gpus=())                                                          # no GPU telemetry (collector only reads NVIDIA cards)
        self.assertEqual(self.scheduler().reserve('SDJ-A', 'A1', {'vram_gb': 4})['reason'], 'no_gpu_telemetry_for_vram_request')
        self.assertEqual(self.scheduler().reserve('SDJ-B', 'A1', {'ram_gb': 4})['status'], 'GRANTED')             # CPU-only job is fine
        for job in ('SDJ-A', 'SDJ-B'): self.scheduler().release_job(job)
        granted = self.scheduler(unknown_vram_telemetry='declared_only').reserve('SDJ-C', 'A1', {'vram_gb': 4})
        self.assertEqual((granted['status'], granted['reservation']['device_id']), ('GRANTED', None))

    def test_a_gpu_with_unusable_readings_is_ignored(self):
        self.hw.state['gpus'] = [{'device_id': 'GPU-0', 'vram_total': metric(None), 'vram_available': metric(16.0)}]
        self.assertEqual(self.scheduler().reserve('SDJ-A', 'A1', {'vram_gb': 2})['reason'], 'no_gpu_telemetry_for_vram_request')

    def test_thermal_state_gates_admission(self):
        for state in ('HOT', 'CRITICAL', 'SENSOR_FAULT', 'RECOVERY'):
            self.hw.state = sample(thermal=state)
            out = self.scheduler().reserve('SDJ-A', 'A1', {'ram_gb': 1})
            self.assertEqual((out['status'], out['reason']), ('DENIED', f'thermal_{state.lower()}'), state)
        self.hw.state = sample(thermal='WARM'); s = self.scheduler()
        self.assertEqual(s.reserve('SDJ-A', 'A1', {'ram_gb': 1})['status'], 'GRANTED')
        self.assertEqual(s.reserve('SDJ-B', 'A1', {'ram_gb': 1})['reason'], 'job_limit')           # WARM: one at a time, though the profile allows two
        self.hw.state = sample(thermal='NORMAL')
        self.assertEqual(s.reserve('SDJ-B', 'A1', {'ram_gb': 1})['status'], 'GRANTED')

    def test_job_limit_follows_the_profile(self):
        self.hw.profile['max_jobs'] = 1; s = self.scheduler()
        s.reserve('SDJ-A', 'A1', {'ram_gb': 1})
        self.assertEqual(s.reserve('SDJ-B', 'A1', {'ram_gb': 1})['reason'], 'job_limit')
        self.hw.profile['max_jobs'] = 3
        self.assertEqual(s.reserve('SDJ-B', 'A1', {'ram_gb': 1})['status'], 'GRANTED')

    def test_exclusive_jobs_run_alone_and_others_wait_for_them(self):
        s = self.scheduler()
        s.reserve('SDJ-A', 'A1', {'ram_gb': 1})
        self.assertEqual(s.reserve('SDJ-X', 'A1', {'ram_gb': 1}, exclusive=True)['reason'], 'exclusive_conflict')
        s.release_job('SDJ-A')
        self.assertEqual(s.reserve('SDJ-X', 'A1', {'ram_gb': 1}, exclusive=True)['status'], 'GRANTED')
        self.assertEqual(s.reserve('SDJ-B', 'A1', {'ram_gb': 1})['reason'], 'exclusive_held')
        s.release_job('SDJ-X')
        self.assertEqual(s.reserve('SDJ-B', 'A1', {'ram_gb': 1})['status'], 'GRANTED')

    def test_the_card_with_the_most_room_is_chosen_and_recorded(self):
        self.hw.state = sample(gpus=((16.0, 16.0), (24.0, 24.0))); s = self.scheduler()
        a = s.reserve('SDJ-A', 'A1', {'vram_gb': 20})
        self.assertEqual(a['reservation']['device_id'], 'GPU-1')
        b = s.reserve('SDJ-B', 'A1', {'vram_gb': 10})                                            # GPU-1 has 3 left; GPU-0 has 15
        self.assertEqual(b['reservation']['device_id'], 'GPU-0')
        self.assertEqual(s.reserve('SDJ-C', 'A1', {'vram_gb': 10})['reason'], 'job_limit')        # max_jobs is 2
        self.hw.profile['max_jobs'] = 5
        self.assertEqual(s.reserve('SDJ-C', 'A1', {'vram_gb': 10})['reason'], 'vram_insufficient')
        self.assertEqual({g['device_id']: g['free_gb'] for g in s.reserve('SDJ-D', 'A1', {'vram_gb': 99})['headroom']['gpus']}, {'GPU-0': 5.0, 'GPU-1': 3.0})

    def test_one_job_never_counts_twice(self):
        s = self.scheduler(); s.reserve('SDJ-A', 'A1', {'vram_gb': 9}); s.reserve('SDJ-A', 'A2', {'vram_gb': 9})
        self.assertEqual([(r['job_id'], r['attempt_id']) for r in s.reservations()], [('SDJ-A', 'A2')])

    def test_release_and_reconcile_follow_state_not_time(self):
        s = self.scheduler()
        for job in ('SDJ-A', 'SDJ-B'): s.reserve(job, 'A1', {'ram_gb': 1})
        self.assertEqual(s.release_job('SDJ-A'), 1); self.assertEqual(s.release_job('SDJ-A'), 0)
        self.assertEqual(s.reconcile(['SDJ-B']), []); self.assertEqual(s.reconcile([]), ['SDJ-B'])
        self.assertEqual(s.reservations(), [])
        s.reserve('SDJ-C', 'A1', {'ram_gb': 1})
        self.clock_now += timedelta(days=30)                                                     # a month passes (or the clock jumps): nothing expires by itself
        self.assertEqual([r['job_id'] for r in s.reservations()], ['SDJ-C'])
        self.clock_now -= timedelta(days=60)
        self.assertEqual(s.reconcile(['SDJ-C']), [])

    def test_the_ledger_survives_a_restart(self):
        self.scheduler().reserve('SDJ-A', 'A1', {'ram_gb': 5, 'vram_gb': 8})
        again = self.scheduler()
        self.assertEqual([(r['job_id'], r['vram_gb']) for r in again.reservations()], [('SDJ-A', 8.0)])
        self.hw.state = sample(gpus=((16.0, 8.0),))
        self.assertEqual(again.reserve('SDJ-B', 'A1', {'vram_gb': 8})['reason'], 'vram_insufficient')

    def test_an_unreadable_ledger_promises_nothing_and_is_not_overwritten(self):
        (self.root / 'ledger.json').write_text('{broken', encoding='utf-8')
        s = self.scheduler()
        out = s.reserve('SDJ-A', 'A1', {'ram_gb': 1})
        self.assertEqual((out['status'], out['reason']), ('DENIED', 'resource_ledger_unreadable'))
        self.assertEqual((self.root / 'ledger.json').read_text(encoding='utf-8'), '{broken')
        self.assertEqual(s.explain({'ram_gb': 1}), 'resource_ledger_unreadable')
        with self.assertRaises(RuntimeError): s.release_job('SDJ-A')                              # the supervisor catches this and audits it
        self.assertIn('error', s.view())

    def test_no_picture_of_the_host_means_no_promise(self):
        s = self.scheduler(); self.hw.fail = True
        out = s.reserve('SDJ-A', 'A1', {'ram_gb': 1})
        self.assertEqual((out['status'], out['reason']), ('DENIED', 'hardware_state_unavailable'))
        self.assertEqual(s.explain({'ram_gb': 1}), 'hardware_state_unavailable')
        self.assertEqual(s.reservations(), [])

    def test_profile_bound_to_other_hardware_is_named_not_called_memory(self):
        s = self.scheduler(); self.hw.fail = 'active_profile_hardware_changed'
        out = s.reserve('SDJ-A', 'A1', {'ram_gb': 1})
        self.assertEqual((out['status'], out['reason']), ('DENIED', 'hardware_profile_changed'))
        self.assertEqual(s.explain({'ram_gb': 1}), 'hardware_profile_changed')
        err = ResolutionError('hardware_pressure', {'considered': [{'reason': 'hardware_profile_changed'}]})
        self.assertEqual((err.code, str(err)), ('hardware_pressure', 'hardware_pressure:hardware_profile_changed'))
        self.assertEqual(str(ResolutionError('hardware_pressure', {'considered': [{'reason': 'vram_insufficient'}]})), 'hardware_pressure')

    def test_explain_is_advisory_and_reserves_nothing(self):
        s = self.scheduler()
        self.assertIsNone(s.explain({'ram_gb': 4, 'vram_gb': 4}))
        self.assertEqual(s.explain({'vram_gb': 40}), 'vram_insufficient')
        self.assertEqual(s.explain({'ram_gb': 1}, exclusive=True), None)
        self.assertEqual(s.reservations(), [])
        s.reserve('SDJ-A', 'A1', {'ram_gb': 1})
        self.assertEqual(s.explain({'ram_gb': 1}, exclusive=True), 'exclusive_conflict')

    def test_concurrent_requests_cannot_overbook(self):
        self.hw.profile['max_jobs'] = 10; s = self.scheduler(vram_reserve_gb=1.0)
        results = []
        threads = [threading.Thread(target=lambda n=n: results.append(s.reserve(f'SDJ-{n}', 'A1', {'vram_gb': 7})['status'])) for n in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(results.count('GRANTED'), 2)                                            # 15 usable GB hold two 7 GB jobs, not three
        self.assertEqual(sum(r['vram_gb'] for r in s.reservations()), 14.0)

    def test_concurrent_processes_cannot_overbook_either(self):
        code = ("import sys, json\nsys.path.insert(0, sys.argv[1])\nfrom pathlib import Path\nfrom guppi_runtime.jobs.resource_scheduler import *\n"
                "hw = type('H', (), {'get_state': lambda self, fresh=False: json.loads(sys.argv[3]), 'active_profile': lambda self: {'ram_reserve_gib': 2, 'max_jobs': 10}})()\n"
                "s = ResourceScheduler(ResourceConfig({'enabled': True, 'vram_reserve_gb': 1.0}), hw, Path(sys.argv[2]))\n"
                "print(s.reserve('SDJ-P' + sys.argv[4], 'A1', {'vram_gb': 7})['status'])\n")
        state = json.dumps(sample())
        procs = [subprocess.Popen([sys.executable, '-c', code, SRC, str(self.root / 'ledger.json'), state, str(n)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for n in range(5)]
        outs = []
        for p in procs:
            out, err = p.communicate(timeout=120); self.assertEqual(p.returncode, 0, err); outs.append(out.strip())
        self.assertEqual(outs.count('GRANTED'), 2, outs)

    def test_audit_trail_and_no_secrets(self):
        s = self.scheduler(); s.reserve('SDJ-A', 'A1', {'ram_gb': 1}); s.reserve('SDJ-B', 'A1', {'vram_gb': 99}); s.release_job('SDJ-A'); s.release_job('SDJ-A')
        self.assertEqual([t for t in self.types() if t.startswith('RESOURCE')], ['RESOURCE_RESERVED', 'RESOURCE_DENIED', 'RESOURCE_RELEASED'])   # the second release is silent
        self.assertTrue(self.audit.verify_chain())

    def test_a_refusal_is_audited_with_its_numbers(self):
        # Spec 2 (SCH-03, G2-S2-08): RESOURCE_DENIED carries need and free memory, not only the reason
        s = self.scheduler()
        self.hw.state = sample(gpus=((16.0, 9.0),))
        out = s.reserve('SDJ-B', 'A1', {'vram_gb': 12})
        self.assertEqual(out['detail'], {'need_gb': 12.0, 'best_free_gb': 8.0, 'measured_free_gb': 9.0})
        s.audit_denied('server:main', 'vram_insufficient', need_gb=11.0, measured_free_gb=None, limit_gb=11.5)
        denied = [json.loads(x) for x in (self.root / 'audit.jsonl').read_text(encoding='utf-8').splitlines() if '"RESOURCE_DENIED"' in x]
        self.assertEqual([{k: d['payload'].get(k) for k in ('job_id', 'reason', 'need_gb', 'best_free_gb', 'measured_free_gb', 'limit_gb')} for d in denied],
                         [{'job_id': 'SDJ-B', 'reason': 'vram_insufficient', 'need_gb': 12.0, 'best_free_gb': 8.0, 'measured_free_gb': 9.0, 'limit_gb': None},
                          {'job_id': 'server:main', 'reason': 'vram_insufficient', 'need_gb': 11.0, 'best_free_gb': None, 'measured_free_gb': None, 'limit_gb': 11.5}])
        self.assertEqual(s.measured_free_vram_gb(), 9.0)
        self.hw.fail = True
        self.assertIsNone(s.measured_free_vram_gb())
        off = ResourceScheduler(ResourceConfig(dict(raw_config(), enabled=False)), self.hw, self.root / 'x.json')
        self.assertIsNone(off.measured_free_vram_gb())

    def test_view_reports_ledger_and_headroom(self):
        s = self.scheduler(); s.reserve('SDJ-A', 'A1', {'ram_gb': 10, 'vram_gb': 5})
        view = s.view()
        self.assertEqual((view['enabled'], len(view['reservations'])), (True, 1))
        self.assertEqual(view['headroom']['gpus'][0]['free_gb'], 10.0)                           # 16 - 1 reserve - 5 promised
        self.hw.fail = True
        self.assertIn('error', s.view())                                                         # a status view never raises

    def test_source_is_read_only_towards_the_machine(self):
        source = Path(importlib.import_module('guppi_runtime.jobs.resource_scheduler').__file__).read_text(encoding='utf-8')
        for forbidden in ('subprocess', 'apply_profile', 'save_profile', 'constrain_runtime_profile', 'os.system', 'unload', 'kill'):
            self.assertNotIn(forbidden, source)
        for word in ('lm-studio', 'llama', 'qwen', 'kev', 'openai', 'anthropic'):
            self.assertNotRegex(source.lower(), rf'\b{word}\b', word)


def recipe(cid, provider, size, vram, kv_rate=None, **kw):
    base = {'id': cid, 'version': 1, 'roles': ['coder'], 'provider': provider, 'model': None, 'model_family': provider, 'weights_id': f'{provider}-w',
            'location': 'local', 'requirements': {'min_ram_gb': 4, 'min_vram_gb': vram}, 'model_size_gb': size,
            'profile': {'context': {'recommended': 8192, 'maximum': 32768}, 'gpu_layers': 99 if vram else 0}, 'permissions': {'max_level': 2},
            'network': {'allowed': False}, 'tests': [], 'rollback': {'supported': True}, 'metadata': {'source': 'builtin', 'trust_level': 'BUILT_IN'}}
    if kv_rate is not None: base['kv_cache_gb_per_1k_tokens'] = kv_rate
    base.update(kw); return base


def routing_config(recipes):
    return RoutingConfig({'enabled': True, 'policy': {'allowed_trust_levels': ['BUILT_IN']}, 'capabilities': recipes,
                          'provider_health': {'degraded_after': 2, 'cooldown_after': 3, 'base_cooldown_s': 30, 'max_cooldown_s': 600}})


HOST = SimpleNamespace(hardware_class='nvidia_16plus', cpu_threads=16, gpu_vendor='NVIDIA', ram_gb=64, vram_gb=16)


class RoutingIntegrationTests(Base):
    def test_kv_cache_is_estimated_from_a_declared_rate_never_guessed(self):
        router = RoleRouter(routing_config([recipe('c.a', 'p1', 8.0, 8, kv_rate=0.5), recipe('c.b', 'p2', 8.0, 8)]), snapshot=HOST)
        known = router.resolve_role('coder', exclude=['p2'])['estimated_resources']
        self.assertEqual((known['kv_cache_gb'], known['kv_cache_placement'], known['complete']), (4.096, 'gpu', True))   # 0.5 GB per 1k tokens at a working context of 8192
        unknown = router.resolve_role('coder', exclude=['p1'])['estimated_resources']
        self.assertEqual((unknown['kv_cache_gb'], unknown['complete']), (None, False))
        cpu = recipe('c.c', 'p3', 4.0, 0, kv_rate=0.25, profile={'context': {'recommended': 4096, 'maximum': 8192}, 'gpu_layers': 0, 'kv_cache': {'placement': 'cpu'}})
        self.assertEqual(RoleRouter(routing_config([cpu]), snapshot=HOST).resolve_role('coder')['estimated_resources']['kv_cache_placement'], 'cpu')
        self.assertEqual(RoutingConfig.__name__, 'RoutingConfig')
        with self.assertRaises(ValueError): routing_config([recipe('c.d', 'p4', 4.0, 0, kv_rate=-1)])

    def test_a_job_that_does_not_fit_makes_the_router_choose_the_smaller_model(self):
        self.hw.state = sample(gpus=((16.0, 9.0),))                                              # another process holds 7 GB
        scheduler = self.scheduler(vram_reserve_gb=1.0)
        router = RoleRouter(routing_config([recipe('c.big', 'big', 14.0, 12, kv_rate=0.25), recipe('c.small', 'small', 4.0, 5, kv_rate=0.1)]), snapshot=HOST,
                            load_check=lambda r, est, req: scheduler.explain(est, exclusive=req['exclusive']))
        res = router.resolve_role('coder')
        self.assertEqual(res['capability_id'], 'c.small')
        self.assertEqual([(c['capability_id'], c['category']) for c in res['considered']], [('c.big', 'pressure')])
        self.hw.state = sample(gpus=((16.0, 2.0),))
        with self.assertRaises(ResolutionError) as ctx: router.resolve_role('coder')
        self.assertEqual(ctx.exception.code, 'hardware_pressure')

    def test_gpu_resident_weights_are_counted_in_vram_and_cpu_resident_ones_in_ram(self):
        on_gpu = recipe('c.gpu', 'p1', 6.0, 0, profile={'context': {'recommended': 8192, 'maximum': 32768}, 'gpu_layers': 99})
        gpu = RoleRouter(routing_config([on_gpu]), snapshot=HOST).resolve_role('coder')['estimated_resources']
        self.assertEqual((gpu['vram_gb'], gpu['ram_gb']), (6.3, 4))                              # weights in VRAM; RAM is the declared minimum
        cpu = recipe('c.cpu', 'p2', 6.0, 0, profile={'context': {'recommended': 4096, 'maximum': 8192}, 'gpu_layers': 0})
        cpu_est = RoleRouter(routing_config([cpu]), snapshot=HOST).resolve_role('coder')['estimated_resources']
        self.assertEqual((cpu_est['vram_gb'], cpu_est['ram_gb']), (0, 7.2))                      # weights in RAM, 20 % overhead
        floor = RoleRouter(routing_config([recipe('c.floor', 'p3', 2.0, 8)]), snapshot=HOST).resolve_role('coder')['estimated_resources']
        self.assertEqual(floor['vram_gb'], 8)                                                    # a declared minimum is never lowered by the estimate
        unknown_size = recipe('c.nosize', 'p4', None, 0)
        self.assertEqual(RoleRouter(routing_config([unknown_size]), snapshot=HOST).resolve_role('coder')['estimated_resources']['vram_gb'], 0)

    def test_exclusive_requirement_reaches_the_scheduler(self):
        scheduler = self.scheduler(); scheduler.reserve('SDJ-A', 'A1', {'ram_gb': 1})
        router = RoleRouter(routing_config([recipe('c.a', 'p1', 4.0, 0)]), snapshot=HOST,
                            load_check=lambda r, est, req: scheduler.explain(est, exclusive=req['exclusive']))
        self.assertEqual(router.resolve_role('coder')['capability_id'], 'c.a')
        with self.assertRaises(ResolutionError) as ctx: router.resolve_role('coder', {'exclusive': True})
        self.assertEqual(ctx.exception.code, 'hardware_pressure')


class SupervisorBase(Base):
    def setUp(self):
        super().setUp()
        self.clock = SimpleNamespace(wall=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc), mono=1000.0)
        raw = yaml.safe_load(SUPERVISOR.read_text(encoding='utf-8'))['job_supervisor']; raw['enabled'] = True
        self.scheduler_ = self.scheduler(vram_reserve_gb=1.0)
        self.router = RoleRouter(routing_config([recipe('c.a', 'pa', 6.0, 6, kv_rate=0.25)]), snapshot=HOST,
                                 health=ProviderHealth(routing_config([]), None, clock=lambda: self.clock.wall))
        self.sup = JobSupervisor(SupervisorJobStore(self.root / 'jobs', self.audit), SupervisorConfig(raw), audit=self.audit,
                                 clock=lambda: self.clock.wall, monotonic=lambda: self.clock.mono, pass_gate=lambda j, v: [],
                                 resolver=lambda role, req, exclude, independent_of: self.router.resolve_role(role, req, exclude=exclude, independent_of=independent_of),
                                 scheduler=self.scheduler_)

    def advance(self, s): self.clock.wall += timedelta(seconds=s); self.clock.mono += s

    def create(self, **kw):
        contract = development_contract(objective='probe', classification='E1', acceptance_criteria=[{'type': 'capability_smoke_test', 'id': 's'}],
                                        verification_plan=[{'type': 'deterministic_tests'}])
        job = self.sup.create_job(contract, requested_role='coder', **kw); self.sup.enqueue(job['job_id'])
        return job['job_id']

    def start(self, worker='w1', **kw):
        job_id = self.create(**kw); self.sup.claim(worker, ['coder'])
        return job_id, self.sup.confirm_start(job_id, worker)

    def load(self, job_id): return self.sup.store.load(job_id)
    def held(self): return [r['job_id'] for r in self.scheduler_.reservations()]


class SupervisorLifecycleTests(SupervisorBase):
    def test_start_reserves_and_the_attempt_remembers_which_reservation(self):
        job_id, out = self.start()
        self.assertEqual(out['status'], 'running')
        reservation = self.scheduler_.reservations()[0]
        self.assertEqual((reservation['job_id'], reservation['attempt_id'], reservation['vram_gb'], reservation['kv_cache_gb']), (job_id, out['attempt_id'], 8.348, 2.048))     # GPU-resident weights 6 GB * 1.05 = 6.3, plus 0.25 GB per 1k tokens * 8192 of KV cache
        self.assertEqual(self.load(job_id)['attempt_log'][0]['reservation_id'], reservation['reservation_id'])

    def test_heartbeats_and_steps_leave_the_ledger_alone(self):
        job_id, _ = self.start(); before = self.scheduler_.reservations()
        for _ in range(3): self.sup.heartbeat(job_id, 'w1')
        self.sup.complete_step(job_id, 'w1', 'TESTING'); self.sup.complete_step(job_id, 'w1', 'VERIFYING')
        self.assertEqual(self.scheduler_.reservations(), before)

    def test_every_way_an_attempt_can_end_gives_the_room_back(self):
        def failed(s, j): s.sup.fail(j, 'w1', reason_code='TOOL_UNAVAILABLE')
        def passed(s, j): s.sup.complete_step(j, 'w1', 'TESTING'); s.sup.complete_step(j, 'w1', 'VERIFYING'); s.sup.mark_passed(j, 'w1', {'result': 'PASS', 'verification_digest': 'd' * 64})
        def cancelled(s, j): s.sup.cancel(j, requested_by='t', reason='r'); s.sup.acknowledge_cancel(j, 'w1')
        def lost(s, j): s.sup.reap(); s.advance(s.sup.config.lease_s + s.sup.config.suspect_after_s + 1); s.sup.reap(); s.advance(s.sup.config.grace_s + 1); s.sup.reap()
        for name, end in (('fail', failed), ('pass', passed), ('cancel', cancelled), ('lost worker', lost)):
            with self.subTest(end=name):
                self.setUp(); job_id, _ = self.start(); self.assertEqual(self.held(), [job_id])
                end(self, job_id)
                self.assertEqual(self.held(), [], name)

    def test_a_parked_job_holds_no_hardware(self):
        from guppi_runtime.core.permission_levels import PermissionConfig, PermissionGate
        rt = GuppiRuntime(self.root / 'rt', ARCH)
        self.sup.permissions = rt.permission_gate; self.sup.guard = rt.guard
        self.router.config.recipes[0]['max_level'] = 3                                           # the recipe must allow a level-3 job to start at all
        contract = development_contract(objective='probe', classification='E1', permission_level=3, acceptance_criteria=[{'type': 'x', 'id': 's'}], verification_plan=[{'type': 'd'}])
        job = self.sup.create_job(contract, requested_role='coder'); self.sup.enqueue(job['job_id']); self.sup.claim('w1', ['coder']); self.sup.confirm_start(job['job_id'], 'w1')
        self.assertEqual(self.held(), [job['job_id']])
        self.sup.request_approval(job['job_id'], 'w1', 'sandbox_execute', 'sandbox:run-1')
        self.assertEqual(self.held(), [])

    def test_a_crash_leaves_no_reservation_behind(self):
        job_id, _ = self.start()
        self.scheduler_.reserve('SDJ-GHOST', 'A1', {'ram_gb': 1})                                # a reservation no job record knows about
        restarted = JobSupervisor(SupervisorJobStore(self.root / 'jobs', self.audit), self.sup.config, audit=self.audit, clock=lambda: self.clock.wall,
                                  monotonic=lambda: self.clock.mono, scheduler=self.scheduler_)
        restarted.startup_recovery()
        self.assertEqual(self.held(), [])

    def test_the_reaper_drops_orphans_but_never_the_room_of_a_live_job(self):
        job_id, _ = self.start()
        self.scheduler_.reserve('SDJ-GHOST', 'A1', {'ram_gb': 1})
        self.sup.reap()
        self.assertEqual(self.held(), [job_id])
        self.clock.wall += timedelta(days=3)                                                     # the wall clock leaps three days (no real time passes); the worker still beats
        self.sup.heartbeat(job_id, 'w1'); self.sup.reap()
        self.assertEqual(self.held(), [job_id])

    def test_a_failed_start_releases_what_it_promised(self):
        job_id = self.create(); self.sup.claim('w1', ['coder'])
        self.advance(self.sup.config.claim_timeout_s + 1)
        with self.assertRaises(JobError) as ctx: self.sup.confirm_start(job_id, 'w1')
        self.assertEqual(ctx.exception.code, 'claim_expired')
        self.assertEqual(self.held(), [])
        with self.assertRaises(JobError): self.sup.confirm_start(job_id, 'intruder')
        self.assertEqual(self.held(), [])

    def test_a_refusal_means_not_now_and_the_job_comes_back_when_room_exists(self):
        self.hw.state = sample(gpus=((16.0, 3.0),))
        job_id, out = self.start()
        stored = self.load(job_id)
        self.assertEqual((out['status'], out['code']), ('resolution_failed', 'hardware_pressure'))
        self.assertEqual((stored['state'], stored['supervisor_flags']['escalated_to'], stored['retry']['count']), ('QUEUED', None, 1))   # queued again with a wait, not escalated
        self.assertEqual((stored['attempt_log'][0]['outcome'], stored['attempt_log'][0]['failure_class']), ('FAILED', 'hardware_pressure'))
        self.assertIn('vram_insufficient', stored['last_error']['message'])
        self.assertEqual(self.held(), [])
        self.assertEqual(stored['retry']['exclude'], [])                                         # the provider is not to blame
        with self.assertRaises(JobError) as ctx: self.sup.claim('w1', ['coder'])
        self.assertEqual(ctx.exception.code, 'no_job')                                           # still waiting out its backoff
        self.hw.state = sample(); self.advance(300)
        self.sup.claim('w1', ['coder'])
        self.assertEqual(self.sup.confirm_start(job_id, 'w1')['status'], 'running')
        self.assertEqual(self.held(), [job_id])

    def test_repeated_refusals_end_in_escalation_not_in_a_loop(self):
        self.hw.state = sample(thermal='HOT')
        job_id, out = self.start()
        for _ in range(self.sup.config.retry_limit):
            self.advance(300); self.sup.claim('w1', ['coder']); out = self.sup.confirm_start(job_id, 'w1')
        stored = self.load(job_id)
        self.assertEqual((stored['state'], stored['supervisor_flags']['escalated_to']), ('BLOCKED', 'guppi'))
        self.assertEqual(stored['last_error']['reason_code'], 'hardware_pressure')

    def test_exclusive_jobs_wait_for_a_free_machine(self):
        first, _ = self.start()
        self.sup._worker_limit = lambda: 2                                                        # let a second worker try (only the model scheduler allows that since Spec 2); the ledger is what refuses
        second = self.create(requirements={'exclusive': True}); self.sup.claim('w2', ['coder'])
        out = self.sup.confirm_start(second, 'w2')
        self.assertEqual((out['status'], out['code']), ('resolution_failed', 'hardware_pressure'))
        self.assertEqual(self.held(), [first])

    def test_no_scheduler_or_a_disabled_one_changes_nothing(self):
        for make in (lambda: None, lambda: ResourceScheduler(ResourceConfig(dict(raw_config(), enabled=False)), self.hw, self.root / 'x.json')):
            self.setUp()
            self.sup.scheduler = make()
            job_id, out = self.start()
            self.assertEqual(out['status'], 'running')
            self.assertIsNone(self.load(job_id)['attempt_log'][0]['reservation_id'])
        self.assertFalse((self.root / 'x.json').exists())

    def test_a_broken_ledger_cannot_wedge_a_job_that_is_ending(self):
        job_id, _ = self.start()
        (self.root / 'ledger.json').write_text('{broken', encoding='utf-8')
        self.sup.fail(job_id, 'w1', reason_code='TOOL_UNAVAILABLE')                              # releasing raises inside the scheduler; the job still ends
        self.assertEqual(self.load(job_id)['attempt_log'][0]['outcome'], 'FAILED')
        self.assertIn('JOB_RESOURCE_RELEASE_FAILED', self.types())

    def test_the_whole_story_with_two_jobs_and_one_card(self):
        self.hw.profile['max_jobs'] = 4
        first, _ = self.start()                                                                  # 8 GB of a 16 GB card (1 GB reserve): room for one more 8 GB job? 15 - 8 = 7 < 8
        self.hw.state = sample(gpus=((16.0, 8.0),))
        self.sup._worker_limit = lambda: 2                                                        # a second worker, as with the model scheduler on
        second = self.create(); self.sup.claim('w2', ['coder'])
        self.assertEqual(self.sup.confirm_start(second, 'w2')['status'], 'resolution_failed')
        self.advance(1)                                                                          # so the failed job queues up behind the waiting one (no tie on the enqueue time)
        self.sup.fail(first, 'w1', reason_code='TOOL_UNAVAILABLE')                              # the first job ends, its room is free
        self.hw.state = sample(); self.advance(300)
        self.sup.claim('w2', ['coder'])
        self.assertEqual(self.sup.confirm_start(second, 'w2')['status'], 'running')
        self.assertEqual(self.held(), [second])
        self.assertTrue(self.audit.verify_chain())


class RuntimeWiringTests(unittest.TestCase):
    def test_runtime_wires_the_scheduler_off_and_reports_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
            self.assertFalse(rt.resource_scheduler.enabled)
            self.assertIs(rt.job_supervisor.scheduler, rt.resource_scheduler)
            self.assertIsNone(rt.role_router.load_check)
            status = rt.boot()['resources']
            self.assertFalse(status['enabled']); self.assertEqual(status['reservations'], [])
            self.assertFalse((Path(tmp) / 'project' / 'runtime_data' / 'resource_reservations.json').exists())

    def test_enabled_scheduler_feeds_the_router_and_keeps_the_ledger_in_runtime_data(self):
        import guppi_runtime.runtime as runtime_module
        real = runtime_module.ResourceConfig.load

        def enabled(path):
            config = real(path); config.enabled = True; return config

        runtime_module.ResourceConfig.load = staticmethod(enabled)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
                self.assertTrue(rt.resource_scheduler.enabled)
                self.assertIsNotNone(rt.role_router.load_check)
                self.assertEqual(rt.resource_scheduler.path, rt.project_root / 'runtime_data' / 'resource_reservations.json')
                self.assertIn('enabled', rt.resource_status())
        finally:
            runtime_module.ResourceConfig.load = real

    def test_a_broken_resource_file_leaves_no_scheduler_and_says_why(self):
        import guppi_runtime.runtime as runtime_module
        real = runtime_module.ResourceConfig.load
        runtime_module.ResourceConfig.load = staticmethod(lambda path: (_ for _ in ()).throw(ValueError('resource_config_invalid:test')))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
        finally:
            runtime_module.ResourceConfig.load = real
        self.assertIsNone(rt.resource_scheduler); self.assertIsNone(rt.job_supervisor.scheduler)
        self.assertEqual(rt.resource_status(), {'enabled': False, 'error': 'resource_config_invalid:test'})


if __name__ == '__main__':
    unittest.main()
