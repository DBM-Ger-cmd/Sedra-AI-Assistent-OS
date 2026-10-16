from copy import deepcopy
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml

from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.sandbox.broker import SandboxBroker
from guppi_runtime.sandbox.provider import MicrosandboxProvider
from guppi_runtime.tools.base import ToolValidationError
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = sorted((Path(__file__).resolve().parents[2]/'architecture').glob('GUPPI_Architecture_v*'))[-1]


class FakeProvider:
    def __init__(self): self.calls=[]; self.response=None
    def probe(self): return {'backend':'microsandbox','sdk_version':'0.7.4','blockers':[]}
    def execute(self, request, job):
        self.calls.append(request)
        if self.response is not None:return deepcopy(self.response)
        return {'status':'PASS','cleanup_confirmed':True,'commands':[{'argv': argv, 'exit_code':0, 'success':True, 'output':''} for argv in request['commands']],
                'exports':[{'path':'example.py','data_base64':base64.b64encode(b'value = 2\n').decode()}]}


class SandboxCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.rt=GuppiRuntime(self.root, ARCH)
        self.source=self.rt.filesystem_tool.root/'project';self.source.mkdir()
        (self.source/'example.py').write_text('value = 1\n')
        self.fake=FakeProvider()
        original=self.rt.sandbox.policy()
        # Own sandbox state for the runtime broker: the shipped unqualified default, never the PC's real (possibly released) config.
        self.rt.sandbox.config_path=self.root/'unqualified-sandbox.yaml'
        self.rt.sandbox.config_path.write_text(yaml.safe_dump({'sandbox':dict(original,target_qualified=False)}))
        original['target_qualified']=True
        original['image']='test/image@sha256:'+'a'*64
        self.cfg=self.root/'sandbox.yaml';self.cfg.write_text(yaml.safe_dump({'sandbox':original}))
        self.broker=SandboxBroker(self.rt.filesystem_tool.root,self.root/'sandbox-data',self.cfg,self.fake,self.rt.guard,self.rt.audit)
        self.args={'source':'project','commands':[['python3','example.py']],'exports':['example.py']}

    def tearDown(self):self.tmp.cleanup()
    def plan(self):return self.broker.preview(**self.args)
    def approve_and_run(self, plan=None):
        plan=plan or self.plan()
        pending=self.broker.execute('M-SBX','run',{'plan':plan})
        token=self.rt.guard.approve(pending['gate'])
        return self.broker.execute('M-SBX','run',{'plan':plan},token)

    def test_failure_before_the_provider_starts_leaves_no_lock_behind(self):
        plan=self.plan()
        with patch('guppi_runtime.sandbox.broker.atomic_write_json',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.broker._run('M-SBX',plan)
        self.assertFalse((self.broker.data_root/'active.lock').exists())      # no VM existed, so nothing is pending cleanup
        self.assertEqual(self.fake.calls,[])

    def test_doctor_uses_the_path_health_capability(self):
        self.fake.home=self.root/'home'
        self.broker.path_health_source=lambda:(str(self.root),[{'mission_id':'M-OLD','host_root':'C:\\elsewhere'}])
        out=self.broker.doctor()
        self.assertEqual(out['path_health']['stale_missions'],['M-OLD'])     # reported, not blocking
        self.assertNotIn('vm_path_too_long',out['blockers'])
        self.fake.home=Path('C:\\'+'x'*230)                                   # the longest VM path would pass the Windows limit
        out=self.broker.doctor()
        self.assertIn('vm_path_too_long',out['blockers']);self.assertFalse(out['execution_ready'])

    def test_doctor_survives_a_missing_or_failing_capability(self):
        self.assertEqual(self.broker.doctor()['path_health']['status'],'UNAVAILABLE')      # the fake provider has no backend home
        self.fake.home=self.root/'home'
        def boom():raise RuntimeError('broken source')
        self.broker.path_health_source=boom
        out=self.broker.doctor()
        self.assertEqual(out['path_health']['status'],'ERROR');self.assertNotIn('vm_path_too_long',out['blockers'])

    def test_runtime_lists_only_open_candidates(self):
        m=self.rt.brain.create_mission('x');mid=m['identity']['mission_id']
        report=self.rt.control.workspace/mid/'candidate-report.json';report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps({'sandbox_plan':{'host_root':'C:\\old'}}))
        self.assertEqual(self.rt._open_candidate_bindings()[1],[])                          # NEW: not a candidate
        m['lifecycle']['phase']='CANDIDATE_REVIEW';self.rt.missions.save(m)
        self.assertEqual(self.rt._open_candidate_bindings()[1],[{'mission_id':mid,'host_root':'C:\\old'}])

    def test_default_real_backend_blocked_and_no_fallback(self):
        out=self.rt.sandbox.execute('M','run',{'plan':self.rt.sandbox.preview(**self.args)})
        self.assertEqual(out['status'],'blocked')
        # setUp isolates the shipped unqualified config, so this holds whether or not this PC released its VM or has the pinned SDK.
        self.assertIn('target_boundary_acceptance_pending',out['sandbox']['blockers'])
        self.assertTrue(out['sandbox']['blockers'])
        self.assertFalse(out['sandbox']['unsafe_host_fallback'])

    def test_preview_pure_deterministic_and_registry_integrated(self):
        self.assertEqual(self.plan(),self.plan())
        self.assertEqual(self.fake.calls,[])
        self.assertFalse(self.broker.data_root.exists())
        self.assertIn('sandbox',self.rt.tools.list())

    def test_guest_command_never_executed_in_preview(self):
        with patch('subprocess.Popen') as popen:self.plan()
        popen.assert_not_called()

    def test_source_escape_and_root_rejected(self):
        for source in ['../','/tmp','.','project/../../']:
            with self.subTest(source=source),self.assertRaises(Exception):self.broker.preview(**dict(self.args,source=source))

    def test_symlink_hidden_special_and_sensitive_files_rejected(self):
        for name in ['.env','secret.json','password.txt','unsafe.pem']:
            p=self.source/name;p.write_text('no')
            with self.subTest(name=name),self.assertRaises(ToolValidationError):self.plan()
            p.unlink()
        link=self.source/'link.py'
        try:link.symlink_to(self.source/'example.py')
        except OSError:return
        with self.assertRaises(ToolValidationError):self.plan()

    def test_input_size_limit(self):
        p=yaml.safe_load(self.cfg.read_text());p['sandbox']['max_file_bytes']=1;self.cfg.write_text(yaml.safe_dump(p))
        with self.assertRaises(ToolValidationError):self.plan()

    def test_windows_device_and_control_names_rejected(self):
        for value in ['CON.py', 'dir/LPT1.txt', 'NUL.json', 'COM¹.txt', 'bad\nname.py', 'dir./file.py']:
            with self.subTest(value=value), self.assertRaises(ToolValidationError): self.broker.relative(value)

    def test_bad_exports_and_commands(self):
        for exports in [['../escape.py'],['.git/config'],['/etc/passwd'],['example.py','example.py']]:
            with self.subTest(exports=exports),self.assertRaises(ToolValidationError):self.broker.preview(**dict(self.args,exports=exports))
        for commands in [[],['shell'],[['python3','\x00']],[[None]]]:
            with self.subTest(commands=commands),self.assertRaises(ToolValidationError):self.broker.preview(**dict(self.args,commands=commands))

    def test_modified_plan_source_and_policy_refused(self):
        plan=self.plan();changed=deepcopy(plan);changed['request']['commands']=[['rm','-rf','/']]
        with self.assertRaises(ToolValidationError):self.broker.validate(changed)
        (self.source/'example.py').write_text('different')
        with self.assertRaises(ToolValidationError):self.broker.validate(plan)
        plan=self.plan();p=yaml.safe_load(self.cfg.read_text());p['sandbox']['cpus']=1;self.cfg.write_text(yaml.safe_dump(p))
        with self.assertRaises(ToolValidationError):self.broker.validate(plan)

    def test_exact_gate_and_single_use(self):
        plan=self.plan();pending=self.broker.execute('M-SBX','run',{'plan':plan})
        self.assertEqual(pending['status'],'captain_required');self.assertFalse(self.fake.calls)
        token=self.rt.guard.approve(pending['gate'])
        other=self.broker.preview(**dict(self.args,exports=[]))
        self.assertEqual(self.broker.execute('M-SBX','run',{'plan':other},token)['status'],'captain_required')
        self.assertEqual(self.broker.execute('M-SBX','run',{'plan':plan},token)['status'],'completed')
        self.assertEqual(self.broker.execute('M-SBX','run',{'plan':plan},token)['status'],'captain_required')

    def test_isolated_staging_candidate_and_original_unchanged(self):
        result=self.approve_and_run()
        self.assertEqual(result['status'],'completed')
        self.assertEqual((self.source/'example.py').read_text(),'value = 1\n')
        candidate=result['sandbox']['candidate']
        self.assertEqual((Path(candidate['path'])/'example.py').read_text(),'value = 2\n')
        self.assertEqual(candidate['promotion'],'CAPTAIN_REVIEW_REQUIRED')
        self.assertEqual(candidate['files'][0]['change'],'modified')
        self.assertNotEqual(self.fake.calls[0]['source'],str(self.source))
        self.assertFalse((self.broker.data_root/'active.lock').exists())
        self.assertEqual(self.broker.history()[0]['status'],'PASS')

    def test_export_traversal_scope_and_oversize_rejected(self):
        for path,data in [('../escape.py',b'x'),('new.py',b'x'),('example.py',b'x'*(1024*1024+1))]:
            self.fake.response={'status':'PASS','cleanup_confirmed':True,'commands':[{'argv':['python3','example.py'],'exit_code':0,'success':True,'output':''}],
                                'exports':[{'path':path,'data_base64':base64.b64encode(data).decode()}]}
            result=self.approve_and_run()
            self.assertEqual(result['status'],'failed')
            self.assertFalse(list(self.broker.data_root.glob('jobs/*/candidate')))

    def test_duplicate_and_missing_exports_rejected(self):
        rec={'path':'example.py','data_base64':'eA=='}
        for exports in [[],[rec,rec]]:
            self.fake.response={'status':'PASS','cleanup_confirmed':True,'commands':[{'argv':['python3','example.py'],'exit_code':0,'success':True,'output':''}],'exports':exports}
            self.assertEqual(self.approve_and_run()['status'],'failed')

    def allow_dirs(self):
        cfg=yaml.safe_load(self.cfg.read_text()); cfg['sandbox']['allow_export_dirs']=True; self.cfg.write_text(yaml.safe_dump(cfg))

    def dir_response(self, exports):
        return {'status':'PASS','cleanup_confirmed':True,'commands':[{'argv':['python3','example.py'],'exit_code':0,'success':True,'output':''}],
                'exports':[{'path':p,'data_base64':base64.b64encode(d).decode()} for p,d in exports]}

    def test_export_dirs_are_off_unless_the_captain_turns_them_on(self):
        self.assertNotIn('export_dirs',self.plan()['request'])                                  # unused: the plan (and its digest) is exactly as before
        with self.assertRaises(ToolValidationError) as ctx: self.broker.preview(**dict(self.args,export_dirs=['out']))
        self.assertIn('export_dirs_disabled_by_policy',str(ctx.exception))
        cfg=yaml.safe_load(self.cfg.read_text()); cfg['sandbox']['allow_export_dirs']='yes'; self.cfg.write_text(yaml.safe_dump(cfg))
        with self.assertRaises(ToolValidationError): self.broker.policy()                       # not a boolean

    def test_export_dir_plan_validation(self):
        self.allow_dirs()
        plan=self.broker.preview(**dict(self.args,export_dirs=['out','build/gen']))
        self.assertEqual(plan['request']['export_dirs'],['out','build/gen'])
        self.broker.validate(plan)
        for bad in (['out','out/sub'],['out','out'],['.hidden'],['../x'],['/abs'],'out',[1],['a']*9,['con'],['out:x']):
            with self.assertRaises(ToolValidationError,msg=str(bad)): self.broker.preview(**dict(self.args,export_dirs=bad))

    def test_export_dir_files_come_back_into_a_candidate_with_scope_checked(self):
        self.allow_dirs()
        plan=self.broker.preview(**dict(self.args,export_dirs=['out']))
        self.fake.response=self.dir_response([('example.py',b'value = 3\n'),('out/a.py',b'a = 1\n'),('out/sub/n.txt',b'note\n')])
        result=self.approve_and_run(plan)
        self.assertEqual(result['status'],'completed')
        candidate=result['sandbox']['candidate']
        self.assertEqual({f['path']:f['change'] for f in candidate['files']},{'example.py':'modified','out/a.py':'added','out/sub/n.txt':'added'})
        self.assertEqual((Path(candidate['path'])/'out'/'sub'/'n.txt').read_text(),'note\n')
        self.assertEqual(candidate['promotion'],'CAPTAIN_REVIEW_REQUIRED')
        self.assertEqual(self.fake.calls[0]['export_dirs'],['out'])
        job_id=Path(candidate['path']).parent.name
        import hashlib
        report=self.broker.receipt(job_id)
        verdict=self.broker.verify('M-SBX',job_id,hashlib.sha256(report).hexdigest(),plan['plan_digest'])
        self.assertEqual(verdict['verification'],'PASS',verdict)                                # the recorded manifest passes the independent check

    def test_export_dir_answers_outside_the_approved_scope_are_refused_and_leave_no_candidate(self):
        self.allow_dirs()
        plan=self.broker.preview(**dict(self.args,export_dirs=['out']))
        ok=('example.py',b'value = 3\n')
        cases={'outside':[ok,('other/x.py',b'x')],'sibling_prefix':[ok,('outside/x.py',b'x')],'file_type':[ok,('out/prog.exe',b'MZ')],
               'hidden':[ok,('out/.env.py',b'x')],'credential_name':[ok,('out/token.py',b'x')],'traversal':[ok,('out/../x.py',b'x')],
               'duplicate':[ok,('out/a.py',b'1'),('out/a.py',b'2')],'missing_explicit':[('out/a.py',b'1')],
               'oversize':[ok,('out/big.py',b'x'*(1024*1024+1))]}
        for name,exports in cases.items():
            self.fake.response=self.dir_response(exports)
            self.assertEqual(self.approve_and_run(plan)['status'],'failed',name)
            self.assertFalse(list(self.broker.data_root.glob('jobs/*/candidate')),name)
        self.fake.response=self.dir_response([ok]+[('out/f%d.py'%i,b'x') for i in range(self.broker.policy()['max_files']+1)])
        self.assertEqual(self.approve_and_run(plan)['status'],'failed')                         # more files than the policy allows
        self.assertFalse(list(self.broker.data_root.glob('jobs/*/candidate')))

    def test_command_failure_has_no_candidate(self):
        self.fake.response={'status':'FAILED','cleanup_confirmed':True,'commands':[],'exports':[],'error':'guest failure'}
        result=self.approve_and_run();self.assertEqual(result['status'],'failed')
        self.assertIsNone(result['sandbox']['candidate'])
        self.assertFalse((self.broker.data_root/'active.lock').exists())

    def test_cleanup_failure_retains_interlock(self):
        self.fake.response={'status':'CLEANUP_UNCONFIRMED','cleanup_confirmed':False,'commands':[],'exports':[]}
        self.assertEqual(self.approve_and_run()['status'],'failed')
        self.assertTrue((self.broker.data_root/'active.lock').exists())
        self.assertFalse(self.broker.doctor()['execution_ready'])
        self.assertEqual(self.broker.execute('M','run',{'plan':self.plan()})['status'],'blocked')

    def test_provider_exception_retains_interlock(self):
        with patch.object(self.fake,'execute',side_effect=RuntimeError('worker disappeared')):
            result=self.approve_and_run()
        self.assertEqual(result['status'],'failed')
        self.assertEqual(self.broker.history()[0]['status'],'CLEANUP_UNCONFIRMED')
        self.assertTrue((self.broker.data_root/'active.lock').exists())

    def test_disallowed_policy_blocks(self):
        for field,value in [('network','allow'),('sdk_version','latest'),('cpus',100),('root_disk_mib',1024)]:
            original=self.cfg.read_text();p=yaml.safe_load(original);p['sandbox'][field]=value;self.cfg.write_text(yaml.safe_dump(p))
            with self.subTest(field=field),self.assertRaises(Exception):self.broker.policy()
            self.cfg.write_text(original)

    def test_worker_environment_drops_cloud_secrets_and_python_hooks(self):
        provider=MicrosandboxProvider(self.root/'home',self.root)
        with patch.dict('os.environ',{'OPENAI_API_KEY':'private','MSB_API_KEY':'private','MSB_BACKEND':'cloud','PYTHONPATH':'evil','HTTP_PROXY':'private'}):
            env=provider.environment(self.root/'job')
        self.assertEqual(env['MSB_BACKEND'],'local')
        for key in ['OPENAI_API_KEY','MSB_API_KEY','PYTHONPATH','HTTP_PROXY']:self.assertNotIn(key,env)
        self.assertIn('-I',provider._command('run','request','response'))

    def test_worker_environment_keeps_the_system_folders_the_native_sdk_needs(self):
        provider=MicrosandboxProvider(self.root/'home',self.root)
        with patch.dict('os.environ',{'PROGRAMDATA':'C:\\ProgramData','ALLUSERSPROFILE':'C:\\ProgramData','SYSTEMDRIVE':'C:','PUBLIC':'C:\\Users\\Public'}):
            env=provider.environment(self.root/'job')
        for key in ['PROGRAMDATA','ALLUSERSPROFILE','SYSTEMDRIVE','PUBLIC']:self.assertIn(key,env)
        self.assertEqual(env['USERPROFILE'],str((self.root/'job').resolve()))      # the user's own folders stay hidden

    def test_existing_host_shell_cannot_bypass_sandbox_with_test_command(self):
        import sys
        with patch('subprocess.run') as run:
            out=self.rt.tools.execute('shell','M-SBX','run',{'argv':[sys.executable,'-m','unittest','discover','-s','.']})
        self.assertEqual(out['status'],'blocked')
        self.assertEqual(out['reason'],'project_code_requires_sandbox')
        run.assert_not_called()

    def test_control_master_dispatches_preview(self):
        mission=self.rt.brain.create_mission('Preview isolated development')
        result=self.rt.control.execute(mission,{'action':'tool_call','tool':'sandbox','operation':'preview','args':self.args})
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['tool_result']['plan']['network'],'deny')



class WorkerCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from types import SimpleNamespace as NS
        self.NS=NS
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.p=GuppiPolicyForTest()
        self.request={'policy':self.p,'job_id':'SBX-test','source':str(self.root),'commands':[['python3','x.py']],
                      'exports':[],'job_root':str(self.root)}
        self.created=[];self.stopped=[];self.exec_calls=[];self.kill_calls=[]
        outer=self
        class Handle:
            def __aiter__(self):return self
            async def __anext__(self):
                if getattr(self,'sent',False):raise StopAsyncIteration
                self.sent=True;return NS(data=b'output')
            async def wait(self):return 0,True
            async def kill(self):outer.kill_calls.append('kill')
        self.mkdirs=[];self.written={};self.plain_execs=[];self.share_writable=False
        class FS:
            async def mkdir(self,path):outer.mkdirs.append(path)
            async def write(self,path,data):outer.written[path]=data
        class Guest:
            fs=FS()
            async def exec(self,*args,**kw):
                outer.plain_execs.append((args,kw))
                return NS(success=kw.get('user')!='65534' or outer.share_writable)   # the guest's write probe on /.msb must fail
            async def exec_stream(self,*args,**kw):outer.exec_calls.append((args,kw));return Handle()
            async def stop(self,**kw):outer.stopped.append(kw)
        class Sandboxes:
            @staticmethod
            async def create(name,**kw):outer.created.append(kw);return Guest()
            @staticmethod
            async def remove(name):pass
        class Images:
            @staticmethod
            async def get(name):return NS(manifest_digest='sha256:'+'a'*64)
            @staticmethod
            def oci(ref,**kw):return (ref,kw)
        class Limits:
            def __getattr__(self,name):return lambda value:(name,value)
        self.sdk=NS(Sandbox=Sandboxes,Image=Images,RootDisk=NS(tmpfs=lambda x:('tmpfs',x)),
                    Network=NS(none=lambda:'deny'),SecurityProfile=NS(RESTRICTED='restricted'),
                    PullPolicy=NS(NEVER='never'),Rlimit=Limits())

    async def asyncTearDown(self):self.tmp.cleanup()

    async def test_worker_constructs_offline_unmounted_guest_and_cleans_up(self):
        from guppi_runtime.sandbox.worker import run_job
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'PASS');self.assertTrue(result['cleanup_confirmed'])
        kw=self.created[0]
        self.assertEqual(kw['network'],'deny');self.assertEqual(kw['pull_policy'],'never')
        self.assertEqual(kw['volumes'],{});self.assertEqual(kw['secrets'],[])
        self.assertFalse(kw['detached']);self.assertTrue(kw['ephemeral'])
        self.assertEqual(kw['cpus'],2);self.assertEqual(kw['memory'],1024)
        self.assertEqual(self.exec_calls[0][1]['user'],'65534')
        self.assertIn(('nproc',64),self.exec_calls[0][1]['rlimits'])
        self.assertEqual(len(self.stopped),1)

    async def test_runtime_share_is_locked_before_any_guest_command(self):
        from guppi_runtime.sandbox.worker import run_job
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'PASS')
        calls=[(a[0],a[1],kw.get('user')) for a,kw in self.plain_execs]
        self.assertIn(('/bin/chmod',['0700','/.msb'],None),calls)
        self.assertEqual(calls[-1][2],'65534')                        # the lock is proven with the guest user, last before commands

    async def test_guest_command_never_runs_when_the_share_stays_writable(self):
        from guppi_runtime.sandbox.worker import run_job
        self.share_writable=True
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'FAILED');self.assertIn('runtime_share_writable_by_guest',result['error'])
        self.assertEqual(self.exec_calls,[]);self.assertTrue(result['cleanup_confirmed'])

    async def test_sandbox_name_is_short_and_stable(self):
        from guppi_runtime.sandbox.worker import sandbox_name
        long_id='SBX-96875c51adf94b76921018261c2aadbc'
        self.assertEqual(len(sandbox_name(long_id)),18);self.assertEqual(sandbox_name(long_id),sandbox_name(long_id))
        self.assertNotEqual(sandbox_name(long_id),sandbox_name(long_id+'x'))

    async def test_source_tree_is_copied_file_by_file(self):
        from guppi_runtime.sandbox.worker import run_job
        src=self.root/'src';(src/'pkg').mkdir(parents=True);(src/'x.py').write_text('print(1)');(src/'pkg'/'m.py').write_bytes(b'a=1')
        self.request['source']=str(src)
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(self.mkdirs,['/workspace','/workspace/pkg'])
        self.assertEqual(self.written,{'/workspace/pkg/m.py':b'a=1','/workspace/x.py':b'print(1)'})

    async def test_ephemeral_sandbox_gone_after_stop_counts_as_cleaned(self):
        from guppi_runtime.sandbox.worker import run_job
        SandboxNotFoundError=type('SandboxNotFoundError',(Exception,),{})
        async def gone(name):raise SandboxNotFoundError(name)
        self.sdk.Sandbox.remove=gone
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'PASS');self.assertTrue(result['cleanup_confirmed'])

    async def test_cleanup_failure_keeps_the_job_error(self):
        from guppi_runtime.sandbox.worker import run_job
        async def boom(**kw):raise RuntimeError('stop failed')
        async def bad_copy(*a):raise OSError('copy failed')
        guest=await self.sdk.Sandbox.create('n');type(guest).stop=lambda self,**kw:boom(**kw);type(guest.fs).mkdir=lambda self,p:bad_copy(p)
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'CLEANUP_UNCONFIRMED')
        self.assertIn('stop failed',result['error']);self.assertIn('copy failed',result['error'])

    async def test_worker_output_limit_stops_and_discards_exports(self):
        from guppi_runtime.sandbox.worker import run_job
        self.p['max_log_bytes']=1
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'FAILED');self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual(self.kill_calls,['kill']);self.assertEqual(result['exports'],[])

    async def test_worker_startup_failure_does_not_claim_cleanup(self):
        from guppi_runtime.sandbox.worker import run_job
        async def fail(*args,**kw):raise RuntimeError('partial startup')
        self.sdk.Sandbox.create=fail
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'CLEANUP_UNCONFIRMED');self.assertFalse(result['cleanup_confirmed'])

    async def test_failed_start_is_cleaned_only_when_the_sdk_says_not_found(self):
        from guppi_runtime.sandbox.worker import run_job
        async def fail(*args,**kw):raise RuntimeError('sandbox process exited before agent relay became available')
        self.sdk.Sandbox.create=fail
        NotFound=type('SandboxNotFoundError',(Exception,),{})
        async def gone(name):raise NotFound(name)
        self.sdk.Sandbox.get=gone
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'FAILED');self.assertTrue(result['cleanup_confirmed'])
        async def unknown(name):raise RuntimeError('agent unreachable')
        self.sdk.Sandbox.get=unknown
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'CLEANUP_UNCONFIRMED')

    async def test_exit_code_comes_from_the_exited_event(self):
        from guppi_runtime.sandbox.worker import run_job
        NS=self.NS
        class Handle:
            def __init__(self):self.events=[NS(data=b'42\n',code=None),NS(data=None,code=3)]
            def __aiter__(self):return self
            async def __anext__(self):
                if not self.events:raise StopAsyncIteration
                return self.events.pop(0)
            async def wait(self):raise RuntimeError('exec session ended without exit event')
            async def kill(self):pass
        guest=await self.sdk.Sandbox.create('n')
        async def stream(*a,**kw):return Handle()
        type(guest).exec_stream=lambda self,*a,**kw:stream()
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['commands'][0]['exit_code'],3);self.assertIn('guest_command_failed',result['error'])

    async def test_command_timeout_is_enforced_by_the_worker(self):
        import asyncio
        from guppi_runtime.sandbox.worker import run_job
        self.p['command_timeout_seconds']=0.2
        killed=[]
        class Hang:
            def __aiter__(self):return self
            async def __anext__(self):await asyncio.sleep(5)
            async def kill(self):killed.append(1)
        guest=await self.sdk.Sandbox.create('n')
        async def stream(*a,**kw):return Hang()
        type(guest).exec_stream=lambda self,*a,**kw:stream()
        result=await run_job(self.request,self.sdk)
        self.assertTrue(result['commands'][0]['timed_out']);self.assertEqual(killed,[1])
        self.assertIn('guest_command_timeout',result['error']);self.assertTrue(result['cleanup_confirmed'])

    async def test_worker_missing_image_refuses_before_launch(self):
        from guppi_runtime.sandbox.worker import run_job
        async def fail(*args,**kw):raise FileNotFoundError('cache missing')
        self.sdk.Image.get=fail
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'FAILED');self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual(self.created,[])

    async def test_worker_cancel_before_execution_retains_safe_status(self):
        import asyncio
        from guppi_runtime.sandbox.worker import supervise
        async def hang(*args,**kw):await asyncio.sleep(10)
        self.sdk.Image.get=hang
        (self.root/'cancel').touch()
        result=await supervise(self.request,self.sdk)
        self.assertEqual(result['status'],'CANCELLED');self.assertTrue(result['cleanup_confirmed'])

    async def prepare_guest_tree(self, tree, files):
        NS=self.NS
        guest=await self.sdk.Sandbox.create('n')
        async def lst(path): return tree[path]
        async def stat(path): return NS(kind='file' if path in files else 'directory',size=len(files.get(path,b'')))
        async def read_stream(path):
            async def gen(): yield files[path]
            return gen()
        guest.fs.list=lst;guest.fs.stat=stat;guest.fs.read_stream=read_stream

    async def test_export_dirs_refused_unless_the_policy_allows_them(self):
        from guppi_runtime.sandbox.worker import run_job
        self.request['export_dirs']=['out']
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'FAILED');self.assertIn('export_dirs_disabled_by_policy',result['error']);self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual(result['exports'],[])

    async def test_export_dirs_walk_the_guest_directory_with_the_sdk_and_return_every_file(self):
        import base64
        from guppi_runtime.sandbox.worker import run_job
        NS=self.NS
        self.p.update(allow_export_dirs=True,max_files=5)
        await self.prepare_guest_tree({'/workspace/out':[NS(path='/workspace/out/a.py',kind='file',size=3),NS(path='sub',kind='directory',size=0)],
                                       '/workspace/out/sub':[NS(path='/workspace/out/sub/b.txt',kind='file',size=2)]},
                                      {'/workspace/out/a.py':b'a=1','/workspace/out/sub/b.txt':b'hi'})
        self.request['export_dirs']=['out']
        result=await run_job(self.request,self.sdk)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual({e['path']:base64.b64decode(e['data_base64']) for e in result['exports']},{'out/a.py':b'a=1','out/sub/b.txt':b'hi'})

    async def test_export_dirs_fail_closed_on_symlinks_special_files_counts_and_bad_paths(self):
        from guppi_runtime.sandbox.worker import run_job
        NS=self.NS
        self.p.update(allow_export_dirs=True,max_files=2)
        for kind,expected in (('symlink','guest_export_symlink'),('other','guest_export_special_file')):
            await self.prepare_guest_tree({'/workspace/out':[NS(path='a.py',kind='file',size=1),NS(path='x',kind=kind,size=0)]},{'/workspace/out/a.py':b'a'})
            self.request['export_dirs']=['out']
            result=await run_job(self.request,self.sdk)
            self.assertEqual(result['status'],'FAILED',kind);self.assertIn(expected,result['error']);self.assertEqual(result['exports'],[])
        await self.prepare_guest_tree({'/workspace/out':[NS(path='a.py',kind='file',size=1),NS(path='b.py',kind='file',size=1),NS(path='c.py',kind='file',size=1)]},
                                      {'/workspace/out/%s.py'%n:b'x' for n in 'abc'})
        result=await run_job(self.request,self.sdk);self.assertIn('guest_export_file_count_limit',result['error'])
        for bad in ('../etc','/etc','out//x'):
            self.request['export_dirs']=[bad]
            result=await run_job(self.request,self.sdk);self.assertIn('guest_export_dir_invalid',result['error'],bad)
        self.assertTrue(result['cleanup_confirmed'])


def GuppiPolicyForTest():
    return {'image':'test@sha256:'+'a'*64,'cpus':2,'memory_mib':1024,'root_disk_mib':256,
            'job_timeout_seconds':120,'command_timeout_seconds':30,'cleanup_timeout_seconds':5,
            'max_processes':64,'max_file_bytes':1024,'max_export_bytes':1024,'max_log_bytes':32768}

if __name__=='__main__':unittest.main()
