# Werkzeug `gauge-gpu` – GPU

Eine Zelle der Instrumentenleiste. Sie formatiert einen Messwert aus `/api/strip` und sonst nichts – die Leiste holt, das Instrument zeichnet.

Ein Instrument ist ein Werkzeug wie jedes andere (Regel 11): eine andere Shell kann dieselbe Zelle in eine Menüleiste hängen.

**Objekttypen:** – (instrument)
**Art:** `instrument` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/strip`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: task.changed, decision.pending, decision.answered, model.changed, system.state

## Abnahme
`python benchmarks/uix_check.py --tool gauge-gpu` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/gauge-gpu.png`
