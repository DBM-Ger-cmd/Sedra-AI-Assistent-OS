# Werkzeug `task` – Aufgabe

Aufgaben als Satz, Fortschrittszeile und Ergebnis (Regel 6). Missions-IDs und Phasen bleiben im Logbuch.

Zeigt die Liste bei `id: alle`, sonst die eine Aufgabe.

**Objekttypen:** task, intent
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/missions`
- `POST /api/mission/run`
- `POST /api/mission/details`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: task.changed, decision.answered

## Abnahme
`python benchmarks/uix_check.py --tool task` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/task.png`
