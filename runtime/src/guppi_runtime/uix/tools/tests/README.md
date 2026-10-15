# Werkzeug `tests` – Tests

Was über den Kandidaten nachgewiesen ist: Teststand, statische Prüfungen, geplante Läufe, Blocker der isolierten Ausführung.

Ein nicht gelaufener Test wird nie als grün dargestellt – die Quelle ist `candidate-report.json`, nicht eine Annahme der Oberfläche.

**Objekttypen:** candidate
**Art:** `object` · **Platz:** nachweis · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `POST /api/candidate/report`
- `POST /api/actions`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: task.changed

## Abnahme
`python benchmarks/uix_check.py --tool tests` – mountet das Werkzeug an seinem Objekt, prüft Inhalt, Spalte, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/tests.png`
