# 02 – Design

## Farben
Gemessen am gerenderten Folienbild (Pixelmessung, nicht geschätzt). Die Werte stehen als Tokens in `ui/tokens.css`
(Block `--kmu-…`) und in `assets/design-ableitungen.json`.

| Token | Wert | Verwendung |
|---|---|---|
| `--kmu-bg` | `#0d174e` | Folienhintergrund, Grund der Shell |
| `--kmu-deep` | `#080d33` | Schlussfolie, Kopf-Verlauf, Gespräch |
| `--kmu-box` | `#243269` | Kästchen des Ablaufs |
| `--kmu-box-2` | `#1a2862` | innere Flächen (Werkzeuge) |
| `--kmu-line` | `#2c3d86` | feine Linien |
| `--kmu-accent` | `#53ddd0` | türkiser Akzentstrich, Pfeile |
| `--kmu-title` | `#ffffff` | Überschriften |
| `--kmu-sub` | `#b4c2ec` | Untertitel |
| `--kmu-text` | `#e8edff` | Fließtext |

Die Werkzeuge der Shell bekommen diese Farben über die Umlegung der bekannten Tokens in `shell.css` (`--bg`, `--panel`,
`--text`, `--accent` usw. zeigen auf die `--kmu-…`-Werte). An den Werkzeugen selbst ändert sich nichts.

## Schrift
- Titel: 34 px, fett (`--kmu-titel-groesse`). Untertitel: 17 px (`--kmu-sub-groesse`).
- Fließtext und Werkzeuge: die Schrift der Oberfläche (`--font`).
- Die Folienschrift ist **nicht eingebettet** und nicht gesichert. Die Shell nutzt die Oberflächenschrift; eine Folienschrift
  wird erst eingebunden, wenn ihre Lizenz geklärt ist.

## Raster und Elemente
- Kopf mit 28 px oben, 32 px seitlich; Werkstück und Gespräch mit 32 px seitlich (auf dem Handy 16 px).
- Ablauf: Kästchen mit 10/14 px Innenabstand, Radius der Oberfläche, Pfeil in Türkis.
- Gespräch: maximal 36 % der Bildschirmhöhe, Rollbalken, in der Höhe zu ziehen.
- Unter 760 px Breite entfällt die Grafik im Kopf.

## Grafik
- `shell/kmu-grafik.png`: Ausschnitt aus Folie 1 der neueren PDF-Fassung (Schild mit Datenstrom und Balkendiagramm),
  gerendert mit 1,6-facher Auflösung. Das Bild ist dekorativ (`alt=""`).
- `assets/kopf-ausschnitt-1x.png` und `-2x.png`: derselbe Ausschnitt, für Bildschirme mit doppelter Dichte in der 2x-Fassung.
- `assets/folie-NN-bild-1.png`: die eingebetteten Bilder der Folien 1, 2, 4, 9 und 11 unverändert.

**Herkunft und Lizenz:** Die Bilder stammen aus der Präsentation „KI Gateway für KMU · B6 · SEDRA“ (neuere Fassung,
`KI-Gateway-fur-KMU-B6-SEDRA-2.pdf`). Die Lizenz ist laut Klaus geklärt (19.10.2026). Die Bilder tragen keine eingebettete
Urheberangabe; diese Herkunft ist die einzige Quelle.
