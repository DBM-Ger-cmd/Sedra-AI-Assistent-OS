# Rahmen-Probe

**Wofür:** Prüft den abgeschotteten Rahmen der Stufe C (docs/PLAN_STUFE_C_2026-10-19.md). Das Werkzeug läuft in einem
`iframe` mit `sandbox="allow-scripts"`, ohne Zugriff auf die Seite und ohne Token.

**Was es zeigt:** Jeder Knopf probiert etwas, das ein Werkzeug im Rahmen nicht darf. Erlaubt sind nur der Status (`GET /api/status`)
und ein Hinweis an die Shell. Eine fremde Route, eine Freigabe, das Lesen der Seite der Shell und der Token-Zugang müssen mit
„verweigert“ oder „nicht vorhanden“ enden.

**Vertrauensstufe:** CAPTAIN. Es ist ein Prüfwerkzeug, kein Teil der Arbeit; es kann nach der Abnahme von C5 ausgeblendet werden.
