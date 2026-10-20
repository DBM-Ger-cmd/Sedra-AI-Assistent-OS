from __future__ import annotations
import json
import tempfile
import unittest
import sys
import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.core.mission import MissionStore
from guppi_runtime.core.audit import AuditLog
from guppi_runtime.core.guard import Guard
from guppi_runtime.core.message_bus import MessageBus, Message
from guppi_runtime.selfdev.evolution import EvolutionManager
from guppi_runtime.updater import UpdateBuilder
from guppi_runtime.core.errors import InvalidTransition, CompatibilityError
from guppi_runtime.knowledge import KnowledgeStore
from guppi_runtime.hardware import detect_hardware
from guppi_runtime.models.model_profiles import ModelProfileStore
from guppi_runtime.models.lmstudio import LMStudioAdapter
from guppi_runtime.models.base import ModelAdapterError
from guppi_runtime.models.router import ModelRouter
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('GUPPI_Architecture_v*'))[-1]

class RuntimeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.rt = GuppiRuntime(self.root, ARCH)
        # Own portable model folder: the runtime points at the package's real runtime/portable/models, which other GUPPI
        # processes on this PC scan. Test files (fake .gguf) must never appear there.
        models=self.root/'portable'/'models'; models.mkdir(parents=True)
        self.rt.model_runtime.portable_root=models.parent.resolve(); self.rt.model_runtime.catalog.allowed_roots=[models.resolve()]
    def tearDown(self):
        self.tmp.cleanup()

    def test_boot_ready(self):
        report = self.rt.boot()
        self.assertEqual(report['state'], 'READY')
        self.assertGreaterEqual(report['registry']['modules'], 5)

    def test_broken_supervisor_config_leaves_status_views_working(self):
        # Review 2026-10-11: an invalid job_supervisor.yaml returned early and left resource_scheduler, permission_gate and
        # model_loader unset, so boot() died with AttributeError instead of saying why.
        from guppi_runtime import runtime as runtime_module
        with patch.object(runtime_module.SupervisorConfig, 'load', side_effect=ValueError('job_supervisor_config_invalid')):
            rt = GuppiRuntime(self.root / 'broken', ARCH)
        self.assertEqual(rt.job_supervisor_error, 'job_supervisor_config_invalid')
        self.assertEqual(rt.resource_status(), {'enabled': False, 'error': None})
        self.assertEqual(rt.permission_status(), {'available': False, 'error': None})
        self.assertIsNone(rt.model_loader)

    def test_architecture_versions_sort_by_number(self):
        from guppi_runtime.runtime import _architecture_version
        names = ['GUPPI_Architecture_v1.20_SELF_DEVELOPMENT', 'GUPPI_Architecture_v1.9_OLD', 'GUPPI_Architecture_v1.17_RUNTIME_SYNC']
        self.assertEqual(sorted(names, key=_architecture_version)[-1], 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT')

    def test_new_artifact_that_appears_after_guard_check_is_not_overwritten(self):
        m = self.rt.brain.create_mission('Race')
        target = self.rt.control.workspace / m['identity']['mission_id'] / 'race.txt'
        evaluate = self.rt.guard.evaluate
        def evaluate_then_someone_writes(action, **kw):
            verdict = evaluate(action, **kw)
            target.parent.mkdir(parents=True, exist_ok=True); target.write_text('foreign', encoding='utf-8')
            return verdict
        with patch.object(self.rt.guard, 'evaluate', side_effect=evaluate_then_someone_writes):
            out = self.rt.control._create_text_artifact(m, {'target': 'race.txt', 'content': 'mine'})
        self.assertEqual(out['error'], 'target_appeared_after_guard_check')
        self.assertEqual(target.read_text(encoding='utf-8'), 'foreign')

    def test_full_mission_completes(self):
        m = self.rt.brain.create_mission('Create a test artifact')
        out = self.rt.brain.run(m['identity']['mission_id'])
        self.assertEqual(out['lifecycle']['phase'], 'COMPLETE')
        self.assertEqual(out['verification']['status'], 'PASS')
        self.assertEqual(len(out['execution']['artifacts']), 1)
        self.assertTrue(Path(out['execution']['artifacts'][0]['path']).exists())

    def test_captain_intent_immutable(self):
        m = self.rt.brain.create_mission('Original')
        with self.assertRaises(PermissionError):
            self.rt.missions.set_captain_intent(m, 'Changed')

    def test_invalid_transition(self):
        m = self.rt.brain.create_mission('X')
        with self.assertRaises(InvalidTransition):
            self.rt.missions.transition(m, 'COMPLETE')

    def test_audit_chain_and_redaction(self):
        a = AuditLog(self.root/'events.jsonl')
        a.append('X', payload={'token':'abc', 'nested':{'password':'pw'}})
        a.append('Y')
        self.assertTrue(a.verify_chain())
        txt = (self.root/'events.jsonl').read_text()
        self.assertNotIn('\"token\": \"abc\"', txt)
        self.assertNotIn('\"password\": \"pw\"', txt)
        self.assertIn('REDACTED', txt)

    def test_audit_redacts_keys_that_end_in_token_or_secret_but_not_usage_counters(self):
        a = AuditLog(self.root/'redact.jsonl')
        a.append('X', payload={'approval_token':'t1','client_secret':'s1','max_tokens':1024,'prompt_tokens':7,'token_id':'APR-1'})
        text = (self.root/'redact.jsonl').read_text()
        self.assertNotIn('t1"',text); self.assertNotIn('s1"',text)
        self.assertIn('"max_tokens": 1024',text); self.assertIn('"prompt_tokens": 7',text); self.assertIn('APR-1',text)

    def test_audit_repair_moves_a_torn_last_line_aside(self):
        path = self.root/'torn.jsonl'; a = AuditLog(path)
        a.append('A'); a.append('B')
        with path.open('a',encoding='utf-8') as f: f.write('{"schema":1,"event_id":"EVT-0000')      # power loss in the middle of a write
        with self.assertRaises(ValueError): a.append('C')              # fail closed
        out = a.repair()
        self.assertEqual(out['status'],'repaired'); self.assertTrue(out['chain_ok'])
        self.assertIn('EVT-0000',Path(out['moved_to']).read_text())
        a.append('C'); self.assertTrue(a.verify_chain()); self.assertEqual(a.repair()['status'],'clean')
        self.assertEqual(len(path.read_text().splitlines()),3)

    def test_audit_detects_events_cut_off_the_end(self):
        path = self.root/'cut.jsonl'; a = AuditLog(path)
        for name in 'ABC': a.append(name)
        self.assertTrue(a.verify_chain())
        lines = path.read_text().splitlines(); path.write_text('\n'.join(lines[:-1])+'\n')      # an intact chain, only shorter
        self.assertFalse(a.verify_chain())

    def test_guard_token_expires_and_old_tokens_are_pruned(self):
        rules = self.rt.architecture_root/'core'/'guard'/'guard_rules.yaml'
        store = self.root/'tokens.json'
        gate = lambda g: g.create_gate('M-TTL','overwrite_existing','t')
        g = Guard(rules, None, store, token_ttl_s=0)                  # void the moment it is issued
        token = g.approve(gate(g))
        self.assertEqual(g.authorize(token,mission_id='M-TTL',action='overwrite_existing',target='t')['reason'],'token_expired')
        g2 = Guard(rules, None, store)                                # default: a day
        token2 = g2.approve(gate(g2))
        self.assertTrue(g2.authorize(token2,mission_id='M-TTL',action='overwrite_existing',target='t')['authorized'])
        stored = json.loads(store.read_text())
        old = '2000-01-01T00:00:00+00:00'
        stored[token['token_id']]['validity']['expires_at'] = old; stored[token2['token_id']]['used_at'] = old
        store.write_text(json.dumps(stored))
        g3 = Guard(rules, None, store); g3.approve(gate(g3))
        self.assertEqual(len(json.loads(store.read_text())),1)        # both old ones dropped, only the new token is left
        forged = dict(token2,validity={'expires_at':None})
        self.assertFalse(g3.authorize(forged,mission_id='M-TTL',action='overwrite_existing',target='t')['authorized'])

    def test_guard_rules(self):
        g = self.rt.guard
        self.assertEqual(g.evaluate('create_new_artifact')['decision'], 'ALLOW')
        self.assertEqual(g.evaluate('overwrite_existing')['decision'], 'CAPTAIN_REQUIRED')
        self.assertEqual(g.evaluate('modify_core_invariants')['decision'], 'BLOCK')

    def test_guard_permission_missing_blocks(self):
        v = self.rt.guard.evaluate('read_project_file', required_permissions=['read'], present_permissions=[])
        self.assertEqual(v['decision'], 'BLOCK')

    def test_message_bus(self):
        bus = MessageBus()
        bus.register('b', lambda msg: {'echo': msg.payload['x']})
        out = bus.send(Message('M-1','a','b','t',{'x':3}))
        self.assertEqual(out['echo'], 3)

    def test_registry_loads_modules(self):
        self.assertIn('planning-context', self.rt.registry.modules)
        self.assertIn('knowledge', self.rt.registry.modules)
        self.assertIn('communications', self.rt.registry.modules)

    def test_artifact_hash_registered(self):
        p = self.root/'x.txt'; p.write_text('hello')
        rec = self.rt.artifacts.register('M-1', p)
        self.assertEqual(len(rec['integrity']['hash']), 64)

    def test_knowledge_store(self):
        store = KnowledgeStore(self.root/'k.jsonl')
        store.add('Model USB', 'Portable model runtime', tags=['portable'])
        self.assertEqual(len(store.search('portable')), 1)

    def test_evolution_classification(self):
        em = EvolutionManager()
        self.assertEqual(em.classify('skill'), 'E1')
        self.assertEqual(em.classify('module'), 'E2')
        self.assertEqual(em.classify('guard'), 'E3')
        gap = em.record_gap('Need better verifier', target_type='module')
        self.assertEqual(em.propose(gap)['proposed_change']['classification'], 'E2')

    def test_update_builder_base_mismatch(self):
        evo = self.root/'evo.yaml'
        evo.write_text('evolution:\n  base:\n    guppi_version: "9.9.9"\n')
        with self.assertRaises(CompatibilityError):
            UpdateBuilder('1.0.0').validate_evolution(evo)

    def test_overwrite_requires_captain_and_token_works(self):
        m = self.rt.brain.create_mission('Overwrite test')
        mid = m['identity']['mission_id']
        target = self.root/'runtime_data'/'workspace'/mid/'same.txt'
        first = self.rt.control.execute(m, {'action':'create_text_artifact','target':str(target),'content':'one'})
        self.assertEqual(first['status'],'completed')
        second = self.rt.control.execute(m, {'action':'create_text_artifact','target':str(target),'content':'two'})
        self.assertEqual(second['status'],'captain_required')
        token = self.rt.guard.approve(second['gate'])
        third = self.rt.control.execute(m, {'action':'create_text_artifact','target':str(target),'content':'two'}, approval_token=token)
        self.assertEqual(third['status'],'completed')
        self.assertEqual(target.read_text(),'two')
        self.assertEqual(token['status'],'used')

    def test_target_escape_rejected(self):
        m = self.rt.brain.create_mission('Escape test')
        outside = self.root/'outside.txt'
        out = self.rt.control.execute(m, {'action':'create_text_artifact','target':str(outside),'content':'x'})
        self.assertEqual(out['status'],'failed')
        self.assertFalse(outside.exists())


    def test_evolution_threshold_and_file(self):
        em = EvolutionManager()
        self.assertIsNone(em.propose(em.record_gap('same fail', gap_type='repeated_failure', target_type='module')))
        self.assertIsNone(em.propose(em.record_gap('same fail', gap_type='repeated_failure', target_type='module')))
        proposal = em.propose(em.record_gap('same fail', gap_type='repeated_failure', target_type='module'))
        self.assertEqual(proposal['proposed_change']['classification'], 'E2')
        path = self.root/'GUPPI_EVOLUTION.yaml'
        em.generate_evolution_file(proposal, path, '1.0.0')
        self.assertTrue(path.exists())

    def test_brain_human_gate_resume(self):
        m = self.rt.brain.create_mission('Gate test')
        mid=m['identity']['mission_id']
        # Advance until EXECUTE without executing it.
        for _ in range(4): self.rt.brain.step(mid)
        target=self.root/'runtime_data'/'workspace'/mid/'result.txt'
        target.parent.mkdir(parents=True, exist_ok=True); target.write_text('existing')
        out=self.rt.brain.step(mid)
        self.assertEqual(out['lifecycle']['phase'],'CAPTAIN_REVIEW')
        gate=out['human_gates']['pending'].pop(0)
        token=self.rt.guard.approve(gate)
        out['human_gates']['resolved'].append(gate); out['execution']['approval_token']=token; self.rt.missions.save(out)
        self.rt.brain.step(mid)
        final=self.rt.brain.run(mid)
        self.assertEqual(final['lifecycle']['phase'],'COMPLETE')


    def test_tool_registry_and_manager(self):
        self.assertIn('filesystem', self.rt.registry.tools)
        self.assertIn('git', self.rt.registry.tools)
        self.assertIn('shell', self.rt.registry.tools)
        tools=self.rt.tools.list()
        self.assertTrue(tools['filesystem']['healthy'])
        self.assertTrue(tools['shell']['healthy'])

    def test_filesystem_read_write_and_escape(self):
        mid='M-TOOLS1'
        out=self.rt.tools.execute('filesystem',mid,'write_text',{'path':'a/test.txt','content':'hello'})
        self.assertEqual(out['status'],'completed')
        read=self.rt.tools.execute('filesystem',mid,'read_text',{'path':'a/test.txt'})
        self.assertEqual(read['content'],'hello')
        with self.assertRaises(Exception):
            self.rt.tools.execute('filesystem',mid,'read_text',{'path':'../outside.txt'})

    def test_filesystem_overwrite_scope_and_single_use_token(self):
        mid='M-TOOLS2'
        self.rt.tools.execute('filesystem',mid,'write_text',{'path':'same.txt','content':'one'})
        second=self.rt.tools.execute('filesystem',mid,'write_text',{'path':'same.txt','content':'two'})
        self.assertEqual(second['status'],'captain_required')
        token=self.rt.guard.approve(second['gate'])
        third=self.rt.tools.execute('filesystem',mid,'write_text',{'path':'same.txt','content':'two'},token)
        self.assertEqual(third['status'],'completed')
        self.assertEqual(token['status'],'used')
        retry=self.rt.tools.execute('filesystem',mid,'write_text',{'path':'same.txt','content':'three'},token)
        self.assertEqual(retry['status'],'captain_required')

    def test_guard_rejects_forged_or_wrong_scope_token(self):
        mid='M-TOOLS3'
        self.rt.tools.execute('filesystem',mid,'write_text',{'path':'x.txt','content':'x'})
        pending=self.rt.tools.execute('filesystem',mid,'write_text',{'path':'x.txt','content':'y'})
        forged={'token_id':'APR-FAKE','mission_id':mid,'grants':{'action_type':'overwrite_existing','targets':[pending['gate']['request']['targets'][0]]},'limits':{'single_use':True},'status':'active','used_at':None}
        out=self.rt.tools.execute('filesystem',mid,'write_text',{'path':'x.txt','content':'y'},forged)
        self.assertEqual(out['status'],'captain_required')
        token=self.rt.guard.approve(pending['gate'])
        other=self.rt.tools.execute('filesystem',mid,'write_text',{'path':'other.txt','content':'new'})
        self.assertEqual(other['status'],'completed')
        # Token is exact-scope; it cannot authorize another existing target.
        self.rt.tools.execute('filesystem',mid,'write_text',{'path':'z.txt','content':'z'})
        wrong=self.rt.tools.execute('filesystem',mid,'write_text',{'path':'z.txt','content':'changed'},token)
        self.assertEqual(wrong['status'],'captain_required')

    def test_filesystem_delete_requires_captain(self):
        mid='M-TOOLS4'
        self.rt.tools.execute('filesystem',mid,'write_text',{'path':'delete.txt','content':'x'})
        pending=self.rt.tools.execute('filesystem',mid,'delete',{'path':'delete.txt'})
        self.assertEqual(pending['status'],'captain_required')
        token=self.rt.guard.approve(pending['gate'])
        done=self.rt.tools.execute('filesystem',mid,'delete',{'path':'delete.txt'},token)
        self.assertEqual(done['status'],'completed')

    def test_shell_is_no_shell_and_requires_exact_approval(self):
        mid='M-SHELL1'
        exe=sys.executable
        pending=self.rt.tools.execute('shell',mid,'run',{'argv':[exe,'--version']})
        self.assertEqual(pending['status'],'captain_required')
        token=self.rt.guard.approve(pending['gate'])
        done=self.rt.tools.execute('shell',mid,'run',{'argv':[exe,'--version']},token)
        self.assertEqual(done['status'],'completed')
        self.assertEqual(done['returncode'],0)
        with self.assertRaises(Exception):
            self.rt.tools.execute('shell',mid,'run',{'argv':[exe,'-c','print(1)']})
        with self.assertRaises(Exception):
            self.rt.tools.execute('shell',mid,'run',{'argv':['sh','-c','echo nope']})

    def test_git_read_and_mutation_gate_when_available(self):
        if shutil.which('git') is None:
            self.skipTest('git not installed')
        mid='M-GIT1'
        pending=self.rt.tools.execute('git',mid,'init',{'cwd':'.'})
        self.assertEqual(pending['status'],'captain_required')
        token=self.rt.guard.approve(pending['gate'])
        init=self.rt.tools.execute('git',mid,'init',{'cwd':'.'},token)
        self.assertEqual(init['status'],'completed')
        status=self.rt.tools.execute('git',mid,'status',{'cwd':'.','args':['--short']})
        self.assertEqual(status['status'],'completed')

    def test_control_master_dispatches_tool_call(self):
        m=self.rt.brain.create_mission('Use filesystem tool')
        req={'action':'tool_call','tool':'filesystem','operation':'write_text','args':{'path':'cm.txt','content':'via control'},'register_artifact':True}
        out=self.rt.control.execute(m,req)
        self.assertEqual(out['status'],'completed')
        self.assertEqual(len(out['artifacts']),1)


    def test_guard_approval_survives_runtime_restart(self):
        mid='M-PERSIST1'
        self.rt.tools.execute('filesystem',mid,'write_text',{'path':'persist.txt','content':'one'})
        pending=self.rt.tools.execute('filesystem',mid,'write_text',{'path':'persist.txt','content':'two'})
        token=self.rt.guard.approve(pending['gate'])
        restarted=GuppiRuntime(self.root, ARCH)
        done=restarted.tools.execute('filesystem',mid,'write_text',{'path':'persist.txt','content':'two'},token)
        self.assertEqual(done['status'],'completed')
        self.assertEqual(token['status'],'used')


    def test_hardware_detector_and_profile_selection(self):
        snap=detect_hardware()
        self.assertTrue(snap.hardware_class)
        self.assertGreaterEqual(snap.cpu_threads,1)
        self.assertIsInstance(self.rt.recommended_model_profile,dict)
        self.assertIn('runtime',self.rt.recommended_model_profile)
        self.assertIn('context',self.rt.recommended_model_profile)

    def test_custom_model_profile_persists(self):
        builtin=Path(__file__).resolve().parents[1]/'config'/'model_profiles.yaml'
        custom=self.root/'custom_profiles.yaml'
        store=ModelProfileStore(builtin,custom)
        profile={
            'runtime':'llama-cpp-server','model':'Custom Model','quantization':'Q4_K_M',
            'context':{'recommended':4096,'maximum':8192},'memory_reserve_gb':3
        }
        store.save_custom('captain-test',profile)
        reloaded=ModelProfileStore(builtin,custom)
        self.assertEqual(reloaded.custom()['captain-test']['model'],'Custom Model')

    def test_local_model_adapter_rejects_remote_endpoint(self):
        with self.assertRaises(ModelAdapterError):
            LMStudioAdapter('https://example.com')

    def test_local_model_adapter_and_router(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                if self.path == '/v1/models':
                    body=json.dumps({'data':[{'id':'test-model'}]}).encode()
                    self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
                else:
                    self.send_response(404); self.end_headers()
            def do_POST(self):
                if self.path == '/v1/chat/completions':
                    length=int(self.headers.get('Content-Length','0')); self.rfile.read(length)
                    body=json.dumps({'choices':[{'message':{'role':'assistant','content':'pong'}}]}).encode()
                    self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
                else:
                    self.send_response(404); self.end_headers()
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            adapter=LMStudioAdapter(f'http://127.0.0.1:{server.server_port}')
            self.assertTrue(adapter.health())
            self.assertEqual(adapter.list_models(),['test-model'])
            router=ModelRouter(); router.register(adapter)
            out=router.chat('M-MODEL',[{'role':'user','content':'ping'}],provider='lm-studio')
            self.assertEqual(out['content'],'pong')
        finally:
            server.shutdown(); thread.join(timeout=2); server.server_close()

    def test_control_master_model_inference(self):
        class FakeRouter:
            adapters={'fake':True}
            def choose(self,provider=None):
                from types import SimpleNamespace
                return SimpleNamespace(id='fake')
            def chat(self,mission_id,messages,**kwargs):
                return {'provider':'fake','model':'fake-model','content':'ok'}
        m=self.rt.brain.create_mission('Model test')
        old=self.rt.control.model_router; self.rt.control.model_router=FakeRouter()
        try:
            out=self.rt.control.execute(m,{'action':'model_inference','messages':[{'role':'user','content':'hello'}]})
            self.assertEqual(out['status'],'completed')
            self.assertEqual(out['model_result']['content'],'ok')
        finally:
            self.rt.control.model_router=old


    def test_filesystem_cannot_delete_tool_root(self):
        with self.assertRaises(Exception):
            self.rt.tools.execute('filesystem','M-ROOT','delete',{'path':'.'})

    def test_git_rejects_unsafe_arguments_when_available(self):
        if shutil.which('git') is None:
            self.skipTest('git not installed')
        with self.assertRaises(Exception):
            self.rt.tools.execute('git','M-GITSAFE','init',{'cwd':'.','args':['../outside']})
        with self.assertRaises(Exception):
            self.rt.tools.execute('git','M-GITSAFE','diff',{'cwd':'.','args':['--ext-diff']})


    def test_filesystem_stat_hash_copy_move_and_atomic_precondition(self):
        mid='M-FS13'
        first=self.rt.tools.execute('filesystem',mid,'write_text',{'path':'ops/a.txt','content':'alpha'})
        self.assertEqual(first['status'],'completed')
        stat=self.rt.tools.execute('filesystem',mid,'stat',{'path':'ops/a.txt'})
        self.assertEqual(stat['type'],'file')
        digest=self.rt.tools.execute('filesystem',mid,'sha256',{'path':'ops/a.txt'})
        self.assertEqual(digest['sha256'],first['sha256'])
        copy=self.rt.tools.execute('filesystem',mid,'copy',{'src':'ops/a.txt','dst':'ops/b.txt'})
        self.assertEqual(copy['status'],'completed')
        with self.assertRaises(Exception):
            self.rt.tools.execute('filesystem',mid,'write_text',{'path':'ops/a.txt','content':'changed','expected_sha256':'0'*64})
        pending=self.rt.tools.execute('filesystem',mid,'move',{'src':'ops/b.txt','dst':'ops/c.txt'})
        self.assertEqual(pending['status'],'captain_required')
        token=self.rt.guard.approve(pending['gate'])
        moved=self.rt.tools.execute('filesystem',mid,'move',{'src':'ops/b.txt','dst':'ops/c.txt'},token)
        self.assertEqual(moved['status'],'completed')

    def test_filesystem_recursive_delete_is_explicit(self):
        mid='M-FSDEL13'
        self.rt.tools.execute('filesystem',mid,'write_text',{'path':'tree/x.txt','content':'x'})
        pending=self.rt.tools.execute('filesystem',mid,'delete',{'path':'tree'})
        self.assertEqual(pending['status'],'captain_required')
        token=self.rt.guard.approve(pending['gate'])
        with self.assertRaises(Exception):
            self.rt.tools.execute('filesystem',mid,'delete',{'path':'tree'},token)
        # The first token was consumed before the non-empty-directory validation,
        # so a new exact approval is intentionally required for retry.
        pending2=self.rt.tools.execute('filesystem',mid,'delete',{'path':'tree','recursive':True})
        token2=self.rt.guard.approve(pending2['gate'])
        done=self.rt.tools.execute('filesystem',mid,'delete',{'path':'tree','recursive':True},token2)
        self.assertEqual(done['status'],'completed')

    def test_filesystem_rejects_symlink_components_when_supported(self):
        mid='M-SYMLINK13'
        outside=self.root/'outside-symlink-target'; outside.mkdir(exist_ok=True)
        link=self.rt.filesystem_tool.root/'link'
        try:
            link.symlink_to(outside,target_is_directory=True)
        except (OSError,NotImplementedError):
            self.skipTest('symlink unavailable')
        with self.assertRaises(Exception):
            self.rt.tools.execute('filesystem',mid,'write_text',{'path':'link/escape.txt','content':'nope'})

    def test_filesystem_bad_encoding_is_a_validation_error_not_a_crash(self):
        from guppi_runtime.tools.base import ToolValidationError
        fs=self.rt.filesystem_tool
        (fs.root/'latin.txt').write_bytes('Grüße'.encode('latin-1'))
        with self.assertRaisesRegex(ToolValidationError,'invalid_encoding'):
            fs.execute('M-ENC','read_text',{'path':'latin.txt','encoding':'no-such-codec'})
        with self.assertRaisesRegex(ToolValidationError,'invalid_encoding'):
            fs.execute('M-ENC','read_text',{'path':'latin.txt','encoding':'base64'})      # a bytes codec, not a text codec
        with self.assertRaisesRegex(ToolValidationError,'file_not_decodable'):
            fs.execute('M-ENC','read_text',{'path':'latin.txt'})
        self.assertEqual(fs.execute('M-ENC','read_text',{'path':'latin.txt','encoding':'latin-1'})['content'],'Grüße')
        with self.assertRaisesRegex(ToolValidationError,'content_not_encodable'):
            fs.execute('M-ENC','write_text',{'path':'ascii.txt','content':'Grüße','encoding':'ascii'})

    def test_filesystem_list_dir_truncation_flag(self):
        fs=self.rt.filesystem_tool
        for name in 'abc': (fs.root/f'{name}.txt').write_text(name)
        out=fs.execute('M-LS','list_dir',{'path':'.','limit':2})
        self.assertEqual((len(out['entries']),out['truncated']),(2,True))
        self.assertFalse(fs.execute('M-LS','list_dir',{'path':'.','limit':100})['truncated'])

    def test_tool_manager_is_registry_backed(self):
        listing=self.rt.tools.list()
        self.assertTrue(listing['filesystem']['registered'])
        self.assertEqual(listing['filesystem']['version'],'0.2.0')
        self.assertIn('sha256',listing['filesystem']['operations'])

    def test_git_add_is_not_exposed(self):
        if shutil.which('git') is None:
            self.skipTest('git not installed')
        with self.assertRaises(Exception):
            self.rt.tools.execute('git','M-GIT13','add',{'cwd':'.','args':['.']})

    def test_control_master_tool_sequence_and_resume(self):
        m=self.rt.brain.create_mission('Sequence tool calls')
        mid=m['identity']['mission_id']
        steps=[
            {'id':'create','tool':'filesystem','operation':'write_text','args':{'path':'seq.txt','content':'one'}},
            {'id':'overwrite','tool':'filesystem','operation':'write_text','args':{'path':'seq.txt','content':'two'}},
            {'id':'read','tool':'filesystem','operation':'read_text','args':{'path':'seq.txt'}},
        ]
        out=self.rt.control.execute(m,{'action':'tool_sequence','steps':steps})
        self.assertEqual(out['status'],'captain_required')
        self.assertEqual(out['resume_from'],1)
        token=self.rt.guard.approve(out['gate'])
        resumed=self.rt.control.execute(m,{'action':'tool_sequence','steps':steps,'start_at':1,'approval_tokens':{'overwrite':token}})
        self.assertEqual(resumed['status'],'completed')
        self.assertEqual(resumed['steps'][-1]['result']['content'],'two')

    def test_shell_only_allows_bounded_test_compile_modes(self):
        mid='M-SHELL13'
        exe=sys.executable
        with self.assertRaises(Exception):
            self.rt.tools.execute('shell',mid,'run',{'argv':[exe,'-m','http.server']})
        with self.assertRaises(Exception):
            self.rt.tools.execute('shell',mid,'run',{'argv':[exe,'-m','compileall','../']})

    def test_portable_model_catalog_scan(self):
        model_dir=self.rt.model_runtime.portable_models_dir
        sample=model_dir/'Tiny-1.5B-Q4_K_M.gguf'
        sample.write_bytes(b'GGUFTEST')
        try:
            found=self.rt.model_runtime.scan_portable()
            self.assertTrue(any(x['filename']==sample.name for x in found))
            rec=[x for x in found if x['filename']==sample.name][0]
            self.assertEqual(rec['quantization'],'Q4_K_M')
            self.assertEqual(rec['parameters_hint'],'1.5B')
        finally:
            sample.unlink(missing_ok=True)

    def test_hardware_model_pass_resolves_runtime_values(self):
        result=self.rt.model_runtime.profile_for(model_size_gb=0.01)
        self.assertIn(result['status'],{'PASS','REVIEW'})
        self.assertIsInstance(result['effective_profile']['cpu_threads'],int)
        self.assertLessEqual(result['effective_profile']['context']['recommended'],result['effective_profile']['context']['maximum'])

    def test_model_runtime_tool_read_operations(self):
        out=self.rt.tools.execute('model-runtime','M-MODELRT','status',{})
        self.assertEqual(out['status'],'completed')
        self.assertIn('providers',out['runtime'])
        hp=self.rt.tools.execute('model-runtime','M-MODELRT','hardware_pass',{'model_size_gb':0.01})
        self.assertEqual(hp['status'],'completed')

    def test_model_runtime_control_requires_captain(self):
        out=self.rt.tools.execute('model-runtime','M-MODELCTRL','runtime_action',{'provider':'lm-studio','action':'server_stop','params':{}})
        self.assertEqual(out['status'],'captain_required')
        self.assertEqual(out['gate']['request']['exact_action'],'model_runtime_control')

    def test_lmstudio_controller_command_contract(self):
        from guppi_runtime.models.runtime_control import LMStudioRuntimeController
        class FakeRunner:
            def __init__(self): self.calls=[]
            def run(self,argv,timeout=30):
                self.calls.append(list(argv))
                if argv[1:3] == ['daemon','status']: return '{"status":"running"}'
                if argv[1:3] == ['server','status']: return '{"running":true,"port":1234}'
                if argv[1:3] == ['ls','--json']: return '[]'
                if argv[1:3] == ['ps','--json']: return '[]'
                return 'ok'
        runner=FakeRunner(); ctl=LMStudioRuntimeController('/fake/lms',runner=runner)
        status=ctl.status(); self.assertTrue(status['available'])
        ctl.list_models(); ctl.loaded_models()
        load=ctl.load_model('example/model',context_length=4096,gpu='max',identifier='guppi')
        self.assertIn('--context-length',load['command'])
        self.assertIn('--gpu',load['command'])

    def test_llamacpp_start_command_is_loopback_and_tuned(self):
        from guppi_runtime.models.runtime_control import LlamaCppRuntimeController
        model=self.rt.model_runtime.portable_models_dir/'Cmd-4B-Q4_K_M.gguf'
        model.write_bytes(b'x')
        try:
            ctl=LlamaCppRuntimeController('/opt/llama-server')
            passed=self.rt.model_runtime.profile_for(model_size_gb=0.01)
            cmd=ctl.build_start_command(model,passed['effective_profile'],port=18080)
            self.assertIn('127.0.0.1',cmd)
            self.assertIn('--ctx-size',cmd)
            self.assertIn('--n-gpu-layers',cmd)
            self.assertIn('--cache-type-k',cmd)
        finally:
            model.unlink(missing_ok=True)

    def test_portable_import_and_remove_are_guarded(self):
        src=self.root/'External-2B-Q4_K_M.gguf'; src.write_bytes(b'model')
        mid='M-IMPORT14'
        req={'provider':'portable','action':'import_model','params':{'source_path':str(src)}}
        pending=self.rt.tools.execute('model-runtime',mid,'runtime_action',req)
        self.assertEqual(pending['status'],'captain_required')
        token=self.rt.guard.approve(pending['gate'])
        done=self.rt.tools.execute('model-runtime',mid,'runtime_action',req,token)
        self.assertEqual(done['status'],'completed')
        rec=done['result']
        self.assertTrue(Path(rec['path']).exists())
        remove_req={'provider':'portable','action':'remove_model','params':{'model_id':rec['id']}}
        pending2=self.rt.tools.execute('model-runtime',mid,'runtime_action',remove_req)
        token2=self.rt.guard.approve(pending2['gate'])
        removed=self.rt.tools.execute('model-runtime',mid,'runtime_action',remove_req,token2)
        self.assertEqual(removed['status'],'completed')
        self.assertFalse(Path(rec['path']).exists())

    def test_llamacpp_managed_process_contract(self):
        from guppi_runtime.models.runtime_control import LlamaCppRuntimeController
        class FakeProcess:
            pid=4242
            def __init__(self): self.running=True
            def poll(self): return None if self.running else 0
            def terminate(self): self.running=False
            def wait(self,timeout=None): return 0
            def kill(self): self.running=False
        calls=[]
        def factory(argv,**kwargs): calls.append((argv,kwargs)); return FakeProcess()
        model=self.rt.model_runtime.portable_models_dir/'Proc-1B-Q4_K_M.gguf'; model.write_bytes(b'x')
        log=self.root/'llama.log'
        try:
            ctl=LlamaCppRuntimeController('/opt/llama-server',process_factory=factory)
            passed=self.rt.model_runtime.profile_for(model_size_gb=0.01)
            started=ctl.start_server(model,passed['effective_profile'],port=18081,log_path=log)
            self.assertEqual(started['pid'],4242)
            # status() also asks the endpoint's /health; no real port in tests (a server of this PC could answer on 8080).
            with patch('guppi_runtime.models.runtime_control.urlopen',side_effect=OSError('no network in tests')) as probe:
                self.assertTrue(ctl.status()['managed_running'])
            probe.assert_called_once()
            stopped=ctl.stop_server(); self.assertTrue(stopped['stopped'])
        finally:
            model.unlink(missing_ok=True)

    def test_hardware_fingerprint_is_stable(self):
        fp1=self.rt.hardware.fingerprint(); fp2=self.rt.hardware.fingerprint()
        self.assertEqual(fp1,fp2); self.assertEqual(len(fp1),24)

    def test_benchmark_active_and_known_good_promotion(self):
        from guppi_runtime.models.benchmark import ModelBenchmarkRunner
        class FakeAdapter:
            def health(self): return True
            def list_models(self): return ['fake-model']
            def chat(self,messages,model=None,**kwargs):
                return {'provider':'fake','model':model or 'fake-model','content':'abcdefgh','raw':{'usage':{'completion_tokens':8}}}
        class FakeCtl:
            endpoint='http://127.0.0.1:9999'
            def status(self): return {'managed_pid':None}
        old_controller=self.rt.model_runtime.controller
        old_adapter=self.rt.model_runtime.benchmark._adapter
        try:
            self.rt.model_runtime.controller=lambda provider: FakeCtl()
            self.rt.model_runtime.benchmark._adapter=lambda provider,endpoint: FakeAdapter()
            result=self.rt.model_runtime.benchmark.benchmark_active('llama-cpp-server',repeats=2,warmups=0,max_tokens=8)
            self.assertEqual(result['qualification']['status'],'PASS')
            promoted=self.rt.model_runtime.benchmark.promote_known_good(result['benchmark_id'])
            self.assertTrue(promoted['profile_id'].startswith('kgp-'))
            self.assertIn(promoted['profile_id'],self.rt.model_profiles.known_good_records())
        finally:
            self.rt.model_runtime.controller=old_controller
            self.rt.model_runtime.benchmark._adapter=old_adapter

    def test_known_good_requires_passing_benchmark(self):
        store=self.rt.model_runtime.benchmark.store
        rec={
            'benchmark_id':'BM-FAILTEST','created_at':'x','provider':'llama-cpp-server',
            'hardware':{**self.rt.hardware.to_dict(),'fingerprint':self.rt.hardware.fingerprint()},
            'model':{'id':'GGUF-X'},'profile_pass':{'effective_profile':self.rt.recommended_model_profile},
            'metrics':{'median_tokens_per_second':0},'qualification':{'status':'FAIL'}
        }
        store.save(rec)
        with self.assertRaises(ValueError): self.rt.model_runtime.benchmark.promote_known_good('BM-FAILTEST')

    def test_known_good_promotion_tool_is_guarded(self):
        mid='M-KNOWNGOOD15'
        m=self.rt.brain.create_mission('Confirm a known-good model profile')
        mid=m['identity']['mission_id']
        pending=self.rt.tools.execute('model-runtime',mid,'promote_known_good',{'benchmark_id':'BM-NOT-THERE'})
        self.assertEqual(pending['status'],'captain_required')
        self.assertEqual(pending['gate']['request']['exact_action'],'model_profile_promote')

    def test_known_good_profile_selected_for_exact_model_and_hardware(self):
        builtin=Path(__file__).resolve().parents[1]/'config'/'model_profiles.yaml'
        custom=self.root/'kg-custom.yaml'; known=self.root/'kg-known.yaml'
        store=ModelProfileStore(builtin,custom,known)
        profile=dict(self.rt.recommended_model_profile)
        store.save_known_good('kgp-test',{
            'status':'confirmed','runtime':'llama-cpp-server','hardware':{'fingerprint':'HW1','hardware_class':'x'},
            'model':{'id':'MODEL1'},'score':99.0,'profile':profile
        })
        selected=store.select_for_hardware('cpu_small',hardware_fingerprint='HW1',model_id='MODEL1',runtime='llama-cpp-server')
        self.assertEqual(selected['runtime'],profile['runtime'])
        self.assertEqual(selected['model'],profile['model'])

if __name__ == '__main__':
    unittest.main()
