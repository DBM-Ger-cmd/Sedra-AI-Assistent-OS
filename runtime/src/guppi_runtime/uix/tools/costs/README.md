# Werkzeug `costs` – Kosten

Das Münzloch: Token und Aufrufe dieser Aufgabe, in Münzen und mit der Herkunft der Zahlen.

Gemeldet und geschätzt werden nie vermischt; eine Kostengrenze gibt es erst, wenn sie gemessen ist (Build 9).

**Objekttypen:** task
**Art:** `object` · **Platz:** nachweis · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `POST /api/cost`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: task.changed, live.line

## Abnahme
`python benchmarks/uix_check.py --tool costs` – mountet das Werkzeug an seinem Objekt, prüft Inhalt, Spalte, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/costs.png`
