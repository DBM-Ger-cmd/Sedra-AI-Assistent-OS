# Werkzeug `nachrichten` – Nachrichten (Fisch)

Aus dem Translator-Fisch-Konzept v0.1 (Skill B), ehrlich für eine Runtime ohne Netz: der **Brief** entsteht aus den **Quellen,
die der Captain gibt** (Text einfügen, Name und Datum dazu) – nie aus dem Gedächtnis des Modells, nie aus dem Internet.
Das **Profil** (Interessen, Ausschluss, Region, Sprache, Tiefe, Anzahl, Briefart; DATA_MODEL.json → news) liegt im Projekt
(`local_config/fisch.profil.json`), keine Cloud.

Je Meldung: Titel, Kurz, „Warum relevant?“, Deep Dive, Quelle (nur ein Name aus den gegebenen Quellen – sonst „unsicher“), Tags,
Vertrauen. Keine Mindestmenge: liefert das Modell aus den Quellen nichts, steht da nichts. Audit `FISCH_BRIEF` ohne Text.

Ein echter Nachrichtenabruf (Suche, Primärquellen, Dubletten über das Netz) ist nicht Teil dieser Runtime; die Stelle dafür ist
`fisch/nachrichten.py` – die Lese- und Profilregeln bleiben dieselben.

## Routen (Allowlist im Manifest)
- `GET /api/fisch/profil` · `POST /api/fisch/profil/speichern` · `POST /api/fisch/brief`
