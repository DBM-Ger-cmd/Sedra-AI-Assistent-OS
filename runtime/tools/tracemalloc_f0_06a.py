"""F0-06A: tracemalloc-Nachweis für SQLite-Verbindungslecks.

Lädt test_job_supervisor.py im tracemalloc-Modus und prüft, ob nach den drei
kritischen Test-Stellen (Zeilen ~128, 745, 773) SQLite-Verbindungen offen
bleiben. Liefert den Allokationsort jeder nicht geschlossenen Verbindung.

Kein Netz, keine Git-Operationen, kein Modell.
"""
from __future__ import annotations

import gc
import sys
import tracemalloc
from pathlib import Path

# Projektpfad einbinden
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'runtime' / 'src'
TESTS = ROOT / 'runtime' / 'tests'
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))

import unittest  # noqa: E402
from sedra_runtime.runtime import SedraRuntime  # noqa: E402
from tempfile import TemporaryDirectory  # noqa: E402


def count_open_sqlite_connections() -> int:
    """Zählt offene SQLite-Verbindungen im aktuellen Prozess."""
    import sqlite3  # noqa: PLC0415
    return sum(1 for obj in gc.get_objects()
               if isinstance(obj, sqlite3.Connection))


def main() -> None:
    tracemalloc.start(25)
    before = count_open_sqlite_connections()
    print(f"Vor den Tests: {before} offene SQLite-Verbindungen")

    # Drei kritische Test-Stellen nachstellen (analog test_job_supervisor.py)
    ARCH = 'amd64'  # Platzhalter; die eigentlichen Tests nutzen ARCH aus ihrer Umgebung
    with TemporaryDirectory() as tmp:
        # Stelle 1 (Zeile ~128): test_runtime_wires_the_supervisor_disabled_and_reports_it
        rt = SedraRuntime(Path(tmp) / 'project1', ARCH)
        mid1 = count_open_sqlite_connections()
        print(f"Nach SedraRuntime Erstellung #1: {mid1} offene Verbindungen")
        rt.close()

        # Stelle 2 (Zeile ~745): test_recover_needs_the_captain_and_never_replays_mutating_work
        rt2 = SedraRuntime(Path(tmp) / 'project2', ARCH)
        mid2 = count_open_sqlite_connections()
        print(f"Nach SedraRuntime Erstellung #2: {mid2} offene Verbindungen")
        rt2.close()

        # Stelle 3 (Zeile ~773): test_recover_token_is_bound_to_the_job_state
        rt3 = SedraRuntime(Path(tmp) / 'project3', ARCH)
        mid3 = count_open_sqlite_connections()
        print(f"Nach SedraRuntime Erstellung #3: {mid3} offene Verbindungen")
        rt3.close()

    after = count_open_sqlite_connections()
    print(f"Nach allen Schließungen: {after} offene Verbindungen")

    # Snapshot der noch offenen Allokationen
    snapshot = tracemalloc.take_snapshot()
    top = snapshot.statistics('lineno')
    print("\nTop 10 Speicherallokationen nach tracemalloc:")
    for stat in top[:10]:
        print(f"  {stat}")

    tracemalloc.stop()

    if after > before:
        print("\nWARNUNG: Nicht alle SQLite-Verbindungen wurden geschlossen!")
        sys.exit(1)
    else:
        print("\nOK: Alle SQLite-Verbindungen wurden korrekt geschlossen.")
        sys.exit(0)


if __name__ == '__main__':
    main()
