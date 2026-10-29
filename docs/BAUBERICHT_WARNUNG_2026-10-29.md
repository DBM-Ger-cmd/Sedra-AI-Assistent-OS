# Baubericht: Warnung beim Überschreiben einer bestehenden Datei (29.10.2026)

Grundlage: Nachtrag `434b108` zur G3-Spec Stufe 2. Captain-Antworten (29.10.2026, über die Vorarbeiter-Sitzung): Berechtigungen B-1 bis B-6
freigegeben, nichts darüber hinaus; Schwellen 50 Zeilen oder 30 %; zuerst Hinweis ans Modell (W-1), besteht es darauf, Karte mit Warnkasten
(W-2); Qwen-Vergleichslauf nach dieser Warnung erlaubt, Start nur auf Ansage. Kein Modell geladen, nichts gepusht.

## Gebaut (Branch `harness/stufe-2-warnung` ab `spec/agenten-orchestrierung` `8f2a638`)

| Datei | Änderung | Berechtigung |
|---|---|---|
| `harness/werkzeuge.py` | `ersetzung_warnung(alt, neu)` über `difflib` (Zeilen, nicht Zeichen): Warnung, wenn mehr als 50 Zeilen entfernt werden oder mehr als 30 %. Der Plan trägt `warnung` nur für `datei_schreiben` auf eine bestehende Datei. | B-1 |
| `harness/freigabe.py` | W-1: erster Aufruf mit Warnung → Werkzeugergebnis `hinweis` (Zahlen, Verweis auf `datei_aendern`, Anleitung zur Bestätigung), nichts geschrieben, keine Karte. W-2: derselbe Inhalt zum zweiten Mal → Karte mit `warnung`, auch wenn der Katalog `frei` sagt. `oeffentlich()` gibt `warnung` aus. | B-1 |
| `uix/shells/harness/karte.js` | Warnkasten oben auf der Karte (`hs-karte-warnung`, `role=alert`), Knopf „Erlauben (ersetzt die Datei)“. | B-2 |
| `uix/shells/harness/shell.css` | Stil für Kasten und Karte (nur Tokens). | B-2 |
| `tests/test_harness_warnung.py` (neu) | 14 Tests: Schwellen, Plan, W-1 und W-2 über die Kiste, Zustimmung gilt nur für genau den Inhalt, `datei_aendern` und neue Dateien unberührt. | B-3 |

## Ergebnisse (ohne Modell)

- Gruppen `test_harness_warnung test_harness_werkzeuge test_uix_harness_freigabe test_harness_schleife harness`: **121 Tests, 0 rot**.
- `uix_check --shell harness` (1024×700, 1400×860): **18 von 18 ok**.
- Gesamtlauf `scheduler desk orchestra uix harness`: 1195 Tests, 6 übersprungen, **3 rot** – alle drei Browsertests des Cockpits
  (`test_uix_cockpit_baum.test_k5…`, `…test_k8…`, `test_uix_dock_stufe2…test_neuladen…`). Allein gelaufen: **18 von 18 grün**.
  Sie hängen am Zeitverhalten unter Last (wie bei der Dock-Reparatur vorher); die Harness-Änderungen berühren sie nicht. Nicht
  verändert, weil der Auftrag dafür keine Berechtigung enthält. **Offen:** Die drei Tests auf Warten nach Zustand umstellen – Freigabe nötig.

## Konflikt mit einer nicht freigegebenen Datei (wichtig für den Captain)

Die Schleife (`harness/schleife.py`) blockiert einen **zweiten identischen Aufruf** (HS-14: gleiche Werkzeug und Argumente zweimal →
Hinweis „Diesen Aufruf hast du gerade gemacht“, beim dritten Mal Zug ohne Werkzeuge). Damit erreicht ein Modell, das auf derselben
Ersetzung besteht, die Karte **nicht**: W-2 greift nur, wenn sich der Inhalt ändert. Die Tests auf Kistenebene beweisen W-2; das
Zusammenspiel mit der Schleife nicht.

Nötig dafür (nicht gebaut, `schleife.py` ist nicht in B-1 bis B-6): nach einem Ergebnis mit Status `hinweis` die Wiederholungszählung
zurücksetzen (eine Zeile, `letzter = None`). Vorschlag: **Berechtigung B-7** für `harness/schleife.py`, nur diese Zeile plus Test.

Außerdem: Die Oberfläche kennt den Status `hinweis` noch nicht; die Werkzeugzeile erscheint in der Fehlerfarbe. Das wäre `verlauf.js`
(Status-Zuordnung), ebenfalls nicht in B-1 bis B-6. Vorschlag: **B-8** für diese eine Zuordnungszeile.

## Offen (Captain entscheidet)

1. B-7 (`schleife.py`, eine Zeile) – ohne sie erreicht W-2 mit identischem Aufruf die Karte nicht.
2. B-8 (`verlauf.js`, Status `hinweis` in Warnfarbe).
3. Drei Cockpit-Browsertests unter Last (Berechtigung für Umstellung auf Warten nach Zustand).
4. Merge `harness/stufe-2-warnung` nach `spec/agenten-orchestrierung` – Entscheidung des Captains; nichts gepusht.
5. Qwen-Vergleichslauf: erlaubt nach dieser Warnung, Start **nur auf Ansage** in dieser Sitzung (nicht gestartet).
