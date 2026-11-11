"""Regeln für fremde Shells (AM0-06, SPEC_APPS_v1_AM0_G2 §6): eine COMMUNITY-Shell ist nur eine Vorgabe – kein eigener Code, kein eigenes CSS.

Gebaut als Kandidat von SEDRAs Factory-Bau (`am0_shell_regeln`, 10.11.2026). Nachgearbeitet am 11.11.: der Name `shell.css` gilt ohne Rücksicht auf Groß- und Kleinschreibung
(unter Windows ist `SHELL.CSS` dieselbe Datei und kam sonst am Verbot vorbei); die Spec hatte das Gegenteil festgeschrieben."""
def pruefe_shell(doc, trust, dateien):
    if trust != "COMMUNITY":
        return []
    if not isinstance(doc, dict):
        return ["community_shell_needs_vorgabe"]
    meldungen = []
    vorgabe = doc.get("vorgabe")
    if vorgabe is None or vorgabe == "" or vorgabe is False or vorgabe == {} or vorgabe == []:
        meldungen.append("community_shell_needs_vorgabe")
    entry = doc.get("entry")
    if entry is not None and entry != "" and entry is not False and entry != {} and entry != []:
        meldungen.append("community_shell_no_entry")
    if isinstance(dateien, (list, tuple, set)):
        if any(isinstance(d, str) and d.casefold() == "shell.css" for d in dateien):      # Windows: `SHELL.CSS` ist dieselbe Datei, `_check_frame_shell` lädt sie als shell.css
            meldungen.append("community_shell_no_css")
    return meldungen


def pruefe_einbau(kind, doc):
    if kind != "shell":
        return []
    if isinstance(doc, dict) and doc.get("vorgabe") not in (None, "", False, {}, []):
        return []
    return ["shell_einbau_nur_vorgabe"]


def darf_code_laden(trust, frame):
    if trust == "COMMUNITY":
        return False
    return True
