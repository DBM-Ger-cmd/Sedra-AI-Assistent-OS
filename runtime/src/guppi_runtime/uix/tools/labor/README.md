# Werkzeug `labor` – KI Labor

Die Werkstatt für Cloud-Modelle mit API-Schlüssel. Alles an einem Ort, in drei Bereichen:

- **Anbieter und Schlüssel:** Hauptschalter, Anbieter ein- und ausschalten, Adresse, Schlüssel verschlüsselt ablegen oder löschen. Jeder Anbieter zeigt seinen Status (aus · nicht bereit mit Grund · bereit) und ob er im laufenden Server wirkt.
- **Modelle:** Karten wie auf build.nvidia.com, mit Filterspalte, Suche, Sortierung und Seiten. „Modelle abfragen“ holt die Liste live vom Anbieter (nur lesen, kein Prompt). „Als Standard nehmen“ schreibt das Standardmodell.
- **Tests:**
  - *Verbindung testen* geht die Kette in Schritten durch: Schlüssel und Anbieter, gemeldete Modelle, eine beantwortete Testnachricht. Jeder Schritt sagt, was fehlt.
  - *Alle Modelle testen* spricht jedes Modell einmal an und zeigt je Modell, ob es antwortet, wie schnell und warum nicht. Das kostet Tokens und dauert.

Die Tests lesen die gespeicherte Konfiguration und brauchen keinen Neustart. Ist der Hauptschalter oder der Anbieter aus, wird nichts gesendet. Ein Schlüssel wird nie angezeigt.

**Objekttypen:** labor
**Art:** `object` · **Vertrauen:** CORE · **Version:** 1.0.0

## Routen (Allowlist im Manifest)
- `GET /api/cloud`
- `POST /api/cloud/save`
- `POST /api/cloud/key`
- `POST /api/cloud/models`
- `POST /api/labor/connection`
- `POST /api/labor/models-test`
