"""Reviewed offline image archive import; no VM, pull or automatic qualification."""
import hashlib
import os
from pathlib import Path
import re
import uuid
from ..tools.base import ToolValidationError
from ..models.tuning import digest
from ..core.util import atomic_write_json, utcnow

MAX_ARCHIVE_BYTES = 2 * 1024**3


def file_hash(path, destination=None):
    total = 0; sha = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024*1024):
            total += len(block)
            if total > MAX_ARCHIVE_BYTES: raise ToolValidationError('image_archive_size_limit')
            sha.update(block)
            if destination: destination.write(block)
    if not total: raise ToolValidationError('image_archive_empty')
    return total, sha.hexdigest()


def preview_image(broker, archive_path, expected_archive_sha256, image_reference):
    if not isinstance(archive_path, str) or Path(archive_path).is_absolute() or '\\' in archive_path or any(p in {'','..','.'} or p.startswith('.') for p in archive_path.split('/')):
        raise ToolValidationError('relative_image_archive_required')
    if not isinstance(expected_archive_sha256, str) or not re.fullmatch('[0-9a-f]{64}',expected_archive_sha256):
        raise ToolValidationError('image_archive_sha256_required')
    if not isinstance(image_reference, str) or not re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}',image_reference):
        raise ToolValidationError('pinned_image_reference_required')
    path=broker._resolve(archive_path, must_exist=True)
    if not path.is_file() or path.stat().st_size>MAX_ARCHIVE_BYTES: raise ToolValidationError('image_archive_invalid')
    size, observed=file_hash(path)
    if observed != expected_archive_sha256: raise ToolValidationError('image_archive_checksum_mismatch')
    policy=broker.policy()
    plan={'schema':1,'kind':'offline_image_import','host_root':str(broker.root),
          'request':{'archive_path':archive_path,'expected_archive_sha256':expected_archive_sha256,'image_reference':image_reference},
          'archive_bytes':size,'policy':policy,'backend_home':str(broker.provider.home) if hasattr(broker.provider,'home') else None,
          'network':'no_download_requested','vm_started':False}
    plan['plan_digest']=digest(plan)
    return plan


def import_image(broker, mission_id, plan, approval_token=None):
    if not isinstance(plan,dict) or not isinstance(plan.get('request'),dict): raise ToolValidationError('image_import_plan_required')
    if preview_image(broker, **plan['request']) != plan: raise ToolValidationError('image_import_plan_changed')
    probe=broker.provider.probe()
    # Import needs the pinned SDK, not a VM/hypervisor or prior target qualification.
    blockers=[b for b in probe['blockers'] if b!='kvm_unavailable']
    if blockers or not callable(getattr(broker.provider,'import_image',None)):
        return {'status':'blocked','blockers':blockers or ['image_import_provider_unavailable']}
    if (broker.data_root/'active.lock').exists(): return {'status':'blocked','blockers':['sandbox_active_or_cleanup_pending']}
    target='image-import:'+plan['plan_digest'];action='sandbox_image_import'
    verdict=broker.guard.evaluate(action,mission_id=mission_id,target=target)
    if verdict['decision']=='BLOCK':return {'status':'blocked','guard':verdict}
    if verdict['decision']=='CAPTAIN_REQUIRED' and not broker.guard.authorize(approval_token,mission_id=mission_id,action=action,target=target,request_binding=plan)['authorized']:
        return {'status':'captain_required','gate':broker.guard.create_gate(mission_id,action,target,
                risks=['Import reviewed image archive into local SDK cache; native archive parser; no VM or pull'],
                rollback_available=False,request_binding=plan)}
    broker.data_root.mkdir(parents=True,exist_ok=True)
    job_id='IMG-'+uuid.uuid4().hex;lock=broker.data_root/'active.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:return {'status':'blocked','blockers':['sandbox_active_or_cleanup_pending']}
    os.write(fd,job_id.encode());os.close(fd)
    job=broker.data_root/'image-imports'/job_id;job.mkdir(parents=True)
    record={'schema':1,'job_id':job_id,'mission_id':mission_id,'created_at':utcnow(),'status':'RUNNING','plan':plan,'vm_started':False,'target_qualified':False}
    atomic_write_json(job/'report.json',record)
    confirmed=True
    try:
        source=broker._resolve(plan['request']['archive_path'],must_exist=True)
        staged=job/'image.archive'
        with staged.open('xb') as out:size,sha=file_hash(source,out)
        if size!=plan['archive_bytes'] or sha!=plan['request']['expected_archive_sha256']:raise ToolValidationError('image_changed_during_staging')
        confirmed=False
        response=broker.provider.import_image({'archive':str(staged),'image_reference':plan['request']['image_reference']},job)
        confirmed=isinstance(response,dict) and response.get('operation_confirmed') is True
        if not confirmed:raise ToolValidationError('image_import_outcome_unconfirmed')
        if response.get('status')!='PASS' or response.get('manifest_digest')!=plan['request']['image_reference'].rsplit('@',1)[1] or response.get('image_reference')!=plan['request']['image_reference']:
            raise ToolValidationError('imported_image_digest_or_status_mismatch')
        record.update(status='IMPORTED_NOT_QUALIFIED',manifest_digest=response['manifest_digest'],qualification=broker.result_qualification())
        return {'status':'completed','image_import':record,'target_qualified':False}
    except Exception as exc:
        record.update(status='FAILED' if confirmed else 'IMPORT_OUTCOME_UNCONFIRMED',error=f'{type(exc).__name__}:{exc}')
        return {'status':'failed','image_import':record,'target_qualified':False}
    finally:
        record.update(finished_at=utcnow(),operation_confirmed=confirmed)
        staged_copy=job/'image.archive'
        if confirmed and staged_copy.exists():
            # The private copy only matters while the SDK reads it; afterwards the SDK cache holds the image and the report keeps
            # hash and size. Five kept copies of 132 MB each were found on 2026-10-02. An unconfirmed outcome keeps it as evidence.
            try:
                staged_copy.unlink(); record['staged_archive_removed']=True
            except OSError:
                record['staged_archive_removed']=False
        atomic_write_json(job/'report.json',record)
        if confirmed:lock.unlink(missing_ok=True)
        broker._audit('IMAGE_IMPORT_FINISHED',mission_id,{'job_id':job_id,'status':record['status'],'operation_confirmed':confirmed})
