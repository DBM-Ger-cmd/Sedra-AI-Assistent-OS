# Wunsch: Modellname im Markdown-Export

**Beschreibung:**
In `runtime/src/guppi_runtime/harness/export.py` soll der Markdown-Export unter der Token-Zeile eine Zeile „Modell: <Name>“ zeigen, wenn die Sitzung ein Modell hat.

**Verständnis:**
Der Captain möchte die Transparenz des Exports erhöhen, indem das verwendete Modell explizit aufgeführt wird, sofern eines vorhanden ist. Die Änderung betrifft die Formatierung der Exportfunktion im Harness.
