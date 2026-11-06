# Werkzeug `wissen` – Wissen

Der Wissensspeicher (Spec 7, SPEC_WERKZEUG_WISSEN_v2): Suche, Quellen, Vorschläge und Messung (Index und Nachmessung).

**Objekttypen:** wissen (das eine Objekt `speicher`; die Ansichten wählt `view: suche | quellen | vorschlaege | eigenes | messung`,
dazu die alten Namen `index` und `nachmessung` – sie öffnen den jeweiligen Abschnitt der Messung)
**Art:** `object` · **Platz:** inhalt · **Vertrauen:** CORE · **Version:** 2.0.0 · **Gedächtnis:** sitzung, ablage

Fünf Ansichten als Reiter (Pfeiltasten wechseln); die Zahlen am Reiter kommen aus dem einen Objekt `wissen:speicher`:

- **Suche** (Start, WZ1) – ein Feld, Enter sucht. Treffer als Karten: die Stelle als Titel (Klick → Quelle), Quelle · Datei · Stand darunter, ein
  Balken für die Relevanz im Verhältnis zum besten Treffer, Suchwörter markiert. „Fundstelle“ klappt auf und sendet `wissen.auswahl`, „Ins Gespräch“
  setzt Kennung und Stelle ins Eingabefeld des Gesprächs, Kennung und Ränge stehen unter „Details“. ↑/↓ wechseln den Treffer, Esc zurück ins Feld.
  Zitate `[W…]` im Text sind Verweise. Nach einem Neuladen oder Shell-Wechsel stehen Frage und Treffer wieder da („Treffer von HH:MM · neu suchen“).
- **Quellen** – eine Liste statt einer Tabelle: Titel, Marken in Klartext (Art, Stufe, Projekt, Personenbezug), Abschnitte und Stand; die
  Handlungen im Menü „⋯“. „Stufe heraufsetzen …“ (ohne Gate, nur enger) und „Neu beantragen …“ öffnen eine Auswahl mit dem Klartext der Stufe
  (Abbrechen/Esc, Enter bestätigt, kein `prompt()`). Filter alle · aktiv · aus. Ein Treffer markiert hier seine Quelle.
  **Quelle beantragen …** ist geführt (WZ4, `antrag.js`): 1 Was soll SEDRA lernen? (Vorlagen, Freigegebenes ist nicht doppelt wählbar)
  → 2 Wo genau? (Vorprüfung `quelle_pruefen`: Dateien, etwa Abschnitte, Überschneidung) → 3 Wer darf es lesen? → 4 Zusammenfassung → Antrag im Posteingang.
- **Filter der Suche** (SPEC_SHELL_WISSEN_v1 §4.5): „Filter“ neben dem Feld – Art, Quelle, Projekt, Zeitraum; gefiltert wird auf dem Server
  vor dem Ranking (Top-k läuft nicht leer). Ein Auftrag aus der Shell (Palette „Im Wissen suchen“, Menü „Quelle für Wissen“) liegt einmal
  im Memo des Werkzeugs und wird beim Einhängen ausgeführt – nie im Objekt, nie im Browser-Speicher.
- **Eigenes** (§4.4, `eigenes.js`) – Notizen des Captains: Titel, Text, Personenbezug; „Speichern“ (Strg+Enter), Ändern, Löschen in zwei
  Schritten. Beim ersten Mal wird „Notizen des Captains“ einmal beantragt; danach ohne Gate, die Notiz ist sofort per Volltext findbar.
  Der Entwurf liegt in der Ablage.
- **Vorschläge** – Filter offen · entschieden · alle; Herkunft und Belege; „Im Posteingang entscheiden“ öffnet den einen Posteingang.
- **Messung** (WZ2) – Index als Karte (Modus, Abdeckung, letzter Lauf, Pause-Grund; Rest unter „Details“) und Nachmessung mit drei Knöpfen je
  Frage (eine Bewertung zeichnet nur ihre Zeile) und Fortschritt.

Die Handlungen der offenen Ansicht stehen in der Werkbank-Zeile der Shell (WZ3, `actions()`); nach einem Reiterwechsel sendet das Werkzeug
`object.actions`, die Shell zeichnet die Zeile neu. Ohne Schalter `wissen` (local_config/switches.yaml) sagt die Seite, dass der Speicher
ausgeschaltet ist. Fehler aus `ctx.api()` werden Sätze auf Deutsch (`zitate.js`, `fehlerSatz`), nie Konsolenzeilen.

**Gedächtnis (Vertrag 1.1):** in der Sitzung (sessionStorage) nur der Zustand der Ansicht (Reiter, Zahl der Treffer, Filter, aufgeklappt, die
Kennung der markierten Quelle) – nie Frage, Treffer oder Eingaben. Die liegen in der Ablage des Servers (RAM, nie auf der Platte).

Dateien: `ui/zitate.js` (reine Teile, Vertragscode – auch Gespräch und Fundstelle nutzen es), `suche.js`, `quellen.js`, `antrag.js`, `messung.js`, `eigenes.js`, `tool.js` (Zustand, Reiter, Vorschläge, Werkbank).

## Routen (Allowlist im Manifest)
- `POST /api/objects` (Typen `wissen`, `wissen_quelle`, `wissen_vorschlag`)
- `POST /api/actions` (Typ-Verben `suche` (mit `filter`), `nachfuehren`, `quelle_pruefen`, `quelle_beantragen`, `erstbestueckung`, `nachmessung*`,
  `notizen`, `notiz_anlegen`, `notiz_aendern`, `notiz_loeschen`; an der Quelle
  `abschalten`, `stufe_heraufsetzen`, `neu_beantragen`; am Vorschlag `zuruecknehmen`)
- implizit aus `gedaechtnis: ablage`: `POST /api/ablage/lesen`, `POST /api/ablage/schreiben`

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit. Wer liest, bestimmt der Server (Captain, Stufe 6).

## Ereignisse
- sendet: object.open („Agent öffnen“), wissen.auswahl (Fundstelle, Ins Gespräch), object.actions (Ansicht gewechselt)
- hört: decision.answered, desk.resync

## Abnahme
`python benchmarks/uix_check.py --tool wissen --shell cockpit` – mountet das Werkzeug an `wissen:speicher`, prüft Inhalt, Aufräumen beim `unmount`
und dass nur erlaubte Routen gerufen wurden. `node -r ../../../../../tests/uix_spec_dom.js test.spec.js` prüft die Ansichten im Schein-DOM (20 Prüfungen).

## Bildschirmfoto
`docs/shots/cockpit/wissen.png` – TODO auf dem PC (Browser): Ansicht „Suche“ mit Treffern, Ansicht „Quellen“ mit geführtem Antrag.
