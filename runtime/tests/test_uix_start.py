import unittest
from guppi_runtime import uix_start
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real PowerShell / taskkill in tests

def row(pid,parent,name,cmd):return {'ProcessId':pid,'ParentProcessId':parent,'Name':name,'ExecutablePath':'','CommandLine':cmd}
UIX='python.exe -B -m guppi_runtime.uix_server --root x'

class UIXStartTests(unittest.TestCase):
 def run_pre(self,rows,own,leftovers=None,**kw):
  said,stopped=[],[]
  orig=uix_start.gpu_preflight.guppi_llama_servers
  uix_start.gpu_preflight.guppi_llama_servers=lambda run=None:leftovers or {}
  self.addCleanup(setattr,uix_start.gpu_preflight,'guppi_llama_servers',orig)
  code=uix_start.preflight(rows,own,say=said.append,stop=lambda pid,run:stopped.append(pid),**kw)
  return code,said,stopped
 def test_off_windows_the_start_has_no_process_inventory_and_still_starts(self):
  # 2026-10-14: start for Mac users. Without PowerShell there are no rows, nothing is stopped, and preflight lets the start go on.
  calls=[]
  self.assertEqual(uix_start.process_rows(run=lambda *a,**k:calls.append(a),platform='darwin'),[])
  self.assertEqual(uix_start.process_rows(run=lambda *a,**k:calls.append(a),platform='linux'),[])
  self.assertEqual(calls,[])
  code,said,stopped=self.run_pre([],{1,2})
  self.assertEqual((code,stopped),(0,[]))
  root=__import__('pathlib').Path(__file__).resolve().parents[2]
  for name in ('start_sedra.sh','START_SEDRA.command'):
   text=(root/name).read_bytes()
   self.assertTrue(text.startswith(b'#!/bin/sh'),name);self.assertNotIn(b'\r\n',text,name+' must keep LF line endings for sh')
  self.assertIn('guppi_runtime.uix_start',(root/'start_sedra.sh').read_text(encoding='utf-8'))
 def test_second_start_is_refused_but_own_launcher_is_not_counted(self):
  rows=[row(10,1,'python.exe',UIX),row(11,10,'python.exe',UIX),row(20,1,'python.exe',UIX)]
  code,said,stopped=self.run_pre(rows,{11,10})
  self.assertEqual(code,3);self.assertIn('20',said[0]);self.assertEqual(stopped,[])
  code,said,stopped=self.run_pre(rows,{11,10},replace=True)
  self.assertEqual((code,stopped),(0,[20]))
 def test_orphan_llama_server_is_stopped_and_one_with_live_starter_is_not(self):
  info={'name':'llama-server.exe','path':'','cmd':'llama-server.exe --alias gpt-oss-20b'}
  rows=[row(30,999,'llama-server.exe',info['cmd']),row(31,40,'llama-server.exe',info['cmd']),row(40,1,'python.exe','python benchmarks/run.py')]
  code,said,stopped=self.run_pre(rows,{1},leftovers={30:info,31:info})
  self.assertEqual((code,stopped),(0,[30]));self.assertTrue(any('PID 31' in s and 'unberührt' in s for s in said))
 def test_nothing_running_changes_nothing(self):
  self.assertEqual(self.run_pre([],{1})[0::2],(0,[]))
 def test_the_starter_uses_the_standard_start(self):
  from pathlib import Path
  root=Path(__file__).resolve().parents[2]
  for name in ('START_SEDRA.bat','start_sedra.sh'):
   self.assertIn('guppi_runtime.uix_start',(root/name).read_text(encoding='utf-8'))
  for old in ('ERSTER_START.bat','START_GUPPI.bat','GUPPI_EINRICHTEN_UND_STARTEN.bat'):
   self.assertFalse((root/old).exists(),old+' ist durch START_SEDRA.bat ersetzt')

 def test_start_sedra_knows_overview_and_a_direct_shell(self):
  """START_SEDRA (Übersicht) · START_SEDRA cockpit (direkt, nur dieser Start) · --gewaehlt (uix.yaml). 15.10.2026, 09:21."""
  from pathlib import Path
  root=Path(__file__).resolve().parents[2]
  bat=(root/'START_SEDRA.bat').read_text(encoding='utf-8'); sh=(root/'start_sedra.sh').read_text(encoding='utf-8')
  for text in (bat,sh):
   self.assertIn('--uebersicht',text); self.assertIn('--shell',text); self.assertIn('--gewaehlt',text)
  self.assertEqual(uix_start.main(['--root','x','--architecture','y','--shell','a','--uebersicht']),2,'beides zugleich geht nicht')

 def test_the_start_menu_lists_only_choosable_shells(self):
  """START_SEDRA fragt nach der Oberfläche; die Liste kommt aus uix_start --liste (ohne Vorlagen und den Einstieg)."""
  ids=[sid for sid,_ in uix_start.list_shells()]
  self.assertIn('cockpit',ids); self.assertIn('gateway-studio',ids)
  self.assertNotIn('start',ids); self.assertFalse([i for i in ids if i.startswith('_')])
  self.assertEqual(uix_start.main(['--liste']),0)

 def test_a_running_uix_is_described_with_its_folder(self):
  rows=[{'ProcessId':'4711','ExecutablePath':r'C:\SEDRA\GUPPI_Runtime_v1.20_Build_009\runtime\portable\python\current\python.exe','CommandLine':'python -m guppi_runtime.uix_start'}]
  self.assertEqual(uix_start.describe_running(rows,4711),r'PID 4711, aus C:\SEDRA\GUPPI_Runtime_v1.20_Build_009')
  self.assertIn('Ordner unbekannt',uix_start.describe_running([],1))
  said=[]
  self.assertEqual(uix_start.preflight(rows+[{'ProcessId':'4711','CommandLine':'python -m guppi_runtime.uix_server'}],{1},say=said.append),3)
  self.assertTrue(any('Build_009' in t for t in said),said)
