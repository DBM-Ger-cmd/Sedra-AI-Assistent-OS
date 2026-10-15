# Werkzeug `boundaries` – Modus und Grenzen

Modus und die vier Grenzen je Projekt: Projekt · Netz · Löschen · Kosten (Regel 7, §3).

„Frei“ gibt es für Netz und Löschen nicht – der Knopf fehlt, nicht nur die Wirkung. Bestätigen und Ändern sind Freigaben und laufen über die Entscheidung. Beim ersten Mal steht hier der Vorschlag aus dem Projekt mit seiner Begründung.

**Objekttypen:** boundary
**Art:** `object` · **Platz:** inhalt · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/boundaries`
- `POST /api/boundaries/request`
- `POST /api/actions`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: decision.answered

## Abnahme
`python benchmarks/uix_check.py --tool boundaries`

## Bildschirmfoto
`docs/shots/cockpit/boundaries.png`
