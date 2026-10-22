"""VRAM arithmetic of the model scheduler (Spec 2, D2.2, SCH-03, S2.C1). Pure: no files, no clock, no guppi_runtime import.

One server holds the weights ONCE and the KV cache once per slot. The limit (Captain 2026-10-22: 11.5 GB INCLUDING the reserve of 0.7 GB, so 10.8 GB usable) is checked
first; then the measured free memory, from which the reserve is taken as well. The ledger of the resource scheduler is a third, separate check.
"""
from __future__ import annotations

EPS = 1e-9      # 8.7 - 0.7 is 7.999999999999999 in floating point: an exact fit must still fit


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError("value_invalid")
    return float(value)


def _slots(slots):
    if type(slots) is not int or not 1 <= slots <= 8:
        raise ValueError("slots_invalid")
    return slots


def server_need(weights_gb, kv_gb_per_slot, slots, compute_gb=0.0, ram_gb=0.0):
    """What one server with `slots` slots needs: {vram_gb, ram_gb}. Weights and compute buffers once, the KV cache per slot."""
    weights, kv, compute, ram = (_number(v) for v in (weights_gb, kv_gb_per_slot, compute_gb, ram_gb))
    return {"vram_gb": round(weights + compute + kv * _slots(slots), 3), "ram_gb": round(ram, 3)}


def fits(need_gb, limit_gb, reserve_gb, measured_free_gb):
    """None when the start fits, else {need_gb, measured_free_gb, limit_gb, reserve_gb, reason}; reason `limit` (need above limit minus reserve) or `frei` (above measured free minus reserve)."""
    need, limit, reserve, free = (_number(v) for v in (need_gb, limit_gb, reserve_gb, measured_free_gb))
    reason = "limit" if need - (limit - reserve) > EPS else "frei" if need - (free - reserve) > EPS else None
    if reason is None:
        return None
    return {"need_gb": round(need, 3), "measured_free_gb": round(free, 3), "limit_gb": round(limit, 3), "reserve_gb": round(reserve, 3), "reason": reason}


def max_slots(weights_gb, kv_gb_per_slot, compute_gb, limit_gb, reserve_gb=0.0, cap=8):
    """The largest slot count (at most `cap`) whose server need stays within limit minus reserve; 0 when not even one slot fits."""
    weights, kv, compute, limit, reserve = (_number(v) for v in (weights_gb, kv_gb_per_slot, compute_gb, limit_gb, reserve_gb))
    _slots(cap)
    room = limit - reserve - weights - compute
    if room < 0:
        return 0
    return cap if kv == 0 else max(0, min(cap, int(room / kv + 1e-9)))
