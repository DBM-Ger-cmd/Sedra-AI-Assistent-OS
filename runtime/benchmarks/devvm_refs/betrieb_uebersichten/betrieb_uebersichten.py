from urllib.parse import urlsplit

UNBEKANNT = "unbekannt"


def _name(wert, vorgabe):
    if isinstance(wert, str) and wert.strip():
        return wert.strip()
    return vorgabe


def schutzklassen_uebersicht(vorgaenge):
    erg = {"summe": 0, "uebersprungen": 0, "nach_klasse": {}, "nach_zustand": {}, "ohne_verantwortlichen": []}
    if not isinstance(vorgaenge, list):
        return erg
    for v in vorgaenge:
        if not isinstance(v, dict) or "fehler" in v:
            erg["uebersprungen"] += 1
            continue
        erg["summe"] += 1
        k = _name(v.get("klasse"), UNBEKANNT)
        z = _name(v.get("zustand"), UNBEKANNT)
        erg["nach_klasse"][k] = erg["nach_klasse"].get(k, 0) + 1
        erg["nach_zustand"][z] = erg["nach_zustand"].get(z, 0) + 1
        if _name(v.get("verantwortlich"), "") == "":
            erg["ohne_verantwortlichen"].append(_name(v.get("id"), "?"))
    return erg


def adresse_kuerzen(url):
    if not isinstance(url, str):
        return ""
    try:
        t = urlsplit(url.strip())
        host, port = t.hostname, t.port
    except ValueError:
        return ""
    if t.scheme.lower() not in ("http", "https") or not host:
        return ""
    if ":" in host:
        host = "[" + host + "]"
    return t.scheme.lower() + "://" + host + (":" + str(port) if port else "")


def ki_verzeichnis(anbieter):
    if not isinstance(anbieter, list):
        return []
    zeilen, gesehen = [], set()
    for a in anbieter:
        if not isinstance(a, dict):
            continue
        n = _name(a.get("anbieter"), "")
        if not n or n in gesehen:
            continue
        gesehen.add(n)
        zeilen.append({"anbieter": n, "status": "an" if a.get("an") is True else "aus", "adresse": adresse_kuerzen(a.get("adresse"))})
    return sorted(zeilen, key=lambda z: (z["anbieter"].lower(), z["anbieter"]))


def ki_text(zeilen):
    gut = [z for z in zeilen if isinstance(z, dict) and isinstance(z.get("anbieter"), str) and z["anbieter"]] if isinstance(zeilen, list) else []
    if not gut:
        return "Keine Cloud-KI eingetragen. Nur lokale Modelle."
    aus = ["Eingesetzte Cloud-KI:"]
    for z in gut:
        t = "- %s: %s" % (z["anbieter"], "an" if z.get("status") == "an" else "aus")
        if isinstance(z.get("adresse"), str) and z["adresse"]:
            t += ", " + z["adresse"]
        aus.append(t)
    return "\n".join(aus)
