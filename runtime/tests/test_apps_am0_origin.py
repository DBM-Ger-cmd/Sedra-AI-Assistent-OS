"""AM0-09 (SPEC_APPS_v1_AM0_G2 §9): ein Rahmen ohne `allow-same-origin` sendet `Origin: null`. Der Server lehnt das ab – auch mit gültigem Browser-Token – für GET, POST,
PATCH und DELETE. Der Test hält das fest, damit eine spätere Änderung an `_same_origin_ok` es nicht stillschweigend öffnet."""
import http.client
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.uix_server import UIXHub, make_server

ARCH = Path(__file__).resolve().parents[2] / "architecture" / "SEDRA_Architecture_v1.17_RUNTIME_SYNC"


class OriginNull(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am0-origin-")
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        server, url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port = server.server_port
        self.token = url.split("#")[1]

    def anfrage(self, methode, pfad, origin=None, body=None):
        kopf = {"X-SEDRA-Token": self.token}
        if origin is not None:
            kopf["Origin"] = origin
        if body is not None:
            kopf["Content-Type"] = "application/json"
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            c.request(methode, pfad, body, kopf)
            res = c.getresponse()
            res.read()
            return res.status
        finally:
            c.close()

    def test_get_mit_origin_null_wird_abgelehnt(self):
        self.assertEqual(self.anfrage("GET", "/api/strip", origin="null"), 403)

    def test_post_mit_origin_null_wird_abgelehnt(self):
        self.assertEqual(self.anfrage("POST", "/api/objects", origin="null", body="{}"), 403)

    def test_patch_und_delete_mit_origin_null_werden_abgelehnt(self):
        self.assertEqual(self.anfrage("PATCH", "/api/harness/sitzungen/S-0", origin="null", body="{}"), 403)
        self.assertEqual(self.anfrage("DELETE", "/api/harness/sitzungen/S-0", origin="null"), 403)

    def test_dieselbe_anfrage_ohne_origin_wird_angenommen(self):
        self.assertEqual(self.anfrage("GET", "/api/strip"), 200)

    def test_origin_der_eigenen_seite_wird_angenommen(self):
        self.assertEqual(self.anfrage("GET", "/api/strip", origin=f"http://127.0.0.1:{self.port}"), 200)

    def test_fremder_origin_wird_abgelehnt(self):
        self.assertEqual(self.anfrage("GET", "/api/strip", origin="http://evil.example"), 403)


if __name__ == "__main__":
    unittest.main()
