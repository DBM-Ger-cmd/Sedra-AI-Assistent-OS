"""Gewährung, Aktivierung und Ladeentscheidung einer fremden App (AM3-05, AM3-06, AM3-08, AM3-09, AM3-28, SPEC_APPS_v1_AM3_BERECHTIGUNG): der reine Kern auf dicts,
noch ohne Anbindung (Berechtigungsdatei local_config/apps/berechtigung.yaml und Gateway kommen mit AM3).

Gebaut als Kandidat von SEDRAs Factory-Bau (`am3_berechtigung`, 11.11.2026), unverändert übernommen."""
def _check_faehigkeiten(obj):
    if not isinstance(obj, (list, tuple, set)):
        raise ValueError("faehigkeiten_ungueltig")
    for item in obj:
        if not isinstance(item, str):
            raise ValueError("faehigkeiten_ungueltig")


def wirksam(beantragt, gewaehrt, obergrenze=None):
    _check_faehigkeiten(beantragt)
    _check_faehigkeiten(gewaehrt)
    if obergrenze is not None:
        _check_faehigkeiten(obergrenze)
    s_beantragt = set(beantragt)
    s_gewaehrt = set(gewaehrt)
    result = s_beantragt & s_gewaehrt
    if obergrenze is not None:
        result = result & set(obergrenze)
    return sorted(result)


def ladeentscheidung(eintrag, beantragt, manifest_sha256):
    _check_faehigkeiten(beantragt)
    if not isinstance(eintrag, dict):
        return {"laden": False, "grund": "keine_gewaehrung", "wirksam": []}
    if eintrag.get("manifest_sha256") != manifest_sha256:
        return {"laden": False, "grund": "gewaehrung_veraltet", "wirksam": []}
    if eintrag.get("aktiv") is not True:
        return {"laden": False, "grund": "app_inaktiv", "wirksam": []}
    gewaehrt_list = eintrag.get("gewaehrt")
    if not isinstance(gewaehrt_list, list):
        gewaehrt_set = set()
    else:
        gewaehrt_set = {item for item in gewaehrt_list if isinstance(item, str)}
    beantragt_set = set(beantragt)
    missing = beantragt_set - gewaehrt_set
    if missing:
        grund = "rechte_nicht_gewaehrt:" + ",".join(sorted(missing))
        return {"laden": False, "grund": grund, "wirksam": []}
    return {"laden": True, "grund": None, "wirksam": sorted(set(beantragt))}

def werkseinstellung(beantragt, eigene_typen):
    _check_faehigkeiten(beantragt)
    if isinstance(eigene_typen, (list, tuple, set)):
        typen = set(eigene_typen)
    else:
        typen = set()
    erlaubte_ereignisse = {"system.state", "model.changed", "desk.resync", "tools.refresh", "slot.changed"}
    ergebnis = set()
    for f in beantragt:
        if f.startswith("lesen:"):
            typ = f[6:]
            if typ in typen:
                ergebnis.add(f)
        elif f.startswith("ereignis:"):
            name = f[9:]
            if name in erlaubte_ereignisse:
                ergebnis.add(f)
        elif f.startswith("ablage:"):
            n_str = f[7:]
            if n_str and all(c in "0123456789" for c in n_str):
                n = int(n_str)
                if 0 < n <= 1048576:
                    ergebnis.add(f)
    return sorted(ergebnis)

def eintrag_neu(manifest_sha256, vertrauen, gewaehrt):
    _check_faehigkeiten(gewaehrt)
    return {"vertrauen": vertrauen, "manifest_sha256": manifest_sha256, "aktiv": False, "gewaehrt": sorted(set(gewaehrt))}

def gewaehren(eintrag, faehigkeiten):
    if not isinstance(eintrag, dict) or not isinstance(eintrag.get("gewaehrt"), list):
        raise ValueError("eintrag_ungueltig")
    _check_faehigkeiten(faehigkeiten)
    old = eintrag["gewaehrt"]
    combined = sorted(set(old) | set(faehigkeiten))
    result = dict(eintrag)
    result["gewaehrt"] = combined
    return result

def entziehen(eintrag, faehigkeiten):
    if not isinstance(eintrag, dict) or not isinstance(eintrag.get("gewaehrt"), list):
        raise ValueError("eintrag_ungueltig")
    _check_faehigkeiten(faehigkeiten)
    old = eintrag["gewaehrt"]
    removed = set(faehigkeiten)
    combined = sorted(set(old) - removed)
    result = dict(eintrag)
    result["gewaehrt"] = combined
    return result

def aktivieren(eintrag, aktiv):
    if not isinstance(eintrag, dict) or not isinstance(eintrag.get("gewaehrt"), list):
        raise ValueError("eintrag_ungueltig")
    if aktiv is not True and aktiv is not False:
        raise ValueError("aktiv_ungueltig")
    result = dict(eintrag)
    result["aktiv"] = aktiv
    return result
