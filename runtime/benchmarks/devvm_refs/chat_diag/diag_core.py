KNOWN = ("status", "fehler", "rebind", "modelle", "log", "hilfe")
LABELS = {"gpu": "Grafikkarte", "lease": "GPU-Lease", "model": "Modell", "canary": "GPU-Selbsttest", "profile": "Hardware-Profil"}
PATTERNS = [
    ("hardware_profile_changed", "Hardware-Profil passt nicht mehr zu diesem PC", "Meist nach einem Treiber-Update. Mit /rebind neu binden.", "rebind"),
    ("hardware_pressure", "Nicht genug freier Grafikspeicher", "Andere Programme beenden, die die Grafikkarte nutzen, oder ein kleineres Modell wählen.", "free_vram"),
    ("gpu_canary_failed", "GPU-Selbsttest fehlgeschlagen", "NVIDIA-Debug-Modus prüfen, dann den Selbsttest wiederholen.", "canary"),
    ("valid_gguf_model_required", "Modelldatei nicht gefunden", "Pfad der Modelldatei im Rezept prüfen.", "check_files"),
    ("port_in_use", "Port belegt", "Den laufenden Server im Fenster Modelle beenden.", "stop_server"),
    ("model_loader_unavailable", "Automatisches Laden ist aus", "Den Schalter im Fenster Modelle einschalten.", "enable_loader"),
]


def explain_error(raw):
    text = raw if isinstance(raw, str) else ""
    if text.startswith("gpu_lease_busy"):
        parts = text.split(":")
        owner = parts[1] if len(parts) > 1 and parts[1] else "jemand anderem"
        purpose = parts[2] if len(parts) > 2 and parts[2] else ""
        hint = "Warten, bis der Lauf fertig ist" + (" (" + purpose + ")" if purpose else "") + "."
        return {"code": "gpu_lease_busy", "title": "GPU belegt von " + owner, "hint": hint, "action": "wait"}
    for code, title, hint, action in PATTERNS:
        if code in text:
            return {"code": code, "title": title, "hint": hint, "action": action}
    return {"code": "unknown", "title": "Unbekannter Fehler", "hint": text[:200], "action": None}


def parse_command(text):
    if not isinstance(text, str) or not text.strip().startswith("/"):
        return None
    words = text.strip()[1:].split()
    name = words[0].lower() if words else ""
    args = words[1:]
    if name == "plan":
        return None
    if name not in KNOWN:
        return {"cmd": "unknown", "name": name, "args": [], "confirm": False}
    confirm = name == "rebind" and bool(args) and args[0].lower() in ("ja", "yes")
    return {"cmd": name, "args": args, "confirm": confirm}


def row(key, state, detail):
    return {"id": key, "label": LABELS[key], "state": state, "detail": detail}


def gpu_row(gpu):
    if not gpu:
        return row("gpu", "warn", "keine Messung")
    free = gpu["total_gb"] - gpu["used_gb"]
    state = "bad" if free < 2 else "warn" if free < 4 else "ok"
    return row("gpu", state, "%.1f GB frei von %.1f GB" % (free, gpu["total_gb"]))


def lease_row(lease):
    if not lease:
        return row("lease", "ok", "frei")
    if lease.get("mine"):
        return row("lease", "ok", "von GUPPI (diese Oberfläche)")
    if lease.get("stale"):
        return row("lease", "warn", "verwaist (%s)" % lease.get("owner"))
    return row("lease", "warn", "belegt von %s: %s" % (lease.get("owner"), lease.get("purpose")))


def model_row(model):
    if model and model.get("running"):
        return row("model", "ok", str(model.get("model")))
    return row("model", "warn", "kein Modell geladen")


def canary_row(canary):
    if not canary or canary.get("ok") is None:
        return row("canary", "warn", "noch nicht gelaufen")
    if canary["ok"]:
        return row("canary", "ok", "bestanden " + str(canary.get("at") or "").strip())
    return row("canary", "bad", "fehlgeschlagen")


def profile_row(profile):
    profile = profile or {}
    if profile.get("ok"):
        return row("profile", "ok", "passt zu diesem PC")
    if profile.get("rebind_needed"):
        return row("profile", "bad", "passt nicht mehr zu diesem PC: /rebind")
    return row("profile", "bad", profile.get("error") or "Fehler")


def status_rows(snap):
    snap = snap or {}
    return [gpu_row(snap.get("gpu")), lease_row(snap.get("lease")), model_row(snap.get("model")), canary_row(snap.get("canary")), profile_row(snap.get("hardware_profile"))]
