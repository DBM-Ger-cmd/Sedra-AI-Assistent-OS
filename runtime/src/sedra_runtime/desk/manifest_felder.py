"""Die Manifest-Felder `shells`, `profile` und `zelle` (AM1, Vertrag 1.1, SPEC_APPS_v1_AM1_G2 §1 und G3 §4): Prüfung und Filter nach Shell und Profil.

Gebaut als Kandidat von SEDRAs Factory-Bau (`am1_manifest_felder`, 10.11.2026), von Hand nachgearbeitet: `pruefe_zelle` vergleicht `ort` mit
einer Liste (ein unhashbarer YAML-Wert warf sonst gegen eine Menge). Sichtbarkeit, kein Recht: `Gateway.allowed` ändert sich nicht."""
import re


def pruefe_shells(wert, bekannte=None):
    if wert is None:
        return ([], [])

    if not isinstance(wert, list):
        return (["shells_invalid"], [])

    if len(wert) < 1 or len(wert) > 20:
        return (["shells_invalid"], [])

    pattern = re.compile(r'^[a-z0-9-]{2,40}$')
    seen = set()

    for entry in wert:
        if not isinstance(entry, str):
            return (["shells_invalid"], [])
        if not pattern.fullmatch(entry):
            return (["shells_invalid"], [])
        if entry in seen:
            return (["shells_invalid"], [])
        seen.add(entry)

    if bekannte is not None:
        if isinstance(bekannte, list):
            bekannte_set = set(bekannte)
        else:
            bekannte_set = bekannte
        warnungen = []
        for entry in wert:
            if entry not in bekannte_set:
                warnungen.append(f"shells_unbekannt:{entry}")
        return ([], warnungen)

    return ([], [])


def pruefe_profile(wert, bekannte=None, grundfunktion=False):
    if wert is None:
        return ([], [])

    if not isinstance(wert, list):
        return (["profile_invalid"], [])

    if len(wert) < 1 or len(wert) > 40:
        return (["profile_invalid"], [])

    pattern = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
    seen = set()

    for entry in wert:
        if not isinstance(entry, str):
            return (["profile_invalid"], [])
        if not pattern.fullmatch(entry):
            return (["profile_invalid"], [])
        if entry in seen:
            return (["profile_invalid"], [])
        seen.add(entry)

    warnungen = []
    if bekannte is not None:
        if isinstance(bekannte, list):
            bekannte_set = set(bekannte)
        else:
            bekannte_set = bekannte
        for entry in wert:
            if entry != "standard" and entry not in bekannte_set:
                warnungen.append(f"profil_unbekannt:{entry}")

    if grundfunktion:
        warnungen.append("grundfunktion_ignoriert_profil")

    return ([], warnungen)


def pruefe_zelle(wert, kind, orte):
    if wert is None:
        return []

    if kind != "instrument":
        return ["zelle_nur_fuer_instrument"]

    if not isinstance(wert, dict):
        return ["zelle_invalid"]

    meldungen = []

    if "feld" not in wert or not isinstance(wert["feld"], str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,30}', wert["feld"]):
        meldungen.append("zelle_feld_invalid")

    if "label" not in wert or not isinstance(wert["label"], str) or len(wert["label"]) < 1 or len(wert["label"]) > 20:
        meldungen.append("zelle_label_invalid")

    if "ort" in wert:
        if wert["ort"] not in list(orte):                      # list(): ein unhashbarer Wert (YAML-Liste) wirft sonst gegen eine Menge
            meldungen.append("zelle_ort_unbekannt")

    if "aktion" in wert:
        aktion = wert["aktion"]
        if not isinstance(aktion, str):
            meldungen.append("zelle_aktion_invalid")
        elif aktion not in ("freigaben", "modellmenue", "routermenue") and not re.fullmatch(r'einstellungen:[a-z]+(/[a-z]+)?', aktion):
            meldungen.append("zelle_aktion_invalid")

    if "quelle" in wert:
        if not isinstance(wert["quelle"], str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,30}', wert["quelle"]):
            meldungen.append("zelle_quelle_invalid")

    bekannte_schluessel = {"feld", "label", "ort", "aktion", "quelle"}
    for schluessel in sorted(wert.keys()):
        if schluessel not in bekannte_schluessel:
            meldungen.append(f"zelle_unbekannt:{schluessel}")

    return meldungen

def filtere(tools, shell, profil, grundfunktionen):
    sichtbar = []
    nicht_in_shell = []
    nicht_in_profil = []
    gf = set(grundfunktionen) if grundfunktionen is not None else set()
    aktives_profil = profil if profil is not None else "standard"
    if tools is None:
        return (sichtbar, nicht_in_shell, nicht_in_profil)
    for entry in tools:
        if not isinstance(entry, dict):
            continue
        eid = entry.get("id")
        ename = entry.get("name")
        if eid in gf:
            sichtbar.append(entry)
            continue
        shells = entry.get("shells")
        if shells is not None and shell not in shells:
            nicht_in_shell.append({"id": eid, "name": ename, "shells": shells})
            continue
        profiles = entry.get("profile")
        if profiles is not None and aktives_profil not in profiles:
            nicht_in_profil.append({"id": eid, "name": ename, "profile": profiles})
            continue
        sichtbar.append(entry)
    return (sichtbar, nicht_in_shell, nicht_in_profil)