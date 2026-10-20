import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.uix_server import UIXHub,make_server
from guppi_runtime.selfdev.candidate_acceptance import preview,command
from guppi_runtime.projects import ProjectRegistry
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH=Path(__file__).resolve().parents[2]/'architecture/GUPPI_Architecture_v1.17_RUNTIME_SYNC'
class WorkflowCase(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.rt=GuppiRuntime(Path(self.tmp.name),ARCH)
  self.source=self.rt.filesystem_tool.root/'demo';self.source.mkdir();self.old='value = 1\r\n';self.new='value = 2\n';(self.source/'app.py').write_bytes(self.old.encode())
  req={'project_path':'demo','files':['app.py'],'changes':[{'path':'app.py','expected_sha256':hashlib.sha256(self.old.encode()).hexdigest(),'content':self.new}]}
  m=self.rt.brain.create_mission('Ändere Code als Kandidat',inputs=req);self.m=self.rt.brain.run(m['identity']['mission_id']);self.mid=m['identity']['mission_id']
 def test_missing_tests_and_simulation_refuse_acceptance(self):
  with self.assertRaises(ValueError):preview(self.rt,self.m)
  self.assertEqual((self.source/'app.py').read_bytes(),self.old.encode())
 def qualified(self):return patch('guppi_runtime.selfdev.candidate_acceptance.test_qualification',return_value={'qualification':'TEST_CONTRACT_FIXTURE'})
 def approved(self,op,plan):
  gate=command(self.rt,self.mid,op,plan)['gate'];token=self.rt.guard.approve(gate);m=self.rt.missions.load(self.mid);m['execution']['approval_token']=token;self.rt.missions.save(m)
  return command(self.rt,self.mid,op,plan)
 def test_guarded_accept_and_rollback_preserve_bytes(self):
  with self.qualified():
   plan=preview(self.rt,self.m);out=self.approved('accept',plan);self.assertEqual(out['status'],'completed')
   self.assertEqual((self.source/'app.py').read_bytes(),self.new.encode())
   m=self.rt.missions.load(self.mid);plan=preview(self.rt,m,'rollback');out=self.approved('rollback',plan)
   self.assertEqual(out['status'],'completed');self.assertEqual((self.source/'app.py').read_bytes(),self.old.encode())
 def test_changed_source_refuses_approved_plan(self):
  with self.qualified():
   plan=preview(self.rt,self.m);(self.source/'app.py').write_text('changed')
   with self.assertRaises(ValueError):command(self.rt,self.mid,'accept',plan)
 def test_replay_refused_after_acceptance(self):
  with self.qualified():
   plan=preview(self.rt,self.m);self.approved('accept',plan)
   with self.assertRaises(ValueError):command(self.rt,self.mid,'accept',plan)
 def test_rollback_refuses_unrelated_edits(self):
  with self.qualified():
   plan=preview(self.rt,self.m);self.approved('accept',plan);(self.source/'app.py').write_text('later edit')
   with self.assertRaises(ValueError):preview(self.rt,self.rt.missions.load(self.mid),'rollback')
 def test_write_interruption_stays_review_required(self):
  with self.qualified():
   plan=preview(self.rt,self.m)
   import guppi_runtime.selfdev.candidate_acceptance as ca
   original=ca.os.replace
   def fail(src,dst):
    if Path(dst)==self.source/'app.py':raise OSError('fixture interrupted')
    return original(src,dst)
   with patch('guppi_runtime.selfdev.candidate_acceptance.os.replace',side_effect=fail):out=self.approved('accept',plan)
   self.assertEqual(out['acceptance']['status'],'REVIEW_REQUIRED')
   with self.assertRaises(ValueError):command(self.rt,self.mid,'accept',plan)
 def test_project_records_are_real_and_persistent(self):
  registry=ProjectRegistry(self.rt);item=registry.create('<img src=x>');self.assertTrue((self.rt.filesystem_tool.root/item['workspace_path']).is_dir())
  self.assertEqual(ProjectRegistry(self.rt).get(item['project_id']),item)
 def test_ui_require_exact_gate_and_bounded_steps(self):
  hub=UIXHub(Path(self.tmp.name)/'hub',ARCH)
  for payload in [{'mission_id':'M-X','max_steps':-1},{'mission_id':'M-X','max_steps':1000}]:
   with self.assertRaises(ValueError):hub.run_mission(payload)
  with self.assertRaises(ValueError):hub.approve_gate({'mission_id':'M-X'})
