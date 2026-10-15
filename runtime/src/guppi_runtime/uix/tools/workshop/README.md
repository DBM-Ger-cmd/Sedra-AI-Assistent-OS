# Werkzeug `workshop` – Werkstatt

Modelle laden, entladen und testen. Jede Rezeptänderung ist eine Entscheidung und läuft nicht über dieses Werkzeug.

Verben stehen in der Werkbank-Zeile, nicht im Inhalt.

**Objekttypen:** model
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/models`
- `POST /api/model/load`
- `POST /api/model/unload`
- `POST /api/model/test`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: model.changed

## Abnahme
`python benchmarks/uix_check.py --tool workshop` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/workshop.png`
