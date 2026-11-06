# Werkzeug `planung` – Planungstisch

Die Arbeitsumgebung für KI-Assistenten (19.10.2026, Wunsch Klaus): in Paperclip unter „Assistenten → Planungstisch“, über Strg+K
(„Planungstisch“) und als Objekt `planung:tisch` in jeder Shell.

**Was es tut:** Links das Gespräch mit einem Assistenten in einer Rolle (Planer, Rechercheur, Entwickler, Prüfer … – die Rollen aus
den Rezepten, wie in der Besatzung). Der Assistent antwortet über `POST /api/planung/reply` – derselbe Weg wie das Gespräch
(Control Master, Audit, Inhaltsschutz), nur mit dem Systemsatz der Rolle und den Werkzeugen des Planens (`chat_tools.PLANUNG_TOOLS`):
`propose_intent` (ein Ziel mit Stufen), `propose_task` (ein Auftrag), dazu lesen, wo die Firma steht. Rechts stehen seine Vorschläge
als Karten: **Übernehmen** legt an (`/api/intent/create` mit Stufen, `/api/chat` für eine Aufgabe – geplant, nicht ausgeführt),
**Verwerfen** wirft weg. Darunter: was in dieser Sitzung festgelegt wurde, mit Sprung zum Objekt.

**Ohne Modell** bleibt der Tisch nutzbar: „Als Ziel“ und „Als Auftrag“ neben „Senden“ legen den eingegebenen Satz direkt an.

**Was es nicht tut:** nichts läuft ohne den Klick des Captains; der Assistent legt nichts selbst an (das Modell bekommt nur
Vorschlags-Werkzeuge); keine Datei, kein Programm. Die Gespräche werden nicht gespeichert – der Stand steht in Zielen und Aufgaben.

## Routen (Allowlist im Manifest)
- `POST /api/planung/reply` · `POST /api/intent/create` · `POST /api/chat` · `POST /api/actions` · `GET /api/models` · `POST /api/objects`

## Abnahme
`test_uix_planung` (Vorschlag mit Stufen aus einem Fake-Modell → Übernehmen → das Ziel steht mit seinen Stufen) und `uix_check --shell paperclip`.
