# Baubericht UIX Stufe 6 – 27.10.2026

Stand: Zweig `uix-stufe1-vertrag`, jetzt auf `origin/main` = `4ecd343` (die Stufen 1–5 sind neu aufgesetzt; einziger Konflikt: zwei neue
Zeilen im Logbuch, beide behalten). Spec: `SPEC_UIX_STUFE6_RAHMEN_v1` (Entscheidungen S6-E1 bis S6-E5 wie vorgeschlagen). **Nicht abgenommen.**

## Gebaut

| Bereich | Was | Wo |
|---|---|---|
| A1 Leiste | ruhige Zellen wandern in „+n ▾“ (höchstes `order` zuerst), Klick zeigt sie lebendig darunter; warn/bad und Zellen mit abgeschottetem Rahmen bleiben; unter 1200 px ohne dritte Zeile; kein Wert mehr abgeschnitten | `ui/leiste.js` (neu), Cockpit `strip.js`, Rahmen `ui/frame.js`, Minimal `menubar.js` |
| A2 Prüfwerkzeuge | Manifestfeld `zweck: pruefung`, Schalter `entwicklung`; `rahmen-probe` nur damit (Manifest `pruefung` nennt es) | `desk/gateway.py`, `local_switches.py`, `uix_server.py`, Schema |
| A3 Knöpfe | Rekorder und Umschalter in Leiste/Kopfleiste (Cockpit, Rahmen, Minimal, paperclip, `sedraWechsel.inLeiste`); ohne Leiste klein | `ui/wechsel.js`, `wechsel.css` |
| A4 | Zellen der Rahmen-Leiste passen in die Höhe | `ui/frame.css` |
| B1 Leeren | Rückfrage im Knopf (4 s, Esc), abgesetzt von Senden | `tools/talk/verlauf.js` |
| B2 Grüne | Knopf weg; Auswahl immer mit „Geprüft schnell ✓“ oben | `tools/talk/tool.js` |
| C1 offen | `/api/missions` mit `offen`/`antrag`; Anträge keine Aufgaben (Liste, Baum, Leiste, Arbeitsplatz) | `uix_server.py`, `desk/builtin_kinds.py`, `cockpit/tree.js` |
| C2 Baum | eigene Kopfzeile mit dem Knopf zum Ausblenden; „Projekt“ mit Name als Notiz; ein Griff für die Höhe des Gesprächs | `cockpit/shell.js`, `rahmen.js`, `tree.js` |
| D1 Nachweise | höchstens 34 %; unter 1100 px als Reiter (Treffer schaltet um); leer eingeklappt (Haken `shell.nachweisLeer`); ohne Nachweise keine leere Spalte | `ui/frame.js`, `frame.css`, `tools/fundstelle` |
| D2 KMU | Kopf kompakt unter 820 px Höhe oder mit offenem Vorgang | `shells/gateway-kmu/shell.js` |

Bewusst so: das Objekt `task` bleibt, wie es aufgezeichnet ist (Golden-Test `test_desk_kinds`); die Zahl „offen“ steht in der Missionsliste.

## Prüfungen
- Neu: `test_uix_stufe6` (8: Verteilung rein, Gespräch-Spec, Prüfwerkzeug am Manifest, Anträge keine Aufgaben, Browser über Cockpit, Wissensbasis, paperclip, Minimal bei 1400 und 1024 px: nichts schwebt über dem Inhalt, kein Überhang, kein abgeschnittener Wert; „+n“ öffnet die übrigen; Fundstelle eingeklappt/aufgeklappt/Reiter; KMU-Arbeitsbereich ≥ 55 %), `tools/talk/test.spec.js` (3).
- Gesamtlauf: siehe INTEGRATION.md im Paket.

## Offen
- „Datei öffnen“ in der Fundstelle, Projekt je Notiz, „Aus dem GateWay“ unter Eigenes, Maschinenraum „Gedächtnis der Oberfläche“ (aus Stufe 5).
- Cockpit-Nachweisspalte (Dock) noch ohne „leer eingeklappt“ – der Rahmen hat es; das Dock steht bei 399 Zeilen und braucht dafür eine Teilung.
- gateway-kmu, fisch, start: keine Kopfleiste – dort bleibt der kleine schwebende Knopf.
