"""Fisch (19.10.2026): die Fachlogik hinter der Shell „Fisch“ – Übersetzer (Rollen), Nachrichten (Profil, Brief aus gegebenen Quellen)
und Transkripte (Import, Suche, Pseudonymisierung, Freigabe, Export). Quellen: Translator-Fisch-Konzept v0.1 (Prompt-Spec, Datenmodell),
LocalScribe (Exporter TXT/SRT/VTT/JSON, Cue-Gruppierung, Suche nach ganzen Wörtern) und VoiceBrief (Record-Regeln: Export ändert
den Record nie, Identity-Mapping getrennt, Platzhalter heißen so).

Reine Funktionen hier, der Modellaufruf liegt im Hub (uix_server.py) – wie beim GateWay."""
