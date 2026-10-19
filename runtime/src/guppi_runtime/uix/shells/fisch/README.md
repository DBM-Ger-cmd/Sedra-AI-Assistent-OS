# Shell „Fisch“

Aus dem Translator-Fisch-Konzept v0.1 (19.10.2026): ein großes Goldfischglas, ein Goldfisch, die Eingabe als **Wolke**, Antworten als
**Blasen**, vier Modi – **Übersetzen · News · Aufnahme · Transkript**. Klein, freundlich, lokal. Der Fisch hat Zustände: ruhig schwimmend,
hörend (Blick zur Wolke), denkend (mehr Blubber), antwortend (größere Blasen), News (mehrere Blasen).

**Wie sie den Vertrag abbildet:** Die Shell besitzt den Bildschirm und gibt Container; sie kennt kein Werkzeug beim Namen. Jeder Modus
ist ein Objekt (`uebersetzung:wolke`, `nachrichten:brief`, `aufnahme:rekorder`, `transkript:alle`); wer es zeichnet, sagt die
Registrierung (Werkzeuge `uebersetzer`, `nachrichten`, `rekorder`, `transkript`). Der Satz aus der Wolke geht als `frage` in das
Objekt des Modus – das Werkzeug macht daraus Übersetzung, Interessen oder Suche; im Modus Aufnahme wird er der Titel im ersten
Feld der Blase (das Pult bleibt stehen, nichts wird neu gemountet). Nachweise (`slot: nachweis`) stehen in der Blase als Seitenspalte
(`data-slot="nachweis"`); die Handlungen des Werkstücks über der Blase (`data-verbs`). Das **Gespräch** ist eine Schublade wie in
Paperclip („Mit SEDRA sprechen“); Strg+K springt zur Wolke, Alt+S ist der Umschalter. Der Modus bleibt je Browser gemerkt.

**Gestaltung:** Tokens `--fisch-…` in `ui/tokens.css` (hell am Tag, nachts dunkler Raum mit leuchtendem Glas); die Werkzeuge in der
Blase folgen den allgemeinen Tokens. Fisch, Glas, Wolke und Blasen sind CSS-Zeichnungen – keine Bilddatei, keine fremde Figur.
Bewegung nur `transform`/`opacity`; `prefers-reduced-motion` schaltet ab.

**Herkunft der Werkzeuge:** Übersetzer und Nachrichten aus dem Translator-Fisch-Konzept (Prompt-Spec, Datenmodell); Transkript aus
LocalScribe (Exporter, Suche) und VoiceBrief (Record-Regeln); der Rekorder ist Kern (`sprache/`, `ui/sprache.js`) und steht jeder
Shell offen. Sprache → Text macht der Provider des Rechners (whisperx, whisper) – fehlt er, heißt das so. **SEDRA-KI-Zugang:**
„Erkenntnisse mit SEDRA“ im Transkript (Zusammenfassung, Entscheidungen, offene Fragen, Aufgaben → Auftrag), „An den Übersetzer“.

## Abnahme
`python benchmarks/uix_check.py --shell fisch` · `test_uix_shell_fisch`
