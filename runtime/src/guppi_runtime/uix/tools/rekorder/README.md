# Werkzeug `rekorder` – Rekorder (Kern Sprache)

Für jede Shell: das Werkzeug zeichnet den Typ `aufnahme` (`{type: 'aufnahme', id: 'rekorder'}`); der Ort „Rekorder“ steht in
`ui/places.js`, also öffnet „öffne den Rekorder“ im Gespräch ihn in Cockpit, Paperclip, Minimal und Fisch.

**Weg:** Titel und Sprache (die Sprache ist eine Angabe des Captains, kein Raten) → Aufnehmen (der Browser fragt einmal nach dem
Mikrofon; `ui/sprache.js` nimmt auf und schickt alle vier Sekunden ein Stück an den Kern, jedes unter dem Request-Limit) → Pause /
Weiter / Stopp / Verwerfen → die Aufnahme liegt in `<Projekt>/sprache/aufnahmen/<id>.webm` + `<id>.json` → Abspielen → **Sprache →
Text** mit dem Provider des Rechners (`whisperx` bevorzugt, sonst `whisper`; läuft im Hintergrund, die Karte meldet sich) → das
Ergebnis ist ein Transkript-Record (Herkunft `stt:whisperx`), „Transkript öffnen“ führt hin.

**Ohne Provider** sagt das Werkzeug das oben in der Auskunft und zeigt den Befehl (`pip install whisperx`; ffmpeg muss da sein).
Der ehrliche Weg bis dahin: **Abschrift von Hand** – wird ein Transkript mit Herkunft `manuell`. Nichts wird erfunden
(VoiceBrief ADR-008). Keine Sprecher-Trennung (bräuchte Netz und Token – Entscheidung des Captains).

**Einstellung** (optional): `<Projekt>/local_config/sprache.stt.json` mit `modell` (tiny … large-v3, Standard small), `geraet`
(cpu | cuda), `rechenart` (int8 | float16 | float32), `befehl` (Pfad zur ausführbaren Datei).

## Routen (Allowlist im Manifest)
- `GET /api/sprache/aufnahmen` · `POST /api/sprache/aufnahme` · `/beginnen` · `/stueck` · `/beenden` · `/loeschen` · `/transkribieren`
