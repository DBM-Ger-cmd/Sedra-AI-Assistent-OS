"""Der Takt der Orchestrierung (Spec 1, ORC-16, D1.1 `tick.py`, D1.5, D1.7, S1.H6).

Fake-Uhr über die Uhr der Fassade, Fake-Supervisor, Fake-Guard und Fake-Lauf/Antrag (die echten baut der Desk in S1.H7/H8).
`tick()` ruft Routinen und Weckrufe; ohne Dauerfreigabe entsteht ein Antrag statt eines Laufs; Supervisor aus heißt: kein Lauf,
Weckruf offen, einmal `ORC_TICK_ERROR`; ein zweiter Takter bekommt `tick_busy`; `boot()["orchestra"]["takt"]`; nach 3 × tick_s
ohne Takt `laeuft: false`."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.orchestra import board, heartbeat, routines, service, tick
from guppi_runtime.orchestra.config import OrchestraConfig
from guppi_runtime.orchestra.store import open_db

RUNTIME = Path(__file__).resolve().parents[1]
CONFIG = RUNTIME / 'config' / 'orchestra.yaml'
T0 = '2026-10-22T08:00:00Z'


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


class FakeGuard:
    def __init__(self, standing=False):
        self.standing, self.used, self.revoked = standing, [], []

    def authorize_standing(self, agent_id, *, fingerprint, budget_stage, run_ref):
        self.used.append((agent_id, budget_stage, run_ref))
        return {'authorized': True, 'uses': 1} if self.standing else {'authorized': False, 'reason': 'no_standing_approval'}

    def revoke_standing(self, agent_id, *, reason):
        self.revoked.append((agent_id, reason))
        return 1


class FakeStore:
    def __init__(self):
        self.jobs = {}

    def load(self, job_id):
        return self.jobs[job_id]


class FakeSupervisor:
    def __init__(self, enabled=True):
        self.enabled, self.store = enabled, FakeStore()


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='orchestra-tick-')
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / 'orchestra'
        self.clock = Clock()
        self.events, self.runs, self.requests = [], [], []
        self.guard, self.supervisor = FakeGuard(), FakeSupervisor()
        self.orch = self.make()

    def make(self, **parts):
        conn = open_db(self.dir / 'orchestra.db')
        self.admitted = {'i-A1', 'i-A2'}
        defaults = dict(guard=self.guard, supervisor=self.supervisor, clock=self.clock, start_run=self.start_run,
                        request_run=self.request_run, token_cap=lambda role: 1000, instance_admitted=lambda iid: iid in self.admitted)
        defaults.update(parts)
        orch = service.Orchestra(OrchestraConfig.load(CONFIG), conn, audit=lambda e, p: self.events.append((e, p)),
                                 data_dir=self.dir, **defaults)
        self.addCleanup(orch.close)
        return orch

    def start_run(self, orch, agent, task, wakeup, approval):
        self.runs.append((agent['id'], task['id'], wakeup['id'], approval))
        return {'job_id': 'J-' + task['id'], 'mission_id': 'M-' + task['id']}

    def request_run(self, orch, agent, task, wakeup):
        self.requests.append((agent['id'], task['id'], wakeup['id']))
        return 'MR-' + str(len(self.requests))

    def agent(self, aid, status='aktiv', budget_tokens=None, reports_to=None):
        self.orch.conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, budget_tokens,"
                               " created_at, updated_at) VALUES (?, ?, 't', ?, 'coder', ?, ?, 2, ?, ?, ?)",
                               (aid, 'i-' + aid, aid, reports_to, status, budget_tokens, T0, T0))

    def task(self, tid, assignee=None, **fields):
        return board.create(self.orch.conn, dict(id=tid, title='Aufgabe ' + tid, assignee=assignee, **fields), T0, 'captain')

    def wake(self, aid, key, task_id=None):
        return heartbeat.enqueue(self.orch.conn, aid, 'zugewiesen', key, self.clock.now, 0, task_id=task_id)

    def wakeup(self, wid):
        return dict(self.orch.conn.execute('SELECT * FROM wakeups WHERE id = ?', (wid,)).fetchone())

    def tick(self):
        return tick.tick(self.orch, self.clock.now)

    def names(self, event):
        return [p for e, p in self.events if e == event]


class Wakeups(Base):
    def setUp(self):
        super().setUp()
        self.agent('A1')
        self.task('T1', assignee='A1')

    def test_with_standing_approval_a_run_starts_without_a_decision(self):
        self.guard.standing = True
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        out = self.tick()
        self.assertEqual((out['weckrufe'], out['laeufe'], out['antraege'], out['fehler']), (1, 1, 0, []))
        self.assertEqual(self.runs, [('A1', 'T1', wid, 'standing')])
        self.assertEqual(self.requests, [])
        w = self.wakeup(wid)
        self.assertEqual((w['outcome'], w['job_id'], w['mission_id']), ('lauf', 'J-T1', 'M-T1'))
        self.assertEqual(self.guard.used, [('A1', 'ok', wid)])

    def test_without_standing_approval_a_request_and_no_second_one(self):
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        out = self.tick()
        self.assertEqual((out['laeufe'], out['antraege']), (0, 1))
        self.assertEqual((self.runs, self.requests), ([], [('A1', 'T1', wid)]))
        self.assertEqual((self.wakeup(wid)['outcome'], self.wakeup(wid)['request_mission_id']), ('antrag', 'MR-1'))
        wid2 = self.wake('A1', 'comment:7', 'T1')
        self.tick()
        self.assertEqual(len(self.requests), 1, 'ein Antrag wartet schon: kein zweiter')
        self.assertEqual((self.wakeup(wid2)['outcome'], self.wakeup(wid2)['request_mission_id']), ('antrag', 'MR-1'))

    def test_a_decided_request_does_not_strand_the_wakeups_that_hung_on_it(self):
        """Betriebsmessung 27.10.2026: ein zweiter Weckruf (andere Aufgabe) hängt sich an den wartenden Antrag. Wird der Antrag entschieden,
        endet nur sein eigener Weckruf; der andere blieb für immer `antrag` an einem toten Antrag, und neue Aufgaben bekamen nie einen."""
        self.task('T2', assignee='A1')
        w1 = self.wake('A1', 'assign:T1:1', 'T1')
        self.tick()
        w2 = self.wake('A1', 'assign:T2:1', 'T2')
        self.tick()
        self.assertEqual(self.wakeup(w2)['request_mission_id'], 'MR-1')
        heartbeat.finish(self.orch.conn, w1, 'lauf', self.clock.now, job_id='J-T1')                      # der Captain gibt den Antrag frei
        w2row = self.wakeup(w2)
        self.assertEqual((w2row['outcome'], w2row['done_at'], w2row['request_mission_id']), (None, None, None), 'wieder offen')
        self.tick()
        self.assertEqual(self.requests[-1], ('A1', 'T2', w2), 'die zweite Aufgabe bekommt ihren eigenen Antrag')
        self.assertEqual(self.wakeup(w2)['request_mission_id'], 'MR-2')

    def test_a_wakeup_for_the_same_task_ends_with_its_decided_request(self):
        w1 = self.wake('A1', 'assign:T1:1', 'T1')
        self.tick()
        w2 = self.wake('A1', 'comment:7', 'T1')
        self.tick()
        heartbeat.finish(self.orch.conn, w1, 'abgelehnt', self.clock.now)
        self.assertEqual(self.wakeup(w2)['outcome'], 'abgelehnt')

    def test_an_already_decided_request_is_not_waited_for(self):
        w1 = self.wake('A1', 'assign:T1:1', 'T1')
        self.tick()
        w2 = self.wake('A1', 'comment:7', 'T1')
        self.tick()
        self.orch.conn.execute("UPDATE wakeups SET outcome = 'lauf' WHERE id = ?", (w1,))           # Bestand aus der Zeit vor der Korrektur
        self.assertIsNone(heartbeat.pending_request(self.orch.conn, 'A1'))
        self.assertEqual(self.wakeup(w2)['outcome'], 'antrag')

    def test_supervisor_off_leaves_the_wakeup_open_and_says_so_once(self):
        self.supervisor.enabled = False
        self.guard.standing = True
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        self.tick()
        self.tick()
        self.assertIsNone(self.wakeup(wid)['done_at'])
        self.assertEqual((self.runs, self.requests, self.guard.used), ([], [], []), 'keine Nutzung der Dauerfreigabe ohne Lauf')
        self.assertEqual(self.names('ORC_TICK_ERROR'), [{'stage': 'weckrufe', 'error': 'supervisor_off'}])

    def test_no_runner_wired_is_the_same(self):
        orch = self.orch
        orch.start_run = None
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        self.tick()
        self.assertIsNone(self.wakeup(wid)['done_at'])
        self.assertEqual(self.names('ORC_TICK_ERROR'), [{'stage': 'weckrufe', 'error': 'runner_off'}])

    def test_only_blocked_tasks_end_without_run_or_request(self):
        self.task('T0')
        board.set_blocker(self.orch.conn, 'T1', 'T0', T0)
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        self.tick()
        self.assertEqual(self.wakeup(wid)['outcome'], 'blockiert')
        self.assertEqual((self.runs, self.requests), ([], []))

    def test_a_paused_agent_ends_as_paused(self):
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        self.orch.conn.execute("UPDATE agents SET status = 'pausiert', pause_reason = 'captain'")
        self.tick()
        self.assertEqual(self.wakeup(wid)['outcome'], 'pausiert')

    def test_a_running_agent_keeps_its_wakeup_for_the_next_tick(self):
        self.task('T2', assignee='A1')
        board.checkout(self.orch.conn, 'T2', 'A1', 'J-T2', T0)
        self.supervisor.store.jobs['J-T2'] = {'state': 'BUILDING', 'attempt_log': [{'outcome': 'RUNNING'}]}
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        self.tick()
        self.assertIsNone(self.wakeup(wid)['done_at'])

    def test_two_tasks_of_one_agent_both_run_one_after_the_other(self):
        """Betriebsstunde 26.10.2026: zwei Aufgaben für einen Agenten legen zwei Weckrufe an, der zweite wird zusammengelegt. Der Lauf
        bedient nur eine Aufgabe; der zusammengelegte Weckruf darf nicht mit ihm enden, sonst bleibt die zweite Aufgabe liegen."""
        self.guard.standing = True
        self.task('T2', assignee='A1')

        def start(orch, agent, task, wakeup, approval):
            board.checkout(orch.conn, task['id'], agent['id'], 'J-' + task['id'], T0)
            self.runs.append((agent['id'], task['id']))
            return {'job_id': 'J-' + task['id'], 'mission_id': 'M-' + task['id']}
        self.orch.start_run = start
        w1, w2 = self.wake('A1', 'assign:T1:1', 'T1'), self.wake('A1', 'assign:T2:1', 'T2')
        self.tick()
        self.assertEqual(self.runs, [('A1', 'T1')])
        self.assertEqual(self.wakeup(w1)['outcome'], 'lauf')
        self.assertIsNone(self.wakeup(w2)['done_at'], 'der Weckruf der zweiten Aufgabe bleibt offen')
        self.supervisor.store.jobs['J-T1'] = {'state': 'BUILDING', 'attempt_log': [{'outcome': 'RUNNING'}]}
        self.tick()
        self.assertEqual(self.runs, [('A1', 'T1')], 'solange der erste Lauf läuft, wartet der zweite')
        board.release(self.orch.conn, 'T1', 'J-T1', 'erledigt', T0, 'fertig')
        self.tick()
        self.assertEqual(self.runs, [('A1', 'T1'), ('A1', 'T2')])
        self.assertEqual(self.wakeup(w2)['outcome'], 'lauf')

    def test_a_stopped_budget_pauses_the_agent(self):
        self.orch.conn.execute("UPDATE agents SET budget_tokens = 100")
        self.orch.conn.execute("INSERT INTO spend (agent_id, provider, tokens_out, ts) VALUES ('A1', 'lokal', 100, ?)", (T0,))
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        self.tick()
        self.assertEqual(self.wakeup(wid)['outcome'], 'kein_budget')
        agent = dict(self.orch.conn.execute("SELECT status, pause_reason FROM agents WHERE id = 'A1'").fetchone())
        self.assertEqual(agent, {'status': 'pausiert', 'pause_reason': 'budget'})
        self.assertEqual(self.orch.conn.execute("SELECT kind FROM budget_incidents").fetchone()[0], 'stopp')
        self.assertEqual(self.guard.revoked, [('A1', 'budget')])
        self.assertEqual(self.names('ORC_BUDGET_STOP'), [{'agent_id': 'A1', 'prozent': 100}])

    def test_rest_below_the_run_cap_is_no_budget(self):
        self.orch.conn.execute("UPDATE agents SET budget_tokens = 1500")
        self.orch.conn.execute("INSERT INTO spend (agent_id, provider, tokens_out, ts) VALUES ('A1', 'lokal', 600, ?)", (T0,))
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        self.tick()
        self.assertEqual(self.wakeup(wid)['outcome'], 'kein_budget')
        self.assertEqual(self.runs, [])

    def test_a_failed_start_after_the_standing_check_keeps_the_use_and_retries_once(self):
        """Entscheidung HALT 2 (Captain 22.10.2026): Nutzung verbraucht, Weckruf `lauf` ohne Job, ORC_TICK_ERROR mit run_ref,
        höchstens ein Wiederholungs-Weckruf je Aufgabe – also höchstens zwei Nutzungen."""
        self.guard.standing = True

        def broken(orch, agent, task, wakeup, approval):
            raise RuntimeError('start_failed')
        self.orch.start_run = broken
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        self.tick()
        w = self.wakeup(wid)
        self.assertEqual((w['outcome'], w['job_id']), ('lauf', None))
        self.assertEqual(self.names('ORC_TICK_ERROR'), [{'stage': 'weckrufe', 'error': 'start_failed', 'agent_id': 'A1', 'run_ref': wid}])
        retry = self.orch.conn.execute("SELECT id, reason FROM wakeups WHERE idempotency_key = 'retry:T1:1'").fetchone()
        self.assertEqual(retry[1], 'wiederholung')
        self.clock.now = '2026-10-22T08:00:05Z'
        self.tick()
        self.assertEqual(self.wakeup(retry[0])['outcome'], 'lauf')
        self.assertEqual(self.orch.conn.execute("SELECT COUNT(*) FROM wakeups WHERE done_at IS NULL").fetchone()[0], 0, 'kein dritter Weckruf')
        self.clock.now = '2026-10-22T08:00:10Z'
        self.tick()
        self.assertEqual(len(self.guard.used), 2, 'höchstens zwei Nutzungen je Aufgabe')

    def test_without_admission_no_wake_and_no_standing_use(self):
        """Entscheidung Zulassung vor erstem Lauf (Captain 22.10.2026): geprüft vor authorize_standing."""
        self.guard.standing = True
        self.admitted.clear()
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        self.tick()
        self.assertEqual(self.wakeup(wid)['outcome'], 'abgelehnt')
        self.assertEqual((self.runs, self.requests, self.guard.used), ([], [], []))
        self.assertEqual(self.names('ORC_WAKE_REFUSED'), [{'agent_id': 'A1', 'instance_id': 'i-A1', 'wakeup_id': wid, 'reason': 'nicht_zugelassen'}])
        self.orch.instance_admitted = None
        wid = self.wake('A1', 'comment:1', 'T1')
        self.tick()
        self.assertEqual(self.wakeup(wid)['outcome'], 'abgelehnt', 'ohne Prüfer heißt es nein')

    def test_at_most_max_runs_per_tick(self):
        self.guard.standing = True
        self.agent('A2', reports_to='A1')
        self.task('T9', assignee='A2')
        w1, w2 = self.wake('A1', 'assign:T1:1', 'T1'), self.wake('A2', 'assign:T9:1', 'T9')
        out = self.tick()
        self.assertEqual(out['laeufe'], 1)
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(sorted([self.wakeup(w1)['done_at'] is None, self.wakeup(w2)['done_at'] is None]), [False, True])
        self.tick()
        self.assertEqual(len(self.runs), 2, 'der zweite läuft im nächsten Takt')


class Routines(Base):
    def test_a_due_routine_creates_a_task_and_a_wakeup_once(self):
        self.agent('A1')
        r = routines.create(self.orch.conn, {'agent_id': 'A1', 'title': 'Täglich', 'cron': '0 9 * * *', 'catch_up': 'auslassen', 'timezone': 'UTC',
                                             'task_template': json.dumps({'titel': 'Bericht schreiben', 'beschreibung': 'kurz'})}, T0)
        self.assertEqual(self.tick()['routinen'], 0)
        self.clock.now = '2026-10-22T09:00:30Z'
        out = self.tick()
        self.assertEqual(out['routinen'], 1)
        task = dict(self.orch.conn.execute("SELECT * FROM tasks").fetchone())
        self.assertEqual((task['title'], task['description'], task['origin'], task['assignee']), ('Bericht schreiben', 'kurz', 'routine', 'A1'))
        keys = [r_[0] for r_ in self.orch.conn.execute("SELECT idempotency_key FROM wakeups")]
        self.assertEqual(keys, [f"routine:{r['id']}:2026-10-22T09:00:00Z"])
        self.assertEqual(self.tick()['routinen'], 0, 'doppelter Takt: keine zweite Aufgabe')
        self.assertEqual(self.orch.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 1)


    def test_a_routine_with_an_unknown_zone_only_stops_itself(self):
        """OP-S1-15: die kaputte Routine meldet ORC_TICK_ERROR, die andere erzeugt ihre Aufgabe."""
        self.agent('A1')
        good = routines.create(self.orch.conn, {'agent_id': 'A1', 'title': 'Gut', 'cron': '0 9 * * *', 'catch_up': 'auslassen', 'timezone': 'UTC'}, T0)
        self.orch.conn.execute("INSERT INTO routines (id, agent_id, title, cron, timezone, catch_up, enabled, last_run) "
                               "VALUES ('R-0', 'A1', 'Kaputt', '0 9 * * *', 'Mars/Olymp', 'auslassen', 1, ?)", (T0,))
        self.clock.now = '2026-10-22T09:00:30Z'
        out = self.tick()
        self.assertEqual((out['routinen'], out['fehler']), (1, ['routinen']))
        self.assertEqual(self.orch.conn.execute("SELECT routine_id FROM routine_runs").fetchall()[0][0], good['id'])
        self.assertEqual(self.names('ORC_TICK_ERROR'), [{'stage': 'routinen', 'error': 'cron_timezone_unknown', 'routine_id': 'R-0'}])


class Reconcile(Base):
    def setUp(self):
        super().setUp()
        self.agent('A1')
        self.task('T1', assignee='A1')

    def running(self, run_id='J-T1'):
        board.checkout(self.orch.conn, 'T1', 'A1', run_id, T0)
        self.n = getattr(self, 'n', 0) + 1
        wid = self.wake('A1', f'assign:T1:{self.n}', 'T1')
        heartbeat.finish(self.orch.conn, wid, 'lauf', T0, job_id=run_id)

    def task_row(self):
        return dict(self.orch.conn.execute("SELECT state, checkout_by, checkout_run FROM tasks WHERE id = 'T1'").fetchone())

    def last_comment(self):
        return self.orch.conn.execute("SELECT author_kind, text FROM comments ORDER BY id DESC").fetchone()[:]

    def test_a_stalled_or_ended_job_frees_the_checkout(self):
        for job in ({'state': 'CANCELLED', 'attempt_log': []}, {'state': 'BUILDING', 'attempt_log': [{'outcome': 'UNKNOWN'}]}):
            with self.subTest(job):
                self.running()
                self.supervisor.store.jobs['J-T1'] = job
                out = self.tick()
                self.assertEqual(out['freigegeben'], 1)
                self.assertEqual(self.task_row(), {'state': 'zugewiesen', 'checkout_by': None, 'checkout_run': None})
                self.assertEqual(self.last_comment(), ('system', 'lauf_beendet'))

    def test_the_comment_names_why_the_job_ended(self):
        """Ein Job, der vor dem Handler scheitert (z. B. zu wenig RAM für das Modell), ließ nur `lauf_beendet` zurück; der Grund stand nur im Audit."""
        self.running()
        self.supervisor.store.jobs['J-T1'] = {'state': 'FAILED', 'attempt_log': [{'outcome': 'FAILED', 'failure_class': 'hardware_pressure'}]}
        self.tick()
        self.assertEqual(self.last_comment(), ('system', 'lauf_beendet: hardware_pressure'))

    def test_a_living_job_keeps_its_checkout(self):
        self.running()
        self.supervisor.store.jobs['J-T1'] = {'state': 'BUILDING', 'attempt_log': [{'outcome': 'RUNNING'}]}
        self.assertEqual(self.tick()['freigegeben'], 0)
        self.assertEqual(self.task_row()['checkout_run'], 'J-T1')

    def test_the_first_tick_frees_orphans(self):
        board.checkout(self.orch.conn, 'T1', 'A1', 'run-ohne-job', T0)
        tick.run_once(self.orch, first=True)
        self.assertEqual(self.task_row(), {'state': 'zugewiesen', 'checkout_by': None, 'checkout_run': None})
        self.assertEqual(self.last_comment(), ('system', 'lauf_verwaist'))
        self.assertEqual(self.names('ORC_RUN_RELEASED'), [{'task_id': 'T1', 'run_id': 'run-ohne-job', 'agent_id': 'A1', 'reason': 'lauf_verwaist'}])


class Quarantine(Base):
    def test_a_quarantined_instance_pauses_its_agent(self):
        self.agent('A1')
        self.agent('A2', reports_to='A1')
        self.orch.instance_status = lambda iid: 'QUARANTINED' if iid == 'i-A2' else 'ACTIVE'
        self.tick()
        rows = dict(self.orch.conn.execute("SELECT id, pause_reason FROM agents").fetchall())
        self.assertEqual(rows, {'A1': None, 'A2': 'quarantaene'})
        self.assertEqual(self.guard.revoked, [('A2', 'quarantaene')])

    def test_an_error_in_one_stage_does_not_stop_the_others(self):
        self.agent('A1')
        self.task('T1', assignee='A1')
        self.orch.instance_status = lambda iid: 1 / 0
        wid = self.wake('A1', 'assign:T1:1', 'T1')
        out = self.tick()
        self.assertEqual(out['fehler'], ['quarantaene'])
        self.assertEqual(self.wakeup(wid)['outcome'], 'antrag', 'die Weckrufe liefen trotzdem')
        self.assertEqual(self.names('ORC_TICK_ERROR'), [{'stage': 'quarantaene', 'error': 'division by zero'}])


class Reports(Base):
    def test_a_root_with_finished_children_wakes_its_owner_once(self):
        self.agent('A1')
        self.task('ROOT', assignee='A1')
        self.task('C1', parent_id='ROOT')
        self.tick()
        self.assertEqual(self.orch.conn.execute("SELECT COUNT(*) FROM wakeups WHERE idempotency_key = 'report:ROOT'").fetchone()[0], 0)
        self.orch.conn.execute("UPDATE tasks SET state = 'erledigt' WHERE id = 'C1'")
        self.orch.config.coalesce_s = 1                     # der Weckruf ist erst im nächsten Takt fällig
        self.tick()
        self.tick()
        rows = self.orch.conn.execute("SELECT reason, task_id FROM wakeups WHERE idempotency_key = 'report:ROOT'").fetchall()
        self.assertEqual([r[:] for r in rows], [('antwort', 'ROOT')])


class Takt(Base):
    def test_the_tick_is_written_and_goes_stale_after_three_intervals(self):
        self.assertEqual(self.orch.takt(), {'laeuft': False, 'letzter': None, 'owner': None})
        self.tick()
        self.assertEqual(self.orch.takt(), {'laeuft': True, 'letzter': T0, 'owner': str(os.getpid())})
        self.assertEqual(service.boot_entry(self.orch, None)['takt']['letzter'], T0)
        self.clock.now = '2026-10-22T08:00:15Z'               # 3 × tick_s (5 s)
        self.assertTrue(self.orch.takt()['laeuft'])
        self.clock.now = '2026-10-22T08:00:16Z'
        self.assertFalse(self.orch.takt()['laeuft'])
        self.assertNotIn('takt', service.boot_entry(None, None), 'aus bleibt der Eintrag wie in Spec 0')

    def test_the_thread_ticks_and_a_second_ticker_is_busy(self):
        thread = self.orch.start_tick()
        self.assertIs(self.orch.start_tick(), thread, 'einmal je Fassade')
        deadline = time.monotonic() + 10
        while self.orch.takt()['letzter'] is None and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(self.orch.takt()['letzter'], T0)
        other = self.make()
        with self.assertRaisesRegex(ValueError, '^tick_busy$'):
            other.start_tick()
        self.orch.stop_tick()
        self.assertFalse(thread.is_alive())
        self.assertIsNotNone(other.start_tick(), 'nach dem Ende des ersten darf ein anderer takten')
        other.stop_tick()


class Quelle(Base):
    """D1.7, Fehlerfälle zwei Takter, Takt fällt aus, Supervisor aus: was Shell D über `quelle` sieht."""
    def quelle(self, orch=None):
        from types import SimpleNamespace
        from guppi_runtime.desk import orchestra_kinds
        return orchestra_kinds.quelle(SimpleNamespace(runtime=SimpleNamespace(orchestra=orch or self.orch)))

    def test_the_second_ticker_does_not_move_the_takt_of_the_first(self):
        self.orch.start_tick()
        deadline = time.monotonic() + 10
        while self.orch.takt()['letzter'] is None and time.monotonic() < deadline:
            time.sleep(0.05)
        other = self.make()
        with self.assertRaisesRegex(ValueError, '^tick_busy$'):
            other.start_tick()
        self.assertEqual(self.quelle()['takt'], {'laeuft': True, 'letzter': T0})
        self.assertEqual(self.quelle(other)['takt'], {'laeuft': True, 'letzter': T0}, 'dieselbe Datenbank, derselbe Takt des ersten')
        self.orch.stop_tick()

    def test_without_a_tick_for_three_intervals_the_takt_says_not_running(self):
        self.tick()
        self.assertEqual(self.quelle()['takt'], {'laeuft': True, 'letzter': T0})
        self.clock.now = '2026-10-22T08:00:16Z'                   # mehr als 3 × tick_s (5 s)
        self.assertEqual(self.quelle()['takt'], {'laeuft': False, 'letzter': T0})

    def test_with_the_supervisor_off_quelle_names_the_reason(self):
        self.assertIsNone(self.quelle()['grund'])
        self.supervisor.enabled = False
        out = self.quelle()
        self.assertEqual((out['zustand'], out['grund']), ('bereit', 'supervisor_off'))


if __name__ == '__main__':
    unittest.main()
