import unittest

from path_health import MSB_SUFFIX, path_health, stale_bindings, vm_path_budget

OLD = r"D:\Projekte-Neu\Guppy\GUPPI_Developer_Archive_v1.20_SELF_DEVELOPMENT_FOUNDATION\GUPPI_Runtime_v1.20\workspace\GUPPI_OS"
NEW = r"D:\Projekte-Neu\Guppy\GUPPI v1.20_S D A\GUPPI_Runtime_v1.20\workspace\GUPPI_OS"
HOME_OLD = OLD + r"\runtime_data\sandboxes\backend_home"


class VmPathBudget(unittest.TestCase):
    def test_the_measured_failure_is_reported(self):
        # 154-character backend_home + 43-character VM name = 262 > 259 (the real failure of 2026-10-02)
        home = "x" * 154
        out = vm_path_budget(home, name_length=43)
        self.assertEqual(out, {"longest": 262, "limit": 260, "spare": -3, "ok": False})

    def test_short_name_fits(self):
        out = vm_path_budget("x" * 154, name_length=18)
        self.assertEqual(out["longest"], 154 + 18 + MSB_SUFFIX)
        self.assertTrue(out["ok"])
        self.assertEqual(out["spare"], 259 - out["longest"])

    def test_exactly_at_the_limit_is_ok(self):
        out = vm_path_budget("y" * (259 - 18 - MSB_SUFFIX), name_length=18)
        self.assertEqual((out["spare"], out["ok"]), (0, True))

    def test_trailing_separator_does_not_count(self):
        self.assertEqual(vm_path_budget("C:\\a\\")["longest"], vm_path_budget("C:\\a")["longest"])
        self.assertEqual(vm_path_budget("C:/a/")["longest"], vm_path_budget("C:/a")["longest"])

    def test_custom_limit(self):
        self.assertEqual(vm_path_budget("z", name_length=1, limit=100)["limit"], 100)


class StaleBindings(unittest.TestCase):
    def test_reports_bound_to_the_old_folder_are_stale(self):
        reports = [{"mission_id": "M-B", "host_root": OLD + r"\runtime_data\tool_workspace"},
                   {"mission_id": "M-A", "host_root": NEW + r"\runtime_data\tool_workspace"},
                   {"mission_id": "M-C", "host_root": OLD}]
        self.assertEqual(stale_bindings(NEW, reports), ["M-B", "M-C"])

    def test_case_and_separators_do_not_matter(self):
        reports = [{"mission_id": "M-1", "host_root": NEW.lower().replace("\\", "/") + "/runtime_data"}]
        self.assertEqual(stale_bindings(NEW, reports), [])

    def test_the_root_itself_is_not_stale(self):
        self.assertEqual(stale_bindings(NEW + "\\", [{"mission_id": "M-1", "host_root": NEW}]), [])

    def test_a_sibling_with_the_same_prefix_is_stale(self):
        self.assertEqual(stale_bindings(NEW, [{"mission_id": "M-9", "host_root": NEW + "2\\x"}]), ["M-9"])

    def test_duplicates_are_reported_once(self):
        reports = [{"mission_id": "M-1", "host_root": OLD}, {"mission_id": "M-1", "host_root": OLD + "\\y"}]
        self.assertEqual(stale_bindings(NEW, reports), ["M-1"])


class PathHealth(unittest.TestCase):
    def test_all_good(self):
        out = path_health(NEW, NEW + r"\runtime_data\sandboxes\backend_home", [{"mission_id": "M-1", "host_root": NEW}])
        self.assertEqual(out["status"], "OK")
        self.assertEqual(out["actions"], [])
        self.assertEqual(out["stale_missions"], [])
        self.assertTrue(out["vm_path"]["ok"])

    def test_the_day_of_the_rename(self):
        out = path_health(NEW, HOME_OLD, [{"mission_id": "M-372CA76F", "host_root": OLD}], name_length=43)
        self.assertEqual(out["status"], "ATTENTION")
        self.assertEqual(out["actions"], ["shorten_project_path", "regenerate_candidates"])
        self.assertEqual(out["stale_missions"], ["M-372CA76F"])
        self.assertFalse(out["vm_path"]["ok"])

    def test_only_stale_candidates(self):
        out = path_health(NEW, "C:\\h", [{"mission_id": "M-1", "host_root": OLD}])
        self.assertEqual(out["actions"], ["regenerate_candidates"])


if __name__ == "__main__":
    unittest.main()
