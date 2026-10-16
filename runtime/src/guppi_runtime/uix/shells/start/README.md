# Shell: Start

Der Einstieg. Hier wird die Oberfläche gewählt, eine eigene aus der Vorlage angelegt oder eine von außen vorgelegt.

- **Standard**, solange `local_config/uix.yaml` keine Shell nennt. Sobald der Captain eine nimmt, startet SEDRA direkt dort.
- **Zurück** hierher: in jeder Oberfläche im Werkzeug „Module“ → „Start“ → „Diese Shell nehmen“.
- **Öffnet keine Objekte.** Sie zeigt die Auswahl, das Gespräch unten und – sobald eine wartet – die Entscheidungen rechts
  (das Werkzeug `decisions`, dieselbe Antwortroute wie überall). Wer ein Objekt will, bekommt den Satz, wo es sich öffnet.
- Ein Bild je Oberfläche kommt aus `shells/<id>/preview.png`, wenn es eines gibt; sonst steht „kein Bild“.

Die Abnahme (`uix_check --shell start`) weiß aus dem Manifest (`provides` ohne `dock`/`windows`), dass diese Shell keine
Werkzeuge zu Objekten zeigt, und prüft nur, was sie verspricht: Laden, Gespräch, Konsole, Allowlist, Retro.
