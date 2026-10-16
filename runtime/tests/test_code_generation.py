import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.projects import ProjectRegistry
from guppi_runtime.code_generation import generate
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests
ARCH=Path(__file__).resolve().parents[2]/'architecture/GUPPI_Architecture_v1.17_RUNTIME_SYNC'
class GenerationTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.rt=GuppiRuntime(Path(t.name),ARCH)
  self.project=ProjectRegistry(self.rt).create('Demo');self.file=self.rt.filesystem_tool.root/self.project['workspace_path']/'app.py';self.file.write_text('x = 1\n')
  t=self.file.parent/'tests';t.mkdir();(t/'test_app.py').write_text('import unittest\n')
  self.m=self.rt.brain.create_mission('Ändere Code als Kandidat')
 def output(self,data):return patch.object(self.rt.control,'execute',return_value={'status':'completed','model_result':{'content':json.dumps(data)}})
 def test_candidate_never_changes_original(self):
  with self.output({'changes':[{'path':'app.py','content':'x = 2\n'}]}):out=generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'])
  self.assertEqual(out['qualification'],'GENERATED_NOT_TESTED');self.assertEqual(self.file.read_text(),'x = 1\n')
  self.assertEqual(out['candidate_request']['changes'][0]['path'],'app.py')
 def test_repro_harness_runs_first_only_when_selected_and_stays_read_only(self):
  with self.output({'changes':[{'path':'app.py','content':'x = 2\n'}]}):out=generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'])
  self.assertEqual(out['candidate_request']['test_commands'],[['python3','-m','unittest','discover','-s','tests','-v']])
  (self.file.parent/'tests'/'_guppi_repro.py').write_text('print("REPRO all tests pass")\n')
  files=['app.py','tests/test_app.py','tests/_guppi_repro.py']
  with self.output({'changes':[{'path':'app.py','content':'x = 2\n'}]}):out=generate(self.rt,self.m,self.project,files)
  self.assertEqual(out['candidate_request']['test_commands'],[['python3','tests/_guppi_repro.py'],['python3','-m','unittest','discover','-s','tests','-v']])
  with self.output({'changes':[{'path':'tests/_guppi_repro.py','content':'import os\n'}]}):
   with self.assertRaises(ValueError):generate(self.rt,self.m,self.project,files)
 def test_invented_path_refused(self):
  with self.output({'changes':[{'path':'outside.py','content':'x=2'}]}):
   with self.assertRaises(ValueError):generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'])
 def test_invalid_model_schema_refused(self):
  with self.output([]):
   with self.assertRaises(ValueError):generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'])
 def test_target_names_the_model_and_one_code_fence_is_tolerated(self):
  fenced='```json\n'+json.dumps({'changes':[{'path':'app.py','content':'x = 2\n'}]})+'\n```'
  with patch.object(self.rt.control,'execute',return_value={'status':'completed','model_result':{'content':fenced}}) as ex:
   out=generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'],target={'provider':'llama-cpp-server','model':'gpt-oss-20b','reasoning_effort':'low','max_tokens':6000})
  req=ex.call_args[0][1]
  self.assertEqual((req['provider'],req['model'],req['reasoning_effort'],req['max_tokens']),('llama-cpp-server','gpt-oss-20b','low',6000))
  self.assertEqual(out['status'],'completed')
 def test_text_around_the_json_is_still_refused(self):
  with patch.object(self.rt.control,'execute',return_value={'status':'completed','model_result':{'content':'Here you go: {"changes":[]}'}}):
   with self.assertRaises(ValueError):generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'])
 def test_tests_must_be_selected_so_they_reach_the_vm(self):
  with self.output({'changes':[{'path':'app.py','content':'x = 2\n'}]}):
   with self.assertRaises(ValueError) as ctx:generate(self.rt,self.m,self.project,['app.py'])
  self.assertIn('test_files_must_be_selected',str(ctx.exception))
 def test_selected_tests_may_not_be_changed(self):
  with self.output({'changes':[{'path':'tests/test_app.py','content':'pass\n'}]}):
   with self.assertRaises(ValueError):generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'])
 def test_answer_lost_to_thinking_is_named(self):
  with patch.object(self.rt.control,'execute',return_value={'status':'completed','model_result':{'content':'','truncated':True}}):
   with self.assertRaises(ValueError) as ctx:generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'])
  self.assertIn('model_answer_truncated',str(ctx.exception))
  with patch.object(self.rt.control,'execute',return_value={'status':'completed','model_result':{'content':'{"changes": [','truncated':True}}):
   with self.assertRaises(ValueError) as ctx:generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'])
  self.assertIn('model_output_not_json:truncated',str(ctx.exception))
 def test_source_limit_grows_with_the_window(self):
  from guppi_runtime.code_generation import source_limit
  self.assertEqual(source_limit(None,4096),65536)
  self.assertEqual(source_limit(49152,16000),(49152-16000-2048)*3)
  self.assertEqual(source_limit(8192,4096),65536)
  self.assertEqual(source_limit(1048576,8000),262144)
  for bad in (True,1000,'49152',2**21):
   with self.assertRaises(ValueError):source_limit(bad,4096)
 def test_big_selection_needs_a_big_window_and_the_window_is_not_sent(self):
  root=self.file.parent;(root/'app.py').write_text('x = 1\n'+'#'*40000+'\n');(root/'ui.py').write_text('#'*30000+'\n')
  files=['app.py','ui.py','tests/test_app.py']
  with self.output({'changes':[{'path':'app.py','content':'x = 2\n'}]}):
   with self.assertRaises(ValueError) as ctx:generate(self.rt,self.m,self.project,files)
  self.assertIn('model_source_context_limit',str(ctx.exception))
  with patch.object(self.rt.control,'execute',return_value={'status':'completed','model_result':{'content':json.dumps({'changes':[{'path':'app.py','content':'x = 2\n'}]})}}) as ex:
   out=generate(self.rt,self.m,self.project,files,target={'model':'gpt-oss-20b','max_tokens':8000,'context_window':49152})
  self.assertEqual(out['status'],'completed');self.assertNotIn('context_window',ex.call_args[0][1])
 def test_rework_feedback_reaches_the_model_but_not_the_mission_objective(self):
  before=self.m['objective']['current']
  with patch.object(self.rt.control,'execute',return_value={'status':'completed','model_result':{'content':json.dumps({'changes':[{'path':'app.py','content':'x = 2\n'}]})}}) as ex:
   generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'],feedback='REPRO input http://localhost:8080/ failed')
  sent=json.loads(ex.call_args[0][1]['messages'][1]['content'].split('\n\nAnswer format')[0])
  self.assertEqual(sent['previous_attempt'],'REPRO input http://localhost:8080/ failed')
  self.assertEqual(self.m['objective']['current'],before)
  for bad in (123,'x'*32001):
   with self.assertRaises(ValueError):generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'],feedback=bad)
 def test_matching_lessons_from_the_knowledge_base_reach_the_model(self):
  self.rt.knowledge.add_lesson('port','urlparse().port raises ValueError itself',triggers=['urlparse'])
  self.rt.knowledge.add_lesson('other','never shown',triggers=['frobnicate'])
  self.file.write_text('from urllib.parse import urlparse\n')
  with patch.object(self.rt.control,'execute',return_value={'status':'completed','model_result':{'content':json.dumps({'changes':[{'path':'app.py','content':'x = 2\n'}]})}}) as ex:
   generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'])
  sent=json.loads(ex.call_args[0][1]['messages'][1]['content'].split('\n\nAnswer format')[0])
  self.assertEqual(sent['lessons'],['urlparse().port raises ValueError itself'])
  with self.assertRaises(ValueError):self.rt.knowledge.add_lesson('x','y',triggers=[])
 def test_target_may_set_temperature_within_bounds(self):
  with patch.object(self.rt.control,'execute',return_value={'status':'completed','model_result':{'content':json.dumps({'changes':[{'path':'app.py','content':'x = 2\n'}]})}}) as ex:
   generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'],target={'model':'gpt-oss-20b','temperature':1.0})
  self.assertEqual(ex.call_args[0][1]['temperature'],1.0)
  for bad in (-0.1,2.5,'1',True):
   with self.assertRaises(ValueError):generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'],target={'temperature':bad})
 def test_unknown_target_keys_refused(self):
  with self.assertRaises(ValueError):generate(self.rt,self.m,self.project,['app.py','tests/test_app.py'],target={'messages':[]})
