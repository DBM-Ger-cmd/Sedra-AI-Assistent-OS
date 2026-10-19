"""Sprache (Kern, 19.10.2026): Aufnehmen und Sprache → Text für jede Shell – nicht an den Fisch gebunden.
`stt.py` findet den Provider auf dem Rechner (whisperx, whisper) und baut seine Kommandozeile; `aufnahmen.py` ist die Ablage der
Aufnahmen (`<Projekt>/sprache/aufnahmen/`); `hub.py` sind die Routen `/api/sprache/…` am Hub. Kein Netz, keine Cloud: läuft der
Provider nicht auf diesem Rechner, sagt der Kern das – und erfindet kein Transkript (VoiceBrief ADR-008: Platzhalter heißen so).
Das Ergebnis einer Transkription wird ein Transkript-Record (fisch/transkripte.py), den jede Shell über den Typ `transkript` öffnet."""
