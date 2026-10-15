import sys, unittest
from pathlib import Path
import env_skip
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
import cuda_crash_hunt as hunt
import small_team as st
from guppi_runtime.llama_server_runtime import build_command

class CrashHuntTests(unittest.TestCase):
 @env_skip.needs_pc_files
 def test_every_variant_builds_a_valid_server_command(self):
  for name, spec in hunt.VARIANTS.items():
   server = {'gguf': str(st.CODER['gguf']), **spec.get('server', {})}
   if 'flash_attn' in spec: server['flash_attn'] = spec['flash_attn']
   argv = build_command(Path('llama-server.exe'), gguf=server['gguf'], context=spec.get('context', st.CONTEXT), host='127.0.0.1', port=8089, alias='x',
                        flash_attn=server.get('flash_attn', 'on'), ubatch=server.get('ubatch'))
   self.assertIn('-fa', argv, name)
   if spec.get('flash_attn') == 'off': self.assertEqual(argv[argv.index('-fa') + 1], 'off')
 def test_baseline_changes_nothing_and_the_env_variants_name_a_real_switch(self):
  self.assertEqual(hunt.VARIANTS['baseline'], {})
  self.assertEqual(hunt.VARIANTS['graphs_off']['env'], {'GGML_CUDA_DISABLE_GRAPHS': '1'})
 @env_skip.needs_pc_files
 def test_engine_variant_exists_on_disk(self):
  self.assertTrue((hunt.RUNTIME.parent / 'engines' / 'llama.cpp' / hunt.VARIANTS['engine_b11160']['engine_build']).is_dir())

class ModelsTests(unittest.TestCase):
 @env_skip.needs_pc_files
 def test_model_specs_and_variants_cover_the_three_models(self):
  project = Path(__file__).resolve().parents[2] / 'workspace' / 'GUPPI_OS'
  for name, workload in (('jan', 'repair'), ('swe', 'review'), ('qwen3coder', 'repair')):
   spec = hunt.model_spec(name, project)
   self.assertEqual(spec['workload'], workload); self.assertTrue(Path(spec['server']['gguf']).is_file(), name)
  self.assertEqual(hunt.model_spec('qwen3coder', project)['server']['n_cpu_moe'], 44)
  q6 = hunt.model_spec('coder.llama_qwen35_q6', project); self.assertEqual((q6['alias'], q6['workload'], q6['recipe_id']), ('qwen3.5-9b-q6', 'repair', 'coder.llama_qwen35_q6')); self.assertTrue(Path(q6['server']['gguf']).is_file())   # gpt-oss moved to quarantine 2026-10-12 (RM-20261012T055725)
  for v in hunt.ALL_VARIANTS.split(','): self.assertIn(v, hunt.VARIANTS)
 def test_speed_probe_takes_the_servers_own_timings(self):
  import json, io, urllib.request
  class R:
   def __enter__(s): return s
   def __exit__(s, *a): return False
   def read(s): return json.dumps({'timings': {'prompt_n': 1300, 'prompt_per_second': 500.0, 'predicted_per_second': 30.0}}).encode()
  class RT: endpoint = 'http://127.0.0.1:1'
  orig = urllib.request.urlopen; urllib.request.urlopen = lambda *a, **k: R()
  try: out = hunt.speed_probe(RT(), 'm')
  finally: urllib.request.urlopen = orig
  self.assertEqual(out, {'prompt_tokens': 1300, 'prompt_tps': 500.0, 'gen_tps': 30.0})

if __name__ == '__main__':
 unittest.main()
