# Werkzeug `logbook` – Logbuch

Die Audit-Kette: Zeit, Ereignis, Teil – und zuerst die Antwort, ob die Kette intakt ist.

Ereignisnamen werden in Worte übersetzt, der technische Name steht im Tooltip.

**Objekttypen:** logbook
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/audit`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: task.changed, decision.answered

## Abnahme
`python benchmarks/uix_check.py --tool logbook` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/logbook.png`
