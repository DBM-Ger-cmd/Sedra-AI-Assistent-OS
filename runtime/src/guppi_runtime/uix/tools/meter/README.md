# Werkzeug `meter` – Guppy-Meter

Was die Arbeit kostet: Token je Zeitraum, Zeilen und das Münzloch.

Nur lesend; die Kostengrenze kommt mit Build 9.

**Objekttypen:** meter
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/meter`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: task.changed

## Abnahme
`python benchmarks/uix_check.py --tool meter` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/meter.png`
