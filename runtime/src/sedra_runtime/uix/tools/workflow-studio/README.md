# Workflow Studio (App)

App „Workflow Studio“: n8n Workflows, Szenario Studio, Factory, Live und Freigaben in einem App-Reiter der Harness-Shell.

- **One Sedra (`harness`):** die Shell zeichnet die App selbst, `shells/harness/workflow_studio.js`. Fünf Modi: n8n Workflows, Szenario Studio, Factory, Live, Freigaben.
- **Andere Shells:** Hinweis auf die App. Die anderen Shells werden nicht weiterentwickelt.
- **Die Werkzeuge bleiben**, was sie sind (`workflow`, `scenario`, `live`, `decision`, `project`). Die Factory-Läufe kommen aus der Lese-Ansicht der App Factory Studio.
- Keine eigene Route, kein Speicher. Notaus sitzt in der Lauf-Leiste des n8n-Editors.
