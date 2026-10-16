from __future__ import annotations
from pathlib import Path
import hashlib, json, os, tempfile, threading, time
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def _replace_with_retry(src, dst, attempts=12):
    """os.replace, retried briefly on Windows PermissionError.

    On Windows another process (virus scanner, indexer, a reader without FILE_SHARE_DELETE) can hold the target
    for a few milliseconds; the rename then fails although nothing is wrong. Other errors are raised at once.
    """
    for attempt in range(attempts):
        try:
            os.replace(src,dst); return
        except PermissionError:
            if os.name!='nt' or attempt==attempts-1: raise
            time.sleep(0.01*(attempt+1))

def atomic_write_text(path: Path, text: str):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', dir=str(path.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        _replace_with_retry(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def atomic_write_bytes(path: Path, data: bytes):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        _replace_with_retry(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def atomic_write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', dir=str(path.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2,sort_keys=False)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        _replace_with_retry(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def read_last_jsonl(path: Path):
    """Return the last non-empty JSON line of an append-only log without reading the whole file."""
    path=Path(path)
    if not path.exists():
        return None
    with path.open('rb') as f:
        position=f.seek(0,2)
        buf=b''
        while position>0:
            step=min(8192,position); position-=step
            f.seek(position); buf=f.read(step)+buf
            body=buf.rstrip(b'\r\n \t')
            if not body:
                continue
            cut=body.rfind(b'\n')
            if cut!=-1 or position==0:
                return json.loads(body[cut+1:].decode('utf-8'))
    return None

# Bound at import so tests that patch time.monotonic for other modules cannot starve the lock loop.
_monotonic=time.monotonic
_sleep=time.sleep
_APPEND_THREAD_LOCKS={}
_APPEND_GUARD=threading.Lock()
_APPEND_HELD=threading.local()

@contextmanager
def append_lock(path: Path, timeout: float=10.0):
    """Serialize appends to one log across threads and processes (blocking, bounded wait)."""
    from .mission_lock import exclusive
    path=Path(path)
    with _APPEND_GUARD:
        thread_lock=_APPEND_THREAD_LOCKS.setdefault(str(path.resolve()),threading.RLock())
    with thread_lock:
        held=_APPEND_HELD.__dict__.setdefault('keys',{})
        key=str(path.resolve())
        if held.get(key):
            # Re-entrant use by the same thread: the OS lock is already ours (a second handle would block us).
            held[key]+=1
            try: yield
            finally: held[key]-=1
            return
        stack=ExitStack(); deadline=_monotonic()+timeout
        while True:
            try:
                stack.enter_context(exclusive(Path(str(path)+'.lock'))); break
            except RuntimeError as exc:
                if str(exc)!='mission_execution_busy' or _monotonic()>=deadline:
                    raise RuntimeError('append_lock_timeout') from exc
                _sleep(0.005)
        with stack:
            held[key]=1
            try: yield
            finally: held[key]=0

def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))
