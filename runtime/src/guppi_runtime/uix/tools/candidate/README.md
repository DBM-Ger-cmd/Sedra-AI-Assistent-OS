# Werkzeug `candidate` – Kandidat

Das Werkstück: was GUPPI an den Dateien ändern will, Zeile für Zeile. Der Diff wird hier gerechnet und gezeichnet – ohne Bibliothek, mit einer LCS-Tabelle über die Zeilen; lange unveränderte Strecken werden gefaltet.

Die Verben kommen vom Desk (`/api/objects`), nicht aus diesem Werkzeug: „Übernehmen“ erscheint erst, wenn die Runtime den Kandidaten auch übernehmen würde.

**Objekttypen:** candidate
**Art:** `object` · **Platz:** inhalt · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `POST /api/objects`
- `POST /api/candidate/diff`
- `POST /api/actions`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: task.changed, decision.answered

## Abnahme
`python benchmarks/uix_check.py --tool candidate` – mountet das Werkzeug an seinem Objekt, prüft Inhalt, Spalte, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/candidate.png`
