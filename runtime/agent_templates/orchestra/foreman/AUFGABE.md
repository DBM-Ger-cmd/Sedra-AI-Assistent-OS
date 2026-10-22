# Beispielaufgabe der Abnahme-Suite `orchestra.foreman`

Die Instanz bekommt im Modus `zerlegen` diese Anweisung des Captains: „Bau einen CSV-Export für den Monatsbericht.“
Untergebene: planer (Stufe 1), coder (Stufe 2), reviewer (Stufe 1). Ihre Antwort (JSON) wird als `antwort.py` mit
`ANTWORT = {...}` abgelegt und mit `agent_manager.cli suite <instanz> --suite orchestra.foreman --candidate <ordner>` geprüft.
