# Werkzeug `settings` – Einstellungen

API-Einstellungen für Cloud-Modelle mit API-Schlüssel: Anbieter ein- und ausschalten, Modell und Adresse eintragen, Schlüssel verschlüsselt ablegen oder löschen.

Der Schlüssel wird nie angezeigt, nur sein Zustand (aus der Umgebung · gespeichert · fehlt). Gespeichert wird nur auf Klick des Captains; die Änderungen wirken nach dem nächsten Start.

**Objekttypen:** settings
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/cloud`
- `POST /api/cloud/save`
- `POST /api/cloud/key`

## Hinweis
Der Objekttyp `settings` steht im Kernvertrag (`desk/gateway.py`, OBJECT_TYPES), damit jede Shell dieses Werkzeug öffnen kann.
