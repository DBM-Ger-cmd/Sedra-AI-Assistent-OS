# 01 – Überblick: die Shell „KI Gateway für KMU“

## Was sie ist
Eine Oberfläche (Shell) im Design der Präsentation „KI Gateway für KMU · B6 · SEDRA“. Sie gehört zu den austauschbaren
Oberflächen von SEDRA (Cockpit, Minimal, Paperclip, Start, GateWay-Studio). Sie besitzt den Bildschirm und gibt den
Werkzeugen Container; sie kennt kein Werkzeug beim Namen.

## Aufbau auf dem Bildschirm
1. **Kopf:** Titel „KI Gateway für KMU“, Untertitel „KI-Power. Mit Kontrolle.“, der Satz „Eine Aufgabe. Eine Oberfläche.
   Nachvollziehbare Kontrollpunkte.“, der Ablauf als fünf Kästchen (Aufgabe eingeben → Schutz prüfen → Entwurf erzeugen →
   Ergebnis prüfen → selbst entscheiden.) und rechts oben die Grafik. Der Ablauf zeigt nur; er ist keine Schaltfläche.
2. **Werkstück (Mitte):** Verben des Objekts oben, darunter das Werkzeug des Objekts. Beim Start ist das das KI GateWay
   (Sammlung). Nachweis-Werkzeuge (`slot: nachweis`) zeigt die Shell nicht daneben.
3. **Gespräch (unten):** das Werkzeug „Gespräch“ in einer Zone mit begrenzter Höhe (36 % der Bildschirmhöhe), die man
   hochscrollen und in der Höhe ziehen kann.

## Was die Shell zeigt, und was nicht
- **Zeigt:** den Ablauf und die Oberfläche des KI GateWay (Vorgänge, Dateien, Regeln, Prüfung, Verlauf) in dem Design.
- **Zeigt nicht:** Folien, Timer, Präsentationsmodus, Sprechernotizen, den Demo-Bereich mit der SEDRA-Adresse. Das wäre eine
  zweite Shell für die Präsentation (siehe `04_OFFENES.md`). Die Vorlagen dafür (V4a/V4b-Texte, Dashboard-HTML) liegen nicht
  im Archiv.

## Wie sie eingebunden wird
Die Shell wird wie jede andere über `local_config/uix.yaml` gewählt (`uix: {shell: gateway-kmu}`) oder im Umschalter unten
rechts (Eintrag „KI Gateway für KMU“). Die Abnahme (`benchmarks/uix_check.py`) kennt ein Profil für sie.
