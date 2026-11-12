"""AM7-18 (SPEC_APPS_v1_AM7_UNTERNEHMEN): die Aufbewahrung der Richtlinie – Frist der Entwürfe als Obergrenze, Gesprächsverläufe nach geloescht/ (nicht endgültig gelöscht),
höchstens ein Lauf je 24 Stunden, Audit nur mit Zahlen. Wegwerf-Projekt."""
import json
import os
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import aufbewahrung
from sedra_runtime.uix_server import UIXHub

from test_apps_betrieb import GUT, kopie
from test_desk_install import ARCH

TAG = 86400


class Aufbewahrung(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am7-aufb-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        (self.root / "local_config").mkdir(parents=True)
        (self.root / "local_config" / "switches.yaml").write_text("switches:\n  betrieb_unternehmen: {enabled: true}\n", encoding="utf-8")
        self.hub = self.neu(GUT)

    def neu(self, richtlinie):
        if getattr(self, "hub", None) is not None:
            self.hub.close()
        (self.root / "local_config" / "richtlinie.yaml").write_text(yaml.safe_dump(richtlinie), encoding="utf-8")
        hub = UIXHub(self.root, ARCH)
        self.addCleanup(hub.close)
        return hub

    def sitzung(self, titel, alter_tage):
        kopf = self.hub.harness.sitzungen.anlegen("projekt-x", titel=titel)
        pfad = self.hub.harness.sitzungen.ordner / f"{kopf['id']}.jsonl"
        alt = time.time() - alter_tage * TAG
        os.utime(pfad, (alt, alt))
        return kopf["id"], pfad

    def audit(self, art):
        zeilen = [json.loads(z) for z in self.hub.runtime.audit.path.read_text(encoding="utf-8").splitlines() if z.strip()]
        return [z for z in zeilen if z.get("event_type") == art]

    def test_frist_der_entwuerfe_ist_eine_obergrenze(self):
        stunden = lambda: (datetime.fromisoformat(self.hub.gw.loeschen_am()) - datetime.now().astimezone()).total_seconds() / 3600
        self.assertAlmostEqual(stunden(), 12, delta=0.1)                           # GUT: entwuerfe_stunden 12, Vorgabe 24
        self.hub = self.neu(kopie(aufbewahrung={"entwuerfe_stunden": 100}))
        self.assertAlmostEqual(stunden(), 24, delta=0.1, msg="die Richtlinie verlängert die Vorgabe nie")
        self.hub = self.neu(kopie(aufbewahrung={"gespraeche_tage": 30}))
        self.assertAlmostEqual(stunden(), 24, delta=0.1, msg="ohne Angabe bleibt die Vorgabe")

    def test_alte_gespraeche_gehen_nach_geloescht_junge_bleiben(self):
        alt, alt_pfad = self.sitzung("Vertrauliche Sache", 40)
        jung, jung_pfad = self.sitzung("Von heute", 1)
        erg = aufbewahrung.lauf(self.hub, erzwingen=True)
        self.assertEqual((erg["gespraeche_verschoben"], erg["gespraeche_uebersprungen"]), (1, 0))
        self.assertFalse(alt_pfad.exists())
        self.assertTrue((alt_pfad.parent / "geloescht" / alt_pfad.name).is_file(), "nichts wird endgültig gelöscht")
        self.assertTrue(jung_pfad.is_file())

    def test_audit_nennt_zahlen_und_fristen_nie_inhalte(self):
        self.sitzung("Vertrauliche Sache", 40)
        aufbewahrung.lauf(self.hub, erzwingen=True)
        e = self.audit("AUFBEWAHRUNG_LAUF")[-1]                                     # der erste Eintrag stammt vom Lauf beim Start
        self.assertEqual((e["payload"]["gespraeche_verschoben"], e["payload"]["gespraeche_tage"], e["payload"]["entwuerfe_stunden"]), (1, 30, 12))
        self.assertEqual(e["payload"]["person"], "Erika Muster", "AM7-12: Person und Rolle wie bei jedem Eintrag")
        self.assertNotIn("Vertrauliche", self.hub.runtime.audit.path.read_text(encoding="utf-8").replace("HARNESS_SITZUNG_VERSCHOBEN", ""))

    def test_hoechstens_ein_lauf_je_24_stunden(self):
        jetzt = time.time()
        self.assertIsNotNone(aufbewahrung.lauf(self.hub, jetzt=jetzt, erzwingen=True))
        self.assertIsNone(aufbewahrung.lauf(self.hub, jetzt=jetzt + 3600))
        self.assertIsNone(aufbewahrung.lauf(self.hub, jetzt=jetzt + TAG - 60))
        self.assertIsNotNone(aufbewahrung.lauf(self.hub, jetzt=jetzt + TAG + 60))
        self.assertAlmostEqual(aufbewahrung.zuletzt(self.root), jetzt + TAG + 60, delta=1)

    def test_der_blick_auf_den_betrieb_loest_den_lauf_aus(self):
        _, pfad = self.sitzung("Alt", 40)
        self.assertEqual(len(self.audit("AUFBEWAHRUNG_LAUF")), 1, "ein Lauf beim Start")
        self.hub.betrieb_view()
        self.assertTrue(pfad.exists(), "am selben Tag kein zweiter Lauf")
        (self.root / "local_config" / "aufbewahrung.json").unlink()                # als wäre der letzte Lauf lange her
        self.hub.betrieb_view()
        self.assertFalse(pfad.exists())
        self.assertEqual(len(self.audit("AUFBEWAHRUNG_LAUF")), 2)
        self.hub.betrieb_view()
        self.assertEqual(len(self.audit("AUFBEWAHRUNG_LAUF")), 2)

    def test_ohne_gespraeche_tage_bleiben_gespraeche_liegen(self):
        self.hub = self.neu(kopie(aufbewahrung={"entwuerfe_stunden": 12}))
        _, pfad = self.sitzung("Uralt", 400)
        erg = aufbewahrung.lauf(self.hub, erzwingen=True)
        self.assertEqual(erg["gespraeche_verschoben"], 0)
        self.assertTrue(pfad.is_file())

    def test_ohne_richtlinie_tut_der_lauf_nichts(self):
        self.hub.close()
        (self.root / "local_config" / "switches.yaml").write_text("switches:\n  betrieb_unternehmen: {enabled: false}\n", encoding="utf-8")
        hub = UIXHub(self.root, ARCH)
        self.addCleanup(hub.close)
        kopf = hub.harness.sitzungen.anlegen("projekt-x", titel="Alt")
        pfad = hub.harness.sitzungen.ordner / f"{kopf['id']}.jsonl"
        os.utime(pfad, (time.time() - 400 * TAG,) * 2)
        self.assertIsNone(aufbewahrung.lauf(hub, erzwingen=True))
        self.assertIsNone(hub._aufbewahrung())
        self.assertTrue(pfad.is_file())


if __name__ == "__main__":
    unittest.main()
