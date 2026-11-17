import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401
from sedra_runtime.workflows.store import WorkflowStore
from sedra_runtime.workflows import lokal, rechnung_dashboard
from sedra_runtime.workflows.execution import _modell
from sedra_runtime.harness.sitzung import Sitzungen
from sedra_runtime.harness.modellwahl import loaded
from test_workflow_lokal import WF, RECHNUNG, pdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from prepare_invoice_showcase import prepare


class Showcase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        rec = WorkflowStore(self.project).save(WF)
        self.rec = prepare(self.project, rec['id'])
        from sedra_runtime.workflows.lokal_daten import Tabellen
        t = Tabellen(self.project)
        t.importieren('Auftraege', json.dumps([{'auftragsnummer': 'AUF-2026-ST-17', 'gesamt_brutto': 2510.90}]))
        t.importieren('Auftragspositionen', json.dumps([
            {'auftragsnummer': 'AUF-2026-ST-17', 'lv_position': '01.01.0010', 'menge': 1, 'einzelpreis_netto': 1200, 'gesamtpreis_netto': 1200},
            {'auftragsnummer': 'AUF-2026-ST-17', 'lv_position': '01.01.0020', 'menge': 20, 'einzelpreis_netto': 45.5, 'gesamtpreis_netto': 910}]))

    def run_invoice(self, lines=RECHNUNG):
        from sedra_runtime.workflows.lokal_daten import Eingaben
        file_id = Eingaben(self.project).speichern(pdf(lines))
        model = mock.Mock(return_value={'Rechnungsnummer': 'RE-ST-2026-0042', 'Rechnungsbetrag': 2510.90, 'Rechnungsdatum': '2026-11-12'})
        result = lokal.ausfuehren(self.rec['workflow'], {'Rechnung': {'datei': file_id, 'name': 'testrechnung.pdf'}}, self.project, modell=model)
        return result, model

    def test_complete_process_model_and_report(self):
        result, model = self.run_invoice()
        self.assertEqual(result['status'], 'completed', result)
        model.assert_called_once()
        self.assertTrue(any(n['name'] == 'HTML-Dashboard als Datei ausgeben' and n['status'] == 'ok' for n in result['knoten']))
        data = result['rechnungsauswertung']
        self.assertEqual(len(data['rows']), 2)
        self.assertTrue(all(r['status'] == 'OK' for r in data['rows']))
        self.assertEqual(data['invoice'], 'RE-ST-2026-0042')
        html = rechnung_dashboard.render(data)
        self.assertIn('Prüfung ohne Positionsabweichung', html)
        self.assertIn('2.110,00 €', html)
        self.assertEqual(prepare(self.project, self.rec['id'])['revision'], 2)

    def test_deviation_does_not_look_like_success(self):
        result, _ = self.run_invoice([line.replace('910,00', '900,00') for line in RECHNUNG])
        self.assertEqual(result['status'], 'completed', result)
        html = rechnung_dashboard.render(result['rechnungsauswertung'])
        self.assertIn('Klärung erforderlich', html)
        self.assertIn('data-state="issue"', html)
        self.assertNotIn('Prüfung ohne Positionsabweichung', html)

    def test_local_privacy_node_forwards_only_approved_fields(self):
        from prepare_local_invoice import prepare as local_prepare
        self.rec=local_prepare(self.project,self.rec['id'])
        result,model=self.run_invoice(['Kontakt: nina@example.test; IBAN DE89370400440532013000; Nina Beispiel']+RECHNUNG)
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(self.rec['workflow']['name'],'Lokale Rechnungsprüfung')
        self.assertEqual(self.rec['workflow']['meta']['sedra_model']['provider'],'llama-cpp-server')
        sent=model.call_args.args[0][-1]['content']
        self.assertNotIn('nina@example.test',sent)
        self.assertNotIn('DE89370400440532013000',sent)
        self.assertNotIn('Nina Beispiel',sent)
        self.assertEqual(json.loads(sent)['Rechnungsnummer'],'RE-ST-2026-0042')
        self.assertEqual(json.loads(sent)['Rechnungsbetrag'],2510.90)
        self.assertTrue(any(n['name']=='Datenschutz – Rechnungsdaten minimieren' and n['status']=='ok' for n in result['knoten']))

    def test_local_auto_selection_ignores_unloaded_router_presets(self):
        from sedra_runtime.models.openai_local import OpenAICompatibleLocalAdapter
        adapter=OpenAICompatibleLocalAdapter('llama-cpp-server','http://127.0.0.1:8090')
        with mock.patch.object(adapter,'_request',return_value={'data':[{'id':'wrong-first','status':{'value':'unloaded'}},{'id':'actual','status':{'value':'loaded'}},{'id':'sleeping','status':{'value':'sleeping'}}]}):
            self.assertEqual(adapter.list_models(),['actual','sleeping'])

    def test_report_escapes_html_and_cannot_claim_success_without_data(self):
        data = {'workflow': '</script><img src=x onerror=alert(1)>', 'execution_status': 'failed', 'rows': [], 'steps': []}
        html = rechnung_dashboard.render(data)
        self.assertNotIn('<img src=x', html)
        self.assertNotIn('</script><img', html)
        self.assertIn('Technischer Lauf fehlgeschlagen', html)
        self.assertIn('Keine auswertbaren Positionsvergleiche', html)

    def test_nvidia_choice_reaches_router_without_local_fallback(self):
        calls = []
        router = SimpleNamespace(chat=lambda *a, **k: calls.append(k) or {'parsed': {'ok': True}})
        fn = _modell(SimpleNamespace(model_router=router), 'M-TEST', {'meta': {'sedra_model': {'provider': 'nvidia', 'model': 'test/model'}}})
        self.assertEqual(fn([{'role': 'user', 'content': 'Test'}], {'type': 'object'}), {'ok': True})
        self.assertEqual((calls[0]['provider'], calls[0]['model']), ('nvidia', 'test/model'))

    def test_cloud_structured_outputs_and_tool_calls_are_preserved(self):
        from sedra_runtime.models.cloud_api import CloudOpenAICompatibleAdapter
        adapter=CloudOpenAICompatibleAdapter('nvidia','https://example.test/v1','secret://nvidia/api-key','test-model',environ={'SEDRA_SECRET_NVIDIA_API_KEY':'test-key-not-real'})
        tool={'type':'function','function':{'name':'get_model_status','parameters':{'type':'object'}}}
        fmt={'type':'json_schema','json_schema':{'name':'data','strict':True,'schema':{'type':'object'}}}
        call={'id':'call-1','type':'function','function':{'name':'get_model_status','arguments':'{}'}}
        with mock.patch.object(adapter,'_post',return_value={'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[call]},'finish_reason':'tool_calls'}]}) as post:
            out=adapter.chat([{'role':'user','content':'Status?'}],tools=[tool],response_format=fmt)
        self.assertEqual(post.call_args.args[1]['tools'],[tool])
        self.assertEqual(post.call_args.args[1]['response_format'],fmt)
        self.assertEqual(out['message']['tool_calls'],[call])
        self.assertFalse(out['empty_answer'])

    def test_end_to_end_gate_to_registered_html_file(self):
        from sedra_runtime.uix_server import UIXHub
        from sedra_runtime.workflows.desk import _start, _run_read, _dashboard_read
        from sedra_runtime.workflows.lokal_daten import Eingaben
        from sedra_runtime.desk import systemdialog
        architecture=Path(__file__).resolve().parents[2] / 'architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
        hub=UIXHub(self.project,architecture)
        self.addCleanup(hub.close)
        systemdialog.setzen(lambda *a:None)
        self.addCleanup(systemdialog.setzen,None)
        model=mock.Mock(return_value={'parsed':{'Rechnungsnummer':'RE-ST-2026-0042','Rechnungsbetrag':2510.9,'Rechnungsdatum':'2026-11-12'}})
        newer=json.loads(json.dumps(self.rec['workflow']))
        newer['name']='Neuere Fassung darf diesen Test nicht ersetzen'
        WorkflowStore(self.project).save(newer,self.rec['id'],self.rec['revision'])
        with mock.patch.object(hub.runtime.model_router,'chat',model):
            file_id=Eingaben(self.project).speichern(pdf(RECHNUNG))
            run=_start(hub,self.rec['id'],{'revision':self.rec['revision'],'inputs':{'Rechnung':{'datei':file_id,'name':'Testrechnung.pdf'}}})
            self.assertEqual(run['state'],'CAPTAIN_REVIEW')
            mission=hub.runtime.missions.load(run['id'])
            self.assertEqual(mission['context']['n8n_workflow']['revision'],self.rec['revision'])
            self.assertEqual(mission['plan']['steps'][0]['workflow']['name'],self.rec['workflow']['name'])
            gate=mission['human_gates']['pending'][0]
            mission['execution']['approval_token']=hub.runtime.guard.approve(gate)
            mission['human_gates']['pending']=[]
            hub.runtime.missions.save(mission)
            hub.run_mission({'mission_id':run['id']})
            finished=_run_read(hub,run['id'])
        self.assertEqual(finished['state'],'COMPLETE',finished)
        self.assertEqual(finished['result']['dashboard']['status'],'created')
        record=hub.runtime.artifacts.get(finished['result']['dashboard']['artifact_id'])
        self.assertTrue(Path(record['path']).is_file())
        downloaded=_dashboard_read(hub,run['id'],{})
        self.assertEqual(downloaded['filename'],'rechnung-dashboard.html')
        self.assertEqual(downloaded['html'],Path(record['path']).read_bytes().decode('utf-8'))
        self.assertIn('2.110,00 €',downloaded['html'])

    def test_chats_keep_independent_models_after_reopening(self):
        store = Sitzungen(self.project / 'sessions')
        a, b = store.anlegen('p')['id'], store.anlegen('p')['id']
        store.modell_waehlen(a, 'local/model', provider='llama-cpp-server')
        store.modell_waehlen(b, 'cloud/model', provider='nvidia')
        reopened = Sitzungen(self.project / 'sessions')
        self.assertEqual((reopened.laden(a)['provider'], reopened.laden(a)['modell']), ('llama-cpp-server', 'local/model'))
        self.assertEqual((reopened.laden(b)['provider'], reopened.laden(b)['modell']), ('nvidia', 'cloud/model'))
        api = SimpleNamespace(hub=SimpleNamespace(runtime=SimpleNamespace(model_router=SimpleNamespace(adapters={
            'nvidia': SimpleNamespace(health=lambda: True, default_model='default/model')}))), geladen=lambda: (_ for _ in ()).throw(AssertionError('Local GPU queried')))
        models, error = loaded(api, reopened.laden(b))
        self.assertIsNone(error)
        self.assertEqual(models[0]['identifier'], 'cloud/model')

    def test_missing_selected_local_model_is_not_replaced_silently(self):
        api=SimpleNamespace(geladen=lambda:([{'identifier':'other-model','modelKey':'other-key'}],None))
        models,error=loaded(api,{'provider':'llama-cpp-server','modell':'selected-model'})
        self.assertEqual(models,[])
        self.assertIn('nicht geladen',error)


if __name__ == '__main__':
    unittest.main()
