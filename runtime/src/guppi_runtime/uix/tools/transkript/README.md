# Werkzeug `transkript` – Transkript (Fisch)

Aus LocalScribe (Transkript = Cues mit Zeiten; Exporter TXT/SRT/VTT/JSON; Suche nach ganzen Wörtern in Reihenfolge) und VoiceBrief
(Record = Status + Versionen; **Export ändert den Record nie** (ADR-009); **Identity-Mapping getrennt** (ADR-011); **Golden Record erst
nach Prüfung** (ADR-014); **Platzhalter heißen so** (ADR-008)).

**Weg:** Importieren (TXT, SRT oder VTT einfügen; Titel, Sprache – die Sprache ist eine Angabe des Captains, wie bei LocalScribe der
Guard vor dem Modell) → Suchen → Pseudonymisieren (neue Fassung mit Platzhaltern über den Inhaltsschutz, Mapping daneben, nie im
Export) → Prüfen → Freigeben (friert die Fassung ein) → Exportieren (`<Projekt>/fisch/export/`, vorläufig, solange nicht freigegeben).

**STT:** In dieser Runtime gibt es keinen Sprach-zu-Text-Provider. Das Werkzeug sagt das und bietet keinen Knopf, der so tut.
Anschlussstellen: VoiceBrief (Whisper lokal, Windows), LocalScribe (Voz, macOS).

## Routen (Allowlist im Manifest)
- `GET /api/fisch/transkripte` · `POST /api/fisch/transkript` · `/import` · `/suche` · `/pseudonymisieren` · `/status` · `/export`
