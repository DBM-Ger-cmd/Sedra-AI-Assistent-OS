# Prüfung: Minimalpaket mit nur vier Oberflächen (02.11.2026)

Anlass (Captain): Der Stick (Minimal) bringt nicht alle Oberflächen mit; das ist zu prüfen. Geprüft wurde, was passiert, wenn nur die Shells und Werkzeuge der
Stick-Liste (`runtime/benchmarks/stick_liste.txt` auf dem Branch `claude/usb-stick-minimal-3c1b19`) im Paket liegen.

## Aufbau der Probe
- Paket mit `stick_paket.py` aus dem Stand von `main` (7cf6094) und der Stick-Liste, ohne die `bestand`-Zeilen (Engine, portables Python): 592 Dateien, 4 MB.
- Shells im Paket: `cockpit`, `harness`, `paperclip`, `fisch` (Translator). Werkzeuge: `uebersetzer`, `nachrichten`, `transkript`, `rekorder`.
- Der Server lief aus dem Paket (`PYTHONPATH=<Paket>/runtime/src`) mit leerem Arbeitsbereich; Browser-Prüfung mit Playwright (Konsole, HTTP-Antworten ab 400, sichtbarer Text).

## Befunde
1. **Start ohne `--shell` scheitert.** Ohne Angabe (und ohne `uix.yaml`) ist die aktive Shell `start`, die nicht im Paket liegt: die Seite meldet
   „Keine Shell verfügbar: start“ (`uix/ui/loader.js`). Betroffen: `START_SEDRA.bat --uebersicht`, `--gewaehlt`, jeder Start ohne gewählte Oberfläche.
   Mit `--shell harness|cockpit|paperclip|fisch` lädt jede Shell ohne Konsolenfehler.
2. **Harness:** Startmenü nur 5 Apps (Übersetzer, Transkripte, Rekorder, Nachrichten, Einstellungen) statt 40; die Zeile „Oberflächen“ listet automatisch nur die
   anderen mitgebrachten Shells (cockpit, fisch, paperclip). Die Statuszellen GPU, RAM, Scheduler und Zustand führen auf „kein Werkzeug“
   (ihre `gauge-*`-Werkzeuge fehlen); Freigaben funktioniert.
3. **Cockpit:** meldet beim Start `400` auf `/api/objects` (nicht gegen das volle Paket geprüft). **Paperclip:** die Navigation zeigt Einträge
   (Issues, Ziele, Organigramm, Agenten, Kosten …), deren Werkzeuge nicht mitkommen. Beide waren nicht vollständig durchgeklickt.
4. **Translator** ist vollständig: er braucht genau die vier mitgebrachten Werkzeuge.
5. Werkzeuge ordnen sich nach Objekttyp zu; ein Shell-Manifest nennt sie nicht (`needs` kennt nur `ui`). Ein fehlendes Werkzeug fällt darum erst im Gebrauch auf.

## Folgerung
Auf dem Stick sind nur Harness und Translator wirklich benutzbar. Vorschlag: (a) der Server nimmt die erste vorhandene Shell, wenn die gewünschte fehlt;
(b) Statuszellen ohne Werkzeug sind nicht klickbar oder sagen es; (c) Entscheidung des Captains, welche Shells auf den Stick kommen
(Vorschlag: Harness und Translator; Cockpit und Paperclip nur zusammen mit ihren Werkzeugen).

## Stand der Stick-Arbeit
Der Branch `claude/usb-stick-minimal-3c1b19` (4 Commits: Plan, Stick-Paketbau `stick_paket.py`, Stick-Liste, `local_paths.py`-Änderung mit Tests) liegt nur auf diesem
Rechner und steht 17 Commits hinter `main`. Der alte Branch `origin/plan/usb-stick-minimal` (ein Commit, Plan vom 30.10.) ist überholt.
