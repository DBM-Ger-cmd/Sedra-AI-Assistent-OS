# Bericht: Freigaben B-7, B-8 und Umstellung der Cockpit-Browsertests (29.10.2026)

Grundlage: Captain-Antworten (29.10.2026, über die Vorarbeiter-Sitzung): B-7 Ja (eine Zeile in `harness/schleife.py`), B-8 Ja
(Status `hinweis` in `verlauf.js`), die drei Cockpit-Browsertests auf Warten statt feste Zeiten umstellen. Cockpit-Code unverändert.
Kein Modell geladen, nichts gepusht.

## Gebaut

| Datei | Änderung | Freigabe |
|---|---|---|
| `harness/schleife.py` | eine Zeile: `if status == 'hinweis': letzter = None` – der Aufruf nach einem Hinweis gilt nicht als Wiederholung (HS-14 bleibt sonst unverändert). | B-7 |
| `tests/test_harness_schleife.py` | neuer Test: nach einem Hinweis erreicht der zweite identische Aufruf das Werkzeug, Ende `wartet`. | B-7 |
| `uix/shells/harness/verlauf.js` | Status `hinweis` mit Label „Hinweis – nicht geschrieben“; die Werkzeugzeile zeigt ihn in der Fehlerfarbe. | B-8 |
| `tests/test_uix_cockpit_baum.py` | `test_k5` und `test_k8`: feste Wartezeiten durch Warten auf den Zustand ersetzt. | Umstellung |
| `tests/test_uix_dock_stufe2.py` | `test_neuladen_bringt_die_reiter…`: Warten, bis der Arbeitsstand beide Reiter hat und nach dem Neuladen der Reiter da ist. | Umstellung |

## Ergebnisse (ohne Modell)

- Die drei Browsertests allein: `test_uix_cockpit_baum` + `test_uix_dock_stufe2`: **18 von 18 grün**.
- Gruppen `scheduler desk orchestra uix harness`: 1196 Tests, 6 übersprungen, **1 rot**: `test_uix_cockpit_baum…test_k5_tastatur_im_baum_und_fokus_nach_dem_neuzeichnen`.
- `uix_check --shell harness`: **18 von 18 ok** (1024×700 und 1400×860).

## Offen: `test_k5` unter Last (ehrlich vermerkt)

`test_k5` ist vor und nach dieser Umstellung im Gesamtlauf rot; allein läuft er grün. Die Diagnose ist jetzt genauer: Das Element
`.ck-tree [role=treeitem][tabindex="0"]` ist im Dokument vorhanden, wird aber 20 Sekunden lang **nicht sichtbar** (Playwright: „to be
visible“). Eine längere Wartezeit würde das nur verdecken. Die Ursache liegt in der Anzeige des Baums unter Last, nicht im Test; sie
ist nicht gelöst. Das Cockpit bleibt unverändert, wie beauftragt.

## Merge

Entscheidung beim Captain (über den Vorarbeiter). Der Branch `harness/stufe-2-warnung` enthält diesen Stand; nichts gepusht.
