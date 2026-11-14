"""F2-01: Universal Factory Framework / Registry — Tests.

Keine externen Abhängigkeiten, kein Modell, kein Netzwerk. Laufbar mit unittest.
"""
from __future__ import annotations

import unittest

from sedra_runtime.factory_registry import (  # noqa: E402
    ACTIVE,
    READY,
    REGISTERED,
    RETIRED,
    FactoryRegistry,
    FactoryRegistryError,
)


class FactoryRegistryTest(unittest.TestCase):
    def setUp(self):
        self.reg = FactoryRegistry()

    def test_registriere_typ_legt_registriert_an(self):
        ft = self.reg.registriere_typ("ft-1", "Test Factory", ["bau", "prüfung"])
        self.assertEqual(ft.typ_id, "ft-1")
        self.assertEqual(ft.name, "Test Factory")
        self.assertEqual(ft.functionen, {"bau", "prüfung"})
        self.assertEqual(ft.zustand, REGISTERED)
        self.assertFalse(ft.manifest_ref is not None and ft.manifest_ref)

    def test_doppelte_registrierung_wird_abgelehnt(self):
        self.reg.registriere_typ("ft-1", "Erste")
        with self.assertRaises(FactoryRegistryError) as ctx:
            self.reg.registriere_typ("ft-1", "Zweite")
        self.assertIn("typ_bereits_registriert", str(ctx.exception))

    def test_liste_typen_enthält_alle(self):
        self.reg.registriere_typ("ft-1", "Eins", ["a"])
        self.reg.registriere_typ("ft-2", "Zwei", ["b"])
        typen = self.reg.liste_typen()
        self.assertEqual(len(typen), 2)
        ids = {t["typ_id"] for t in typen}
        self.assertEqual(ids, {"ft-1", "ft-2"})

    def test_uebergang_registered_ready_braucht_gate(self):
        self.reg.registriere_typ("ft-1", "Test")
        with self.assertRaises(FactoryRegistryError) as ctx:
            self.reg.wechsel_zustand("ft-1", READY)
        self.assertIn("gate_freigabe_erforderlich", str(ctx.exception))
        # Zustand bleibt unverändert
        self.assertEqual(self.reg.get("ft-1").zustand, REGISTERED)

    def test_uebergang_registered_ready_mit_gate(self):
        self.reg.registriere_typ("ft-1", "Test")
        self.reg.gate_freigabe_setzen("ft-1")
        ft = self.reg.wechsel_zustand("ft-1", READY, gate_freigabe=True)
        self.assertEqual(ft.zustand, READY)

    def test_uebergang_ready_aktiv_braucht_gate(self):
        self.reg.registriere_typ("ft-1", "Test")
        self.reg.gate_freigabe_setzen("ft-1")
        self.reg.wechsel_zustand("ft-1", READY, gate_freigabe=True)
        # Zweiter Übergang ohne Gate scheitert
        with self.assertRaises(FactoryRegistryError) as ctx:
            self.reg.wechsel_zustand("ft-1", ACTIVE)
        self.assertIn("gate_freigabe_erforderlich", str(ctx.exception))

    def test_uebergang_zu_retired_ohne_gate(self):
        """RETIRED ist jederzeit möglich (auch ohne Gate)."""
        self.reg.registriere_typ("ft-1", "Test")
        ft = self.reg.wechsel_zustand("ft-1", RETIRED)
        self.assertEqual(ft.zustand, RETIRED)

    def test_ungueltiger_uebergang_wird_abgelehnt(self):
        self.reg.registriere_typ("ft-1", "Test")
        self.reg.gate_freigabe_setzen("ft-1")
        self.reg.wechsel_zustand("ft-1", READY, gate_freigabe=True)
        # Direkt READY -> ACTIVE geht, aber READY -> REGISTERED nicht
        with self.assertRaises(FactoryRegistryError) as ctx:
            self.reg.wechsel_zustand("ft-1", REGISTERED, gate_freigabe=True)
        self.assertIn("ungueltiger_uebergang", str(ctx.exception))

    def test_funktionen_hinzufuegen_braucht_gate(self):
        self.reg.registriere_typ("ft-1", "Test", ["a"])
        with self.assertRaises(FactoryRegistryError) as ctx:
            self.reg.funktionen_hinzufuegen("ft-1", ["b"])
        self.assertIn("gate_freigabe_erforderlich", str(ctx.exception))
        self.assertEqual(self.reg.get("ft-1").functionen, {"a"})

    def test_funktionen_hinzufuegen_mit_gate(self):
        self.reg.registriere_typ("ft-1", "Test", ["a"])
        self.reg.gate_freigabe_setzen("ft-1")
        ft = self.reg.funktionen_hinzufuegen("ft-1", ["b", "c"], gate_freigabe=True)
        self.assertEqual(ft.functionen, {"a", "b", "c"})

    def test_funktionen_entfernen_braucht_gate(self):
        self.reg.registriere_typ("ft-1", "Test", ["a", "b"])
        self.reg.gate_freigabe_setzen("ft-1")
        self.reg.funktionen_hinzufuegen("ft-1", ["c"], gate_freigabe=True)
        with self.assertRaises(FactoryRegistryError) as ctx:
            self.reg.funktionen_entfernen("ft-1", ["c"])
        self.assertIn("gate_freigabe_erforderlich", str(ctx.exception))

    def test_get_gibt_none_für_unbekannt(self):
        self.assertIsNone(self.reg.get("nicht-da"))

    def test_health(self):
        self.reg.registriere_typ("ft-1", "Eins", ["a"])
        self.reg.registriere_typ("ft-2", "Zwei", ["b"])
        h = self.reg.health()
        self.assertEqual(h["typen"], 2)
        self.assertEqual(h["zustände"][REGISTERED], 2)
        self.assertTrue(h["ok"])

    def test_manifest_ref_leiht_keine_rechte(self):
        """Ein Manifest-Referenz im Typ ergibt keine automatische Gate-Freigabe."""
        self.reg.registriere_typ("ft-1", "Test", manifest_ref="config/factory.yaml")
        self.assertFalse(self.reg.hat_gate_freigabe("ft-1"))
        # Zustandsänderung ohne Gate scheitert trotz manifest_ref
        with self.assertRaises(FactoryRegistryError):
            self.reg.wechsel_zustand("ft-1", READY)


if __name__ == "__main__":
    unittest.main()
