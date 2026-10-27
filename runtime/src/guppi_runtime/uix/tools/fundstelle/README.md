# Werkzeug `fundstelle` – Fundstelle

Der Nachweis neben dem Wissen (SPEC_SHELL_WISSEN_v1 §4.2). Wählt der Captain im Werkzeug `wissen` einen Treffer („Fundstelle“),
sendet es `wissen.auswahl {id, quelle, woerter}`; hier steht der Abschnitt dann im Zusammenhang: Datei, Stelle, Stand, Stufe, Projekt,
Personenbezug, Befund des Inhaltsschutzes, der Abschnitt davor und danach, die Suchwörter markiert. Kein Werkzeug kennt das andere.

**Objekttypen:** wissen (als Nachweis) · **Art:** `object` · **Platz:** nachweis · **Vertrauen:** CORE · **Version:** 1.0.0 · **Gedächtnis:** sitzung

- „Ins Gespräch übernehmen“ sendet `wissen.auswahl` mit `zweck: gespraech` – das Gespräch setzt Kennung und Stelle ins Eingabefeld.
- „Quelle zeigen“ öffnet Wissen › Quellen mit der Quelle markiert. „Zeigen“ an einem Nachbarn macht ihn zur Fundstelle.
- Gedächtnis: nur die Kennung `W…` in der Sitzung; den Text liest das Werkzeug nach einem Neuladen neu vom Server.

## Routen (Allowlist im Manifest)
- `POST /api/objects` (Typ `wissen_abschnitt`; der Server prüft Stufe, Projekt und ob die Quelle aktiv ist – wie bei der Suche)

## Ereignisse
- sendet: object.open, wissen.auswahl (zweck gespraech)
- hört: wissen.auswahl

## Abnahme
`node -r ../../../../../tests/uix_spec_dom.js test.spec.js` – Leerzustand, Abschnitt mit Nachbarn, Markierung, nicht lesbar, Ins Gespräch.
`python benchmarks/uix_check.py --tool fundstelle --shell wissensbasis`.
