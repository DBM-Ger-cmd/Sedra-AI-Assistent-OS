import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ORDNER = 'uix_herkunft'
_ID = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')


_LEER = object()


def _pruefe(area, mid=_LEER):
    if area not in ('tools', 'shells'):
        raise ValueError('area')
    if mid is not _LEER and (not isinstance(mid, str) or not _ID.match(mid)):
        raise ValueError('id')


def pfad(project_root, area, mid):
    _pruefe(area, mid)
    return Path(project_root) / 'local_config' / ORDNER / area / (mid + '.json')


def _dateien(folder):
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError('ordner')
    for wurzel, ordner, dateien in os.walk(folder):
        ordner.sort()
        for name in sorted(dateien):
            voll = Path(wurzel) / name
            rel = voll.relative_to(folder).as_posix()
            if any(teil.startswith('.') for teil in rel.split('/')):
                raise ValueError('punkt_pfad')
            yield rel, voll
        for name in ordner:
            if name.startswith('.'):
                raise ValueError('punkt_pfad')


def erfassen(folder, area):
    _pruefe(area)
    erg = {}
    for rel, voll in _dateien(folder):
        erg[rel] = hashlib.sha256(voll.read_bytes()).hexdigest()
    return dict(sorted(erg.items()))


def schreiben(project_root, area, mid, folder, *, quelle, mission_id, vertrauen):
    ziel = pfad(project_root, area, mid)
    daten = {
        'schema': 1, 'art': area, 'id': mid, 'vertrauen_beim_einbau': vertrauen, 'quelle': str(quelle), 'commit': None,
        'mission_id': mission_id, 'eingebaut_am': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'dateien': erfassen(folder, area),
    }
    ziel.parent.mkdir(parents=True, exist_ok=True)
    temp = ziel.with_name(ziel.name + '.tmp')
    temp.write_text(json.dumps(daten, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(temp, ziel)
    return daten


def lesen(project_root, area, mid):
    ziel = pfad(project_root, area, mid)
    if not ziel.exists():
        return None
    try:
        daten = json.loads(ziel.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise ValueError('herkunft_unlesbar')
    if not isinstance(daten, dict) or daten.get('schema') != 1:
        raise ValueError('herkunft_unlesbar')
    return daten


def entfernen(project_root, area, mid):
    ziel = pfad(project_root, area, mid)
    if ziel.exists():
        ziel.unlink()


def pruefen(folder, area, eintrag):
    if not isinstance(eintrag, dict) or not isinstance(eintrag.get('dateien'), dict):
        return ['herkunft_unlesbar']
    soll = eintrag['dateien']
    if Path(folder).is_dir():
        try:
            ist = erfassen(folder, area)
        except ValueError:
            return ['herkunft_pfad_ungueltig']
    else:
        ist = {}
    erg = []
    for rel in sorted(set(soll) | set(ist)):
        if rel not in ist:
            erg.append('herkunft_datei_fehlt:' + rel)
        elif rel not in soll:
            erg.append('herkunft_datei_neu:' + rel)
        elif ist[rel] != soll[rel]:
            erg.append('herkunft_abweichung:' + rel)
    return erg


def _stand(folder):
    erg = []
    for rel, voll in _dateien(folder):
        st = voll.stat()
        erg.append((rel, st.st_size, st.st_mtime_ns))
    return tuple(erg)


class HerkunftsPruefer:
    def __init__(self):
        self.hash_laeufe = 0
        self._cache = {}

    def pruefen(self, folder, area, eintrag):
        schluessel = str(Path(folder).resolve())
        try:
            stand = _stand(folder) if Path(folder).is_dir() else None
            eintrag_text = json.dumps(eintrag, sort_keys=True, default=str)
        except (ValueError, TypeError):
            stand = None
            eintrag_text = None
        if stand is not None and eintrag_text is not None:
            alt = self._cache.get(schluessel)
            if alt is not None and alt[0] == stand and alt[1] == eintrag_text:
                return list(alt[2])
        self.hash_laeufe += 1
        erg = pruefen(folder, area, eintrag)
        if stand is not None and eintrag_text is not None:
            self._cache[schluessel] = (stand, eintrag_text, list(erg))
        return erg
