# Auftrag: Token-Verbrauch in Markdown-Export einfügen

**Ziel:** Der Markdown-Export einer Sitzung soll direkt unter der Überschrift eine Zeile mit dem aktuellen Token-Verbrauch enthalten.

**Schritte:**
1. `runtime/src/guppi_runtime/harness/verbrauch.py` lesen, um die Datenstruktur zu verstehen.
2. `runtime/src/guppi_runtime/harness/export.py` lesen, um die Stelle für das Einfügen zu finden.
3. `runtime/src/guppi_runtime/harness/export.py` anpassen: Import von `verbrauch` und Einfügen der Zeile „Token: {antworten} Antworten · {eingehend} eingehend · {erzeugt} erzeugt“.
4. Einen Test in `runtime/tests/` erstellen, der den korrekten String im Markdown-Export prüft.
5. Testlauf `run_tests` für die Gruppe `harness` ausführen.

**Abnahmekriterien:**
- Der Markdown-Export zeigt den Token-Verbrauch korrekt an.
- Der Test läuft erfolgreich durch.

**Risiken:**
- Verwechslung der Variablen für eingehende/erzeugte Tokens.

**Status:** umgesetzt (Commit 26b2fa1, Tests runtime/tests/test_harness_export_token.py), Abnahme durch den Captain offen
