"""Gemeinsame Helfer der Fabrik-Prüfungen (Referenz zur Bau-Spec factory_sdk_grundlage)."""
import re

SCHEMA_VERSION = "1.0.0"


class FabrikFehler(ValueError):
    def __init__(self, code, field=""):
        super().__init__(f"{code}" + (f" ({field})" if field else ""))
        self.code = code
        self.field = field


def verlange_objekt(daten, art):
    if not isinstance(daten, dict):
        raise FabrikFehler("kein_objekt", "")
    if daten.get("schema_version") != SCHEMA_VERSION:
        raise FabrikFehler("schema_version_unzulaessig", "schema_version")
    if daten.get("kind") != art:
        raise FabrikFehler("art_unzulaessig", "kind")


def verlange_feld(daten, feld):
    if feld not in daten or daten[feld] in (None, ""):
        raise FabrikFehler("pflichtfeld_fehlt", feld)
    return daten[feld]


def verlange_aufzaehlung(wert, erlaubt, feld):
    if wert not in erlaubt:
        raise FabrikFehler("wert_unzulaessig", feld)
    return wert


def verlange_hex(wert, feld):
    if not isinstance(wert, str) or not re.fullmatch(r"[0-9a-f]{64}", wert):
        raise FabrikFehler("hash_unzulaessig", feld)
    return wert


def verlange_keine_zusatzfelder(daten, erlaubt, feld=""):
    extra = sorted(set(daten) - set(erlaubt))
    if extra:
        raise FabrikFehler("zusatzfeld_verboten", extra[0])
