import importlib

MODULES = ("guppi_runtime.desk.orchestra_kinds",)


def _reason(exc):
    return str(exc) or type(exc).__name__


def _report(audit, event, name, reason):
    if audit is not None:
        audit(event, {"module": name, "reason": reason})


def load(registry, hub, modules=MODULES, importer=importlib.import_module, audit=None):
    loaded = []
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
            registry.refuse(name, _reason(exc))
            _report(audit, "DESK_KIND_REFUSED", name, _reason(exc))
            continue
        loaded.append(module)
    return loaded


def start(hub, loaded, audit=None):
    started = []
    for module in loaded:
        begin = getattr(module, "start", None)
        if not callable(begin):
            continue
        name = getattr(module, "__name__", "?")
        try:
            begin(hub)
        except Exception as exc:
            _report(audit, "DESK_EXTENSION_START_FAILED", name, _reason(exc))
            continue
        started.append(name)
    return started
