"""AM3 (SPEC_APPS_v1_AM3_BERECHTIGUNG): der reine Kern der Rechte – Fähigkeiten aus `rechte`, Schutzstufen A/B/C, Diff beim Update, Schlüssel der Entscheidung."""
import hashlib
import unittest

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.rechte_diff import rechte_diff, rechte_schluessel, rechte_urteil, rechte_zu_faehigkeiten, stufe


class Faehigkeiten(unittest.TestCase):
    def test_alle_schluessel(self):
        rechte = {"lesen": ["b", "a", "b"], "verben": ["x.y"], "ereignisse": ["system.state"], "zelle": "text", "ablage": 5, "dienst": "microvm"}
        self.assertEqual(rechte_zu_faehigkeiten(rechte), ["ablage:5", "dienst:microvm", "ereignis:system.state", "lesen:a", "lesen:b", "verb:x.y", "zelle:text"])

    def test_leer(self):
        self.assertEqual(rechte_zu_faehigkeiten(None), [])
        self.assertEqual(rechte_zu_faehigkeiten({"zelle": "nein", "ablage": 0, "dienst": "nein"}), [])

    def test_fehler(self):
        for rechte, text in (("x", "rechte_ungueltig"), ({"zebra": 1, "alpha": 1}, "rechte_unbekannt:alpha"), ({"lesen": "x"}, "rechte_ungueltig:lesen"),
                             ({"zelle": "ja"}, "rechte_ungueltig:zelle"), ({"ablage": True}, "rechte_ungueltig:ablage"), ({"dienst": "cloud"}, "rechte_ungueltig:dienst")):
            with self.assertRaises(ValueError) as ctx:
                rechte_zu_faehigkeiten(rechte)
            self.assertEqual(str(ctx.exception), text)


class Stufen(unittest.TestCase):
    def test_stufen(self):
        for f, s in (("lesen:rechnung", "A"), ("verb:a.b", "B"), ("ereignis:system.state", "A"), ("ereignis:decision.pending", "B"), ("zelle:text", "B"), ("zelle:bild", "C"),
                     ("ablage:1048576", "A"), ("ablage:1048577", "B"), ("ablage:abc", "C"), ("dienst:microvm", "B"), ("dienst:host", "C"), ("route:GET /x", "C"),
                     ("lesen:", "C"), ("", "C"), (None, "C")):
            self.assertEqual(stufe(f), s, f)

    def test_unicode_ziffern_stuerzen_nicht_ab(self):
        self.assertEqual(stufe("ablage:²"), "C")


class Diff(unittest.TestCase):
    def test_neu_und_entfallen_sortiert(self):
        d = rechte_diff({"lesen": ["a", "b"], "verben": ["x.y"]}, {"lesen": ["b", "c"], "zelle": "text", "dienst": "host"})
        self.assertEqual([(x["faehigkeit"], x["richtung"], x["stufe"]) for x in d],
                         [("dienst:host", "neu", "C"), ("lesen:c", "neu", "A"), ("zelle:text", "neu", "B"), ("lesen:a", "entfallen", "A"), ("verb:x.y", "entfallen", "B")])

    def test_geaenderte_ablage_ist_entfallen_plus_neu(self):
        d = rechte_diff({"ablage": 1000}, {"ablage": 2000000})
        self.assertEqual([(x["faehigkeit"], x["richtung"]) for x in d], [("ablage:2000000", "neu"), ("ablage:1000", "entfallen")])

    def test_urteil(self):
        d = rechte_diff({"verben": ["x.y"]}, {"zelle": "text", "dienst": "host"})
        self.assertEqual(rechte_urteil(d), {"braucht_gate": True, "abgewiesen": ["dienst:host"]})
        self.assertEqual(rechte_urteil(rechte_diff({"verben": ["x.y"], "dienst": "host"}, None)), {"braucht_gate": False, "abgewiesen": []})
        self.assertEqual(rechte_urteil(None), {"braucht_gate": False, "abgewiesen": []})

    def test_urteil_liest_die_stufe_des_eintrags(self):
        eintrag = [{"richtung": "neu", "stufe": "B", "faehigkeit": "lesen:a"}, {"richtung": "neu", "stufe": "C", "faehigkeit": "lesen:b"}]
        self.assertEqual(rechte_urteil(eintrag), {"braucht_gate": True, "abgewiesen": ["lesen:b"]})


class Schluessel(unittest.TestCase):
    def test_schluessel(self):
        h = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()  # noqa: E731
        self.assertEqual(rechte_schluessel(["b", "a", "a"]), h("a\nb"))
        self.assertEqual(rechte_schluessel([]), h(""))
        for falsch in (None, "a", [1], ("a",)):
            with self.assertRaises(ValueError):
                rechte_schluessel(falsch)


if __name__ == "__main__":
    unittest.main()
