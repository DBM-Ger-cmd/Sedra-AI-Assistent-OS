# Build 22: Der Umschalter in jeder Shell, Lesbarkeit, Korpuslauf (15.10.2026, Ticket B6-G-04)

**Klaus, 15:11:** *„Kannst du noch das UIX der Shell anpassen, das Design verbessern sowie die Bedienung und die Lesbarkeit der Schriften
und Beschreibungen – und es muss in jeder Shell eine schnelle Möglichkeit geben, die Shell zu wechseln oder auf die Übersicht der
Shell-Hauptseiten zurückzukommen.“* Dazu der Korpus v0.2 (Torsten) und seine Rückmeldungen vom 13.10.

## 1. Der Umschalter (`ui/wechsel.js`, `ui/wechsel.css`)

Ein kleiner runder Knopf unten rechts, **in jeder Shell derselbe** – auch in Shells aus Vorgabe und in GUPPI XP: er gehört zur Seite
(`desk.html`), der Loader hängt ihn nach dem Start der Shell an; eine Shell kann ihn nicht abschalten. Er öffnet ein Menü mit:
- **Übersicht der Oberflächen** (wie `START_SEDRA` ohne Argument: nur für diesen Lauf, die Wahl in `uix.yaml` bleibt),
- **Wechseln zu …** jede andere Oberfläche (Beschreibung dabei; die eigene steht nicht zur Wahl; Wahl wird gespeichert, Seite lädt neu),
- **Darstellung** Klar / Nacht und **Schrift** Normal / Groß (im Browser gemerkt – Anzeige-Komfort, kein Runtime-Zustand).

Tastatur: **Alt+S** öffnet und schließt, **Esc** schließt, Tab läuft durch die Einträge. In der Übersicht selbst gibt es ihn nicht – sie ist die Wahl.
Er spricht nur über `sedraApi.api` (Token-geprüft) und nur zwei Routen: `GET /api/uix/modules`, `POST /api/uix/shell` (Audit `UIX_SHELL_VISIT` / `UIX_SHELL_CHANGED`, wie bisher). Nichts läuft ohne Klick.

## 2. Lesbarkeit (`ui/tokens.css`, Werkzeuge `gateway` und `regelbuch`)

| Was | vorher | jetzt |
|---|---|---|
| Schriftstufen | xs 10,5 · small 11,5 · 13 · l 15 · head 16 · xl 20 px | **xs 11,5 · small 12,5 · 14 · l 16 · head 17 · xl 22 px** – eine Stufe größer; Shells und Werkzeuge folgen, weil sie nur Stufen kennen |
| Schrift „Groß“ | – | `html[data-scale="gross"]`: 13 · 14 · 16 · 18 · 19 · 24 px, Leiste und Gespräch wachsen mit |
| Zeilenabstand | 1,45 | 1,5 (Grundtext), 1,45 für Hinweise (`.s-muted`) |
| Kontrast Hinweistext | `--muted #66717f` (4,5:1) | `#5b6673` (≈ 5,6:1 auf Weiß) |
| Werkzeug `gateway` | Hinweise in xs, Kästchen klein | Beschreibungen in „small“, Formularfelder in der Grundstufe, Kästchen 16 px mit Abstand, Stationen deutlicher getrennt, Fakten als Raster, Tabelle mit Zeilenlinien, Entwurf mit Zeilenabstand 1,65 |
| Werkzeug `regelbuch` | Kopf mit Dateinamen, Pille rechts abgeschnitten | Kopf „Policy … · Regelwerk v0.1 · 16 Regeln“, Cloud-Pille umbricht, kein waagerechter Überlauf |

Bildschirmfotos: `docs/shots/build22/` (Umschalter in Studio, Cockpit, Minimal, Paperclip; Nacht + Groß; Leitfaden; Frag SEDRA).

## 3. Korpuslauf (G-06, Ticket B6-G-01)
`benchmarks/b6_korpus_gegen_guppi.py` liest jetzt auch den **Korpus v0.2 (CSV + inputs/)**. Lauf auf den 15 Fällen gegen
`b6-datenregeln-0.1`: 10 PASS, 4 FAIL, 1 NOT_TESTABLE; die drei als „kritisch“ markierten Abweichungen (TC-004, -008, -013) beruhen
auf Quellenregister, Versionskonflikt und unbekannter Quellenklasse – das kennt die Prototyp-Matrix nicht (Option C). TC-003 weicht wegen
R-01 ab (Cloud nach Pseudonymisierung ist im Regelwerk v0.1 gesperrt). Bericht: `MESSUNG_KORPUS_v0.2_GEGEN_GUPPI_b6-datenregeln-0.1_2026-10-15.md` (B6-Projekt).

## 4. Abnahme (Linux, Python 3.13)

| Was | Ergebnis |
|---|---|
| `test_uix_flows` (8: Studio Flow, Minimal, Paperclip, Cockpit, Umschalter in Cockpit mit Übersicht/Nacht/Groß/Alt+S/Esc und kein waagerechter Überlauf, Umschalter in der Studio-Shell) | 8/8, dreimal hintereinander |
| `test_uix_contract` (30; `desk.html` lädt nur `/uix/ui/`, kein Inline-Skript, nur Token) | grün |
| `uix_check` Cockpit / Minimal / Paperclip / GateWay Studio / GUPPI XP | 30/30 · 30/30 · 30/30 · 30/30 · 3/3 |
| Volle Suite | 2.129 Tests, 1 Fehler = bekannter Umgebungsfehler `library_not_built`, 49 übersprungen (425 s) |
| Nicht gelaufen | Windows; echtes Modell |

Ein Hinweis zur Stabilität: der Browser-Test des Studio Flow brauchte beim Zurückkehren zur Liste zweimal einen zweiten Anstoß
(`object.open` auf die Sammlung, wenn der Reiter des Vorgangs noch vorn steht); der Test stößt jetzt bis zu viermal an. Das ist ein
Testdetail, keine Bedienlücke – in der Oberfläche steht der Weg zurück im Baum und in den Orten.

## 5. Bewusst nicht
Kein neues Shell-Layout, keine neuen Farben außer dem Kontrast des Hinweistexts; der Rahmen und die Shells selbst sind unverändert
(der Umschalter liegt darüber). Der Dateiname des Regelwerks bleibt im Tooltip des Regelbuchs.
