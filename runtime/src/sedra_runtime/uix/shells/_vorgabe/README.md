# Vorlage: eine Shell aus einer Vorgabe

Kopieren nach `local_config/uix/shells/<id>/`, in beiden Dateien `id` auf den Ordnernamen setzen, in `uix.yaml` wählen (oder im
Einstieg „Diese Oberfläche nehmen“). Kein JavaScript: der Rahmen (`ui/frame.js`) baut aus `shell.vorgabe.yaml` den Bildschirm –
Zonen, Werkzeuge, Verben, Marken, Gespräch, Entscheidungen, Palette, Layout-Merken. Eine `shell.css` daneben darf Farben und
Abstände der `.fr-…`-Flächen nachstellen.

Abnahme: `python benchmarks/uix_check.py --shell <id>` – eine Shell aus Vorgabe wird vollständig geprüft (kein „nicht geprüft“),
weil das Prüfwerkzeug ihr Profil aus der Vorgabe ableitet.
