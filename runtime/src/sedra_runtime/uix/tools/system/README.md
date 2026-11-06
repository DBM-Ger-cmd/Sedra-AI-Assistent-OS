# Werkzeug `system` – System

Maschinenraum und Hardware: Zustand der Teile, Entwicklungsumgebung, GPU und Speicher.

Nur lesend; was ändert, ist ein Schalter und damit eine Entscheidung.

**Objekttypen:** machine, hardware
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/status`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: system.state, model.changed

## Abnahme
`python benchmarks/uix_check.py --tool system` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/system.png`
