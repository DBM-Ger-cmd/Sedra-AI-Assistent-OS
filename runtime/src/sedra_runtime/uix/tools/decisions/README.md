# Werkzeug `decisions` – Entscheidungen

Der eine Ort, an dem der Captain entscheidet: Mission-Gates, Änderungsanträge aus Werkstatt und Bibliothek und (ab Build 9) Grenzüberschreitungen – alle in derselben Form, mit denselben Wegen.

Die Wege kommen vom Desk (`/api/decisions`); das Werkzeug erfindet keinen.

**Objekttypen:** decision
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/decisions`
- `POST /api/decisions/answer`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: decision.pending, decision.answered

## Abnahme
`python benchmarks/uix_check.py --tool decisions` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/decisions.png`
