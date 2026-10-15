# Werkzeug `intent` – Vorhaben

Ein Vorhaben ist der Satz, um den es geht – und die Klammer um die Aufgaben, die daraus entstehen (Regel 8).

Anlegen kostet nichts und braucht keine Freigabe: es wird nichts ausgeführt. Erst „Aufgabe daraus machen“ beginnt den gewohnten Weg (Plan, Gates, Ausführung).

**Objekttypen:** intent
**Art:** `object` · **Platz:** inhalt · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `POST /api/objects`
- `POST /api/actions`
- `POST /api/intent/create`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: task.changed, tools.refresh

## Abnahme
`python benchmarks/uix_check.py --tool intent`

## Bildschirmfoto
`docs/shots/cockpit/intent.png`
