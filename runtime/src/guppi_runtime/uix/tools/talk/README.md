# Werkzeug `talk` – Gespräch

Das eine Eingabefeld des Cockpits. Antwort, Auftrag, Navigationsphrase und „einmal ja“ laufen hier zusammen; eine Zusage im Gespräch erzeugt genau dasselbe Audit wie der Knopf an der Werkbank (COCKPIT_MODUL_v1 Regel 1 und 2).

Es ruft `/api/chat/reply`; Entscheidungen beantwortet es über die Shell, nie selbst. Ein „ja“ oder „nein“ liest die
wartenden Entscheidungen frisch (Build 19) – es beantwortet die angekündigte, sonst die einzige; warten mehrere, fragt es nach.

**SEDRA bewegt sich in der Oberfläche (Build 19).** Das Modell hat Werkzeuge zum Öffnen (`open_place`, `open_object`), zum
Nachsehen (`list_actions`) und zum Vorschlagen (`propose_action`, `propose_intent`). Keines tut etwas: die Antwort trägt
`ui_actions`, und dieses Werkzeug zeichnet dafür Knöpfe unter die Antwort. Erst der Klick öffnet das Fenster oder ruft
`POST /api/actions` – denselben Weg wie jeder Werkzeugknopf, mit Warnsatz (`confirm`) und Gate darunter. Hat der Captain im
selben Satz selbst ums Öffnen gebeten („öffne …“), ist das die Freigabe: das Fenster geht gleich auf. Sätze wie „kannst du
mir ein Fenster für Maschinenraum öffnen“ erkennt schon die Ortskunde (`ui/places.js`, `wantsOpen`) – ohne Modell.

**Objekttypen:** – (panel)
**Art:** `panel` · **Vertrauen:** CORE · **Version:** 1.1.0

## Routen (Allowlist im Manifest)
- `POST /api/chat/reply`
- `GET /api/decisions`
- `POST /api/actions` (Knopf unter einer Antwort)
- `POST /api/intent/create` (Knopf „Als Vorhaben anlegen“)

Alles andere beantwortet der Server mit `403 tool_route_not_allowed` und schreibt `UIX_TOOL_DENIED` ins Audit.

## Stufe 4 bis 6
- **Verlauf vom Server** (`verlauf.js`): nach Neuladen oder Shell-Wechsel steht das Gespräch wieder da; im Browser liegt nichts.
- **„Leeren“** fragt im Knopf nach: erster Klick „Wirklich leeren?“ (4 s), zweiter Klick leert – auch auf dem Server; Esc bricht ab.
- **Modellauswahl:** oben immer die Gruppe „Geprüft schnell ✓“ (grüne Ampel), darunter die übrigen; kein Knopf „Grüne zuerst“ mehr.
- **Aus dem Wissen:** „Ins Gespräch“ setzt Kennung und Stelle ins Feld; schaltet die Shell `gespraech.wissen` ein, antwortet das Gespräch
  aus dem Wissen, Kennungen [W…] sind Verweise. Eine Antwort mit Personenbezug bleibt lokal (`nurLokal`) und geht in keinen Cloud-Weg.
- **Höhe:** hat die Shell einen eigenen Griff (`shell.gespraechGriff`, Cockpit), zeichnet das Gespräch keinen zweiten.

## Ereignisse
- sendet: object.open, talk.mode, wissen.auswahl
- hört: talk.context, decision.pending, decision.answered, live.line, object.open, wissen.auswahl

## Spec
`node -r ../../../../../tests/uix_spec_dom.js test.spec.js` (Leeren, Cloud-Weg, Körper der Antwort).

## Abnahme
`python benchmarks/uix_check.py --tool talk` – mountet das Werkzeug in einen leeren Container, prüft Inhalt, Handlungen,
Aufräumen beim `unmount` und dass nur erlaubte Routen gerufen wurden.

## Bildschirmfoto
`docs/shots/cockpit/talk.png`
