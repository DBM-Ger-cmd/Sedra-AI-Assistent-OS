# Harness-Shell Stufe 3, N2: die Deckung einer Aufgaben-Freigabe (SPEC_HARNESS_SHELL_v1 HS-27, G2 Stufe 3 §4.2).
# Gebaut von SEDRA (devvm_build --spec harness_aufgabe_deckung --profile standard, Qwen3.6-35B-A3B, 29.10.2026, versteckt 15/15, Kandidat
# runtime_data/devvm_candidates/harness_aufgabe_deckung/attempt_01_20261029_132428). Übernommen mit drei Korrekturen von Claude (Captain 29.10.2026,
# Eingriff im Logbuch): (1) ein `bis`, das kein lesbarer Zeitpunkt mit Zeitzone ist, gilt als abgelaufen; (2) ein `max_aufrufe`, das keine ganze Zahl
# ist, gilt als erschöpft; (3) eine Aufgabe ohne `id` wirft nicht, IDs werden als Text verglichen. Sonst unverändert; die Referenz von Claude steht
# in benchmarks/devvm_refs/harness_aufgabe_deckung, test_harness_aufgabe_deckung_vergleich hält beide gleich.
from datetime import datetime, timezone


def _is_aktiv(aufgabe):
    if not isinstance(aufgabe, dict):
        return False
    s = aufgabe.get("status")
    return s == "aktiv"


def _parse_bis(ende):
    bis = None
    if isinstance(ende, dict):
        bis = ende.get("bis")
    if bis is None:
        return None
    try:
        dt = datetime.fromisoformat(bis) if isinstance(bis, str) else bis
        if not isinstance(dt, datetime) or dt.tzinfo is None:
            return False
        return dt
    except (ValueError, TypeError):
        return False


def _max_used(aufgabe):
    ende = aufgabe.get("ende")
    if not isinstance(ende, dict):
        return None
    m = ende.get("max_aufrufe")
    if m is None:
        return None
    if not isinstance(m, int) or isinstance(m, bool):
        return False
    return m


def _aufrufe_ok(aufgabe):
    a = aufgabe.get("aufrufe")
    if not isinstance(a, int) or isinstance(a, bool):
        return False
    return True

def zustand(aufgabe, jetzt):
    if not isinstance(aufgabe, dict):
        return "zurueckgenommen"
    s = aufgabe.get("status")
    if s != "aktiv":
        if isinstance(s, str):
            return s
        return "zurueckgenommen"
    ende = aufgabe.get("ende")
    if not isinstance(ende, dict):
        return "aktiv"
    bis_dt = _parse_bis(ende)
    if bis_dt is False:
        return "abgelaufen"
    if bis_dt is not None:
        try:
            if jetzt >= bis_dt:
                return "abgelaufen"
        except (TypeError, ValueError):
            return "abgelaufen"
    mx = _max_used(aufgabe)
    if mx is not None:
        if mx is False or not _aufrufe_ok(aufgabe):
            return "erschoepft"
        if aufgabe["aufrufe"] >= mx:
            return "erschoepft"
    return "aktiv"

def deckt(aufgaben, sitzung_id, werkzeug, ziel, jetzt, passt):
    if not isinstance(aufgaben, list):
        return None
    candidates = []
    for a in aufgaben:
        if zustand(a, jetzt) != "aktiv":
            continue
        sitz = a.get("sitzungen")
        if not isinstance(sitz, list) or sitzung_id not in sitz:
            continue
        erlaubt = a.get("erlaubt")
        if not isinstance(erlaubt, list):
            continue
        for entry in erlaubt:
            if not isinstance(entry, dict):
                continue
            if entry.get("werkzeug") != werkzeug:
                continue
            muster = entry.get("muster")
            try:
                if not passt(muster, werkzeug, ziel):
                    continue
            except Exception:
                continue
            bis_dt = _parse_bis(a.get("ende"))
            candidates.append((str(a.get("id")), bis_dt, entry))
            break
    if not candidates:
        return None
    def sort_key(c):
        bid, bis_dt, _ = c
        if bis_dt is not None and bis_dt is not False:
            return (0, bis_dt, bid)
        return (1, datetime.max.replace(tzinfo=timezone.utc), bid)
    candidates.sort(key=sort_key)
    winner = candidates[0]
    return {"aufgabe_id": winner[0], "eintrag": winner[2]}
