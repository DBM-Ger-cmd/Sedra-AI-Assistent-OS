import importlib

MODULES = ("guppi_runtime.desk.orchestra_kinds", "guppi_runtime.wissen.desk_wissen")     # Spec 7 (G2-S7-u)


def _reason(exc):
    s = str(exc)
    if s:
        return s
    return type(exc).__name__


def load(registry, hub, modules=MODULES, importer=importlib.import_module, audit=None):
    succeeded = []
    for name in modules:
        mark = registry.mark()
        try:
            module = importer(name)
            register = getattr(module, "register", None)
            if not callable(register):
                raise ValueError("extension_without_register")
            register(registry, hub)
        except Exception as exc:
            registry.reset(mark)
            reason = _reason(exc)
            registry.refuse(name, reason)
            if audit is not None:
                audit("DESK_KIND_REFUSED", {"module": name, "reason": reason})
            continue
        succeeded.append(module)
    return succeeded


def start(hub, loaded, audit=None):
    result = []
    for module in loaded:
        fn = getattr(module, "start", None)
        if not callable(fn):
            continue
        try:
            fn(hub)
        except Exception as exc:
            reason = _reason(exc)
            if audit is not None:
                audit("DESK_EXTENSION_START_FAILED", {"module": module.__name__, "reason": reason})
            continue
        result.append(module.__name__)
    return result


def snapshot(hub, loaded):
    """Spec 4 (D4.3.2): was die Erweiterungen dem Schnappschuss des Ereignisstroms beilegen (z. B. `orchestra`, `slots`).
    Ein Modul ohne `snapshot` legt nichts bei; ein Fehler darin kostet nur seinen Teil, nicht die Ereignisse der anderen."""
    out = {}
    for module in loaded:
        fn = getattr(module, "snapshot", None)
        if not callable(fn):
            continue
        try:
            part = fn(hub)
        except Exception:
            continue
        if isinstance(part, dict):
            for key, value in part.items():
                out.setdefault(key, value)
    return out
