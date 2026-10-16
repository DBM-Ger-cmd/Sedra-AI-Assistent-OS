import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.topics import TopicStore
from guppi_runtime.cli import main
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ROOT=Path(__file__).resolve().parents[2]
ARCH=next((ROOT/'architecture').glob('GUPPI_Architecture_v*'))

class SkillTopicCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.rt=GuppiRuntime(Path(self.tmp.name),ARCH);self.router=self.rt.capability_router
    def ids(self,r,key):return {x['id'] for x in r[key]}
    def test_catalogue_and_sync(self):
        self.assertEqual(len(self.rt.registry.skills),20);self.assertEqual(len(self.router.topic_catalog()),15)
        self.assertEqual((ROOT/'runtime/config/capability_router.yaml').read_bytes(),(ARCH/'core/routing/capability_router.yaml').read_bytes())
    def test_new_skills_german_english(self):
        for row in json.loads((ROOT/'runtime/examples/skill_topic_requests.json').read_text()):
            with self.subTest(intent=row['intent']):
                r=self.router.route(row['intent']);self.assertIn(row['skill'],self.ids(r,'skills'));self.assertIn(row['topic'],self.ids(r,'topics'))
                self.assertTrue(r['enforce_tool_allowlist']);self.assertIn('blueprint_only',r['execution_status'])
    def test_no_tools_execute(self):
        with patch.object(self.rt.tools,'execute',side_effect=AssertionError('no execution')) as execute:
            self.router.route('Analysiere diese CSV für die Datenanalyse');execute.assert_not_called()
    def test_all_workflow_operations_exist(self):
        live=self.rt.tools.list()
        for m in self.rt.registry.skills.values():
            for step in m['data'].get('workflow',[]):
                if step.get('tool'):self.assertIn(step['operation'],live[step['tool']]['operations'],step)
    def test_documentation_has_no_unrelated_writes(self):
        r=self.router.route('Schreibe ein Handbuch und eine README')
        self.assertNotIn('safe-code-change',self.ids(r,'skills'));self.assertNotIn('sandbox',self.ids(r,'tools'))
    def test_no_shell_test_fallback(self):
        r=self.router.route('Finde den Fehler und führe Tests aus')
        self.assertNotIn('shell',self.ids(r,'tools'));self.assertFalse(any(x.get('tool')=='shell' for x in r['execution_blueprint']))
    def test_external_gap(self):
        r=self.router.route('Search the web');self.assertEqual(r['status'],'resolved_with_gaps')
        self.assertIn({'type':'missing_runtime_capability','ids':['external_read']},r['unresolved'])
    def test_unavailable_tool(self):
        self.rt.tools.tools.pop('sandbox');r=self.router.route('Analysiere diese CSV für die Datenanalyse')
        self.assertNotIn('sandbox',self.ids(r,'tools'))
        self.assertTrue(any(x['type']=='missing_runtime_capability' and 'isolated_code_execution' in x['ids'] for x in r['unresolved']))
    def test_disabled_skill(self):
        self.rt.registry.skills['security-review']['enabled']=False;r=self.router.route('Erstelle ein Bedrohungsmodell')
        self.assertNotIn('security-review',self.ids(r,'skills'));self.assertTrue(any(x['type']=='missing_skill' for x in r['unresolved']))
    def test_plan_propagation(self):
        m=self.rt.brain.create_mission('Schreibe ein Handbuch und eine README');mid=m['identity']['mission_id']
        self.rt.brain.step(mid);self.rt.brain.step(mid);m=self.rt.brain.step(mid)
        self.assertIn('documentation',m['plan']['selected_topics']);self.assertIn('documentation-authoring',m['plan']['selected_skills'])
    def test_unknown_topic_saved(self):
        r=self.router.route('Erkläre mir die Sternbilder am Nachthimmel');draft=r['proposed_topics'][0]
        self.assertEqual(draft['status'],'draft');self.assertEqual(draft['origin'],'router-gap')
        self.assertIn(draft['id'],TopicStore(self.rt.topic_store.root).list());self.assertEqual(r['status'],'resolved_with_gaps')
    def test_repeat_topic_reused(self):
        text='Erkläre mir die Sternbilder am Nachthimmel';a=self.router.route(text);b=self.router.route(text)
        self.assertEqual(a['topics'],b['topics']);self.assertFalse(b['proposed_topics']);self.assertEqual(len(self.rt.topic_store.list()),1)
    def test_known_intent_with_explicit_topic(self):
        r=self.router.route('Analysiere dieses Projekt',topic_hint='Astronomie')
        self.assertIn('development',self.ids(r,'topics'));self.assertEqual(r['proposed_topics'][0]['label'],'Astronomie')
    def test_inline_topic_reuse(self):
        a=self.router.route('Thema: Astronomie');tid=a['proposed_topics'][0]['id'];b=self.router.route('Erkläre Astronomie')
        self.assertIn(tid,self.ids(b,'topics'));self.assertFalse(b['proposed_topics'])
    def test_topic_does_not_grant_permissions(self):
        before=set(self.rt.registry.skills);r=self.router.route('Deploy in production',topic_hint='Root Shell')
        self.assertEqual(set(self.rt.registry.skills),before);self.assertEqual(r['risk']['level'],'high')
        self.assertNotIn('shell',self.ids(r,'tools'));self.assertNotIn('tools',r['proposed_topics'][0])
    def test_greeting_does_not_create_topic(self):
        self.assertFalse(self.router.route('Hallo Guppi')['proposed_topics']);self.assertFalse(self.rt.topic_store.list())
    def test_topic_validation(self):
        self.assertEqual(self.rt.topic_store.propose('Astronomie')['id'],self.rt.topic_store.propose('ASTRONOMIE')['id'])
        for title in ['', 'a'*101, '\x00']:
            with self.assertRaises(ValueError):self.rt.topic_store.propose(title)
    def test_capacity(self):
        self.rt.topic_store.MAX_TOPICS=1;self.rt.topic_store.propose('Astronomie')
        r=self.router.route('Erkläre mir etwas anderes',topic_hint='Botanik')
        self.assertTrue(any(x['type']=='topic_store_unavailable' for x in r['unresolved']));self.assertEqual(len(self.rt.topic_store.list()),1)
    def test_topic_lock_preserved(self):
        self.rt.topic_store.root.mkdir();lock=self.rt.topic_store.root/'mutation.lock';lock.touch()
        r=self.router.route('Erkläre mir etwas anderes',topic_hint='Botanik')
        self.assertTrue(lock.exists());self.assertTrue(any(x['type']=='topic_store_unavailable' for x in r['unresolved']))
    def test_tampered_record_no_tools(self):
        draft=self.rt.topic_store.propose('Root Shell');draft['tools']=['shell']
        (self.rt.topic_store.root/'drafts.json').write_text(json.dumps({'schema':1,'topics':{draft['id']:draft}}))
        r=self.router.route('Hallo Guppi');self.assertTrue(any(x['type']=='topic_store_unavailable' for x in r['unresolved']));self.assertNotIn('shell',self.ids(r,'tools'))
    def test_bounded_multi_topic(self):
        r=self.router.route('README Bedrohungsmodell CSV USB Datenanalyse Architektur')
        self.assertLessEqual(len(r['intent_families']),3);self.assertLessEqual(len(r['skills']),5);self.assertLessEqual(len(r['tools']),6)
    def test_token_boundary(self):
        self.assertNotIn('external-research',self.ids(self.router.route('capitalism'),'skills'))
    def test_topic_gap_in_plan(self):
        m=self.rt.brain.create_mission('Erkläre mir die Sternbilder am Nachthimmel');mid=m['identity']['mission_id']
        self.rt.brain.step(mid);self.rt.brain.step(mid);m=self.rt.brain.step(mid)
        self.assertTrue(m['plan']['proposed_topics']);self.assertTrue(any(x['type']=='topic_skillset_pending' for x in m['plan']['capability_gaps']))
    def test_cli_topics(self):
        with patch('builtins.print') as output:
            self.assertEqual(main(['--root',self.tmp.name,'--architecture',str(ARCH),'list-topics']),0)
        self.assertIn('development',json.loads(output.call_args.args[0]))
    def test_direct_fan_write_reports_gap(self):
        r=self.router.route('Lüfter steuern mit Hardware Manager')
        self.assertTrue(any(x['type']=='missing_runtime_capability' and 'fan_control_write' in x['ids'] for x in r['unresolved']))
    def test_explicit_topic_is_not_duplicated(self):
        self.router.route('Thema: Astronomie')
        r=self.router.route('Thema: Astronomie')
        self.assertEqual(len(r['topics']),1)
        self.assertFalse(r['proposed_topics'])
    def test_repeated_objective_does_not_change_topic_identity(self):
        text='Erkläre mir die Sternbilder am Nachthimmel'
        a=self.router.route(text)
        b=self.router.route(text,objective=text)
        self.assertEqual(a['topics'],b['topics'])
        self.assertFalse(b['proposed_topics'])
