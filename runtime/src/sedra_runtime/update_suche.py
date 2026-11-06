"""Die Update-Suche (Plan docs/PLAN_ISOLATION_UND_UPDATE_2026-10-19.md, Abschnitt 4): nur lesen, nur auf Klick.

Fragt die Versions-Tags des öffentlichen Repositorys ab und vergleicht sie mit der installierten Version. Es wird nichts geladen,
nichts geschrieben und nichts ausgeführt. Ist eine neuere Version da, zeigt die Oberfläche das an; übernommen wird erst nach einer
Bestätigung (Teil 2 des Updates)."""
from __future__ import annotations

import json
import re
import urllib.request

from .version import REPO, VERSION

TAG = re.compile(r'^v(\d+)\.(\d+)\.(\d+)$')
ZEITLIMIT_S = 10


def versionen(tags: list) -> list:
    """Die Release-Versionen aus einer Tag-Liste, aufsteigend, als (Tupel, Name). Andere Tags werden ignoriert."""
    out = []
    for t in tags:
        name = t.get('name', '') if isinstance(t, dict) else str(t)
        m = TAG.match(name)
        if m: out.append((tuple(int(x) for x in m.groups()), name))
    return sorted(out)


def _tags_holen():
    req = urllib.request.Request('https://api.github.com/repos/%s/tags?per_page=100' % REPO,
                                 headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'SEDRA-Update-Suche'})
    with urllib.request.urlopen(req, timeout=ZEITLIMIT_S) as resp:
        return json.loads(resp.read().decode('utf-8'))


def suche(installiert: str = VERSION, tags_holen=_tags_holen) -> dict:
    """{'installiert', 'neueste', 'verfuegbar', 'status'} – status: aktuell | neu | nicht_erreichbar | keine_releases."""
    try:
        liste = versionen(tags_holen())
    except Exception:
        return {'installiert': installiert, 'neueste': None, 'verfuegbar': False, 'status': 'nicht_erreichbar'}
    if not liste:
        return {'installiert': installiert, 'neueste': None, 'verfuegbar': False, 'status': 'keine_releases'}
    neueste = liste[-1][1]
    ist = tuple(int(x) for x in installiert.split('.'))
    neu = liste[-1][0] > ist
    return {'installiert': installiert, 'neueste': neueste, 'verfuegbar': neu, 'status': 'neu' if neu else 'aktuell'}
