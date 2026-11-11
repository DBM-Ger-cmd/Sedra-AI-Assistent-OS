import re

_MODUL = re.compile(r'[a-z0-9-]{2,40}')
_PROFIL = re.compile(r'[a-z0-9][a-z0-9-]{1,39}')
_FELD = re.compile(r'[a-z][a-z0-9_]{1,30}')
_AKTION = re.compile(r'einstellungen:[a-z]+(/[a-z]+)?')
AKTIONEN = ('freigaben', 'modellmenue', 'routermenue')


def _liste(wert, grenze, muster):
    if not isinstance(wert, list) or not 1 <= len(wert) <= grenze:
        return False
    if not all(isinstance(x, str) and muster.fullmatch(x) for x in wert):
        return False
    return len(set(wert)) == len(wert)


def pruefe_shells(wert, bekannte=None):
    if wert is None:
        return [], []
    if not _liste(wert, 20, _MODUL):
        return ['shells_invalid'], []
    warnungen = []
    if bekannte is not None:
        bekannt = set(bekannte)
        warnungen = ['shells_unbekannt:' + s for s in wert if s not in bekannt]
    return [], warnungen


def pruefe_profile(wert, bekannte=None, grundfunktion=False):
    if wert is None:
        return [], []
    if not _liste(wert, 40, _PROFIL):
        return ['profile_invalid'], []
    warnungen = []
    if bekannte is not None:
        bekannt = set(bekannte) | {'standard'}
        warnungen = ['profil_unbekannt:' + p for p in wert if p not in bekannt]
    if grundfunktion:
        warnungen.append('grundfunktion_ignoriert_profil')
    return [], warnungen


def pruefe_zelle(wert, kind, orte):
    if wert is None:
        return []
    if kind != 'instrument':
        return ['zelle_nur_fuer_instrument']
    if not isinstance(wert, dict):
        return ['zelle_invalid']
    fehler = []
    feld = wert.get('feld')
    if not (isinstance(feld, str) and _FELD.fullmatch(feld)):
        fehler.append('zelle_feld_invalid')
    label = wert.get('label')
    if not (isinstance(label, str) and 1 <= len(label) <= 20):
        fehler.append('zelle_label_invalid')
    if 'ort' in wert and wert['ort'] not in set(orte):
        fehler.append('zelle_ort_unbekannt')
    if 'aktion' in wert:
        aktion = wert['aktion']
        if not (isinstance(aktion, str) and (aktion in AKTIONEN or _AKTION.fullmatch(aktion))):
            fehler.append('zelle_aktion_invalid')
    if 'quelle' in wert:
        quelle = wert['quelle']
        if not (isinstance(quelle, str) and _FELD.fullmatch(quelle)):
            fehler.append('zelle_quelle_invalid')
    for schluessel in sorted(k for k in wert if k not in ('feld', 'label', 'ort', 'aktion', 'quelle')):
        fehler.append('zelle_unbekannt:' + str(schluessel))
    return fehler


def filtere(tools, shell, profil, grundfunktionen):
    sichtbar, nicht_shell, nicht_profil = [], [], []
    grund = set(grundfunktionen or ())
    aktiv = profil or 'standard'
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        if t.get('id') in grund:
            sichtbar.append(t)
            continue
        shells = t.get('shells')
        if shells is not None and shell not in shells:
            nicht_shell.append({'id': t.get('id'), 'name': t.get('name'), 'shells': shells})
            continue
        profile = t.get('profile')
        if profile is not None and aktiv not in profile:
            nicht_profil.append({'id': t.get('id'), 'name': t.get('name'), 'profile': profile})
            continue
        sichtbar.append(t)
    return sichtbar, nicht_shell, nicht_profil
