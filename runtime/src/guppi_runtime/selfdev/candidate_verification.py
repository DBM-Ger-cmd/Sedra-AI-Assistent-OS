"""Candidate preparation is verified separately from test/merge qualification."""
import difflib
import hashlib
import json
from pathlib import Path
import re
from ..selfdev.execution_binder import BindingError


def verify_candidate(verifier,mission):
    evidence=[];findings=[]
    try:
        binder=verifier.inspection_binder;binding=mission['plan']['steps'][0]['binding']
        binder.revalidate_candidate(mission,binding)
        if mission['plan']['acceptance_criteria']!=[{'type':'code_candidate_preparation','binding_digest':binding['digest']}]:raise BindingError('candidate_criteria_changed')
        mid=mission['identity']['mission_id'];path=verifier.workspace/mid/'candidate-report.json'
        path.resolve().relative_to(verifier.workspace.resolve())
        if path.is_symlink() or not path.is_file() or path.stat().st_size>2000000:raise BindingError('candidate_report_missing_or_invalid')
        with path.open('rb') as stream:raw=stream.read(2000001)
        if len(raw)>2000000:raise BindingError('candidate_report_oversize')
        record=next((a for a in mission['execution']['artifacts'] if Path(a['path'])==path),None)
        if not record or hashlib.sha256(raw).hexdigest()!=record['integrity']['hash']:raise BindingError('candidate_report_integrity_failed')
        report=json.loads(raw)
        if report.get('schema')!=1 or report.get('kind')!='code_candidate_preparation' or report.get('mission_id')!=mid or report.get('binding_digest')!=binding['digest']:raise BindingError('candidate_report_identity_mismatch')
        if report.get('qualification')!='PREPARED_NOT_TESTED' or report.get('captain_review')!='PENDING' or any(report.get(k) is not False for k in ('tests_executed','host_code_executed','source_modified','ready_for_merge')):raise BindingError('candidate_qualification_claim_invalid')
        stage=report.get('candidate')
        if not isinstance(stage,str) or not re.fullmatch(binder.STAGING+'/'+re.escape(mid)+r'-[0-9a-f]{32}/project',stage):raise BindingError('candidate_stage_outside_namespace')
        inputs=binding['inputs'];source_records,source=binder.source(mission,inputs)
        if report['source']!=inputs['project_path'] or report['source_files']!=source_records or source_records!=binding['source_files']:raise BindingError('source_manifest_changed')
        expected=dict(source);expected.update({c['path']:c['content'] for c in inputs['changes']})
        if len(report['candidate_files'])!=len(expected) or [f['path'] for f in report['candidate_files']]!=list(expected):raise BindingError('candidate_selection_mismatch')
        selected={t['id'] for t in mission['routing']['route']['tools']}
        if 'filesystem' not in selected:raise BindingError('verification_filesystem_not_selected')
        # Recursively enumerate at most the declared files plus their parent folders.
        permitted=set(expected)
        for f in expected:
            permitted.update(str(p) for p in Path(f).parents if str(p)!='.')
        root=binder.filesystem._resolve(stage,must_exist=True)
        todo=[root];seen=[]
        while todo:
            directory=todo.pop()
            listing=verifier.tools.execute('filesystem',mid,'list_dir',{'path':str(directory.relative_to(binder.filesystem.root)),'limit':200,'bounded':True})
            if listing.get('status')!='completed' or listing['truncated']:raise BindingError('candidate_inventory_unavailable')
            for item in listing['entries']:
                rel=(directory/item['name']).relative_to(root).as_posix()
                if rel not in permitted or item['type'] not in {'file','dir'}:raise BindingError('candidate_unexpected_entry')
                if item['type']=='dir':todo.append(directory/item['name'])
                else:seen.append(rel)
        if set(seen)!=set(expected):raise BindingError('candidate_files_missing')
        checks=[]
        for file,content in expected.items():
            out=verifier.tools.execute('filesystem',mid,'read_text',{'path':stage+'/'+file,'encoding':'utf-8','max_bytes':binder.MAX_FILE_BYTES})
            if out.get('status')!='completed' or out['content']!=content:raise BindingError('candidate_content_mismatch')
            observed={'path':file,'bytes':out['bytes'],'sha256':hashlib.sha256(out['content'].encode('utf-8')).hexdigest()}
            if observed!=next(f for f in report['candidate_files'] if f['path']==file):raise BindingError('candidate_manifest_mismatch')
        for change in inputs['changes']:checks.append({'path':change['path'],'check':binder.static_check(change['path'],change['content'])})
        if report['static_checks']!=checks or checks!=binding['static_checks']:raise BindingError('candidate_static_checks_mismatch')
        diffs=[''.join(difflib.unified_diff(source[c['path']].splitlines(keepends=True),c['content'].splitlines(keepends=True),fromfile='source/'+c['path'],tofile='candidate/'+c['path'])) for c in inputs['changes']]
        if report['diff']!=diffs:raise BindingError('candidate_diff_mismatch')
        if inputs.get('test_commands'):
            if 'sandbox' not in selected:raise BindingError('sandbox_not_selected')
            preview=verifier.tools.execute('sandbox',mid,'preview',{'source':stage,'commands':inputs['test_commands'],'exports':[]})
            if preview.get('status')!='completed' or preview['plan']!=report['sandbox_plan']:raise BindingError('sandbox_preview_changed')
        elif report['sandbox_plan'] is not None:raise BindingError('unexpected_test_plan')
        binder.revalidate_candidate(mission,binding)
        evidence.append({'criterion':'code_candidate_preparation','artifact_id':record['artifact_id'],'verified_files':len(expected),
                         'qualification':'PREPARED_NOT_TESTED','tests_executed':False,'ready_for_merge':False})
    except Exception as exc:findings.append(f'{type(exc).__name__}:{exc}')
    return {'status':'FAIL' if findings else 'PASS','findings':findings,'evidence':evidence,
            'qualification':'PREPARED_NOT_TESTED','rework_request':{'reason':findings} if findings else None}
