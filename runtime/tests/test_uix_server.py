import unittest, unittest.mock, tempfile, threading, json, http.client, re, shutil, subprocess
from pathlib import Path
from guppi_runtime.uix_server import UIXHub, make_server
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests
UIX_DIR=Path(__file__).parents[1]/'src/guppi_runtime/uix'
def page_source():
 """The page as the browser gets it: markup, styles and every script file (the UIX is split into uix/css and uix/js)."""
 parts=[(UIX_DIR/'retro_desktop.html').read_text(encoding='utf-8')]
 parts+=[f.read_text(encoding='utf-8') for f in sorted((UIX_DIR/'css').glob('*.css'))+sorted((UIX_DIR/'js').glob('*.js'))]
 return chr(10).join(parts)
ARCH=Path(__file__).resolve().parents[2]/'architecture/GUPPI_Architecture_v1.17_RUNTIME_SYNC'
class UIXTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.hub=UIXHub(Path(self.tmp.name)/'project',ARCH)
 def test_runtime_status(self):
  status=self.hub.status();self.assertIn(status['system_state'],{'READY','SAFE_MODE'})
  self.assertGreaterEqual(status['capability_router']['skills'],1)
  self.assertFalse(status['development_environment']['unsafe_host_fallback'])
 def test_chat_plans_without_execution(self):
  out=self.hub.create_chat_mission({'intent':'Create a GUPPI demo artifact'})
  m=self.hub.runtime.missions.load(out['mission']['mission_id'])
  self.assertIn(m['lifecycle']['phase'],{'READY','PAUSED'});self.assertEqual(m['execution']['results'],[])
 def test_real_route(self):
  route=self.hub.route({'intent':'Inspect a software project and its files'})
  self.assertIn(route['status'],{'resolved','partial'});self.assertIn('tools',route)
 def test_project_context_and_unknown_project(self):
  p=self.hub.new_project({'name':'Example'})
  out=self.hub.create_chat_mission({'intent':'Inspect project','project_id':p['project_id']})
  self.assertEqual(self.hub.mission_details({'mission_id':out['mission']['mission_id']})['context']['refs'][0]['project_id'],p['project_id'])
  count=len(self.hub.missions())
  with self.assertRaises(ValueError):self.hub.create_chat_mission({'intent':'Inspect','project_id':'unknown'})
  self.assertEqual(len(self.hub.missions()),count)
 def test_http_origin_token_body_limits(self):
  server,url=make_server(self.hub);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
  token=url.split('#')[1]
  def request(method,path,body=None,headers=None):
   c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
   try:
    c.request(method,path,body,headers or {});res=c.getresponse();data=res.read();return res.status,data
   finally:c.close()
  self.assertEqual(request('GET','/api/missions')[0],403)
  h={'X-GUPPI-Token':token}
  self.assertEqual(request('GET','/api/missions',headers=h)[0],200)
  self.assertEqual(request('GET','/api/missions',headers=dict(h,Origin='http://evil.example'))[0],403)
  self.assertEqual(request('GET','/api/missions',headers=dict(h,Host='evil.example'))[0],403)
  self.assertEqual(request('POST','/api/chat',headers=dict(h,**{'Content-Length':'-1'}))[0],400)
  self.assertEqual(request('POST','/api/chat','[]',h)[0],400)
 def test_persisted_intent_html_is_escaped(self):
  html=page_source()
  self.assertIn("escapeHtml(String(m.intent||m.objective||''))",html)
 def test_the_cockpit_is_served_and_the_old_desktop_stays_in_the_archive(self):
  # Since Build 7 '/' is the Cockpit: it carries no layout of its own, it loads the UI contract, which loads the active shell.
  # The desktop of Build 6 is reachable under '/retro' with the same runtime (docs/BUILD_7_DESK_2026-10-14.md).
  server,url=make_server(self.hub);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
  def get(path,token=None):
   c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
   try:
    c.request('GET',path,headers={'X-GUPPI-Token':token} if token else {});res=c.getresponse();return res.status,res.read().decode('utf-8')
   finally:c.close()
  status,body=get('/')
  self.assertEqual(status,200)
  self.assertIn('/uix/ui/loader.js',body)
  self.assertIn('/uix/ui/start.js',body)
  self.assertNotIn('<script>',body)                              # no inline code: CSP self, top-level code only in start.js
  status,retro=get('/retro')
  self.assertEqual(status,200)
  self.assertIn('/uix/js/main.js',retro)
  status,loader=get('/uix/ui/loader.js')                         # a <script src> carries no token: the contract's files are code, no data
  self.assertEqual(status,200)
  self.assertIn('sedraLoader',loader)
  status,manifest=get('/uix/manifest',url.split('#')[1])
  self.assertEqual(status,200)
  self.assertIn('"cockpit"',manifest)
  self.assertEqual(get('/uix/manifest')[0],403)                  # everything that carries data still needs the token
 def test_no_project_greeting_and_single_open_bridge(self):
  html=page_source()
  self.assertIn('Noch kein Projekt gewählt',html);self.assertIn('let activeProject = null;',html)
  self.assertNotIn("'GUPPI OS';\n",html.split('let activeProject')[1][:80])
  self.assertEqual(html.count('function openBridge('),1)
  self.assertEqual(html.count('function closeWindow('),1)
 def test_chat_without_project_id_gives_mission(self):
  out=self.hub.create_chat_mission({'intent':'Hallo GUPPI','project_id':None})
  self.assertTrue(out['mission']['mission_id'])
 def test_audit_view_is_read_only_and_compact(self):
  self.hub.create_chat_mission({'intent':'Audit probe'})
  view=self.hub.audit_view()
  self.assertIs(view['chain_ok'],True);self.assertIsInstance(view['events'],list)
  for e in view['events']:self.assertEqual(set(e),{'event_id','timestamp','event_type','component','mission_id'})
 def test_chat_card_has_run_and_gate_controls(self):
  html=page_source()
  for needle in ('function renderMission(','/api/mission/run','/api/mission/approve','function candidateSteps(','/api/audit'):self.assertIn(needle,html)
 def test_run_after_chat_completes_mission(self):
  mid=self.hub.create_chat_mission({'intent':'Create a GUPPI demo artifact'})['mission']['mission_id']
  out=self.hub.run_mission({'mission_id':mid,'max_steps':20})
  self.assertEqual(out['pending_gates'],[]);self.assertEqual(self.hub.mission_details({'mission_id':mid})['lifecycle']['phase'],'COMPLETE')

 def test_reject_gate_denies_without_token(self):
  mid=self.hub.create_chat_mission({'intent':'Gate probe'})['mission']['mission_id']
  rt=self.hub.runtime;m=rt.missions.load(mid);gate=rt.guard.create_gate(mid,'write_file','x.txt');m['human_gates']['pending'].append(gate);rt.missions.save(m)
  out=self.hub.reject_gate({'mission_id':mid,'gate_id':gate['gate_id']})
  m=rt.missions.load(mid)
  self.assertEqual(out['status'],'rejected');self.assertEqual(m['human_gates']['pending'],[])
  self.assertEqual(m['human_gates']['resolved'][-1]['resolution']['decision'],'DENY')
  self.assertNotIn('approval_token',m['execution'])
  with self.assertRaises(ValueError):self.hub.reject_gate({'mission_id':mid,'gate_id':gate['gate_id']})
  with self.assertRaises(ValueError):self.hub.reject_gate({'mission_id':mid})
 def test_models_view_and_profile_switch(self):
  view=self.hub.models_view()
  self.assertIn('recipes',view);self.assertIsNone(view['lease']);self.assertIn('loader_enabled',view)
  with self.assertRaises(ValueError):self.hub.use_profile({'name':'does-not-exist'})
  with self.assertRaises(ValueError):self.hub.load_model({})
 def test_load_refused_while_gpu_lease_is_held_by_another(self):
  other=self.hub.lab.try_acquire('someone-else','test round',ttl_s=600);self.assertTrue(other)
  self.addCleanup(self.hub.lab.release,other)
  recipes=self.hub.models_view()['recipes']
  if not recipes or self.hub.runtime.model_loader is None or not self.hub.runtime.model_loader.enabled:self.skipTest('no loader in this test project')
  with self.assertRaises(ValueError):self.hub.load_model({'recipe_id':recipes[0]['id']})
  self.assertIsNone(self.hub.gpu_token)
 def test_models_window_is_wired(self):
  html=page_source()
  for needle in ('id="modelWindow"','function openModels(','/api/models','/api/model/load','/api/model/unload','/api/routing-profile'):self.assertIn(needle,html)
 def test_window_layout_never_outgrows_the_window(self):
  # 2026-10-13: the content was sized with a fixed calc() and overridden by height:100%; focusing the chat input then scrolled the title bar out of the window
  css=(UIX_DIR/'css'/'desktop.css').read_text(encoding='utf-8')
  self.assertIn('.window.active{display:flex}',css)
  self.assertNotIn('calc(100% - 69px)',css)
  for cls in ('.chat-body','.project-layout','.dev-layout','.model-main','.processor'):
   rule=css.split(cls+'{',1)[1].split('}',1)[0]
   self.assertNotIn('height:100%',rule.replace('min-height:100%',''),cls)
 def test_taskbar_has_one_button_per_window(self):
  html=(UIX_DIR/'retro_desktop.html').read_text(encoding='utf-8');js=(UIX_DIR/'js'/'desktop.js').read_text(encoding='utf-8')
  for w in ('deckWindow','guppiWindow','modelWindow','agentWindow'):self.assertIn('class="taskbtn launcher" data-window="'+w+'"',html)      # Build 5: Deck, GUPPI, Werkstatt, Besatzung (+ Projekte without a window)
  self.assertIn(".taskbtn.launcher[data-window=",js);self.assertIn("classList.toggle('open', open)",js)
  self.assertIn('.taskbtn.launcher.open{display:none}',(UIX_DIR/'css'/'desktop.css').read_text(encoding='utf-8'))
 def test_model_without_name_is_shown_by_recipe_id(self):
  js=(UIX_DIR/'js'/'models.js').read_text(encoding='utf-8')
  self.assertIn('function modelName(r)',js);self.assertIn("r.model || r.id",js)
  self.assertNotIn("el('option',null,r.model+",js)
 def test_mission_card_stays_live_while_running(self):
  # 2026-10-13: a long run left a frozen card; now the record is re-read every 3 s and the card redrawn, without a second run button
  js=(UIX_DIR/'js'/'missions.js').read_text(encoding='utf-8')
  self.assertIn('async function runMissionLive(body, mid)',js);self.assertIn('const MISSION_POLL_MS = 3000;',js)
  self.assertIn("()=>runMissionLive(body, mid)",js);self.assertIn('function renderMission(body, m, running)',js)
  self.assertIn("if(!running && !pending.length",js)
  self.assertEqual(js.count('/api/mission/run'),2)      # the chat card (live) and the mission window
 def test_state_colours_come_from_tokens(self):
  # UIX_STYLE_MANIFEST_v0.2.md 3.2: ok/warn/bad and the other meaningful colours are tokens in :root; no rule writes them as hex again
  css=(UIX_DIR/'css'/'desktop.css').read_text(encoding='utf-8');root,body=css.split('*{box-sizing:border-box}',1)
  for token in ('--ok-bg','--ok-fg','--ok-line','--warn-bg','--warn-fg','--warn-line','--bad-bg','--bad-fg','--bad-line','--card-bg','--card-line','--heading','--accent'):
   value=re.search(re.escape(token)+r':([^;]+);',root).group(1).strip()
   if value.startswith('#'):self.assertNotIn(value,body.lower(),token)
   self.assertIn('var('+token+')',body,token)
  self.assertGreaterEqual(body.count('var(--'),150)
 def test_sea_chart_model_is_pure_and_places_the_ship(self):
  node=shutil.which('node')
  if not node:self.skipTest('node is not installed')
  js=(UIX_DIR/'js'/'sea_chart.js').read_text(encoding='utf-8')
  probe='''const vm=require('vm');const box={};vm.createContext(box);vm.runInContext(process.argv[1],box);const c=box.chartModel;const out=[];
const plan={steps:[{id:'s1',description:'A'},{id:'s2',description:'B'},{id:'s3',description:'C'}]};
out.push(c({lifecycle:{phase:'READY'},plan}));out.push(c({lifecycle:{phase:'EXECUTE'},plan,execution:{results:[1]}}));
out.push(c({lifecycle:{phase:'COMPLETE'},plan,execution:{results:[1,2,3]}}));out.push(c({lifecycle:{phase:'PAUSED'},plan,execution:{results:[1]},human_gates:{pending:[{}]}}));
out.push(c({lifecycle:{phase:'FAILED'},plan,execution:{results:[1,2]}}));out.push(c(null));console.log(JSON.stringify(out));'''
  run=subprocess.run([node,'-e',probe,js],capture_output=True, text=True, encoding='utf-8',timeout=60);self.assertEqual(run.returncode,0,run.stderr)
  ready,run1,done,paused,failed,empty=json.loads(run.stdout)
  self.assertEqual([s['label'] for s in ready['stops']],['Hafen','A','B','C','Ziel']);self.assertEqual((ready['ship'],ready['barrier'],ready['tone']),(0,None,'ok'))
  self.assertEqual((run1['ship'],run1['tone']),(1.5,'run'));self.assertEqual([s['state'] for s in run1['stops']],['done','done','active','open','open'])
  self.assertEqual((done['ship'],done['tone'],done['stops'][-1]['state']),(4,'ok','done'))
  self.assertEqual((paused['tone'],paused['barrier'],paused['pending']),('warn',2,1))
  self.assertEqual((failed['tone'],failed['stops'][-1]['state']),('bad','fail'))
  self.assertEqual((empty['phase'],empty['ship'],len(empty['stops'])),('NEW',0,2))
 def test_process_list_off_windows_is_a_note_not_an_error(self):
  import sys
  if sys.platform=='win32':self.skipTest('Windows has the PowerShell inventory')
  view=self.hub.processes_view()
  self.assertEqual((view['servers'],view['runs'],view['jobs'],view['mismatch']),([],[],[],False));self.assertIn('nur unter Windows',view['note'])
  self.assertIn("if(p.note) box.append(el('div','mnote',p.note));",page_source())
 def _fake_gguf(self,name='Qwen3.5-9B-Q6_K.gguf',arch='qwen3',ctx=131072):
  import struct
  def kv_str(k,v):return struct.pack('<Q',len(k))+k.encode()+struct.pack('<I',8)+struct.pack('<Q',len(v))+v.encode()
  def kv_u32(k,v):return struct.pack('<Q',len(k))+k.encode()+struct.pack('<I',4)+struct.pack('<I',v)
  def kv_arr(k,vals):return struct.pack('<Q',len(k))+k.encode()+struct.pack('<I',9)+struct.pack('<I',8)+struct.pack('<Q',len(vals))+b''.join(struct.pack('<Q',len(x))+x.encode() for x in vals)
  d=Path(self.tmp.name)/'modelle';d.mkdir(exist_ok=True);(d/'unterordner').mkdir(exist_ok=True);f=d/name
  kvs=[kv_str('general.architecture',arch),kv_str('general.name','Qwen3.5 9B'),kv_u32(arch+'.context_length',ctx),kv_u32(arch+'.block_count',36),kv_u32('general.file_type',18),kv_arr('tokenizer.ggml.tokens',['a','b'])]
  f.write_bytes(b'GGUF'+struct.pack('<I',3)+struct.pack('<QQ',5,len(kvs))+b''.join(kvs)+b'\0'*2048);return d,f
 def test_new_model_from_file_to_recipe_behind_a_gate(self):
  # Captain 2026-10-14: pick a GGUF, see the recipe, approve once, then load and test. Nothing is written before the approval.
  d,f=self._fake_gguf()
  unittest.mock.patch.object(self.hub,'_models_root',lambda:d).start();self.addCleanup(unittest.mock.patch.stopall)
  view=self.hub.model_inspect({'path':str(f)})
  self.assertEqual((view['info']['architecture'],view['info']['context_length'],view['info']['quantization']),('qwen3',131072,'Q6_K'))
  self.assertEqual(view['recipe']['id'],'coder.local_qwen3_5_9b_q6_k');self.assertTrue(view['in_models_root']);self.assertIn('- id: coder.local_qwen3_5_9b_q6_k',view['yaml'])
  self.assertFalse(self.hub._routing_path().exists())
  for bad in ({},{'path':'relativ.gguf'},{'path':str(d/'fehlt.gguf')},{'path':str(f),'recipe_id':'Bad Id'},{'path':str(f),'recipe_id':'coder.local_primary'},{'path':str(f),'context_recommended':5000}):
   with self.assertRaises(ValueError):self.hub.model_inspect(bad)
  out=self.hub.model_add_request({'path':str(f),'recipe_id':'coder.local_test','roles':['coder','reviewer'],'context_recommended':8192})
  self.assertFalse(self.hub._routing_path().exists())      # a request writes nothing
  with self.assertRaises(ValueError):self.hub.model_add_apply({'mission_id':out['mission_id']})      # not approved
  self.hub.approve_gate({'mission_id':out['mission_id'],'gate_id':out['gate']['gate_id']})
  done=self.hub.model_add_apply({'mission_id':out['mission_id']})
  self.assertEqual((done['status'],done['recipe_id'],done['effective']),('applied','coder.local_test','now'))
  text=self.hub._routing_path().read_text(encoding='utf-8');self.assertIn('- id: coder.local_test',text);self.assertIn('roles: [coder, reviewer]',text);self.assertIn('recommended: 8192',text)
  ids=[r['id'] for r in self.hub.models_view()['recipes']];self.assertIn('coder.local_test',ids)      # usable without a restart
  self.assertFalse(self.hub.routing_config_view()['restart_needed'])
  with self.assertRaises(ValueError):self.hub.model_add_apply({'mission_id':out['mission_id']})      # the approval was single-use
  events=[e['event_type'] for e in self.hub.audit_view()['events']];self.assertIn('ROUTING_RECIPE_ADDED',events)
  with self.assertRaises(ValueError) as cm:self.hub.model_test({'recipe_id':'coder.local_test'})
  self.assertEqual(str(cm.exception),'model_not_loaded')
  # a second recipe lands behind the first, the loader still accepts the file
  out2=self.hub.model_add_request({'path':str(f)});self.hub.approve_gate({'mission_id':out2['mission_id'],'gate_id':out2['gate']['gate_id']})
  self.assertEqual(self.hub.model_add_apply({'mission_id':out2['mission_id']})['recipe_id'],'coder.local_qwen3_5_9b_q6_k')
  self.assertEqual(len([r for r in self.hub.models_view()['recipes'] if r['id'].startswith('coder.local_')]),3)
 def test_model_browse_and_pick_stay_inside_the_model_folder(self):
  d,f=self._fake_gguf()
  unittest.mock.patch.object(self.hub,'_models_root',lambda:d).start();self.addCleanup(unittest.mock.patch.stopall)
  view=self.hub.model_browse({'path':''})
  self.assertEqual([(e['name'],e['type']) for e in view['entries']],[('unterordner','dir'),('Qwen3.5-9B-Q6_K.gguf','file')])
  self.assertEqual(self.hub.model_browse({'path':'unterordner'})['entries'],[])
  for bad in ({'path':'..'},{'path':'/etc'},{'path':'C:/x'},{'path':'a/../..'}):
   with self.assertRaises(ValueError):self.hub.model_browse(bad)
  class Out:
   def __init__(s,t):s.stdout=t;s.stderr='';s.returncode=0
  seen=[]
  def run(cmd,**kw):seen.append(cmd);return Out(str(f)+'\n')
  self.hub._run=run
  picked=self.hub.model_pick({})
  if picked['picked']:self.assertEqual(picked['path'],str(f));self.assertIn(seen[0][0],('powershell','osascript','zenity'))
  else:self.assertIn(picked['reason'],('no_dialog','cancelled'))      # a PC without a dialog program: the folder list takes over
  self.hub._run=lambda cmd,**kw:Out('')
  self.assertFalse(self.hub.model_pick({})['picked'])
 def test_new_model_section_is_wired(self):
  html=page_source()
  for needle in ('function openModelAdd(','/api/model/pick','/api/model/browse','/api/model/inspect','/api/model/add/request','/api/model/add/apply','/api/model/test','onclick="openModelAdd()"','renderModelAdd(box);','function modelTest('):self.assertIn(needle,html)
  page=(UIX_DIR/'retro_desktop.html').read_text(encoding='utf-8');self.assertLess(page.index('/uix/js/models.js'),page.index('/uix/js/model_add.js'));self.assertLess(page.index('/uix/js/model_add.js'),page.index('/uix/js/main.js'))
 def test_only_main_runs_code_at_load(self):
  for f in sorted((UIX_DIR/'js').glob('*.js')):
   if f.name=='main.js':continue
   top=[l for l in f.read_text(encoding='utf-8').splitlines() if re.match(r'^(document\.|window\.|cc[A-Z]\w*\(\);|refresh\w*\(\);)',l)]
   self.assertEqual(top,[],f.name)
  self.assertIn('ccInit();',(UIX_DIR/'js'/'main.js').read_text(encoding='utf-8'))
 def test_chat_reply_without_model_and_input_checks(self):
  count=len(self.hub.missions())
  self.assertEqual(self.hub.chat_reply({'text':'Hallo'})['status'],'no_model')
  self.assertEqual(len(self.hub.missions()),count)      # no mission without a model answer
  for bad in ({},{'text':''},{'text':'x','history':'no'},{'text':'x','history':[{'role':'system','content':'y'}]}):
   with self.assertRaises(ValueError):self.hub.chat_reply(bad)
 def test_chat_reply_goes_through_control_with_fake_model(self):
  class FakeServer:
   def loaded_models(self):return [{'identifier':'fake-model','modelKey':'fake-model'}]
  seen={}
  def fake_execute(mission,request):
   seen.update(request);return {'status':'completed','model_result':{'content':' Hallo Captain. ','truncated':False}}
  self.hub.runtime.llama_server=FakeServer();self.hub.runtime.control.execute=fake_execute
  out=self.hub.chat_reply({'text':'Hallo','history':[{'role':'user','content':'a'},{'role':'assistant','content':'b'}]})
  self.assertEqual({k:out[k] for k in ('status','reply','model','truncated')},{'status':'completed','reply':'Hallo Captain.','model':'fake-model','truncated':False})
  self.assertEqual(seen['action'],'model_inference');self.assertEqual(seen['model'],'fake-model')
  self.assertEqual([m['role'] for m in seen['messages']],['system','user','assistant','user'])
  m=self.hub.runtime.missions.load(out['mission_id']);self.assertEqual(m['plan']['status'],'missing')   # session mission is not planned
  again=self.hub.chat_reply({'text':'Noch eins','mission_id':out['mission_id']});self.assertEqual(again['mission_id'],out['mission_id'])
 def test_chat_attach_refuses_secrets_and_is_audited(self):
  # hardening 2026-10-14: secret files never reach a prompt, folder listings hide them, every attach read leaves an audit event
  d=Path(self.tmp.name)/'geheim';d.mkdir();(d/'notiz.txt').write_text('ok',encoding='utf-8')
  for name in ('tokens.json','.env','.env.local','api.token','id_rsa','server.pem'):(d/name).write_text('SECRET',encoding='utf-8')
  (d/'.ssh').mkdir();(d/'.ssh'/'config').write_text('Host x',encoding='utf-8')
  for name in ('tokens.json','.env','.env.local','api.token','id_rsa','server.pem','.ssh/config'):
   with self.assertRaises(ValueError) as cm:self.hub.chat_attach({'path':str(d/name)})
   self.assertEqual(str(cm.exception),'secret_file_refused',name)
  info=self.hub.chat_attach({'path':str(d)});self.assertEqual([e['name'] for e in info['entries']],['notiz.txt'])
  with self.assertRaises(ValueError):self.hub._attachment_context([str(d/'tokens.json')])
  self.hub.chat_attach({'path':str(d/'notiz.txt')})
  events=[e for e in self.hub.audit_view()['events'] if e['event_type']=='UIX_CHAT_ATTACH']
  self.assertGreaterEqual(len(events),2);self.assertEqual(events[-1]['component'],'uix')
 def test_shell_reports_errors_and_server_times_out_idle_clients(self):
  html=page_source()
  for needle in ('function uiError(',"addEventListener('unhandledrejection'","addEventListener('error'",'Keine Verbindung zur Runtime (Server beendet'):self.assertIn(needle,html)
  src=Path(__file__).parents[1].joinpath('src/guppi_runtime/uix_server.py').read_text(encoding='utf-8')
  self.assertRegex(src,r'class Handler\(BaseHTTPRequestHandler\):\s+server_version = .*\s+timeout = 30')
 def test_chat_attach_is_read_only_and_reaches_the_model(self):
  d=Path(self.tmp.name)/'anhang';d.mkdir();(d/'a.txt').write_text('Inhalt A',encoding='utf-8');(d/'b.bin').write_bytes(bytes([0xff,0xfe,0,1]))
  (d/'sub').mkdir();(d/'sub'/'c.txt').write_text('C',encoding='utf-8')
  info=self.hub.chat_attach({'path':str(d)});self.assertEqual(info['kind'],'dir');self.assertEqual({e['name'] for e in info['entries']},{'a.txt','b.bin','sub/c.txt'})   # subfolders are listed
  self.assertEqual(self.hub.chat_attach({'path':str(d/'a.txt')})['excerpt'],'Inhalt A')
  self.assertTrue(self.hub.chat_attach({'path':str(d/'b.bin')})['binary'])
  for bad in ({},{'path':'relativ/pfad'},{'path':str(d/'fehlt')},{'path':'x'+chr(0)}):
   with self.assertRaises(ValueError):self.hub.chat_attach(bad)
  class FakeServer:
   def loaded_models(self):return [{'identifier':'fake-model','modelKey':'fake-model'}]
  seen={}
  def fake_execute(mission,request):
   seen.update(request);return {'status':'completed','model_result':{'content':'ok','truncated':False}}
  self.hub.runtime.llama_server=FakeServer();self.hub.runtime.control.execute=fake_execute
  self.hub.chat_reply({'text':'Was ist da?','attachments':[str(d),str(d/'a.txt')]})
  last=seen['messages'][-1]['content'];self.assertIn('Inhalt A',last);self.assertIn('a.txt',last);self.assertTrue(last.endswith('Was ist da?'))
  with self.assertRaises(ValueError):self.hub.chat_reply({'text':'x','attachments':'nein'})
  with self.assertRaises(ValueError):self.hub.chat_reply({'text':'x','attachments':[str(d)]*6})
  self.assertEqual((d/'a.txt').read_text(encoding='utf-8'),'Inhalt A')
 def _fake_host(self,rows):
  killed=[]
  class Out:
   def __init__(s,t):s.stdout=t;s.stderr='';s.returncode=0
  def run(cmd,**kw):
   if cmd[0]=='powershell':return Out(json.dumps(rows))
   if cmd[0]=='nvidia-smi':return Out('10234')
   if cmd[0] in ('taskkill','kill'):killed.append(int(cmd[-1]));return Out('')      # taskkill on Windows, kill elsewhere
   raise AssertionError(cmd)
  self.hub._run=run;return killed
 def _rows(self):
  root=str(Path(__file__).resolve().parents[1])
  srv='"E:\\x\\engines\\llama.cpp\\b1\\llama-server.exe" -m m.gguf -c 16384 --port 8089 --alias gpt-oss-20b --no-webui --spec-type none'
  return [{'ProcessId':10,'ParentProcessId':5,'Name':'python.exe','ExecutablePath':'p','Started':'2026-10-04T10:00:00','CommandLine':'"'+root+'\\.venv\\Scripts\\python.exe" benchmarks/e1_golden_path.py x generate'},
          {'ProcessId':11,'ParentProcessId':10,'Name':'llama-server.exe','ExecutablePath':'E:\\x\\engines\\llama.cpp\\b1\\llama-server.exe','Started':'2026-10-04T10:01:00','CommandLine':srv},
          {'ProcessId':12,'ParentProcessId':1,'Name':'llama-server.exe','ExecutablePath':'C:\\LM\\llama-server.exe','Started':'x','CommandLine':'llama-server.exe -m other.gguf'},
          {'ProcessId':13,'ParentProcessId':1,'Name':'python.exe','ExecutablePath':'p','Started':'x','CommandLine':'python other_tool.py'}]
 def test_processes_view_lists_only_guppi_servers_and_runs(self):
  self._fake_host(self._rows());v=self.hub.processes_view()
  self.assertEqual([s['pid'] for s in v['servers']],[11]);self.assertEqual(v['servers'][0]['alias'],'gpt-oss-20b');self.assertEqual(v['servers'][0]['parent_pid'],10)
  self.assertIn('e1_golden_path.py',v['servers'][0]['parent']);self.assertNotIn('python.exe',v['servers'][0]['parent'])
  self.assertEqual([r['pid'] for r in v['runs']],[10]);self.assertEqual(v['vram_used_gb'],9.99)
 def test_stop_process_only_listed_pids_with_confirmation(self):
  killed=self._fake_host(self._rows())
  for bad in ({'pid':12,'confirm':True},{'pid':99,'confirm':True},{'pid':11},{'pid':'11','confirm':True}):
   with self.assertRaises(ValueError):self.hub.stop_process(bad)
  self.assertEqual(killed,[])
  self.hub.stop_process({'pid':11,'confirm':True});self.assertEqual(killed,[11])
 def test_a_reused_pid_is_not_killed(self):
  rows=self._rows();killed=self._fake_host(rows)
  real=self.hub._run
  def reused(cmd,**kw):                      # between listing and kill pid 11 now belongs to another process (other start time)
   if cmd[0]=='taskkill':raise AssertionError('must not kill')
   return real(cmd,**kw)
  calls=[]
  orig=self.hub._process_rows
  def rows_after_first():
   calls.append(1)
   data=orig()
   if len(calls)>1:data=[dict(r,Started='2026-10-05T09:00:00') if r['ProcessId']==11 else r for r in data]
   return data
  self.hub._run=reused;self.hub._process_rows=rows_after_first
  with self.assertRaisesRegex(ValueError,'process_changed_or_gone'):self.hub.stop_process({'pid':11,'confirm':True})
  self.assertEqual(killed,[])
 def test_stopping_a_run_takes_its_servers_down(self):
  killed=self._fake_host(self._rows());self.hub.stop_process({'pid':10,'confirm':True});self.assertEqual(killed,[11,10])
 def test_cancel_job_errors_are_bad_requests(self):
  with self.assertRaises(ValueError):self.hub.cancel_job({})
  with self.assertRaises(ValueError):self.hub.cancel_job({'job_id':'SDJ-UNKNOWN'})
 def test_running_section_is_wired(self):
  html=page_source()
  for needle in ('function renderRunning(','/api/processes','/api/process/stop','/api/job/cancel'):self.assertIn(needle,html)
 def test_page_script_has_valid_syntax(self):
  import shutil,subprocess
  node=shutil.which('node')
  if not node:self.skipTest('node is not installed')
  files=sorted((UIX_DIR/'js').glob('*.js'));self.assertTrue(files)
  for f in files:
   r=subprocess.run([node,'--check',str(f)],capture_output=True, text=True, encoding='utf-8',timeout=60)
   self.assertEqual(r.returncode,0,f.name+': '+r.stderr[:400])
 def test_hardware_view_is_served_in_a_frame_and_read_only(self):
  class FakeHardware:
   def get_state(self):return {'timestamp':'t','cpu_utilization':None,'gpus':[]}
   def history(self,limit):return []
   def inventory(self):return {'fingerprint':'f'}
   def profiles(self):return {'auto':{'label':'Automatisch'}}
   def capabilities(self):return {'native_telemetry':True}
  self.hub.runtime.hardware_manager=FakeHardware()
  server,url=make_server(self.hub);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
  token=url.split('#')[1]
  def get(path,headers=None):
   c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
   try:
    c.request('GET',path,headers=headers or {});res=c.getresponse();return res.status,res.getheader('Content-Security-Policy'),res.read()
   finally:c.close()
  status,csp,body=get('/hardware');self.assertEqual(status,200);self.assertIn(b'Maschinenraum',body);self.assertIn("frame-ancestors 'self'",csp)
  self.assertIn("frame-ancestors 'none'",get('/')[1])        # the main page can still not be framed
  self.assertEqual(get('/api/state')[0],403)               # data needs the token
  h={'X-GUPPI-Token':token}
  self.assertEqual(json.loads(get('/api/state',h)[2])['state']['timestamp'],'t')
  self.assertEqual(json.loads(get('/api/capabilities',h)[2])['native_telemetry'],True)
  c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
  try:c.request('POST','/api/state','{}',dict(h,**{'Content-Length':'2'}));self.assertEqual(c.getresponse().status,404)   # no write route
  finally:c.close()
 def test_hardware_window_is_wired(self):
  html=page_source()
  for needle in ('id="hardwareWindow"','function openHardware(',"'/hardware#'"):self.assertIn(needle,html)

 def test_machine_room_is_built_from_cards(self):
  html=page_source()
  for needle in ("el('div','mr-grid')",".mr-card{","card('GPU und Arbeitsspeicher')","card('Entwicklungsumgebung')"):self.assertIn(needle,html)
  self.assertNotIn("section('Hardware',st",html)       # the old text dump is gone
 def test_hardware_dashboard_uses_the_uix_look(self):
  dash=(Path(__file__).parents[1]/'src/guppi_runtime/hardware_manager/dashboard.html').read_text(encoding='utf-8')
  self.assertIn('#f8f6ec',dash);self.assertNotIn('color-scheme:dark',dash);self.assertIn('Maschinenraum',dash)

 def _project_with_files(self):
  rec=self.hub.new_project({'name':'Dateien'});root=self.hub.runtime.filesystem_tool._resolve(rec['workspace_path'])
  (root/'src').mkdir();(root/'src'/'main.py').write_text('print(1)\n',encoding='utf-8');(root/'README.md').write_text('# Hallo\n',encoding='utf-8')
  (root/'__pycache__').mkdir();(root/'blob.bin').write_bytes(bytes([0xff,0xfe,0x00,0x80]))
  return rec['project_id']
 def test_project_files_lists_folders_first_and_hides_noise(self):
  pid=self._project_with_files();out=self.hub.project_files({'project_id':pid})
  self.assertEqual([(e['name'],e['type']) for e in out['entries']],[('src','dir'),('blob.bin','file'),('README.md','file')])
  self.assertEqual([e['name'] for e in self.hub.project_files({'project_id':pid,'path':'src'})['entries']],['main.py'])
 def test_project_files_refuses_escapes_and_unknown_projects(self):
  pid=self._project_with_files()
  for bad in ('..','../x','src/../..','/etc','C:/Windows','..\\x'):
   with self.assertRaises(ValueError):self.hub.project_files({'project_id':pid,'path':bad})
  with self.assertRaises(ValueError):self.hub.project_files({'project_id':'PRJ-nope'})
  with self.assertRaises(ValueError):self.hub.project_files({'project_id':pid,'path':'missing'})
 def test_project_file_reads_text_flags_binary_and_needs_a_path(self):
  pid=self._project_with_files()
  self.assertEqual(self.hub.project_file({'project_id':pid,'path':'src/main.py'})['content'].strip(),'print(1)')
  self.assertTrue(self.hub.project_file({'project_id':pid,'path':'blob.bin'})['binary'])
  big=self.hub.runtime.filesystem_tool._resolve(self.hub.projects.get(pid)['workspace_path'])/'big.txt';big.write_text('x'*(self.hub.FILE_PREVIEW_BYTES+1))
  self.assertTrue(self.hub.project_file({'project_id':pid,'path':'big.txt'})['too_large'])
  with self.assertRaises(ValueError):self.hub.project_file({'project_id':pid})
 def test_project_file_cards_are_wired(self):
  html=page_source()
  for needle in ('function loadProjectFiles(','function openProjectFile(','/api/project/files','/api/project/file','id="fileGrid"'):self.assertIn(needle,html)
  self.assertNotIn('ROADMAP.md</div>',html)          # the fixed placeholder cards are gone

 def _switch_file(self,text=None):
  d=self.hub.runtime.project_root/'local_config';d.mkdir(exist_ok=True);f=d/'switches.yaml'
  f.write_text(text if text is not None else '# kept comment\nswitches:\n  model_loader: {enabled: true, evict_idle_models: true}   # trailing\n  llama_server: {enabled: true, mtp: true}\n',encoding='utf-8');return f
 def _approved_switch(self,section,key,value):
  req=self.hub.switch_request({'section':section,'key':key,'value':value})
  self.hub.approve_gate({'mission_id':req['mission_id'],'gate_id':req['gate']['gate_id']});return req
 def test_switch_change_needs_the_gate_and_keeps_the_file_layout(self):
  f=self._switch_file();req=self.hub.switch_request({'section':'llama_server','key':'mtp','value':False})
  self.assertEqual(req['gate']['request']['exact_action'],'change_switch')
  with self.assertRaises(ValueError):self.hub.switch_apply({'mission_id':req['mission_id']})        # no approval yet
  self.assertIn('mtp: true',f.read_text(encoding='utf-8'))
  self.hub.approve_gate({'mission_id':req['mission_id'],'gate_id':req['gate']['gate_id']})
  out=self.hub.switch_apply({'mission_id':req['mission_id']});self.assertEqual(out['effective'],'next_start')
  text=f.read_text(encoding='utf-8');self.assertIn('llama_server: {enabled: true, mtp: false}',text)
  self.assertIn('# kept comment',text);self.assertIn('# trailing',text)
  self.assertTrue(list(f.parent.glob('switches.yaml.bak-*-uix')))
  self.assertTrue(self.hub.switches_view()['restart_needed'])
  with self.assertRaises(ValueError):self.hub.switch_apply({'mission_id':req['mission_id']})        # the approval is single use
 def test_switch_new_section_and_validation(self):
  f=self._switch_file()
  req=self._approved_switch('token_policy','enabled',True);self.hub.switch_apply({'mission_id':req['mission_id']})
  self.assertIn('token_policy: {enabled: true}',f.read_text(encoding='utf-8'))
  for bad in ({'section':'nope','key':'enabled','value':True},{'section':'llama_server','key':'port','value':True},{'section':'llama_server','key':'mtp','value':'yes'}):
   with self.assertRaises(ValueError):self.hub.switch_request(bad)
 def test_switch_rejected_or_stale_requests_change_nothing(self):
  f=self._switch_file();before=f.read_text(encoding='utf-8')
  req=self.hub.switch_request({'section':'llama_server','key':'mtp','value':False})
  self.hub.reject_gate({'mission_id':req['mission_id'],'gate_id':req['gate']['gate_id']})
  with self.assertRaises(ValueError):self.hub.switch_apply({'mission_id':req['mission_id']})
  stale=self._approved_switch('llama_server','mtp',False);f.write_text(before+'# edited meanwhile\n',encoding='utf-8')
  with self.assertRaises(ValueError):self.hub.switch_apply({'mission_id':stale['mission_id']})
  self.assertNotIn('mtp: false',f.read_text(encoding='utf-8'))
 def test_switch_section_is_wired(self):
  html=page_source()
  for needle in ('function renderSwitches(','/api/switches','/api/switch/request','/api/switch/apply','Freigeben und anwenden'):self.assertIn(needle,html)

 def test_chat_model_picker_is_wired_and_explains_models(self):
  html=page_source()
  for needle in ('id="chatModel"','function chooseChatModel(','function refreshChatModels(','const MODEL_HINTS','Gut für:','qwen3-coder-30b-a3b','gpt-oss-20b','google/gemma-4-12b-qat'):self.assertIn(needle,html)

 def test_static_files_are_served_from_a_whitelist_only(self):
  server,url=make_server(self.hub);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
  def get(path):
   c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
   try:
    c.request('GET',path);res=c.getresponse();return res.status,res.getheader('Content-Type'),res.getheader('Content-Security-Policy'),res.read()
   finally:c.close()
  status,kind,csp,body=get('/uix/css/desktop.css');self.assertEqual(status,200);self.assertIn('text/css',kind);self.assertIn(b'.window',body)
  status,kind,csp,body=get('/uix/js/core.js');self.assertEqual(status,200);self.assertIn('javascript',kind);self.assertIn("script-src 'self'",csp)
  for bad in ('/uix/js/core.css','/uix/js/nope.js','/uix/js/../uix_server.py','/uix/js/%2e%2e/x.js','/uix/other/core.js','/uix/js/Core.js','/uix/retro_desktop.html'):
   self.assertIn(get(bad)[0],(403,404),bad)      # never served: 404, or 403 for a path the token does not cover
 def test_page_is_split_into_files_and_loads_main_last(self):
  html=(UIX_DIR/'retro_desktop.html').read_text(encoding='utf-8')
  scripts=re.findall(r'<script src="/uix/js/([a-z_]+)\.js"></script>',html)
  self.assertEqual(scripts[-1],'main');self.assertEqual(scripts[0],'core')
  self.assertEqual(sorted(scripts),sorted(f.stem for f in (UIX_DIR/'js').glob('*.js')))      # every file is loaded, none is missing
  self.assertNotIn('<script>',html);self.assertNotIn('<style>',html)
  for f in (UIX_DIR/'js').glob('*.js'):self.assertLess(len(f.read_text(encoding='utf-8').splitlines()),400,f.name)   # small enough for a model to edit
 def test_switching_models_frees_the_old_one_when_vram_is_short(self):
  from guppi_runtime.role_routing import ResolutionError
  state={'loaded':True,'calls':0,'unloaded':0}
  class FakeServer:
   def loaded_models(self):return [{'identifier':'a'}] if state['loaded'] else []
   def unload_model(self,all_models=False):state['loaded']=False;state['unloaded']+=1;return {'output':'stopped'}
  class FakeRouter:
   def resolve_recipe(self,rid):
    state['calls']+=1
    if state['loaded']:raise ResolutionError('hardware_pressure',{})
    return {'provider_ref':'llama-cpp-server','model':'b'}
  class FakeLoader:
   enabled=True
   def ensure(self,res):return {'identifier':'b','action':'loaded'}
  rt=self.hub.runtime;rt.llama_server=FakeServer();rt.role_router=FakeRouter();rt.model_loader=FakeLoader()
  self.hub.gpu_token=self.hub.lab.try_acquire('guppi-uix','test',ttl_s=600);self.addCleanup(self.hub._release_gpu)
  import guppi_runtime.uix_server as u
  with unittest.mock.patch.object(u.time,'sleep'):out=self.hub.load_model({'recipe_id':'x'})
  self.assertEqual(out['identifier'],'b');self.assertEqual((state['calls'],state['unloaded']),(2,1))
 def test_foreign_pressure_does_not_unload_anything(self):
  from guppi_runtime.role_routing import ResolutionError
  class FakeRouter:
   def resolve_recipe(self,rid):raise ResolutionError('hardware_pressure',{})
  class FakeLoader:enabled=True
  class FakeServer:
   def loaded_models(self):return [{'identifier':'foreign'}]
   def unload_model(self,all_models=False):raise AssertionError('must not stop a server this UIX does not own')
  rt=self.hub.runtime;rt.llama_server=FakeServer();rt.role_router=FakeRouter();rt.model_loader=FakeLoader()
  with self.assertRaises(ValueError):self.hub.load_model({'recipe_id':'x'})
 def test_model_errors_are_explained_in_plain_language(self):
  js=(UIX_DIR/'js'/'models.js').read_text(encoding='utf-8')
  for needle in ('function explainModelError(','hardware_pressure','gpu_lease_busy','Nicht genug freier Grafikspeicher'):self.assertIn(needle,js)
 def _routing_overlay(self,crlf=False):
  src=Path(__file__).resolve().parent/'fixtures'/'role_routing_overlay.yaml'      # frozen copy, not the live recipes of this PC
  d=self.hub.runtime.project_root/'local_config';d.mkdir(exist_ok=True);f=d/'role_routing.yaml'
  text=src.read_text(encoding='utf-8')
  with open(f,'w',encoding='utf-8',newline='') as o:o.write(text.replace('\n','\r\n') if crlf else text)
  return f
 def _routing_apply(self,rid,field,value):
  req=self.hub.routing_request({'recipe_id':rid,'field':field,'value':value})
  self.hub.approve_gate({'mission_id':req['mission_id'],'gate_id':req['gate']['gate_id']})
  return self.hub.routing_apply({'mission_id':req['mission_id']})
 def _changed_lines(self,before,after):
  b,a=before.splitlines(),after.splitlines()
  return [(x,y) for x,y in zip(b,a) if x!=y],len(a)-len(b)
 def test_routing_view_reads_the_overlay(self):
  self._routing_overlay();v=self.hub.routing_config_view()
  r={x['id']:x for x in v['recipes']}
  self.assertEqual((r['coder.llama_gptoss']['n_cpu_moe'],r['coder.llama_gptoss']['context_recommended'],r['coder.llama_gptoss']['kv_cache_type']),(7,8192,'f16'))
  self.assertIs(r['coder.llama_qwen35']['enabled'],False);self.assertIn(8192,r['coder.llama_gptoss']['context_tiers'])
 def test_routing_change_touches_one_line_and_keeps_the_rest(self):
  f=self._routing_overlay();before=f.read_text(encoding='utf-8')
  self._routing_apply('coder.llama_gptoss','n_cpu_moe',6)
  changed,extra=self._changed_lines(before,f.read_text(encoding='utf-8'))
  self.assertEqual((len(changed),extra),(1,0));self.assertIn('n_cpu_moe: 6',changed[0][1]);self.assertIn('gguf:',changed[0][1])
  self.assertTrue(list(f.parent.glob('role_routing.yaml.bak-*-uix')));self.assertTrue(self.hub.routing_config_view()['restart_needed'])
 def test_routing_enable_context_kv_and_new_key(self):
  f=self._routing_overlay();before=f.read_text(encoding='utf-8')
  self._routing_apply('coder.llama_qwen35','enabled',True)
  text=f.read_text(encoding='utf-8');self.assertIn('      enabled: true   # set in the UIX',text);self.assertNotIn('guppi-model-remove RM-20261003T185920\n      version: 1\n      roles: [coder, planner, reviewer, tester, documentation, context_curator, tool_operator, researcher]\n      provider: llama-cpp-server\n      model: qwen3.5-9b',text)
  self._routing_apply('coder.llama_gptoss','context_recommended',16384);self.assertIn('context: {recommended: 16384, maximum: 49152',f.read_text(encoding='utf-8'))
  self._routing_apply('verifier.llama_gemma','kv_cache_type','q8_0');self.assertRegex(f.read_text(encoding='utf-8'),r"gemma-4-12B-it-QAT-Q4_0\.gguf', kv_cache_type: q8_0")
  self._routing_apply('verifier.llama_gemma','n_cpu_moe',3);self.assertRegex(f.read_text(encoding='utf-8'),r"mtp: false, reasoning: auto, n_cpu_moe: 3\}")
 def test_routing_rejects_bad_values_and_unknown_things(self):
  self._routing_overlay()
  for bad in ({'recipe_id':'nope','field':'enabled','value':True},{'recipe_id':'coder.llama_gptoss','field':'gguf','value':'x'},
              {'recipe_id':'coder.llama_gptoss','field':'enabled','value':'yes'},{'recipe_id':'coder.llama_gptoss','field':'context_recommended','value':9999},
              {'recipe_id':'coder.llama_gptoss','field':'n_cpu_moe','value':99},{'recipe_id':'coder.llama_gptoss','field':'n_cpu_moe','value':True},
              {'recipe_id':'coder.llama_gptoss','field':'kv_cache_type','value':'q4_0'}):
   with self.assertRaises(ValueError):self.hub.routing_request(bad)
 def test_routing_needs_approval_once_and_a_fresh_file(self):
  f=self._routing_overlay();before=f.read_text(encoding='utf-8')
  req=self.hub.routing_request({'recipe_id':'coder.llama_gptoss','field':'n_cpu_moe','value':6})
  with self.assertRaises(ValueError):self.hub.routing_apply({'mission_id':req['mission_id']})
  self.hub.reject_gate({'mission_id':req['mission_id'],'gate_id':req['gate']['gate_id']})
  with self.assertRaises(ValueError):self.hub.routing_apply({'mission_id':req['mission_id']})
  self.assertEqual(f.read_text(encoding='utf-8'),before)
  stale=self.hub.routing_request({'recipe_id':'coder.llama_gptoss','field':'n_cpu_moe','value':5})
  self.hub.approve_gate({'mission_id':stale['mission_id'],'gate_id':stale['gate']['gate_id']});f.write_text(before+'# edited meanwhile\n',encoding='utf-8')
  with self.assertRaises(ValueError):self.hub.routing_apply({'mission_id':stale['mission_id']})
  self.assertNotIn('n_cpu_moe: 5',f.read_text(encoding='utf-8'))
 def test_routing_edit_keeps_crlf_line_endings(self):
  f=self._routing_overlay(crlf=True);self._routing_apply('coder.llama_gptoss','n_cpu_moe',6)
  raw=f.read_bytes();self.assertEqual(raw.count(b'\n'),raw.count(b'\r\n'))
 def test_routing_panel_is_wired(self):
  js=(UIX_DIR/'js'/'models.js').read_text(encoding='utf-8')
  for needle in ('function renderRoutingConfig(','/api/routing-config','/api/routing-config/request','/api/routing-config/apply','n_cpu_moe'):self.assertIn(needle,js)
 # ---- rework watch (plan 2026-10-04): stalled reworks wait for the Captain's hint
 def _e1_state(self,name='demo',hint=None,failures=2):
  from guppi_runtime.rework_watch import ReworkWatch,failure_signature
  state={'job_id':'SDJ-STALLED','scenario':name}
  if hint: state['captain_hint']=hint
  w=ReworkWatch();sig=failure_signature('gen','model_answer_truncated')
  for _ in range(failures): w.record(sig,hint)
  w.save(state)
  path=self.hub.project_root/'runtime_data'/'e1_golden_path'/name/'state.json'
  path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(state),encoding='utf-8')
  return path
 def test_rework_view_lists_a_stalled_e1_run_and_nothing_else(self):
  self.assertEqual(self.hub.rework_view(),{'stalled':[]})
  self._e1_state('fine',failures=1)
  self.assertEqual(self.hub.rework_view(),{'stalled':[]})
  self._e1_state('stuck')
  item=self.hub.rework_view()['stalled'][0]
  self.assertEqual((item['kind'],item['job_id'],item['scenario'],item['detector'],item['count']),('e1','SDJ-STALLED','stuck','generic_repeat',3))
  self.assertTrue(item['failure'].startswith('gen:'))
 def test_rework_hint_lets_an_e1_run_continue(self):
  path=self._e1_state('stuck')
  out=self.hub.rework_hint({'job_id':'SDJ-STALLED','text':'  shorten the objective  '})
  self.assertEqual((out['status'],out['kind']),('hint_given','e1'))
  state=json.loads(path.read_text(encoding='utf-8'))
  self.assertEqual(state['captain_hint'],'shorten the objective')
  self.assertEqual(self.hub.rework_view(),{'stalled':[]})              # the new hint changes the rework call: not stalled any more
  events=[json.loads(l) for l in (self.hub.project_root/'runtime_data'/'audit'/'events.jsonl').read_text(encoding='utf-8').splitlines()]
  self.assertEqual(events[-1]['event_type'],'UIX_REWORK_HINT_GIVEN')
 def test_rework_hint_refuses_bad_input_and_non_stalled_jobs(self):
  self._e1_state('fine',failures=1)
  for payload,message in (({},'job_id_required'),({'job_id':'SDJ-STALLED'},'invalid_hint'),({'job_id':'SDJ-STALLED','text':'   '},'invalid_hint'),
                          ({'job_id':'SDJ-STALLED','text':'x'*2001},'invalid_hint'),({'job_id':'SDJ-STALLED','text':'hint'},'no_stalled_rework'),
                          ({'job_id':'SDJ-OTHER','text':'hint'},'no_stalled_rework')):
   with self.assertRaises(ValueError,msg=str(payload)) as ctx:self.hub.rework_hint(payload)
   self.assertEqual(str(ctx.exception),message)
 def test_rework_hint_must_be_new(self):
  self._e1_state('stuck',hint='first',failures=2)                      # stalled although a hint was given before
  with self.assertRaises(ValueError) as ctx:self.hub.rework_hint({'job_id':'SDJ-STALLED','text':'first'})
  self.assertEqual(str(ctx.exception),'hint_not_new')
 def test_rework_view_and_hint_for_a_stalled_supervisor_job(self):
  from guppi_runtime.rework_watch import ReworkWatch,failure_signature
  w=ReworkWatch();sig=failure_signature('test','FAIL: test_a (m.C.test_a)')
  w.record(sig);w.record(sig)
  job={'job_id':'SDJ-SUP','state':'BLOCKED','supervisor_flags':{'escalated_to':'captain'},'last_error':{'reason_code':'rework_stalled'},
       'retry':{'watch':w.entries,'captain_hint':None}}
  sup=unittest.mock.Mock();sup.store.scan.return_value=([job,{'job_id':'SDJ-OK','state':'REWORK','supervisor_flags':{},'retry':{}}],[])
  self.hub.runtime.job_supervisor=sup
  item=self.hub.rework_view()['stalled'][0]
  self.assertEqual((item['kind'],item['job_id'],item['detector'],item['count']),('supervisor','SDJ-SUP','generic_repeat',3))
  self.hub.rework_hint({'job_id':'SDJ-SUP','text':'look at the port check'})
  sup.give_hint.assert_called_once_with('SDJ-SUP','look at the port check',resolved_by='captain-uix')
  from guppi_runtime.job_supervisor import JobError
  sup.give_hint.side_effect=JobError('hint_not_new')
  with self.assertRaises(ValueError):self.hub.rework_hint({'job_id':'SDJ-SUP','text':'again'})
 def test_rework_panel_is_wired(self):
  js=(UIX_DIR/'js'/'rework.js').read_text(encoding='utf-8')
  for needle in ('function renderStalled(','/api/rework','/api/rework/hint','renderRunningBase'):self.assertIn(needle,js)
  self.assertIn('/uix/js/rework.js',(UIX_DIR/'retro_desktop.html').read_text(encoding='utf-8'))
  self.assertLess(page_source().index('async function renderRunning('),page_source().index('const renderRunningBase'))
  server,url=make_server(self.hub);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
  token=url.split('#')[1]
  def get(path,headers=None):
   c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
   try:
    c.request('GET',path,headers=headers or {});r=c.getresponse();return r.status,r.read()
   finally:c.close()
  self.assertEqual(get('/uix/js/rework.js')[0],200)
  self.assertEqual(get('/api/rework')[0],403)                            # needs the token like every API call
  status,body=get('/api/rework',{'X-GUPPI-Token':token})
  self.assertEqual((status,json.loads(body)),(200,{'stalled':[]}))


class LoadFailureLog(unittest.TestCase):
 """2026-10-16: MODEL_LOAD_FAILED names the recipe's model file. The server profile is in `load_profile`; `profile` is the
 routing profile's NAME, so the old lookup logged gguf '' for every failure."""
 def test_the_failure_carries_the_recipe_file_and_whether_it_exists(self):
  with tempfile.TemporaryDirectory() as tmp:
   hub=UIXHub(Path(tmp)/'project',ARCH)
   gguf=Path(tmp)/'m.gguf';gguf.write_bytes(b'GGUF')
   resolution={'provider_ref':'llama-cpp-server','profile':'Standard','load_profile':{'server':{'gguf':str(gguf)}}}
   with unittest.mock.patch.object(hub.runtime.audit,'append') as append:
    hub._log_load_failure('coder.local_qwen3_5_9b_q6_k',resolution,ValueError('valid_gguf_model_required'))
  name,=append.call_args.args
  payload=append.call_args.kwargs['payload']
  self.assertEqual(name,'MODEL_LOAD_FAILED')
  self.assertEqual((payload['recipe_id'],payload['gguf'],payload['gguf_exists']),('coder.local_qwen3_5_9b_q6_k',str(gguf),True))
  self.assertEqual((payload['exception'],payload['detail']),('ValueError','valid_gguf_model_required'))
