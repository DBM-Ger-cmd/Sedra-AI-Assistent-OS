import hashlib

OEFFENTLICH = ('system.state', 'model.changed', 'desk.resync', 'tools.refresh', 'slot.changed')
ABLAGE_FREI = 1048576
_SCHLUESSEL = ('lesen', 'verben', 'ereignisse', 'zelle', 'ablage', 'dienst')
_PRAEFIX = {'lesen': 'lesen:', 'verben': 'verb:', 'ereignisse': 'ereignis:'}


def rechte_zu_faehigkeiten(rechte):
    if rechte is None:
        return []
    if not isinstance(rechte, dict):
        raise ValueError('rechte_ungueltig')
    for key in sorted(rechte, key=str):
        if key not in _SCHLUESSEL:
            raise ValueError('rechte_unbekannt:' + str(key))
    erg = set()
    for key, praefix in _PRAEFIX.items():
        if key in rechte:
            wert = rechte[key]
            if not isinstance(wert, list) or not all(isinstance(x, str) and x for x in wert):
                raise ValueError('rechte_ungueltig:' + key)
            for x in wert:
                erg.add(praefix + x)
    if 'zelle' in rechte:
        if rechte['zelle'] not in ('nein', 'text'):
            raise ValueError('rechte_ungueltig:zelle')
        if rechte['zelle'] == 'text':
            erg.add('zelle:text')
    if 'ablage' in rechte:
        n = rechte['ablage']
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError('rechte_ungueltig:ablage')
        if n > 0:
            erg.add('ablage:' + str(n))
    if 'dienst' in rechte:
        if rechte['dienst'] not in ('nein', 'host', 'microvm'):
            raise ValueError('rechte_ungueltig:dienst')
        if rechte['dienst'] != 'nein':
            erg.add('dienst:' + rechte['dienst'])
    return sorted(erg)


def stufe(faehigkeit):
    if not isinstance(faehigkeit, str) or ':' not in faehigkeit:
        return 'C'
    art, _, rest = faehigkeit.partition(':')
    if not rest:
        return 'C'
    if art == 'lesen':
        return 'A'
    if art == 'verb':
        return 'B'
    if art == 'ereignis':
        return 'A' if rest in OEFFENTLICH else 'B'
    if art == 'zelle':
        return 'B' if rest == 'text' else 'C'
    if art == 'ablage':
        if not (rest.isascii() and rest.isdigit()):
            return 'C'
        return 'A' if int(rest) <= ABLAGE_FREI else 'B'
    if art == 'dienst':
        return 'B' if rest == 'microvm' else 'C'
    return 'C'


def rechte_diff(alt, neu):
    a = set(rechte_zu_faehigkeiten(alt))
    n = set(rechte_zu_faehigkeiten(neu))
    erg = [{'faehigkeit': f, 'richtung': 'neu', 'stufe': stufe(f)} for f in sorted(n - a)]
    erg += [{'faehigkeit': f, 'richtung': 'entfallen', 'stufe': stufe(f)} for f in sorted(a - n)]
    return erg


def rechte_urteil(diff):
    liste = diff if isinstance(diff, list) else []
    neu = [d for d in liste if isinstance(d, dict) and d.get('richtung') == 'neu']
    return {
        'braucht_gate': any(d.get('stufe') == 'B' for d in neu),
        'abgewiesen': [d.get('faehigkeit') for d in neu if d.get('stufe') == 'C'],
    }


def rechte_schluessel(faehigkeiten):
    if not isinstance(faehigkeiten, list) or not all(isinstance(f, str) for f in faehigkeiten):
        raise ValueError('faehigkeiten_ungueltig')
    return hashlib.sha256('\n'.join(sorted(set(faehigkeiten))).encode('utf-8')).hexdigest()
