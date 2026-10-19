# Shell „KI Gateway für KMU“

**Wofür:** Das KI Gateway im Design der Präsentation „KI Gateway für KMU · B6 · SEDRA“ (Designvorschlag V4.2 von Klaus, 19.10.2026).
Drei Zonen, die stehen bleiben: der Kopf mit dem Ablauf (Aufgabe eingeben → Schutz prüfen → Entwurf erzeugen → Ergebnis prüfen →
selbst entscheiden), das Werkstück in der Mitte, das rollt, und das Gespräch unten mit dem Griff des Werkzeugs (Höhe ziehen,
`--talk-h`). Rollt das Werkstück, wird der Kopf kompakt (Titel und Ablauf bleiben); oben angekommen wächst er wieder.

**Gestaltung:** Farben, Schrift und Abstände kommen aus den Tokens `--kmu-…` in `ui/tokens.css`; Mischungen (Glas, Licht) per
`color-mix` aus denselben Tokens, kein Hex in dieser Shell. Die Werkzeuge in dieser Shell bekommen dieselben Farben über die
Umlegung in `shell.css`; an ihnen ändert sich nichts. Die Schaltflächen des Vertrags (`.s-btn`) und die Eingabefelder sind in dieser
Shell als Pillen bzw. dunkle Felder mit Akzentrand gestaltet – auch in den Werkzeugen, weil die Shell den Bildschirm besitzt.

**Bilder:** zwei Folienbilder der Präsentation, verkleinert und auf 256 Farben gebracht (Lizenz laut Klaus geklärt, 19.10.2026):
`kmu-hero.png` (Folie 11, Bogen mit Schild, 1280×720, rechts im Kopf mit weichem Verlauf) und `kmu-glow.png` (Folie 4, die Kugel,
560 px, schwach hinter dem Werkstück). Sie liegen im Shell-Ordner, weil der Server nur Dateien direkt darin ausliefert.
Die Quellbilder in voller Größe: `runtime/assets/kmu-praesentation/`.

**Ablauf:** nur zum Lesen – er ist der Messwert der Abnahme (`uix_check`, Profil `gateway-kmu`), keine Schaltfläche.

**Nachweise:** Werkzeuge mit `slot: nachweis` zeigt diese Shell nicht daneben; das Gateway hat seinen Überblick selbst.
