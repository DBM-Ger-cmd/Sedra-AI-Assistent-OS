# Auftrag: Modellname im Markdown-Export anzeigen

**Ziel**
Im Markdown-Export der Harness soll unter der Zeile mit den Token-Informationen eine zusätzliche Zeile „Modell: <Name>“ stehen, sofern der aktuellen Sitzung ein Modell zugeordnet ist.

**Schritte**
1. **Analyse**: `runtime/src/guppi_runtime/harness/export.py` lesen, um die Markdown-Generierung zu finden.
2. **Logik-Prüfung**: Prüfen, wie der Modellname aus dem Kontext abgerufen wird.
3. **Implementierung**: `runtime/src/guppi_runtime/harness/export.py` anpassen, um die Zeile „Modell: <Name>“ einzufügen.
4. **Test-Erstellung**: Einen Test in `runtime/tests/` erstellen, der den Markdown-String für eine Sitzung mit und ohne Modell prüft.
5. **Verifizierung**: `python -m py_compile` und `lauf_starten run_tests` ausführen.

**Abnahmekriterien**
- Der Markdown-Export zeigt korrekt „Modell: <Name>“ an, wenn ein Modell vorhanden ist.
- Wenn kein Modell vorhanden ist, wird die Zeile übersprungen.
- Die Syntax der Datei ist korrekt (keine Compile-Fehler).

**Risiken**
- Falsche Formatierung des Markdown-Strings (z.B. Zeilenumbrüche).
- Zugriff auf einen ungültigen Kontext-Key für den Modellnamen.

**Status:** umgesetzt (Commit 078694b, Tests runtime/tests/test_harness_export_token.py), Abnahme durch den Captain offen
