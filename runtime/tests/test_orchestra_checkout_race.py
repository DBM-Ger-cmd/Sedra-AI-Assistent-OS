"""ORC-04 (Spec 1, D1.7): zwei Prozesse greifen gleichzeitig nach derselben Aufgabe; 100 Durchläufe auf einer temporären Datenbank.
Genau einer gewinnt, der andere bekommt `task_already_checked_out`, und `checkout_by` nennt den Sieger.

Die zwei Prozesse starten einmal (spawn) und laufen die Durchläufe nacheinander ab; eine Schranke je Durchlauf lässt beide im selben
Augenblick zugreifen."""
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.orchestra import board
from guppi_runtime.orchestra.store import open_db

ROUNDS = 100
NOW = '2026-10-22T08:00:00Z'


def _grab(db_path, name, barrier, out, rounds):
    conn = open_db(Path(db_path))
    try:
        for n in range(rounds):
            barrier.wait(60)
            try:
                board.checkout(conn, f'T{n}', 'A1', f'run-{name}-{n}', NOW)
                out.put((n, name, 'ok'))
            except ValueError as exc:
                out.put((n, name, str(exc)))
    finally:
        conn.close()


class CheckoutRace(unittest.TestCase):
    def test_100_rounds_two_processes_exactly_one_winner(self):
        with tempfile.TemporaryDirectory(prefix='orchestra-race-') as tmp:
            db = Path(tmp) / 'orchestra.db'
            conn = open_db(db)
            conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, status, permission_level, created_at, updated_at)"
                         " VALUES ('A1', 'i-A1', 't', 'A1', 'coder', 'aktiv', 2, ?, ?)", (NOW, NOW))
            for n in range(ROUNDS):
                board.create(conn, dict(id=f'T{n}', title=f'Aufgabe {n}', assignee='A1'), NOW, 'captain')
            conn.close()
            ctx = multiprocessing.get_context('spawn')
            barrier, out = ctx.Barrier(2), ctx.Queue()
            procs = [ctx.Process(target=_grab, args=(str(db), name, barrier, out, ROUNDS)) for name in ('p1', 'p2')]
            for p in procs:
                p.start()
            results = [out.get(timeout=120) for _ in range(2 * ROUNDS)]
            for p in procs:
                p.join(30)
            for n in range(ROUNDS):
                got = sorted((name, res) for r, name, res in results if r == n)
                winners = [name for name, res in got if res == 'ok']
                losers = [res for name, res in got if res != 'ok']
                self.assertEqual((len(winners), losers), (1, ['task_already_checked_out']), f'Durchlauf {n}: {got}')
            conn = open_db(db)
            try:
                for n in range(ROUNDS):
                    row = conn.execute('SELECT checkout_by, checkout_run FROM tasks WHERE id = ?', (f'T{n}',)).fetchone()
                    winner = next(name for r, name, res in results if r == n and res == 'ok')
                    self.assertEqual((row[0], row[1]), ('A1', f'run-{winner}-{n}'), f'Durchlauf {n}')
            finally:
                conn.close()


if __name__ == '__main__':
    unittest.main()
