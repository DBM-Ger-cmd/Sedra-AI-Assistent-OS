"""Gemeinsamer KV-Pool (`--kv-unified`): ein Manager mit grossem Fenster und mehrere Angestellte mit kleinem Fenster in EINEM Server.

Ohne den Schalter teilt llama-server `-c` gleichmaessig auf die Slots: jeder Slot bekommt dasselbe Fenster, `-c` = Fenster x Slots. Mit `kv_unified: true`
im Server-Block des Rezepts teilen sich alle Slots einen Pool; ein Slot darf so viel davon nutzen, wie frei ist (Motor b11160, auf das Trainingsfenster
des Modells gekappt). Das Rezept sagt dann:
  - Fenster (Stufen, `per_slots`) = das Fenster des MANAGERS, des groessten einzelnen Slots,
  - `kv_pool_je_angestellter` = die Token, die jeder weitere Slot (Angestellter) zusaetzlich im Pool bekommt.
Pool (`-c`) = Fenster des Managers + (Slots - 1) x kv_pool_je_angestellter. Nur Rechnung, ohne Seiteneffekte."""
from __future__ import annotations


def aktiv(server) -> bool:
    return bool((server or {}).get("kv_unified"))


def zusatz(server, slots) -> int | None:
    """Token der weiteren Slots im Pool; None = kein Pool (gleiche Slots)."""
    if not aktiv(server):
        return None
    return max(0, int(slots or 1) - 1) * int((server or {}).get("kv_pool_je_angestellter") or 0)


def gesamt(server, fenster, slots):
    """`-c` fuer das Fenster des Managers (bzw. des einzelnen Slots) und die Zahl der Slots."""
    z = zusatz(server, slots)
    return fenster * int(slots or 1) if z is None else fenster + z


def fenster_aus_gesamt(server, gesamt_token, slots):
    """Das Fenster des Managers (bzw. je Slot) aus dem Wert, den der Server als `n_ctx` meldet."""
    z = zusatz(server, slots)
    if z is None:
        return gesamt_token // int(slots or 1) if int(slots or 1) > 1 else gesamt_token
    return gesamt_token - z
