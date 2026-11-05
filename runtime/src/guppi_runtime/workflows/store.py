"""Immutable revisions, optimistic concurrency and no paths supplied by clients."""
import json
import re
import uuid
from pathlib import Path
from ..core.mission_lock import exclusive
from ..core.request_binding import digest
from ..core.util import utcnow
from .schema import validate
from .process import has_process
from .versions import compare


class WorkflowStore:
    def __init__(self, project):
        self.root = Path(project).resolve() / 'runtime_data' / 'workflows'

    def _folder(self, wid):
        if not isinstance(wid, str) or not re.fullmatch('WF-[a-f0-9]{24}', wid):
            raise ValueError('invalid_workflow_id')
        path = self.root / wid
        for part in (self.root.parent, self.root, path):
            if part.is_symlink():
                raise ValueError('workflow_symlink_refused')
        return path

    def revisions(self, wid):
        path = self._folder(wid)
        return sorted(int(p.stem) for p in path.glob('*.json') if p.stem.isdigit())

    def read(self, wid, revision=None):
        revisions = self.revisions(wid)
        if not revisions:
            raise ValueError('workflow_not_found')
        if revision is None:
            revision = revisions[-1]
        if type(revision) is not int or revision not in revisions:
            raise ValueError('invalid_workflow_revision')
        previous_hash = None
        for number in range(1, revision + 1):
            path = self._folder(wid) / f'{number:06d}.json'
            if path.is_symlink():
                raise ValueError('workflow_symlink_refused')
            out = json.loads(path.read_text(encoding='utf-8'))
            validate(out['workflow'])
            if out['digest'] != digest(out['workflow']) or out['id'] != wid or out['revision'] != number:
                raise ValueError('workflow_integrity_failed')
            if 'record_digest' in out:
                fields = {k: v for k, v in out.items() if k != 'record_digest'}
                if out['record_digest'] != digest(fields) or out.get('previous_record_digest') != previous_hash:
                    raise ValueError('workflow_version_chain_invalid')
            previous_hash = out.get('record_digest') or digest(out)
        return out

    def save(self, workflow, wid=None, base_revision=None, change_note=None):
        doc = validate(workflow)
        if change_note is not None and (not isinstance(change_note, str) or not change_note.strip() or len(change_note) > 500):
            raise ValueError('invalid_version_change_note')
        if has_process(doc) and wid and not change_note:
            raise ValueError('process_version_change_note_required')
        if wid is None:
            wid = 'WF-' + uuid.uuid4().hex[:24]
            if base_revision is not None:
                raise ValueError('new_workflow_has_no_base_revision')
        path = self._folder(wid)
        path.mkdir(parents=True, exist_ok=True)
        with exclusive(path / 'revision.lock'):
            revisions = self.revisions(wid)
            latest = revisions[-1] if revisions else None
            if base_revision != latest:
                raise ValueError('workflow_revision_conflict')
            revision = (latest or 0) + 1
            previous = self.read(wid, latest) if latest else None
            out = {'id': wid, 'revision': revision, 'digest': digest(doc), 'saved_at': utcnow(), 'workflow': doc,
                   'change_note': (change_note or ('Erstfassung' if not latest else 'Workflow bearbeitet')).strip(),
                   'previous_revision': latest, 'previous_record_digest': (previous.get('record_digest') or digest(previous)) if previous else None,
                   'changes': compare(previous['workflow'] if previous else None, doc)}
            out['record_digest'] = digest(out)
            with (path / f'{revision:06d}.json').open('x', encoding='utf-8') as stream:
                json.dump(out, stream, ensure_ascii=False, allow_nan=False, indent=2)
                stream.flush()
                import os
                os.fsync(stream.fileno())
        return out

    def listing(self):
        if not self.root.exists():
            return []
        return [self.read(p.name) for p in sorted(self.root.iterdir()) if p.is_dir()]
