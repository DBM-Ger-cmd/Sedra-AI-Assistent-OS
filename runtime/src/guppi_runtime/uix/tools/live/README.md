# Werkzeug `live` – Live

Was gerade passiert: die Zeilen dieser Aufgabe aus Schritt-Journal, Übernahme und Audit.

Geholt wird einmal, alles Weitere schickt der Ereignisstrom (`live.line` mit `since`) – kein Polling.

**Objekttypen:** task
**Art:** `object` · **Platz:** nachweis · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `POST /api/live`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: live.line, task.changed

## Abnahme
`python benchmarks/uix_check.py --tool live` – mountet das Werkzeug an seinem Objekt, prüft Inhalt, Spalte, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/live.png`
