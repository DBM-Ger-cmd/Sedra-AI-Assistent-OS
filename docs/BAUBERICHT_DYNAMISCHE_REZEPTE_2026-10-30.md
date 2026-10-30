# Baubericht Dynamische Rezepte (30.10.2026): R1 Bau-Spec, R2 SEDRA-Bau der Rechenmodule

Spec: `SPEC_DYNAMISCHE_REZEPTE_v1_G1.md`, `…_G2.md`, `…_G3.md`, `BAUSPEC_AUFTEILUNG.md`. Captain 30.10.2026: „lass SEDRA G3 bauen, wenn möglich“ (Ansage für den Modelllauf), danach „Du darfst ihn beenden“ (übrig gebliebener Modellserver, PID 34024).

## R1 (Claude): gebaut

`devvm_specs/modelle_aufteilung.py` (Aufgabe, 16 versteckte Prüfungen, L3 ≤ 20), Referenz `devvm_refs/modelle_aufteilung/aufteilung.py` (92 Zeilen), Bau-Spec. `spec_check` lint, Größe, Referenz ok, Stempel `--vm` (microVM, Python 3.12.15).

## R2 (SEDRA): zwei Bauversuche über die Harness, **nicht bestanden**

Weg: Vorarbeiter-Sitzung `S-2C1BABE6` (Qwen3.6-35B-A3B, `coder.local_primary`), Aufgaben-Freigabe `T-B68BE1EC` (nur `spec_check` und `devvm_build`, Modell `coder.local_primary`, 20 Aufrufe): Der Vorarbeiter startete beide Läufe, ohne Karte.

| Versuch | Prüfungen | Ergebnis |
|---|---|---|
| 1 (`L-C554A758`) | 14 | **bestanden** (536 s, 14 Aufrufe, 1 Agentenlauf, 0 Nacharbeiten, 0 Eskalationen), Kandidat 256 Zeilen |
| Review des Kandidaten | gegen die Referenz (3000 Fälle `waehlen`, 2000 Fälle `bedarf`) | Rechnung **identisch** (`bedarf` 2000/2000, Erfolgsfälle 432/432, beste Kombination im Fehlschlag gleich); **aber** `fehlt` enthielt in allen 2568 Fehlschlägen den ganzen Bedarf statt des Fehlbetrags, `vorschlag` war nur „Waehlen Sie Lagen=…“, und kaputte Eingaben lösten `KeyError`/`TypeError` statt `ValueError` aus (`gemessen` mit falschem Wert, `frei_vram=None`, Kontext „x“, `slots=0` ohne Fehler); Berechnung doppelt (in `bedarf` und `waehlen`), Interpolation dreifach, ein unerreichbares `return` |
| Befund zur Prüfung | – | **Meine versteckten Prüfungen waren zu schwach** (`fehlt > 0` statt der Zahl; keine Eingabefehler). Geschärft auf 16 Prüfungen (Fehlbetrag als Zahl, sieben Eingabefehler, Satz mit GB); der erste Kandidat fällt nun durch |
| 2 (`L-C2D41245`) | 16 | **nicht bestanden** (3831 s, 4 Agentenläufe, 67 Aufrufe, 3 Nacharbeiten, 0 Eskalationen), Kandidat 389 Zeilen: `fehlt` jetzt richtig (4,8 und 5,13 GB im Probefall), aber die Eingabeprüfung (Zeile 38) besteht er nicht |

**Ergebnis (V4):** Die Referenz von Claude bleibt und steht als `models/aufteilung.py` im Paket (Kopfkommentar nennt den Bau); `tests/test_models_aufteilung.py` lässt sie dieselben versteckten Prüfungen bestehen und prüft die Zahlen des Befunds (Qwen3.6, 10,65 GB VRAM und 14,3 GB RAM frei → 30 Lagen). Quote Claude/SEDRA: Referenz 92 Zeilen, Spec und Prüfungen etwa 100; SEDRA-Kandidat 256 bzw. 389 Zeilen – kein Gewinn an Aufwand.

**Was der Versuch lehrt:** (1) SEDRA trifft die Rechenlogik zuverlässig (Zahlen identisch), scheitert aber an Randverhalten (Eingabeprüfung, Fehlertyp) und liefert viel Wiederholung; (2) schwache versteckte Prüfungen lassen einen falsch gebauten Kandidaten bestehen – Prüfungen müssen die Rückgabewerte prüfen, nicht nur ihre Form; (3) der Vorarbeiter (Qwen3.6) erfand zweimal eine Lauf-ID, ohne das Werkzeug aufzurufen (HS-16 zählt das richtig nicht als erledigt) und tippte `modell_aufteilung` statt `modelle_aufteilung`; erst die ausdrückliche Aufforderung „Ruf das Werkzeug wirklich auf“ führte zum Aufruf; (4) nach `devvm_build` ist das Gespräch ohne Modell (exklusive GPU), es muss neu geladen werden.

## Offen

R3 (Rezeptblock im Routing, Lader wählt vor dem Start), R4 (Messspeicher), R5 (Antwort, Audit, Oberfläche), R6 (Abnahme, danach mit Modell auf Ansage). Die Zahlen für das Rezept (`profile.dynamisch`) trägt der Captain in `local_config` ein oder gibt ihre Anlage ausdrücklich frei (D-R2).
