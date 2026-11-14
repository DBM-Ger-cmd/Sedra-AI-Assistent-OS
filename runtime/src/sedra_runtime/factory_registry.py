"""F2-01: Universal Factory Framework / Registry.

Gemeinsame Factory-Registry/Lifecycle-Schnittstellen. Der Control Core bleibt Gate:
Factory-Typen können nur explizite Funktionen registrieren; kein Recht wird aus
einem Manifest abgeleitet.

Rein: kein Netz, kein Zustand, keine Wirkung außer der internen Registry.
"""
from __future__ import annotations
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- Lifecycle-Zustände
# Ein Factory-Typ durchläuft diese Zustände. Jeder Übergang ist eine explizite
# Funktion; das Manifest legt keine Rechte fest.
REGISTERED = "registered"
READY = "ready"
ACTIVE = "active"
RETIRED = "retired"

# Gültige Übergänge (von -> nach). Alles andere wird abgelehnt.
VALID_TRANSITIONS = {
    REGISTERED: {READY, RETIRED},
    READY: {ACTIVE, RETIRED},
    ACTIVE: {RETIRED},
    RETIRED: set(),
}

# ---------------------------------------------------------------- Factory-Fehler
class FactoryRegistryError(ValueError):
    """Die Registry lehnt eine ungültige Registrierung oder Übergabe ab."""


@dataclass
class FactoryType:
    """Ein registrierter Factory-Typ mit Lifecycle-Zustand."""
    typ_id: str
    name: str
    functionen: set[str] = field(default_factory=set)   # explizite Funktionen
    zustand: str = REGISTERED
    manifest_ref: str | None = None                     # nur Referenz, keine Rechte
    meta: dict[str, Any] = field(default_factory=dict)


class FactoryRegistry:
    """Zentrale Registry aller Factory-Typen.

    Der Control Core bleibt Gate: jede Registrierung und jeder Zustandsübergang
    ist eine explizite Funktion. Ein Manifest liefert keine Rechte.
    """

    def __init__(self) -> None:
        self._typen: dict[str, FactoryType] = {}
        self._gate_erlaubt: set[str] = set()   # IDs, die der Control Core freigegeben hat

    # ---------------------------------------------------------------- Registrierung
    def registriere_typ(
        self,
        typ_id: str,
        name: str,
        functionen: list[str] | None = None,
        manifest_ref: str | None = None,
        *,
        gate_freigabe: bool = False,
    ) -> FactoryType:
        """Registriert einen neuen Factory-Typ.

        `gate_freigabe` muss vom Control Core gesetzt werden (kein Recht aus Manifest).
        """
        if typ_id in self._typen:
            raise FactoryRegistryError(f"typ_bereits_registriert:{typ_id}")
        ft = FactoryType(
            typ_id=typ_id,
            name=name,
            functionen=set(functionen or []),
            zustand=REGISTERED,
            manifest_ref=manifest_ref,
        )
        self._typen[typ_id] = ft
        if gate_freigabe:
            self._gate_erlaubt.add(typ_id)
        return ft

    def liste_typen(self) -> list[dict[str, Any]]:
        """Gibt alle registrierten Typen mit Zustand und Gate-Status zurück."""
        return [
            {
                "typ_id": ft.typ_id,
                "name": ft.name,
                "zustand": ft.zustand,
                "funktionen": sorted(ft.functionen),
                "manifest_ref": ft.manifest_ref,
                "gate_freigabe": ft.typ_id in self._gate_erlaubt,
            }
            for ft in self._typen.values()
        ]

    # ---------------------------------------------------------------- Lifecycle (Gate-geschützt)
    def wechsel_zustand(self, typ_id: str, neu: str, *, gate_freigabe: bool = False) -> FactoryType:
        """Wechselt den Lifecycle-Zustand. Nur explizite Übergänge, nur mit Gate-Freigabe."""
        if typ_id not in self._typen:
            raise FactoryRegistryError(f"typ_nicht_registriert:{typ_id}")
        ft = self._typen[typ_id]
        if neu not in VALID_TRANSITIONS.get(ft.zustand, set()):
            raise FactoryRegistryError(
                f"ungueltiger_uebergang:{typ_id}:{ft.zustand}->{neu}"
            )
        # Zustandsänderungen brauchen Gate-Freigabe (außer RETIRED, das jederzeit möglich ist)
        if neu != RETIRED and not gate_freigabe:
            raise FactoryRegistryError(f"gate_freigabe_erforderlich:{typ_id}:{neu}")
        ft.zustand = neu
        return ft

    def funktionen_hinzufuegen(
        self, typ_id: str, funktionen: list[str], *, gate_freigabe: bool = False
    ) -> FactoryType:
        """Fügt explizite Funktionen hinzu. Braucht Gate-Freigabe."""
        if typ_id not in self._typen:
            raise FactoryRegistryError(f"typ_nicht_registriert:{typ_id}")
        if not gate_freigabe:
            raise FactoryRegistryError(f"gate_freigabe_erforderlich:{typ_id}:funktionen_hinzufuegen")
        ft = self._typen[typ_id]
        ft.functionen.update(funktionen)
        return ft

    def funktionen_entfernen(
        self, typ_id: str, funktionen: list[str], *, gate_freigabe: bool = False
    ) -> FactoryType:
        """Entfernt Funktionen. Braucht Gate-Freigabe."""
        if typ_id not in self._typen:
            raise FactoryRegistryError(f"typ_nicht_registriert:{typ_id}")
        if not gate_freigabe:
            raise FactoryRegistryError(f"gate_freigabe_erforderlich:{typ_id}:funktionen_entfernen")
        ft = self._typen[typ_id]
        ft.functionen.difference_update(funktionen)
        return ft

    # ---------------------------------------------------------------- Gate (Control Core)
    def gate_freigabe_setzen(self, typ_id: str) -> None:
        """Der Control Core erteilt Gate-Freigabe für einen Typ."""
        if typ_id not in self._typen:
            raise FactoryRegistryError(f"typ_nicht_registriert:{typ_id}")
        self._gate_erlaubt.add(typ_id)

    def gate_freigabe_entfernen(self, typ_id: str) -> None:
        """Der Control Core entzieht Gate-Freigabe."""
        self._gate_erlaubt.discard(typ_id)

    def hat_gate_freigabe(self, typ_id: str) -> bool:
        return typ_id in self._gate_erlaubt

    def get(self, typ_id: str) -> FactoryType | None:
        return self._typen.get(typ_id)

    def health(self) -> dict[str, Any]:
        return {
            "typen": len(self._typen),
            "gate_freigegeben": len(self._gate_erlaubt),
            "zustände": {z: sum(1 for t in self._typen.values() if t.zustand == z) for z in (REGISTERED, READY, ACTIVE, RETIRED)},
            "ok": True,
        }

    def save(self, path: Path) -> None:
            """Speichert die Registry in eine JSON-Datei (atomar via tmp + rename)."""
            data = {
                "typen": {
                    tid: {
                        "typ_id": ft.typ_id,
                        "name": ft.name,
                        "funktionen": sorted(ft.functionen),
                        "zustand": ft.zustand,
                        "manifest_ref": ft.manifest_ref,
                        "meta": ft.meta,
                    }
                    for tid, ft in self._typen.items()
                },
                "gate_erlaubt": list(self._gate_erlaubt),
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            # Atomar: erst tmp-Datei schreiben, dann rename
            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', dir=path.parent, delete=False, suffix='.tmp'
            ) as tmp:
                json.dump(data, tmp, indent=2, ensure_ascii=False)
                tmp_path = Path(tmp.name)
            tmp_path.replace(path)

    @classmethod
    def load(cls, path: Path) -> "FactoryRegistry":
        """Lädt die Registry aus einer JSON-Datei."""
        registry = cls()
        if not path.exists():
            return registry
        data = json.loads(path.read_text(encoding="utf-8"))
        for tid, td in data.get("typen", {}).items():
            ft = FactoryType(
                typ_id=td["typ_id"],
                name=td["name"],
                functionen=set(td.get("funktionen", [])),
                zustand=td.get("zustand", REGISTERED),
                manifest_ref=td.get("manifest_ref"),
                meta=td.get("meta", {}),
            )
            registry._typen[tid] = ft
        registry._gate_erlaubt = set(data.get("gate_erlaubt", []))
        return registry


__all__ = [
    "FactoryRegistry",
    "FactoryType",
    "FactoryRegistryError",
    "REGISTERED",
    "READY",
    "ACTIVE",
    "RETIRED",
]
