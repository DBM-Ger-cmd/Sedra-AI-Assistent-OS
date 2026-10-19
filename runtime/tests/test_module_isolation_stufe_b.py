"""Stufe B der Modul-Isolation (Plan docs/PLAN_ISOLATION_UND_UPDATE_2026-10-19.md, Abschnitt 3): die Durchsicht vor dem Einbau
erkennt den Zugriff auf den Kern-Zugang, die Adresse mit dem Token, Cookies und das Elternfenster."""
import unittest

from guppi_runtime.desk.install import scan_text


def flags(code):
    return sorted({f['flag'] for f in scan_text(code)})


class DurchsichtStufeB(unittest.TestCase):
    def test_access_to_the_core_api_is_flagged(self):
        self.assertIn('sedraApi', flags('const k = window.sedraApi.forModule({kind:"tool",id:"x"});'))

    def test_reading_the_address_that_carries_the_token_is_flagged(self):
        self.assertIn('location', flags('const t = location.hash;'))

    def test_cookies_are_flagged(self):
        self.assertIn('document.cookie', flags('document.cookie = "x=1";'))

    def test_the_parent_window_is_flagged(self):
        self.assertIn('window.parent/top', flags('window.parent.postMessage(1, "*");'))

    def test_dynamic_window_access_is_flagged(self):
        self.assertIn('window[...]', flags('window["sedra" + "Api"];'))

    def test_ordinary_module_code_passes(self):
        self.assertEqual(flags('const o = {a: 1}; console.log(o.name); ctx.api("/api/gateway/vorgaenge");'), [])


if __name__ == '__main__':
    unittest.main()
