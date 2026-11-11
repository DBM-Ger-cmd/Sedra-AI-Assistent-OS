def _gesetzt(wert):
    return wert not in (None, '', False, {}, [])


def pruefe_shell(doc, trust, dateien):
    if trust != 'COMMUNITY':
        return []
    if not isinstance(doc, dict):
        return ['community_shell_needs_vorgabe']
    fehler = []
    if not _gesetzt(doc.get('vorgabe')):
        fehler.append('community_shell_needs_vorgabe')
    if _gesetzt(doc.get('entry')):
        fehler.append('community_shell_no_entry')
    if isinstance(dateien, (list, tuple, set)) and 'shell.css' in dateien:
        fehler.append('community_shell_no_css')
    return fehler


def pruefe_einbau(kind, doc):
    if kind != 'shell':
        return []
    if isinstance(doc, dict) and _gesetzt(doc.get('vorgabe')):
        return []
    return ['shell_einbau_nur_vorgabe']


def darf_code_laden(trust, frame):
    if trust == 'COMMUNITY':
        return False
    return True
