"""Lese-Sicht auf die Factory-Daten für die App Factory Studio (F3-01, SPEC_F3_01_FACTORY_STUDIO_APP Abschnitt 2.2 bis 2.4).

Nur lesen, nichts anlegen, nichts ändern:
- die Registry der Factory-Typen (`local_config/factory_registry.json`, geschrieben vom Control Core / von der CLI),
- der Evidence Store (`local_config/evidence/evidence.db`, SQLite; hier schreibgeschützt geöffnet).
Hinweis: Im WAL-Modus von SQLite aktualisiert auch ein schreibgeschütztes Öffnen den Index (`-shm`); Daten ändert es nie (die Verbindung ist `mode=ro`).
Fehlt eine Quelle, sagt die Antwort es ehrlich (`quelle: fehlt`) und erzeugt keine Datei. Es gibt keine Route, die startet, genehmigt oder löscht (F301-Grenzen).
Rein im Sinn von „keine eigene Ablage“: alle Funktionen bekommen den Projekt-Wurzelordner."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .factory_registry import FactoryRegistry

REGISTRY_DATEI = ('local_config', 'factory_registry.json')
EVIDENCE_DATEI = ('local_config', 'evidence', 'evidence.db')
LIMIT_STANDARD, LIMIT_MAX = 50, 200


def _pfad(root, teile):
    return Path(root).joinpath(*teile)


def _evidence(root):
    """Schreibgeschützte Verbindung zum Evidence Store oder None, wenn es keinen gibt."""
    p = _pfad(root, EVIDENCE_DATEI)
    if not p.is_file():
        return None
    conn = sqlite3.connect(p.resolve().as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _json(text):
    try:
        return json.loads(text) if text else None
    except (TypeError, ValueError):
        return None


def _grenze(limit):
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return LIMIT_STANDARD
    return max(1, min(n, LIMIT_MAX))


def typen(root) -> dict[str, Any]:
    """Die registrierten Factory-Typen (Katalog der Fachfabriken, F301-05) mit Zustand und Gate-Freigabe."""
    p = _pfad(root, REGISTRY_DATEI)
    if not p.is_file():
        return {'quelle': 'fehlt', 'typen': [], 'anzahl': 0, 'grund': 'keine Registry-Datei (local_config/factory_registry.json)'}
    try:
        liste = FactoryRegistry.load(p).liste_typen()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {'quelle': 'fehler', 'typen': [], 'anzahl': 0, 'grund': f'Registry nicht lesbar: {type(exc).__name__}'}
    return {'quelle': 'ok', 'typen': liste, 'anzahl': len(liste)}


def runs(root, limit=LIMIT_STANDARD, typ=None) -> dict[str, Any]:
    """Die letzten Läufe (Builds) aus dem Evidence Store, neueste zuerst (Execution View, F301-10/12)."""
    conn = _evidence(root)
    if conn is None:
        return {'quelle': 'fehlt', 'runs': [], 'anzahl': 0, 'grund': 'kein Evidence Store (local_config/evidence/evidence.db)'}
    try:
        sql = ('SELECT run_id, typ_id, name, build_type, started_at, finished_at, duration_ms, success, artifacts_count, error_message, metrics_json '
               'FROM runs ' + ('WHERE typ_id = ? ' if typ else '') + 'ORDER BY started_at DESC LIMIT ?')
        rows = conn.execute(sql, ((typ, _grenze(limit)) if typ else (_grenze(limit),))).fetchall()
    except sqlite3.DatabaseError as exc:
        return {'quelle': 'fehler', 'runs': [], 'anzahl': 0, 'grund': f'Evidence Store nicht lesbar: {type(exc).__name__}'}
    finally:
        conn.close()
    out = [{'run_id': r['run_id'], 'typ_id': r['typ_id'], 'name': r['name'], 'build_type': r['build_type'], 'gestartet': r['started_at'],
            'beendet': r['finished_at'], 'dauer_ms': r['duration_ms'], 'erfolg': bool(r['success']), 'artefakte': r['artifacts_count'],
            'fehler': r['error_message'], 'metriken': _json(r['metrics_json'])} for r in rows]
    return {'quelle': 'ok', 'runs': out, 'anzahl': len(out)}


def benchmarks(root, typ=None) -> dict[str, Any]:
    """Die gespeicherten Benchmark-Vergleiche, neueste zuerst."""
    conn = _evidence(root)
    if conn is None:
        return {'quelle': 'fehlt', 'benchmarks': [], 'anzahl': 0, 'grund': 'kein Evidence Store (local_config/evidence/evidence.db)'}
    try:
        sql = ('SELECT benchmark_id, typ_id, variant, params_json, score, runs_count, aggregated_metrics_json, created_at FROM benchmarks '
               + ('WHERE typ_id = ? ' if typ else '') + 'ORDER BY created_at DESC LIMIT 100')
        rows = conn.execute(sql, ((typ,) if typ else ())).fetchall()
    except sqlite3.DatabaseError as exc:
        return {'quelle': 'fehler', 'benchmarks': [], 'anzahl': 0, 'grund': f'Evidence Store nicht lesbar: {type(exc).__name__}'}
    finally:
        conn.close()
    out = [{'benchmark_id': r['benchmark_id'], 'typ_id': r['typ_id'], 'variante': r['variant'], 'parameter': _json(r['params_json']), 'punkte': r['score'],
            'laeufe': r['runs_count'], 'metriken': _json(r['aggregated_metrics_json']), 'angelegt': r['created_at']} for r in rows]
    return {'quelle': 'ok', 'benchmarks': out, 'anzahl': len(out)}


def health(root) -> dict[str, Any]:
    """Factory Health (F301-13): Registry und Evidence Store erreichbar? Zahlen je Quelle. Offene Gates zählt die Seite selbst (Freigaben)."""
    t = typen(root)
    reg = {'erreichbar': t['quelle'] == 'ok', 'typen': t['anzahl']}
    if reg['erreichbar']:
        reg['zustaende'] = {}
        for x in t['typen']:
            reg['zustaende'][x['zustand']] = reg['zustaende'].get(x['zustand'], 0) + 1
        reg['gate_freigegeben'] = sum(1 for x in t['typen'] if x.get('gate_freigabe'))
    else:
        reg['grund'] = t.get('grund')
    ev = {'erreichbar': False}
    conn = _evidence(root)
    if conn is not None:
        try:
            ev = {'erreichbar': True, **{k: conn.execute(f'SELECT COUNT(*) AS c FROM {k}').fetchone()['c'] for k in ('runs', 'benchmarks', 'gate_evidence', 'meta_insights')}}
            letzter = conn.execute('SELECT started_at FROM runs ORDER BY started_at DESC LIMIT 1').fetchone()
            ev['letzter_lauf'] = letzter['started_at'] if letzter else None
        except sqlite3.DatabaseError as exc:
            ev = {'erreichbar': False, 'grund': f'nicht lesbar: {type(exc).__name__}'}
        finally:
            conn.close()
    else:
        ev['grund'] = 'kein Evidence Store'
    return {'registry': reg, 'evidence': ev, 'ok': reg['erreichbar'] and ev['erreichbar']}
