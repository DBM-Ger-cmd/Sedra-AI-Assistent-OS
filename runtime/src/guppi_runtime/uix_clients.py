"""Client-Token für die externen Clients des Desk (Spec 0, D2, G2-S0-05).

Beim Start schreibt die Oberfläche je externem Client (`cli`, `mcp`) einen eigenen Zufallstoken mit Port und PID nach
`runtime_data/uix/clients/<client>.json` – atomar; der Token unter Windows mit der DPAPI (nur dieser Benutzer auf diesem PC liest
ihn, wie `cloud_keys.json`), sonst im Klartext in einer Datei mit Rechten 0600. Die Zuordnung Token → Client steht nur im Speicher des
Servers. Beim Beenden werden die Dateien gelöscht, beim nächsten Start neu geschrieben.

`client` ist eine Herkunftsangabe für Audit und Abnahme, keine Berechtigung (Vertrauensgrenze D2): alle Token-Halter sind dasselbe
Konto auf Loopback. Ein CLI- oder MCP-Token öffnet nur `POST /api/objects` und `POST /api/actions` – kein Weg am Desk vorbei."""
from __future__ import annotations

import base64
import http.client
import json
import os
import sys
from pathlib import Path

from .core.util import atomic_write_json

CLIENTS = ('cli', 'mcp')
ROUTES = ('/api/objects', '/api/actions')       # was ein externer Client aufrufen darf


def clients_dir(project_root) -> Path:
    return Path(project_root) / 'runtime_data' / 'uix' / 'clients'


def path_for(project_root, client) -> Path:
    if client not in CLIENTS:
        raise ValueError('unknown_client')
    return clients_dir(project_root) / f'{client}.json'


def _protect(token: str):
    if sys.platform == 'win32':
        from .cloud_settings import _dpapi
        return 'dpapi', base64.b64encode(_dpapi(token.encode('utf-8'), True)).decode('ascii')
    return 'datei-0600', token


def _unprotect(doc) -> str:
    if doc.get('protection') == 'dpapi':
        from .cloud_settings import _dpapi
        return _dpapi(base64.b64decode(doc['token']), False).decode('utf-8')
    return str(doc['token'])


def write(project_root, client, token, port, pid=None):
    """Die Datei eines Clients – atomar; unter POSIX legt `mkstemp` sie mit 0600 an, `chmod` hält das fest."""
    protection, value = _protect(token)
    path = path_for(project_root, client)
    atomic_write_json(path, {'client': client, 'port': int(port), 'pid': int(pid or os.getpid()),
                             'protection': protection, 'token': value})
    if sys.platform != 'win32':
        os.chmod(path, 0o600)
    return path


def remove(project_root, client):
    try:
        path_for(project_root, client).unlink()
    except FileNotFoundError:
        pass


def read(project_root, client):
    """{'port', 'pid', 'token'} aus der Datei; fehlt oder bricht sie, läuft keine Oberfläche: `uix_not_running`."""
    path = path_for(project_root, client)
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
        return {'port': int(doc['port']), 'pid': int(doc.get('pid') or 0), 'token': _unprotect(doc)}
    except Exception:
        raise ValueError('uix_not_running') from None


def status(project_root):
    """Harness Stufe 5 (G3 N3): je Client vorhanden, Port, PID und Zeit der Datei – nie der Token. Für `GET /api/uix/clients`."""
    out = {}
    for client in CLIENTS:
        path = path_for(project_root, client)
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
            out[client] = {'vorhanden': True, 'port': int(doc.get('port') or 0), 'pid': int(doc.get('pid') or 0),
                           'schutz': str(doc.get('protection') or ''), 'zeit': int(path.stat().st_mtime), 'datei': path.name}
        except Exception:
            out[client] = {'vorhanden': False, 'port': None, 'pid': None, 'schutz': None, 'zeit': None, 'datei': path.name}
    return out


def call(project_root, client, path, body, timeout=120):
    """`POST path` an die laufende Oberfläche mit dem Token dieses Clients. Rückgabe (status, antwort)."""
    if path not in ROUTES:
        raise ValueError('route_not_for_clients')
    info = read(project_root, client)
    conn = http.client.HTTPConnection('127.0.0.1', info['port'], timeout=timeout)
    try:
        conn.request('POST', path, body=json.dumps(body, ensure_ascii=False).encode('utf-8'),
                     headers={'Content-Type': 'application/json', 'X-GUPPI-Token': info['token']})
        res = conn.getresponse()
        raw = res.read().decode('utf-8')
    except (ConnectionError, OSError):
        raise ValueError('uix_not_running') from None
    finally:
        conn.close()
    try:
        return res.status, json.loads(raw) if raw else None
    except ValueError:
        return res.status, {'error': f'http_{res.status}'}        # z. B. 403 als HTML-Seite: der Text sagt nichts, die Zahl alles
