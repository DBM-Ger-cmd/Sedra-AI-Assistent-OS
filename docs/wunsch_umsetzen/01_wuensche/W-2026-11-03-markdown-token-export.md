# Wunsch: Markdown-Export mit Token-Verbrauch

## Wunsch des Captains
Der Markdown-Export einer Sitzung soll gleich unter der Überschrift eine Zeile mit dem Token-Verbrauch der Sitzung enthalten, in der Form „Token: X Antworten · Y eingehend · Z erzeugt".

## Verständnis
Der Captain möchte die Transparenz über den Ressourcenverbrauch erhöhen, indem die bereits in `harness/verbrauch.py` verfügbaren Daten direkt in den exportierten Markdown-Bericht integriert werden. Der Export soll die Anzahl der Antworten sowie die eingehenden und erzeugten Token anzeigen.