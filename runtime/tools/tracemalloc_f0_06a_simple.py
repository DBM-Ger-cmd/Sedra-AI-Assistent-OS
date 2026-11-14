"""F0-06A: Einfacher tracemalloc-Nachweis für SQLite-Verbindungslecks.

Instanziert SedraRuntime dreimal (analog den drei kritischen Test-Stellen in
test_job_supervisor.py) und prüft nach rt.close(), ob Verbindungen offen bleiben.
"""
from __future__ import annotations

import gc
import sqlite3
import sys
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'runtime' / 'src'
sys.path.insert(0, str(SRC))

from sedra_runtime.runtime import SedraRuntime  # noqa: E402
from tempfile import TemporaryDirectory  # noqa: E402


def count_open_connections() -> int:
    return sum(1 for obj in gc.get_objects()
               if isinstance(obj, sqlite3.Connection))


def main() -> int:
    tracemalloc.start(25)
    before = count_open_connections()
    print(f"Vor den Tests: {before} offene SQLite-Verbindungen")

    arch = Path(ROOT / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT')

    for i in range(1, 4):
        with TemporaryDirectory() as tmp:
            rt = SedraRuntime(Path(tmp) / f'project{i}', arch)
            mid = count_open_connections()
            print(f"Nach SedraRuntime Erstellung #{i}: {mid} offene Verbindungen")
            rt.close()
            after_close = count_open_connections()
            print(f"  Nach rt.close() #{i}: {after_close} offene Verbindungen")

    after = count_open_connections()
    print(f"\nNach allen Schließungen: {after} offene Verbindungen")

    snapshot = tracemalloc.take_snapshot()
    top = snapshot.statistics('lineno')
    print("\nTop 10 Speicherallokationen:")
    for stat in top[:10]:
        print(f"  {stat}")

    tracemalloc.stop()

    if after > before:
        print("\nWARNUNG: Nicht alle SQLite-Verbindungen wurden geschlossen!")
        return 1
    print("\nOK: Alle SQLite-Verbindungen wurden korrekt geschlossen.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
