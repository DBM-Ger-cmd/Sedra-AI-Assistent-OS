

def explain_error(raw):
    if not isinstance(raw, str):
        raw = ""

    if raw.startswith("gpu_lease_busy"):
        parts = raw.split(":", 2)
        owner = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "jemand anderem"
        purpose = parts[2].strip() if len(parts) > 2 else ""
        hint = "Warten, bis der Lauf fertig ist"
        if purpose:
            hint += " (" + purpose + ")"
        hint += "."
        return {
            "code": "gpu_lease_busy",
            "title": "GPU belegt von " + owner,
            "hint": hint,
            "action": "wait",
        }

    keywords = [
        ("hardware_profile_changed",
         "Hardware-Profil passt nicht mehr zu diesem PC",
         "Meist nach einem Treiber-Update. Mit /rebind neu binden.",
         "rebind"),
        ("hardware_pressure",
         "Nicht genug freier Grafikspeicher",
         "Andere Programme beenden, die die Grafikkarte nutzen, oder ein kleineres Modell wählen.",
         "free_vram"),
        ("gpu_canary_failed",
         "GPU-Selbsttest fehlgeschlagen",
         "NVIDIA-Debug-Modus prüfen, dann den Selbsttest wiederholen.",
         "canary"),
        ("valid_gguf_model_required",
         "Modelldatei nicht gefunden",
         "Pfad der Modelldatei im Rezept prüfen.",
         "check_files"),
        ("port_in_use",
         "Port belegt",
         "Den laufenden Server im Fenster Modelle beenden.",
         "stop_server"),
        ("model_loader_unavailable",
         "Automatisches Laden ist aus",
         "Den Schalter im Fenster Modelle einschalten.",
         "enable_loader"),
    ]

    for word, title, hint, action in keywords:
        if word in raw:
            return {
                "code": word,
                "title": title,
                "hint": hint,
                "action": action,
            }

    return {
        "code": "unknown",
        "title": "Unbekannter Fehler",
        "hint": raw[:200],
        "action": None,
    }


def parse_command(text):
    if not isinstance(text, str):
        return None

    stripped = text.strip()
    if not stripped.startswith("/"):
        return None

    words = stripped[1:].split()

    if not words:
        name = ""
        args = []
    else:
        name = words[0].lower()
        args = words[1:]

    if name == "plan":
        return None

    known_commands = {"status", "fehler", "rebind", "modelle", "log", "hilfe"}

    if name not in known_commands:
        return {"cmd": "unknown", "name": name, "args": [], "confirm": False}

    confirm = False
    if name == "rebind" and args:
        if args[0].lower() in ("ja", "yes"):
            confirm = True

    return {"cmd": name, "args": args, "confirm": confirm}


def status_rows(snap):
    if snap is None:
        snap = {}

    rows = []

    gpu_data = snap.get("gpu")
    if gpu_data is None:
        rows.append({
            "id": "gpu",
            "label": "Grafikkarte",
            "state": "warn",
            "detail": "keine Messung",
        })
    else:
        used_gb = gpu_data.get("used_gb", 0)
        total_gb = gpu_data.get("total_gb", 0)
        free = total_gb - used_gb
        if free < 2:
            state = "bad"
        elif free < 4:
            state = "warn"
        else:
            state = "ok"
        rows.append({
            "id": "gpu",
            "label": "Grafikkarte",
            "state": state,
            "detail": "%.1f GB frei von %.1f GB" % (free, total_gb),
        })

    lease_data = snap.get("lease")
    if lease_data is None:
        rows.append({
            "id": "lease",
            "label": "GPU-Lease",
            "state": "ok",
            "detail": "frei",
        })
    else:
        if lease_data.get("mine"):
            rows.append({
                "id": "lease",
                "label": "GPU-Lease",
                "state": "ok",
                "detail": "von GUPPI (diese Oberfläche)",
            })
        elif lease_data.get("stale"):
            owner = lease_data.get("owner", "unbekannt")
            rows.append({
                "id": "lease",
                "label": "GPU-Lease",
                "state": "warn",
                "detail": "verwaist (" + owner + ")",
            })
        else:
            owner = lease_data.get("owner", "unbekannt")
            purpose = lease_data.get("purpose", "")
            if purpose:
                detail = "belegt von " + owner + ": " + purpose
            else:
                detail = "belegt von " + owner
            rows.append({
                "id": "lease",
                "label": "GPU-Lease",
                "state": "warn",
                "detail": detail,
            })

    model_data = snap.get("model")
    if model_data is None:
        rows.append({
            "id": "model",
            "label": "Modell",
            "state": "warn",
            "detail": "kein Modell geladen",
        })
    else:
        if model_data.get("running"):
            model_name = model_data.get("model", "")
            rows.append({
                "id": "model",
                "label": "Modell",
                "state": "ok",
                "detail": model_name,
            })
        else:
            rows.append({
                "id": "model",
                "label": "Modell",
                "state": "warn",
                "detail": "kein Modell geladen",
            })

    canary_data = snap.get("canary")
    if canary_data is None or canary_data.get("ok") is None:
        rows.append({
            "id": "canary",
            "label": "GPU-Selbsttest",
            "state": "warn",
            "detail": "noch nicht gelaufen",
        })
    else:
        if canary_data["ok"]:
            at = canary_data.get("at", "")
            if at is None:
                at = ""
            rows.append({
                "id": "canary",
                "label": "GPU-Selbsttest",
                "state": "ok",
                "detail": "bestanden " + at.strip(),
            })
        else:
            rows.append({
                "id": "canary",
                "label": "GPU-Selbsttest",
                "state": "bad",
                "detail": "fehlgeschlagen",
            })

    profile_data = snap.get("hardware_profile")
    if profile_data is None:
        profile_data = {}

    if profile_data.get("ok"):
        rows.append({
            "id": "profile",
            "label": "Hardware-Profil",
            "state": "ok",
            "detail": "passt zu diesem PC",
        })
    else:
        if profile_data.get("rebind_needed"):
            rows.append({
                "id": "profile",
                "label": "Hardware-Profil",
                "state": "bad",
                "detail": "passt nicht mehr zu diesem PC: /rebind",
            })
        else:
            error_text = profile_data.get("error")
            if not error_text:
                error_text = "Fehler"
            rows.append({
                "id": "profile",
                "label": "Hardware-Profil",
                "state": "bad",
                "detail": error_text,
            })

    return rows
