"""Run the full invoice pipeline in a temporary project with real local/NVIDIA inference.
Only synthetic invoice data is used; the user's source project and tables are read-only.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import sys
from datetime import datetime, timezone

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tests'))
from test_workflow_lokal import RECHNUNG, pdf
import host_isolation
from sedra_runtime.workflows.store import WorkflowStore
from sedra_runtime.workflows.lokal_daten import Tabellen, Eingaben
from sedra_runtime.workflows.desk import _start, _run_read, _dashboard_read
from sedra_runtime.models.llamacpp import LlamaCppRouterAdapter
from sedra_runtime.models.cloud_api import provider_adapter
from sedra_runtime import cloud_settings
from sedra_runtime.desk import systemdialog
from sedra_runtime.uix_server import UIXHub


def main(args):
    source=WorkflowStore(args.source).read(args.workflow)
    doc=deepcopy(source['workflow'])
    doc['meta']['sedra_model']={'provider':args.provider,'model':args.model}
    doc['meta']['sedra_test_mode']='Vorführung mit synthetischer Testrechnung und echter '+('NVIDIA-API' if args.provider=='nvidia' else 'lokaler Modellantwort')
    doc['meta']['sedra_report_dir']='Auswertung'
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    host_isolation.setUpModule()
    try:
        with tempfile.TemporaryDirectory(prefix='sedra-invoice-live-') as folder:
            project=Path(folder)
            rec=WorkflowStore(project).save(doc)
            tables=Tabellen(project)
            names={n['name']:(n.get('parameters') or {}).get('dataTableId',{}).get('cachedResultName') for n in doc['nodes']}
            tables.importieren(names.get('Auftragsdaten abrufen') or 'Auftraege',json.dumps([{'auftragsnummer':'AUF-2026-ST-17','gesamt_brutto':2510.90}]))
            tables.importieren(names.get('Auftragspositionen abrufen') or 'Auftragspositionen',json.dumps([
                {'auftragsnummer':'AUF-2026-ST-17','lv_position':'01.01.0010','menge':1,'einzelpreis_netto':1200,'gesamtpreis_netto':1200},
                {'auftragsnummer':'AUF-2026-ST-17','lv_position':'01.01.0020','menge':20,'einzelpreis_netto':45.5,'gesamtpreis_netto':910}]))
            file=pdf(RECHNUNG);file_id=Eingaben(project).speichern(file)
            arch=Path(__file__).resolve().parents[2] / 'architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
            hub=UIXHub(project,arch)
            try:
                if args.provider=='nvidia':
                    cfg=cloud_settings.load_config(args.source)
                    if not cfg.get('enabled'):raise RuntimeError('configured_cloud_disabled')
                    adapter=provider_adapter(cfg,'nvidia',key_store=cloud_settings.CloudKeyStore(cloud_settings.key_store_path(args.source)),project_root=args.source)
                    if not adapter.health():raise RuntimeError('nvidia_credentials_unavailable')
                    hub.runtime.model_router.adapters['nvidia']=adapter
                    hub.runtime.content_guard.cloud_enabled=True
                else:hub.runtime.model_router.adapters['llama-cpp-server']=LlamaCppRouterAdapter(args.endpoint,timeout=180)
                systemdialog.setzen(lambda *a:None)
                run=_start(hub,rec['id'],{'revision':rec['revision'],'inputs':{'Rechnung':{'datei':file_id,'name':'Testrechnung.pdf'}}})
                if run['state']!='CAPTAIN_REVIEW':raise RuntimeError('expected_execution_gate')
                mission=hub.runtime.missions.load(run['id'])
                gate=mission['human_gates']['pending'][0]
                # The user explicitly requested this isolated test with synthetic data.
                mission['execution']['approval_token']=hub.runtime.guard.approve(gate)
                mission['human_gates']['pending']=[];hub.runtime.missions.save(mission)
                hub.run_mission({'mission_id':run['id']})
                finished=_run_read(hub,run['id']);result=finished.get('result') or {}
                summary={'created_at':datetime.now(timezone.utc).isoformat(),'provider':args.provider,'model':args.model,'run_id':run['id'],'state':finished['state'],
                         'status':result.get('status'),'dashboard':result.get('dashboard'),'error':result.get('fehler_text') or result.get('error'),
                         'nodes':[{'name':n['name'],'status':n['status']} for n in result.get('knoten',[])],
                         'source_revision':source['revision'],'synthetic_invoice':True,'real_model_inference':True}
                if (result.get('dashboard') or {}).get('status')=='created':
                    report=_dashboard_read(hub,run['id'],{})
                    (output / report['filename']).write_text(report['html'],encoding='utf-8')
                (output / 'Testrechnung.pdf').write_bytes(file)
                (output / 'pruefergebnis.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps(summary,ensure_ascii=True))
                if finished['state']!='COMPLETE' or result.get('status')!='completed' or (result.get('dashboard') or {}).get('status')!='created':return 1
                return 0
            finally:systemdialog.setzen(None);hub.close()
    finally:host_isolation.tearDownModule()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--workflow',required=True);p.add_argument('--provider',choices=['llama-cpp-server','nvidia'],required=True);p.add_argument('--model',required=True);p.add_argument('--endpoint',default='http://127.0.0.1:8090');p.add_argument('--output',type=Path,required=True)
    raise SystemExit(main(p.parse_args()))
