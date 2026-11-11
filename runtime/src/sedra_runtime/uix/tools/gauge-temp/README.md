# gauge-temp

Instrument „Temperatur“: Temperatur der Grafikkarte (aus dem Wert gpu abgeleitet).

Eine Datenzelle der Taskleiste von One Sedra (`shells/harness/taskleiste.js`). Beschriftung, Ort und Klick stehen als `zelle` in `tool.yaml`
(Vertrag 1.1, AM1); `shells: [harness]` hält das Instrument aus dem Cockpit heraus. Die Zelle erscheint, wenn `shells/harness/leiste.json` das
Instrument nennt. Kein eigener Abruf: die Leiste liest `/api/strip`.
