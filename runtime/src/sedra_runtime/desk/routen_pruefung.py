"""Routenregeln für Module aus `local_config` (AM0-03, SPEC_APPS_v1_AM0_G2 §3): zu breite Platzhalter und die Sperrliste der Leserouten für fremde Module.

Gebaut als Kandidat von SEDRAs Factory-Bau (`am0_routen`, 10.11.2026), von Hand nachgeschärft: `route_zu_breit` vergleicht den ganzen Pfad
(der Kandidat prüfte nur das Ende und hätte `GET /api/x/api/*` zu Unrecht abgewiesen)."""
from __future__ import annotations

SENSIBEL_COMMUNITY = (
    '/api/chat/', '/api/harness/', '/api/arbeitsstand', '/api/audit', '/api/missions', '/api/decisions', '/api/uix/',
    '/api/cloud', '/api/switches', '/api/processes', '/api/gateway/', '/api/fisch/', '/api/sprache/', '/api/projects',
    '/api/diagnose', '/api/context', '/api/permissions', '/api/supervisor',
)


def _pfad(route):
    if not isinstance(route, str) or ' ' not in route:
        return None
    return route.split(' ', 1)[1]


def route_zu_breit(route):
    return _pfad(route) in ('/api/*', '/uix/*')


def route_sensibel(route):
    pfad = _pfad(route)
    if pfad is None:
        return False
    if pfad.endswith('/*'):
        pfad = pfad[:-1]
    return any(pfad.startswith(e) or e.startswith(pfad) for e in SENSIBEL_COMMUNITY)


def pruefe_routen(routes, origin, trust):
    fehler = []
    if origin != 'local' or not isinstance(routes, list):
        return fehler
    for route in routes:
        if not isinstance(route, str):
            continue
        if route_zu_breit(route):
            fehler.append('api_route_too_broad:' + route)
        if trust == 'COMMUNITY' and route_sensibel(route):
            fehler.append('api_route_sensitive:' + route)
    return fehler
