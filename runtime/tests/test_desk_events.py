"""The desk's event stream (SHELL_WERKZEUG_VERTRAG_v1 §5, §10.4): what changed between two looks, the ring buffer a reconnecting
shell reads from, and the SSE wire format. The poller is driven by hand here, so the test never waits for a thread."""
import io
import json
import threading
import unittest

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk.events import EventStream, Poller, diff, sse, stream_to


def mission(mid, phase="EXECUTE", done=0, pending=0, steps=3):
    return {"mission_id": mid, "phase": phase, "status": "active", "steps": ["a", "b", "c"][:steps], "steps_done": done,
            "pending_gates": pending, "intent": "Parser bauen"}


def decision(did, kind="gate"):
    return {"id": did, "kind": kind, "title": "Netzgrenze", "describe": "pypi.org", "mission_id": "M-1", "gate_id": "HG-1"}


class Diff(unittest.TestCase):
    def test_nothing_changed_means_no_event(self):
        snap = {"missions": [mission("M-1")], "decisions": [], "model": {"running": False}, "state": "READY"}
        self.assertEqual(diff(snap, dict(snap)), [])

    def test_a_step_forward_is_one_task_event(self):
        before = {"missions": [mission("M-1", done=1)], "decisions": [], "model": {}, "state": "READY"}
        after = {"missions": [mission("M-1", done=2)], "decisions": [], "model": {}, "state": "READY"}
        events = diff(before, after)
        self.assertEqual([n for n, _ in events], ["task.changed"])
        self.assertEqual(events[0][1]["step"], 2)
        self.assertEqual(events[0][1]["id"], "M-1")

    def test_a_new_decision_arrives_and_an_answered_one_leaves(self):
        empty = {"missions": [], "decisions": [], "model": {}, "state": "READY"}
        waiting = {"missions": [], "decisions": [decision("gate:HG-1")], "model": {}, "state": "READY"}
        self.assertEqual([(n, p["id"]) for n, p in diff(empty, waiting)], [("decision.pending", "gate:HG-1")])
        self.assertEqual([(n, p["id"]) for n, p in diff(waiting, empty)], [("decision.answered", "gate:HG-1")])

    def test_a_task_that_disappears_is_not_silently_dropped(self):
        before = {"missions": [mission("M-1")], "decisions": [], "model": {}, "state": "READY"}
        after = {"missions": [], "decisions": [], "model": {}, "state": "READY"}
        self.assertEqual([(n, p["phase"]) for n, p in diff(before, after)], [("task.changed", "GONE")])

    def test_model_and_state_changes_are_their_own_events(self):
        before = {"missions": [], "decisions": [], "model": {"running": False}, "state": "READY"}
        after = {"missions": [], "decisions": [], "model": {"running": True, "model": "qwen"}, "state": "SAFE_MODE"}
        self.assertEqual([n for n, _ in diff(before, after)], ["model.changed", "system.state"])

    def test_the_first_look_tells_everything_that_is_already_there(self):
        after = {"missions": [mission("M-1")], "decisions": [decision("gate:HG-1")], "model": {}, "state": "READY"}
        self.assertEqual(sorted(n for n, _ in diff(None, after)), ["decision.pending", "system.state", "task.changed"])


class Stream(unittest.TestCase):
    def test_events_are_numbered_and_the_ring_keeps_the_last_ones(self):
        s = EventStream(ring=3)
        for i in range(5):
            s.publish("task.changed", {"id": "M-%d" % i})
        self.assertEqual(s.last_id, 5)
        missed, lost = s.since(0)
        self.assertEqual([e["id"] for e in missed], [3, 4, 5])
        self.assertFalse(lost, "a shell that connects for the first time has missed nothing")
        self.assertTrue(s.since(1)[1], "a shell that was away too long must be told to read everything again")
        missed, lost = s.since(4)
        self.assertEqual([e["id"] for e in missed], [5])
        self.assertFalse(lost)

    def test_the_wire_format_is_one_event_per_block(self):
        line = sse({"id": 7, "event": "decision.pending", "data": {"id": "gate:HG-1", "title": "Netz"}})
        text = line.decode("utf-8")
        self.assertTrue(text.startswith("id: 7\nevent: decision.pending\ndata: "))
        self.assertTrue(text.endswith("\n\n"))
        self.assertEqual(json.loads(text.split("data: ", 1)[1])["id"], "gate:HG-1")

    def test_a_reader_gets_what_it_missed_and_then_stops_when_asked(self):
        s = EventStream()
        s.publish("task.changed", {"id": "M-1"})
        s.publish("task.changed", {"id": "M-2"})
        stop = threading.Event()
        out = io.BytesIO()
        out.flush = lambda: None
        done = []
        thread = threading.Thread(target=lambda: done.append(stream_to(out, s, 0, stop=stop, heartbeat=0.05)), daemon=True)
        thread.start()
        s.publish("decision.pending", {"id": "gate:HG-1"})
        stop.set()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive(), "the stream must end when the server stops")
        text = out.getvalue().decode("utf-8")
        self.assertIn("event: task.changed", text)
        self.assertIn("gate:HG-1", text)
        self.assertEqual(done, [3])

    def test_a_shell_that_was_away_too_long_is_told_to_read_again(self):
        s = EventStream(ring=2)
        for i in range(5):
            s.publish("task.changed", {"id": "M-%d" % i})
        out = io.BytesIO()
        out.flush = lambda: None
        stop = threading.Event()
        stop.set()
        stream_to(out, s, 1, stop=stop)
        self.assertIn("event: desk.resync", out.getvalue().decode("utf-8"))


class PollerTests(unittest.TestCase):
    def test_the_poller_publishes_only_what_changed(self):
        snaps = [
            {"missions": [mission("M-1", done=0)], "decisions": [], "model": {}, "state": "READY"},
            {"missions": [mission("M-1", done=0)], "decisions": [], "model": {}, "state": "READY"},
            {"missions": [mission("M-1", done=1)], "decisions": [decision("gate:HG-1")], "model": {}, "state": "READY"},
        ]
        s = EventStream()
        p = Poller(None, s, snapshot=lambda: snaps.pop(0))
        self.assertEqual([e["event"] for e in p.tick()], ["task.changed", "system.state"])     # the first look reports what is there
        self.assertEqual(p.tick(), [])
        self.assertEqual(sorted(e["event"] for e in p.tick()), ["decision.pending", "task.changed"])

    def test_a_broken_view_is_reported_once_and_does_not_kill_the_stream(self):
        s = EventStream()
        state = {"fail": True}

        def snapshot():
            if state["fail"]:
                raise RuntimeError("missions kaputt")
            return {"missions": [], "decisions": [], "model": {}, "state": "READY"}
        p = Poller(None, s, snapshot=snapshot)
        self.assertEqual([e["event"] for e in p.tick()], ["desk.error"])
        self.assertEqual(p.tick(), [], "the same problem is not repeated every three seconds")
        state["fail"] = False
        p.tick()
        self.assertIsNone(p.error)


def team(agents=None, issues=None, budgets=None):
    return {"missions": [], "decisions": [], "model": {}, "state": "READY",
            "orchestra": {"agents": agents or {}, "issues": issues or {}, "budgets": budgets or {}}}


def slots(belegt=(), schlange=(), gesamt=3):
    return {"missions": [], "decisions": [], "model": {}, "state": "READY",
            "slots": {"gesamt": gesamt, "belegt": [{"slot": n, "run_id": r, "prioritaet": p} for n, r, p in belegt], "schlange": list(schlange)}}


class TeamDiff(unittest.TestCase):
    """Spec 4 (D4.3.2, N3, N4): agent.changed, issue.changed, budget.warning, slot.changed – rein und nach ID sortiert."""

    def test_the_first_look_and_a_missing_key_stay_silent(self):
        full = team({"A-1": ["aktiv", 1, 0, False]}, {"UA-1": ["offen", None, 1, 0]}, {"A-1": 80})
        self.assertEqual(diff(None, full), [("system.state", {"state": "READY"})])
        plain = {"missions": [], "decisions": [], "model": {}, "state": "READY"}
        self.assertEqual(diff(plain, full), [], "Orchestrierung eben eingeschaltet: der erste Blick darauf ist die Grundlage")
        self.assertEqual(diff(full, plain), [], "Orchestrierung aus: kein Ereignis")
        self.assertEqual(diff(slots([(1, "L-1", "agent")]), plain), [])

    def test_agents_and_issues_change_in_the_order_of_their_ids(self):
        before = team({"A-2": ["aktiv", 1, 0, False], "A-1": ["aktiv", 1, 0, False]}, {"UA-2": ["offen", None, 1, 0]})
        after = team({"A-2": ["pausiert", 2, 0, False], "A-1": ["aktiv", 1, 4, True], "A-3": ["aktiv", 1, 0, False]},
                     {"UA-2": ["zugewiesen", "A-1", 2, 0], "UA-1": ["offen", None, 1, 0]})
        self.assertEqual(diff(before, after), [("agent.changed", {"id": "A-1"}), ("agent.changed", {"id": "A-2"}),
                                               ("agent.changed", {"id": "A-3"}), ("issue.changed", {"id": "UA-1"}),
                                               ("issue.changed", {"id": "UA-2"})])
        self.assertEqual(diff(after, before)[:3], [("agent.changed", {"id": "A-1"}), ("agent.changed", {"id": "A-2"}),
                                                   ("agent.changed", {"id": "A-3"})], "ein Agent, der verschwindet, ist auch eine Änderung")
        self.assertEqual(diff(after, after), [])

    def test_a_budget_warns_only_when_its_level_rises(self):
        a = {"A-1": ["aktiv", 1, 0, False]}
        ok, warn = team(a, budgets={"A-1": 0}), team(a, budgets={"A-1": {"stufe": 80, "prozent": 83}})
        stop = team(a, budgets={"A-1": {"stufe": 100, "prozent": 100}})
        self.assertEqual(diff(ok, warn), [("budget.warning", {"agent_id": "A-1", "prozent": 83, "stufe": "warnung"})])
        self.assertEqual(diff(warn, stop), [("budget.warning", {"agent_id": "A-1", "prozent": 100, "stufe": "gestoppt"})])
        self.assertEqual(diff(stop, ok), [("agent.changed", {"id": "A-1"})], "Budget erhöht: nur agent.changed, kein Alarm")
        self.assertEqual(diff(warn, team(a, budgets={"A-1": {"stufe": 80, "prozent": 91}})), [], "gleiche Stufe: still")
        self.assertEqual(diff(team(a), team(a, budgets={"A-1": "gestoppt"})),
                         [("budget.warning", {"agent_id": "A-1", "prozent": None, "stufe": "gestoppt"})])

    def test_a_slot_event_per_changed_slot_and_one_for_the_queue(self):
        idle, busy = slots(), slots([(1, "L-1", "captain"), (2, "L-2", "agent")], ["L-3"])
        self.assertEqual(diff(idle, busy), [
            ("slot.changed", {"slot": 1, "state": "belegt", "run_id": "L-1", "priority": "captain", "queue_len": 1}),
            ("slot.changed", {"slot": 2, "state": "belegt", "run_id": "L-2", "priority": "agent", "queue_len": 1})])
        freed = slots([(2, "L-2", "agent")], ["L-3"])
        self.assertEqual(diff(busy, freed), [("slot.changed", {"slot": 1, "state": "frei", "run_id": "L-1", "priority": None, "queue_len": 1})])
        self.assertEqual(diff(freed, slots([(2, "L-2", "agent")], ["L-3", "L-4"])),
                         [("slot.changed", {"slot": None, "state": None, "run_id": None, "priority": None, "queue_len": 2})])
        self.assertEqual(diff(freed, freed), [])

    def test_a_decision_names_its_agent_and_stays_empty_without_one(self):
        empty = {"missions": [], "decisions": [], "model": {}, "state": "READY"}
        mit = dict(empty, decisions=[dict(decision("gate:HG-2"), agent_id="A-1")])
        self.assertEqual(diff(empty, mit)[0][1]["agent_id"], "A-1")
        ohne = dict(empty, decisions=[decision("gate:HG-1")])
        self.assertIsNone(diff(empty, ohne)[0][1]["agent_id"])


class SnapshotHook(unittest.TestCase):
    """Spec 4 (D4.3.2): `extensions.snapshot` mischt die Felder der Erweiterungen; ohne Haken bleibt alles wie es war."""

    def test_modules_add_fields_a_broken_one_costs_only_its_part(self):
        from types import SimpleNamespace
        from guppi_runtime.desk import extensions

        def broken(hub):
            raise RuntimeError("db belegt")
        mods = [SimpleNamespace(__name__="ohne"), SimpleNamespace(__name__="kaputt", snapshot=broken),
                SimpleNamespace(__name__="team", snapshot=lambda hub: {"orchestra": {"agents": {"A-1": [hub]}}}),
                SimpleNamespace(__name__="zweiter", snapshot=lambda hub: {"orchestra": "nicht überschreiben", "slots": {"gesamt": 1}})]
        self.assertEqual(extensions.snapshot("hub", mods), {"orchestra": {"agents": {"A-1": ["hub"]}}, "slots": {"gesamt": 1}})
        self.assertEqual(extensions.snapshot("hub", []), {})

    def test_the_orchestra_kinds_module_adds_nothing_while_the_switch_is_off(self):
        from types import SimpleNamespace
        from guppi_runtime.desk import extensions, orchestra_kinds
        self.assertEqual(extensions.snapshot(SimpleNamespace(runtime=SimpleNamespace(orchestra=None)), [orchestra_kinds]), {})


class SchedulerSlots(unittest.TestCase):
    """Spec 2, S2.H5 (SCH-09, G2-S2-13): `slots` in the snapshot comes from `ModelScheduler.view()`, `diff` turns it into `slot.changed`, the poller
    takes the scheduler's step, `POST /api/objects {type:'model'}` and `GET /api/strip` carry it. Off: nothing of it exists."""

    def setUp(self):
        import tempfile
        from types import SimpleNamespace
        from guppi_runtime.uix_server import UIXHub
        from model_scheduler_fakes import make_scheduler, resolution
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.sched, self.lab, self.loader, self.runtime, self.audit, self.clock = make_scheduler(self.tmp.name)
        self.addCleanup(self.sched._release_gpu)
        self.resolution = resolution
        self.rt = SimpleNamespace(model_scheduler=self.sched, orchestra=None, audit=self.audit)
        self.hub = object.__new__(UIXHub)
        self.hub.runtime = self.rt

    def start(self, job="SDJ-1"):
        self.assertTrue(self.sched.take_for_job(job, 5, agent_id="A-1", task_id="T-1")["granted"])
        self.sched.ensure_server(self.resolution(), run_id=job)

    def test_view_has_the_shape_of_spec_4_and_the_titles_come_from_the_board(self):
        from types import SimpleNamespace
        self.rt.orchestra = SimpleNamespace(issue=lambda tid: {"title": "Parser bauen"} if tid == "T-1" else None)
        self.start()
        self.sched.take_for_job("SDJ-2", 7, agent_id="A-2", task_id="T-2")
        self.sched.take_for_job("SDJ-3", 5, agent_id="A-3", task_id="T-3")
        slots = self.hub.slots_view()
        self.assertEqual({"gesamt", "belegt", "schlange", "modell", "warte_max_s"} - set(slots), set())
        self.assertEqual((slots["gesamt"], slots["modell"], slots["warte_max_s"]), (2, "main.local", 600))
        self.assertEqual(sorted(slots["belegt"][0]), ["agent_id", "prioritaet", "run_id", "seit", "slot", "task_id", "titel"])
        self.assertEqual(slots["belegt"][0]["titel"], "Parser bauen")
        self.assertEqual(sorted(slots["schlange"][0]), ["agent_id", "grund", "prioritaet", "run_id", "seit"])

    def test_a_slot_taken_and_given_back_are_two_slot_events_within_one_look_each(self):
        self.start()
        before = {"slots": self.hub.slots_view()}
        self.sched.take_for_job("SDJ-2", 5)
        mid = {"slots": self.hub.slots_view()}
        self.assertEqual(diff(before, mid), [("slot.changed", {"slot": 2, "state": "belegt", "run_id": "SDJ-2", "priority": 5, "queue_len": 0})])
        self.sched.release("SDJ-2")
        self.assertEqual(diff(mid, {"slots": self.hub.slots_view()}), [("slot.changed", {"slot": 2, "state": "frei", "run_id": "SDJ-2", "priority": None, "queue_len": 0})])
        self.sched.take_for_job("SDJ-3", 5)
        full = {"slots": self.hub.slots_view()}
        self.sched.take_for_job("SDJ-4", 5)                                                # only the queue grows
        self.assertEqual(diff(full, {"slots": self.hub.slots_view()}), [("slot.changed", {"slot": None, "state": None, "run_id": None, "priority": None, "queue_len": 1})])
        self.assertEqual(diff(full, dict(full)), [])

    def test_off_there_is_no_slots_field_anywhere(self):
        from guppi_runtime.desk import builtin_kinds
        off, *_ = make_off(self.tmp.name)
        for scheduler in (None, off):
            self.rt.model_scheduler = scheduler
            self.assertIsNone(self.hub.slots_view())
            self.assertIsNone(self.hub._slots_gauge())
            self.assertEqual(builtin_kinds._model_extra(self.hub, {}), {})
            self.hub.scheduler_poll()                                                       # nothing, no error

    def test_the_model_list_carries_slots(self):
        from guppi_runtime.desk import builtin_kinds
        self.start()
        extra = builtin_kinds._model_extra(self.hub, {})
        self.assertEqual(sorted(extra["slots"]), ["belegt", "gesamt", "modell", "schlange", "warte_max_s"])
        self.assertEqual(extra["slots"]["belegt"][0]["run_id"], "SDJ-1")

    def test_the_strip_gauge_is_held_over_total_with_the_waiting_as_hint(self):
        self.assertEqual(self.hub._slots_gauge(), {"value": "0/0", "hint": "Modellserver aus", "tone": "off"})
        self.start()
        self.assertEqual(self.hub._slots_gauge(), {"value": "1/2", "hint": "frei", "tone": "ok"})
        self.sched.take_for_job("SDJ-2", 5); self.sched.take_for_job("SDJ-3", 5)
        self.assertEqual(self.hub._slots_gauge(), {"value": "2/2", "hint": "1 wartet", "tone": "ok"})

    def test_the_poller_takes_the_schedulers_step_before_every_look(self):
        self.start()
        self.hub.scheduler_poll = lambda: order.append("poll")
        order = []
        poller = Poller(self.hub, EventStream(), snapshot=lambda: order.append("look") or {"state": "READY"})
        poller.tick(); poller.tick()
        self.assertEqual(order, ["poll", "look", "poll", "look"])

    def test_a_crashed_server_is_noticed_in_the_pollers_beat(self):
        self.start()
        self.runtime.running = False
        self.hub.scheduler_poll()
        self.assertEqual(self.sched.view()["server"]["state"], "aus")
        self.assertEqual(self.sched.view()["belegt"], [])


def make_off(root):
    from model_scheduler_fakes import make_scheduler
    return make_scheduler(root + "-off", enabled=False)


if __name__ == "__main__":
    unittest.main()
