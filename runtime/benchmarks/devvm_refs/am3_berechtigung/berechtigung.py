OEFFENTLICH = ('system.state', 'model.changed', 'desk.resync', 'tools.refresh', 'slot.changed')
ABLAGE_FREI = 1048576


def _liste(wert):
    if not isinstance(wert, (list, tuple, set)) or not all(isinstance(x, str) for x in wert):
        raise ValueError('faehigkeiten_ungueltig')
    return set(wert)


def _eintrag(eintrag):
    if not isinstance(eintrag, dict) or not isinstance(eintrag.get('gewaehrt'), list):
        raise ValueError('eintrag_ungueltig')
    return eintrag


def wirksam(beantragt, gewaehrt, obergrenze=None):
    erg = _liste(beantragt) & _liste(gewaehrt)
    if obergrenze is not None:
        erg &= _liste(obergrenze)
    return sorted(erg)


def ladeentscheidung(eintrag, beantragt, manifest_sha256):
    wanted = _liste(beantragt)
    if not isinstance(eintrag, dict):
        return {'laden': False, 'grund': 'keine_gewaehrung', 'wirksam': []}
    if eintrag.get('manifest_sha256') != manifest_sha256:
        return {'laden': False, 'grund': 'gewaehrung_veraltet', 'wirksam': []}
    if eintrag.get('aktiv') is not True:
        return {'laden': False, 'grund': 'app_inaktiv', 'wirksam': []}
    gewaehrt = eintrag.get('gewaehrt')
    gewaehrt = set(x for x in gewaehrt if isinstance(x, str)) if isinstance(gewaehrt, list) else set()
    fehlend = sorted(wanted - gewaehrt)
    if fehlend:
        return {'laden': False, 'grund': 'rechte_nicht_gewaehrt:' + ','.join(fehlend), 'wirksam': []}
    return {'laden': True, 'grund': None, 'wirksam': sorted(wanted)}


def werkseinstellung(beantragt, eigene_typen):
    eigene = set(eigene_typen) if isinstance(eigene_typen, (list, tuple, set)) else set()
    erg = set()
    for f in _liste(beantragt):
        art, _, rest = f.partition(':')
        if art == 'lesen' and rest in eigene:
            erg.add(f)
        elif art == 'ereignis' and rest in OEFFENTLICH:
            erg.add(f)
        elif art == 'ablage' and rest.isascii() and rest.isdigit() and 0 < int(rest) <= ABLAGE_FREI:
            erg.add(f)
    return sorted(erg)


def eintrag_neu(manifest_sha256, vertrauen, gewaehrt):
    return {'vertrauen': vertrauen, 'manifest_sha256': manifest_sha256, 'aktiv': False, 'gewaehrt': sorted(_liste(gewaehrt))}


def gewaehren(eintrag, faehigkeiten):
    alt = _eintrag(eintrag)
    neu = dict(alt)
    neu['gewaehrt'] = sorted(set(alt['gewaehrt']) | _liste(faehigkeiten))
    return neu


def entziehen(eintrag, faehigkeiten):
    alt = _eintrag(eintrag)
    neu = dict(alt)
    neu['gewaehrt'] = sorted(set(alt['gewaehrt']) - _liste(faehigkeiten))
    return neu


def aktivieren(eintrag, aktiv):
    alt = _eintrag(eintrag)
    if not isinstance(aktiv, bool):
        raise ValueError('aktiv_ungueltig')
    neu = dict(alt)
    neu['aktiv'] = aktiv
    return neu
