from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from guppi_runtime.hardware_manager.collector import NativeCollector, metric
from guppi_runtime.hardware_manager.manager import HardwareManager, digest
from guppi_runtime.hardware_manager.power import SCHEMES
from guppi_runtime.hardware_manager.dashboard import make_server
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.tools.hardware_manager import HardwareManagerTool
from guppi_runtime.tools.base import ToolValidationError
from guppi_runtime.util import atomic_write_json, utcnow
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('GUPPI_Architecture_v*'))[-1]


class FakeCollector:
    def __init__(self):
        self.temperature = 40; self.ram = 12; self.age = 0; self.fingerprint = 'fake-PC'
    def inventory(self):
        return {'fingerprint': self.fingerprint, 'gigabyte': {'write_supported': False,
                'profile_automation': 'not_verified', 'installed_products': ['GCC']}}
    def sample(self):
        reading = metric(self.temperature, '°C', 'fixture')
        reading['timestamp'] = (datetime.now(timezone.utc) - timedelta(seconds=self.age)).isoformat()
        return {'timestamp': utcnow(), 'cpu_utilization': metric(25, '%', 'fixture'),
                'memory': {'available': metric(self.ram, 'GiB', 'fixture')}, 'gpus': [],
                'sensors': [{'sensor_id': 'gpu-core', 'name': 'GPU', 'type': 'Temperature', 'reading': reading}],
                'disks': [], 'provider_status': {'gpu': 'fixture', 'sensors': None}}


class FakePower:
    def __init__(self): self.guid = '00000000-0000-0000-0000-000000000001'; self.calls = []; self.fail = False
    def current(self): return self.guid
    def capabilities(self):
        return {'read_supported': True, 'write_supported': True, 'profiles': list(SCHEMES),
                'validation_status': 'fixture'}
    def set_guid(self, guid):
        self.calls.append(guid)
        if self.fail and guid in SCHEMES.values(): raise RuntimeError('fixture_readback_failed')
        self.guid = guid


class HardwareCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.rt = GuppiRuntime(self.root, ARCH)
        self.collector = FakeCollector(); self.power = FakePower()
        self.manager = HardwareManager(self.root/'hardware', self.rt.audit, self.collector, self.power)
        self.tool = HardwareManagerTool(self.root/'tool', self.manager, self.rt.guard, self.rt.audit)
    def tearDown(self): self.tmp.cleanup()

    def custom(self, **kw):
        return dict(label='Captain test', ram_reserve_gib=2, max_jobs=1, cpu_thread_cap=2,
                    power_plan=None, thermal_limits=[], vendor_profile_reference='GCC: meine Kurve',
                    hardware_fingerprint='fake-PC', **kw)

    def save(self, profile=None, profile_id='custom-test'):
        p = self.manager.save_preview(profile_id, profile or self.custom())
        pending = self.tool.execute('M-HW', 'save_profile', {'plan': p})
        token = self.rt.guard.approve(pending['gate'])
        return self.tool.execute('M-HW', 'save_profile', {'plan': p}, token)

    def apply(self, profile_id='custom-test'):
        p = self.manager.preview_profile(profile_id)
        pending = self.tool.execute('M-HW', 'apply_profile', {'plan': p})
        token = self.rt.guard.approve(pending['gate'])
        return self.tool.execute('M-HW', 'apply_profile', {'plan': p}, token)

    def test_registry_and_boot_integration(self):
        self.assertIn('hardware-manager', self.rt.tools.list())
        self.assertIn('hardware_manager', self.rt.boot())
        self.assertFalse(self.rt.hardware_manager.capabilities()['fan_control']['write_supported'])

    def test_read_only_and_preview_do_not_write_or_set_power(self):
        for op in ['get_inventory', 'get_state', 'get_capabilities', 'profiles', 'get_history']:
            self.assertEqual(self.tool.execute('M', op)['status'], 'completed')
        first = self.manager.preview_profile('quiet')
        self.assertEqual(first, self.manager.preview_profile('quiet'))
        self.assertEqual(self.power.calls, [])
        self.assertFalse(self.manager.root.exists())

    def test_save_exact_gate_hardware_binding_and_persistence(self):
        plan = self.manager.save_preview('custom-test', self.custom())
        pending = self.tool.execute('M-HW', 'save_profile', {'plan': plan})
        self.assertEqual(pending['status'], 'captain_required')
        token = self.rt.guard.approve(pending['gate'])
        self.assertEqual(self.tool.execute('OTHER', 'save_profile', {'plan': plan}, token)['status'], 'captain_required')
        self.assertEqual(self.tool.execute('M-HW', 'save_profile', {'plan': plan}, token)['status'], 'completed')
        new = HardwareManager(self.manager.root, collector=self.collector, power=self.power)
        self.assertEqual(new.profiles()['custom-test']['vendor_profile_reference'], 'GCC: meine Kurve')
        self.collector.fingerprint = 'different-PC'
        with self.assertRaises(ValueError): new.profiles()

    def test_invalid_profiles_and_no_arbitrary_commands(self):
        for field, value in [('max_jobs', True), ('ram_reserve_gib', float('nan')),
                             ('cpu_thread_cap', -1), ('power_plan', 'custom_shell'),
                             ('hardware_fingerprint', 'other-PC'), ('command', 'evil')]:
            p = self.custom(); p[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.manager.save_preview('custom-test', p)
        with self.assertRaises(ValueError): self.manager.save_preview('../escape', self.custom())

    def test_tampered_plan_rejected_and_no_effect(self):
        self.save(); plan = self.manager.preview_profile('custom-test')
        bad = deepcopy(plan); bad['profile']['max_jobs'] = 4
        bad['plan_digest'] = digest({k:v for k,v in bad.items() if k != 'plan_digest'})
        with self.assertRaises(ToolValidationError): self.tool.execute('M', 'apply_profile', {'plan':bad})
        self.assertEqual(self.manager.state_record()['profile_id'], 'auto')

    def test_apply_single_use_gate_and_restore(self):
        self.save(); plan = self.manager.preview_profile('custom-test')
        pending = self.tool.execute('M', 'apply_profile', {'plan':plan})
        token = self.rt.guard.approve(pending['gate'])
        other = self.manager.preview_profile('quiet')
        self.assertEqual(self.tool.execute('M', 'apply_profile', {'plan':other}, token)['status'], 'captain_required')
        self.assertEqual(self.tool.execute('M', 'apply_profile', {'plan':plan}, token)['status'], 'completed')
        restore = self.manager.restore_preview()
        pending = self.tool.execute('M', 'restore_defaults', {'plan':restore}, token)
        self.assertEqual(pending['status'], 'captain_required')
        token2 = self.rt.guard.approve(pending['gate'])
        self.assertEqual(self.tool.execute('M', 'restore_defaults', {'plan':restore}, token2)['status'], 'completed')
        self.assertEqual(self.manager.state_record()['profile_id'], 'auto')
        self.assertEqual(self.tool.execute('M', 'apply_profile', {'plan':plan}, token)['status'], 'captain_required')
        self.assertTrue(self.rt.audit.verify_chain())

    def test_power_plan_readback_rollback_and_external_conflict(self):
        p = self.custom(); p['power_plan'] = 'power_saver'; self.save(p)
        original = self.power.guid
        self.assertEqual(self.apply()['status'], 'completed')
        self.assertEqual(self.power.guid, SCHEMES['power_saver'])
        self.power.guid = '00000000-0000-0000-0000-000000000009'
        plan = self.manager.restore_preview()
        with self.assertRaises(RuntimeError): self.manager.restore(plan)
        self.assertNotIn(original, self.power.calls)
        self.power.guid = SCHEMES['power_saver']
        self.manager.restore(self.manager.restore_preview())
        self.assertEqual(self.power.guid, original)
        self.power.fail = True
        self.assertEqual(self.apply()['status'], 'failed')
        self.assertEqual(self.manager.state_record()['profile_id'], 'auto')

    def test_active_profile_cannot_be_changed_and_requires_restore(self):
        self.save(); self.apply()
        with self.assertRaises(ValueError): self.manager.save_preview('custom-test', self.custom())
        out = self.apply('quiet')
        self.assertEqual(out['status'], 'failed')
        self.assertIn('restore_active_profile', out['error'])

    def test_memory_and_concurrency_admission(self):
        self.save(); self.apply()
        self.collector.ram = 1
        with self.assertRaises(RuntimeError): self.manager.preflight()
        self.collector.ram = 8
        with self.manager.job():
            with self.assertRaises(RuntimeError):
                with self.manager.job(): pass
        self.assertEqual(self.manager.jobs, 0)
        with self.assertRaises(ValueError):
            with self.manager.job(): raise ValueError('job failure')
        self.assertEqual(self.manager.jobs, 0)

    def thermal_profile(self):
        p = self.custom(); p['thermal_limits'] = [dict(sensor_id='gpu-core', warm=60, hot=70, critical=80, hysteresis=5)]
        self.save(p); self.apply()

    def test_temperature_escalation_missing_stale_nan_and_recovery(self):
        self.thermal_profile()
        for temp, state in [(40,'NORMAL'), (65,'WARM'), (75,'HOT'), (85,'CRITICAL')]:
            self.collector.temperature=temp
            self.assertEqual(self.manager.get_state(fresh=True)['thermal_state'], state)
        self.collector.temperature = 40
        self.assertEqual(self.manager.get_state(fresh=True)['thermal_state'], 'RECOVERY')
        self.manager._cool_since -= 16
        self.assertEqual(self.manager.get_state(fresh=True)['thermal_state'], 'NORMAL')
        for temp, age in [(None,0), (float('nan'),0), (40,60)]:
            self.collector.temperature=temp; self.collector.age=age
            with self.subTest(temp=temp,age=age):
                self.assertEqual(self.manager.get_state(fresh=True)['thermal_state'], 'SENSOR_FAULT')
                with self.assertRaises(RuntimeError): self.manager.preflight()

    def test_no_thresholds_are_explicitly_unqualified(self):
        self.assertEqual(self.manager.get_state()['thermal_state'], 'UNQUALIFIED')
        self.assertFalse(self.manager.capabilities()['fan_control']['write_supported'])

    def test_runtime_parameters_only_reduced(self):
        self.save(); self.apply()
        profile = {'cpu_threads':8,'parallelism':4,'memory_reserve_gb':1}
        out = self.manager.constrain_runtime_profile(profile)
        self.assertEqual(out, {'cpu_threads':2,'parallelism':1,'memory_reserve_gb':2})
        self.assertEqual(profile['cpu_threads'],8)

    def test_model_router_admission_blocks_before_provider_chat(self):
        from guppi_runtime.models.router import ModelRouter
        from unittest.mock import Mock
        router=ModelRouter(); router.hardware_manager=self.manager
        adapter=Mock(); adapter.id='test'; adapter.health.return_value=True; router.register(adapter)
        self.thermal_profile(); self.collector.temperature=90
        with self.assertRaises(RuntimeError): router.chat('M',[],provider='test')
        adapter.chat.assert_not_called()

    def test_recording_bounded_persistent_and_history_copy(self):
        with patch('guppi_runtime.hardware_manager.manager.time.sleep'):
            run=self.manager.record_run(3,1)
        data=json.loads(Path(run['path']).read_text())
        self.assertEqual(data['status'],'completed'); self.assertEqual(len(data['samples']),3)
        history=self.manager.history(); history[0]['thermal_state']='tampered'
        self.assertNotEqual(self.manager.history()[0]['thermal_state'],'tampered')
        for count, interval in [(1000,1),(3,0),(True,2),(100,10),(3,float('nan'))]:
            with self.assertRaises(ValueError): self.manager.record_run(count,interval)

    def test_mutation_interlock_and_hardware_relocation(self):
        self.save(); self.apply()
        with self.manager.mutation():
            with self.assertRaises(RuntimeError): self.manager.restore(self.manager.restore_preview())
        self.collector.fingerprint='other-PC'
        with self.assertRaises(RuntimeError): self.manager.restore_preview()
        with self.assertRaises(RuntimeError): self.manager.preflight()

    def test_rebind_after_driver_update_keeps_limits_and_audits(self):
        self.thermal_profile()
        self.assertFalse(self.manager.rebind_preview()['needed'])
        self.collector.fingerprint='after-driver-update'
        with self.assertRaises(RuntimeError): self.manager.active_profile()
        plan=self.manager.rebind_preview()
        self.assertTrue(plan['needed']); self.assertEqual(plan['profiles_rebound'],['custom-test'])
        self.assertTrue(plan['active_state_rebound'])
        stale=dict(plan,hardware_fingerprint='other')
        with self.assertRaises(ValueError): self.manager.rebind(stale)
        out=self.manager.rebind(plan)
        self.assertEqual(out['hardware_fingerprint'],'after-driver-update')
        profile=self.manager.active_profile()
        self.assertEqual(profile['thermal_limits'][0]['hot'],70)            # limits untouched, only the binding moved
        self.assertFalse(self.manager.rebind_preview()['needed'])
        self.assertTrue(list(self.manager.root.glob('active.json.bak_*')))

    def test_native_metrics_nan_and_nvidia_multi_gpu_missing_fields(self):
        self.assertEqual(metric(float('nan'),'x','fixture')['state'],'unavailable')
        self.assertEqual(metric(0,'x','fixture')['state'],'valid')
        from types import SimpleNamespace
        output='GPU-a, One, 1.0, 55, 20, 8192, 4096, 30, 99\nGPU-b, Two, 1.0, [N/A], 0, 8192, 0, [N/A], [N/A]\n'
        with patch('guppi_runtime.hardware_manager.collector.shutil.which',return_value='nvidia-smi'), \
             patch('guppi_runtime.hardware_manager.collector.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=output)):
            gpus,reason=NativeCollector(self.root)._gpu()
        self.assertIsNone(reason);self.assertEqual(len(gpus),2)
        self.assertEqual(gpus[0]['vram_available']['value'],4)
        self.assertEqual(gpus[1]['temperature_core']['state'],'unavailable')
        self.assertEqual(gpus[1]['utilization']['value'],0)

    def test_native_sample_timestamps_do_not_hide_chart_values(self):
        collector=NativeCollector(self.root)
        with patch.object(collector,'_gpu',return_value=([],None)), patch.object(collector,'_sensors',return_value=([],None)):
            collector.sample();sample=collector.sample()
        end=datetime.fromisoformat(sample['timestamp'])
        for m in [sample['cpu_utilization'],*sample['memory'].values()]:
            self.assertLessEqual(datetime.fromisoformat(m['timestamp']),end)

    def test_windows_power_command_is_fixed_and_read_back(self):
        from guppi_runtime.hardware_manager.power import WindowsPowerAdapter
        from types import SimpleNamespace as NS
        guid=SCHEMES['balanced']
        with patch('guppi_runtime.hardware_manager.power.os.name','nt'), \
             patch('guppi_runtime.hardware_manager.power.windows_exe',return_value='C:/Windows/System32/powercfg.exe'), \
             patch('guppi_runtime.hardware_manager.power.subprocess.run',side_effect=[
                 NS(returncode=0,stdout='Power Scheme GUID: '+guid),NS(returncode=0,stdout=''),
                 NS(returncode=0,stdout='Power Scheme GUID: '+guid)]) as runner:
            WindowsPowerAdapter().set_guid(guid)
            self.assertEqual([x.args[0][1:] for x in runner.call_args_list], [['/list'],['/setactive',guid],['/getactivescheme']])
            self.assertTrue(all(x.kwargs['shell'] is False for x in runner.call_args_list))

    def test_windows_power_rejects_command_injection_without_subprocess(self):
        from guppi_runtime.hardware_manager.power import WindowsPowerAdapter
        with patch('guppi_runtime.hardware_manager.power.subprocess.run') as runner:
            with self.assertRaises(ValueError): WindowsPowerAdapter().set_guid('balanced & command')
            runner.assert_not_called()

    def test_warm_state_reduces_parallel_admission(self):
        p=self.custom();p['max_jobs']=4
        p['thermal_limits']=[dict(sensor_id='gpu-core',warm=60,hot=70,critical=80,hysteresis=5)]
        self.save(p);self.apply();self.collector.temperature=65
        with self.manager.job():
            with self.assertRaises(RuntimeError):
                with self.manager.job(): pass


class DashboardCase(unittest.TestCase):
    def test_loopback_auth_host_origin_no_mutation_and_html(self):
        with tempfile.TemporaryDirectory() as folder:
            manager=HardwareManager(Path(folder)/'hardware',collector=FakeCollector(),power=FakePower())
            server,url=make_server(manager)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            base,token=url.split('#')
            try:
                html=urlopen(base).read().decode()
                self.assertIn('Maschinenraum',html)
                req=Request(base+'api/state',headers={'X-GUPPI-Token':token})
                self.assertIn('history',json.loads(urlopen(req).read()))
                for headers in [{}, {'X-GUPPI-Token':'wrong'}, {'X-GUPPI-Token':token,'Host':'evil.example'},
                                {'X-GUPPI-Token':token,'Origin':'http://evil.example'}]:
                    with self.assertRaises(HTTPError) as err: urlopen(Request(base+'api/state',headers=headers))
                    self.assertEqual(err.exception.code,403)
                with self.assertRaises(HTTPError) as err: urlopen(Request(base+'api/state',data=b'{}',headers={'X-GUPPI-Token':token}))
                self.assertEqual(err.exception.code,501)
                self.assertEqual(manager.power.calls,[])
            finally: server.shutdown();server.server_close();worker.join()


if __name__ == '__main__': unittest.main()


class FreshSampleTest(unittest.TestCase):
    def test_fresh_reaches_collectors_that_accept_it_and_skips_the_slow_cache(self):
        from guppi_runtime.hardware_manager.collector import NativeCollector
        calls = []
        class Plain:
            def sample(self): calls.append('plain'); return {'memory': {}, 'gpus': [], 'sensors': []}
        class Fresh:
            def sample(self, fresh=False): calls.append(fresh); return {'memory': {}, 'gpus': [], 'sensors': []}
        with tempfile.TemporaryDirectory() as tmp:
            for collector in (Plain(), Fresh()):
                manager = HardwareManager(Path(tmp) / 'hw', collector=collector)
                manager.get_state(fresh=True)
            self.assertEqual(calls, ['plain', True])
            c = NativeCollector(Path(tmp)); gpu_calls = []
            c._gpu = lambda: (gpu_calls.append(1) or [], None); c._sensors = lambda: ([], None)
            c.sample(); c.sample(); self.assertEqual(len(gpu_calls), 1)       # cached
            c.sample(fresh=True); self.assertEqual(len(gpu_calls), 2)         # bypassed
