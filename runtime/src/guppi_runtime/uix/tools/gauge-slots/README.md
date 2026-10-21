# Slots – Kachel (`gauge-slots`)

Ein Instrument wie `gauge-gpu` und `gauge-model`: eine Zelle der Leiste, im Dashboard von Shell D eine Kachel. Zeigt `reading.slots`
aus `GET /api/strip` (`{value: '2/3', hint: '1 wartet', tone}`); ein Klick öffnet „Modelle und Slots“ (`model:alle`).
Spec 4, D4.2.4 (Gate G2-S4-09). Solange die Leiste kein Feld `slots` hat (Scheduler, Spec 2), steht „–“ mit „noch keine Daten“.

Dateien: `tool.js` (rein: `zelle`), `tool.css`, `test.spec.js` (Schein-DOM, `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`).
