"""The desk's decisions (SHELL_WERKZEUG_VERTRAG_v1 §10.3, COCKPIT_MODUL_v1 rule 2): mission gates and change requests in one shape,
answered through one route – and the guard underneath keeps every rule it had (once-only token, content binding, audit)."""
import unittest

import tempfile
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk import decisions as desk

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'


def gate(gid="HG-1", action="change_switch", targets=("switch:model_loader.enabled",), risks=("gilt erst nach Neustart",)):
    return {"gate_id": gid, "created_at": "2026-10-14T18:00:00+00:00",
            "request": {"exact_action": action, "targets": list(targets), "risks": list(risks), "rollback_available": True}}


def mission(mid="M-1", gates=(), intent="Parser bauen"):
    return {"identity": {"mission_id": mid}, "captain_intent": {"original": intent}, "human_gates": {"pending": list(gates)}}


class Shape(unittest.TestCase):
    def test_a_mission_gate_becomes_a_decision_with_two_ways(self):
        [d] = desk.collect([mission(gates=[gate()])], [])
        self.assertEqual(d["id"], "gate:HG-1")
        self.assertEqual(d["kind"], "gate")
        self.assertEqual(d["title"], "Parser bauen")
        self.assertEqual(d["ways"], ["einmal", "ablehnen"])
        self.assertIn("switch:model_loader.enabled", d["describe"])
        self.assertIn("gilt nur einmal", d["note"])

    def test_a_change_request_is_approved_and_applied_in_one_go(self):
        req = {"kind": "switch", "mission_id": "M-2", "gate": gate("HG-2"), "binding": {"section": "model_loader", "key": "enabled", "old": None, "new": True}}
        [d] = desk.collect([], [req])
        self.assertEqual(d["ways"], ["freigeben_und_anwenden", "ablehnen"])
        self.assertEqual(d["apply"], "/api/switch/apply")
        self.assertEqual(d["binding"]["new"], True)

    def test_a_mission_that_is_a_change_request_is_counted_once(self):
        req = {"kind": "switch", "mission_id": "M-1", "gate": gate("HG-1"), "binding": {}}
        items = desk.collect([mission("M-1", [gate("HG-1")])], [req])
        self.assertEqual([d["id"] for d in items], ["request:M-1"], "the request can be applied, the bare gate cannot")

    def test_the_summary_is_what_the_instrument_shows(self):
        self.assertEqual(desk.summary([]), {"count": 0, "first": None, "kind": None, "tone": "ok"})
        s = desk.summary(desk.collect([mission(gates=[gate()])], []))
        self.assertEqual((s["count"], s["first"], s["tone"]), (1, "Parser bauen", "warn"))

    def test_every_decision_carries_agent_id(self):
        """Spec 1, D1.3.5 (G2-S4-15): aus `binding.agent_id` eines Antrags, sonst None; `agent_id` und `op` bleiben in der Bindung."""
        req = {"kind": "orchestra", "mission_id": "M-5", "gate": gate("HG-5", "wake_agent", ("agent:A1",)),
               "binding": {"op": "wecken", "agent_id": "A1", "describe": "Agent A1 wecken", "geheim": "nicht zeigen"}}
        crossing = {"id": "boundary:x", "title": "Grenze", "describe": "d", "ways": ["einmal", "ablehnen"], "boundary": "kosten",
                    "project_id": "p", "created_at": "2026-10-14T18:00:00+00:00"}
        content = {"id": "content:1", "segments": [], "created_at": "2026-10-14T18:00:00+00:00"}
        items = {d["id"]: d for d in desk.collect([mission("M-1", [gate()])], [req], [crossing], [content])}
        self.assertEqual(items["request:M-5"]["agent_id"], "A1")
        self.assertEqual(items["request:M-5"]["binding"], {"op": "wecken", "agent_id": "A1", "describe": "Agent A1 wecken"})
        for did in ("gate:HG-1", "boundary:x", "content:1"):
            self.assertIsNone(items[did]["agent_id"], did)
        [plain] = desk.collect([], [{"kind": "switch", "mission_id": "M-2", "gate": gate("HG-2"), "binding": {}}])
        self.assertIsNone(plain["agent_id"])

    def test_only_an_offered_way_is_accepted(self):
        [d] = desk.collect([mission(gates=[gate()])], [])
        self.assertEqual(desk.check_answer(d, "einmal"), "einmal")
        with self.assertRaises(ValueError):
            desk.check_answer(d, "freigeben_und_anwenden")
        with self.assertRaises(ValueError):
            desk.check_answer(None, "einmal")


class ThroughTheHub(unittest.TestCase):
    """The whole way: a request from the Werkstatt, seen as a decision, answered once – and the switch really changed."""

    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix="desk-hub-")
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)

    def test_a_switch_request_is_answered_once_and_applied(self):
        self.hub.switch_request({"section": "model_loader", "key": "enabled", "value": True})
        view = self.hub.decisions_view()
        self.assertEqual(view["summary"]["count"], 1)
        item = view["items"][0]
        out = self.hub.decide({"id": item["id"], "way": "freigeben_und_anwenden"})
        self.assertEqual(out["status"], "answered")
        self.assertEqual(out["result"]["new"], True)
        self.assertEqual(self.hub.decisions_view()["summary"]["count"], 0)
        value = {(i["section"], i["key"]): i["value"] for i in self.hub.switches_view()["items"]}
        self.assertTrue(value[("model_loader", "enabled")])
        self.assertIn("LOCAL_SWITCH_CHANGED", [e["event_type"] for e in self.hub.audit_view()["events"]])

    def test_the_same_decision_cannot_be_answered_twice(self):
        self.hub.switch_request({"section": "model_loader", "key": "enabled", "value": True})
        item = self.hub.decisions_view()["items"][0]
        self.hub.decide({"id": item["id"], "way": "ablehnen"})
        with self.assertRaises(ValueError):
            self.hub.decide({"id": item["id"], "way": "ablehnen"})

    def test_a_way_the_decision_does_not_offer_is_refused(self):
        self.hub.switch_request({"section": "model_loader", "key": "enabled", "value": True})
        item = self.hub.decisions_view()["items"][0]
        with self.assertRaises(ValueError):
            self.hub.decide({"id": item["id"], "way": "einmal"})
        self.assertEqual(self.hub.decisions_view()["summary"]["count"], 1, "a refused way leaves the decision open")

    def test_the_strip_reads_the_same_numbers(self):
        strip = self.hub.strip_view()
        self.assertEqual(strip["decisions"]["value"], 0)
        self.assertEqual(strip["decisions"]["tone"], "ok")
        self.hub.switch_request({"section": "model_loader", "key": "enabled", "value": True})
        strip = self.hub.strip_view()
        self.assertEqual(strip["decisions"]["value"], 1)
        self.assertEqual(strip["decisions"]["tone"], "warn")
        self.assertEqual(strip["state"]["value"], "READY")
        self.assertIn("Audit intakt", strip["state"]["hint"])

    def test_the_snapshot_the_stream_watches_holds_what_the_shell_needs(self):
        snap = self.hub.desk_snapshot()
        # 'live' kam mit Build 8 dazu (Zeilenzahl je laufender Aufgabe); wächst diese Liste, muss desk/events.diff mitwachsen.
        self.assertEqual(sorted(snap), ["decisions", "live", "missions", "model", "state"])
        self.assertEqual(snap["state"], "READY")
        self.assertEqual(self.hub.desk_snapshot(), snap, "two looks without a change must be equal, or the stream never rests")


if __name__ == "__main__":
    unittest.main()
