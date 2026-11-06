# n8n Workflows 0.2.0

Eigenständige App im One-Sedra-Startmenü unter Arbeit: Knoten- und Parameterebene,
Import/Export einzelner n8n-Workflow-JSON, Canvas, Undo/Redo, SIPOC, Prozessfelder
und Versionsvergleich. Gemeinsame Bibliothek unter uix/ui/workflow-*.js, gleiche
Datenbasis mit Szenario Studio; eigene Gestaltung und Bedienung. Keine n8n-
Oberfläche eingebettet und kein Kursfall als Programmlogik enthalten.

Unbekannte Knoten und JSON-Felder werden erhalten; ausführbar ist nur das geprüfte
Datenprofil. Die App hat keine Freigaberoute. Start legt eine Mission an; nach
Bestätigung im bestehenden Posteingang wird der Lauf ausdrücklich fortgesetzt.
Die Laufansicht zeigt den Missionsschritt und die Engine-Antwort, kein vollständiges
n8n-Knoten-Tracing. Bereinigter Export ist eine Hilfe, keine Geheimniserkennung
für freie Texte. Siehe docs/N8N_WORKFLOW_APP.md für Betrieb und Grenzen.
