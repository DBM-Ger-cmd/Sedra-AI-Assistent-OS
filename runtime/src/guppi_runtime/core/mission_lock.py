"""OS advisory locks release on process death; no automatic stale-file deletion."""
from contextlib import contextmanager
import os


@contextmanager
def exclusive(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise RuntimeError('mission_lock_symlink')
    stream=path.open('a+b');locked=False
    try:
        if os.name=='nt':
            import msvcrt
            if path.stat().st_size==0:stream.write(b'0');stream.flush()
            stream.seek(0)
            try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as exc:raise RuntimeError('mission_execution_busy') from exc
        elif os.name=='posix':
            import fcntl
            try:fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as exc:raise RuntimeError('mission_execution_busy') from exc
        else:raise RuntimeError('mission_lock_platform_unsupported')
        locked=True;yield
    finally:
        if locked:
            if os.name=='nt':
                stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
        stream.close()
