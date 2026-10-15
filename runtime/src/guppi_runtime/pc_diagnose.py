"""Collect prerequisites and weakness backlog; does not qualify a PC."""
import argparse, platform
from pathlib import Path
from .runtime import GuppiRuntime
from .readiness import build_report, initialization_failure
from .util import atomic_write_json

def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--architecture',required=True);args=p.parse_args(argv)
 root=Path(args.root).resolve()
 try:
  rt=GuppiRuntime(root,Path(args.architecture));report=build_report(rt)
  report['model_runtimes']=rt.model_router.status(check_health=False)
  report['portable_model_runtime']=rt.model_runtime.status()
 except Exception as exc:report=initialization_failure(exc)
 report['host']={'system':platform.system(),'machine':platform.machine(),'python':platform.python_version()}
 report['qualification']='PREREQUISITES_ONLY_NOT_PC_ACCEPTANCE'
 report['weakness_backlog']=[{'id':f'PC-{n+1:03}','finding':s,'status':'OPEN'} for n,s in enumerate(report['blockers']+report['warnings']+report['pending_acceptance'])]
 path=root/'runtime_data/reports/PC_DIAGNOSE_v1.20.json';atomic_write_json(path,report)
 print('Diagnosebericht:',path);print('Status:',report['status']);print('Offene Punkte:',len(report['weakness_backlog']))
 return 2 if report['blockers'] else 0
if __name__=='__main__':raise SystemExit(main())
