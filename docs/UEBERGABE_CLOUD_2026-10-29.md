# Übergabe für die Arbeit in der Cloud (29.10.2026)

Das Nutzungsguthaben der lokalen Sitzungen ist fast verbraucht; die Arbeit geht in einer Cloud-Sitzung weiter. Diese Datei ist der Einstieg.
Repository: `DBM-Ger-cmd/Sedra-AI-Assistent-OS` auf GitHub. Sprache: Deutsch, kurz, Ergebnis zuerst.

## 1. Was auf GitHub liegt

| Branch | Inhalt | Stand |
|---|---|---|
| `main` | Harness-Shell Stufe 1 und 2 (Gespräch, Werkzeuge, Freigabe-Katalog, Karten, Warnung beim Überschreiben), Specs, Berichte, Logbuch | abgenommen, übernommen |
| `harness/stufe-3` | Stufe 3: Vorlagen, Vorarbeiter-Freigabe, Aufgaben-Freigabe, Läufe, Endpunkte, Oberfläche (N1 bis N11 Teil 1), SEDRA-Bau N2 und Pilot N8 | **nicht** auf main gemerged, N12 und Rest N11 offen |

Nicht in Git (lokal auf dem PC des Captains, in der Cloud **nicht** vorhanden): `workspace/GUPPI_OS/local_config/` (Rezepte `role_routing.yaml`, `freigabe_katalog.yaml`),
alle Modelle (Ablage `I:\KI-Daten\modelle`), `engines/`, `runtime_data/`, `.venv`. Eine Cloud-Sitzung kann deshalb **keine Modelle laden und keine
Bau-/Messläufe mit SEDRA starten**. Sie kann Specs schreiben, Code ändern und Tests ausführen, soweit diese ohne Modell laufen.

## 2. Regeln des Captains (gelten auch in der Cloud)

- **Spec vor Umsetzung:** G1 Anforderungen, G2 Design, G3 Bau-Aufgaben; jedes Gate entscheidet der Captain (`docs/ENTWICKLUNG.md`).
- **Berechtigungen vorher einholen:** Jede Spec nennt alle Freigaben vorab (Schreibbereich, Befehle, Modelle, Läufe). Nichts mitten in der Arbeit nachfragen, was die Spec hätte klären können.
- Modelle laden, Läufe, Vergleichsläufe, Downloads, Push nur nach **ausdrücklichem Ja des Captains**, bei Bau-Sitzungen direkt in der jeweiligen Sitzung.
- Nie löschen (auch nicht in den Papierkorb). Kein `git push --force`. Logbuch `docs/LOGBUCH_AGENT_MANAGER.md`: Zeile unten anhängen, CRLF beibehalten, richtige Uhrzeit.
- Tests: im Ordner `runtime` `python benchmarks/run_tests.py <Gruppen>` (z. B. `scheduler desk orchestra uix harness`), mit `PYTHONIOENCODING=utf-8`.

## 3. Stand der Harness-Shell

- **Stufe 1 und 2 auf `main`:** Streamen, Sitzungen, Taskleiste, Werkzeuge `datei_lesen`/`datei_schreiben`/`datei_aendern`/`befehl`, Freigabe-Katalog (`harness/katalog.py`, Vorlage `config/freigabe_katalog.beispiel.yaml`), feste Vorbehalte, Karten im Posteingang, Warnung beim Überschreiben (50 Zeilen oder 30 %).
- **Stufe 3 auf `harness/stufe-3`:** G2/G3 in `SPEC_HARNESS_SHELL_v1_G2_STUFE3.md` und `…_G3_STUFE3.md` (vom Captain freigegeben). N1 bis N10 gebaut; N11 Teil 1 committet. **Erster Pilot eines SEDRA-Agenten unter einem Vorarbeiter über die Harness ist gelaufen:** N2 `aufgabe_deckung` (15/15, 544 s) und N8 `lauf_fortschritt` (Quote 0,9) von Qwen3.6-35B-A3B gebaut und mit kleinen Eingriffen von Claude übernommen.
- **Modelle:** Qwen3.6-35B-A3B ist der Standard-Coder (`coder.local_primary`). Nemotron E4B hat die Abnahme nicht bestanden (C2, C4) und bleibt ohne Rolle. Der Vergleichslauf mit Qwen (C1 bis C4, `MODELLTEST_HARNESS_v1.md`) ist **nicht** gelaufen.

## 4. Offen

1. **P-16:** vier Zeilen in `runtime/src/guppi_runtime/uix/ui/bus.js` (Ereignisse `harness.lauf`, `harness.aufgabe`, `harness.vorarbeiter`, `harness.karte`) plus Test in `test_uix_harness_shell.py`. Ohne sie erreichen die Ereignisse den Browser nicht. Freigabe liegt beim Captain.
2. **Stufe 3:** Rest von N11 (Läufe und Benachrichtigung in der Taskleiste), N12 (Gruppe, Abnahme, Bericht). Danach Merge von `harness/stufe-3` auf `main` nach Review durch den Captain.
3. **`test_k5`** (Cockpit-Baum-Tastatur) wackelt unter Last, allein grün; Server-Fix `request_queue_size` 64 ist auf `main`.
4. **Web-Browser (`SPEC_WEB_BROWSER_v1.md`, G1):** offen sind WBQ-3 (Zahlungsvariante A bis D, Vorschlag B und C), WBQ-6 (Tresor an Windows-Konto oder Master-Passwort), WBQ-7 (`anmelden` vorab in der Aufgaben-Freigabe). Danach G2. Eigene Linie nach Stufe 3.
5. **Wunsch-Anbindung (`SPEC_WUNSCH_ANBINDUNG_v1.md`):** G1 entschieden (WQ-1 bis WQ-4); G2 folgt nach Stufe 3.
6. Alte Punkte aus `docs/VERLAUF_VORARBEITER_2026-10-20_bis_25.md` §10: Spec 2 (Worker-Pool, S2.H5 bis H7), Spec 1 S1.H9, Spec 3 Mammouth-Bedingungen, Spec 7 Einschalten erst nach Erstbestückung und Abnahme S7.5.

## 5. Einstieg für die Cloud-Sitzung

1. `git log --oneline -15` auf `main` und auf `harness/stufe-3`; die letzten 20 Zeilen des Logbuchs lesen.
2. Diese Datei, `docs/ENTWICKLUNG.md` (Regeln), `SPEC_HARNESS_SHELL_v1_G3_STUFE3.md` (Aufgaben N1 bis N12) lesen.
3. Nur das tun, was ohne Modell und ohne lokale Konfiguration geht; alles andere als Frage an den Captain aufschreiben.
