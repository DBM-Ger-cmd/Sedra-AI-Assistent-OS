"""F0-06A: SQLite-Verbindungslecks beheben.

Das Problem: rt.close() schließt nicht alle SQLite-Verbindungen.
Analyse zeigte: rt.close() ruft orchestra.close() und wissen.schliessen(),
aber es gibt weitere SQLite-Verbindungen die nicht geschlossen werden.

Fix: In rt.close() auch alle bekannten sqlite3.Connection-Objekte schließen.
"""
from __future__ import annotations

import gc
import sqlite3
from pathlib import Path
from sedra_runtime.runtime import SedraRuntime
from tempfile import TemporaryDirectory


def count_open_connections():
    return sum(1 for obj in gc.get_objects()
               if isinstance(obj, sqlite3.Connection))


def test_before_fix():
    """Zeigt das Problem vor dem Fix."""
    import gc
    import sqlite3
    import tracemalloc
    from sedra_runtime.runtime import SedraRuntime
    from tempfile import TemporaryDirectory
    from pathlib import Path

    ARCH = Path('E:/Sedra Umgebung/A1 Sedra Main Branch Entwicklungs umgebung/architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT')
    
    tracemalloc.start(25)
    before = sum(1 for obj in gc.get_objects() if isinstance(obj, sqlite3.Connection))
    print(f"Vor den Tests: {before} offene Verbindungen")

    with TemporaryDirectory() as tmp:
        rt = SedraRuntime(Path(tmp) / 'project1', Path('E:/Sedra Umgebung/A1 Sedra Main Branch Entwicklungs umgebung/architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'))
        print(f"Nach Erstellung: {sum(1 for obj in gc.get_objects() if isinstance(obj, sqlite3.Connection))} Verbindungen")
        rt.close()
        print(f"Nach rt.close(): {sum(1 for obj in gc.get_objects() if isinstance(obj, sqlite3.Connection))} Verbindungen")

    tracemalloc.stop()


if __name__ == '__main__':
    test_before_fix()