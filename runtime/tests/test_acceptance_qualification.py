import unittest,json
from types import SimpleNamespace
from unittest.mock import Mock,patch
from guppi_runtime.selfdev.candidate_acceptance import test_qualification
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests
ARGV=['python3','-m','unittest','discover','-s','tests','-v']
class QualificationTests(unittest.TestCase):
 def run_qualification(self,output='Ran 3 tests in 0.1s\n\nOK\n',qualification='MICROVM_RESULT',commands=None):
  sandbox=SimpleNamespace(verify=Mock(return_value={'verification':'PASS','qualification':qualification}),receipt=Mock(return_value=json.dumps({'commands':commands if commands is not None else [{'argv':ARGV,'output':output}]})))
  rt=SimpleNamespace(sandbox=sandbox)
  m={'identity':{'mission_id':'M-TEST'},'execution':{'candidate_test':{'status':'FINISHED','preparation_sha256':'sha','plan_digest':'digest','job_id':'J-TEST','report_sha256':'report'}}}
  with patch('guppi_runtime.selfdev.candidate_acceptance.contract',return_value=({'plan_digest':'digest'},'sha')):return test_qualification(rt,m)
 def test_nonempty_suite(self):self.assertEqual(self.run_qualification()['test_counts'],[3])
 def test_zero_tests(self):
  with self.assertRaises(ValueError):self.run_qualification('Ran 0 tests in 0.0s\nOK\n')
 def test_simulation(self):
  with self.assertRaises(ValueError):self.run_qualification(qualification='SIMULATED_INTERFACE')
 def test_no_commands(self):
  with self.assertRaises(ValueError):self.run_qualification(commands=[])
 def test_repro_step_before_the_tests_is_allowed(self):
  repro={'argv':['python3','tests/_guppi_repro.py'],'output':'REPRO input x\n'}
  ok={'argv':ARGV,'output':'Ran 3 tests in 0.1s\n\nOK\n'}
  self.assertEqual(self.run_qualification(commands=[repro,ok])['test_counts'],[3])
 def test_repro_step_alone_or_other_commands_are_not_enough(self):
  repro={'argv':['python3','tests/_guppi_repro.py'],'output':''}
  ok={'argv':ARGV,'output':'Ran 3 tests in 0.1s\n\nOK\n'}
  with self.assertRaises(ValueError):self.run_qualification(commands=[repro])
  with self.assertRaises(ValueError):self.run_qualification(commands=[dict(repro,argv=repro['argv']+['--x']),ok])
 def test_failed_summary(self):
  with self.assertRaises(ValueError):self.run_qualification('Ran 2 tests in 0.1s\nFAILED\n')
