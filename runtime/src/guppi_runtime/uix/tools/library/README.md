# Werkzeug `library` – Bibliothek

Fähigkeiten, eigene Skills und die Regale der Bibliothek. Lesen ist frei, Schreiben nur nach Freigabe mit Sicherung.

Drei Regale wie seit Build 5, jetzt in einem Container statt in einem Fenster.

**Objekttypen:** skill
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/library`
- `POST /api/library/search`
- `POST /api/library/read`
- `POST /api/library/text`
- `POST /api/library/custom/request`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: decision.answered

## Abnahme
`python benchmarks/uix_check.py --tool library` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/library.png`
