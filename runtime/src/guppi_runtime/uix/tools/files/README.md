# Werkzeug `files` – Projekt

Die Dateien des Projekts; eine Datei öffnet als eigener Reiter (Regel 4). In Build 7 nur lesend.

Schreiben wird in Build 8/9 eine Entscheidung.

**Objekttypen:** project, file
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/projects`
- `POST /api/project/files`
- `POST /api/project/file`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: task.changed

## Abnahme
`python benchmarks/uix_check.py --tool files` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/files.png`
