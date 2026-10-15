import unittest

from uix_window import DEFAULT_SIZE, browser_candidates, check_uix_url, pick_browser, window_argv

ENV = {"ProgramFiles(x86)": "C:\\Program Files (x86)", "ProgramFiles": "C:\\Program Files\\", "LOCALAPPDATA": "C:\\Users\\D\\AppData\\Local"}
URL = "http://127.0.0.1:52341/#tok-EN_abc123"


class Candidates(unittest.TestCase):
    def test_order_and_joining(self):
        self.assertEqual(browser_candidates(ENV), [
            "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
            "C:\\Users\\D\\AppData\\Local\\Microsoft\\Edge\\Application\\msedge.exe",
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Users\\D\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe"])

    def test_missing_or_empty_variables_are_skipped(self):
        self.assertEqual(browser_candidates({"ProgramFiles": "C:\\PF", "LOCALAPPDATA": ""}),
                         ["C:\\PF\\Microsoft\\Edge\\Application\\msedge.exe", "C:\\PF\\Google\\Chrome\\Application\\chrome.exe"])
        self.assertEqual(browser_candidates({}), [])

    def test_duplicates_once_case_insensitive(self):
        env = {"ProgramFiles(x86)": "C:\\Program Files", "ProgramFiles": "c:\\program files"}
        # Chrome is first reached through ProgramFiles (lower case here), so that spelling is the one kept.
        self.assertEqual(browser_candidates(env), ["C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
                                                   "c:\\program files\\Google\\Chrome\\Application\\chrome.exe"])


class Pick(unittest.TestCase):
    def test_first_existing(self):
        self.assertEqual(pick_browser(["a", "b", "c"], lambda p: p in {"b", "c"}), "b")
        self.assertIsNone(pick_browser(["a"], lambda p: False))
        self.assertIsNone(pick_browser([], lambda p: True))


class Url(unittest.TestCase):
    def test_own_uix_is_allowed(self):
        for url in (URL, "http://127.0.0.1:8080/", "http://127.0.0.1:1/#x", "http://127.0.0.1:65535/#a.b-c_d=e"):
            self.assertEqual(check_uix_url(url), url)

    def test_everything_else_is_refused(self):
        for url in ("https://127.0.0.1:8080/", "http://localhost:8080/", "http://127.0.0.1:8080/api/status", "http://127.0.0.1:8080/?x=1",
                    "http://127.0.0.1:0/", "http://127.0.0.1:65536/", "http://127.0.0.1:123456/", "http://127.0.0.1:8080",
                    "http://127.0.0.1:8080/# x", "http://evil.example/#http://127.0.0.1:8080/", "http://127.0.0.1:80a/",
                    "javascript:alert(1)", "", "http://127.0.0.1:8080/\n"):
            with self.assertRaises(ValueError, msg=repr(url)) as ctx:
                check_uix_url(url)
            self.assertEqual(str(ctx.exception), "uix_url_not_allowed")

    def test_control_characters_anywhere_are_refused(self):
        # urllib.parse silently drops tab, CR and LF wherever they are, so a check that only looks at the parsed parts lets these through.
        for url in ("http://127.0.0.1:8080/\n#x", "http://127.0.0.1:80\n80/", "ht\ntp://127.0.0.1:8080/", "http://127.0.0.1:8080/#a\tb",
                    "http://127.0.0.1:8080/#a\rb", "http://127.0.0.1:8080/#a\nb", "\thttp://127.0.0.1:8080/", "http://127.0.0.1:8080/#x\n"):
            with self.assertRaises(ValueError, msg=repr(url)) as ctx:
                check_uix_url(url)
            self.assertEqual(str(ctx.exception), "uix_url_not_allowed")

    def test_brackets_are_refused_with_our_own_error(self):
        # urllib.parse raises its own ValueError for these ("Invalid IPv6 URL", ...); that message must not leak out.
        for url in ("http://[::1/", "http://[::1]:8080/", "http://[127.0.0.1]:8080/", "http://[/", "http://127.0.0.1:8080[/"):
            with self.assertRaises(ValueError, msg=repr(url)) as ctx:
                check_uix_url(url)
            self.assertEqual(str(ctx.exception), "uix_url_not_allowed")

    def test_brackets_in_the_fragment_are_allowed(self):
        # The fragment may hold anything except whitespace, so a fix for the bracket case must not refuse these.
        for url in ("http://127.0.0.1:8080/#[x]", "http://127.0.0.1:8080/#[", "http://127.0.0.1:8080/#a[::1]b"):
            self.assertEqual(check_uix_url(url), url)


class Argv(unittest.TestCase):
    def test_exact_argument_list(self):
        self.assertEqual(window_argv("C:\\e\\msedge.exe", URL, "C:\\p\\profile"), [
            "C:\\e\\msedge.exe", "--app=" + URL, "--user-data-dir=C:\\p\\profile", "--window-size=1280,820",
            "--no-first-run", "--no-default-browser-check", "--disable-extensions"])
        self.assertEqual(DEFAULT_SIZE, (1280, 820))

    def test_custom_size_and_its_limits(self):
        self.assertEqual(window_argv("b", URL, "p", size=(400, 7680))[3], "--window-size=400,7680")
        for size in ((399, 800), (800, 7681), (800.0, 600), ("800", 600), (800,), None):
            with self.assertRaises(ValueError, msg=repr(size)) as ctx:
                window_argv("b", URL, "p", size=size)
            self.assertEqual(str(ctx.exception), "invalid_window_size")

    def test_bad_url_and_profile(self):
        with self.assertRaises(ValueError) as ctx:
            window_argv("b", "https://example.com/", "p")
        self.assertEqual(str(ctx.exception), "uix_url_not_allowed")
        for profile in ("", None):
            with self.assertRaises(ValueError) as ctx:
                window_argv("b", URL, profile)
            self.assertEqual(str(ctx.exception), "profile_dir_required")


if __name__ == "__main__":
    unittest.main()
