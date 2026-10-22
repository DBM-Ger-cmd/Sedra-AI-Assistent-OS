# Werkzeug `wissen` – Wissen

Der Wissensspeicher (Spec 7): Quellen, Stand des Index, Suche mit Treffern, Nachmessung und offene Vorschläge.

**Objekttypen:** wissen (das eine Objekt `speicher`; Quellen und Vorschläge sind Ansichten: `view: quellen | index | suche | nachmessung | vorschlaege`)
**Art:** `object` · **Platz:** inhalt · **Vertrauen:** CORE · **Version:** 1.0.0

Fünf Ansichten im Container (D7.9):

- **Quellen** – Pfad, Adapter, Stufe, Projekt, Personenbezug, Abschnitte, Stand; Verben „Abschalten“, „Stufe heraufsetzen“ (ohne Gate, nur enger),
  „Neu beantragen“ (Antrag); dazu „Quelle beantragen …“ (Formular → Antrag im Posteingang) und „Erstbestückung beantragen“ (ein Antrag, ein Gate je Quelle).
- **Index** – Modell-ID, Abdeckung, letzter Lauf, Gerät, Pause-Grund, Modus hybrid/volltext; Verb „Nachführen“ (Abgleich und ein Einbett-Schritt, nur CPU).
- **Suche** – Eingabe; Treffer mit `[id]`, Quelle, Stelle, Datum, Rang je Liste, Punkte, Hinweis; der Klick auf die Kopfzeile öffnet die Quellen-Ansicht (`object.open`).
- **Nachmessung** – die protokollierten Fragen des Captains (nur Hash und Treffer), je Frage ein Urteil, „Nachmessung abschließen“ (D7.11).
- **Vorschläge** – offene und entschiedene Vorschläge der Agenten mit Herkunft und Belegen; freigegeben oder abgelehnt wird im Posteingang (Werkzeug `decisions`).

Ohne Schalter `wissen` (local_config/switches.yaml) sagt die Seite, dass der Speicher ausgeschaltet ist.

## Routen (Allowlist im Manifest)
- `POST /api/objects` (Typen `wissen`, `wissen_quelle`, `wissen_vorschlag`)
- `POST /api/actions` (Typ-Verben `suche`, `nachfuehren`, `quelle_beantragen`, `erstbestueckung`, `nachmessung*`; an der Quelle `abschalten`, `stufe_heraufsetzen`, `neu_beantragen`; am Vorschlag `zuruecknehmen`)

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit. Wer liest, bestimmt der Server (Captain, Stufe 6).

## Ereignisse
- sendet: object.open
- hört: decision.answered, desk.resync

## Abnahme
`python benchmarks/uix_check.py --tool wissen --shell paperclip` – mountet das Werkzeug an `wissen:speicher`, prüft Inhalt, Aufräumen beim `unmount`
und dass nur erlaubte Routen gerufen wurden. `node -r ../../../../../tests/uix_spec_dom.js test.spec.js` prüft die Ansichten im Schein-DOM.

## Bildschirmfoto
`docs/shots/paperclip/wissen.png` (noch anzufertigen, S7.5)
