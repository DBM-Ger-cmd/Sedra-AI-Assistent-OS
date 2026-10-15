# KI GateWay (Werkzeug, Objekttyp `gateway`)

Der Vorgang nach dem Studio Flow v1.1 (`docs/SPEC_GATEWAY_VORGANG_v1.md`): **01** Wunsch lokal/Cloud (simuliert) · **02** Anfrage
+ ein .md/.txt aus dem Projekt → „Datenschutz prüfen“: links das Original mit Markierungen, rechts der Übergabeprompt mit
Platzhaltern · **03** Empfehlung (SK0–SK3, Merkmale, erlaubte Wege, Policy-Status) → Freigabe = ein Gate · **04** Entwurf →
„Geprüft“ oder „Verwerfen“. Kein Versand. Der Nachweis daneben ist das Werkzeug `schutz` (Inhaltsschutz von ganz SEDRA).

Backend: `guppi_runtime/gateway/` (`klassen.py` Matrix, `vorgang.py` Ablauf und Ablage). Routen `/api/gateway/*`.
