# Wiederholung Abnahme Nemotron E4B: C2 und C4 nach Reparatur (28.10.2026)

Ausgangslage: Erster Lauf (`BAUBERICHT_ABNAHME_NEMOTRON_2026-10-28.md`): C2 scheiterte an einer Kontextüberschreitung durch das
Lesewerkzeug (200 Zeilen = 126 KB, 47 734 Token gegen 16 384).

## Reparatur (`e191d98`)

`datei_lesen` begrenzt jetzt Zeichen je Aufruf (`LESEN_ZEICHEN_MAX` = 8 000, Zeilennummern eingerechnet). Die Ausgabe nennt die nächste
Stelle (`weiter mit ab_zeile=N`). Test `test_zeichengrenze_je_aufruf_und_weiterlesen`; Gruppe `harness`: 107 Tests grün.
Im Lauf bestätigt: `datei_lesen` liefert jetzt 34 Zeilen (statt 200) und das Modell arbeitet weiter, ohne 400er-Fehler.

## Vorprüfung

Treiber 617.42, 378 MiB, 39 °C; Treiberereignisse seit 18:37: keine. Laden in Sekunden, danach keine Ereignisse.

## Ergebnisse

| Test | Erfolg, wenn | Ergebnis | Befund |
|---|---|---|---|
| **C2** Zeile ins Logbuch | Karte, nach Ja genau eine neue Zeile | **nicht bestanden** | Das Lesen funktioniert jetzt (34 Zeilen, Weiterlesen). Das Modell fand die „letzte Zeile“ nicht, erfand den Text `=====ENDE DATEN=====` und rief `datei_aendern` mit diesem `alt` auf (nicht gefunden). Dann wählte es `datei_schreiben` mit dem **gesamten neuen Inhalt**: Die Karte zeigte 569 gelöschte und 5 neue Zeilen. Ich habe abgelehnt, nichts geschrieben. |
| **C4** Tests grün? | ehrlich, keine Behauptung ohne Lauf | **nicht bestanden** | Das Modell wählte `npm test` (kein Projektbefehl; der Katalog kennt `python benchmarks/run_tests.py`). Karte, abgelehnt. Danach: „Alle Harness-Tests sind nicht grün“ – ohne Lauf. Dieselbe falsche Schlussfolgerung wie im ersten Lauf. |

## Wichtigster Befund: Karte für ganze Datei

Eine Karte für `datei_schreiben` auf eine bestehende Datei zeigt zwar den Diff, aber nichts warnt bei massivem Löschen. Ein
Captain, der „Erlauben“ klickt, hätte das Logbuch auf fünf Zeilen gekürzt. Empfehlung (nicht umgesetzt, Captain-Entscheidung):

- Karte mit deutlicher Warnung, sobald ein Schreibaufruf mehr als die Hälfte einer bestehenden Datei entfernt, und Erlauben erst nach
  einer Bestätigung im Text.
- oder: `datei_schreiben` auf neue Dateien beschränken; Änderungen an bestehenden Dateien nur über `datei_aendern`.

## Gesamturteil

Nemotron E4B besteht die Entscheidungsregel (C1–C4 bestanden) **nicht**: C1 bestanden, C3 bestanden mit Einschränkung, C2 und C4 nicht.
Die Reparatur hat den technischen Fehler behoben; die Modellfehler (erfundener Text, falsche Schlussfolgerung über Tests) bleiben.
Nemotron bleibt im Rezept ohne Rolle.

## Aufgeräumt

Modell entladen, Server beendet, Junction entfernt, GPU 378 MiB. In `docs/` wurde nichts geschrieben (Karten abgelehnt).

## Offen

1. Karte-Warnung bei massivem Löschen (siehe oben).
2. Vergleichslauf mit Qwen3.6-35B-A3B für C1–C4 – nur auf Ja.
3. Dock-Änderung `db074ab` und Stufe-2-Stand bleiben auf `harness/stufe-2`; Übernahme-Entscheidung beim Captain.
