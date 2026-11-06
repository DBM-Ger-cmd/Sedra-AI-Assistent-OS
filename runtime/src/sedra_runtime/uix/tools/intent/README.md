# Werkzeug `intent` – Vorhaben

Ein Vorhaben ist der Satz, um den es geht – und die Klammer um die Aufgaben, die daraus entstehen (Regel 8).

Anlegen kostet nichts und braucht keine Freigabe: es wird nichts ausgeführt. Erst „Aufgabe daraus machen“ beginnt den gewohnten Weg (Plan, Gates, Ausführung).

**Stufen (19.10.2026):** ein Vorhaben kann ein Weg in Stufen sein (Werkflow) – jede Stufe hat Name und Satz, kann eine Aufgabe werden
und hängt sie dann an sich; der Zustand einer Stufe kommt aus ihren Aufgaben, die erste nicht fertige Stufe ist die aktuelle (Knopf
„Aufgabe daraus machen“ dort, auch in der Handlungszeile der Shell). Die Sammlung zeigt je Vorhaben einen Fortschrittsbalken, ein
Segment je Stufe. **Vorlagen** (`GET /api/intent/vorlagen`, `desk/vorhaben_vorlagen.py`) geben Titel, Satz und Stufen vor – z. B.
„3D-Assets über einen Etsy-Shop vertreiben“ mit acht Stufen; sie legen nichts an und führen nichts aus. Keine Aussage zu Rechten,
Steuern oder Plattformregeln – solche Punkte stehen in den Stufen als „prüfen“.

**Objekttypen:** intent
**Art:** `object` · **Platz:** inhalt · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `POST /api/objects`
- `POST /api/actions`
- `POST /api/intent/create` (auch mit `vorlage` oder `stufen`)
- `GET /api/intent/vorlagen`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open
- hört: task.changed, tools.refresh

## Abnahme
`python benchmarks/uix_check.py --tool intent`

## Bildschirmfoto
`docs/shots/cockpit/intent.png`
