# Werkzeug `crew` – Besatzung

Wer an Bord ist: der Captain, SEDRA, die Rollen aus den Rezepten und die Agenten, die wirklich existieren.

Demo-Zeilen und echte Zeilen werden nie vermischt.

**Objekttypen:** agent
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/agents`
- `GET /api/models`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: task.changed

## Abnahme
`python benchmarks/uix_check.py --tool crew` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/crew.png`
