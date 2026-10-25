"""Thin switch for the slot store (Spec 2, S2.H1). The four slot tables were seeded here for the SEDRA build of `slot_store.py`
(`benchmarks/s2_schema_seed/slot_db.py`); in the package they live in `testlab.db` schema 2 (`testlab.SLOT_SCHEMA`, same text). This module only
keeps the two names the store imports, so `slot_store.py` stays as it was built."""
from contextlib import contextmanager

from .testlab import SLOT_SCHEMA as SCHEMA, TestLab


@contextmanager
def immediate(conn):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def open_db(path, busy_ms=30000):
    """A connection to the test lab file at `path`, migrated to schema 2 (with backup). Refuses when the migration failed."""
    lab = TestLab(path)
    if lab.schema_error:
        raise ValueError(lab.schema_error)
    conn = lab.connect()
    conn.execute(f"PRAGMA busy_timeout = {busy_ms}")
    return conn
