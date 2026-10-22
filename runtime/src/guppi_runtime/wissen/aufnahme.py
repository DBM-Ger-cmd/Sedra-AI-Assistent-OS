"""Der Takt der Aufnahme (Spec 7, D7.3, G2-S7-j): ein Thread je Prozess unter der Betriebssystem-Sperre
`local_config/wissen/takt.lock` (`core.mission_lock.exclusive`, nur benutzt); alle `intervall_s` (Vorgabe 600) ein Abgleich und
ein Einbett-Schritt über `WissenSpeicher.nachfuehren` – nur über freigegebene Quellen, nur CPU (D7.4). Wer die Sperre nicht
bekommt, taktet nicht (`wis_takt_busy`). Das Verb `wissen.nachfuehren` ruft dieselbe Funktion sofort."""
from __future__ import annotations

import threading
from contextlib import ExitStack

from ..core.mission_lock import exclusive

LOCK = "takt.lock"


def nachfuehren(speicher):
    """Ein Durchlauf: Abgleich aller aktiven Quellen und ein Einbett-Schritt; Fehler landen im Audit, nicht im Aufrufer."""
    try:
        return speicher.nachfuehren()
    except Exception as exc:                                     # der Takt stirbt nicht an einem Durchlauf
        speicher.audit("WIS_TAKT_FEHLER", {"error": (str(exc) or type(exc).__name__)[:200]})
        return {"fehler": str(exc) or type(exc).__name__}


def start(speicher, lock_path, intervall_s, *, sofort=False):
    """Den Takt starten; `wis_takt_busy`, wenn ein anderer Prozess die Sperre hält. Der Thread trägt `stop` (Event)."""
    stack = ExitStack()
    try:
        stack.enter_context(exclusive(lock_path))
    except RuntimeError as exc:
        stack.close()
        if str(exc) == "mission_execution_busy":
            raise ValueError("wis_takt_busy") from None
        raise
    stop = threading.Event()

    def loop():
        with stack:
            if not sofort:
                stop.wait(min(float(intervall_s), 30.0))         # der Start der Oberfläche bleibt frei von der ersten Aufnahme
            while not stop.is_set():
                nachfuehren(speicher)
                stop.wait(float(intervall_s))

    thread = threading.Thread(target=loop, name="wissen-takt", daemon=True)
    thread.stop = stop
    thread.start()
    return thread


def stop(thread, wait_s=5):
    if thread is not None:
        thread.stop.set()
        thread.join(wait_s)
