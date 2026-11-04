# Auftrag: Token-Verbrauch in Markdown-Export integrieren

## Ziel
Die Funktion `harness_export.markdown` soll so erweitert werden, dass sie nach der Überschrift des Exports eine Zeile mit dem Token-Verbrauch der Sitzung anzeigt.

## Schritte
1. **Datenquellen prüfen**: `runtime/src/guppi_runtime/harness/verbrauch.py` lesen, um die Struktur der Token-Daten zu verstehen.
2. **Export-Logik vorbereiten**: Die Funktion `markdown` in `runtime/src/guppi_runtime/harness/export.py` analysieren und die Stelle für die neue Zeile identifizieren.
3. **Daten abrufen**: Sicherstellen, dass die Token-Daten (Anzahl Antworten, eingehend, erzeugt) korrekt aus dem Sitzungsobjekt oder über die `verbrauch`-Module extrahiert werden können.
4. **Code anpassen**: Die neue Zeile in `export.py` einfügen.
5. **Testen**: Den Markdown-Export prüfen und die Anzeige verifizieren.

## Abnahmekriterien
- Der Export enthält die Zeile: „Token: X Antworten · Y eingehend · Z erzeugt" direkt unter der Überschrift.
- Die Werte X, Y und Z stimmen mit den Daten aus `harness/verbrauch.py` überein.
- Der Rest des Exports bleibt unverändert.

## Risiken
- Fehler beim Abrufen der Token-Daten könnten den Export unterbrechen (Abhilfe: Fehlerbehandlung oder Standardwerte).
- Falsche Formatierung der Zeile.

Status: umgesetzt (Commit 26b2fa1, Tests runtime/tests/test_harness_export_token.py), Abnahme durch den Captain offen
