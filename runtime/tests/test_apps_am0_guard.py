"""AM0-08 (SPEC_APPS_v1_AM0_G2 §8, G3 S9): Einbau und Rechte-Erhöhung fremder Module haben ausdrückliche Guard-Regeln (GR-039 bis GR-041, CAPTAIN_REQUIRED, Stufe 5), und der Antrag
wertet die Regel vor dem Gate aus: das Audit nennt die Regel, ein BLOCK bricht ab, ohne ein Gate zu hinterlassen."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from test_desk_install import CODE, module
from sedra_runtime.uix_server import UIXHub

RUNTIME = Path(__file__).resolve().parents[1]
ARCH = RUNTIME.parent / "architecture" / "SEDRA_Architecture_v1.20_SELF_DEVELOPMENT"
RULES = ARCH / "core" / "guard" / "guard_rules.yaml"
PERMS = RUNTIME / "config" / "permission_levels.yaml"


class Regeln(unittest.TestCase):
    def test_drei_ausdrueckliche_regeln_captain_required(self):
        regeln = {r["id"]: r for r in yaml.safe_load(RULES.read_text(encoding="utf-8"))["guard_rules"]["rules"]}
        for rid, aktion in (("GR-039", "install_module"), ("GR-040", "grant_module_write_routes"), ("GR-041", "grant_app_rights")):
            self.assertEqual(regeln[rid]["action"], aktion)
            self.assertEqual(regeln[rid]["decision"], "CAPTAIN_REQUIRED")

    def test_stufe_fuenf_ohne_pfadbindung(self):
        aktionen = yaml.safe_load(PERMS.read_text(encoding="utf-8"))["permission_levels"]["actions"]
        for aktion in ("install_module", "grant_module_write_routes", "grant_app_rights"):
            self.assertEqual(aktionen[aktion], {"level": 5, "path_scoped": False}, aktion)


class VorDemGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am0-guard-")
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.quelle = module(Path(self.tmp.name) / "quelle" / "fremd", CODE)

    def audit(self, typ):
        zeilen = [json.loads(z) for z in self.hub.runtime.audit.path.read_text(encoding="utf-8").splitlines() if z.strip()]
        return [e for e in zeilen if e.get("event_type") == typ]

    def einbauen(self):
        self.hub.install_request({"kind": "tool", "source": str(self.quelle)})
        item = next(d for d in self.hub.decisions_view()["items"] if d["kind"] == "request:install")
        self.hub.decide({"id": item["id"], "way": "freigeben_und_anwenden"})

    def test_install_request_wertet_gr_039_vor_dem_gate_aus(self):
        self.hub.install_request({"kind": "tool", "source": str(self.quelle)})
        zeilen = [e for e in self.audit("CAPTAIN_GATE_REQUESTED") if (e.get("payload") or {}).get("action") == "install_module"]
        self.assertEqual([(z["payload"]["rule_id"], z["payload"]["target"]) for z in zeilen], [("GR-039", "tools:fremd")])
        self.assertEqual(self.hub.decisions_view()["summary"]["count"], 1, "das Gate gibt es weiterhin, der Captain entscheidet")

    def test_trust_request_wertet_gr_040_vor_dem_gate_aus(self):
        self.einbauen()
        self.hub.trust_request({"kind": "tool", "id": "fremd"})
        zeilen = [e for e in self.audit("CAPTAIN_GATE_REQUESTED") if (e.get("payload") or {}).get("action") == "grant_module_write_routes"]
        self.assertEqual([z["payload"]["rule_id"] for z in zeilen], ["GR-040"])

    def test_ein_block_bricht_ab_und_hinterlaesst_kein_gate(self):
        block = {"decision": "BLOCK", "rule_id": "GR-039", "reason": "Rule GR-039", "action": "install_module", "target": "tools:fremd"}
        with mock.patch.object(self.hub.runtime.guard, "evaluate", return_value=block):
            with self.assertRaises(ValueError) as ctx:
                self.hub.install_request({"kind": "tool", "source": str(self.quelle)})
        self.assertEqual(str(ctx.exception), "guard_blocked:GR-039")
        self.assertEqual(self.hub.decisions_view()["summary"]["count"], 0)
        self.assertFalse((Path(self.tmp.name) / "project" / "local_config" / "tools" / "fremd").exists())

    def test_ein_block_bei_der_rechte_erhoehung_laesst_das_modul_unveraendert(self):
        self.einbauen()
        yaml_vorher = (Path(self.tmp.name) / "project" / "local_config" / "tools" / "fremd" / "tool.yaml").read_text(encoding="utf-8")
        block = {"decision": "BLOCK", "rule_id": "GR-040", "reason": "Rule GR-040", "action": "grant_module_write_routes", "target": "tools:fremd"}
        with mock.patch.object(self.hub.runtime.guard, "evaluate", return_value=block):
            with self.assertRaises(ValueError) as ctx:
                self.hub.trust_request({"kind": "tool", "id": "fremd"})
        self.assertEqual(str(ctx.exception), "guard_blocked:GR-040")
        self.assertEqual((Path(self.tmp.name) / "project" / "local_config" / "tools" / "fremd" / "tool.yaml").read_text(encoding="utf-8"), yaml_vorher)

    def test_ein_allow_ersetzt_das_gate_nicht(self):
        allow = {"decision": "ALLOW", "rule_id": "GR-039", "reason": "Rule GR-039", "action": "install_module", "target": "tools:fremd"}
        with mock.patch.object(self.hub.runtime.guard, "evaluate", return_value=allow):
            self.hub.install_request({"kind": "tool", "source": str(self.quelle)})
        self.assertEqual(self.hub.decisions_view()["summary"]["count"], 1, "der Einbau braucht immer die Entscheidung des Captains")


if __name__ == "__main__":
    unittest.main()
