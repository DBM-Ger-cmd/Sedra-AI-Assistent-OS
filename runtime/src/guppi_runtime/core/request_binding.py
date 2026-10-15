"""Bounded content fingerprints for concrete Captain requests."""
import hashlib
import json
from pathlib import Path


def digest(value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
    if len(raw)>8_000_000: raise ValueError('request_binding_too_large')
    return hashlib.sha256(raw).hexdigest()


def path_state(path):
    path=Path(path)
    if path.is_symlink(): raise ValueError('binding_symlink_not_allowed')
    if not path.exists(): return {'kind':'absent'}
    records=[]; budget=64_000_000
    def visit(item):
        nonlocal budget
        if len(records)>=2000: raise ValueError('binding_entry_budget')
        rel=str(item.relative_to(path)) if item!=path else '.'
        if item.is_symlink(): raise ValueError('binding_symlink_not_allowed')
        if item.is_dir():
            records.append([rel,'directory'])
            # Bound enumeration before sorting; no unbounded list of a hostile directory.
            children=[]
            for child in item.iterdir():
                children.append(child)
                if len(children)>2000: raise ValueError('binding_entry_budget')
            for child in sorted(children): visit(child)
        elif item.is_file():
            h=hashlib.sha256(); size=0
            with item.open('rb') as stream:
                while True:
                    raw=stream.read(min(65536,budget+1))
                    if not raw: break
                    budget-=len(raw); size+=len(raw)
                    if budget<0: raise ValueError('binding_byte_budget')
                    h.update(raw)
            records.append([rel,'file',size,h.hexdigest()])
        else: raise ValueError('binding_special_file_not_allowed')
    visit(path)
    return {'kind':'tree' if path.is_dir() else 'file','digest':digest(records)}


def file_request(operation,args,*paths):
    return {'operation':operation,'args_digest':digest(args),
            'preconditions':[{ 'path':str(Path(p).resolve()),'state':path_state(p)} for p in paths]}
