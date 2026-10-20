"""Bounded local topic drafts. These records never grant skills or permissions."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
from .core.util import atomic_write_json, load_json, utcnow


class TopicStore:
    MAX_TOPICS = 64

    def __init__(self, root, audit=None):
        self.root = Path(root)
        self.audit = audit

    @staticmethod
    def normalize(text):
        if not isinstance(text, str): raise ValueError('topic_text_required')
        text = re.sub(r'\s+', ' ', text).strip()
        if not text or any(ord(c) < 32 for c in text): raise ValueError('invalid_topic_text')
        return text

    def list(self):
        path = self.root / 'drafts.json'
        if path.exists() and path.stat().st_size > 262144: raise ValueError('topic_store_oversize')
        value = load_json(self.root / 'drafts.json', {'schema': 1, 'topics': {}})
        if not isinstance(value, dict) or value.get('schema') != 1 or not isinstance(value.get('topics'), dict):
            raise ValueError('invalid_topic_store')
        if len(value['topics']) > self.MAX_TOPICS: raise ValueError('topic_store_limit')
        # Reject executable fields even if the local record was hand-edited.
        for tid, record in value['topics'].items():
            expected = {'id', 'label', 'description', 'status', 'origin', 'created_at', 'examples'}
            if not isinstance(record, dict) or set(record) != expected or record['id'] != tid or record['status'] != 'draft':
                raise ValueError('invalid_topic_draft')
            if not isinstance(record['label'], str) or not 1 <= len(record['label']) <= 100:
                raise ValueError('invalid_topic_label')
            expected_id = 'custom-' + hashlib.sha256(record['label'].casefold().encode()).hexdigest()[:16]
            if tid != expected_id or record['origin'] not in {'captain','router-gap'} or self.normalize(record['label']) != record['label']:
                raise ValueError('invalid_topic_identity')
            if not isinstance(record['description'], str) or len(record['description']) > 500:
                raise ValueError('invalid_topic_description')
            if not isinstance(record['examples'], list) or len(record['examples']) > 5 or any(not isinstance(x,str) or len(x)>500 for x in record['examples']):
                raise ValueError('invalid_topic_examples')
        return value['topics']

    @contextmanager
    def mutation(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / 'mutation.lock'
        try: fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError: raise RuntimeError('topic_store_busy_or_interrupted')
        try:
            os.close(fd)
            yield
        finally: lock.unlink(missing_ok=True)

    def propose(self, title, description='', example='', origin='captain'):
        title = self.normalize(title)
        if len(title) > 100: raise ValueError('topic_title_too_long')
        if not isinstance(description,str) or len(description)>500: raise ValueError('invalid_topic_description')
        if not isinstance(example,str) or len(example)>500: raise ValueError('invalid_topic_example')
        if origin not in {'captain', 'router-gap'}: raise ValueError('invalid_topic_origin')
        tid = 'custom-' + hashlib.sha256(title.casefold().encode()).hexdigest()[:16]
        with self.mutation():
            records = self.list()
            if tid not in records:
                if len(records) >= self.MAX_TOPICS: raise ValueError('topic_draft_capacity_reached')
                records[tid] = {'id': tid, 'label': title, 'description': description,
                                'status': 'draft', 'origin': origin, 'created_at': utcnow(), 'examples': []}
            if example and example not in records[tid]['examples']:
                records[tid]['examples'] = (records[tid]['examples'] + [example])[-5:]
            atomic_write_json(self.root / 'drafts.json', {'schema': 1, 'topics': records})
        if self.audit:
            self.audit.append('TOPIC_DRAFT_RECORDED', component='capability-router', payload={'topic_id':tid,'origin':origin})
        return records[tid]

    def match(self, text):
        return [r for r in self.list().values()
                if re.search(r'(?<!\w)' + re.escape(r['label'].casefold()) + r'(?!\w)', text)]
