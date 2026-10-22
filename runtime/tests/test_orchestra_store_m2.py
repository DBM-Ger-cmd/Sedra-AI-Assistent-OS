"""Migration 2 der Orchestrierungs-Datenbank (Spec 1, D1.2, S1.H1, G2-S1-02).

Schema 1 mit Daten wird zu Schema 2; vorher sichert `open_db` die Datei (`orchestra.db.bak-<datum>`). Die Tabellen sind
wörtlich die der Saat `benchmarks/s1_schema2_seed/store.py`. Der Teilindex `ux_agents_root` weist eine zweite Wurzel auch per
SQL ab."""
import ast
import sqlite3
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.orchestra import store

RUNTIME = Path(__file__).resolve().parents[1]
SEED = RUNTIME / 'benchmarks' / 's1_schema2_seed' / 'store.py'
NOW = '2026-10-21T08:00:00Z'


def _seed_values():
    tree = ast.parse(SEED.read_text(encoding='utf-8'))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ('SCHEMA_VERSION', 'TABLES', 'MIGRATIONS'):
                out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


def _schema1_with_data(path):
    conn = store.open_db(path, target=1)
    conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, status, permission_level, created_at, updated_at)"
                 " VALUES ('a1', 'i1', 't', 'Chef', 'foreman', 'aktiv', 2, ?, ?)", (NOW, NOW))
    conn.execute("INSERT INTO tasks (id, title, state, created_by, created_at, updated_at) VALUES ('t1', 'Aufgabe', 'offen', 'captain', ?, ?)",
                 (NOW, NOW))
    conn.execute("INSERT INTO wakeups (agent_id, reason, due_at, created_at) VALUES ('a1', 'captain', ?, ?)", (NOW, NOW))
    conn.execute("INSERT INTO spend (agent_id, provider, tokens_out, ts) VALUES ('a1', 'lokal', 10, ?)", (NOW,))
    conn.close()


def _columns(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA table_info({table})')]


class SameAsSeed(unittest.TestCase):
    def test_schema_tables_and_migrations_are_the_seed_word_for_word(self):
        seed = _seed_values()
        self.assertEqual(store.SCHEMA_VERSION, 2)
        self.assertEqual(seed['SCHEMA_VERSION'], store.SCHEMA_VERSION)
        self.assertEqual(seed['TABLES'], store.TABLES)
        self.assertEqual(seed['MIGRATIONS'], store.MIGRATIONS)


class FromSchema1(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='orchestra-m2-')
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'orchestra' / 'orchestra.db'
        _schema1_with_data(self.path)

    def test_data_survives_and_new_columns_have_their_defaults(self):
        conn = store.open_db(self.path, stamp='20261021')
        self.addCleanup(conn.close)
        self.assertEqual(store.schema_version(conn), 2)
        agent = dict(conn.execute("SELECT * FROM agents WHERE id = 'a1'").fetchone())
        self.assertEqual((agent['name'], agent['can_delegate'], agent['max_parallel'], agent['pause_reason']), ('Chef', 0, 1, None))
        task = dict(conn.execute("SELECT * FROM tasks WHERE id = 't1'").fetchone())
        self.assertEqual((task['title'], task['origin'], task['max_level'], task['check_result']), ('Aufgabe', 'captain', None, None))
        self.assertEqual(conn.execute('SELECT estimated, tokens_out FROM spend').fetchone()[:], (0, 10))
        self.assertIn('idempotency_key', _columns(conn, 'wakeups'))
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertTrue(set(store.TABLES) <= names)

    def test_the_file_is_saved_before_the_migration(self):
        conn = store.open_db(self.path, stamp='20261021')
        conn.close()
        bak = Path(str(self.path) + '.bak-20261021')
        self.assertTrue(bak.exists())
        old = sqlite3.connect(bak)
        try:
            self.assertEqual(old.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0], '1')
            self.assertEqual(old.execute('SELECT name FROM agents').fetchone()[0], 'Chef')
            self.assertNotIn('can_delegate', _columns(old, 'agents'))
        finally:
            old.close()

    def test_a_second_backup_on_the_same_day_does_not_overwrite_the_first(self):
        Path(str(self.path) + '.bak-20261021').write_bytes(b'alt')
        store.open_db(self.path, stamp='20261021').close()
        self.assertEqual(Path(str(self.path) + '.bak-20261021').read_bytes(), b'alt')
        self.assertTrue(Path(str(self.path) + '.bak-20261021-2').exists())

    def test_no_backup_when_nothing_is_migrated_or_the_file_is_new(self):
        store.open_db(self.path, stamp='20261021').close()
        store.open_db(self.path, stamp='20261022').close()
        self.assertFalse(Path(str(self.path) + '.bak-20261022').exists())
        fresh = self.path.parent / 'neu.db'
        store.open_db(fresh, stamp='20261021').close()
        self.assertEqual(list(self.path.parent.glob('neu.db.bak-*')), [])

    def test_a_failing_migration_says_migration_and_keeps_schema_1(self):
        broken = dict(store.MIGRATIONS)
        broken[2] = store.MIGRATIONS[2] + ('CREATE TABLE agents (x)',)
        with self.assertRaisesRegex(ValueError, '^orchestra_db_error:migration$'):
            store.open_db(self.path, migrations=broken, stamp='20261021')
        conn = store.open_db(self.path, target=1)
        self.addCleanup(conn.close)
        self.assertEqual(store.schema_version(conn), 1)
        self.assertNotIn('can_delegate', _columns(conn, 'agents'))
        self.assertTrue(Path(str(self.path) + '.bak-20261021').exists())


class Constraints(unittest.TestCase):
    def setUp(self):
        self.conn = store.open_db(':memory:')
        self.addCleanup(self.conn.close)

    def _agent(self, aid, reports_to=None, status='aktiv'):
        self.conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, created_at,"
                          " updated_at) VALUES (?, ?, 't', ?, 'coder', ?, ?, 1, ?, ?)", (aid, 'i-' + aid, aid, reports_to, status, NOW, NOW))

    def test_ux_agents_root_rejects_a_second_root_in_sql(self):
        self._agent('a1')
        self._agent('a2', reports_to='a1')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'UNIQUE'):
            self._agent('a3')
        self._agent('a4', status='beendet')

    def test_new_checks_and_partial_indexes(self):
        self._agent('a1')
        bad = ["UPDATE agents SET can_delegate = 2", "UPDATE agents SET max_parallel = 5", "UPDATE agents SET pause_reason = 'urlaub'"]
        for sql in bad:
            with self.subTest(sql), self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute(sql)
        self.conn.execute("INSERT INTO wakeups (agent_id, reason, due_at, created_at, idempotency_key) VALUES ('a1', 'captain', ?, ?, 'k')",
                          (NOW, NOW))
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'UNIQUE'):
            self.conn.execute("INSERT INTO wakeups (agent_id, reason, due_at, created_at, idempotency_key) VALUES ('a1', 'captain', ?, ?,"
                              " 'k')", (NOW, NOW))
        row = ("INSERT INTO standing_approvals (token_id, agent_id, granted_at, expires_at, max_uses, status, fingerprint_digest,"
               " updated_at) VALUES (?, 'a1', ?, ?, 5, 'aktiv', 'd', ?)")
        self.conn.execute(row, ('STD-1', NOW, NOW, NOW))
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'UNIQUE'):
            self.conn.execute(row, ('STD-2', NOW, NOW, NOW))
        inc = "INSERT INTO budget_incidents (agent_id, kind, percent, used_tokens, created_at) VALUES ('a1', 'stopp', 100, 10, ?)"
        self.conn.execute(inc, (NOW,))
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'UNIQUE'):
            self.conn.execute(inc, (NOW,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO agent_messages (agent_id, rolle, text, ts, status) VALUES ('a1', 'captain', ?, ?, 'angenommen')",
                              ('x' * 8001, NOW))


if __name__ == '__main__':
    unittest.main()
