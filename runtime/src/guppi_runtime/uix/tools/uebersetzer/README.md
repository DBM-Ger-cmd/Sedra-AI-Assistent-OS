# Werkzeug `uebersetzer` – Übersetzer (Fisch)

Aus dem Translator-Fisch-Konzept v0.1 (Skill A): eine Nachricht für eine andere **Rolle** neu formulieren – Alltag, Business,
Management, IT/Entwicklung, Einkauf, Vertrieb; Ton (klar, freundlich, formell) und Tiefe (kurz, standard, ausführlich).
Die Regeln stehen im Systemsatz (`fisch/uebersetzer.py`): Bedeutung, Absicht und Fakten bewahren; keine Budgets, Termine,
Anforderungen erfinden; Fachbegriffe erhalten oder erklären; Unsicherheit und fehlende Angaben kennzeichnen; keine Floskeln.

**Ausgabe:** die neue Fassung, die Unsicherheiten, die Hinweise – gelesen aus einem festen Antwortformat. Antwortet das Modell
nicht im Format, ist die ganze Antwort die Fassung und das Werkzeug sagt das (nichts wird erfunden). Ohne Modell: „Kein Modell geladen“.

Der Modellaufruf geht durch den Control Master wie jeder andere (Mission je Aufruf, Audit `FISCH_UEBERSETZT` ohne Text, Inhaltsschutz).
Die Shell „Fisch“ reicht den Satz aus der Wolke als `ctx.object.frage` herein; in anderen Shells hat das Werkzeug ein eigenes Feld.

## Routen (Allowlist im Manifest)
- `GET /api/fisch/rollen` · `POST /api/fisch/uebersetzen`
