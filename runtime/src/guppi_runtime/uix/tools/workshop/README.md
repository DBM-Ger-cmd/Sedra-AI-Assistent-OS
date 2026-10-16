# Werkzeug `workshop` – Werkstatt

Modelle laden, entladen und testen. Jede Rezeptänderung ist eine Entscheidung und läuft nicht über dieses Werkzeug.

Build 24 (B6-G-06): zwei Abschnitte – **Neues Modell** (GGUF wählen: Dialog dieses PCs, Modellordner oder Pfad → Datei lesen → Rezept prüfen → `POST /api/model/add/request` legt das Gate vor; geschrieben wird erst nach „freigeben und anwenden“ im Werkzeug Entscheidungen) und **Teststrecke** (Standardtest des geladenen Modells; die Empfehlung wird ein Änderungsantrag). Objekt `model:neu` bzw. `model:teststrecke` öffnet den Abschnitt. `arbeitsplatz.yaml`: die Anleitungen dazu für das Gespräch.

Verben stehen in der Werkbank-Zeile, nicht im Inhalt.

**Objekttypen:** model
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.1.0

## Routen (Allowlist im Manifest)
- `GET /api/models`
- `POST /api/model/load`
- `POST /api/model/unload`
- `POST /api/model/test`
- `POST /api/model/pick` · `POST /api/model/browse` · `POST /api/model/inspect` · `POST /api/model/add/request`
- `GET /api/standard-test` · `POST /api/standard-test/start` · `POST /api/routing-config/request`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Ereignisse
- sendet: object.open, decision.pending
- hört: model.changed, decision.answered

## Abnahme
`python benchmarks/uix_check.py --tool workshop` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/workshop.png`
