"""The desk's gateway and registry (SHELL_WERKZEUG_VERTRAG_v1 §3, §6, §10): which modules are accepted, which files may be served,
and that a tool only reaches the routes its own manifest lists. No browser: everything here is the plain Python side."""
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk.gateway import HANDLE, Gateway, check_shell, check_tool, needs_ok, route_allowed
from guppi_runtime.desk.registry import Registry, UixConfigError

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "guppi_runtime" / "uix"

TOOL = {"tool": {"id": "probe", "name": "Probe", "version": "1.0.0", "kind": "object", "handles": ["task"],
                 "entry": {"js": "tool.js"}, "api": ["GET /api/missions"], "events": {"emits": ["object.open"], "listens": ["task.changed"]},
                 "trust": "CAPTAIN", "needs": {"ui": ">=1.0 <2"}}}


def write_tool(root, name, doc, files=("tool.js",)):
    folder = root / "local_config" / "tools" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "tool.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    for f in files:
        (folder / f).write_text("// probe\n", encoding="utf-8")
    return folder


class ManifestRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="desk-")
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def check(self, changes, name="probe"):
        doc = {"tool": dict(TOOL["tool"], **changes)}
        folder = write_tool(self.root, name, doc)
        return check_tool(doc, folder, "local")

    def test_a_correct_manifest_passes_and_keeps_its_fields(self):
        man, errors = self.check({})
        self.assertEqual(errors, [])
        self.assertEqual((man["id"], man["kind"], man["handles"], man["api"]), ("probe", "object", ["task"], ["GET /api/missions"]))

    def test_every_rule_of_the_contract_is_enforced(self):
        cases = {
            "id_invalid": {"id": "Probe!"},
            "version_invalid": {"version": "1.0"},
            "kind_invalid": {"kind": "window"},
            "handles_unknown_type": {"handles": ["Space Ship!"]},      # kein Typname; ein eigener Typ (`spaceship`) ist seit 15.10. erlaubt
            "object_tool_needs_handles": {"handles": []},
            "api_route_invalid": {"api": ["DELETE /api/missions"]},
            "events_emits_invalid": {"events": {"emits": ["Object.Open"]}},
            "trust_invalid": {"trust": "SOMETIMES"},
            "needs_ui_not_met": {"needs": {"ui": ">=2.0"}},
            "entry_js_required": {"entry": {"css": "tool.css"}},
            "unknown_field": {"hands": ["task"]},
        }
        for expected, change in cases.items():
            with self.subTest(expected):
                _, errors = self.check(change)
                self.assertTrue(any(e == expected or e.startswith(expected + ":") for e in errors),
                                f"{change} should be refused with {expected}, got {errors}")

    def test_an_own_tool_may_bring_its_own_object_type_but_a_core_tool_may_not(self):
        """Gefunden mit der ersten externen Lieferung (KI GateWay): `handles: [gateway]` wurde am Manifest abgewiesen.
        Die Shells öffnen jeden Typ über die Registrierung – nur das Paket selbst spricht kein Privatvokabular."""
        # `gateway` ist seit Build 19 ein Vertragstyp – der eigene Typ im Test heißt deshalb `rechnung`
        man, errors = self.check({"handles": ["rechnung"], "trust": "CAPTAIN"})
        self.assertEqual(errors, [])
        self.assertEqual(man["own_types"], ["rechnung"])
        man, errors = self.check({"handles": ["task"], "trust": "CAPTAIN"})
        self.assertEqual(man["own_types"], [], "ein Vertragstyp ist kein eigener")
        _, errors = self.check({"handles": ["rechnung"], "trust": "CORE"})
        self.assertIn("handles_unknown_type", errors)
        _, errors = check_tool({"tool": dict(TOOL["tool"], handles=["rechnung"], trust="CORE")},
                               write_tool(self.root, "probe", {"tool": dict(TOOL["tool"], handles=["rechnung"])}), "package")
        self.assertIn("handles_unknown_type", errors, "im Paket gibt es keine Privatsprache")

    def test_handles_may_carry_a_suffix_like_the_schema(self):
        """Nachtrag N1: `typ`, `typ:alle`, `typ:*`, `typ:<id>` – dasselbe Muster wie ui/schema/tool.schema.json."""
        man, errors = self.check({"handles": ["issue:alle", "issue:*", "agent:rollen", "routine", "budget", "gespraech"]})
        self.assertEqual(errors, [])
        self.assertEqual(man["handles"], ["issue:alle", "issue:*", "agent:rollen", "routine", "budget", "gespraech"])
        self.assertEqual(man["own_types"], [])
        for bad in (["issue:"], ["issue:**"], ["Issue:alle"], ["issue:a:b"], [":alle"]):
            with self.subTest(bad):
                self.assertIn("handles_unknown_type", self.check({"handles": bad})[1])
        man, errors = self.check({"handles": ["rechnung:*", "rechnung:alle"], "trust": "CAPTAIN"})
        self.assertEqual((errors, man["own_types"]), ([], ["rechnung"]), "der eigene Typ zählt einmal, ohne Zusatz")
        _, errors = self.check({"handles": ["rechnung:*"], "trust": "CORE"})
        self.assertIn("handles_unknown_type", errors)
        schema = json.loads((PACKAGE / "ui" / "schema" / "tool.schema.json").read_text(encoding="utf-8"))
        pattern = schema["properties"]["tool"]["properties"]["handles"]["items"]["pattern"]
        self.assertEqual(pattern, HANDLE.pattern, "Server und Schema prüfen dieselbe Form")

    def test_a_route_with_a_wildcard_only_matches_below_it(self):
        routes = ["GET /api/candidate/*", "POST /api/mission/approve"]
        self.assertTrue(route_allowed(routes, "GET", "/api/candidate/17"))
        self.assertFalse(route_allowed(routes, "GET", "/api/candidate"))
        self.assertFalse(route_allowed(routes, "POST", "/api/candidate/17"))
        self.assertFalse(route_allowed(routes, "GET", "/api/candidate/../switches"))
        self.assertTrue(route_allowed(routes, "POST", "/api/mission/approve"))

    def test_the_folder_name_is_the_id_and_a_missing_file_is_noticed(self):
        folder = write_tool(self.root, "other", {"tool": dict(TOOL["tool"], id="probe")})
        _, errors = check_tool({"tool": dict(TOOL["tool"], id="probe")}, folder, "local")
        self.assertIn("id_must_match_folder", errors)
        folder2 = write_tool(self.root, "probe", TOOL, files=())
        _, errors2 = check_tool(TOOL, folder2, "local")
        self.assertIn("file_missing:tool.js", errors2)

    def test_a_captains_module_cannot_claim_to_be_core_and_a_community_module_only_reads(self):
        _, errors = self.check({"trust": "CORE"})
        self.assertIn("local_module_cannot_be_core", errors)
        man, errors = self.check({"trust": "COMMUNITY", "api": ["GET /api/missions", "POST /api/mission/run"]})
        self.assertEqual(errors, [])
        self.assertEqual(man["api"], ["GET /api/missions"], "a foreign module gets its write routes stripped, not an error")

    def test_needs_ranges(self):
        for spec, ok in ((">=1.0 <2", True), ("==1.0", True), (">=1.1", False), ("<1", False), ("", False), ("egal", False)):
            self.assertEqual(needs_ok(spec), ok, spec)


class ManifestEndpoint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="desk-")
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.gateway = Gateway(self.root)

    def test_every_module_in_the_package_keeps_the_contract(self):
        manifest = self.gateway.manifest()
        self.assertEqual(manifest["rejected"], [], "a module of the package was refused")
        self.assertEqual(manifest["shell"]["id"], "start", "ohne uix.yaml lädt der Einstieg – der Captain wählt dort")
        ids = [t["id"] for t in manifest["tools"]]
        for needed in ("talk", "decisions", "task", "workshop", "library", "crew", "meter", "logbook", "system", "files"):
            self.assertIn(needed, ids)
        self.assertTrue(any(t["kind"] == "instrument" for t in manifest["tools"]))
        self.assertTrue(all(url.startswith("/uix/tools/") for t in manifest["tools"] for url in t["js"]))
        self.assertNotIn("api", manifest["tools"][0], "the allowlist stays on the server")

    def test_a_broken_module_is_named_instead_of_breaking_the_desktop(self):
        write_tool(self.root, "kaputt", {"tool": dict(TOOL["tool"], id="kaputt", version="nope")})
        manifest = self.gateway.manifest()
        self.assertEqual([r["id"] for r in manifest["rejected"]], ["kaputt"])
        self.assertIn("version_invalid", manifest["rejected"][0]["reasons"])
        self.assertEqual(manifest["shell"]["id"], "start", "the shell still loads")

    def test_uix_yaml_picks_the_shell_the_order_and_what_is_switched_off(self):
        (self.root / "local_config").mkdir(parents=True, exist_ok=True)
        (self.root / "local_config" / "uix.yaml").write_text(
            "uix:\n  shell: cockpit\n  tools:\n    order: [logbook, task]\n    disabled: [meter]\n", encoding="utf-8")
        manifest = Gateway(self.root).manifest()
        ids = [t["id"] for t in manifest["tools"]]
        self.assertEqual(ids[:2], ["logbook", "task"])
        self.assertNotIn("meter", ids)
        self.assertEqual(manifest["disabled"], ["meter"])

    def test_an_unreadable_uix_yaml_says_so(self):
        (self.root / "local_config").mkdir(parents=True, exist_ok=True)
        (self.root / "local_config" / "uix.yaml").write_text("uix:\n  shell: [nein]\n", encoding="utf-8")
        with self.assertRaises(UixConfigError):
            Registry(self.root).config()

    def test_an_unknown_shell_is_reported_and_nothing_is_guessed(self):
        (self.root / "local_config").mkdir(parents=True, exist_ok=True)
        (self.root / "local_config" / "uix.yaml").write_text("uix:\n  shell: gibtsnicht\n", encoding="utf-8")
        manifest = Gateway(self.root).manifest()
        self.assertIsNone(manifest["shell"])
        self.assertIn("active_shell_not_available", [r for x in manifest["rejected"] for r in x["reasons"]])


class FilesAndAllowlist(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="desk-")
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.gateway = Gateway(self.root)

    def test_only_files_of_registered_folders_are_served(self):
        self.assertIsNotNone(self.gateway.file("ui", None, "api.js"))
        self.assertIsNotNone(self.gateway.file("ui", "schema", "tool.schema.json"))
        self.assertIsNotNone(self.gateway.file("tools", "talk", "tool.js"))
        self.assertIsNotNone(self.gateway.file("shells", "cockpit", "shell.css"))
        for area, module, name in (("tools", "talk", "../../uix_server.py"), ("tools", "talk", "tool.yaml"),
                                   ("tools", "gibtsnicht", "tool.js"), ("ui", None, "../desk.html"),
                                   ("secrets", None, "api.js"), ("tools", "talk", "tool.js.bak")):
            with self.subTest(name):
                self.assertIsNone(self.gateway.file(area, module, name))

    def test_a_tool_only_reaches_its_own_routes(self):
        self.assertTrue(self.gateway.allowed("tool", "talk", "POST", "/api/chat/reply"))
        self.assertFalse(self.gateway.allowed("tool", "talk", "POST", "/api/model/load"))
        self.assertFalse(self.gateway.allowed("tool", "meter", "POST", "/api/switch/apply"))
        self.assertFalse(self.gateway.allowed("tool", "gibtsnicht", "GET", "/api/missions"))
        self.assertTrue(self.gateway.allowed("shell", "cockpit", "POST", "/api/decisions/answer"))

    def test_every_route_a_shipped_tool_lists_exists_in_the_server(self):
        from guppi_runtime import uix_server
        source = Path(uix_server.__file__).read_text(encoding="utf-8")
        for tid, (_folder, man) in sorted(self.gateway.tools().items()):
            for route in man["api"]:
                path = route.split(" ", 1)[1].rstrip("/*")
                with self.subTest(tid + " " + route):
                    self.assertIn(f"'{path}'", source, f"{tid} lists {route}, but the server has no such route")


class SchemaFiles(unittest.TestCase):
    def test_the_schemas_describe_the_same_rules_the_gateway_enforces(self):
        for name, sample, check in (("tool.schema.json", TOOL, check_tool),
                                    ("shell.schema.json", {"shell": {"id": "probe", "name": "P", "version": "1.0.0", "entry": {"js": "shell.js"},
                                                                     "provides": ["dock"], "trust": "CAPTAIN", "needs": {"ui": ">=1.0 <2"}}}, check_shell)):
            schema = json.loads((PACKAGE / "ui" / "schema" / name).read_text(encoding="utf-8"))
            key = list(sample)[0]
            allowed = set(schema["properties"][key]["properties"])
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / "probe"
                folder.mkdir()
                (folder / "tool.js").write_text("//\n", encoding="utf-8")
                (folder / "shell.js").write_text("//\n", encoding="utf-8")
                man, errors = check(sample, folder, "local")
            self.assertEqual(errors, [], name)
            self.assertTrue(set(sample[key]) <= allowed, f"{name} does not list every field of the example")
            for field in schema["properties"][key]["required"]:
                self.assertIn(field, allowed)


if __name__ == "__main__":
    unittest.main()
